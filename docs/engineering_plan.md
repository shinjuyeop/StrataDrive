# Engineering and learning plan

Status: **계획 정의 / 실행 PLANNED**. 기존 **StrataDrive Reference Baseline v0.1**을
유지한다. 이 문서는 개발·학습 방향이며 AUTOSAR 도입 완료, 안전 분석 완료 또는
표준 준수의 증거가 아니다. 학습자 검토는 **PENDING**, runtime 결과는 **NOT RUN**이다.

## Project objective

StrataDrive는 Zonal E/E Architecture의 차량 software를 SIL에서 설계·구현·검증하며,
각 결정의 이유와 한계를 직접 설명하는 프로젝트다. Central Vehicle Compute,
Zone Controller, Leaf ECU의 책임을 이해하고 통신·제어·timing·fault·AI를 단계적으로
통합한다. 같은 요구사항을 서로 다른 compute budget에서 만족하는지도 비교한다.

현업의 기술과 산출물을 학습 대상으로 삼는다. 한 기능마다 요구사항, interface,
설정 또는 코드, 정상·fault 시험, 결과와 변경 근거를 연결한다. 진도는 파일 수보다
학습자가 설계를 설명하고 시험을 재현할 수 있는지로 확인한다.

## Architecture baseline

- Host x86 Ubuntu는 CARLA, sensor/plant, scenario, fault orchestration과 결과 평가를 맡는다.
- Target은 Jetson AGX Thor 또는 Jetson Orin NX 한 대다. 두 보드는 독립적인 배포 대안이다.
- Target 내부 경로는 Central Vehicle Compute → Virtual Ethernet / DDS → Zone Controller
  → SocketCAN / vCAN → Steering / Brake / Drive vECU다.
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
| AUTOSAR Classic / Methodology | SWC, Port, Interface, Runnable, Event, ECU mapping과 OS Task의 관계 학습; ARXML, RTE/BSW 설정·생성·통합 실습 | Steering vECU를 첫 pilot 후보로 검토; release/stack/generator/target 미선정, 실행 NOT RUN |
| Automotive SPICE 4.0 | 요구사항·설계·검증의 일관성, 추적성, 변경 영향과 review 기록 | 개발 과정 점검에 참고; capability level 평가나 전체 process 적용을 주장하지 않음 |
| ISO 26262 | Item Definition → HARA → Safety Goal → Functional Safety Concept → 안전 요구·설계·검증의 연결 학습 | Concept study 초안부터 시작; ASIL 미평가, 전체 lifecycle 준수·인증 범위 아님 |
| ISO 21448 / SOTIF | 기능 사양·인식·판단의 한계와 triggering condition, scenario coverage 검토 | M10/M11의 AI 통합에 연결할 계획; ODD 확장은 별도 baseline 변경 |

AUTOSAR는 architecture와 Methodology를 함께 제공한다([공식 설명](https://www.autosar.org/standards/classic-platform)).
Automotive SPICE는 process reference/assessment model이며 개발 순서를 규정하는 lifecycle이
아니다([PAM 4.0, 3.3.4](https://vda-qmc.de/wp-content/uploads/2023/12/Automotive-SPICE-PAM-v40.pdf)).
ISO 26262의 concept 활동은 [Part 3](https://www.iso.org/standard/68385.html),
기능 불충분성에 관한 SOTIF의 범위는 [ISO 21448](https://www.iso.org/standard/77490.html)을 참고한다.
이 표의 프로젝트 배치는 학습 계획이며 표준이 지정한 milestone 순서가 아니다.

## AUTOSAR adoption path

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

기존 M0 종료 결과와 M1–M13 milestone을 유지한다. 단계별 연결은
[roadmap](roadmap.md#engineering-activities)에 정리한다. 다음 작은 작업의 순서는 다음과 같다.

1. Concept study의 Item 경계와 운전자·환경 가정을 학습자가 검토한다.
2. 곡선 주행에서 의도한 조향을 유지하지 못하는 사례 하나를 분석하고, feedback loss와
   실제 조향 기능 상실의 차이를 설명한다. 미결정 평가값은 그대로 남긴다.
3. Steering Command/Actual의 의미와 AUTOSAR SWC/Port/Runnable/Task 대응 초안을 그린다.
4. 사용 가능한 toolchain을 조사하고 작은 실행 예제의 범위·환경·예상 결과를 정한다.
5. M1의 기존 six-frame wire 계약, golden vectors, codec, vCAN 시험 순서로 진행한다.
   Pilot에서 발견한 제약은 구현 전에 ICD와 도구 선택 검토에 반영한다.

각 작업은 **개념 설명 → 프로젝트에 대입 → 작은 변경 → review → 직접 실행 → 결과 해석**으로
진행한다. 이번 문서 정리로 runtime 구현이나 위 학습 과정이 완료된 것은 아니다.
