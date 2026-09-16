# Ethernet / DDS ICD template

Status: **DRAFT / TBD**. DDS vendor, direct DDS/ROS 2, IDL, domain/topic 이름은
미결정이다. Logical DDS link는 Target 내부 Central Vehicle Compute–Zone Controller Virtual Ethernet이다.
Host physical Ethernet interface에도 공통 metadata 계약을 적용할 예정이지만
Host transport로 DDS를 사용할지는 미결정이다.

## Message / service definition

| Field | IF-DDS-VEHICLE-CMD 초안 | IF-DDS-ZONE-STATUS 초안 |
| --- | --- | --- |
| Message/service name | VehicleCommand (논리적 이름, TBD) | ZoneStatus (논리적 이름, TBD) |
| Kind / schema version | 주기적 message / TBD | 주기적 message / TBD |
| Source | Central Vehicle Compute의 Classical Controller + output guard | Zone Controller gateway |
| Destination | Zone Controller command_validation | Central Vehicle Compute vehicle_state/health/safety |
| Period | TBD | TBD |
| QoS reliability | TBD; 손실과 재전송/staleness의 trade-off | TBD |
| QoS history/depth/resource limits | TBD | TBD |
| QoS deadline/lifespan/liveliness/durability | TBD | TBD |
| Timestamp | source 생성 시각 + clock domain, encoding TBD | source/actuator별 시각 보존, encoding TBD |
| Sequence | 폭/wrap/restart/correlation TBD | 폭/wrap/restart/correlation TBD |
| Timeout | valid-command age threshold + clock TBD | valid-status age threshold + clock TBD |
| Failure behavior | stale/invalid 거부; Zone Controller의 local safety 정책 TBD | unavailable/degraded 표시; 대응 TBD |
| Requirement / test | SYS-CTRL-001, SYS-COM-002 / TC-CTRL-001, TC-COM-002 | SYS-SAFE-001 / TC-SAFE-001 |

## Payload template

| Field name | Type | Unit/frame | 범위 / validity | Source 의미 | Fault 시 값/정책 |
| --- | --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD | TBD |

Vehicle command의 steering/acceleration/torque 등 정확한 물리량은 control allocation
설계에서 결정한다. Actual actuator feedback과 requested command는 서로 다른
필드/타입으로 구분한다. Service를 추가하면 request/response correlation,
idempotency, deadline, retry와 partial failure behavior를 명시한다.

## Transport and integrity review

Network namespace/container topology, DDS discovery peers/domain, multicast/routing,
queue backpressure, ownership/arbitration, reconnect와 schema compatibility는 TBD다.
DDS deadline/liveliness만으로 application command freshness가 검증됐다고 간주하지
않는다. Application CRC를 DDS에도 쓸지, 어떤 metadata를 보호할지는 TBD이며 CAN
CRC 정책을 그대로 복제하지 않는다. Source age, invalid frame, sequence 재시작의
의미를 [common contract](interface_overview.md)와 일치시킨다.
