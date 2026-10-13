# ADR-0015: Front/Rear 두 논리 Zone

Date: 2026-10-13. Status: **ZON-01 포함 범위·책임 배치 ACCEPTED / 상세 protocol 초안 / runtime PLANNED / 시험 NOT RUN**.
Owner: 학습자(project owner). 근거: 두 Zone 설계와 단일 Zone 동작 확인 후 확장하자는
제안에 대한 사용자의 수용 및 문서 정리·검증·push 요청.
Protocol/물리 parameter의 학습자 review는 PENDING이다.

## 문제

단일 Zone은 M1/component 학습에 적합하지만 물리 영역별 gateway와 cross-zone
통신 상실을 학습하지 못한다. Zone을 복제하면 전체 차량의 토크/제동 배분과 power
permission이 중복될 수 있어 기능 owner와 경로를 먼저 정해야 한다.

## 결정

- 최종 Reference에 **Front/Rear 두 논리 Zone**을 포함한다. 단일 Zone은 단계적
  component bring-up이며 최종 다중 Zone acceptance를 대신하지 않는다.
- 학습용 packaging 가정은 rear-drive single motor, Front의 Steering/Brake controller,
  Rear의 Drive/BMS controller다. Battery pack은 차체 하부의 등가 모델이며 BMS controller의
  논리 접속 위치를 Rear로 정한다. Aggregate Brake는 차량 전체 마찰제동 압력이고 전륜 전용이 아니다.
- **Front Zone**의 `vehicle_management`와 `control_allocation`을 차량 전체의 단일
  coordinator로 유지한다. Rear는 routed demand/constraint의 validation, CAN dispatch,
  actual/status 수집과 local safety를 맡고 총 차량 요구를 다시 배분하지 않는다.
- Central vehicle/power request → Front; Front↔Rear는 logical Ethernet/DDS;
  각 Zone↔담당 Leaf는 분리된 SocketCAN/vCAN 경로다. VCU 계층이나 별도 보드를 추가하지 않는다.
- Rear Leaf feedback → Rear → Front aggregate/target bridge → Central/Host다.
  Front Leaf feedback도 같은 Front aggregate에서 원천별로 처리한다.
- 각 receiver는 원천/의존 validity·time·identity와 상위 command의 유효 기간을 유지한다.
  Cross-zone heartbeat/새 timestamp로 끊긴 Leaf 또는 상위 request를 fresh하게 만들지 않는다.
- Front/Rear의 독립 loss/partition, local protection, trusted startup/rejoin을 검증한다.
  단일 coordinator redundancy/failover는 이번 범위에 추가하지 않는다.

## 대안과 배치 근거

Vehicle management/allocation을 Central의 별도 기능으로 옮기는 대안도 가능하다.
현재 Central vehicle-level command와 Zone 배분 경계를 재사용하고 한 Zone에서 동작을
확인한 뒤 Rear gateway를 추가하기 위해 Front co-location을 선택한다.
이는 물리 Zone과 차량 domain 기능을 같은 node에 배치하는 프로젝트의 reference 선택이다.
별도 fault-independent safety controller나 모든 양산차의 공통 배치로 해석하지 않는다.

## 영향과 남은 결정

[Zone 분할 설계](../architecture/zonal_partition.md)에 역할과 routing을 정의한다.
TBD-15에서 **두 Zone 채택/기능 owner는 결정**했으며 peer schema/QoS/queue/clock/skew,
physical model geometry, timeout/rejoin budget은 M4/M5/M6 전까지 남는다.
SYS-ARCH-003 v0.4와 TC-ZON-001–003을 추가하고 기존 COM/EV/fault coverage를 연결한다.
M0 v0.1/단일 Zone 검토와 기존 M1 six-frame 실행 결과는 역사적·부분 증거다.
최종 Reference의 BMS 및 두 Zone runtime/차량 시험은 NOT RUN이다.

ADR-0002의 계층/command/actual 원칙을 유지하며 단일 Zone topology를 확장한다.
ADR-0014와 EV 설계의 **다중 Zone 채택 PENDING** 상태를 이 결정으로 대체한다.
기존 codec/receiver/도구를 제거하거나 복제하지 않는다.

## 실행 순서

M1 actuator/EV wire와 남은 수용 항목 → M2 실제 응답/배터리·BMS·power model
→ M4 단일 coordinator 동작 및 Front/Rear 분할 → M5 DDS 경계 → M6/M7 실제 모델
feedback loop → M9 fault/DTC → M12/M13 동일 두 Zone feature의 독립 보드/최종 검증 순서다.

참고: [NXP](https://community.nxp.com/t5/NXP-Tech-Blog/How-electrification-is-changing-vehicle-architectures/ba-p/1491151)는
물리 Zone과 기능 domain을 구분하며 domain 기능의 Zone co-location을 설명한다.
