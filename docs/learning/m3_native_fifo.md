# M3: 같은 workload를 일반/FIFO 우선순위로 비교하기

Date: 2026-10-18. Scope: **Host native Linux 실행**. Trampoline 파일럿·Jetson runtime과 별도다.
결정은 [ADR-0042](../adr/ADR-0042-native-owner-fifo-scheduling.md)에 있다.

RT 권한은 우선순위를 요청할 수 있는 범위다. 이번 코드는 그 권한으로 각 thread에 Linux SCHED_FIFO를 요청한다.
일반 실행은 CPU를 다른 일반 작업과 나눠 쓰며 FIFO 실행은 높은 priority의 runnable thread부터 실행한다.
FIFO thread가 sleep/I/O로 대기하면 낮은 priority의 작업도 실행할 수 있다. 이 설정만으로 모든 지연이 없어지지는 않는다.

## 준비와 실행

```sh
cmake --build build/m1-angle --parallel 4
sudo -n -u "$(id -un)" -- unshare --user --map-root-user --net \
  python3 tests/integration/runtime/check_timing.py --family multirate --experiment scheduler \
  --runtime-cpu 0 --load-cpu 1 --repetitions 3 --output-dir build/m3-fifo-comparison
```

CPU 0/1은 이 Host의 예다. Inherited allowed mask 안의 다른 두 CPU로 바꿀 수 있으며 topology도 기록한다.
같은 사용자 PAM 실행 세션으로 rtprio 한도를 받고 별도 network namespace에서 vCAN을 만든다.
이 Host의 비밀번호 없이 실행 가능한 경로는 [권한 적용 기록](m3_rtos_pilot.md#권한-설정-후-기존-ide-세션에서-실행하기)에 있다.
최종 실행 전에 새 output directory를 선택한다. 설정 적용이 거부되면 실패를 기록하며 일반 policy로 대체하지 않는다.

| 조건 | ECU/RX·monitor·plant 정책 | 추가 부하 |
| --- | --- | --- |
| other-quiet | 모두 SCHED_OTHER/0 | 없음 |
| fifo-quiet | 각 owner에 명시한 SCHED_FIFO | 없음 |
| other-loaded | 모두 SCHED_OTHER/0 | ECU CPU의 SCHED_OTHER 부하 |
| fifo-loaded | 각 owner에 명시한 SCHED_FIFO | 같은 CPU·같은 부하 |

각 조건은 full/minimal trace를 3회씩 실행해 총 24 runs다. ECU CPU=1, RX/monitor/plant CPU=0 배치를 유지한다.
`--owner-cpus`로 명시한 일곱 CPU map도 사용할 수 있다. `--owner-fifo`는 일곱 priority를 바꾸는 옵션이며
기본 map은 Brake/Drive/BMS/Power/RX/monitor/plant 순서로 **10,10,9,10,18,20,19**다.

## 시작 전 검증이 필요한 이유

수신만 RT가 되고 감시가 일반 priority로 남으면 계획과 다른 시험이 된다. 그래서 모든 owner가 설정과 실제값 확인을
마칠 때까지 기다린다. 하나라도 실패하면 gate를 열지 않아 CAN/제어/물리 본문이 시작되지 않는다.
성공 후에는 기존 enable 시각과 주기를 그대로 사용한다. 작업이 끝나면 main/plant thread의 설정도 원래대로 복원한다.
이 대기용 mutex는 startup에만 쓰며 제어 본문의 기존 snapshot 전달 방식을 바꾸지 않는다.

`run.json`의 `runtime_scheduling`에 요청 priority, 준비 시각·오류, gate release와 호출 thread의 전/후 설정이 있다.
기존 `threads`는 각 owner에 적용된 실제 policy/priority/CPU/TID다. CSV에는 원래 release/시한과 실행하지 못한 slot도 남는다.
설정이 실패하면 JSON·빈 실행 행·원래 errno를 남기고 nonzero로 종료한다. 허용 상한보다 높은 priority는 권한 오류다.

## 결과 읽기

먼저 per-run의 `placement_and_load_verdict`와 요청/실제 정책이 맞는지 확인한다. 그다음 원래 timing 계약 PASS/FAIL,
skip/miss 수, release→완료와 wake 지연, body/CPU 시간, 보호가 실제 물리에 적용된 시각을 확인한다.
Control이 실패한 run은 `control_excluded_runs`에 남기고 비교 통계에서 제외한다. 유효한 timing FAIL은 통계에 포함한다.
Full과 minimal은 별도 관측이며 차이를 deadline에서 빼지 않는다. 정상 24 runs와 fault 회귀·sanitizer 표본도 합치지 않는다.

현재 kernel은 PREEMPT_DYNAMIC이다. FIFO 적용과 PREEMPT_RT kernel은 별개이며 kernel trace 권한도 자동으로 생기지 않는다.
실제 보드/차량의 정시성, WCET, 전체 M3 수용 여부는 별도 검토다.

## 2026-10-19 측정 결과

일반/FIFO 비교 24회는 모두 PASS였다. 추가 부하에서 Drive의 release→완료 지연은 다음과 같아.
각 값은 같은 trace 조건의 3 runs에서 관측한 p99이며 단위는 ms다.

| Trace | 일반 p99 | FIFO p99 | 기존 Drive 시한 |
| --- | --- | --- | --- |
| Full | 1.947 | 0.065 | 5 ms |
| Minimal | 2.450 | 0.073 | 5 ms |

CPU를 많이 쓰는 일반 작업과 경쟁할 때, 깨어난 제어 thread가 우선 실행되도록 설정한 결과를 볼 수 있어.
다만 quiet/minimal RX max는 FIFO 쪽이 더 컸고 둘 다 시한 안이었다. 모든 지연을 개선하거나 정시성을 보장하는 결과는 아니야.

고장 회귀는 normal OTHER/FIFO 각각 17/17, sanitizer OTHER 15/17·FIFO 17/17이었다.
Sanitizer 일반 실행의 두 실패에는 요청 wake 뒤 약 2.05–2.11 ms 지연과 owner slot 누락이 있었다.
한 run에서는 RX 정지 주입 전에 보호가 걸려 Drive가 활성화되지 않았다. 원래 시한·보호 계약을 유지해 FAIL로 보존했다.
정확한 timer/IRQ/CPU 배정 원인은 kernel trace가 없어 아직 분리하지 못했다.

기존 Trampoline 회귀 4/4를 포함한 최종 실행은 **94/96 PASS**야. C++은 normal/sanitizer 각각 523개,
당시 Python 59개와 정적 분석·native/별도 OS/ARM64 빌드도 검사했다. 상세 원인·scope·재현 로그는
[품질 기록](../quality_policy.md#2026-10-19--native-owner별-fifo-실행과-동일-부하-비교)에 정리했다.

## 수용 검토에서 결정한 것

[M3 수용 검토](../m3_acceptance_review.md)에서 IO 동반 배치/FIFO를 다음 Host 통합의 실행 기준으로 선택했다.
일반 실행의 기본값은 유지하며 FIFO는 CLI로 명시해. 두 sanitizer OTHER 실패와 전체 M3 수용은 아직 열려 있어.
검토 중 pooled guarded 주기 통계의 run 사이 gap 오류를 수정했고 Python 60개가 통과했어.
원본 96회를 재분석해 해당 분포만 교정했으며 판정·Drive/RX 지연·miss/skip은 동일해. 새 workload 실행은 없었어.
로그의 `floor_applied_ns`/`zero_applied_ns`는 plant에 보호 목표가 적용된 시각이야.
압력·토크가 목표에 도달한 시각은 `physical.csv`에서 따로 읽어야 해.
