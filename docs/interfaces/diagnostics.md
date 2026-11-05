# Fault event와 DTC 계약

2026-11-03. **계약 v0.1 / TBD-08 최종 수용 전 OPEN**.
M9-2의 집계/store에 M9-3 SpeedRequest·NormalStop·Coordinator 관측 adapter를 연결했다.
SimpleVehicle 논리 시간의 정상 정지/HV-off·speed 입력 누락 및 SD-1001 복구/clear/재고장을 실제 owner 경로와 연결했다.
CARLA30km/h fault matrix·native 3-ECU/wall owner 진단 통합·전체 monitor 수용은 **NOT RUN**이다.
범위는 Host 기능 SIL의 SYS-DIAG-001, ARCH-DIAG, IF-FAULT-EVENT다.
전체 UDS/OBD 서비스나 표준 DTC 번호를 정의하지 않는다.

## 현재 구현 경계

`central/diagnostics/diagnostics.hpp/.cpp`는 순수 집계·유한 SPSC 큐와 writer용 Recorder,
`diagnostics_journal.hpp/.cpp`는 Linux local-filesystem adapter다.
[집계/store 근거](../test-plan/evidence/m9_diagnostics_component/README.md)를 따른다.
별도 `control_diagnostics.hpp/.cpp`가 실제 Central owner의 snapshot을 읽고 큐에 발행한다.
집계/store는 controller에 의존하지 않으며 adapter도 actuator/permission을 변경하지 않는다.

Queue는 producer 한 개당256 events다. 기본 ledger 한계는 events512 / records64 /
occurrences128 / clear requests64이며 각 ledger 한계는1–4096로 명시적으로 설정한다.
한계·store ID·schema/registry revision은 bootstrap manifest에 영속 저장한다.
`Kind::Session`은 trusted global session 전환이며 더 큰 application Epoch가 필요하다.
개별 owner의 INIT 통보는 Observation으로 연결하고 동일 epoch의 새 global Session으로 넣지 않는다.
Numeric component/subject/profile/reason·SYS/IF bit dictionary와 실제 config/source hash의
run manifest 연결은 hook 통합의 책임이다. 현재 내부 encoding을 CAN/owner-wire로 사용하지 않는다.

Writer의 `Recorder::drain`은 queue health를 먼저/나중에 확인해 drop을 진단 불완전으로
반영한다. M9-3 logical harness의 Central owner 호출부를 연결했다. 별도 background writer는
아직 없고 SIL 시험은 실행 뒤 또는 논리 owner step 사이의 별도 writer 구간에서 drain/commit한다. RT owner는 bounded publish만
호출해야 한다. 큐를 직접 소비하면 동일 health 검사 책임이 있다.
Rejected mutation·capacity·저장 오류는 sticky health와 가능한 경우 durable `incomplete`
marker로 남긴다. 저장 장치가 실패한 동안 marker 자체의 영속성도 보장하지 않는다.
SD-5001 event를 임의 producer/시각으로 합성하지 않으며 실제 gap event 발행은 hook에 남긴다.

저장 파일은 `manifest`, `journal`, `commit`, `lock`이다. Committed frame은 sequence·길이·
CRC32로 검사한다. 미완료 tail은 commit offset 밖에 원형대로 격리하며 해당 store는
read-only/incomplete다. 자동 truncate·repair·용량 회수는 없다. 명시적 reconciliation은 후속이다.
CRC는 accidental corruption 검사이며 외부 변조 인증이나 Target durability 수용이 아니다.

`Proof`와 evidence event 참조는 trusted monitor adapter의 qualification 선언이다.
집계기는 code·key·occurrence·session·source 순서를 검사하며 실제 Brake 응답식/ACK mask를
다시 계산하지 않는다. `ServiceEvidence`의 원본 stream 유효성·dispatch 억제 여부도 trusted
caller 책임이다. 집계기는 stationary 값·원본 age30ms/skew20ms·실제 session enable을 확인한다.
모든 code별 실제 predicate는 해당 hook의 시험으로 추가 검증해야 한다.

## SpeedRequest·NormalStop 연결

`SpeedRequestFaultObservation`은 최초 fault·PI reason·application epoch/enable·실제
판정 시각·그때의 원본 input/PI sample을 보존한다. `step_derived` expiry overflow도 같은
경로를 쓴다. 후속 step/poll로 최초 원인을 갱신하지 않으며 성공한 새 INIT만 snapshot을 비운다.

NormalStop은 최초 고장과 후속 최초 ClockError 두 slot, Braking/HandoffPending/
PowerDown/Complete 네 phase slot을 보존한다. 원본 request, 실제 pending StopLease,
적용 config·phase 기점과 마지막으로 보존한 Drive/Brake/Power input을 함께 남긴다.
Snapshot capture는 bounded value copy이며 파일 I/O·callback·추가 debounce를 수행하지 않는다.
Observer는 이 자료를 같은 Central owner에서 읽는다. 다른 thread가 snapshot을 직접 읽는 API가 아니다.

Coordinator는 관리 release 사이에도 실제 관측 시각으로 NormalStop의 원래 만료 검사를
poll한다. 원본 request의50ms inclusive age 또는 exclusive expiry 위반을 관측하면
RequestLost/SD-1105와 보호 선택을 연결한다. Poll은 control tick·새 grant/child 발행·
last_tick 갱신이 아니며30ms control deadline을 연장하지 않는다. 새로운 물리 입력을
취득했다고 표시하지 않고 저장된 evidence의 원래 취득 시각을 유지한다.

| 관측 | 이벤트와 시각의 의미 |
| --- | --- |
| Speed/Stop 최초 판정 | `Fault`의 Detected는 원본 detector call 시각. Permission/UpstreamProtection은 원인 미상의 Observation이며 별도 root DTC로 꾸미지 않음 |
| NormalStop phase | 원본 state transition과 exact StopLease·fresh measured wheel/torque/pressure/Off bus를 Observation/Actual로 기록. PowerDown의 Acknowledged는 trusted handoff 수용 시각 |
| Coordinator `protect()` true | `ProtectionAck`와 Acknowledged에 callback 결과 관측 시각. Async port는 이미 발생한 Zone ACK를 확인하므로 이 시각을 Leaf 선택 시각으로 사용하지 않음 |
| Local owner 보호 | 단일 thread 논리 harness의 기존 `leaf-protection-selected` / `zone-protection-ack` 원본을 cursor로 회수해 Selected/Acknowledged에 각각 기록. INIT 전 epoch도 보존하고 재관측으로 retimestamp하지 않음 |
| 보호 후 Actual | 실제 Central current Drive/Brake receiver에서 동일 epoch·LocalProtection/FailSafe·finite·age30ms/skew20ms를 검사. abs(torque)≤1Nm·pressure≥1MPa를 처음 함께 관측한 wheel/torque/pressure3개를 원본 acquisition으로 기록 |

Local selection과 Actual은 같은 root event/occurrence를 참조한다. Front/Rear·각 Leaf의
role bit는 원본 log의 owner를 유지한다. Torque/brake 도달은 차량 정지나 HV-off가 아니다.
NormalStop 정상 완료의 measured 증거와 fault 대응 증거를 구분한다. 이 adapter는
clear를 자동 발행하지 않는다. SD-1001의 qualified `Passed`만 아래 predicate로 발행하며 다른 code의 복구 시험은 후속이다.

M9-3 dictionary v1은 component/producer ID1 Speed,2 Stop,3 Coordinator,4 Drive torque,
5 Brake,6 Power,7 Front,8 Rear,9 Steering,10 BMS,11 Drive wheel을 쓴다. Monitor1/2/3은
Speed/Stop/Coordinator, subject1–7은 wheel/stop cycle/handoff/protection/torque/pressure/power다.
Wheel sequence는 wire envelope가 아닌 acquisition timestamp cursor다. Local protection log의
sequence도 원본 log timestamp cursor이며 CAN wire sequence를 발명한 것이 아니다.
Requirement/interface bit0은 SYS-DIAG-001/IF-FAULT-EVENT다.

Speed native reason은 `(fault_tag << 8) | pi_reason_tag`다. Fault tag1–7은 기존
Session/Permission/Feedback/Source/Controller/Sequence/PropulsionSelection 순서,
PI tag0–9는 Normal/Uninitialized/Latched/SampleTime/Permission/Target/InvalidSpeed/
Epoch/SourceAge/Identity다. Stop tag0–10과 Coordinator tag0–12는 현재 enum 이름의
명시적 switch mapping이며 DTC code는 별도 switch로 선택한다. Registry에 없는 진단 root를 추측하지 않는다.

Opt-in `M4Config::diagnostics_run`은 현재 Normal/NormalStop/SpeedInputLoss의 논리 시간만
지원한다. 이 SimpleVehicle export의 Profile1은 기존 Host10ms allocation·20ms SpeedPI·radius0.3m·기본 stop config이며
Coordinator의 기존 external-release minimum tick1ms를 포함한다. Clock instance는 run ID다.
Input-loss는 global elapsed10s에 SpeedRequest argument만 누락한다. 실제 sensor/다른
traffic과 물리/EV는 계속한다. 이 case를 실제 CAN/전체 통신 단절이라고 부르지 않는다.
처음 도달한 보호 Actual 이후에도 물리 실행을 계속해 기존230ms 반응과 에너지 연속성을 판정한다.
[실행·독립 journal/원본 log 감사](../test-plan/evidence/m9_control_hooks/README.md)를 따른다.

현재 durable commit 확인은 비 RT writer에서 수행하며 write-clock `Recorded` 계측은 추가하지 않았다.
물리 model epoch는 원본 physical evidence에서 검증하며 adapter가 application epoch로
재발급하지 않는다. Production wire/spool·live writer와 실제 부하의 저장 latency는 후속이다.

## SD-1001 복구·명시적 clear

`SpeedRequestSuccessObservation`은 실제 성공한 step의 epoch/enable/issued 시각·원본
Drive input·최종 반환 request를 보존한다. Derived 경로도 반환된 두 clock의 root를 그대로
기록하며 expiry 생성 실패는 성공 snapshot을 발급하지 않는다. INIT는 이 native slot을 비운다.

진단 observer는 최초 SD-1001 occurrence를 global INIT 너머로 유지한다. 더 큰 epoch에서
native SpeedRequest가 healthy하고 실제 성공 request가 Coordinator의 accepted request와
정확히 일치해야 한다. 현재 Drive identity/acquisition도 성공 input과 같아야 하며 원본30ms,
normal readiness·normal armed·유효 permission을 모두 재검증한다. 이때 원본 wheel과
accepted command를 가진 `Actual/Proof::Input` 뒤에 이를 참조하는 `Passed`를 한 번 발행한다.
단순 입력 복원·INIT 요청/완료·새 feedback 하나·미수용 request는 복구 증거가 아니다.
`Passed`는 기존 count/generation과 이력을 남기며 차량 제어를 다시 초기화하지 않는다.

`speed_clear_evidence`는 실제 current input·전체 input health, NormalStop Complete,
management Stopped/power-off, 정상 dispatch 억제, 세 접촉기 open·bus≤30V를 확인한다.
원본 wheel≤.01rad/s·abs(torque)≤.1Nm·pressure100kPa–1.5MPa 및 age30ms/skew20ms도
필요하다. Caller는 이 immutable 증거와 **별도의 명시적 clear 의도**, key/expected revision,
request ID를 non-RT Recorder에 전달한다. 이동 중·stale/untrusted·revision 불일치·저장 실패는
clear 성공으로 응답하지 않는다. Clear 자체는 INIT/arm/permission을 호출하지 않는다.

실제 연속 SIL에서는 복원 후 보호 유지→INIT2 뒤 Passed/이력 유지→정상 정지/HV-off→명시적
durable clear→writer 재시작/tombstone 유지→INIT3 뒤 재고장 generation2를 확인했다.
[실행과 독립 감사](../test-plan/evidence/m9_speed_recovery/README.md)를 따른다.
Source emitter는 같은 run에서 계속 살아 있다. Emitter process 재시작 시 기존 occurrence를
채택하는 API·서비스 UI·원격 clear 인증·production background writer는 이 범위에 없다.
Writer 재시작은 clear 뒤 tombstone 보존을 검증했다. Clear 전 writer 재시작으로 Unknown이
된 미삭제 DTC의 source 재시험/service 연결은 후속이며 과거 proof만으로 clear하지 않는다.

