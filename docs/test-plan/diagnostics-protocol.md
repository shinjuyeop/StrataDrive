# 진단 계약 검증 프로토콜

2026-11-02. **집계/store·Central hook·SimpleVehicle 부분 검증 / CARLA fault matrix 후속**. SYS-DIAG-001 / TC-DIAG-001의
Host component·기능 SIL 분해안이다. 새 system TC/Result ID를 발급하거나 과거 시험을
DTC 통합 PASS로 올리지 않는다. Oracle은 [진단 계약](../interfaces/diagnostics.md)이다.
계약 검토 후 아래 component → 기존 경로 연결 →30km/h 고장 통합 순서로 실행한다.

M9-2의 [실제 실행·추적성](evidence/m9_diagnostics_component/README.md)은 synthetic typed event를
사용한 집계/중복·역순/재발·Unknown/clear·bounded failure·journal/commit 복원과 SPSC 검사다.
M9-3은 [SpeedRequest/NormalStop의 실제 판정과 SimpleVehicle 정상/입력 누락](evidence/m9_control_hooks/README.md)을
연결했다. DG-01/02의 해당 fixture, DG-04 source/expiry·DG-06 timeout/rejection의 detector
component 연결, DG-09/11의 원본 시각/ACK 구분과 DG-14 queue failure를 확인했다.
DG-03 response monitor 자체의 DTC 발행, DG-05 실제30km/h 제동 timeout,
DG-06 실제 ACK lane 손실·DG-19 packet→DTC, DG-10 실제 pause/reset 전달,
30km/h CARLA fault matrix는 아직 실행하지 않았다. DG-14의 실제 용량 적합성/장치 crash,
cross-process spool과 원격 전송도 후속이다. 일부 component PASS를 DG 전체 PASS로 올리지 않는다.

## Component 수용 조건

아래 ID는 protocol case이며 실행 가능한 test 이름은 [component 추적표](component-traceability.csv)의
C-M9-DIAG-*에서 연결한다. 검출/선택 규칙의
원본 회귀와 새 진단 집계/storage 검사를 구분한다.

| Case | 입력·경계 | 기대 결과 |
| --- | --- | --- |
| DG-01 정상/초기화 | INIT wait, 정상 주행·NormalStop, cap0, 정상 포화 | confirmed DTC0; startup 허용 구간과 fault를 혼동하지 않음 |
| DG-02 즉시 확정 | qualified SpeedRequest Feedback/Source | SD-1001 한 occurrence; 추가 debounce0, 원본 detect/선택 시각 유지 |
| DG-03 원본 debounce | Brake response의 threshold 직전/정확히 도달/회복, cached polling | 기존 fresh-sample dwell 확정 전 DTC0, 확정 시 SD-3001 하나; cached sample로 count/dwell 증가 없음 |
| DG-04 boundary | source age30ms/30ms+1ns, exclusive expiry 전/동일 시각, timeout 직전/동일 시각 | 원본 monitor와 동일 결과; PI60ms로 gate 완화 없음 |
| DG-05 제동 예산 | 동일 이상적30km/h 입력에 기본5s / 명시적10s config | 원본 NormalStop 결과와 code 일치; SD-1101에 적용 config와 phase 기점 보존 |
| DG-06 ACK 구분 | pending, missing, rejected, 잘못된 epoch/lease/role, expired | pending만으로 DTC 생성 안 함; 실제 Handoff reject/expiry는 SD-1102; 없는 ACK/PowerDown 성공을 합성하지 않음 |
| DG-07 중복/재발 | 동일 ID replay, 같은 occurrence 반복, pass 후 새 fault | 중복 count 불변; 새 qualified occurrence만+1; 최초 원인/시각 보존 |
| DG-08 source 분리 | Front/Rear, command/status, Brake/Drive 동시 loss | 독립 key/occurrence; link를 통한 원인·전파 추적, aggregate 한 개로 뭉개지 않음 |
| DG-09 cause 보존 | 원본 fault 후 UpstreamProtection/ClockError 관측 | 원본 evidence 유지; 전파는 관계, 새 clock fault는 별도 기록; root 미도착은 cause_unknown |
| DG-10 clock | simulation pause/reset, wall clock instance 변경, rollback | domain/instance 보존; 잘못된 latency는 not_comparable; wall 검증으로 확대하지 않음 |
| DG-11 역순/과거 event | 보호/Actual이 검출보다 먼저 collector 도착, 이전 epoch 지연 회수 | causal ID로 연결; detect timestamp/현재 session 권한 변경 없음 |
| DG-12 restart | durable record replay, 새 collector instance/새 INIT | 이력/count 유지, 현재 condition/latch Unknown; replay는 재발 아님 |
| DG-13 journal crash | append·commit·clear 전후 crash, tail partial, 중간 손상, sequence gap, payload mutation | committed prefix만 복원; 손실/손상 명시; false durable/false clear 없음 |
| DG-14 bounded failure | queue full, record capacity, count 한계, disk full/write 오류 | 조용한 drop/evict/wrap 없음; gap health 증거 유지; 기록 실패 중에도 기존 보호 선택·Actual 경로 실행 |
| DG-15 pass | fresh traffic 하나, INIT만 성공, response tracking disabled | Passed로 단정하지 않음; code별 재시험 필요; missing monitor는 Unknown |
| DG-16 clear 거절 | Failed/Unknown, moving/invalid hold, 정상 dispatch 중, stale revision, store 오류 | clear 실패, 이력·제어 latch 불변 |
| DG-17 clear 성공/경합 | qualified pass+stationary/inhibited, clear 중 새 fault, clear-all 일부 fault, request replay | 조건 충족만 durable tombstone; 경합/부분 실패는 거절; 중복 요청 idempotent |
| DG-18 clear 후 재발 | 새 fault와 clear 전 occurrence의 지연 전송 | 새 generation count1, 과거 이력 연결; 늦은 과거 event로 새 generation 생성 안 함 |
| DG-19 F02 rejection | invalid/duplicate/stale packet과 정상 valid traffic 또는 지속 loss | raw Observation 보존, last-valid 갱신 없음; rejection만으로 confirmed DTC 생성 안 함, 실제 timeout은 SD-2001 |
| DG-20 unmapped fault | registry에 없는 실제 reason, root 없이 protection만 도착 | 원본 증거/UNMAPPED 표시; 가짜 root code·정상 판정 없음, 해당 scope 통합 수용 보류 |

기존 회귀의 출발점은 `tests/unit/speed_request_test.cpp`, `normal_stop_test.cpp`,
`vehicle_coordinator_test.cpp`, `command_admission_test.cpp`, `command_gateway_test.cpp`,
`brake_response_monitor_test.cpp`, `steering_response_monitor_test.cpp`다.
현재 회귀 PASS는 새 진단 기능을 검증하지 않는다. 새 구현 시 실제 test/function·결과·
evidence를 component 추적표에 연결하고, 영향 경계의 Normal/ASan·UBSan 검사를 실행한다.
새 동시성 경계를 추가하면 해당 writer/queue의 TSan도 검증한다.

