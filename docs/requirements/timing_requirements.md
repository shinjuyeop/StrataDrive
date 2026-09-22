# Timing requirements and measurement contract

Status: **DEFINED / Reference Baseline v0.1**. Logical configuration만 정의하며
execution/latency/jitter 실측은 모두 **NOT RUN**이다. Rate와 100 ms 검출 상한은
engineering starting point이며 production timing 보장이 아니다.

## Logical rate baseline

| 단계 | Rate | Period | 적용 의미 |
| --- | --- | --- | --- |
| CARLA simulation / sensor baseline | 20 Hz | 50 ms | 한 Host orchestrator가 tick 소유; sensor/state baseline |
| Planner | 20 Hz | 50 ms | 최신 유효 state snapshot 사용 |
| Vehicle Controller (Classical Controller) | 50 Hz | 20 ms | 센서 frame 재사용 가능; 원천 age 보존 |
| Zone Controller | 100 Hz | 10 ms | validation/allocation/local monitor 및 actuator command publication |
| Steering vECU | 100 Hz | 10 ms | control/dynamics task 및 actual feedback publication |
| Brake vECU | 100 Hz | 10 ms | 위와 동일 |
| Drive vECU | 100 Hz | 10 ms | 위와 동일 |

Communication 구현이 별도 thread여도 외부 publication cadence는 위 baseline을 따른다.
Zone status/Host feedback bridge는 100 Hz 논리 publication starting point다. 재전송된
snapshot은 새 actual sample이 아니다. Safety Supervisor는 Planner의 각 후보에 적용하며
Controller/Zone 출력 guard는 각 실행에서 확인한다. 별도 safety thread rate는 TBD-04다.
Diagnostics aggregation은 control/timeout 경로를 blocking하지 않는다.

50 ms sensor tick 사이 Controller 20 ms, Zone/vECU 10 ms task가 최신 유효 snapshot을
사용한다. Functional simulation 모드는 10 ms logical scheduling quantum을 기준으로
sensor/plant를 5 quantum마다 갱신하는 계약이다. 새 sensor를 임의로 보간/생성하지 않는다.
동시 release의 순서/queue/substep 구현과 plant aliasing 검증은 M3/M6/M7(TBD-04/07)이다.
이 논리 schedule을 실측 CPU schedule로 주장하지 않는다.

## Terms

| 용어 | 정의 |
| --- | --- |
| period | 연속된 예정 release 사이 간격; 실행 시간이나 deadline이 아님 |
| execution time | task start→end의 elapsed monotonic duration; CPU time은 별도 지표 |
| scheduling jitter | actual start − scheduled release (ms, 양수는 늦은 시작); release timestamp도 별도 기록 |
| communication latency | sender publish/enqueue→receiver valid acceptance; serialization, queue, transport 포함, 범위 명시 |
| end-to-end latency | source sensor timestamp→그 입력에 인과적으로 연결된 actual feedback의 CARLA apply |
| deadline | job/event가 완료되어야 할 절대 시각 또는 기준점 대비 허용 duration; period에서 자동 추론하지 않음 |
| deadline miss | finish > absolute deadline; drop/미완료 job도 deadline 도달 시 miss로 집계, 제외하지 않음 |
| source freshness age | now − source generation/acquisition time; 같은 clock domain 또는 보정/불확실성 필요 |
| valid-command age | receiver now − last accepted valid-command RX time; invalid/stale/duplicate 수신은 갱신하지 않음 |
| timeout | 정해진 clock에서 유효 수신 없이 허용 age를 넘은 상태; threshold와 실제 detection latency는 다름 |

Feedback도 last-valid-feedback RX age와 source age를 각각 검사한다. 단순 heartbeat나
bridge 재발행으로 끊긴 실제 actuator stream이 정상으로 바뀌지 않는다.

## Clock, timeout and pause contract

- Runtime local timeout은 **receiver의 monotonic elapsed wall time**을 사용한다.
  UTC는 run 식별용이다. Host와 Target monotonic 값을 직접 빼지 않는다.
- Deterministic functional replay는 simulation clock 기반 timeout을 별도 모드로 허용한다.
  그 결과를 wall-time 100 ms 검증으로 대체할 수 없다. Clock mode는 run 시작 전 고정한다.
- SYS-COM-001/003의 기점 `t0`는 **마지막 유효 수신 시각**이다.
  `t_detect − t0 <= 100 ms`가 판정식이며 fault injection onset과 마지막 유효 RX를 모두 기록한다.
  Local action/state/actual response 시간은 별도이며 100 ms 안에 차량 정지를 보장하지 않는다.
- Timeout threshold + monitor polling/dispatch + execution/jitter margin이 100 ms를 넘지
  않게 M1에서 parameter를 할당하고 M3에서 검증한다(TBD-01/04). Threshold를 100 ms로
  설정한 뒤 다음 10 ms tick에서 검출하는 것은 계약 위반이다. 부하로 지연되면 FAIL이다.
