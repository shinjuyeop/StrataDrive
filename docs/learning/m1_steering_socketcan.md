# M1 Steering을 실제 SocketCAN/vCAN에 연결하기

Status: **2026-10-12 Host 구현·실행 완료 / 학습자 review·재현 PENDING**.
[수신부의 메모리 실험](m1_steering_receiver.md)에 실제 Linux socket과 시계를 연결했다.
[설계 결정](../adr/ADR-0009-steering-socketcan.md)은 transport와 검증 책임을 분리한다.

## 이번 연결의 흐름

```text
TX process: 조향 메시지 → angle/frame codec + P05 → SocketCAN send
                                                       ↓
                                                     vCAN
                                                       ↓
RX process: current_sample ← SteeringReceiver 검사 ← SocketCAN receive
```

송신부는 실제 CLOCK_MONOTONIC으로 SourceTimeNs를 만들고 P05 Counter를 발행마다 진행한다.
수신부는 실제 수신 시각으로 기존 envelope/E2E/Epoch/source age/Sequence/mode/range 규칙을 적용한다.
Command와 Actual은 별도 case로 실행한다. Command=0.2 rad, Actual=0.15 rad는 독립적인 시험 값이다.
아직 차량 모델이 움직여서 Actual을 만든 것은 아니다.

| 위치 | 담당 |
| --- | --- |
| [common/e2e_profile5.cpp](../../interfaces/common/e2e_profile5.cpp) | message와 독립인 P05 CRC/Counter |
| [steering/steering_frame_codec.cpp](../../interfaces/steering/steering_frame_codec.cpp) | 조향 32-byte payload와 E2E 연결 |
| [steering/steering_receiver.cpp](../../interfaces/steering/steering_receiver.cpp) | 수용 조건, last-valid 이력, source age/timeout |
| [socketcan/socketcan_endpoint.cpp](../../interfaces/socketcan/socketcan_endpoint.cpp) | Linux socket 생성/종료, FD send/receive, 누적 RX drop 관측 |
| [socketcan/actuator_socketcan.cpp](../../interfaces/socketcan/actuator_socketcan.cpp) | 64-byte transport와 32-byte 조향 표현 사이 변환 |
| [socketcan_tx.cpp](../../tests/integration/can/socketcan_tx.cpp) / [socketcan_rx.cpp](../../tests/integration/can/socketcan_rx.cpp) | 독립 송신/수신 실행 프로그램 |
| [check_socketcan.py](../../tests/integration/can/check_socketcan.py) | 임시 vCAN, trusted start handshake, fault 주입/결과 검사/cleanup |

