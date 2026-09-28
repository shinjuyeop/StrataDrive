# Steering angle field encoding draft

Status: **M1 field 단위 구현 초안 / 학습자 review PENDING**.
관련 범위는 IF-CAN-STEERING, TBD-01/02다. 아래 형식은 codec을 검토하기 위한 제안이며
six-frame wire baseline으로 채택한 상태가 아니다. CAN ID, frame 내 위치, 전체 payload
길이, CRC/sequence/epoch/freshness/validity/state는 별도 M1 작업으로 남는다.

## Field contract

Steering Command와 Steering Actual은 모두 equivalent front road-wheel angle, rad,
좌회전 양수라는 [기존 의미](interface_overview.md#semantic-payload-contract)를 유지한다.
두 message의 field 표현을 공통으로 검토하지만 실제 값의 생성 책임은 서로 다르다.

| 항목 | 이번 초안 |
| --- | --- |
| Field 크기 | 16 bits / 2 bytes |
| Raw 표현 | signed two's complement |
| Byte order | little-endian; 하위 byte 먼저 |
| Scaling / offset | 0.0001 rad/count / 0 rad |
| 표현 가능한 유효 raw | −32767 … +32767 |
| Reserved raw | −32768, bytes `00 80`; decoder가 거부 |
| 표현 범위 | −3.2767 … +3.2767 rad; actuator 허용 범위와 구분 |
| Encode | finite·표현 범위 확인 → 가장 가까운 raw 정수로 반올림 → bytes |
| 반올림 동률 | 구현의 `double` 나눗셈 결과가 정확한 half이면 0에서 멀어지는 방향 |
| Invalid 입력 | NaN/±Inf/표현 범위 밖은 실패; 조용히 clamp하지 않음 |

표현 범위는 저장 형식의 용량이다. 실제 최대 조향각과 정상 command 허용 범위는
TBD-02/03/06이며 이후 receiver가 calibration·mode와 함께 검사한다.
이 codec의 성공은 숫자 표현이 가능하다는 뜻이다. Command 수용, actual validity,
last-valid RX 갱신 또는 차량 안전성을 보장하지 않는다.

## Rationale and limits

16-bit fixed-point는 양·음 조향을 2 bytes로 표현하며 raw/physical 관계를 직접 확인하기
쉽다. 0.0001 rad 간격을 후보로 두어 반올림 오차가 원칙적으로 반 간격인 0.00005 rad
이내가 되도록 한다(부동소수점 계산 오차 별도). 이는 센서 정확도나 추종 성능 요구가 아니다.
Little-endian은 explicit byte packing으로 구현하며 CPU native endian에 의존하지 않는다.
Reserved code는 미정·invalid 숫자 표현을 구분하기 위한 후보이며 별도 validity metadata를
대신하지 않는다. Encoder는 이를 생성하지 않고 decoder는 거부한다.

0.001 rad 간격은 더 넓은 범위를 표현하지만 이 초안보다 거칠다. Float32는 표현 범위가
넓지만 4 bytes가 필요하고 NaN/Inf의 처리도 필요하다. 최종 채택 전에 actuator 범위,
필요 분해능, six-frame layout 및 AUTOSAR pilot 제약과 함께 재검토한다.
변경 시 이 계약과 codec·golden vectors를 함께 수정하며 기존 runtime 호환성을 주장하지 않는다.

## Golden vectors

아래 기대값은 scale 계산과 two's complement에서 구한 기준이다. Encoder 출력을
그대로 기대값으로 복사하지 않는다.

| 입력 rad | Raw | Bytes (전송 순서) | Decode rad |
| --- | --- | --- | --- |
| 0 | 0 | `00 00` | 0 |
| +0.1 | 1000 (`0x03E8`) | `E8 03` | +0.1 |
| −0.1 | −1000 (`0xFC18`) | `18 FC` | −0.1 |
| +3.2767 | 32767 | `FF 7F` | +3.2767 |
| −3.2767 | −32767 | `01 80` | −3.2767 |
| — | reserved −32768 | `00 80` | reject |

DBC의 factor/offset, signed 및 byte order 의미는
[CSS Electronics의 DBC 설명](https://www.csselectronics.com/pages/can-dbc-file-database-intro)을
참고했다. 이번 변경에는 불완전한 message를 실제 DBC로 등록하지 않는다.
전체 DBC의 start bit와 다른 field를 확정한 뒤 독립 DBC parser와의 교차 검증을 추가한다.
