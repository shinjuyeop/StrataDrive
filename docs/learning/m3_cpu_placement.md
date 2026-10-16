# M3: CPU에 부하를 주고 배치를 비교하기

Date: 2026-10-16. Status: **Host 고정 부하·CPU 배치 실험 / Target·RT 우선순위 검증 후속**.
[다중 주기 실행](m3_multirate_runtime.md) 다음 단계다. 결정은 [ADR-0035](../adr/ADR-0035-controlled-cpu-load-and-placement.md)에 있다.

## 무엇을 비교하나

주기가 10 ms라는 것은 10 ms마다 실행 기회가 생긴다는 뜻이다. CPU를 실제로 언제 얻는지는 scheduler와 부하에 달려 있다.
이번 실험은 ECU 코드를 그대로 두고 CPU 배치와 추가 부하만 바꾼다.

| 조건 | ECU·RX·monitor·plant 7개 owner | 추가 부하 |
| --- | --- | --- |
| baseline | 모두 CPU A | 없음 |
| shared | 모두 CPU A | CPU A |
| separate | 모두 CPU A | CPU B |

모든 조건에서 runtime mask가 같아 추가 부하와 위치의 영향을 비교할 수 있다.
별도 CPU는 가능하면 다른 physical core를 선택한다. SMT sibling이나 같은 VM/host의 공유 자원은 완전한 격리가 아니다.
각 owner가 기록한 `allowed_cpus`, `observed_cpu`, `policy`, `priority`로 요청이 적용됐는지 확인한다.
SCHED_OTHER를 유지하며 이번에는 RT priority를 조절하지 않는다. 부모 runner는 CPU를 고정하지 않는다.

## 요청 부하율과 실제 CPU 시간

부하 process는 10 ms마다 7 ms 동안 계산할 window를 요청한다. **요청 duty는 70%**다.
CPU를 다른 작업에 빼앗기면 실제로는 그보다 적게 계산할 수 있다. `load_metrics`의 실제 CPU 비율을 함께 읽어야 한다.

- **Job elapsed:** 실행 시작→종료의 wall time. 중간 선점/대기를 포함한다.
- **Start lateness:** 예정 release→실제 시작. CPU를 얻기까지 밀린 정도다.
- **Response time:** 예정 release→종료. Relative deadline과 비교할 값이다.
- **Load CPU time:** 부하 worker가 실제 CPU에서 실행한 시간. Wall time과 구분한다.

Measurement window를 가로지르는 cycle의 CPU를 임의로 나누지 않으므로 실제 busy 계산은 하한·상한 두 값으로 보고한다.
완전히 포함된 busy 구간의 CPU 합이 하한, 일부라도 겹치는 busy 구간 전체 CPU 합이 상한이다.
Bookkeeping을 포함한 worker loop 전체의 process CPU 비율도 별도 기록하며 두 지표의 측정 범위를 구분한다.
Skipped load cycle도 원래 release에 남고 몰아서 실행하지 않는다.

## 실행

기존 `actuator_demo`와 timing runner를 사용한다. CPU A/B는 현재 allowed mask에서 자동 선택한다.
직접 지정하려면 `--runtime-cpu`와 `--load-cpu`를 추가한다. 같은 CPU를 두 값으로 지정하거나 allowed mask 밖이면 시작 전에 거부한다.

```sh
cmake --build build/m1-angle --parallel 4
python3 tests/unit/timing_report_test.py
unshare --user --map-root-user --net python3 tests/integration/runtime/check_timing.py --family multirate --experiment cpu-placement --repetitions 3
```

3 layouts × 2 trace modes × 3 repetitions = 18 runs다. Layout 순서를 회전하고 full/minimal 순서도 번갈아 실행한다.
Warm-up 제외는 0이다. 설정 기록은 [reference.yaml](../../profiles/reference.yaml)의 `m3_cpu_placement_fixture`이며 YAML loader는 없다.
기존 fault matrix는 `--experiment faults`가 기본이다. Deadline이나 ECU 기능 설정을 변경하지 않는다.

## 결과 읽기