## 기존 경로 연결

먼저 기존 저속 input-loss/NormalStop과 논리 시간 command loss에 event→DTC를 연결한다.
기존 정상·보호 출력과 원본 source/expiry/권한 결과가 유지되는지 비교한다.
DTC writer 지연/실패가 기존 protection selection을 막거나 timeout을 늘려서는 안 된다.
새 replay 결과는 새 물리 실행으로 세지 않는다.

정상 경로는 원래 profile/config로 **confirmed DTC0 + recording gap0**이어야 한다.
고장 경로는 code/key/count/native reason·clock/인과·제어 state·Actual을 함께 판정한다.
기존 log에 DTC가 없다는 사실을 DTC0 PASS로 읽지 않는다.

## 30km/h 고장 통합의 사전 고정 항목

출발 참조는 기존 [30km/h NormalStop fixture](carla-stop30-protocol.md)다. 아래 표는
주입 종류와 oracle의 구분이며 **실제 주입 위치·시각·기간/profile hash가 고정된 실행 recipe가 아니다**.
각 case 실행 전 recipe와 expected code set을 manifest로 고정해야 한다.

| 고장 종류 | 고정할 주입 경계 | 예상 진단·구분 |
| --- | --- | --- |
| 현재 speed 입력 손실 | Central SpeedRequest 인자만 누락; 실제 sensor/다른 traffic 유지 | SD-1001; 실제 command/전체 통신 손실이라고 부르지 않음 |
| NormalStop 제동 시간 초과 | config5s를 별도 profile로 명시; 정상10s control case와 분리 | SD-1101; timeout 뒤 실제 보호/정지·에너지 별도 판정 |
| Brake actuator 응답 고장 | 실제 sensor/actuation 경계의 stuck/지연; command·sensor delivery는 유지 | 원본 response monitor가 확정하면 SD-3001; stopping timeout과 구분, 제동 성공을 가정하지 않음 |
| Stop 인계 ACK 손실 | 특정 Leaf→Zone 또는 Zone→Central의 실제 ACK lane만 차단; 요청/Actual은 유지 | missing 역할/lease·원본 deadline 명시; 최초 실제 detector에 따른 SD-1102 또는 SD-2001 set을 recipe에서 고정 |
| 실제 command/status 통신 손실 | Front/Rear·방향·lane과 살아 있는 owner/센서 명시 | 실제 owner의 SD-2001/SD-2002와 root/전파 연결. ACK-only와 별도 |

ACK가 이미 수용된 뒤의 보호 요청 주입은 기존 stop-protection 시험이며 ACK-loss가 아니다.
ACK/통신 차단 뒤 어떤 expiry/monitor가 먼저 실패하는지는 실제 scheduling·authority에
달려 있다. 기대 code를 결과를 보고 고르지 않는다. 먼저 component에서 결정 순서를
검토하고 full recipe의 code·phase·기점을 고정한 다음 물리 실행한다.

각 recipe에는 다음을 포함한다.

- source/binary/config/profile/route/map hash·seed, clock domain/instance, session/role,
  발생 위치·시각·지속, 원본 last-valid/source/expiry와 expected detector/first reason.
- 검출·보호 요청/실제 선택/ACK·Actual acquisition/관측·body/wheel 정지·HV 상태·
  solver work/단일 EV 정산·DTC enqueue/durable commit을 각각 판정하는 기준.
- 해당 source/timeout의 원래 검출 budget과 물리 budget. 검출100ms를 모든 phase에
  재사용하지 않으며 저속 정지5s를30km/h 고장 전체에 자동 적용하지 않는다.
- 가용 actuator의 기대 동작, unavailable일 때 주장할 수 없는 결과, tick gate 시
  완료 physics/EV 분모·미정산 구간과 containment 판정. Tick 차단은 정지 성공이 아니다.
- store 지연·회수/restart·원인 해소·INIT·clear 후 재발의 검증과 원본 evidence 보관 위치.

전체 M9 종료에는 위 recipe의 실제 기능 SIL과 정상 false-DTC0, 고장별 trace 완전성,
재시작·clear/복구·손실 검증이 필요하다. 이번 설계 문서 작성으로 system TC, wall 실시간,
Target·전체 Reference 수용을 올리지 않는다.

## SD-1001 연속 복구 fixture

M9-4의 실행 recipe는 `ControlRecoverySil.RealRecoveryExplicitSafeClearAndRecurrencePreservePhysicalAndDiagnosticHistory`에
고정한다. Run2001·producer7·simulation instance2001·profile1·Host10ms·20ms SpeedPI,
physical epoch7을 유지한다. 새 source emitter/restart를 합성하지 않는다.

| global elapsed | 주입/행동과 고정 기대 |
| --- | --- |
|10s|현재 SpeedRequest argument만 누락; 기존 detector/보호와 SD-1001 Failed1 |
|12s|argument 복원; epoch1 native fault/gate 유지; Passed/clear 없음 |
|20s|실제8-role trusted INIT2 요청; INIT 자체는 Passed 아님 |
|22s 관측|native SpeedRequest 성공 root가 수용되고 readiness/permission 재검증; Passed·count1/generation1·미삭제 |
|24s|실제 NormalStop root를20ms마다 갱신; 기본 감속/제동5s/shutdown2s 유지 |
|28s|실제 Complete/Stopped/HV-off·fresh stationary Actual로 명시적 선택 clear; expected revision 일치·durable commit |
|29s|writer만 재시작; tombstone/count 보존·현재 condition Unknown; 같은 clear ID는 Duplicate |
|31s|실제 INIT3 요청; 물리 모델/배터리/position reset 없음 |
|36s|argument 재누락; 새 SD-1001 Failed·generation2/count1·이전 event/proof/clear 보존 |
|40s|종료; 물리/EV 연속성·두 epoch 원본 local 선택·journal commit 감사 |

Absolute simulation은 elapsed에1s를 더한다. 고정 입력의 release phase가 INIT마다 다를 수
있으므로 재고장 detector의 기대는 injection부터20ms 이내이며 원본 detector log와 같아야
한다. 측정한1ms를 이전 epoch의2ms로 강제하지 않는다.

복구 음성 시험10개는 epoch/enable·Drive 누락/identity/acquisition 불일치·stale 시각·INIT만
수행한 native controller·power input 누락·diagnostics INIT 누락·미수용 native request다.
명시적 clear는 실제 이동 중/source 누락/stale, revision 불일치·dispatch 미억제·moving 값·
untrusted·writer failure에서 거부해야 한다. Queue/record completeness도 별도로 확인한다.
독립 Python은 journal CRC/commit·native root·원본 owner/Actual·clear·generation/에너지와
8개 손상 거부를 검사한다. [원본/실패·재현](evidence/m9_speed_recovery/README.md)을 따른다.

