# CAN / CAN FD application ICD baseline

Status: semantic/failure contract **DEFINED**, CAN ID/DBC/codec/vCAN runtime **PLANNED**.
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
| IF-CAN-DRIVE / Zone → vECU | Drive Command (torque demand) | 10 ms | invalid reject, age 미갱신; command loss <=100 ms, zero-propulsive target/FAIL_SAFE; F03 |
| IF-CAN-DRIVE / vECU → Zone | Drive Actual | 10 ms | actual loss <=100 ms, unavailable/FAIL_SAFE |

단위/부호는 [common contract](interface_overview.md), actuator별 물리 반응 TBD는
[safety](../requirements/safety_requirements.md)를 따른다. Feedback의 값은 command echo가
아니라 task/delay/saturation/dynamics/fault를 거친 실제 **모델 state sample**이다.

## M1 wire-definition work (TBD-01)

M0에서는 아래 필드를 할당하지 않는다. 각 6개 frame에 대해 M1에서 결정한다.

| 결정 그룹 | M1에서 기록할 내용 |
| --- | --- |
| Frame | CAN ID, 11/29-bit format, FD/BRS flags, DLC code, payload byte length, direction |
| Signal | start bit, bit length, signed/type, scaling/offset, unit, endian, min/max, invalid/reserved |
| Sequence | width/modulus, increment/window, duplicate/out-of-order, wrap/restart/epoch 재동기화 |
| Application CRC | width/polynomial/init/reflection/xor-out/order, coverage, CRC field 제외, data ID 보호 |
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

Steering/Brake local timeout의 물리 출력/hold/ramp, Drive torque 감소 envelope는
M2(TBD-03)에서 정하고 test를 실행한다. M1 frame/vector 시험으로 물리 응답까지
VERIFIED 처리하지 않는다. M1 acceptance는 DBC golden vectors와 vCAN application-frame
검사이며, M0에는 DBC 파일이나 vCAN 실행을 추가하지 않는다.

관련 요구: SYS-COM-001/002/003/004, SYS-ARCH-002, SYS-CTRL-001/002, SYS-SAFE-003/004.
[Timing](../requirements/timing_requirements.md), [verification](../test-plan/verification_strategy.md).
