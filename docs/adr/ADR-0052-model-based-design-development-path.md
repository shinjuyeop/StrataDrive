# ADR-0052: 제어 기능의 MBD 개발·검증 경로

후속 관계(2026-10-22): M6 범위 종료는 [검토표](../m6_exit_review.md), M8 동등성/자동 생성은 후속이다.

Date: 2026-10-19. Status: **개발 방향 채택 / M6 첫 Python MIL 검증 / M8 동등성·자동 생성 NOT RUN**.
2026-10-22 [ADR-0063](ADR-0063-simple-vehicle-and-longitudinal-mil.md)으로 첫 Python 도구와
M6 plant/MIL을 구현·검증했다. 아래 원래 M6→M8 책임 분리는 유지한다.
사용자 요청으로 MBD(Model-Based Design)를 기존 M6–M8 개발 계획에 추가한다.
M4 Central/Zone 통합과 M3 타이밍 예외 해소를 계속 진행하며 milestone 번호와 Reference ODD는 유지한다.

## 결정과 첫 적용 대상

제어 기능은 요구·interface → 실행 가능한 제어 모델 → MIL 검증 → C++ 구현 → 모델/코드 비교 →
차량 SIL 통합의 순서로 개발한다. 모델을 설계 기준으로 관리하고 parameter·시험·코드와 함께 변경한다.
첫 대상은 **Central 종방향 속도 제어기**다. 기존 [ICD](../icd/interface_overview.md)의
목표/실제 속도(m/s) → bounded longitudinal acceleration demand(m/s²) 경계를 따른다.
PID의 적분·미분 이산화, saturation·anti-windup·출력 변화율·허가 상실/재시작 상태를 명시한다.
선택한 PI/PID 구조와 각 항의 필요성은 모델 시험으로 설명하고 TBD-11에 기록한다.

출력은 기존 Central allocation을 거쳐 torque/pressure로 배분한다. 모델이 Leaf에 직접 CAN을 보내거나
Zone에 차량 speed controller를 추가하지 않는다. Curvature/조향 제어는 종방향 pilot 검토 뒤 M8에서 확장한다.
기존 BMS·전원 lifecycle·Zone 보호와 session/freshness 검사는 별도 owner의 책임을 유지한다.

## 단계와 산출물

| 단계 | 수행 범위 | 다음 단계에 필요한 근거 |
| --- | --- | --- |
| M4–M5 준비 | 제어 interface·단위·state/validity·원천 시각·출력 허용 조건과 model/code 실행 경계 정의 | 기존 ICD/owner와 일치하는 입출력 표, 도구 평가·재현 절차 |
| M6 초기 pilot | Simple Vehicle와 actuator 실제 응답을 반영한 종방향 plant·실행 가능한 이산 제어 모델 | 수식/가정·단위·초기 상태·sample time·solver/step·parameter revision |
| M6 MIL | 제어 모델 + plant로 reference 추종·제약·고장 입력을 구현 전 시험 | 고정 stimulus/seed·결과·판정 기준·실패 로그, 학습자의 제어식 설명 |
| M8 component | 검증한 모델과 같은 이산 의미의 C++ 제어기 구현, 공통 vector replay | tick별 출력/내부 상태·모드/유효성·거부 결정의 모델/코드 비교 |
| M8 차량 SIL | 실제 C++ 제어기를 Central→Zone→Leaf→actual→차량 feedback에 연결 | 기존 주행 scenario와 timing/fault 회귀, 모델 가정과 통합 결과의 차이 |
| 후속 선택 pilot | 한 제어 component의 자동 코드 생성과 동일 harness 비교 | 도구/license·생성 설정/버전·재생성·Host/Target 호환·코드 검사·비교 결과 |

M7 CARLA 연결은 기존 계획을 따른다. M6의 모델/가정을 CARLA mapping과 대조하고 M8에서 같은 제어기 계약으로 시험한다.
Model-based design 방법을 채택한 것이 모든 ECU/분산 통신을 모델 도구로 다시 만드는 결정은 아니다.

## 검증 계약

MIL은 모델 수준의 제어기/plant loop다. 현재 C++ 물리 모델/단위 시험의 PASS를 새 MIL 결과로 소급하지 않는다.
현재 repository의 Host SIL은 수작업 C++ ECU/물리 모델 시험을 포함한다. MBD pilot의 SIL/동등성 결과에는
어느 제어 모델과 어느 수작업/생성 코드 revision을 비교했는지 별도로 표시한다.

