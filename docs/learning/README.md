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

## 학습 기록 template

- 날짜 / milestone / 관련 commit: TBD
- 공부한 개념과 직접 확인한 공식 자료: TBD
- Requirement / Component / Interface / Test ID: TBD
- 내 말로 설명한 설계와 대안의 trade-off: TBD
- 작은 변경의 diff와 내가 설명하지 못한 부분: TBD
- 직접 실행한 명령 / 환경 / 결과 경로: TBD (미실행은 NOT RUN)
- fault / edge case와 예상 및 관측 결과: TBD
- 해결하지 못한 질문 / 다음 실험: TBD
- Acceptance 기준 확인 / 학습자 검토: PENDING

기록은 필요한 시점에 작은 Markdown 파일로 추가한다. 모델 답변을 그대로
붙여넣는 대신 이해한 내용, 재현 조건과 틀렸던 가정을 함께 남긴다.
