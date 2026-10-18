# ADR-0043: Hosted RTOS의 절대 주기 타이머와 명시적 Host 배치

Date: 2026-10-19. Status: **구현·비교 검증 중**.
[M3 수용 검토](../m3_acceptance_review.md)의 OPEN-M3-01/02와
[RTOS 파일럿](ADR-0040-steering-rtos-pilot-and-delay-observation.md)의 tick drift를 후속 검토한다.

## 확인한 문제와 변경 경계

Native multirate는 이미 CLOCK_MONOTONIC/TIMER_ABSTIME을 사용한다.
일반 sanitizer의 두 실패에서 요청 wake 뒤 지연과 네 slot 누락을 관측했지만 커널 원인은 미확정이다.
Native FIFO의 실제 배치·priority·startup 검사는 ADR-0042를 유지한다.

Pinned Trampoline의 ViPer AUTO timer는 relative usleep을 반복한다.
매번의 늦은 wake와 다음 sleep까지의 비용이 다음 예정 시각에 더해지는 구조다.
기존 측정의 약 24–30 ms / 1.6 s drift와 일치하는 누적 경로지만 모든 Host 지연의 원인이라는 뜻은 아니다.
RTOS OS API/Task/Alarm/Resource와 ECU 코드·CAN wire는 유지하고 Linux 가상 timer backend만 교체한다.

## 타이머와 관측 계약

`vecu/platform/trampoline_posix/viper_timer.c`는 Linux timerfd의 CLOCK_MONOTONIC 절대 시작 시각과
10 ms periodic interval을 사용한다. Read가 여러 expirations를 반환하면 최신 기회에 signal 하나만 보내고
`expirations-1`을 누락으로 기록한다. 밀린 interrupt를 몰아서 보내거나 놓친 OS tick을 실행했다고 표시하지 않는다.
기존 POSIX signal의 비큐잉/coalescing 한계도 남으므로 실제 RTOS release를 distinct timer send와 대조한다.

Build helper의 `--timer-mode`는 `absolute`(새 기본), `relative`(동일 계측의 상대 sleep 대조군),
`upstream`(고정 원본)이다. 원본 checkout은 수정하지 않고 ViPer link의 timer object만 명시적으로 교체한다.
원본 GPLv2 license와 lock은 유지하고 교체 source의 GPL-2.0-or-later 표기·hash·compiler 명령·선택 mode를 build manifest에 기록한다.

각 timer thread는 시작 전에 bounded mmap trace를 생성·prefault한다. Tick 본문에 파일 출력은 없다.
128-byte header/64-byte record, 512 records의 little-endian schema 1이다.
Origin·period·intended target/wake/send·expiration 누락·PID/TID·실제 policy/priority/CPU를 기록한다.
Count 공개는 lock-free다. Trace overflow/error/누락이나 source/build mismatch는 FAIL이며 없던 timer tick을 0 지연으로 보충하지 않는다.
이는 trace page만 준비한 것이며 전체 memory locking/page fault/WCET 보장을 뜻하지 않는다.

## Host 배치와 판정 기준

`check_rtos.py --rtos-cpu B --plant-cpu A --fifo`는 자식에서만 설정한다.
RTOS와 그 ViPer 자식/timer는 CPU B FIFO 10, 외부 물리 모델은 CPU A FIFO 19다.
비교 대조군도 같은 CPU map에서 SCHED_OTHER/0을 명시한다. RTOS 내부 Task priority와 Linux priority는 별개다.
권한/실제 설정 오류는 FAIL이고 fallback하지 않는다. Runner/사용자 shell의 policy·affinity는 변경하지 않는다.
이 첫 Host priority map은 최적화·양산 calibration 결과가 아니다.

원래 실제 ReleaseDispatch→Control 완료 5 ms·감시 margin 20 ms·유효 수신 상실 100 ms는 유지한다.
추가 Host 판정은 **원래 timer phase→ReleaseDispatch <=5 ms**, 정상에서는 **phase→Control 완료 <=5 ms**다.
기존 5 ms보다 기점을 앞당긴 추가 fixture 검사이며 차량/Target requirement revision은 아니다.
Relative 대조군도 최초 origin의 nominal phase로 평가해 움직이는 target이 drift를 숨기지 못하게 한다.
Measured window의 skipped expiration/coalesced signal은 0이어야 한다.
`--require-wall-timing`은 위 추가 계약을 실행 verdict에 적용한다. 미지정 시 timing FAIL도 독립 필드에 보존한다.
고장 주입의 늦은 Control 자체는 원래 oracle로 검사하고 정상 성능 표본과 합치지 않는다.

개발 시험에서 absolute tick의 12-tick ResumeAlarm이 suspend 위상 때문에 120 ms보다 짧아졌다.
최소 wall 정지 **120 ms** 검사를 유지하고 ResumeAlarm을 **13 ticks**로 바꾼다.
예상하지 않은 개발 실패는 보존하고 새 비교에 합치지 않는다. 원래 native 120 ms 주입은 변경하지 않는다.

## 비교 protocol과 남은 범위

계측 relative/absolute × OTHER/FIFO, 동일 CPU A=0/B=1·4 scenario·각 3회로 48 runs를 계획한다.
Repetition마다 네 profile 순서를 회전한다. 추가 부하 없음·warm-up 제외 0, 원래 1.6 s window/500 ms enable lead를 사용한다.
Normal phase 지연/nominal drift와 fault 반응을 따로 기록하며 모든 유효 실패를 보존한다.
Native normal/sanitizer FIFO fault 회귀와 같은 observer/CPU 조건의 OTHER/FIFO 대기 관측도 별도 수행한다.
진단 observer는 intrusive이며 정규 성능 비교와 섞지 않는다.

Timerfd의 누락 기록은 별도 owned ViPer 정지 주입으로 확인한다. 이를 정상 timing PASS로 처리하지 않는다.
원본 sanitizer 두 실패를 새 PASS로 교체하지 않는다. 추가 실행이 kernel 원인을 소급 확정하지 않는다.
Tracefs/perf 권한, PREEMPT_RT 비교·Target runtime·동시 process/OS 정지 중 독립 보호는 여전히 후속이다.

공식 근거: [clock_nanosleep과 absolute drift](https://man7.org/linux/man-pages/man2/clock_nanosleep.2.html),
[timerfd의 periodic expiration count](https://man7.org/linux/man-pages/man2/timerfd_create.2.html),
[timer slack과 RT policy](https://man7.org/linux/man-pages/man2/PR_SET_TIMERSLACK.2const.html).
