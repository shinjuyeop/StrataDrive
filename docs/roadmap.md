# Milestone roadmap

Status: **M0 — Architecture / Requirement / ICD Baseline: BASELINED**.
기준 이름은 **StrataDrive Reference Baseline v0.1**이며 [exit review](m0_baseline.md)를
모두 통과했다. M1–M13은 **PLANNED**, 착수/구현하지 않았다.
M0 완료는 system contract의 고정이며 runtime/vehicle verification 완료가 아니다.

| Milestone | 계획 범위 | Acceptance 증거 후보 |
| --- | --- | --- |
| M0 | Architecture / Requirement / ICD Baseline | ODD/scenario/수치/계층/timing/fault/ICD 의미 계약, traceability, owner가 있는 TBD, exit checklist |
| M1 | DBC + vCAN | Frame/signal 계약, CRC/counter golden vectors, vCAN encoding/decoding |
| M2 | Steering / Brake / Drive vECU | 주기 task/queue/state/dynamics와 local timeout/fault의 작은 테스트 |
| M3 | Real-Time Timing & Scheduling Measurement | execution/period/jitter/tails/miss 측정, clock/overhead 조건 기록 |
| M4 | Virtual Zone Controller | validation/allocation/local safety, CAN feedback loss와 rejoin |
| M5 | Central Compute + DDS | 논리 Ethernet 분리, DDS command/status, QoS/freshness 시험 |
| M6 | Simple Vehicle Plant | Zone Controller/vECU actual response를 통과한 closed-loop와 mapping 검증 |
| M7 | CARLA Integration | Host–Target 실제 Ethernet, single ego writer, feedback-driven CARLA motion |
| M8 | Classical Autonomous Driving | route/waypoint, Pure Pursuit 또는 Stanley, longitudinal PID의 기준 scenario |
| M9 | Fault / Diagnostics / DTC | Fault Event/DTC/state/local action/plant response를 연결한 fault regression |
| M10 | Physical AI Perception | pretrained detection/segmentation/tracking, TensorRT 통합과 accuracy/latency 기준 |
| M11 | Learned Temporal Planner | 0.5–1초 history, trajectory/speed/risk 출력, Safety Supervisor/Classical Planner fallback 시험 |
| M12 | Thor vs Orin Compute-Tier Optimization | 동일 Reference 비교 후 tier별 구성 최적화, 공통 requirement 재검증 |
| M13 | Final SIL / V&V / Regression | scenario/fault/performance regression, traceability 결과와 한계 공개 |

Fault architecture는 M0부터 다루며 local fault behavior는 M2/M4 등의 component와
함께 설계한다. Fault handling을 M9까지 미룬다는 뜻이 아니다. 각 단계에서
[학습 절차](learning/README.md)와 [quality policy](quality_policy.md)를 적용한다.

## Open M0 Decisions

모든 owner의 최종 책임은 **학습자(project owner)**다. 아래 역할 표시는 별도 인력/위임을
뜻하지 않는다. 상태는 전부 **TBD**, 각 결정 milestone에서 구현/시험 전에 해소한다.
해당 milestone 전까지 보류할 수 있는 상세값이며 M0 계층/경로/의미 계약의 미결정은 아니다.
문서/YAML의 미결정 값은 아래 ID에 귀속된다. Template의 `TBD`는 향후 기록 필드이지
별도의 design decision이 아니다.

