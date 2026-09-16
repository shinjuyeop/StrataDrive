# Interface inventory and common contract

Status: **DRAFT / TBD**. Interface ID부터 관리하며 wire schema/DBC/IDL은 미구현이다.

| Interface ID | Logical content | Source → Destination | Transport / schema |
| --- | --- | --- | --- |
| IF-HOST-SENSOR | Camera/IMU/GNSS + ego vehicle state | Host sensor bridge → Central vehicle_state/perception | physical Ethernet; protocol TBD |
| IF-CENTRAL-TRAJECTORY | candidate/validated trajectory, target speed, risk | Planner → Safety → Controller | in-process/IPC TBD; validation 경계 유지 |
| IF-DDS-VEHICLE-CMD | vehicle-level command | Central → Zone | DDS over virtual Ethernet; DDS ICD |
| IF-DDS-ZONE-STATUS | actuator availability, aggregate feedback, health | Zone → Central | DDS over virtual Ethernet; DDS ICD |
| IF-CAN-STEERING | steering command / actual steering feedback | Zone ↔ Steering vECU | SocketCAN/vCAN; CAN FD application contract |
| IF-CAN-BRAKE | brake command / actual pressure feedback | Zone ↔ Brake vECU | 同上 |
| IF-CAN-DRIVE | torque command / actual torque, speed/RPM feedback | Zone ↔ Drive vECU | 同上 |
| IF-HOST-ACTUATOR | actual actuator state with source freshness | vECU → CAN → Zone/target bridge → Host Plant Adapter | feedback aggregation + physical Ethernet; protocol TBD |
| IF-FAULT-EVENT | fault occurrence, evidence, local action/state | local monitors → Diagnostics Manager → Host logging | local IPC/DDS/telemetry mapping TBD |

양방향 CAN interface ID는 logical family를 뜻한다. Command와 feedback의 wire
frame ID는 각각 할당할 예정이다. Host telemetry와 Central–Zone DDS가 같은
프로토콜이라고 가정하지 않는다. System state를 command/status에 전달하는 방법도
schema 확정 시 정의한다.

## Common metadata and semantics template

- Interface ID / schema version / owner / requirement IDs: TBD
- Source / destination / authority / direction / message vs service: TBD
- Payload fields / type / valid range / unit / coordinate frame / sign convention: TBD
- Timestamp unit / clock domain / source acquisition or production semantics: TBD
- Simulation frame / run ID / correlation ID / sequence width and restart/wrap: TBD
- Validity, age limit, timeout clock / reset/pause handling: TBD
- Queue depth / overflow / loss / duplicate / out-of-order behavior: TBD
- Initialization / shutdown / reconnect / compatibility policy: TBD
- Failure behavior / diagnostics / recovery contract: TBD

Source timestamp와 bridge receive timestamp는 의미가 다르다. Bridge가 오래된
feedback을 전달하면서 새로 생성된 것처럼 timestamp를 바꾸면 안 된다. Actuator별
timestamp/validity를 보존하고, 집계 snapshot의 최대 skew와 결측 처리를 정한다.
모든 metadata가 CAN payload에 들어간다고 가정하지 않으며 wire field와 logger
metadata의 대응을 CAN ICD에서 정의한다.

`interfaces/common/`은 공통 타입/단위 계약, `interfaces/dds/`는 IDL 등,
`interfaces/dbc/`는 DBC의 향후 배치 경로다. 지금은 .gitkeep만 있다.
참조: [DDS ICD](ethernet_dds_icd.md), [CAN ICD](can_icd.md),
[traceability](../test-plan/traceability.md).
