# Software architecture and contracts

Status: 계약 **DEFINED**, M1 통신·M2 모델 **Host component 기술 검사 완료 / 학습자 수용 대기**,
M3 다중 주기·독립 task/CAN 감시·CPU 부하/배치 **Host 부분 구현·계측**, 차량/Target runtime **PLANNED / NOT RUN**.
Component ID는 [system architecture](system_architecture.md)의 ID를 사용한다.

## Module responsibility

| Directory | 입력 → 출력 / 책임 |
| --- | --- |
| `central/vehicle_state` | sensor/ego state → timestamp/frame/validity를 갖는 state snapshot |
| `central/perception` | sensor + inference 결과 → object/lane observations; 모델 경계의 integration |
| `central/world_model` | state + observations → planner용 일관된 world representation |
| `central/planner` | Phase A route/waypoint, Phase C의 learned 제안 → candidate trajectory; classical fallback 유지 |
| `central/safety` | trajectory/state/health → 검증된 trajectory, 한계값, 선택된 fallback/system state |
| `central/control` | validated trajectory + ego state → speed reference + bounded acceleration/curvature/braking demand |
| `central/health` | task, resource, heartbeat → fault monitor 입력 |
| `central/diagnostics` | fault event → DTC lifecycle / system state 결정 |
| `zone/gateway` | Front/Rear 공통 DDS↔각 CAN dispatch; 각 Zone의 원천 status를 Central bridge에 전달 |
| `central/session` | Linux 영속 Epoch issuer 구현; Central trusted owner, M1 fixture 연결; 실제 Central–Zone INIT protocol 후속 |
| `zone/command_validation` | validity, age, sequence, range, mode 검증 → accept/reject 사유 |
| `central/vehicle_management` | Central 별도 VCU: lifecycle 요청 + fresh BMS/power/actuator 상태 → 전원 요청/drive permission; 차량 전체 단일 VCU 역할, PLANNED |
| `central/control_allocation` | Central 별도 배분: vehicle command + actual/capability → steering/brake/drive demand; 차량 전체 단일 배분, arbitration TBD-06 |
| `central/feedback_bridge` | 두 Zone의 per-source actual/EV status → Central consumer/Host; 원천 age/identity 보존, PLANNED |
| `zone/local_safety` | local timeout/fault → 제한 또는 local fail-safe; Central Vehicle Compute 의존 없는 판단 |
| `vecu/common` | absolute task schedule·독립 completion monitor·유효 RX age monitor와 SPSC latest snapshot 구현; 전체 watchdog·diagnostics 배치는 후속 |
| `vecu/steering`, `vecu/brake`, `vecu/drive` | accepted demand + 외부 sensor → normal/protection 목표·actual feedback; DriveController는 BMS limits·Central permission·로컬 HV/속도의 필수 gate와 capability 계산, 기존 DriveActuator는 isolated 응답 fixture |
| `simulation/steering` / `vecu/steering/steering_response_monitor.*` | delay/rate·jam/angle sensor를 만드는 SIL plant / bounded target 이력·독립 sensor로 정상 range/residual/dwell·sensor health를 검사하는 local monitor |
| `simulation/brake` / `vecu/brake/brake_response_monitor.*` | delay·가압/감압·stuck/pressure sensor를 만드는 SIL plant / 방향별 정상 range/residual/dwell·sensor health를 검사하는 local monitor |
| `simulation/drive/torque_response.*` | Drive 목표 → delay/rate/saturation·zero-target 물리 응답; ECU 수신/상태 판단과 별도 모듈, 차량 speed/current loop는 미구현 |
| `simulation/drive/drive_energy_model.*` | begin actual torque/speed·auxiliary → motor DC/손실 → 단일 BatteryModel SOC/관측; 이상적 경로 fixture, dynamic RC는 별도 EvPowerModel에서 연결; vehicle speed/current loop 후속 |
| `simulation/power/ev_power_model.*` | 실제 torque/speed·inverter stage·pack aux current·coil 출력 → 공통 motor DC·PowerModel 회로/구간 전류·BatteryModel SOC; capacitor/경로 손실과 atomic commit, 외부 speed fixture |
| `simulation/battery` | 실제 DC branch power+auxiliary → chemical energy/SOC·Rint/lumped thermal·독립 관측; Host component 구현·시험, BMS와 분리 |
| `vecu/bms` | local sensor port 검사 → 충방전 derating·보호 latch·PowerLimits와 로컬 safety gate; 물리 모델과 분리 |
| `vecu/bms/power_controller.*` / `simulation/power` | BMS leaf의 lifecycle runnable / 실제 접점·RC bus·current 센서; controller/plant 분리, Host component 구현·시험 |
| `simulation/{steering,brake,drive}/*_sil` | ECU와 plant 연결, physical step/acquisition·출력 적용·fault injection; ECU library 밖의 single-owner SIL runner |
| `simulation/runtime` | Steering 및 다중 주기 Host fixture: Brake/Drive/BMS/Power/RX별 worker·독립 monitor·별도 plant owner, 출력 admission/적용과 CSV 계측; 차량 runtime·Target scheduler는 후속 |
| `simulation/simple_plant` | CARLA 전 계약 검증용 작은 vehicle model |
| `simulation/plant_adapter` | actual actuator feedback → plant별 actuation mapping |
| `simulation/carla`, `simulation/scenarios`, `simulation/fault_injection` | simulator lifecycle, scenario, 명시적 fault injection |
| `physical_ai/perception`, `physical_ai/learned_planner` | model-specific inference/preprocessing와 temporal model 연구 |
| `physical_ai/export`, `physical_ai/inference` | artifact provenance, export, TensorRT runtime; Central Vehicle Compute가 결과를 소비 |