## 소유자별 검출·복구 fixture

최종 recipe는 `OwnerDiagnosticsSil` source에 고정한다. Run/clock instance3001·Central7,
Front20/Rear21/Steering22/Brake23/Drive24·profile1·physical epoch7·Host10ms·20ms SpeedPI다.
Owner diagnostics는 logical Normal/Fault speed-loop만 지원한다. On/off는 같은 공개 실행
경로/recipe를 사용한다. 별도 wall diagnostic cohort로 해석하지 않는다.

| fixture | 실행·판정 |
| --- | --- |
|정상92s|기존4350 controls·정상 정지/HV-off·local DTC0 |
|Central만 elapsed10s부터200ms 정지|먼저 발생한 gateway 보호를 Leaf root로 추측하지 않음; known propagation Observation·root coverage는 미완료 |
|Central/Front/Rear elapsed10s부터200ms 정지|Leaf만 계속 실행. 원래 context expiry+≤0.2ms에 SD-2001 세 건·local selection; 정지한 상위 owner의 가짜 검출/ACK0 |
|상위 재개|같은 epoch/gate는 보호 유지. 두 Zone의 원래30ms call guard 초과 SD-4002 두 건; violation과 detector call을 구분 |
|elapsed20s|실패한 bounded links를 기존 joined logical 교체 경로로 교체하고 실제8-role INIT2; physical/battery reset 없음 |
|정상 재시험 후|Zone 실제 healthy tick/full input은 Control proof; Leaf 실제 accepted command/healthy body/live context는 Input proof; 각 Passed·count1/generation1·미삭제 |
|24s 종료|2400 physical samples·journal30 events·다섯 원본 occurrence/proof와 분리된 물리 응답 감사 |

Zone SD-2002는 실제 ZoneFeedbackMonitor/Gateway component에서 current input 누락·원본
last-healthy source·fresh 복원만으로 latch 유지·INIT만/닫힌 gate/stale 증거 거부·새 정상
tick으로 Input proof를 검사한다. 이 결과를 차량의 실제 feedback-loss 통합으로 올리지 않는다.
다른 코드/누락 mask가 뒤이어 발생해도 이전 key의 재시험을 보존하는 혼합 고장 검사도 수행한다.

Leaf는 세 실제 owner snapshot 각각에 gate/faulted·success 누락·epoch/enable 불일치·
expired context·71ms dependency·stale body 음성 검사 후 원래 유효 증거만 Passed가 되어야
한다. 기존 receiver의 dependency70ms와 body30ms를 각각 유지한다. Queue overflow는
native 보호를 바꾸지 않으며 collector가 불완전해진다. Local proof를 물리 달성으로 표시하지 않는다.
독립 감사는 canonical CRC/journal·native CSV·원본 owner log·physical 응답/연속성과
7개 손상 거부를 검사한다. [실행·재현·실패](evidence/m9_owner_sources/README.md)를 따른다.

## Gateway·BMS·Power native fixture

Recipe는 `NativeDiagnosticsSil`/`NativeDiagnostics`/`NativePower` source에 고정한다.
Run/clock4001·Central7/Front30/Rear31/BMS32/Power33·profile1·model7·Host10ms이며
store bootstrap은 명시적 registry2다. 기존 registry1 회귀를 별도로 유지한다.

| fixture | 고정 판정 |
| --- | --- |
|정상92s|4350 controls·정상 정지/HV-off·9200 physical samples·root DTC0 |
|Central만 elapsed10s부터200ms pause|live Zone Gateway 두 곳의 실제 context expiry→SD-2001 각각1·원본 ACK; BMS/Power 보호 전달을 root로 만들지 않음 |
|재개·13s 관측|같은 epoch native latch/gate 유지·Failed; traffic 복원만으로 Passed 없음 |
|20s joined link 교체·실제8-role INIT2|같은 physical model/position/sequence 유지; INIT만으로 복구 아님 |
|실제 정상 전송 후·24s 종료|Front2/Rear1 완전 dispatch proof로 두 occurrence Passed·count1/generation1·미삭제; 2400 physical samples |
|Gateway component partial send|실제 Front 두 번째 write 실패→SD-2101; 첫 성공 write 수1/원래 context 유지; 새 INIT/완전 dispatch만 qualified |
|BMS component|실제 native controller 입력4.3V·trip4.25V·40ms dwell로120→160ms 확정; 복원/recovery_ready만으로 latch 유지; 새 INIT와100ms release dwell 뒤 Passed |
|BMS propagation component|외부 Protection110ms 후 자체 trip160ms를 별도 slot에 기록; 전달 자체는 DTC0 |
|Power component|실제 RC plant Ready 뒤 current scalar만 누락→SD-3201; 복원/Off/INIT만으로 Passed 아님; plant reset 없이 새 sequence/HV Ready 뒤 Passed |

Gateway 실제 proof에10개, BMS/Power 실제 proof에 각8개 음성 변형을 적용하고 원래 유효
증거만 통과시킨다. Rear 네 stream 단절은 원래 누락 stream mask/source/expiry를 보존하며
외부 continuity는 후속 poll에서도 전달 관측으로 유지한다. On/off는 같은 runtime recipe의
전 physical 표본/authority와 원래 fault/보호 시각이 일치해야 한다. 독립 canonical journal/
native CSV/ACK/physical 감사와8개 손상 거부를 실행한다. 원본 budget을 완화하지 않는다.
[결과·실패·재현](evidence/m9_native_causes/README.md)을 따른다. BMS/Power 자체 고장 차량
SIL·release 이전 startup·remote wire/spool·Clock 복구·wall/Target는 이 실행으로 수용하지 않는다.

## BMS·Power 자체 입력 손실 차량 SIL fixture

실행 전 고정 recipe: logical Host10ms·physical model7·native run5001/registry2,
24s 실행, elapsed10s부터 BMS electrical 그룹 또는 Power pack-current scalar만 ECU 입력
사본에서 누락,10.2s 복원,20s 기존 joined link 교체/8-role INIT2다. 원래 plant/current·
CAN/권한·threshold/dwell/보호 정책은 바꾸지 않는다. 최초 native BMS InputsInvalid→SD-3101,
Power InputsUnavailable→SD-3201을 기대하며 보호 전달을 자체 root로 만들지 않는다.
검출은 각각 다음 BMS20ms/Power10ms body 이내, 기존100ms 보호·230ms 토크/제동 응답을
유지한다. 복원 후 같은 epoch의 latch/gate·Failed 유지, 실제 정지/contacts-open/낮은 bus를
별도로 확인한다. INIT 자체는 Passed가 아니며 새 정상 BMS Active/release dwell 또는
Power actual HV Ready·current gate/입력 유효성이 필요하다. Passed 이력/count는 삭제하지 않는다.
복구 없는 음성 recipe도 실행하며, 진단 on/off에서 원래 입력 주입·제어/물리/권한은 같아야 한다.

