# M1 복습과 Brake wire·수신부 확장

Date: 2026-10-13. Status: **Host 구현·실행 완료 / 학습자 이해 확인 PENDING**.
관련 결정은 [ADR-0010](../adr/ADR-0010-brake-wire-codec.md), wire 계약은
[Brake frame 초안](../icd/brake_frame_draft.md)이다. M1 전체 acceptance와 차량 TC는 미완료다.

## 조향 복습

`0.2 rad / 0.0001 rad = raw 2000 = 0x07D0`이고 LE bytes는 `D0 07`이다.
16진수는 bytes를 읽기 쉽게 표시한 형식이며 CAN에 문자열을 보내는 것이 아니다.
Frame codec은 값과 metadata를 32 bytes에 담고 P05 Protect는 CRC/Counter를 붙인다.
수신부는 P05 뒤에 Epoch/source age/trace Sequence/mode/물리 범위를 검사한다.

오늘 기존 `angle 0.2`, `frame command 0.2`, `receiver`를 재실행했다.
Normal ACCEPTED, duplicate E2E_REJECTED, 새 Counter의 cached Sequence 거부,
source stale 거부, source-age 30 ms 초과 시 current sample 소멸, invalid와 다른 Epoch 거부,
last-valid RX +80 ms TIMEOUT, late frame으로 latch 해제 불가, 새 Epoch의 explicit INIT을 확인했다.
코드의 단순 decode, 상태 있는 수신 수용, 물리 actuator 응답은 별도 책임이다.

## 이번 설계와 코드 읽기

| 파일 | 책임 |
| --- | --- |
| [brake_pressure_codec.cpp](../../interfaces/brake/brake_pressure_codec.cpp) | Pa ↔ unsigned 2 bytes, 반올림/표현 범위/invalid |
| [brake_frame_codec.cpp](../../interfaces/brake/brake_frame_codec.cpp) | Brake envelope·Data ID·압력과 Validity 연결·stream별 P05 |
| [actuator_payload_codec.cpp](../../interfaces/common/actuator_payload_codec.cpp) | 공통 schema 2 metadata 배치와 CRC protect/decode |
| [brake_receiver.cpp](../../interfaces/brake/brake_receiver.cpp) | 압력 command/actual의 application 수용과 explicit session |
| [actuator_receiver_state.cpp](../../interfaces/common/actuator_receiver_state.cpp) | Steering/Brake 공통 clock/Epoch/source age/Sequence/timeout 상태 |
| [brake_m1_draft.dbc](../../interfaces/dbc/brake_m1_draft.dbc) | 같은 wire 정의를 parser가 읽는 형식 |
| [actuator_socketcan.cpp](../../interfaces/socketcan/actuator_socketcan.cpp) | Linux transport와 typed actuator frame 변환, 실제 envelope 보존 |
| [actuator_demo.cpp](../../tools/actuator_demo.cpp) | 기존 조향 네 명령 + brake-pressure/brake-frame/brake-receiver |
| [brake_codec_test.cpp](../../tests/unit/brake_codec_test.cpp) | 새 Brake 모듈과 공유 layout의 자동 시험 |
| [brake_receiver_test.cpp](../../tests/unit/brake_receiver_test.cpp) | Brake 수용/거부/범위/clock/timeout 경계와 상태 독립성 |
| [check_socketcan.py](../../tests/integration/can/check_socketcan.py) | Steering 8 + Brake application 8 + Brake wire 2 case |

2,000,500 Pa는 raw 2001로 반올림되어 `D1 07`, 복원값 2,001,000 Pa가 된다.
0 Pa는 `00 00`, Validity=1이다. 값 없음은 `FF FF`, Validity=0이다.
Raw unsigned 최대값 하나를 invalid로 예약했으므로 유효 wire 최대는 65,534,000 Pa다.
이는 실제 압력 limit가 아니다. 해상도 선택 이유와 error budget은 wire 초안에 기록했다.

## 재현 명령

