# M1 두 번째 실행: 조향각을 bytes로 표현하기

Status: **field codec 구현·Host 단위 시험 완료 / 학습자 review PENDING**.
전체 DBC/frame codec, vCAN application 검증과 M1 acceptance는 미완료다.

## 실행부터 시작

Repository root의 Linux terminal에서 실행한다. 현재 Host에 필요한 도구가 설치돼 있다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle --output-on-failure
./build/m1-angle/steering_angle_demo 0.1
```

예상 출력:

```text
입력: 0.1 rad
Bytes: E8 03
복원: 0.1 rad
```

이번에는 이 세 개념을 코드와 함께 본다.

| 개념 | 지금 예제에 적용 |
| --- | --- |
| Scaling | 후보 간격 0.0001 rad로 나누면 `0.1 / 0.0001 = 1000` |
| Signed | 좌회전/우회전의 부호를 유지하도록 signed 정수로 표현 |
| Little-endian | raw 1000의 hex `0x03E8`에서 하위 byte `E8`을 먼저 저장 |

`-0.1`로 실행하면 `18 FC`, `0.10006`으로 실행하면 `E9 03`과 복원값 `0.1001`이 나온다.
마지막 예제의 차이는 quantization이다. `nan`과 `4.0`은 실패(exit 1)한다.
4.0의 거부는 현재 wire 표현 범위를 넘기 때문이며 실제 차량의 조향 한계 판정이 아니다.

[짧은 codec 구현](../../interfaces/common/steering_angle_codec.cpp)에서
`encode_steering_angle()`의 범위 검사·반올림·byte 분리를 읽고,
`decode_steering_angle()`에서 부호와 단위를 복원하는 부분을 읽는다.
성공/실패는 `std::optional`로 표현한다. 값이 없으면 호출자가 거부를 처리해야 한다.

표현 형식과 검토 근거는 [field 계약 초안](../icd/steering_angle_encoding.md),
도구 선택은 [ADR-0005](../adr/ADR-0005-first-cpp-codec.md)에 있다.
이 단계에서 Command 수용이나 actuator actual response를 구현한 것은 아니다.

## 검증 기록

2026-09-28, Codex가 x86_64 Linux 6.8.0-138-generic에서 실행했다.
GCC 11.4.0 / CMake 4.3.2 / C++17 / GoogleTest 1.11.0, Debug build다.

- GoogleTest 6개 PASS: 독립 golden vectors, 양·음 반올림, nonfinite/범위 밖 거부,
  reserved code 거부, byte order, 65,535개 유효 wire code의 복원·재표현.
- CLI: `0.1`, `-0.1`, `0.10006` 성공; `nan`, `4.0`, `0.1junk` 실패를 확인했다.
- 별도 ASan/UBSan build에서 같은 6개 테스트 PASS.
- clang-tidy 14.0.0과 cppcheck 2.7로 codec/demo를 검사했다. 해당 소스의 진단 없음.
  clang-tidy의 system/non-user header 진단은 기본 filter로 제외됐다.

검사 재현 명령:

```sh
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 2
ctest --test-dir build/m1-angle-sanitized --output-on-failure
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' interfaces/common/steering_angle_codec.cpp tools/steering_angle_demo.cpp
cppcheck --enable=warning,performance,portability --error-exitcode=1 --std=c++17 --suppress=missingIncludeSystem -I interfaces/common interfaces/common/steering_angle_codec.cpp tools/steering_angle_demo.cpp
```

관련 interface는 IF-CAN-STEERING이다. SYS-COM-002 / TC-COM-002의 향후 frame validation을
구성할 후보 field를 시험했지만 CRC/sequence/freshness/last-valid age는 검사하지 않았다.
기존 Requirement/TC를 VERIFIED/PASS로 변경하지 않는다. Target, timing, 전체 DBC parser와의
교차 검증은 NOT RUN이다. 학습자의 직접 실행·설명 여부는 별도로 기록한다.

## 다음 작은 작업

Steering Command와 Steering Actual을 포함한 six-frame 계약에 CAN ID/field 위치와
공통 metadata를 배치한다. Field 초안과 최종 frame의 일관성을 검토한 뒤 전체 codec과
vCAN 송수신에 연결한다. 지금은 위 실행에서 부호와 반올림에 따른 bytes 변화를 확인하면 된다.