## Zone/Leaf 소유자 수집 경계

`OwnerDiagnostics`는 Front/Rear와 Steering/Brake/Drive 각각의 독립 queue를 사용한다.
현재 논리 Host10ms speed profile에서 `owner_diagnostics_run`으로 켠다. Source producer는
Front20/Rear21/Steering22/Brake23/Drive24이며 기존 Central7과 구분한다. Global Session은
Central만 발행한다. 개별 owner INIT는 새 global Session으로 기록하지 않으며 source queue
sequence는 INIT 너머로 계속 증가한다. 실제 wire/spool publisher는 아직 아니다.

ZoneFeedbackMonitor는 최초 fault·scope/epoch/enable·native 판정 시각·current input/
last healthy input·healthy mask를 보존한다. Source/dependency/quality 검사는 기존 shared
feedback predicate를 따른다. ControlDeadline의 위반은 원래 gap/callback 기점+30ms+1ns,
검출은 실제 다음 detector call/completion이다. Clock rollback이 최초 원인을 덮지 않는다.
InputsUnavailable은 SD-2002, ControlDeadline은 SD-4002, 최초 ClockError는 SD-4001이다.
SourceProtection/GatewayProtection은 원인 미상의 Observation이며 새 feedback-loss DTC를
만들지 않는다. SequenceExhausted는 unmapped로 표시한다. Native gateway admission/send/
power 자체 원인의 publisher와 BMS/Power 자체 fault publisher는 후속이다.

Monitor4의 subject는 필요한 stream 중 unhealthy mask다(steering1/brake2/drive4/power8/
limits16). 누락 mask가 없으면 해당 scope의 전체 required mask(Front3/Rear28)를 쓴다.
한 detector fault를 필드 수만큼 복제하지 않는다. 다른 key의 복구 대기는 owner마다32개
고정 slot에 보존하고 기존 key를 조용히 축출하지 않는다. 같은 key의 재발은 최신 occurrence로
재시험하되 durable ledger의 이전 count/event는 유지한다. Capacity 실패는 sticky Gap이다.

Leaf wrapper는 **실제로 수용한** LeafRequest/CommandContext와 최초 original context expiry
검출을 기록한다. 기존 fault·실패 link·pending 보호가 이미 있으면 보호 전달 Observation이다.
자체 expiry일 때만 SD-2001이다. Monitor5/subject1을 쓰며 세 actuator component를 구분한다.
Native reason1은 wrapper context-expired이며 DriveGateFault enum을 임의로 붙인 값이 아니다.
Source identity의 token/sent/deadline은 원래 delivery envelope이고 command identity는
원래 VehicleRequest parent/child expiry다. Delivery 완료 기한과 수용된 명령 수명은 다르다.

SD-2002/SD-4002는 더 큰 global Epoch에서 해당 Zone monitor가 실제 정상 tick을 완료하고
전체 required input/current source/dependency가 다시 유효하며 global gate가 열려야 Passed다.
이는 해당 monitor의 복구이고 Central arm/차량 주행 허가를 대신하지 않는다. SD-2001은 새
epoch의 실제 명령 수용 뒤 healthy native control body/output과 살아 있는 context가 필요하다.
기존 child input dependency70ms·원본 command expiry·current body30ms를 각각 검사한다.
INIT만·단순 traffic 재개·오래된 body·닫힌 gate·faulted actor로는 Passed를 발행하지 않는다.
Clock은 아래 명시적 trusted 재검증 predicate로만 복구하며 일반 zone/leaf 복구로 넘기지 않는다.

복구 proof는 원본 source identity와 native 판정의 **Observation**이다. 비어 있는 measured0을
물리 Actual로 발급하지 않는다. 실제 토크/제동/차량 상태는 원본 physical evidence와 별도로
대조한다. Passed는 이력을 남기며 owner clear service/원격 clear 인증은 이 단계의 범위가 아니다.
[소유자 경계·실제 실행](../test-plan/evidence/m9_owner_sources/README.md)을 따른다.

`diagnostics_complete`는 연결된 collector의 queue/protocol health다. 모든 root 원인이나
전체 Zone/Leaf monitor coverage를 뜻하지 않는다. 알려진 보호 전달도 원인이 미상일 수 있다.

## Gateway·BMS·Power native 원인 수집

`native_fault_observation.hpp`의 유한 값 snapshot은 같은 owner에서 최초 native 원인과
정상 재시험을 보존한다. `native_diagnostics.hpp/.cpp`는 logical Host10ms Normal/Fault 및 BmsInputLoss/PowerInputLoss의
`native_diagnostics_run`으로 연결한다. Front30/Rear31/BMS32/Power33은 각 SPSC producer이며
monitor6 CommandGateway /7 RearPowerGateway /8 BMS /9 Power다. Global Session은 Central7만
발행한다. Collector는 global release 이후 같은 application epoch의 source만 읽는다.
Release 이전 startup root 수집·remote spool은 아직 이 경계에 포함하지 않는다.

CommandGateway는 실제 partial write 수, admission reason, 원래 context source/child expiry/
oldest dependency를 보존한다. RearPowerGateway는 최초 실패 stream mask(power1/permission2/
limits4/status8), 원래 Lifecycle parent와 네 stream identity/expiry를 보존한다. 보호 전달은
Observation이며 후속 poll의 로컬 continuity 표면을 새 root로 추정하지 않는다.
BMS·Power는 외부 보호 전달과 이후 실제 자체 fault를 별도 최초 slot으로 보존한다.
BMS snapshot에는 원본 다섯 입력의 값/identity·trip/release band·dwell/config가 있고,
Power에는 부분/누락 sensor·BMS gate·실제 phase 기점·threshold/timeout과 수용 request가 있다.
Power root identity는 수용한 **PowerRequest message**이며 expiry는 그 child expiry,
dependency는 원래 parent source다. 전체 trusted parent context라고 해석하지 않는다.
Typed snapshot의 scalar/config 전체는 현재 journal event schema에 직렬화하지 않는다.
Journal에는 native reason/detail/state·identity/시각과 sample identity Observation을 기록하며
정밀 scalar 판정은 실제 source component 시험으로 검증한다.

복구 대기는64개 고정 slot이며 다른 key를 몰래 지우지 않는다. 더 큰 global epoch/동일 enable,
현재 source healthy·normal gate, 원본 config의 source/dependency age와 body age·live expiry를
모두 요구한다. INIT나 traffic 복원만으로 Passed가 아니다. CommandGateway는 실제 완전
Front2/Rear1 전송, RearPowerGateway는 arm 이후 유효 네 stream과 실제 전송, BMS는
release-band dwell 뒤 Active/pending trip0, Power는 유효 actual sensor/BMS gate와 실제
Enable/Ready 재도달이 필요하다. Metadata Observation proof 뒤 기존 occurrence의 Passed를
발행하며 clear·권한 발급·plant reset을 하지 않는다. Clock은 아래 별도 trusted 재검증을 따른다.

새 SD-2101/3101/3201은 **code registry revision2**다. Binary transaction schema1은 유지하고
`FileJournal::initialize(..., limits, 2)`로 새 store를 명시적으로 만든다. 기존 기본 registry1을
자동 migration하지 않는다. Registry1에 새 code를 append하면 durable=false/incomplete이며
기존 watermark/manifest는 유지한다. Replay도 manifest보다 새 code를 거부하고 지원하지
않는 registry는 bootstrap하지 않는다. Component 검증과 Gateway 차량 SIL/독립 감사의
범위는 [native 원인 근거](../test-plan/evidence/m9_native_causes/README.md)를 따른다.

## BMS·Power 입력 손실 차량 연결

`M4Scenario::BmsInputLoss / PowerInputLoss`는 ECU runnable이 읽는 입력 사본에서만 BMS
`electrical` 그룹 또는 Power `pack_current_a`를 누락한다. Physical producer와 다른 ECU의
sensor channel·원래 source/identity/sequence·control period를 바꾸지 않는다. 누락/복원 event는
window 설정 시각이 아닌 **실제 affected body** 시각과 원래 acquisition/dependency를 보존한다.
Logical speed-loop/Host10ms 전용이며 다른 fault recipe와 혼합하지 않는다. 명시적 복원이
없으면 손실은 계속된다. Recovery를 요청하는 recipe는 복원이 recovery보다 앞서야 한다.

Run5001·registry2에서 elapsed10s 주입/10.2s 복원/20s 기존 link 교체·실제 INIT2를 사용한다.
SD-3101 InputsInvalid 한 건 또는 SD-3201 InputsUnavailable 한 건과 원본 local selection,
Zone ACK log·실제 토크/압력·stationary/HV-off·새 epoch source proof를 대조한다. 전달된
다른 ECU의 보호는 Observation이다. BMS local Passed는 release dwell/Active 확인이며
전체 차량의 주행 준비 완료와 구분한다. Power local Passed는 actual HV Ready가 필요하다.

`M4Scenario::NativeSensorFault`는 같은8-role 논리 차량에서 BMS trip mask9종,
Power charger-connected/contact feedback/bus-low3종 및 BMS170과의 동시3종을 검사한다.
값만 해당 ECU 소비 사본에서 바꾸며 원래 source/dependency·model identity를 보존한다.
복원만 한14s와 새 Release를 거친24s를 각각 실행한다. BMS pending trip이 먼저 Power를
정지시키면 실제 BmsInhibit를 전달 Observation으로 남긴다. 이후 contactor timeout이 실제
발생한 경우만 별도 SD-3201을 발행하며, 감시가 성립하지 않은 Ready bus-low를 합성하지 않는다.
[사전 조건과 최초 기대값 교정](../test-plan/native-sensor-matrix-protocol.md),
[원본·검증](../test-plan/evidence/m9_sensor_matrix/README.md)을 따른다.

복원만으로 native latch/gate가 풀리지 않는다. 영구 Power current 누락에서는 실제 current를
0으로 대체하지 않으며 WaitCurrent/shutdown_blocked 상태로 HV를 유지한다. 정지한 차량을
HV-off로 기록하지 않는다. 두 입력 손실 case의 차량 SIL이며 모든 BMS trip/Power contactor
고장 matrix를 완료한 것은 아니다. [차량 입력 손실 근거](../test-plan/evidence/m9_native_vehicle/README.md)를 따른다.

## 책임과 기존 계약

Local monitor와 기존 Central/Zone/Leaf owner가 검출·정상 출력 차단·보호 선택을 소유한다.
Diagnostics Manager는 그 결과를 집계한다. Logger의 queue, 저장 완료, Central 연결이나
DTC 생성 성공을 기다리느라 보호를 지연하지 않는다. RT owner에서 파일 I/O를 수행하지 않는다.

**원인 해소, 제어 latch 복구, DTC 이력 삭제는 서로 다른 연산이다.**
기존 새 Epoch의 trusted INIT/rejoin·입력/health/permission 재검증을 유지한다.
INIT는 DTC를 지우지 않고 DTC clear는 INIT·permission·RunLease·정상 출력을 발급하지 않는다.
다른 Zone의 재가입으로 해당 Zone의 고장을 복구하지 않는다.

기존 [안전 계약](../requirements/safety-requirements.md),
[시간 계약](../requirements/timing-requirements.md),
[30km/h NormalStop](../test-plan/carla-stop30-protocol.md)이 우선한다.
검출100ms 상한, 로컬 선택, Actual 도달, 차량 정지, HV-off는 별도 판정이다.
다음 tick 차단·보호 ACK만으로 물리 정지나 HV-off 완료를 기록하지 않는다.

## 코드와 검출기 연결

