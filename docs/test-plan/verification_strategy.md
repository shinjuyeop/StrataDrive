# Verification strategy

Status: case contract **DEFINED**, 아래 system TC의 runtime result는 **NOT RUN**이다.
현재 component 구현·시험 상태의 기준은 [project_status](../project_status.md)다.
아래 M1/초기 M2의 미구현·수치는 해당 단계의 이력이며 최신 상태를 대체하지 않는다.
[Steering angle field codec](../learning/m1_steering_codec.md)과
[frame codec·DBC parser](../learning/m1_steering_frame_codec.md)의 Host 표현 검사는 실행했다.
Field 단위 결과, M0 document review와 vehicle/SIL verification을 구분한다.
TC ID의 유일한 정의 목록은 아래 표, S/F ID 정의는 [scenario baseline](scenario_baseline.md)이다.
[RG-01](../icd/regenerative_braking_design.md)의 후속 시험 TC-REG-001–005도 아래에 정의한다.
회생 관련 시험은 계획이며 기존 Steering/Brake wire 시험의 PASS를 적용하지 않는다.
[EV-01](../icd/ev_power_bms_design.md)의 TC-EV-001–005를 추가했다. BMS/power/차량 관리의
2026-10-14 [BMS wire 초안](../icd/bms_frame_draft.md)의 DBC/CRC/canonical 부분 검사를 추가했다.
EV C++ codec/receiver·SocketCAN unit과 EV local vCAN 36개 case도 수행했다.
당시 component model/Zone runtime은 미실행이었다. 현재 Host component 범위는 아래 M4 근거를 따르며 전체 system Result는 NOT RUN이다.
[ZON-01](../architecture/zonal_partition.md)의 TC-ZON-001–003을 추가했다.
기존 M1 단위/vCAN PASS는 두 Zone runtime 증거가 아니며 새 Result는 NOT RUN이다.

## Verification layers

### M4 실행한 component 근거

[ADR-0055](../adr/ADR-0055-asynchronous-normal-owner-integration.md)의 정상 비동기 경로를
`tests/integration/runtime/check_m4_async.py`로 검사한다. 단일 실행에서 normal·ASan/UBSan 각각
당시 전체872개 CTest와 영속 grant CLI 재가입을 실행하고 동일 결과를 [component 추적표](component_traceability.csv)에 연결한다.
대표 정상·부분 송신 실패·Actual 상실·정상 종료·새 Epoch 복구의 [CSV/그래프/결과와 재현 절차](evidence/m4_async/README.md)를 Git에 보존한다.
원본 JUnit/로그/모든 scenario CSV는 지정한 `build/` raw directory에 남긴다.
`--reuse`는 source SHA256이 같을 때만 결과를 다시 추출하며 **실제로 시험한 원래 commit**을 유지한다.

논리 clock의 state/fault/expiry 경계 시험과9개 실제 thread의 monotonic wall 관측을 구분한다.
정상 request·arm·TX enqueue result·독립 status/Actual·보호 선택 ACK는 다른 관측점이다.
ACK 성공을 물리 압력 도달·토크0·전원 OFF로 간주하지 않고 actual trace/해당 시험의 별도 assertion을 사용한다.
Native 표본은 SCHED_OTHER·1.8초·고정 speed0·별도 부하 없음이다. M3 FIFO/배치 cohort의 대체나 WCET 증명이 아니다.
기존 timing 실패·학습자 review와 아래 system TC의 **NOT RUN**을 유지한다.

### M4 고장·M3 독립 감시 후속

[ADR-0056](../adr/ADR-0056-m4-faults-and-independent-execution-watch.md)의 `check_m4_faults.py`는 전체 normal/sanitizer908개,
고장/복구 runtime32개씩과 기존 CLI 재가입을 같은 실행에서 추출한다. [최신 근거](evidence/m4_faults/README.md)와56개 추적성을 연결한다.
[사전 프로토콜](m4_fault_timing_protocol.md)로 고정한 native48회는41 PASS/7 FAIL이며 setting/load control48/48 PASS다.
Whole-owner2/4ms 독립 감시와10/20ms 제어 자체5/8ms 검사, body 초과/누락 slot, 실제 물리 적용과 ECU ACK를 분리한다.
Logical 기능, sanitizer 성능, 원격 process/네트워크·전체 system TC는 서로 다른 범위다.
기존 M3 예외·학습자 review·system TC NOT RUN은 유지한다. 물리 응답 CSV의 사후 감사는 새로운 timing 수용 결과가 아니다.