| ID | 미결정 사항 / owner 역할 | 결정 milestone / gate | 보류 rationale / 영향 |
| --- | --- | --- | --- |
| TBD-01 | CAN ID/DLC/layout/scaling/ranges, CRC/counter/epoch/source-age metadata, queue/restart/startup handshake, timeout threshold / interface 담당 | **M1**, DBC/codec 및 vector test 전; task 검증 M2/M3 | M0는 의미/검출 상한을 고정하고 encoding을 M1 산출물로 유지; 100 ms에 polling/실행 margin 포함 |
| TBD-02 | units의 raw scaling, allocation/calibration 값, frame/geometry 변환, feedback skew/age 한계, dynamics 중복 방지 / plant·interface 담당 | **M1** wire 범위; **M2** actuator 의미 구현; **M6** simple mapping; **M7** CARLA mapping 전 | 차량/plant 모델이 없으므로 변환 계수 미확정; physical meaning/sign은 M0 ICD에 정의 |
| TBD-03 | actuator delay/saturation/dynamics/초기값, Steering/Brake timeout 물리 출력, Drive zero-target 후 torque 감소/ramp/반응 deadline, recovery dwell / vECU 담당 | **M2**, 각 actuator 정상/fault test 전; M6/M7 재검증 | 물리 parameter 근거 없이 압력/torque/ramp 수치 확정하지 않음; raw fallback/무제한 torque 유지 금지는 확정 |
| TBD-04 | task/E2E deadline/budget, source-age 한계, clock sync/uncertainty, trace/overhead/queue schedule, watchdog 독립성, priority/affinity, multirate ordering, timing warmup/duration/repetitions / timing 담당 | **M1** timeout encoding budget; **M3** 측정 protocol/task budget; **M5/M7** cross-node/E2E 전 | logical rate와 실제 execution/latency를 구분; M3 존재 구간부터 측정하고 future endpoint 확장 |
| TBD-05 | ROS 2 vs direct DDS/vendor/QoS/IDL/integrity, Docker vs netns/veth, bridge process/transport/Host acknowledgement, addressing/discovery / communication 담당 | **M4** 비교, **M5 runtime 시작 전** 결정 | 호환성/학습 비용/queue-freshness/관측성/재연결 기준; 계층을 바꾸지 않고 adapter로 수용 |
| TBD-06 | Zone allocation/conflict arbitration, availability/rejoin/local protection 상세, DEGRADED envelope, local↔Central state reconcile / Zone·safety 담당 | **M4**, local fault/재연결 시험 전 | 정상 torque/brake 충돌과 actuator availability 검증 필요; critical loss는 M0에서 FAIL_SAFE로 고정 |
| TBD-07 | exact CARLA/Ubuntu/Python/ScenarioRunner 호환 build, map/route/seed/geometry/curve, Host GPU, tick/apply ordering 및 fidelity / simulation 담당 | **M7 통합 전**, route suitability M8 확인 | M0 설치/실행 없음; 공식 호환 정보와 재현 시험으로 선택; ODD/50 ms baseline 유지 |
| TBD-08 | DTC code/debounce/persistence/clear, diagnostic aggregation cadence/storage / diagnostics 담당 | **M9**, event→DTC 통합 전 | local fault/protection은 M2/M4부터 구현, DTC 통합이 선행 조건 아님 |
| TBD-09 | board/RAM/platform stack/power/cooling, reference AI model/checksum/input/precision/feature, profile override, accuracy/resource threshold와 benchmark protocol / compute·AI 담당 | **M5** 첫 Target 호환 stack; **M10** model/reference workload; **M12** board별 비교 전 | 두 보드 독립 배포 원칙은 확정; 동일 binary/engine/JetPack 호환을 가정하지 않음 |
| TBD-10 | perception/learned-planner shape/risk/history/calibration, AI fallback timing/feasibility/recovery / AI·safety 담당 | **M10/M11**, AI 통합 시험 전 | classical M8 baseline 후 확장; AI로 actuator 직접 제어 금지는 확정 |
| TBD-11 | C++ standard/compiler/CI/test tool versions, artifact size/license/storage policy; control 알고리즘/tuning, speed transition slope/duration, scenario repetitions / toolchain·control 담당 | **M1** 첫 code/tool 전; **M8** control/정상 시험 전; **M10** 첫 model fixture 전 | 작은 변경과 설명 가능한 도구 선택; 5 s settling + 10 s steady window와 수치 requirement 변경은 revision 필요 |

추가 TBD는 owner / 결정 milestone / rationale을 이 표에 등록한다. M3/M6/M7/M8 evidence로
수치 변경 시 [requirement revision](requirements/system_requirements.md)에 이전/새 값과
rationale/Result/영향 test를 기록하고 profile/ICD/scenario를 함께 갱신한다.

## M1 entry and first work

M0 exit checklist 확인 후 **M1 시작 가능**, 실행 착수는 별도 작업이다.

1. 위 CAN semantic/failure 계약으로 6개 command/actual frame의 DBC wire 정의를 작성한다.
2. CRC/sequence/wrap/restart/freshness, timeout threshold+monitor margin을 확정하고 golden vectors를 만든다.
3. 선택한 최소 toolchain으로 encoder/decoder와 invalid-frame rejection 시험을 구현한다.
4. vCAN application-frame 송수신과 loss/replay/invalid frame 시험을 추가한다.
5. 결과를 requirement/test revision에 연결한다. vECU dynamics/물리 timing 검증으로 확대 해석하지 않는다.

M0의 성공 기준은 문서량이 아니라 M1 DBC/vCAN을 시작해도 Central/Zone/vECU/Plant
책임과 command/actual 계약을 뒤집지 않아도 되는 상태다. M1에서 처음 발견한 encoding
제약은 architecture 변경 대신 ICD revision과 rationale로 해결한다. 필요한 설계 변경은
숨기지 않고 영향 requirement를 다시 검토한다. 학습자는 milestone마다 설계와 trade-off를
자신의 말로 기록하며 문서 baseline 상태가 개인의 이해를 대신하지 않는다.
