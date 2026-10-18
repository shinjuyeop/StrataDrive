# ADR-0042: Native M3 owner별 FIFO 설정과 비교

Date: 2026-10-18. Status: **옵션 실행 경로 구현 / Host 측정·M3 수용 검토**.
[ADR-0041](ADR-0041-arm64-rtos-build-and-host-preflight.md)의 새 PAM 세션에서 개발 계정의 rtprio 20을 확인했다.
기존 native M3 workload에 Linux FIFO를 적용한다. Trampoline 내부 Task나 그 POSIX tick을 변경하는 작업과 구분한다.

## 실행 계약

`actuator_demo multirate-runtime`의 선택 옵션 `owner-fifo=`에 일곱 owner의 priority를 명시한다.
기본 실행은 기존 상속 정책이다. 비교 실행기는 일반 조건이 실제 SCHED_OTHER/0인지도 검사한다.
FIFO는 SCHED_OTHER/0 launcher에서 시작하고 startup 시 `pthread_setschedparam` 뒤 실제 policy/priority를 읽어 확인한다.
요청 범위는 Linux API의 1..99이며 계정의 실제 허용 상한은 별도다. 현재 Host 계정은 20이다.

| Owner | 비교용 FIFO priority | 이유 |
| --- | --- | --- |
| Monitor | 20 | 완료 시한·수신 감시 |
| Plant/fixture | 19 | 교차 감시와 실제 보호 적용·물리/센서 진행 |
| RX | 18 | 2 ms 주기와 3 ms 완료 budget |
| Brake/Drive/Power | 10 | 10 ms 주기의 ECU 판단 |
| BMS | 9 | 20 ms 주기의 ECU 판단 |

이 map은 첫 Host 비교 fixture다. Criticality·WCET에 근거한 양산 우선순위 결정이나 최적값을 주장하지 않는다.
IO owner는 CPU A, ECU 네 owner는 CPU B에 두며 조건 사이에 동일한 map을 유지한다.

일곱 owner 모두 affinity·scheduler 설정과 실제값 취득을 마친 뒤에만 startup gate를 연다.
기존 enable lead 100 ms와 release/시한을 유지하고, coordinator의 준비 대기는 최대 50 ms다.
준비 실패 또는 enable 이후에는 workload를 시작하지 않는다. 시작 gate의 mutex/CV는 측정 window 밖에서만 사용한다.
본문의 기존 bounded RX·latest snapshot·완료 guard와 original source 규칙을 유지한다.

설정 실패는 모든 대기를 깨우고 abort한다. 일반 policy로 fallback하지 않는다. 부분 적용 실패에서도 application body,
plant 진행·CAN 송신은 시작하지 않는다. 실제 관측 policy·priority, owner별 ready/error, startup release와 aborted를 기록하고
nonzero로 종료한다. Coordinator/plant가 공유하는 호출 thread의 원래 policy·priority·affinity는 join/CSV 출력 전에 복원한다.
`run.json` schema 5의 추가 필드 `runtime_scheduling`으로 기록한다. 이전 schema의 분석은 유지한다.

## 비교와 증거

기존 `check_timing.py --experiment scheduler`가 SCHED_OTHER/FIFO × quiet/loaded × full/minimal ×3회를 실행한다.
조건 순서를 repetition마다 회전하고 trace 순서를 번갈아 둔다. CPU B의 부하는 기존 SCHED_OTHER 7/10 ms wall busy window다.
실제 부하 CPU 소비와 생존, 배치·policy control을 별도로 검사한다. 설정/부하 control이 실패한 run도 FAIL로 보존하되
비교 통계에서는 제외한다. 유효한 관측을 가진 timing FAIL은 포함한다. 두 방식 모두 동일한 binary/workload/시한을 쓴다.
Sanitizer는 별도 기능 회귀 build이며 성능 비교 숫자에 합치지 않는다.

원래 [ADR-0039](ADR-0039-owner-completion-guards.md)의 owner 2 ms/4 ms·1211 slots, RX 2 ms/3 ms·1210 jobs와
ECU 5/8 ms 시한을 완화하지 않는다. Job/owner의 skip·miss·wake/body/CPU·유효 수신·보호 적용을 함께 본다.
RT 권한 거부와 partial setup을 별도 CLI 시험하고 기존 fault 17조건도 일반/FIFO로 검사한다.

FIFO는 Linux scheduling policy다. PREEMPT_RT kernel 적용, memory locking·page-fault 제한, kernel trace,
실제 Jetson/MCU 정시성이나 full AUTOSAR stack을 의미하지 않는다. 기존 RT throttling과 시스템 설정을 유지한다.
현재 실행 환경의 결과로 WCET나 hard real-time을 보장하지 않는다. 전체 32개 requirement/29개 TC는 NOT RUN이다.

공식 API 근거: [pthread_setschedparam](https://man7.org/linux/man-pages/man3/pthread_setschedparam.3.html),
[Linux scheduling](https://man7.org/linux/man-pages/man7/sched.7.html).
실행·결과는 [학습 안내](../learning/m3_native_fifo.md), [품질 기록](../quality_policy.md)에 둔다.
