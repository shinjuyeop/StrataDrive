# Milestone roadmap

Status: **M0 — BASELINED / M1·M2 — TECHNICAL CHECKS PASS · REVIEW PENDING / M3 — IN PROGRESS / M4–M13 — PLANNED**.
M3의 [첫 Steering wall-time 실행](learning/m3_steering_timing.md)은 독립 monitor·plant, deadline/누락 job과 CSV 계측을 구현·검사했다.
후속 [다중 주기·CAN 감시](learning/m3_multirate_runtime.md)는 Brake/Drive/BMS·Power와 실제 RX를 연결했다.
후속 [고정 부하·CPU 배치 비교](learning/m3_cpu_placement.md)는 contention과 실패 run도 기록했다.
후속 [비동기 Drive Actual](learning/m3_drive_feedback.md)은 원래 취득 시각과 독립 보조 시각을 보존해 CAN 송수신을 연결했다.
후속 [owner별 CPU 배치 비교](adr/ADR-0037-runtime-owner-cpu-placement.md)는 같은 부하에서 RX 단독/감시·plant 동반 이동을 비교한다.
후속 [전체 owner cycle](learning/m3_owner_cycles.md)은 sleep/본문/CPU 시간을 나눠 RX miss와 감시·물리 owner를 대조한다.
Host owner 4 ms 완료 guard·수신 이중 감시를 채택했고 IO 동반 배치를 시험 기준으로 유지한다. RT 우선순위와 Target/E2E 확장은 후속이다.
[M0 exit review](m0_baseline.md)는 문서 계약의 검토다. 현재 Steering/Brake/Drive six-frame
codec/P05/receiver/SocketCAN과 EV 통신을 Host에서 구현했다. Local session/queue를 포함해
normal·ASan/UBSan 각각 unit 143개와 vCAN 89 case, 독립 DBC/CRC 교차 검증을 통과했다. [학습 안내](learning/README.md)에
상세 실행 기록을 보존한다. Wire baseline 채택/학습자 review와 M1 최종 acceptance는 미완료다.

[RG-01](icd/regenerative_braking_design.md)은 회생·마찰 배분,
[EV-01](icd/ev_power_bms_design.md)은 Battery/BMS/power/vehicle management 범위다.
[ZON-01 v0.5 / ADR-0021](adr/ADR-0021-central-coordination-and-parallel-zones.md)로 최종 Front/Rear 두 논리 Zone과 Central 별도 단일
coordinator를 채택했다. 각 Zone은 Central과 독립 command/status/session 경로를 갖고 기존 Central–Zone–Leaf 계층을 유지한다.
2026-10-14 [BMS wire 초안](icd/bms_frame_draft.md)의 EV 6개 DBC와 Host CRC/canonical 검사를
추가했다. [EV C++ codec/항목별 receiver](learning/m1_bms_codec.md)와 SocketCAN 변환의 Host
단위 검사와 EV local vCAN 36개 case도 통과했다. M2의 [첫 조향 모델](learning/m2_steering_model.md)은 Host 부분 구현·시험했다.
[첫 Brake 압력 모델](learning/m2_brake_model.md)의 정상 가압/감압·release와 local protection도 연결했다.
[Drive torque 응답](learning/m2_drive_model.md)의 ECU/물리 모듈 분리와 signed loss zero ramp도 연결했다.
[Battery 에너지·관측](learning/m2_battery_model.md)은 local component unit 30개를 추가했다.
[BMS 한계·보호](learning/m2_bms_controller.md)는 local sensor port와 방향별 derating/latch를 연결해 unit 33개를 더했다.
[Power lifecycle](learning/m2_power_lifecycle.md)은 RC bus/접점 actual·BMS gate·controlled shutdown으로 38개를 더했다.
[Drive local gate/capability](learning/m2_drive_gate.md)는 gate 37개와 공유 physics 4개를 추가했다.
[첫 Drive/Battery energy 연결](learning/m2_drive_energy.md)은 이상적 HV 경로에서 actual DC·SOC와 BMS/Drive loop 시험 28개를 추가했다.
[실제 RC/접점·Battery 연결](learning/m2_ev_power_circuit.md)은 circuit 24개·Battery integrated-flow 5개를 추가했다.
[Steering response monitor](learning/m2_steering_fault_monitor.md)는 물리 9개·monitor 21개·adapter 9개를 추가했다.
[Brake response monitor](learning/m2_brake_fault_monitor.md)는 plant 10개·monitor 16개·adapter 14개를 추가했다.
[ECU/SIL 실행 경계](learning/m2_execution_boundaries.md)의 core 18개·외부 물리 진행 3개를 추가했다.
M2 구조 정리 시점 전체 unit 491개를 normal·sanitizer에서 검사했다. M3의 30개를 더해 현재 521개이며 Python 리포터 47개를 검사했다.
기존 vCAN 97개 이력과 M3 multirate/fault·고정 부하 실험은 별도 범위다. 실행 횟수·PASS/FAIL은 [품질 기록](quality_policy.md)에 남긴다.
Gate 단계에는 normal·sanitizer 각각 기존 Drive model vCAN 3개를 재검사했고,
[M2 수용 검토](m2_acceptance_review.md)에서는 각각 model vCAN 8개·전체 unit·기존 demo를 재검사해 통과했다.
Steering/Brake monitor 단계도 각각 model vCAN 8개를 회귀 검사했다. 학습자 수용은 PENDING이다. Zone/DDS/차량 runtime과
TC-REG/EV/ZON 전체 결과는 **PLANNED / NOT RUN**이다.

