# Timing requirements and measurement contract

Status: **DEFINED / Reference Baseline v0.1 + M3 Host 다중 주기·CAN 상실·CPU 부하/배치 부분 측정**.
차량 전체 E2E/Target latency·차량 전체 multirate 실측은 **NOT RUN**이다.
M1의 local CAN timeout/expiry fixture 부분 측정은 별도로 기록한다. Rate와 100 ms 검출
상한은 engineering starting point이며 production timing 보장이 아니다.

## Logical rate baseline

| 단계 | Rate | Period | 적용 의미 |
| --- | --- | --- | --- |
| CARLA world / Vehicle State (M7-1d 개정) | 100 Hz | 10 ms | 단일 Host tick owner; 매 frame 새 snapshot, 실제 wheel feedback 적합성은 미확정 |
| CARLA RGB / Semantic GT | 20 Hz | 50 ms | world5frame마다 capture; GT는 학습/평가 전용 |
| Planner | 20 Hz | 50 ms | 최신 유효 state snapshot 사용 |
| Vehicle Controller (Classical Controller) | 50 Hz | 20 ms | 센서 frame 재사용 가능; 원천 age 보존 |
| Central VCU/session/bridge | TBD-04/05/14 | M4/M5 task 검증 전 결정 | 별도 vehicle management/allocation·trusted INIT·원천 feedback 집계; 기존 Controller/Zone rate를 자동 복제하지 않음 |
| Zone Controller | 100 Hz | 10 ms | scoped validation/local monitor 및 actuator command dispatch |
| Steering vECU | 100 Hz | 10 ms | control/dynamics task 및 actual feedback publication |
| Brake vECU | 100 Hz | 10 ms | 위와 동일 |
| Drive vECU | 100 Hz | 10 ms | 위와 동일 |
| BMS control / limits | 50 Hz | 20 ms | EV wire 초안; M3 Host runnable 부분 측정 |
| Power lifecycle | 100 Hz | 10 ms | BMS leaf의 별도 runnable; M3 Host 부분 측정 |

Communication 구현이 별도 thread여도 외부 publication cadence는 위 baseline을 따른다.
Zone status/Host feedback bridge는 100 Hz 논리 publication starting point다. 재전송된
snapshot은 새 actual sample이 아니다. Safety Supervisor는 Planner의 각 후보에 적용하며
Controller/Zone 출력 guard는 각 실행에서 확인한다. 별도 safety thread rate는 TBD-04다.
Diagnostics aggregation은 control/timeout 경로를 blocking하지 않는다.

[EV-01](../icd/ev_power_bms_design.md)과 SYS-PERF-002 v0.3은 BMS/power task·status·constraint
발행 주기는 [ADR-0016 wire 초안](../icd/bms_frame_draft.md)으로 구체화했다.
BMS control/model sampling·limits/request는 50 Hz, power status/permission은 100 Hz,
battery 관측 CAN은 10 Hz다. Critical source age 50 ms/dependency 70 ms, RX threshold
80 ms+monitor 10 ms+dispatch/jitter margin 10 ms를 제안한다. 관측 age 150 ms/RX unavailable
300 ms는 비critical이다. 위 기존 actuator rate와 구분한다. BMS/Power Host task의 부분 측정은
[ADR-0034](../adr/ADR-0034-multirate-runtime-and-can-loss-monitoring.md)에 있으며 실제 Zone/Target runtime은 미검증이다.
M1 Drive auxiliary의 source/input config를 분리·시험했고 기본값은 모두 30 ms다.
Capability input age 70 ms를 명시적으로 설정할 수 있으며 source/torque budget은 유지한다.
Local EV transport의 timeout/expiry는 fixture에서 시험했다. Sampler/model과 실제
Zone forwarding/cross-node clock budget의 충족은 후속 통합에서 검증한다.
M7-1d는 world/state100Hz·영상20Hz로 개정한다. 실제 wheel speed 원천과 clock/전송
budget의 연결은 TBD-04/07/14이며,30ms source-age는 유지한다.
EV critical stream도 <=100 ms loss 검출 상한을 적용하되 power/토크 물리 반응 budget은 별도다.

