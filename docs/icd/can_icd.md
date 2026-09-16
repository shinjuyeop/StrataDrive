# CAN / CAN FD application ICD template

Status: **DRAFT / TBD**. CAN ID, DBC와 codec은 미구현이다. Zone Controller–Leaf ECU는 SocketCAN/vCAN을
사용할 계획이며 application interface는 CAN FD frame을 가정한다. vCAN이 CAN FD
전기적 동작, bit timing, 실제 bus arbitration/부하를 재현한다고 주장하지 않는다.
[SocketCAN 공식 문서](https://docs.kernel.org/networking/can.html)는 API와 가상 interface의
참고 자료이며 실제 차량 bus 검증 증거가 아니다.

## Frame definitions

| Interface / frame direction | CAN ID | ID format | FD/BRS flags | DLC | Payload bytes | Cycle time | Timeout | Failure behavior |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IF-CAN-STEERING / Zone Controller → ECU command | TBD | 11/29-bit TBD | TBD | TBD | TBD | TBD | TBD | invalid/stale 거부 + local 정책 TBD |
| IF-CAN-STEERING / ECU → Zone Controller actual feedback | TBD | TBD | TBD | TBD | TBD | TBD | 100 ms 통신 상실 검출 예시; budget 분해 TBD | unavailable event + 상태 정책 TBD |
| IF-CAN-BRAKE / Zone Controller → ECU command | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| IF-CAN-BRAKE / ECU → Zone Controller actual feedback | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| IF-CAN-DRIVE / Zone Controller → ECU command | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| IF-CAN-DRIVE / ECU → Zone Controller actual feedback | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

DLC code와 payload byte length를 구분하고 유효한 CAN FD length mapping을 M1에서
검증한다. Application frame bytes와 SocketCAN API의 length 의미를 명시한다.

## Signal layout template (one table per frame)

| Signal | Start bit | Bit length | Signed/type | Scaling / offset | Unit | Endianness | Min/max | Invalid/reserved | Producer / consumer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Demand or actual physical value | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Alive counter | TBD | TBD | unsigned, TBD | TBD | count | TBD | TBD | TBD | TBD |
| Application CRC | TBD | TBD | TBD | N/A | N/A | TBD | TBD | TBD | TBD |
| Status/validity | TBD | TBD | TBD | TBD | N/A | TBD | TBD | TBD | TBD |

DBC bit numbering, Intel/Motorola mapping, signed encoding, physical↔raw rounding,
saturation, reserved value와 golden frame vectors를 검토한다. CAN FD link-layer CRC와
application alive counter/CRC는 별개다. 후자는 software로 검증할 예정이다.

## Integrity / timeout contract template

- Alive counter 폭, modulus, 허용 increment/window, 중복/순서 오류 정책: TBD
- Counter 초기화, ECU restart, receiver 재동기화와 startup grace: TBD
- CRC 폭, polynomial, init, reflection, xor-out, byte order: TBD
- CRC 적용 bytes, data ID/CAN ID 포함 여부, CRC field 제외: TBD
- Command/feedback timeout, clock domain, last-valid-RX 의미와 monitor task: TBD
- Queue depth/drop 정책, 오류 threshold, debounce, DTC mapping과 복구: TBD
- Fault 시 출력/ramp/hold의 수치 한계, 상태 전환과 반응 budget: TBD

Invalid CRC/counter/range frame은 reject하고 valid-command age를 갱신하지 않는
방향이다. Freshness는 송신 요청값 대신 검증된 수신과 연결한다. Actual feedback이
오래되거나 멈춘 경우 정상 heartbeat만으로 actuator health를 정상 판정하지 않도록
tracking/response monitor를 둔다.

M1 acceptance는 DBC encoding/decoding golden vectors와 vCAN application-frame
검사다. 이를 physical CAN FD 또는 HIL 시험이라고 표현하지 않는다.
관련 요구: SYS-COM-001/002, SYS-CTRL-001;
[verification](../test-plan/verification_strategy.md).
