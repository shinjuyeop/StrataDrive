# M1 다섯 번째 실행: 조향 메시지 수신부

Status: **2026-10-12 Host 로컬 수신부·제어 가능한 시계 시험 완료 / 학습자 review PENDING**.
결정은 [ADR-0008](../adr/ADR-0008-steering-receiver.md), 입력은 기존 [schema 2 frame](../icd/steering_frame_draft.md)이다.
이 단계는 수동 시계의 로컬 수신부 시험이다. 실제 socket/clock 연결은
[후속 SocketCAN 기록](m1_steering_socketcan.md)에 있으며 영속 coordinator, queue budget,
actuator/차량 통합 및 M1 acceptance는 미완료다.

## 무엇을 추가했나

Codec은 bytes를 복원하고 P05는 손상과 Counter 진행을 검사한다.
이번 수신부는 복원한 값이 이번 실행의 새롭고 유효한 sample인지 판단한다.
CRC가 맞아도 오래된 timestamp, 다른 Epoch, cached Sequence, invalid angle이면 거부한다.
거부한 frame은 최신 수용값과 last-valid RX를 갱신하지 않는다.

| API | 역할 |
| --- | --- |
| `start_session(epoch, now)` | 신뢰된 INIT 설정; 새 Epoch와 수신 시작 시각 지정 |
| `receive(frame, now)` | timeout/E2E/표현/시간/순서/mode/range 검사, 수용 또는 reject 이유 반환 |
| `poll(now)` | 입력 없는 cycle에서도 acquisition/RX timeout 감시 |
| `current_sample(now)` | 원천 age와 RX timeout 안의 sample만 반환 |
| `last_accepted()` | 진단용 과거 message와 수용 시각; 제어 입력으로 직접 사용하지 않음 |
| `last_raw_rx_time_ns()` | 거부한 frame도 포함한 최근 RX 시각; valid age와 별개 |

`SteeringReceiverHealth::Receiving`은 수신 기록이 있다는 뜻이다. Actual sender의 NORMAL이나
정상 주행 가능을 뜻하지 않는다. Fault/protection 중 valid Actual의 상태 metadata도 보존한다.
Actual invalid 확인 시 Host의 apply/tick gate는 상위 통합에서 별도로 적용해야 한다.

## 실행

Repository root에서 기존 C++17/GCC/CMake/GoogleTest 환경을 사용한다. 새 dependency는 없다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle --output-on-failure
./build/m1-angle/actuator_demo receiver
```

Demo는 socket/clock syscall 없이 수동 monotonic 시각을 전달한다. +/-0.5 rad는 시험용 한계이며
실제 차량의 물리 한계가 아니다. 주요 결과는 다음과 같다.

```text
정상 첫 frame -> ACCEPTED (E2E status=0) last-valid RX=1000000000
같은 frame 반복 -> E2E_REJECTED (E2E status=8) last-valid RX=1000000000
cached sample 재포장 -> SEQUENCE_REJECTED (E2E status=0) last-valid RX=1000000000
오래된 sample -> SOURCE_STALE (E2E status=0) last-valid RX=1000000000
새 정상 sample -> ACCEPTED (E2E status=0) last-valid RX=1050000000
source age 30 ms 초과 -> current sample 없음
invalid sample -> UNAVAILABLE (E2E status=0) last-valid RX=1050000000
다른 Epoch -> EPOCH_MISMATCH (E2E status=0) last-valid RX=1050000000
last-valid RX +80 ms -> TIMEOUT
timeout 뒤 정상 frame -> TIMEOUT last-valid RX=1050000000
새 Epoch + explicit INIT -> ACCEPTED (E2E status=0) last-valid RX=1150000000
```

E2E status 0은 OK, 8은 REPEATED다. E2E OK인 거부 frame이 여럿 있어도 last-valid RX는
바뀌지 않는다. 마지막 수용 시각 1.05 s로부터 80 ms인 1.13 s에서 timeout을 검출하고,
다음 정상 frame 하나로 fault를 해제하지 않는다.

## 코드 읽기와 사용

1. [설정/API](../../interfaces/steering/steering_receiver.hpp)를 읽는다. Command/Actual마다 별도
   receiver를 유지하며 호출 시각과 source 시각은 같은 monotonic domain이어야 한다.
2. [수신 구현](../../interfaces/steering/steering_receiver.cpp)의 `poll`을 먼저 본다.
   `now - reference >= timeout`이며 reference는 last-valid RX 또는 session 시작이다.
   Clock 감소와 timeout은 새 Epoch의 explicit INIT 전까지 유지한다.
3. `receive`는 raw P05 counter와 application 수용 기록을 분리한다.
   WRONGSEQUENCE의 E2E 재동기화나 CRC 정상인 invalid payload는 application cursor를 갱신하지 않는다.
4. `current_sample`은 timeout 전이어도 source age가 끝나면 값이 없다.
   Sample-and-hold를 계속하려면 반드시 이 API로 현재 유효 기간을 확인한다.

설정 예제:

```cpp
stratadrive::can::SteeringReceiver receiver({
    stratadrive::can::SteeringFrameKind::Command, -0.5, 0.5});
