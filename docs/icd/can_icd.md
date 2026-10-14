# CAN / CAN FD application ICD baseline

Status: semantic/failure contract **DEFINED**, actuator 6개 + EV 6개 DBC/codec **Host 초안 구현·시험 / baseline 채택 PENDING**.
[Steering 두 frame의 설계·DBC 초안](steering_frame_draft.md)을 작성했다(학습자 review PENDING).
ID/layout/metadata/receiver 정책은 제안이며 wire baseline 채택이 아니다.
[Steering frame codec·Host parser 검증](../learning/m1_steering_frame_codec.md)은 실행했다.
[AUTOSAR R25-11 P05 Protect/Check](../learning/m1_autosar_e2e_profile5.md)를 추가했다.
Wire decode는 stateless이며 P05 Counter는 별도 state로 검사한다.
[Steering 수신부의 수용/trace Sequence/freshness/timeout](../learning/m1_steering_receiver.md)은
제어 가능한 시계로 Host에서 시험했다. 이어서 [SocketCAN/vCAN 연결](../learning/m1_steering_socketcan.md)의
독립 TX/RX, bounded dispatch, fault/timeout을 실행했다. 후속 [session/queue](../learning/m1_session_queue.md)에서
영속 local Epoch 발급과 application/kernel overflow를 검사했다. Actual Central coordinator/Zone DDS와 차량 통합은 남아 있다.
[Steering angle field 초안](steering_angle_encoding.md)의 C++ codec과 Host 단위 시험을 추가했다.
Host vCAN에서 Steering application Command/Actual fixture를 송수신했다. Actual dynamics와
[Brake Command/Actual 초안](brake_frame_draft.md)의 압력 codec·DBC·P05와 vCAN wire 송수신도
[시험했다](../learning/m1_brake_codec.md). 이어서 [Brake application receiver](../adr/ADR-0012-brake-receiver.md)의
수용/timeout을 normal/sanitizer unit·vCAN에서 실행했다.
[Drive signed torque/회생 피드백 wire](drive_frame_draft.md)와 [application receiver/vCAN](../learning/m1_drive_codec.md)도
실행했다. Actual dynamics, Zone blending 및 전체 차량 TC는 NOT RUN이다.
Zone–vECU는 SocketCAN/vCAN을 사용하고 CAN FD application contract를 학습한다.
vCAN은 전기적 동작, bit timing, 실제 arbitration/bus load 검증이 아니다.

## Frame families and behavior

각 command와 actual은 별도 frame이다. Cycle은 Reference v0.1의 logical starting point이며
100 ms는 timeout parameter 자체가 아닌 last-valid RX부터 **검출 완료까지의 상한**이다.

| Family / 방향 | 의미 | Cycle | 검출 / failure behavior |
| --- | --- | --- | --- |
| IF-CAN-STEERING / Zone → vECU | Steering Command (road-wheel angle demand) | 10 ms | invalid reject, age 미갱신; command loss <=100 ms, local FAIL_SAFE |
| IF-CAN-STEERING / vECU → Zone | Steering Actual | 10 ms | actual loss <=100 ms, unavailable/FAIL_SAFE; F01 |
| IF-CAN-BRAKE / Zone → vECU | Brake Command (pressure demand) | 10 ms | invalid reject, age 미갱신; command loss <=100 ms, local FAIL_SAFE |
| IF-CAN-BRAKE / vECU → Zone | Brake Actual | 10 ms | actual loss <=100 ms, unavailable/FAIL_SAFE; braking stop 보장 아님 |
| IF-CAN-DRIVE / Zone → vECU | Drive Command (signed motor torque demand: 구동/회생) | 10 ms | invalid reject, age 미갱신; command loss <=100 ms, zero motor torque target/FAIL_SAFE; F03 |
| IF-CAN-DRIVE / vECU → Zone | Drive Actual + 별도 유효성의 회생 가용량 | 10 ms | actual loss <=100 ms, unavailable/FAIL_SAFE; capability 0/unknown은 별도 처리 |