후속 [release-grid/구조 분리·원격 계약 evidence](evidence/m4_followup/README.md)에 당시 전체948개 normal/ASan·UBSan과68개 함수/시험 연결, source별 두48회(각42/6), native TSan8/9 및 remote36/36을 별도로 보존한다. 원본7 FAIL과 당시 TSan1 FAIL을 닫지 않으며 M4 종료는 [검토 중](../m4_exit_review.md)이다. DDS/Zenoh netns echo는 middleware API/queue 실험이며 실제 controller/Actual 배포·session 재가입이나 아래 system TC 전체 결과가 아니다.

### 원격 계약 수정과 OPEN 실패 분석

[사전 프로토콜](m4_contract_review_protocol.md)과 [새 근거](evidence/m4_contract_review/README.md)에
각 결함의 수정 전 실패·수정 후 결과, 원본948개와 신규18개를 구분한다. `1989477` 전체 normal/ASan·UBSan966개씩,
경계 TSan67개·wall9개, 함수/실제 시험/판정86개는 해당 source의 component 결과다.
실제 Central·두 Zone 출력의 codec 왕복→private gate를 가진 다섯 RemoteLeafEndpoint→arm/제어/Actual/Stop을
논리 clock으로 검사한다. 같은 process의 시험 harness이며 실제 remote scheduling/network 단절 증거는 아니다.
Native runtime의 shared global gate/atomic 보호 효과도 실제 원격 보호 전달 보장으로 확대하지 않는다.

Full transport trace는 owner별 bounded log를 join 뒤 수집한다. 최초 sent/원래 context expiry·enqueue·RX·dispatch·
완료·결과 수신을 같은 identity로 연결하며, Leaf handling 완료와 물리 응답 CSV는 별개다.
`f895dc6` 고정 native20+TSan20회(guards off)는40/40 PASS로 과거 실패 미재현이다.
별도 논리12ms/19.8ms result 지연은 expiry/pending 충돌 보호를 구분하며 실제 wall 지연 분포에 합치지 않는다.
`1989477` 48회(guards on/trace off)는41/7, FIFO23/24이고 실패/설정/분모를 모두 보존한다.
계측 trace와 실제 M3 완료 guard의 검출 기능, 수용 timing을 각각 판정한다. SDK source/stack 분석은 새 SDK 실행이 아니며
기존 경고·M4 NOT CLOSED·학습자 REVIEW PENDING·전체32요구/29TC NOT RUN을 유지한다.

### Pending settlement 후속 검증

[ADR-0059](../adr/ADR-0059-pending-command-allocation-settlement.md)와
[사전 프로토콜](m4_settlement_protocol.md)에 따라 pending 배분 보류·원래 시한/authority 감시를 검사했다.
`97afb35` normal/ASan·UBSan 각각973/973(unit800/logical164/wall9), TSan 경계108/108·wall9/9,
Python71/71와93개 component 추적 결과는 [새 evidence](evidence/m4_settlement/README.md)에 있다.
Baseline966 이름은 유지하고7개를 추가했다. 기존19.8ms 재현의 oracle은 기한 전 pending 실패에서
exact expiry 보호로 변경했으며 수정 전 raw/assertion 결과를 보존했다. 양쪽12ms의 기존 applied expiry 보호는 그대로다.
논리 시간의 정상/지속 지연·만료·Stop/rejoin 검사와 실제 monotonic wall 검증을 별도 판정한다.
Runner mock은 실제 Python process exit/수집 계약만 검사한다. 고정 실제40회는Normal20+TSan20 PASS,
별도 기존48회 timing은42 PASS/6 FAIL(FIFO24/24), 모든 control48/48이다. deadline·분모는 그대로다.
과거 native/SDK TSan·FIFO 누락 원인 미확정, Host timing PENDING, system/Target NOT RUN을 유지한다.

### 이전 단계의 부분 검사 이력

[M2 첫 Steering 모델](../learning/m2_steering_model.md)은 manual-clock unit과 세 독립 process의
Command TX → response model → Actual RX vCAN을 실행했다. Functional component 부분 증거이며
vehicle closed-loop/Target timing/전체 system TC Result는 NOT RUN이다.
[Brake 첫 모델](../learning/m2_brake_model.md)은 정상 가압/감압·release와 source-loss 후
floor ramp/high-pressure retain을 같은 model loop에서 검사한다. Full TC Result는 유지한다.