| Milestone | 계획 범위 | Acceptance 증거 후보 |
| --- | --- | --- |
| M0 | Architecture / Requirement / ICD Baseline | ODD/scenario/수치/계층/timing/fault/ICD 의미 계약, traceability, owner가 있는 TBD, exit checklist |
| M1 | DBC + vCAN | 12개 wire/receiver, 영속 local Epoch/queue 및 overflow/restart 기술 검사 완료; wire 채택·학습자 review PENDING |
| M2 | TECHNICAL CHECKS PASS: Actuator + Battery / BMS / Power models | component·Steering/Brake response monitor 시험; 학습자 수용 PENDING |
| M3 | IN PROGRESS: Real-Time Timing & Scheduling Measurement | 다중 주기·독립 감시·owner별 배치·전체 cycle/RX 대응·Drive Actual CAN; 4 ms Host 교차 guard·수신 이중 감시; RT 우선순위·Target 후속 |
| M4 | Central coordinator + Front/Rear Zone | 단일 vehicle management/allocation 확인 후 Zone gateway 분리; 각 Zone routing/원천 freshness/local loss/rejoin, TC-ZON-001–003; protocol TBD-15 |
| M5 | Central Compute + DDS | Central/Front/Rear 논리 Ethernet, vehicle/power/scoped request·원천 status, QoS/freshness/Host bridge 및 독립 partition/rejoin |
| M6 | Simple Vehicle + EV Plant | 실제 actuator/power 응답을 통한 lifecycle/closed-loop, battery energy/SOC balance와 mapping 검증 |
| M7 | CARLA Integration | Host–Target 실제 Ethernet, single ego writer, feedback-driven CARLA motion |
| M8 | Classical Autonomous Driving | route/waypoint, Pure Pursuit 또는 Stanley, longitudinal PID의 기준 scenario |
| M9 | Fault / Diagnostics / DTC | actuator/BMS/power 및 cross-zone loss Fault Event/DTC/state/local action/actual response를 연결한 regression |
| M10 | Physical AI Perception | pretrained detection/segmentation/tracking, TensorRT 통합과 accuracy/latency 기준 |
| M11 | Learned Temporal Planner | 0.5–1초 history, trajectory/speed/risk 출력, Safety Supervisor/Classical Planner fallback 시험 |
| M12 | Thor vs Orin Compute-Tier Optimization | 동일 Reference 비교 후 tier별 구성 최적화, 공통 requirement 재검증 |
| M13 | Final SIL / V&V / Regression | scenario/fault/performance regression, traceability 결과와 한계 공개 |

Fault architecture는 M0부터 다루며 local fault behavior는 M2/M4 등의 component와
함께 설계한다. Fault handling을 M9까지 미룬다는 뜻이 아니다. 각 단계에서
[학습 절차](learning/README.md)와 [quality policy](quality_policy.md)를 적용한다.

## Engineering activities

