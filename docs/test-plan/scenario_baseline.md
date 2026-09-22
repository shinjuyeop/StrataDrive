# Reference scenario baseline

Status: **DEFINED / StrataDrive Reference Baseline v0.1**.
Scenario/test execution은 **PLANNED / NOT RUN**이다. OpenSCENARIO 파일, CARLA runtime,
측정 결과를 포함하지 않는다. 아래 수치/구간 규칙은 engineering starting point이며
production acceptance가 아니다. Owner는 project owner(시나리오/검증 역할)다.

## Common inputs and measurement rules

정상 S01–S03은 [Reference ODD](../requirements/system_requirements.md) 안에서 수행한다.
초기 ego는 reference path의 rear-axle reference point에 정렬하고 INIT gate를 통과한 뒤
출발한다. Sensor/state → Planner → Safety Supervisor → Controller → Zone → vECU → actual
feedback → Plant Adapter 경로와 Reference logical rates를 모두 적용한다.
실행 전 map/route/seed/차량 geometry, 시작/종료 marker, profile/requirement revision을 고정한다.

Planner의 **구간 speed request**와 Safety/Controller가 사용하는 **연속 validated target
speed `v_ref(t)`**를 구분한다. 예를 들어 S03의 request 30→20 km/h는 즉시 물리 속도를
20으로 바꾸라는 뜻이 아니다. 연속 감속 target profile은 M8에 사전 고정한다(TBD-11).
Profile은 실제 속도 결과를 본 뒤 뒤따라가도록 수정할 수 없으며 정상 plateau는 반드시
요청된 30/20 km/h에 도달해야 한다. VehicleCommand는 이 target과 Central PID의 acceleration demand, curvature/braking
의미를 Zone에 전달한다. Test는 request와 validated reference를 모두 기록한다.

| Metric | Sample / 평가 구간 | PASS 후보 (현재 requirement v0.1) |
| --- | --- | --- |
| steady-state speed error | `abs(v_ego - v_ref)`; 각 일정 target plateau에서 사전 정의 settling 구간 후 모든 sample의 max | <=1 km/h; plateau별 별도 판정 |
| lateral cross-track error | rear-axle center의 reference path 최근접 진행 segment에 대한 signed normal distance의 absolute 값 | 전체 active route의 P95 <=0.3 m |
| heading error | reference path tangent 대비 ego yaw를 [-180,180) deg로 wrap 후 absolute 값 | 전체 active route의 P95 <=3 deg |
| overspeed | 각 ego state 시각과 정렬된 positive `v_ref(t)`; `(v_ego-v_ref)/v_ref`의 max | <=0.10; 출발/곡선/감속 transient도 포함 |
| loop integrity | source/command/actual lineage, writer audit, feedback age/state, run gate | 우회/복수 writer/invalid actual 사용 없음 |

Reference settling allowance는 **plateau 시작 후 5 simulation seconds**, 그 다음
**최소 10 simulation seconds**를 steady-state window로 고정한다. 이는 transient와
steady tracking을 분리하기 위한 초기 평가 규칙이며 실측 settling time이 아니다.
각 plateau는 해당 window를 확보하도록 route를 M7/M8에 선택한다. Settling이 느리다는
이유로 window를 사후 이동하거나 error가 작은 구간만 선택하지 않는다.
연속 target transition의 duration/slope는 M8(TBD-11)에 고정하고 그 구간의 speed error도
별도 보고한다. Zero target에서는 percentage가 정의되지 않으므로 overspeed를 N/A로
표시하고 steady-state absolute error를 사용한다. INIT/정지 중 uncommanded propulsion은
허용하지 않는다. 0–40 km/h ODD 전체의 stop/launch 성능을 30 km/h 시험만으로 입증하지 않는다.

Tracking metric은 20 Hz plant/state sample을 사용하며 목표/reference를 같은 simulation
시각으로 정렬한다. P95는 정렬된 N개 absolute sample의 `ceil(0.95*N)`번째 값
(nearest-rank, 1-based)이다. 시간 weighted 평가와 혼용하지 않는다. N, Max, P95,
누락 sample 수와 전체 run duration을 함께 보고한다. Delayed transport 때문에 나중에 받은
state도 원래 simulation 시각을 사용한다. Heading/cross-track은 초기 active route부터
종료 marker까지 평가하며 settling 구간을 빼지 않는다.

정상 PASS 후보는 관련 수치, ODD, route 완료, 모든 경계/invariant 충족이다.
Runtime fault/run gate/계약 위반으로 조기 종료하면 FAIL이다. 필요한 데이터 누락,
미고정 route/profile/clock 조건으로 판정 불가면 BLOCKED이며 PASS 처리하지 않는다.
시작 전 인프라 문제로 실행하지 못한 경우도 원인을 기록한다. 현재 모든 Result는 NOT RUN이다.