SocketCAN의 payload length는 DLC가 아닌 byte 수다. ID flags와 FD/Classical 구분은 수신 입력의
일부이므로 codec에 전달할 때 보존한다. 16/64-byte 입력을 32-byte로 정규화하지 않는다.
ABI의 근거는 [Linux SocketCAN 문서](https://docs.kernel.org/networking/can.html)다.

## 직접 실행

현재 Host의 기존 C++17/CMake/GoogleTest를 사용하며 새 package 의존성을 추가하지 않는다.
Linux에서 아래 명령으로 build한 뒤 integration fixture를 실행한다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle --output-on-failure
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py
```

User/network namespace 안에 `sd_m1_app` vCAN을 만들고 CAN FD MTU=72로 설정한다.
기존 interface는 건드리지 않으며 이번 실행에서 만든 interface와 자식 process만 정리한다.
이 환경은 user/network namespace와 vCAN을 지원해야 한다. 실패하면 원인을 출력하고 종료한다.

Fixture가 RX/TX 양쪽의 ready를 기다린 뒤 RX의 `start_session(1, now)`를 완료하고 TX를 시작한다.
Epoch는 CLI 설정이며 수신 payload에서 학습하지 않는다. 시간은 같은 kernel/time namespace의
CLOCK_MONOTONIC이다. 영속 Epoch 발급/재시작 coordinator와 Host–Target 시계 동기화는 남아 있다.

개별 executable의 형식은 아래와 같다. 각각 stdin에서 `start` 한 줄을 받아야 발행/감시를 시작한다.
처음에는 위 Python runner로 시작 순서를 맞추는 편이 쉽다. `IFACE`는 이미 만든 FD-capable interface다.

```text
actuator_socketcan_tx IFACE cmd|actual EPOCH normal|faults|silent|flood
actuator_socketcan_rx IFACE cmd|actual EPOCH DURATION_MS
```

## 확인하는 8개 case

Command/Actual 각각 아래 네 case를 실행한다. 두 process의 stdout/stderr를 함께 읽어 로그 pipe가
수신부를 막지 않게 하며 각 case의 실행 제한은 5초, RX 관측 시간은 230 ms다.

| Case | 입력 | 기대 결과 |
| --- | --- | --- |
| normal | 10 ms 간격 정상 fixture 5개 후 중단 | 5개 수용, source age 만료, 마지막 valid RX 후 timeout |
| faults | 반복, CRC bit 손상, stale source, 새 정상 값, 길이 16/64, EFF, BRS, Classical, cached Sequence, timeout 뒤 정상 값 | 정상 2개만 수용; reject가 accepted 이력을 바꾸지 않음; late frame도 TIMEOUT |
| silent | 첫 frame부터 송신 없음 | trusted monitoring enable부터 acquisition timeout |
| flood | 정상 1개 후 같은 frame 32개씩 5 ms마다, 총 반복 768개 | 반복은 valid age를 연장하지 않음; flood 중에도 timeout 검출 |

RX loop는 한 cycle 최대 8개를 처리하고 timeout/source age 검사 후 1 ms를 쉰다.
Application queue는 추가하지 않았고 kernel queue의 정확한 깊이는 확정하지 않았다.
`SO_RXQ_OVFL` nonzero이면 continuity fault로 demo를 종료한다. 이번 flood는 실제 drop을
강제한 시험이 아니며 kernel overflow 주입은 NOT RUN이다. 차량 보호 출력은 아직 연결하지 않았다.
근거는 [Linux socket(7)](https://www.man7.org/linux/man-pages/man7/socket.7.html)이다.

수신 로그의 `last_valid_ns`, `last_source_ns`, `last_seq`, `history_angle_rad`는 진단 이력이다.
실제 입력 사용은 `current_sample(now)`로 제한한다. Source age가 30 ms를 넘으면 timeout 전에도
current sample이 사라지고, timeout을 검출하면 새 Epoch의 explicit INIT 전까지 복구하지 않는다.

## 실행 결과

2026-10-12, x86 Ubuntu Host, GCC 11.4.0/C++17, CMake 4.3.2, Debug,
`-Wall -Wextra -Werror`, 별도 user/network namespace의 vCAN에서 실행했다.

- Normal build: 기존 44개 + adapter 4개 = **48 unit test PASS**.
- ASan/UBSan build: **48 unit test PASS**, 새로운 두 executable도 계측했다.
- Normal vCAN: **8 case PASS**, 관측 timeout **80.226–81.047 ms**.
- ASan/UBSan vCAN: **8 case PASS**, 관측 timeout **80.081–80.755 ms**. 성능 대표값으로 사용하지 않는다.
- 모든 timeout은 마지막 accepted RX 또는 first-frame monitoring enable 이후 80..100 ms인지 검사했다.
- clang-tidy 14.0.0: 새 adapter/TX/RX/test 5개 source의 적용 검사에서 소스 진단 없음.
- cppcheck 2.7: 새 production adapter/TX/RX 4개 source의 적용 검사에서 진단 없음.
- 기존 DBC parser/golden bytes/independent CRC/C++ demo 교차 검증 PASS. Wire schema는 유지했다.

Integration trace는 각 build의 `socketcan-results/{cmd|actual}-{scenario}-1.log`에 남는다.
Observed timeout은 이 8개 local fixture의 결과이며 임의 부하에서의 deadline 보장이나
TC-COM/TC-SAFE 전체 결과가 아니다. vCAN은 실제 CAN의 전기적/bit timing을 검증하지 않는다.
M1 전체 acceptance와 학습자 review는 완료로 바꾸지 않는다.

```sh
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 2
ctest --test-dir build/m1-angle-sanitized --output-on-failure
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --build-dir build/m1-angle-sanitized
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' interfaces/socketcan/socketcan_endpoint.cpp interfaces/socketcan/actuator_socketcan.cpp tests/integration/can/socketcan_tx.cpp tests/integration/can/socketcan_rx.cpp tests/unit/actuator_socketcan_test.cpp
cppcheck --enable=warning,performance,portability --error-exitcode=1 --std=c++17 --suppress=missingIncludeSystem -I interfaces/common -I interfaces/steering -I interfaces/brake -I interfaces/socketcan interfaces/socketcan/socketcan_endpoint.cpp interfaces/socketcan/actuator_socketcan.cpp tests/integration/can/socketcan_tx.cpp tests/integration/can/socketcan_rx.cpp
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py --demo build/m1-angle/actuator_demo
```

## 예제·시험 정리와 재검증

2026-10-12 예제 4개를 `tools/actuator_demo.cpp` 하나로 합쳤다.
각 단계는 `angle`, `frame`, `e2e`, `receiver` 명령으로 실행한다.
SocketCAN TX/RX/helper/runner는 `tests/integration/can/`에 모았고 `BUILD_TESTING=ON`에서만
TX/RX 실행 파일을 만든다. 단위 시험 파일은 기존 모듈 구분을 유지한다.
새 기능은 기존 모듈의 case로 추가하는 [배치 기준](../quality_policy.md#코드예제시험-배치)을 정했다.

정리 후에도 기존 예제의 입력/출력/정상·거부 동작 17개가 normal/ASan·UBSan에서 일치했다.
Normal에서 잘못된 명령 형태 7개와 `--help`를 확인했다. DBC 검사기도 `actuator_demo frame`으로
호출하도록 바꾸고 기존 4개 payload의 독립 교차 검증을 통과했다.
Fresh `BUILD_TESTING=OFF` build에서 라이브러리와 예제만 생성되는 것도 확인했다.

재실행 중 flood에서 실제 kernel RX drop이 한 번 관측되어 continuity fault로 종료했다.
정확한 원인을 단정하지 않는다. 수신 trace의 매 출력 항목 flush를 cycle당 한 번으로 묶어
로깅 부담을 줄였고, runner가 실패해도 handshake/stdout/stderr를 보존하도록 보완했다.
임시 Python participant의 nonzero exit를 주입해 실패가 유지되고 수집된 trace가 저장되는지 확인했다.
일반 flood는 계속 32개씩/5 ms, 총 반복 768개이며 수용/overflow/timeout 기준은 유지한다.
계획적으로 kernel overflow를 강제한 독립 case는 여전히 NOT RUN이다.

수정 후 결과는 normal/ASan·UBSan 각각 **48 unit test + 8 vCAN case PASS**다.
최종 normal 관측 timeout은 **80.173–80.947 ms**, ASan·UBSan은 **80.007–81.033 ms**였다.
통합 demo/TX/RX source 3개에 clang-tidy/cppcheck를 적용해 소스 진단이 없었다.
이 값은 지정된 local fixture 결과이며 부하와 scheduling에 대한 보장으로 사용하지 않는다.

## 이해 확인과 다음 단계

2026-10-13 [Brake wire 확장](m1_brake_codec.md)으로 demo/DBC 검사기는 각각
`actuator_demo`/`check_actuator_dbc.py`로 이름을 바꿨고, 통합 시험을 `tests/integration/can/`으로 옮겼다.
위 명령/링크는 현재 경로다. 이 문서의 2026-10-12 결과는 당시 Steering 8개 case의 기록이다.

`TX first`와 첫 `RX ACCEPTED`를 찾아 Angle이 복원되는 경로를 설명한다.
`faults`에서 E2E 통과한 stale/cached Sequence도 거부되는지, timeout의 reference가 raw RX가 아닌
last-valid RX인지 확인한다. `flood`에서 한 번에 8개를 처리하는 이유와 kernel queue 깊이가
8개라는 의미가 아님을 설명한다. 이것을 직접 재현하고 diff를 검토하는 단계는 PENDING이다.

Brake의 두 frame은 wire 검사까지 추가했다. 다음은 Brake 수신 수용과 Drive 두 frame의
units/ranges/scaling 및 송수신 확장이다. M2에서는 실제 조향 state/dynamics, 유효 command에 따른 Actual 생성,
local protection output과 task/queue를 연결한다. 영속 session과 kernel overflow 주입도 후속 검증이다.
