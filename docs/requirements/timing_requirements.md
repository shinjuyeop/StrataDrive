# Timing requirements and budget template

Status: **DRAFT / TBD**. SYS-PERF-001, SYS-COM-001, SYS-SAFE-001을 구체화하는
측정 설계다. Budget/측정값은 전부 미확정/미측정이며 0으로 채우지 않는다.

## Clock and measurement contract

- Host와 Target의 local monotonic clock은 서로 직접 뺄 수 없다. Cross-node latency는
  검증된 synchronization/offset 추정과 uncertainty 또는 같은 clock endpoint가 필요하다.
- Source simulation timestamp/frame ID, source monotonic timestamp/clock ID, receive time,
  sequence와 run ID를 구분해 보존한다. wall-clock UTC는 run 식별용이며 duration 기준과 구분한다.
- Functional SIL의 simulation time과 scheduler/communication의 elapsed wall time을 별도 기록한다.
  Timeout 기준 clock, pause/reset 처리와 fixed-step/multirate scheduling은 M0 TBD다.
- Synchronous CARLA가 느려진 target을 기다려도 real-time 성능을 만족한 것으로 처리하지 않는다.
  Replay/step 모드와 wall-clock performance 모드 및 real-time factor를 함께 기록한다.
- Execution time은 task start→finish elapsed 값과 CPU time 중 무엇인지 명시한다.
  release jitter는 actual release − scheduled release, deadline miss는 finish > absolute deadline으로
  정의하는 초안이며 sign convention/late dropped job 처리와 sampling policy를 확정한다.

## Stage budget / observation table

단위는 ms 후보다. Period, deadline, latency budget은 서로 다른 값이다. Safety 뒤
Controller 구간 및 feedback/adapter 경로도 end-to-end 합계에 포함한다.

| Stage / measurement endpoints | Period | Deadline | Budget | Mean | P95 | P99 | Max observed | Jitter | Miss count / jobs | Samples |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sensor ingress: acquisition → Central usable input | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Perception: input accepted → observation ready | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Planner: snapshot accepted → trajectory candidate | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Safety: candidate received → validated trajectory | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Controller: validated input → vehicle command | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Central-Zone Ethernet: publish → valid receive | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Zone processing: receive → CAN command queued | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| CAN/vECU: command queued → accepted by control task | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Actuator response: demand accepted → defined response criterion | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Feedback/adapter: response feedback → applied plant input | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| End-to-end: sensor acquisition → corresponding plant input applied | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |

각 queue의 대기, sensor age, pre/post-processing, copy/transport를 어느 구간에
포함할지 중복과 누락 없이 정의한다. 위 표는 일대일 pipeline을 가정한 template이다.
Multirate/parallel stage에서는 실제 causal path와 response criterion을 별도로 정의한다.
P95/P99의 단순 합을 end-to-end percentile이라고 부르지 않는다. Sequence/correlation
ID로 source frame과 적용 command/actual feedback을 연결하고 stale/missing frame도
집계한다. Actuator response latency는 step 응답의 도달 조건이나 settling 등의
물리 기준을 먼저 정해야 하며 현재 TBD다.

## Fault timing template

| Fault / requirement | Injection or loss origin | Detected at | Local action at | System state at | Actual response at | Detection budget | Reaction budget | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STEERING_ECU_LOSS / SYS-COM-001 | TBD; last valid RX와 loss onset을 모두 기록 | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | 100 ms example, TBD | TBD | NOT_RUN |
| Safety-critical interface loss / SYS-SAFE-001 | TBD | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | TBD | TBD | NOT_RUN |

Fault detection latency = detection − defined fault onset, fail-safe reaction latency
= protective action − fault onset을 후보로 하고 detection→action도 별도 측정한다.
통신 상실의 onset, last-valid-RX, 다음 기대 수신 시각 중 어떤 값을 요구사항의
기점으로 삼을지 먼저 결정한다. System state 변경만으로 실제 actuator 보호 반응을
검증했다고 판단하지 않는다.

## Measurement report template

Run ID, requirement/test IDs, commit/profile hash, board/OS/kernel/toolchain,
scenario/seed, simulator mode/step, build/instrumentation, model hash/precision,
power/clocks/cooling, background load, warm-up, duration/repetitions, sample/drop count,
percentile estimator, trace overhead and clock uncertainty를 기록한다.
Outlier를 숨기지 않고 miss count, total eligible jobs와 miss rate를 함께 보고한다.
AI latency의 pre/inference/post 범위, Camera-to-trajectory의 acquisition→validated
trajectory 등 endpoint를 확정한다. FPS는 유효 처리 출력 수/elapsed time으로 정의한다.
CPU/GPU utilization, RAM, power, temperature의 도구/샘플링/단위도 같은 report에 남긴다.

## WCET terminology

**Worst observed execution time**은 지정한 환경/부하/샘플에서 관측한 최대 실행
시간이며, 관측하지 못한 실행 시간의 상한을 증명하지 않는다.
**WCET-oriented timing analysis**는 향후 stress, scheduling, blocking, interference,
path coverage 등을 검토하는 활동을 뜻한다. 정적 WCET 분석과 보장된 WCET bound는
M0에서 수행하거나 얻지 않았다. Max latency와 execution time을 혼동하지 않으며,
Linux/vCAN 관측에서 MCU나 실제 CAN의 시간 보장을 도출하지 않는다.
