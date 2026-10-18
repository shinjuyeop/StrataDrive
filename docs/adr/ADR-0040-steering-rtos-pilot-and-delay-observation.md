# ADR-0040: Steering RTOS 파일럿과 Host 실행 대기 관측

Date: 2026-10-18. Status: **옵션 Host 파일럿 구현 / Jetson·RTE/BSW·실시간 수용 후속**.
[ADR-0022](ADR-0022-leaf-classic-development-methodology.md)의 작은 OS 파일럿을 진행한다.
기존 Linux 실행·CAN 계약·Central/Zone/Leaf 배포 계획은 유지하며 Steering 한 경로만 별도로 비교한다.

## 구현체와 실행 경계

[Trampoline](https://github.com/TrampolineRTOS/trampoline)의 revision은
`third_party/trampoline.json`으로 고정한다. 생성 도구 GOIL과 가상 하드웨어 ViPer도 같은 소스에서 빌드한다.
Upstream은 OSEK/VDX·AUTOSAR OS 4.2 API alignment를 설명한다. 이 파일럿은 **OIL 2.5 OSEK 설정**이며
R25-11 Classic 적합성이나 ARXML/RTE/BSW 통합 결과가 아니다. 기존 R25-11 P05 wire 구현은 유지한다.
Upstream GPL v2 license 파일과 hash를 기록한다. Upstream checkout·생성 파일·연결 binary는 `build/`에 둔다.
정상 CMake 실행은 다운로드하지 않는다. 사용자가 명시한 build helper의 `--fetch`만 고정 revision을 받는다.
Root 프로젝트의 license나 Target OS를 이번 파일럿으로 변경하지 않는다.

| 실행자 | 책임 |
| --- | --- |
| Trampoline ReleaseDispatch, priority 5 | OS Alarm으로 실행, release 시각 게시 후 Control의 Event 설정 |
| Trampoline Watch, priority 4 | 5 ms 완료 budget 감시, 늦음/미완료 latch와 hold 요청 |
| Trampoline Receive, priority 3 | CAN Command·로컬 sensor channel을 각 8개까지 읽고 bounded mailbox 갱신 |
| Trampoline Control, priority 2 | Event 대기·mailbox snapshot·기존 SteeringActuator prepare/complete·Actual 송신 |
| 별도 Linux plant process | 2 ms 물리 진행·원래 센서 취득·ECU 출력 적용·Actual 수신 감시 |

Mailbox는 OS Resource로 보호하고 Control과 Receive만 접근한다. Control이 대기할 때 Resource를 보유하지 않는다.
OS kernel/Alarm/Event/Resource를 실제 빌드·실행하며 Linux pthread에 이름만 대응한 구현이 아니다.
ECU 판단 library에는 물리 모델을 링크하지 않는다. C ABI adapter가 기존 C++ ECU·codec·SocketCAN을 연결한다.
센서는 inherited Unix SOCK_SEQPACKET의 고정 크기 private packet으로 보낸다. 같은 Host clock의 취득 time/model identity를
그대로 전달하며 이 channel을 양산 sensor protocol로 간주하지 않는다. CAN Command/Actual은 기존 0x180/0x280·32-byte P05다.

Sensor/command 이전에 application clock을 읽지 않는다. Command의 accepted/source 시각, 센서 취득 시각과 Actual generation을
구분한다. Hold를 받은 plant는 실제 적용 시각에 이동을 취소하고 각도를 유지한다. 보호 flag와 실제 물리 적용은 별도다.
Parent Actual receiver의 유효 수신 상실도 hold를 latch한다. 복귀/재수신으로 보호를 자동 해제하지 않는다.
Application epoch 2/model epoch 1은 격리된 시험 fixture다. 실제 session coordinator·OS restart/rejoin은 후속이다.

## 가상 시간과 Host 시간

고정한 upstream POSIX target의 SystemCounter 입력은 **10 ms relative usleep timer**다. 수정하지 않았다.
Control/Receive/Watch/ReleaseDispatch는 각각 1 tick Alarm을 사용한다. OS tick이 Host wall time과 일치한다고 가정하지 않는다.
파일럿의 검출 margin 20 ms는 10 ms 감시 tick과 추가 한 tick의 Host dispatch 여유를 둔 시험 값이다.
5 ms budget의 기점은 **ReleaseDispatch가 게시한 실제 monotonic 시각**이다. Alarm 예정→ReleaseDispatch 실행 지연은
이 budget 밖이며 release interval과 첫 release 기준 nominal wall drift로 따로 기록한다.
밀린 Control Event는 합쳐질 수 있어 release별 행을 보존하고 실행하지 못한 행에도 Watch 검출을 남긴다.
놓친 virtual timer signal의 정확한 개수는 이 기록만으로 증명하지 않는다.

기존 [ADR-0039](ADR-0039-owner-completion-guards.md)의 RX 2 ms/3 ms 시한과 owner 2 ms/4 ms 시한은 유지한다.
RTOS 파일럿의 기능 PASS를 기존 M3 정상 timing PASS로 대체하지 않는다. Hosted RTOS의 실행도 Linux/가상 환경 영향을 받는다.
이번 확인 target은 x86_64 Linux다. ARM64 Jetson 지원·실제 MCU/hypervisor 배포·Target latency는 NOT RUN이다.

## 호환 설정과 시험

POSIX port는 setjmp/longjmp로 별도 task stack을 전환한다. 현재 glibc의 fortified longjmp 검사와 충돌해
생성된 hosted C 쪽에만 `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0`을 적용한다. 일반 CMake 품질 설정은 유지한다.
Port의 stack-size 표현에 맞춰 task 49152 bytes/ISR 32768 bytes를 사용하고 overflow warning을 error로 처리한다.
Sanitizer/fiber 연동은 미검증이므로 hosted OS binary를 ASan/UBSan 수용 증거로 쓰지 않는다. 기존 native core/unit 검사는 별도 수행한다.
GOIL 생성 C의 upstream 경고와 직접 작성한 adapter의 정적 분석 결과를 구분한다.

정상, command-loss, CRC-corrupt, Control-stall 4조건을 실행한다. Control-stall은 12-tick Resume Alarm과
WaitEvent를 사용해 Control만 대기시킨다. Host thread 전체를 sleep시키는 주입이 아니다.
Watch가 복귀 전에 검출/hold하고 외부 plant가 진행하는지 확인한다. Late job의 Actual은 폐기한다.
보호 후 센서 Actual을 Command로 대체하거나 원래 취득 time을 새로 찍지 않는다.
Console shim은 자식 실패도 exit 0으로 끝날 수 있으므로 shutdown JSON·OS error·actual/source·물리 trace까지 검사한다.
Launcher는 자기 process group을 정리하며 실제 RTOS PID의 per-application POSIX IPC 이름만 정리한다.

## 지연 분석

Runtime ThreadInfo에 native TID를 추가한다. 기존 schema 5 metadata의 추가 필드이며 CAN/schema 계약은 유지한다.
별도 observer가 `/proc/PID/task/TID/schedstat`의 CPU/queue/time-slice 누적값과 voluntary/involuntary switch를 읽는다.
`CONFIG_SCHED_INFO`와 probe 권한 상태, sample begin/end를 기록한다. 이 관측은 intrusive diagnostic이며 성능 baseline이 아니다.
누락 release 앞과 다음 실행 뒤를 완전히 덮는 표본 두 개가 있을 때만 delta를 계산한다. 경계 여유 시간과 불완전 coverage도 남긴다.
그 구간의 runqueue 대기 증가는 확인할 수 있지만 전부를 한 wakeup에 할당하거나 경쟁 process/IRQ/VM 원인을 단정하지 않는다.
Queue delta 0도 timer 지연의 증명이 아니다. 기본 커널의 timer→wakeup→switch 분리는 커널 trace가 필요하다.
현재 tracefs는 접근 거부, perf는 paranoid=4로 거부된다. 시스템 권한/커널 설정을 바꾸지 않고 원래 오류를 보존한다.
공식 참고: [schedstat](https://www.kernel.org/doc/html/latest/scheduler/sched-stats.html),
[event tracing](https://www.kernel.org/doc/html/latest/trace/events.html).

실행 방법은 [학습 안내](../learning/m3_rtos_pilot.md), 최종 결과는 [품질 기록](../quality_policy.md)에 둔다.
전체 32개 requirement/29개 system TC는 NOT RUN이며 M3 전체 종료나 AUTOSAR stack 채택을 선언하지 않는다.