Safety Supervisor가 Planner와 Classical Controller 사이에서 trajectory를 검사한다.
Classical Controller는 자체 출력 한계를 적용하고 Zone Controller는 수신 command를 독립 검증한다.
어떤 layer도 다른 layer의 검증을 이유로 자신의 timeout/validity 계약을 생략하지 않는다.
[ZON-01 v0.5](zonal_partition.md)에서 두 Zone은 Central의 차량 전체 배분기를 복제하지 않는다.
위 경로는 책임의 예정 위치이며 아직 존재하지 않는 runtime module도 포함한다.

## vECU task/communication contract

vECU는 CAN echo simulator가 아니라 MCU/RTOS를 학습하는 Linux software model이다.
실제 RTOS task나 interrupt의 등가 구현/실시간 보장은 주장하지 않는다.

### Leaf Classic 개발 체계와 물리 모델 경계

[ADR-0022](../adr/ADR-0022-leaf-classic-development-methodology.md)로 Leaf ECU 소프트웨어의
개발 방향을 채택했다. 첫 대상은 Steering이며 Brake/Drive/BMS로 단계적으로 확장한다.

| 경계 | 책임 / 설계 산출물 |
| --- | --- |
| ECU 기능 | 명령 처리, 상태/로컬 보호 판단, 출력 요구 결정과 상태 보고; SWC/Port/Interface/Runnable/Event 설계 |
| 실행·통신 서비스 | Runnable→OS Task mapping, RTE/BSW 연결, 통신·timer·driver adapter; 실제 stack/toolchain은 pilot에서 결정 |
| SIL 물리 모델 | ECU 출력 요구→조향각·압력·torque·battery/power 응답→관측 actual; model clock/초기값/parameter와 controller 경계 |

