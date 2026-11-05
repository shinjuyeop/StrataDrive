# 지연 수신 권한의 원래 due와 현재 실행 회차

2026-11-05, base `da19483`. 기능 **12/12**, 서비스 **26/30**
(Normal5/6·ASan3/6·TSan18/18). **서비스 전체와 M9 전체는 OPEN이다.**
[사전 protocol](../../deferred-grant-protocol.md), [원본 결과](results.json)를 따른다.
이전 후보와 분모를 합치거나 성공까지 재실행하지 않았다.

## 수정한 조건

이전 poll 후보에서 새 grant146은 기다리는 due 이후 발행됐고 현재 실행 회차부터
18ms 이상 남아 있었지만, 수신이 회차 경계를 넘었다는 이유만으로 버려졌다.
그 뒤 이전 grant145가 만료됐다. [당시 원본](../m9_stop_deadline/remaining-grant-failure.json)을 보존한다.

권한 freshness는 원래 due 이후인지, 남은 support는 실제 current release+기존18ms를
엄격히 넘는지 따로 검증한다. 실제 수신 identity·quality·현재 유효성, 이전 command
완료, callback 중 회차 변경 시 보류를 유지한다. 기존 두 인자 port는 보수적인 기존
조건을 유지한다. Source/expiry·실행 주기·기한·SDK 오류 기준은 늘리거나 완화하지 않았다.

기존 source>=current 조건을 복원한 회귀는 실패하고 수정 후 통과했다. 이미 처리한
회차의 권한 재사용, 정확히18ms만 남은 support, 잘못된 due/current 순서를 거절했다.
현재 회차 검사는 이전 후보의 next-release 이전 command 만료 결함을 계속 차단한다.

원본4478개 command에서 현재 회차 불일치0, due freshness/current support/원래
command expiry 위반0이었다. 이번 native 실행에서 실제로 회차를 넘어 수신한 새
권한의 수용은 **0건**으로, 이 분기의 긍정 검증은 회귀 시험 범위다.
[회차 대조](release-audit.json)·[권한 대조](grant-audit.json)는 독립 Clock agreement 증명이 아니다.

## 남은 네 실패

| 실행 | 원본에서 확인한 최초 경로 |
| --- | --- |
| normal-actual-loss | 주입 전 Epoch3 Front의 Brake 피드백 불가 SD-2002(native reason3,830400812138838ns) → 보호 → VehicleRequest token157 거절 → Central SD-1002(0x20006). Command expiry 위반으로 분류하지 않음 |
| asan-normal | 실제 peer 종료 시 Front/Rear SDK Broken pipe32. 나머지 ordering/timing/response 검사는 통과해도 전체는 실패 |
| asan-stop-request-loss | Front SDK Connection reset by peer104. 원래 종료 오류를 면제하지 않음 |
| asan-normal-slow-signals | Rear SDK Connection reset by peer104. signal IO250ms 조건도 그대로 보존 |

[SDK/런타임 원본 분석](failure-analysis.json), [최초 native DTC](native-root-failure.json),
[후속 거절 token/시각](remaining-command-failure.json), [원래 VehicleRequest wire](rejected-root-wire.json)를
함께 보존한다. Brake 피드백이 현재 검사에서 불가해진 세부 경로는 아직 확정하지 않았다.
SDK 오류가 발생하지 않은 TSan18건만으로 일반/ASan 실패를 지우지 않는다.

기본 시험 전에 선언한 [조건부 TSan60건](../../deferred-grant-confirmation-protocol.md)은
기본 cohort가 실패했으므로 [NOT RUN](confirmation-disposition.json)이다.

## 검사와 무결성

- 전체 Debug1273/1273·ASan/UBSan1273/1273, 관련 TSan112/112.
- 변경 구현4개 TU cppcheck/clang-tidy, Python30+8+4, CARLA adapter6개 binary의 논리162개 통과.
- 실제 CARLA 서버·silent-loss subinterval·native4ms·Target 재실행으로 해석하지 않는다.
- 초기 계측 필드 이름과 회귀 fixture 설정 오류, 수정 후 실패/통과 로그도 `validation-tools.tar.gz`에 보존한다.

Source snapshot·binary hash·고정 manifest와 각 profile/round raw archive를 보관한다.
[동일성 확인](identity-checks.json)은 포장 시점 기준이다. [원본 파일 대조](archive-verification.json)는
이번5개 후보의29개 native archive를 실행 폴더와 byte 단위로 대조한다.
[압축 해제 재감사](archive-recheck.json)는 성공과 SDK 오류·TCP capture 누락 실패를
각각 같은 판정으로 재현한다. 후속 분석/스크립트/로그는 `post-runtime-validation.tar.gz`에 있다.

남은 전체 완료 조건은 [프로젝트 상태](../../../project-status.md)를 따른다.
