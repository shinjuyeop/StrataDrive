# M0–M6 단계 검토 기록

이 문서는 당시 결정과 검토를 보존한 기록이다. 현재 상태는 [프로젝트 상태](../project-status.md), 현재 계약은 [문서 안내](../README.md)를 따른다. 과거의 “다음 작업/미구현”은 현재 지시가 아니다.

- [M0 baseline summary and exit review](#m0)
- [M2 수용 검토: 응답 모델과 EV 전원·에너지](#m2)
- [M3 수용 검토: Host 실행·타이밍·보호 동작](#m3)
- [M4 Host IO/FIFO 한정 수용 검토안](#m4-host)
- [M4 기술 종료 검토 — Host component와 원격 경계](#m4)
- [M6 종료 검토 — Host quiet SIL / Python MIL](#m6)

<a id="m0"></a>

## M0 baseline summary and exit review

Baseline: **StrataDrive Reference Baseline v0.1** / 2026-09-22.
Status: **BASELINED**. 15개 exit 항목의 문서/계약 검토를 모두 통과했다.
이 문서는 M0 계약 검토 결과이며 runtime test result가 아니다.

후속 변경: 2026-10-13 [RG-01 회생제동 범위](design-decisions.md#adr-0011)를
결정했다. 아래 v0.1의 요구사항/TC 수와 exit 검토 결과는 당시 기록이며 RG-01을 포함하지 않는다.

<a id="m0-decisions-and-rationale"></a>

### Decisions and rationale

- Reference ODD는 맑은 낮/포장도로/단일 ego/신호등 없는 직선·완만한 곡선/0–40 km/h다.
  복잡한 교차로·traffic interaction을 제외해 architecture와 tracking을 먼저 검증한다.
- Vehicle-level command, Zone actuator command, vECU actual feedback은 producer/물리 의미가
  다르다. Delay/saturation/fault를 관측할 수 있도록 command→actual shortcut을 금지한다.
  Central longitudinal PID의 acceleration demand를 vehicle-level payload에 명시하여 Zone은
  torque/brake allocation을 맡고 speed controller 책임이 모호해지지 않도록 했다.
- Central→logical Ethernet/DDS→Zone→CAN application→vECU→actual feedback→Zone/Target
  bridge→Physical Ethernet→Host Plant Adapter 경로를 고정한다. Plant Adapter만 ego writer다.
- Critical stream loss는 last-valid RX부터 <=100 ms에 검출한다. Invalid frame은 valid age를
  갱신하지 않는다. Threshold와 polling/jitter margin의 합을 구현 시 검토한다.
- Actual loss에서 synchronous simulation 다음 tick을 gate한다. Raw fallback을 피하고
  증거 결손을 표시하기 위한 선택이며 물리적인 안전 정지로 간주하지 않는다.
- INIT/NORMAL/DEGRADED/FAIL_SAFE 네 상태를 사용한다. Critical loss는 FAIL_SAFE,
  recovery는 explicit reinitialize→INIT다. Central diagnostics 없이 local protection을 수행한다.
- 20/50/100 Hz는 logical starting point다. Simulation time과 monotonic wall time,
  period/deadline/latency/freshness/timeout을 구분하고 M3부터 존재 구간을 측정한다.
- S01/S02는 30 km/h, S03은 30→20 km/h request로 정의했다. 연속 validated speed reference를
  기준으로 overspeed를 평가한다. Steady plateau의 5 s settling/최소 10 s 평가 window는
  transient를 분리하고 사후 유리한 구간 선택을 막기 위한 engineering choice다.
- Speed <=1 km/h, lateral P95 <=0.3 m, heading P95 <=3 deg, overspeed <=10%는
  production 기준이나 실측값이 아니다. M3/M6/M7/M8 evidence에 따른 revision/rationale을 허용한다.
- Thor Premium과 Orin NX Mainstream은 동일 architecture의 독립 배포 대안이다.
  Reference를 먼저 비교하고 feature/resource profile을 최적화한다. 동시에 차량을 구성하지 않는다.
- 실제 DBC/CRC encoding은 M1, dynamics는 M2, middleware는 M4 비교/M5 선택이다.
  보류한 상세값이 책임 경계의 재설계를 요구하지 않도록 semantic/failure 계약을 먼저 고정했다.

<a id="m0-exit-criteria"></a>

### Exit criteria

PASS는 **M0 문서 계약의 충족**만 뜻한다. Runtime requirement VERIFIED나 TC PASS가 아니다.

| Check | 증거 | Review |
| --- | --- | --- |
| Reference ODD 정의 | [system requirements](../requirements/system-requirements.md) | PASS |
| 정상 scenario 3개 정의 | [S01–S03](../test-plan/scenario-baseline.md) 목적/input/expected/metric/판정/ID/milestone | PASS |
| fault scenario 최소 4개 정의 | [F01–F04](../test-plan/scenario-baseline.md) trigger/monitor/state/local action/판정 | PASS |
| Vehicle/actuator command/actual 책임 분리 | [공통 ICD](../interfaces/README.md), SYS-ARCH-002 | PASS |
| Central/Zone/vECU/Plant Adapter 경계 | [system architecture](../architecture/README.md), single writer/우회 금지 | PASS |
| Logical timing/rate baseline | [timing](../requirements/timing-requirements.md), [reference.yaml](../../profiles/reference.yaml) | PASS |
| Timeout/freshness/clock/pause 개념 | [timing](../requirements/timing-requirements.md), last-valid origin/invalid age 미갱신 | PASS |
| Top-level fault state | [fault architecture](../architecture/README.md), INIT recovery/local independence | PASS |
| Physical/logical communication boundary | [ICD](../interfaces/README.md), [deployment](../architecture/README.md) | PASS |
| Thor/Orin 독립 배포 원칙 | [ADR-0003](design-decisions.md#adr-0003) | PASS |
| Requirement→test→future result 추적 | [traceability](../test-plan/requirements-traceability.md), 23 requirements / 16 TC / NOT RUN | PASS |
| 모든 unresolved TBD의 owner/milestone/rationale | [TBD-01–11 register](../roadmap.md#open-m0-decisions), profile null mapping | PASS |
| M1 구현 시작에 충분한 계약 | [CAN ICD](../interfaces/can.md), six frame 의미/방향/validation/failure gate | PASS |
| M1+ runtime 구현 혼입 없음 | Git diff 및 placeholder/CMake inventory | PASS |
| ID/link/용어/결과 상태 일관성 | 아래 repository audit | PASS |

<a id="m0-repository-audit-evidence"></a>

### Repository audit evidence

검토일: 2026-09-22. 수행: Codex repository 문서/구조 검토.
사용자의 개인 학습 기록이나 runtime/차량 검증을 대신하지 않는다.

| 실제 수행한 검사 | 결과 / 근거 범위 |
| --- | --- |
| `git diff --check` | PASS; whitespace 오류 없음 |
| 임시 Python 문서 감사: authoritative table 정의/참조/trace coverage | PASS; requirement 23개, TC 16개, component 8개, interface 9개, scenario 7개; ID 중복/undefined reference 없음 |
| Traceability의 미실행 상태 | PASS; requirement 23개 모두 component/interface/test/future milestone 연결, Future Result 전부 NOT RUN |
| Markdown file/heading link 및 외부 link 확인 | PASS; local 링크 136개 존재/anchor 확인, 기존 외부 링크 2개 HTTP 200 확인 |
| YAML parse 및 duplicate key/rate-period/수치/scenario/state 검사 | PASS; 기존 PyYAML 사용, profile 3개 유효, Reference 값과 문서 기준 일치 |
| TBD register/profile null 대응 | PASS; TBD-01–11에 project owner 역할/결정 gate/rationale; 향후 run revision은 design TBD와 구분 |
| 전체 문서 의미 검색 및 검토 | PASS; direct actuation 금지, 독립 Thor/Orin, command/actual 분리, 미측정/TBD/PLANNED 표기 일관성 확인 |
| `cmake -S . -B build` | PASS; 기존 LANGUAGES NONE bootstrap configure만 성공, compiler/application target/dependency 없음 |
| Git diff와 runtime directory inventory | PASS; Markdown/YAML 27개만 변경/추가, runtime directory는 .gitkeep만 유지, CMake/기존 bootstrap 변경 없음 |

문서 감사용 임시 script는 repository/runtime에 추가하지 않았다. 차량 시험, actual latency
측정, DBC/vCAN 실행, CARLA/ROS 2/DDS 설치, model 다운로드는 수행하지 않았다.
M0 exit는 **PASS**, M1 계약 설계/구현 **시작 가능**이며 이 변경에서는 착수하지 않았다.

<a id="m0-implemented-versus-planned"></a>

### Implemented versus planned

실제 파일로 존재하는 것은 Markdown 설계 계약, YAML design data, directory placeholder,
configure-only CMake다. YAML loader/schema validator/application target은 없다.
DBC/IDL/codec/vCAN/vECU/Zone/Central/CARLA/ROS 2·DDS/AI/deployment/차량 test는 PLANNED다.
TC의 Future Result는 모두 NOT RUN이며 Result ID와 benchmark 실측 파일은 없다.

Requirement registry에 새로 추가한 ID는 SYS-ARCH-002, SYS-ODD-001, SYS-COM-003/004,
SYS-CTRL-002/003/004/005/006/007, SYS-SAFE-002/003/004, SYS-PERF-002/003이다(15개).
기존 8개는 ID를 유지하며 v0.1 의미/판정/trace를 구체화했다.
Scenario ID는 S01/S02/S03/F01/F02/F03/F04(7개), 신규 Test ID는
TC-COM-003/004/005, TC-CTRL-002/003/004, TC-SAFE-002, TC-PERF-002(8개)다.

미결정 상세와 각 gate는 [roadmap](../roadmap.md#open-m0-decisions)에 모았다.
M1의 첫 작업은 frame/DBC, integrity golden vectors, codec/rejection, vCAN application test,
traceability 결과 연결 순서다. M0 성공 기준은 문서량이 아니라 **M1 DBC/vCAN을 시작해도
architecture와 contract를 다시 뒤집지 않아도 되는 상태**다.

<a id="m0-changed-files"></a>

### Changed files

추가 2개:

- [m0_baseline.md](#m0)
- [scenario_baseline.md](../test-plan/scenario-baseline.md)

수정 25개:

- [README.md](../../README.md), [roadmap.md](../roadmap.md)
- [system_requirements.md](../requirements/system-requirements.md), [timing_requirements.md](../requirements/timing-requirements.md), [safety_requirements.md](../requirements/safety-requirements.md)
- [system_architecture.md](../architecture/README.md), [software_architecture.md](../architecture/README.md), [deployment_architecture.md](../architecture/README.md), [fault_diagnostics_architecture.md](../architecture/README.md)
- [interface_overview.md](../interfaces/README.md), [can_icd.md](../interfaces/can.md), [ethernet_dds_icd.md](../interfaces/ethernet-dds.md)
- [verification_strategy.md](../test-plan/verification-strategy.md), [traceability.md](../test-plan/requirements-traceability.md)
- [ADR-0001-simulator-selection.md](design-decisions.md#adr-0001), [ADR-0002-zonal-architecture.md](design-decisions.md#adr-0002), [ADR-0003-compute-tier-strategy.md](design-decisions.md#adr-0003), [ADR-0004-ai-control-boundary.md](design-decisions.md#adr-0004)
- [profiles/README.md](../../profiles/README.md), [reference.yaml](../../profiles/reference.yaml), [thor_premium.yaml](../../profiles/thor_premium.yaml), [orin_mainstream.yaml](../../profiles/orin_mainstream.yaml)
- [learning/README.md](../learning/README.md), [quality_policy.md](../development-guide.md), [models/README.md](../../models/README.md)

<a id="m2"></a>

## M2 수용 검토: 응답 모델과 EV 전원·에너지

Review ID: **M2-REV-20261016** / Date: **2026-10-16**.
Status: **기존 component 및 Steering/Brake detector 검사 PASS / 학습자 직접 재현·이해 검토 PENDING**.
수행: Codex의 코드·설정·시험 증거 대조. M2 상태는 **IN PROGRESS**로 유지한다.

후속 2026-10-16: [Steering response monitor](../learning/vehicle-models-guide.md)를 구현·시험했다.
Steering 후속 시점의 unit은 430개였다. 이어 [Brake response monitor](../learning/vehicle-models-guide.md)도
구현·시험해 OPEN-M2-01/02 모두 **Host component 검사 완료 / 학습자 수용 PENDING**이다.
구조 정리 전 전체 unit은 normal·ASan/UBSan 각각 **470개 PASS**였다.
후속 [ECU/SIL 실행 경계](../learning/vehicle-models-guide.md)에서 21개를 더해 M2 구조 정리 시점 전체 **491개 PASS**였다. 아래 최초 검토의 391개 결과와 미구현 판정은 이후 `69a9614`로 커밋한 당시 snapshot의 이력이다.
최신 실행 증거와 수치는 위 학습 안내/품질 기록에 따로 연결한다.

<a id="m2-검토-범위와-판정"></a>

### 검토 범위와 판정

수용 검토는 구현한 기능, 약속한 기능, 시험한 범위를 대조하는 작업이다.
이 기록의 PASS는 아래 명시한 Host component 기능에만 적용한다.
전체 requirement를 VERIFIED로 바꾸거나 차량 TC의 NOT RUN을 변경하지 않는다.
기존 [학습 절차](../learning/README.md)와 [품질 정책](../development-guide.md)을 적용한다.

최초 검토에서 확인한 결과는 다음과 같다.

- Steering/Brake/Drive 응답, Battery/BMS/Power, Drive gate, 실제 회로·에너지 연결은 기존 기능 시험을 재통과했다.
- 주기는 외부 caller가 실행하는 논리 계약이다. `tick()`이 다시 호출될 때 gap을 검출하는 것과
  멈춘 task를 독립적으로 감시하는 것은 다르다. 실제 scheduler/watchdog·부하 측정은 M3에 남는다.
- **당시 Steering jam/tracking 및 Brake stuck/slow-response 검출은 미구현이었다.**
  [fault architecture](../architecture/README.md)가 M2 검증 대상으로 둔 항목이므로
  통신 timeout 시험으로 대체하지 않고 M2 미완료로 남긴다.
- 설정값은 단위·부호·C++ fixture와 YAML 기록을 대조했다. 실차 calibration 채택이나 학습자 수용을 뜻하지 않는다.
- Central request/grant·relay·wheel speed는 fixture다. 실제 Central/Zone/DDS와 차량 운동·회생/마찰 배분은 후속 범위다.

<a id="m2-주기입출력감시-경계"></a>

### 주기·입출력·감시 경계

아래 시간은 ms다. `max gap`은 마지막 논리 실행과의 간격에 대한 guard이며 OS job deadline이 아니다.
Source/dependency age는 `>`에서 만료하고 receiver timeout은 `>=`에서 latch한다.
각 API의 clock 역행은 출력 중단/무효를 드러내며 실제 물리 상태를 과거로 돌리지 않는다.
아래 첫 네 행은 현재 SIL 연결과 ECU core를 함께 표시한다. Delay/rate와 gap interval hold는
SIL의 응답 정책이며 ECU core가 plant를 소유하거나 직접 진행한다는 뜻이 아니다.

| 모듈 / 코드 | 실행·입력 시간 | 입력 → 출력 | 상실·실행 누락 반응 |
| --- | --- | --- | --- |
| [SteeringSil](../../simulation/steering/steering_sil.cpp) / [SteeringActuator](../../vecu/steering/steering_actuator.cpp) | SIL tick 10 / ECU max gap 30; command source 30, RX 80 | ECU 목표 → plant delay/rate/angle 제한 → angle sensor → Actual/P05 | ECU hold/FAIL_SAFE 요청; SIL pending 취소·현재 angle 유지, 누락 구간 catch-up 없음 |
| [BrakeSil](../../simulation/brake/brake_sil.cpp) / [BrakeActuator](../../vecu/brake/brake_actuator.cpp) | SIL tick 10 / ECU max gap 30; command source 30, RX 80 | ECU 목표 → plant delay/rise/fall 제한 → pressure sensor → Actual/P05 | ECU increase-only/floor 요청; SIL 보호 응답·gap interval hold, stuck 시 floor 도달 보장 없음 |
| [DriveActuatorSil](../../simulation/drive/drive_actuator_sil.cpp) / [DriveActuator](../../vecu/drive/drive_actuator.cpp) | SIL tick 10 / ECU max gap 30; command source 30, RX 80 | ECU signed 목표 → TorqueResponse → torque sensor → Actual/P05 | ECU zero target/latch, plant 유한 ramp; speed/capability와 EV gate 없는 isolated fixture |
| [DriveSil](../../simulation/drive/drive_sil.cpp) / [DriveController](../../vecu/drive/drive_controller.cpp) | SIL tick 10 / ECU max gap 30; command 30/RX 80, limits·grant 50/70/RX 80, local age 30/skew 20 | Command + limits + grant + local speed/HV → ECU 제한 목표·capability; plant torque sensor → Actual | 활성화 뒤 입력/허가 상실 latch, zero target/유한 residual; SIL gap interval backfill 없음 |
| [BmsController](../../vecu/bms/bms_controller.cpp) | tick 20 / max gap 40; sensor source 50/dependency 70/skew 20 | 독립 local sensor group → 방향별 PowerLimits + local safety gate | active 중 무효 입력 latch/unknown; 보호 pending 즉시 inhibit, fresh acquisition dwell 뒤 확정 |
| [PowerController](../../vecu/bms/power_controller.cpp) | tick 10 / max gap 30; sensor·gate 50/70, request RX 80/원래 expiry | actual sensor + BMS gate + trusted request → coil 요청·PowerStatus | inhibit 후 actual current dwell→접점 open→bus 방전; current unknown/high에서 강제 open하지 않음 |
| [BatteryModel](../../simulation/battery/battery_model.cpp) | standalone demo step 20 / max step 40; oldest input age 50 | actual DC power 또는 회로 current 적분 → 단일 chemical energy/SOC·heat·sensor port | gap/무효/capacity 초과 latch, 0 대입·clip·나중 backfill 없음 |
| [PowerModel](../../simulation/power/power_model.cpp) | demo step 10 / max step 20; input age 50 | begin coil·전기 입력 → 지연 접점·RC bus·sensor port | 입력/전기적 불가능성은 fault; 접점 event 시각으로 구간 분할 |
| [DriveEnergyModel](../../simulation/drive/drive_energy_model.cpp) / [EvPowerModel](../../simulation/power/ev_power_model.cpp) | demo step 10 / max step 20; end 기준 age 30/skew 10 | begin actual torque/speed·부하 → motor DC·손실·Battery; 후자는 실제 RC/접점 포함 | 구간 공백/old dependency/잘못된 identity를 거부; combined 모델은 Battery·회로·장부를 함께 commit |

Freshness는 처리 시각을 새로 붙여 연장하지 않는다. 초기 연결 획득/유효 0/unknown은 모듈별 의미가 다르다.
Steering/Brake의 수용 명령 없는 startup timeout은 unavailable 진단 Actual을 내고,
Drive는 fresh zero/Inhibit/known HV OFF일 때 non-driving INIT를 유지할 수 있다.
BMS의 missing startup sensors는 INIT/unknown으로 남으며 fresh release dwell을 완료하지 못한다.
Power는 확인 전 coil을 쓰지 않고 Inspect에서 실제 접점과 bus를 검사한다.

현재 caller와 component는 single owner다. 네 ECU core는 trusted `ActuatorSession`으로 초기화하고,
같은 job 시각의 `prepare/complete` 사이에 외부 실행자가 physical step/capture를 수행한다.
외부에서 독립 진행한 plant 상태는 ECU 복귀 때 되돌리지 않는다. 이 검토 시점의 같은 job end torque 제한은
후속 [비동기 Drive Actual 연결](../learning/runtime-timing-guide.md)에서 실제 취득 시각을 보존하도록 개정했다.
Cached sample은 새 측정으로 발행하지 않는다. 상세 port/phase 계약은 [실행 경계 안내](../learning/vehicle-models-guide.md)를 따른다.
[SocketCAN fixture](../learning/communication-guide.md)의
application FIFO 32 / cycle당 ingress·dispatch 8과 물리 delay FIFO 128은 서로 다른 용도다.
모든 함수 호출에 queue를 붙이는 구조가 아니다. Thread 분리 시 snapshot 동기화·queue ownership·overflow 반응을
M3에서 설계하고, 전체 통신 task 정지 중 감시의 독립성을 따로 시험해야 한다.

Combined EV loop는 이전 tick의 actual/coil로 `[begin,end]` 물리를 계산하고 end sensor를 취득한 뒤
BMS/Power/Drive를 호출한다. 새 제어 출력은 다음 구간에 적용한다. BMS 실행 간격은 20 ms다.
Battery 물리는 이 loop에서 10 ms마다 진행하므로 BMS 발행 주기와 같다고 가정하지 않는다.
50 µs electrical substep은 solver 설정이며 ECU task period가 아니다.

<a id="m2-설정값-대조와-적용-한계"></a>

### 설정값 대조와 적용 한계

원본은 [reference.yaml](../../profiles/reference.yaml)의 `m2_*_fixture` 기록과 각 C++ config/demo다.
YAML loader는 없으므로 이 파일을 수정해도 실행 설정이 자동 변경되지 않는다.

| 대상 | 이번에 대조한 fixture | 판정 / 남은 검증 |
| --- | --- | --- |
| Steering | command ±0.5 rad, actual ±0.3 rad, 1 rad/s, delay 50 ms | 단위/range·거부와 포화 구분 일치; 정상 delay/rate를 고려한 jam detector는 OPEN |
| Brake | command 0..2 MPa, actual 0..1.5 MPa, rise/fall 5/10 MPa/s, delay 50 ms, fault floor 1 MPa | 압력 의미/0 해제·floor 정책 일치; 차량 정지·pressure→wheel torque calibration 및 response detector 미검증 |
| Drive | command −300..500 N·m, actual −200..300, normal/protection 1000/2000 N·m/s, delay 50 ms | gate와 isolated fixture 구분; BMS 한계 축소 시 목표를 제한해도 actual residual은 유한 시간 존재 |
| Drive envelope | forward speed ≤100 rad/s, regen taper 2..5 rad/s, propulsion/regen mechanical 20/10 kW | zero/low speed·방향별 제한 시험; 실제 motor map/차량 속도 매핑은 후속 |
| Battery/BMS | 50 kWh, constant OCV 400 V, Rint 0.05 Ω, SOC charge zero/full 0.95/0.80, discharge 0.05/0.10 | energy/SOC·센서 극값·derating/dwell 시험; chemistry·SOC 추정기·제조사 threshold 검증은 아님 |
| Power | C 2 mF, precharge/main/bleed 50/0.02/100 Ω, 접점 지연 20 ms, OFF bus ≤30 V | actual 전압/접점 기반 sequence·blocked 시험; 실제 접점 차단 능력/전압 안전 기준의 채택은 아님 |
| Combined 전용 설정 | opening current 0.5 A, Drive reserve 500 W, pack-side auxiliary 0.375 A | standalone 5 A / reserve 200 W와 의도적으로 다름; nominal steady 손실 예산이며 transient hard power 보장 아님 |
| 수치 장부 오차 | Battery 0.00018 J / ideal energy 0.00036 J / combined 0.00072 J | capacity에 비례한 numerical conservation tolerance; 실차 모델 정확도나 안전 여유와 다른 값 |

TBD-02/03/12/13/14는 이 fixture의 시험만으로 닫지 않는다.
고정 외부 speed에서 회생을 계속할 기계 에너지원은 fixture 경계 밖이다.
차량 운동 에너지와의 수지·마찰제동·저속 hold는 M4/M6/M7에서 연결한다.

<a id="m2-고장세션-검토표"></a>

### 고장·세션 검토표

아래 PASS는 관련 component unit와 명시한 demo 범위다. 상세 case는 연결한 test source에 있다.

| 수용 항목 | 실행 증거 | 검토 |
| --- | --- | --- |
| 정상 delay/rate/saturation, repeated demand가 delay를 미루지 않음, Actual≠echo | [Steering 13개](../../tests/unit/steering_actuator_test.cpp), [Brake 16개](../../tests/unit/brake_actuator_test.cpp), [TorqueResponse/isolated Drive 24개](../../tests/unit/drive_actuator_test.cpp) | PASS |
| source expiry·CRC reject·continuity·gap에서 pending 취소/보호, late fresh 입력으로 복구하지 않음 | 위 actuator 시험, [Drive gate 37개](../../tests/unit/drive_controller_test.cpp), model vCAN 8개 | PASS; task 자체 중단의 독립 검출은 M3 |
| 충전/방전 유효 0와 unknown 구분, cached acquisition·skew·old dependency 거부 | [BMS 34개](../../tests/unit/bms_controller_test.cpp), Drive gate 시험 | PASS |
| READY와 주행 허가 구분, trusted parent 없으면 허가하지 않음, local HV 독립 확인 | Drive gate 및 [Power 37개](../../tests/unit/power_lifecycle_test.cpp) | PASS; Central/Zone는 fixture |
| 부하 전류·unknown에서 종료 차단, 접점 용착/응답 실패·잔류 전압 확인 | Power 시험 + `ev-power` 네 scenario | PASS; OFF 성공과 shutdown blocked를 구분 |
| actual torque 기반 구동·충전, auxiliary/loss·capacitor 소유, atomic failure와 장시간 수지 | [Battery 35개](../../tests/unit/battery_model_test.cpp), [ideal energy 28개](../../tests/unit/drive_energy_model_test.cpp), [circuit 24개](../../tests/unit/ev_power_model_test.cpp) | PASS |
| 새 application epoch에서 old input/pending 폐기, 물리 angle/pressure/torque·battery scenario 보존 | actuator/Drive gate/BMS/Power unit; explicit physical reset 시험 | PASS; 배포 환경의 trusted INIT/rejoin은 M4/M5 |
| fresh 통신 중 Steering jam, Brake stuck/slow response를 local detector가 구분 | 최초 검토 당시 detector 없음; 이후 [Steering](../learning/vehicle-models-guide.md)·[Brake](../learning/vehicle-models-guide.md) 구현·시험 | **후속 component PASS / 학습자 수용 PENDING** |

Combined normal 종료의 `drive_fault=4`는 활성화 뒤 Inhibit를 latch하는 현재 정책이다.
`phase=OFF, power_fault=0, blocked=0`인 전원 종료 성공과 모순되지 않는다.
재구동에는 trusted INIT/새 application epoch와 모든 입력의 재검증이 필요하다.
Normal OFF 뒤에도 pack-side auxiliary는 소비하므로 SOC가 정지한다고 가정하지 않는다.

<a id="m2-이번-실행-증거와-추적성"></a>

### 이번 실행 증거와 추적성

검사 대상은 기존 미커밋 구현을 포함한 working tree다. HEAD만으로 이 실행을 재현했다고 주장하지 않는다.
실행 source/DBC/profile의 SHA-256과 base commit은 `build/m1-angle/m2-review/evidence.json`에 보존한다.

| 이번 실행 | normal | ASan/UBSan | 기록 경로 |
| --- | --- | --- | --- |
| 기존 build + 전체 unit | 391 PASS | 391 PASS | 각 build의 `m2-review/build.txt`, `unit.txt`, `unit.xml`, `test-inventory.json` |
| model vCAN: Steering 2 / Brake 3 / isolated Drive 3 | 8 PASS | 8 PASS | 각 build의 `m2-review/vcan-model.txt`, `socketcan-results/*-model-*.log` |
| Steering/Brake/isolated Drive/Battery/BMS demo | 5 PASS | 5 PASS | 각 build의 `m2-review/<command>.txt`; 실행 smoke, unit와 별도 |
| combined `normal/weld/current-unknown/aux-blocked` | 4 PASS | 4 PASS | 각 build의 `m2-review/ev-power-<scenario>.txt`; 종료 phase/fault/접점·unknown·에너지 잔차를 별도 assertion으로 확인 |

391개는 기존 M1 143개와 M2 component 248개의 합이다. vCAN 기존 all 97개 이력을 유지하며,
이번에 재실행한 것은 model 8개다. EV gate/combined loop를 SocketCAN에 연결한 새 case는 없다.
새 runtime 코드·시험 모듈·외부 의존성은 추가하지 않았다. 정적 분석/production build의 앞선
[회로 연결 기록](../development-guide.md)은 같은 구현에 대한 이력으로 유지한다.

```sh
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --build-dir build/m1-angle --family model
build/m1-angle/actuator_demo ev-power normal
build/m1-angle/actuator_demo ev-power weld
build/m1-angle/actuator_demo ev-power current-unknown
build/m1-angle/actuator_demo ev-power aux-blocked
```

Sanitizer는 `build/m1-angle-sanitized`의 기존 `STRATADRIVE_SANITIZERS=ON` build에서 동일 범위를 실행했다.
Unit/수동 시계 demo의 시간은 논리 시간이며, vCAN의 local monotonic wall-time 결과와 구분한다.
Sanitizer 실행 시간은 대표 성능 수치가 아니다.

[Traceability](../test-plan/requirements-traceability.md)의 다음 요구에 **부분 증거**를 연결한다.

- SYS-ARCH-002, SYS-COM-002/003/004, SYS-SAFE-002/003/004: Command/Actual 구분, 수신·보호·세션.
- SYS-CTRL-009, SYS-EV-003/005: actual 기반 회생·한계·단일 energy owner.
- SYS-EV-001/002/004: local power readiness, source/dependency/validity, 고장별 local reaction.
- SYS-PERF-002/003: 논리 주기·명시적 clock/gap 처리의 부분 증거. 실제 task/E2E 측정은 후속이다.

32개 system requirement와 29개 system TC의 전체 Result는 모두 **NOT RUN**을 유지한다.
학습자의 wire 채택·설명·직접 실행 기록도 **PENDING**이다.

<a id="m2-brake-후속-기술-검토"></a>

### Brake 후속 기술 검토

2026-10-16, ADR-0031의 구현 commit `c1b58f2`를 대조했다. 새 unit 40개와 기존 Brake adapter 16개를 포함해 전체 470개,
normal·ASan/UBSan에서 PASS다. Production build, static analysis, Brake 8개 scenario와 기존 model vCAN 8개도 검사했다.
세부 증거는 [품질 기록](../development-guide.md), 수동 재현은 [Brake 학습 안내](../learning/vehicle-models-guide.md)에 있다.

- 정상 가압/감압의 양끝 rate·delay·saturation은 고장으로 판정하지 않는다.
- Fresh command/sensor 중 stuck·slow response는 residual의 source-time dwell로 검출한다.
- 보호 요청 뒤에도 물리 stuck이 지속되고 floor를 못 채우는 경우를 시험했다. Floor 관측과 제동 성공은 다르다.
- Sensor cache/invalid는 fresh Actual을 만들지 않는다. 새 epoch는 물리 압력/취득 번호를 보존하고 persistent stuck을 다시 검출한다.
- 단일 센서로 기계 원인을 분리하지 않으며 OS task 정지·vehicle stop·DTC 통합을 검증한 결과가 아니다.

OPEN-M2-01/02의 component 구현 공백은 해소했다. OPEN-M2-03과 wire 채택은 학습자 검토로 남긴다.
[실행 경계 정리](../learning/vehicle-models-guide.md)로 ECU library의 plant 소유/호출은 제거했다.
M3의 첫 산출물은 release/clock owner와 실제 task 경계, bounded handoff, 독립 monitor의 정지 검출 계약,
job/입력/적용 target을 연결하는 trace schema와 측정 protocol이다. Period와 deadline을 별도로 정하고
manual-clock 응답 지연과 실제 execution/jitter를 구분한다.

<a id="m2-미완료-항목과-다음-작업"></a>

### 미완료 항목과 다음 작업

| 항목 | 닫기 위해 필요한 것 | 단계 / 담당 |
| --- | --- | --- |
| OPEN-M2-01 Steering response fault | 후속 sensor/물리 경계와 rate-band predictor·residual/dwell·latch, 정상/고장/새 epoch를 구현·시험; [상세 증거](../learning/vehicle-models-guide.md) | **M2 component 검사 완료 / 학습자 수용 PENDING** / vECU·model 담당 |
| OPEN-M2-02 Brake response fault | [독립 pressure sensor·가압/감압 band·residual/dwell](../learning/vehicle-models-guide.md), 보호 floor 요청/관측·persistent stuck·새 epoch 구현·시험 | **M2 component 검사 완료 / 학습자 수용 PENDING** / vECU·model 담당 |
| OPEN-M2-03 학습자 수용 | 기존 M1 wire와 M2 정상/고장/복구를 직접 재현하고 설정·로그의 의미를 본인 설명으로 기록 | **M1/M2 PENDING** / project owner |
| M3 준비: 실제 task/monitor | release owner·clock·period와 deadline 구분, RX/monitor/control 배치·bounded queue/snapshot, task 정지 감시 독립성과 gap/overload 처리 | **M3** / runtime·timing 담당 |
| M3 준비: trace와 원인 연결 | run/epoch/clock, release/start/end, raw RX/accept/reject, queue/drop, 보호 검출·동작 시각, 사용 입력과 actual의 identity | **M3** / instrumentation 담당 |
| M3 준비: 측정 protocol | 사전 workload/warmup/duration/repetitions·deadline/budget, Mean/P95/P99/Max와 eligible/missed/dropped jobs, trace overhead | **M3**, TBD-04 / timing 담당 |
| 실제 coordinator·Zone·배분·차량 | fixture 교체, 원천 metadata 보존, 독립 loss/rejoin, pressure/torque mapping과 실제 차량 에너지·정지 검증 | **M4–M7** / architecture·plant 담당 |

Actual.CausalSequence는 현재 마지막 수용 Command 문맥이다. Delay 동안 더 최근 명령으로 바뀔 수 있으므로
그 값만으로 실제 운동을 만든 delayed target이나 command→응답 latency를 확정할 수 없다.
M3 trace는 사용 snapshot/목표 적용 시각을 별도로 연결해야 한다.
통합 demo의 100 ms/상태 변화 콘솔 출력도 모든 10 ms job의 trace를 대신하지 않는다.

**Steering/Brake local detector의 Host component 구현·검사는 완료했다. 학습자 수용은 PENDING이며 M3 실행·계측은 진행 중이다.**
현재 다중 주기·CAN 감시 범위와 다음 과제는 [M3 안내](../learning/runtime-timing-guide.md)에 기록한다.
Brake도 독립 sensor/fault 경계를 두고 기존 delay/rise/fall·floor 시험 16개를 유지했다.
학습자 수용을 대신 작성하거나 M2를 전체 완료 표시하지 않는다.
M3 계측 설계는 병행 준비할 수 있지만 M2 미완료 항목의 해결 결과와 별도로 기록한다.

<a id="m3"></a>

## M3 수용 검토: Host 실행·타이밍·보호 동작

Review ID: **M3-REV-20261019** / Date: **2026-10-19**.
판정: **Host 실행 기준 선택·기술 검토 완료 / 타이밍 예외 OPEN / 전체 M3 수용 PENDING**.
수행: Codex의 계약·코드·보존된 실행 증거 대조. Milestone은 **IN PROGRESS**로 유지한다.

다음 Host 통합의 기준으로 IO 동반 CPU 배치와 owner별 FIFO 설정을 선택한다.
기존 실행의 기본 정책을 변경하지 않으며 명시적 CLI 옵션으로 적용한다.
정상 비교 24회와 FIFO 고장 회귀는 통과했지만 일반 우선순위 sanitizer의 실패 2건은 남아 있다.
이 선택은 해당 Host fixture에서 후속 통합을 시작할 기준이며 전체 timing 충족이나 학습자 수용 판정은 아니다.

<a id="m3-검토-범위와-근거"></a>

### 검토 범위와 근거

측정 구현은 `7843a7e`, 직전 결과 문서는 `66c1dc3`이다. 이번 집계 수정은 `da185c3`이다.
검토 기준은 [timing 계약](../requirements/timing-requirements.md),
[다중 주기·CAN 감시](design-decisions.md#adr-0034),
[비동기 Actual](design-decisions.md#adr-0036),
[owner 완료 guard](design-decisions.md#adr-0039),
[native FIFO](design-decisions.md#adr-0042)다.
기존 [학습 원칙](../learning/README.md)과 [품질 정책](../development-guide.md)을 적용한다.

대상은 x86_64 Host의 finite Linux/vCAN 실행과 별도 Steering hosted OS 파일럿이다.
Native multirate는 Brake/Drive/BMS/Power·RX·monitor·plant 일곱 owner를 실행한다.
Steering은 별도 native/RTOS fixture로 검사했으며 모든 Leaf가 한 차량 runtime에 통합된 결과는 아니다.
Central request/grant·relay·고정 speed 20 rad/s는 fixture다.
Central/두 Zone·DDS·차량 운동·CARLA·Target timing 및 RTE/BSW는 후속 범위다.

| 수용 항목 | 대조한 근거와 판정 |
| --- | --- |
| Release·실행·완료·누락 분모 | Absolute release와 개별 시한, skipped row·monitor tail을 유지. 정상 비교의 eligible/miss/skip 대조 PASS |
| Clock·원천 시각·Actual | Local CLOCK_MONOTONIC, 실제 torque 취득→보고 생성→socket TX→독립 RX를 보존. Local 부분 검사 PASS; cross-node/E2E 미실행 |
| 작업 정지·유효 수신 상실 | ECU/RX stall, CRC-invalid·Actual replay, owner overrun/stall·교차 guard·수신 이중 감시의 FIFO 회귀 PASS |
| 보호 요청·물리 적용·관측 | 검출→plant 보호 목표 적용과 유한 pressure/torque 응답을 구분. Plant/process 전체 정지 중 출력 변경은 보장하지 않음 |
| 실제 CPU·policy·startup·복원 | Native 92회의 설정·배치·부하 control PASS. 별도 CLI 3건의 예상 거부 PASS; 부분 설정 실패 시 workload 미실행 |
| 일반/FIFO 비교 | 동일 binary·workload·시한의 24/24 PASS. 선택한 Host 배치/FIFO의 근거로 사용 |
| Sanitizer 회귀 | OTHER 15/17, FIFO 17/17. OTHER 두 타이밍 실패 OPEN; sanitizer 결과를 성능 표본에 합치지 않음 |
| Hosted OS·ARM64 | Trampoline 기능 회귀 4/4, ARM64 교차 빌드 PASS. Hosted tick drift와 보드 runtime은 미해소/미실행 |
| 전체 시스템·학습자 수용 | 32개 requirement/29개 system TC는 NOT RUN. 직접 재현·설명 기록은 PENDING |

위 PASS는 명시한 유한 component 실행에 적용한다. 전체 system requirement의 VERIFIED 판정으로 확대하지 않는다.

<a id="m3-선택한-host-실행-기준과-분모"></a>

### 선택한 Host 실행 기준과 분모

기존 [reference.yaml](../../profiles/reference.yaml)의 `m3_multirate_runtime_fixture`와
`m3_native_fifo_fixture` 값을 사용한다. YAML은 설계 기록이며 loader는 없다.

| Owner | CPU 역할 | FIFO priority | 주기 / 완료 시한 (ms) | Run당 eligible jobs |
| --- | --- | --- | --- | --- |
| Brake | Work B | 10 | 10 / 5 | 240 |
| Drive | Work B | 10 | 10 / 5 | 240 |
| BMS | Work B | 9 | 20 / 8 | 120 |
| Power | Work B | 10 | 10 / 5 | 240 |
| RX | IO A | 18 | 2 / 3 | 1210 |
| Monitor | IO A | 20 | 2 / 4 | 1211 guarded slots |
| Plant/fixture | IO A | 19 | 2 / 4 | 1211 guarded slots |

이번 Host는 IO A=CPU 0, Work B=CPU 1의 서로 다른 physical core를 사용했다.
다른 Host에서는 allowed mask·topology와 실제 owner 설정을 다시 확인한다. 우선순위는 초기 fixture이며 최적값을 입증하지 않았다.
Owner 순서의 CLI 값은 `owner-cpus=1,1,1,1,0,0,0`, `owner-fifo=10,10,9,10,18,20,19`다.
계정 rtprio 상한 20을 받는 새 PAM 실행 세션과 SCHED_OTHER/0 launcher를 사용한다.
일곱 owner의 실제 설정·ready 확인 후에만 시작하며 실패 시 일반 policy로 대체하지 않는다.
호출 thread의 policy·priority·affinity는 join/파일 출력 전에 복원한다.

정상 workload는 2400 ms, 감시 tail은 40 ms, warm-up 제외는 0이다.
Monitor/plant는 각각 총 1221 slots를 관측하고 마지막 10개를 guard 분모에서 제외한다.
Guard는 enable부터 2420 ms까지 1211 slots, 마지막 시한은 2424 ms다.
최신 release를 실행해도 생략된 이전 slot은 miss로 남긴다.
정상 비교 24회의 분모는 Brake/Drive/Power 각각 **5760**, BMS **2880**, RX **29040**,
monitor/plant guarded slot은 각각 **29064**이며 이 범위의 missed/skipped는 모두 0이다.
주입 시험은 주입된 누락을 0으로 요구하지 않고 해당 정지 검출·보호·관련 없는 누락 여부를 검사한다.

유효 RX threshold는 80 ms, 마지막 accepted RX부터 실제 검출까지 상한은 100 ms다.
Raw/CRC-invalid/replay는 accepted age를 갱신하지 않는다. Owner 시한 이후 검출 margin과
첫 검출 이후 보호 목표 적용 margin은 각각 10 ms의 Host 기준이다.
후자는 plant가 실행 가능한 주입 조건에서 검사하며 실제 압력 도달·차량 정지 시한과 다르다.

<a id="m3-보존된-결과와-타이밍-예외"></a>

### 보존된 결과와 타이밍 예외

| 실행 묶음 | 결과 |
| --- | --- |
| Normal build 일반/FIFO × quiet/loaded × full/minimal × 3회 | 24/24 PASS |
| Normal build OTHER / FIFO 고장 회귀 | 각각 17/17 PASS |
| ASan/UBSan OTHER / FIFO 고장 회귀 | 15/17 / 17/17 PASS |
| 별도 hosted OS Steering 회귀 | 4/4 PASS |
| 합계 | **94/96 PASS, 2 FAIL 보존** |

Native FIFO는 비교 12회와 두 build 고장 회귀 34회를 합쳐 46/46 PASS다.
CLI 권한 없음·부분 설정 거부·중복 옵션 3건은 예상 거부 검사이며 96회 분모에 넣지 않는다.

추가 부하의 Drive release→완료 지연은 다음과 같다. 단위는 ms이며 각 셀은 독립 3회에서
수집한 720개 job 관측의 nearest-rank p99다. Run별 p99의 평균이나 단계별 percentile 합이 아니다.

| Trace | OTHER p99 / max | FIFO p99 / max | 시한 |
| --- | --- | --- | --- |
| Full | 1.946878 / 2.638265 | 0.065454 / 0.099024 | 5 |
| Minimal | 2.449738 / 2.493961 | 0.073157 / 0.090526 | 5 |

Quiet/minimal RX max는 OTHER 0.342025 ms, FIFO 1.065564 ms로 모두 3 ms 안이었다.
부하는 Work B의 SCHED_OTHER 7/10 ms wall busy window이며 실제 CPU 비율 경계는 약 0.664–0.688이었다.
Host는 i7-11700·Linux 6.8.0-138-generic PREEMPT_DYNAMIC, governor powersave다.
Power/clocks/cooling·background는 고정하지 않았다. 짧은 관측과 세 번의 반복으로 WCET·hard real-time을 보장하지 않는다.
Full/minimal은 별도 관측이며 그 차이를 시한에서 빼지 않는다.

두 FAIL은 모두 sanitizer OTHER·full trace다. 다음 시각은 enable 기준 ms다.

| Run / 원래 실패 | 관측과 보호 동작 |
| --- | --- |
| `power-stall-full-1` / `unplanned owner deadline miss` | Plant slot 1035(release 2070) 생략, 다음 요청 wake 지연 2.053252. Monitor 검출 2074.100001, floor 목표 plant 적용 2076.057343. 그때 압력은 이미 1.3 MPa. Power 정지 때문에 먼저 적용한 zero 목표는 1104.230218, 실제 torque 0 관측은 1200.234945 |
| `rx-stall-full-1` / `Drive gate never enabled before fault` | Plant slots 210/721·monitor slot 721 생략. 요청 wake 지연 2.073495/2.054862/2.111280. 첫 검출 424.154572, floor/zero 목표 적용 426.067791. 그때 압력 0.3 MPa, 1 MPa 이상 첫 관측 566.313704; torque는 이미 0 |

총 4개 guarded slot 누락이다. RX 시험은 계획한 1100 ms 주입 전에 보호되어 Drive가 활성화되지 않았다.
보호가 실행된 사실은 원래 시험 조건의 실패를 없애지 않는다. Plant body max는 각각 0.238077/0.205986 ms였지만
이 사실만으로 timer·IRQ·runqueue의 원인을 특정할 수 없다. 이 cohort의 kernel trace는 없다.
별도 observer 실험의 runqueue 증가를 이 두 run의 원인으로 소급하지 않는다.
Runtime abort/trace drop·설정 control 실패는 없었고 시한 완화나 재실행 PASS로 원본을 교체하지 않았다.

`floor_applied_ns`/`zero_applied_ns`는 물리 owner가 보호 목표를 받은 시각이다.
Actual이 그 목표에 도달한 시각은 `physical.csv`에서 따로 확인해야 한다.
특히 이미 torque 0인 RX 실패는 주행 중 감속 성공의 증거로 쓸 수 없다.

<a id="m3-이번-검토의-집계-수정과-증거"></a>

### 이번 검토의 집계 수정과 증거

여러 run을 합친 nested `guarded_deadlines.observed_start_interval_ms`가 실행 사이의 대기 시간을
포함하는 오류를 발견했다. 기존 `pooled_job_metrics`로 run 경계를 보존하도록 수정하고
guarded slot·tail·skip을 포함한 회귀 검사를 추가했다. Python은 **60개 PASS**다.
수정 전 회귀 검사의 interval 수는 예상 3개 대신 4개로 실패했다.

보존된 96회를 수정한 리포터로 재분석했다. 비교 8조건×2 owner의 해당 16개 분포만 바뀌었고,
각 분포의 interval 표본은 3632→3630이다. 개별 run의 owner 통계·판정, Drive/RX 응답 지연,
job 분모·miss/skip·trace 비교는 동일했다. 새 workload 실행은 **0회**다.
이번 변경은 리포터와 회귀 검사이며 native runtime/binary·주기·시한은 수정하지 않았다.
직전 C++ normal/sanitizer 각각 523개·static/build PASS는 기존 검사 이력으로 유지한다.

원본은 `build/m3-fifo-comparison/`, `build/m3-fifo-{other-faults,fifo-faults,asan-other-faults,asan-fifo-faults}/`,
`build/m3-fifo-rtos-regression/`에 있다. 각 environment/source/binary·CSV/summary/artifact manifest를 보존했다.
검토 전 감사는 구현 commit의 blob·현재 source/binary·manifest를 대조했다.
`build/m3-acceptance-review/`에 그 감사 `m3-fifo-evidence.*`와 수정 후 `reanalyze.py`·`reanalysis.json`·`reanalysis.txt`를 둔다.
원본 summary/hash는 교정된 값으로 덮어쓰지 않았다. 상세 실행 명령·과거 실패·build 한계는
[품질 기록](milestone-reviews.md)과
[학습 안내](../learning/runtime-timing-guide.md)에 있다. `build/`는 git 제외 경로이며 clone에 원본 로그가 포함되지는 않는다.

<a id="m3-남은-항목과-다음-단계"></a>

### 남은 항목과 다음 단계

| 항목 | 닫기 위해 필요한 증거 / 책임 단계 |
| --- | --- |
| OPEN-M3-01 일반 sanitizer 타이밍 실패 | 두 원본 run·4개 skip을 보존하고 wake 지연 원인을 추가 관측. 원인·영향·개선 또는 적용 범위 제한의 근거와 새 cohort 회귀를 검토한다. 새 PASS만으로 닫지 않는다. **M3 timing 담당** |
| OPEN-M3-02 추가 지연 분석 | Trace/perf 접근 준비 후 같은 TID/clock의 timer→wakeup→switch 대조, observer overhead·miss·실제 부하를 기록. PREEMPT_RT 비교는 후속 실험이며 FIFO 적용과 구분한다. **M3 진단 후속** |
| OPEN-M3-03 학습자 수용 | Period/deadline·skip·source/accepted age·보호 목표/Actual·일반/FIFO 결과를 직접 재현하고 설명한다. **Project owner; M1/M2 review도 PENDING** |
| Target timing·hosted OS | Board OS/BSP/sysroot·ELF ABI/stack/IPC/SocketCAN과 실제 ARM64 runtime·tick drift 검증. 교차 빌드 PASS를 실행 PASS로 바꾸지 않는다. **Target 배포/M5·M12 및 OS 확장 전** |
| Cross-node·전체 E2E | Central/각 Zone task budget·clock uncertainty·QoS와 원천 인과 경로를 연결한 측정. **M4/M5/M7** |

Kernel trace 미확보·PREEMPT_RT 미실험·Target 미실행은 해당 증거의 공백이다.
PREEMPT_RT 채택을 새로운 필수 요구로 추가하거나 기존 Host 시험을 Target 시험으로 대체하지 않는다.
TBD-04는 Host fixture 값만 부분 결정했고 차량/Target·E2E의 전체 budget은 열린 상태다.

다음 구현은 **M4의 Central coordinator 입출력·상태 계약과 순수 판단 로직부터** 준비할 수 있다.
Central이 vehicle management/allocation/session을 소유하고 Front(Steering/Brake), Rear(Drive/BMS)를
각각 연결한다. Original source/dependency·parent expiry·유효 0/unknown·local loss/rejoin을 먼저 정의한다.
이 설계·기능 준비와 M3 timing 예외 해소를 병행할 수 있으나 M3 전체 수용 완료로 표시하지 않는다.
새 통합 workload의 task/queue/monitor budget을 먼저 정하고 정상·정지·재가입을 다시 시험해야 한다.
Central/Zone 추가 뒤에도 기존 보호 경로의 독립성과 실제 적용을 재확인한다.
실제 DDS transport는 M5, 차량 closed-loop/control은 후속 milestone이다.

<a id="m3-후속-host-지연-개선"></a>

### 후속 Host 지연 개선

2026-10-19 [ADR-0043](design-decisions.md#adr-0043)으로 hosted RTOS timer의
누적 relative 지연을 absolute timerfd로 수정하고 실제 배치·FIFO·expiration/OS release를 대조했다.
별도 48회는 기능 48 PASS, 추가 Host timing은 absolute 24 PASS / relative 24 FAIL이다.
선택한 RTOS/FIFO의 normal phase→Control 완료 max 0.276923 ms와 drift 절댓값 <0.001 ms를 관측했다.
고장 주입은 13 ticks로 최소 wall 정지 120 ms를 유지한다. Native 120 ms/기존 시한은 바꾸지 않았다.
Native FIFO 후속은 normal/sanitizer 각각 51/51 PASS다. 진단 12회·timer stop·원본 호환은 별도이며
원래 96회/94 PASS·두 FAIL을 대체하지 않는다. Python은 현재 63개, C++은 각각 523개다.
OPEN-M3-01/02의 native 커널 원인과 학습자·Target/전체 수용은 남긴다.
실행 명령·한계·source cohort는 [학습 안내](../learning/runtime-timing-guide.md)를 따른다.

<a id="m4-host"></a>

## M4 Host IO/FIFO 한정 수용 검토안

이 문서는 **M4 판정과 당시 DDS 검토 기록**이다. M5 Rear 연결·M6 후속의 현재 상태는
[project_status](../project-status.md), M6 범위 종료는 [종료 검토](#m6)를 따른다.
SOME/IP 후속 채택이 아래 M4 전체 NOT CLOSED·DDS gate/원본 FAIL을 바꾸지는 않는다.

Updated:2026-10-21. **B APPROVED — Host native IO/FIFO component 한정 수용**.
승인 근거: `7bbafc7` 검토 뒤 사용자의 명시적 B안 승인.
**M4 전체 NOT CLOSED / DDS 제어 gate CLOSED**다. M5 transport qualification은 착수한다.
승인은 아래 Host component 범위에만 적용한다. 기본 OTHER policy·Ubuntu/CPU/FIFO 배치·
2ms 기회/4ms deadline·명령 expiry/20ms envelope와 보호 조건은 변경하지 않는다.
[현재 상태](../project-status.md), [기존 종료 기준](#m4),
[새 DDS 수명 검증](../test-plan/evidence/m4_dds_lifetime/README.md)을 함께 본다.

`658562e` 후속 [종료·TSan 경로별 검토](../test-plan/evidence/m5_dds_shutdown_followup/README.md)에서도
full-RHC 종료 OPEN·64회 경고 FAIL이 남아 DDS 정규 adapter 연결은 불가다.
관련 Python29/29는 fresh-checkout 준비/실패 수집 검증이며 SDK 수용 근거가 아니다.

별도 [SOME/IP 파일럿](../test-plan/evidence/m5_someip_pilot/README.md)은 Host 두 프로세스
component 경로의 조건부 후보 검증이다. 지정 기능과 실제 SDK 계측 결과를 확보했지만
전체 session/보호/Target 배포는 미검증이며, 이 문서의 한정 수용이나 DDS gate를 변경하지 않는다.

<a id="m4-host-판단과-선택지"></a>

### 판단과 선택지

**기존 조건을 모두 유지한 M4 전체 종료는 NO-GO**다. DDS 전체 동시성 검증과 과거
두 실행 실패의 원인이 미확정이다. 다만 **검증된 Host native component를 IO/FIFO
조건으로 한정 수용하는 안은 권고할 수 있다.** 수용은 원인 해결 선언과 다르며 아래
명시적 예외 이관과 M5 진입 순서를 사용자가 승인했다. DDS 안전성 승인·전체 M4 종료는 아니다.

| 결정 | 기존 조건에 대한 변경 | 영향과 권고 |
| --- | --- | --- |
| A. 기존 M4 종료 조건 유지 | 변경 없음. timing/native/SDK 세 OPEN의 기존 차단 유지 | 비선택 대안으로 보존. 원래 전체 종료 조건은 여전히 미충족 |
| B. Host IO/FIFO component 한정 수용 | Host component 범위를 아래 profile로 명시. OTHER loaded 정상 운전 수용 제외를 공식 승인하고 TIM/native 미확정 사건은 OPEN 예외로 이관. SDK 검증은 M5의 transport 단계 진입 gate로 이관 | **승인·적용**. Host 한정 기술 단위 수용과 M5 transport qualification 착수. DDS 정규 제어 adapter의 정상 명령 enable은 SDK gate 이후. 전체 M3/Target/system/학습자 종료를 뜻하지 않음 |

B를 선택해도 기존 실패를 PASS나 RESOLVED로 바꾸지 않는다. 과거 사건과 DDS 경고는
추적·재발 판정·후속 차단이 유지된다. B는 이 범위로 승인됐고 OTHER 부하 실패·과거 FIFO/native 사건·DDS 경고는
원본과 함께 OPEN 예외로 유지한다. M4 전체 무조건 종료나 M5 정규 제어 허용을 권고하는 근거는 없다.

<a id="m4-host-재사용-가능한-소스시험-근거"></a>

### 재사용 가능한 소스·시험 근거

[소스/바이너리 대조](../test-plan/evidence/m4_dds_lifetime/source-reuse.json): `97afb35`부터
검토 HEAD까지 `central/zone/vecu/interfaces/simulation/cmake/CMakeLists.txt`의 production
변경은 없다. Normal/ASan/TSan의 `actuator_demo`와 runtime test, **6개 SHA256가 모두
기존 근거와 동일**하다. 그 뒤 변경한 runner·수집기·진단 시험을 C++ 제어 경로의 변경으로
취급하거나 예전 결과를 새 실행이라고 부르지 않는다.

기존 [48회](../test-plan/evidence/m4_settlement/README.md)는 normal/ASan, OTHER/FIFO,
동일 CPUs0/1, 무부하 또는 CPU1에7ms/10ms OTHER 부하, normal/Drive pause/Monitor overrun을
3회씩 수행했다. 설정·부하·grid·성장 control은48/48 통과했고 결과는42 PASS/6 FAIL이다.
정상 운전 비교만 추리면 다음과 같다. 숫자는 **실제 실행 횟수**, 새 측정값이 아니다.

| Build/정상 조건 | OTHER | FIFO | 입증한 범위 |
| --- | --- | --- | --- |
| Normal, 추가 부하 없음 | 3/3 PASS | 3/3 PASS | 같은 map/주기/시한에서 정상 운전 |
| Normal, CPU1 부하7/10ms | **0/3 PASS** | **3/3 PASS** | 같은 부하에서 FIFO 정상 운전; OTHER 기회/완료 계약 실패 |
| ASan/UBSan, 추가 부하 없음 | 3/3 PASS | 3/3 PASS | 계측된 동일 조건의 기능·기회 관측 |
| ASan/UBSan, CPU1 부하7/10ms | **0/3 PASS** | **3/3 PASS** | 같은 부하에서 FIFO 통과; OTHER 실패 보존 |

나머지 고장24회는 두 policy/build의 Drive pause와 Monitor6ms 지연이다. FIFO12회는
모두 고장 oracle PASS이며 정상 FIFO12회와 합쳐 **FIFO24/24**다. 고장 중 발생하는
미실행 기회를 정상 timing PASS로 바꾸지 않는다. [전체 비교 CSV](../test-plan/evidence/m4_dds_lifetime/host-comparison.csv).

[213425 고정 수집](../test-plan/evidence/m4_kernel_campaign/completed_213425/README.md)의 FIFO20회는
**Normal build·추가 부하 없는 Monitor overrun**이다. 48회의 loaded 정상 조건을 대체하지
않는다. 추적11쌍 유효, FIFO 주입 전 miss0, 원래 deadline 뒤3.170–5.059µs 검출·
이후1.008–3.484µs Physical override는 독립 감시 경로의 추가 근거다.
OTHER2회는191/186 miss·FAIL이며 정상 arm 전에 보호했다.

이 재사용 범위에서 새 수용용48회나 같은 FIFO 수집을 반복할 누락 조건은 없다.
새 DDS adapter로 실행 부하/스레드/프로세스가 달라지면 그때 별도 원래 프로토콜을
적용한다. 이번 DDS ASan/TSan·수명 시험은 기능/동시성 진단이며 timing 수용 결과가 아니다.

<a id="m4-host-승인한-host-실행-조건"></a>

### 승인한 Host 실행 조건

| 항목 | 한정 수용 profile과 실제 근거 |
| --- | --- |
| Host | 현재 Ubuntu22.04/x86_64, kernel6.8.0-138-generic/PREEMPT_DYNAMIC. Jetson에 이 수치를 이식하지 않음 |
| 기본 정책 | 현재 상속 OTHER 기본은 그대로. 제어 실행 profile은 CLI로 명시한 SCHED_FIFO. profile을 요청했는데 적용 실패하면 SETUP 실패, timing 실패나 PASS로 합치지 않음 |
| 권한 | 검증된 원래 사용자 RTPRIO20/20; vECU/부하 UID1000·effective capabilities0. sudo는 추적 수집만 수행 |
| CPU A=0 | Front18, Rear18, Physical19, Monitor20; 각 thread의 affinity=[0] |
| CPU B=1 | Central11, Steering/Brake/Drive/Power10, BMS9; 각 affinity=[1] |
| 부하 | 무부하 및 CPU1의 OTHER0 7ms busy/10ms period가 검증됨. 임의 고우선순위 RT 경쟁·다른 CPU map·SDK 추가 worker까지 보장하지 않음 |
| 시간 계약 | CLOCK_MONOTONIC grid,2ms 실행 기회/4ms 완료 deadline, 원래 command expiry와 최초 sent 기준20ms envelope. 늦은 회차를 앞선 회차 완료로 채우지 않음 |
| 보호·복구 | 독립 Monitor/Physical 감시와 실제 output override·gate latch. 통신/부분 송신 실패·epoch/parent/lease·준비/arm·durable epoch 재가입은 기존 component 회귀 근거로 유지 |
| IO 범위 | M3 IO 배치 계열과 현재 same-process typed port/mailbox·vCAN component 근거. 아직 없는 실제 DDS control adapter/NIC·원격 process timing을 포함하지 않음 |

현재 관측된 OTHER loaded 실패는 주로 CPU 배정 대기다. 대표 구간에서 timer hard-expiry
초과2.268µs, runnable 대기3.559ms(부하 process3.536ms), body1.102µs였다. 기존 최신-slot
선택 때문에 기회를 놓친 것이며 짧은 body만으로2ms/4ms 계약을 만족한다고 판단할 수 없다.
이 부하 조건의 OTHER 정상 제어는 **미충족**이다. B 승인으로 이 부하 조건의 OTHER 정상 운전은 한정 수용 범위에서
명시적으로 제외했다. 실패 판정 자체는 변경하지 않는다. 이 관측으로 과거 FIFO 사건의 OS 원인을 확정하지 않는다.

<a id="m4-host-미확정-사건의-처리안"></a>

### 미확정 사건의 처리안

| OPEN | 복원 가능한 사실 / 없는 정보 | 영향·이미 확인한 보호 | 재발 시 필수 기록 / 처리 제안 |
| --- | --- | --- | --- |
| OPEN-M4-TIM-01: 과거 FIFO | `1989477` Front/Rear slot281 release662ms/deadline666ms 미실행. 직전 Rear body1.117555ms/CPU1.107494ms, 다음 요청 wake662ms→실제 slot282 start664.151891ms. timer 만료/wakeup/switch/IRQ chain 없음 | 실제666.004077ms 검출·666.009677ms physical override. 정상 가용성 실패. 현재97afb35 FIFO24/24와 추가20/20에서 해당 주입 전 사건은 미재현 | 동일 source/binary, 실제 TID·timer/스케줄/IRQ, 요청 wake·job 시작/완료·deadline·보호 이벤트. Rear CPU burst만으로 다음2.15ms 지연의 원인을 확정할 수 없음. A에서는 차단, B에서는 원인 미확정 예외로 OPEN 유지·같은 profile 재발 시 수용 재검토 |
| OPEN-M4-TSAN-01: native CommandDelivery | `d7115ff` 정상 arm810.816152ms 뒤 fault915.290114ms, protection selection915.819030ms. token/source/deadline·구간별 transaction trace 없음. 별도 저장 trace는 후속 PASS | 원본 실패의 최종 모델 pressure1MPa·torque0는 보호 출력으로 바뀐 결과. 정확한 실제 override 시각은 없음. 현재 boundary108+wall9와 두 native40 묶음 PASS; pending 계약 수정은 별도 논리 재현으로 검증 | 최초 요청의 epoch/token/source/expiry, Central enqueue→Zone RX/dispatch→Leaf 적용→result, 실제 gate/모델/ACK. 기존 settlement 수정이나 TSan 부담이 옛 원인이라는 인과 증명 불가. A에서는 차단, B에서는 원래 OTHER/unpinned/guard-OFF 진단 사건을 OPEN 예외로 이관하고 재발 즉시 분석 |
| OPEN-M4-MWTSAN-01: DDS | 29개 경고를4개 수명/게시 계열로 구분. 실제 Writer scope/GC·mutex 수명은 정상6회 및 ASan UAF 대조3회로 좁힘. TSan Writer3회와 wrapper2회는 여전히 FAIL. bucket/remote/WHC 전체 안전성 미확정 | 현재 실제 DDS control adapter가 없으므로 Host component의 명령 경로에는 이 SDK가 참여하지 않음. 향후 원격 adapter에서는 SDK 경쟁/오류가 누락·만료·재시작으로 나타날 수 있음. 기존 in-process gate가 원격 안전성을 보장하지 않음 | 생성/게시/unlink/vtime/마지막 접근/free·callback 종료·mutex destroy를 객체 identity로 연결. A에서는 차단, B에서는 **M5 transport qualification gate**로 이관. 원인/수명 근거 또는 지원되는 수정이 준비되기 전 정규 제어 enable 금지 |

후속 반복은 같은 PASS를 더 모으는 목적이 아니라 새 가설·계측을 검증할 때만 한다.
과거 FIFO/native 실패 로그의 빠진 사건은 새 실행으로 복원할 수 없다.
기존2ms/4ms/expiry/envelope를 완화하거나 기록을 RESOLVED로 바꾸지 않는다.

<a id="m4-host-승인-후-m5-첫-단위와-제어-gate-판정"></a>

### 승인 후 M5 첫 단위와 제어 gate 판정

1. **첫 착수: pinned DDS의 두 process transport/lifetime qualification.** Central↔Front의
   bounded ingress/result lane, session/epoch identity, 정상 종료·중간 peer 종료·재시작을
   실제 process로 구분한다. 이 단계에서는 control run gate를 닫아 둔다. DDS의 남은
   bucket/proxy/WHC 경로를 실제 생성·접근·종료·해제로 재현하고, ASan/TSan 결과 및 source
   수명 논증으로 분류하거나 검증된 지원 수정을 비교한다. 기존 증명 없는 경고는 PASS가
   아니며 suppress/seq_cst 일괄 교체로 종결하지 않는다.
2. **기존 계획의 첫 제어 adapter는 그 gate 뒤에 시작.** 실제 Central↔Front의
   Prepare→INIT/ACK→readiness→arm→normal request/result→원천 Actual을 연결한다.
   Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임은 유지한다.
3. **제어 단위 합격:** 정상 경로의 원래 source/epoch/token/parent/lease·CAN/P05·expiry가
   wire 왕복에 보존되고, down/up loss·delay·부분 송신/큐 포화·old epoch/late ACK를 거부한다.
   같은 epoch 자동 복구 금지·durable epoch/full handshake 재가입·모델/에너지 연속을 검사한다.
   독립 원격 감시의 보호와 stopped owner ACK 부재를 확인하고 새 workload의 기존 타이밍
   프로토콜을 별도로 실행한다. 기간/횟수/조건은 구현 전 프로토콜에 고정한다.

SDK의 기존 미완료 조건을 승인에 따라 M5 정규 제어 연결 전 필수 gate로 관리한다.
통신·종료·재시작 계약 통과, 실제 경로의 경고별 수정 또는 구체적 계측 한계/수명 근거,
설명되지 않은 메모리·수명 경고 부재, 정확한 SDK build/config 연결을 모두 충족해야 한다.
충족 시 추가 승인 없이 Central↔Front 제어 adapter를 진행한다. 미충족 시 gate를 닫고 진단을 계속한다.

Host component 수용과 별개로 **학습자 REVIEW PENDING**, Jetson·전체 원격 배포·
32 requirement/29 system TC는 **NOT RUN**이다. 배치는 Host PC + Jetson 한 대 안의 여러
vECU를 유지한다. Jetson 일반 kernel/PREEMPT_RT 비교, NIC/IPC/SocketCAN·clock·CPU/RT
priority 실제 적용과 새 workload의 성능은 Target에서 검증한다. MBD/AUTOSAR 순서는
기존 ADR·로드맵을 유지한다.

<a id="m4-host-승인-이후-실제-진행"></a>

### 승인 이후 실제 진행

[2026-10-21 qualification 결과](../test-plan/evidence/m5_dds_qualification/README.md)는
42회23 PASS/19 FAIL이다. 실제 bucket/WHC/Proxy·lease 관측과 명시적 staged restart를
추가했지만 raw close timeout·20ms 전달 실패·미확정 TSan 경고가 남는다.
**B 한정 수용 유지 / M4 전체 NOT CLOSED / DDS control gate CLOSED**다.
정규 adapter는 미착수이며 Daybreak 인증 요구 확인 뒤 추가 조사는 보류했다.
학습자·Target·system 상태와 과거 OPEN은 승인 전후 모두 유지한다.

`c10688d` 이후 [환경·운용 후보 후속](../test-plan/evidence/m5_dds_operating_profile/README.md)에서
실제 QoS/thread/status 관측, partial writer 삭제 뒤 reader 정지 결함 수정,
첫 heartbeat 전 DATA/100ms 재전송에 대한 양방향 transport 준비를 검사했다.
새 성공은 기존42회 실패나 full-RHC close/TSan OPEN을 닫지 않는다.
Host 한정 수용·M4 NOT CLOSED·DDS control gate CLOSED는 동일하다.

<a id="m4"></a>

## M4 기술 종료 검토 — Host component와 원격 경계

이 문서는 **M4 판정과 당시 DDS 검토 기록**이다. M5 Rear 연결·M6 후속의 현재 상태는
[project_status](../project-status.md), M6 범위 종료는 [종료 검토](#m6)를 따른다.
SOME/IP 후속 채택이 아래 M4 전체 NOT CLOSED·DDS gate/원본 FAIL을 바꾸지는 않는다.

Updated: 2026-10-21. Status: **HOST IO/FIFO COMPONENT LIMITED ACCEPTANCE / M4 NOT CLOSED**. 현재 상태 기준은 [project_status](../project-status.md)다.
학습자 직접 재현/설명은 **REVIEW PENDING**, system32요구/29TC·Target/전체 원격 배포는 **NOT RUN**이다.
이 검토는 위 상태를 PASS로 바꾸지 않는다.

별도 [SOME/IP Host 파일럿](../test-plan/evidence/m5_someip_pilot/README.md)은 실제 IP의
Central↔Front component 경로와 제한된 sanitizer/종료·재가입 시험을 실행한 조건부 후보다.
M4 전체 종료, 기존 DDS 실패 해결, 정규 M5 통합 또는 Jetson/전체 시스템 수용을 뜻하지 않는다.

`658562e` 후속 [DDS 종료·경고 분류](../test-plan/evidence/m5_dds_shutdown_followup/README.md)는
새 checkout의 잠금 준비 결함을 수정해 관련 Python29/29를 확인했다. SDK runtime 재실행은
없으며 full-RHC close OPEN·64 TSan occurrences FAIL·제어 gate CLOSED를 유지한다.
Writer bitfield 공유 바이트 경합을 좁혔으나 지원되는 SDK 수정은 미확정이며 문의 초안만 남겼다.

`1a4afe5` 후속은 [고정 커널 수집 준비/검사](../test-plan/evidence/m4_kernel_campaign/README.md)와
[native·SDK 진단](../test-plan/evidence/m4_sdk_followup/README.md)까지 진행했다.
해당 수집기 단계 Python112 PASS, 이전 native40 PASS이나 과거 실패 원인은 미확정이다.
사용자의 별도 `d3e7f6d` 고정 수집213425는 **11/11쌍 VALID**, OTHER2 FAIL·FIFO20 PASS다.
FIFO 주입 전 deadline 누락0건, 예정된 Monitor sleep 중 Physical이 원래 deadline 뒤
3.170–5.059µs 검출·그 뒤1.008–3.484µs 출력을 보호했다. 실제 사용자20/20·FIFO 배치·
marker/cleanup·유실0을 확인했다. 이전212418 CPU9 유실/INVALID·FIFO20회 NOT RUN은
보존한다. [전체 분모·시간축·재현](../test-plan/evidence/m4_kernel_campaign/completed_213425/README.md).
새20회는 과거 FIFO 누락의 원인 해소나 기존48회 수용 시험의 대체가 아니다.

`c52445a` 후속의 [실제 DDS 수명 근거](../test-plan/evidence/m4_dds_lifetime/README.md)는
Writer 한 경로의 GC/TSan 가시성을 좁혔지만 SDK 전체 동시성 차단을 닫지는 못했다.
Middleware runner의 오류 exit0를 수정했고 신규8개·전체 Python120개가 통과했다.
**기존 M4 전체 종료는 NO-GO**다. [Host IO/FIFO component 한정 수용 검토안](#m4-host)은
검증된 실행 profile과 과거 사건·DDS gate의 명시적 이관안을 제시한다.
사용자는 `7bbafc7` 검토 뒤 **B안을 승인**했다. 승인한 Host profile 안에서만 component를
한정 수용한다. OTHER loaded 실패·과거 FIFO/native 사건·DDS 경고는 OPEN으로 남는다.
DDS는 **M5 정규 제어 연결 전 필수 gate**이며 Target/system/학습자·전체 M4 종료는 승인하지 않았다.
현재 배치·FIFO priority·2ms/4ms·expiry/20ms envelope 및 보호 계약은 유지한다.

| 종료 항목 | 구현/실제 시험 | 근거/판정 | 차단 여부 |
| --- | --- | --- | --- |
| 정상 request/arm/TX result/status/Actual/protection 소유권 | AsyncCoordinatorPort·AsyncZoneOwner·AsyncLeafOwner; M4AsyncRuntime·AsyncOwnerTest | 실제 BMS/HV/센서 준비·arm 뒤 정상 배분; 함수→시험→두 빌드 결과93개 연결 | Host component PASS |
| owner stop/방향별 loss/delay/부분 송신/보호·재가입 | M4FaultRuntime/Wall·M4OwnerStop/M4Direction; Network::replace_joined_links | 원래 source/deadline, stopped ACK 부재, 별도 physical watchdog, failed link join/교체, 새 durable Epoch/full readiness/arm, 모델/SOC/energy 연속 | Host component PASS; 원격 격리 증거 아님 |
| 실행/메시지/복구 구조 정리 | ADR-0057, boundary compile, CTest disjoint labels | 원본948+이전 검토18+이번7개; `97afb35` normal/ASan·UBSan 각각973/973. Baseline966 이름 유지;19.8ms oracle만 ADR-0059에 따라 수정·원본 보존 | PASS; 실행 시간 동일성 증거 아님 |
| 명령 settlement·주기·실제 authority | ADR-0059; AsyncCoordinatorPort::allocation_ready, VehicleCoordinator::allocate, ControlAllocation::poll | pending이면 due 배분 한 건 보류; 새 명령/완료 tick/기준 시각을 만들지 않음. 성공 후 fresh 입력·기존20ms grid; 원래 TX20ms·request/support/적용 명령 expiry·30ms gap 검사 유지. 지연/만료·Stop·새 Epoch 회귀 PASS | 코드 결함 수정 PASS; wall timing 수용과 별도 |
| 원격 Leaf composite authority/INIT/arm/stop/protection | ICD owner-wire v1; RemoteLeafTest·RemoteZoneIntegration·RemoteOldRequestTest | 이전 Epoch 응답 identity, 최초 sent 기반20ms envelope, issuer/Epoch/token ACK8개씩 불변 보관. 실제 Zone 생산→codec→다섯 Leaf의 arm/명령/Actual/Power/Stop·만료 거부; 신규 계약15개 PASS | Host 계약/component PASS; 전체 원격 process 배포 미실행 |
| 원천 feedback/parent/epoch/sequence/expiry | owner_wire explicit catalogue; NoInnerCanCounterSourceOrCrcIsRegenerated·BMS unknown/zero·real Leaf Actual | CAN/DBC/P05 불변; byte/uint64/binary64 보존; 지연 도착이 원래 expiry로 거부 | PASS component; 전체 DDS Actual 왕복은 M5 |
| clock/source-age/skew/rejoin | RunLeaseGate·mapped_time; RemoteClock/PeerFixture | common kernel monotonic profile 고정; 불확실성 산술 경계 검사; 다른 clock runtime 거부 | Host 계약 PASS; Target sync 후속, Host M5 자체 차단 아님 |
| TBD-05/15 API/QoS/queue/프로세스 | optional DDS/Zenoh6조건×3회, netns/veth/실제 tc/실제 thread·load | v1 30 PASS/6 FAIL 보존, 관측 보완 v2 별도36/36 PASS. QoS만으로 로컬 SPSC/atomic 의미를 재현할 수 없음; 첫 adapter는 bounded lane/실패 latch·full handshake 필요 | 후보 실험과 실제 배포 구분; 세부 결과 공유 근거 참조 |
| 새 workload M3 감시/타이밍 수용 | 기존48회 프로토콜을 `97afb35`에 새 실행 | **42 PASS/6 FAIL**, 설정·부하·grid·사전 할당 control48/48. OTHER loaded normal6 FAIL; FIFO24/24·intentional fault24/24 PASS. `1989477`41/7·FIFO23/24와 이전 실패 보존 | **OPEN-M4-TIM-01 / 승인한 Host 범위의 미확정 예외**; 전체 timing 미충족, 원인·시한·분모 유지 |
| 고정 kernel 관측/수집 보완 | `d3e7f6d` OTHER1+FIFO10 OFF/ON,22 workload | 11쌍 VALID; OTHER191/186 miss·2 FAIL, FIFO20 PASS·주입 전 miss0·예정된 보호 확인. 버퍼/RT 한도/설정/정리 실제 검증 | 수집 보완 확인; 과거 FIFO 원인 OPEN, 별도 진단이며 timing 수용 대체 아님 |
| 변경 동시성 sanitizer | `97afb35` TSan 경계108+wall9; 동일 source의 full trace native20+TSan20 | 108/108·9/9 및40/40 PASS, 경합 경고0. `d7115ff`8/9의 CommandDelivery 실패 원인 미확정 | **OPEN-M4-TSAN-01 / 승인한 Host 범위의 미확정 예외**; 전체973 TSan NOT RUN, 논리 수정/새 PASS로 원인 확정하지 않음 |
| 진단 수집·실패 종료 | check_m4_delivery_trace.py; Python runner 실제 child-process 시험8개 | 전체 예정 결과 저장 후 FAIL/timeout/누락/TSan 경고에 exit1, 전부 PASS는 exit0. 수정 전1 PASS/5 FAIL/2 ERROR→8 PASS; 전체 Python71 PASS | PASS; mock은 실행 성능 검증이 아님 |
| Middleware 동시성 검증 | 기존 DDS4 FAIL/helper9회·Zenoh matched8회 보존 + 실제 Writer 수명12회·wrapper4회 | Writer normal3/ASan3 PASS·TSan3 FAIL, ASan UAF control3 검출; 초기 harness12 setup 실패 별도 보존. wrapper ASan2 PASS/TSan2 FAIL. 실제 awake-vtime→GC 경로의 좁은 계측 공백 근거; bucket/proxy/WHC 안전성 OPEN. Zenoh partial4 FAIL/full4 PASS 이력 유지 | **BLOCK M5 CONTROL: OPEN-M4-MWTSAN-01**; wrapper 종료 결함 확인 안 됨; SDK algorithm/pin 변경·suppression 없음 |
| Middleware runner 실패 종료 | run_probe.py::checked_result/run_trial/main; MiddlewareProbeExitTest 8개 | 수정 전2 PASS/5 FAIL/1 ERROR→8 PASS; 전체 Python120/120. FAIL/경고/timeout/누락을 보존하고 nonzero, 실제 TSan wrapper도 exit1. 기존36 결과 offline 재검사36 PASS는 새 workload 실행 아님 | 도구 결함 수정 PASS; SDK 경고는 FAIL 유지 |
| 기존 M3 예외 | OPEN-M3-01/02·ADR-0042/43 | 원본 OTHER sanitizer2 FAIL·과거 원인 미확정 유지; kernel 접근은 사용자 고정 sudo 수집으로 확보 | 전체 M3 수용 PENDING; 새 성공으로 닫지 않음 |

최신 commit/환경/명령·수정 전후·원본·CSV/그래프는 [settlement evidence](../test-plan/evidence/m4_settlement/README.md),
이전966개·41/7 timing은 [계약 검토 evidence](../test-plan/evidence/m4_contract_review/README.md),
원본948개와 이전 실패는 [이전 evidence](../test-plan/evidence/m4_followup/README.md)에 묶는다.
기능 PASS, 정상 timing FAIL, TSan race warning 부재, 학습자 이해 확인은 서로 다른 판정이다.

<a id="m4-남은-차단과-필요한-결정"></a>

### 남은 차단과 필요한 결정

1. **실행 타이밍:** 새 `97afb35`는42/48 PASS이고 FIFO24/24다. OTHER loaded normal6개는 원래4ms 완료 기회를 놓쳐 실패했다. 각 최초 누락·deadline·검출·override·직전 body/CPU/다음 wake는 [failures.csv](../test-plan/evidence/m4_settlement/timing48/failures.csv)에 있다. 독립 보호 성공을 정상 timing PASS로 바꾸지 않는다. 이전 `1989477`의 예정1.2s 주입 전 Front/Rear slot281(release662ms/deadline666ms) 누락과666.004077ms 검출·666.009677ms override는 미해결 이력이다. 이번 미재현이 원인을 증명하지 않는다. 사용자 compact-v2 kernel capture 중185513쌍은 OFF243/ON159 miss지만 추적은 유실 없이 VALID다. 최초 조향 timer 초과3.714µs·CPU 배정대기2.856ms·body1.125µs, 최신-slot 선택으로2ms 기회가 누락되고4ms deadline 뒤65.184µs 검출·4.895µs 뒤 physical override를 확인했다. 이 OTHER 구간의 CPU contention 위치를 확인했으며 FIFO의 원인 증명은 아니다. [전체 원본/시간축](../test-plan/evidence/m4_kernel_valid/README.md)을 따른다. 앞선183050쌍은 OFF176/ON311 miss, CPU1 event256668개 유실로 INVALID 이력이다. syscall pretty-printer와 relative realtime clock 처리 결함을 수정해762977 event 전부 파싱했어도9076 chain은 UNTRUSTED로 유지한다. 두 시도의 instance 제거/global 불변을 확인했고, 앞선183033 export EBADF는 원인 OPEN이다. [수집기 compact-v2](m4-test-protocols.md#m4_kernel_capture)는 필수 event 유지·optional 감소·CPU1 buffer32MiB를 적용했으며95개 Python 검사를 통과했다. 후속185446/185458 두 쌍의 EBADF stack은 종료 trace_marker 쓰기 실패를 가리킨다. Kernel ring reserve 실패/CPU2 포화가 후보이나 실패 통계가 없어 확정하지 않는다. `eecc1d7`의 실패 후 raw/stat 보존·collector CPU2MiB 배분은97개 Python 검사 통과, 당시 새 실제 tracefs 검증은 NOT RUN이었다. 이후212418에서 두 marker·정리 성공과 사용자20/20 복원을 실제 확인했으나 CPU9 유실로 INVALID라서 FIFO는 미실행이다. Background buffer 보완 후213425 고정11쌍은 모두 유효하고 FIFO20회 주입 전 누락은 없었으며 예정된 보호가 PASS다. 해당20회 미재현을 과거 FIFO 원인 해결로 간주하지 않는다. [원본/재분석](../test-plan/evidence/m4_kernel_capture_followup/README.md)을 보존하며 OS 원인으로 단정하지 않는다.
2. **TSan native 정상 기능 실패:** `97afb35` full trace40/40 PASS에서 Command enqueue→result 최대 normal0.442994ms/TSan0.446838ms를 관측했다. 이전 `d7115ff` 사건은 여전히 미재현·원인 미확정이다. 논리 pending 충돌 결함은 ADR-0059로 수정했고, Rear19.8ms는1025.4ms exclusive deadline에서 보호한다. 양 Zone12ms는 기존 Rear 적용 명령의1011.000001ms expiry가 먼저 보호하는 결과를 유지한다. 다음 native 실패 시 원래 source/deadline·enqueue·RX/dispatch·Leaf 처리/출력 발행·결과 도착의 최초 실패 identity를 대조해야 한다. TSan 부담이나 이번 코드 결함이 과거 원인이라고 확정하지 않는다. Timeout 증가는 없다.
3. **Middleware SDK 검증:** [기존 근거](../test-plan/evidence/m4_sdk_followup/README.md)의 DDS 공식 TSan4회29경고를 publication bucket3·GC bucket7·Writer/WHC4·remote object15로 묶었다. 반복 경고 수를 결함 수로 세지 않는다. [실제 Writer 시험](../test-plan/evidence/m4_dds_lifetime/README.md)은 독립 deleter·awake reader·allocator hook으로 마지막 접근→quiescence→실제 mutex/free를 연결했다. Normal3/ASan3 PASS와 고의 UAF3 검출, TSan3 FAIL/각2경고는 해당 경로의 invisible vtime handoff를 뒷받침한다. bucket array·proxy/lease publication·receive AckNack/WHC의 수명은 아직 독립 검증되지 않았다. wrapper ASan 정상/overflow2 PASS, TSan2 FAIL이며 wrapper 소유권·종료 순서 결함은 확인되지 않았다. 초기 harness12 setup 실패를 SDK 결함으로 세지 않고 보존했다. SDK11.0.1 유지; upstream PR2162는 closed/unmerged라 적용하지 않았다. Suppression·SDK atomic 일괄 교체는 없다. 이전 Zenoh matched partial4 FAIL/full4 PASS와 도구 확보 근거는 재사용하며 새 빌드 반복으로 분모를 늘리지 않았다.
4. **수용 범위 판단:** 기존 전체 종료는 **NO-GO**다. 다만 production source/6개 바이너리 동일성, 기존 matched48회 중 FIFO24/24·최신 별도 무부하 고장20회·보호 시간축을 근거로 [Host native IO/FIFO 한정 수용안](#m4-host)을 **조건부 권고**한다. A는 비선택 대안으로 보존한다. B는 명시된 FIFO profile만 Host component 수용하고 OTHER loaded 실패와 과거 FIFO/native 사건은 OPEN 예외로 보존하며, DDS 전체 qualification을 M5 transport gate로 이관하는 변경안이다. B는 사용자 승인에 따라 Host component 한정 수용으로 적용했다. 실제 DDS 정규 제어 adapter enable은 그 gate 통과 뒤다. 한정 수용은 M3 전체·Target/system·학습자 종료나 과거 원인의 해결을 뜻하지 않는다. 재발 영향·검증한 보호·필요 기록과 이관 근거는 검토안에 구체화했다.

Host PC + Jetson 한 대 내부 여러 vECU 배치를 유지한다. Jetson 일반 커널/PREEMPT_RT 동일 workload 비교는
Target 성능 검증 PLANNED / NOT RUN이다. 이번 커널 교체·MCU 이식·종료 조건 변경은 없다.

<a id="m4-m5-첫-구현-단위"></a>

### M5 첫 구현 단위

이번 후속에서는 DDS 실제 수명 진단과 middleware runner 수정·Host 수용 검토까지 수행했고
**M5 Central↔Zone 제어 adapter는 미착수**다. M4 전체 종료 선행 조건은 충족되지 않았다.
승인한 B안에 따라 정상 제어 gate를 닫은 독립 Central↔Front DDS process에서
생성·통신·종료·재시작과 bucket/proxy/WHC 수명을 먼저 검증한다. SDK gate 통과 전 정규 제어는 허용하지 않는다. 조건을 모두 충족하면 추가 승인 없이 adapter를 진행한다.
그 뒤 기존 request→arm→normal command→원천 Actual/result adapter를 구현한다.
공통 clock/netns profile과 원래 source/parent/expiry, 방향별 loss/delay·old message/late ACK 거부·
새 durable Epoch/전체 INIT·readiness·arm·독립 보호를 검증한다.
Front 먼저여도 Central–Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임을 유지한다.
정확한 첫 단위·합격 기준·이관 전후는 [수용 검토안](#m4-host)에 둔다.

<a id="m4-승인-후-m5-gate-실제-판정--2026-10-21"></a>

### 승인 후 M5 gate 실제 판정 — 2026-10-21

[새 근거](../test-plan/evidence/m5_dds_qualification/README.md):42회23 PASS/19 FAIL,
GDB1회와 의도한 timeout이 재현되지 않아 post-check가 실패한 추가1회는 별도 보존한다.
첫5회 build/setup 실패는 runtime NOT RUN이다. SDK pin/알고리즘·제품 source는 변경하지 않았다.
실제 bucket/WHC·Proxy/lease/mutex 객체 관측을 확장했지만 전체 수명 안전성은 승인하지 않는다.

| M5 정규 제어 연결 조건 | 현재 판정 |
| --- | --- |
| 통신·종료·재시작 계약 통과 | **미충족**. 원래20ms normal 전달 실패·full reliable RHC close timeout 보존. 명시적 quiesce/drain→새43·old42 거부는 기능 통과하지만 이보다 좁은 조건 |
| 경고별 수정 또는 개별 계측 한계/수명 근거 | **미충족**. scoped bucket/WHC 근거와 실제 Proxy 생성/관측/free 연결 확보. remote lease·TKMAP·다른 callback interleaving은 OPEN |
| 실제 경로에 설명되지 않은 메모리 경고 부재 | **FAIL**. TSan 원본98 warning occurrences 보존; 다른 결함98개라는 뜻 아님 |
| 실제 SDK 버전·빌드·기능 연결 | 진단11.0.1/e54e991 세 library SHA·compile/run/source 기록 확인. 숨겨진 lookup은 동일 vendor source의 진단 object이며 실제 정규 adapter 구성은 NOT BUILT/NOT RUN |

따라서 **DDS control gate CLOSED / Central↔Front 정규 제어 adapter 미착수**다.
OPEN-M5-DDS-CLOSE-01(full RHC/awake recv/GC close wait), OPEN-M5-DDS-DELIVERY-01
(원래20ms 전달 미충족)과 기존 OPEN-M4-MWTSAN-01을 추적한다. B의 Host 한정 수용은 유지한다.
SDK 경고·원래 OTHER/FIFO/native 실패, 학습자/Target/system 상태는 변경하지 않는다.
추가 조사는 사용자가 보고한 Daybreak 인증 요구로 보류했다. 이미 완료한 로컬 실행 결과는 유지하며
인증 우회·추가 SDK 실험은 하지 않았다. 인증 문제 해소 뒤 미확정 경로와 지원되는 close 해결책을
검증하고 위 조건을 모두 충족할 때만 추가 승인 없이 adapter를 진행한다.

후속 사용자 요청에 따른 [Host 환경·운용 후보 점검](../test-plan/evidence/m5_dds_operating_profile/README.md)은
설정과 실제 적용값을 분리하고 진단의 writer/reader 삭제 상태·통신 준비·관측 공백을 보완했다.
5ms 단일 CPU의 초기20ms 실패 중 실제 heartbeat/retransmission 경로를 좁혔지만,
과거 모든 전달 실패의 원인 확정은 아니다. 후보20ms/CPU 분리에서는 포화 중 지속 송신을
포함한 close가 기능 통과했다. 과거 close timeout은 미재현/OPEN, 새 TSan64경고는 unresolved다.
따라서 위 연결 조건의 판정과 OPEN-M5-DDS-CLOSE-01/DELIVERY-01/MWTSAN-01을 유지한다.

<a id="m6"></a>

## M6 종료 검토 — Host quiet SIL / Python MIL

2026-10-22. 검토 기준 `6705388`(fetch 후 HEAD/origin/main 일치, clean).
**판정: M6 Host quiet SIL/MIL 범위 종료(CLOSED). 해당 범위의 필수 산출물 누락 없음.**
제어/모델/통신 수치나 실행 코드를 바꾸지 않고 기존 구현·원본 결과를 대조한 문서 검토다.
M4 전체 종료·Jetson·전체 시스템 수용, M7 CARLA/M8 C++ controller 완료를 뜻하지 않는다.
실제 SIL은 기존 문서의 Normal FIFO CPU/스레드 배치·quiet 부하·정상 사례8s 관측과 기존2.5s
shutdown tail 범위다. Python MIL의87logical s와 실제 SDK wall-time을 합치지 않는다.

<a id="m6-종료-검토표"></a>

### 종료 검토표

로드맵/개발 계획의 M6 산출물은 Simple Vehicle + EV plant의 actual/lifecycle/energy와
실행 가능한 종방향 제어 모델·MIL의 parameter/sample time/추종·제약 검증이다.
전체 차량 system TC나 M8 C++ 속도 폐루프를 M6 종료 조건으로 추가하지 않는다.

| M6 필수 산출물 / 관련 요구의 부분 범위 | 구현·기존 검증 근거 | 판정/한계 |
| --- | --- | --- |
| Simple Vehicle / SYS-CTRL-001·002, SYS-ARCH-002 | [모델 ICD](../interfaces/simple-vehicle-model.md), `simulation/vehicle/simple_vehicle.*`; 실제 torque/pressure/angle→전진 운동·bicycle pose, finite/time/identity 검증·원래 step 보존 | 완료. 평지/전진/no-slip 근사, OEM calibration·S01 전체 차량 추종 아님 |
| actual actuator·센서·네트워크 / SYS-ARCH-003, SYS-COM-002·004 | [3-vECU 근거](../test-plan/evidence/m5_someip_rear_adapter/README.md), [M6 첫 연결](../test-plan/evidence/m6_simple_vehicle/README.md); Central·Front·Rear 별도 process, 실제8 ACK/RunLease/arm, CAN/P05, 실제 wheel sensor→Drive→Rear→SOME/IP→Central validator | 완료. 시나리오 입력과 단일 persistent SIL physical process는 fixture. 공유 감시/물리 채널이 명령·권한을 우회하지 않음 |
| EV 전원·Battery/BMS·실제 회생/마찰 / SYS-EV-001–005, SYS-CTRL-008·009 | [에너지 근거](../test-plan/evidence/m6_vehicle_energy/README.md), `VehicleEvModel`/`EvPowerModel`; 정상 시동·stop/HV-off, 실제 charge-zero SOC0.96/BMS0W, owner-pause·Rear 새 Epoch 재가입 | 완료한 유한 Normal FIFO quiet 기능 범위. 전체 EV 고장 조합/차량 calibration 수용 아님 |
| 구간 에너지 수지 / SYS-CTRL-009, SYS-COM-004 | [에너지 ICD](../interfaces/vehicle-energy.md), 동일 motor work·candidate 동시 commit, independent ledger. Normal received DC194.015J, friction776.297J, max residual1.630e-8J<0.001J | 완료. chemical/kinetic/마찰/회로 손실의 단일 소유권, 원천 dependency 유지. SOC 증가를 회생 필요조건으로 삼지 않음 |
| 물리 보호 응답 / SYS-SAFE-004, SYS-COM-003 | [최종 응답 근거](../test-plan/evidence/m6_physical_response/README.md), [물리 계약](../interfaces/vehicle-energy.md#physical-response-contract). RX→검출<=100ms/로컬 선택<=4ms/최초 선택→실제 토크·1MPa 완료<=230ms | 완료. 실제 command-loss: RX→검출24.195ms, 선택→완료200.925ms. 기존 rate·권한·expiry·2ms/4ms·20ms envelope 유지. 다른 fault profile의 과거 판정은 그대로 |
| 종방향 실행 모델/MIL / SYS-CTRL-004·007, SYS-COM-004·SYS-SAFE-002의 모델 부분 | `models/longitudinal/model.py`, `mil.py`, [고정 MIL protocol](../test-plan/evidence/m6_simple_vehicle/protocol.md). Python binary64/PI20ms·plant2ms·speed50ms, 고정30/20/0km/h reference87s·1741sample | 완료. 각 plateau5s settling+10s/200sample; max error0.049180/0.046337/0.005251km/h, overspeed1.2233%. saturation/slew·stale/invalid/permission loss/새 INIT 계약 포함. 독립 Python 근사이며 실제 C++ 폐루프 아님 |
| 변경 경계/원본·재현성 | [최종 결과 JSON](../test-plan/evidence/m6_physical_response/results-summary.json): Normal/ASan 각1018/1018, 실제 TSan 경계35/35, Python/무build export 각54/54 | 기존 결과 대조 완료. 비계측35회는 TSan 수용에서 제외. SDK 전체 sanitizer 기능은 아래 OPEN이며 component PASS로 대체하지 않음 |

각 행은 관련 요구의 **M6 부분 증거**다. 원래32 requirement/29 system TC의 전체 Result는
[추적성](../test-plan/requirements-traceability.md)대로 NOT RUN이며, 이 종료 검토로 PASS로 바꾸지 않는다.
M6 물리 후속 실제 SDK3회는2PASS/1FAIL(관측기 수정 전 FAIL 보존), 수정 후 command-loss1/1과
영향 없는 nominal1/1이 수용 근거다. 에너지 단계5/9·개발 포함5/12와 첫 MIL FAIL도 유지한다.

<a id="m6-tbd의-m6-결정과-후속-경계"></a>

### TBD의 M6 결정과 후속 경계

| ID / owner | M6에서 결정·검증한 부분 | M7 이후 결정할 부분 / 선행 gate |
| --- | --- | --- |
| TBD-02 / plant·interface | [SimpleVehicleConfig](../../simulation/vehicle/simple_vehicle.hpp):1000kg/r0.3m/wheelbase2.7m, aggregate friction0.001Nm/Pa, rolling100N/drag0.4, actual/source/skew·wheel 기준. allocator와 일치 | M7 CARLA 좌표·geometry·steer 정규화/Drive·마찰 한 번씩 적용하는 mapping. 실제 차/OEM/tire/후진·경사 calibration은 범위 밖 |
| TBD-03 / vECU·plant | 현재 finite delay/rate/limit/초기값, normal stop standing-hold·60ms dwell. [M6 response JSON](../../profiles/m6_sil_response_v1.json)의 양·음수 torque→0/실제 brake floor 병렬230ms 산정·실측 | M7 외부 vehicle response와의 중복 dynamics 방지·mapping 오차/물리 응답 재검증. 다른 모델/Target/OEM 반응 budget을230ms로 일괄 결정하지 않음 |
| TBD-07 / simulation | 단일 persistent Host physical process가 vehicle·actuator·EV/Battery model/energy를 소유, model epoch와 ECU Epoch 분리. clock/solver·계측 scope 명시 | M7 CARLA/Ubuntu/Python/client/server/ScenarioRunner 호환 버전·GPU·map/route/seed,50ms synchronous tick·single writer·clock/source-age 경계 확정 후 접속 |
| TBD-12 / vehicle management·safety | 실제8-role INIT/Release ACK·RunLease·arm, actual 기반 power sequence/정상 stop/HV-off·새 Epoch 재가입. READY/권한/물리 완료를 구분 | M7 Host–Target clock/transport·외부 plant/LV/charging/interlock·차량 특성에 따른 threshold/반응 범위. 현재 SIL 범위 밖 기능의 차량 수용은 별도 |
| TBD-13 / model | Battery50kWh/400V·SOC 초기0.63/0.96 등 명시 SIL 설정, RC/접점/auxiliary·손실/효율·BMS limits, 실제 회생/charge-zero와 coherent energy 오차 예산. [vehicle-energy 계약](../interfaces/vehicle-energy.md) | M7 에너지/actuation mapping·정밀 battery/thermal/chemistry/OEM calibration. 모델 가정을 실차 특성으로 간주하지 않음 |
| TBD-16 / control·toolchain | [ADR-0063](design-decisions.md#adr-0063): Python 표준 라이브러리/binary64·독립 plant, sample/solver/reference/초기 상태/제약 고정, MIL 추종·fault/state 판정 완료 | M8 모델↔C++의 공통 입력 vector·tick별 출력/내부 상태 tolerance·동등성, 생성 도구를 채택할 때 license/재생성/qualification. 미선정 자동 생성 도구는 M6 누락 아님 |

이는 각 TBD의 **M6 부분 결정**이며 ID 전체를 CLOSED로 덮어쓰지 않는다.
Canonical register는 [roadmap](../roadmap.md#open-m0-decisions), 모델의 실행 계약은 위 ICD/설정이다.

<a id="m6-제한과-open"></a>

### 제한과 OPEN

- `OPEN-M6-ENERGY-01`: 현재 SIL 모델/응답 시한 불일치 범위 해소. 옛100ms FAIL과
  옛 로그의1MPa 미완료는 보존한다. 후속 성공으로 과거 FAIL을 바꾸지 않는다.
- `OPEN-M6-ENERGY-02`: 실제 instrumented SDK의 wall/송수신/SDK 오류·기능 미완료는 OPEN.
  메모리/UB/경합 진단0이 전체 기능 PASS는 아니다. 이번 범위 종료의 일괄 선행 조건으로 추가하지 않는다.
- M4 전체 NOT CLOSED, 역사적 OTHER/FIFO/native/물리 pause/DDS OPEN과 DDS 제어 gate CLOSED 유지.
  OTHER 부하 timing은 진단이며, 이번 M6 quiet 수용은 M5 부하 범위를 확장하지 않는다.
- Jetson/실제 IO/Host–Target Ethernet·전체 차량32req/29TC·M7/M8은 미검증.
  학습자 직접 설명/수용 기록은 기술적 범위 종료와 별도다.

<a id="m6-다음-한-단계--m7-최초-접속-계약과-환경-확인"></a>

### 다음 한 단계 — M7 최초 접속 계약과 환경 확인

첫 작업은 **CARLA 접속 전 호환 환경과 actual-only/synchronous bridge 계약 확정**이다.
M7 구현은 이번 작업에서 시작하지 않았다. 다음 작업에서 확인할 선행 조건은 다음과 같다.

1. 사용할 Host GPU/OS·CARLA server/client·Python·ScenarioRunner 호환 버전과 실행 환경을
   실제 자원/공식 호환 근거로 고정한다(TBD-07). 설치/권한·Target 가용성은 확인 결과로 구분한다.
2. 기존50ms 동기 tick/orchestrator와 Plant Adapter 단일 ego writer를 적용하고,
   원래 actual/identity/source/expiry가 보존되는 인터페이스·역방향 state/sensor를 정의한다.
   특히 CARLA20Hz state와 기존 Drive30ms source-age의 차이를 명시적으로 해결해야 한다.
   cached state restamp/직접 raw command fallback으로 연결하지 않는다.
3. M6 모델과 CARLA 중 각 inertia/actuator/energy 상태를 누가 한 번만 계산하는지,
   torque/압력/steer·좌표 mapping·clock/pause/reset·invalid containment를 고정한다.
   실제 Host–Jetson 배포는 BSP/ABI·NIC/clock/권한 확인 후 별도 검증하며 M6 결과로 대체하지 않는다.

M4/DDS/SDK OPEN 전체 해소나 새로운 극단·복합고장을 이 첫 작업의 선행 조건으로 만들지 않는다.

<a id="m6-저장소-정리검증-기록"></a>

### 저장소 정리·검증 기록

현재 상태는 [project_status](../project-status.md), 단계/TBD는 [roadmap](../roadmap.md),
이력/원본은 기존 evidence와 [품질 기록](../development-guide.md)로 역할을 나눴다.
중복 물리 응답 ICD를 vehicle-energy의 위 절로 통합하고 이전 링크를 갱신했다.
내용이 생긴14개 디렉터리의 불필요한 `.gitkeep`만 제거했다. 다른 빈 디렉터리 placeholder,
원본/실패/중복 cohort CSV·archive·재현 script·codec 초안·사용자 build/측정 자료는 보존했다.
실행 script/fixture는 빌드·시험·문서/재현 참조를 대조했으며 삭제 대상으로 입증된 것은 없었다.

문서 링크/앵커·요구사항/112개 component 추적성·M6 archive/재현 경로를 정적 검증한다.
실행 코드/모델 수치/전송 계약 변경이 없으므로 새 C++/SDK/48회 타이밍 시험은 수행하지 않는다.
최종 정적 검증(새 runtime 실행 아님):

- 마크다운199개(이전199개와 동일), 로컬 링크/앵커1888개: 깨짐0.
- component112개: 요구사항/구현/evidence 경로 누락0. 기존1018개 XML에105개 C++ 이름이 존재하고,
  나머지7개는 별도 DDS diagnostic/Python 연결로 분류했다.32개 requirement/29개 system TC와
  Result 표, component CSV·stable interface ID는 변경하지 않았다.
- M5 Rear 및 M6 model/energy/physical archive4개의 SHA 일치. 기존 최종 MIL1741sample/3plateau
  결과와 현재 model.py/mil.py source hash를 archive에서 대조했다. 기존 결과를 재실행 결과로 세지 않았다.
- 재현 명령8개 runner 옵션·CMake target·5개 Python 진입 경로를 정적으로 확인했다.
  실제 script/fixture·빌드·공통 로직 변경0, `.gitkeep` 제거 디렉터리14개 모두 다른 tracked 내용이
  존재하고 실행 경로에서 marker 참조0. YAML은 수용 상태 문자열2개만 변경, 실행 JSON/모델 수치 불변.
- `git diff --check` PASS. C++ 전체/SDK/MIL/48회 타이밍 신규 실행0회.

실패 원본·NOT RUN·OPEN을 삭제/승격하지 않았으며 무시된 build/사용자 측정 자료는 정리하지 않았다.