## Release 전 기동 시도 진단 fixture

사전 고정: logical Host10ms·startup run6001·store registry3, session-ack Drive의 prepare/init/
release ACK를 elapsed0–2.5s에 각각 누락한다. Native phase budget(Prepare2s·Init lead20ms/
commit window20ms·owner gap30ms)은 유지한다. 전체 Release 전에도 trusted Attempt와 최초
session detector를 기록한다. Prepare/Init에서는8개 participant Timeout과 Central Timeout,
Release에서는Central Timeout을 기대한다. Abort는 보호 전달이다. 실패한 epoch1의 Session/
Passed·주행 gate는 없어야 한다.3s 기존 joined link 교체·실제 INIT2/full8-role Release 후에만
기동 진단 Control proof/Passed를 허용한다. Native DTC의 기존 positive predicate도 유지한다.
ACK 경로 복원만으로 회복하지 않는 음성 fixture와 collector on/off 동등성을 검사한다.

Prepare 실패로 어떤 actor도 초기화되지 않은 경우 존재하지 않는 보호 ACK를 요구하지 않는다.
원래 실패 plan의 enable0·첫 epoch Release 부재·복구 전 실제 gate closed/torque≤.1Nm/
contacts0/bus≤30V 전 표본을 요구한다. INIT/Release 실패의 기존 보호 기준은 유지한다.
독립 journal/native source/600 physical 표본 감사와10개 변조 거부를 세 phase·두 빌드에서
실행한다. 정상92s/4350 controls는 Attempt1/Session1/DTC0이어야 한다. 연속 실패한 proposal의
서로 다른 occurrence와 중복 방지도 단위 검사한다. [결과](evidence/m9_startup_sources/README.md).

## 원격 진단 wire·유한 spool fixture

실행 전 고정: diagnostic wire v1은 Event와 durable ACK만 전달한다. 원래 canonical event를
바꾸지 않고 stream ID=명시적 source/replica store ID, registry1–3, transport sequence는
source committed journal ordinal이다. 원격 clear/control 명령은 없다. 수신 순서는 정확한
다음 ordinal만 허용하며 미래 frame은 ACK 없이 재전송을 기다린다. 동일 ordinal/동일 bytes는
중복 ACK, 다른 bytes는 sticky incomplete다. ACK는 해당 event checksum과 ordinal을 묶고
수신 journal의 durable commit 뒤에만 생성한다. 손상·잘못된 방향/stream/registry/ACK는
진행시키지 않는다. CRC는 전송 오류 검출이며 인증을 대신하지 않는다.

Non-RT source writer는 기존 bounded journal에 먼저 commit한다. ACK로 원본을 삭제하거나
capacity를 재사용하지 않는다. 재시작한 sender는 ordinal1부터 replay하고 replica는 중복으로
처리한다. Receiver 재시작 시 기존 current condition은 Unknown을 유지한다. 연결 복원·중복
replay는 physical recovery나 Passed/clear가 아니다. 불완전 source/replica에서는 ACK/전송
성공을 주장하지 않는다. 실제 middleware 적용·compaction·보존 용량 수용은 후속이다.

시험은 registry3 Attempt1→Startup fault1→Attempt2→실제 Session2→qualified proof/Passed를
원본 source로 사용한다. Separate Linux process의 AF_UNIX SOCK_SEQPACKET 경계에서 최초
ACK 유실/receiver 종료·sender 재시작·순서 역전/손상·최종 replay를 주입한다. Source/replica
canonical bytes·commit watermark·count1/generation1·재시작 Unknown·미삭제 이력이 같아야 한다.
Unit에서는 작은 capacity·commit 실패/미완성 tail·registry mismatch·mutated duplicate·future
ACK·stream mismatch·원격 clear 거부를 각각 검사한다. 큐 overflow도 원래 제어를 변경하지 않는다.

## SOME/IP 진단 channel·새 logical owner fixture

사전 고정: pinned vSomeIP3.7.6/4187431d2815bd351845a09d01aa85b2a3163cab을 사용한다.
기존 control service/queue/권한은 수정하지 않는다. 별도 diagnostic application·service
0x5d10 Publisher/0x5d11 Replica, instance1/interface1, Data method0x0101/ACK0x0102,
MT_REQUEST_NO_RETURN/reliable TCP에만 wire v1을 bind한다. Callback queue8·wire2048 bytes,
SDK payload2048/local4096·queue16384다. Source/replica store7001·registry3는 명시적으로 생성한다.
Callback은 bounded ingress만 수행하고 journal/fsync는 non-RT writer에서 실행한다.

새 logical SimpleVehicle Central owner/ControlDiagnostics producer7이 SPSC에 publish하는 동안
writer가 원래 Event를 spool로 회수해 별도 netns/veth의 replica로 전송한다. Archived source를
입력으로 사용하지 않는다. Normal92s/4350 controls/DTC0과 speed-input-loss13s·elapsed10s 주입/
SD-1001 한 건을 사용하며 기존100ms 보호·230ms 실제 반응 기준을 유지한다. 수신 측 durable
prefix와 원본 canonical bytes·원래 detector/selection/ACK/Actual·physical/energy를 대조한다.
진단 on/off의 전체 physical/권한 표본은 같아야 한다. Simulation과 monotonic 전송 시각은
별도로 보존하며 이 실행을 native wall 차량 제어 수용으로 올리지 않는다.

손실 case는 최초 Fault commit의 ACK1회 유실→100ms 재시도→Duplicate ACK와, 그 commit 뒤
replica SIGKILL→새 SDK client ID로 같은 durable store 재시작을 각각 검사한다. 연결 복원만으로
Passed/clear를 만들지 않는다. SDK send-return은 전달/commit 증거가 아니다. PCAP에서 실제
TCP의 SOME/IP header와 원본 payload를 복원한다. Process별 /tmp·/dev/shm도 분리해 local IPC
우회를 막는다. 잘못된 service/method/type/version/direction/stream/registry는 ingress 전 거부한다.
기본 unit·logical/ASan·SDK 실제 Normal/ASan과 필요한 동시성 경계를 구분해 기록한다.
Front/Rear의 live source merge·정규 DDS gate·Target·부하/보존 용량 수용은 후속이다.
Host test pacing은 logical1ms마다20µs sleep이며 logical clock/제어 기준을 변경하지 않는다.
이는1:1 wall 실행이 아니다. 원본 Fault가 producer 실행 중 spool에 commit된 증거를 요구한다.

