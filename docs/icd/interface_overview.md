# Interface inventory and common contract

Status: semantic contract **DEFINED / Reference Baseline v0.1**.
2026-10-13 [RG-01 회생제동 확장](regenerative_braking_design.md)의 포함 범위를 결정했다.
아래 Drive 의미는 이 후속 설계를 반영한다. 회생/에너지·배분은 Host component로 구현했으며 차량 runtime은 PLANNED / NOT RUN이다.
CAN actuator 6개 + EV 6개 wire/DBC/codec은 **Host 초안 구현·시험 / baseline 채택 PENDING**이며 DDS controller IDL/adapter는 **PLANNED**다. 후보 실험의 fixed packet IDL과 실제 controller 배포를 구분한다.
[Steering Command/Actual의 DBC·layout 제안](steering_frame_draft.md)을 작성했으며 review PENDING이다.
[Steering angle field 초안](steering_angle_encoding.md)의 독립 codec을 Host에서 시험했다.
[Steering 두 frame의 codec·DBC parser 교차 검증](../learning/m1_steering_frame_codec.md)도
Host에서 수행했다. [Steering 수신부](../learning/m1_steering_receiver.md)의 stateful 수용/시간/Epoch/
timeout도 Host에서 시험했다. [SocketCAN/vCAN 연결](../learning/m1_steering_socketcan.md)의
Steering application 송수신/fault/timeout은 실행했다. [M1 session/queue](../learning/m1_session_queue.md)의
영속 local Epoch와 실제 application/kernel overflow도 검사했다. Actual Central coordinator/Zone DDS·차량 통합은 남아 있다.
[Brake Command/Actual wire 제안](brake_frame_draft.md)의 압력·metadata/P05 codec과
[vCAN wire 시험](../learning/m1_brake_codec.md)도 수행했다. 이어서
[Brake application 수용/timeout](../adr/ADR-0012-brake-receiver.md)을 Host/vCAN에서 시험했다.
[첫 Brake 압력 모델](../learning/m2_brake_model.md)의 Host 응답/보호는 구현·시험했다. 차량 보호 통합은 후속이다.
[Drive Command/Actual](drive_frame_draft.md)의 signed torque와 독립 capability freshness를
[Host/vCAN에서 시험했다](../learning/m1_drive_codec.md). M2 응답/에너지와 [M4 첫 배분 component](../learning/m4_control_allocation.md)는 구현했으며 차량 피드백 loop는 후속이다.

M4 [Zone 명령 수용](../learning/m4_zone_command_admission.md)은 shared in-process
VehicleRequest/FrontCommands/RearCommands 계약을 사용한다. 독립 trusted root·scope·expiry를 검증하며,
후속 [CAN egress/로컬 보호](../learning/m4_zone_gateway.md)는 구현·시험했다. 원래 parent/expiry가 없는
기존 32-byte CAN의 remote Leaf lease 검사·remote 보호 신호와 전체 runtime은 후속이다.
[Rear 전원·초기 구동](../learning/m4_rear_power_startup.md)은 별도 lifecycle root·Enable ACK 검증과
PowerRequest/limits/permission 전달·Drive trusted arm을 실제 controller/component·vCAN에서 연결했다.
[Front startup](../learning/m4_front_startup.md)도 same-host trusted pair arm과 실제 Leaf/독립 Actual·vCAN에 연결했다.
Arm은 CAN payload에서 학습하지 않으며 기존 wire·critical source/expiry 계약은 유지한다.
[정상 종료](../learning/m4_normal_stop.md)의 stop intent/자식 root·terminal lease/ACK도 shared in-process 계약이다.
NormalStopControl은 실제 Leaf·gateway/allocator를 연결하며 remote stop/lease transport는 후속이다.
2026-10-20 후속 [owner-wire v1](owner_wire_v1.md)은 위 composite context/terminal lease·INIT/arm/protection·원천 raw CAN feedback을 outer CRC32C와 명시적 role/domain으로 전달한다. 실제 Leaf component에서 local Release와 별도 global credit, arm·expiry·보호/rejoin을 검사했다. 기존 CAN/DBC/P05는 불변이다. [DDS/Zenoh 후보](../adr/ADR-0058-remote-owner-authority-and-dds-probe.md)는 두 독립 netns process의 echo이며, 실제 Central/Zone 제어·Actual·세션 adapter는 아직 미구현이다. Target clock/보안·full deployment는 후속 gate다.

