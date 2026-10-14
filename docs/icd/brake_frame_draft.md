# Brake Command/Actual wire 초안

Date: 2026-10-13. Status: **DESIGN PROPOSAL / Host codec·DBC·vCAN wire 시험 실행**.
학습자 review는 PENDING이다. [M0 의미 계약](interface_overview.md)의 effective aggregate brake
pressure, Pa, nonnegative를 유지한다. 차량 calibration이나 six-frame wire baseline 채택은 아니다.
[설계 결정](../adr/ADR-0010-brake-wire-codec.md), [실행 기록](../learning/m1_brake_codec.md).

## 압력 표현

[첫 M2 Brake 모델](../learning/m2_brake_model.md)은 이 wire를 유지하면서 delay/rise/fall과
독립 Actual, local source-loss pressure protection을 Host에서 구현·시험했다.
실차 pressure/torque calibration과 전체 vehicle TC는 후속이다.

| 항목 | 초안 |
| --- | --- |
| 물리 의미 | Command: Central이 배분하고 Zone이 검증·전달한 압력 demand; Actual: 독립 Brake 모델의 실제 압력 sample |
| 단위 | Pa; 음수 없음 |
| Field | byte 0–1, unsigned 16-bit, little endian |
| Scaling | raw × 1,000 Pa, offset 0 |
| 유효 wire 범위 | raw 0–65,534 → 0–65,534,000 Pa |
| Invalid/unavailable | raw 65,535 → `FF FF`, Validity=0 |
| 제동 해제 | raw 0 → `00 00`, Validity=1 |
| Encode | finite와 범위를 먼저 검사, 가장 가까운 raw로 반올림; 정확한 양수 절반은 위쪽 |

1,000 Pa는 프로젝트의 해상도 제안이다. 양산차/OEM 표준 해상도를 주장하지 않는다.
양자화 오차는 유효 입력에 대해 최대 500 Pa이며, 500 Pa보다 작은 양수는 0으로 표현된다.
음수나 wire 최대 초과를 0/최댓값으로 clamp하지 않는다. 실제 압력 한계·응답·보호 출력은
TBD-02/03의 별도 설정이며 wire 최대 압력을 차량의 최대 제동 압력으로 사용하지 않는다.

## Envelope와 E2E

| Frame | CAN ID | Sender → Receiver | P05 Data ID |
| --- | --- | --- | --- |
| BrakeCommand | `0x181` | Zone → BrakeVecu | `0x1101` |
| BrakeActual | `0x281` | BrakeVecu → Zone | `0x1102` |

Standard 11-bit CAN FD, payload 32 bytes, DLC code 13, BRS=0, ESI=0이다.
Linux FDF marker=4는 허용하며 extended/RTR/error ID flags, 다른 길이, classic CAN은 거부한다.
Logical cycle은 10 ms다. 실제 bus timing이나 arbitration 검증은 이번 vCAN 시험 범위가 아니다.

기존 [Steering schema 2](steering_frame_draft.md)의 metadata 배치를 재사용한다.
32 bytes는 이 프로젝트에서 선택한 배치이며 압력 하나나 P05가 요구하는 고정 길이가 아니다.

| Byte | 내용 |
| --- | --- |
| 0–1 | Pressure |
| 2 / 3 | SchemaVersion=2 / Validity=0 또는 1 |
| 4–7 / 8–11 | trace Sequence uint32 / Epoch uint32, nonzero |
| 12–19 | SourceTimeNs uint64, 정수 그대로 보존 |
| 20–23 | CausalSequence uint32 |
| 24 / 25 | LocalState / Origin, Steering과 같은 enum 표현 |
| 26–28 | Reserved=0 |
| 29–30 / 31 | P05 CRC16 LE / Counter uint8 |

P05 설정은 length 256 bits, offset 232 bits, MaxDeltaCounter=10이다.
CRC는 payload 0–28 + Counter byte 31 + 해당 Data ID의 low/high byte를 포함한다.
CRC byte 29–30은 제외한다. [기존 P05 알고리즘](../learning/m1_autosar_e2e_profile5.md)을 사용한다.
각 Command/Actual은 별도 TX/RX Counter state를 가진다. Steering과 Brake의 Data ID도 분리한다.

SourceTimeNs는 Command의 allocation 생성 시각, Actual의 원천 모델 sample 시각이다.
서로 같은 clock/session을 설정해야 한다. Actual의 CausalSequence는 같은 Epoch의 마지막 수용
BrakeCommand Sequence이고 Origin=NoAcceptedInput에서는 해석하지 않는다. 재전송한 cached sample의
Sequence/source time을 갱신해서는 안 된다. 현재는 모델 대신 독립 fixture를 송신한다.

## Golden vectors와 검사 경계

Sequence=0, Epoch=1, Counter=0의 독립 fixture다. Normal 입력은 LocalState=1, Origin=1이며
invalid Actual은 두 값이 0이다. 전체 32-byte 기대값은
[단위 시험](../../tests/unit/brake_codec_test.cpp)과 [DBC 검사기](../../tools/check_actuator_dbc.py)에 있다.

| Frame / 값 | Pressure bytes | SourceTimeNs | CausalSequence | CRC |
| --- | --- | --- | --- | --- |
| Command 2,000,000 Pa | `D0 07` | 1,000,000,000 | 7 | `0x36CA` |
| Actual 1,500,000 Pa | `DC 05` | 1,010,000,000 | 0 | `0x3D73` |
| Command 0 Pa | `00 00` | 1,000,000,000 | 7 | `0x0D2A` |
| Actual unavailable | `FF FF` | 1,010,000,000 | 0 | `0x6BB3` |

Stateless decode는 envelope, CRC, schema, enum, reserved, Epoch 표현과
Validity/invalid code의 일관성을 검사한다. Stateful Check는 P05 Counter를 추가로 검사한다.
둘 다 성공해도 Brake command를 actuator에서 사용할 수 있다는 판정은 아니다.
Trusted session, trace Sequence 진행, source-age, mode, 실제 압력 범위, last-valid snapshot과
timeout latch는 [Brake application receiver](../adr/ADR-0012-brake-receiver.md)에서 구현·시험했다.
Source/now는 같은 monotonic clock, 기본 source age <=30 ms와 RX timeout >=80 ms이며
fixture pressure 범위는 0–2,000,000 Pa다. 차량 calibration과 물리 timeout 출력은 미확정이다.
<=100 ms loss 검출 계약은 유지하며 로컬 fixture 결과를 전체 system 요구 충족으로 표시하지 않는다.
