# ADR-0005 — First C++ field codec experiment

## Status

2026-09-28 **Implemented for Host experiment / 학습자 review PENDING**.
M1의 작은 구현 단위이며 전체 wire 계약 채택이나 milestone acceptance가 아니다.

## Context

vCAN fixture 송수신을 확인했으므로 실제 물리량의 byte 표현을 구현하며 학습한다.
Steering Command/Actual의 의미는 정해졌지만 six-frame wire layout과 actuator calibration은
미정이다. 한 field를 먼저 검토하면 encoding의 부호·단위·반올림 오류를 작게 시험할 수 있다.

## Decision

[Steering angle field 초안](../icd/steering_angle_encoding.md)을 먼저 명시하고,
해당 초안의 독립 golden vectors → codec → 단위 시험 → CLI 실행 순서로 구현한다.
이 초안은 향후 전체 DBC 검토에서 바뀔 수 있다. Receiver/transport에는 아직 연결하지 않는다.
Command와 Actual이 같은 표현을 쓰더라도 actual을 command echo로 생성하지 않는다.

첫 C++ 작업은 C++17, 현재 Host의 GCC 11.4.0, CMake 4.3.2와 설치된 GoogleTest 1.11.0을
사용한다. `std::array`와 `std::optional`로 고정 크기 bytes와 실패를 명시한다.
CMake의 최소 지원 선언은 기존 3.20을 유지하며 3.20 자체를 검증했다고 주장하지 않는다.
GoogleTest는 exact 1.11.0을 요구하고 자동 download를 넣지 않는다. 테스트를 끈 빌드는
GoogleTest가 필요 없지만 검증 완료로 취급하지 않는다.

GoogleTest 1.11.0의 [BSD-3-Clause license](https://github.com/google/googletest/blob/release-1.11.0/LICENSE)와
현재 설치 package의 copyright를 확인했다. Third-party source/binary를 repository에 복사하지 않는다.
직접 관리하는 target에만 `-Wall -Wextra -Werror`를 적용한다. ASan/UBSan은 별도 Host build로
실행하고, clang-tidy 14.0.0과 cppcheck 2.7의 검사 범위·명령은 [실행 기록](../learning/m1_steering_codec.md)에 남긴다.

## Alternatives Considered

- Python codec만 구현: 빠른 실험에는 적합하지만 이번에는 향후 C++ component가 사용할
  field 함수를 작은 단위로 작성하고 build/test 경로를 확인한다.
- Six-frame codec 전체를 한 번에 구현: metadata와 상태 검증까지 커지므로 먼저 field
  표현을 검토한다. 전체 frame 구현 전에 남은 wire/receiver 계약을 해소한다.
- 새 compiler나 test framework 설치: 현재 환경의 도구로 이번 범위를 검증할 수 있어 보류한다.

## Consequences

TBD-11의 첫 Host C++ 실험 선택만 기록했다. CI/Target/AUTOSAR toolchain 호환성은
미검증이며 TBD-11/09와 pilot 검토가 계속 필요하다. TBD-01/02의 field 제안은 별도 초안으로
추적하고 전체 TBD를 CLOSED로 처리하지 않는다. 실제 조향 한계, frame identity, CRC,
freshness, local safety는 이번 codec의 책임 밖이다. 기존 Requirement ID/shall 문장은 유지한다.