| 검증 계층 / directory | 계획된 검사 | 증거 범위 |
| --- | --- | --- |
| Document review / M0 | architecture 경계, 요구사항, ICD field, 추적성, TBD 담당자 | 설계 검토일 뿐 runtime verification 아님 |
| Unit / tests/unit | CRC/counter golden vectors, 상태 전환, 한계값, dynamics 불변 조건 | Linux software 로직 |
| Integration / tests/integration | vCAN/DDS 계약, timeout/재연결, process isolation | application 통신; 실제 CAN의 전기적 동작에 대한 증거 아님 |
| SIL / tests/sil | Simple Plant 이후 CARLA actual-feedback loop, route tracking | 정해진 scenario/ODD 안의 simulator behavior |
| Fault / tests/fault | loss/corruption/delay/jam/AI invalid/overrun 주입과 복구 | detection, local reaction, DTC, state, plant response 관측 |
| Performance / tests/performance | task timing tail, overload, reference와 tier별 비교 | 지정한 환경의 observed statistics; static WCET proof 아님 |

Steering의 [R25-11 P05 Protect/Check](../learning/m1_autosar_e2e_profile5.md)와 DBC를
공식 예제/Counter 경계/fault/independent CRC로 Host에서 시험했다.
이 범위는 command 수용/timeout이나 TC-COM-002 전체 acceptance가 아니다.
[Steering 수신부](../learning/m1_steering_receiver.md)의 수용/시간/Epoch/timeout은
제어 가능한 clock으로 Host에서 시험했다. 실제 wall-time 검출 지연이나 기존 system TC의
전체 acceptance 결과로 확대하지 않는다.
[Steering SocketCAN fixture](../learning/m1_steering_socketcan.md)에서 Command/Actual의 독립 process
송수신, duplicate/corruption/stale/envelope/cached replay, silent/flood/stop과 timeout latch를 실행했다.
Normal local 관측 timeout은 80.173–80.947 ms다. 이 증거를 kernel overflow 주입, 차량 보호 출력,
전체 TC-COM/TC-SAFE나 임의 부하 timing 보장으로 확대하지 않는다.