## 원격 context admission component fixture

사전 assertion recipe: run10/Central producer20/local Front30·Rear31, profile1/common monotonic
domain99, stream/store101·102/registry3. 실제 SessionCoordinator와8개 SessionParticipant가
기존 Prepare/INIT/Release를 수행한다. Central StartupDiagnostics가 생성한 원본 Session과
RunLeaseIssuer→원래 owner codec→실제 RunLeaseGate의 accepted snapshot을 사용한다.
Local Ready와7개 Release ACK 상태에는 credit/전역 context가 없어야 한다.

원본 Session 전 로컬 고장은32개까지 대기하고 durable 전송 frame이 없어야 한다.
미확인 context의 Proof/Passed는 NotReady로 거부하며 지연 Session으로 소급 수용하지 않는다.
Lease 만료 후 지연 context는 원래 Session→고장 순서로 commit하되 보호/권한은 유지한다. Wrong issuer/
run/profile/clock/enable/deadline·partial mask는 무기록 거부한다. 다른 bytes의 동일 epoch context,
queue loss/identity·pending capacity·commit capacity·enable 충돌은 incomplete다. 미해결 과거
epoch를 건너뛰지 않으며 새 context 뒤 기존 고장은 Unknown이다. 정상 종료의 미commit 대기도
incomplete로 남긴다. 급작스러운 source 종료의 메모리 손실 복구를 검증했다고 표시하지 않는다.

두 source/replica 쌍은 같은 Central 원본을 각각 보존하고 독립 ACK를 진행한다. 병합 unique
event3개/고장2개, 원본 Session bytes1종, foreign stream ACK 거부를 기대한다. Source 재개 시
original duplicate context/fault로 Unknown이 바뀌지 않아야 한다. 일반/ASan export의4개 journal과
원본3개를 독립 Python parser로 대조하고4개 변조를 거부한다. 기존 native Leaf endpoint의
Ready/credit/expiry/INIT reset snapshot도 회귀한다. 실제 IP/SDK native owner 배선·wall 차량
반응·새 고장 matrix는 이 component 검증의 분모가 아니다.

## Native 3-ECU 진단 배선 fixture

실행 전 고정: 기존 실제 Central/Front/Rear process·netns·8 participant/control TCP와 persistent
plant를 사용한다. 새 logical Network나 archived event를 source로 사용하지 않는다. Run8001,
registry3/profile1/common kernel monotonic clock `0x53444d4f4e4f`다. Central Startup7이 만든 원본
Attempt/Session과 Coordinator/Stop8, Front/Rear·Steering/Brake/Drive20–24, native Gateway/BMS/
Power30–33의 기존 observer를 실제 owner에서 호출한다. Control8은 자체 Session을 만들지 않는다.

Central→Front/Rear context stream8101/8102는 source·receiver journal을 각각 갖는다. 원격9개
source는 독립 stream8200–8208/source·Central replica journal을 사용한다. Service pairs는
context0x5e00–03/source0x5e10–21, instance/interface1, Data0x101/ACK0x102, reliable request-no-return다.
PCAP의 모든 Data/ACK를 source ordinal/원본 bytes와 대조한다. Central merged journal은 동일
Session을 한 번만 저장하며 remote ACK는 replica와 merged의 durable commit 뒤에만 보낸다.

Owner는 원본 snapshot과 bounded SPSC만 사용한다. SDK application을 공유해도 control lane과
진단 callback FIFO8·writer는 분리한다. Writer CPU15/SCHED_OTHER0의 실제 배치를 기록한다.
Control wire/TCP512와 queue8192를 유지한다. Diagnostic endpoint31610–12만 TCP2048을 사용하며
SDK가 요구하는 shared local envelope는 opt-in profile에서1024→2048로 명시한다. Event-only
canonical Data는602 bytes다. 기존 off profile의 설정은 바꾸지 않는다.
유효 Abort/보호 요청은 같은 대상·plan/epoch·clock의 미사용 RunLease만 송신/수신 큐에서
취소한다. 다른 제어/명령/ACK와 이미 actor가 수용한 credit는 지우지 않는다. Queue8은 그대로다.
4-role credit→Abort4→보호의 burst와 다른 plan/peer/clock·Release의 음성을 실제 codec으로
검사한다. 종료 시 보호 cleanup 뒤 진단 ACK를 기다리는 동안 late ingress를 별도 계수해 retire한다.
정상 physical trace의 선행 표본 timestamp는 plant가 atomic으로 넘기고 별도 non-RT observer가
주입 prerequisite marker를 쓴다. 새로운 marker 파일 IO를 plant runnable에서 수행하지 않는다.

Source context pending32·retry100ms·종료 drain2s를 유지한다. Durable 저장은 `/var/tmp`의 새
고유 ext4 directory를 명시하고 원본을 남긴다. Private `/tmp`·`/dev/shm`의 local IPC로 진단을
운반하지 않는다. 종료/join 뒤 artifact copy와 원본을 대조한다. 느린 `/d` 저장에서 관찰한
overflow/timeout과 payload 설정 오류는 실패로 보존하며 용량 수용 PASS로 올리지 않는다.

필수 기능 cohort는 normal, Front/Rear command-loss, 최초 Fault ACK1회 유실, context1500ms
지연의5개다. Normal/ASan과 필요한 SDK-instrumented TSan을 구분한다. 기존 normal readiness/
정지/HV-off와 command-loss의 정상 제어 선행·원본 만료·모든 ECU 보호·실제100ms 물리 기준을
유지한다. 정상 DTC0, 손실에는 target 소유 영역의 실제 Gateway/Leaf SD-2001과 원래 native 원인만 기록하고 보호
전달을 임의 root로 만들지 않는다. ACK 유실은 같은 ordinal의 duplicate와 이력/count1을,
context 지연은 실제 owner의 accepted credit와 pending 후 원본 context→고장 commit을 요구한다.
Code2001/2002의 서로 다른 실제 monitor는 별도 key이며 발생하지 않은 code/Passed/clear는 없다.
Native detector/selection snapshot·control/diagnostic PCAP·journal·physical 원본과 변조 거부를
독립 감사한다. Off profile 회귀도 실행한다. 결정적 on/off physics byte 동등성은 wall 실행에
요구하지 않으며 각 실행의 같은 기존 제어·물리 oracle를 적용한다. Guarded4ms wall trial은
별도 분모이며 실패를 기능 PASS로 바꾸지 않는다. Source kill/rejoin adoption·Clock/Target·부하/
보존 용량·CARLA 전체 matrix·학습자 수용은 여전히 후속이다.


## 진단 전달 재개와 crash window fixture

