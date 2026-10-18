# M3: Steering을 실제 RTOS Task로 실행하기

Date: 2026-10-18. Scope: **Trampoline POSIX Host 파일럿**. Target·RTE/BSW·실시간 수용은 후속이다.
결정과 clock/budget 경계는 [ADR-0040](../adr/ADR-0040-steering-rtos-pilot-and-delay-observation.md)에 있다.

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
- `control-stall`: 600 ms 이후 Control이 12 ticks WaitEvent한다. Watch·Receive와 외부 물리의 진행을 확인한다.

`rtos-jobs.csv`는 release·start·phase·end·sensor/Actual source·Watch 검출·suspend/resume를 기록한다.
`plant.csv`와 `actual.csv`는 외부 물리 및 실제 CAN Actual 수신이다. JSON은 OS API 오류·폐기·보호 적용을 담는다.
기능 PASS와 함께 wall timing은 별도 상태로 표시한다. 누락·늦은 보고·없는 종료 trace를 정상으로 간주하지 않는다.

## 10 ms tick이 정확히 10 ms인가

이 target은 ViPer의 relative sleep로 10 ms tick을 발생시킨다. Linux에서 늦게 실행되면 tick이 밀리거나 signal이 합쳐질 수 있다.
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

`*-schedstat.csv`에서 CPU 실행 누적과 runqueue 대기 누적을 구분한다. 누락 구간을 덮는 두 sample의 차이를 보고
그 구간에서 CPU를 기다린 시간이 늘었는지 확인한다. 앞뒤 sample 경계가 넓으면 옆 작업의 대기도 포함될 수 있다.
따라서 report는 전체 구간의 관측과 불확실성을 함께 기록한다. 표본이 없으면 unknown이다.
Perf/tracefs가 막혔다는 원래 오류도 environment에 남긴다. 정확한 timer→wakeup→CPU 전환 분석은 권한이 있는 환경에서 후속으로 진행한다.