## S01 — Straight Speed Tracking

- 목적: 직선에서 longitudinal controller의 기본 steady-state speed tracking 검증.
- Input: 맑은 낮/포장 직선, 정렬된 ego, target speed request **30 km/h**, fault 없음.
  출발 reference와 30 km/h plateau, route 종료 marker를 실행 전에 고정한다.
- Expected behavior: valid startup 후 30 km/h를 추종하고 직선 경로를 유지한다.
  Zone allocation과 각 vECU actual response를 통해서만 차량이 움직인다.
- 주요 측정: speed error/overspeed, cross-track/heading P95, actual torque/brake/steering,
  command→actual lineage, completion와 timing trace.
- PASS/FAIL 후보: 공통 판정 전부 적용; 30 km/h steady window max error <=1 km/h,
  cross-track P95 <=0.3 m, heading P95 <=3 deg, positive target 대비 overspeed <=10%.
- 관련 requirement: SYS-ODD-001, SYS-ARCH-002, SYS-CTRL-001/003/004/005/006/007, SYS-PERF-002.
- Test / 향후 milestone: **TC-CTRL-002**; M6 simple-plant precursor, M7 route/mapping,
  M8 CARLA classical driving acceptance. Result: **NOT RUN**.

## S02 — Curved Path Tracking

- 목적: 완만한 곡선에서 lateral path tracking 기본 성능 검증.
- Input: 신호등/복잡한 교차로 없는 완만한 곡선, target speed request **30 km/h**,
  초기 pose/곡률/path tangent가 고정된 route, fault 없음. 곡선 plateau의 평가 길이 확보.
- Expected behavior: 30 km/h를 유지하며 curvature에 맞게 조향한다. Steering actual의
  delay/saturation을 통과한 결과로 path를 추종하며 Controller command를 actual로 쓰지 않는다.
- 주요 측정: cross-track/heading P95와 Max, speed error/overspeed, Steering Command↔Actual,
  saturation/availability, route completion.
- PASS/FAIL 후보: cross-track P95 <=0.3 m, heading P95 <=3 deg, steady speed error <=1 km/h,
  overspeed <=10%, 공통 경계와 route 완료. 수치 미충족 또는 run gate면 FAIL.
- 관련 requirement: SYS-ODD-001, SYS-ARCH-002, SYS-CTRL-001/003/004/005/006/007.
- Test / 향후 milestone: **TC-CTRL-003**; M6 geometry precursor, M7 CARLA curve/calibration,
  M8 lateral control acceptance. Result: **NOT RUN**.

## S03 — Combined Route

- 목적: longitudinal + lateral 통합 동작과 구간 감속 command 검증.
- Input: **직선 → 완만한 곡선 → 직선**; 초기 request **30 km/h**, 곡선 진입 전
  고정 route marker에서 **20 km/h 감속 request**를 넣고 이후 유지한다. 30/20 plateau와
  연속 target transition은 사전 고정한다. 20 km/h 선택은 0–40 ODD 안의 명확한 감속
  관측점을 만들기 위한 engineering choice다.
- Expected behavior: safety 검증된 감속 reference를 따라 speed를 낮추면서 경로를 유지한다.
  Drive/Brake allocation의 상충 처리가 명시되고 actual response가 차량에 반영된다.
- 주요 측정: 30/20 plateau 각각의 speed error, transition speed/overspeed trace,
  전체 route cross-track/heading P95, torque/brake/steering actual, completion/lineage.
- PASS/FAIL 후보: 두 plateau 각각 max error <=1 km/h, route cross-track P95 <=0.3 m,
  heading P95 <=3 deg, 연속 positive `v_ref(t)` 대비 overspeed <=10%, 공통 invariant 충족.
  감속 request 미반영/plateau 미도달/route 미완료는 FAIL; reference 미고정은 BLOCKED.
- 관련 requirement: SYS-ODD-001, SYS-ARCH-002, SYS-CTRL-001/003/004/005/006/007, SYS-SAFE-002.
- Test / 향후 milestone: **TC-CTRL-004**; M6 combined precursor, M7 route,
  M8 integrated control acceptance. Result: **NOT RUN**.

## Fault scenario common rules

유효한 command/actual feedback으로 NORMAL에 진입한 뒤 지정한 stream 하나에 fault를
주입한다. 원인 분리를 위해 기본 case는 나머지 stream을 정상 유지한다. Test마다 target,
onset/duration, clock, last valid RX, reject/detect/local action/state/actual response/Host gate를
기록한다. Fault는 timeout 관측까지 유지하고 명시적인 recovery 요청으로만 복구한다.
검출 판정은 monotonic wall time의 `t_detect - t_last_valid_rx <=100 ms`이며 simulation
replay 결과는 별도 표시한다. Fault duration/seed/repetition은 실행 protocol에서 고정한다.

