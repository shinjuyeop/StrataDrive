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

단위는 ms 후보다. Period, deadline, latency budget은 서로 다른 값이다. Safety Supervisor 뒤
Classical Controller 구간 및 feedback/Plant Adapter 경로도 end-to-end 합계에 포함한다.

| 단계 / 측정 endpoint | Period | Deadline | Budget | Mean | P95 | P99 | Max observed | Jitter | Miss count / jobs | Samples |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sensor ingress: 수집 → Central Vehicle Compute에서 사용 가능한 입력 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Perception: 입력 수용 → observation 준비 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Planner: snapshot 수용 → trajectory 후보 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Safety Supervisor: 후보 수신 → 검증된 trajectory | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Classical Controller: 검증된 입력 → vehicle command | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Central Vehicle Compute–Zone Controller Ethernet: publish → 유효 수신 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Zone Controller 처리: 수신 → CAN command queue 등록 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| CAN/vECU: command queue 등록 → control task에서 수용 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Actuator response: demand 수용 → 정의된 응답 기준 도달 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| Feedback/Plant Adapter: 응답 feedback → plant 입력 적용 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |
| End-to-end: sensor 수집 → 해당 plant 입력 적용 | TBD | TBD | TBD | NOT_MEASURED | — | — | — | — | — | — |

각 queue의 대기, sensor age, pre/post-processing, copy/transport를 어느 구간에
포함할지 중복과 누락 없이 정의한다. 위 표는 일대일 pipeline을 가정한 template이다.
Multirate/parallel stage에서는 실제 causal path와 response criterion을 별도로 정의한다.
P95/P99의 단순 합을 end-to-end percentile이라고 부르지 않는다. Sequence/correlation
ID로 source frame과 적용 command/actual feedback을 연결하고 stale/missing frame도
집계한다. Actuator response latency는 step 응답의 도달 조건이나 settling 등의
물리 기준을 먼저 정해야 하며 현재 TBD다.

## Fault timing template

| Fault / Requirement | 주입 또는 상실 기점 | 검출 시점 | Local action 시점 | System state 변경 시점 | 실제 응답 시점 | 검출 budget | 반응 budget | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STEERING_ECU_LOSS / SYS-COM-001 | TBD; last valid RX와 loss onset을 모두 기록 | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | 100 ms 예시, TBD | TBD | NOT_RUN |
| Safety-critical interface 상실 / SYS-SAFE-001 | TBD | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | TBD | TBD | NOT_RUN |

Fault detection latency = detection − defined fault onset, fail-safe reaction latency
= protective action − fault onset을 후보로 하고 detection→action도 별도 측정한다.
통신 상실의 onset, last-valid-RX, 다음 기대 수신 시각 중 어떤 값을 요구사항의
기점으로 삼을지 먼저 결정한다. System state 변경만으로 실제 actuator 보호 반응을
검증했다고 판단하지 않는다.

## Measurement report template

Run ID, requirement/test IDs, commit/profile hash, board/OS/kernel/toolchain,
scenario/seed, simulator mode/step, build/instrumentation, model hash/precision,
power/clocks/cooling, background load, warm-up, duration/repetitions, sample/drop count,
percentile estimator, trace overhead와 clock uncertainty를 기록한다.
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