[실행 경계 정리](../learning/m2_execution_boundaries.md) 뒤 `vecu`의 SteeringActuator·BrakeActuator·DriveActuator·DriveController는
plant 객체를 소유하거나 물리/취득을 호출하지 않는다. `prepare(now)`/`complete(sensor, now)`로 job을 나누고
interfaces의 typed actuation/sensor port를 사용한다. 두 phase는 한 owner가 같은 논리 job 시각에서 직렬로 호출한다.
`simulation/*/*_sil`의 연결 코드가 ECU와 plant를 소유해 기존 delay·gap·fault 정책을 실행한다.
실제 실행자는 둘을 각각 진행할 수 있으며, ECU 정지 중 외부 plant가 진행한 상태를 복귀 때 되돌리지 않는다.
기존 CLI와 CAN fixture는 이 SIL 연결 코드를 사용한다. DriveController의 필수 BMS/permission/HV gate는 유지한다.
BMS/PowerController도 기존의 외부 sensor/출력 port 경계를 유지한다. ECU library에는 simulation include/link 의존성이 없다.
Phase API 자체는 task/watchdog 구현이 아니다. 후속 [첫 M3 fixture](../learning/m3_steering_timing.md)는
Steering ECU·독립 monitor/plant를 별도 owner/thread로 실행했다. 후속 [다중 주기 fixture](../learning/m3_multirate_runtime.md)는
Brake/Drive/BMS/Power/RX worker를 분리하고 소비자별 SPSC snapshot을 사용한다. Target 배치·RTE mapping은 후속이다.
[CPU 배치 실험](../learning/m3_cpu_placement.md)은 7개 owner를 같은 allowed CPU에 고정하고 별도 load process의 위치를 비교한다.
각 owner가 실제 affinity/policy를 보고한다. CPU 예약·독립 OS watchdog이나 priority 변경의 구현은 아니다.
모델을 분리해도 command와 actual, 정상/보호 출력과 실제 응답의 차이를 보존한다.
Actuator 물리 응답과 battery/power sensor 모델을 production SWC로 자동 분류하지 않는다.
현재 library·single-owner Linux 실행은 생성된 RTE/BSW나 AUTOSAR OS의 증거가 아니다.
Classic stack pilot은 PLANNED / NOT RUN이며 Central/Zone의 배치·Linux 계획은 유지한다.

### 주기와 수신 계약

| Logical task | Period starting point | 계획된 책임 |
| --- | --- | --- |
| Task_10ms_Control | 10 ms | 유효 command snapshot·센서 검사, state update와 normal/protection 출력 선택; SIL 물리 진행은 외부 책임 |
| Communication publication | 10 ms | bounded RX/TX queue, command 검증, 각 actual feedback publication |
| Diagnostics aggregation | TBD-08 (M9) | fault aggregation/status; 빠른 timeout 검출은 10 ms local monitor 경로 |

위 10 ms starting point는 Steering/Brake/Drive에 적용한다. [BMS wire 초안](../icd/bms_frame_draft.md)은
BMS model/limit 20 ms, power actual/permission 10 ms, 관측 100 ms와 별도 age/monitor budget을 제안한다.
EV codec/receiver와 BMS 20 ms·Power 10 ms Host 실행을 시험했으며 전체 task/hop timing은 TBD-14다. `models/`는 AI artifact
정책의 directory이며 EV 물리 model source는 위 `simulation/` 책임으로 분류한다.

Periodic Task, RX/TX Queue, Mutex / Synchronization, State Machine, Watchdog,
Command Timeout, Alive Counter, CRC, Deadline Monitoring, Fault State, Actuator
Dynamics를 포함할 계획이다. Queue capacity/overflow, lock 범위/priority inversion,
thread/process model, scheduling policy/priority/affinity는 TBD-01/04다.
M1 FIFO capacity 32와 cycle당 ingress/dispatch 8을 local fixture에 적용하고 overflow 시
ContinuityError/current-sample 폐쇄를 검사했다. [Session/queue 기록](../learning/m1_session_queue.md)을 따른다.
위 period는 logical config이며 production timing 보장이 아니다. M3 Host fixture는 Steering에 이어
Brake/Drive/Power 10 ms·BMS 20 ms와 SocketCAN RX 2 ms를 실행했다. 전체 통신·Target 배치는 후속이다.

수신된 bytes는 검사 후 command snapshot에 게시한다. stale, 중복, 순서 오류,
CRC 오류 frame은 valid-command freshness를 갱신해서는 안 된다. Alive counter
폭/wrap/restart 정책, CRC coverage/polynomial, startup grace와 rejoin은 M1에 CAN ICD에서 확정한다(TBD-01). Timeout 감시는 통신 task 정지 중에도 관측 가능해야 하며 watchdog과
monitor 배치/독립성 및 stop 조건을 설계 검토한다. 수신 검증·timeout은 M1 library/fixture에서
부분 구현·시험했다. M3에서 독립 thread가 task deadline과 5개 critical stream의 유효 RX 상실을 감시한다.
RX 정지·지속 CRC 실패에서도 Brake floor/Drive zero·BMS inhibit를 검사한다. BMS/Power 정지의
유한 torque 반응·측정 전류 기반 종료를 구분하며 전체 차량 보호 응답·영구 hang 격리는 후속이다.
출력/보호 snapshot을 적용 시각보다 먼저 읽어 검출 이전으로 결정을 소급하지 않는다.
후속 [Drive Actual 연결](../learning/m3_drive_feedback.md)은 기존 header SourceTimeNs에 비동기 torque 취득 시각을 보존한다.
보조 시각은 각자 session/now·age/cursor를 검사하며 cached torque로 valid RX를 연장하지 않는다.
기존 RX owner의 0x282 socket/별도 DriveReceiver와 여섯 번째 valid-RX monitor를 연결했고 20 ms drain tail을 둔다.
차량/Zone feedback bridge는 후속이다.
후속 [owner별 CPU 배치](../adr/ADR-0037-runtime-owner-cpu-placement.md)는 같은 runtime의 7개 owner에 선택적으로
각각 CPU를 지정한다. RX만 이동하거나 RX·monitor·physical/fixture를 함께 이동해 비교하며 ECU/물리 책임과
CAN 계약은 유지한다. 별도 OS/하드웨어 watchdog이나 CPU 예약을 구현한 것은 아니다.