단위/부호는 [common contract](interface_overview.md), actuator별 물리 반응 TBD는
[safety](../requirements/safety_requirements.md)를 따른다. Feedback의 값은 command echo가
아니라 task/delay/saturation/dynamics/fault를 거친 실제 **모델 state sample**이다.

Drive는 [RG-01](regenerative_braking_design.md)을 반영해 Command 32 / Actual 64 bytes로
정의했다. Signed torque와 capability의 scaling/invalid code/원천 freshness/배치는
[Drive wire 초안](drive_frame_draft.md)을 따른다. Critical actual validity와 capability validity를
분리하고 Steering/Brake wire는 유지했다. 회생 물리 모델·배분 구현은 후속 작업이다.

## EV-01 추가 wire 초안

2026-10-14 [BMS wire 초안](bms_frame_draft.md)과 [BMS DBC](../../interfaces/dbc/bms_m1_draft.dbc)를
추가했다. EV schema 1의 6개 frame에 대해 Host layout/CRC/canonical vector를 검사했다.
[EV C++ codec/항목별 receiver와 native SocketCAN 변환](../learning/m1_bms_codec.md)은 Host에서 시험했다.
EV vCAN TX/RX/relay도 기존 fixture에서 36개 case로 시험했다.
Actual coordinator/Zone timing과 Drive의 실제 통합 gate는 PLANNED / NOT RUN이다.
[EV 설계](ev_power_bms_design.md)의 IF-CAN-BMS(power 요청 / battery·limit·power status),
IF-CAN-DRIVE-CONSTRAINT(원천 limit / drive permission)의 wire/library를 추가했다.
Frame 수/ID/DLC/schema/P05/Data ID, critical 목록과 local rate/age는 ADR-0016 초안에 있다.
Receiver의 trusted INIT·typed parent/expiry 검사는 구현했다. 실제 context 전달 coordinator와
wire 최종 수용은 **TBD-14 / 후속**이다. Local transport는 독립 trusted stdin fixture로 검사했다.
기존 six-frame C++/vCAN PASS와 구분한다.
관련 요구는 SYS-EV-001–005, SYS-COM-003/004 v0.3이며 TC-EV-001–005는 NOT RUN이다.

기존 M1 Drive의 보조 feedback source-age <=30 ms를 BMS에 자동 복제하지 않는다.
BMS 센서/limit 생성·발행 주기를 정한 뒤 cached input의 age와 monitor margin을 포함해
검증한다. 유효 zero limit와 unknown을 구분하고 Zone 전달 시각으로 원천 age를 연장하지 않는다.
Critical status loss 검출 상한은 <=100 ms지만 power sequence/physical response 기한은 별도다.
새 source 50/input 70 ms 시작값과 기존 Drive 30 ms 정책의 차이를 config로 분리·시험했다.
Drive source/torque 기본 budget은 유지하며 capability input 70 ms는 명시적 opt-in이다.

## M1 wire-definition work (TBD-01)

M0에서는 아래 필드를 할당하지 않는다. 각 6개 frame에 대해 M1에서 결정한다.

| 결정 그룹 | M1에서 기록할 내용 |
| --- | --- |
| Frame | CAN ID, 11/29-bit format, FD/BRS flags, DLC code, payload byte length, direction |
| Signal | start bit, bit length, signed/type, scaling/offset, unit, endian, min/max, invalid/reserved |
| Sequence | width/modulus, increment/window, duplicate/out-of-order, wrap/restart/epoch 재동기화 |
| Application integrity | 세 actuator에 R25-11 P05 Protect/Check 적용; stream별 Data ID/CRC/Counter와 trace Sequence 구분; Drive Actual extension도 CRC에 포함 |
| Freshness | source time/age 표현 또는 동등한 replay 방지, local RX time, 원천 metadata side-channel 대응 |
| Receiver | bounded queue/depth/overflow, latest-valid snapshot, timeout threshold/monitor budget, startup handshake |
| Verification | physical↔raw rounding/saturation, endian/bit numbering, counter/CRC golden vectors, malformed frame tests |