[개발·학습 계획](engineering_plan.md)을 기존 milestone에 연결한다. 아래 표는 학습과
검토 활동의 배치이며 위 milestone의 번호·구현 범위·기존 acceptance를 변경하지 않는다.
추가 안전 분석과 RTE/BSW·Target pilot은 **PLANNED**다. Host의 [Steering OS 파일럿](learning/m3_rtos_pilot.md)은 별도로 구현했다. M0 exit review의 PASS에 포함하지 않는다.
Steering의 [AUTOSAR R25-11 P05 Protect/Check](learning/m1_autosar_e2e_profile5.md)는
M1 Host에서 직접 구현·시험했다. 이 부분 결과를 전체 AUTOSAR pilot 완료로 확대하지 않는다.
[ADR-0022](adr/ADR-0022-leaf-classic-development-methodology.md)로 Leaf의 Classic 개발 체계를
채택했다. Steering부터 ECU 소프트웨어와 SIL 물리 모델 경계를 설계하고 Brake/Drive/BMS로 확장한다.
ECU/SIL 코드 분리는 완료했다. 실제 Classic stack 채택·RTE/BSW pilot은 후속이며 기존 component 결과를 전체 stack pilot PASS로 바꾸지 않는다.

| 관련 단계 | 함께 수행할 학습·검토 | 남길 근거 |
| --- | --- | --- |
| M1 준비 / M1 | Item Definition 초안과 첫 HARA 사례 검토; Steering interface와 AUTOSAR 개념 대응; toolchain 타당성 조사 | 가정·열린 질문, SWC/Port/Runnable/Task 대응, toolchain 지원·제약과 wire 계약 영향 |
| M2–M4 | Leaf의 ECU/물리 모델 경계와 Steering SWC/Port/Runnable/Event/Task 설계; local protection 검토; 작은 AUTOSAR pilot과 stack 채택 여부 검토 | 설계 대응·입출력 계약, actuator response/fault/timing 증거, 설정·생성·실행 기록, 채택·보류 ADR |
| M5–M8 | 선택한 배포 환경과 closed-loop에서 계약 검증; 차량 거동으로 안전 분석의 가정 재검토 | clock/통신/plant 한계와 실제 관측 구간, 변경된 가정 및 requirement revision |
| M9 | local protection과 diagnostics를 연결하고 분석한 fault의 coverage 검토 | fault→검출→보호→actual response→DTC 연결과 미검증 경로 |
| M10–M11 | SOTIF 관점의 인식·판단 한계, triggering condition, fallback 검토 | scenario/ODD 범위, AI 출력 검증과 fallback의 실제 결과 |
| M12–M13 | compute profile 변경의 timing·보호 동작 영향과 최종 추적성 검토 | profile별 regression, 검증된 범위와 남은 위험·제약 |

AUTOSAR 도구가 미확보되거나 Target 호환성이 부족하면 pilot의 보류 근거를 기록한다.
기존 Linux vECU 개발을 AUTOSAR 적용 완료로 표시하지 않는다. 안전 분석에서 새로운
요구사항이나 architecture 변경이 필요하면 기존 revision 절차로 검토한다.

## Open M0 Decisions

모든 owner의 최종 책임은 **학습자(project owner)**다. 아래 역할 표시는 별도 인력/위임을
뜻하지 않는다. 남은 상세값은 **TBD**이며 각 gate에서 해소한다. TBD-15의 topology/owner는 부분 결정했다.
해당 milestone 전까지 보류할 수 있는 상세값이며 M0 계층/경로/의미 계약의 미결정은 아니다.
문서/YAML의 미결정 값은 아래 ID에 귀속된다. Template의 `TBD`는 향후 기록 필드이지
별도의 design decision이 아니다.