// 신뢰된 local INIT 설정에서 전달한다. Frame의 Epoch로 호출하지 않는다.
const bool started = receiver.start_session(trusted_epoch, monotonic_now_ns);
```

Caller는 `started`가 false이면 실행을 시작하지 않는다. `receive` 결과의 reject 이유와
호출 시각은 외부 로그에 기록한다. `current_sample(now)`가 없으면 정상 제어 입력이 없다.
수신부 자체에는 thread/queue/periodic scheduler가 없으므로 입력 없는 cycle에도 `poll`이 필요하다.
한 stream을 여러 thread에서 동시에 호출하지 않는다.

Default source age는 <=30 ms, RX/acquisition timeout은 >=80 ms다. Config는
`0 < max_source_age_ns < timeout_ns <=80 ms`를 요구한다. First trace Sequence는 0..9,
이후 +1..+10이며 uint32 wrap은 거부한다. P05 Counter의 255→0은 정상이고 별도 시험한다.
Angle 한계는 finite min < max로 명시하고 wire 범위 안에서만 설정한다.
Raw→double의 1 ULP 경계 오차만 허용하며 다음 0.0001-rad 값으로 범위를 넓히지 않는다.
Command는 NORMAL/DEGRADED + normal path만 수용한다. Actual origin=0은 INIT에서만 허용하며
나머지 sender 상태를 정상 주행 상태로 덮어쓰지 않는다.

## 검증 기록

2026-10-12 Linux 6.8.0-138-generic x86_64, GCC 11.4.0, CMake 4.3.2,
GoogleTest 1.11.0/C++17 Debug에서 실행했다.

- Normal/ASan·UBSan: 기존 25개 + 새 receiver 19개 = 각각 **44개 PASS**.
- Receiver: 설정/신뢰된 INIT, 정상 진행, CRC/Counter/stream/표현 오류,
  P05 resync와 application cursor 분리, stale/future/old epoch/cached replay,
  startup window/gap/backward/uint32 wrap, unavailable vs zero, mode/range/1 ULP 경계,
  source age와 RX age 분리, startup/accepted timeout, late frame/explicit INIT,
  clock 감소, P05 8-bit wrap, UINT64_MAX 인접 시각을 검사했다.
- `actuator_demo receiver`의 위 정상/reject/timeout/재초기화 결과 PASS.
- clang-tidy 14: 변경 receiver/demo/test 및 E2E demo의 적용 검사에서 user source 진단 없음.
  Non-user header/NOLINT는 기본 filter로 제외했다.
- cppcheck 2.7: 변경 receiver/demo/E2E demo의 적용 검사에서 진단 없음.
  GoogleTest macro source는 기존 tool 제약 때문에 제외하며 compiler/clang-tidy/실행으로 검사했다.
- README architecture는 Host/Target 구역과 Target의 Central/Zone/Leaf 구역을 묶어
  light/dark Mermaid로 렌더링했다. SVG viewBox 기준 높이 1282인 한 줄 흐름은 높이 380의 배치 그림으로 정리했다.

```sh
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 2
ctest --test-dir build/m1-angle-sanitized --output-on-failure
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' interfaces/steering/steering_receiver.cpp tools/actuator_demo.cpp tests/unit/steering_receiver_test.cpp
cppcheck --enable=warning,performance,portability --error-exitcode=1 --std=c++17 --suppress=missingIncludeSystem -I interfaces/common -I interfaces/steering -I interfaces/brake interfaces/steering/steering_receiver.cpp tools/actuator_demo.cpp
```

같은 clock domain을 전제로 제어 가능한 시각의 경계를 시험했다. 실제 10 ms dispatch,
마지막 valid RX부터 100 ms 안의 wall-time 검출 지연과 Host–Target 시계 동기화는 미측정이다.
SYS-COM/TC-COM/TC-SAFE 전체 결과나 M1 acceptance를 PASS/VERIFIED로 변경하지 않는다.

## 다음 작은 작업

실제 CLOCK_MONOTONIC adapter, SocketCAN/vCAN의 독립 socket, bounded queue/overflow 관측,
monitor dispatch, trusted session/coordinator 설정을 연결한다.
Command/Actual fixture로 송수신을 검증하며 Actual fixture를 Command echo나 dynamics의 증거로 사용하지 않는다.
물리 한계 calibration, Brake/Drive의 공통 metadata와 six-frame 확장, vECU의 물리 응답은 후속 작업이다.

위 작업 중 실제 시계/SocketCAN/독립 process/trusted fixture handshake/bounded dispatch와
local timeout 시험은 [다음 SocketCAN 실행 기록](m1_steering_socketcan.md)에서 수행했다.
영속 coordinator, application queue depth와 kernel overflow 주입은 여전히 후속 범위다.