`SD-xxxx`는 아래 hexadecimal 값을 표시하는 프로젝트 내부 ID다. Enum의 정수값을
직접 DTC로 cast하지 않는다. `code + origin_component + monitor_id + subject_id`가
집계 key이며 `subject_id`에는 Zone/actuator/stream/방향을 넣는다.
동일 코드라도 Front/Rear, command/status, sensor/Actual을 합치지 않는다.
아래 cause는 관측된 검출 사유이며 실제 hardware root cause의 확정을 뜻하지 않는다.

| 코드 / 이름 | 원본 검출 결과와 범위 | 기록 시점 / 제어 영향 |
| --- | --- | --- |
| SD-1001 SPEED_INPUT_UNAVAILABLE | `SpeedRequestFault::Feedback / Source`; 원본 Drive Actual/wheel 누락·invalid·age·진행 오류 | 첫 latched 결과; 새 speed request 없음, 기존 보호 경로 |
| SD-1002 CENTRAL_CONTROL_FAILURE | `SpeedRequestFault::Session / Controller / Sequence / PropulsionSelection`, `NormalStopFault::SequenceExhausted` | 첫 latched 결과; 원본 controller reason도 보존 |
| SD-1101 STOP_BRAKING_TIMEOUT | `NormalStopFault::BrakingTimeout` | 해당 profile의 braking deadline 도달; FailSafe/protection_required |
| SD-1102 STOP_HANDOFF_FAILED | `NormalStopFault::HandoffExpired` 또는 `CoordinatorFault::Handoff` | 원본 lease 만료 또는 실제 인계 거절; pending 자체는 고장 아님 |
| SD-1103 STOP_EVIDENCE_LOST | `NormalStopFault::FeedbackUnavailable / StopEvidenceLost` | 최초 판정; 정지/hold 증거 상실을 별도 reason으로 보존 |
| SD-1104 STOP_SHUTDOWN_TIMEOUT | `NormalStopFault::ShutdownTimeout` | PowerDown 기점의 해당 shutdown deadline; Complete로 세지 않음 |
| SD-1105 STOP_REQUEST_LOST | `NormalStopFault::RequestLost` | 원본 stop request age/expiry 위반; fresh child로 연장 불가 |
| SD-2001 COMMAND_CONTINUITY_LOST | `AdmissionFault::CommandTimeout / CommandExpired / ContinuityLost`, Leaf `CommandUnavailable / ContinuityLost / StopLeaseExpired` | 해당 owner의 실제 latch; upstream/Leaf와 정상/stop authority를 subject/reason으로 구분 |
| SD-2002 FEEDBACK_UNAVAILABLE | `ZoneFeedbackFault::InputsUnavailable`, 수신기의 `Timeout / ContinuityError`, Leaf sensor unavailable/invalid | 원본 monitor의 fault 확정; 어느 stream의 어떤 검사인지 필수 |
| SD-2101 GATEWAY_DELIVERY_FAULT | 실제 Gateway `SendFailure / QueueOverflow` | partial write도 원래 native reason으로 기록; 물리 달성으로 해석하지 않음 |
| SD-3101 BMS_LOCAL_FAULT | 실제 BMS `InputsInvalid / Protection` | 원래 input issue/trip mask·dwell 보존; 외부 Protection 전달과 구분 |
| SD-3201 POWER_LOCAL_FAULT | 실제 Power startup/input/request/condition/contactor/precharge/bus/current/discharge fault | 실제 phase·부분 입력·timeout 보존; BmsInhibit/ContinuityLost는 보호 전달 |
| SD-3001 ACTUATOR_RESPONSE_FAULT | `BrakeMonitorFault::ResponseError`, `SteeringMonitorFault::TrackingError` | 기존 delay/rate/tolerance·fresh-sample dwell 확정 뒤 기록 |
| SD-4001 CLOCK_ERROR | 해당 scope owner/monitor의 `ClockError` | 최초 판정; 비교 불가능한 시각을 함께 표시 |
| SD-4002 CONTROL_DEADLINE | 해당 scope owner의 `ControlDeadline`, session participant `OwnerGap` | 최초 판정; job/owner와 적용 budget 명시 |
| SD-4101 SESSION_STARTUP_FAILURE | session participant/coordinator의 Timeout·Rejected·Initialize·Quiesce·Send·Continuity·CentralCommit 중 해당 native reason | trusted Attempt부터 최초 기록; 실제 새 전역 Release와 해당 source 정상 completion만 기동 복구 증거 |
| SD-5001 DIAGNOSTIC_RECORDING_GAP | event overflow, journal/store 오류, 손상·누락·같은 ID의 내용 변조 | 기록 경로 고장; 차량 보호 동작을 새로 발명하지 않으며 진단 완전성 판정은 실패 |

`None`, `NotInitialized`, 정상 startup wait, 정상 완료, 유효한 regen capability0,
정상 propulsion saturation은 confirmed DTC가 아니다. F02의 개별 invalid/duplicate/stale
command rejection은 **Observation event**로 남기고 last-valid age를 갱신하지 않는다.
그 결과 기존 timeout/continuity fault가 확정되면 해당 DTC를 생성한다.

상위 `CoordinatorFault::Stop / Management / Allocation / LocalProtection`,
`NormalStopFault::UpstreamProtection`, `SpeedRequestFault::Permission`, Zone/Leaf의
`UpstreamProtection / SourceProtection / GatewayProtection / CoordinatorRequest`는
가능하면 원본 fault occurrence에 연결한 **전파/보호 관측**이다. 이를 독립 root fault로
중복 집계하지 않는다. 원본이 도착하지 않으면 `cause_unknown`으로 남기며 정상이나 특정
DTC로 추측하지 않는다. 실제로 별개의 monitor가 command timeout 등을 검출한 경우에는
자신의 DTC도 보존하고 두 occurrence를 관계로 연결한다.

표에 없는 VehicleManagement/Drive/Host gate와 BMS/Power SequenceExhausted의 구체 fault는 이번 연결 범위에서
**UNMAPPED**다. 원본 enum/reason/event를 보존하고 scope가 진단 완료라고 주장하지 않는다.
그 경로를 통합하기 전 코드·검출/복구 predicate·시험 oracle을 추가한다. SD-5001은
unknown vehicle fault를 숨기는 catch-all 코드가 아니다.

## 검출 확정과 debounce

DTC 계층의 추가 debounce는 **0**이다. 보호를 이미 선택한 검출 결과를 다시 N회 또는
N ms 기다리지 않는다. 원본 monitor의 qualification을 그대로 따른다.

| 검출기 | 확정 기준의 원천 | 진단에서 유지할 경계 |
| --- | --- | --- |
| SpeedRequest | 현재 Actual/wheel 검증, `kSourceAgeNs=30ms`와 원천 진행 | age30ms는 inclusive; PI의60ms dependency를 현재 입력 gate로 대체하지 않음 |
| NormalStop | 생성 시 주입한 `NormalStopConfig`와 원본 stop authority | 기본 제동5s와 별도30km/h profile10s 구분; braking/shutdown `>=`, lease expiry는 exclusive |
| Zone/Leaf command monitor | 해당 session의 arm/enable·last-valid RX·source/expiry/timeout | reject/raw RX/child generation으로 검출 기점을 갱신하지 않음 |
| Brake/Steering response monitor | 실제 config의 delay/rate/tolerance·confirmation | 기본 confirmation60ms를 중복 적용하지 않음; cached polling은 새 확정 표본 아님 |
| Clock/deadline/continuity | 각 owner의 기존 즉시 latch | timestamp rollback에 음수 latency를 정상 값으로 보고하지 않음 |

상세 수치는 원본 config/profile과 source revision을 manifest에 보존한다. 이 문서는
timeout·제어 tuning·100ms 검출 요구·물리 응답 budget을 바꾸지 않는다.

## Event와 인과·시각

Event는 immutable하다. 검출 후 보호 ACK/Actual이 늦게 도착하면 원본 event를 고쳐 쓰지
않고 같은 occurrence를 참조하는 새 event를 붙인다. 고장 주입 정보는 Host 시험 증거다.
검출기는 injection enum이나 plant truth로 원인을 알아내지 않는다.

| 필드 묶음 | 필수 의미 |
| --- | --- |
| `schema_version`, `event_id` | v1; event ID=`run_id / producer_instance / event_sequence`. Sequence wrap 금지, process 재시작 시 instance 재사용 금지 |
| `occurrence_id`, `related_event_id` | 확정 episode ID=`origin run / producer instance / application epoch / monitor / occurrence_sequence`; 최초 fault부터 보호·Actual·clear까지 유지. 관계가 미상이면 null+reason |
| `kind` | Observation, FaultConfirmed, ProtectionSelected, ProtectionAcknowledged, ActualObserved, ConditionPassed, ConditionUnknown, SessionInitialized, ClearRequested, ClearCommitted, RecordingGap, StartupAttempt. 구현의 `Fault/Passed/Unavailable/Session/Gap/Attempt`과 clear transaction에 각각 대응 |
| `origin_component`, `monitor_id`, `subject_id`, `code`, `native_reason`, `severity` | 관측 owner/대상·코드·원래 enum/reason. Severity는 원본 정책/영향 설명이며 DTC가 보호 우선순위를 변경하지 않음 |
| `run_id`, `application_epoch`, `model_epoch`, `session_enable`, `profile_id` | application 복구와 물리 model reset을 구분. 해당하지 않거나 미관측이면 null+reason |
| `requirement_ids`, `interface_ids` | 해당 SYS/IF 추적성; scenario/test ID는 Host가 별도 연결 |
| `source_identity`, `command_identity`, `stop_lease_identity` | 원본 producer/sequence/source/expiry와 causal parent. 보호 Actual의 마지막 정상 command와 protection origin을 구분 |
| `state_before`, `state_after`, `control_latched`, `evidence` | 실제 관측한 local state/선택/값·유효성; 없는 필드는 null+reason. ACK의 요청·수용·거절/미도착과 expected/received role mask를 구분 |
| `injection`, `first_violation`, `detected`, `selected`, `acknowledged`, `actual_source`, `observed`, `recorded` | 각각 선택적 원본 시각. 검출 원점, 출력 선택, 물리 acquisition, 수신·저장 시각을 합치지 않음 |

각 시각은 `(clock_domain, clock_instance, ns, validity)`다. 같은 domain 이름만으로
서로 다른 process boot/reset을 비교하지 않는다. Simulation과 monotonic wall time을
분리하고 pause/reset 경계를 보존한다. `recorded`나 collector 수신 시각을 `detected`로
대체하지 않는다. Clock fault 당시 값은 untrusted로 보존하고 신뢰 가능한 logger clock을
별도 둔다. 공통 clock/mapping 증거 없는 timestamp 차이는 `not_comparable`로 보고한다.

한쪽 통신이 끊겨도 살아 있는 owner의 local event를 남긴다. 연결 뒤 회수한 과거 event는
과거 epoch의 이력에만 귀속한다. 늦은 event가 현재 제어 상태·freshness·permission을
갱신할 수 없다. 전송 순서가 뒤바뀌어도 ID와 causal link로 복원하고 시각을 재작성하지 않는다.

## DTC 기록·유지·재발

집계 record에는 `first/last occurrence`, 최초/최근 검출 시각, `occurrence_count`,
원본 evidence 참조, `confirmed`, `condition`, `control_latched`, `record_revision`을 둔다.
`condition`은 **Failed / Passed / Unknown**이다. 관측 불가능·monitor 정지·통신 상실은
Unknown이며 Passed로 간주하지 않는다. 현재 latch는 원본 owner에서 관측한 값/unknown이다.

| 사건 | DTC 집계 규칙 |
| --- | --- |
| 최초 qualified fault | confirmed=true, condition=Failed, count=1; 원본 occurrence 고정 |
| 같은 occurrence의 polling/재전송/보호 ACK/Actual | evidence만 추가; count와 최초 원인/시각 유지 |
| 같은 event ID·같은 내용의 replay | idempotent. Payload가 다르면 거부하고 RecordingGap |
| 원본 monitor의 qualified pass | condition=Passed; confirmed와 이력/count는 유지. 제어 latch를 지우지 않음 |
| pass 후 새 qualified fault 또는 새 trusted epoch에서 새 fault 판정 | 새 occurrence로 count+1. 같은 code의 독립 monitor/대상은 별도 key |
| restart·새 run·새 INIT | 저장 이력 유지, 현재 condition/latch는 Unknown에서 재평가. collector 재생은 새 occurrence가 아님 |
| 원인 미확인·evidence gap | Unknown과 불완전성 표시; 무소식으로 복구/삭제하지 않음 |