실행 전 고정: 위 native5개 기본 cohort에 source-restart(Front), rear-restart(Rear), collector-restart
(Central), both-restart(세 ECU 전달 객체)의4개를 추가한다. 추가4개는 같은 기존 command-loss와
최초 Fault ACK 유실을 함께 사용한다. 실제 고장 committed prefix가 생긴 뒤 객체를 다시 열고,
`all` 중 무고장 peer는 기존 owner quiesce 뒤에 연다. 제어 process/SDK/observer는 연속이며
전체 ECU 재기동 시험이 아니다. Pending32·FIFO8·retry100ms·종료 drain2s와 기존100ms 물리 판정은
그대로다. Source context admission을 리셋해 실제 accepted evidence와 원본 Session을 다시 대조한다.

Normal/ASan은9개, SDK-instrumented TSan은 normal/drop-ack과 추가4개를 실행한다. PCAP/원본
검출/control credit·physical/journal 기준은 위와 같다. Reopen checkpoint 전후의 stream/ordinal/
canonical bytes가 같고 최종 journal에도 그 prefix가 남아야 한다. Remote source는 실제 TCP로
ordinal1을 다시 보내야 한다. 재개 직후 모든 기존 record는 Unknown/count1/generation1/uncleared다.
Collector 재개 전의 고장 key는 duplicate retry 뒤에도 Unknown이고 새 고장만 원래 Fault 판정을
반영한다. ACK는 두 journal의 durable commit 뒤에만 허용한다. Service 번호를 바꾼 중복 packet도
검출해야 한다. Restart bytes/상태를 바꾸는 변조를 추가한다.

별도 `DiagnosticsDeliveryProcess.SigkillAtSourceReplicaAndMergedCommitCutsRetainsBytesAndNeverRecounts`
시험은 parent가 실제 commit을 확인한 뒤 child에 SIGKILL을 보낸다. Source commit, replica만
commit, merged reconciliation 완료의3개 경계를 순서대로 중단한다. 새 process가 같은 store를
다시 열어 정확한 원본 bytes·독립 ordinal·중복 count1·Unknown을 유지해야 한다. 새 event emitter를
자동 채택하거나 commit 전 메모리 손실을 복구했다고 판정하지 않는다. Foreign manifest/충돌/
merged 저장 실패와 ACK 차단은 별도 단위 검사한다. 실패/중간 audit 결과도 보존한다.


## ECU process 재기동과 발행자 adoption fixture

실행 전 고정: 기존 native9개 기능 cohort에 front-process-rejoin/rear-process-rejoin2개를 추가한다.
3-ECU `restart-live`의 실제 normal control/physical 선행 표본 뒤 대상 generation1 process를
SIGKILL한다. 생존2 ECU와 plant를 유지하고 독립 보호/기존100ms torque·brake 기준을 확인한 뒤
같은 netns에서 새 process/client ID로 시작한다. 명시적 rejoin 요청과 원래 EpochStore의 새
Epoch2·모든8역할 Release ACK·원래 endpoint의 accepted credit 뒤에만 새 source를 발행한다.
Control/진단 queue·retry100ms·drain2s·clock/4ms·물리 기준은 그대로다.

별도 lifecycle store9101/9102는 process lifetime flock과 fsynced generation 발급을 사용한다.
마지막 unclosed start는 previous_unclean이다. 새 source ID의 상위32bit는 generation-1, 하위는
기존 logical source다. 새 순번1은 Code5001/monitor10의 연속성 미확인 incident로 예약하며 원래
boot 시각과 이전/새 세대를 기록한다. 손실 개수를 발명하지 않고 unmapped로 clear를 막는다.
계속 살아 있는 source만 원래 proof로 새 Epoch의 recovery를 발행할 수 있다.

Fixture는2개 process generation의 독립18개 source/replica와2개 context stream을 provision한다.
미사용 생존 ECU의 두 번째 세대 store는 비어 있어야 한다. 새 client는 이전 세대의 검증된
committed prefix를 원형 재전송하고 uncommitted suffix는 byte 그대로 남겨야 한다. Collector는
동일 원본 Session/EventId/bytes를 dedup하고 두 store commit 뒤에만 stream별 ACK한다. 이전
source의 complete/tail 보고와 실제 journal을 독립 비교한다. 기본 Outbox의 incomplete 차단은 유지한다.

Normal/ASan은11개 기능 cohort, SDK TSan은 normal/drop-ack와 두 process rejoin을 구분해 실행한다.
기존 객체 reopen은 별도이며 full process 성공으로 바꾸지 않는다. 독립 auditor는 실제 old PID의
SIGKILL·생존 PID 동일·두 원본 Release·accepted credit18개·source producer/sequence·새 SDK
client의 old ordinal1 replay·원형 source/replica/merged와 물리 보호/새 정상 정지·HV-off를 비교한다.
발행자 재사용/marker 제거/원래 boot 변조/credit/두 번째 handshake/old replay/물리/lifecycle/tail
보고의9개 변조를 거부한다. Unverified continuity의 root 원인을 임의로 차량 고장에 연결하지 않는다.

별도 `KilledVolatileQueueGetsFreshProducerAndExplicitUnverifiedContinuity`는 실제 child가 lifecycle/
Session을 commit하고 EventQueue에 원본 fault를 발행한 뒤 writer drain 전에 SIGKILL한다. 이 event는
어느 source journal에도 나타나지 않아야 한다. 새 generation은 ID를 재사용하지 않고 별도 marker만
기록한다. Root event를 재구성하거나 ACK했다고 표시하지 않는다. Lifecycle wrong manifest/time/
capacity/lock·read-only prefix/clear 차단은 component 시험한다. 전체 system TC·Central process
재기동·host clock/power cycle·실제 부하/용량·연속성 reconciliation/clear 수용은 후속이다.


## Central process 재기동 fixture

사전 고정: 기존11개 기능 case에 central-process-rejoin(control case central-rejoin)1개를 추가한다.
실제 정상 control/physical·9개 원격 source 최초 committed prefix·두 context ACK·8개 실제 Release
ACK의 writer flush 뒤 Central1을 SIGKILL한다. 같은 Front/Rear PID·plant를 유지하고 독립 보호와
원래100ms torque/brake 반응을 관측한다. 명시적 startup 요청 뒤 Central2의 새 SDK client·실제
Epoch2/8-role Release·accepted credit18개·새 정상 운전/정지/HV-off를 확인한다.

Trusted issuer 범위는 Epoch1의7과 Epoch2 이상의(1<<32)|7이다. 잘못된 issuer/범위·중복 ID·빈
manifest·local ID·17개 범위는 거부한다. 실제 새 credit 없이 successor Session을 채택하지 않는다.
새 issuer 채택 뒤 sender ACK0부터 재전송하며 새 replica는 원본 ordinal1부터 commit/ACK해야 한다.
Central2의 준비/EpochStore IO에는 기존 ingress quiesce를 적용하고 폐기 수를 남긴다. 정상 제어의
queue/deadline 예산을 늘리거나 이미 관측한 overflow를 지워 통과시키지 않는다.