2026-10-13 [EV-01](ev_power_bms_design.md)으로 BMS Leaf, 차량 관리와 power lifecycle을
추가했다. 2026-10-14 [BMS wire 초안](bms_frame_draft.md)의 EV 6개 DBC frame과
Host C++ codec/항목별 receiver·DBC 교차 검증과 native SocketCAN 변환 시험을 추가했다.
[BMS 실행 안내](../learning/m1_bms_codec.md)에 범위를 기록한다. EV TX/RX/relay의 vCAN도
36개 case로 시험했다. Actual coordinator·DDS·component runtime은 PLANNED다.
[ZON-01](../architecture/zonal_partition.md)의 Central–Front/Rear 독립 경로와 의미를 반영했다.
Peer binary schema/IDL/QoS/clock/rejoin은 TBD-15/05이며 runtime은 미구현이다.

| Interface ID | 논리적 내용 | Source → Destination | Transport / schema |
| --- | --- | --- | --- |
| IF-HOST-SENSOR | Camera/IMU/GNSS + ego vehicle state | Host sensor bridge → Central vehicle_state/perception | Physical Ethernet; protocol TBD-05 |
| IF-CENTRAL-TRAJECTORY | candidate/validated trajectory, target speed, risk | Planner → Safety Supervisor → Classical Controller | in-process/IPC TBD-05; validation 경계 유지 |
| IF-CENTRAL-VEHICLE-REQUEST | Vehicle-level Command | Central Classical Controller → Central allocation | Central 내부 의미 interface; transport TBD-05 |
| IF-DDS-ZONE-STATUS | 각 Zone status의 공통 family | Front/Rear → Central state/VCU/bridge | 두 독립 status interface의 의미; DDS ICD |
| IF-CAN-STEERING | Steering Command / Steering Actual | Front ↔ Steering vECU | SocketCAN/vCAN; CAN FD application contract |
| IF-CAN-BRAKE | Brake Command / Brake Actual | Front ↔ Brake vECU | 위와 동일 |
| IF-CAN-DRIVE | Drive Command / Drive Actual | Rear ↔ Drive vECU | 위와 동일 |
| IF-CENTRAL-POWER-REQUEST | enable/shutdown 요청과 correlation | lifecycle requester → Central vehicle management | Central 내부 의미 interface; transport TBD-05 |
| IF-DDS-FRONT-CMD | scoped Steering/Brake demand | Central allocation → Front validation/gateway | logical Ethernet / DDS; schema TBD-15 |
| IF-DDS-FRONT-STATUS | Steering/Brake 원천 actual/health | Front → Central state/배분/bridge | logical Ethernet / DDS; source metadata 보존 |
| IF-DDS-FRONT-SESSION | trusted INIT/rejoin/Epoch/monitor enable | Central session ↔ Front session validation | logical Ethernet / DDS; handshake TBD-15 |
| IF-DDS-REAR-CMD | 배분된 Drive demand, BMS constraint/permission, power 요청·speed 입력 | Central allocation/vehicle management → Rear validation/gateway | logical Ethernet / DDS; 의미 ZON-01, schema TBD-15 |
| IF-DDS-REAR-STATUS | Drive actual/capability, BMS/power 원천 status | Rear → Central state/배분/vehicle management/bridge | logical Ethernet / DDS; source/dependency 보존, schema TBD-15 |
| IF-DDS-REAR-SESSION | trusted INIT/rejoin, epoch·monitor enable·correlation | Central session ↔ Rear session validation | logical Ethernet / DDS; handshake TBD-15 |
| IF-CAN-BMS | power 요청 / BMS state·limits·power actual | Rear ↔ BMS vECU | EV schema 1 DBC·C++ codec/receiver·local vCAN 부분 검사; actual coordinator TBD-14 |
| IF-CAN-DRIVE-CONSTRAINT | 원천 charge/discharge limit와 drive permission | Rear → Drive vECU | 별도 DriveBatteryLimits / DrivePermission DBC 초안; runtime TBD-14 |
| IF-HOST-ACTUATOR | per-actuator actual sample + 원천 metadata | vECU → CAN → 담당 Zone → Central bridge → Host Plant Adapter | feedback 집계 + Physical Ethernet; protocol TBD-05 |
| IF-HOST-EV-STATUS | 관측용 BMS/power/energy 정보; wheel actuation 아님 | BMS → CAN → Rear → Central bridge → Host | Physical Ethernet; schema TBD-14/05 |
| IF-MODEL-BMS | modeled pack 센서, 셀 전압·온도 극값과 실제 전원 상태 | battery/power plant → BMS | SIL 로컬 sensor 경계; validity/time/batch 보존, 모델 TBD-13/07 |
| IF-MODEL-DRIVE-POWER | modeled Drive local HV bus 실제 센서, source time/validity/identity | power plant → Drive local sensor validation | SIL 로컬 물리 경계; Central permission과 별도, schema/threshold TBD-12/13/14 |
| IF-FAULT-EVENT | fault occurrence, evidence, local action/state | local monitors → Diagnostics Manager / Host logging | IPC/DDS/telemetry mapping TBD-05/08 |

