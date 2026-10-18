# M3: Steering을 실제 RTOS Task로 실행하기

Date: 2026-10-18. Scope: **Trampoline POSIX Host 파일럿**. Target·RTE/BSW·실시간 수용은 후속이다.
결정과 clock/budget 경계는 [ADR-0040](../adr/ADR-0040-steering-rtos-pilot-and-delay-observation.md)에 있다.
2026-10-19부터 build helper의 기본 timer는 absolute timerfd다. 아래 최초 relative/12-tick 설명·수치는 당시 이력이며,
현재 실행 기준·비교는 [누적 지연 수정](#절대-타이머로-누적-지연-줄이기)을 따른다.

## 이번에 달라지는 것

기존 Steering ECU 판단 코드는 유지하고 **누가 언제 실행하는가**를 바꾼다.
Trampoline kernel과 GOIL이 생성한 설정을 실제로 연결한다. Linux thread를 RTOS Task라고 부르는 모형과 구분한다.
Application/RTE/BSW 전체를 생성한 결과는 아니며 C ABI adapter로 기존 ECU를 직접 연결한 첫 OS 파일럿이다.

| 개념 | 여기서 하는 일 |
| --- | --- |
| Task | 수신, 제어, 감시, release 전달을 OS가 우선순위로 실행 |
| Alarm | Counter tick마다 Task를 실행하거나 Resume Event 설정 |
| Event | Control이 새 release 또는 주입된 대기의 종료를 기다림 |
| Resource | Receive와 Control이 같은 입력 mailbox를 동시에 변경하지 않게 함 |
| Error/Startup/Shutdown Hook | API 오류·실제 RTOS PID·종료 trace 기록 |

평소에는 Receive가 새 CAN Command와 sensor를 읽고, Control이 prepare/complete를 호출해 출력·Actual을 만든다.
물리 각도는 별도 Linux process의 SteeringResponse가 진행한다. 따라서 Control이 멈춰도 물리와 감시는 계속 실행할 수 있다.
보호 요청과 실제 hold 적용을 다른 timestamp로 남긴다. Actual은 원래 취득 시각·센서 값과 대조한다.

## 실행하기

일반 CMake build는 RTOS를 받거나 링크하지 않는다. 별도 옵션 build를 명시적으로 준비한다.

```sh
python3 tools/build_rtos_pilot.py --fetch
unshare --user --map-root-user --net python3 tests/integration/runtime/check_rtos.py --output-dir build/m3-rtos-results --repetitions 3
```

첫 명령은 lock의 upstream commit으로 GOIL/ViPer·C++ bridge를 빌드하고 OIL→C 설정을 생성한다.
`build/m3-rtos-pilot/build.json`에 revision/license·도구·binary·library·입력 hash를 남긴다.
이미 source가 있으면 `--fetch` 없이 재빌드한다. 일반 C++/sanitizer 시험 build와 다른 directory를 사용한다.
POSIX stack 전환에 필요한 C flag와 stack 크기는 OIL 설정 및 ADR에 명시돼 있다. 시스템 커널이나 RT 권한은 변경하지 않는다.

두 번째 명령은 4조건×3회=12 runs다. 결과 directory는 새 경로여야 한다.

- `normal`: 0→0.2 rad 명령과 실제 이동·원래 source의 Actual을 확인한다.
- `command-loss`: 600 ms 뒤 명령을 끊고 local hold를 확인한다.
- `corrupt`: 원래 트래픽은 계속 보내되 CRC를 깨뜨린다. 유효 수신 time을 갱신하면 실패다.
- `control-stall`: 600 ms 이후 Control이 WaitEvent한다. 최초 12 ticks였고 현재는 최소 wall 120 ms를 위해 13 ticks를 사용한다. Watch·Receive와 외부 물리의 진행을 확인한다.

`rtos-jobs.csv`는 release·start·phase·end·sensor/Actual source·Watch 검출·suspend/resume를 기록한다.
`plant.csv`와 `actual.csv`는 외부 물리 및 실제 CAN Actual 수신이다. JSON은 OS API 오류·폐기·보호 적용을 담는다.
기능 PASS와 함께 wall timing은 별도 상태로 표시한다. 누락·늦은 보고·없는 종료 trace를 정상으로 간주하지 않는다.

## 10 ms tick이 정확히 10 ms인가

최초 upstream backend는 ViPer의 relative sleep로 10 ms tick을 발생시켰다. Linux에서 늦게 실행되면 tick이 밀리거나 signal이 합쳐질 수 있다.
OS Task는 이 가상 tick에 따라 실행된다. 센서 freshness와 보호는 Host CLOCK_MONOTONIC을 사용한다.
보고서의 `release_interval_ms`와 `nominal_wall_drift_ms`로 두 시간의 차이를 확인한다.
`release_to_end_ms`는 ReleaseDispatch가 실제 release를 게시한 뒤의 응답이다. 앞선 timer/Host 지연을 포함한 전체 latency가 아니다.
원래 M3의 2 ms/4 ms guard나 RX 3 ms 기준은 그대로 남아 있으며 이 파일럿으로 충족했다고 표시하지 않는다.

## Host의 실행 대기 보기

```sh
unshare --user --map-root-user --net python3 tools/runtime_diagnostics.py --output-dir build/m3-schedstat-quiet --repetitions 3
unshare --user --map-root-user --net python3 tools/runtime_diagnostics.py --output-dir build/m3-schedstat-loaded --repetitions 3 --load-cpu 2
```

현재 예의 ECU CPU=1, RX/plant CPU=0, monitor CPU=2, observer CPU=3은 해당 Host의 allowed mask에 맞게 지정한다.
첫 명령은 추가 부하가 없고 두 번째는 monitor CPU에 기존 7/10 ms wall busy-window 부하를 둔다.
이것은 observer까지 추가한 진단 workload다. 원래 무계측 성능 비교에 숫자를 합치지 않는다.

진단 대상은 기존 native `multirate-runtime`의 Linux thread다. Hosted RTOS 내부 Task별 kernel trace가 아니다.
`*-schedstat.csv`에서 CPU 실행 누적과 runqueue 대기 누적을 구분한다. 누락 구간을 덮는 두 sample의 차이를 보고
그 구간에서 CPU를 기다린 시간이 늘었는지 확인한다. 앞뒤 sample 경계가 넓으면 옆 작업의 대기도 포함될 수 있다.
따라서 report는 전체 구간의 관측과 불확실성을 함께 기록한다. 표본이 없으면 unknown이다.
Perf/tracefs가 막혔다는 원래 오류도 environment에 남긴다. 정확한 timer→wakeup→CPU 전환 분석은 권한이 있는 환경에서 후속으로 진행한다.

## 확인한 결과

최종 기능 시험은 RTOS **12/12 PASS**, 기존 native Linux 실행 회귀 **42/42 PASS**다.
C++ 521개를 normal/sanitizer 각각, Python 48개를 검사했다. Hosted RTOS binary의 sanitizer 검증은 미실행이다.
POSIX 가상 tick의 첫 release 기준 drift는 1.6초 시험에서 약 23.8–30.6 ms였다. 정상 3 runs의
ReleaseDispatch→Control 완료 최대는 약 0.131 ms였다. Timer 앞단의 지연과 Task 본문 응답은 구분해서 읽어야 한다.

진단용 무부하/감시 CPU 부하 각 3 runs는 모두 수집했고 배치·부하 control도 통과했다.
기존 정상 계약은 무부하 2/3, 부하 0/3 PASS다. Monitor의 486개 누락을 덮는 sample 구간 모두에서 runqueue 대기가 증가했다.
Queue 증가가 관측된 것과 그 전부를 해당 wakeup에 할당하는 것은 다르다. 경계 여유와 원래 sample을 확인한다.
개별 process/IRQ/VM 원인은 미확정이며 커널 trace는 권한 제한으로 NOT RUN이다.
상세 수치·실패 자료·source cohort와 로그는 [품질 기록](../quality_policy.md)에 있다.

## ARM64에서 빌드할 수 있는가

교차 컴파일은 현재 x86 PC에서 **ARM64 CPU용 파일을 만드는 작업**이다. 그 파일을 실제 보드에서 실행한 결과와 구분한다.
[ADR-0041](../adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)로 다음 점검을 추가했다.

```sh
python3 tools/build_rtos_pilot.py --architecture aarch64
```

`aarch64-linux-gnu-gcc/g++`와 `readelf`가 필요하다. Upstream source가 없다면 기존과 같이 명시적으로 `--fetch`를 붙인다.
Host에서 실행할 GOIL을 먼저 준비하고 ARM64용 RTOS·ViPer·외부 plant를 빌드한다.
CMake 산출물은 `build/m3-rtos-aarch64-host/`, 생성 OS/ViPer는 `build/m3-rtos-aarch64-pilot/`에 둔다.
Native 기본 directory는 그대로 유지한다. ViPer도 architecture별 object를 사용한다.

각 `build.json`의 `architecture`와 `elf_artifacts`를 확인한다. 파일 이름이나 compiler 옵션만 보고 CPU를 판정하지 않는다.
실행기는 RTOS·ViPer·plant 세 파일의 CPU가 현재 Host와 다르면 vCAN 생성 전에 거부한다.
Compiler가 다르거나 다른 architecture의 output directory를 지정한 경우도 새 directory를 사용해야 한다.
이번 GNU/Linux ARM64 빌드는 Jetson의 실제 OS/BSP용 sysroot 검증을 대신하지 않는다.
`runtime_requirements`의 loader·필요 library·symbol version을 보드와 대조한 뒤 실행해야 한다.

## 이 Linux에서 RT 시험을 할 수 있는가

```sh
python3 tools/runtime_diagnostics.py --probe-only --output-dir build/rt-capabilities
```

이 명령은 native/RTOS build나 vCAN 권한 없이 실행할 수 있다. 결과는 `capabilities.json`과 hash manifest다.
CPU affinity·kernel config·RT priority limit·FIFO 적용 결과·trace/perf 접근 제한을 기록한다.
FIFO는 별도 자식에서 잠깐 시험하고 원래 정책으로 복원한다. 부모나 M3 workload를 RT로 바꾸는 옵션은 아니다.
`--fifo-priority 1`은 기본 권한 점검값이며 owner별 우선순위 설계와 구분한다.

- `preemption.preempt_rt`: PREEMPT_RT kernel 설정 여부다. 일반 PREEMPT_DYNAMIC과 별개다.
- `fifo_probe.verdict`: AVAILABLE/BLOCKED/UNKNOWN 중 하나다. AVAILABLE은 해당 priority의 syscall 적용 확인이다.
- `tracefs_error`·`perf_probe_*`: 지연 분해에 필요한 관측이 현재 가능한지와 원래 오류를 확인한다.

Exit 0은 보고서를 수집했다는 뜻이다. FIFO가 거부됐다면 RT workload·지연 개선 비교는 **NOT RUN**으로 남긴다.
일반 Linux에서도 FIFO를 사용할 수 있고, PREEMPT_RT kernel에서도 실행 계정의 권한은 별도로 확인해야 한다.
후속 [native FIFO 비교](m3_native_fifo.md)에서 같은 M3 workload·시한에 owner별 RT 설정과 실제 적용값 기록을 연결했다.

2026-10-18에 native/ARM64 세 실행 파일의 빌드·ELF/ABI 확인과 native 기능 회귀 **12/12회**, Python **54개**를 통과했다.
첫 Host 점검의 FIFO 요청은 EPERM이었으며 PREEMPT_RT가 아니다. 후속 권한 적용 결과는 아래에 기록한다.
이 사전 점검 당시 ARM64 runtime과 RT workload는 실행하지 않았다. 이후 native FIFO 측정 결과는 후속 문서에 기록했다.
재현 로그·검증 범위와 다음 조건은 [품질 기록](../quality_policy.md#2026-10-18--arm64-빌드-경계와-rt-사전-점검)에 정리했다.

## 권한 설정 후 기존 IDE 세션에서 실행하기

관리자가 `/etc/security/limits.d/90-stratadrive.conf`에 개발 계정의 soft/hard rtprio 20을 설정했다.
기존 SSH/IDE/Codex process의 0/0 한도는 변경되지 않는다. 새 로그인과 IDE 재시작으로 적용하거나,
이 Host에서 확인한 다음 방식으로 같은 사용자에게 새 PAM 실행 세션을 만들 수 있다.

```sh
sudo -n -u "$(id -un)" -- python3 tools/runtime_diagnostics.py --probe-only \
  --output-dir build/rt-capabilities-new-session
```

`sudo`의 PAM 설정에 `pam_limits.so`가 있어 새 process에 계정의 limit을 적용한다. 명령의 대상은 현재 사용자다.
이 Host에서는 비밀번호 추가 입력 없이 UID 1000/CapEff=0을 유지한 채 20/20 한도를 받았다.
FIFO priority 1과 20은 AVAILABLE, 상한을 넘는 21은 EPERM이었다. 모든 자식 probe는 원래 scheduler를 복원했다.
이는 권한 확인이며 runtime owner의 policy/priority를 설정하거나 PREEMPT_RT·trace 권한을 활성화하지 않는다.
후속 [native FIFO 실행·측정](m3_native_fifo.md)에 owner별 RT 적용·실제값 확인과 같은 시한의 비교 결과를 기록했다.

## 절대 타이머로 누적 지연 줄이기

2026-10-19, [ADR-0043](../adr/ADR-0043-hosted-monotonic-timer-and-placement.md)으로 ViPer timer backend를 바꿨어.
Relative 방식은 이번 실행이 늦게 끝난 시각부터 다음 10 ms를 기다려. 지연이 매 주기 더해질 수 있어.
Absolute 방식은 최초 origin의 10/20/30 ms처럼 다음 예정 시각을 유지해. 늦게 깨어나도 다음 예정 시각을 함께 밀지 않아.
Native multirate는 이미 absolute sleep을 썼고 이번 수정의 대상은 hosted RTOS의 가상 타이머야.

새 backend는 CLOCK_MONOTONIC timerfd야. 놓친 expirations는 기록하고 signal 하나만 보내.
Mmap trace에 예정 시각·wake·send와 실제 policy/CPU를 기록하며 tick 본문에서는 파일 출력을 하지 않아.
일반 POSIX signal은 합쳐질 수 있어서 RTOS release도 서로 다른 timer send와 대조해.
`--timer-mode relative`는 같은 계측의 상대 타이머 대조군, `upstream`은 고정 원본을 사용하는 옵션이야.
원본 checkout을 수정하지 않고 별도 object로 링크해. 새 기본은 `absolute`야.

현재 기준 실행은 다음과 같아. CPU 번호는 이 Host의 예이고 새 output directory를 사용해야 해.

```sh
python3 tools/build_rtos_pilot.py --timer-mode absolute \
  --build-dir build/m3-timer-host --output-dir build/m3-timer-pilot
sudo -n -u "$(id -un)" -- unshare --user --map-root-user --net \
  python3 tests/integration/runtime/check_rtos.py \
  --build-dir build/m3-timer-host --pilot-dir build/m3-timer-pilot \
  --rtos-cpu 1 --plant-cpu 0 --fifo --require-wall-timing \
  --repetitions 3 --output-dir build/m3-timer-results
```

RTOS와 그 ViPer timer는 CPU 1/FIFO 10, 외부 물리는 CPU 0/FIFO 19야.
Linux priority와 Trampoline 내부 Task priority는 별개야. Runner는 일반 priority를 유지하고 설정 거부는 실패로 남겨.
13-tick ResumeAlarm으로 정지 주입을 바꿨지만 실제 정지가 최소 120 ms라는 검사는 그대로야.
처음 12 ticks로 실행한 개발 시험이 120 ms를 못 채워 실패한 기록도 보존했어.

이번 추가 검사는 원래 timer phase부터 RTOS release까지 5 ms 이내, 정상에서는 phase부터 Control 완료까지도 5 ms 이내야.
기존 실제 release부터 완료까지 5 ms라는 검사도 유지해. Relative 모드도 최초 origin의 nominal phase로 계산하므로
매번 target을 뒤로 옮겨 지연을 숨길 수 없어. 미실행 expiration·합쳐진 signal·trace 오류도 timing 실패야.
고장 주입 중 의도한 Control 정지는 원래 fault oracle로 검사하며 정상 완료 지연 통계와 구분해.

동일 CPU map·추가 부하 없음·warm-up 제외 0으로 4 profiles×4 scenarios×3회, 총 48 runs를 실행했어.
순서는 repetition마다 회전했고 아래 ms 값은 **normal 3 runs**의 drift 범위와 관측 최대야.
Drift는 첫 release부터 마지막 release까지 nominal 10 ms 간격과의 차이야.

| Timer / Linux 정책 | Normal drift (ms) | Phase→Control 완료 max (ms) | 추가 Host timing (12 runs) |
| --- | --- | --- | --- |
| Relative / OTHER | 24.565720..30.122158 | 41.513909 | 0/12 PASS |
| Relative / FIFO | 15.016595..17.319982 | 25.781443 | 0/12 PASS |
| Absolute / OTHER | 0.000191..0.007147 | 0.284828 | 12/12 PASS |
| Absolute / FIFO | −0.000862..−0.000368 | 0.276923 | 12/12 PASS |

기능은 48/48 PASS지만 상대 타이머 24회는 추가 timing이 FAIL이야. 전체 verdict와 process exit도 FAIL로 보존했어.
FIFO만으로 relative drift가 없어지지는 않았고, absolute timer로 누적 경로를 없앤 효과가 이 비교에서 나타났어.
이 짧은 무부하 Host 결과를 모든 작업·부하·Target의 정시성으로 확대하지 않아.

별도 native FIFO 회귀는 normal/sanitizer 각각 51/51 PASS야. 같은 observer/CPU map의 진단 12회도 별도로 실행했어.
무부하는 두 정책 모두 3/3 PASS, IO CPU 부하에서는 OTHER 0/3·FIFO 3/3이었어.
OTHER의 187개 miss event를 덮는 sample 모두에서 runqueue 대기가 증가했지만 sample 경계 여유는 최대 2.891313 ms야.
정확한 한 번의 wake 지연이나 원래 sanitizer 두 실패의 원인을 이 누적 카운터에 전부 할당할 수는 없어.

Owned ViPer만 약 35.133 ms 멈춘 별도 주입에서는 expirations 3개 누락을 기록하고 정상 시험을 FAIL로 유지했어.
원본 backend 선택 경로도 기능 4/4를 재검사했어. 이 주입/호환 8회와 개발 probe 8회는 위 48회 비교에 합치지 않아.
Python 63개, C++ normal/sanitizer 각각 523개·정적 분석과 native/ARM64 build를 검사했어.
ARM64는 교차 빌드이며 실제 보드 실행은 아니야.

실행은 clean `554e91c` source야. `build/m3-latency-campaign/`에 48회·native 102회·진단 12회의
원본 CSV/binary timer trace·environment/source/binary hash·manifest·summary를 보존했어.
`build/m3-latency-audit.{py,json,txt}`, `m3-latency-timer-stop*`, `m3-latency-upstream-*`에도 재분석·주입·호환 근거를 둬.
원래 94/96 결과의 두 실패는 그대로이며 kernel trace/perf 권한도 여전히 없어.
Host RTOS의 누적 tick 지연을 수정한 결과와 native 커널 원인·PREEMPT_RT·Target 검증은 구분해야 해.
