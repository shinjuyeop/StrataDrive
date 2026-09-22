# M0 baseline summary and exit review

Baseline: **StrataDrive Reference Baseline v0.1** / 2026-09-22.
Status: **BASELINED**. 15개 exit 항목의 문서/계약 검토를 모두 통과했다.
이 문서는 M0 계약 검토 결과이며 runtime test result가 아니다.

## Decisions and rationale

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

## Exit criteria

PASS는 **M0 문서 계약의 충족**만 뜻한다. Runtime requirement VERIFIED나 TC PASS가 아니다.

| Check | 증거 | Review |
| --- | --- | --- |
| Reference ODD 정의 | [system requirements](requirements/system_requirements.md) | PASS |
| 정상 scenario 3개 정의 | [S01–S03](test-plan/scenario_baseline.md) 목적/input/expected/metric/판정/ID/milestone | PASS |
| fault scenario 최소 4개 정의 | [F01–F04](test-plan/scenario_baseline.md) trigger/monitor/state/local action/판정 | PASS |
| Vehicle/actuator command/actual 책임 분리 | [공통 ICD](icd/interface_overview.md), SYS-ARCH-002 | PASS |
| Central/Zone/vECU/Plant Adapter 경계 | [system architecture](architecture/system_architecture.md), single writer/우회 금지 | PASS |
| Logical timing/rate baseline | [timing](requirements/timing_requirements.md), [reference.yaml](../profiles/reference.yaml) | PASS |
| Timeout/freshness/clock/pause 개념 | [timing](requirements/timing_requirements.md), last-valid origin/invalid age 미갱신 | PASS |
| Top-level fault state | [fault architecture](architecture/fault_diagnostics_architecture.md), INIT recovery/local independence | PASS |
| Physical/logical communication boundary | [ICD](icd/interface_overview.md), [deployment](architecture/deployment_architecture.md) | PASS |
| Thor/Orin 독립 배포 원칙 | [ADR-0003](adr/ADR-0003-compute-tier-strategy.md) | PASS |
| Requirement→test→future result 추적 | [traceability](test-plan/traceability.md), 23 requirements / 16 TC / NOT RUN | PASS |
| 모든 unresolved TBD의 owner/milestone/rationale | [TBD-01–11 register](roadmap.md#open-m0-decisions), profile null mapping | PASS |
| M1 구현 시작에 충분한 계약 | [CAN ICD](icd/can_icd.md), six frame 의미/방향/validation/failure gate | PASS |
| M1+ runtime 구현 혼입 없음 | Git diff 및 placeholder/CMake inventory | PASS |
| ID/link/용어/결과 상태 일관성 | 아래 repository audit | PASS |

## Repository audit evidence

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

## Implemented versus planned

실제 파일로 존재하는 것은 Markdown 설계 계약, YAML design data, directory placeholder,
configure-only CMake다. YAML loader/schema validator/application target은 없다.
DBC/IDL/codec/vCAN/vECU/Zone/Central/CARLA/ROS 2·DDS/AI/deployment/차량 test는 PLANNED다.
TC의 Future Result는 모두 NOT RUN이며 Result ID와 benchmark 실측 파일은 없다.

Requirement registry에 새로 추가한 ID는 SYS-ARCH-002, SYS-ODD-001, SYS-COM-003/004,
SYS-CTRL-002/003/004/005/006/007, SYS-SAFE-002/003/004, SYS-PERF-002/003이다(15개).
기존 8개는 ID를 유지하며 v0.1 의미/판정/trace를 구체화했다.
Scenario ID는 S01/S02/S03/F01/F02/F03/F04(7개), 신규 Test ID는
TC-COM-003/004/005, TC-CTRL-002/003/004, TC-SAFE-002, TC-PERF-002(8개)다.

미결정 상세와 각 gate는 [roadmap](roadmap.md#open-m0-decisions)에 모았다.
M1의 첫 작업은 frame/DBC, integrity golden vectors, codec/rejection, vCAN application test,
traceability 결과 연결 순서다. M0 성공 기준은 문서량이 아니라 **M1 DBC/vCAN을 시작해도
architecture와 contract를 다시 뒤집지 않아도 되는 상태**다.

## Changed files

추가 2개:

- [m0_baseline.md](m0_baseline.md)
- [scenario_baseline.md](test-plan/scenario_baseline.md)

수정 25개:

- [README.md](../README.md), [roadmap.md](roadmap.md)
- [system_requirements.md](requirements/system_requirements.md), [timing_requirements.md](requirements/timing_requirements.md), [safety_requirements.md](requirements/safety_requirements.md)
- [system_architecture.md](architecture/system_architecture.md), [software_architecture.md](architecture/software_architecture.md), [deployment_architecture.md](architecture/deployment_architecture.md), [fault_diagnostics_architecture.md](architecture/fault_diagnostics_architecture.md)
- [interface_overview.md](icd/interface_overview.md), [can_icd.md](icd/can_icd.md), [ethernet_dds_icd.md](icd/ethernet_dds_icd.md)
- [verification_strategy.md](test-plan/verification_strategy.md), [traceability.md](test-plan/traceability.md)
- [ADR-0001-simulator-selection.md](adr/ADR-0001-simulator-selection.md), [ADR-0002-zonal-architecture.md](adr/ADR-0002-zonal-architecture.md), [ADR-0003-compute-tier-strategy.md](adr/ADR-0003-compute-tier-strategy.md), [ADR-0004-ai-control-boundary.md](adr/ADR-0004-ai-control-boundary.md)
- [profiles/README.md](../profiles/README.md), [reference.yaml](../profiles/reference.yaml), [thor_premium.yaml](../profiles/thor_premium.yaml), [orin_mainstream.yaml](../profiles/orin_mainstream.yaml)
- [learning/README.md](learning/README.md), [quality_policy.md](quality_policy.md), [models/README.md](../models/README.md)