| vECU | Command / dynamics 후보 | Feedback / fault 후보 |
| --- | --- | --- |
| Steering | steering command; rate / acceleration limit, dead time, friction, overshoot, noise | actual steering + validity/time; jam / tracking fault |
| Brake | brake command; pressure buildup, response delay | actual brake pressure + validity/time; stuck / slow-response fault |
| Drive | signed 구동/회생 torque command; torque saturation, motor response, 단순 충전 수용 모델 | actual torque/speed, 회생 한계와 별도 validity/time; over-current / mismatch fault |
| BMS / EV-01 | pack 센서·셀 전압/온도 극값·요청, battery limits·power protection; limits 20 ms / power 10 ms | 센서·limits/protection·power lifecycle/RC/contactor·Drive gate Host component 구현; 실제 ECU/차량 runtime 후속 |

Sign/unit 의미는 [공통 ICD](../icd/interface_overview.md)에 정의한다.
[RG-01 회생제동 설계](../icd/regenerative_braking_design.md)는 Drive/Brake/Zone의 후속 범위다.
에너지 집계는 actual 기반이다. [EV-01](../icd/ev_power_bms_design.md)에서 별도 BMS 논리
vECU와 Battery/power model을 추가하며 RG-01의 BMS 제외 범위를 대체했다.
Drive의 실제 HV bus sensor는 IF-MODEL-DRIVE-POWER의 power plant→Drive 로컬 물리 경계다.
Central permission/PowerStatus 참조 metadata를 자체 실제 bus 측정 대신 사용하지 않는다.
Sensor schema/threshold는 TBD-12/13/14이며 BMS→Drive application 직접 우회가 아니다.
IF-MODEL-BMS의 셀 전압·온도 극값은 독립 pair validity/acquisition/batch를 가지며
oldest dependency에 포함한다. [로컬 입력 계약](../icd/ev_power_bms_design.md#로컬-셀-극값-입력)을 따른다.
[첫 Steering 모델](../learning/m2_steering_model.md)은 single-owner tick/지연 FIFO와
Command expiry/continuity/deadline 시 hold/latch, Actual/P05를 Host에서 시험했다.
[Brake ECU](../learning/m2_brake_model.md)는 local fault 시 increase-only/floor 출력을 요청한다.
SIL plant가 normal pending을 취소하고 별도 rise/fall rate와 delay·보호 응답을 계산한다.
정상 plant는 현재 압력 이상을 유지하며 floor까지 가압하지만 물리 stuck에도 도달을 보장하지 않는다.
[Drive torque 모델](../learning/m2_drive_model.md)은 signed 정상 응답과 loss 시 zero-target ramp를 시험했다.
이 isolated fixture의 speed/capability는 unavailable이다. 별도 [DriveController](../learning/m2_drive_gate.md)는
원천 BMS limits·trusted permission·실제 local HV/speed를 확인해 목표/가용량을 계산한다.
[Battery 모델](../learning/m2_battery_model.md)은 실제 DC 입력의 에너지 장부·전압/전류·온도와
독립 acquisition/source/dependency/batch를 갖는 다섯 관측 group을 구현·시험했다.
Pack 전압은 Drive 쪽 HV bus 준비 상태가 아니다. [BMS controller](../learning/m2_bms_controller.md)는
simulation과 독립인 local sensor port를 소비해 방향별 한계와 inhibit request를 만든다.
[Power controller/model](../learning/m2_power_lifecycle.md)은 같은 BMS leaf의 gate와 요청을 검사하고
실제 접점/RC bus·current feedback으로 readiness/종료를 확인한다. Drive gate의 demo는 actual RC bus를
관측하지만 Central/relay·wheel speed/SOC는 fixture다. 별도 [Drive energy loop](../learning/m2_drive_energy.md)는
실제 torque→DC→Battery 관측→BMS 한계를 연결한다. 이 loop의 speed·Central grant/relay는 fixture이고
이 첫 loop의 HV는 이상적 경로의 battery terminal이다. [EvPowerModel](../learning/m2_ev_power_circuit.md)은
별도 combined loop에서 dynamic RC/접점·Battery를 연결하고 actual local bus voltage와 구간 energy를 계산한다.
Power current sensor unknown/hold는 물리 장부와 독립이며 제어기가 physical truth로 우회하지 않는다.
[M2 수용 검토](../m2_acceptance_review.md)에서 주기·감시·설정·고장/세션 경계를 대조했다.
[Steering response monitor](../learning/m2_steering_fault_monitor.md)는 fresh acquisition과 delay/rate-band 예측을 비교해
tracking residual을 확인하고 hold/latch한다. Sensor unavailable/invalid와 cached Actual 재발행도 구분한다.
[Brake pressure monitor](../learning/m2_brake_fault_monitor.md)는 별도 plant/sensor와 방향별 rise/fall band·residual/dwell을 둔다.
Fault에서 increase-only/floor 출력 primitive를 요청하며 물리 stuck은 보호 뒤에도 적용된다. Floor 도달은 fresh sensor로만 관측한다.
기계 원인 분리·센서 이중화·실제 hydraulic closed-loop controller는 미구현이다.
M3 Host 다중 주기·실제 CAN 입력/독립 deadline·유효 RX 감시와 trace는 구현·검사했다. 부하·CPU 배치/Target timing은 M3 이후 배포 단계,
차량 보호 동작의 통합 검증은 M4/M6/M7에 남는다.
Dynamics parameter, noise seed, 초기화 수치와 calibration은 TBD-02/03 (M2/M6/M7)다.
Accepted demand와 actual actuator state를 다른 interface로 유지한다. Simulated current 등의 상태가 없으면 해당 fault는 검증됐다고 주장하지 않는다.

## Autonomous driving / Physical AI sequence

**Phase A — classical first (M8):** CARLA route/waypoint 기반 planner, Pure Pursuit
또는 Stanley lateral controller, Longitudinal PID. 반드시 Zone Controller/vECU를 거친
closed-loop를 먼저 완성하고 재현 가능한 기준 결과를 얻는다.

**Phase B — perception (M10):** pretrained Object Detection, Lane / Drivable Area
Segmentation, Multi-object Tracking을 우선한다. 처음부터 대형 모델 학습 대신
TensorRT deployment / optimization / integration과 accuracy 검증에 집중한다.

**Phase C — learned temporal planner (M11):** 최근 **0.5~1초** ego state history
(speed, yaw rate, steering, lane offset, route curvature, nearby objects)를 사용한다.
GRU 또는 작은 Temporal Transformer가 Future Waypoints, Target Speed, Risk Score를
제안한다. sample rate/history padding, trajectory frame encoding, risk 의미/calibration은 TBD-10 (M11)이다.

Learned Planner → Suggested Trajectory → Safety Supervisor → Classical Controller
→ Vehicle Command. AI는 actuator command를 직접 생성하지 않는다. Timeout, NaN,
stale history, invalid trajectory 시 Classical Planner fallback을 유지하며 fallback의
입력도 유효하지 않으면 안전 상태 정책으로 넘어간다. [ADR-0004](../adr/ADR-0004-ai-control-boundary.md)
및 [fault architecture](fault_diagnostics_architecture.md)를 참조한다.

Top-level state는 INIT / NORMAL / DEGRADED / FAIL_SAFE이며 local command loss는
Central diagnostics 없이 처리한다. [Fault architecture](fault_diagnostics_architecture.md)와
[timing contract](../requirements/timing_requirements.md)를 함께 적용한다.
