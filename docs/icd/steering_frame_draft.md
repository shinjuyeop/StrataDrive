# M1 Steering Command / Actual frame draft

Status: **2026-10-12 설계 제안 / 학습자 review PENDING**.
관련 interface는 IF-CAN-STEERING, 미결정 항목은 TBD-01/02/04/11이다.
2026-10-12 [ADR-0007](../adr/ADR-0007-autosar-e2e-profile5.md)에 따라 P05/schema 2로 개정했다.
이 문서와 [DBC](../../interfaces/dbc/steering_m1_draft.dbc)는 두 Steering frame의
배치 초안이다. [두 frame의 Host codec/DBC parser 검증](../learning/m1_steering_frame_codec.md)은
구현·실행했고 [P05 Protect/Check](../learning/m1_autosar_e2e_profile5.md)도 Host에서 시험했다.
[로컬 Application Receiver](../learning/m1_steering_receiver.md)는 제어 가능한 시계로 Host에서 시험했다.
Application socket/queue/coordinator 및 measured timeout 통합은 **PLANNED / NOT RUN**이다.
Six-frame baseline 채택이나 M1 acceptance 완료로 처리하지 않는다.

## 1. 먼저 값의 의미와 생성 책임을 정한다

| Message | 송신 → 수신 | Angle의 의미 |
| --- | --- | --- |
| SteeringCommand | Zone → Steering vECU | equivalent front road-wheel angle demand |
| SteeringActual | Steering vECU → Zone | dynamics/fault를 거친 actual model state sample |

두 angle 모두 rad, 좌회전 양수다. 같은 표현 형식을 사용해도 같은 값이라는 뜻은 아니다.
Actual을 Command echo로 생성하지 않는다. 아래 Actual 예시는 독립적인 시험 fixture이며
actuator model의 실행 결과가 아니다. Dynamics는 M2에서 구현한다.

## 2. Frame identity와 크기를 정한다

| Family | Command CAN ID | Actual CAN ID | 이번 상태 |
| --- | --- | --- | --- |
| Steering | `0x180` (384) | `0x280` (640) | 두 frame의 DBC 초안 작성 |
| Brake | `0x181` | `0x281` | ID 후보만 예약; signal/DBC 미작성 |
| Drive | `0x182` | `0x282` | ID 후보만 예약; signal/DBC 미작성 |

ID는 이 프로젝트의 후보이며 OEM/산업 표준 번호가 아니다. CAN ID는 message 종류를
구분하고 송신 책임에 대응한다. 목적지 주소 필드로 취급하지 않는다. 낮은 ID의 물리적
arbitration 우선순위와 실제 bus load는 별도 검토이며 vCAN으로 입증하지 않는다.
기존 transport fixture ID `0x5A0`는 그대로 별개다.

- Standard 11-bit CAN FD data frame; EFF/RTR/ERR 금지.
- BRS=0, ESI=0 송신 후보. 수신에서 BRS/ESI가 set이면 이 실험의 정상 입력으로 수용하지 않는다.
  Linux ABI의 CANFD_FDF 표시는 frame 구분용이며 application signal이 아니다.
- Payload 32 bytes, bus DLC code는 13 (`0xD`). SocketCAN `canfd_frame.len`에는 **32**를 넣는다.
- Logical publication period는 기존 10 ms를 유지한다. 이 문서에는 주기 실행 측정 결과가 없다.

