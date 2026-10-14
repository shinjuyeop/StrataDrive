# ADR-0022: Leaf vECU의 Classic 개발 체계와 SIL 모델 경계

Date: 2026-10-14. Status: **설계·학습 방향 ACCEPTED / 코드 분리·OS/RTE/BSW pilot PLANNED / pilot 실행 NOT RUN**.
Owner: project owner. Leaf vECU의 ECU 소프트웨어는 AUTOSAR Classic의 개발 개념으로
설계하고 Steering부터 적용한다. 실제 Classic stack의 채택은 pilot 결과로 별도 결정한다.

## 배경과 결정

M1은 CAN 계약·수신 검증·P05를, M2는 Steering/Brake의 첫 functional SIL 응답을 구현했다.
현재 C++ class는 ECU 판단과 물리 응답 계산을 함께 실행한다. Classic 설계를 정리할 때는
기능 소프트웨어, 통신·OS 서비스, SIL에서 대신하는 물리 장치의 책임을 구분해야 한다.

- Leaf의 명령 처리·로컬 상태/보호 판단·출력 결정·상태 보고를 SWC/Port/Interface와
  Runnable/Event로 설계한다. Runnable의 OS Task mapping은 별도 산출물로 정의한다.
- Steering 한 경로의 설계와 실행을 확인한 뒤 Brake/Drive/BMS로 확장한다.
  C++ class 하나를 SWC 하나로 자동 대응시키거나 기능마다 SWC를 추가하지 않는다.
- 실제 조향각·압력·torque 변화, battery 에너지·센서·컨택터 응답은 SIL 물리 모델의 책임이다.
  ECU 출력 요구 → 물리 모델 → 관측 actual 경계를 정의한다. 실제 RTE/BSW 도입 전에도
  이 의미 경계를 설계·시험할 수 있다. 물리 모델을 production ECU 제어 로직으로 간주하지 않는다.
- 첫 모델의 delay/rate/saturation, protection 출력·응답, source/sequence/Epoch/validity와
  actual-only feedback 계약을 유지한다. 모델 분리로 보호 요구나 실제 반응을 생략하지 않는다.
- Application↔RTE↔BSW와 OS의 책임을 학습하며 ARXML·generator·stack의 호환성을
  확인한다. 수작업 adapter, Linux 실행 또는 P05 library만으로 Classic 통합 완료를 표시하지 않는다.

Classic의 Application/RTE/BSW 구조와 Methodology는 [AUTOSAR 공식 설명](https://www.autosar.org/standards/classic-platform/),
SWC 설계는 [R25-11 SW-C and System Modeling Guide](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_TR_SWCModelingGuide.pdf),
Runnable/OS mapping은 [R25-11 RTE Requirements](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_RS_RTE.pdf)를 참고한다.
아래 대응은 StrataDrive의 설계 초안이며 생성 도구로 검증한 AUTOSAR 설정이 아니다.

## Steering부터 적용할 경계

| 현재 구현 | Classic 설계에서 정리할 책임 / 후속 |
| --- | --- |
| `SteeringReceiver`와 `SteeringActuator::receive` | CAN decode/P05와 application의 Epoch·freshness·mode·range 검사 경계; accepted command Port와 reject/health 의미 정의 |
| `SteeringActuator::start_session` | trusted INIT 입력과 상태 초기화; Linux harness가 제공하는 session을 실제 startup/rejoin 경로에 어떻게 연결할지 정의 |
| `SteeringActuator::tick`의 monitor·목표 선택 | 주기 Runnable 후보: command snapshot, expiry/continuity/deadline 검사, normal/protection 출력 선택 |
| `move`/`advance`와 delayed demand FIFO | SIL 물리 응답 모델; 목표 입력과 modeled angle 출력, time/초기값/한계/fault policy를 명시 |
| `tick`의 Actual 생성·P05와 SocketCAN endpoint | 관측 actual/health Port와 통신 adapter를 구분; simulation 관측을 실제 sensor feedback과 혼동하지 않음 |
| 외부 clock과 single-owner 호출 | TimingEvent/Task mapping 초안의 검증 환경; logical 10 ms와 실제 OS scheduling을 구분하고 M3에 측정 |

현재 위치는 [Steering 구현](../../vecu/steering/steering_actuator.cpp),
[수신부](../../interfaces/steering/steering_receiver.hpp),
[M2 모델 시험](../learning/m2_steering_model.md)이다. 이번 결정은 코드 이동이나 동작 변경을 포함하지 않는다.
SWC 수/Port type/Runnable 순서·동시성, actual sensor schema, RTE/BSW 연결은 후속 상세 설계다.
현재 `tick`은 여러 책임을 함께 실행하므로 위 행별로 독립 Runnable이 이미 존재한다고 보지 않는다.

## 다른 계층과 기술 선택

[ADR-0021](ADR-0021-central-coordination-and-parallel-zones.md)의 Central 단일 조정 기능과
대등한 Front/Rear Zone, 담당 Leaf, CAN FD 계약과 피드백 경로를 유지한다.
Central/Zone의 Linux 구성을 Classic 또는 Adaptive 적용으로 표시하지 않는다.
QNX 전환이나 Adaptive stack 도입은 이번 결정에 포함하지 않는다.

Central–Zone의 기본 통신 계획은 DDS이며 Zenoh를 TBD-05의 비교 후보로 추가한다.
M4에 같은 의미 계약·입력 부하·단절/재연결 조건으로 비교하고 M5 runtime 착수 전에
채택 ADR과 schema/ICD/배포/시험 영향을 기록한다. 비교 활동은 PLANNED이며 Zenoh 채택은 미결정이다.
기존 IF-DDS 이름과 의미 계약을 유지하고 transport 선택만으로 freshness/Epoch/local protection을 대체하지 않는다.

## 실행 순서와 검토 근거

1. M2의 Drive/Battery/BMS/Power 구현과 함께 Steering의 입출력·기능/물리 모델 경계를 정리한다.
2. Steering의 SWC/Port/Runnable/Event 및 Task mapping을 작성하고 기존 정상·fault 시험에 연결한다.
3. M2–M4의 작은 pilot에서 호환되는 release/ARXML/RTE/BSW/OS/virtual target을 선정한다.
   [도입 절차](../engineering_plan.md#autosar-adoption-path)를 따라 설정·생성·build·I/O 실행을 기록한다.
4. 도구·license·Host/Jetson 호환성 근거로 stack의 채택·보류를 결정한다.
   이후 Leaf 확장과 코드 분리는 각 변경의 정상·timeout·invalid input·restart 회귀로 확인한다.

SYS 요구사항·CAN wire·32개 requirement/29개 system TC의 수용 조건은 이번 결정으로 바꾸지 않는다.
기존 Host unit/vCAN 결과는 유지하며 Classic pilot, Target timing과 full vehicle TC는 NOT RUN이다.
학습자의 설계 설명·직접 재현 review는 PENDING이다.