공통 open-loop stimulus를 모델과 코드에 각각 주고, tick별 acceleration output·적분 등 관련 내부 상태와
validity/mode/재시작 결정을 비교한다. Closed-loop 경로와 지표 비교도 수행하되 수치 차이의 원인 분석을 대신하지 않는다.
모델이 구현 함수를 호출해 자기 자신과 비교하는 시험은 독립 설계 기준의 검증으로 보지 않는다.

Sample time·실행 순서·hold/interpolation·초기 상태·parameter·numeric type·NaN 처리·saturation과
상태 reset 규칙을 고정한다. 동등성의 절대/상대 오차와 차량 추종 성능 기준은 별도로 **결과를 보기 전에** 정한다.
Floating-point 수치 비교가 필요할 수 있으며 항상 bitwise 동일성을 요구하지 않는다.
Mode/validity·허가 상실/거부 결정은 명시한 이산 계약대로 일치해야 한다.
기존 scenario·requirement threshold를 모델에 맞춰 조용히 완화하지 않는다.

첫 case는 속도 유지/증가/감소 reference·긴 saturation 뒤 회복·가감속/변화율 경계·정지 부근·
stale/invalid 속도·permission 상실·새 INIT의 controller state 초기화를 포함한다.
개별 fault의 출력 선택은 기존 safety/lifecycle 계약과 함께 검토한다. 이 pilot이 임의의 안전 정지 law를 정하지 않는다.
정확한 parameter/tolerance는 TBD-02/03/04/11/16에서 고정한 뒤 실행한다.

## 도구와 범위 관리

MBD 절차는 채택하지만 MATLAB/Simulink·자동 코드 생성 도구의 구매/설치·사용권 확보는 이번 결정에 포함하지 않는다.
Simulink와 도구 독립 실행 모델(Python 등)을 TBD-16에서 검토한다. License·Host/CI 재현성·model artifact diff·
numeric/solver 설정·기존 C++ harness 연동을 확인하고 M6 pilot 전에 선택한다.
자동 코드 생성은 선택한 제어 component에 한정한 후속 pilot이다. 지원이 없으면 수작업 C++와 모델 비교 경로를 유지한다.
도구 부재로 MBD 계획을 완료 처리하지 않는다. 선택 경로와 남은 항목을 ADR에 기록한다.

AUTOSAR RTE/BSW 생성은 이 제어 알고리즘의 코드 생성과 별도 활동이다. 생성 코드를 채택하면 원본 모델·
도구/설정·수정 금지 경계·재생성 명령·adapter·검증 증거를 관리한다. 현재 C++17/ARM64/RTOS 호환은 시험 전 가정하지 않는다.
PIL은 실제 processor 실행, HIL은 실시간 plant와 hardware 연결의 별도 검증으로 남긴다.
이번 계획이 Target/PIL/HIL이나 MBD tool qualification·안전 표준 준수의 검증 결과를 추가하지 않는다.

## 근거와 변경 영향

[MathWorks MBD 설명](https://www.mathworks.com/solutions/model-based-design.html)은 모델을 개발 과정의 기준으로
활용하고 작은 범위부터 단계적으로 도입하는 접근을 설명한다.
[공식 SIL 설명](https://www.mathworks.com/help/ecoder/software-in-the-loop-sil-simulation.html)은 Host에서 생성 코드를
실행하고 모델 결과와 수치 동등성을 비교하는 범위를 설명한다. 이 문서의 수작업 C++ 비교·단계 배치는 프로젝트 결정이다.
도구 문서를 참고한 사실은 특정 제품 채택이나 그 제품의 SIL을 실행했다는 증거가 아니다.

변경 대상은 [개발 계획](../engineering_plan.md#model-based-design-path), [로드맵](../roadmap.md),
[검증 계층](../test-plan/verification_strategy.md#mbd-model-and-code-verification)과 현재 진행 안내다.
기존 requirement32/system TC29·M3/M4 상태·C++/CAN/RTOS 실행 결과는 유지한다.
모델/코드/차량 결과는 revision·환경·입력·판정·실패를 기록한 뒤 해당 기존 TC의 부분 증거로 연결한다.