| ID | 미결정 사항 / owner 역할 | 결정 milestone / gate | 보류 rationale / 영향 |
| --- | --- | --- | --- |
| TBD-01 | CAN ID/DLC/layout/scaling/ranges, CRC/counter/epoch/source-age metadata, queue/restart/startup handshake, timeout threshold / interface 담당 | **M1**, DBC/codec 및 vector test 전; task 검증 M2/M3 | M0는 의미/검출 상한을 고정하고 encoding을 M1 산출물로 유지; 100 ms에 polling/실행 margin 포함 |
| TBD-02 | units의 raw scaling, allocation/calibration 값, frame/geometry 변환, feedback skew/age 한계, dynamics 중복 방지 / plant·interface 담당 | **M1** wire 범위; **M2** actuator 의미 구현; **M6** simple mapping; **M7** CARLA mapping 전 | 차량/plant 모델이 없으므로 변환 계수 미확정; physical meaning/sign은 M0 ICD에 정의 |
| TBD-03 | actuator delay/saturation/dynamics/초기값, Steering/Brake timeout 물리 출력, Drive zero-target 후 torque 감소/ramp/반응 deadline, recovery dwell / vECU 담당 | **M2**, 각 actuator 정상/fault test 전; M6/M7 재검증 | 물리 parameter 근거 없이 압력/torque/ramp 수치 확정하지 않음; raw fallback/무제한 torque 유지 금지는 확정 |
| TBD-04 | task/E2E deadline/budget, source-age 한계, clock sync/uncertainty, trace/overhead/queue schedule, watchdog 독립성, priority/affinity, multirate ordering, timing warmup/duration/repetitions / timing 담당 | **M1** timeout encoding budget; **M3** 측정 protocol/task budget; **M5/M7** cross-node/E2E 전 | 부분 결정: ADR-0033/0034 Host task 10/20/2 ms·deadline 5/8/3 ms, monitor/plant 2 ms와 RX threshold 80 ms·검출 <=100 ms; ADR-0035/37 부하·배치와 ADR-0038의 whole-cycle/CPU·1221개 기회·RX 대응 기록; ADR-0039 Host owner deadline 4 ms·1211 guard slots·교차 보호·이중 수신 감시 채택; RT 우선순위·Target/E2E 미결정 |
| TBD-05 | 기본 DDS와 Zenoh 후보 비교, ROS 2 vs direct API/구현체/QoS/schema/integrity, Docker vs netns/veth, bridge process/transport/Host acknowledgement, addressing/discovery / communication 담당 | **M4** 비교, **M5 runtime 시작 전** 결정 | DDS 기본 계획 유지·Zenoh 미채택; 같은 계약/부하/fault로 호환성·학습 비용·queue-freshness·관측성·재연결 비교; adapter로 수용 |
| TBD-06 | Central allocation/conflict arbitration, availability/rejoin/local protection 상세, DEGRADED envelope, local↔Central state reconcile / Central VCU·Zone safety 담당 | **M4**, local fault/재연결 시험 전 | 정상 torque/brake 충돌과 actuator availability 검증 필요; critical loss는 M0에서 FAIL_SAFE로 고정 |
| TBD-07 | exact CARLA/Ubuntu/Python/ScenarioRunner 호환 build, map/route/seed/geometry/curve, Host GPU, tick/apply ordering 및 fidelity / simulation 담당 | **M7 통합 전**, route suitability M8 확인 | M0 설치/실행 없음; 공식 호환 정보와 재현 시험으로 선택; ODD/50 ms baseline 유지 |
| TBD-08 | DTC code/debounce/persistence/clear, diagnostic aggregation cadence/storage / diagnostics 담당 | **M9**, event→DTC 통합 전 | local fault/protection은 M2/M4부터 구현, DTC 통합이 선행 조건 아님 |
| TBD-09 | board/RAM/platform stack/power/cooling, reference AI model/checksum/input/precision/feature, profile override, accuracy/resource threshold와 benchmark protocol / compute·AI 담당 | **M5** 첫 Target 호환 stack; **M10** model/reference workload; **M12** board별 비교 전 | 두 보드 독립 배포 원칙은 확정; 동일 binary/engine/JetPack 호환을 가정하지 않음 |
| TBD-10 | perception/learned-planner shape/risk/history/calibration, AI fallback timing/feasibility/recovery / AI·safety 담당 | **M10/M11**, AI 통합 시험 전 | classical M8 baseline 후 확장; AI로 actuator 직접 제어 금지는 확정 |
| TBD-11 | C++ standard/compiler/CI/test tool versions, artifact size/license/storage policy; control 알고리즘/tuning, speed transition slope/duration, scenario repetitions / toolchain·control 담당 | **M1** 첫 code/tool 전; **M8** control/정상 시험 전; **M10** 첫 model fixture 전 | 작은 변경과 설명 가능한 도구 선택; 5 s settling + 10 s steady window와 수치 requirement 변경은 revision 필요 |
| TBD-12 | EV 전원 sequence/주행 허가/INIT handshake, LV·충전 연결·interlock와 고장별 torque/power reaction, shutdown/복구 threshold·budget / vehicle management·safety 담당 | **M1** 의미/handshake; **M2** power component 시험 전; **M4/M6** gate/vehicle 검증 전 | READY≠NORMAL, 요청≠actual; 일괄 즉시 contactor open/정지 성공을 가정하지 않음 |
| TBD-13 | battery usable capacity/initial SOC, pack·셀 극값 voltage/thermal 모델·threshold/dwell, charge/discharge 곡선·효율/부하/에너지 오차, motor power→torque / model 담당 | **M2** Battery/BMS/Drive 시험 전; **M6/M7** 일관성/매핑 재검증 | 부분 구현: Battery/BMS·Drive gate·RC/접점/capacitor 실제 energy 연결·장부 시험; 차량 calibration/정밀 모델은 미결정; actual power·단일 owner/clock 유지 |
| TBD-14 | EV wire 수용·coordinator, trusted startup/parent·model identity 전달, clock/각 hop budget, DDS/Host status / interface·timing 담당 | **M1** wire/session 수용 전; **M2/M3** sampler/task/timing; **M5** DDS/Host bridge 전 | **부분 구현:** ADR-0016/17 6개 frame/P05와 항목별 receiver Host 검사; source 50/input 70/RX 80 ms 초안, Drive input age opt-in 분리와 local vCAN 36개 검사 완료; actual coordinator·Zone/runtime budget은 남음 |
| TBD-15 | 남은 Central–Zone schema/QoS/queue/clock/skew/source-age·monitor budget/INIT-rejoin/routing config / architecture·communication 담당 | **M4** 각 Zone/local test 전, **M5/M6** DDS/plant 통합 검증 전 | **부분 결정:** ZON-01 Front/Rear, 후륜 구동 packaging, Central 별도 단일 coordinator 채택; 세부 protocol은 TBD, calibration TBD-02/07; 별도 하드웨어 불필요 |

