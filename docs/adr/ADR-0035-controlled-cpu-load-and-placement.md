# ADR-0035: 고정 부하와 CPU 배치를 구분하는 Host 실험

Date: 2026-10-16. Status: **M3 Host 실험 구현 / 측정 결과는 품질 기록에 연결**.
2026-10-18 follow-up: [ADR-0036](ADR-0036-asynchronous-drive-actual-feedback.md)은 Actual RX 비용과 drain tail을 추가한다.
아래 실험 protocol은 유지하며 10월 16일 측정과 새 workload 결과를 구분한다.
후속 [ADR-0037](ADR-0037-runtime-owner-cpu-placement.md)은 이 비교를 보존하고 owner별 CPU map 실험을 추가한다.
[ADR-0034](ADR-0034-multirate-runtime-and-can-loss-monitoring.md)의 ECU 기능·period/deadline·CAN 계약을 유지한다.
TBD-04의 부하/배치 측정 protocol 부분 결정이며 Target/차량 budget 확정은 아니다.

## 결정

기존 timing runner에 `--experiment cpu-placement`를 추가한다. 새 executable이나 ECU의 load 분기를 만들지 않는다.
모든 runtime owner 7개를 allowed logical CPU A에 고정하고 아래 조건을 비교한다.

| Layout | Runtime | 별도 load process |
| --- | --- | --- |
| baseline | CPU A | 없음 |
| shared | CPU A | CPU A |
| separate | CPU A | 다른 CPU B |

CPU는 부모의 allowed mask 안에서 선택한다. B는 가능하면 SMT sibling과 다른 physical core를 고른다.
Topology가 없거나 사용자가 같은 core의 다른 logical CPU를 명시한 경우도 실제 topology를 기록하며 물리 격리를 주장하지 않는다.
부모 runner의 mask는 변경하지 않고 runtime child가 exec 전에 affinity를 설정해 모든 thread가 상속한다.
각 owner가 직접 capture한 mask·observed CPU·policy/priority를 결과와 대조한다.
SCHED_OTHER·상속된 nice를 유지하고 RT scheduling/priority 변경은 하지 않는다.

## 부하의 의미와 수명

별도 process가 10 ms absolute release마다 7 ms wall busy window를 요청한다.
이는 요청 duty 70%이며 실현된 CPU 사용률 70%를 보장하지 않는다. 선점·부하 worker의 누락 cycle도 원래 release와 함께 기록한다.
실제 busy 구간의 thread CPU time과 wall interval을 측정하고, runtime 측정 window에 완전히 포함된 busy 구간의 CPU 합을 하한,
겹치는 busy 구간 전체의 CPU 합을 상한으로 보고한다. 경계 cycle의 CPU를 비례 배분해 만들어내지 않는다.
이 경계는 busy 계산에 한정하며 bookkeeping을 포함한 worker loop 전체의 process CPU 비율은 별도 기록한다.

Run마다 worker를 새로 만들고 ready handshake 후 runtime을 시작한다. Worker는 measurement window 전체에 걸쳐 살아 있어야 한다.
Runtime/analysis 실패에도 finally에서 stop→결과 수집→join을 수행하고, 필요하면 자신이 만든 child만 terminate/kill한다.
강제 종료/worker 오류는 control FAIL이다. 15 s hard limit은 남은 worker를 제한하며 정상 측정 길이는 기존 2.4 s+tail 40 ms다.
Trace와 worker 결과는 실행 중 파일에 쓰지 않고 종료 후 보존한다.

## 반복·판정

각 layout의 full/minimal trace를 기본 3회, 총 18 runs 실행한다. Layout 순서는 반복마다 회전하며 full/minimal 순서도 번갈아 쓴다.
Warm-up 제외는 0이다. CPU 시간·release 지연·job elapsed·deadline miss/skip은 별개다.
조건별 individual sample로 Mean/P95/P99/Max를 만들며 다른 layout/주기의 sample을 섞지 않는다.
여러 run 사이 공백은 task interval에 포함하지 않는다.

기존 normal 계약은 유지한다. 부하에서 deadline/물리 목표/valid RX 계약 위반이 있으면 FAIL과 nonzero exit를 유지한다.
실패 run도 schedule/interval이 유효하면 모든 job을 통계에 남긴다. 통계에 넣을 수 없는 run은 label을 명시한다.
배치·부하 적용 성공과 ECU 계약 충족을 구분하고, 실패 조건을 조용히 재실행하거나 threshold를 바꿔 PASS로 만들지 않는다.
Full/minimal 차이에는 scheduling/cache와 fault path 차이가 포함될 수 있어 계측 비용의 상한으로 쓰지 않는다.

## 범위와 후속

CPU affinity는 resource reservation이나 fault isolation이 아니다. Monitor와 plant도 같은 CPU를 공유하는 비교이며
host/VM의 다른 process·interrupt·DVFS·cooling은 통제하지 않는다. Controller/plant/transport 비용의 대표 WCET도 아니다.
Sanitizer는 기능/수명 검사이며 성능 비교의 대표 값으로 사용하지 않는다.
결과는 [학습 안내](../learning/m3_cpu_placement.md)와 [품질 기록](../quality_policy.md)에 연결한다.
Drive sampling/timestamp 계약, 실제 priority/owner별 배치·Target 검증과 M3 수용 검토는 후속이다.
전체 32개 요구/29개 system TC의 NOT RUN은 유지한다.