50 ms camera tick 사이 Controller 20 ms, Zone/vECU 10 ms task가 최신 유효 snapshot을
사용한다. Functional simulation 모드는 10 ms logical scheduling quantum을 기준으로
M7 world/state는 매 quantum, 영상은5 quantum마다 갱신하는 계약이다. 새 sensor를 임의로
보간/생성하지 않는다. 사용자 승인 M7-1d 개정은 기존50ms world baseline을 대체하며,
M6 실행 profile/모델·과거 검증 및 native2ms/4ms guard는 변경하지 않는다.
[Plant Adapter ICD](../icd/carla_plant_adapter.md#5-clock과-m7-multirate-개정-m7-1d)에 범위를 둔다.
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
| central_vehicle_request | Controller VehicleCommand publish/enqueue → Central allocation |
| central_allocation_start / central_allocation_end | 유효 vehicle-level 요구·원천 feedback 사용 / scoped demand 완료 |
| central_scoped_command_tx | 담당 Zone별 actuator demand publish/enqueue; parent identity/expiry 보존 |
| zone_ingress / zone_egress | scoped command valid acceptance / CAN actuator command enqueue |
| vecu_command_rx | actuator command valid acceptance; raw RX/reject도 별도 event |
| vecu_task_start / vecu_task_end | ECU job의 입력 snapshot 사용 / 판단·보고 완료; 외부 physics 비용은 별도 |
| feedback_tx | 해당 actual sample publish/enqueue |
| zone_feedback_rx / zone_status_tx | 담당 actuator별 valid RX / Central status 송신; 원천 metadata 보존 |
| central_zone_status_rx / bridge_tx | 각 Zone/Leaf 원천 valid acceptance / Host 송신; source별 age/identity 보존 |
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

[ADR-0039](../adr/ADR-0039-owner-completion-guards.md)는 monitor/plant의 Host 완료 시한 **4 ms**와
각 1211개 guard slot(마지막 release 2420 ms/deadline 2424 ms)을 채택한다. 2440 ms까지의 나머지 10개 slot은
관측 tail이다. 정상은 guard miss/skip 0이며 peer 검출·최초 검출 후 적용 margin은 각각 <=10 ms다.
각자 별도 accepted-RX 감시를 실행해 monitor 정지 중에도 plant가 유효 RX 상실을 검출한다. 실제 먼저 검출한
observer의 원래 last-valid/detected pair를 보존한다. 기존 RX 3 ms·threshold 80 ms·검출 <=100 ms는 유지한다.
공통 process/OS 정지 중에는 observer가 실행되지 못하므로 복귀 전 보호 적용을 보장하지 않는다.
이것은 Host fixture 계약이며 차량·Target·전체 E2E/TBD-04를 닫는 증거가 아니다.

전체 task deadline, 단계별 latency budget, E2E deadline은 **TBD-04**다.
[ADR-0033](../adr/ADR-0033-first-wall-time-execution-and-monitor.md)에서 첫 Steering Host fixture만
period 10 ms / relative deadline 5 ms / 독립 monitor·plant 2 ms로 선택했다.
120 jobs의 release/start/end, ECU prepare/complete와 외부 physics, output issued/applied·local feedback을
실제 wall time으로 기록했다. [첫 실행 안내](../learning/m3_steering_timing.md)를 따른다.
[ADR-0034](../adr/ADR-0034-multirate-runtime-and-can-loss-monitoring.md)의 후속 Host fixture는
Brake/Drive/Power 10 ms·deadline 5 ms, BMS 20 ms·deadline 8 ms, 실제 SocketCAN RX 2 ms·deadline 3 ms를 사용한다.
독립 monitor/plant 2 ms와 2.4 s workload, 감시 tail 40 ms·warm-up 제외 0을 기록한다.
각 receiver의 Accepted 시각만 별도 원자로 게시하고 critical 5개 stream의 유효 RX threshold 80 ms와
실제 검출 <=100 ms를 검사한다. Task 정지와 유효 입력 상실을 구분하며 CRC 실패는 age를 갱신하지 않는다.
출력/보호 snapshot 취득 뒤 적용 기준 시각을 읽어 인과 순서를 보존한다.
이 첫 fixture는 비동기 torque를 unavailable로 남겼다. 후속 [ADR-0036](../adr/ADR-0036-asynchronous-drive-actual-feedback.md)은
기존 SourceTimeNs의 실제 취득 의미를 유지해 Actual CAN TX→독립 RX를 연결한다.
각 보조 source는 receiver now/session·자기 age로 판정하며 torque source보다 나중일 수 있다.
Critical watch는 Actual을 포함한 6개 stream이고 RX는 마지막 feedback을 비우기 위해 20 ms 더 실행한다(1210 jobs).
Trace schema 3의 취득/생성/TX begin/end·RX/Accepted 시각과 원래 bytes를 구분하고 source→RX는 local 경계로만 보고한다.
현재 sample age 30 ms와 valid-RX timeout 80 ms는 별개이며 차량 전체 E2E 완료를 뜻하지 않는다.
[다중 주기 안내](../learning/m3_multirate_runtime.md)와 [품질 기록](../quality_policy.md)에 범위·실측을 남긴다.
[ADR-0035](../adr/ADR-0035-controlled-cpu-load-and-placement.md)는 같은 runtime CPU mask에서 추가 부하 없음/같은 CPU/다른 CPU를 비교한다.
부하 10 ms period·7 ms wall busy window와 실제 thread/process CPU 시간을 구분하고 3 layouts×2 trace modes×3회 반복한다.
Owner가 직접 기록한 mask/policy를 확인하며 기존 deadline 위반은 FAIL로 유지하고 유효한 실패 job도 통계에 포함한다.
CPU affinity는 resource reservation이 아니며 RT 우선순위·Target 보장은 후속이다. [부하 실행 안내](../learning/m3_cpu_placement.md)를 따른다.
이 실험의 deadline이나 SCHED_OTHER 관측 결과를 차량/Target 전체 budget으로 채택하지 않는다.

[ADR-0037](../adr/ADR-0037-runtime-owner-cpu-placement.md)은 같은 CPU B 부하에서 7-owner 배치를
colocated/RX만 분리/RX·monitor·plant 분리로 비교하고 같은 IO map의 무부하 대조군을 둔다.
요청/실제 thread map을 대조하며 기존 period/deadline·valid RX·output expiry 계약을 유지한다.
RX는 최신 release만 실행하므로 period를 넘겨 생략한 job도 miss다. 실행된 job의 duration만으로 판단하지 않는다.
이 비교는 RT 우선순위 확정이나 monitor/plant 전체 cycle의 실행 budget 채택을 대신하지 않는다.

[ADR-0038](../adr/ADR-0038-whole-owner-cycle-observation.md)은 monitor/plant 각각 1221개의 2 ms 기회를 기록한다.
Sleep target/call/start·application phase·body end를 구분하고 full에서 thread CPU delta를 추가한다.
전체 body에는 fixture TX도 포함하며 기존 sensor/source 시각을 갱신하지 않는다. 이 계측 당시 owner deadline은 미채택(TBD-04)이었다.
RX miss와 같은 시간의 owner 실행/생략 및 앞뒤 phase를 대조하되 공통 kernel/VM 원인으로 단정하지 않는다.
6 ms owner overrun의 주입/expiry accounting 검사는 정상 timing 수용과 구분한다. Normal/기존 fault의 만료 0 기준은 유지한다.
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

## Host 실행 수용 검토

[ADR-0039](../adr/ADR-0039-owner-completion-guards.md)는 monitor/plant에 2 ms 주기·4 ms 완료 시한과
각각 1211 guarded slots를 채택했다. 최신 release를 실행해도 생략한 이전 slot은 miss이며 관측 tail 10개는 분모에서 제외한다.
[ADR-0042](../adr/ADR-0042-native-owner-fifo-scheduling.md)는 기존 ECU/RX/owner 시한을 유지하고 일반/FIFO를 비교했다.
[M3-REV-20261019](../m3_acceptance_review.md)는 IO 동반 배치/FIFO를 다음 Host 통합 기준으로 선택했다.
기본 CLI 정책·기존 requirement 수치는 변경하지 않았다. 두 sanitizer OTHER 타이밍 실패는 OPEN이고 전체 수용은 PENDING이다.
이번 리포터 수정은 pooled guarded interval의 run 사이 gap을 제거하며 정상/고장 판정이나 누락 분모를 완화하지 않는다.
Central/Zone 추가 시 새 workload의 task/queue/monitor budget과 원천 인과 경로를 재검증한다. TBD-04의 차량/Target·E2E 값은 남긴다.

[ADR-0043](../adr/ADR-0043-hosted-monotonic-timer-and-placement.md)은 hosted RTOS의 timer phase부터
ReleaseDispatch까지 5 ms, 정상은 phase부터 Control 완료까지 5 ms인 추가 Host 검사를 채택·측정했다.
기존 실제 release→완료 5 ms와 감시 20 ms를 유지하며 원래 기점보다 앞선 phase를 함께 검사한다.
Relative 대조군도 원래 origin으로 평가하며 expiration 누락·signal coalescing은 timing FAIL이다.
Absolute 24/24 PASS와 native FIFO 후속 102/102는 local 부분 증거다. 차량/Target 전체 시한·SYS requirement를 완화하거나 VERIFIED로 바꾸지 않는다.

## M6 SIL physical-response-v1 (2026-10-22)

100ms는 마지막 유효 RX→검출의 기존 상한이다.

현재 Host quiet M6 모델의 별도 실제 출력 판정은 [실행 JSON](../../profiles/m6_sil_response_v1.json)과
[계산/실측 근거](../test-plan/evidence/m6_physical_response/README.md)를 따른다.
로컬 검출 회차→보호 선택 ACK<=4ms, 최초 로컬 목표 선택→양쪽 실제 출력 적용<=4ms,
최초 목표 선택→abs(torque)<=1Nm AND 실제 brake>=1MPa의 완료 관측<=230ms다.
200ms 병렬 물리 최악값+출력 인계4+모델4+CSV관측10+여유12로 산정했다.
Synchronous 보호 이후의 fault 관측 시각은 검출 순간이 아니므로 진입~반환 구간과
원래 command-expired/last-valid RX를 연결한다.10ms 첫 관측과 모델 crossing 구간도 분리한다.
이는 명시한 SIL 설정/Host profile의 판정으로, command expiry/RunLease/20ms envelope/
2ms opportunity/4ms watch를 늘리거나 다른 profile·차량 반응 시한을 일괄 변경하지 않는다.