RG-01의 추가 상세값도 기존 owner/gate에 귀속된다. 범위 결정으로 TBD가 해소되지는 않는다.

| 기존 ID | 회생 설계에서 결정할 항목 / gate |
| --- | --- |
| TBD-01 | M1 Drive signed scaling/범위/layout/Data ID, capability validity/reason/source freshness와 frame 구성 |
| TBD-02 | M2/M6 공통 wheel 기준/geometry, 압력→마찰 torque calibration, capability age/skew와 에너지 산출 단위 변환 |
| TBD-03 | M2 양·음수 motor response/zero-target ramp, 속도별 회생 한계, 충전 수용/효율 fixture, 저속 hold와 energy integration 오차 |
| TBD-04 | M1/M3 capability freshness/monitor timing budget; critical loss 검출 상한 유지 |
| TBD-05 | M5 vehicle state→Zone→Drive 속도 입력/원천 metadata 전달과 ZoneStatus capability schema |
| TBD-06 | M4 회생/마찰 전환/arbitration, actual 보정, 감속 부족·과다/전환 budget와 local protection envelope |
| TBD-07 | M7 signed Drive Actual과 friction Brake Actual을 한 번씩 적용하는 CARLA mapping 및 에너지 모델 fidelity |

추가 TBD는 owner / 결정 milestone / rationale을 이 표에 등록한다. M3/M6/M7/M8 evidence로
수치 변경 시 [requirement revision](requirements/system_requirements.md)에 이전/새 값과
rationale/Result/영향 test를 기록하고 profile/ICD/scenario를 함께 갱신한다.

M1 부분 진행: TBD-01/02의 [Steering field 표현 초안](icd/steering_angle_encoding.md)과
TBD-11의 [첫 Host C++ 실험 도구 선택](adr/ADR-0005-first-cpp-codec.md)을 기록했다.
이어서 [Steering frame·DBC 제안](icd/steering_frame_draft.md)과
[Host frame codec·parser 도구 선택](adr/ADR-0006-steering-frame-codec.md)을 구현·검증했다.
로컬 Receiver 정책은 [ADR-0008](adr/ADR-0008-steering-receiver.md)에 기록했다.
[SocketCAN 결정](adr/ADR-0009-steering-socketcan.md)에 local wall-time 시험을 기록했다.
영속 로컬 Epoch issuer/queue와 실제 overflow는 [M1 기술 exit](learning/m1_session_queue.md)에서 구현·검사했다.
Wire 최종 채택/물리 범위/Target·CI, 실제 Central–Zone session protocol·차량 timing은 남아 있으므로
위 TBD 전체를 CLOSED로 바꾸지 않는다.

## 다음 작업과 M1 남은 수용 항목