CAN family ID는 양방향 그룹이며 command와 actual feedback은 별도의 frame/message다.
각 wire ID는 M1에 할당한다. Host transport와 Central–Zone DDS가 같다고 가정하지 않는다.
`Vehicle-level command != actuator command != actual actuator feedback`을 모든 schema에서 유지한다.

이전 IF-DDS-VEHICLE-CMD/IF-DDS-POWER-REQUEST는 ADR-0021로 retired하고 위 Central 내부 ID로
대체했다. 아직 DDS IDL/runtime이 없어 wire migration은 없으며 과거 ADR/결과는 이전 ID에 귀속된다.

## Semantic payload contract

아래는 물리적 의미이며 binary type/bit width/layout 확정이 아니다.

| 계층 / 의미 필드 | 의미 / 단위 / 부호 | 책임 |
| --- | --- | --- |
| VehicleCommand.target_speed | validated continuous speed reference, m/s, 전진 nonnegative; ODD/보고서는 km/h 병기 | Central Controller가 생성; Planner의 구간 speed request와 구분 |
| VehicleCommand.longitudinal_acceleration_demand | desired vehicle acceleration, m/s², 전진 가속 양수/감속 음수 | Central longitudinal PID의 bounded 출력; Central allocation이 torque/brake demand로 배분 |
| VehicleCommand.target_curvature | ego 진행 경로 curvature, 1/m, 좌회전 양수 | Central이 steering wheel/actuator actual을 출력하지 않음 |
| VehicleCommand.braking_demand | 무차원 [0,1], 0=제동 요구 없음, 1=설정된 최대 제동 요구 | 압력/정지 성능 자체가 아님; Central allocation이 actuator demand로 변환 |
| VehicleCommand.standstill_hold | 명시적 정지 유지 요청 bool; in-process M4 fixture의 추가 의미 | 저속에서 마찰 hold demand 선택; 실제 정지/경사 유지 보장은 M6/M7 검증 |
| Steering Command / Steering Actual | equivalent front road-wheel angle, rad, 좌회전 양수 | Central 배분·Zone 전달 demand / Steering vECU dynamics 후 actual |
| Drive Command / Drive Actual | aggregate driven-wheel signed motor torque, N·m; 전진 구동 양수, 전진 회생 음수 | Central 배분·Zone 전달 demand / Drive vECU dynamics 후 actual; 후진 확장 제외 |
| Drive Actual regen capability | nonnegative 회생 토크 한계 N·m + 별도 validity/source freshness/제한 원인 | Drive가 산출하고 Central allocation이 배분에 사용; actual torque와 구분 |
| Brake Command / Brake Actual | effective aggregate friction-brake pressure, Pa, nonnegative | Central 배분·Zone 전달 demand / Brake vECU dynamics 후 actual; caliper 상세 모델은 요구하지 않음 |
| 각 actual validity/state | actuator별 valid/unavailable 및 local state | 수신 성공만으로 actual health가 유효해지지 않음 |

