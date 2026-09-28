# 학습 원칙

이 프로젝트에서는 Codex가 코드를 빠르게 생성하는 것보다 작성된 코드와
architecture를 내가 직접 이해하는 것을 우선한다. M0 문서 baseline과 개인의 이해 기록은 구분한다.
생성된 파일이나 문서 review PASS만으로 내가 설계를 설명할 수 있다고 간주하지 않는다.
이번 M0 계약은 사용자 요청의 범위/판정 기준을 반영하며 종료 검토는
[M0 baseline summary](../m0_baseline.md)에 기록한다.

각 milestone은 다음 순서로 진행한다.

1. 개념 공부
2. 요구사항 확인
3. 설계 작성
4. 작은 단위 구현
5. diff/code review
6. 직접 실행
7. fault/edge case test
8. 학습 내용 기록
9. Acceptance 기준 확인
10. 다음 milestone

**Codex가 작성한 코드를 내가 설명할 수 없다면 완료로 간주하지 않는다.**

M0에서는 4~7단계의 실행 기능 작업을 시작하지 않는다. 대신 문서 diff, 구조,
계약의 정상/오류 경로를 검토하고 configure-only 확인의 한계를 기록한다.
M1 이후 구현은 별도의 milestone 작업으로 진행한다.

## Standards learning cycle

[개발·학습 계획](../engineering_plan.md)에 따라 한 번에 작은 기능이나 fault 하나를
다룬다. 첫 대상은 Steering 경로이며, [concept study](../safety/concept_study.md)의
Item 경계와 차량 수준 위험을 먼저 이해한 뒤 interface와 AUTOSAR 개념에 연결한다.

- 개념: Item/HARA, SWC/Port/Runnable/Task 중 이번 작업에 필요한 용어와 책임을 설명한다.
- 대입: 기존 Requirement/ICD/Component에 연결하고 현재 가정과 미결정 사항을 표시한다.
- 실습: 작게 설정·생성·구현하고 diff를 검토한 뒤 직접 실행한다. 문서 작업에는 해당하지
  않는 runtime 단계를 완료했다고 표시하지 않는다.
- 해석: 예상과 실제 결과의 차이, 검증하지 못한 범위와 다음 질문을 기록한다.

표준 개념을 참고한 설계, 실제 구현체를 사용한 실행, SIL에서 관측한 결과를 구분한다.
AUTOSAR OS 예제 실행은 RTE/BSW 통합 완료가 아니며 HARA 초안 작성은 ASIL 평가나
안전 요구사항 도출 완료가 아니다. 설명하지 못한 개념은 다음 학습 항목으로 남긴다.

첫 실습 자료는 [조향 fault 비교](../safety/concept_study.md#first-exercise-steering-fault-comparison)다.
Command loss, feedback loss, actuator jam의 관측값과 검출 주체를 각각 설명한다.
특히 fresh feedback이 계속 도착해도 actuator가 고장일 수 있는 이유를 자신의 말로 남긴다.
이 자료는 Codex가 준비한 분석 메모이며 학습자가 작성한 이해 기록을 대신하지 않는다.

## 학습 기록 template

- 날짜 / milestone / 관련 commit: TBD
- 공부한 개념과 직접 확인한 공식 자료: TBD
- Requirement / Component / Interface / Test ID: TBD
- 내 말로 설명한 설계와 대안의 trade-off: TBD
- 참고 표준/판과 프로젝트 적용 범위, 확인하지 못한 가정: TBD
- AUTOSAR 실습 시 입력 설정 / generator·toolchain 버전 / 생성 결과: 해당 시 기록
- 작은 변경의 diff와 내가 설명하지 못한 부분: TBD
- 직접 실행한 명령 / 환경 / 결과 경로: TBD (미실행은 NOT RUN)
- fault / edge case와 예상 및 관측 결과: TBD
- 해결하지 못한 질문 / 다음 실험: TBD
- Acceptance 기준 확인 / 학습자 검토: PENDING

기록은 필요한 시점에 작은 Markdown 파일로 추가한다. 모델 답변을 그대로
붙여넣는 대신 이해한 내용, 재현 조건과 틀렸던 가정을 함께 남긴다.
