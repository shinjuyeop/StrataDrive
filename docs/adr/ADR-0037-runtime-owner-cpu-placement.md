# ADR-0037: RX·감시·물리 실행 owner의 CPU 배치 비교

Date: 2026-10-18. Status: **Host 비교 구현 / 결과·제한은 품질 기록에 연결**.
[ADR-0035](ADR-0035-controlled-cpu-load-and-placement.md)의 같은 CPU 부하에서 RX job이 생략됐고,
[ADR-0036](ADR-0036-asynchronous-drive-actual-feedback.md)의 여섯 stream workload에서도 재현했다.
후속 [ADR-0038](ADR-0038-whole-owner-cycle-observation.md)은 감시·물리 전체 cycle 계측과 RX miss의 시간 대조를 추가한다.

## 관측과 결정

이전 12-run smoke에서 실행된 RX body의 최대 elapsed는 약 0.32 ms였다. 누락 직전 실행은 짧았고
다음 실행이 생략된 release보다 2–3 ms 이상 늦은 구간이 있었다. CPU 대기 지연의 영향을 먼저 비교한다.
Body의 실행 시간을 줄이면 해결된다고 단정하거나 miss를 제외하지 않는다.

TaskSchedule은 최신 release만 실행한다. RX의 period 2 ms와 deadline 3 ms는 별개이며,
다음 release가 왔을 때 이전 job을 생략한 경우도 원래 분모에 남는다. 생략된 job의 duration은 만들지 않는다.

`MultirateRuntimeOptions`에 선택적인 7-owner CPU map을 추가한다. 미지정 시 기존 상속 동작을 유지한다.
순서는 **brake, drive, bms, power, rx, monitor, plant_fixture**다. 실행 전 모든 ID가 inherited mask 안에 있는지
검사하고, 각 thread가 자기 affinity를 설정한 뒤 실제 mask/observed CPU/policy/priority를 capture한다.
설정 실패는 run 실패이며 다른 CPU로 자동 대체하지 않는다. 요청과 실제 배치를 `run.json`에 함께 남긴다.
Owner는 그대로 7개이며 제어 판단·물리 모델·CAN wire·RX budget·period/deadline·보호 기준은 변경하지 않는다.

## 비교 조건

기존 runner에 `--experiment owner-placement`를 추가한다. Allowed CPU A/B는 기존 topology 선택을 재사용한다.
`--runtime-cpu`는 A, `--load-cpu`는 B다. 부모 runner의 affinity는 변경하지 않고 각 runtime thread가 직접 배치한다.

| Layout | CPU A | CPU B | 추가 부하 |
| --- | --- | --- | --- |
| colocated | 없음 | 7개 owner | B |
| rx-isolated | RX | 나머지 6개 | B |
| io-isolated | RX·monitor·plant/fixture | ECU 4개 | B |
| io-baseline | RX·monitor·plant/fixture | ECU 4개 | 없음 |

Loaded 조건은 모두 같은 B에 부하를 둬 부하 위치 변경과 owner 이동을 혼동하지 않는다.
RX만 이동한 조건으로 감시/센서 취득/실제 출력 적용의 간섭을 따로 본다.
부하 worker·7/10 ms 요청 window·실제 CPU 측정·정리·실패 보존은 ADR-0035를 재사용한다.
각 layout의 full/minimal을 기본 3회, 총 24 runs 측정하며 순서를 회전한다. Warm-up 제외는 0이다.
SCHED_OTHER와 priority 0을 확인하며 이 비교에서 RT policy/priority/nice를 바꾸지 않는다.
Nice는 상속하며 변경하지 않는다. Runtime의 thread별 nice는 이번 trace에서 별도 측정하지 않았다.

기존 `--experiment cpu-placement`는 기존 3 layouts와 상속 방식을 유지한다.
`--owner-cpus`는 multirate fault 회귀에서 고정 map을 재현할 때 쓴다. 각 fault의 독립 검출·보호 검사는 유지한다.
Control(배치/부하)와 normal/fault 계약의 verdict를 구분하고 둘 중 실패하면 run/전체 exit는 FAIL이다.
실패 run의 유효한 예정 jobs도 기존 통계에 포함한다. 예비·최종 실행은 별도 directory에 보존한다.

## 해석과 후속

Thread가 달라도 같은 CPU의 실행 지연을 공유할 수 있다. RX만 빠른 것과 센서→ECU→송신→수신이 제시간에
완료되는 것은 별개다. `expired_outputs`, Actual의 sent/received/accepted/expired, 모든 task의 miss/skip,
독립 검출·실제 보호 시각을 함께 확인한다. PASS run만 골라 latency를 비교하지 않는다.

Affinity는 CPU 예약이나 물리적 watchdog 격리가 아니다. 이 Host에서 여러 번 통과해도 다른 부하/VM/Target의
실시간 보장은 아니다. Sanitizer는 기능·수명 확인으로 분리한다. Per-owner RT priority, monitor/plant 전체 cycle의
실행 budget과 watchdog 독립성, Target/차량 E2E는 후속이며 M3 전체 수용을 선언하지 않는다.
전체 32개 requirement/29개 system TC의 Result는 NOT RUN이다.
재현 명령·측정은 [CPU 배치 학습 안내](../learning/m3_cpu_placement.md)와 [품질 기록](../quality_policy.md)을 따른다.
