# Ethernet / DDS ICD baseline

Status: semantic contract **DEFINED**. Vendor, ROS 2 vs direct DDS, IDL/topic/binary schema와
runtime은 **TBD-05 / PLANNED**. Target 내부 Central–Zone은 logical Ethernet + DDS 계열,
Host–Target은 Physical Ethernet이다. Host bridge transport에 DDS를 강제하지 않는다.

## Logical messages

| 항목 | IF-DDS-VEHICLE-CMD | IF-DDS-ZONE-STATUS |
| --- | --- | --- |
| Name | VehicleCommand | ZoneStatus |
| Source → Destination | Central Classical Controller → Zone command validation | Zone gateway → Central state/health/safety |
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

## Host bridge contracts

IF-HOST-SENSOR는 sensor timestamp/frame ID, source clock, ego state validity를 전달한다.
IF-HOST-ACTUATOR는 각 vECU actual sample을 Zone/Target bridge에서 Host Plant Adapter로
전달한다. Bridge가 actual을 생성하거나 command로 보충하지 않는다. Host는 actual
stream별 loss를 <=100 ms에 검출하고 valid source가 없으면 tick을 gate한다.
Protocol, serialization, source time sync/uncertainty, snapshot skew, Host acknowledgement는
M5에 설계하고 M6/M7에 검증한다(TBD-02/04/05/07).

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

관련 요구: SYS-ARCH-001/002, SYS-COM-002/003/004, SYS-SAFE-003, SYS-CTRL-001/002.
[Deployment](../architecture/deployment_architecture.md),
[TBD register](../roadmap.md#open-m0-decisions).
