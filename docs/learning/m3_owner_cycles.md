# M3: 감시·물리 작업이 언제 시작하고 끝났는지 보기

Date: 2026-10-18. Status: **Host 전체 cycle 관측·완료 guard 구현 / RT·Target·M3 수용 후속**.
[Owner별 CPU 배치](m3_cpu_placement.md#owner별로-cpu를-나누기) 다음 단계다.
계측은 [ADR-0038](../adr/ADR-0038-whole-owner-cycle-observation.md), 현재 완료 계약은
[ADR-0039](../adr/ADR-0039-owner-completion-guards.md)에 기록한다.

## 지금 적용한 완료 guard

Monitor와 plant는 2 ms마다 실행하며 각 release의 완료 시한은 **4 ms**다. 각자 1211개 slot(0–2420 ms)을
서로 감시하고 마지막 deadline 2424 ms 이후에도 기존 2440 ms tail까지 실행한다. 전체 관측은 각 1221개다.
정상 판정은 guard 대상에서 missed/skipped 0을 요구한다. 아래 schema 4 관측의 PASS에는 이 기준이 없었다.
4 ms는 첫 Host 설정이며 차량/Target budget은 아니다. RX의 3 ms 시한을 늘린 것이 아니다.

| 멈춘 작업 | 누가 검출하는가 | 보호가 실제 적용되는 때 |
| --- | --- | --- |
| Monitor | Plant가 monitor의 slot 완료를 확인 | Monitor가 멈춘 동안에도 plant가 floor/zero 요청 적용 |
| Plant | Monitor가 plant의 slot 완료를 확인 | 검출 중 flag는 걸지만 실제 physics는 plant 복귀 뒤 |
| 둘 다 | 먼저 실행 가능한 peer가 늦은 완료/누락 확인 | 실행이 재개된 뒤; 공백 중 동작 보장은 없음 |

단순 heartbeat와 달리 완료 slot별 기록을 검사한다. 6 ms 쉬고 다음 slot을 완료해도 이전 slot의 누락은 남고
fault는 latch된다. 보호는 pressure를 기존 floor 이상으로 유지하고 torque를 유한 ramp로 0에 접근시킨다.
전원을 무조건 끊는 동작은 추가하지 않았다.

각 accepted-RX stream도 monitor/plant가 별도의 상태로 감시한다. Monitor가 오래 쉬어도 plant의 수신 감시는 계속된다.
Effective loss는 실제로 먼저 검출한 observer의 원래 last-valid/detected pair다. 늦게 복귀한 monitor의 진단을
앞당겨 적지 않고 `streams[].observers`에 양쪽 기록을 보존한다.

```sh
unshare --user --map-root-user --net python3 tests/integration/runtime/check_timing.py --family multirate --repetitions 1 --owner-cpus 1,1,1,1,0,0,0
unshare --user --map-root-user --net python3 tests/integration/runtime/check_timing.py --family multirate --experiment guard-placement --repetitions 3
```

CPU 번호는 해당 Host의 allowed mask에 맞게 정한다. 첫 명령은 **17 runs**, 두 번째는 4 layouts×2 modes×3회=24 runs다.
두 번째는 IO 동반 배치·RX 단독 분리·monitor 단독 분리·무부하 monitor 분리를 같은 ECU CPU B 조건으로 비교한다.
한 번 통과한 배치를 보장으로 삼지 않는다. 실패도 남기고 full/minimal·build별 통계를 구분한다.

현재 trace schema는 **5**, CAN schema는 **2**다. `owner_cycles.by_owner.<owner>.guarded_deadlines`는 해당 slot만 분모로 삼고
CSV의 `guarded/deadline_ns/detected_ns`와 `run.json.owner_guards`를 대조한다. 생략한 slot에도 deadline/detection은
있을 수 있지만 가짜 start/end는 없다. 미감시 tail에는 deadline이 없다. 아래는 schema 4 계측의 설계·당시 기록이다.

## 계산 시간이 짧아도 주기가 밀리는 이유

2 ms마다 실행을 요청해도 OS가 실제로 CPU를 주는 시각은 다를 수 있다. 작업 중 선점되거나 I/O에서 기다릴 수도 있다.
또 물리 계산이 짧아도 센서·snapshot 전달, frame encoding과 socket TX까지 하면 전체 body는 더 길어진다.
기존 physical.csv의 physics_begin/end는 그중 계산·센서 발행 부분이다. 이제 그 앞뒤를 포함한 body를 별도로 기록한다.

| 시각/지표 | 읽는 방법 |
| --- | --- |
| `wake_target_ns` | 실제 clock_nanosleep에 요청한 절대 기상 시각 |
| `sleep_begin_ns` | sleep 호출 직전. 이때 이미 target보다 늦었을 수도 있다 |
| `start_ns` | sleep 반환 후, 외부 snapshot을 읽기 전 body 시작 |
| `release_ns` | 시작 때 가장 최근에 도래한 2 ms grid. 원래 wake target과 다를 수 있다 |
| `phase_ns` | 기존 감시 판단/물리 적용·취득의 기준 시각. 외부 상태를 읽은 뒤 찍는다 |
| `end_ns` | 보호·계산·센서·CAN fixture 송신·trace body 완료, 다음 sleep 준비 전 |
| `body_elapsed_ms` | start→end의 실제 wall time. 작업 중 대기도 포함 |
| `thread_cpu_ms` | body 안에서 잰 스레드 CPU delta. Full만 기록 |
| `wake_target_to_start_ms` | 요청한 wake부터 실제 시작까지의 지연. 최신 release로 바꿔 작게 만들지 않는다 |
| `sleep_call_lateness_ms` | sleep 호출 자체가 target보다 늦었던 부분 |
| `sleep_return_delay_ms` | max(target, 호출 직전)→반환 후 시각 |

CPU delta와 wall delta의 차이에는 sleep/선점/I/O·계측 경계 등이 영향을 준다. 이를 그대로 특정 scheduler 원인의 시간으로 부르지 않는다.
Clock 이름과 ns 저장 형식도 ns 단위의 물리적 정확도를 보장하지 않는다. CPU 절대 시각은 서로 다른 owner 사이에서 비교하지 않는다.

## 생략한 기회도 기록하기

Enable부터 2440 ms까지 owner마다 1221개의 예정 기회가 있다. 실제 실행한 최신 slot에만 시작·종료를 적고,
이전 slot은 `ran=0`, 나머지 실행 필드는 0이다. 밀린 작업을 한꺼번에 실행해 채우지 않는다.
마지막 body가 늦으면 마지막 slot에 남기며 window 밖의 새 예정 기회를 만들지 않는다.

`skip_locations`는 생략된 release의 위치를 세 가지로 나눈다.

- `inside_previous_body`: 이전 body가 아직 끝나지 않은 구간.
- `before_requested_wake`: 이전 body는 끝났지만 다음 요청 wake보다 앞인 구간. Body 밖 bookkeeping/실행 지연도 볼 수 있다.
- `after_requested_wake`: 요청 wake가 도래한 뒤 실제 시작까지의 구간. 늦은 sleep 호출도 별도 지표로 구분한다.

셋의 합은 skipped_slots다. `body_crossed_next_release`는 body가 다음 예정 기회까지 이어진 횟수다.
Schema 4에서는 owner deadline을 정하지 않아 이를 task deadline miss로 표시하지 않았다.
당시 normal 계약이 PASS여도 owner grid의 skip이 있을 수 있었다. 당시 sanitizer의 RX 단독 분리에서는 monitor/plant가
각각 244개 기회를 생략한 채 기존 계약 2/2 PASS였다. 이 관측을 숨기거나 새 owner budget 충족으로 해석하지 않는다.

## RX와 같은 시간축에서 보기

각 run summary의 `owner_cycles.rx_correlation.events`에는 모든 RX miss의 원래 release/deadline/실행·검출 시각이 남는다.
같은 시각의 monitor/plant slot 실행 여부와 앞/뒤 phase, 그 사이 간격을 대조한다.
RX를 120 ms 멈춘 경우 두 owner는 계속 실행할 수 있다. CPU/Host 간섭에서는 여러 owner의 관측 간격도 함께 벌어질 수 있다.
이는 시간상 대응이며 공통 원인의 증명은 아니다. Kernel scheduler trace·Target 측정은 별도다.

Failed run도 cycle 기록이 유효하면 통계에 포함한다. 기록이 잘못되면 `owner_observation_error`와 제외 label을 표시하고
기존 유효한 ECU/RX job 통계는 유지한다. Full/minimal이나 layout을 한 percentile로 섞지 않는다.

## 실행과 파일

```sh
cmake --build build/m1-angle --parallel 4
python3 tests/unit/timing_report_test.py
unshare --user --map-root-user --net python3 tests/integration/runtime/check_timing.py --family multirate --repetitions 1
unshare --user --map-root-user --net python3 tests/integration/runtime/check_timing.py --family multirate --experiment owner-placement --repetitions 3
```

당시 첫 실행은 기존 9조건에 monitor/plant overrun full/minimal 4조건을 더한 **13 runs**였다. 현재 기본 matrix는 위의 17 runs다.
두 번째는 기존 4 layouts × 2 trace modes × 3회 = 24 runs다. 지정한 output directory를 덮어쓰지 않는다.

| 파일/필드 | 의미 |
| --- | --- |
| `monitor-cycles.csv`, `plant-cycles.csv` | Full/minimal 모두 essential schedule·interval·expiry delta; Full은 CPU clock 추가 |
| `monitor.csv`, `physical.csv`, `actual-*.csv` | 기존 상세 phase·physics 일부·실제 Actual bytes; Minimal은 비어 있음 |
| `run.json.owner_cycles` | Schema 4는 deadline(null); schema 5는 4 ms·guarded slots·검출/적용 margin |
| 각 run report의 `owner_cycles` | 검증한 owner별 개별 표본 통계와 RX miss 대응 |
| `placement_comparison.*.by_owner` | 같은 layout/trace mode의 전체 run을 합친 통계. Run 사이 공백 제외 |
| `owner_excluded_from_statistics` | 기록이 불완전해 제외한 label과 이유 |

당시 trace schema 4와 CAN schema 2를 구분한다. Reader는 기존 trace 2/3/4도 읽지만 없던 시각이나 guard를 만들어내지 않는다.
Body start가 새 sensor/Actual source time이 되는 것은 아니다. 원래 취득 시각·epoch/sequence·보호 인과 순서를 유지한다.

## 6 ms 지연을 넣어 확인하기

`monitor-overrun`/`plant-overrun`은 1100 ms 이후 첫 body 끝에서 한 번 6 ms sleep한다.
새 계측이 전체 지연과 생략된 기회를 잡는지 확인한다. 이 6 ms는 CPU 계산 부하가 아니며 실제 차량 calibration도 아니다.
Plant가 쉬는 동안 도착한 출력과 Actual은 시한이 지나 폐기될 수 있다. 첫 후속 cycle의 expiry delta와 전체 count를 맞추고
당시 Actual sent+expired=240, sent=received=accepted 및 송신 admission 시한을 검사했다. Schema 5 보호 전이에서는
sent+expired=Drive reported job 수다. 다른 시점의 expiry는 FAIL이다.
정상 시험의 expiry 0 기준은 유지한다. 지연 주입 시험 PASS를 정상 timing PASS로 읽지 않는다.

최종 반복 수·PASS/FAIL·관측과 로그 경로는 [품질 기록](../quality_policy.md)에 둔다.
계측 뒤 ADR-0039에서 Host 완료 budget과 교차 감시를 채택했다.
Process/OS 공통 정지·hardware watchdog·RT priority·Target/차량 전체 E2E와 M3 수용 검토는 남는다.

## 완료 guard를 연결한 뒤의 측정

Schema 5 최종 124 runs 중 119 PASS/5 FAIL이다. 기존 IO map의 고장 회귀 3 build×17=51 runs와
상속 배치 17 runs는 통과했다. 배치 비교는 56 runs 중 51 PASS/5 FAIL이며 IO 동반 배치는 14/14 PASS였다.
Monitor 별도 코어는 13/14, 무부하 monitor 별도 코어도 13/14였으므로 CPU를 더 나누면 보장된다고 해석하지 않는다.
현재 Host 기준은 기존 IO 동반 map을 유지한다. 세부 실패와 full/minimal 통계·증거는 [품질 기록](../quality_policy.md)에 둔다.

예를 들어 일반 build monitor-stall/full에서 peer 검출은 deadline 뒤 약 0.10 ms, 보호 요청 적용은 그 뒤 약 0.01 ms였다.
Brake command의 backup 수신 상실 검출은 last-valid 뒤 약 81.94 ms로 monitor 복귀 전에 일어났다.
Plant-overrun/full에서는 감시가 먼저 검출했고 보호는 plant 복귀 뒤 적용됐다. 검출→적용 간격은 약 4.10 ms였다.
이는 특정 Host 표본이며 최대 보장값이 아니다. 두 owner가 함께 정지한 동안의 물리 출력을 보장하는 사례도 아니다.