- INIT에서 아직 valid RX가 없으면 age는 unknown이다. Monitoring enable 시각을 acquisition
  deadline의 기점으로 사용하고 100 ms 안에 연결이 성립하지 않으면 unavailable로 남기며
  startup fault를 발생시킨다. INIT 동안 정상 주행을 허용하지 않는다.
- CARLA pause는 wall clock을 멈추지 않는다. 통신도 멈추면 timeout을 검출한다.
  의도된 pause는 사전 기록하고 normal performance window에서 제외하되 silent reset하지 않는다.
  Simulation clock 모드는 pause 동안 logical age가 멈춘다는 것을 명시한다.
- Run reset은 새 run/epoch와 INIT 재진입을 요구한다. 이전 epoch의 frame은 거부한다.
  자동 reconnect만으로 last-valid age/state를 초기화하거나 NORMAL로 복귀하지 않는다.
- Slow synchronous simulation이 Target을 기다려도 wall-time miss를 숨기지 않는다.
  Simulation duration, elapsed wall duration, real-time factor를 함께 보고한다.

Cross-node source freshness 판정의 offset/uncertainty와 source time을 CAN wire 또는
side-channel로 운반하는 방법은 TBD-01/04/05다. M1 로컬 계약 시험은 같은 clock으로
실행할 수 있으나 Host–Target source-age 검증이 완료됐다고 볼 수 없다.

## M3 instrumentation endpoints

아래 endpoint 이름은 trace 의미 계약이며 구현은 M3부터 추가한다. M3에는 존재하는
component 구간만 측정하고 Central/Host/CARLA endpoint는 M5/M7 이후 연결한다.

| Endpoint | 의미 / clock |
| --- | --- |
| sensor_timestamp | sensor acquisition simulation timestamp + frame ID; Host monotonic capture도 기록 |
| central_ingress | sensor/state valid acceptance; Target monotonic |
| planner_start / planner_end | snapshot 사용 시작 / candidate 완료 |
| safety_start / safety_end | candidate 검증 시작 / validated trajectory 완료 |
| controller_start / controller_end | 입력 snapshot 사용 / vehicle-level command 완료 |
| central_command_tx | VehicleCommand publish/enqueue |
| zone_ingress / zone_egress | vehicle command valid acceptance / CAN actuator command enqueue |
| vecu_command_rx | actuator command valid acceptance; raw RX/reject도 별도 event |
| vecu_task_start / vecu_task_end | accepted snapshot 사용 / dynamics update 완료 |
| feedback_tx | 해당 actual sample publish/enqueue |
| zone_feedback_rx / bridge_tx | actuator별 valid RX / Host 송신; 원천 metadata 보존 |
| plant_adapter_ingress | Host의 각 actual feedback valid acceptance |
| carla_actuation_apply | Plant Adapter가 입력을 적용한 시각과 적용 대상 simulation frame |
| next_sensor_timestamp | 다음 sensor frame; 폐루프 확인용이며 기본 E2E 끝점과 구분 |

Run/epoch, source frame, trajectory/vehicle command, actuator command, actual sample의
sequence/correlation을 연결한다. Multirate에서 같은 sensor가 여러 command로 이어지면
각 apply의 causal lineage를 기록하며 일대일 pipeline을 가정하지 않는다. 측정 불가한
구간은 NOT RUN/N/A + 이유로 남긴다. P95/P99의 단계별 합을 E2E percentile로 쓰지 않는다.
Queue wait/copy/pre/post-processing의 소유 구간을 명시해 누락/중복을 방지한다.
Actuator 물리 응답의 settling/도달 시간은 feedback 송신 latency와 다르다(TBD-03).

## Future budget and report

Task deadline, 단계별 latency budget, E2E deadline은 **TBD-04**, 아직 수치가 없다.
Logical period가 같아도 모든 task deadline이 그 period와 같다고 가정하지 않는다.
M3에서는 task release/start/end, Mean/P95/P99/Max, sample/drop 수, eligible jobs와
miss 수/비율, trace overhead를 보고한다. M5/M7에 전체 causal path로 확장한다.

Report에는 Test/Requirement revision, run ID, commit/profile hash, board/OS/kernel/toolchain,
scenario/seed, simulator mode/step, build/instrumentation, model hash/precision,
power/clocks/cooling, background load, warm-up, duration/repetitions, percentile estimator,
clock uncertainty를 기록한다. 동기화 오차 때문에 상한 충족 여부를 판단할 수 없으면
BLOCKED다. AI latency의 pre/inference/post와 camera-to-validated-trajectory endpoint,
FPS의 유효 출력 수/elapsed time, resource 도구/단위는 M10/M12에 고정한다(TBD-09).

Worst observed execution time은 관측 sample의 최대값이다. **WCET bound**나 hard real-time
보장이 아니며, Linux/vCAN 결과로 MCU/실제 CAN timing 보장을 도출하지 않는다.
참조: [Reference Config](../../profiles/reference.yaml),
[CAN ICD](../icd/can_icd.md), [verification](../test-plan/verification_strategy.md).
