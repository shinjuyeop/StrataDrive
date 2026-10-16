# M1 Drive Command / Actual wire 초안

Date: 2026-10-13. Status: **DBC/codec/receiver/vCAN Host 시험 실행 / 학습자 review PENDING**.
[ADR-0013](../adr/ADR-0013-drive-feedback-wire.md)과 [RG-01](regenerative_braking_design.md)을 따른다.
Six-frame wire baseline 채택이나 차량 runtime 완료를 뜻하지 않는다.

## 물리량과 프레임

Torque는 aggregate driven-wheel 기준 N·m다. 전진 구동 양수, 회생 음수, 0은 모터 토크
요구 없음이다. 마찰제동 압력은 별도 Brake frame으로 전달한다. Wheel speed는 같은
equivalent-wheel 기준의 nonnegative rad/s이며 후진은 현재 ODD 밖이다.

| 항목 | DriveCommand | DriveActual |
| --- | --- | --- |
| CAN ID / 방향 | 0x182, Zone → Drive vECU | 0x282, Drive vECU → Zone |
| Payload / bus DLC | 32 bytes / 13 | 64 bytes / 15 |
| P05 Data ID / length bits | 0x1201 / 256 | 0x1202 / 512 |
| 의미 | 모터 torque demand | 독립 actual torque + wheel speed + regen capability |

Standard 11-bit CAN FD, BRS=0/ESI=0, logical period 10 ms다. SocketCAN len에는 DLC code가
아닌 32/64를 넣는다. Kernel FDF flag 0x04만 허용한다. 실제 ID/flags/length를 보존하고
다른 길이, classic/extended/RTR/error 입력을 수용 가능한 frame으로 정규화하지 않는다.
64 bytes는 원천 시각을 포함하기 위한 프로젝트 선택이며 회생제동의 표준 고정 길이가 아니다.

## 공통 prefix: 두 frame의 bytes 0..31

| Byte | 필드 / 표현 |
| --- | --- |
| 0..1 | Torque: signed int16 LE, 0.1 N·m, valid raw -32767..32767, -32768(00 80) invalid |
| 2 / 3 | SchemaVersion=2 / Torque Validity=0 또는 1 |
| 4..7 / 8..11 | uint32 trace Sequence / nonzero uint32 Epoch |
| 12..19 | uint64 actual sample 또는 command generation SourceTimeNs |
| 20..23 | uint32 CausalSequence |
| 24 / 25 | LocalState / Origin: 기존 actuator enum |
| 26..28 | Reserved=0 |
| 29..30 / 31 | P05 CRC16 LE / uint8 Counter |

Validity=0이면 torque raw -32768이어야 한다. 유효한 0은 raw 0000/Validity=1이다.
반올림 전 finite와 wire 범위 ±3276.7 N·m를 검사한다. Half-away-from-zero rounding을
사용하며 최대 양자화 오차는 0.05 N·m다. 차량 한계로 clamp하는 codec이 아니다.

## Actual extension: bytes 32..63

| Byte | 필드 / 표현 |
| --- | --- |
| 32..33 | WheelSpeed: uint16 LE, 0.01 rad/s, valid 0..65534, FFFF invalid |
| 34 | WheelSpeedValid: 0/1 |
| 35 | RegenLimitReason: 0 Nominal / 1 MotorOrSpeedLimited / 2 ChargeAcceptanceLimited / 3 Disabled / 4 InputsInvalid |
| 36..37 | RegenTorqueLimit: uint16 LE, 0.1 N·m, valid raw 0..32767, FFFF invalid; 32768..65534 forbidden |
| 38 / 39 | RegenCapabilityValid: 0/1 / FeedbackReserved=0 |
| 40..47 | uint64 WheelSpeedSourceTimeNs |
| 48..55 | uint64 CapabilitySourceTimeNs: 실제 capability 산출 시각 |
| 56..63 | uint64 CapabilityInputTimeNs: 산출에 사용한 모든 dependency 중 가장 오래된 원천 시각 |

Invalid speed는 FFFF/validity 0/time 0이다. Invalid capability는 FFFF/validity 0/
InputsInvalid/두 time 0이다. Valid capability는 wire상 speed가 존재해야 한다.
Disabled reason은 유효 0 limit만 허용한다. Nominal은 현재 모델의 nominal 한계라는 뜻이며
회생 torque >0 또는 무제한을 보장하지 않는다. Validity flag만으로 사용을 허가하지 않는다.
유효한 0 limit은 현재 회생 가용량이 없다는 정보이며 torque unavailable과 구분한다.
정수 timestamp를 float64로 변환하지 않는다.

P05는 CRC bytes 29..30만 제외한 전체 payload를 계산한 뒤 implicit Data ID low/high를
추가한다. Command는 0..28 + 31, Actual은 0..28 + 31..63을 보호한다.
첫 Protect counter 0, modulo 256, max delta 10이며 trace Sequence와 별개다.

## 수신 정책과 제어 입력

Torque 수용은 공통 clock/timeout → envelope/P05 → canonical payload → metadata →
value/mode/range 순서다. 첫 Sequence 0..9, 이후 +1..+10, same-Epoch uint32 wrap 금지,
trusted session 시작 이후의 엄격히 증가하는 source time과 age <=30 ms를 적용한다.
Command는 NormalPath + NORMAL/DEGRADED만 수용한다. M2의 [Drive local gate](../learning/m2_drive_gate.md)는
원천 battery limits·Central permission·실제 local HV/speed를 검사하고 local protection을 적용한다.
Actual의 유효 torque와 sender state는 별개다. NoAcceptedInput은 INIT에서만 허용한다.

보조 feedback은 다음을 별도로 검사한다.

- Caller가 명시한 speed/regen 범위; capability 최대값은 수용 가능한 음수 torque 크기 이내.
- 각 source time은 session 시작 이상, torque source time/now 이하.
  Capability input time은 session 시작 이상, capability source time 이하.
- Wheel/capability source와 capability input의 now 기준 age가 모두 <=30 ms.
  Config는 0 < feedback_age <= torque_source_age < timeout <=80 ms다.
- 직전 usable feedback보다 source/input time이 후퇴하지 않는다. 같은 source time을
  재사용하면 원천 sample의 값/이유/input time도 동일해야 한다.

Canonical wire를 위반하면 전체 frame을 거부한다. Canonical 보조 값의 원천 age/range/
시간관계가 실패하면 해당 feedback을 제거하고 fresh torque는 독립 수용할 수 있다.
Speed가 사용할 수 없으면 capability도 제거한다. 수용 결과에 Usable/Unavailable/Stale/
Invalid quality를 반환한다. current_sample(now)는 이후 age 만료도 반영하며 과거 보조 값으로
fallback하지 않는다. last_accepted는 raw accepted 진단 이력이며 제어에 직접 쓰지 않는다.

Invalid torque는 보조 capability가 valid여도 critical valid-RX를 갱신하지 않는다.
RX timeout 80 ms/clock rollback은 latched이며 새 Epoch와 비감소 clock의 explicit INIT으로
초기화한다. M2 component의 local motor zero-target 응답과 Drive gate는 구현·시험했고,
실제 Zone/Host gate·에너지 경로는 후속 통합이다. 보조 dependency age의 기본값은 30 ms이며
Drive gate fixture는 capability input에만 70 ms를 명시적으로 선택한다.

Wire golden과 독립 CRC, 범위/시간/invalid/timeout 및 실행 명령은
[Drive 학습 안내](../learning/m1_drive_codec.md)에 기록한다.