Ego/path 의미 frame은 x forward, y left, z up, yaw left-positive다. Path tracking 기준점은
**ego rear-axle center**로 통일한다. CARLA-native 좌표/steer 부호와 rear-axle 위치 변환은
Host adapter/state bridge에서 M6/M7에 검증한다(TBD-02/07). 단위 변환을 Controller에
숨기지 않는다. Acceleration demand/curvature→torque/angle, normalized braking→pressure의 allocation,
max pressure/torque/angle와 CARLA normalization 수치는 M2/M4/M6(TBD-02/03/06)이다.
Target speed는 추종 기준이고 longitudinal acceleration demand는 Central PID의 제어 출력이다.
이를 분리해야 Zone에 speed controller의 책임이 암묵적으로 옮겨가지 않는다. Central allocation은
vehicle acceleration demand를 구동/제동 물리량으로 배분하며 정상/보호 braking demand의
충돌 우선순위는 M4(TBD-06)에 결정한다. 물리 의미를 고정하되 특정 차량의 calibration을
M0에서 꾸며내지 않기 위한 선택이다.

RG-01에서는 Central이 회생 한계 안에서 Drive의 음수 토크와 Brake의 마찰제동 압력을
배분한다. 공통 wheel 기준의 압력→토크 변환과 actual 기반 전환 보정의 첫 component는
[M4 allocation](../learning/m4_control_allocation.md)에 구현했다. 차량 calibration/전환 수용은 TBD-02/03/06이다.
유효 capability 0과 critical Drive Actual 상실은 다른 조건이며 상세 계약은
[회생제동 설계](regenerative_braking_design.md)를 따른다.

EV-01의 BMS SOC/전압/전류/온도/charge·discharge power limit, 전원 요청과 실제 상태는
[EV 의미 계약](ev_power_bms_design.md#semantic-interface-초안)을 따른다. 상위 status는
Zone을 거치고 Drive에 전달한 BMS dependency도 원천 validity/time을 유지한다.
셀 전압·온도의 최소/최대값은 로컬 IF-MODEL-BMS 입력 범위이며 기존 CAN pack 관측 layout과 별개다.
기존 six-frame payload에 EV 상태를 이미 담는 것으로 해석하지 않는다.
ZON-01에서 차량 전체 allocation/permission은 Central 별도 단일 owner이며 두 Zone은 각 scope를 검증·전달한다.
Peer envelope와 원천/의존 sample의 validity/age를 별도로 검사한다.

## Metadata and validity

[M2 첫 Steering 모델](../learning/m2_steering_model.md)이 accepted Command에 delay/rate/angle limit을
적용해 Actual을 생성한다. Source expiry/continuity/control gap의 첫 SIL 보호 정책은 pending 취소와
angle hold, FAIL_SAFE + LocalProtection이다. 기존 wire/meaning은 유지하며 차량 보호 calibration은 후속이다.
[Brake 첫 모델](../learning/m2_brake_model.md)도 독립 pressure Actual을 생성하고 가압/감압 rate를
분리한다. Local fault에서는 max(actual, fixture floor) ramp를 사용한다. Pressure→wheel torque 변환과
첫 Central 회생 배분은 component로 구현했으며 차량 통합은 후속이다. 유효 0/release와 unavailable의 기존 의미는 유지한다.

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

`interfaces/common/`에는 domain과 독립인 P05, 공통 actuator payload 직렬화와 수신 상태,
`interfaces/steering/`에는 angle/frame codec과 로컬 수신부, `interfaces/brake/`에는 pressure/frame
codec·로컬 수신부, `interfaces/drive/`에는 signed torque/feedback codec·수신부,
`interfaces/bms/`에는 EV 물리값·6개 frame codec과 항목별 수신부가 있다.
`interfaces/socketcan/`은 Linux socket I/O와 actuator·EV 변환을 맡는다.
`interfaces/dbc/`에는 actuator/EV 총 12개 frame 초안이 있고 DDS 구현은 후속 작업이다. [DDS ICD](ethernet_dds_icd.md),
[traceability](../test-plan/traceability.md)를 참조한다.
