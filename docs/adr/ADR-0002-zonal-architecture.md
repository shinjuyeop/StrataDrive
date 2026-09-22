# ADR-0002 — Central → Zone → Leaf architecture

## Status

Accepted for **StrataDrive Reference Baseline v0.1** (2026-09-22).
설계 경계의 수용이며 runtime 구현/호환성/성능 검증은 **PLANNED / NOT RUN**이다.

## Context

Classical Controller가 simulator를 직접 구동하는 loop로는 Zone Controller의 allocation,
actuator 통신, local ECU의 fault response를 살펴보기 어렵다. 하나의 Linux Target에서
component를 실행하더라도 현대 차량의 E/E 경계를 학습하는 것이 목적이다.

## Decision

Central Vehicle Compute → Virtual Ethernet / DDS → Virtual Zone Controller
→ SocketCAN / vCAN → Steering / Brake / Drive vECU 구조를 채택한다.
Docker network 또는 Linux namespace + veth pair로 Central Vehicle Compute와
Zone Controller를 논리적으로 별도인 Ethernet node로 분리한다. 구체적 선택은 TBD다.
Host–Target은 실제 Ethernet을 사용한다.

vECU의 실제 actuator response는 Zone Controller/Target feedback bridge와 Host의
Plant Adapter를 거친 뒤 차량 동작에 반영해야 한다. Periodic task, queue, 동기화,
state, watchdog, integrity, actuator dynamics를 vECU 계약으로 정의한다.
이 항목들은 M0에서 구현하지 않는다.

## Alternatives Considered

- CARLA를 호출하는 monolithic controller: 설정은 줄지만 해당 경계를 시험하지 못한다.
- DDS로 actuator model에 직접 연결: gateway 작업은 줄지만 CAN/Zone Controller 계약이 빠진다.
- 지금부터 물리적으로 분산된 ECU 사용: hardware를 더 직접 다룰 수 있지만 M0 범위를 벗어난다.

## Consequences

책임, timeout, 변환, fault 경계가 명확해지는 대신 scheduling/통신/설정의 복잡도가
늘어난다. Linux Host를 공유하면 물리적 fault isolation은 확보되지 않는다.
vCAN은 application frame 시험용이며 CAN FD의 전기적 동작이나 실제 arbitration timing을
검증하지 않는다. ECU timing 충실도, Zone Controller의 process 배치와 allocation 규칙은
TBD다. [software 계약](../architecture/software_architecture.md)을 참조한다.

## M0 contract refinement and rationale

Vehicle-level command(target speed 및 acceleration/curvature/braking demand), Zone의 actuator command,
vECU actual actuator feedback을 서로 다른 의미/방향으로 고정한다. Requested demand를
actual state로 대체하면 delay/saturation/fault를 검증할 수 없기 때문이다.
Central longitudinal PID는 vehicle acceleration demand를 출력하고 Zone이 이를 torque/brake로
배분한다. Target speed만 전달해 longitudinal control 책임이 Zone으로 옮겨가는 모호함을 피한다.
Planner/Controller/Zone의 CARLA direct actuation과 feedback loss의 raw fallback을 금지한다.
Plant Adapter만 ego actuation writer이며 Host orchestrator는 tick만 소유한다.

Critical actual loss에서는 synchronous simulation의 다음 apply/tick을 gate한다.
이는 가상의 emergency actual을 만들지 않고 증거 결손을 드러내기 위한 선택이다.
물리적 안전 정지의 대체 증거로 보지 않는다. Critical loss는 FAIL_SAFE, 복구는 explicit
reinitialize→INIT이며 Central diagnostics 없이 Zone/vECU가 local protection을 수행한다.

Semantic units는 [ICD](../icd/interface_overview.md), state/action은
[safety](../requirements/safety_requirements.md), logical rate와 100 ms 검출 기준은
[timing](../requirements/timing_requirements.md)에 정의했다. 20/50/100 Hz는 센서보다 빠른
control/actuator task와 freshness를 학습하기 위한 출발점이며 생산 요구나 실측값이 아니다.
Wire encoding/CRC는 TBD-01(M1), dynamics는 TBD-03(M2), schedule은 TBD-04(M3),
isolation/middleware는 TBD-05(M4/M5), allocation은 TBD-06(M4)로 보류한다.

미결정 항목의 owner/rationale은 [TBD register](../roadmap.md#open-m0-decisions)를 따른다.
