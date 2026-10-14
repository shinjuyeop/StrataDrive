# Software quality policy

Status: **M1 통신과 M2 첫 Steering/Brake 모델에 적용**. Compiler warnings, GoogleTest,
clang-tidy/cppcheck와 ASan/UBSan을 사용했다. 현재 normal·sanitizer 각각 **unit 172개 PASS**다.
Actuator 6개 + EV 6개 DBC/독립 CRC와 C++ payload 36개의 교차 검사가 PASS다.
[Drive 실행 기록](learning/m1_drive_codec.md)과 [BMS 실행 기록](learning/m1_bms_codec.md)에
도구 버전, 검사 범위와 재현 명령을 보존한다. M1 89개와 M2 첫 Steering 2개·Brake 3개,
총 local vCAN **94개 case**를 검사한다.

2026-10-13 문서 정리 시 normal·ASan/UBSan build/unit/vCAN과 DBC 검사를 다시 통과했다.
Local observed timeout은 normal 80.019–81.072 ms, sanitizer 80.053–81.065 ms였다.
차량 timing 보장이나 sanitizer의 대표 성능으로 확대하지 않는다. M1 최종 acceptance/학습자
review는 PENDING이었다. 당시 EV C++ 통신과 두 Zone/runtime/차량 TC는 PLANNED / NOT RUN이었다.
문서 52개의 상대 링크/앵커 459개, 요구사항 32개/TC 29개의 정의·추적성,
YAML 3개의 중복 key/책임 배치와 Python syntax를 검사했다. 활성 경로의 낡은 참조를 정리하고
과거 ADR/부분 시험 이력과 목적이 다른 검증 계층은 보존했다.

2026-10-14 [BMS wire 초안](icd/bms_frame_draft.md)의 DBC·6개 goldens/uint64/CRC/canonical
검사를 추가했다. Normal·ASan/UBSan unit 99개, 기존 C++ demo 14개 교차 검증을 통과했다.
48-byte P05 case는 전체 384개 single-bit corruption/잘못된 DataID를 검사한다.
변경 C++ test에 clang-tidy 14 analyzer/bugprone을 적용해 user-source 진단은 없었다.
이 결과는 EV codec/receiver/Drive gate/모델/transport와 전체 TC-EV의 PASS가 아니다.
문서 54개/상대 링크·앵커 478개, 32개 요구와 29개 TC의 추적성, YAML 3개 및
EV rate/age/100 ms monitor budget의 설계 일관성도 검사했다. Python syntax/whitespace 검사를 통과했다.

같은 날 후속 구현에서 BMS value/frame codec·항목별 receiver를 추가했다. Normal·ASan/UBSan
각각 129개 unit이 PASS다. BMS 28개와 기존 Drive/SocketCAN 파일에 추가한 age/adapter case를
포함한다. 전체 12개 DBC/C++ payload 36개를 교차 검증했다.
변경 C++ source/test 10개에 clang-tidy 14의 analyzer/bugprone을 적용해 user-source 진단 없이
통과했다(third-party/header 진단은 제외). Cppcheck 2.7의 warning/performance/portability는
BMS 3개·공통 수신 상태·Drive receiver·SocketCAN adapter·demo의 source 7개에 적용해 통과했다.
EV의 native 48/64-byte 변환과 수동 clock timeout/parent expiry는 Host 단위 범위다.
이 codec 구현 시점에는 EV TX/RX/wall-time budget, Drive의 torque·limits·permission·로컬 HV
통합 gate, BMS/power 모델과 두 Zone/runtime/전체 TC-EV는 NOT RUN이었다.
공통 수신 상태 변경 후 기존 actuator vCAN은 normal·ASan/UBSan 각각 27 case를 재통과했다.
Local timeout은 normal 80.007–81.081 ms, sanitizer 80.029–81.219 ms였다.
이는 기존 6개 actuator frame 회귀이며 새 EV transport의 검증 결과가 아니다.
Fresh `BUILD_TESTING=OFF` build에서 BMS 포함 라이브러리/demo만 생성하고 receiver 예제를 실행했다.
문서 57개/상대 링크·앵커 508개, 요구사항 32개/TC 29개, YAML 3개 및 Python 3개의 syntax와
whitespace도 검사했다. System TC의 Runtime Result는 모두 NOT RUN을 유지한다.

