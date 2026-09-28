# Functional safety concept study

Status: **DRAFT / 학습자 검토 PENDING**. Item Definition과 HARA 학습을 시작하기 위한
초안이다. HARA 완료, Safety Goal 확정, ASIL 할당 또는 Functional Safety Concept 승인을
뜻하지 않는다. 기존 M0 요구사항·scenario·시험의 baseline은 변경하지 않는다.
운전자 역할의 학습 방향은 사용자 선택을 반영했으며 상세 분석의 이해 확인은 아직 PENDING이다.

## Item definition draft

검토할 Item은 **제한된 운행 조건에서 지정 route와 target speed를 추종하는 차량의
횡방향·종방향 제어 기능**이다. 이 명칭과 경계는 학습용 초안이며 학습자 검토가 필요하다.
Steering vECU 하나는 이 기능을 구성하는 구현 단위다.

| 항목 | 기존 baseline 또는 검토할 가정 |
| --- | --- |
| 의도한 기능 | 차량 상태와 route를 이용해 trajectory와 vehicle-level command를 생성하고, Zone Controller와 vECU를 거쳐 차량 거동에 반영 |
| Software 범위 | Central Vehicle Compute의 planning/control/safety, Zone Controller, Steering/Brake/Drive vECU와 이들 사이의 통신 |
| 외부 입력과 plant | Sensor/vehicle state 및 route 입력; actuator model의 actual response가 Host Plant Adapter를 통해 CARLA plant로 전달됨 |
| SIL 시험 환경 | CARLA, Host orchestrator, fault injection, logger는 시험 환경의 역할; simulator tick gate를 실제 차량의 안전 수단으로 전제하지 않음 |
| 운행 조건 | 맑은 낮, 포장도로, 단일 ego, 신호등 없는 직선·완만한 곡선, 0–40 km/h; 정확한 route/geometry는 TBD-07 |
| 기존 제외 범위 | 복잡한 traffic interaction, 교차로, 야간/악천후, 후진/parking, lane change, obstacle avoidance 성능 |
| 운전자 역할 | 제한된 ODD에서 운전자 개입에 의존하지 않는 자동 주행 SIL을 학습; 정상 주행과 fault 대응에 운전자 인계를 전제하지 않음 |
| 탑승자와 주변 사람 | 탑승 유무, 상해·노출 조건과 주변 사람의 피해 회피 가능성은 미정; 운전자에게 의존하지 않는다는 선택으로 무탑승이나 피해 부재를 가정하지 않음 |
| 물리적 특성 | Steering/Brake/Drive dynamics, failure response와 vehicle mapping은 TBD-02/03/06/07 |