같은 monitor의 현재 epoch에서 pass 없이 새 occurrence ID를 발급하거나 producer instance를
바꾸면 protocol conflict다. 과거 fault는 원본 source 순서로 first/last를 보존하고 현재 상태를
덮지 않는다. Clear 이전 pass보다 오래된 occurrence는 이력에만 귀속한다. 그 pass보다 나중의
새 fault가 뒤늦게 도착하면 현재 generation을 다시 열어 불확실한 정상 판정을 피한다.
재시작/Unavailable 이후에는 이전 fault·pass보다 나중의 새로운 복구 evidence가 필요하다.

Occurrence/record revision/count는 wrap하지 않는다. 표현 한계는 saturation+명시적
overflow 표시로 남기고 진단 완전성 수용을 실패시킨다. 같은 detector가 clock fault로
최신 reason을 바꾸더라도 앞서 기록한 최초 고장 증거를 덮지 않는다.

## 영속 저장과 손실

Host 저장은 별도 writer의 append journal로 제안한다. Run manifest에 schema/code
registry revision, profile/config/source hash, store identity와 queue/record 용량을 고정한다.
Queue와 메모리 집계는 유한하며 초과 시 조용히 drop/evict하지 않는다. 최초 미기록
sequence·drop 수·overflow flag를 owner의 별도 bounded health snapshot에 남기고,
writer가 회복하면 RecordingGap을 기록한다. Disk failure 중 영속 기록 성공을 주장하지 않는다.

Writer는 record sequence·길이·checksum으로 journal을 검증하고 commit/fsync 완료
watermark를 제공한다. Memory의 confirmed와 durable watermark를 구분한다. Crash 뒤
마지막 미완성 record는 격리하고 gap을 표시하며, 중간 손상/누락은 store 불완전으로 거부한다.
Committed prefix 밖의 event는 전달·저장 증거가 없으면 `unknown/lost`다. Logger 장애가
기존 local protection 경로를 막아서는 안 된다.

보존 기간에 따른 자동 aging/삭제는 v0.1에서 **사용하지 않는다**. INIT·HV-off·프로세스
종료로 지우지 않는다. Clear도 원본 journal/evidence를 물리 삭제하지 않고 tombstone을
추가한다. Capacity/저장 실패·crash로 이력 전체를 보장할 수 없으면 그 한계와 실패를 남긴다.
분리 process의 Event-only wire/spool 부분 검증은 아래 경계를 따른다. 실제 DDS/SOME-IP 배치·
live owner 수집·부하/보존 용량과 compaction 수용은 후속이다.

## Event-only 원격 replica와 유한 spool

`interfaces/diagnostics/diagnostic_wire`는 최대2048-byte datagram의 wire v1을 정의한다.
C++ padding/원본 시각을 바꾸지 않고 기존 schema1 canonical Event bytes를 그대로 넣는다.
Entry tag가 Clear인 payload는 decode 전에 거부한다. Data와 durable ACK 두 종류만 있다.

| 필드 | bytes / 의미 |
| --- | --- |
| magic/version | 8 / `SDDWIR` +1 +0 |
| kind/reserved | 1 +3 / Data1 또는 ACK2; reserved0 |
| registry | 4 / 명시적1–3, 양 끝 manifest와 정확히 같아야 함 |
| stream / ordinal | 8 +8 / unique source store ID /1부터 시작한 committed journal ordinal |
| payload length | 4 / 실제 길이와 일치 |
| payload | Data: 원래 canonical Event; ACK: 해당 Event의 CRC32 4 bytes |
| CRC32 | 4 / 앞선 header+payload 전체, polynomial0xedb88320, init/final xor0xffffffff |

정수는 little endian이다. 최대 길이·magic/version·reserved·kind·길이·CRC·zero ID/ordinal·
schema/code registry를 검사한다. CRC는 오류 검출이며 인증이 아니다. 동일 unique stream ID와
registry로 별도 source/replica store를 명시적으로 provision하고 trusted peer에 바인딩하는 것은
호출자 책임이다. 기존 store ID 재사용/자동 adoption·공개 원격 서비스·인증은 추가하지 않는다.

Linux `Outbox`/`Inbox`는 단일 non-RT owner가 기존 `FileJournal`을 사용하는 adapter다.
RT owner는 기존 SPSC publish까지만 수행한다. Outbox writer는 먼저 durable local commit하고
정확히 다음 한 ordinal을 준비한다. 한 번에 하나의 ACK만 진행하며 stream/registry/ordinal과
원본 Event CRC가 같아야 한다. 미래/미준비 ACK·다른 stream/direction/registry·손상 ACK는
watermark를 전진시키지 않는다. ACK 유실은 같은 datagram 재시도로 처리한다. 호출자에게
재전송 시점/transport I/O를 맡기며 이 adapter가 sleep/block/send를 수행하지 않는다.

Inbox는 다음 ordinal만 commit한다. 미래 ordinal은 ACK 없이 NotReady, 과거 동일 bytes는
Duplicate ACK다. 과거 ordinal의 다른 bytes나 같은 event ID를 새 ordinal에 재사용하면
원본을 덮지 않고 sticky incomplete marker를 남긴다. ACK는 해당 Event의 durable commit 뒤에만
생성한다. 손상 datagram이나 stream/registry mismatch는 저장소를 건드리지 않고 거부하므로
원본 재시도가 가능하다. 실제 저장 실패·capacity·불완전 tail은 성공 ACK를 만들지 않는다.
`healthy()`는 journal/집계 완전성만 뜻하며 peer liveness나 source freshness 보장이 아니다.

Source journal 자체가 spool이며 manifest의 유한 events/records/occurrences 용량과 기존64MiB
상한을 따른다. ACK로 원본을 삭제하거나 capacity를 재사용하지 않는다. 자동 aging/compaction·
정책적 rotation은 없다. 용량 초과는 incomplete로 남기고 별도 복구/보존 정책을 요구한다.
ACK cursor는 메모리에만 있다. Sender 재시작 시 ordinal1부터 같은 durable history를 재전송하고
수신 측이 기존 prefix를 정확히 비교한다. 따라서 crash 사이에 ACK cursor와 데이터 삭제를
잘못 결합해 미전송 기록을 잃지 않는다. 느린 링크·장기 저장의 용량 적합성은 아직 수용하지 않았다.

하나의 stream은 trusted 집계 writer의 전역 Session/Attempt와 source Event를 순서대로 가진다.
개별 Leaf가 Session을 발명하거나 여러 독립 store를 하나의 stream으로 합치지 않는다.
Local Clear tombstone을 가진 store는 Event-only stream으로 채택할 수 없으며 원격 clear
요청/replication은 없다. Global clear service, multi-source merge와 live owner routing은 후속이다.

Replica ledger는 **원래 source lifecycle의 이력 projection**이다. 처음 전달된 원래 새 epoch
proof/Passed는 그대로 남기지만 이것은 receiver의 현재 물리 readiness나 링크 freshness가 아니다.
Receiver 재시작은 current condition을 Unknown으로 만들며, 이미 committed된 중복 replay는
재평가하거나 Passed를 새로 만들지 않는다. 원격 ACK는 control/physical ACK와 별개다.
실제 제어 권한·latch·clear 경로에 replica의 상태를 연결하지 않는다.