이전 merged/9개 replica의 committed prefix를 새 store로 가져온다. 이전 store·suffix·incomplete를
보존하고 독립 auditor로 watermark/bytes/보고값을 대조한다. 단위 시험은 실제 uncommitted tail,
foreign registry, 동일 ID 충돌도 검사한다. Source/replica/새 merged의 원형 bytes·DTC 중복 집계 없음·
SD-5001 uncleared를 확인한다. 정상 복귀와 replay는 unknown volatile loss의 복구 증거가 아니다.

Normal/ASan은12개 case를, SDK TSan은 normal/drop-ack/Central process 재기동을 단독 실행한다.
모든 실패/timeout/cleanup·source/binary/config/도구 hash를 보존한다. 독립 auditor는 두 실제 process,
8개 실제 ACK씩의 원래 수신 시각, 원본 Session/credit, 새 client의 모든 remote ordinal ACK와
fresh replica ordinal1, lifecycle9100의 unclosed start/new generation/explicit close를 확인한다.
issuer/Release/prefix/tail/gap/boot/credit/fresh ACK/ordinal1/clear/physical/survivor12개 변조를 거부한다.
Native4ms/Target·host clock 변경·무한 반복·연속성 reconciliation/clear·TBD-08 수용은 OPEN이다.


## 연속성 로컬 서비스 심사 fixture

사전 고정: 별도 service journal9000/registry4에 canonical SD-5001 incident를 원형 보존한다.
주입 가능한 logical monotonic clock99/run10/profile1을 사용한다. 실제 coordinator/8-participant의
Epoch2 Release와 두 endpoint의 accepted RunLease 뒤 ContextualOutbox의 source500/501 및 별도
replica에 원본 context/incident를 commit/ACK한다. Epoch3의 실제8-role handshake/credit 뒤 모든
stream의 원본 prefix와 ACK가 일치해야 한다. 물리 정지 입력은 service component의 typed fixture
입력이며 실차/native plant 또는 wall 성능 관측으로 표시하지 않는다.

Trusted 서비스 요청 AcceptUnknownHistory가 있어야 전체 manifest를 검사한다. 누락/중복/foreign
stream·incomplete/tail·pending·queue 유실·미완료 ACK·stale/moving/dispatch 허용·잘못된 Session/
clock/revision/proof·미심사 다른 incident·일반 unknown cause·budget 초과는 거부한다. Service
proof가 과거 loss-free를 뜻하지 않음을 원본 unknown/unmapped bytes와 count1로 확인한다.

로컬 writer child가 Proof/Review/Passed/Clear의 fsynced watermark를 parent에 알린 직후 실제
SIGKILL한다. 네 독립 case의 새 writer는 committed prefix만 복구하고 condition/latch Unknown·
count1/generation1·원래 incident bytes·이미 commit된 disposition/clear만 유지해야 한다. Duplicate
Review나 과거 proof로 현재 Passed를 재활성화하지 않는다. 별도 새 검사/심사/Passed/clear의 성공
경로도 unit에서 확인한다. 오래된 registry3는 Review를 저장하지 못하고 remote Event Data는 local
Review/Clear transaction을 수용하지 않아야 한다.

독립 Python reader가 registry4/tag2와 기존 tag0/1·commit watermark·원래8 ACK씩·accepted credit4개·
source/replica/stream cut/CRC·explicit disposition·Passed/clear 순서/revision·SIGKILL·미확인 원본 보존을
감사한다. disposition/incident/proof/부분 범위/ordinal/replica/Release/credit/움직임/clear revision/
가짜 kill/Passed 제거의12개 변조를 거부한다. Normal/ASan4컷씩을 별도로 보관한다.

기존 native12개 Normal/ASan과 SDK TSan normal/drop-ack/Central rejoin3개를 회귀한다. 이들 native
경로는 Review를 자동 발행하지 않고 기존 SD-5001 clear 차단을 유지해야 한다. Compile/초기 test/
regression 실패·source/binary/config/tool hash와 원본 분모를 모두 보존한다. Native 서비스 요청
인증/인가·quiesce/최신 물리 evidence 연결·remote RPC·TBD-08·native4ms/Target 수용은 후속이다.


## Linux 로컬 연속성 서비스 요청 fixture

실제3-ECU 서비스 운용과 구분하는 연결 component 검증이다. 기존 clock99의 실제8-role
coordinator/participant·Epoch2→3·두 accepted endpoint credit·source/replica fixture를 쓴다.
생산자를 끝낸 뒤 실제 Outbox ACK를 보존하고 FileJournal lifetime flock을 별도 서비스 process가
인수한다. 실행 중인3개 ECU의 RT/SDK 생산자 quiesce를 구현/검증한 것으로 세지 않는다.
Actual 값은 결정적 주입이며 실제 차량/plant 정지 측정은 아니다.

- Private0700 directory/0600 AF_UNIX SOCK_SEQPACKET listener를 caller가 provision한다.
  서비스는 SO_PEERCRED의 고정 UID/PID와 nonzero16-byte boot capability를 모두 검사한다.
  Fixture capability는0x42 반복이며 실사용 비밀이 아니다. 다른 PID child와 잘못된 capability는
  capture/저장 없이 거절한다. 서비스 actor·run·Session·incident는 수신 packet으로 만들지 않는다.
- 별도 SDS v1 요청76byte/SDR v1 응답32byte를 사용한다. 진단 SOME/IP Event-only wire는 유지한다.
  Review 요청은 정확한 revision과 AcceptUnknownHistory, Clear는 별도 요청과 disposition=None이다.
  요청번호 n의 proof/review/Passed는4n−3/4n−2/4n−1, Clear는4n이다. Actor는 매 lifetime 새로
  provision한다. 최대32개 증가 요청을 캐시하고 동일 bytes 재요청은 원래 receipt를 반환한다.
  다른 bytes 재사용·범위/boot/시대 불일치는 거절하며 cache를 퇴거하거나 예산을 늘리지 않는다.
- FrozenContinuity guard는 acquire부터 모든 commit까지 같은 source/replica/ACK/queue 경계를
  소유한다. 최신 정상 dispatch 차단·Actual 취득은 trusted adapter 책임이다. 요청에는 물리
  evidence를 싣지 않는다. Guard가 없거나 완전한 고정 manifest를 검사하지 못하면 쓰지 않는다.
