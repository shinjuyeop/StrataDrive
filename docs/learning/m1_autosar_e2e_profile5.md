# M1 네 번째 실행: AUTOSAR E2E Profile 5

Status: **2026-10-12 Host Protect/Check·Steering 연결 구현/시험 완료 / 학습자 review PENDING**.
기준 판은 AUTOSAR R25-11이고 결정은 [ADR-0007](../adr/ADR-0007-autosar-e2e-profile5.md)에 있다.
Application command 수용/freshness/timeout, E2E State Machine, vCAN application,
Brake/Drive 및 M1 acceptance는 미완료다.

## 직접 실행

Repository root에서 실행한다. 새 package 설치는 필요 없다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle --output-on-failure
./build/m1-angle/steering_frame_demo command 0.2
./build/m1-angle/steering_e2e_demo
build/m1-dbc-venv/bin/python tools/check_steering_dbc.py --demo build/m1-angle/steering_frame_demo
```

DBC 전용 격리 환경이 없으면 [기존 설치 방법](m1_steering_frame_codec.md)을 따른다.
첫 Command 결과는 SchemaVersion=2, Counter=0, CRC=0x26EB, 각도 0.2 rad다.

```text
Payload: D0 07 02 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 EB 26 00
```

`steering_e2e_demo`의 결과는 다음과 같다.

```text
정상 첫 frame Counter=0 -> OK
같은 frame 재수신 Counter=0 -> REPEATED
2개 누락 후 수신 Counter=3 -> OKSOMELOST
payload 손상 Counter=4 -> ERROR
손상 뒤 정상 frame Counter=5 -> OKSOMELOST
허용 차이 초과 Counter=16 -> WRONGSEQUENCE
E2E counter 재동기화 Counter=17 -> OK
새 데이터 없는 cycle -> NONEWDATA
Counter 순환 Counter=254 -> OK
Counter 순환 Counter=255 -> OK
Counter 순환 Counter=0 -> OK
```

고정 fixture이며 socket이나 actuator model 실행이 아니다. 같은 frame 반복, 수신하지 않은
frame의 누락, 보호 후 byte 손상 및 Counter 순환을 Host 메모리 안에서 확인한다.
WRONGSEQUENCE 뒤 E2E OK가 나온 것은 profile counter 재동기화이며, 차량의 정상 복귀가 아니다.

## 배치와 CRC를 먼저 읽는다

[DBC](../../interfaces/dbc/steering_m1_draft.dbc)의 조향각/metadata byte 0–25는 유지한다.
마지막 영역만 다음처럼 바뀌며 SchemaVersion=2다.

| Byte | 의미 |
| --- | --- |
| 26–28 | Reserved=0, 3 bytes |
| 29–30 | E2ECrc, 16-bit little-endian |
| 31 | E2ECounter, 8-bit |

P05의 Offset=232 bits, DataLength=256 bits다. Header는 앞부분에만 놓을 필요가 없다.
Data ID는 Command=0x1001, Actual=0x1002로 설정하고 payload에는 보내지 않는다.
계산 순서는 다음과 같다.

```text
payload[0..28] → payload[31] → Data ID low byte → Data ID high byte → CRC
```

CRC 두 byte는 제외하고 Counter와 모든 user data를 포함한다.
CAN ID/length는 P05 CRC에 prefix로 넣지 않는다. CAN envelope는 별도로 검사한다.
세부 규칙의 공식 근거는 [AUTOSAR Protocol §6.8](https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_E2EProtocol.pdf)이다.

## 송신 state와 수신 state를 나눠 읽는다

1. [e2e_profile5.hpp](../../interfaces/common/e2e_profile5.hpp)의 config/state/return/status를 읽는다.
   Config의 길이와 Offset은 bit 단위, 함수의 buffer length는 byte 단위다.
2. [p05_protect](../../interfaces/common/e2e_profile5.cpp)는 Counter 기록 → CRC 계산/기록 →
   다음 Counter 증가를 담당한다. 첫 값은 0이고 255 뒤에 0으로 순환한다.
3. `p05_check`는 CRC를 확인한 뒤 이전 Counter와 modulo-256 차이를 계산한다.
   초기 수신 Counter는 255다. 첫 Counter=0은 delta=1이므로 OK다.
4. [SteeringTxState/SteeringRxState](../../interfaces/common/steering_frame_codec.hpp)는
   Command/Actual별로 별도 유지한다. 새로 초기화할 때마다 Counter가 시작되므로
   매 송신/수신 호출에서 state를 다시 만들면 안 된다.
5. `encode_steering_frame(message, tx)`는 angle/metadata를 포장한 뒤 Protect를 호출한다.
   메시지 표현이나 stream 종류가 잘못되면 Counter를 소모하지 않는다.
6. `decode_steering_frame(frame)`은 stateless CRC/field 복원이다.
   `check_steering_e2e(&frame, rx)`가 별도 stateful Counter 검사다.
   `check_steering_e2e(nullptr, rx)`는 새 frame 없는 cycle을 나타낸다.

| 상태 | 현재 설정에서의 의미 |
| --- | --- |
| OK | Counter가 1 증가 |
| OKSOMELOST | Counter 차이가 2…10; 일부 누락 |
| REPEATED | Counter 차이가 0 |
| WRONGSEQUENCE | Counter 차이가 10을 초과 |
| ERROR | CRC/Data ID 불일치 |
| NONEWDATA | 이번 cycle에 새 buffer 없음 |

함수 호출의 `P05Return`과 수신 상태인 `P05Status`는 다르다.
잘못된 buffer/config/stream은 InputNull/InputWrong을 반환하며 이전 status를 보존할 수 있다.
`p05_is_ok(result, rx.check.status)`는 둘 다 확인한다.
입력 오류 때 이전 OK status만 읽고 이번 frame을 수용하면 안 된다.

규격에 따라 WRONGSEQUENCE에서도 E2E Counter는 수신 번호로 갱신한다.
CRC 오류와 NONEWDATA는 Counter를 갱신하지 않는다.
이 raw E2E state를 actuator snapshot이나 last-valid RX로 사용하지 않는다.
E2E OK여도 Validity=0, old Epoch, stale time, 물리 한계/상태 위반이면 command로 수용할 수 없다.
Cached sample을 다시 포장하면 E2E Counter가 증가할 수 있어도 sample 자체가 새로 생긴 것은 아니다.
SourceTimeNs/trace Sequence를 보존해 source age를 따로 검사해야 한다.
Counter 순환과 32-bit trace Sequence의 wrap/restart 정책도 구분한다.
이 application 수용 검사는 다음 receiver 작업이다.

## 검증 기록

2026-10-12 Linux 6.8.0-138-generic x86_64, GCC 11.4.0, CMake 4.3.2,
C++17, GoogleTest 1.11.0에서 Codex가 실행했다.

- Normal GoogleTest: angle 6 + frame 10 + P05 9 = **25개 PASS**.
- ASan/UBSan build: 같은 **25개 PASS**.
- 공식 PRS §6.8.5 예제 두 개: DataID=0x1234, offset 0/64 bits의 CRC 0xCA1C/0x9128과 일치.
- P05: init, 0…255→0, 첫 수신 경계, duplicate/loss/jump/backward/resync,
  missing/CRC/wrong Data ID, header 앞뒤 모든 bit 손상, 잘못된 config/length/null,
  규격의 최소 3-byte/최대 4096-byte buffer를 검사했다.
- Frame: schema 1 거부, P05/Data ID/Counter, stream 분리, 실패한 송신의 Counter 보존,
  기존 invalid/zero/uint64/envelope/metadata 검사 PASS.
- cantools 40.7.1 strict DBC/parser, 12 signals와 profile 설정, 독립 binascii CRC,
  3 golden vectors와 C++ demo 4 payload 교차 검증 PASS.
- clang-tidy 14.0.0: 변경 codec/demo/test 6개 source의 적용 검사에서 소스 진단 없음.
  Non-user header/NOLINT는 기본 filter로 제외됐다.
- cppcheck 2.7: 변경 production codec/demo 4개 source의 적용 검사에서 진단 없음.
  GoogleTest macro source는 기존 tool 제약 때문에 cppcheck 대상에서 제외했다.

```sh
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 2
ctest --test-dir build/m1-angle-sanitized --output-on-failure
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' interfaces/common/e2e_profile5.cpp interfaces/common/steering_frame_codec.cpp tools/steering_frame_demo.cpp tools/steering_e2e_demo.cpp tests/unit/e2e_profile5_test.cpp tests/unit/steering_frame_codec_test.cpp
cppcheck --enable=warning,performance,portability --error-exitcode=1 --std=c++17 --suppress=missingIncludeSystem -I interfaces/common interfaces/common/e2e_profile5.cpp interfaces/common/steering_frame_codec.cpp tools/steering_frame_demo.cpp tools/steering_e2e_demo.cpp
```

Profile 5 Protect/Check를 기준으로 직접 작성한 구현의 시험이다. Vendor BSW 도입은 아니다.
E2E State Machine, OS/RTE/COM/BSW 통합, Target/차량 runtime TC는 NOT RUN이다.
학습자 review는 PENDING이고 M1 acceptance나 100 ms loss 검출 완료로 처리하지 않는다.
