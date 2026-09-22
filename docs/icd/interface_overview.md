# Interface inventory and common contract

Status: semantic contract **DEFINED / Reference Baseline v0.1**.
Wire schema/DBC/IDL/codec/transport runtime은 **PLANNED**, binary layout은 미확정이다.

| Interface ID | 논리적 내용 | Source → Destination | Transport / schema |
| --- | --- | --- | --- |
| IF-HOST-SENSOR | Camera/IMU/GNSS + ego vehicle state | Host sensor bridge → Central vehicle_state/perception | Physical Ethernet; protocol TBD-05 |
| IF-CENTRAL-TRAJECTORY | candidate/validated trajectory, target speed, risk | Planner → Safety Supervisor → Classical Controller | in-process/IPC TBD-05; validation 경계 유지 |
| IF-DDS-VEHICLE-CMD | Vehicle-level Command | Central Classical Controller → Zone command validation | logical Ethernet / DDS; DDS ICD |
| IF-DDS-ZONE-STATUS | actuator availability, actual feedback, local state/health | Zone → Central vehicle_state/health/safety | logical Ethernet / DDS; DDS ICD |
| IF-CAN-STEERING | Steering Command / Steering Actual | Zone ↔ Steering vECU | SocketCAN/vCAN; CAN FD application contract |
| IF-CAN-BRAKE | Brake Command / Brake Actual | Zone ↔ Brake vECU | 위와 동일 |
| IF-CAN-DRIVE | Drive Command / Drive Actual | Zone ↔ Drive vECU | 위와 동일 |
| IF-HOST-ACTUATOR | per-actuator actual sample + 원천 metadata | vECU → CAN → Zone/Target feedback bridge → Host Plant Adapter | feedback 집계 + Physical Ethernet; protocol TBD-05 |
| IF-FAULT-EVENT | fault occurrence, evidence, local action/state | local monitors → Diagnostics Manager / Host logging | IPC/DDS/telemetry mapping TBD-05/08 |

CAN family ID는 양방향 그룹이며 command와 actual feedback은 별도의 frame/message다.
각 wire ID는 M1에 할당한다. Host transport와 Central–Zone DDS가 같다고 가정하지 않는다.
`Vehicle-level command != actuator command != actual actuator feedback`을 모든 schema에서 유지한다.

## Semantic payload contract

아래는 물리적 의미이며 binary type/bit width/layout 확정이 아니다.

| 계층 / 의미 필드 | 의미 / 단위 / 부호 | 책임 |
| --- | --- | --- |
| VehicleCommand.target_speed | validated continuous speed reference, m/s, 전진 nonnegative; ODD/보고서는 km/h 병기 | Central Controller가 생성; Planner의 구간 speed request와 구분 |
| VehicleCommand.longitudinal_acceleration_demand | desired vehicle acceleration, m/s², 전진 가속 양수/감속 음수 | Central longitudinal PID의 bounded 출력; Zone이 torque/brake demand로 allocation |
| VehicleCommand.target_curvature | ego 진행 경로 curvature, 1/m, 좌회전 양수 | Central이 steering wheel/actuator actual을 출력하지 않음 |
| VehicleCommand.braking_demand | 무차원 [0,1], 0=제동 요구 없음, 1=설정된 최대 제동 요구 | 압력/정지 성능 자체가 아님; Zone이 actuator demand로 변환 |
| Steering Command / Steering Actual | equivalent front road-wheel angle, rad, 좌회전 양수 | Zone demand / Steering vECU dynamics 후 actual |
| Drive Command / Drive Actual | aggregate driven-wheel propulsive torque, N·m, 전진 양수 | Zone demand / Drive vECU dynamics 후 actual; 후진/회생제동 확장 제외 |
| Brake Command / Brake Actual | effective aggregate brake pressure, Pa, nonnegative | Zone demand / Brake vECU dynamics 후 actual; caliper 상세 모델은 요구하지 않음 |
| 각 actual validity/state | actuator별 valid/unavailable 및 local state | 수신 성공만으로 actual health가 유효해지지 않음 |

Ego/path 의미 frame은 x forward, y left, z up, yaw left-positive다. Path tracking 기준점은
**ego rear-axle center**로 통일한다. CARLA-native 좌표/steer 부호와 rear-axle 위치 변환은
Host adapter/state bridge에서 M6/M7에 검증한다(TBD-02/07). 단위 변환을 Controller에
숨기지 않는다. Acceleration demand/curvature→torque/angle, normalized braking→pressure의 allocation,
max pressure/torque/angle와 CARLA normalization 수치는 M2/M4/M6(TBD-02/03/06)이다.
Target speed는 추종 기준이고 longitudinal acceleration demand는 Central PID의 제어 출력이다.
이를 분리해야 Zone에 speed controller의 책임이 암묵적으로 옮겨가지 않는다. Zone은
vehicle acceleration demand를 구동/제동 물리량으로 배분하며 정상/보호 braking demand의
충돌 우선순위는 M4(TBD-06)에 결정한다. 물리 의미를 고정하되 특정 차량의 calibration을
M0에서 꾸며내지 않기 위한 선택이다.

## Metadata and validity

각 stream은 논리적으로 schema version, run/epoch, producer, source acquisition/generation
시각 + clock domain, source sequence, validity, causal input identity를 갖는다.
Vehicle command에는 source sensor/trajectory identity, actuator command에는 vehicle command
identity, actual feedback에는 수용한 actuator command identity를 연결한다. Local protection으로
생성한 actual은 protection origin과 마지막 수용 command를 구분한다.

Receiver는 raw RX time, accept/reject, last-valid RX time을 별도 기록한다. CRC/sequence,
finite/range/mode, freshness가 모두 통과해야 valid snapshot을 갱신한다. Invalid/stale/duplicate
frame은 valid-command age를 갱신하지 않는다. 주기적 Zone command 생성도 상위 command의
유효 기간을 연장하지 못하며 Zone은 Central last-valid age를 별도로 감시한다.

Feedback bridge는 actuator별 원천 timestamp/sequence/validity를 유지한다.
Bridge receive/send time 또는 aggregate sequence만 갱신해 cached actual을 fresh로 만들지
않는다. 집계에서 하나가 누락되어도 다른 actuator의 age로 덮지 않는다. Host는 원천 진행과
local valid RX age를 모두 검사한다. Source-age 한계/최대 snapshot skew와 전달 방식은
TBD-01/02/04/05에서 정하되, 100 ms critical loss 검출 상한은 유지한다.

모든 metadata를 CAN payload에 넣는 것은 아니다. M1에 wire field와 logger/side-channel
metadata의 대응을 명시하고 replay/restart rejection을 검증한다. Application sequence,
CRC, timestamp encoding과 queue 정책은 [CAN ICD](can_icd.md)에서 결정한다.
Timeout clock, reset/pause는 [timing](../requirements/timing_requirements.md)를 따른다.

`interfaces/common/`, `interfaces/dds/`, `interfaces/dbc/`는 향후 구현 경로이며 현재
.gitkeep만 있다. [DDS ICD](ethernet_dds_icd.md),
[traceability](../test-plan/traceability.md)를 참조한다.