DLC code와 payload byte length의 CAN FD mapping을 구분한다. Application CRC는 CAN FD
link-layer CRC와 별개이며 application에서 검증한다. 단순 sequence increment만으로
지연된 순차 replay의 freshness를 입증할 수 없으므로 source-age/replay 정책을 함께 결정한다.

## Validation / timeout invariant

1. 원시 frame 수신과 유효 command 수용을 분리한다.
2. CRC, sequence/epoch, range/mode, freshness 중 하나라도 실패하면 reject한다.
3. Rejected frame은 마지막 유효 demand와 last-valid-command RX를 갱신하지 않는다.
4. 정상 heartbeat/다른 actuator feedback으로 해당 actuator의 timeout을 reset하지 않는다.
5. 유효 RX 없이 100 ms를 넘기기 전에 receiver가 loss를 검출한다. Threshold + polling +
   dispatch/execution margin의 합을 M1/M3에 검토한다. Startup/pause는 timing 계약을 따른다.
6. Timeout 후 old demand 유지 대신 local protection을 선택한다. 복구는 explicit INIT gate다.
7. Zone/Host는 raw command를 actual feedback으로 합성하지 않는다.
8. Application queue full/kernel drop은 backlog를 버리고 continuity error를 latch한다.
   Current sample을 닫고 diagnostic history를 유지하며 fresh packet으로 복구하지 않는다.
   새 trusted Epoch/INIT와 깨끗한 socket/queue 경계를 사용한다.
9. 다른 Epoch의 CRC/canonical 메시지는 현재 P05 transport check state를 변경하지 않는다.

M1 local issuer/FIFO의 운영 계약은 [ADR-0018](../adr/ADR-0018-local-session-and-rx-continuity.md)을 따른다.
Queue capacity 32, ingress/dispatch budget 각 8은 첫 fixture 설정이며 task/bus 부하의 수용은 M2/M3다.
Central session은 persistent store를 소유하고 authority를 제공한다. M1은 CLI/stdin을 사용하는
trusted local bootstrap을 검사했으며 실제 Central–Zone/vehicle INIT gate 구현은 M4/M5다.

Drive의 canonical 보조 feedback은 freshness/range 실패 시 torque와 분리해 무효화한다.
Critical torque 검증이 통과하면 해당 stream의 valid-RX는 갱신할 수 있지만 capability의
원천 age는 갱신하지 않는다. Canonical wire 위반이나 torque 검증 실패는 전체 frame을 거부한다.

Steering/Brake local timeout의 물리 출력/hold/ramp, Drive torque 감소 envelope는
M2(TBD-03)에서 정하고 test를 실행한다. M1 frame/vector 시험으로 물리 응답까지
VERIFIED 처리하지 않는다. M1 acceptance는 DBC golden vectors와 vCAN application-frame
검사이며, M0에는 DBC 파일이나 vCAN 실행을 추가하지 않는다.

관련 요구: SYS-COM-001/002/003/004, SYS-ARCH-002, SYS-CTRL-001/002, SYS-SAFE-003/004.
[Timing](../requirements/timing_requirements.md), [verification](../test-plan/verification_strategy.md).

## ZON-01 예정 bus 배치

[Front/Rear 분할](../architecture/zonal_partition.md)에서 Steering/Brake는 Front CAN,
Drive/BMS/Drive constraint는 Rear CAN에 연결한다. 기존 six-frame wire 의미는 유지한다.
현재 단일 vCAN fixture PASS가 두 bus/Zone routing 증거는 아니다. Bus/interface 이름은
runtime config로 분리하고 bus/producer identity를 trace에 포함한다. Peer와 원천의 age를
재직렬화로 연장하지 않는다. BMS 추가 wire는 TBD-14, Central–Zone 계약은 TBD-15다.
