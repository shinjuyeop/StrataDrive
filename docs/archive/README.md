# 보관 문서

당시의 결정과 검토를 보존한다. 현재 작업은 [프로젝트 상태](../project-status.md)와
[문서 안내](../README.md)에서 시작한다. 이곳의 과거 “다음/미구현/수용 보류”는 당시 판정이다.

| 문서 | 내용 |
| --- | --- |
| [설계 결정](design-decisions.md) | ADR-0001–0065의 결정·이유·제약. ID별 목차 제공 |
| [M0–M6 검토](milestone-reviews.md) | Baseline, M2/M3 수용, M4 Host/종료, M6 종료 검토 |
| [CARLA 이력](carla-history.md) | 과거 환경 조사·계약 v25까지의 경위·M7 검토 |
| [M4 프로토콜](m4-test-protocols.md) | 완료된 계약 검토·kernel 관측·middleware v1·settlement 계획 |
| `protocols/` | 현존 runner가 직접 읽는 고정 M4 fault/follow-up/middleware v2 프로토콜 |

Raw log·CSV·센서·hash·시험 source snapshot은 기존 `../test-plan/evidence/` 경로를 유지한다.
과거 정상/실패 원본은 최신 통과로 덮어쓰지 않는다. 오래된 문서의 실행 명령은 당시 조건이며,
현재 실행 방법은 학습 안내·CARLA 안내와 runner의 `--help`를 따른다.