BMS/power/Drive constraint의 [의미·DBC·timing 초안](icd/bms_frame_draft.md)을 작성했다.
물리 field/frame codec과 항목별 수신부, Drive auxiliary age 분리를 Host에서 시험했다.
기존 vCAN fixture의 EV 송수신/session·parent·relay도 36개 case로 확장·시험했다.
Local Epoch/queue·overflow/restart를 구현·시험해 M1 기술 수용 항목을 정리했다.
M2는 [Steering 응답 모델](learning/m2_steering_model.md)의 delay/rate/saturation 및 local source-loss hold를
Host에서 구현·시험했다. [Brake 압력 모델](learning/m2_brake_model.md)의 가압/감압과
압력 floor/retain 보호도 구현·시험했다. [Drive torque-only fixture](learning/m2_drive_model.md)는
signed 응답/zero ramp와 speed/capability unavailable을 검사했다.
[Battery 모델](learning/m2_battery_model.md)의 에너지·센서 component도 구현·시험했다.
[BMS 한계·보호](learning/m2_bms_controller.md)는 센서 검사·dwell/latch·PowerLimits를 구현·시험했다.
[Power lifecycle](learning/m2_power_lifecycle.md)은 실제 접점/전압·current wait·shutdown blocked를 구현·시험했다.
[Drive local gate·capability](learning/m2_drive_gate.md)는 원천 limits·허가·로컬 HV/속도를 확인한다.
[실제 DC/Battery energy 연결](learning/m2_drive_energy.md)은 고정 speed/이상적 HV에서 실제 토크의 손실·auxiliary와
finite residual·SOC guard band를 검사했다. [실제 RC/접점 연결](learning/m2_ev_power_circuit.md)도 capacitor/path 손실·구간 전류와
Battery의 단일 chemical energy owner를 연결해 시험했다. [M2 수용 검토](m2_acceptance_review.md)로
실행·설정·고장/세션·증거를 대조했다. [Steering jam/tracking local monitor](learning/m2_steering_fault_monitor.md)를
별도 물리·sensor 경계와 함께 구현·시험했다. [Brake response detector](learning/m2_brake_fault_monitor.md)도
가압/감압과 보호 floor 요청·관측 경계를 구현·시험했다. M2 기술 검사는 완료했고 학습자 수용 기록은 별도다.
[M3 첫 Steering 실행](learning/m3_steering_timing.md)에서는 독립 task monitor·물리 owner와 trace를 연결했다.
후속 다중 주기 fixture에서 Brake/Drive/BMS·Power와 실제 통신/RX 정지·CRC 손상 감시를 검사했다.
고정 부하·owner별 CPU 배치/전체 cycle 계측과 비동기 Drive Actual 연결도 실행했다. Host 완료 guard·수신 이중 감시를 연결했다. 배치 비교에서 IO 동반 map을 Host 기준으로 유지했다. 다음은 RT/Target·M3 수용 검토다.
Wire/학습자 review는 PENDING이다.

1. EV 초안의 producer/단위/validity/source·dependency time/expiry와 주기 차이를 review한다.
2. Actuator/EV vCAN 89개 case와 영속 Epoch/queue의 source·parent·model identity 및 fault trace를 재현·review한다.
3. Wire baseline 채택과 학습자의 설명 기록을 남긴다. Actual Central coordinator/Zone DDS coordinator는 M4/M5에 연결한다.
4. 실제 circuit/energy loop와 M2 parameter·task/monitor·fault/session의 component 증거는 수용 검토에 기록했다.
   OPEN-M2-01/02는 component 구현·시험했고 learner review가 남았다. M3의 runtime/trace 측정은 별도 준비한다.
5. ECU/plant 소유와 호출을 분리했고 demo는 도메인별 source/단일 executable로 유지한다.
   M3의 Steering 및 다중 주기 execution/period/jitter/deadline·유효 RX 감시와 고정 부하 비교·Drive Actual CAN을 연결했다. 실행 budget/배치·수용을 검토하고 이후 M4 단일 coordinator/두 Zone 분할로 진행한다. Target 검증은 실제 배포 단계와 연결한다.

Six-frame 구현·부분 시험과 새 EV/ZON 수용 항목을 구분한다. EV wire 값이나 물리 반응/전원
parameter를 기존 100 Hz/30 ms 또는 특정 OEM 수치로 자동 확정하지 않는다.

M0의 성공 기준은 문서량이 아니라 M1 DBC/vCAN을 시작해도 Central/Zone/vECU/Plant
책임과 command/actual 계약을 뒤집지 않아도 되는 상태다. M1에서 처음 발견한 encoding
제약은 architecture 변경 대신 ICD revision과 rationale로 해결한다. 필요한 설계 변경은
숨기지 않고 영향 requirement를 다시 검토한다. 학습자는 milestone마다 설계와 trade-off를
자신의 말로 기록하며 문서 baseline 상태가 개인의 이해를 대신하지 않는다.
