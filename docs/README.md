# 문서 안내

처음에는 [현재 상태](project-status.md) → [실행 안내](carla-guide.md) →
[아키텍처](architecture/README.md) 순서로 읽는다. 상세 계약은 필요할 때 찾는다.

## 현재 작업에 쓰는 문서

| 문서 | 관리하는 내용 |
| --- | --- |
| [현재 상태](project-status.md) | 구현·검증 범위, 남은 문제, M7 종료 조건과 다음 작업 |
| [CARLA 실행](carla-guide.md) | 설치 위치, 재실행 명령, 화면과 결과 확인 방법 |
| [아키텍처](architecture/README.md) | Central/Zone/Leaf/plant 책임, 실행·배포 경계 |
| [로드맵](roadmap.md) | 후속 단계와 TBD 담당·결정 시점 |
| [개발 정책](development-guide.md) | 변경·검증·학습·문서 작성 원칙 |
| [학습 안내](learning/README.md) | 통신 → 모델 → 실행 감시 → 차량 lifecycle 읽는 순서 |

## 상세 기준

| 분야 | 기준 문서 |
| --- | --- |
| 요구사항 | [시스템](requirements/system-requirements.md) · [시간](requirements/timing-requirements.md) · [안전](requirements/safety-requirements.md) |
| Interface | [계약 목록](interfaces/README.md) · [CARLA](interfaces/carla-plant-adapter.md) |
| 검증 | [검증 안내](test-plan/README.md) · [전략·TC](test-plan/verification-strategy.md) · [시나리오](test-plan/scenario-baseline.md) · [추적성](test-plan/requirements-traceability.md) |
| 안전 분석 학습 | [Item Definition / HARA 초안](safety/concept-study.md) |

## 과거 기록

[보관 문서 안내](archive/README.md)에서 설계 결정(ADR), 완료 단계 검토와 과거 CARLA
계약을 찾는다. 당시의 실패·미구현·다음 작업은 현재 상태로 해석하지 않는다.
실행 로그·센서·해시·source snapshot은 `test-plan/evidence/`의 기존 경로에 보관한다.

현재 상태는 `project-status.md`, 예정 작업은 `roadmap.md`, 수치와 인터페이스는
각 계약 문서에서 한 번만 관리한다. 새 실행 결과를 README나 정책 문서에 계속 덧붙이지 않는다.

문서명은 소문자 영어와 하이픈으로 통일하고, 폴더 안내는 `README.md`를 쓴다.
세부 규칙은 [문서 이름 규칙](development-guide.md#문서-이름-규칙)에 있다.
