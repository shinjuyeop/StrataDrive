# Ethernet / DDS ICD baseline

Status: semantic contract **DEFINED**. Vendor, ROS 2 vs direct DDS, IDL/topic/binary schema와
runtime은 **TBD-05 / PLANNED**. Target 내부 Central–Zone은 logical Ethernet + DDS 계열,
Host–Target은 Physical Ethernet이다. Host bridge transport에 DDS를 강제하지 않는다.
[ZON-01](../architecture/zonal_partition.md)에서 Central의 목적 Zone과 상위 집계 owner는 Front다.
Front↔Rear peer 의미는 아래에 추가하며 IDL/runtime은 미구현이다.

## Logical messages

| 항목 | IF-DDS-VEHICLE-CMD | IF-DDS-ZONE-STATUS |
| --- | --- | --- |
| Name | VehicleCommand | ZoneStatus |
| Source → Destination | Central Classical Controller → Front command validation | Front aggregate gateway → Central state/health/safety |
| Payload 의미 | target speed, longitudinal acceleration demand, target curvature, braking demand | per-actuator actual sample/validity/age, availability, local state/fault |
| Generation/publication | Controller 50 Hz / 20 ms | Zone 100 Hz / 10 ms starting point |
| Metadata | source timestamp/clock, sequence/run epoch, source sensor/trajectory identity | 각 vECU 원천 time/sequence/validity/accepted-command identity 보존 |
| Validation | finite/range/mode, sequence/epoch, source freshness/integrity | actuator별 원천 validity/freshness; aggregate heartbeat는 actual health가 아님 |
| Timeout / failure | Zone last-valid-command RX부터 <=100 ms 검출; local FAIL_SAFE, F04 | unavailable 표시/보호 상태; Host actual path는 독립 monitor |
| Recovery | explicit reinitialize → INIT gate | 원천 상태 재검증 후 복구; 새 aggregate만으로 정상화 금지 |
| Wire/QoS | M5 TBD-05 | M5 TBD-05 |

Vehicle-level target speed는 차량 속도 reference이고 longitudinal acceleration demand는
Central PID의 제어 출력이다. 둘 다 Drive torque나 Drive Actual이 아니다.
Target curvature는 lateral demand이지 Steering Actual이 아니다. Braking demand는
Brake Actual pressure가 아니다. 정확한 semantic units/frame은
[common contract](interface_overview.md)를 적용한다.

[RG-01](regenerative_braking_design.md)에서도 Central의 vehicle-level demand를 유지한다.
ZoneStatus는 actual torque와 구분해 회생 한계/validity/제한 원인 및 원천 freshness를
전달할 계획이다. Cached capability를 aggregate 발행 시각으로 fresh하게 만들지 않는다.
정확한 IDL/QoS는 TBD-05이며 Central에 직접 모터 command 경로를 추가하지 않는다.

[EV-01](ev_power_bms_design.md)은 별도 IF-DDS-POWER-REQUEST(enable/shutdown 요청)와
ZoneStatus의 source별 BMS/power/permission 정보를 추가한다. Central의 요청으로 READY를
선언하지 않고 Zone vehicle management와 BMS가 actual/health를 확인한다.
각 request correlation/epoch/deadline, status 원천/의존 validity/time, QoS와 publication
주기는 TBD-14/05이며 기존 VehicleCommand의 runtime/IDL 구현 완료가 아니다.
## Front/Rear peer 의미 — ZON-01

| Interface | Producer → Consumer | 의미 / validation |
| --- | --- | --- |
| IF-DDS-REAR-CMD | Front → Rear | 배분된 Drive demand, 원천 BMS constraint/permission, power request와 speed; parent identity/expiry 보존; 차량 전체 재배분 금지 |
| IF-DDS-REAR-STATUS | Rear → Front | Drive actual/capability, BMS/power 원천별 status; identity/time/clock/validity/dependency를 집계 시 보존 |
| IF-DDS-REAR-SESSION | Front ↔ Rear | trusted INIT/rejoin epoch·monitor-enable·correlation; payload만으로 epoch를 수용하지 않음 |

Front는 vehicle management/allocation의 단일 owner, Rear는 로컬 validation/gateway다.
Peer envelope 진행과 각 Leaf 원천/의존 freshness는 독립 검사한다. 재발행/새 CAN counter로
상위 request의 유효 기간이나 cached BMS/actual age를 연장하지 않는다.
Critical loss는 각 방향/원천별 <=100 ms 검출 및 상위 승인 없는 local protection을 적용한다.
INIT/rejoin과 power/health gate를 통과하기 전 정상 출력/자동 복구를 허용하지 않는다.
Schema/IDL/topic, rate/source-age/monitor budget, clock/skew, QoS/queue/overflow, trusted handshake는
TBD-15/05/14다. 의미 계약만 정의했으며 두 Zone runtime/TC-ZON-001–003은 NOT RUN이다.

## Host bridge contracts

IF-HOST-SENSOR는 sensor timestamp/frame ID, source clock, ego state validity를 전달한다.
IF-HOST-ACTUATOR는 각 vECU actual sample을 Zone/Target bridge에서 Host Plant Adapter로
전달한다. Bridge가 actual을 생성하거나 command로 보충하지 않는다. Host는 actual
stream별 loss를 <=100 ms에 검출하고 valid source가 없으면 tick을 gate한다.
Protocol, serialization, source time sync/uncertainty, snapshot skew, Host acknowledgement는
M5에 설계하고 M6/M7에 검증한다(TBD-02/04/05/07).

IF-HOST-EV-STATUS는 Zone을 거친 BMS/power/energy 관측 정보다. Actual actuator stream을
대체하거나 별도 wheel torque로 더하지 않는다. Battery model의 physical sensor/coupling은
이 상위 status bridge와 별도 경계이며 배치/단일 energy owner는 TBD-07이다.

## Middleware decision criteria and timing

M4에서 후보를 비교하고 **M5 runtime 착수 전** ROS 2 integration 또는 direct DDS,
vendor, isolation(Docker network vs netns/veth), Host bridge transport를 결정한다.
판단 기준은 두 Jetson stack 호환성, dependency/학습 비용, discovery 재현성,
QoS와 bounded queue/freshness 제어, tracing/clock 접근성, reconnect 시험 가능성이다.
새 middleware 선택이 Central/Zone/vECU 책임을 바꾸는 이유가 되어서는 안 된다.

결정할 QoS는 reliability, history/depth/resource limit, deadline/lifespan/liveliness,
durability/ownership이다. Reliable delivery가 오래된 command의 적용을 정당화하지 않는다.
DDS deadline/liveliness는 application freshness/timeout 검사를 대체하지 않는다.
Application integrity 방식을 DDS에도 CRC로 할지 여부는 CAN의 정책을 무조건 복제하지
않고 M5에 정한다. Sequence width/wrap/restart, schema compatibility, multicast/routing,
queue backpressure도 함께 고정한다. Service를 추가하면 request/response correlation,
idempotency/deadline/retry/partial failure 계약을 별도로 정의한다.

관련 요구: SYS-ARCH-001/002/003, SYS-COM-002/003/004, SYS-SAFE-003, SYS-CTRL-001/002.
[Deployment](../architecture/deployment_architecture.md),
[TBD register](../roadmap.md#open-m0-decisions).
