# Software quality policy

Status: **Planned**. M0에는 컴파일된 application이나 자동화된 차량 시험이 없다.

| 영역 | 향후 정책 | 적용 시점 / 증거 |
| --- | --- | --- |
| Compiler | 직접 관리하는 GCC/Clang target에 `-Wall -Wextra -Werror` 적용 | 첫 C++ target부터 적용; 검토된 최소 범위의 예외는 문서화하고 third-party에 global flag 적용 지양 |
| Static analysis | clang-tidy와 cppcheck | 처음 적용할 코드와 함께 규칙을 검토하고 도구 버전 고정 |
| Dynamic analysis | ASan과 UBSan | Host의 계측된 test job에서 사용; Target 지원은 별도 검증 |
| Unit tests | C++는 GoogleTest, Python은 pytest | 구현과 함께 동작/계약 시험 작성 |
| System tests | Integration Test, SIL Regression, Fault Regression, Performance Regression | Milestone별로 추적 가능한 case와 검토된 threshold 사용 |
| CI | 초기에 필요하면 configure/문서 검사만 수행 | M0에는 CI workflow 없음; 실제로 수행하지 않은 차량 시험을 PASS로 표시하거나 의존성이 많은 골격을 만들지 않음 |

Sanitizer를 사용한 timing은 대표 성능 증거로 볼 수 없다. 결과에는 build type,
compiler/option, 활성화된 계측을 기록한다. Real-time priority, affinity, kernel 선택,
최적화에는 변경 전후 증거가 필요하며 효과를 미리 보장하지 않는다.
Linux 측정만으로 hard real-time 인증을 주장하지 않는다.

코드를 수용하기 전에 학습자가 변경을 설명하고 diff를 검토하며 관련 검사를 직접
실행한다. Edge/fault 동작도 확인하고 결과를 요구사항에 연결한다. 미실행 test를
PASS로 표시하지 않는다. 의존성을 추가하기 전에 버전과 license를 검토하며,
M0에서는 대형 의존성을 설치하지 않는다.
