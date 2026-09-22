# Safety requirements and behavior contract

Status: **DEFINED / Reference Baseline v0.1**; runtime **PLANNED / NOT RUN**.
SYS-SAFE-001/002/003/004와 SYS-CTRL-002를 구체화한다. 학습용 SIL 보호 계약이며
ISO 26262 준수, ASIL 할당, 인증, 실차 안전성이나 QNX/AUTOSAR 사용을 주장하지 않는다.

## Responsibility and startup

Safety Supervisor는 trajectory의 freshness, finite values, range, feasibility와
health/state를 검사한다. Classical Controller는 bounded vehicle-level command를 생성한다.
Zone Controller는 age/integrity/mode/range와 actuator availability를 독립 검증하고,
각 vECU는 자신의 command timeout, task watchdog와 actuator model을 담당한다.
상위 검증 성공이 하위 검증 생략의 근거가 되지 않는다.

모든 component는 INIT에서 시작한다. 요구 input/command/actual feedback의 validity,
run epoch, sequence와 local health가 확인되기 전 정상 주행을 허용하지 않는다.
INIT에서 Drive의 propulsion target은 0이며 actuator 초기값/brake hold 수치는 TBD-03다.
초기 actual feedback은 vECU model의 초기 state로 생성할 수 있으나 command echo로
만들지 않는다. INIT용 non-driving handshake는 NORMAL 요구와 구분한다(TBD-01/02).
Plant Adapter는 초기 valid actual set이 준비될 때까지 driving tick을 허용하지 않는다.
Sensor/state 초기 수집과 vECU 초기 actual 발행은 NORMAL command의 도착을 기다리지
않는다. 필요한 INIT용 수집 tick도 Plant Adapter의 유효 초기 actual/비주행 gate를 거치며,
전 component가 서로의 NORMAL을 기다리는 순환 startup 조건을 만들지 않는다.
정확한 handshake/tick 순서는 TBD-01/07에서 정한다.

## Minimum protection policy

| Trigger | Detection owner / local state | 정의된 최소 동작 | 후속 상세 결정 |
| --- | --- | --- | --- |
| F01 Steering feedback loss | Zone의 steering last-valid age → FAIL_SAFE; Host도 각 actual stream 감시 | steering unavailable 표시, normal route 수행 중단, 가용 Drive에 zero-propulsive target 요청; raw steering command를 feedback으로 대체 금지 | brake/steering 물리 동작과 반응 budget TBD-03/06 |
| F02 Invalid/stale actuator command | 수신 vECU validation; Zone도 DDS command를 독립 검사 | reject, 유효 snapshot/last-valid RX 보존; timeout 전 마지막 valid demand는 age 한계 안에서만 사용, timeout 후 local FAIL_SAFE | CRC/sequence/freshness/재동기화 encoding TBD-01 |
| F03 Drive command loss | Drive vECU 자체 timeout → FAIL_SAFE | 이전 demand 무효화, local zero-propulsive-torque target 선택; actual torque는 model response로 feedback; positive torque 무기한 유지 금지 | ramp/actual torque 감소 기한 TBD-03, M2 test 전 결정 |
| F04 Central/Zone command loss | Zone local timeout → FAIL_SAFE | Central diagnostics 응답 없이 normal allocation 중단, actuator에 local protection command 전달; 이 경로도 끊기면 각 vECU timeout 동작 | allocation/brake conflict policy TBD-06; local mechanism M2/M4 |
| Brake/Drive feedback loss | Zone의 actuator별 age → FAIL_SAFE; Host 독립 감시 | 가용성 제거, normal driving 중단; brake unavailable에서 braking stop 보장 금지 | actuator별 reaction matrix TBD-03/06 |
| Any stale/invalid/missing actual feedback at Plant Adapter | Host local validation/age monitor → FAIL_SAFE run gate | 마지막 actual을 새 sample처럼 재발행 금지, 명령 대체 금지; 유효 actual set 없는 다음 plant apply/tick을 차단 | mapping/skew 검증 TBD-02/07 |
| Optional feature unavailable, critical paths healthy | 해당 monitor → DEGRADED | 사전에 검증된 제한 envelope 안에서만 기능 축소 허용 | envelope TBD-06/10; M0에서 critical fault의 계속 주행 허용 없음 |
| AI timeout / invalid output | Central Safety Supervisor | 유효 Classical Planner fallback; fallback도 무효면 FAIL_SAFE | 전환/연속성/threshold TBD-10, M11 |
| Task overrun / compute overload | 각 task monitor/watchdog; Central health | 필수 경로의 계약 위반 기록 및 local protection; optional workload 축소 후보 | budget/threshold/monitor 독립성 TBD-04/06 |

100 ms는 [timing 계약](timing_requirements.md)의 **검출 상한**이다. Local output 선택,
physical ramp, 정지 완료의 공통 100 ms 요구가 아니다. Protection request도 actuator
command이므로 actual actuator feedback과 혼동하지 않는다. FAIL_SAFE 상태 이름만으로
정지 성공/안전 보장을 주장하지 않는다. 가용 actuator와 plant response를 별도 검증한다.

## Plant Adapter feedback-loss policy

Reference v0.1은 synchronous CARLA + 단일 Host tick owner를 사용한다.
Actual feedback이 invalid로 확인되거나 age limit을 넘으면 Plant Adapter는 driving input
적용을 중단하고 Host tick owner에 gate를 걸어 **다음 simulation tick을 보류**한다.
직전 fresh actual은 유효 기간 안에서만 sample-and-hold 가능하다. 유효 기간이 끝나면
hold를 연장하거나 raw command/임의 brake 값으로 주행을 계속하지 않는다.

이는 시험 환경의 명시적인 run containment이며 차량이 물리적으로 안전하게 정지했다는
뜻이 아니다. Fault test에서는 gate/검출/기록을 판정하고, 정상 scenario에서는 gate 발생이
FAIL이다. Host wall-time logger/timeout monitor는 계속 동작한다. Adapter/process 자체
정지에도 tick owner가 유효 apply acknowledgement 없이는 tick을 진행하지 않는 계약이다.
구현은 M6/M7이며 asynchronous simulator 모드는 이 baseline의 범위 밖이다.

## Recovery

Top-level state는 INIT / NORMAL / DEGRADED / FAIL_SAFE 네 개만 사용한다.
Recovery는 별도 상태를 늘리지 않고 **명시적 reinitialize 요청 → INIT → NORMAL**
절차로 정의한다. Fault clear, 필요한 stream 재확인, epoch/sequence 재동기화, local
health 확인 전 NORMAL로 돌아갈 수 없다. Timeout이 해제되거나 새 frame 하나가
도착했다는 이유로 FAIL_SAFE→NORMAL 자동 전환을 허용하지 않는다.
Dwell/재연결 handshake의 정확한 값은 M1/M2/M4(TBD-01/03/06)에서 정한다.

[Fault architecture](../architecture/fault_diagnostics_architecture.md),
[fault scenarios](../test-plan/scenario_baseline.md),
[TBD register](../roadmap.md#open-m0-decisions)를 함께 적용한다.
