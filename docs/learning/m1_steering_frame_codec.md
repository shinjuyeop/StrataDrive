# M1 세 번째 실행: DBC와 전체 Steering payload codec

Status: **2026-10-12 Host DBC parser·frame codec/P05 구현/시험 완료 / 학습자 review PENDING**.
[Application 수신부의 수용/freshness/trace Sequence/timeout](m1_steering_receiver.md)은 후속 Host 실험에서 시험했다.
vCAN application/queue/coordinator, Brake/Drive, actuator model과 M1 acceptance는 미완료다.

현재 source는 [AUTOSAR E2E Profile 5 후속 작업](m1_autosar_e2e_profile5.md)을 적용한 schema 2다.
최초 자체 CRC 구현은 이 후속 작업으로 대체했다.

## 직접 실행

Repository root에서 기존 Host C++17/GCC/CMake/GoogleTest를 사용한다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle --output-on-failure
./build/m1-angle/actuator_demo frame command 0.2
./build/m1-angle/actuator_demo frame actual 0.15
./build/m1-angle/actuator_demo frame actual invalid
```

첫 예제의 결과는 ID=`0x180`, CRC=`0x26EB`, 복원=`0.2 rad`이다.

```text
Payload: D0 07 02 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 EB 26 00
```

Actual 예제는 독립 fixture `0.15 rad`, ID=`0x280`, CRC=`0x2D52`이다.
Command에서 Actual을 만들어낸 결과가 아니다. `actual invalid`는 각도 없음,
Validity=0, reserved angle=`00 80`을 출력한다. 실제 조향각 **0 rad**와 구분한다.
CLI의 epoch/timestamp/sequence는 고정 fixture이며 runtime의 fresh frame이 아니다.
이 실행에는 socket 송수신이나 actuator dynamics가 없다.

## DBC parser와 C++ 결과 교차 확인

DBC 검증 도구로 **cantools 40.7.1**을 선택했다. Python 3.10.12/uv 0.9.15를 사용했고,
모든 transitive version은 [requirements](../../tools/requirements-dbc.txt)에 고정했다.
선정/라이선스 근거는 [ADR-0006](../adr/ADR-0006-steering-frame-codec.md)에 있다.
Python package는 Git에서 제외된 `build/m1-dbc-venv`에만 설치했다.
C++ runtime에는 이 package가 필요 없으며 CMake는 설치/다운로드를 수행하지 않는다.

격리 환경이 없는 경우 아래의 **명시적 설치 명령**을 먼저 실행한다.

```sh
uv venv --python /usr/bin/python3 build/m1-dbc-venv
uv pip install --python build/m1-dbc-venv/bin/python -r tools/requirements-dbc.txt
```

```sh
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py --demo build/m1-angle/actuator_demo
```

첫 명령은 [DBC](../../interfaces/dbc/steering_m1_draft.dbc)의 문법과 strict layout,
ID/FD/길이/주기/송수신자/형식/배치, 독립 golden vectors와 CRC를 검사한다.
두 번째는 C++ demo의 Command 양·음수, Actual 유효·invalid payload를 DBC와 비교한다.
DBC factor/endianness 검증과 raw 정수 표현을 비교한 것이며 각 도구의 모든 반올림
정책이 같다고 주장하지 않는다. Codec의 반올림은 기존 `std::lround` 계약을 따른다.

`SourceTimeNs`는 uint64 raw 정수로 검사한다. 2^53+1과 UINT64_MAX도 손실 없이 복원했다.
`invalid` fixture의 sentinel은 DBC physical min/max 밖이므로 그 fixture만 strict range
검사를 끄고 raw encode한다. DBC의 유효 angle 범위를 넓히지 않으며 C++ codec은
Validity와 sentinel의 일관성을 별도로 검사한다.
또한 cantools는 DBC의 `[0|0]`을 min/max 미지정으로 해석한다. Reserved=0 규칙은
DBC range 검사에 맡기지 않고 C++ decoder에서 명시적으로 검사한다.

## 코드 읽기

1. [SteeringMessage / SteeringFrame](../../interfaces/steering/steering_frame_codec.hpp)을 본다.
   Message는 물리량과 metadata, Frame은 CAN ID/종류/flags/길이/payload다.
2. [encode_steering_frame](../../interfaces/steering/steering_frame_codec.cpp)은 기존 angle
   codec으로 byte 0–1을 만들고, 나머지 field를 DBC 위치에 little-endian으로 기록한다.
   호출자가 stream별로 유지한 SteeringTxState를 받아 P05 Protect를 호출한다.
   Reserved byte 26–28은 0이고 CRC byte 29–30/Counter byte 31은 P05가 기록한다.
3. `decode_steering_frame`은 envelope, CRC, version/reserved/enums/epoch, angle 표현을
   확인한 뒤 metadata를 복원한다. FD의 BRS/ESI는 거부하고 FDF marker는 허용한다.
4. `std::optional<SteeringMessage>` 없음은 잘못된 frame이다. Message는 있지만
   `angle_rad`가 없으면 invalid/unavailable 진단 frame이다. 호출자는 두 경우를 구분해야 한다.

Wire decode는 **상태가 없는 표현 검사**다. 별도 `check_steering_e2e`가 Counter의
반복/누락/순서 오류를 검사한다. Application의 source age/trace Sequence 진행과 INIT/FAIL_SAFE
command mode, Origin/CausalSequence 관계, 물리 조향 한계, actuator availability는 아직 판정하지 않는다.
숫자/enum 복원이 성공해도 command 수용이나 last-valid RX 갱신의 근거가 아니다.
실제 adapter는 수신된 FD/Classical 종류·CAN ID flags·payload length·FD flags를 보존해
SteeringFrame을 채워야 한다. 실제 socket ABI를 이 struct와 동일하다고 가정하지 않는다.

## 검증 기록

2026-10-12 Codex가 Linux 6.8.0-138-generic x86_64에서 실행했다.
GCC 11.4.0, CMake 4.3.2, C++17, GoogleTest 1.11.0, Debug build다.

- 최초 자체 CRC 구현은 field 6 + frame 8의 **14개 PASS**였고, 현재 P05 개정은
  field 6 + frame 10 + P05 9의 **25개 PASS**였다. 후속 수신부 추가 뒤 전체는 44개다.
  독립 golden vectors, invalid vs zero, NaN/Inf/범위 밖/잘못된 enum 거부,
  FD/ID/길이/flags, 모든 payload byte의 single-bit 손상, CRC를 재계산한 비정상 field,
  정확한 uint64 time/uint32 경계, CRC의 implicit Data ID/Counter coverage와 CRC field 제외를 확인했다.
- 별도 ASan/UBSan build: P05 개정 **25개 PASS**.
- cantools strict parser, 3개 golden vectors encode/decode, 독립 Python CRC,
  C++ demo 4개 payload 교차 검증 PASS.
- CLI: `nan`, `inf`, `4.0`, `0.2junk`, 잘못된 message 종류는 exit 1.
- clang-tidy 14.0.0: P05/frame codec/demo/test에 적용한 검사에서 소스 진단 없음.
  Non-user header/NOLINT 진단은 tool의 기본 filter에 따라 제외됐다.
- cppcheck 2.7: P05/frame codec/demo 진단 없음. GoogleTest의 TEST macro를 포함한 test 소스는
  이 tool 설정에서 syntaxError가 발생해 cppcheck 완료 범위에서 제외했다.
  Test 소스는 compiler/clang-tidy 및 실제 GoogleTest/ASan/UBSan 실행으로 확인했다.

검사 재현 명령:

```sh
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 2
ctest --test-dir build/m1-angle-sanitized --output-on-failure
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' interfaces/common/e2e_profile5.cpp interfaces/steering/steering_frame_codec.cpp tools/actuator_demo.cpp tests/unit/e2e_profile5_test.cpp tests/unit/steering_frame_codec_test.cpp
cppcheck --enable=warning,performance,portability --error-exitcode=1 --std=c++17 --suppress=missingIncludeSystem -I interfaces/common -I interfaces/steering -I interfaces/brake interfaces/common/e2e_profile5.cpp interfaces/steering/steering_frame_codec.cpp tools/actuator_demo.cpp
```

IF-CAN-STEERING의 wire 표현 일부를 검사했다. SYS-COM-002 / TC-COM-002/005 /
TC-SAFE-002의 전체 acceptance나 100 ms loss 검출 결과를 PASS/VERIFIED로 바꾸지 않는다.
이 codec 실행 당시 Target/vCAN application/차량 runtime TC는 NOT RUN이었다. 학습자 review는 PENDING이다.
제어 가능한 시계로 실행한 로컬 수신부 결과는 [별도 기록](m1_steering_receiver.md)에 있다.
이후 vCAN application 송수신/local timeout을 수행한 결과는 [SocketCAN 기록](m1_steering_socketcan.md)에 있다.

## 다음 작은 작업

[로컬 수신부](m1_steering_receiver.md)의 freshness/duplicate/order/epoch/restart/wrap/timeout을
제어 가능한 clock으로 시험했다. 이어서 실제 clock과 bounded dispatch/trusted fixture handshake를
SocketCAN/vCAN에 연결해 시험했다. 영속 coordinator, queue overflow 주입, 실제 물리 한계 확정,
[Brake의 field/frame wire](m1_brake_codec.md)는 후속 작업에서 추가했다.
Brake 수신 수용, Drive field 설계와 six-frame 검증은 남아 있다.