후속 EV SocketCAN 작업은 기존 TX/RX/support/runner를 확장했다. 6종류 각각의 normal/faults/
silent/flood와 partial limits, cached dependency/physical input, 비critical 관측, parent expiry/
identity·explicit INIT/rejoin, 3-process 원천 보존 relay의 **EV 36개**를 추가했다.
Harness는 승인된 parent 목록을 stdin으로 공급하며 CAN에서 context를 자동 생성하지 않는다.
RX는 cycle당 8개 dispatch 후 poll하며 overflow 관측 시 실패한다. Kernel overflow 주입과
application queue/실제 coordinator·DDS는 남아 있다. Normal·ASan/UBSan 각각 전체 63개
(기존 actuator 27 + EV 36)를 검사하고 전체 unit 129개와 DBC 교차 검증도 재통과했다.
Clang-tidy 14 analyzer/bugprone은 변경 TX/RX 2개와 support header에 적용해 user-source
진단 없이 통과했고 cppcheck 2.7 warning/performance/portability도 통과했다.
EV critical timeout은 normal **80.021–81.045 ms**, sanitizer **80.052–81.036 ms**,
관측 envelope timeout은 normal **300.282–300.984 ms**, sanitizer **300.275–301.069 ms**였다.
Forward relay도 따로 80..100 ms budget을 판정했다. Actuator 회귀는 normal
80.008–81.034 ms, sanitizer 80.001–81.050 ms였다. 고정된 local fixture의 관측값이며
Target/차량 timing 보장이나 sanitizer의 대표 성능으로 확대하지 않는다.
실제 BMS limit/power 모델·Drive actuation gate와 두 Zone/차량 TC는 NOT RUN이다.

2026-10-14 [M1 session/queue 마무리](learning/m1_session_queue.md)는 영속 Epoch 발급과
fixed-capacity FIFO/continuity latch를 구현했다. 기존 unit 129 + session/queue 14 = 143개,
기존 vCAN 63 + application/kernel overflow 24 + durable restart 2 = 89개를 검사한다.
Unit의 동시 8개 process 발급·손상/상실/busy/I/O/소진과 12개 receiver 복구를 확인했다.
VCan kernel case는 실제 SO_RXQ_OVFL >0을 요구한다. 이전 Epoch의 counter 200이 새 세션의
P05 state를 오염시키지 않는지 unit/독립 process 양쪽에서 검사했다.
M1 기술 구현·자동 검사는 수용 항목별 기록하고 학습자 review/wire 채택은 PENDING으로 남긴다.
Actual Front session/DDS 및 물리 response/system TC 결과는 후속이다.
Normal·ASan/UBSan 각각 143개 unit/89개 vCAN이 PASS다. App overflow report의 최초 usable
RX 대비 시간은 normal 23.601–25.059 ms, sanitizer 23.698–25.513 ms였다.
Kernel drop report는 normal 48.986–51.073 ms, sanitizer 49.257–50.936 ms였고 12종류 모두
실제 nonzero drop을 기록했다. Report latency는 물리 loss onset latency가 아니다.
Critical timeout은 normal 80.013–81.071 ms, sanitizer 80.002–81.184 ms,
관측 timeout은 normal 300.030–301.045 ms, sanitizer 300.422–300.788 ms였다.
Clang-tidy 14 analyzer/bugprone은 변경 source/test 11개와 receiver/queue/support header에
적용해 user-source 진단 없이 통과했다. Cppcheck 2.7은 production/fixture source 10개에 적용했다.
59개 Markdown의 상대 링크·앵커 528개, 32개 요구/29개 TC, YAML 3개와 Python 3개의
정합성·syntax/whitespace를 검사했다. 실제 차량/Target 성능이나 전체 TC PASS로 확대하지 않는다.

2026-10-14 [M2 첫 Steering 모델](learning/m2_steering_model.md)은 unit 13개를 추가했다.
Normal·ASan/UBSan 각각 전체 156개 unit을 통과했다. 기존 M1 89개 vCAN 회귀를 모두 통과했고,
model-normal/model-loss 2개를 별도로 실행해 각각 통과했다. 첫 model verifier에서 expiry의
reference를 RX time에서 Command source time으로 수정하고 두 model case를 다시 통과했다.
유효 Command → delay/rate/saturation → 독립 Actual RX, source-expiry hold/latch/late command
거부를 확인했다. Actual validity와 FAIL_SAFE를 분리하며 full vehicle TC는 NOT RUN이다.
Clang-tidy의 변경 source/test 5개와 cppcheck production/fixture 4개를 최종 user-source 진단 없이
통과했다. BUILD_TESTING=OFF의 model library/demo build와 결정론적 demo도 통과했다.
61개 Markdown의 상대 링크/앵커, 요구사항 32개/TC 29개와 YAML/Python 정합성을 확인했다.
모델 설정은 SIL fixture이며 Target timing/실차 calibration은 별도다.

2026-10-14 [M2 첫 Brake 압력 모델](learning/m2_brake_model.md)은 unit 16개와 model vCAN 3개를
추가했다. Normal·ASan/UBSan 각각 전체 **172개 unit / 94개 vCAN**을 통과했다.
가압/감압·delay/saturation·valid-zero release, expiry/continuity/deadline의 protective floor ramp,
이미 높은 압력의 retain·late release 거부·clock/restart를 검사한다.
Maximum delay/300개 목표 변경도 fixed history에 유지되는지 unit에서 확인했다.
Generic model loop/runner를 Steering과 공유하고 Actual source/sequence/causal/state/pressure가
독립 RX에 보존되는지 검사했다. Clang-tidy 14 변경 source/test 5개와 cppcheck 2.7 source 4개는
user-source 진단 없이 통과했다. BUILD_TESTING=OFF library/demo build와 brake-model 실행도 통과했다.
63개 Markdown의 상대 링크/앵커, 32개 요구/29개 TC와 YAML/Python 정합성도 확인했다.
Pressure→wheel torque/차량 감속/ABS/회생 배분과 Target scheduling/full TC는 후속이다.