32 bytes를 택한 이유는 source time과 identity를 축약하지 않고 byte 단위로 배치해
검토하기 위해서다. 더 작은 frame으로 최적화하려면 metadata 전달과 replay 검증을 함께
다시 설계한다. [Linux SocketCAN 문서](https://docs.kernel.org/networking/can.html)는
payload length와 socket ABI 크기(CANFD_MTU=72)를 구분한다. DLC 대응은
[Linux length helper](https://github.com/torvalds/linux/blob/master/include/linux/can/length.h)를 참고한다.

## 3. Payload 안에 값과 metadata를 배치한다

모든 multi-byte field는 **little-endian**, byte 0부터 번호를 센다.
DBC start bit는 byte offset × 8이며 모든 field가 byte 경계에서 시작한다.
두 frame은 배치가 같고 송신자/Angle/CausalSequence의 의미가 다르다.

| Byte | DBC start bit / bits | Signal | 형식 / 의미 |
| --- | --- | --- | --- |
| 0–1 | 0 / 16 | Angle | signed, factor 0.0001 rad, offset 0; 기존 field codec 재사용 |
| 2 | 16 / 8 | SchemaVersion | unsigned; 초안 버전 2만 허용, 이전 자체 CRC 버전 거부 |
| 3 | 24 / 8 | Validity | 0=invalid/unavailable, 1=valid; 다른 값 reserved |
| 4–7 | 32 / 32 | Sequence | unsigned; 해당 stream의 발행 번호 |
| 8–11 | 64 / 32 | Epoch | unsigned; 신뢰된 run 설정의 공통 session 번호, 0 금지 |
| 12–19 | 96 / 64 | SourceTimeNs | unsigned; 원천 생성/sample 시각, 같은 clock domain의 ns |
| 20–23 | 160 / 32 | CausalSequence | Command: 원천 VehicleCommand 번호 / Actual: 마지막 수용 SteeringCommand 번호 |
| 24 | 192 / 8 | LocalState | 0=INIT, 1=NORMAL, 2=DEGRADED, 3=FAIL_SAFE; 다른 값 reserved |
| 25 | 200 / 8 | Origin | 0=no accepted input, 1=normal path, 2=local protection; 다른 값 reserved |
| 26–28 | 208 / 24 | Reserved | 반드시 0; 향후 변경은 version 검토 필요 |
| 29–30 | 232 / 16 | E2ECrc | AUTOSAR P05 CRC, 낮은 byte 먼저 저장 |
| 31 | 248 / 8 | E2ECounter | stream별 P05 Protect가 관리; 0…255 → 0 순환 |

Angle의 유효 raw는 −32767…32767, reserved invalid는 `00 80`이다.
Validity=1이면 reserved angle을 거부한다. Validity=0이면 Angle=`00 80`을 사용하고
valid snapshot/last-valid RX를 갱신하지 않는다. 이때 나머지 metadata는 진단용이며
받았다는 이유로 actuator availability를 valid로 바꾸지 않는다.
DBC의 Angle min/max는 **wire 표현 범위**이고 실제 command 허용 한계가 아니다.
Invalid sentinel은 DBC min/max 밖에 있어 별도 처리해야 하며 field decoder는 계속 거부한다.

LocalState는 sender의 상태 표시다. Receiver 자신의 상태를 이 값으로 덮어쓰지 않는다.
정상 경로의 Command는 NORMAL/DEGRADED + Origin=1을 사용한다. INIT Command는
수용하지 않는다. FAIL_SAFE + Origin=2의 보호 command 허용 범위/동작은 M2/M4에서
별도 정의하기 전까지 actuator command로 수용하지 않는다.
Actual은 유효 sample과 actuator health/state를 함께 해석한다. Validity=1만으로
NORMAL/주행 가능을 뜻하지 않는다. Origin=0은 INIT Actual에서만 허용하고
CausalSequence=0은 placeholder로 무시한다. Origin=1/2에서 causal 번호 0은 유효한 첫 번호다.
Origin=2의 Actual은 보호 동작에 따른 sample이며 마지막 수용 command는 인과관계 기록용이다.
Command/Actual의 허용 mode와 물리 한계는 codec의 숫자 복원 이후 별도 검사한다.

SchemaVersion과 Epoch는 다르다. Version은 bytes 해석 방법, Epoch는 이번 실행을 구분한다.
Producer는 bus/ID/송신 책임으로 대응한다. CAN ID나 CRC가 송신자 인증을 제공하지 않는다.

## 4. 손상, 중복, 오래된 입력을 따로 검사한다

### AUTOSAR E2E Profile 5

기준 판은 **AUTOSAR R25-11**이며 [FO Protocol §6.8](https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_E2EProtocol.pdf)과
[CP E2E Library §8.2.5/8.3.5](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_SWS_E2ELibrary.pdf)을 따른다.
직접 작성한 C++17 Protect/Check와 초기화 구현이다. C ABI/vendor BSW/ARXML 설정을 가져온 것은 아니다.
Profile-independent E2E State Machine과 application socket/queue/coordinator 통합은 미구현이다.
로컬 application 수신부의 적용 범위는 [ADR-0008](../adr/ADR-0008-steering-receiver.md)에 있다.

| 설정 | Command | Actual |
| --- | --- | --- |
| Data ID | 0x1001 | 0x1002 |
| DataLength (bits) | 256 | 256 |
| Offset (bits) | 232 | 232 |
| MaxDeltaCounter | 10 | 10 |

Data ID는 프로젝트에서 할당한 보호 대상 identity다. CAN ID와 별개이며 payload에 보내지 않는다.
DBC의 E2EProfile/E2EDataID/E2EOffsetBits/E2EMaxDeltaCounter는 프로젝트 정의 attribute다.
표준 ARXML/COM 설정의 대체물이 아니며 DBC parser가 Protect/Check를 자동 생성하지 않는다.

CRC는 16-bit, polynomial=0x1021, init=0xFFFF, refin/refout=false, xorout=0이다.
CRC 두 byte만 제외한 모든 payload와 implicit Data ID를 다음 순서로 계산한다.

```text
payload[0] … payload[28] → payload[31] → Data ID low byte → Data ID high byte
```

Command의 마지막 Data ID bytes는 `01 10`, Actual은 `02 10`이다.
기존 자체 CRC의 CAN ID/length prefix를 제거했다. Header는 CRC byte 29–30 LE와 Counter byte 31이다.
ID/length/FD flags는 별도 검사하고 message ID에 대응하는 Data ID를 선택한다.
같은 payload를 다른 message 종류로 옮기면 서로 다른 Data ID로 CRC mismatch가 난다.
CRC는 손상 검사이며 source-age 검사나 송신자 인증을 대신하지 않는다.

Protect의 첫 Counter는 0이고 성공한 호출마다 증가하며 255 다음은 0이다.
Command/Actual state는 별도로 유지하고 message마다 재초기화하지 않는다.
수신 Check는 Counter=255, Status=ERROR로 시작한다.
CRC 정상인 modulo-256 Counter 차이가 0이면 REPEATED, 1이면 OK,
2…10이면 OKSOMELOST, 그 밖이면 WRONGSEQUENCE다. 첫 0…9는 OK 또는 OKSOMELOST다.
CRC 정상인 WRONGSEQUENCE에서도 E2E counter를 수신 값으로 갱신해 재동기화한다.
CRC 오류와 새 데이터 없음(NONEWDATA)에서는 counter를 보존한다.
잘못된 buffer/config/envelope의 API return도 status와 함께 확인해야 한다.

이 E2E state는 application의 last-accepted Sequence/source cursor/snapshot/last-valid RX와 다르다.
E2E OK만으로 actuator command를 수용하거나 FAIL_SAFE에서 자동 복귀하지 않는다.
MaxDeltaCounter=10은 기존 rate에 맞춘 실험 후보이며 측정으로 확정한 값은 아니다.

### Local session / sequence / freshness 후보

- 첫 실험은 동일 Linux kernel의 `CLOCK_MONOTONIC`과 wall-time 모드만 지원한다.
  서로 다른 time namespace나 Host–Target clock 값을 직접 비교하지 않는다.
  Simulation-clock 모드는 별도 run 설정과 검토가 필요하다(TBD-04).
- Coordinator가 INIT에서 각 participant에 Epoch, clock mode, monitoring enable 시각을
  신뢰된 설정으로 전달하고 ready를 확인한다. RX frame에서 Epoch를 자동 학습하지 않는다.
  Epoch는 저장된 카운터로 실행마다 증가시키고 재사용/overflow 시 시작을 거부하는 후보다.
  실제 coordinator/handshake는 미구현이다. 로컬 수신부는 신뢰된 호출자의
  `start_session(epoch, monitoring_enable_ns)`를 사용하며 같은 인스턴스에서 Epoch 재사용/감소를 거부한다.
- Stream마다 Sequence는 0부터 새 발행마다 증가한다. 첫 수용은 startup window 내 번호
  0…9 중 하나를 허용한다(초기 packet loss 허용). 이후 `1 <= new − last <= 10`이면 진행,
  동일 번호는 duplicate, 감소/더 큰 jump는 reject한다. 계산은 unsigned wrap에 의존하지 않는다.
- 32-bit trace Sequence는 8-bit E2E Counter와 별개다. E2E Counter wrap은 정상이다.
  같은 Epoch에서 trace Sequence wrap을 허용하지 않는다. 최대값에 도달하기 전에 발행을 중단하고
  새 Epoch + explicit INIT를 요구한다. `0xFFFFFFFF → 0`은 reject 시험 대상이다.
- SourceTimeNs는 monitoring enable 이후이고 now 이하이며, 수용 후에는 엄격히 증가해야 한다.
  `now − source_time <= 30 ms`를 freshness 후보로 둔다. 10 ms 주기의 세 주기 분량을
  초안 budget으로 둔 것이며 부하/queue 측정 근거는 아직 없다. 변경 시 시험 기준도 갱신한다.
- Command의 SourceTimeNs는 Zone allocation 생성 시각, Actual은 모델 state sample 시각이다.
  Cached Actual의 재송신은 새 sample이 아니므로 timestamp/sequence를 새로 만들지 않는다.
  Zone은 별도로 Central last-valid age를 감시하며 allocation 생성으로 상위 유효 기간을 연장하지 않는다.
- CausalSequence는 같은 run Epoch의 원천 identity와 연결한다. Upstream sensor/trajectory,
  clock-domain 이름, 원천 전체 identity는 logger/side-channel에 보존한다. Wire tuple과 log의
  대응 구현 및 Host bridge 보존 검증은 M4/M5 이후에 남는다. 다른 epoch input을 참조하지 않는다.

### Receiver / timeout 후보

수신 순서는 frame ID/FD/길이 → P05 CRC/Counter → schema/reserved/enums → Epoch/source age/trace Sequence
→ validity/angle/mode/물리 한계다. 모든 수용 조건을 통과할 때만 snapshot, sequence cursor,
source-time cursor, last-valid RX를 함께 갱신한다. 규격의 E2E counter 갱신과 이 application 수용 기록을 구분한다. Reject 이유와 raw RX time은 따로 기록한다.
Rejected/invalid/duplicate/다른 stream의 frame은 이 stream의 valid age를 갱신하지 않는다.

Application queue capacity는 stream당 8개 후보, overflow는 기록하고 continuity fault로 처리한다.
처리 iteration은 최대 8개를 검사하고 마지막 valid sample만 snapshot으로 남긴다.
Socket buffer 크기/overflow 관측과 실제 dispatch budget은 구현 전에 TBD-01/04에서 해소한다.
Kernel queue까지 정확히 8개로 제한됐다고 주장하지 않는다. Queue가 바빠도 timeout monitor를
건너뛰지 않으며 unbounded drain을 넣지 않는다.

Local timeout/acquisition threshold는 80 ms 후보, monitor period 10 ms와
dispatch/execution/jitter margin 10 ms를 배정한다: `80 + 10 + 10 <= 100 ms`.
Valid age가 80 ms 이상이면 loss를 검출한다. 첫 valid RX가 없으면 monitoring enable이 기점이다.
마지막 valid RX 이후 100 ms 내 **실제 검출 완료** 여부는 별도 실행으로 측정해야 한다.
Timeout 이후 late frame으로 자동 복귀하지 않고 explicit INIT gate를 요구한다.
Physical protection output과 실제 actuator response는 M2/M4 범위다.

이 로컬 수용/시간/timeout 정책은 [SteeringReceiver](../../interfaces/common/steering_receiver.hpp)에
구현했다. `receive`는 timeout을 먼저 검사하므로 deadline 이후 도착한 frame이 fault를 해제하지 않는다.
`poll`은 입력이 없는 cycle에도 호출해야 한다. `current_sample(now_ns)`는 last-valid RX age뿐 아니라
원천 source age도 검사한다. 진단용 `last_accepted()` 이력은 제어 입력으로 직접 사용하지 않는다.
Clock 감소도 fault로 유지하며 새로운 Epoch의 explicit INIT만 수신 상태를 재설정한다.
Actual의 유효 sample은 sender health/주행 가능 판정이 아니다. Actual invalid 시 Plant Adapter의
apply/tick gate와 actuator별 availability 정책은 상위 통합에서 별도로 적용해야 한다.

## 5. 구현 전에 기대 bytes를 만든다

모든 예시는 version=2, validity=1, epoch=1, state=NORMAL, origin=normal path,
reserved=0이다. Timestamp는 산술 검토용 고정값이며 현재 wall clock의 fresh frame이 아니다.

| Vector | ID | Angle rad / raw | Sequence | SourceTimeNs | CausalSequence | E2E Counter | CRC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CMD-POS | 0x180 | +0.2 / 2000 | 0 | 1000000000 | 7 | 0 | 0x26EB |
| ACT-POS | 0x280 | +0.15 / 1500 | 0 | 1010000000 | 0 | 0 | 0x2D52 |
| CMD-NEG | 0x180 | −0.2 / −2000 | 1 | 1020000000 | 8 | 1 | 0xBA82 |

32-byte payloads (전송 byte 순서):

```text
CMD-POS:
D0 07 02 01 00 00 00 00 01 00 00 00 00 CA 9A 3B
00 00 00 00 07 00 00 00 01 01 00 00 00 EB 26 00

ACT-POS:
DC 05 02 01 00 00 00 00 01 00 00 00 80 60 33 3C
00 00 00 00 00 00 00 00 01 01 00 00 00 52 2D 00

CMD-NEG:
30 F8 02 01 01 00 00 00 01 00 00 00 00 F7 CB 3C
00 00 00 00 08 00 00 00 01 01 00 00 00 82 BA 01
```

기존 codec의 출력을 기대값으로 복사하지 않고, 정수 산술·explicit packing과
Python standard library `binascii.crc_hqx(data, 0xffff)`로 구한 설계 vector다.
공식 AUTOSAR 예제의 CRC=0xCA1C/0x9128도 C++/Python에서 확인했다. API의 근거는
[Python binascii 문서](https://docs.python.org/3/library/binascii.html#binascii.crc_hqx)를 참고한다.
DBC는 signal 정의이며 CRC 계산이나 receiver policy를 구현하지 않는다.
SourceTimeNs는 raw uint64로 다루고 float64 변환으로 ns 정밀도를 잃지 않도록 한다.

## 6. 다음 구현에서 확인할 것

- C++ frame codec과 기존 angle codec의 연결, 위 golden vectors 및
  CRC/ID/length/flags/version/reserved/sentinel의 표현 검사는 [Host에서 실행했다](../learning/m1_steering_frame_codec.md).
- P05 Counter의 duplicate/loss/jump/resync/wrap은 Host에서 시험했다. 이어서 로컬 Application receiver에서
  제어 가능한 clock으로 trace Sequence/old epoch/restart/wrap,
  stale/future/cached replay, timeout과 explicit INIT를 [시험했다](../learning/m1_steering_receiver.md).
- vCAN에서 독립 socket 사이 Command/Actual fixture를 송수신한다. Actual fixture를
  command echo나 actuator dynamics의 증거로 사용하지 않는다.
- Brake/Drive의 units/ranges/scaling과 공통 metadata를 검토해 six-frame으로 확장한다.
- Host DBC parser 검증은 실행했다. Target/CI 호환 검사, queue/handshake 구현, 물리 허용 범위 확정,
  measured timeout evidence는 미완료다. 기존 TC-COM-002/005·TC-SAFE-002 결과를 PASS로 바꾸지 않는다.

## 설계 확인 기록

2026-10-12 초안 작성 시 문서/DBC의 byte·bit 배치와 위 vector를 산술 검사했다.
이어서 cantools parser와 C++ wire codec을 구현·검증했고 P05/schema 2로 개정해 다시 시험했다. 자세한 범위는 [실행 기록](../learning/m1_steering_frame_codec.md)에 있다.
로컬 Receiver는 제어 가능한 시계로 Host에서 시험했다. Socket/queue/coordinator/vCAN application
및 실제 wall-time 검출 지연 시험은 **NOT RUN**이다.
기존 field codec의 검증 결과와 별개의 범위이며 학습자의 이해 확인도 **PENDING**이다.
이 제안은 Requirement의 shall이나 Reference v0.1을 변경하지 않고 TBD를 CLOSED로 처리하지 않는다.