- Drive/Brake Actual을 실제 codec/E2E/application receiver/current_sample에 통과시킨다.
  바퀴·torque·pressure 취득 시각은 now보다 각각1000/2000/3000ns 이전이다. 원래 각 시각을
  보존하며 기존 정지·age30ms·skew20ms 기준을 쓴다. Review는 proof 전/Review 전/Passed 전,
  Clear는 전체 cut 검사와 commit 전에 다시 취득한다. 연속 취득 간격도30ms를 넘으면 거절한다.
- Review는 clear를 실행하지 않는다. Clear는 이번 서비스가 성공시킨 Passed ID·정확한 revision·
  동일한 전체 stream cut와 새 물리 evidence를 재검사한다. 새 source append나 중단된 재심사,
  capture 예외·저장 실패 뒤에는 이전 Passed로 clear하지 않는다. 정상 dispatch/INIT 권한은 없다.
- 실제 서비스 writer를 proof/Review/Passed/Clear의 fsynced commit 직후 각각 SIGKILL한다.
  재개는5+cut개 entry·Unknown condition·원형 unknown incident·cut4에만 clear tombstone을 요구한다.
  UID/PID 인가 결과·request 원본·11쌍 Actual payload·16 Release ACK·4 accepted credit를 보존한다.
  독립 Python codec/P05/원본 시각/stream cut/승인 순서 감사와16개 변조 거절을 요구한다.

실행 target은 `remote_diagnostics_context_test`의 ContinuityServiceTest와
`diagnostics_delivery_process_test`의 실제 Unix peer/SIGKILL case다.
`STRATADRIVE_CONTINUITY_SERVICE_TEST_DIR`로 새 export directory를 지정한 뒤
`tests/integration/diagnostics/audit_continuity_service.py <directory> --mutations`로 감사한다.
일반 전체/ASan 영향 범위·독립 TSan 경계·정적 검사·Release 빌드는 별도 분모로 기록한다.
실제3-ECU 서비스 owner/SDK quiesce·fresh global Epoch 후 물리 정지 취득 조합·원격 인가/운용,
TBD-08·native4ms/Target·M9/학습자 수용은 OPEN이다.

## Native3-ECU terminal 연속성 서비스 fixture

Linux local service component를 실제 SOME/IP3.7.6 ECU/owner/plant 경로에 연결한다.
`front_run.py --three --simple-vehicle --diagnostics --diagnostic-service --cases central-rejoin`
전용 opt-in이다. 기존 native-watch4ms/RT 수용과 구분하며 control FIFO8·ACK/RunLease·
18ms permission·10ms renewal·2500ms NormalStop·2000ms diagnostic drain 예산은 유지한다.

- Central1을 실제 SIGKILL하고 생존 Front/Rear·SimpleVehicle을 유지한다. 기존100ms 물리 보호
  기준과 원래9개 source/2개 context의 replay/ACK를 검사한다. 새 Central2의 Epoch2/실제8 ACK·
  accepted credit 뒤 정상 운전·NormalStop/HV-off를 완료한다.
- 별도 명시적 operator startup 요청으로 같은 Central process/SDK에서 Epoch3를 발급한다.
  보호 ACK 후 EpochStore IO는 비실시간 작업에서 수행하고 기존 owner가 수신을 계속 처리한다.
  실제8-role handshake·전 source accepted credit 뒤 다시 정상 운전·NormalStop/HV-off를
  완료한다. 서비스 Review가 INIT/Epoch/actuator 권한을 발행하지 않는다.
- Central이 명시적으로 보호를 요청한 뒤 Front13/Rear114/Central128의 실제 normal gate를
  닫고 원래 보호 선택을 확인한다. 각 owner가 마지막 진단 capture 뒤 quiesce한다. Front/Rear
  queue/pending/실제 ACK를 끝낸 후에만 Central collector를 quiesce한다. 원래2s drain을 넘기지 않는다.
  SDK/제어 owner/plant는 보호 상태에서 Actual을 계속 생산한다. 진단 생산자의 재개는 허용하지 않는다.
- 원래 source/replica/merged file의 lifetime flock을 비실시간 service writer(CPU15/SCHED_OTHER)가
  인수한다. 실제 freeze report의 epoch/stream/producer/watermark/ACK/queue health를 검사하고,
  고정9개 source와 exact replica 전체를 hold한다. 기존 merged는 Event-only로 보존하고 별도
  registry4/store8900 service journal에 원형 prefix만 가져온다. 이전 저장소/suffix를 repair하지 않는다.
- 최신 current_sample의 wheel/torque/pressure가 전 writer의 freeze보다 뒤에서 취득됐는지
  확인한다. Service 준비에서 최대200ms 기다릴 수 있으나 evidence age30ms/skew20ms·정지 값은
  그대로다. 이후 request window2s·연결당 packet readiness100ms·최대16 connection의 유한 fixture다.
  Owner snapshot 시각을 현재로 가장하지 않고 서비스의 독립 monotonic now로 age를 재평가한다.
- Private0700 storage/0600 Unix socket·SO_PEERCRED의 supervisor UID/PID·별도 boot capability를
  쓴다. 실제 다른 PID·잘못된 capability·미명시 disposition·과거 Epoch·stale revision을 거절한다.
  명시적 Review3의 proof9→Review10→Passed11 뒤 동일 요청은 같은 receipt, 다른 bytes는 Conflict다.
  별도 Clear4/ID16만 같은 cut/Passed revision·새 정지 evidence를 재검사해 SD-5001 한 건을 해제한다.
  다른 DTC와 원형 unknown history/count/generation은 보존한다. 전체 service journal 증분은 정확히4다.
- 독립 감사는 PCAP의 owner CRC32C·CAN P05와 원래 Drive/Brake Actual의 값/취득 시각,
  서비스 구간의 유한40000개 acquisition 기록에서 물리 producer의 동일 timestamp를 서비스5개 관측과 연결한다. 물리→CAN 양자화는 원래
  resolution의 절반(.05Nm/.005rad/s/500Pa)만 허용하며 현재 stationary wheel/body는0이어야 한다.
  실제3개 global Session·24 Release ACK·27 accepted credit·11 stream 전체 Data/ACK·원형 prefix,
  source→collector freeze 순서·closed role mask·exact9 cuts·local 인가/duplicate/별도 clear를 감사한다.
  변조17종을 각 정상 자료에서 모두 거절해야 한다.

Normal/ASan·SDK TSan을 독립 실행하고 기존 native12개 Normal/ASan 및 TSan normal/drop-ack/
Central rejoin3개를 회귀한다. 새 service/기존 campaign의 실패·timeout·강제 cleanup·raw PCAP·
원본 persistent store와 artifact copy·당시 source/binary/config/tool hash를 모두 보존한다.
Terminal service 뒤에는 ECU/SDK를 정상 종료한다. Service 후 정상운행 재개·일반 production
service/RPC·다른 host/clock/반복 세대·TBD-08·native4ms/Target·M9/학습자 수용은 OPEN이다.
