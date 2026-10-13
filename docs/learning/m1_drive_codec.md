# M1 Drive 통신 — 구동·회생 토크와 피드백

Date: 2026-10-13. Status: **Codex 구현·Host 시험 실행 / 학습자 설명·직접 재현 PENDING**.
[Wire 초안](../icd/drive_frame_draft.md), [ADR-0013](../adr/ADR-0013-drive-feedback-wire.md)를 따른다.

## 이번에 연결한 흐름

Zone의 signed torque demand → DriveCommand encode/P05 → SocketCAN →
Drive command receiver의 수용 검증까지 구현했다. 반대 방향도 독립 Actual fixture →
DriveActual encode/P05 → SocketCAN → receiver → fresh current_sample으로 연결했다.

Actual에는 실제 모델 토크, 바퀴 속도, 회생 토크 한계가 들어갈 자리를 만들었다.
현재 TX는 독립 fixture 값이며 모터 모델·충전 모델의 실제 계산 결과가 아니다.
Torque만 fresh하고 회생 정보가 stale이면 torque는 유지하고 capability만 사용 불가로 표시한다.
유효 0 capability와 unknown을 구분하므로 나중에 Zone이 마찰제동 배분을 판단할 수 있다.

| 파일 | 책임 |
| --- | --- |
| [drive_value_codec](../../interfaces/drive/drive_value_codec.cpp) | signed torque / wheel speed / regen limit의 raw 표현 |
| [drive_frame_codec](../../interfaces/drive/drive_frame_codec.cpp) | 32-byte Command / 64-byte Actual과 P05 |
| [drive_receiver](../../interfaces/drive/drive_receiver.cpp) | torque 수용·timeout과 보조 feedback 유효성 |
| [Drive DBC](../../interfaces/dbc/drive_m1_draft.dbc) | 양쪽이 합의할 byte/단위/enum 배치 |
| [actuator_payload_codec](../../interfaces/common/actuator_payload_codec.cpp) | 공통 prefix와 32/64-byte P05 보호 |
| [CAN 통합 시험](../../tests/integration/can/check_socketcan.py) | 기존 TX/RX/runner에서 Drive 9개 case 확장 |

## 직접 실행

기존 Host 도구와 의존성을 사용하며 새로 설치하지 않았다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 4
ctest --test-dir build/m1-angle --output-on-failure
./build/m1-angle/actuator_demo drive-frame command 200
./build/m1-angle/actuator_demo drive-frame command -200
./build/m1-angle/actuator_demo drive-frame actual -150
./build/m1-angle/actuator_demo drive-frame command 0
./build/m1-angle/actuator_demo drive-frame actual invalid
./build/m1-angle/actuator_demo drive-feedback
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py --demo build/m1-angle/actuator_demo
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py
```

drive-feedback는 수동 clock으로 정상 → cached capability → age 초과 → 새 산출 시각이지만
old input → fresh 유효 0 → torque timeout을 보여준다. 숫자는 시험용 설정이며 차량 calibration이 아니다.
vCAN runner는 별도 TX/RX process로 위 관계와 실제 송수신을 검사하고 실패 trace도 보존한다.

Sanitizer 검사:

```sh
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 4
ctest --test-dir build/m1-angle-sanitized --output-on-failure
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --build-dir build/m1-angle-sanitized
```

## 실행 결과

- GCC 11.4.0 / C++17 / CMake 4.3.2 / GoogleTest 1.11.0 / cantools 40.7.1.
- Normal·ASan/UBSan 각각 **unit 98개 PASS**: 기존 80 + Drive value/frame/receiver 17 +
  SocketCAN adapter 1. 모든 valid signed torque/wheel-speed/regen-limit raw code를 왕복 검사했다.
- Six-frame DBC 배치·enum·단위·P05 설정, 독립 golden 9개와 C++ demo payload 14개 교차 검증 PASS.
  Drive의 4개 uint64 timestamp는 2^53+1과 UINT64_MAX에서도 정수 정밀도를 보존한다.
- Normal·ASan/UBSan 각각 **vCAN 27 case PASS**: 기존 18 + Drive cmd/actual의
  normal/fault/silent/flood 8 + capability 유효/0/invalid/cached/old input/torque 상실 1.
- Torque가 fresh인 동안 capability를 별도로 제거하는지, valid 0이 남는지, invalid torque가
  valid capability로 대체되지 않는지 검사했다. 물리 limit/time tuning의 evidence는 아니다.
- 관측 timeout은 마지막 valid RX 또는 trusted enable부터 normal **80.026–81.038 ms**,
  sanitizer **80.066–81.042 ms**였다. Local fixture 결과이며 sanitizer는 대표 성능 측정이 아니다.
- Trace는 각 build/socketcan-results/에 있으며 fixed seed 차량 TC와 M1 최종 acceptance는 미완료다.

- clang-tidy 14의 clang-analyzer/bugprone을 변경 C++ source 10개에 적용했다.
  최종 user-source 진단은 없었다. Non-user/header 및 기존 NOLINT suppression을 포함한
  전체 무경고 주장이 아니다. cppcheck 2.7 warning/performance/portability도
  runtime/demo/participant 8개에서 통과했다.
- DriveReceiver config를 const reference로 받은 뒤 소유 copy를 유지하도록 정리하고
  normal/sanitizer unit 98개와 해당 static analysis를 재검증했다.
- Fresh BUILD_TESTING=OFF에서 라이브러리/demo만 build했고 drive-feedback 실행을 확인했다.
  문서 relative link와 변경 text의 whitespace/Python syntax를 검사했다.

Static analysis 재현 명령:

```sh
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' interfaces/common/actuator_payload_codec.cpp interfaces/drive/drive_value_codec.cpp interfaces/drive/drive_frame_codec.cpp interfaces/drive/drive_receiver.cpp interfaces/socketcan/actuator_socketcan.cpp tools/actuator_demo.cpp tests/integration/can/socketcan_tx.cpp tests/integration/can/socketcan_rx.cpp tests/unit/drive_test.cpp tests/unit/actuator_socketcan_test.cpp
cppcheck --enable=warning,performance,portability --error-exitcode=1 --std=c++17 --suppress=missingIncludeSystem -I interfaces/common -I interfaces/steering -I interfaces/brake -I interfaces/drive -I interfaces/socketcan interfaces/common/actuator_payload_codec.cpp interfaces/drive/drive_value_codec.cpp interfaces/drive/drive_frame_codec.cpp interfaces/drive/drive_receiver.cpp interfaces/socketcan/actuator_socketcan.cpp tools/actuator_demo.cpp tests/integration/can/socketcan_tx.cpp tests/integration/can/socketcan_rx.cpp
```

학습자의 코드 설명/직접 재현 결과는 자동 시험과 별도로 기록한다.

## 다음 단계

양수/음수/0 torque와 actual/capability의 유효성 차이를 복습한다.
M1의 영속 Epoch coordinator, application queue/overflow 주입, 학습자 wire review는 남아 있다.
다음 작은 작업은 [EV-01](../icd/ev_power_bms_design.md)의 BMS/power/constraint 의미·wire·timing이다.
[ZON-01](../architecture/zonal_partition.md)의 Front 단일 coordinator/Rear gateway는 후속 M4/M5에 연결한다.
M2에서 command가 실제 angle/pressure/torque로 변하는 응답 모델을 만들고, Drive의
속도·충전 수용 한계와 에너지 모델을 붙인다. 이후 Zone 배분과 Plant/Central 차량 피드백을 연결한다.
현재 vehicle closed-loop, 실제 충전·회생, ABS/ESC, TC-REG-001–005 전체는 **NOT RUN**이다.
