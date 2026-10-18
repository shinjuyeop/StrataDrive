# M3: 감시·물리 작업이 언제 시작하고 끝났는지 보기

Date: 2026-10-18. Status: **Host 전체 cycle 관측 / budget 채택·RT·Target 후속**.
[Owner별 CPU 배치](m3_cpu_placement.md#owner별로-cpu를-나누기) 다음 단계다.
결정은 [ADR-0038](../adr/ADR-0038-whole-owner-cycle-observation.md)에 기록한다.

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
Owner의 새 deadline을 period와 같다고 정하지 않았으므로 이를 task deadline miss로 표시하지 않는다.
기존 normal 계약이 PASS여도 owner grid의 skip이 있을 수 있다. 이번 sanitizer의 RX 단독 분리에서는 monitor/plant가
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

첫 실행은 기존 9조건에 monitor/plant overrun full/minimal 4조건을 더한 **13 runs**다.
두 번째는 기존 4 layouts × 2 trace modes × 3회 = 24 runs다. 지정한 output directory를 덮어쓰지 않는다.

| 파일/필드 | 의미 |
| --- | --- |
| `monitor-cycles.csv`, `plant-cycles.csv` | Full/minimal 모두 essential schedule·interval·expiry delta; Full은 CPU clock 추가 |
| `monitor.csv`, `physical.csv`, `actual-*.csv` | 기존 상세 phase·physics 일부·실제 Actual bytes; Minimal은 비어 있음 |
| `run.json.owner_cycles` | Grid·CPU clock·미채택 deadline(null)·주입 sleep 설정 |
| 각 run report의 `owner_cycles` | 검증한 owner별 개별 표본 통계와 RX miss 대응 |
| `placement_comparison.*.by_owner` | 같은 layout/trace mode의 전체 run을 합친 통계. Run 사이 공백 제외 |
| `owner_excluded_from_statistics` | 기록이 불완전해 제외한 label과 이유 |

Trace schema 4와 CAN schema 2를 구분한다. Reader는 기존 trace 2/3도 읽지만 없던 whole-cycle 시각을 만들어내지 않는다.
Body start가 새 sensor/Actual source time이 되는 것은 아니다. 원래 취득 시각·epoch/sequence·보호 인과 순서를 유지한다.

## 6 ms 지연을 넣어 확인하기

`monitor-overrun`/`plant-overrun`은 1100 ms 이후 첫 body 끝에서 한 번 6 ms sleep한다.
새 계측이 전체 지연과 생략된 기회를 잡는지 확인한다. 이 6 ms는 CPU 계산 부하가 아니며 실제 차량 calibration도 아니다.
Plant가 쉬는 동안 도착한 출력과 Actual은 시한이 지나 폐기될 수 있다. 첫 후속 cycle의 expiry delta와 전체 count를 맞추고
Actual sent+expired=240, sent=received=accepted 및 송신 admission 시한을 검사한다. 다른 시점의 expiry는 FAIL이다.
정상 시험의 expiry 0 기준은 유지한다. 지연 주입 시험 PASS를 정상 timing PASS로 읽지 않는다.

최종 반복 수·PASS/FAIL·관측과 로그 경로는 [품질 기록](../quality_policy.md)에 둔다.
Monitor/plant 전체 body를 잰 것과 그 작업의 watchdog/실행 budget을 채택한 것은 별개다.
RT priority·감시 독립성·Target/차량 전체 E2E와 M3 수용 검토는 남는다.