2026-10-14 [ADR-0021](adr/ADR-0021-central-coordination-and-parallel-zones.md)은 Central의 별도
VCU/allocation/session/feedback bridge와 대등한 두 Zone의 문서·profile 배치를 개정했다.
요구 4개를 v0.5로 기록하고 기존 32개 요구/29개 TC의 owner/interface/fault variant를 갱신했다.
Epoch library를 central/session으로 이동해 normal·ASan/UBSan build와 각 172개 unit을 통과했다.
CPP 발급 동작은 이전 source와 동일함을 확인했다. BUILD_TESTING=OFF build와 독립 production
issuer process의 1→2 발급, 64개 Markdown/상대 링크·앵커/추적성/YAML/Python 검사를 통과했다.
앞선 94개 vCAN 결과는 기존 component/wire 부분 증거다. 실제 새 Central–Zone DDS topology와
vehicle/system TC 결과는 NOT RUN이며 M4/M5 이후 검증한다.

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

Toolchain/compiler/CI/test 버전은 TBD-11(M1), board 지원/측정 환경은 TBD-09(M5/M12)로
관리한다. Owner와 rationale은 [TBD register](roadmap.md#open-m0-decisions)를 따른다.

## 코드·예제·시험 배치

- 재사용 기능은 `interfaces/`와 해당 runtime component에 둔다.
- 학습/확인 예제는 영역별 실행 프로그램으로 묶는다. 세 actuator와 EV/BMS는
  `tools/actuator_demo.cpp` 하나에 기존 아홉 명령 + BMS 세 명령 + Linux Epoch 명령을 제공한다.
  기존 기능의 작은 변경마다 별도 demo를 추가하지 않는다.
- 단위 시험 파일은 모듈별로 유지한다. 기존 모듈의 조건/경계/fault 추가는 같은 파일의 case로 추가하고,
  새로운 독립 모듈이 생기면 시험 파일을 만든다.
- 통합 시험의 participant/helper/runner는 같은 영역 아래 모은다.
  세 actuator SocketCAN은 `tests/integration/can/`이며 새 fault는 기존 runner의 case로 확장한다.
- DBC 검사와 환경 확인은 `tools/`에 둔다. 목적과 확인 범위가 완전히 겹치는 임시 코드만 정리한다.
  표현/수용/transport의 서로 다른 검증 계층은 유지한다.

CMake의 `BUILD_TESTING=OFF`는 단위 시험과 통합 시험용 TX/RX build를 제외한다.
Fresh build에서 라이브러리와 `actuator_demo`만 생성되는 것을 확인했다.
기존 예제 4개의 정상/거부 출력 17개를 통합 프로그램과 비교했고 명령 오류 7개/도움말도 확인했다.
단위 시험 파일은 이 정리로 추가하거나 합치지 않았다.
정리 후 normal/ASan·UBSan 각각 unit 48개와 vCAN 8개 case를 통과했고,
통합 demo/TX/RX source 3개의 static analysis와 DBC 교차 검증도 통과했다.
수신 로그의 cycle flush와 실패 trace 보존을 보완한 범위는 [실행 기록](learning/m1_steering_socketcan.md#예제시험-정리와-재검증)에 남겼다.

## Design and evidence review

[개발·학습 계획](engineering_plan.md)의 표준 참고 활동에도 기존 review와 변경 관리를
적용한다. Automotive SPICE의 추적성과 일관성 관점을 참고하며 평가 등급을 주장하지 않는다.
안전 분석의 가정·Goal 후보와 기존 requirement의 검토 연결은
[concept study](safety/concept_study.md)에 남긴다. 분석 초안을 승인된 safety concept이나
기존 requirement의 도출 근거로 소급해서 표시하지 않는다.

AUTOSAR pilot은 입력 ARXML/설정, schema/release, generator/compiler 버전, 실행 명령과
결과를 기록한다. 직접 작성한 코드와 생성·third-party 코드를 구분하고 재생성 가능성을
검토한다. 도구 채택 전에 license와 지원 환경을 확인한다. 정적 분석이나 단위 시험의
성공만으로 AUTOSAR 적합성, ISO 26262 준수, 실차 안전성 검증을 선언하지 않는다.

분석 또는 실험에서 baseline 변경이 필요하면 이유, 영향 requirement/ICD/profile/test,
재검증 범위를 기록한다. ASIL, FTTI, safe state와 같은 미결정 값을 임의로 확정하지 않는다.
학습자의 review와 자동 문서 검사는 별도 기록이며 한쪽 결과가 다른 쪽을 대신하지 않는다.