### F01 — Steering feedback loss

- 목적 / input: 정상 Steering Actual 이후 vECU→Zone feedback만 중단; command는 정상 유지.
- Expected: Zone이 <=100 ms 안에 loss를 검출하고 STEERING_ECU_LOSS/local FAIL_SAFE를
  발생시킨다. Steering unavailable이 Host에 전달되거나 Host 자체 timeout으로 검출된다.
  Actual loss 시 raw command fallback은 금지하며 Plant Adapter는 다음 tick을 gate한다.
- 측정 / PASS 후보: Zone/Host 검출 시각과 원천 age, fault/local state, gate, raw fallback 부재.
  Bridge가 마지막 actual을 계속 publish하는 변형에서도 원천 age가 갱신되지 않아야 한다.
  F01의 fault 검출/containment PASS가 steering을 잃은 차량의 물리 정지 PASS는 아니다.
- 요구: SYS-COM-001/003/004, SYS-CTRL-002, SYS-SAFE-001.
- Test / milestone: **TC-COM-001**, bridge 변형 **TC-COM-005**; M2 feedback fixture,
  M4 Zone loss, M6/M7 Host gate, M9 통합. Result: **NOT RUN**.

### F02 — Invalid/Stale actuator command

- 목적 / input: 마지막 valid command 이후 CRC 오류, duplicate/out-of-order sequence,
  stale timestamp/epoch를 각각 주입한다. 오류가 age limit을 넘도록 반복되는 변형도 포함한다.
- Expected: 수신 vECU가 invalid frame을 reject하고 accepted demand 및 last-valid RX를
  바꾸지 않는다. Valid-command age는 계속 증가하며 timeout 시 local protection에 진입한다.
- 측정 / PASS 후보: reject reason/count, accepted sequence/demand, age 연속성,
  <=100 ms loss 검출, timeout action. CRC/sequence/freshness 각 variant를 별도 판정한다.
- 요구: SYS-COM-002/003, SYS-SAFE-001/003; Drive variant는 SYS-SAFE-004.
- Test / milestone: **TC-COM-002**; M1 vectors/codec, M2 receiver/local timeout,
  M4 Zone, M5 DDS equivalent validation. Result: **NOT RUN**.

### F03 — Drive command loss

- 목적 / input: 정상 positive drive torque demand/actual 이후 Zone→Drive command만 중단.
  Drive task와 feedback TX는 계속 실행한다.
- Expected: Drive vECU가 <=100 ms 안에 독립 검출, old demand 무효화, FAIL_SAFE와
  zero-propulsive-torque target 선택. Actual torque는 dynamics를 거쳐 feedback으로 보고한다.
- 측정 / PASS 후보: detection/target 선택 시점, local state, torque actual trace.
  Timeout 이후 uncontrolled torque 유지 금지. Actual torque 감소 envelope/deadline은
  TBD-03으로 M2 test 전에 확정하며, 없으면 물리 반응 판정은 BLOCKED다.
- 요구: SYS-COM-003, SYS-SAFE-003/004.
- Test / milestone: **TC-COM-003**; M1 loss fixture, M2 local behavior,
  M4/M6/M9 통합. Result: **NOT RUN**.

### F04 — Central/Zone communication loss

- 목적 / input: 정상 운행 중 Central→Zone VehicleCommand 경로 중단. Central diagnostics도
  사용할 수 없는 변형과 Zone→vECU 추가 loss 변형을 둔다.
- Expected: Zone이 local <=100 ms timeout을 독립 검출하고 normal allocation을 중단,
  FAIL_SAFE/보호 demand를 선택한다. Central acknowledgement를 기다리지 않는다.
  하위 경로도 끊기면 각 vECU의 local timeout 보호가 동작한다.
- 측정 / PASS 후보: Zone valid-command age/detection/state/local output, Central와 독립성,
  vECU timeout/actual response; 오래된 상위 command를 새 CAN sequence로 연장 금지.
- 요구: SYS-COM-003, SYS-SAFE-001/003/004.
- Test / milestone: **TC-COM-004**; M4 mock Central/local Zone, M5 DDS,
  M6/M7 plant response, M9 fault integration. Result: **NOT RUN**.

판정 기준/미결정 물리 세부값은 [safety](../requirements/safety_requirements.md),
추적은 [traceability](traceability.md), remaining decisions는
[roadmap](../roadmap.md#open-m0-decisions)에 연결한다.
