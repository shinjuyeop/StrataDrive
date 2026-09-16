# Software quality policy

Status: **Planned**. M0 has no compiled application or automated vehicle tests.

| Area | Future policy | Activation / evidence |
| --- | --- | --- |
| Compiler | `-Wall -Wextra -Werror` on owned GCC/Clang targets | First C++ target; document any narrow reviewed exception; avoid third-party global flags |
| Static analysis | clang-tidy and cppcheck | Reviewed rules and pinned tool versions with first applicable code |
| Dynamic analysis | ASan and UBSan | Host instrumented test jobs; target support verified separately |
| Unit tests | GoogleTest for C++; pytest for Python | Behavior/contract tests with implementation |
| System tests | Integration Test, SIL Regression, Fault Regression, Performance Regression | Traceable cases and reviewed thresholds per milestone |
| CI | Initially only configure/document checks if needed | No CI workflow at M0; no fake vehicle pass or dependency-heavy skeleton |

Sanitizer timing is not representative performance evidence. Record build type,
compiler/options and enabled instrumentation with results. Real-time priorities,
affinity, kernel choices and optimizations need before/after evidence, not presumed
guarantees. Linux measurements alone are not hard real-time certification.

Before accepting code: learner explains the change, reviews diff, runs relevant
checks, exercises edge/fault behavior and links results to requirements. Never mark
an unrun test PASS. Dependency versions and licenses must be reviewed before adding
them; no large dependency is installed at M0.
