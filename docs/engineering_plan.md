# Engineering and learning plan

Status: **계획 정의 / M1 개발 환경 실험 착수 / 표준 실습 PLANNED**. 기존 **StrataDrive Reference Baseline v0.1**을
유지한다. 이 문서는 개발·학습 방향이며 AUTOSAR 도입 완료, 안전 분석 완료 또는
표준 준수의 증거가 아니다. 학습자 검토는 **PENDING**, 기존 차량 runtime TC는 **NOT RUN**이다.
Host transport smoke는 [M1 첫 실행 기록](learning/m1_vcan_start.md),
field codec 검증은 [C++ 실행 기록](learning/m1_steering_codec.md)에 범위와 결과를 남긴다.
[Steering frame codec·DBC parser 검증](learning/m1_steering_frame_codec.md)도 Host에서 수행했다.
[Steering 수신부의 수용/sequence/freshness/timeout](learning/m1_steering_receiver.md)을
제어 가능한 시계로 Host에서 시험했다. [SocketCAN 연결](learning/m1_steering_socketcan.md)로
Steering의 독립 process 송수신/fault/wall-time timeout을 실행했다. 영속 coordinator,
application queue/overflow 주입과 차량 통합은 남아 있다.
[Brake wire 확장](learning/m1_brake_codec.md)으로 압력 field·공통 metadata·DBC/P05·vCAN을 시험했다.
[Brake 수신 수용/timeout](adr/ADR-0012-brake-receiver.md)도 Host/vCAN에서 구현·시험했다.
[Drive wire/receiver](learning/m1_drive_codec.md)의 signed torque/capability도 Host/vCAN에서 구현·시험했다.
2026-10-13 [RG-01 회생제동 포함 범위](adr/ADR-0011-regenerative-braking-scope.md)를 결정했다.
M0 v0.1의 역사적 검토는 유지하고 현재 interface/safety/profile/test 계획에 확장을 반영한다.
Drive wire는 signed 구동/회생 torque와 capability 원천 시각을 담는다.
M1 통신 검사와 M2 모델로 진행하며 물리 회생/배분 runtime은 PLANNED / NOT RUN이다.
후속 [EV-01 범위 결정](adr/ADR-0014-ev-functional-scope.md)으로 실차의 준비·주행·종료·주요
고장 과정을 Battery/BMS/power/vehicle management까지 확장했다. EV 요구/시험은 v0.3 계획이며
실행 결과는 NOT RUN이다. [ZON-01](architecture/zonal_partition.md)로 최종 Front/Rear 두 Zone,
Front 단일 coordinator와 Rear Drive/BMS gateway를 채택했다. Peer protocol/runtime은 미구현이다.
2026-10-14 [BMS 의미·wire·timing 초안](icd/bms_frame_draft.md)을 작성하고 DBC/CRC를 검사했다.
[EV 물리/frame codec과 항목별 receiver](learning/m1_bms_codec.md), Drive auxiliary age 분리도
Host에서 구현·시험했다. 기존 fixture의 EV vCAN/session·parent·relay 36개 검사도 추가했다.
M2 로컬 모델 입력은 pack 관측과 셀 전압·온도 극값을 포함한다.
M1 남은 수용 항목 이후 M2 응답 모델로 진행한다.

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
- EV-01은 BMS를 같은 계층의 Leaf로 추가하고 Zone의 gateway/vehicle management/
  allocation을 구분한다. ZON-01의 Front만 차량 전체 관리·배분을 소유하고 Rear는 local gateway다.
  BMS/power 상위 피드백은 Rear→Front 집계를 거친다.
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
[roadmap](roadmap.md#engineering-activities)에 정리한다. 현재는 M1을 시작했으며
[첫 SocketCAN/vCAN 실행](learning/m1_vcan_start.md)과
[Steering angle field codec](learning/m1_steering_codec.md)을 학습자가 재현할 수 있다.
Steering frame/DBC에 [AUTOSAR R25-11 P05 Protect/Check](learning/m1_autosar_e2e_profile5.md)를
직접 구현해 Host에서 시험했다. OS/RTE/BSW pilot과 별개의 적용 범위다.
이어서 [로컬 application 수신부](learning/m1_steering_receiver.md)를 구현·시험했다.
[SocketCAN/vCAN 연결](learning/m1_steering_socketcan.md)까지 실행했다.
영속 coordinator, queue overflow, 차량 통합 및 학습자 review는 남아 있다.

Six-frame 초안의 golden vectors → codec → vCAN application 시험까지 실행했다.
세 actuator는 공통 metadata와 수신 상태를 공유하고 Drive는 보조 freshness를 별도 검사한다.
학습자 review와 영속 coordinator/queue overflow 검토가 남아 있으며 다음 모델 작업의
TBD-02/03/04를 관련 구현 전에 검토한다. 개념 설명은 해당 작업에 필요한 만큼만
진행하고 작은 변경·review·직접 실행·결과 해석으로 이어간다.

Concept study의 남은 가정, 정상 응답 범위/jam 검출과 AUTOSAR 대응·pilot은 관련 구현과
함께 이어간다. 전체 이론 학습이나 pilot 완료를 M1 시작 조건으로 두지 않는다.
Pilot에서 발견한 제약은 해당 구현의 ICD와 도구 선택 검토에 반영하며, 변경 영향은 기록한다.
