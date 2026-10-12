# ADR-0006 — Host Steering frame codec and DBC checker

## Status

2026-10-12 **Host 구현·검증 완료 / 학습자 review PENDING**.
Steering 두 frame의 초안을 시험했다. Six-frame baseline과 M1 acceptance는 미완료다.
2026-10-12 자체 CRC/초기 wire 결정은 [ADR-0007](ADR-0007-autosar-e2e-profile5.md)의
P05/schema 2로 대체했다. 아래 Host 도구/dependency 결정은 유지한다.

## Decision

[Frame 제안](../icd/steering_frame_draft.md)을 C++17의 고정 크기 payload로 구현한다.
기존 angle codec을 재사용하고 ID/FD/length/flags, CRC, schema/reserved/enums/epoch와
Validity/angle 표현의 일관성을 검사한다. uint64 timestamp는 double을 거치지 않는다.
Command 수용, 물리 한계, mode/origin 관계와 시간/trace Sequence 진행을 판단하는 receiver는 별도로 둔다.
후속 ADR-0007에서 P05 Protect/Check state를 추가했다.
Wire decode의 성공과 invalid/unavailable 진단 message, 유효 actuator input을 구분한다.

DBC와 수작업 C++ 배치의 차이를 확인할 Host 전용 도구로 **cantools 40.7.1**을 사용한다.
[공식 문서](https://cantools.readthedocs.io/en/latest/)의 strict parser/encode/decode API로
독립 golden vectors 및 C++ demo를 비교한다. 여기서는 code generation을 사용하지 않는다.
현재 Host의 Python 3.10.12, uv 0.9.15로 `build/m1-dbc-venv`를 생성했다.
[전체 dependency pin](../../tools/requirements-dbc.txt)을 기록하고 CMake 자동 설치는 추가하지 않는다.
새 Python checker는 runtime/library/Target 의존성이 아니다.

## Dependency review

2026-10-12 PyPI release metadata의 Python 지원과 license를 확인한 뒤 격리 환경에 설치했다.
cantools 40.7.1 wheel의 MIT license 본문/copyright도 확인했다.
Wheel SHA256: `a68159cce229581f77aad0b906938682f29ecc9164248c997af80f1d49c073c9`.
Third-party source/binary를 repository에 복사하거나 generated code를 배포하지 않는다.

| Package | 고정 version | 확인한 license |
| --- | --- | --- |
| cantools | 40.7.1 | MIT |
| argparse-addons | 0.12.0 | MIT |
| bitstruct | 8.23.0 | MIT |
| crccheck | 1.3.1 | MIT |
| textparser | 0.26.2 | MIT |
| diskcache | 5.6.3 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| python-can | 4.6.1 | LGPL-3.0-only |
| typing-extensions | 4.16.0 | PSF-2.0 |
| wrapt | 1.17.3 | BSD (release metadata 표기) |

python-can은 cantools의 dependency이며 이번 checker가 CAN socket을 사용한다는 뜻이 아니다.
향후 third-party 복사/배포/Target 도입 시 해당 artifact와 조건을 다시 검토한다.

## Alternatives and consequences

- 자체 DBC parser만 작성: 같은 설계 오류를 공유할 수 있어 독립 parser와 비교한다.
- DBC에서 C 코드를 생성: 가능한 후속 선택이다. 이번에는 기존 C++ field codec과 연결하고
  작은 byte packing 구현을 학습하기 위해 수작업 codec + 독립 parser 검증을 선택했다.
- 전체 receiver/vCAN/vECU를 한 번에 구현: 학습/검토 범위를 나누기 위해 이번에는 wire codec만 구현한다.

TBD-11의 Host DBC 검증 도구 선택만 구체화한다. Target/CI/일반 toolchain 선택은 남는다.
TBD-01/02/04의 전체 wire/물리 범위/receiver/timing을 CLOSED로 바꾸지 않는다.
검증 명령과 결과 범위는 [학습 실행 기록](../learning/m1_steering_frame_codec.md)에 남긴다.