기존 Host GCC 11.4.0, CMake 4.3.2, C++17, GoogleTest 1.11.0, Python 3.10.12와
cantools 40.7.1 환경을 사용했다. 새 dependency를 설치하지 않았다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=OFF
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle --output-on-failure
./build/m1-angle/actuator_demo angle 0.2
./build/m1-angle/actuator_demo frame command 0.2
./build/m1-angle/actuator_demo receiver
./build/m1-angle/actuator_demo brake-pressure 2000500
./build/m1-angle/actuator_demo brake-frame command 2000000
./build/m1-angle/actuator_demo brake-frame actual 1500000
./build/m1-angle/actuator_demo brake-frame actual invalid
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py --demo build/m1-angle/actuator_demo
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py
```

Demo의 Actual 1,500,000 Pa는 Command 2,000,000 Pa와 별도인 고정 sample이다.
실제 압력 응답 모델을 실행하지 않는다. 최초 Brake vCAN의 `wire` case 2개는 wire decode와
P05만 검사한다. 아래 application 확장과 구분하며 `WIRE_VALID`를 demand 수용으로 해석하지 않는다.
Session Epoch/start는 신뢰한 stdio handshake로 전달하며 물리 네트워크의 시계 동기화를 시험하지 않는다.

```sh
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 2
ctest --test-dir build/m1-angle-sanitized --output-on-failure
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py --demo build/m1-angle-sanitized/actuator_demo
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --build-dir build/m1-angle-sanitized
```

## Wire codec 단계의 결과와 검증 범위

- Normal/ASan·UBSan 각각 **64 unit test PASS**. 기존 48개를 유지하고 Brake/shared layout 14개와
  adapter 2개를 추가했다. 모든 65,535개 유효 pressure raw의 round trip을 검사했다.
- NaN/Inf/음수/범위 초과, 반올림, 0과 invalid 구분, independent golden vectors,
  uint64/uint32 경계, 전 payload byte 손상, CRC가 정상인 잘못된 field/envelope를 검사했다.
- P05 config/Data ID 분리, stream Counter 독립성, wrap, repeat/loss/corruption/NONEWDATA와
  encode 실패 시 Counter 미소비를 검사했다. Common 추출 후 Steering golden bytes와 수신 시험은 유지됐다.
- DBC 네 frame의 field·단위·scale·enum·P05 속성, 독립 CRC/golden 7개,
  C++ demo payload 9개와 uint64 source time 정밀도 교차 검증 **PASS**.
- Brake demo의 잘못된 숫자·범위·명령 형태 11개는 exit 1로 거부했고 도움말의 여섯 명령을 확인했다.
- vCAN은 normal/sanitizer 각각 **10 case PASS**. Steering 8개는 기존 수용/fault/timeout,
  Brake 2개는 각 stream에 정상/duplicate/CRC 손상/zero/unavailable/64-byte/정상/16-byte 8개 frame이다.
  Brake 결과는 WIRE_VALID 3개, WIRE_UNAVAILABLE 1개, rejected 4개였다.
- clang-tidy 14의 clang-analyzer/bugprone과 cppcheck 2.7의 warning/performance/portability를 적용했다.
  변경한 C++ 소스의 최종 진단은 없었다. clang-tidy의 system/header suppression을 포함한 전체 무경고 주장은 아니다.

실행 trace는 각 build의 `socketcan-results/`에 있다. DBC/codec/vector 통과는 SYS-COM-001/002와
IF-CAN-BRAKE의 부분 증거다. Brake timeout(SYS-COM-003), freshness/replay 수용 정책,
TC-CTRL-001의 실제 actuator 응답은 아직 검증하지 않았다. 아래 수신부 추가에서 timeout/freshness의
부분 검증을 이어갔다. Local vCAN은 CAN FD 전기적/bit timing 검증이 아니다.

최종 Steering timeout 관측 범위는 normal **80.013–81.009 ms**, ASan·UBSan **80.077–81.031 ms**였다.
지정한 local fixture의 결과이며 임의 부하에서의 검출 시간이나 차량 반응 보장이 아니다.

예제/adapter/검사기의 이름과 경로를 두 actuator에 맞춰 변경했다. 새 standalone demo나
Brake 전용 통합 runner를 복제하지 않았다. `BUILD_TESTING=OFF`에서도 라이브러리와 예제만 build한다.

## Application 수신부 추가

같은 날짜의 후속 작업으로 [ADR-0012](../adr/ADR-0012-brake-receiver.md)를 구현했다.
수용 순서는 clock/timeout → CAN envelope/P05 → payload → Epoch/source age/Sequence
→ validity/mode/압력 범위다. 공통 시간·session 상태는 `ActuatorReceiverState`에 추출하고
Steering의 기존 API와 19개 receiver 시험을 유지했다. Pressure codec/한계는 Brake 모듈에 있다.

Fixture 한계는 **0–2,000,000 Pa**이며 source age <=30 ms, valid RX timeout >=80 ms다.
Wire 최대값을 차량 한계로 쓰지 않는다. CRC가 맞아도 3,000,000 Pa는 거부하고 유효한
0 Pa는 수용한다. Unavailable/다른 Epoch/잘못된 mode/stale/replay는 valid RX를 갱신하지 않는다.
Command는 normal path + NORMAL/DEGRADED만 수용하며 보호 압력 정책은 M2 작업이다.
Actual의 유효 sample은 sender health나 정상 주행 가능 판정과 구분한다.

위 normal/sanitizer build 및 DBC 명령을 그대로 사용한다. 새 예제는 다음과 같다.

```sh
./build/m1-angle/actuator_demo brake-receiver
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --build-dir build/m1-angle-sanitized
```

예제는 ACCEPTED → repeat 거부 → cached Sequence 거부 → 압력 한계 초과 거부 →
0 Pa 수용 → unavailable 거부 → source-age 만료 → TIMEOUT → late frame 거부 →
새 Epoch의 explicit INIT 순서를 수동 시계로 보여준다. 실제 압력을 발생시키는 예제가 아니다.

- Normal/ASan·UBSan 각각 **80 unit test PASS**: 기존 64개 + Brake receiver 16개.
  CRC-valid malformed payload, 압력 한계, 0/unavailable, mode 조합, Epoch/time/Sequence 경계,
  invalid traffic의 age 미갱신, clock rollback, timeout latch/restart 및 stream 독립성을 검사했다.
- Normal/ASan·UBSan 각각 **vCAN 18 case PASS**: Steering 8 + Brake application 8 + Brake wire 2.
  Brake normal/fault/silent/flood는 Command/Actual 각각 실행한다. Fault case는 정상 압력/zero와
  repeat/CRC/stale/잘못된 envelope/cached Sequence/압력 초과/unavailable/mode/Epoch/late frame을 포함한다.
- DBC golden/codec 교차 검증은 PASS이며 Steering/Brake wire layout을 변경하지 않았다.
- 최종 application timeout 관측 범위는 전체 stream에서 normal **80.060–81.065 ms**,
  ASan·UBSan **80.004–81.006 ms**였다. Brake만 보면 normal **80.121–81.059 ms**,
  ASan·UBSan **80.153–81.006 ms**다. 마지막 valid RX 또는 trusted monitoring enable 기준이며,
  지정한 local fixture의 결과다. Sanitizer 측정은 대표 성능으로 취급하지 않는다.
- clang-tidy 14의 clang-analyzer/bugprone을 변경 source 7개에 적용하고 cppcheck 2.7을
  runtime/demo/participant 6개에 적용했다. 최종 user-source 진단은 없었다.
  clang-tidy의 system/header suppression 및 GoogleTest macro의 기존 NOLINT를 포함한 전체 무경고 주장은 아니다.
- Fresh `BUILD_TESTING=OFF` build에서 receiver/common-state library와 demo만 생성되며,
  unit/participant 없이 `brake-receiver`가 실행되는 것을 확인했다.

```sh
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' interfaces/common/actuator_receiver_state.cpp interfaces/brake/brake_receiver.cpp interfaces/steering/steering_receiver.cpp tools/actuator_demo.cpp tests/integration/can/socketcan_tx.cpp tests/integration/can/socketcan_rx.cpp tests/unit/brake_receiver_test.cpp
cppcheck --enable=warning,performance,portability --error-exitcode=1 --std=c++17 --suppress=missingIncludeSystem -I interfaces/common -I interfaces/steering -I interfaces/brake -I interfaces/socketcan interfaces/common/actuator_receiver_state.cpp interfaces/brake/brake_receiver.cpp interfaces/steering/steering_receiver.cpp tools/actuator_demo.cpp tests/integration/can/socketcan_tx.cpp tests/integration/can/socketcan_rx.cpp
```

전체 system TC, actuator 물리 반응, 실제 CAN bus, 임의 부하 timing과 영속 Epoch coordinator는
검증 완료가 아니다. 로그는 각 build의 `socketcan-results/`에 있다.

## 다음 작은 작업

Brake application receiver의 trusted Epoch/session, source age, trace Sequence, 물리 압력 범위,
mode/invalid 거부와 last-valid/timeout latch를 구현·시험했다. 다음은
[회생을 포함한 Drive Command/Actual](../icd/regenerative_braking_design.md)의 wire 정의다.
Pressure dynamics, local protection 압력/hold/ramp와 실제 모델 Actual 생성은 M2다.

이해 확인: 0 Pa와 invalid가 다른 이유, factor를 작게 할 때 범위/해상도가 바뀌는 이유,
P05 OK와 Brake 수용을 구분하는 이유를 자신의 말로 설명하고 위 예제를 직접 재현한다.
학습자의 설명·재현·diff review는 PENDING이며 자동 검사 결과가 이를 대신하지 않는다.
