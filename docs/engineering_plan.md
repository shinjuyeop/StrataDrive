# Engineering and learning plan

Status: **개발 방법·학습 계획**. 현재 구현/수용·OPEN은 [project_status](project_status.md),
단계/TBD는 [roadmap](roadmap.md), M6 범위 종료는 [검토표](m6_exit_review.md)를 따른다.
표준 준수·AUTOSAR 전체 도입·개인 학습 수용은 이 문서로 승인하지 않는다.

## Project objective

StrataDrive는 Zonal E/E Architecture의 차량 software를 SIL에서 설계·구현·검증하며,
각 결정의 이유와 한계를 직접 설명하는 프로젝트다. Central Vehicle Compute,
Zone Controller, Leaf ECU의 책임을 이해하고 통신·제어·timing·fault·AI를 단계적으로
통합한다. 같은 요구사항을 서로 다른 compute budget에서 만족하는지도 비교한다.

현업의 기술과 산출물을 학습 대상으로 삼는다. 한 기능마다 요구사항, interface,
설정 또는 코드, 정상·fault 시험, 결과와 변경 근거를 연결한다. 진도는 파일 수보다
학습자가 설계를 설명하고 시험을 재현할 수 있는지로 확인한다.

사용자가 선택한 방향은 **제한된 ODD에서 운전자 개입에 의존하지 않는 자동 주행 SIL**이다.
운전자 인계를 정상 주행이나 fault 대응의 전제에 넣지 않는다. 기존 Reference ODD와
M0 계약을 유지하며, 시스템이 수행할 물리적 보호 동작과 검증 범위는 후속 분석으로 정한다.
[운전자 역할 가정](safety/concept_study.md#driver-role-assumption)은 반영했으며 상세 안전 평가는 미완료다.

## Architecture baseline

- Host x86 Ubuntu는 CARLA, sensor/plant, scenario, fault orchestration과 결과 평가를 맡는다.
- Target은 Jetson AGX Thor 또는 Jetson Orin NX 한 대다. 두 보드는 독립적인 배포 대안이다.
- Target 내부 경로는 Central Vehicle Compute → Virtual Ethernet / DDS → Zone Controller
  → SocketCAN / vCAN → Steering / Brake / Drive vECU다.
- EV-01은 BMS를 같은 계층의 Leaf로 추가하고 Central의 별도 vehicle management/allocation과 각 Zone gateway를 구분한다.
  ZON-01 v0.5에서 Central이 차량 전체 관리·배분을 소유하고 두 Zone은 local gateway다.
  BMS/power 상위 피드백은 Rear→Central 집계를 거친다.
- vECU의 actual actuator feedback이 bridge를 거쳐 Host Plant Adapter로 전달된다.
  Plant Adapter만 CARLA ego actuation을 적용한다. Command를 actual로 대체하지 않는다.
- Classical driving을 검증한 뒤 perception과 Learned Planner를 통합한다.
  AI 출력은 Safety Supervisor와 Classical Controller 경로를 거친다.

정확한 경계는 [system architecture](architecture/system_architecture.md),
[deployment](architecture/deployment_architecture.md), [ICD](icd/interface_overview.md)를 따른다.
이 구성은 프로젝트의 Reference architecture다. 실제 차량마다 ECU 배치와 기능 분할이
다르므로 모든 양산차의 공통 구성으로 일반화하지 않는다.

## Standards and application scope

| 기준 | 프로젝트에서 수행할 활동 | 현재 범위와 상태 |
| --- | --- | --- |
| AUTOSAR Classic / Methodology | Leaf ECU 소프트웨어의 SWC, Port, Interface, Runnable, Event, ECU/OS Task mapping 설계; SIL 물리 모델 경계 구분; ARXML, RTE/BSW 설정·생성·통합 실습 | ADR-0022로 개발 방향 채택, Steering부터 Brake/Drive/BMS로 확장; 전체 stack/release/generator/target 미선정; Trampoline Host OS 파일럿 구현, RTE/BSW·Target NOT RUN |
| Automotive SPICE 4.0 | 요구사항·설계·검증의 일관성, 추적성, 변경 영향과 review 기록 | 개발 과정 점검에 참고; capability level 평가나 전체 process 적용을 주장하지 않음 |
| ISO 26262 | Item Definition → HARA → Safety Goal → Functional Safety Concept → 안전 요구·설계·검증의 연결 학습 | Concept study 초안부터 시작; ASIL 미평가, 전체 lifecycle 준수·인증 범위 아님 |
| ISO 21448 / SOTIF | 기능 사양·인식·판단의 한계와 triggering condition, scenario coverage 검토 | M10/M11의 AI 통합에 연결할 계획; ODD 확장은 별도 baseline 변경 |

AUTOSAR는 architecture와 Methodology를 함께 제공한다([공식 설명](https://www.autosar.org/standards/classic-platform)).
Automotive SPICE는 process reference/assessment model이며 개발 순서를 규정하는 lifecycle이
아니다([PAM 4.0, 3.3.4](https://vda-qmc.de/wp-content/uploads/2023/12/Automotive-SPICE-PAM-v40.pdf)).
ISO 26262의 concept 활동은 [Part 3](https://www.iso.org/standard/68385.html),
기능 불충분성에 관한 SOTIF의 범위는 [ISO 21448](https://www.iso.org/standard/77490.html)을 참고한다.
이 표의 프로젝트 배치는 학습 계획이며 표준이 지정한 milestone 순서가 아니다.

## Model-Based Design path

Status: **M6 Python 모델/MIL 범위 종료 / M8 C++ 동등성·통합 NOT RUN**.
[ADR-0052](adr/ADR-0052-model-based-design-development-path.md)로 MBD를 M6–M8에 추가한다.
기존 M4 coordinator/Zone 통합과 M3 예외 분석을 계속하며 MBD 때문에 구조나 milestone 번호를 바꾸지 않는다.
기존 actuator/Battery/Power C++ plant를 활용하고 M6 차량 운동·제어 모델을 추가한다.
제어 모델에서 구현으로 이어지는 새 MBD workflow의 완료 증거는 별도로 남긴다.

첫 대상은 **Central 종방향 속도 제어기**다. 입력은 validated 목표 속도와 원천 시각/유효성을 갖는 actual 속도(m/s),
출력은 bounded acceleration demand(m/s²)다. 기존 allocation→각 Zone→Leaf→actual feedback 경로를 사용한다.
속도 오차에서 PI/PID의 각 항이 필요한 이유를 설명하고, 적분/미분 이산화·anti-windup·saturation·출력 변화율과
허가 상실/새 INIT의 상태 전환을 설계한다. 구체 구조와 tuning은 TBD-11, 모델/도구·동등성 설정은 TBD-16에서 결정한다.

| 배치 | 작업 | 남길 산출물 |
| --- | --- | --- |
| M4–M5 준비 | 제어/plant·실행 경계, 도구/Host harness 연동 검토 | 기존 ICD와 연결한 입출력/단위·validity·source/clock·출력 허용 조건, 도구 결정 |
| M6 | Simple Vehicle 기반 종방향 plant와 실행 가능한 제어 모델, MIL 시험 | 제어식·가정·sample time/solver·parameter와 고정 scenario/seed·성능/제약 결과 |
| M8 component | 모델 기준 C++ 구현과 공통 vector 동등성 시험 | revision별 tick 출력/관련 내부 상태·mode/validity·fault/INIT 비교와 허용 오차 |
| M8 integration | 실제 Central/Zone/Leaf와 차량 SIL 연결, M7 CARLA mapping 대조 | 기존 주행·fault·timing 시험에 연결한 결과, MIL 가정과 실제 통합 차이 |
| 선택 후속 pilot | 한 제어 component의 자동 코드 생성 가능성 평가 | license/지원 버전·재생성·adapter·Host/Target·동등성/정적 검사 근거 |

MIL(Model-in-the-Loop)은 제어 모델과 plant를 함께 실행해 설계를 검증한다.
모델/코드 비교는 동일한 timestamped input vector와 초기 상태·parameter·sample time으로 모델과 컴파일한 C++를
각각 실행한다. 동일한 production 함수를 모델에서도 호출하는 self-comparison은 피한다.
Closed-loop 추종 성능과 tick별 수치/상태 동등성은 각각 판정한다. 같은 모델과 비슷하게 동작한다는 사실만으로
차량 요구사항 충족이나 Target timing을 선언하지 않는다.

첫 MIL/동등성 case는 속도 유지·증가/감소 reference·가감속/slew 제한·지속 saturation 후 적분 회복·정지 부근과
stale/invalid 속도·permission 상실·새 INIT다. Sample time/step·multirate 순서·numeric type·NaN/invalid 처리와
출력/state 허용 오차는 결과를 보기 전에 고정한다. 기존 scenario/성능 수치 변경은 requirement revision 절차를 따른다.
MBD 시험의 자세한 범위는 [검증 계획](test-plan/verification_strategy.md#mbd-model-and-code-verification)에 둔다.

M6 도구는 [ADR-0063](adr/ADR-0063-simple-vehicle-and-longitudinal-mil.md)의 Python으로 결정했다.
M8 C++ harness/동등성 및 선택적 generator/license·재생성은 후속(TBD-16)이다.
먼저 모델 설계/검증과 수작업 C++ 비교를 수행하고 자동 생성은 선택 후속 pilot으로 둔다.
AUTOSAR RTE/BSW 생성과 제어 알고리즘 생성은 따로 기록한다. PIL/HIL·전체 Leaf 재작성은 추가 확정 범위에 넣지 않는다.

## AUTOSAR adoption path

[ADR-0022](adr/ADR-0022-leaf-classic-development-methodology.md)로 Leaf의 Classic 개발 체계를
채택한다. 이는 설계·학습 방향이며 Classic stack의 실제 도입 결정과 구분한다.
Steering에서 명령 처리·로컬 보호·출력/상태 보고의 ECU 소프트웨어와
delay/rate/saturation을 계산하는 SIL 물리 모델의 입출력 경계를 먼저 정리한다.
[ECU/SIL 경계 정리](learning/m2_execution_boundaries.md)에서 ECU phase와 외부 물리 실행을 분리했고,
[M3 첫 실행](learning/m3_steering_timing.md)에서 Steering의 별도 실행·감시와 계측을 연결했다.
후속 [다중 주기 실행](learning/m3_multirate_runtime.md)은 Brake/Drive/BMS·Power와 실제 SocketCAN RX를 연결했다.
이는 Host runnable/port 경계의 실험이며 생성된 RTE/BSW 또는 AUTOSAR OS 실행으로 보지 않는다.
Steering의 작은 설계·pilot을 확인한 뒤 Brake/Drive/BMS에 확장한다.

먼저 Steering 기능의 입력·출력, 내부 동작과 주기 실행을 기존 ICD에 대응시킨다.
SWC/Runnable과 OS Task를 같은 개념으로 취급하지 않고, RTE가 연결하는 Application과
BSW의 책임을 구분한다. OS는 BSW의 일부다. Central Vehicle Compute의 Linux/DDS 구성을
AUTOSAR Adaptive 적용으로 간주하지 않으며 Adaptive 도입은 현재 확정 범위가 아니다.

1. 공식 Classic Workflow Example과 Methodology를 읽고 필요한 산출물의 관계를 정리한다.
2. 사용 가능한 공개 구현체나 정식 사용 가능한 도구를 조사한다. 현재 확보한 상용
   AUTOSAR 도구·BSW license는 없다. 서로 다른 구현체를 호환되는 한 stack으로 가정하지 않는다.
3. 선택 후보의 작은 OS 예제로 Task/Event/Alarm의 설정과 실행을 확인한다.
   OS 실행만 성공한 결과는 RTE/BSW 통합과 구분한다.
4. 한 release에서 호환되는 SWC/ARXML → RTE/BSW 설정·생성 → build → 실행 → I/O 시험을
   재현한다. 수작업 RTE 모형이나 Linux thread 예제는 그 범위대로 표시한다.
5. 실제 통합 가능성과 학습 비용을 검토하고 ADR로 채택·보류를 기록한다.
   채택 시 영향 requirement/ICD/deployment/test를 검토한 뒤 관련 milestone에 반영한다.

도구 선정 전 확인할 항목은 다음과 같다.

| 확인 항목 | 필요한 근거 |
| --- | --- |
| Release / schema / generator | AUTOSAR release, ARXML/XSD, RTE/BSW generator 간 호환과 재현 가능한 생성 예제 |
| OS / BSW / virtual target | 필요한 모듈의 실제 제공 범위, virtual driver와 대체한 hardware 기능 |
| Host / Target | x86 Linux와 ARM64 Jetson의 build/runtime 지원을 각각 확인한 결과 |
| Communication | 기존 CAN FD application contract, SocketCAN/vCAN 연결, freshness/CRC/sequence 처리의 호환성 |
| Toolchain / license | compiler·언어·버전·배포 조건, 생성 코드와 third-party 코드의 관리 방법 |
| Acceptance | 명령 수신·actual 출력, 주기 실행, timeout/invalid input을 확인한 로그와 실행 절차 |

Toolchain은 TBD-11, Target 지원은 TBD-09, CAN contract는 TBD-01과 연결해 검토한다.
Host에서 수행하는 독립 실습은 target 배포 완료로 표시하지 않는다. Pilot 때문에 vECU를
Host로 옮기거나 별도 MCU를 추가하려면 deployment 변경을 먼저 검토한다.
Pilot이 보류되면 사유를 남기고 현재 Linux vECU 계획으로 진행할 수 있다.
AUTOSAR 구현체를 사용하지 않은 구성의 명칭과 검증 범위는 그대로 유지한다.

Central/Front/Rear는 현재 Linux 계획을 유지한다. QNX 전환은 이번 Leaf 개발 체계의 범위가 아니다.
Central–Zone은 DDS를 기본 계획으로 두고 Zenoh를 M4 비교 후보로 추가한다(TBD-05).
M5 runtime 시작 전 transport/도구를 결정하고 ICD/배포/시험에 반영한다.
CAN FD 경로와 application의 Epoch/freshness/timeout/local protection 책임은 유지한다.

## Functional safety learning

[Concept study](safety/concept_study.md)에서 차량 수준 기능과 경계를 먼저 정리한다.
Steering vECU는 구현 학습 단위이고, HARA는 해당 기능의 차량 동작과 운행 상황을
함께 다룬다. Fault 이름만 나열한 목록으로 위험 분석을 완료했다고 보지 않는다.

첫 학습 순서는 Item Definition 초안 검토 → 한 hazardous event의 가정과 영향 분석 →
Safety Goal 후보 → 필요한 보호 책임과 대응 시간 → 기존 요구사항·시험의 coverage 검토다.
ASIL, safe state, FTTI는 근거 없이 확정하지 않는다. 기존 SYS-SAFE 요구사항도
HARA에서 도출됐다고 소급해서 표시하지 않는다. 상세 설계 단계에서는 필요한 범위의
FMEA/FTA를 학습하며 fault 원인과 보호 수단의 실패 가능성을 검토할 계획이다.

기존 100 ms는 마지막 valid RX 기준 **검출 상한**이다. FTTI나 차량 정지 시간으로
대체하지 않는다. Fault onset, 검출, 보호 출력 선택, actual actuator response와 차량
거동을 구분하고 근거가 생긴 구간만 검증한다. CARLA tick gate는 simulation containment다.

ISO 자료는 공개 개요를 바탕으로 학습 범위를 정하는 데 참고했다. 조항별 준수 평가를
수행한 상태가 아니다. 향후 상세 표준 분석에는 해당 판의 정식 문서와 적용 범위 검토가 필요하다.

## Work products and evidence

| 산출물 | 위치 / 관리 방법 |
| --- | --- |
| 프로젝트 목표와 적용 범위 | 이 문서; 후속 기술 채택 결정은 ADR에 근거와 대안을 기록 |
| Item Definition / HARA 학습 초안 | [concept study](safety/concept_study.md); 미결정 가정과 학습자 검토 상태를 유지 |
| System requirement / timing / safety 계약 | [requirements](requirements/system_requirements.md); 기존 ID와 revision 체계를 유지 |
| Component / Interface / 배포 설계 | [architecture](architecture/system_architecture.md), [ICD](icd/interface_overview.md) |
| 설정·생성·구현 기록 | 관련 milestone에서 추가; 입력 설정, 도구 버전, 명령, 생성 결과와 직접 작성 코드를 구분 |
| Test와 결과 | [verification strategy](test-plan/verification_strategy.md), [traceability](test-plan/traceability.md); 실제 실행 후 Result ID 부여 |
| 이해와 review 기록 | [learning](learning/README.md); 설명하지 못한 부분과 재현 결과를 함께 기록 |

새로운 안전 분석은 기존 요구사항·시험에 대한 **검토 연결**부터 시작한다. Safety Goal과
추가 요구사항의 정의·승인 전에는 공식 traceability에 확정된 도출 관계를 넣지 않는다.
변경이 필요하면 rationale, 영향, 재시험 범위를 기록하고 baseline revision으로 관리한다.

## Next learning cycle

현재 다음 단위와 선행 조건은 [M7 최초 접속 준비](m6_exit_review.md#다음-한-단계--m7-최초-접속-계약과-환경-확인)를 따른다.
각 단계에서 필요한 개념→구현/설계→검증→설명으로 진행하고, 개인 이해 확인은
[학습 원칙](learning/README.md)에 별도 기록한다. 이전 단계의 상세 이력은 각 learning/evidence와
[품질 이력](quality_policy.md)에 남긴다.

## Hosted OS pilot update

2026-10-18 [Trampoline Steering 파일럿](learning/m3_rtos_pilot.md)을 별도 opt-in build로 구현했다.
GOIL/OIL 2.5로 생성한 실제 OS Task/Event/Alarm/Resource와 기존 ECU를 연결한다.
확인 target은 Host x86_64 POSIX다. Classic R25-11 적합성·ARXML/RTE/BSW 생성·Jetson 배포는 NOT RUN이다.
기존 Linux vECU 배포 계획을 유지하며 이 결과로 OS stack 전체를 채택하지 않는다.
[ARM64 교차 빌드·Host RT 사전 점검](adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)도 추가했다.
ARM64 ELF 생성과 CPU/loader/library 확인은 PASS이며 실제 보드의 POSIX stack·IPC·driver·timing은 후속이다.
후속 [native FIFO 실행](learning/m3_native_fifo.md)은 owner별 설정·startup 취소·실제값·호출 thread 복원을 연결했다.
일반/FIFO 비교와 sanitizer 회귀의 실패까지 보존하며 Trampoline OS·Target 정시성 및 전체 M3 수용과 구분한다.

2026-10-19 [hosted timer 후속](adr/ADR-0043-hosted-monotonic-timer-and-placement.md)은 relative 누적 지연을
absolute timerfd로 수정했다. 동일 조건 48회의 기능·추가 timing 판정을 분리하고 native FIFO 102회와
별도 부하 진단·timer 정지 주입을 검사했다. Native 원래 실패의 커널 원인·Target 실행과 다른 Leaf OS 확장은 후속이다.
