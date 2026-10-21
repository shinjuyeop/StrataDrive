# DDS 종료·TSan 후속 — 기준658562e

2026-10-21. **DDS control gate CLOSED / Central↔Front adapter 미착수**.
시작 시 fetch한 origin/main과 HEAD는658562e, 로컬 변경 없음이었다.
M4 Host IO/FIFO component 한정 수용·M4 전체 보류, 과거42회23 PASS/19 FAIL,
운용 profile의 별도45회 및64 TSan warning occurrences를 그대로 유지한다.

## 수정과 실제 검증

두 Python runner가 `build/` 생성 없이 `.m4-exclusive.lock`을 열었다.
공통 `open_build_lock()`이 부모 디렉터리를 만든 뒤 기존 파일에 같은
`LOCK_EX | LOCK_NB`를 적용하게 했다. 잠금 이름/배타성은 바뀌지 않았다.
Compiler-failure fixture는 매번 없는 임시 `fresh-build/`를 사용하고 잠금 파일
생성과 원래 exit7/24·38·6 NOT RUN assertion을 함께 검사한다. 따라서 실제 작업
트리에 SDK/build 산출물이 있든 없든 같은 준비 경로를 검사한다.

[실행 전 protocol](protocol.md), [기계 판독 결과](tests-summary.json).

| 실행 | 결과 | 의미 |
| --- | --- | --- |
| 658562e 별도 checkout, build/ 없음 |29개 중27 PASS/2개 시험 FAIL; 하위 조건 포함3 failure records, exit1 |[실패 원본](python-before.log): 두 runner의 FileNotFoundError |
| 같은 checkout에 수정3파일 적용, build/ 없음 |29/29 PASS, exit0 |[수정 후](python-fresh-after.log); 종료 후에도 checkout의 build/ 없음 |
| 현재 작업 트리 |29/29 PASS, exit0 |[로그](python-working-after.log); 기존29개 이름/assertion 유지 |
| 새 SDK 비교/성능/sanitizer 실행 |**NOT RUN /0회** |경로에 맞는 지원되는 변경 후보를 확보하지 못해 반복하지 않음 |

29개는 lifecycle7+middleware22 Python bookkeeping 시험이다. SDK hash와 컴파일러
실패를 fixture로 대체한다. 실제 subprocess exit/두 child timeout kill·wait·로그
보존도 검사하지만 **실제 DDS 통신·API 종료·sanitizer 검증이 아니다**.
강제 child 정리는 실패 수집 경로이며 정상 종료로 세지 않는다.
제품 C++·진단 C++·SDK·설정·원래 expiry/20ms/Epoch/token/보호 조건 변경 없음.
따라서973/native40/timing48 및 이전 sanitizer 보호11개를 다시 실행하지 않았다.

## 확인한 원인과 한계

[종료 비교](shutdown-review.md)는 과거 v6/GDB와 후속 v7, Host raw restart,
지속 송신·RHC 포화 close를 분리한다. GDB에서 main은 `dds_reader_close`의 GC 완료,
recv는 full-RHC 재전달, GC는 awake thread 진행을 기다렸다. 그 위치는 SDK 소스와
일치한다. 애플리케이션이 take를 중단한 것이 유발 조건이지만, 공개 participant
삭제 API 대신 다른 삭제 순서가 필요하다는 공식 근거는 발견하지 못했다.
SDK GC/재전달 경로의 liveness가 유력하며, 지원되는 해결은 **OPEN**이다.

[경고 분류](warning-review.md), [32개 stack 조합](warning-index.md),
[64회 전수 위치·양쪽 stack·SHA](warnings.json)를 연결했다.9회는 bucket/GUID
publication의 구체적인 TSan 가시성 공백,55회는 실제 사용 SDK 경로 미확정으로
분류한다. **9회도 오탐 확정이나 수용 예외로 바꾸지 않으며64회 전부 FAIL 유지**다.
우리 코드 또는 진단 전용 동기화·수명 결함으로 확인된 경고는0회다. 이는 무결함
증명이 아니다. 특히1회는 재전송 flag 쓰기와 잠금 밖 heartbeat flag 읽기가 같은
bitfield 바이트를 접근하는 원본/소스/실제 라이브러리 기계어 근거를 확보했다.
GC 계측 설명만으로 이 유형을 닫을 수 없다.

공식11.0.1 API의 participant 재귀 삭제는 이미 사용 중이다.
[release11.0.1](https://github.com/eclipse-cyclonedds/cyclonedds/releases/tag/11.0.1),
[미병합 PR2162](https://github.com/eclipse-cyclonedds/cyclonedds/pull/2162),
관련 issue와 제한된 commit 검색에서 두 경로의 지원되는 수정 후보는 확인되지
않았다. 이를 upstream 전체에 수정이 없다는 증명으로 표현하지 않는다.
[조회 범위·판정](upstream-review.json)에 근거를 남겼다. 기본 의존성은11.0.1/e54e991
그대로이며 별도 후보 빌드도 실행하지 않았다.

## Gate와 다음 경로

통신은 초기 준비에 대한 기존 성공 근거만 있고, 운전 중 손실 복구의20ms 보장은
없다. 종료는 full-RHC 사건 OPEN, 경고는 FAIL이다. 따라서 **연결 조건 미충족**이며
정규 adapter 구현/enable을 시작하지 않는다. transport readiness는 INIT·Release·arm
권한이 아니며, Jetson/전체 시스템도 NOT RUN이다. [Gate 기록](gate.json).

다음 한 단계는 [SDK 문의 초안](support-draft.md)을 사용자가 검토하고 유지보수자에게
full-RHC 재전달 중 삭제의 지원 절차와 bitfield 경합의 수정 근거를 확인하는 것이다.
**외부 게시·메시지 전송은 하지 않았다.** 승인된 변경이 오면 pin과 후보를 분리해
동일 조건에서 비교한다. 우리 쪽 후속은 종료 ACK 대기 rc·API별 시작/반환 계측과
명시적 quiesce/drain 계약 설계가 가능하지만, 그것만으로 비협조 상대방/포화 종료를
해결했다고 할 수 없다. 임의 SDK 교체·큐 증설·sleep/timeout 연장·경고 억제는 없다.

Daybreak 중단 이력을 인계했다. 이번 조회/로컬 작업에 새 안내는 없었으며 이전에
접근 실패한 writer API URL은 재요청하지 않았다. 관리자 권한·설정 변경도 없다.

## 재현과 보존

```bash
PYTHONPATH=tests/unit python3 -m unittest dds_lifecycle_test middleware_probe_test -v
python3 docs/test-plan/evidence/m5_dds_shutdown_followup/analyze_warnings.py
```

첫 명령은 관련29개 시험, 둘째는 기존 raw archive만 읽는 offline 분석이다.
이번 [raw.tar.gz](raw.tar.gz)는 시험 command/실패 로그/수정 snapshot, source-review,
기계어·SDK SHA, 이전 실행 identity 비교와 access log를 포함한다.
[manifest](raw-manifest.json)는 원본 bytes SHA다. 이전 종료 원본은
[qualification archive](../m5_dds_qualification/raw.tar.gz)의 `restart-gdb/`와
`cohort-v6/`, 최근 성공 및 경고 원본은
[operating archive](../m5_dds_operating_profile/raw.tar.gz)의 `cohort-v1/`,
`readiness-v2/`에 그대로 있다. 새 분석을 새 SDK 실행 분모로 더하지 않는다.