[프로토콜](../test-plan/diagnostics-protocol.md#원격-진단-wire유한-spool-fixture),
[서로 다른 프로세스·원본·실패·감사](../test-plan/evidence/m9_delivery_spool/README.md)를 따른다.
AF_UNIX SOCK_SEQPACKET Host fixture 부분 검증이며 기존 DDS/SOME-IP/차량 wire 적용이 아니다.

## 해제·삭제와 복구 증거

`ConditionPassed`는 해당 monitor의 실제 재검증 증거다. 수신 재개·새 frame 한 개·INIT
호출 성공·tracking 비활성화·차량이 이미 서 있다는 사실만으로 모든 fault를 pass시키지 않는다.
기존 latched monitor가 재시험을 할 수 없으면 새 trusted INIT와 해당 기능 재검증이 필요하다.

| DTC 범위 | Passed를 위한 증거 |
| --- | --- |
| 입력/command/feedback | 새 session에서 원본 identity/진행/age/validity와 해당 monitor 검사 통과. Clear 시에도 필요한 stream의 현재 유효성 확인 |
| control/clock/deadline | 새 trusted session의 올바른 clock·release·identity와 실패한 검사 재통과; gap 없는 해당 검사 구간 참조 |
| braking timeout | 새 유효 NormalStop cycle이 동일 검토 대상 config/profile의 deadline 안에 실제 stopped/hold와 handoff 확인 |
| handoff 실패 | 새 원본 StopLease의 필요한 모든 실제 ACK 수용, lease/epoch/expiry 검사 통과. Timeout과 rejection 사유를 구분 |
| stop evidence 상실 | 새 cycle의 원본 wheel·torque·pressure 및 confirmation dwell/지속 hold 검증 |
| shutdown timeout | 새 cycle의 정확한 인계 후 실제 PowerStatus Off·세 contactor open·bus≤30V 및 Complete |
| actuator response fault | 새 session에서 실제 excitation·독립 fresh acquisition과 해당 response monitor 통과. Sensor 회복만으로 response pass를 대신하지 않음 |
| recording gap | 새 완전한 저장/전송 구간 검증. 과거 손실은 복원 증거 없이는 계속 불완전으로 보존 |

Config/profile을 바꾼 성공은 이전 계약의 재통과가 아니다. 변경 근거와 새 검증을 연결하고
이전 timeout/FAIL 이력을 유지한다. 과거 run의 pass는 현재 재검증으로 재사용하지 않는다.

**Clear는 trusted local 진단 요청에만 허용**한다. 원격 wire 서비스·자동 clear는 추가하지
않는다. 요청에는 request ID·대상 key·expected record revision·근거 event를 넣는다.
다음 조건을 writer/집계 owner가 직렬로 확인하고 tombstone을 durable commit한 뒤 성공을 응답한다.

1. 대상 record가 Passed이고 gap 없는 복구 증거가 현재 session에 연결된다. Failed/Unknown,
   원인 미상 또는 필요한 monitor/stream이 관측되지 않으면 거절한다.
2. 현재 유효한 원본 wheel≤.01rad/s·|torque|≤.1Nm·brake≥100kPa로 stationary hold를
   확인하고 normal dispatch가 억제되어 있다. 값/clock/freshness 판정은 기존 gate를 따른다.
3. 요청 revision 이후 새 occurrence·증거 상실·session 변경이 없고 저장 경로가 정상이다.
   Clear-all도 scope 전체를 검사하고 하나라도 실패하면 전체를 거절한다.

요청 재전송은 동일 결과로 응답하며 crash/replay도 이미 committed한 clear를 재적용하지 않는다.
Clear 뒤 새 fault는 새 record generation/count1로 시작하고 tombstone 이전 이력을 연결한다.
지연 도착한 과거 event는 과거 이력에 추가할 뿐 새 generation을 열지 않는다. 현재 상태가
불확실해진 경우 Unknown으로 막고 재검증한다. Clear 성공은 제어 latch 해제·주행 허가가 아니다.

## Proposal 이전 기동 incident

`BootstrapJournal`은 EpochStore initialize/issue와 native journal initialize/open을
별도 startup-only 영구 spool에 기록한다. DTC Event/Attempt/Session을 만들지 않으며
application epoch는 absent다. 식별자는 kernel boot UUID·무작위128-bit attempt·PID와
원래 CLOCK_MONOTONIC begin/outcome이다. 성공한 재시도는 이전 실패/중단을 복구·해제하지 않는다.

명시적 fresh initialize 뒤 각 작업 전에 begin file/디렉터리를 fsync하고, 작업 결과도 별도
immutable outcome으로 확정한 뒤에만 다음 단계로 반환한다. 오류·미완료 tail은 보존한다.
Epoch issue 뒤 outcome 기록이 실패하면 해당 Epoch를 반환하지 않으며 다음 issue는 건너뛴다.
Spool 자체 오류도 기동을 중단한다. 이때 영구 기록 성공을 보장할 수 없으며 stderr/supervisor
실패만 남을 수 있다. 자동 초기화·truncation·DTC clear·제어 권한 허가는 없다.

실제 launcher는 DTC store와 다른 `/var/tmp/stratadrive-bootstrap-*/incidents`를 유지한다.
Native `start()`는 writer의 초기 active source/context/collector 검증 완료를 기다린다.
이 실패는 해당 process의 owner 생성·새 proposal 경로 이전에 반환되어야 한다. 세션 도중 worker 오류는 기존
diagnostic 전달/보호 경계이며 bootstrap 성공으로 소급 덮지 않는다.
같은 디스크 전체 장애·전원 차단·장기 보존/운영 reconciliation은 별도다.
[wire/저장 계약과 시험](../test-plan/bootstrap-incidents-protocol.md),
[실행 근거](../test-plan/evidence/m9_bootstrap/README.md)를 따른다.

## Release 전 기동 시도와 실제 Session

`startup_diagnostics_run`은 logical Host10ms Normal/Fault speed-loop 전용 수집 모드다.
기존 control/owner/native 수집 모드와 혼합하거나 wall 실행하지 않는다. 이미 검증한
기존 모드의 global Release 이후 수집 경계는 유지한다. 이 모드에서는 Central이 실제
허가한 proposal의 `Attempt`부터, 각 owner가 실제 local INIT를 마친 native 관측까지 수집한다.
EpochStore/journal bootstrap 또는 trusted proposal 이전의 실패는 위 별도 incident 경계를 따른다.

`Kind::Attempt=9`는 진단 context를 만들며 제어 권한을 주지 않는다. Run/epoch와 동일한
issuer의 trusted proposal source가 필요하고 미래 enable을 알 수 없으므로 session_enable은
absent다. Ledger의 session accessor는 이 진단 context도 반환하므로 RunGate로 사용하지 않는다.
새 Attempt는 epoch가 증가해야 하며 과거 condition을 Unknown으로 재평가한다. 실제 Session은
같은 issuer/run/epoch·8-role mask255·proposal 이후의 comparable enable일 때만 같은 epoch를
승격할 수 있다. 승격 자체는 이미 기록한 Failed를 지우거나 Unknown으로 바꾸지 않는다.
기존 Attempt 없는 상위 epoch Session 경로는 호환을 유지한다.

Release 전 Proof/Passed와 clear 요청은 NotReady로 거절한다. 미리 받은 proof를 나중에
소급 적용하지 않는다. SD-4101의 Passed는 occurrence보다 큰 epoch의 실제 전역 Release와
동일 source의 정상 handshake completion을 요구한다. Local completion은 실제 Ready,
Central은 Running이어야 하며 원래 enable/commit deadline·30ms age·역할 mask를 만족한다.
INIT 요청·ACK 경로 복원·새 Attempt만으로는 Passed가 아니다. Passed는 이력/count/generation을
남기며 latch 해제 명령이나 물리 차량/HV readiness 증거가 아니다. 기존 native DTC 복구는
원래 actual dispatch/BMS Active/Power HV Ready 등의 추가 predicate를 계속 요구한다.

새 `Code::Startup=0x4101`과 Attempt는 **registry3**가 필요하다. 새 store를
`FileJournal::initialize(..., limits, 3)`로 명시적으로 생성한다. Binary schema1·기존 기본
registry1·registry2는 유지하며 자동 migration하지 않는다. Registry2에 CodeNone인 Attempt도
append할 수 없다. 이전 reader는 manifest revision을 먼저 거부한다.

최초 source snapshot은 `session::Observation`으로 plan·원래 call/previous clock·deadline·
실패 직전 state·accepted role mask를 보존한다. Observer용 추가 clock read는 없다.
Central producer7/monitor10/subject9, local producer40–47/monitor11/subject1–8 순서는
Front/Rear/Steering/Brake/Drive/BMS/Power/Central participant다. Timeout/Rejected/Initialize/
Quiesce/Send/Continuity/CentralCommit은 SD-4101, Clock은 기존 clock code, OwnerGap은 기존
Deadline code다. Participant/Cancelled 또는 Aborted 보호 전달은 root DTC가 아닌 Observation이다.
미지 native reason은 unmapped로 남긴다. 각 observer의 fixed32 pending key는 무단 eviction하지
않으며 초과/queue 손실은 sticky incomplete다. 연속 실패한 proposal도 각각 별도 occurrence다.
Clock은 아래 별도 trusted 재검증을 사용한다. Deadline의 기동 복구 predicate는 별도다.

[사전 recipe](../test-plan/diagnostics-protocol.md#release-전-기동-시도-진단-fixture)와
[원본·감사·실패](../test-plan/evidence/m9_startup_sources/README.md)를 따른다.

## SOME/IP 진단 channel과 새 logical owner

`interfaces/someip/diagnostic_binding.hpp`와 `diagnostic_transport.hpp/.cpp`는 선택형
vSomeIP3.7.6의 별도 application을 사용한다. 기존 owner-wire/control service와 별개인
Event-only channel이며 SDK dependency는 기존 pinned SDK를 따른다. Runtime queue와
journal/clear/control 의미를 SDK request/response cache로 바꾸지 않는다.

| Binding | 값과 방향 |
| --- | --- |
| Service / instance / interface | Publisher0x5d10, Replica0x5d11 /1 /1 |
| Method | Data0x0101 → Replica, durable ACK0x0102 → Publisher |
| Message | reliable TCP / MT_REQUEST_NO_RETURN1 / protocol1 |
| Payload | 기존 diagnostic wire v1 / 원본 Event schema1 / 명시적 registry1–3 |
| Application ingress | Callback bounded FIFO8, 최대2048 bytes, overflow/reject/highwater 별도 counter |
| SDK fixture config | reliable2048/local4096 bytes, external/local queue16384; 기존 control512/1024·8192는 그대로 |

Binding은 service·instance·interface·method·type·reliability·Data/ACK 방향·stream/registry를
검사한다. 다른 control binding이나 다른 context는 ingress 전에 거부한다. CRC/service ID는
인증이 아니며 peer trust와 unique stream/producer 할당은 배치 책임이다. Host fixture의 SDK
client ID Publisher0x2211·Replica0x2221/재시작0x2222는 PCAP에서 대조한다.

Callback은 검증/유한 enqueue만 한다. 원래 logical owner는 기존 SPSC EventQueue에 publish하고,
별도 non-RT writer만 Outbox/Recorder와 fsync·SDK send를 호출한다. Sender의 send-return은
전달/commit 증거가 아니다. 수신 writer의 Inbox durable commit 뒤 ACK가 원본 ordinal을
진행한다. Fixture retry 간격은 monotonic100ms다. SDK 연결 상태를 제어 권한으로 사용하지 않는다.

`someip_diagnostics_live`는 **새로 실행하는 논리 SIL source**다. 기존 SimpleVehicle의
8-role INIT/full Release·Central Speed/Stop/Coordinator 원본 observer를 사용한다. Archived
journal을 입력으로 replay하는 fixture와 구분한다. Producer7·test run/stream7001·registry3의
고정 ID는 독립 netns별 test scope이며 여러 case의 이력을 합치는 production identity가 아니다.
Host pacing은 logical1ms마다20µs sleep이고1:1 wall 실행이 아니다. Simulation event의 원래
stamp를 바꾸지 않으며 fsync/SDK의 monotonic 시각은 sidecar CSV에 둔다. Recorded stamp를
Event에 소급해서 넣지 않는다. 실행 중 Fault commit과 진단 on/off의 전 physical/권한/에너지
표본 동등성을 요구한다. 실제 control traffic을 IP로 바꾼 native 3-ECU owner 검증은 아니다.

Normal92s는4350 controls/DTC0, 입력 손실13s는 elapsed10s 주입/SD-1001 한 건이다.
ACK 한 번 유실과 Fault commit 뒤 replica SIGKILL/새 SDK client 재시작을 검사했다.
Source Failed/count1/generation1과 원본 이력은 유지한다. 재시작 replica의 Unknown은 연결
복원이나 중복 replay로 Passed가 되지 않는다. Replica가 처음 받는 이력과 현재 물리 readiness도
구분한다. `/tmp`·`/dev/shm`·netns를 분리하고 PCAP의 TCP/SOME-IP와 journal 원본을 대조한다.

[사전 recipe](../test-plan/diagnostics-protocol.md#someip-진단-channel새-logical-owner-fixture),
[실행·실패·clock·감사](../test-plan/evidence/m9_someip_live/README.md)를 따른다.
DDS control gate는 CLOSED인 별도 대안이다. Target·실제 부하/장기 보존 수용은 후속이다. Native 배선은 아래 별도 범위를 따른다.

## 원격 publisher의 전역 context admission

Linux `ContextualOutbox`는 명시적 run/local producer/Central producer/profile/monotonic clock
manifest를 사용한다. 실제 remote Zone/Leaf endpoint owner의 `diagnostic_evidence()`는
RunLeaseGate가 이미 수용한 원본 credit와 고정 ClockAgreement를 값으로 복사한다. INIT의 bind는
이전 credit를 지운다. 로컬 Ready만으로 accepted credit가 생기지 않는다. Snapshot은 과거 수신
근거이며 현재 권한이 아니다. 만료/보호 뒤에도 남지만 gate를 갱신하거나 여는 함수는 없다.

Non-RT writer는 trusted Central peer의 **원본 Session Event**를 받아 run/issuer/profile,
full role masks255, epoch/enable/prepare deadline, 원래 Running completion, clock agreement와
이미 수용한 credit의 plan/source를 대조한다. 새 Session ID나 수신 시각을 만들어 넣지 않는다.
CRC와 이 값 비교는 peer 인증을 대신하지 않으며 snapshot의 생성 경로는 배치 책임이다.
기존 owner-wire·Event schema·code registry·timing/authority budget은 바꾸지 않는다.

로컬 event는 context 전까지 최대32개만 보관한다. `submit`의 Accepted는 메모리 수집 성공이며
durable ACK가 아니다. Context를 먼저 원래 bytes로 commit한 뒤 일치하는 epoch/enable의
event를 원래 순서/ID로 commit한다. `next`는 committed prefix만 노출한다.
Proof/Passed는 context가 아직 일치하지 않으면 NotReady로 거부하며 대기시켜 소급 수용하지 않는다.
`drain`에서 이미 꺼낸 거부 event는 손실로 표시하므로 source adapter가 이 경계를 지켜야 한다. 오래된 미해결
event를 건너뛰어 새 context로 가지 않는다. Queue loss/identity 오류·대기 한도·변조된 동일 epoch
context·commit 실패는 sticky incomplete다. 대기 event를 남긴 정상 종료도 store를 invalidate한다.
대기/SPSC의 commit 전 메모리는 급작스러운 process 종료에 영속하지 않는다. Source process의
재시작 adoption/손실 조정은 별도이며 보장된 전달 분모는 durable prefix다.

각 source/replica 쌍은 unique stream/store ID를 쓴다. 두 stream에 같은 Central 원본 Session을
넣어도 병합 Ledger는 EventId/bytes로 한 건만 수용한다. ACK ordinal은 stream별로 독립이다.
재시작한 ledger의 Unknown은 같은 Session/fault의 duplicate replay와 context 재대조로 회복하지
않는다. 지연된 근거는 과거 고장 기록에 사용할 수 있지만 현재 readiness나 Passed/clear를
생성하지 않는다. 이 모듈은 전역 Session admission을 다루며 Release 이전 Attempt 수집은 별도다.

[component recipe](../test-plan/diagnostics-protocol.md#원격-context-admission-component-fixture)와
[실행·한계](../test-plan/evidence/m9_remote_context/README.md)를 따른다.

## 실제 native Central/Front/Rear 배선

기존 opt-in `someip_front_adapter --three`의 실제8-participant graph에
`NativeDiagnosticRoutes`를 연결했다. `--diagnostics`에서만 켜지며 새 logical Network나 archived
event를 source로 사용하지 않는다. Central Startup producer7이 원래 Attempt/Session을 발행하고,
Coordinator/Stop producer8은 `start_session(..., false)`로 그 global context를 사용한다.
기존 ControlDiagnostics의 기본 Session 발행은 유지한다. Global Release와 물리 HV/차량 readiness는 별개다.

| 원래 publisher | ECU / producer | source stream |
| --- | --- | --- |
| Zone feedback | Front20 / Rear21 | 8200 /8201 |
| Leaf command authority | Front Steering22·Brake23 / Rear Drive24 | 8202–8204 |
| Gateway native | Front30 / Rear31 | 8205 /8206 |
| BMS·Power native | Rear32·33 | 8207 /8208 |

각 observer는 실제 actor의 epoch/enable·최초 fault·선택/ACK·normal predicate를 자기 owner에서
읽는다. RunLease evidence와 원본 native detector는 lock-free snapshot으로 writer에 복사한다.
Source는 실제 accepted credit 뒤에 시작한다. Writer가 context를 commit하기 전에는 원래 control
gate가 열려 있어도 진단 recovery predicate를 열지 않는다. 진단 gate는 제어 권한을 바꾸지 않는다.

Central→Front/Rear context stream8101/8102와9개 source stream은 각각 독립 source/replica
journal을 쓴다. Central merged store8000은 동일 원본 Session을 한 번만 저장한다. Remote ACK는
해당 replica와 merged의 durable commit 뒤에만 보낸다. Failed commit·source loss·capacity는
성공이 아니며 원본 ACK/ordinal을 건너뛰거나 저장 이력을 지우지 않는다. 원격 Clear는 없다.
Central이 원인 미지로 남긴 CodeNone/Unmapped Observation도 원본대로 보존하며 원격 root로
추정해 바꾸지 않는다. Source 재시작 adoption과 전체 원인 연결/clear 수용은 후속이다.

`diagnostic::Channel`은 기존 SDK application에 붙는 독립 callback FIFO8이다. Control service와
data/authority FIFO는 공유하지 않는다. Setup/registered hook은 dispatch 시작 전에 설치한다.
Context service pair0x5e00–03, source pair0x5e10–21, instance/interface1, reliable Data0x101/
ACK0x102를 사용한다. Source별 stream/registry와 service 방향을 함께 검사한다. 기존 standalone
0x5d10/0x5d11 channel은 유지한다. CRC/service/client ID는 peer 인증을 대신하지 않는다.

Control TCP/wire512·queue8192와 lane8은 그대로다. 새 diagnostic endpoint31610–12만 TCP2048을
사용한다. SDK가 외부 payload 이상을 요구하므로 shared local envelope는 새 opt-in profile에서
1024→2048로 명시한다. 실제 Data602 bytes, retry100ms, source pending32, 종료 drain2s다.
Writer만 CPU15/SCHED_OTHER0에서 파일/SDK IO를 수행한다. 실제 배치를 기록하고 source/replica는
각 ECU의 별도 directory에 둔다. `/var/tmp`의 새 고유 ext4 store 원본을 남기고 종료/join 후
artifact를 복사한다. Private `/tmp`·`/dev/shm`을 진단 전달 경로로 사용하지 않는다.

보호 burst에서는 유효 Abort/ProtectionRequest가 같은 peer·plan/epoch·clock의 미사용 credit만
송신/수신 큐에서 취소한다. Control/command/ACK·다른 세션·actor가 이미 수용한 evidence는
제거하지 않는다. 수신 측 처리는 기존 binding/freshness 검사 뒤, 실제 actor 적용 전에만 한다.
이는 gate 열기나 보호 ACK가 아니며 retire 수를 별도 기록한다. 종료 후 진단 drain 동안의 late
control ingress도 별도 계수하고 완료한 runnable로 세지 않는다.

[고정 recipe](../test-plan/diagnostics-protocol.md#native-3-ecu-진단-배선-fixture)와
[실제 TCP/owner/journal/물리 검증](../test-plan/evidence/m9_native_routing/README.md)을 따른다.
이 배선의 기동 전 로컬 실패·source/collector 재시작 adoption·BMS/Power의 전체 native fault
matrix·Clock/Target/부하/보존 용량·CARLA30km/h와 학습자 수용은 OPEN이다.

## 진단 전달 계층의 저장 이력 재개

`ContextualOutbox::restore`는 source journal의 마지막 원본 Central Session을 실제 local endpoint의
accepted RunLease evidence에 다시 대조한다. 빈 journal·credit만으로 Session을 만들지 않는다.
기존 plan/clock/role/profile 검사와 원래 EventId/시각을 유지한다. 재개한 Outbox의 ACK watermark는0이고
ordinal1부터 durable prefix를 재전송한다. Context 중복 수용으로 restart Unknown을 정상/Failed로
바꾸거나 lease를 연장하지 않는다. 새 Passed는 여전히 실제 monitor의 별도 근거를 요구한다.

`MergedCollector`는 명시적으로 제공한 모든 replica와 merged journal을 한 non-RT owner에서
소유한다. Store ID 중복/merged alias·registry 불일치·event-only 위반·incomplete store는 거부한다.
기동 시 durable replica prefix를 merged의 EventId/bytes에 대조하고 누락된 transaction을 commit한다.
이 복구는 과거 이력이므로 완료 후 projection은 Unknown이다. 동일 ID의 다른 bytes나 저장 실패는
sticky incomplete로 거부하며 원본을 덮지 않는다. 수신 ACK는 replica와 merged 양쪽 commit 뒤에만
만든다. Replica만 commit한 crash window도 ACK 없이 재개·대조할 수 있다. 여러 source에 공유된
Session은 merged에 한 번만 남고 각 stream ordinal은 독립이다. 원격 Clear는 추가하지 않는다.

Native fixture의 `--diagnostic-restart central|front|rear|all`은 실제 제어 owner/observer/SPSC와 SDK
application을 유지하면서 non-RT store·Outbox/Inbox/collector 객체를 닫고 다시 연다. Source의
context-admitted flag를 먼저 내리고 기존 endpoint evidence와 저장된 context를 재대조한다.
진행 중이던 종료 drain2s를 재시작으로 연장하지 않는다. 이전 객체로 향하던 future ACK는
watermark를 진행시키지 않고 별도 stale counter로 남긴다. 재개 전후 prefix bytes와 Unknown/count/
generation을 기록하고 실제 TCP의 ordinal1 재전송을 독립 감사한다. `all`에서 고장이 없는 ECU는
원래 owner가 quiesce된 후 재개한다. 제어 gate/권한·예산·물리 oracle는 바꾸지 않는다.

이 범위는 **진단 전달 객체의 재개와 durable prefix 복구**다. 별도 process 시험의 실제 SIGKILL은
source commit·replica-only commit·merged reconciliation 직후에 주입한다. 전체 native ECU process
kill/rejoin·새 producer incarnation/sequence adoption·commit 전 SPSC/pending 메모리 손실 조정은
후속이다. Source observer가 연속인 시험을 전체 ECU 재기동 수용으로 표시하지 않는다.
[고정 recipe](../test-plan/diagnostics-protocol.md#진단-전달-재개와-crash-window-fixture)와
[결과·원본](../test-plan/evidence/m9_delivery_restart/README.md)을 따른다.

## ECU process 재기동의 발행자 세대와 연속성

`ProducerLifecycle`은 명시적으로 provision한 private journal을 process 수명 동안 독점 잠근다.
Manifest store ID는 해당 ECU lifecycle identity와 같고 registry3/run/profile/common monotonic clock을
검사한다. 원본 start/clean-close transaction의 순서·bytes·시각을 대조하고 새 generation의 start를
file/directory fsync로 commit한 뒤에만 발행자 ID를 반환한다. ID는
`((generation - 1) << 32) | logical_source`다. Logical source는 nonzero uint32이며 첫 세대의 기존
ID20–33을 유지한다. 새 프로세스는 새 ID에서 event sequence1을 시작한다. Generation wrap·용량·
commit 실패·변조·clock regression·동일 store 동시 점유는 발행자 권한을 주지 않는다.
Private lifecycle의 epoch는 process generation이며 wire/global Session이 아니다.

Destructor는 clean-close를 쓰지 않는다. Owner 생산을 종료하고 진단 queue/pending·ACK drain이
완료된 뒤에만 호출자가 명시적으로 close한다. 마지막 start가 닫히지 않았다면 다음 process는
`previous_unclean`이다. Commit 전 SPSC/pending은 사라질 수 있으므로 손실 개수·원인 event를
추정해 복원하지 않는다. 새 실제 Session과 local accepted credit 뒤에 각 재기동 source는 최초
sequence1로 SD-5001/monitor10/subject=logical_source/native_reason1(`UnverifiedContinuity`)를
기록한다. Detected는 새 process가 unclean 상태를 발견한 원래 boot 시각, Observed는 해당
owner가 원본 global context/credit 뒤에 관측한 시각이다. `state_before/after`는 이전/새 generation,
`cause_unknown`·`unmapped`는 true이며 measured0은 손실 개수가 아니다. 이력 incident count1은
연속성 미확인 incident 한 건을 뜻한다. 정상 observer의 첫 순번은2로 예약한다.

SD-5001은 `Kind::Fault`이며 transport/storage 무결성 실패인 `Kind::Gap`과 구분한다. 기존
unmapped 규칙에 따라 clear를 막으면서 영속 전달은 계속한다. 원본 재생·새 INIT·새 source의
정상만으로 이 marker나 이전 source의 고장에 Passed를 만들지 않는다. 연속인 생존 source의
기존 recovery는 실제 새 Epoch와 원래 proof로만 처리한다. 로컬 심사와 한정된 terminal native 연결은 아래 별도 경계를 따르며 일반 원격 clear 운용은 후속이다.

`CommittedReplay`는 이전 source의 검증된 committed prefix만 내보내는 별도 read-only API다.
불완전 suffix가 있어도 frame/commit/semantic 검사를 통과한 prefix를 원래 ID/bytes/ordinal로
재전송할 수 있다. Append/repair/clear API가 없으며 suffix/incomplete marker는 삭제하지 않는다.
`source_complete`를 별도 보고한다. 이 전송 성공은 이전 source가 완전했다는 근거나 readiness가
아니다. 새 source의 unverified continuity 표시가 필요하다. 일반 Outbox는 기존대로 incomplete
store의 전송/기록을 차단한다. Event/ACK wire/schema·registry revision은 바꾸지 않는다.

Native `restart-live --diagnostics --three`는 Front 또는 Rear의 실제 ECU/SDK process를 SIGKILL하고
같은 netns에서 새 SDK client ID로 재시작한다. 생존 Central·다른 Zone·plant를 다시 시작하지
않는다. 기존 명시적 rejoin과 영속 EpochStore의 실제 Epoch2·8-role Release/accepted credit가
필요하다. 새 observer가 이전 Session/Ready를 재활용하지 않는다. Central owner 재구성 뒤에도
동일 진단 issuer를 연결해 원본 Attempt/Session의 sequence를 유지한다.

Fixture는 명시적 두 process generation만 provision한다. 기본 source streams8200–8208/service
pairs0x5e10–21, 두 번째 streams8209–8217/pairs0x5e40–51이며 두 세대 모두 독립 source/replica를
갖는다. 재기동 대상의 두 번째 세대만 활성화한다. Context8101/8102는 원래 ordinal1/2의 두
Session을 전달한다. 새 process는 이전 세대 source prefix도 별도 channel로 원형 재전송한다.
모든 원격 ACK는 기존 replica/merged commit 뒤다. Manifest/CRC는 peer 인증을 대신하지 않는다.

이 범위는 같은 kernel/clock instance의 Front/Rear ECU process 재기동이다. Central process
재기동·host 전원/clock 변경·임의 반복 재시작과 저장 용량 수용·연속성 reconciliation/원격 clear는
닫지 않는다. [고정 recipe](../test-plan/diagnostics-protocol.md#ecu-process-재기동과-발행자-adoption-fixture)와
[실행·한계](../test-plan/evidence/m9_producer_adoption/README.md)를 따른다.

## Central process 재기동과 trusted issuer 계승

`ContextualOutbox`의 명시적 `CentralIssuer` manifest는 최초 Epoch1부터 최대16개의
`producer/first_epoch` 구간을 고정한다. 경계는 증가하고 발행자는 중복되지 않는다. 수신 packet으로
발행자를 학습하지 않는다. 기존 단일 발행자 API는 `{producer,1}`과 같다. 새 원본 Session은 해당
Epoch의 trusted issuer·run/profile/clock·8-role Release와 실제 local accepted RunLease를 모두
만족해야 한다. 새 issuer context를 durable commit한 뒤에만 sender ACK 메모리를0으로 되돌려
원래 ordinal1부터 보낸다. 오래된/앞선 ACK는 진행을 건너뛰지 못한다. 원격 producer/sequence와
원본 times는 유지한다. CRC/manifest는 인증 기능이 아니다.

`MergedCollector`는 명시적으로 전달된 predecessor의 검증 committed prefix를 새 merged store에
가져오고 현재 replica와 대조한 뒤 live 입력을 받는다. 동일 ID/동일 bytes는 dedup하고 충돌·foreign
registry·저장 실패는 fail closed다. 원본 suffix/incomplete marker를 고치거나 옮기지 않는다.
재시작 projection은 Unknown이며 새 Session/재전송만으로 이전 고장을 Passed/cleared로 만들지 않는다.

Native `central-rejoin --diagnostics --three`는 Central1을 실제 SIGKILL하고 같은 kernel/netns에서
새 Central2 SDK client0x1312로 시작한다. Front/Rear/plant는 계속 살아 있다. 명시적 startup 요청과
실제 EpochStore의 Epoch2가 필요하다. Central 준비/영속 Epoch 발급 중에는 기존 quiescent ingress
전환으로 이전 상태 입력을 계수하며 차단한다. 새 handshake 전에 전환을 끝내고 정상 FIFO8을 쓴다.
새 readiness를 과거 overflow 소거로 만들지 않는다.

Private lifecycle9100은 generation2를 영속 발급한다. Global issuer는7→`(1<<32)|7`, observer는
8→`(1<<32)|8`이며 trusted 경계는 Epoch2다. 새 observer 순번1의 SD-5001/monitor10/subject8은
원래 boot 시각·previous/new generation·cause_unknown/unmapped를 기록한다. Central event queue의
저장 전 손실은 증명할 수 없다. 손실 개수를 추정하지 않고, 새 실제 정상 운전/정지/HV-off와 완전한
replay도 이 incident의 복구 proof나 clear 허가가 아니다. 일반 원격/native clear 수용은 OPEN이며 아래 로컬 심사·terminal fixture와 구분한다.

Fixture는9개의 생존 source stream8200–8208을 유지한다. 새 Central replica `source-*-2`, merged
`merged-2`(store8002), context source `context-*-2`를 사전 provision한다. 이전 merged8000/9개
replica의 committed 원본을 가져오며 old context source의 원본 Session1은 ordinal1, 새 Session2는
ordinal2다. 이전 파일·commit·suffix를 보존한다. Control TCP512/진단2048·FIFO8·pending32·retry100ms·
drain2s·원래100ms 물리 판정은 유지한다. 같은 clock의2세대 유한 fixture이며 host reboot·반복 재기동
용량·native4ms/Target 수용은 포함하지 않는다.
[recipe](../test-plan/diagnostics-protocol.md#central-process-재기동-fixture)와
[원본·검증·실패](../test-plan/evidence/m9_central_restart/README.md)를 따른다.

## 연속성 미확인 incident의 로컬 서비스 심사

저장 전 손실 여부는 정상 운전/원본 replay로 증명할 수 없다. 이 경계는 과거 손실이 없었다는
판정을 만들지 않는다. 원래 SD-5001/monitor10/subject=logical producer의 generation·boot·
`cause_unknown/unmapped`와 원형 event bytes를 영구 보존하고, 서비스 요청의 명시적
`AcceptUnknownHistory` disposition으로 **미확인 과거 이력을 수용했음**을 별도로 기록한다.
진단 actor/clock/registry를 임의로 바꾸거나 손실 event 수를 만들어 넣지 않는다.

`ContinuityInspector`는 trusted manifest의 최대32개 고유 stream/producer 전체를 검사하는 단일
비실시간 소유자다. 호출자는 생산자/전송 사용자를 quiesce하고 검사부터 commit까지 같은 frozen
journal/queue/ACK 경계를 소유해야 한다. 미등록/누락/alias/중복 source·registry 불일치·incomplete/
uncommitted suffix·source/replica 원본 불일치·미처리 pending·queue 유실/identity 오류·ACK 미완료는
거부한다. 각 현재 source에는 새 원본 global Session이 있어야 한다. 실제 endpoint의 accepted
credit에 따른 원본 context admission은 기존 `ContextualOutbox`가 수행한다. CRC는 인증을 대신하지 않는다.

| 단계 | 필수 근거와 효과 |
| --- | --- |
| 현재 recording 검사 | 원래 incident보다 높은 application Epoch의 실제8-role global Release. 원래 run/profile/clock과 최신 정지/normal-dispatch 차단. 모든 source/replica가 semantic 검사를 통과하고 원형 bytes/ordinal/ACK가 같아야 함 |
| Recording proof | 별도 서비스 producer의 새 Observation/Proof::Recording. 정확한 incident/occurrence·원래 Session enable·현재 관측 시각에 결속. 과거 loss-free를 주장하지 않음 |
| ContinuityReview | 명시적 AcceptUnknownHistory·현재 Session·incident EventId·record revision·proof EventId·ServiceEvidence·전체 stream의 producer/committed ordinal/tip EventId/CRC. 영속 commit 뒤에만 disposition을 반영 |
| Passed | proof→review→Passed의 별도 영속 순서. 같은 서비스 producer의 증가 sequence와 review ID를 참조해야 함. 심사 전에 저장한 Passed를 나중에 소급 승격하지 않음 |
| Clear | 기존 최신 정지 evidence·current Passed·정확한 revision·명시적 대상 목록 필요. Review만으로 clear되지 않으며 normal control/INIT/actuator 권한을 만들지 않음 |

정지 evidence의 기존 기준(바퀴0–.01rad/s·torque 절대값≤.1Nm·pressure100000–1500000Pa·source
age≤30ms·skew≤20ms)을 재사용한다. Proof도 심사 시점의 같은 clock에서30ms 이내여야 한다.
다른 run/clock·같은/오래된 Epoch·새 genuine Session 없는 local Ready·stale revision/proof·부분 stream
범위·유실된 queue·움직임·dispatch 허용 상태·모르는 native 원인은 승인하지 않는다.

`Ledger::unmapped()`는 미심사 원인이 남았는지를 뜻한다. 승인된 canonical continuity incident의
원본 `unmapped` bytes는 바꾸지 않는다. 일반 CodeNone/unknown reason 등 다른 unmapped 원인은
sticky 차단을 유지하고, 새 incident나 미심사 incident가 하나라도 있으면 clear를 막는다.
손상/incomplete를 뜻하는 `Kind::Gap`/`complete=false`는 이 심사로 해소할 수 없다.

재시작 시 disposition 이력과 이미 commit된 clear tombstone은 유지하지만 현재 condition/latch는
Unknown으로 재평가한다. 과거 proof·Review·Passed의 duplicate 재생은 새 심사를 활성화하지 않는다.
재시작/새 Session 이후 생성한 새 검사 proof와 명시적 심사가 다시 필요하다. 동일 request ID/동일
bytes는 idempotent이며 다른 bytes의 충돌·append 실패·용량 초과는 fail closed다. Review와 clear는
기존 `Limits::clears` 유한 예산64를 **공유**하며 기존 event512/record64/occurrence128을 늘리지 않는다.

로컬 service journal만 manifest registry4와 canonical Entry tag2(ContinuityReview)를 사용한다.
기존 Event(tag0)/Clear(tag1)의 bytes·schema1와 진단 wire1/registry1–3은 유지한다. Source/replica는
기존 registry3의 Event-only journal이다. 오래된 registry에 Review를 쓰거나 Review를 원격 Data로
보내는 것은 거부한다. 기존 파일을 in-place upgrade/repair하지 않고 별도 service journal을 provision한다.

이 API는 인증된 서비스 요청과 실제 최신 정지 상태를 받는 trusted writer-side component다.
현재 시험은 주입 가능한 logical monotonic clock99의 실제8-participant 객체·accepted credit·원본
source/replica와 별도 writer process의 SIGKILL4경계다. Linux 로컬 요청·인가·Actual adapter 연결은 아래 별도 계약을 따른다. 실제3-ECU의
terminal owner/SDK quiesce·물리 정지는 아래 조합 계약을 따르고 일반 원격 운용/Target은 후속이다. Native 재합류만으로
심사가 실행되지 않는다. [고정 recipe](../test-plan/diagnostics-protocol.md#연속성-로컬-서비스-심사-fixture)와
[실행·한계](../test-plan/evidence/m9_continuity_review/README.md)를 따른다.

## Linux 로컬 서비스 요청과 Actual 취득 연결

`ContinuityService`는 별도 비실시간 단일 writer다. 연결된 AF_UNIX/SOCK_SEQPACKET의
SO_PEERCRED UID/PID와 provision된16-byte nonzero boot capability를 검사한다. Caller는 private
listener와 유한 accept scheduling을 소유한다. 원격 네트워크 인증·사용자 계정 체계가 아니며
수신 요청으로 actor/run/Session/incident/manifest를 만들지 않는다. 매 서비스 lifetime에 새 actor를
provision하고 같은 producer의 과거 event가 있으면 시작을 거절한다.

| 로컬 v1 packet | 규칙 |
| --- | --- |
| 요청76byte | SDS/version1, capability16, 요청번호 uint64, Session(run64/epoch32), incident EventId24, revision64, operation8, disposition8, reserved16=0. 다중 byte 정수는 LE |
| Review | operation1/AcceptUnknownHistory1. 요청번호 n의 proof/Review/Passed sequence는4n−3/4n−2/4n−1. 정확한 현재 revision만 수용 |
| Clear | 별도 operation2/disposition0. sequence4n. 이번 서비스의 성공한 Passed ID/현재 revision/동일 전체 stream cut와 새로운 정지 evidence를 요구 |
| 응답32byte | SDR/version1, 요청번호64, durable watermark64, revision64, status8, stage8, inspector block8, reserved8=0. Receipt는 과거 결과이며 현재 control 권한이 아님 |
| 유한 재요청 | 번호1..floor(UINT64_MAX/4), 최대32개 증가 요청. 동일 번호/bytes는 원래 receipt, 다른 bytes/역행은 거절. 부팅 capability/actor를 재사용하지 않으며 영속 재요청 DB는 아님 |

물리 evidence는 요청 packet에서 받지 않는다. Trusted `ContinuityCapture::acquire`가 반환한
`FrozenContinuity` guard가 전체 source/replica/queue/실제 ACK 경계를 검사부터 commit까지
소유한다. Normal dispatch 차단은 진단 guard 해제와 독립적으로 유지한다. 이 인터페이스만으로
다른 process의 RT/SDK 생산자를 정지시켰다고 주장하지 않는다. 실제 구성의 adapter가 그 책임을 진다.

`capture_service_evidence`에는 같은 owner cycle에서 받은 `feedback()`/`current_sample(now)`만
공급한다. last_accepted history를 최신 입력으로 재포장하지 않는다. Trusted run/epoch/enable/clock,
Actual kind와 wheel/torque/pressure의 존재·원래 acquisition timestamp를 검사한다. 취득 시각을
서비스 polling now로 대체하지 않고 기존 정지/age30ms/skew20ms를 적용한다. Proof/Review/Passed
각 commit 전, Clear의 cut 검사와 commit 전에 재취득하며 연속 취득 사이30ms 초과도 거절한다.

Review 성공은 Passed까지 기록하고 clear하지 않는다. 별도 clear가 전 manifest를 재검사하여
그 사이 source append를 거절한다. 재심사의 부분 commit 뒤 이전 Passed를 재사용하지 않는다.
Capture 예외/저장 실패는 해당 service lifetime의 후속 동작을 닫는다. 예외 응답의 stage/watermark는
전체 journal 상태를 보증하지 않으므로 복구 시 committed prefix가 기준이다. Guard는 실패 시에도
해제된다. 권한/범위/물리 거절을 새 normal dispatch/INIT/actuator 허가로 해석하지 않는다.

현재 검증은 실제 Linux peer/별도 writer process·SIGKILL4컷과 결정적 clock99/Actual 주입이다.
실제 codec/P05/application receiver의 current_sample을 통과한 원본11쌍 payload와16개 변조를 독립 감사한다.
실제3-ECU 서비스 운용·물리 plant 정지 검증과 구분한다.
[Protocol](../test-plan/diagnostics-protocol.md#linux-로컬-연속성-서비스-요청-fixture),
[근거·분모·초기 실패](../test-plan/evidence/m9_continuity_service/README.md)를 따른다.

## 실제3-ECU terminal 서비스 연결

Host native3-ECU opt-in 구성은 동일 Central process/SDK에서 Epoch2의 실제 NormalStop/HV-off 뒤
별도 operator startup 요청으로 Epoch3를 연다. 실제8-role Release와9개 source accepted credit를
다시 확보한다. Review/clear 요청이 Epoch·INIT를 발급하지 않는다. Source producer/sequence와
physical model epoch는 유지한다. 새 source 세대를 임의로 만들지 않는다.

EpochStore IO는 기존 session의 normal authority를 닫고 실제 Front/Rear 보호 ACK를 받은 뒤
CPU15/SCHED_OTHER 작업에서 수행한다. 기존 owner는 수신/보호 처리를 계속하며 old owner graph는
새 graph와 분리해 join 이후 폐기한다. 새 Epoch의 실제 handshake 전에는 정상 dispatch를 열지 않는다.
기존 control FIFO8·10ms renewal/18ms support·NormalStop2500ms·diagnostic drain2000ms는 유지한다.

Epoch3 정상 운전/NormalStop/HV-off 뒤 명시적 보호를 선택한다. Front13/Rear114/Central128의
normal gate를 모두 닫고 마지막 진단 capture 뒤 `quiesce`한다. Front/Rear source의 queue/pending와
실제 durable ACK를 먼저 끝내고 collector를 멈춘다. 이후 실제 journal lifetime flock을 서비스가
인수해 같은9개 source/replica/merged cut을 심사/commit 동안 소유한다. SDK callback이 늦은 복사본을
전달해도 journal writer를 재개하지 않는다. Source/collector/report의 health와 정확한 ordinal을 대조한다.

Control owner/SDK/plant는 보호 상태에서 현재 Actual만 계속 제공한다. 서비스는 owner의 현재
feedback/current_sample을 받아 자체 monotonic now로 age를 다시 평가한다. Wheel/drive/brake 취득은
전 writer freeze 이후여야 하며 polling 시각으로 바꾸지 않는다. 준비 시 최대200ms 기다리지만
기존 stationary/age30ms/skew20ms는 유지한다. 요청 window2s·packet readiness100ms·16 connection은
이 terminal 서비스 fixture의 별도 유한 경계이며 control deadline을 연장하지 않는다.

기존 Event-only merged와 source/replica bytes는 보존한다. Fresh registry4/store8900에 원형 prefix를
가져오고 서비스 actor64를 사용한다. 고정 local peer/boot/Session/incident/revision 인가 뒤
Review3의 proof9→Review10→Passed11과 별도 Clear4/ID16만 추가한다. 정확히4 entry가 증가한다.
잘못된 PID/capability·미명시 disposition·old Epoch·stale revision·ID 충돌은 거절한다. Duplicate는
원래 receipt이며 추가 commit이 아니다. Canonical SD-5001 한 건만 해제하며 다른 DTC와 immutable
unknown history/count/generation은 보존한다. 전체 DTC 해소나 과거 loss-free 선언이 아니다.

독립 감사는 실제3개 global Session·24 Release ACK·27 accepted credit·11 stream의 원형 Data/ACK,
source→collector freeze 순서·closed role mask·exact9 cut·실제 local 인가와 별도 clear를 검사한다.
PCAP의 owner CRC32C/CAN P05와 원래 Actual의 값·시각을 별도 physical acquisition 기록에 대조한다.
단순화 차량 모델은 실제로 이동한 뒤 정지하며17개 변조를 거절한다. 기존10ms physical trace는
유지하고 서비스 구간의 acquisition만 별도 유한40000 기록에 남긴다.
[Recipe](../test-plan/diagnostics-protocol.md#native3-ecu-terminal-연속성-서비스-fixture),
[실행·분모·실패](../test-plan/evidence/m9_native_service/README.md)를 따른다.

이는 same-kernel2세대/one-shot terminal maintenance fixture다. Service 뒤 normal 운행을 재개하지
않고 ECU/SDK를 종료한다. 실행 중인 native-watch4ms profile/Target, 일반 service/RPC·다른 host/clock·
반복 세대·서비스 중 새 고장의 실제 거절 수용은 OPEN이다.

## 다음 구현 경계

진단 store와 Central·Zone/Leaf·Gateway·BMS/Power·기동 관측을 제한된 logical fixture에서
연결하고 Event-only replica/spool과 실제 SOME/IP channel의 새 logical owner를 검증했다.
원격 context admission 뒤 실제 native3-ECU의2개 context/9개 source stream도 기능 검증했다.
Central/Front/Rear 재기동과 terminal native 서비스의 ACK/Actual 누락·정지 실패 거절 및
CARLA30 고장 통합의 후속 결과는 아래 M9 후속 근거를 따른다. 미결정 조합과 Clock은 별도다.
Local participant Ready를 global Release로 만들지 않는다.
원본 owner의 최초 판정/선택/ACK를 유지하며 polling 시각이나 aggregate FAIL_SAFE로 대체하지 않는다.
실제 부하의 queue/store 용량 적합성·Clock 복구는 별도 수용한다.
30km/h fault의 구체 주입 위치·기대 DTC와 물리 판정은 [CARLA 진단 protocol](../test-plan/carla-diagnostics-protocol.md)에 고정한다.


## M9 allocator/transport 원인과 NormalStop 재검증

`CoordinatorFaultObservation`은 보호로 allocator 상태를 변경하기 **전** native allocation fault,
원본 VehicleRequest와 AsyncTransportFault의 최초 검출 snapshot을 보존한다. Transport는 실제
operation/token/sent/exclusive deadline과 Stop 인계 여부를 포함한다. 뒤늦은 ACK·재관측·추가
clock 오류로 최초 원인을 덮어쓰지 않는다. `native_reason`의 `0x10000 | AllocationFault`는
allocator, `0x20000 | AsyncTransportFault`는 transport namespace다. Stop operation의 실제 ACK
timeout은 SD-1102, 다른 transport/allocator 고장은 SD-1002이며 각 실제 Clock/Deadline은
SD-4001/4002다. Native NormalStop reason 번호를 만들어 넣지 않는다.

Central 단일 owner의 observer는 미해제 정지 고장의 key별 최근 occurrence를 최대8개 보관한다.
용량 초과 시 observer를 불완전하게 표시하며 미해제 이력을 퇴출하지 않는다. 새 실제 coordinator
Session에서 동일 profile 및 NormalStop의 모든 설정값으로 Braking→HandoffPending→PowerDown→
Complete를 통과해야 복구 proof를 발행한다. 동일 lease의 실제 accepted handoff, 원래 braking/
shutdown deadline, 실제 stopped/hold/PowerStatus Off 증거와 원본 Complete의 age≤30ms를 확인한다.
이는 SD-1101/1102/1103/1104/1105 및 해당 Central allocator/transport·Stop deadline 경로의
재검증이다. Speed monitor SD-1002는 기존 정상 SpeedRequest의 실제 accepted 입력/출력 재검증을
사용한다. Clock 오류에는 적용하지 않는다.

Passed는 삭제가 아니다. `stop_clear_evidence`는 Passed 후보가 있고 현재 원본 wheel·torque·brake,
HV Off·normal dispatch 억제가 유효할 때만 값 복사를 반환한다. Recorder는 명시적인 요청의
key/revision/현재 session과 해당 record의 Passed를 다시 검사하고 durable tombstone을 기록한다.
새 INIT만 수행한 경우, 다른 설정의 성공, 오래된 Complete, 해제 중 새 고장은 성공으로 세지 않는다.

이번 실제 시험 범위·실패 분모·미수용 항목은 [M9 후속 근거](../test-plan/evidence/m9_completion/README.md)를 따른다.

## 명시적 trusted Clock 재검증

`ControlDiagnostics`/`OwnerDiagnostics`/`NativeDiagnostics`/`StartupDiagnostics`는 같은 owner에서
`revalidate_clock`와 `observe_clock`를 제공한다. 이는 신뢰된 로컬 composition API다.
수신 timestamp/정상 packet/INIT 자체가 재검증 권한을 주지 않는다. `ClockRevalidation`은
새 revision·더 큰 recovery epoch·신뢰된 checked Stamp·동일 domain/instance의 established
zero-offset/zero-uncertainty agreement를 요구한다. 다른 kernel/host mapping은 이 경계 밖이다.

새 실제 full8-role Release plan/mask255와 현재 정상 gate/native health를 함께 전달한다.
원래20ms INIT lead/window·2s prepare budget을 유지한다. 해당 same-clock source가100ms
연속 전진하고 age/gap≤30ms인 구간만 수용한다. Cached source는 창을 늘리지 않고 누락·
역행·stale/future·부분 Release·native failure는 창을 만족시키지 않는다. Observed clock
역행/instance 변경 또는 새 Clock fault는 trust를 무효화하여 새 명시적 revision을 요구한다.

원래 Clock occurrence·관련 Fault EventId·발생 횟수·untrusted 검출 시각은 유지한다.
새 Observation/Passed는 ProofControl, `times[Violation]`에 정상 관측창의 첫 source,
`source.source`에 마지막 source, `times[Observed]`에 실제 관측 시각, `measured`에 연속 ns,
`expected_min`에100000000, `state_before`와 proof source sequence에 trust revision을 둔다.
이 source sequence는 로컬 clock-revalidation proof 식별자이며 원본 CAN sequence가 아니다.
자동 clear/권한 발급은 없다. Queue/pending 손실은 기존 sticky Gap/clear 차단을 유지한다.

[사전 protocol](../test-plan/clock-recovery-protocol.md)의 실제 BMS native rollback와
8-role SessionParticipant rollback을 검증한다. Native host의 remote clock-administration
service·hardware clock 복구를 수용한 것으로 확대하지 않는다.

## 비활성 journal 보관·복원

[운영 protocol](../test-plan/diagnostic-retention-protocol.md)의 `tools/archive_diagnostics.py`는
inactive store의 lifetime flock을 독점 확보해 committed prefix·미확정 suffix·incomplete와
pending을 원형으로 보관한다. 새 목적지로만 복원하며 active store/기존 archive를 덮어쓰지
않는다. 용량·ordinal·파일별 hash/size를 공개하고 복원 후 native 의미 재검증을 요구한다.
Archive가 event 용량 회수나 DTC clear를 뜻하지 않는다. 기본512와 명시적 최대4096은
그대로이며 자동 rollover/장기 무제한 retention 수용은 별도다.