근거는 [Reference ODD](../requirements/system_requirements.md#reference-odd),
[system architecture](../architecture/system_architecture.md), [ICD](../icd/interface_overview.md)다.
표의 미정 가정은 안전 분석을 위한 검토 질문이다. 실제 운행 조건이나 새로운 구현 계약으로
승인한 내용이 아니다. 결정이 필요한 설계 변경은 [TBD register](../roadmap.md#open-m0-decisions)와
requirement revision에 연결한다.

## Driver role assumption

| 날짜 | 선택 / 근거 | 상태와 영향 |
| --- | --- | --- |
| 2026-09-28 | 사용자가 운전자 개입에 의존하지 않는 제한 ODD의 자동 주행 SIL 방향에 동의 | 학습 가정 반영; HARA/FSC 승인과 구현·시험 완료는 아님 |

정상 주행은 정해진 route와 target speed를 시스템이 추종하는 것으로 공부한다.
선택한 fault 사례에서도 사람이 즉시 조향·제동을 인계받는다는 가정으로 위험을 줄이지 않는다.
운전자 개입에 기대지 않고 가능한 시스템 대응을 분석하되 모든 fault에서 안전 정지나
계속 주행이 가능하다고 미리 가정하지 않는다.

Host의 시험 시작·중단과 simulator tick gate는 시험 환경의 제어다. 이를 차량의
운전자 인계나 물리적 fallback 성공으로 계산하지 않는다. 기존 ODD는 유지하며,
ODD 이탈의 감지와 대응은 후속 안전 분석에서 다룰 질문으로 남긴다.

이 선택만으로 Level 4, Controllability 등급, ASIL 또는 FTTI를 확정하지 않는다.
각 운행·피해 조건과 가용 actuator를 검토하고 판단 근거를 남긴다.
ODD와 fallback을 함께 다루는 배경은
[NHTSA ADS 2.0의 ODD / Fallback 항목](https://www.nhtsa.gov/sites/nhtsa.dot.gov/files/documents/13069a-ads2.0_090617_v9a_tag.pdf)을
참고한다. 이 자료는 학습 참고 자료이며 프로젝트의 자동화 등급 판정 근거가 아니다.

## Hazard analysis exercise

아래는 분석 질문을 구체화한 예시이며 완성된 HARA가 아니다. 새로운 Scenario ID,
Requirement ID, Test ID를 부여하지 않는다. 차량 수준 오동작과 운행 상황을 먼저 보고,
ECU fault는 이후 원인·검증 시나리오에 연결한다.

| 운행 상황 | 검토할 차량 수준 오동작 | Hazardous event 후보 / 예상 피해 | 기존 계약과의 검토 연결 |
| --- | --- | --- | --- |
| 완만한 곡선에서 route 추종 | 필요한 조향을 유지하지 못하거나 의도하지 않은 조향이 발생 | 경로를 벗어나 도로 경계와 충돌해 상해가 발생할 가능성; 경계·탑승자 조건은 미정 | SYS-COM-001/003, SYS-SAFE-001/003; TC-COM-001, TC-CTRL-001, TC-SAFE-001 |
| 감속을 요청하는 구간 | 이전 추진 요구가 지속되거나 의도하지 않은 가속이 발생 | 의도한 감속 실패와 경로 이탈·충돌 가능성; 거리·도로 형상·피해 조건은 미정 | SYS-SAFE-004; F03, TC-COM-003; actual torque 감소의 근거는 TBD-03 |
| 경로 추종 중 감속이 필요한 구간 | 필요한 제동력을 만들지 못함 | 과속 상태의 경로 이탈·충돌 가능성; 구체적인 상황과 피해 조건은 미정 | SYS-SAFE-001; TC-SAFE-001, TC-CTRL-001; actuator availability와 반응은 TBD-03/06 |

각 후보의 평가 입력, 분류 근거와 ASIL은 **미평가**다. 다음 검토에서는 상해 심각도
(Severity), 운행 상황에 대한 노출 (Exposure), 피해 회피 가능성 (Controllability)을
구분해 학습한다. Exposure를 fault 발생 확률과 혼동하지 않는다. 실제 차량의 가정을
정하지 않은 상태에서 ASIL을 확정하거나, SIL이라는 이유로 차량 위험을 QM으로 분류하지 않는다.
평가 관점의 설명은 [NXP/Freescale의 기초 교육자료](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/ftf2015/54/1/EUF-ACC-T1555.pdf)를
함께 참고한다. 이 자료는 이전 판의 개념 설명이며 실제 분류에는 적용할 판의 상세 표준과 가정 검토가 필요하다.

위 후보는 초기 학습 사례일 뿐 전체 위험 coverage가 아니다. F01은 Steering **feedback**
상실이므로 실제 조향 기능 상실과 동일하지 않다. TC-COM-001의 검출·gate 성공만으로
첫 hazardous event가 방지됐다고 결론 내리지 않는다. 필요하면 별도의 actuator fault와
차량 반응 시험을 설계하고 기존 baseline과의 변경 관계를 검토한다.

## First exercise: steering fault comparison

첫 질문은 **곡선 주행 중 의도한 조향을 유지하지 못할 때, 운전자 도움 없이 시스템이
무엇을 관측하고 어떤 대응을 검토할 수 있는가?**다. 아래는 기존 계약을 읽는 사고실험이며
새 fault scenario나 acceptance를 확정한 것이 아니다. 각 사례는 나머지 통신 경로가
동작한다고 가정해 원인을 구분한다. 실제 시험의 시작 조건·주입 시점·지속 시간은 미정이다.

| 사례 | 관측 가능한 차이 | 기존 계약 / 첫 검출 주체 | 남은 분석 |
| --- | --- | --- | --- |
| Steering command loss | 새 유효 command가 도착하지 않음; vECU task와 actual 발행은 계속될 수 있음 | Steering vECU가 last-valid command age 감시; SYS-COM-003 / SYS-SAFE-003의 local 검출·보호 | timeout 이후 Steering 물리 출력과 반응은 TBD-03; 실제 steering angle과 차량 거동을 따로 확인 |
| Steering feedback loss | Zone이 새 유효 actual을 받지 못함; command 전달과 실제 조향 기능은 계속될 수도 있음 | F01, Zone과 Host의 actual stream 감시; TC-COM-001/005의 검출·containment | 관측 상실만으로 actuator jam을 단정할 수 없음; Host gate 이후의 물리 거동은 이 시험으로 입증되지 않음 |
| Steering actuator jam | command와 feedback의 통신은 정상이어도 actual angle이 요구 변화에 따라 움직이지 않음 | 기존 fault architecture의 Steering vECU demand↔actual residual 검토; STEERING_TRACKING_FAULT | 정상 지연·saturation과의 구별, threshold/dwell/model은 TBD-03/04; 통신 timeout만으로 검출하지 못할 수 있음 |

Actual angle이 같다는 사실만으로 stale sample이라고 판단하지 않는다. Jam 상태에서도
새로운 model state sample의 source time/sequence는 진행할 수 있다. 반대로 bridge가
과거 actual의 metadata만 갱신한 값은 새 관측이 아니다. 통신의 freshness와 actuator의
기능 상태를 구분하는 것이 이 비교의 학습 목표다.

Steering actuator jam 사례를 차량 위험과 연결하면 다음 순서로 검토할 수 있다.

1. **상황:** S02의 완만한 곡선·30 km/h 조건을 사고실험의 출발점으로 삼는다.
   S02 자체는 fault 없는 정상 시험으로 유지한다. 필요한 조향각 변화와 jam 시점은 아직 정하지 않는다.
2. **오동작과 위험:** 필요한 조향이 변해도 actual angle이 고정되면 경로 이탈과 충돌로
   이어질 수 있다. Jam angle이 현재 요구와 같다면 즉시 residual이 커진다고 가정할 수 없다.
3. **검출:** 수신 성공·CRC·sequence 검사와 demand↔actual 반응 검사를 구분한다.
   100 ms stream loss 검출 상한을 jam 검출 deadline으로 복사하지 않는다.
4. **대응 검토:** Steering, Brake, Drive 중 실제로 제어 가능한 기능과 관측 가능한 값을
   확인한다. 추진력 감소·제동 등의 후보는 차량 안정성·도로 경계·actual response로 검토하며
   특정 steering angle, brake pressure나 정지 시간을 지금 확정하지 않는다.
5. **검증의 빈틈:** TC-CTRL-001의 jam/dynamics 관측은 검토 연결점이다. 이것만으로
   jam 검출 시간이나 위험 회피가 입증되지는 않는다. 필요한 추가 요구·시험은 별도 revision으로 검토한다.

이 분석의 근거는 [CAN ICD](../icd/can_icd.md),
[fault architecture](../architecture/fault_diagnostics_architecture.md),
[보호 계약](../requirements/safety_requirements.md),
[기존 TC](../test-plan/verification_strategy.md)다. 분석 메모는 작성했지만 실행 결과는 NOT RUN이다.

다음 학습은 [정상 Steering 응답](../learning/steering_response.md)이다. 사용자가 설명한
정상 지연의 오검출 가능성을 출발점으로 Dead time, Rate limit, Angle saturation을 구분한다.
상세 이해 확인과 runtime 검증 상태는 별도로 유지한다.

## From analysis to safety concept

| 다음 산출물 | 검토할 질문 | 현재 상태 |
| --- | --- | --- |
| HARA 평가 기록 | 어떤 운행·피해 가정이 있고 각 평가의 근거는 무엇인가? | PLANNED; 가정과 분류 미확정 |
| Safety Goal | 분석한 위험을 줄이기 위해 차량 수준에서 무엇을 달성해야 하는가? | PLANNED; 목표와 ASIL 미확정 |
| Functional Safety Concept | 필요한 보호 동작과 책임은 무엇이며 가용 actuator로 실현 가능한가? | PLANNED; safe state와 전환 조건 미확정 |
| 안전 요구사항과 설계 | 검출·대응 시간과 실패 처리의 근거를 어느 Component에 배분할 것인가? | 기존 계약과 비교 예정; 신규 normative statement 없음 |
| 검증 계획 | 어떤 fault, 환경, 관측값으로 동작과 한계를 확인할 것인가? | 기존 TC와의 coverage 검토 예정; runtime NOT RUN |

기존 SYS-SAFE 요구사항은 M0의 SIL 보호 계약이다. 위 학습 분석에서 도출된 요구사항으로
소급해서 표시하지 않는다. Goal/요구사항을 정의할 때 normative statement는 영어,
rationale·가정·acceptance 설명은 한국어로 작성하고 기존 ID/revision 정책을 적용한다.

## Timing and evidence boundary

기존 100 ms 계약은 마지막 valid RX부터 검출까지의 상한이다. Fault onset과 마지막
valid RX가 같은 시각이라는 가정도 검토가 필요하다. FTTI는 현재 미정이며 100 ms를
그 값으로 복사하지 않는다. 검출·반응과 FTTI의 관계는
[TI의 functional safety 설명](https://www.ti.com/lit/fs/sffs222/sffs222.pdf)을 참고한다.

분석에서는 fault onset → detection → protection output → actual actuator response →
vehicle behavior를 구분한다. 각 구간의 clock, 관측 방법과 model 한계를 기록하고,
가용 actuator에 맞는 대응이 가능한지 검토한다. `FAIL_SAFE`라는 이름이나 zero-propulsive
target 선택만으로 안전 정지 또는 위험 회피가 증명되지 않는다.

Actual feedback 상실 시 CARLA의 다음 tick을 보류하는 기존 계약은 유지한다.
이는 시험을 멈추는 containment 증거다. 그 이후 차량의 물리적 거동을 검증하려면
해당 거동을 관측할 수 있는 별도 시험 설계가 필요하다. Raw command fallback으로
기존 계약을 우회하지 않는다.

## SOTIF follow-up

M10/M11에서는 E/E malfunction뿐 아니라 인식·판단의 성능 한계로 잘못된 trajectory가
만들어지는 조건을 검토한다. [ISO 21448](https://www.iso.org/standard/77490.html)의
기능 불충분성 관점을 참고해 입력 조건, 한계, triggering condition과 검증 scenario를
정리할 계획이다. 새 환경이나 traffic interaction을 시험 범위에 넣으면 ODD 변경을 검토한다.

## References and review

Concept 활동의 출발점은 [ISO 26262-3:2018 공개 개요](https://www.iso.org/standard/68385.html)다.
이 문서는 프로젝트에 대한 초기 분석 질문이며 표준 조항별 준수 평가서가 아니다.
학습자는 Item 경계와 첫 사례의 가정을 설명한 뒤 review 의견을 남긴다.
운전자 역할의 방향 선택은 위 기록에 반영했다. Goal/추가 요구사항·도구·architecture 결정과
학습자의 조향 사례 설명·재현 기록은 아직 완료되지 않았다.
