# ADR-0002 — Central → Zone → Leaf architecture

## Status

Proposed — M0 설계 방향이다. Architecture는 문서화했으며 runtime은 Planned다.

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