[Brake application receiver](../learning/m1_brake_codec.md#application-수신부-추가)와 공통 수신 상태를
추가한 뒤 normal/ASan·UBSan 각각 unit 80개와 vCAN 18개 case를 실행했다.
Brake의 수용/거부/timeout latch는 부분 증거이며 압력 응답/보호 출력이나 전체 system TC의 PASS가 아니다.

[Drive wire/receiver](../learning/m1_drive_codec.md) 뒤 normal/ASan·UBSan 각각 unit 98개와
vCAN 27개 case를 실행했다. Signed torque, valid 0/invalid/cached capability와 입력 age,
독립 actual timeout은 TC-COM-002/003/005와 TC-REG-004의 M1 부분 증거다.
실제 torque zero-target 응답, Central 새 회생 demand 억제/마찰 배분, Host gate 및 에너지는
미구현이므로 전체 TC 결과를 PASS로 변경하지 않는다.

BMS wire의 6개 fixed golden, exact uint64, 336개 byte 변조와 51개 canonical 거부 vector를
Host에서 검사했다. 기존 P05 suite에 48-byte golden/잘못된 DataID/384개 single-bit 변조 case를
추가했다. [BMS domain unit 28개](../learning/m1_bms_codec.md)로 partial validity/independent timeout,
dependency/model identity/parent·expiry·INIT 수용을 수동 clock에서 시험했다. Normal·ASan/UBSan
전체 unit 129개와 DBC/C++ payload 36개가 PASS다. TC-EV-001/002/004의 M1 부분 증거에 연결한다.
EV local wall-time transport 36개 case로 critical/관측 timeout, partial loss/cached dependency,
parent expiry/identity·explicit rejoin과 3-process source-preserving relay도 검사했다.
Drive local HV/torque 통합 gate와 vehicle behavior는 미실행이다.
[M1 session/queue](../learning/m1_session_queue.md)의 영속 issuer/FIFO·continuity latch,
12개 receiver의 old Epoch/counter 200, 실제 application/kernel overflow와 process restart도
검사했다. 전체 unit 143개/vCAN 89개는 local 부분 증거이며 system TC Result는 NOT RUN이다.

첫 C++ field codec에 설치된 GoogleTest 1.11.0을 사용했다. Python 단위 시험의 pytest 적용은
PLANNED다. 빈 테스트를 PASS 처리하지 않는다. Regression은 scenario/seed/config/commit을 고정하고 이후
interface/schema/parameter 변경 시 영향 requirement와 baseline 재검토를 포함한다.

## MBD model and code verification

Status: **M6–M8 계획 / NOT RUN**. [ADR-0052](../adr/ADR-0052-model-based-design-development-path.md)와
[개발 계획](../engineering_plan.md#model-based-design-path)을 따른다. 첫 대상은 Central 종방향 속도 제어기다.
현재 C++ 단위/plant·Host SIL PASS와 새 제어 모델 MIL·동등성 결과를 구분한다.

| 계층 | 실행 대상 / 비교 | 필요한 증거 |
| --- | --- | --- |
| M6 MIL | 실행 가능한 제어 모델 + 종방향 plant | 고정 reference/초기 상태·외란·parameter·sample time/solver에서 추종·제약·fault/state 판정 |
| M8 component SIL / 동등성 | 모델과 컴파일된 수작업 C++에 동일한 input vector replay; 생성 코드 채택 시 같은 harness 추가 | 출력/관련 내부 상태의 수치 오차·mode/validity·허가/거부·INIT 전환 대조, model/code revision과 실패 로그 |
| M8 차량 SIL | 실제 Central controller→allocation→Zone→Leaf→actual→Simple Vehicle/CARLA | 기존 scenario·추종 성능과 fault/timing, 모델 가정·multirate/통신 지연·mapping의 영향 |
| 선택 후속 생성 pilot | 고정 model/tool/config에서 재생성한 code + adapter | 재생성 재현·build/정적 검사·동일 vector/회귀, 생성 코드와 수작업 code의 출처 구분 |

입력 vector는 source time·validity·permission·세션 경계도 포함한다. 속도 유지/증가/감소·지속 saturation 후 회복·
가감속/출력 변화율 경계·정지 부근·stale/invalid speed·허가 상실·새 INIT를 시험한다.
각 case는 제어식/상태 계약과 기존 requirement/TC에 연결하고, 정확한 숫자/매핑은 pilot 전에 고정한다.
초기 연결 대상은 기존 TC-CTRL-002–004 및 TC-COM-005/TC-ZON-003의 해당 부분이며 전체 system Result는 유지한다.

Sample/step·실행 순서·초기 state·parameter·precision·invalid/NaN·saturation/anti-windup과
절대/상대 오차·불일치 판정 규칙을 **결과를 보기 전에** 결정한다(TBD-16; timing TBD-04, tuning TBD-11).
모델과 C++가 같은 production 함수를 호출하는 비교를 독립 설계 검증으로 표시하지 않는다.
모델/코드의 tick별 동등성과 차량 closed-loop 성능·실시간 실행은 별도 판정이다.
도구 선택/생성 설정 변경 시 golden vector·모델/코드 비교와 영향 회귀를 다시 검토한다.
PIL/HIL·Target timing·안전 표준 적합성 결과는 이 계획으로 추가되지 않는다.

## Defined test cases

각 case의 requirement/component/interface는 [traceability](traceability.md)에 있다.
수치와 상세 입력/window는 scenario/timing/safety 계약을 적용한다. 아래 milestone은
구현/실행 계획이며 부분 시험과 end-to-end 결과는 별도 Result ID로 남긴다.

| Test ID | 설정 / 동작 | 관측 가능한 acceptance | Future milestone |
| --- | --- | --- | --- |
| TC-ARCH-001 | 두 보드에 동일 architecture/reference 독립 배포 | Central–Zone logical Ethernet, Zone–vECU vCAN, Host physical Ethernet; 다른 보드 의존 없음 | M0 topology review; M5/M12 runtime |
| TC-ZON-001 | ZON-S01 Front/Rear topology와 routing, vehicle-wide 배분 호출/plant writer audit | Central→각 Zone, Front→Steering/Brake 및 Rear→Drive/BMS; Central 별도 단일 VCU/배분, 원천 metadata 보존, 담당 Zone 우회·중복 actuation 없음 | M4/M5; M6/M7 loop; M12 독립 보드 |
| TC-ZON-002 | ZON-F01 각 Central–Zone link 방향별 loss/partition, Front/Rear/coordinator process 정지, Leaf 정지+Zone heartbeat, delay/replay | 각 critical stream <=100 ms 독립 loss 검출, reject는 valid age 미갱신; 원천 actual/dependency age 보존, local protection/Host gate, raw fallback 없음; physical response TBD-03/12/15 | M4/M5; M6/M7/M9 통합 |
| TC-ZON-003 | ZON-F02 startup missing source, 각 Zone/Leaf/coordinator restart, wrong epoch/late parent request, clear/rejoin | trusted INIT/session과 required power/health 재검증; parent 유효 기간 보존, payload로 epoch 자동 학습/자동 NORMAL 복귀 금지; handshake/budget TBD-12/14/15 | M4/M5/M6/M7 |
| TC-COM-001 | F01 정상 후 Steering Actual 중단 | last-valid RX부터 Zone loss <=100 ms, FAIL_SAFE/Host gate, command fallback 부재 | M2/M4; M6/M7/M9 통합 |
| TC-COM-002 | F02 CRC/duplicate/out-of-order/stale/epoch/restart/wrap | reject/accepted snapshot 유지, valid age 미갱신; 지속 invalid 시 timeout | M1/M2/M4/M5 |
| TC-COM-003 | F03 양수 구동/음수 회생 각각에서 Drive command만 상실, 다른 task/feedback 정상 | <=100 ms local detection, old demand 무효/zero motor torque target, M2에서 고정할 양·음수→0 응답 envelope | M1/M2/M4/M6/M9 |
| TC-COM-004 | F04 Central command/diagnostics 단절; 하위 loss 추가 variant | <=100 ms Zone local timeout, Central 승인 없는 보호, 하위 단절 시 vECU 보호 | M4/M5/M6/M7/M9 |
| TC-COM-005 | actual cached replay/aggregate heartbeat; steering/brake/drive 각 missing/invalid/stale variant | 원천 time/sequence/validity 보존; 각 stream <=100 ms loss 검출, raw fallback 없음, 다음 tick gate | M1 metadata; M4/M5/M6/M7 |
| TC-CTRL-001 | 같은 demand에 steering delay/jam/brake response 변화; writer/topology audit | Vehicle/actuator command와 actual 분리, actual 변화가 plant input에 반영; CARLA writer는 Plant Adapter 하나 | M2/M6/M7 |
| TC-CTRL-002 | S01 직선 30 km/h | 정상 공통 metric/ODD/route completion/loop invariant | M6 precursor; M7/M8 acceptance |
| TC-CTRL-003 | S02 완만한 곡선 30 km/h | 정상 공통 metric/ODD/route completion/loop invariant | M6 precursor; M7/M8 acceptance |
| TC-CTRL-004 | S03 직선→곡선→직선, 30→20 request | 두 plateau speed, route lateral/heading, continuous target 대비 overspeed, 감속 반영 | M6 precursor; M7/M8 acceptance |
| TC-REG-001 | 전진 감속 중 회생 단독/회생+마찰/마찰 단독; actual response 지연 변화 | 공통 wheel 기준 배분, valid regen limit 준수, actual 기반 보정; plant 중복 반영 없음; 응답 오차 TBD-02/03/06 | M2/M4/M6/M7 |
| TC-REG-002 | 회생 한계 감소/0 및 충전 수용 0; Brake saturation/slow response 추가 | Drive local cap 준수, 마찰 재배분, 부족분/원인 기록, envelope 이탈 보호; 전환 budget TBD-03/06 | M2/M4/M6/M7 |
| TC-REG-003 | 감속→저속→정지/hold, 다시 출발 | 저속 마찰 전환/hold, 정지에서 회생 에너지 0; 경계/hysteresis/압력/오차 TBD-03/06 | M2/M4/M6/M7 |
| TC-REG-004 | Capability invalid/stale/cached replay/valid 0; 별도로 Drive Actual loss | capability와 actual validity 분리, 새 회생 demand 억제, cached age 보존; actual loss는 <=100 ms 검출/FAIL_SAFE/Host gate | M1/M2/M4/M6/M7 |
| TC-REG-005 | known actual torque/speed/효율/charge cap fixture; command≠actual, friction-only, 정지, invalid sample | J 집계가 actual 기계적 에너지/충전 한계 이내, friction 제외, invalid는 측정 불가; 수치 적분 오차 TBD-02/03 | M2/M6; M7 mapping review |
| TC-EV-001 | EV-S01 전원 준비→주행→정지→종료; 센서/actuator actual 없는 startup variant | 요청≠power actual, READY≠NORMAL, 유효 health/실제 HV 전까지 normal torque 금지; non-driving INIT 순환 의존 없음; 종료 실제 응답/조건 TBD-12 | M1 handshake; M2/M4/M6/M7 |
| TC-EV-002 | EV-F01 BMS/power/constraint corruption/replay/epoch/valid 0/unknown/loss; Zone 재발행과 Drive cached dependency | reject/invalid 구분, 원천 time/age/validity 보존, critical loss <=100 ms 검출, local protection; rate/age/startup/clock/margin TBD-14 | M1 vectors/receiver/vCAN; M2/M3/M4/M5/M6/M7 |
| TC-EV-003 | EV-S02 SOC/온도/모터속도별 charge/discharge cap 변화, valid 0, Brake saturation/응답 지연 | Drive local 한계/permission 준수와 Central 배분, 실제 응답/부족분, W→N·m 변환 및 zero/low speed 경계; parameter/budget TBD-03/13 | M2/M4/M6/M7 |
| TC-EV-004 | EV-F01/02 precharge timeout/contactor mismatch/sensor invalid/LV/interlock와 Central 단절; clear/reinitialize | Central acknowledgement 없는 고장별 로컬 반응과 actual trace, 자동 복귀 금지; power 재검증과 기존 severity/Host gate; matrix/threshold/deadline TBD-12/14 | M2/M4 component; M6/M7/M9 integration |
| TC-EV-005 | EV-S02 actual DC power/효율/부하 fixture, 구동/회생/full/empty/invalid와 command≠actual | 단일 owner/clock의 battery energy/SOC balance, cap/경계/손실 준수, 마찰 회수·이중 집계 없음; 불일치 clip으로 은폐 금지, 오차 TBD-13 | M2/M6; M7 mapping review |
| TC-AI-001 | inference timeout/NaN/stale/infeasible; fallback input 상실 | AI reject→유효 classical fallback 또는 보호 상태; raw actuator 출력 없음; 전환 budget TBD-10 | M11 |
| TC-SAFE-001 | F01–F04 및 Brake/Drive actual loss/복합 loss/clear | 가용 actuator에 맞춘 FAIL_SAFE/local action, Central 기록과 독립; 물리 세부값 TBD-03/06 | M2/M4 local; M6/M7/M9 integration |
| TC-SAFE-002 | startup missing stream, epoch mismatch, fault clear/new frame/reinitialize | INIT 정상 출력 억제; startup 100 ms unavailable 검출; FAIL_SAFE→NORMAL 자동 복귀 없음; 명시적 INIT gate | M1 handshake; M2/M4/M6/M7 |
| TC-DIAG-001 | fault onset/duration 지정 후 clear/reconnect | fault→event/DTC/state correlation, local action, debounce/persistence 규칙 TBD-08 | M9 |
| TC-PERF-001 | timing trace, 고정 workload/overload | endpoint/clock/causal lineage, Mean/P95/P99/Max/sample/drop/miss/uncertainty 보고; deadline TBD-04 | M3 부분; M5/M7/M12 E2E |
| TC-PERF-002 | logical multirate trace; simulation pause/reset/slow Target | 20/50/100 Hz logical 설정, source frame 재사용 식별; clock별 age, epoch reset, wall-time miss 숨김 없음 | M3/M6/M7 |

SYS-COM-003 coverage는 Steering/Brake/Drive command RX, 세 actual RX, Central→Zone,
각 Host actual stream을 모두 포함한다. TC-SAFE-001에서 actuator별 command/feedback loss를
parameterize하며 F01–F04의 대표 사례만 실행하고 전체 stream이 검증됐다고 선언하지 않는다.
유효하지 않은 actual 자체는 즉시 거부하며 stream loss는 last-valid RX부터 <=100 ms에 검출한다.

SYS-COM-003/004 v0.3의 EV 추가 coverage는 TC-EV-002/004에서 BMS/power/Drive constraint의
critical stream 목록(TBD-14)에 따라 parameterize한다. 미구현 status source와 cached
dependency를 기존 actuator heartbeat로 대체하지 않는다. SYS-PERF-002 v0.3의 BMS task/
publication rate는 실행 전에 결정하며 100 Hz actuator rate와 자동으로 같다고 가정하지 않는다.
ZON-01 v0.5의 독립 Central–Zone routing은 TC-ZON-002/003에서 SYS-COM-003/004, SYS-SAFE-002/003과
SYS-EV-001/004 coverage를 확장한다. Peer heartbeat, BMS source, 각 actuator actual을
독립 판정하며 timeout 물리 반응과 detection 결과는 별도 기록한다.

일부 단계만 통과해 전체 requirement를 VERIFIED로 바꾸지 않는다. 미구현은 PLANNED,
실행 결과는 NOT RUN, 실행 시 필수 TBD 미해결은 BLOCKED다. 반복 횟수/실행 환경과
window를 실행 전에 고정한다(TBD-04/07/11). 실제 run에만 PASS/FAIL을 부여한다.

## Safety analysis and AUTOSAR evidence

[Concept study](../safety/concept_study.md)의 hazardous event 후보와 기존 TC의 연결은
coverage 검토용이다. 승인된 Safety Goal에서 도출된 검증 관계가 아니다. 검출 시험,
local reaction 시험, actual actuator response와 차량 거동 시험의 결과를 구분한다.
Feedback loss 검출이나 simulator tick gate 성공만으로 물리적 위험 회피를 입증하지 않는다.
추가 요구사항·시험이 필요하면 ID/revision과 traceability를 함께 검토한다.

AUTOSAR pilot의 OS 예제, RTE 생성, BSW 통신과 기존 closed-loop 통합은 각각 수행한
범위만 기록한다. 실제 사용한 release, 설정, generator, build/runtime 환경을 결과에
연결한다. Virtual driver/Host 실습의 결과를 MCU/Jetson runtime 또는 실제 CAN timing의
검증으로 확대하지 않는다. RG-01의 추가 TC와 F03 variant는 별도 후속 설계 변경이며
기존 M0 review나 AUTOSAR pilot의 실행 결과로 표시하지 않는다.

## Test case template

- Test ID / version / Requirement ID / Component / Interface ID: TBD
- 목적 / 검증 방법 / 사전 조건: TBD
- Scenario ID / ODD / seed / 초기 상태 / 입력 및 model/profile hash: TBD
- 환경 / build / 보드 / clock / simulator mode / 도구 버전: TBD
- 절차와 주입 대상 / 시작 시점 / 지속 시간 / 복구: TBD
- 관측 가능한 판정 기준 / 수치 threshold / 허용 오차 / 측정 endpoint: TBD
- 필요한 artifact / 실행 시간 / 반복 횟수 / 무효 실행 판정 규칙: TBD
- 정상, fault, edge case의 예상 동작: TBD

## Result template

Result ID (`RES-<test-suffix>-<run-id>`), Test ID/version, Requirement IDs, timestamp,
commit, resolved profile hash, board/environment, scenario/seed, command/procedure,
metric units/clock uncertainty, log/trace/checksum locations, observed vs expected,
verdict와 reviewer를 기록한다.

Verdict는 PASS / FAIL / BLOCKED / NOT RUN이다. Threshold나 환경이 부족하면 BLOCKED,
미실행이면 NOT RUN이다. TBD인 numeric acceptance를 PASS로 표시하지 않는다. Raw data는
`build/` 또는 `benchmark/results/raw/` 등 Git 대상 외부에 보관한다.
현재 component의 작은 공유 summary·CSV·그래프는 `docs/test-plan/evidence/`에 두고,
향후 차량 benchmark summary는 `benchmark/results/`에 둔다. 미실행 시험의 결과 파일을 만들어 PASS로 표시하지 않는다.

## M0 review and results boundary

[M0 baseline summary](../m0_baseline.md)에 exit checklist, 문서 점검 증거와 범위를 기록한다.
M0 review PASS는 runtime TC의 PASS가 아니다. Result ID는 실제 시험 이후에만 부여하고,
현재 traceability의 Future Result는 모두 NOT RUN으로 유지한다. 학습자의 이해 기록은
[학습 원칙](../learning/README.md)에 따라 별도로 남긴다.