| 파일/필드 | 의미 |
| --- | --- |
| `environment.json`의 `experiment` | 선택한 CPU·topology·요청 부하·실험 순서, 기존 source/profile/binary hash |
| 각 `run.json`의 `threads` | 7개 owner의 실제 mask/observed CPU·scheduler |
| `*.load.json` | Worker의 모든 예정/실행 cycle·wall/CPU 시간, 정상 stop/exit와 전체 수명 |
| 각 run의 `placement_and_load_verdict` | 배치 적용·부하 수명/측정 검증. ECU 계약 PASS와 구분 |
| `summary.json`의 `placement_comparison` | Layout/trace별 모든 유효 job의 분모·miss/skip와 Mean/P95/P99/Max |
| `trace_overhead_comparison.by_layout` | 같은 layout에서만 full/minimal 비교, 포함·제외 run label |

기존 normal 계약이 실패하면 run과 전체 summary는 FAIL이며 runner도 nonzero로 끝난다.
이때 schedule/interval이 유효한 실패 run의 job도 통계에 남긴다. 기록 자체가 불완전한 run은 제외 label을 표시한다.
Deadline 위반 때문에 정상 목표에 도달하지 못한 경우를 측정 실패와 혼동하지 않는다.
서로 다른 주기/layout을 한 percentile로 섞지 않고 run 사이 공백도 주기 지표에 넣지 않는다.
Full/minimal 차이는 계측 비용 외에도 scheduling/cache·고장 뒤 실행 경로 차이를 포함한다.

Worker는 run마다 별도 process로 실행하고 ready 확인 후 runtime을 시작한다.
분석이 실패해도 finally에서 stop/join하며 강제 종료가 필요하면 control FAIL이다.
최종 측정 수치와 실행/정적 검사 범위는 [품질 기록](../quality_policy.md)에 남긴다.

## 이번 Host 관측

Runtime CPU 0·분리 부하 CPU 1을 사용했고 보이는 topology의 core ID도 서로 달랐다.
Normal build의 3회 반복에서 full/minimal을 합친 run 수와 RX 결과는 다음과 같다.

| Layout | Normal 계약 PASS / runs | RX miss / 예정 jobs |
| --- | --- | --- |
| baseline | 6 / 6 | 0 / 7200 |
| shared | 0 / 6 | 48 / 7200 |
| separate | 6 / 6 | 0 / 7200 |

Shared의 miss 48개는 실행 시한을 놓쳐 skip한 job이다. 실행한 RX job의 response P99는 full 0.761 ms·minimal 0.882 ms로
3 ms deadline보다 작았지만, P99 표본에 실행하지 못한 job의 duration을 만들 수는 없다.
따라서 **P99와 함께 전체 예정 job의 miss/skip 비율을 봐야 한다.** 독립 monitor의 latch로 Drive가 활성화되기 전에 보호 상태가 됐다.
이 run을 정상 구동·토크 감소 검증 PASS로 해석하지 않는다.

Production build도 같은 조건에서 shared 6 runs가 실패했다. Sanitizer는 1회 반복했고 shared 2 runs가 실패했다.
최종 42 runs 중 ECU 계약은 28 PASS / 14 FAIL이며 배치·부하 적용 검사는 42/42 PASS다.
요청 70%에 대해 normal build의 measurement busy CPU 하한/상한 관측 범위는 66.51–69.46%였다.
Threshold를 완화하거나 실패 조건을 제외하지 않았다. 예비 실행과 최종 기록은 각각 별도 directory에 보존한다.

## 다음 판단

CPU 배치를 분리했을 때 결과가 좋아져도 그 Host sample의 관측이다. Affinity는 CPU 예약·hard real-time 보장이 아니다.
Host/VM 다른 부하·interrupt·DVFS·cooling은 통제하지 않았으며 sanitizer 값도 대표 성능으로 사용하지 않는다.
Monitor와 plant까지 CPU A를 공유하므로 독립 OS/하드웨어 watchdog을 검증한 실험은 아니다.

Drive 비동기 torque는 현 CAN 계약에서 여전히 unavailable이다. Sampling 동기화 또는 timestamp 계약과
M3 수용 검토가 다음이며 owner별 배치/priority·Target·차량 전체 E2E는 후속이다.
전체 32개 요구/29개 system TC는 NOT RUN이며 M1/M2 학습자 수용도 별도로 남긴다.
