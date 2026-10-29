# 설계 결정 기록 · ADR-0001–0065

이 문서는 당시 결정과 검토를 보존한 기록이다. 현재 상태는 [프로젝트 상태](../project-status.md), 현재 계약은 [문서 안내](../README.md)를 따른다. 과거의 “다음 작업/미구현”은 현재 지시가 아니다.

- [ADR-0001 — Simulator selection](#adr-0001)
- [ADR-0002 — Central → Zone → Leaf architecture](#adr-0002)
- [ADR-0003 — Independent compute tiers](#adr-0003)
- [ADR-0004 — AI / control boundary](#adr-0004)
- [ADR-0005 — First C++ field codec experiment](#adr-0005)
- [ADR-0006 — Host Steering frame codec and DBC checker](#adr-0006)
- [ADR-0007 — Steering 통신 보호에 AUTOSAR E2E Profile 5 적용](#adr-0007)
- [ADR-0008: Steering의 로컬 application 수신부](#adr-0008)
- [ADR-0009: Steering codec와 Linux SocketCAN 연결](#adr-0009)
- [ADR-0010: Brake wire codec과 공통 actuator payload](#adr-0010)
- [ADR-0011: 회생제동을 포함한 Drive–Brake 설계](#adr-0011)
- [ADR-0012: Brake application 수신부와 공통 수신 상태](#adr-0012)
- [ADR-0013: 구동·회생 Drive wire와 독립 피드백 유효성](#adr-0013)
- [ADR-0014: 전기차 기능·상태·통신을 재현하는 SIL 범위](#adr-0014)
- [ADR-0015: Front/Rear 두 논리 Zone](#adr-0015)
- [ADR-0016: BMS 상태·Power·Drive constraint의 M1 wire 초안](#adr-0016)
- [ADR-0017: EV/BMS codec와 항목별 수신 유효성](#adr-0017)
- [ADR-0018: 영속 Epoch 발급과 수신 연속성 오류](#adr-0018)
- [ADR-0019: 첫 조향 응답 component 모델](#adr-0019)
- [ADR-0020: 첫 마찰제동 압력 응답 모델](#adr-0020)
- [ADR-0021: Central 조정 기능과 대등한 Front/Rear Zone](#adr-0021)
- [ADR-0022: Leaf vECU의 Classic 개발 체계와 SIL 모델 경계](#adr-0022)
- [ADR-0023: 첫 Drive torque 응답과 ECU·물리 모델 분리](#adr-0023)
- [ADR-0024: 첫 Battery 에너지·전기·온도·관측 모델](#adr-0024)
- [ADR-0025: 첫 BMS 충방전 한계·보호 판단](#adr-0025)
- [ADR-0026: 첫 Power lifecycle과 DC-link/contactor 모델](#adr-0026)
- [ADR-0027: 필수 EV Drive gate와 회생 가용량](#adr-0027)
- [ADR-0028: 실제 Drive 토크에서 배터리 에너지까지](#adr-0028)
- [ADR-0029: Battery와 실제 DC-link 회로의 에너지 연결](#adr-0029)
- [ADR-0030: 조향 센서 경계와 local response monitor](#adr-0030)
- [ADR-0031: 브레이크 압력 센서와 local response monitor](#adr-0031)
- [ADR-0032: ECU 판단과 SIL 실행 연결의 분리](#adr-0032)
- [ADR-0033: 첫 wall-time ECU 실행과 독립 deadline 감시](#adr-0033)
- [ADR-0034: 여러 Leaf 작업의 주기 실행과 CAN 수신 상실 감시](#adr-0034)
- [ADR-0035: 고정 부하와 CPU 배치를 구분하는 Host 실험](#adr-0035)
- [ADR-0036: 비동기 Drive Actual의 취득 시각 보존과 CAN 수신](#adr-0036)
- [ADR-0037: RX·감시·물리 실행 owner의 CPU 배치 비교](#adr-0037)
- [ADR-0038: 감시·물리 owner의 전체 cycle 계측과 RX 시간 대조](#adr-0038)
- [ADR-0039: 감시·물리 작업의 완료 시한과 교차 감시](#adr-0039)
- [ADR-0040: Steering RTOS 파일럿과 Host 실행 대기 관측](#adr-0040)
- [ADR-0041: ARM64 RTOS 교차 빌드와 Host RT 사전 점검](#adr-0041)
- [ADR-0042: Native M3 owner별 FIFO 설정과 비교](#adr-0042)
- [ADR-0043: Hosted RTOS의 절대 주기 타이머와 명시적 Host 배치](#adr-0043)
- [ADR-0044: Central 전원 요청·정상 허가 상태 owner](#adr-0044)
- [ADR-0045: 첫 Central 배분과 회생·마찰 전환](#adr-0045)
- [ADR-0046: Front/Rear normal 명령의 독립 수용 경계](#adr-0046)
- [ADR-0047: Zone CAN 전달 직전 검증과 독립 보호 handoff](#adr-0047)
- [ADR-0048: Rear 전원 전달과 명시적 non-driving startup](#adr-0048)
- [ADR-0049: Front non-driving 시작과 두 Leaf/gateway의 arm](#adr-0049)
- [ADR-0050: 정상 정지·terminal handoff·HV 종료](#adr-0050)
- [ADR-0051: 실제 Zone feedback health와 독립 status ingress](#adr-0051)
- [ADR-0052: 제어 기능의 MBD 개발·검증 경로](#adr-0052)
- [ADR-0053: Central coordinator의 단일 실행 순서와 same-host binding](#adr-0053)
- [ADR-0054: trusted 세션 준비·INIT·실행 허용과 owner별 mailbox](#adr-0054)
- [ADR-0055: M4 정상 운전의 비동기 owner 연결과 재현 근거](#adr-0055)
- [ADR-0056: M4 공통 고장 주입과 독립 실행 감시](#adr-0056)
- [ADR-0057: M4 공통 release 위상과 owner 모듈 분리](#adr-0057)
- [ADR-0058: 원격 owner authority와 Host 통신 후보 경계](#adr-0058)
- [ADR-0059 — Pending command와 allocation release의 분리](#adr-0059)
- [ADR-0060: Central–Front SOME/IP Host component pilot](#adr-0060)
- [ADR-0061: Host Central–Front SOME/IP owner adapter](#adr-0061)
- [ADR-0062: Host Central–Front/Rear SOME/IP owner separation](#adr-0062)
- [ADR-0063: M6 actual 기반 Simple Vehicle와 첫 종방향 MIL](#adr-0063)
- [ADR-0064: 차량 운동과 EV의 구간 에너지 결합](#adr-0064)

- [ADR-0065: M7 시뮬레이션 기능 통합과 실시간 수용 분리](#adr-0065)

<a id="adr-0001"></a>

## ADR-0001 — Simulator selection

<a id="adr-0001-status"></a>

### Status

Accepted for **StrataDrive Reference Baseline v0.1** (2026-09-22).
설계 경계의 수용이며 runtime 구현/호환성/성능 검증은 **PLANNED / NOT RUN**이다.

<a id="adr-0001-context"></a>

### Context

Closed-loop 자율주행을 학습하려면 접근하기 쉬운 vehicle plant, sensor, road,
traffic과 scenario 실행 절차가 필요하다. Simulator 통합 전에도 simple plant로
architecture를 시험할 수 있어야 한다.

<a id="adr-0001-decision"></a>

### Decision

x86 Ubuntu Host에서 **CARLA 0.9.16 계열을 초기 simulator 후보로 사용한다**.
정확한 build와 호환되는 Host/Python/client/ScenarioRunner 버전은 TBD다.
Scenario 실행을 위해 OpenDRIVE road와 ScenarioRunner / OpenSCENARIO를 검토한다.
필요한 scenario 기능과 버전 지원 여부는 M7 전에 확인해야 한다.

공식 [0.9.16 release 발표](https://carla.org/2025/09/16/release-0.9.16/)에서 해당 release
계열을 확인할 수 있다. [ScenarioRunner 문서](https://scenario-runner.readthedocs.io/)는
향후 호환성 검토 자료이며, scenario가 이미 실행된다는 증거는 아니다.

<a id="adr-0001-alternatives-considered"></a>

### Alternatives Considered

- Simple Vehicle Plant만 사용: M6 계약 검증에는 유용하지만, 계획한 풍부한 sensor/traffic
  환경을 다루기에는 부족하다.
- 다른 CARLA release 계열: 호환성이나 재현성 때문에 필요하면 다시 검토한다.
- 상용 CarMaker, CANoe, dSPACE 도구: 학생/개인 학습 프로젝트와는 범위, 접근성,
  비용, 통합 제약이 다르다.

<a id="adr-0001-consequences"></a>

### Consequences

CARLA는 자율주행 중심의 sensor/traffic/scenario 생태계를 갖춰 개인 프로젝트의
출발점으로 활용하기 좋다. 다만 **CarMaker/CANoe/dSPACE와 동등하다고 주장하지 않으며**,
simulator 시험은 HIL이나 실차 검증이 아니다. Plant Adapter 경계로 CARLA API와
control을 분리해야 한다. Mapping 충실도, 동기화, 필요한 scenario 기능의 지원 여부는
미결정이다. [system architecture](../architecture/README.md)를 참조한다.

미결정 build/호환성/route는 TBD-07(M7), plant mapping은 TBD-02/07(M6/M7)이다.
M0에서는 CARLA를 설치하거나 release 호환성을 검증하지 않았다.

미결정 항목의 owner/rationale은 [TBD register](../roadmap.md#open-m0-decisions)를 따른다.

<a id="adr-0001-2026-10-23-m7-0-후속-조사"></a>

### 2026-10-23 M7-0 후속 조사

[Host 실측·공식 호환성 조사](../carla-guide.md)에 따라0.9.16 패키지,
Client0.9.16/Python3.10, ScenarioRunner v0.9.16을 우선 후보로 유지한다. UE5의 영상 fidelity
이점은 있으나 이번 접속/계약 단계의 전환 필요성은 없어 보류한다. 설치·실행 검증은 NOT RUN.
[Plant Adapter 초안](../interfaces/carla-plant-adapter.md)은 기존 actual-only 경계를 유지하며
50ms state/Drive30ms·substep actuation·calibration이 해결되기 전 정상 주행을 차단한다.
M7-1 비주행 연결/센서/negative 시험과 실제 주행 gate를 구분한다. M0의 당시 수용은 변경하지 않는다.

<a id="adr-0001-2026-10-23-m7-1d-시간-계약-개정"></a>

### 2026-10-23 M7-1d 시간 계약 개정

사용자 승인으로 world/Vehicle State는10ms, RGB/GT는50ms로 분리한다.
50ms world가 Drive30ms freshness를 필연적으로 위반하므로 sampling 주기를 개정했다.
Controller20ms·Zone/vECU10ms·30ms freshness·단일 tick/actuation owner는 유지한다.
[시간 계약](../requirements/timing-requirements.md)과 [ICD](../interfaces/carla-plant-adapter.md)가
현재 의미 계약이다. 기존 M6 profile과 M7-1b/c 결과는 당시 조건으로 보존한다.
10ms 설정은 wall100Hz 보장이나 wheel feedback/정상 주행 승인 증거가 아니다.

<a id="adr-0002"></a>

## ADR-0002 — Central → Zone → Leaf architecture

현재 배치: [ADR-0021](#adr-0021). Zone의 차량 전체 allocation 배치는 2026-10-14 ADR-0021로 Central 별도 component로 대체했다. Central–Zone–Leaf 및 actual-only plant 원칙과 당시 M0 결과는 유지한다.

<a id="adr-0002-status"></a>

### Status

Accepted for **StrataDrive Reference Baseline v0.1** (2026-09-22).
설계 경계의 수용이며 runtime 구현/호환성/성능 검증은 **PLANNED / NOT RUN**이다.

<a id="adr-0002-context"></a>

### Context

Classical Controller가 simulator를 직접 구동하는 loop로는 Zone Controller의 allocation,
actuator 통신, local ECU의 fault response를 살펴보기 어렵다. 하나의 Linux Target에서
component를 실행하더라도 현대 차량의 E/E 경계를 학습하는 것이 목적이다.

<a id="adr-0002-decision"></a>

### Decision

Central Vehicle Compute → Virtual Ethernet / DDS → Virtual Zone Controller
→ SocketCAN / vCAN → Steering / Brake / Drive vECU 구조를 채택한다.
Docker network 또는 Linux namespace + veth pair로 Central Vehicle Compute와
Zone Controller를 논리적으로 별도인 Ethernet node로 분리한다. 구체적 선택은 TBD다.
Host–Target은 실제 Ethernet을 사용한다.

vECU의 실제 actuator response는 Zone Controller/Target feedback bridge와 Host의
Plant Adapter를 거친 뒤 차량 동작에 반영해야 한다. Periodic task, queue, 동기화,
state, watchdog, integrity, actuator dynamics를 vECU 계약으로 정의한다.
이 항목들은 M0에서 구현하지 않는다.

<a id="adr-0002-alternatives-considered"></a>

### Alternatives Considered

- CARLA를 호출하는 monolithic controller: 설정은 줄지만 해당 경계를 시험하지 못한다.
- DDS로 actuator model에 직접 연결: gateway 작업은 줄지만 CAN/Zone Controller 계약이 빠진다.
- 지금부터 물리적으로 분산된 ECU 사용: hardware를 더 직접 다룰 수 있지만 M0 범위를 벗어난다.

<a id="adr-0002-consequences"></a>

### Consequences

책임, timeout, 변환, fault 경계가 명확해지는 대신 scheduling/통신/설정의 복잡도가
늘어난다. Linux Host를 공유하면 물리적 fault isolation은 확보되지 않는다.
vCAN은 application frame 시험용이며 CAN FD의 전기적 동작이나 실제 arbitration timing을
검증하지 않는다. ECU timing 충실도, Zone Controller의 process 배치와 allocation 규칙은
TBD다. [software 계약](../architecture/README.md)을 참조한다.

<a id="adr-0002-m0-contract-refinement-and-rationale"></a>

### M0 contract refinement and rationale

Vehicle-level command(target speed 및 acceleration/curvature/braking demand), Zone의 actuator command,
vECU actual actuator feedback을 서로 다른 의미/방향으로 고정한다. Requested demand를
actual state로 대체하면 delay/saturation/fault를 검증할 수 없기 때문이다.
Central longitudinal PID는 vehicle acceleration demand를 출력하고 Zone이 이를 torque/brake로
배분한다. Target speed만 전달해 longitudinal control 책임이 Zone으로 옮겨가는 모호함을 피한다.
Planner/Controller/Zone의 CARLA direct actuation과 feedback loss의 raw fallback을 금지한다.
Plant Adapter만 ego actuation writer이며 Host orchestrator는 tick만 소유한다.

Critical actual loss에서는 synchronous simulation의 다음 apply/tick을 gate한다.
이는 가상의 emergency actual을 만들지 않고 증거 결손을 드러내기 위한 선택이다.
물리적 안전 정지의 대체 증거로 보지 않는다. Critical loss는 FAIL_SAFE, 복구는 explicit
reinitialize→INIT이며 Central diagnostics 없이 Zone/vECU가 local protection을 수행한다.

Semantic units는 [ICD](../interfaces/README.md), state/action은
[safety](../requirements/safety-requirements.md), logical rate와 100 ms 검출 기준은
[timing](../requirements/timing-requirements.md)에 정의했다. 20/50/100 Hz는 센서보다 빠른
control/actuator task와 freshness를 학습하기 위한 출발점이며 생산 요구나 실측값이 아니다.
Wire encoding/CRC는 TBD-01(M1), dynamics는 TBD-03(M2), schedule은 TBD-04(M3),
isolation/middleware는 TBD-05(M4/M5), allocation은 TBD-06(M4)로 보류한다.

미결정 항목의 owner/rationale은 [TBD register](../roadmap.md#open-m0-decisions)를 따른다.

<a id="adr-0002-2026-10-13-후속-topology-확장"></a>

### 2026-10-13 후속 topology 확장

[ADR-0015 / ZON-01](#adr-0015)로 최종 Reference를 Front/Rear 두 논리
Zone으로 확장했다. Front의 차량 전체 관리·배분과 상위 feedback 집계는 단일 owner다.
Rear는 Drive/BMS gateway·local validation을 맡는다. 위 M0 계층/command/actual 계약과
역사적 검토 결과는 유지하며 단일 Zone은 component 검증 단계로 사용한다.
Peer protocol과 두 Zone runtime/TC-ZON 검증은 PLANNED / NOT RUN이다.

<a id="adr-0003"></a>

## ADR-0003 — Independent compute tiers

<a id="adr-0003-status"></a>

### Status

Accepted for **StrataDrive Reference Baseline v0.1** (2026-09-22).
설계 경계의 수용이며 runtime 구현/호환성/성능 검증은 **PLANNED / NOT RUN**이다.

<a id="adr-0003-context"></a>

### Context

목표는 주어진 compute budget에서 어떤 차량 feature 구성이 요구사항을 만족하는지
이해하는 것이다. 두 보드로 분산 차량을 구성하면 partitioning, 추가 통신, 보드 간
fault 동작이 함께 개입해 compute budget의 영향을 구분하기 어려워진다.

<a id="adr-0003-decision"></a>

### Decision

동일한 Vehicle SW Architecture의 **Premium Target은 Jetson AGX Thor**,
**Mainstream Target은 Jetson Orin NX**로 정의한다. 한 번에 한 보드에 독립 배포하며,
두 보드를 연결해 하나의 차량을 구성하지 않는다.

먼저 동일한 Reference Config, scenario, 요구사항을 고정하고 두 보드에서 각각 실행한다.
이후 tier별 변경을 측정하고 탐색하며 reference 결과와 최적화 결과를 구분해 보관한다.
AI latency, camera-to-trajectory latency, FPS, CPU/GPU 사용률, RAM, power, temperature,
control jitter, deadline miss를 기록한다.

<a id="adr-0003-alternatives-considered"></a>

### Alternatives Considered

- Thor + Orin을 연결된 compute node로 사용: 다른 architecture 질문을 다루게 된다.
- Target 하나만 사용: 단순하지만 요청한 tier별 trade-off를 탐색할 수 없다.
- Reference 측정 전에 각 보드 최적화: 나중에는 유용하지만 workload 차이를 해석할
  공통 출발점을 잃는다.

<a id="adr-0003-consequences"></a>

### Consequences

Reference model/input/feature와 requirement acceptance는 공통으로 유지하고, 보드별
software 호환성, power mode, cooling 조건은 공개해야 한다. 동일한 binary나 TensorRT
engine을 두 보드에서 그대로 사용할 수 있다고 가정하지 않는다. Premium feature 확장과
Mainstream의 FP16→INT8/model/input/rate/feature 축소는 정확도와 closed-loop 재검증이
필요하다. 보드 성능 순위를 주장하지 않는다. Reference workload, budget, 정확한 보드
variant는 TBD다. [배포 protocol](../architecture/README.md)을 참조한다.

보드 stack/workload/budget TBD의 owner는 project owner이며 TBD-09(M5/M10/M12)에
귀속된다. M0 rate/ODD/acceptance를 board별로 조용히 완화하지 않는다.

미결정 항목의 owner/rationale은 [TBD register](../roadmap.md#open-m0-decisions)를 따른다.

<a id="adr-0004"></a>

## ADR-0004 — AI / control boundary

<a id="adr-0004-status"></a>

### Status

Accepted for **StrataDrive Reference Baseline v0.1** (2026-09-22).
설계 경계의 수용이며 runtime 구현/호환성/성능 검증은 **PLANNED / NOT RUN**이다.

<a id="adr-0004-context"></a>

### Context

Learned Temporal Planner는 늦거나 유효하지 않거나 실행 불가능한 출력을 만들 수 있다.
AI 도입 전에 fault 동작을 관측할 수 있어야 하며 classical baseline이 필요하다.
Interface 경계를 유지하면 이러한 영향을 살펴보기 쉽지만 안전성이 증명되지는 않는다.

<a id="adr-0004-decision"></a>

### Decision

먼저 Zone Controller/vECU를 거치는 classical route/waypoint 주행을 구현한다.
Lateral control에는 Pure Pursuit 또는 Stanley, longitudinal control에는 Longitudinal PID를
사용한다. 그다음 pretrained perception을 추가한다. 이후 0.5–1초의 state/object history를
사용하는 GRU 또는 작은 Temporal Transformer를 평가한다.

AI는 Future Waypoints / Suggested Trajectory, Target Speed, Risk Score를 출력한다.
Actuator command를 직접 생성하지 않는다. 출력은 Safety Supervisor → Classical Controller
→ Vehicle Command 경로를 거친다. AI timeout이나 유효하지 않은 출력에 대비해
Classical Planner fallback을 유지한다. Fallback 입력도 사용할 수 없으면 유효한 fallback으로
간주하지 않고 정의된 degraded/fail-safe 정책을 따른다.

<a id="adr-0004-alternatives-considered"></a>

### Alternatives Considered

- End-to-end learned actuator control: 명시적인 경계는 줄지만 계약, timing, fault를
  구분해 살펴보기 어려워진다.
- Classical autonomy만 사용: 첫 단계에 적합하지만 이후 Physical AI 학습이 빠진다.
- Safety validator 없이 learned 출력 사용: 검증과 복구 경계가 부족하다.

<a id="adr-0004-consequences"></a>

### Consequences

검증, mode 전환, trajectory 연속성, fallback timing을 명시적으로 시험해야 한다.
Classical Controller나 deterministic 규칙만으로 hard real-time 보장이나 안전 인증이
성립하지 않는다. Risk 의미/calibration, 검증 한계값, training/evaluation 분리,
recovery threshold는 TBD다. [software architecture](../architecture/README.md)와
[안전 계약](../requirements/safety-requirements.md)을 참조한다.

Algorithm/tuning은 TBD-11(M8), AI model/feature는 TBD-09(M10), history/risk/fallback은
TBD-10(M10/M11)이다. v0.1 AI 계약 수용은 AI 구현/모델 선택의 완료를 뜻하지 않는다.

미결정 항목의 owner/rationale은 [TBD register](../roadmap.md#open-m0-decisions)를 따른다.

<a id="adr-0005"></a>

## ADR-0005 — First C++ field codec experiment

<a id="adr-0005-status"></a>

### Status

2026-09-28 **Implemented for Host experiment / 학습자 review PENDING**.
M1의 작은 구현 단위이며 전체 wire 계약 채택이나 milestone acceptance가 아니다.

<a id="adr-0005-context"></a>

### Context

vCAN fixture 송수신을 확인했으므로 실제 물리량의 byte 표현을 구현하며 학습한다.
Steering Command/Actual의 의미는 정해졌지만 six-frame wire layout과 actuator calibration은
미정이다. 한 field를 먼저 검토하면 encoding의 부호·단위·반올림 오류를 작게 시험할 수 있다.

<a id="adr-0005-decision"></a>

### Decision

[Steering angle field 초안](../interfaces/steering-angle-encoding.md)을 먼저 명시하고,
해당 초안의 독립 golden vectors → codec → 단위 시험 → CLI 실행 순서로 구현한다.
이 초안은 향후 전체 DBC 검토에서 바뀔 수 있다. Receiver/transport에는 아직 연결하지 않는다.
Command와 Actual이 같은 표현을 쓰더라도 actual을 command echo로 생성하지 않는다.

첫 C++ 작업은 C++17, 현재 Host의 GCC 11.4.0, CMake 4.3.2와 설치된 GoogleTest 1.11.0을
사용한다. `std::array`와 `std::optional`로 고정 크기 bytes와 실패를 명시한다.
CMake의 최소 지원 선언은 기존 3.20을 유지하며 3.20 자체를 검증했다고 주장하지 않는다.
GoogleTest는 exact 1.11.0을 요구하고 자동 download를 넣지 않는다. 테스트를 끈 빌드는
GoogleTest가 필요 없지만 검증 완료로 취급하지 않는다.

GoogleTest 1.11.0의 [BSD-3-Clause license](https://github.com/google/googletest/blob/release-1.11.0/LICENSE)와
현재 설치 package의 copyright를 확인했다. Third-party source/binary를 repository에 복사하지 않는다.
직접 관리하는 target에만 `-Wall -Wextra -Werror`를 적용한다. ASan/UBSan은 별도 Host build로
실행하고, clang-tidy 14.0.0과 cppcheck 2.7의 검사 범위·명령은 [실행 기록](../learning/communication-guide.md)에 남긴다.

<a id="adr-0005-alternatives-considered"></a>

### Alternatives Considered

- Python codec만 구현: 빠른 실험에는 적합하지만 이번에는 향후 C++ component가 사용할
  field 함수를 작은 단위로 작성하고 build/test 경로를 확인한다.
- Six-frame codec 전체를 한 번에 구현: metadata와 상태 검증까지 커지므로 먼저 field
  표현을 검토한다. 전체 frame 구현 전에 남은 wire/receiver 계약을 해소한다.
- 새 compiler나 test framework 설치: 현재 환경의 도구로 이번 범위를 검증할 수 있어 보류한다.

<a id="adr-0005-consequences"></a>

### Consequences

TBD-11의 첫 Host C++ 실험 선택만 기록했다. CI/Target/AUTOSAR toolchain 호환성은
미검증이며 TBD-11/09와 pilot 검토가 계속 필요하다. TBD-01/02의 field 제안은 별도 초안으로
추적하고 전체 TBD를 CLOSED로 처리하지 않는다. 실제 조향 한계, frame identity, CRC,
freshness, local safety는 이번 codec의 책임 밖이다. 기존 Requirement ID/shall 문장은 유지한다.

<a id="adr-0006"></a>

## ADR-0006 — Host Steering frame codec and DBC checker

<a id="adr-0006-status"></a>

### Status

2026-10-12 **Host 구현·검증 완료 / 학습자 review PENDING**.
Steering 두 frame의 초안을 시험했다. Six-frame baseline과 M1 acceptance는 미완료다.
2026-10-12 자체 CRC/초기 wire 결정은 [ADR-0007](#adr-0007)의
P05/schema 2로 대체했다. 아래 Host 도구/dependency 결정은 유지한다.

<a id="adr-0006-decision"></a>

### Decision

[Frame 제안](../interfaces/steering-frame.md)을 C++17의 고정 크기 payload로 구현한다.
기존 angle codec을 재사용하고 ID/FD/length/flags, CRC, schema/reserved/enums/epoch와
Validity/angle 표현의 일관성을 검사한다. uint64 timestamp는 double을 거치지 않는다.
Command 수용, 물리 한계, mode/origin 관계와 시간/trace Sequence 진행을 판단하는 receiver는 별도로 둔다.
후속 ADR-0007에서 P05 Protect/Check state를 추가했다.
Wire decode의 성공과 invalid/unavailable 진단 message, 유효 actuator input을 구분한다.

DBC와 수작업 C++ 배치의 차이를 확인할 Host 전용 도구로 **cantools 40.7.1**을 사용한다.
[공식 문서](https://cantools.readthedocs.io/en/latest/)의 strict parser/encode/decode API로
독립 golden vectors 및 C++ demo를 비교한다. 여기서는 code generation을 사용하지 않는다.
현재 Host의 Python 3.10.12, uv 0.9.15로 `build/m1-dbc-venv`를 생성했다.
[전체 dependency pin](../../tools/requirements-dbc.txt)을 기록하고 CMake 자동 설치는 추가하지 않는다.
새 Python checker는 runtime/library/Target 의존성이 아니다.

<a id="adr-0006-dependency-review"></a>

### Dependency review

2026-10-12 PyPI release metadata의 Python 지원과 license를 확인한 뒤 격리 환경에 설치했다.
cantools 40.7.1 wheel의 MIT license 본문/copyright도 확인했다.
Wheel SHA256: `a68159cce229581f77aad0b906938682f29ecc9164248c997af80f1d49c073c9`.
Third-party source/binary를 repository에 복사하거나 generated code를 배포하지 않는다.

| Package | 고정 version | 확인한 license |
| --- | --- | --- |
| cantools | 40.7.1 | MIT |
| argparse-addons | 0.12.0 | MIT |
| bitstruct | 8.23.0 | MIT |
| crccheck | 1.3.1 | MIT |
| textparser | 0.26.2 | MIT |
| diskcache | 5.6.3 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| python-can | 4.6.1 | LGPL-3.0-only |
| typing-extensions | 4.16.0 | PSF-2.0 |
| wrapt | 1.17.3 | BSD (release metadata 표기) |

python-can은 cantools의 dependency이며 이번 checker가 CAN socket을 사용한다는 뜻이 아니다.
향후 third-party 복사/배포/Target 도입 시 해당 artifact와 조건을 다시 검토한다.

<a id="adr-0006-alternatives-and-consequences"></a>

### Alternatives and consequences

- 자체 DBC parser만 작성: 같은 설계 오류를 공유할 수 있어 독립 parser와 비교한다.
- DBC에서 C 코드를 생성: 가능한 후속 선택이다. 이번에는 기존 C++ field codec과 연결하고
  작은 byte packing 구현을 학습하기 위해 수작업 codec + 독립 parser 검증을 선택했다.
- 전체 receiver/vCAN/vECU를 한 번에 구현: 학습/검토 범위를 나누기 위해 이번에는 wire codec만 구현한다.

TBD-11의 Host DBC 검증 도구 선택만 구체화한다. Target/CI/일반 toolchain 선택은 남는다.
TBD-01/02/04의 전체 wire/물리 범위/receiver/timing을 CLOSED로 바꾸지 않는다.
검증 명령과 결과 범위는 [학습 실행 기록](../learning/communication-guide.md)에 남긴다.

<a id="adr-0007"></a>

## ADR-0007 — Steering 통신 보호에 AUTOSAR E2E Profile 5 적용

<a id="adr-0007-status"></a>

### Status

2026-10-12 사용자 요청으로 채택한 **Host Profile 5 Protect/Check 구현·검증 / 학습자 review PENDING**.
[ADR-0006](#adr-0006)의 자체 CRC wire 설계를 대체한다.
M0 의미 계약, 요구사항 ID, Reference v0.1 및 milestone은 유지한다.
M1 acceptance와 차량 application receiver/vCAN 송수신은 미완료다.

<a id="adr-0007-standard-and-implementation-scope"></a>

### Standard and implementation scope

기준 판은 **AUTOSAR R25-11**이다.

- [FO E2E Protocol Specification](https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_E2EProtocol.pdf), §6.8 및 공통 Protect/Check 도표.
- [CP SW-C E2E Library Specification](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_SWS_E2ELibrary.pdf), §8.2.5/8.3.5의 설정·상태·초기화·Protect/Check 계약.

[직접 작성한 C++17 구현](../../interfaces/common/e2e_profile5.cpp)은 Profile 5의 CRC,
Protect/ProtectInit, Check/CheckInit 동작을 제공한다. C++ reference/optional/return enum을
사용하는 프로젝트 API이며 AUTOSAR C ABI나 vendor BSW를 가져온 구현이 아니다.
Check 함수의 호출 결과와 profile status를 분리한다. `p05_is_ok`는 호출 성공과
OK/OKSOMELOST를 함께 확인하는 프로젝트 helper다.
Forward, GetHeaderInfo, MapStatusToSM 및 profile-independent E2E State Machine은 구현하지 않았다.
OS/RTE/COM/BSW 통합이나 전체 AUTOSAR 적합성·안전 인증 완료를 뜻하지 않는다.

<a id="adr-0007-decision"></a>

### Decision

고정 길이 32-byte Steering Command/Actual에 P05를 적용한다.
P05의 byte 단위 배치와 3-byte header는 기존 byte-aligned codec과 연결하기 쉽다.
Profile 4의 더 큰 header와 CRC32도 대안이지만, 이번 학습 범위에서는 P05를 선택했다.
필요한 오류 검출 성능/잔여 오류율과 safety allocation은 이후 분석 범위이며
이번 선택만으로 ASIL이나 Hamming Distance의 프로젝트 보장치를 확정하지 않는다.

| 설정 | Command | Actual |
| --- | --- | --- |
| CAN ID | 0x180 | 0x280 |
| Data ID | 0x1001 | 0x1002 |
| DataLength (bits) | 256 | 256 |
| Offset (bits) | 232 | 232 |
| MaxDeltaCounter | 10 | 10 |

Data ID 두 값은 이 프로젝트에서 서로 다르게 할당한 값이며 CAN 표준 번호가 아니다.
후속 Brake/Drive/DDS 설정에서도 중복되지 않도록 관리한다. CAN ID는 transport identity이고
Data ID는 보호 대상 identity다. DBC에는 프로젝트 정의 attribute로 설정을 기록하며
이 attribute를 AUTOSAR ARXML이나 자동 COM 설정으로 간주하지 않는다.
MaxDeltaCounter=10은 기존 10 ms stream의 실험 후보이며 측정으로 확정한 값이 아니다.

CRC는 poly=0x1021, init=0xFFFF, refin/refout=false, xorout=0이며,
전체 payload에서 CRC 두 byte만 제외한 뒤 Data ID를 low/high 순서로 붙여 계산한다.
기존 CAN ID/length prefix는 제거한다. Envelope의 종류·ID·길이·flags는 별도 검사한다.
CRC는 byte 29–30에 little-endian으로, Counter는 byte 31에 기록한다.
Angle/metadata byte 0–25를 유지하고 Reserved를 byte 26–28의 3 bytes로 줄인다.
SchemaVersion을 **1 → 2**로 변경하며 이전 wire payload는 지원하지 않는다.

<a id="adr-0007-state-and-application-responsibilities"></a>

### State and application responsibilities

송신 stream별 Protect state는 첫 Counter=0이며 성공한 보호 호출마다 증가한다.
255 다음은 0이다. Counter는 message나 trace Sequence에서 복사하지 않는다.
수신 Check 초기 상태는 Counter=255, Status=ERROR다.
CRC 정상 frame의 modulo-256 delta가 0이면 REPEATED, 1이면 OK,
2…MaxDeltaCounter면 OKSOMELOST, 그 밖이면 WRONGSEQUENCE다.
WRONGSEQUENCE에서도 규격대로 수신 E2E counter를 갱신한다.
CRC 오류와 NONEWDATA는 E2E counter를 갱신하지 않는다.
API 입력 오류는 state를 변경하지 않으므로 return 값도 반드시 확인한다.

E2E state와 application의 last-accepted Sequence/source time/snapshot/last-valid RX는 별도다.
WRONGSEQUENCE 뒤 다음 frame의 E2E OK만으로 FAIL_SAFE를 해제하지 않는다.
32-bit trace Sequence와 Epoch는 기존 application replay/인과관계 정책을 유지한다.
Trace Sequence wrap은 새 Epoch + explicit INIT를 요구하고, E2E Counter wrap은 정상이다.
Freshness, 물리 한계, mode/Origin, timeout, explicit INIT 및 last-valid RX 갱신은 후속 receiver에서
검사한다. Profile-independent E2E State Machine 채택·설정도 별도 receiver 설계 항목이다.
현재 CLI와 unit test는 이 전체 command 수용/gate를 구현한 것이 아니다.

<a id="adr-0007-evidence-and-consequences"></a>

### Evidence and consequences

새 C++/Python runtime dependency는 추가하지 않았다. 기존 cantools와 Python binascii로
DBC/independent CRC를 확인한다. 공식 §6.8.5의 두 예제 CRC **0xCA1C/0x9128**와
프로젝트 golden vectors를 별도로 검사한다.
기존 자체 CRC vectors는 schema 2 P05 vectors로 교체하고 malformed/invalid/uint64 시험을 유지했다.

2026-10-12 normal/ASan·UBSan **25개 PASS**, DBC parser/golden/demo 교차 검증 PASS,
clang-tidy 및 cppcheck의 변경 production source 검사에서 소스 진단 없음.
명령과 한계는 [실행 기록](../learning/communication-guide.md)에 있다.
기존 차량 TC를 VERIFIED로 바꾸지 않으며 학습자 직접 재현/review는 PENDING이다.

<a id="adr-0008"></a>

## ADR-0008: Steering의 로컬 application 수신부

Status: **2026-10-12 Host 구현·제어 가능한 시계 시험 완료 / 학습자 review PENDING**.
관련: [frame 초안](../interfaces/steering-frame.md), [P05 결정](#adr-0007),
SYS-COM-001/002/003/004, SYS-SAFE-003/004. Reference v0.1의 requirement를 변경하지 않는다.

<a id="adr-0008-문제"></a>

### 문제

Frame 복원과 P05 CRC/Counter 검사는 실행했지만 오래된 sample, 다른 Epoch, 새 Counter로
재포장한 cached sample을 application 입력으로 수용할지 결정하는 코드는 없었다.
P05의 raw counter 재동기화를 마지막 유효 수신으로 취급하면 invalid traffic이 timeout을
연장할 수 있다. Timeout 시 도착한 늦은 frame으로 자동 복구하는 것도 recovery 계약과 다르다.

<a id="adr-0008-결정"></a>

### 결정

Socket/clock/coordinator와 독립인 C++17 [SteeringReceiver](../../interfaces/steering/steering_receiver.hpp)를
Command/Actual stream마다 단일 thread에서 소유한다. Runtime 동적 할당이나 unbounded drain은 없다.
신뢰된 호출자의 `start_session(epoch, monitoring_enable_ns)`가 INIT 설정을 전달한다.
첫 Epoch는 nonzero, 재초기화는 이전보다 큰 Epoch와 비감소 시각을 요구한다.
동일 인스턴스의 Epoch reuse/overflow를 거부하며 frame에서 새 Epoch를 자동 학습하지 않는다.

수신 순서는 clock/timeout → envelope → P05 → payload 표현 → Epoch/source age/trace Sequence
→ validity/mode/range다. P05 raw counter는 기존 규격대로 갱신한다. Application의
Sequence/source cursor/snapshot/last-valid RX는 모든 조건이 통과한 경우만 함께 갱신한다.
반환값은 reject 이유와 이번 호출의 E2E status를 구분하며, envelope/API 오류 때 이전 OK를 재사용하지 않는다.

| 정책 | 로컬 실험 설정 / 의미 |
| --- | --- |
| Clock | caller가 전달하는 uint64 ns; source와 now가 같은 monotonic domain이라는 설정 전제 |
| Trace Sequence | 첫 번호 0..9, 이후 +1..+10; 같은 Epoch의 uint32 wrap 거부 |
| Source time | session 시작 이상, now 이하, 수용한 이전 source보다 엄격히 증가 |
| Source freshness | 기본 age <=30 ms; cached 재송신은 source/Sequence를 바꾸지 않음 |
| RX/acquisition timeout | 기본 age >=80 ms; 첫 유효 수신 전에는 monitoring enable이 기점 |
| Timeout 설정 상한 | <=80 ms로 제한해 기존 100 ms budget의 polling/dispatch/jitter 20 ms를 남김 |
| 조향 한계 | finite min < max를 caller가 명시; wire 범위 안, fixture는 +/-0.5 rad |
| Numeric boundary | raw→double의 1 ULP 오차만 허용; 다음 0.0001-rad wire step은 거부 |

Config는 `0 < max_source_age_ns < timeout_ns <=80 ms`를 요구한다. 이 후보값과 fixture 한계는
양산차 calibration이 아니며 TBD-01/02/04를 CLOSED로 바꾸지 않는다.
Command는 NORMAL/DEGRADED + normal path만 수용한다. INIT와 보호 FAIL_SAFE command는
물리 정책이 정의되지 않아 거부한다. Actual은 sender 상태를 보존하며 origin=0은 INIT에서만
허용한다. Fault/protection 중 유효 Actual sample을 정상 주행 가능 판정으로 바꾸지 않는다.

`receive`와 `current_sample`은 timeout을 먼저 검사하고, 입력 없는 cycle은 caller가 `poll`한다.
Timeout/clock 감소는 fault로 유지하며 새 Epoch의 explicit INIT만 초기화한다.
`current_sample(now)`는 source age도 검사한다. 80 ms RX timeout 전이어도 30 ms source age가
끝나면 값이 없다. `last_accepted()`는 fault 후에도 남는 진단 이력이며 제어 입력 조회 API가 아니다.

<a id="adr-0008-대안과-결과"></a>

### 대안과 결과

Socket 내부에서 바로 수용하거나 수신 frame으로 Epoch를 학습하면 clock/epoch/timeout 경계 시험이
transport에 결합된다. 명시적 local API로 분리해 수동 시각으로 경계와 fault를 먼저 검증한다.
항목별 reject는 반환값으로 전달하고 외부 logger가 호출 시각과 함께 기록한다.

실제 CLOCK_MONOTONIC adapter, startup coordinator/영속 Epoch, stream당 bounded queue,
socket overflow 관측, 10 ms monitor dispatch 및 wall-time 검출 지연 측정은 후속 작업이다.
이 수신부는 AUTOSAR profile-independent E2E State Machine이나 vehicle safety state machine이 아니다.
Actual invalid에 대한 Host apply/tick gate와 actuator availability, 보호 출력, dynamics는
Zone/Plant Adapter/vECU 통합에서 별도로 구현한다.

<a id="adr-0008-증거"></a>

### 증거

[실행 기록](../learning/communication-guide.md): 새 receiver 19개 + 기존 25개 = normal/ASan·UBSan
각각 44개 PASS. Demo, 변경 source의 compiler/static analysis와 README의 light/dark Mermaid 렌더링을
확인했다. System TC, 실제 검출 지연, M1 acceptance와 학습자 review는 완료로 처리하지 않는다.

후속 [ADR-0009](#adr-0009)에서 실제 CLOCK_MONOTONIC/SocketCAN adapter와
독립 process 시험을 연결했다. 영속 Epoch coordinator와 차량 task/physical response는 남아 있다.

2026-10-13 [ADR-0012](#adr-0012)에서 이 clock/Epoch/Sequence/timeout 상태를
공통 `ActuatorReceiverState`로 추출해 Brake와 공유했다. 기존 Steering API와 정책은 유지했고
기존 시험을 포함한 normal/sanitizer unit·vCAN을 다시 실행했다.

<a id="adr-0009"></a>

## ADR-0009: Steering codec와 Linux SocketCAN 연결

Status: **2026-10-12 Host vCAN 구현·시험 완료 / 학습자 review PENDING**.
관련: [수신부 결정](#adr-0008), [frame 계약](../interfaces/steering-frame.md),
TBD-01/04/11. Reference v0.1의 requirement나 wire schema를 변경하지 않는다.

<a id="adr-0009-문제"></a>

### 문제

메모리 안에서 검증한 SteeringFrame을 실제 CAN socket으로 전달하는 코드가 없었다.
수신 종류/ID flags/길이를 정규화하면 잘못된 입력을 정상 Steering frame으로 바꿀 수 있다.
Queue를 무한히 비우는 loop는 반복 frame 중 timeout 검사를 늦출 수 있다.

<a id="adr-0009-결정"></a>

### 결정

- `interfaces/common/`: 조향과 독립인 P05 Protect/Check.
- `interfaces/steering/`: angle/frame codec과 application receiver. 기존 파일의 내용은 유지한다.
- `interfaces/socketcan/`: Linux 전용 socket 소유·I/O와 SteeringFrame 변환.

[Endpoint](../../interfaces/socketcan/socketcan_endpoint.hpp)는 RAII로 socket을 닫고,
nonblocking/CLOEXEC, CAN_RAW_FD_FRAMES, interface MTU=72 검사와 RX prefilter를 적용한다.
RX용 ID는 하위 11 bit만 filter하고 EFF/RTR flag를 지우지 않는다. 최종 envelope 판정은
SteeringReceiver가 한다. TX endpoint는 수신 filter를 비운다. 별도 process 사이 전달에는
Linux의 기본 local loopback을 사용한다.

Transport의 Frame은 64-byte 저장 공간을 가진다. `recvmsg`가 반환한 ABI 크기로 Classical과
FD를 구분한다. Classical padding을 FD flag로 해석하지 않는다. 조향 표현으로 변환할 때
실제 ID/FD/flags/length를 유지하고 payload의 앞 32 bytes만 복사한다. 길이 64를 32로 고치지 않는다.
이는 [Linux SocketCAN 문서](https://docs.kernel.org/networking/can.html)의 두 ABI 크기/길이 구분을 따른다.

수신 queue가 비면 nullopt, I/O/잘린 ABI frame은 exception으로 보고한다.
`SO_RXQ_OVFL`의 누적 drop 수를 전달하며 demo는 nonzero drop을 continuity fault로 보고 종료한다.
이 값은 socket 생성 이후 누적된 drop 수이며 실제 buffer 크기를 8개로 만드는 설정이 아니다.
근거는 [Linux socket(7)](https://www.man7.org/linux/man-pages/man7/socket.7.html)이다.
Drop을 강제로 발생시킨 fault 시험과 kernel buffer budget 확정은 후속 작업이다.

TX/RX는 독립 C++ process이며 source와 receive time은 같은 Linux CLOCK_MONOTONIC이다.
Python fixture가 명시적으로 Epoch=1을 전달하고 양쪽 socket ready를 확인한다. Receiver의
`start_session` 완료 후 sender를 시작하여 first-frame acquisition 기점을 정한다.
이 handshake는 시험 시작용이며 영속 Epoch coordinator, 서로 다른 time namespace나
Host–Target clock 동기화를 구현한 것은 아니다. Epoch=1 재사용은 격리된 새 시험에서만 사용한다.

RX demo는 한 cycle 최대 8개를 처리하고 `current_sample(now)`로 timeout/source age를 검사한 뒤
1 ms를 쉰다. 별도 application queue는 없으며 Linux socket queue를 사용한다.
Kernel queue가 8개라는 주장은 하지 않는다. 로깅 비용도 있으므로 이것을 production task의
10 ms deadline/priority/affinity 설계나 hard real-time 보장으로 사용하지 않는다.
Timeout 이후에도 관측을 이어가 late frame이 자동 복구하지 않는지 확인한다.
I/O/overflow 종료는 demo의 오류 처리이며 차량 FAIL_SAFE output은 후속 vECU에서 구현한다.

정리 후 TX/RX/helper/Python runner는 `tests/integration/can/`에 모았다.
Participant는 `BUILD_TESTING=ON`일 때만 build한다. 메모리 실행 예제 4개는
`tools/actuator_demo.cpp`의 angle/frame/e2e/receiver 명령으로 합쳤다.
수신 trace는 cycle마다 한 번 flush하고, runner는 participant가 실패해도 수집한 stdout/stderr를 남긴다.
Frame 검사/Counter/수용/timeout 정책은 유지한다. 추가 기준은 [품질 정책](milestone-reviews.md)을 따른다.

위 경로는 2026-10-13 [Brake 확장](#adr-0010) 후 이름이다.
당시 `steering_demo`/Steering 전용 integration 배치를 actuator 공통 배치로 확장했다.

<a id="adr-0009-증거와-다음-범위"></a>

### 증거와 다음 범위

[실행 기록](../learning/communication-guide.md)에 unit 48개, normal/ASan·UBSan 각각
vCAN 8개 case, compiler/static analysis와 DBC 교차 검증을 기록했다.
Command=0.2 rad, Actual=0.15 rad의 독립 fixture를 사용한다. Actual은 command echo나
dynamics 결과가 아니다. Brake/Drive four-frame 확장, 영속 session, queue overflow 주입,
vECU physical response와 차량 TC는 남아 있다.

<a id="adr-0010"></a>

## ADR-0010: Brake wire codec과 공통 actuator payload

Date: 2026-10-13. Status: **PROPOSED / Host 구현·시험 실행, 학습자 review PENDING**.

<a id="adr-0010-문제"></a>

### 문제

Steering의 angle/frame/P05/receiver/vCAN을 구현했다. 다음 M1 작업은 Brake Command/Actual이다.
M0 의미 계약은 nonnegative aggregate pressure, Pa다. 모듈 추가마다 metadata·E2E·예제·통합
시험을 복사하면 배치가 흩어지고 같은 계약의 수정이 서로 어긋날 수 있다.

<a id="adr-0010-결정"></a>

### 결정

- Pressure는 unsigned 16-bit LE, 1,000 Pa/raw, 0–65,534 유효, 65,535 invalid로 표현한다.
  0 Pa는 유효한 release demand이며 invalid와 구분한다. 범위 검사 후 반올림하고 clamp하지 않는다.
- CAN ID 후보 `0x181`/`0x281`에 P05 Data ID `0x1101`/`0x1102`를 할당한다.
  기존 Steering stream과 중복되지 않으며 profile/config와 Counter state를 stream별로 유지한다.
- Schema 2의 공통 metadata/CRC 배치를 `interfaces/common/actuator_payload_codec.*`로 추출한다.
  Steering의 기존 golden bytes와 수신 동작을 유지한다. 압력/각도 codec과 domain의 CAN ID,
  invalid code, 수신 정책은 `interfaces/brake/` 및 `interfaces/steering/`에 둔다.
- 기존 demo를 `actuator_demo`로 확장한다. 기존 DBC 검사기는 `check_actuator_dbc.py` 하나에서
  두 domain을 검사한다. SocketCAN adapter와 integration participant/runner도 공유한다.
  통합 시험은 `tests/integration/can/`, 새 Brake 모듈의 단위 시험은 `brake_codec_test.cpp`에 둔다.

<a id="adr-0010-대안과-영향"></a>

### 대안과 영향

Signed 16-bit는 음수 pressure가 없는 계약에 표현 공간 절반을 쓴다.
Unsigned 32-bit는 더 넓은 범위/더 작은 해상도를 제공하지만 현재 2-byte field와 metadata 위치를
바꿔야 한다. 초안은 기존 배치를 유지하며 16-bit를 선택했다. 100 Pa/raw 등의 더 작은 factor는
같은 bit 수에서 wire 최대값을 줄인다. 실제 calibration 검토에서 표현력이나 해상도가 부족하면
ICD/DBC/schema/codec/vector를 함께 개정한다. 현재 factor와 wire 최대값은 차량 parameter 근거가 아니다.

추출한 common codec은 고정 schema의 직렬화와 CRC 검사를 담당한다. Freshness, timeout,
mode, 물리 범위, pressure dynamics를 여기에 넣지 않는다. Brake의 Actual은 독립 시험 sample이며
command echo나 물리 모델 결과로 주장하지 않는다. 새로운 범용 framework/외부 의존성은 추가하지 않았다.

<a id="adr-0010-증거와-다음-작업"></a>

### 증거와 다음 작업

[Wire ICD](../interfaces/brake-frame.md)와 [실행 기록](../learning/communication-guide.md)에 설정과
normal/sanitizer unit·DBC·vCAN 검사 범위를 기록한다. 기존 Steering 48개 case를 유지하고
Brake/shared payload/adapter case를 더했다. 다음은 Brake application receiver이고,
이후 Drive wire 확장이다. 영속 coordinator, overflow 주입, six-frame acceptance와 차량 TC는 남아 있다.

<a id="adr-0011"></a>

## ADR-0011: 회생제동을 포함한 Drive–Brake 설계

Date: 2026-10-13. Status: **회생제동 포함 범위 ACCEPTED / 상세 설계 초안 / 구현 PLANNED / 시험 NOT RUN**.
Owner: 학습자(project owner). 근거: 사용자의 회생제동 포함 설계 결정.

후속 [EV-01 / ADR-0014](#adr-0014)가 별도 BMS 제외/충전 fixture만
사용하는 범위를 대체한다. 아래 최초 결정은 역사적 기록이며 RG-01의 토크·배분 계약은 유지한다.

<a id="adr-0011-문제"></a>

### 문제

Reference Baseline v0.1은 Drive를 전진 구동 토크, Brake를 마찰제동 압력으로 정의하고
회생제동을 제외했다. 전기 구동 SIL을 확장하려면 회생 토크와 마찰제동을 함께 배분하고,
회생 가용량의 변화와 실제 회수 에너지를 구분할 계약이 필요하다.

<a id="adr-0011-결정"></a>

### 결정

- 확장 ID는 **RG-01**이다. 전진 ODD는 유지하고 회생제동을 포함한다.
- Drive Command/Actual은 driven-wheel 기준 signed motor torque(N·m)를 사용한다.
  전진 구동은 양수, 전진 중 회생 감속은 음수다. 후진 요구를 추가하는 것은 아니다.
- Brake Command/Actual은 마찰제동 압력(Pa)을 유지한다. 현재 Brake DBC/codec을 변경하지 않는다.
- Zone은 총 제동 요구를 공통 wheel 기준으로 변환하고, 유효한 회생 가용량 안에서
  Drive와 Brake에 배분한다. Drive는 actual torque와 회생 가용량/유효성 정보를 제공한다.
- 회생 가용량 0과 critical Drive Actual 상실은 구분한다. Critical loss의 FAIL_SAFE와
  Host tick gate는 유지한다. Drive command timeout은 양수·음수 demand 모두 무효화하고
  local **zero motor torque target**을 선택한다.
- 첫 모델은 속도·충전 수용 한계의 단순 모델과 actual 기반 에너지 집계를 포함한다.
  상세 배터리 화학 모델, 별도 BMS ECU, ABS/ESC 및 바퀴별 배분은 이번 확장에 추가하지 않는다.

<a id="adr-0011-영향과-미결정-사항"></a>

### 영향과 미결정 사항

[회생제동 설계](../interfaces/regenerative-braking.md)에 의미, 배분, 보호 및 시험을 정의한다.
Drive wire의 signed scaling/layout, capability freshness, 압력→토크 calibration,
응답/전환 budget, 효율과 충전 한계는 TBD-01/02/03/06/07에서 결정한다.
통합 속도 입력의 전달 경로는 TBD-01/05다.
기존 32-byte 배치가 Drive 추가 정보를 충분히 표현하는지는 M1에서 검토한다.

SYS-SAFE-004를 v0.2로 개정하고 SYS-CTRL-008/009와 SYS-SAFE-005를 v0.2로 추가한다.
기존 M0 v0.1의 15개 exit review 결과는 역사적 기록으로 유지하며 RG-01에 적용하지 않는다.
기존 Steering/Brake wire 시험은 회생제동 검증 증거가 아니다.

<a id="adr-0011-구현-순서"></a>

### 구현 순서

Brake application receiver → 회생을 포함한 Drive wire/receiver → M2 actuator·충전 수용 모델
→ M4 Zone 배분 → M6 Simple Plant → M7 CARLA mapping 순서로 진행한다.
이번 결정은 설계 문서 변경이며 회생제동 runtime 구현이나 시험 완료를 뜻하지 않는다.

<a id="adr-0012"></a>

## ADR-0012: Brake application 수신부와 공통 수신 상태

Date: 2026-10-13. Status: **Host 구현·시험 실행 / 학습자 review PENDING**.
관련: [Brake wire](../interfaces/brake-frame.md), [Steering 수신 정책](#adr-0008),
[회생제동 범위](#adr-0011). 요구사항의 새 revision을 추가하지 않는다.

<a id="adr-0012-문제와-결정"></a>

### 문제와 결정

Brake의 DBC/압력/P05/wire 송수신은 있었지만 유효 demand 수용과 timeout 처리가 없었다.
같은 clock/Epoch/Sequence 규칙을 복제하면 actuator별 수정이 어긋날 수 있다.

- [BrakeReceiver](../../interfaces/brake/brake_receiver.hpp)를 Command/Actual stream별로 둔다.
  Frame에서 Epoch를 자동 학습하지 않고 trusted `start_session`으로만 시작한다.
- [ActuatorReceiverState](../../interfaces/common/actuator_receiver_state.hpp)에 clock/session,
  source freshness, trace Sequence, last-valid RX와 fault latch를 공유한다.
  Steering의 API/정책/기존 시험을 유지한다. 값의 codec/P05 Data ID/압력 한계는 Brake가 맡는다.
- 순서는 clock/timeout → envelope/P05 → payload → metadata → validity/mode/pressure range다.
  모든 검사가 통과한 경우만 snapshot/application cursor/valid RX를 함께 갱신한다.
  P05 raw counter 재동기화는 application 수용으로 취급하지 않는다.
- Caller는 finite `0 <= min_pressure_pa < max_pressure_pa <= wire maximum`을 명시한다.
  fixture는 0–2,000,000 Pa다. 이는 차량 최대 압력/제동 성능 calibration이 아니다.
- 기본 source age는 <=30 ms, RX timeout은 >=80 ms이며 설정은
  `0 < source_age < timeout <=80 ms`다. 100 ms 검출 계약의 dispatch margin을 남기는 후보다.
- 첫 trace Sequence는 0..9, 이후 +1..+10이며 같은 Epoch의 uint32 wrap은 거부한다.
  Source time은 session 시작 이상/now 이하/이전 수용 source보다 엄격히 증가한다.
- Command는 NormalPath + NORMAL/DEGRADED만 수용한다. 보호 command의 실제 압력 정책은
  M2에 정의한다. Actual은 sender state를 보존하며 NoAcceptedInput은 INIT에서만 허용한다.
- Source age가 끝나면 timeout 전에도 `current_sample`이 없다. `last_accepted`는 진단 이력이다.
  Timeout/clock fault는 새 Epoch와 비감소 clock의 explicit INIT으로만 초기화한다.

<a id="adr-0012-배치와-검증"></a>

### 배치와 검증

기존 `actuator_demo`에 `brake-receiver`를 추가하고 기존 CAN TX/RX/runner를 확장했다.
TX/RX의 bounded loop/stdio handshake/trace 경로도 두 actuator가 공유한다.
Brake wire 회귀 2개는 별도로 유지하고 application normal/fault/silent/flood 각 2개 stream을 추가했다.
새 독립 receiver 모듈의 시험은 `tests/unit/brake_receiver_test.cpp`에 둔다.

[실행 기록](../learning/communication-guide.md)에 명령과 결과 범위를 남긴다.
Pressure dynamics, timeout 이후 압력 hold/release/ramp, vECU task/watchdog/가용성 및
Host apply/tick gate 통합은 미구현이다. `Receiving`은 정상 주행 허가나 실제 제동 성공이 아니다.
회생 runtime과 Drive wire도 후속 작업이다.
이후 [ADR-0013](#adr-0013)에서 Drive wire/receiver를 구현·시험했다.
물리 응답·회생 배분은 계속 후속 범위다.

<a id="adr-0013"></a>

## ADR-0013: 구동·회생 Drive wire와 독립 피드백 유효성

Date: 2026-10-13. Status: **Host 구현·시험 실행 / 학습자 review PENDING**.
관련: [RG-01](#adr-0011), [wire ICD](../interfaces/drive-frame.md),
[실행 안내](../learning/communication-guide.md). 기존 requirement revision을 변경하지 않는다.

<a id="adr-0013-문제와-결정"></a>

### 문제와 결정

Drive의 signed motor torque와 회생 가용량은 의미만 정의되어 있었다. Torque sample을
새로 보내더라도 cached 속도·충전 입력으로 산출한 capability가 새 정보가 되는 것은 아니다.

- Command는 0x182 / 32 bytes, Actual은 0x282 / 64 bytes로 정의한다. Data ID는
  0x1201/0x1202, stream별 P05 state를 소유한다. Frame 수는 기존 six-frame을 유지한다.
- Torque는 aggregate driven-wheel 기준 signed int16 LE / 0.1 N·m이며 raw -32768은 invalid다.
  양수 구동/음수 전진 회생/유효 0을 구분한다. 이 wire 범위는 물리 calibration이 아니다.
- Actual은 torque의 metadata와 별개로 wheel-speed source time, capability calculation time,
  가장 오래된 dependency source time을 보존한다. Capability에는 별도 validity/limit/reason이 있다.
  유효한 0 한계와 정보 없음은 다르다. 전체 64 bytes를 하나의 P05 CRC로 보호한다.
- 기존 schema 2 prefix/CRC/Counter 위치를 유지하고 공통 payload codec에 명시적인
  64-byte 경로를 추가한다. Steering/Brake의 bytes/API/golden vectors를 유지한다.
- DriveReceiver는 공통 Epoch/Sequence/clock/valid-RX/timeout 상태를 재사용한다.
  Torque가 수용되더라도 speed/capability는 원천 시각과 caller의 범위로 별도 검사한다.
  사용할 수 없는 보조 값은 current sample에서 제거하고 torque의 유효성과 구분한다.
- 같은 원천 시각의 cached feedback은 값/이유/input time이 불변이어야 한다.
  새 산출 시각으로 오래된 입력을 유효하게 만들지 않는다. 최신 frame의 무효 정보를
  과거 capability로 대체하지 않는다. Fault latch는 새 Epoch의 trusted INIT으로만 초기화한다.
- Application fixture의 범위는 torque -300..500 N·m, speed 0..100 rad/s,
  regen magnitude 0..300 N·m다. Source/input age 30 ms와 RX timeout 80 ms는
  기존 Host budget의 초안이며 실차 성능·안전 calibration이 아니다.

<a id="adr-0013-범위와-검증"></a>

### 범위와 검증

기존 actuator_demo/DBC checker/CAN TX·RX·runner에 Drive를 추가한다.
독립 모듈 시험은 한 파일 tests/unit/drive_test.cpp에 모아 value/frame/receiver를 검사한다.
명령·실행 결과와 제한은 [학습 안내](../learning/communication-guide.md)에 기록한다.

M1 wire는 음수 demand를 표현·수용하지만 local capability에 따른 실제 torque 제한은
M2 모델이 담당한다. Charge acceptance/energy, vehicle state의 DDS 전달, Zone blending,
Plant 적용 및 차량 전체 피드백 loop는 미구현이다. 통신 수용은 제동 성공이나 회생 에너지
발생을 입증하지 않는다. M0 baseline을 소급 변경하거나 전체 TC-REG 결과를 PASS로 바꾸지 않는다.

<a id="adr-0014"></a>

## ADR-0014: 전기차 기능·상태·통신을 재현하는 SIL 범위

현재 배치: [ADR-0021](#adr-0021). 차량 관리/배분/session/Host 집계의 배치는 2026-10-14 ADR-0021의 Central 별도 component와 대등한 두 Zone을 따른다. 아래 결정/결과는 작성 당시 범위 기록이다.

Date: 2026-10-13. Status: **EV-01 포함 범위 ACCEPTED / 상세 설계 초안 / 구현 PLANNED / 시험 NOT RUN**.
Owner: 학습자(project owner). 근거: 실차의 프로세스·구조를 재현한다는 사용자 방향과
기존 계층 유지, BMS 추가, Zone을 거치는 상위 feedback 경로에 대한 대화의 합의.
상세 설계/parameter의 학습자 review는 PENDING이다.

<a id="adr-0014-문제"></a>

### 문제

RG-01은 회생제동을 포함하지만 충전 수용 한계를 fixture로 주입하고 별도 BMS ECU를
제외했다. 차량의 준비·주행·종료·주요 고장 대응을 학습하려면 충전/방전 한계의
producer, 차량 주행 허가와 전원 상태, 상실 시 반응을 명시해야 한다.

<a id="adr-0014-결정"></a>

### 결정

- 확장 ID는 **EV-01**이다. Central → Zone → Leaf 계층, 당시 단일 Zone,
  Host–Target 실제 Ethernet, Target 내부 DDS/vCAN, 독립 Thor/Orin 비교를 유지한다.
- Steering/Brake/Drive에 **BMS 논리 vECU**를 추가한다. 상위 status/actual은
  CAN → Zone → Central/Host 경로를 따른다. 로컬 센서 제어는 해당 ECU 안에서 처리한다.
- 차량 관리(VCU 역할)는 Zone 내부의 `vehicle_management`, 구동·제동 배분은
  `control_allocation`, 통신 중계는 `gateway`로 책임을 구분한다.
  별도 VCU 계층/보드를 추가하지 않는다. Central은 요청하고 로컬 주행 허가는 Zone이 판단한다.
- Battery/power plant와 BMS controller를 구분한다. 단순 SOC/전압/전류/온도 모델,
  충전·방전 한계, 프리차지/컨택터 상태와 주행 준비·종료 sequence를 포함한다.
- 핵심 기능의 입력·출력·상태·유효성·고장 반응을 검증한다. 정밀 셀 화학/열화/밸런싱,
  인버터 스위칭/모터 전류 제어, 충전기/DC/DC 회로, 바퀴별 ABS/ESC, body/infotainment는
  상세 구현 범위에서 제외한다. 필요한 전원·열·안정화 가정/연결은 명시한다.
- 기존 0–40 km/h ODD와 classical-first 순서를 유지한다. 전원 lifecycle은 system
  severity와 별개이며 기존 FAIL_SAFE recovery와 Host actual-loss containment를 우회하지 않는다.

<a id="adr-0014-영향"></a>

### 영향

[EV/BMS 설계](../interfaces/ev-power-bms.md)에 역할, lifecycle, semantic interface,
에너지/시간 원칙과 미결정 값을 기록한다. 기존 M1 six-frame codec/receiver 결과는 유지하며
BMS/power wire, Drive 방전 가용량 전달과 DDS status 확장은 **미설계/미구현**이다.
M1은 기존 남은 수용 항목과 EV interface 추가 작업을 구분하고, M2 모델부터 단계적으로 진행한다.
M3 timing, M4 Zone, M5 DDS, M6/M7 plant, M9 diagnostics와 최종 regression 범위를 확장한다.

SYS-COM-003/004와 SYS-PERF-002를 v0.3으로 개정하고 SYS-EV-001–005를 추가한다.
TC-EV-001–005의 Result는 NOT RUN이다. M0 v0.1 검토나 M1 부분 PASS에 소급 포함하지 않는다.

이 ADR은 ADR-0011의 **별도 BMS ECU 제외/충전 fixture만 사용한다는 범위**를 대체한다.
RG-01의 signed torque, 회생/마찰 배분, 실제 출력 기반 에너지와 critical loss 계약은 유지한다.

후속 [ADR-0015 / ZON-01](#adr-0015)로 당시 다중 Zone 검토 후보를
최종 Front/Rear 두 Zone 설계로 채택했다. 차량 관리·배분과 상위 feedback 집계는 Front,
Drive/BMS 연결·검증은 Rear다. 단일 Zone component 검증 후 분리하며 peer protocol은 TBD-15다.
이 ADR의 EV 기능/계층 원칙은 유지하고 당시 단일 Zone 배치를 위 결정으로 확장한다.
다중 Zone runtime/TC-ZON은 NOT RUN이다.

<a id="adr-0014-다음-작은-작업"></a>

### 다음 작은 작업

EV 범위/책임/lifecycle 문서 review → BMS와 power semantic/wire 및 freshness 결정
→ M1 기존 수용 항목과 추가 통신 검증 → M2 actuator + Battery/BMS/power component 모델
→ M4 배분/주행 허가 → M6 Simple Plant → M7 CARLA 순서다.
AUTOSAR/안전 분석은 기존 engineering plan의 작은 pilot/검토로 병행한다.

<a id="adr-0014-설계-근거와-적용-범위"></a>

### 설계 근거와 적용 범위

[NXP 구조 설명](https://community.nxp.com/t5/NXP-Tech-Blog/How-electrification-is-changing-vehicle-architectures/ba-p/1491151)은
물리 Zone과 기능 domain을 구분하며 제어 기능을 별도 ECU, Zone/domain 통합 또는 Central에
배치할 수 있음을 설명한다. [Bosch BMS](https://www.bosch-mobility.com/en/solutions/powertrain/fuel-cell-electric/battery-management-system/)는
셀 감시/배터리 전류 측정과 컨택터 제어를 설명한다. 이를 참고한 StrataDrive의 한 가지
Reference architecture이며 모든 양산차의 공통 ECU 배치나 production safety sequence를 주장하지 않는다.

<a id="adr-0015"></a>

## ADR-0015: Front/Rear 두 논리 Zone

현재 배치: [ADR-0021](#adr-0021). **부분 SUPERSEDED (2026-10-14):** Front의 차량 전체 조정·session·집계 및 Front↔Rear application 경로는 ADR-0021로 대체한다. 두 Zone/담당 Leaf/원천 보존/local 보호는 유지하며 아래 v0.4 내용은 당시 결정 기록이다.

Date: 2026-10-13. Status: **ZON-01 포함 범위·책임 배치 ACCEPTED / 상세 protocol 초안 / runtime PLANNED / 시험 NOT RUN**.
Owner: 학습자(project owner). 근거: 두 Zone 설계와 단일 Zone 동작 확인 후 확장하자는
제안에 대한 사용자의 수용 및 문서 정리·검증·push 요청.
Protocol/물리 parameter의 학습자 review는 PENDING이다.

<a id="adr-0015-문제"></a>

### 문제

단일 Zone은 M1/component 학습에 적합하지만 물리 영역별 gateway와 cross-zone
통신 상실을 학습하지 못한다. Zone을 복제하면 전체 차량의 토크/제동 배분과 power
permission이 중복될 수 있어 기능 owner와 경로를 먼저 정해야 한다.

<a id="adr-0015-결정"></a>

### 결정

- 최종 Reference에 **Front/Rear 두 논리 Zone**을 포함한다. 단일 Zone은 단계적
  component bring-up이며 최종 다중 Zone acceptance를 대신하지 않는다.
- 학습용 packaging 가정은 rear-drive single motor, Front의 Steering/Brake controller,
  Rear의 Drive/BMS controller다. Battery pack은 차체 하부의 등가 모델이며 BMS controller의
  논리 접속 위치를 Rear로 정한다. Aggregate Brake는 차량 전체 마찰제동 압력이고 전륜 전용이 아니다.
- **Front Zone**의 `vehicle_management`와 `control_allocation`을 차량 전체의 단일
  coordinator로 유지한다. Rear는 routed demand/constraint의 validation, CAN dispatch,
  actual/status 수집과 local safety를 맡고 총 차량 요구를 다시 배분하지 않는다.
- Central vehicle/power request → Front; Front↔Rear는 logical Ethernet/DDS;
  각 Zone↔담당 Leaf는 분리된 SocketCAN/vCAN 경로다. VCU 계층이나 별도 보드를 추가하지 않는다.
- Rear Leaf feedback → Rear → Front aggregate/target bridge → Central/Host다.
  Front Leaf feedback도 같은 Front aggregate에서 원천별로 처리한다.
- 각 receiver는 원천/의존 validity·time·identity와 상위 command의 유효 기간을 유지한다.
  Cross-zone heartbeat/새 timestamp로 끊긴 Leaf 또는 상위 request를 fresh하게 만들지 않는다.
- Front/Rear의 독립 loss/partition, local protection, trusted startup/rejoin을 검증한다.
  단일 coordinator redundancy/failover는 이번 범위에 추가하지 않는다.

<a id="adr-0015-대안과-배치-근거"></a>

### 대안과 배치 근거

Vehicle management/allocation을 Central의 별도 기능으로 옮기는 대안도 가능하다.
현재 Central vehicle-level command와 Zone 배분 경계를 재사용하고 한 Zone에서 동작을
확인한 뒤 Rear gateway를 추가하기 위해 Front co-location을 선택한다.
이는 물리 Zone과 차량 domain 기능을 같은 node에 배치하는 프로젝트의 reference 선택이다.
별도 fault-independent safety controller나 모든 양산차의 공통 배치로 해석하지 않는다.

<a id="adr-0015-영향과-남은-결정"></a>

### 영향과 남은 결정

[Zone 분할 설계](../architecture/README.md)에 역할과 routing을 정의한다.
TBD-15에서 **두 Zone 채택/기능 owner는 결정**했으며 peer schema/QoS/queue/clock/skew,
physical model geometry, timeout/rejoin budget은 M4/M5/M6 전까지 남는다.
SYS-ARCH-003 v0.4와 TC-ZON-001–003을 추가하고 기존 COM/EV/fault coverage를 연결한다.
M0 v0.1/단일 Zone 검토와 기존 M1 six-frame 실행 결과는 역사적·부분 증거다.
최종 Reference의 BMS 및 두 Zone runtime/차량 시험은 NOT RUN이다.

ADR-0002의 계층/command/actual 원칙을 유지하며 단일 Zone topology를 확장한다.
ADR-0014와 EV 설계의 **다중 Zone 채택 PENDING** 상태를 이 결정으로 대체한다.
기존 codec/receiver/도구를 제거하거나 복제하지 않는다.

<a id="adr-0015-실행-순서"></a>

### 실행 순서

M1 actuator/EV wire와 남은 수용 항목 → M2 실제 응답/배터리·BMS·power model
→ M4 단일 coordinator 동작 및 Front/Rear 분할 → M5 DDS 경계 → M6/M7 실제 모델
feedback loop → M9 fault/DTC → M12/M13 동일 두 Zone feature의 독립 보드/최종 검증 순서다.

참고: [NXP](https://community.nxp.com/t5/NXP-Tech-Blog/How-electrification-is-changing-vehicle-architectures/ba-p/1491151)는
물리 Zone과 기능 domain을 구분하며 domain 기능의 Zone co-location을 설명한다.

<a id="adr-0016"></a>

## ADR-0016: BMS 상태·Power·Drive constraint의 M1 wire 초안

현재 배치: [ADR-0021](#adr-0021). Producer/vehicle management·배분과 상위 routing 배치는 2026-10-14 ADR-0021로 개정한다. CAN wire/scaling/typed parent/expiry 초안과 당시 시험 결과는 유지한다.

Date: 2026-10-14. Status: **범위 EV-01 / wire·timing PROPOSED / Host DBC·P05 부분 검사 / 학습자 review PENDING**.
Owner: 학습자(project owner). 기존 EV-01/ZON-01과 BMS 규격부터 재개하는 작업 순서를 따른다.
DBC parser/vector 검사와 실제 C++ EV receiver/runtime 채택을 구분한다.

<a id="adr-0016-문제"></a>

### 문제

배터리 관측·제어 한계·power request/actual/permission을 한 validity/주기로 표현하면
cached SOC와 critical 한계의 freshness가 섞인다. BMS 정보의 Front/Rear 중계가
원천 시각을 연장할 수 있으며 기존 Drive의 30 ms 보조 입력 정책과 새 budget도 다르다.

<a id="adr-0016-제안"></a>

### 제안

- BmsPowerRequest, BmsPowerStatus, BmsPowerLimits, BmsBatteryState,
  DriveBatteryLimits, DrivePermission의 6개 frame을 하나의 BMS DBC에 정의한다.
- Critical request/limits는 50 Hz, power status/permission은 100 Hz, 관측 state는 10 Hz로
  구분한다. BMS local battery/model sampling·한계 계산은 첫 SIL에서 50 Hz를 계획한다.
- EV family schema 1을 기존 actuator schema 2와 분리한다. 48/64-byte CAN FD payload와
  독립 P05 Data ID를 쓰고 CRC 29..30/counter 31 및 전체 extension 보호를 유지한다.
- SOC fraction, V/A/°C, pack DC power W를 사용한다. 유효 0과 unknown, sensor group별
  validity/source time, power actual과 주행 permission을 구분한다.
- Front 차량 전체 조정과 Rear routing을 유지한다. DriveBatteryLimits는 BMS 원천
  Sequence/Epoch/Source/Input/causal identity를 보존하며 counter/DataID만 transport별로 바뀐다.
- Request/permission에 parent-bounded expiry를 두고 INIT Enable을 normal-driving grant와
  구분한다. 로컬 보호 command의 origin도 정상 request와 다르게 처리한다.
- Critical source age 50 ms, oldest input age 70 ms, RX threshold 80 ms + monitor/margin
  20 ms를 시작값으로 정의한다. 관측 source/group age 150 ms와 RX unavailable 300 ms는
  비critical 경로다. 양쪽 한계/power의 필요한 source validity는 각각 감시한다.

수치/배치는 프로젝트 초안이며 OEM 표준·실측·물리 안전 budget이 아니다.
상세 표/byte/판정식은 [BMS wire ICD](../interfaces/bms-frame.md)를 따른다.

<a id="adr-0016-대안과-영향"></a>

### 대안과 영향

단일 큰 status는 publication을 줄일 수 있지만 slow observation과 critical gate가 묶인다.
모든 정보를 100 Hz로 보내는 대신 역할/주기를 나누고 CAN 관측과 local sensor cadence도 분리한다.
Drive가 BMS 센서 raw 값으로 한계를 중복 계산하거나 상위 timestamp만 보고 fresh로 수용하지 않는다.

기존 actuator wire/receiver 설정은 변경하지 않는다. EV 연결 전에 Drive auxiliary의 source와
dependency age 설정을 분리하고 20 Hz vehicle state와 speed source 관계를 검증해야 한다.
Power Enable의 INIT/multi-field canonical/deadline 정책은 기존 actuator command 검사를 그대로
재사용할 수 없다. Shared Target clock 시험도 Host–Target 동기화 증거로 확대하지 않는다.

TBD-14의 frame inventory/scaling/flags/DataID와 local timing 시작값을 이 초안으로 구체화한다.
Wire 수용/교차 codec/receiver/vCAN, trusted Epoch/bootstrap/parent correlation, 각 hop clock/budget,
queue/overflow와 학습자 review는 남는다. TBD-12의 sequence/reaction과 TBD-13 모델은 별도다.
기존 요구사항 revision을 변경하지 않고 TC-EV-001/002/004의 M1 부분 증거에 연결한다.

<a id="adr-0016-검증과-다음-단계"></a>

### 검증과 다음 단계

기존 DBC 도구를 12개 frame 검사로 확장하며 EV fixed goldens, canonical/uint64/CRC와
원천 보존을 검사한다. 기존 P05 unit test에 48-byte golden/bit corruption을 추가한다.
전체 TC-EV는 NOT RUN이다. 다음은 BMS 물리/프레임 codec → stateful receiver
→ Drive dependency policy 개정 → 기존 vCAN fixture 확장이다. 모델/permission runtime은 이후다.

후속 구현(2026-10-14): [ADR-0017](#adr-0017)에서 C++ codec/항목별 receiver,
Drive age config 분리와 SocketCAN 변환 unit, 후속 local vCAN 36개 case를 시험했다.
실제 모델/Zone runtime과 wire 최종 수용은 남는다.

<a id="adr-0017"></a>

## ADR-0017: EV/BMS codec와 항목별 수신 유효성

Date: 2026-10-14. Status: **M1 Host 구현·unit/local vCAN 검사 / wire 채택·학습자 review PENDING**.
Owner: 학습자(project owner). [ADR-0016](#adr-0016)의 wire 초안을 구현한다.

<a id="adr-0017-문제와-결정"></a>

### 문제와 결정

BMS 메시지는 여러 센서/한계의 validity를 가진다. Frame이 정상 수신됐다는 이유로 모든
항목의 age를 reset하면 끊긴 충전 한계나 오래된 power 센서가 계속 정상으로 보인다.
전원 요청은 INIT에서도 필요하지만 주행 허가는 원래 요청의 만료를 연장하면 안 된다.

- `interfaces/bms/`에 물리값 codec, 6개 frame의 typed content와 receiver를 둔다.
  기존 actuator schema 2는 유지하며 EV schema 1/48·64 bytes를 별도로 직렬화한다.
  공통 metadata/P05/수신 cursor와 Linux SocketCAN endpoint를 재사용한다.
- Optional field는 known zero와 unknown을 구분한다. Sentinel/validity/reserved/time 관계를
  canonical하게 검사하며 물리 허용 범위는 호출자가 명시한다. Wire 범위는 차량 calibration이 아니다.
- Envelope Sequence/Epoch/Source 검증과 항목별 quality/last-usable RX를 분리한다.
  Partial 메시지는 진단에 수용할 수 있지만 unusable 항목은 제어 view에서 제거한다.
  Observation acquisition/model batch의 진행도 검증한다. Critical timeout/clock rollback은
  latched이며 외부 trusted 새 Epoch/INIT로만 재시작한다.
- NormalPath power request와 AllowNormal permission은 수신 CAN과 독립적으로 검증한
  `BmsParentContext`가 필요하다. Parent identity/age/deadline을 대조하고 동일 원천의
  만료 연장을 금지한다. INIT Enable, 실제 HV readiness, normal-driving permission을 구분한다.
- Drive auxiliary의 source age와 capability input age 설정을 분리한다. 기본값 30 ms를
  유지하고 EV input age 70 ms는 명시적 opt-in으로 시험한다. Torque/source budget은 유지한다.
- 기존 `actuator_demo`/DBC checker에 EV를 확장한다. BMS 단위 시험은 한 domain 파일에
  모으며 SocketCAN adapter 시험도 기존 파일에 추가한다.

<a id="adr-0017-검증-범위와-남은-일"></a>

### 검증 범위와 남은 일

Normal·ASan/UBSan 각각 unit 129개, 전체 12개 DBC와 C++ payload 36개를 검사했다.
Unit의 항목별 timeout/expiry는 수동 clock 시험이며 SocketCAN 변환은 native frame 단위 시험이다.
후속 local vCAN에서는 독립 process의 wall-time timeout/expiry도 검사했다.
실행 명령과 범위는 [BMS 학습 기록](../learning/communication-guide.md)에 둔다.
TC-EV-001/002/004의 부분 증거에 연결하며 전체 system Result는 NOT RUN이다.

후속 작업에서 기존 vCAN fixture의 EV TX/RX/session·parent·relay 36개 case를 시험했다.
Trusted allowlist를 harness stdin으로 제공하며 CAN causal key는 조회에만 쓴다.
Context를 전달하는 실제 coordinator/DDS protocol과 각 hop budget은 TBD-14/15다.
P05와 identity 대조는 인증 기능이 아니다.
BMS limit 산출, power response, local protection과 Drive의 torque/limits/permission/실제 HV
통합 gate는 M2 이후 구현한다. 셀 전압·온도 극값은 로컬 모델 계약에 포함하며 이번 wire를 늘리지 않는다.
TBD-12/13/14와 학습자의 review를 완료 처리하지 않는다.

<a id="adr-0018"></a>

## ADR-0018: 영속 Epoch 발급과 수신 연속성 오류

현재 배치: [ADR-0021](#adr-0021). Epoch owner/배치는 2026-10-14 ADR-0021의 Central session으로 개정하고 library를 central/session으로 이동했다. 아래 zone/session/Front 설명은 당시 배치이며 발급 동작/record/FIFO/시험 결과는 유지한다.

Date: 2026-10-14. Status: **M1 local 구현·검사 / wire 채택·학습자 review PENDING**.
Owner: project owner. SYS-COM-002/003/004, SYS-SAFE-002와 EV 원천/재시작 계약에 연결한다.

<a id="adr-0018-문제와-결정"></a>

### 문제와 결정

Fixture의 고정 Epoch만으로는 프로세스가 재시작한 뒤 이전 세션을 구분하는 발급 책임을
검증하지 못한다. SocketCAN dispatch budget만으로 application queue의 용량·overflow 정책도
정해지지 않는다. Continuity가 끊긴 뒤 새 packet으로 정상 수용을 재개하면 손실을 숨길 수 있다.

- `zone/session/EpochStore`를 Linux 로컬 startup 발급기로 구현한다. 최종 발급 owner는
  Front session coordinator이며 M1 harness가 이 library를 호출한다. Vehicle management/
  DDS handshake와 정상 주행의 physical health gate는 M4/M5의 별도 기능이다.
- 새 namespace의 explicit initialize만 저장소를 만든다. 정상 issue는 기존 record/lock을
  요구하고 손상·상실·busy·I/O 오류·uint32 소진 시 실패한다. 초기 record 0 이후 1부터
  발급하며 wrap/reset하지 않는다. 사용되지 못한 발급 번호도 다음 실행에서 건너뛴다.
- Stable lock file의 nonblocking `flock`, 임시 record의 file fsync → atomic rename →
  directory fsync를 사용하고 commit 이후에만 번호를 반환한다. 파일은 magic/version,
  uint32 Epoch와 complement를 담는다. 삭제/backup rollback은 자동 복구하지 않는다.
- Domain과 독립인 fixed-capacity FIFO를 common에 둔다. M1 fixture capacity 32,
  cycle당 ingress 8/dispatch 8, polling sleep 1 ms다. Queue full/kernel drop count 변화는
  backlog를 버리고 latch한다. 새 trusted Epoch로 queue/receiver를 초기화한다.
- Receiver의 ContinuityError는 current sample을 닫고 raw 진단 history를 보존한다.
  늦은 정상 메시지로 해제하지 않는다. Kernel-drop 복구는 깨끗한 새 socket도 필요하다.
  통신 monitor 상태를 차량 FAIL_SAFE/물리 보호 출력과 같은 것으로 표시하지 않는다.
- 재시작 시험에서 발견한 이전 Epoch의 P05 state 오염을 수정한다. CRC/canonical decode로
  확인한 다른 Epoch의 메시지는 현재 P05 check state에 반영하지 않는다. 기존 P05 wire와
  정상 같은-Epoch의 transport 검사 정책은 유지한다.

<a id="adr-0018-증거와-범위"></a>

### 증거와 범위

Unit은 저장소 동시 프로세스 발급/손상/상실/소진/lock/I/O failure, FIFO/latch,
12개 receiver의 continuity loss와 새 Epoch·old counter를 검사한다.
기존 CAN runner는 실제 발급 번호를 trusted CLI/stdin으로 제공한다. Local vCAN은
기존 63개 + application/kernel overflow 24개 + process/session restart 2개를 검사한다.
Kernel fixture는 SO_RCVBUF 축소·ingress 중단·burst 뒤 실제 SO_RXQ_OVFL >0을 확인한다.
가상의 drop 값을 SocketCAN 결과로 표시하지 않는다.

실행 기록과 M1 technical exit 항목은 [M1 session/queue 안내](../learning/communication-guide.md)에 둔다.
Physical power-cut, storage rollback 방지, 실제 Target scheduling·차량 response, Front/Rear DDS,
full TC-COM/TC-SAFE/TC-EV는 별도다. Wire/학습자의 이해 review를 자동 PASS로 처리하지 않는다.

근거: [Linux fsync](https://man7.org/linux/man-pages/man2/fsync.2.html)의 directory 동기화,
[flock](https://man7.org/linux/man-pages/man2/flock.2.html)의 lock lifetime/nonblocking semantics,
[socket](https://man7.org/linux/man-pages/man7/socket.7.html)의 SO_RCVBUF/SO_RXQ_OVFL을 참고했다.

<a id="adr-0019"></a>

## ADR-0019: 첫 조향 응답 component 모델

현재 배치: [ADR-0021](#adr-0021). 후속 vehicle management/allocation/session/feedback owner와 Zone routing은 2026-10-14 ADR-0021을 따른다. 이 component 모델의 동작과 시험 설정은 유지한다.

Date: 2026-10-14. Status: **Host functional SIL 부분 구현 / 학습자 review PENDING**.
Owner: project owner. TBD-02/03/04, IF-CAN-STEERING, STEERING_COMMAND_LOSS에 연결한다.

후속 구조 변경: [ADR-0032](#adr-0032)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

<a id="adr-0019-결정"></a>

### 결정

`vecu/steering/SteeringActuator`가 기존 Command receiver를 소유하고, 외부 monotonic clock으로
control tick을 실행한다. 수신 codec/receiver는 `interfaces/steering/`에 유지한다.
동일 thread에서 command 검증 → command snapshot → dynamics → Actual/P05를 수행한다.
OS task 분할/독립 watchdog/Target scheduling은 M3 이후 검토한다.

첫 모델은 control tick에서 포착한 목표의 고정 지연, 방향 대칭 rate limit, 물리 각도 saturation을
결합한다. 목표 변경을 bounded delay FIFO에 보관하고, 같은 목표의 반복 수신은 freshness만
갱신한다. Delay 경계가 두 tick 사이에 있으면 경계 뒤 시간에 대해서만 새 목표로 움직인다.
Tick의 최소 간격과 delay 상한을 제한해 128-entry FIFO에 최대 101개 목표 변경이 들어온다.
동적 할당은 control 경로에서 사용하지 않는다. 실제 RTOS 실행 보장은 아니다.

수신 허용 범위와 물리 모델 한계는 별개다. 허용 범위 밖 command는 기존 receiver가 거부한다.
허용된 목표가 물리 한계보다 크면 모델 target만 saturation한다. Normal/Degraded 입력 상태를
Actual에 전달하고 Actual 값은 dynamics의 결과다. CausalSequence는 기존 wire 계약대로
마지막 수용 Command 번호이며 현재 움직임을 만든 delayed target의 번호라는 뜻은 아니다.

<a id="adr-0019-시험용-parameter와-보호-정책"></a>

### 시험용 parameter와 보호 정책

Fixture는 Command ±0.5 rad, model ±0.3 rad, 초기 0 rad, 최대 1 rad/s, 지연 50 ms,
control/publication 최소 간격 10 ms, 허용 tick gap 30 ms를 사용한다.
Source age 30 ms와 valid-RX timeout 80 ms는 기존 Steering receiver 후보값이다.
이 값은 OEM calibration이나 차량의 보호 응답 수치로 채택하지 않는다.
교육 그래프의 deg 예제와 이 SIL fixture의 rad 설정은 서로 다른 예제다.

Command source expiry, receiver timeout, queue continuity loss 또는 control deadline 위반 시
pending target을 취소하고 현재 modeled angle을 hold한다. Tick에서 source freshness를 먼저
검사하므로 interval 끝에서 stale이면 그 interval의 이동 전체를 생략하는 보수적 sampled 정책이다.
수신 함수도 이전 snapshot의 expiry를 새 command 전에 확인한다. 늦은 fresh command가
관측 사이의 expiry를 숨기거나 latched local FAIL_SAFE를 해제하지 못한다.
새 trusted Epoch와 비감소 clock으로만 session을 재시작하며 physical angle은 보존한다.
실차에서 hold가 안전한지, 차량 감속/전원 정책과 어떻게 결합할지는 TBD-03/06 후속 검토다.

Actual은 새 control sample 시각/독립 sequence/P05를 갖는다. 수용 Command가 있으면
hold angle도 유효 Actual이지만 FAIL_SAFE + LocalProtection으로 표시한다.
수용 Command가 없는 startup timeout의 Actual은 unavailable이며 causal=0은 진단용이다.
Clock 역행 후에는 신뢰할 새 source time이 없으므로 publication을 중단한다.
Missed deadline을 여러 tick으로 backfill하지 않는다. Actual sequence 소진 시 wrap하지 않는다.

<a id="adr-0019-증거와-후속"></a>

### 증거와 후속

[M2 조향 실행 안내](../learning/vehicle-models-guide.md)에 단위 시험과 독립 세 process
Command TX → model → Actual RX vCAN 기록을 둔다. 기존 통신 runner/executable과
`actuator_demo steering-model`을 확장하며 feature별 executable을 추가하지 않는다.

이 모델은 inertia/friction/acceleration/noise/센서 고장/actuator jam 검출, vehicle closed-loop,
Front/Rear coordinator 및 DDS를 구현하지 않는다. Tracking fault threshold/dwell과 실제 local
보호 gate는 별도다. 기존 system TC를 PASS로 바꾸지 않는다.

<a id="adr-0020"></a>

## ADR-0020: 첫 마찰제동 압력 응답 모델

현재 배치: [ADR-0021](#adr-0021). 후속 차량 전체 회생 배분/session/feedback owner는 2026-10-14 ADR-0021의 Central component다. 아래 Front 배분 언급은 당시 배치이며 Brake 모델/보호 fixture는 유지한다.

Date: 2026-10-14. Status: **Host functional SIL 부분 구현 / 학습자 review PENDING**.
Owner: project owner. IF-CAN-BRAKE, BRAKE_COMMAND_LOSS, TBD-02/03/04/06에 연결한다.

후속 구조 변경: [ADR-0032](#adr-0032)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

<a id="adr-0020-결정"></a>

### 결정

`vecu/brake/BrakeActuator`가 기존 Brake Command receiver를 소유하고 외부 monotonic clock으로
정상 압력 응답과 local 보호를 계산한다. Codec/receiver는 `interfaces/brake/`에 유지한다.
Control/publication 최소 간격 10 ms, single-owner 호출, bounded delay FIFO와 독립 Actual/P05
방식은 [Steering 첫 모델](#adr-0019)을 따른다.
모델은 물리 압력 상태를 유지하며 Command를 Actual로 복사하지 않는다.

Fixture는 Command 0..2 MPa, model 0..1.5 MPa, 초기 0 Pa, 가압 5 MPa/s, 감압 10 MPa/s,
정상 목표 변경의 지연 50 ms, control gap 상한 30 ms를 사용한다.
Source age 30 ms/RX timeout 80 ms는 기존 receiver 설정이다. 이 수치는 OEM calibration이 아니다.
유효한 0 Pa는 해제 목표다. Unavailable/CRC 오류/범위 밖 command를 해제로 바꾸지 않는다.
같은 목표를 반복 수신하면 freshness만 갱신하며 물리 지연을 다시 시작하지 않는다.
정상 가압과 정상 해제에 같은 delay를 적용하는 첫 단순 모델이다.

<a id="adr-0020-local-fault-정책"></a>

### local fault 정책

Command source expiry, receiver timeout, 수신 continuity loss 또는 control deadline 위반을
감지하면 normal pending target을 폐기하고 FAIL_SAFE/LocalProtection을 latch한다.
최초 fault 시각의 `max(current_pressure, fault_pressure_floor)`를 보호 목표로 고정한다.
Fixture의 floor는 1 MPa다. 이미 높은 압력을 이 floor로 낮추지 않는다.
보호 목표는 정상 지연 FIFO를 우회하지만 실제 압력은 가압 rate를 지키며 접근한다.
Fault를 관측한 시각부터만 보호 이동을 적분하며 즉시 압력 jump나 과거 interval backfill은 없다.
이후 tick의 반복 fault 관측/늦은 release command가 목표나 시작 시각을 재설정하지 못한다.

Deadline을 놓친 interval에서는 압력 이동을 생략한다. 이후 clock/호출 간격이 정상이라면
local protection을 계속 계산한다. Clock 역행 시에는 physics/publication을 중단한다.
복구는 더 큰 trusted Epoch와 비감소 clock을 요구하며 기존 physical pressure를 보존한다.
보호 pressure가 유효 Actual이어도 정상 주행 가능을 의미하지 않는다.
수용 Command가 없는 startup timeout은 causal context가 없으므로 진단 unavailable Actual을
발행한다. 내부 modeled pressure/protection은 계속 유지하며 0 Pa로 의미를 바꾸지 않는다.
이 제한은 현재 wire의 causal 표현에 따른 첫 모델 정책이다.

이 retain-or-increase 정책/floor는 검증할 SIL 선택이다. 차량 정지/타이어 lock 방지나 안전한
제동 압력의 보장은 아니며 차량 상태·ABS·arbitration·위험 분석과 결합한 값은 TBD-03/06이다.

<a id="adr-0020-학습과-증거"></a>

### 학습과 증거

[Brake 모델 학습·실행 안내](../learning/vehicle-models-guide.md)에 압력/토크의 차이, 단위,
가압/감압 계산, 0/unavailable, metadata와 실행 결과를 둔다.
기존 integration participant의 model loop와 runner를 Steering/Brake가 공유한다.
별도 feature executable은 만들지 않고 `actuator_demo brake-model`을 추가한다.

Pressure→wheel friction torque calibration과 차량 감속은 Plant 단계다.
Drive 회생 응답/Front 배분, hydraulic sensor/valve/pump/ABS, stuck/leak response detector,
독립 watchdog/Target timing, 차량 보호/closed-loop 및 full system TC는 후속이다.
공식 참고: [MathWorks Disc Brake](https://www.mathworks.com/help/sdl/ref/discbrake.html)는
pressure와 마찰·피스톤·디스크 geometry의 torque 관계를 설명하고,
[Bosch iBooster](https://www.bosch-mobility.com/en/solutions/driving-safety/ibooster/)는
전동 booster의 master-cylinder 압력 생성 및 자동 압력 제어 사례다. Fixture 수치의 출처는 아니다.

<a id="adr-0021"></a>

## ADR-0021: Central 조정 기능과 대등한 Front/Rear Zone

Date: 2026-10-14. Status: **배치 변경 ACCEPTED / protocol·runtime PLANNED / system 시험 NOT RUN**.
Owner: project owner. 사용자 요청으로 Front의 차량 전체 조정 기능을 Central의 별도
component로 이동하고 Central↔Front, Central↔Rear를 독립 application 경로로 채택한다.

<a id="adr-0021-변경-이유와-범위"></a>

### 변경 이유와 범위

ADR-0015의 Front는 Zone gateway와 VCU 역할을 함께 맡았다. 차량 전체 요구 배분과
지역별 연결 책임을 더 명확히 학습하기 위해 이제 둘을 분리한다.
**Front/Rear 두 Zone, 담당 Leaf, 단일 조정 owner, Central–Zone–Leaf 계층은 유지한다.**
Front 경유 Rear command/status, Front vehicle management/allocation/session/Host bridge 배치만
이 결정으로 대체한다. M0 문서 결과와 기존 M1/M2 실행 결과를 새 topology 증거로 소급하지 않는다.

<a id="adr-0021-결정"></a>

### 결정

- Central의 별도 `vehicle_management`가 전원 lifecycle·정상 주행 허가를 판단한다.
- Central의 별도 `control_allocation`이 Controller의 vehicle-level 요구를 한 번만 배분한다.
  ADAS planner/controller와 VCU 기능의 interface·validation·fault 책임은 분리한다.
- Central `session`이 trusted Epoch/INIT를 소유한다. 기존 Linux EpochStore library는 재사용한다.
  현재 M1 harness의 local 발급 검사는 유지하고 실제 coordinator/배포 경로는 M4/M5에 구현한다.
- Central `feedback_bridge`가 두 Zone의 per-source actual/EV status를 집계해 Central consumer와
  Host에 전달한다. 집계 주기나 다른 Zone heartbeat로 누락 원천의 age/validity를 덮지 않는다.
- Front는 Steering/aggregate Brake, Rear는 Drive/BMS의 gateway·validation·monitor·local protection을
  담당한다. 두 Zone은 Central로 직접 status를 보고하고 각자 scoped command/session을 받는다.
- 정상 제어/feedback/INIT 경로에 Front↔Rear application relay를 요구하지 않는다.
  향후 peer service는 별도 계약과 근거가 필요하다. Ethernet switch/backbone의 물리 forwarding과
  application 배치가 같은 개념은 아니다. 물리 배선/가상 network 방식은 TBD-05/15다.
- Zone/Leaf는 Central 응답 없이 local protection을 계속 수행한다. 하나의 Zone·link 정지가
  다른 Zone의 link failure를 뜻하지 않지만 차량 전체 normal gate는 원천 상실을 보고 FAIL_SAFE로 간다.
  Central/coordinator redundancy/failover와 실제 보호 출력은 별도 범위/TBD다.

<a id="adr-0021-interface와-요구-개정"></a>

### Interface와 요구 개정

| 이전 | 현재 |
| --- | --- |
| IF-DDS-VEHICLE-CMD: Controller→Front | IF-CENTRAL-VEHICLE-REQUEST: Controller→Central allocation |
| IF-DDS-POWER-REQUEST: Central→Front | IF-CENTRAL-POWER-REQUEST: lifecycle requester→Central vehicle management |
| Front→Rear command / Rear→Front status / Front↔Rear session | Central↔Front 및 Central↔Rear 독립 command/status/session |
| Front aggregate→Host | 각 Zone→Central feedback bridge→Host |

기존 IF-DDS-REAR-CMD/STATUS/SESSION ID는 유지하고 endpoint 의미를 개정한다.
대칭 Front CMD/STATUS/SESSION ID를 추가한다. IDL/배포 schema가 아직 없으므로 CAN wire 변경은 없다.
SYS-ARCH-003, SYS-CTRL-008, SYS-SAFE-005, SYS-EV-003을 **v0.5**로 개정한다.
기존 requirement 수/ID와 29개 TC는 유지하며 owner/경로/변형을 변경한다.
100 ms 검출 상한, per-source freshness/parent expiry, local 보호와 actual-only plant gate는 유지한다.

<a id="adr-0021-검증과-후속"></a>

### 검증과 후속

[현재 Zone 계약](../architecture/README.md), [interface 목록](../interfaces/README.md),
[요구 개정](../requirements/system-requirements.md), profile과 traceability/scenario/TC를 일치시킨다.
이번 변경은 문서/설계 데이터와 owner 설명의 변경이다. 이미 구현한 CAN codecs/receivers와
Steering/Brake component 모델, BMS typed parent 검사는 그대로 재사용한다.
M4는 Central 단일 coordinator + 각 Zone routing/local monitor, M5는 독립 DDS 링크·trusted INIT·
Host bridge, M6/M7는 physical model/closed-loop를 검증한다. Runtime/system Result는 NOT RUN이다.

참고: [Bosch Zone ECU](https://www.bosch-mobility.com/en/solutions/control-units/zone-ecu/)와
[NXP zonal architecture](https://www.nxp.com/company/about-nxp/smarter-world-blog/BL-HOW-ZONAL-EE-ARCHITECTURES)는
중앙 기능과 지역별 연결 계층을 설명한다. 이 배치는 StrataDrive의 선택이며 모든 차량의
동일한 물리 topology나 안전성/고장 독립성을 보장하는 규칙으로 해석하지 않는다.

<a id="adr-0022"></a>

## ADR-0022: Leaf vECU의 Classic 개발 체계와 SIL 모델 경계

Date: 2026-10-14. Status: **설계·학습 방향 ACCEPTED / Host OS 파일럿 구현 / RTE/BSW·Target pilot NOT RUN**.
후속 2026-10-18: [ADR-0040](#adr-0040)에서 Trampoline POSIX Steering OS 파일럿을 구현했다.
아래는 최초 결정 당시의 계획이며 실제 RTE/BSW/Target 채택은 여전히 후속이다.

Owner: project owner. Leaf vECU의 ECU 소프트웨어는 AUTOSAR Classic의 개발 개념으로
설계하고 Steering부터 적용한다. 실제 Classic stack의 채택은 pilot 결과로 별도 결정한다.

후속 2026-10-16: [ADR-0032](#adr-0032)에서 ECU와 SIL 실행 코드를 분리했다.
현재 SteeringActuator는 `prepare/complete`로 입력·목표/보호·Actual을 처리하고,
[SteeringSil](../../simulation/steering/steering_sil.cpp)의 `tick`이 외부 물리 진행·센서 취득을 연결한다.
아래 표는 이 결정 당시의 대응 초안이며 실제 Runnable/Task·RTE/BSW pilot은 여전히 후속이다.

<a id="adr-0022-배경과-결정"></a>

### 배경과 결정

M1은 CAN 계약·수신 검증·P05를, M2는 Steering/Brake의 첫 functional SIL 응답을 구현했다.
결정 당시 C++ class는 ECU 판단과 물리 응답 계산을 함께 실행했다. Classic 설계를 정리할 때는
기능 소프트웨어, 통신·OS 서비스, SIL에서 대신하는 물리 장치의 책임을 구분해야 한다.

- Leaf의 명령 처리·로컬 상태/보호 판단·출력 결정·상태 보고를 SWC/Port/Interface와
  Runnable/Event로 설계한다. Runnable의 OS Task mapping은 별도 산출물로 정의한다.
- Steering 한 경로의 설계와 실행을 확인한 뒤 Brake/Drive/BMS로 확장한다.
  C++ class 하나를 SWC 하나로 자동 대응시키거나 기능마다 SWC를 추가하지 않는다.
- 실제 조향각·압력·torque 변화, battery 에너지·센서·컨택터 응답은 SIL 물리 모델의 책임이다.
  ECU 출력 요구 → 물리 모델 → 관측 actual 경계를 정의한다. 실제 RTE/BSW 도입 전에도
  이 의미 경계를 설계·시험할 수 있다. 물리 모델을 production ECU 제어 로직으로 간주하지 않는다.
- 첫 모델의 delay/rate/saturation, protection 출력·응답, source/sequence/Epoch/validity와
  actual-only feedback 계약을 유지한다. 모델 분리로 보호 요구나 실제 반응을 생략하지 않는다.
- Application↔RTE↔BSW와 OS의 책임을 학습하며 ARXML·generator·stack의 호환성을
  확인한다. 수작업 adapter, Linux 실행 또는 P05 library만으로 Classic 통합 완료를 표시하지 않는다.

Classic의 Application/RTE/BSW 구조와 Methodology는 [AUTOSAR 공식 설명](https://www.autosar.org/standards/classic-platform/),
SWC 설계는 [R25-11 SW-C and System Modeling Guide](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_TR_SWCModelingGuide.pdf),
Runnable/OS mapping은 [R25-11 RTE Requirements](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_RS_RTE.pdf)를 참고한다.
아래 대응은 StrataDrive의 설계 초안이며 생성 도구로 검증한 AUTOSAR 설정이 아니다.

<a id="adr-0022-steering부터-적용할-경계"></a>

### Steering부터 적용할 경계

| 결정 당시 구현 | Classic 설계에서 정리할 책임 / 후속 |
| --- | --- |
| `SteeringReceiver`와 `SteeringActuator::receive` | CAN decode/P05와 application의 Epoch·freshness·mode·range 검사 경계; accepted command Port와 reject/health 의미 정의 |
| `SteeringActuator::start_session` | trusted INIT 입력과 상태 초기화; Linux harness가 제공하는 session을 실제 startup/rejoin 경로에 어떻게 연결할지 정의 |
| `SteeringActuator::tick`의 monitor·목표 선택 | 주기 Runnable 후보: command snapshot, expiry/continuity/deadline 검사, normal/protection 출력 선택 |
| `move`/`advance`와 delayed demand FIFO | SIL 물리 응답 모델; 목표 입력과 modeled angle 출력, time/초기값/한계/fault policy를 명시 |
| `tick`의 Actual 생성·P05와 SocketCAN endpoint | 관측 actual/health Port와 통신 adapter를 구분; simulation 관측을 실제 sensor feedback과 혼동하지 않음 |
| 외부 clock과 single-owner 호출 | TimingEvent/Task mapping 초안의 검증 환경; logical 10 ms와 실제 OS scheduling을 구분하고 M3에 측정 |

현재 코드는 [Steering ECU 구현](../../vecu/steering/steering_actuator.cpp),
[수신부](../../interfaces/steering/steering_receiver.hpp),
[M2 모델 시험](../learning/vehicle-models-guide.md)이다. 이번 결정은 코드 이동이나 동작 변경을 포함하지 않는다.
SWC 수/Port type/Runnable 순서·동시성, actual sensor schema, RTE/BSW 연결은 후속 상세 설계다.
당시 `tick`은 여러 책임을 함께 실행했다. 후속 phase API 분리 뒤에도 위 행별 독립 Runnable이 이미 존재한다고 보지 않는다.

<a id="adr-0022-다른-계층과-기술-선택"></a>

### 다른 계층과 기술 선택

[ADR-0021](#adr-0021)의 Central 단일 조정 기능과
대등한 Front/Rear Zone, 담당 Leaf, CAN FD 계약과 피드백 경로를 유지한다.
Central/Zone의 Linux 구성을 Classic 또는 Adaptive 적용으로 표시하지 않는다.
QNX 전환이나 Adaptive stack 도입은 이번 결정에 포함하지 않는다.

Central–Zone의 기본 통신 계획은 DDS이며 Zenoh를 TBD-05의 비교 후보로 추가한다.
M4에 같은 의미 계약·입력 부하·단절/재연결 조건으로 비교하고 M5 runtime 착수 전에
채택 ADR과 schema/ICD/배포/시험 영향을 기록한다. 비교 활동은 PLANNED이며 Zenoh 채택은 미결정이다.
기존 IF-DDS 이름과 의미 계약을 유지하고 transport 선택만으로 freshness/Epoch/local protection을 대체하지 않는다.

<a id="adr-0022-실행-순서와-검토-근거"></a>

### 실행 순서와 검토 근거

1. M2의 Drive/Battery/BMS/Power 구현과 함께 Steering의 입출력·기능/물리 모델 경계를 정리한다.
2. Steering의 SWC/Port/Runnable/Event 및 Task mapping을 작성하고 기존 정상·fault 시험에 연결한다.
3. M2–M4의 작은 pilot에서 호환되는 release/ARXML/RTE/BSW/OS/virtual target을 선정한다.
   [도입 절차](../development-guide.md)를 따라 설정·생성·build·I/O 실행을 기록한다.
4. 도구·license·Host/Jetson 호환성 근거로 stack의 채택·보류를 결정한다.
   이후 Leaf 확장과 코드 분리는 각 변경의 정상·timeout·invalid input·restart 회귀로 확인한다.

SYS 요구사항·CAN wire·32개 requirement/29개 system TC의 수용 조건은 이번 결정으로 바꾸지 않는다.
기존 Host unit/vCAN 결과는 유지하며 Classic pilot, Target timing과 full vehicle TC는 NOT RUN이다.
학습자의 설계 설명·직접 재현 review는 PENDING이다.

<a id="adr-0023"></a>

## ADR-0023: 첫 Drive torque 응답과 ECU·물리 모델 분리

Date: 2026-10-15. Status: **Host functional SIL component 구현 / 학습자 review PENDING**.
TBD-02/03/04/13, IF-CAN-DRIVE와 DRIVE_COMMAND_LOSS의 부분 검증에 연결한다.

후속 구조 변경: [ADR-0032](#adr-0032)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

<a id="adr-0023-결정과-범위"></a>

### 결정과 범위

[ADR-0022](#adr-0022)에 따라 두 책임을 별도 모듈로 둔다.

- `vecu/drive/DriveActuator`: 기존 DriveReceiver, trusted session, 명령 수용·freshness·local fault,
  정상/zero target 선택, Actual metadata/P05를 맡는 ECU 소프트웨어의 부분 구현.
- `simulation/drive/TorqueResponse`: 목표 torque의 delay, signed rate/물리 한계와 zero-target 응답.
  CAN/Epoch/permission/OS에 의존하지 않는 SIL 물리 모델이다.

이 adapter는 **독립 torque 응답 fixture 전용**이다. 차량 운행용 Drive runtime이 아니다.
BMS charge/discharge power limit, drive permission, 실제 local HV, wheel speed와 효율을
아직 연결하지 않았다. Command 수용이나 `NORMAL` stream 상태로 전원 준비·정상 주행 허가를
선언하지 않는다. Wheel speed와 regen capability는 unavailable / InputsInvalid로 보낸다.
고정 음수 torque 한계는 시험용 물리 envelope이며 배터리가 충전을 수용한다는 근거가 아니다.
실제 Drive 통합에서는 [EV-01의 local gate](../interfaces/ev-power-bms.md#한계-freshness와-보호)가 필수다.

수신 command와 실제 torque는 aggregate driven-wheel 기준이다. 전진 구동 양수·회생 음수이며
후진, motor 전류/전압, 인버터 PWM, 회수 에너지와 차량 감속을 이번 모델에서 계산하지 않는다.
현재 control 경로의 rate/saturation은 응답 근사이며 PID/PI/FOC 제어기의 구현이 아니다.
차량 속도 제어는 M8의 Central Controller, 회생/마찰 배분은 M4의 Central allocation이다.
상세 motor current loop는 현재 확정 범위가 아닌 별도 확장이다.

<a id="adr-0023-응답과-보호"></a>

### 응답과 보호

Fixture: command -300..500 Nm, physical -200..300 Nm, 초기 0 Nm,
normal rate 1000 Nm/s, 보호 zero rate 2000 Nm/s, delay 50 ms.
Control 최소 간격 10 ms, 허용 gap 30 ms, source age 30 ms, valid-RX timeout 80 ms다.
이 값은 경계를 관측하기 위한 시험 설정이며 OEM calibration/차량 보호 deadline이 아니다.

같은 목표의 반복 수신은 source freshness만 갱신한다. 변경 목표는 고유 due를 가진다.
고정 128-entry FIFO에 보관하며 adapter의 delay<=100 periods 제한으로 정상 tick에서
최대 101개를 보관한다. Due 사이를 나누어 실제 경과 시간에 rate를 적용한다.

Source expiry/timeout, continuity loss 또는 control gap 위반에서 대기 목표를 취소하고
zero target을 선택한다. Normal delay를 우회하지만 actual은 zero rate로만 0에 접근한다.
부호 반전·overshoot 없이 0에서 멈추고 반복 fault 관측으로 ramp 시작을 미루지 않는다.
유효한 정상 0 command는 normal delay/rate를 사용하므로 이 보호 동작과 구분한다.
보호 검출 이전의 미관측 interval은 hold하며 보호 운동을 검출 시각 이전으로 소급하지 않는다.
Missed tick 구간도 hold하고 다음 정상 간격부터 zero ramp를 진행한다.
Clock 역행은 물리 갱신·publication을 중단한다. 회복에는 새 trusted Epoch가 필요하다.
재시작은 physical torque를 유지하고 INIT에서 zero target을 사용한다.

Actual은 독립 control source/sequence/P05와 마지막 수용 Command의 CausalSequence를 갖는다.
Startup에서 수용 Command가 없는 timeout은 torque unavailable이며 causal=0은 진단용이다.
통신 검출 상한과 actual torque 해소 시간을 구분한다. Fixture에서 300 Nm는 보호 시작 후
150 ms, -200 Nm는 100 ms의 정상 tick 경과가 필요하지만 이 값을 system deadline으로 채택하지 않는다.

<a id="adr-0023-검증과-후속"></a>

### 검증과 후속

[실행·학습 안내](../learning/vehicle-models-guide.md)에 정상 양·음 saturation/전환/0 command,
두 부호의 loss zero ramp, late frame/restart/clock/deadline, bounded history의 시험을 기록한다.
기존 TX/RX/model runner와 `actuator_demo drive-model`을 확장하고 별도 실행 프로그램은 추가하지 않는다.
CAN ID/layout/P05와 기존 requirement/TC의 수용 기준은 유지한다.
Actual 값은 물리 모델의 결과이며 command echo가 아니다.
Classic SWC/Runnable/Task 대응은 설계 후보이고 ARXML/RTE/BSW pilot은 NOT RUN이다.
BMS/Power 모델·원천 검증→실제 local gate·capability 계산→Central 배분/차량 closed-loop 순으로 연결한다.

<a id="adr-0024"></a>

## ADR-0024: 첫 Battery 에너지·전기·온도·관측 모델

Date: 2026-10-15. Status: **Host functional SIL component 구현 / 학습자 review PENDING**.
TBD-02/04/13, IF-MODEL-BMS, SYS-EV-005의 부분 검증이다. Full TC-EV-005는 NOT RUN이다.

<a id="adr-0024-결정과-물리-경계"></a>

### 결정과 물리 경계

`simulation/battery/BatteryModel`이 한 simulation clock에서 chemical energy/SOC와
등가 pack 전기·온도 상태를 소유한다. BMS controller와 CAN 통신은 이 모듈에 넣지 않는다.
실제 차량용 calibration, 전하량 추정기, 셀별 chemistry/열화/balancing은 구현하지 않는다.
Pack 전압은 컨택터 뒤 Drive 자체 HV bus의 관측이 아니다. 이 모델이 전원 READY를 선언하지 않는다.

입력은 명시적 interval의 **실제 traction branch DC power와 별도 auxiliary load**다.
Motor/inverter 변환 후 battery 쪽 DC branch를 기준으로 traction power는 방전 양수·반환 음수다.
Wheel torque·speed에서 이 DC power를 산출하는 coupling은 후속이다. Command/허용 limit나
마찰제동을 적분하지 않는다. 반대 부호의 DC 입력 시험만으로 회생 에너지 검증을 주장하지 않는다.

첫 모델은 constant OCV + 저항의 Rint 근사와 lumped thermal model을 사용한다.
고정 OCV 가정에서 `E = Voc × Q`이므로 `SOC = E / capacity_j`가 전하 비율과 일치한다.
가변 OCV/온도별 parameter/RC polarization이나 실차 SOC 추정으로 일반화하지 않는다.
실제 equivalent-circuit 모델은 OCV/저항·capacity의 SOC/온도 의존성을 다룬다
([공식 모델 설명](https://www.mathworks.com/help/simscape-battery/ref/batteryequivalentcircuit.html)).
전하량 기반 SOC 추정은 [Coulomb counting 설명](https://www.mathworks.com/help/simscape-battery/ref/socestimatorcoulombcountingvariablecapacity.html)을 참고한다.

`Pterminal = Ptraction_dc + Paux`, `Vterminal = Voc - I×R`와 `Pterminal = Vterminal×I`를 풀고
`dE/dt = -Voc×I = -(Pterminal + I²R)`로 chemical energy를 갱신한다.
유입/유출 DC·보조 부하·내부 저항 손실을 별도로 누적하며 inverter 손실을 여기서 다시 더하지 않는다.
`Cthermal dT/dt = I²R - G(T - Tambient)`는 interval 내 고정 전력의 해석해로 적분한다.
발생 열을 SOC에서 두 번 차감하지 않는다. Thermal/OCV/저항의 feedback은 이번 근사에 없다.

<a id="adr-0024-fixture와-에너지-장부"></a>

### Fixture와 에너지 장부

Fixture는 50 kWh(180 MJ), OCV 400 V, R 0.05 Ω, thermal capacity 200 kJ/K,
cooling 20 W/K, ambient/초기 온도 25 °C, 초기 SOC 0.5, series 100개다.
관측 극값 half-spread는 전압 0.01 V·온도 1 °C다. Cell별 물리 분포를 계산한 값은 아니다.
각 DC 항과 terminal 합의 절댓값 상한은 100 kW, step 상한 40 ms, input dependency age는 50 ms다.
예제는 20 ms step을 사용한다. 전부 **독립 시험 parameter**이며 차량 baseline의 TBD-13을 닫지 않는다.

저장 에너지와 네 누적 장부는 compensated summation을 사용한다.
`initial_E - E = drawn_dc - received_dc + auxiliary + ohmic_loss`의 residual을 공개한다.
허용치는 `max(1e-6 J, capacity_j×1e-12)`이며 fixture에서는 0.00018 J다.
Full/empty 초과나 실수 회로해가 없는 부하, 비유한 계산은 step 전체를 거부한다.
에너지/온도/누적값을 일부만 갱신하거나 power를 조용히 clip하지 않는다.
Capacity 위반은 경계 초과 에너지를 보고하며 last committed truth는 진단용으로만 남긴다.

<a id="adr-0024-시간identity와-센서"></a>

### 시간·identity와 센서

각 interval은 직전 committed 시각부터 연속해야 하며 실제 power가 그 구간에서 일정하다는
명시적 입력이다. 끝 시각에 도착한 새 순간 전력을 과거 구간으로 소급 적용하지 않는다.
Power의 Epoch/source/oldest dependency와 sequence progress/동일 cached sample 불변성을 검사한다.
새 envelope 시각으로 cached dependency를 fresh하게 만들 수 없다. Model batch는 별도 증가한다.
Missing/invalid/stale power, gap·clock·identity 오류는 latch하고 current 관측을 unavailable로 만든다.

SOC, electrical pair, pack temperature, cell voltage pair, cell temperature pair는 독립 관측이다.
각 group은 acquisition Epoch/batch/source와 dependency time을 갖는다.
Acquire/Hold/Invalidate 및 cell pair override로 센서 상실·고정·극값을 주입한다.
Hold는 기존 시각·값·batch를 그대로 유지한다. 새 model batch로 group age를 갱신하지 않는다.
Optional 값 존재는 acquisition의 유효성이며 freshness는 BMS 소비자가 별도로 검사해야 한다.
Sensor override는 관측 주입으로서 physical energy/temperature를 바꾸지 않는다.

초기화에는 알려진 SOC/온도를 명시한다. 반복 초기화는 새 Epoch/비감소 clock의 **scenario reset**이며
새 energy ledger를 시작한다. 단순 ECU 재시작으로 battery SOC를 이 초기값으로 되돌리면 안 된다.
Gap 뒤의 미관측 에너지를 추측하지 않으며 복구·물리 상태 이어받기는 후속 통합 계약이다.

<a id="adr-0024-증거와-후속"></a>

### 증거와 후속

[학습·실행 안내](../learning/vehicle-models-guide.md), [단위 시험](../../tests/unit/battery_model_test.cpp),
기존 `actuator_demo battery-model`을 확장했다. 30개 신규 unit은 실제 power/zero/unknown,
energy balance·capacity·회로 경계, analytical thermal response, sensor group/hold와 reset을 검사한다.
이 결과는 BMS 한계·보호, contactor/HV lifecycle, CAN 배포나 차량 energy TC의 PASS가 아니다.
다음은 이 관측값의 원천/유효성/age를 검사하는 BMS controller와 charge/discharge limit다.
그 뒤 Power model과 Drive local gate, actual torque/speed→DC conversion을 연결한다.

<a id="adr-0025"></a>

## ADR-0025: 첫 BMS 충방전 한계·보호 판단

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-12/13/14와 SYS-EV-001/002/005의 부분 검증이다. System TC는 NOT RUN을 유지한다.

<a id="adr-0025-결정과-책임-경계"></a>

### 결정과 책임 경계

`vecu/bms/BmsController`는 별도 local sensor port를 소비하는 20 ms runnable이다.
`interfaces/bms/battery_sensor_snapshot.hpp`에 model identity·개별 acquisition·dependency 계약을
분리했다. BatteryModel의 진단 truth나 simulation 전용 fault enum을 참조하지 않는다.
물리 모델은 같은 port를 제공하며 기존 simulation type 이름은 alias로 유지한다.
SOC/electrical/pack temperature/cell voltage extrema/cell temperature extrema 다섯 group이 모두
유효하고 fresh하며 시간적으로 정합할 때만 한계를 계산한다. 일부 입력의 상실에도 정상 한계를
유지하는 degraded strategy는 이번에 추정해서 넣지 않았다.

실제 BMS의 전압·전류·온도 기반 current limitation과 protection의 책임 구분은
[MathWorks 공식 예제](https://www.mathworks.com/help/simscape-battery/ug/protect-battery-charge-discharge-for-electric-vehicle.html)를 참고한다.
계측과 battery disconnect hardware의 책임은
[Bosch BMS/BDU 설명](https://www.bosch-mobility.com/en/solutions/powertrain/fuel-cell-electric/battery-management-system/)을 참고한다.
아래 수치/회복 정책은 이 프로젝트의 SIL fixture 결정이다. 해당 예제/제품의 동작이나 OEM
calibration을 재현한다고 주장하지 않는다. 실제 cell data sheet·chemistry·fault reaction analysis가 우선한다.

<a id="adr-0025-한계와-보호"></a>

### 한계와 보호

충전과 방전 각각 SOC·cell voltage·온도 ramp의 **최솟값**으로 base current를 줄인다.
Cell voltage는 충전 시 max, 방전 시 min을 사용하고 온도는 pack 및 cell 극값을 모두 고려한다.
`P_allowed = min(P_cap, V_measured × I_base × min(factors))`를 기존 wire의 10 W 단위로
**내림**한다. Generic codec의 nearest rounding은 유지한다. 표시하는 허용 전류는
내림한 power/V이며 값은 nonnegative magnitude다. 실제 전류의 부호(+방전/−충전)와 구분한다.
Reason은 가장 제한적인 factor 하나이며 동률은 SOC→온도→전압 순이다. 모든 factor가 1이면
고정 max-power cap도 정상 설계 한계이므로 Nominal이다.

Operating boundary의 valid zero는 해당 방향만 차단할 수 있다. 별도 hard threshold의
cell/pack OV·UV, 고·저온, 충·방전 overcurrent는 발견 즉시 양방향 valid zero와 inhibit request를
만들고, 항목별 fresh acquisition 40 ms 지속 후 latch한다. 서로 다른 fault의 시간을 합치지 않는다.
이는 software supervisor fixture다. 단락/심각한 고장용 독립 hardware protection의 반응 시간이나
안전성을 40 ms로 정의한 것이 아니다.

Startup은 release band 안의 fresh acquisitions 100 ms를 확인한다. 정상화한 센서·온도만으로
latch를 자동 해제하지 않는다. Recovery-ready는 진단일 뿐이며 새 trusted application Epoch와
INIT/release dwell을 다시 통과해야 한다. Hard threshold와 release threshold를 분리해
경계 근처 반복 복구를 막는다. Pending hard trip이 사라지면 latch 전에는 다시 제한 계산이 가능하다.

Missing/invalid/stale/skew/identity 오류에는 unknown/InputsInvalid를 보고한다. Active 중 입력
상실은 latch한다. 초기 센서 미도착은 InitialChecks/unknown으로 대기하며 허용을 만들지 않는다.
유효 센서가 복원돼도 latch 중이면 valid zero/Disabled만 보고한다. Gap >40 ms는 limits를
unknown으로 latch하고, clock rollback/sequence 소진은 publication을 중단한다. Catch-up은 하지 않는다.

<a id="adr-0025-시간identity와-can"></a>

### 시간·identity와 CAN

Source age 50 ms, oldest dependency 70 ms, sensor skew 20 ms를 검사한다. Cached group의
identity/time/dependency/value는 불변이다. 새 envelope만으로 old acquisition이 갱신되지 않는다.
Dwell은 관련 acquisition source가 전진할 때만 진행하며 freshness gap이 크면 다시 시작한다.
Pack voltage가 `N×min_cell .. N×max_cell`에 tolerance 2 V를 더한 범위에 있는지도 검사한다.
이는 cell-sum/open-wire/중복 센서 진단이 아니다. Broad wire/finite 범위와 실제 operating
threshold를 구분한다. 모델 energy나 SOC를 BMS가 직접 갱신하지 않는다.

Trusted local startup은 `{application_epoch, model_epoch, enable_ns}`를 명시한다. CAN Epoch는
application session, CausalSequence는 이 mapping에 속한 model batch다. 같은 model Epoch를
유지한 BMS application restart가 가능하며 BatteryModel.initialize를 호출하지 않는다.
새 세션의 dependency는 enable 이전일 수 없으므로 실제 관측/입력을 다시 받아야 한다.
이것은 local component contract이며 실제 Central/Zone startup protocol, model placement/clock과
cross-process session 교환(TBD-12/14/15)을 완료한 것이 아니다.

기존 BmsPowerLimits message/codec/P05/receiver에 연결한다. Schema/DBC 변경은 없다.
State/Origin은 BMS runnable의 상태이며 vehicle NORMAL·HV_READY·DrivePermission이 아니다.
초기 센서 미도착은 INIT/NoAcceptedInput, 유효 센서를 받은 초기 dwell은 INIT/NormalPath다.
Pending hard trip은 DEGRADED/LocalProtection, latch는 FAIL_SAFE/LocalProtection으로 보고한다.
기존 `actuator_demo bms-control`은 plant→port→controller→codec→receiver를 수동 시계로 실행한다.
새 transport executable이나 vCAN case는 추가하지 않았다.

<a id="adr-0025-검증과-남은-일"></a>

### 검증과 남은 일

[33개 단위 시험](../../tests/unit/bms_controller_test.cpp)은 방향별 derating, 단일 cell 이상,
trip/release dwell, stale/skew/cache/clock/deadline, valid zero/unknown, P05/receiver와
physical energy를 유지하는 application restart를 검사한다. 정상·sanitizer 전체 unit은 255개다.
실행/parameter와 배터리 개념은 [학습 안내](../learning/vehicle-models-guide.md)에 있다.

Power lifecycle·precharge·contactor weld/actual HV·Drive local gate 및 실제 limit 추종 동작은
후속이다. 현재 OC protection은 고정 absolute-current band이며 derated dynamic limit의
tracking error/settling fault detector는 미구현이다. 정밀 SOP의 시간 horizon·전압 sag 예측,
SOC 추정/신뢰도·열 제어·balancing·SOH·절연/HVIL·hardware protector·DTC는 별도 단계다.
이 결과로 실차 safety/ISO 26262/AUTOSAR BSW 적합성을 선언하지 않는다.

<a id="adr-0026"></a>

## ADR-0026: 첫 Power lifecycle과 DC-link/contactor 모델

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-12/13/14의 부분 구현이다. 전체 SYS-EV system TC는 NOT RUN이다.

<a id="adr-0026-결정과-경계"></a>

### 결정과 경계

`vecu/bms/PowerController`는 BMS leaf 내부의 전원 lifecycle runnable이다. 별도 ECU/VCU 계층을
추가하지 않는다. `simulation/power/PowerModel`은 지연 있는 실제 접점과 DC-link RC 응답을 소유한다.
코일 명령/실제 접점/실제 bus 전압을 구분한다. Local sensor port는
`interfaces/bms/power_sensor_snapshot.hpp`다. Controller는 simulation header를 참조하지 않는다.

기존 BMS 한계 runnable은 동일 decision identity/source/dependency를 가진 typed `BmsSafetyGate`를
내보낸다. 초기 검사·전체 금지는 true, 정상 방향별 사용 가능은 false, 입력 상실은 unknown이다.
PowerController는 별도로 이 gate의 Epoch/age/sequence/cache를 검사한다. 같은 leaf의 로컬 연결이며
BMS→Drive application 우회나 Central DrivePermission 생성이 아니다.

기존 PowerRequest codec/P05/receiver와 **별도로 신뢰한 parent context**를 사용한다.
PowerStatus의 CausalSequence/AcceptedRequestSourceTime은 마지막 수용한 Central 결정의
Sequence/Source를 보존한다. Upstream parent sequence, physical model batch와 혼동하지 않는다.
PowerStatus InputSequence/InputTime은 **실제 physical acquisition**의 batch/oldest dependency다.
BMS gate freshness는 로컬에서 검사하며 Central은 이후 PowerLimits/PowerStatus를 함께 검증해야 한다.
Wire/DBC 변경은 없다. 실제 Central/Zone/session protocol은 후속이다.

<a id="adr-0026-정상-sequence와-protection"></a>

### 정상 sequence와 protection

OFF→CHECKS→PRECHARGE→HV_READY→SHUTDOWN→OFF를 사용하되 내부 phase를 세분한다.
Negative close→실제 negative 확인→precharge close→버스 ratio/delta의 fresh dwell→positive close→
실제 positive 확인→precharge open→실제 precharge open을 확인해야 READY다.
시간만으로 준비 완료를 선언하지 않는다. LV/interlock/isolation/charger/power-fault의 unknown은 정상과 다르다.
Common LocalState는 controller 초기 검사/health이고 PowerState와 별개다. 검사 통과 뒤 PRECHARGE나
정상 종료한 OFF에서도 LocalState=NORMAL일 수 있다. HV_READY는 차량 NORMAL/Drive 허가가 아니다.

종료는 즉시 drive inhibit request→전류 magnitude가 낮은 fresh acquisition의 dwell→접점 open
요청→실제 세 접점 open 확인→bus discharge→잔류 전압 확인 순이다. 회생의 음수 전류도 magnitude로
검사한다. Current unknown/high/timeout은 0으로 바꾸지 않는다. 종료 timeout은 blocked/latch이며
강제 개방 권한이 아니다. Weld/stuck feedback이나 고전압 잔류에는 OFF를 보고하지 않는다.
Fault 후 Enable/new frame/정상 센서로 자동 재시작하지 않는다. 새 trusted Epoch/INIT가 필요하다.

이번 fault fixture는 request loss/expiry, BMS inhibit, 조건 불충족, sensor/deadline/continuity,
응답/프리차지 timeout에 **controlled shutdown**을 요청한다. 모든 실차 고장의 보편적 반응이 아니다.
심각한 단락/열/절연 고장의 즉시 차단·pyrofuse 등은 별도 fault matrix와 hardware protection 분석 대상이다.
LV loss는 모델 코일의 실제 deenergization을 일으킬 수 있어 software hold로 막는다고 주장하지 않는다.
Actual feedback이 없으면 추가 coil write를 생성하지 않는다. 기존 driver/watchdog 정책은 미구현이며
불명 상태에서 물리 회로가 안전하게 정지했다고 선언하지 않는다.

<a id="adr-0026-물리-근사와-시간"></a>

### 물리 근사와 시간

Positive main과 precharge 저항 branch를 병렬로, negative main을 공통 return으로 둔다.
DC-link capacitor와 명시적 switched discharge resistor, 실제 signed DC load current를 계산한다.
접점 event 전후를 나눠 `C dV/dt = Gpack(Vpack−V) − Gdischarge V − Iload`의 constant-input 해석해를
적분한다. Begin의 명령을 전체 과거 interval에 소급하지 않는다. Opening/closing delay는 20 ms다.
실제 전력의 누락을 zero load로 추정하지 않으며 불가능한 전압은 clip하지 않고 step을 거부한다.

RC precharge/ratio/timeout 원리는
[MathWorks 공식 모델 설명](https://www.mathworks.com/help/stateflow/ug/learn-how-to-model-battery-management-system.html)을 참고한다.
[TI DC-link precharge 예](https://www.ti.com/tool/TIDA-050063)는 active topology도 제시한다.
이번 passive-R functional fixture가 그 제품 회로나 calibration을 복제한 것은 아니다.

Fixture는 C 2 mF, precharge 50 Ω, main equivalent link 0.02 Ω, discharge 100 Ω다.
모델 voltage/load 표현 상한은 1000 V/±500 A다. Controller pack 300..450 V,
precharge ratio ≥0.99와 |Vpack−Vbus|≤5 V를 20 ms 확인한다. OFF 잔류 기준 30 V,
opening |I|≤5 A/20 ms다. 이 값은 부품 정격·안전 전압·실차 calibration의 채택이 아니다.
Checks 500 ms, contactor 100 ms, precharge 2 s, current wait 300 ms, discharge 1 s의 timeout을 쓴다.
Controller period 10 ms/max gap 30 ms, physical source age 50 ms/dependency 70 ms다.

Physical port는 하나의 atomic acquisition이고 내부 optional의 unknown을 보존한다.
Hold는 전체 identity/time/value를 유지한다. Cached observation을 반복 읽어 dwell을 채우지 않는다.
Time gap/clock/invalid physical interval은 plant를 latch/unavailable로 하고 backfill하지 않는다.
Controller clock rollback은 publication/coil write를 중단한다. Deadline은 controlled shutdown을 latch한다.

Application INIT와 physical scenario reset을 분리한다. 재시작은 코일 초기화나 bus voltage reset을
수행하지 않는다. 첫 fresh feedback에 접점이 닫혀 있으면 StartupEnergized를 latch하고 inhibit/
controlled shutdown한다. 물리 OFF 이후 새 Epoch로 다시 검사해야 한다.

<a id="adr-0026-검증과-다음-단계"></a>

### 검증과 다음 단계

[학습·실행](../learning/vehicle-models-guide.md), [37개 component 시험](../../tests/unit/power_lifecycle_test.cpp),
기존 BMS 시험에 추가한 local gate 1개를 포함해 normal·ASan/UBSan 전체 unit은 293개다.
RC 해석해/접점 지연/부하와 회생 부호, LV·weld/stuck·부분 관측·cached dwell, 정상/blocked 종료,
trusted parent/expiry/restart/deadline/codec·receiver를 검사한다. 기존 CLI의 `power-model` 네 scenario는
실제 BmsController gate→PowerController→PowerModel→PowerStatus/P05→receiver를 연결한다.
새 transport executable이나 vCAN case를 추가하지 않았다. 이전 97개 vCAN 증거는 별도 이력이다.

Demo의 400 V/SOC 0.5/온도와 cell spread는 명시적 fixture이며 전류·bus·접점은 power plant의 actual이다.
Actual load도 별도 fixture다. BatteryModel SOC/energy를 동시에 실행하거나 DC-link 충방전 에너지를
pack capacity에서 적분하지 않는다. **차량·배터리 에너지 통합의 PASS가 아니다.** M6에서 단일
battery energy owner와 capacitor/path losses/actual inverter power의 일관된 coupling이 필요하다.
Arc/bounce, resistor 정격/발열, LV 회로, 절연/HVIL 물리 검출, pyrofuse와 hardware watchdog은 미구현이다.
다음은 actual speed·BMS limits·Central permission·Drive 자체 HV feedback을 묶는 Drive local gate/capability다.

<a id="adr-0027"></a>

## ADR-0027: 필수 EV Drive gate와 회생 가용량

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-02/03/12/13/14의 부분 구현이다. Full TC-REG/EV/ZON은 NOT RUN이다.

후속 구조 변경: [ADR-0032](#adr-0032)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

<a id="adr-0027-결정과-책임"></a>

### 결정과 책임

`vecu/drive/DriveController`는 Command, 원천 보존된 DriveBatteryLimits, 별도로 검증한 parent의
Central DrivePermission, Drive 자체 actual speed/HV를 요구한다. 허용을 우회하는 config는 없다.
기존 `DriveActuator`는 명시적인 isolated torque-response fixture로 남긴다. 기존 예제/vCAN의
성격을 갑자기 operational EV로 바꾸지 않는다. 물리 응답은 공통 `simulation/drive/TorqueResponse`다.

`interfaces/drive/drive_local_sensors.hpp`는 independent speed/HV acquisitions의 Epoch/sequence/
source/dependency를 정의한다. HV voltage·inverter-ready·local fault는 실제 로컬 센서 port다.
Central permission이나 참조한 CAN PowerStatus로 로컬 HV를 대체하지 않는다.
Model Epoch는 trusted startup 인자이고 application 재시작과 독립이다.

기존 P05/receiver를 재사용한다. Limits 입력은 **0x193 DriveBatteryLimits**만 받으며 0x284 BMS
원본 frame을 자동 변환/수용하지 않는다. Demo는 명시적인 relay fixture에서 기존 forward 함수를
사용한다. Central grant/trusted parent도 독립 fixture다. 실제 Central/Zone/DDS runtime은 후속이다.
Wire/DBC의 변경은 없다. 새 별도 실행 프로그램 대신 기존 CLI에 `drive-gated`를 추가한다.

<a id="adr-0027-gate와-복구"></a>

### Gate와 복구

모든 필수 입력이 usable이고 BMS producer가 NormalPath NORMAL/DEGRADED, Central AllowNormal이
fresh/parent-bounded이며 actual HV/inverter health·speed가 정상일 때만 활성화한다.
초기에는 fresh zero Command/known Inhibit·센서를 먼저 보낼 수 있고 HV OFF는 정상 non-driving INIT다.
상위가 허가를 내렸어도 다른 첫 입력이 아직 도착하지 않았으면 활성화하지 않는다. 최초 수신 순서만으로
fault를 만들지는 않는다. 각 critical receiver/startup 80 ms monitoring 계약은 유지한다.

활성화 뒤 permission Inhibit/loss/expiry, 한계·로컬 센서 상실, BMS protection·HV fault·overspeed,
continuity/deadline은 zero-target과 latch다. Fresh frame이나 정상 센서로 자동 복구하지 않는다.
새 trusted application Epoch/INIT는 actual torque를 보존하고 pending goals를 취소한다.
Clock rollback은 physics를 진행하지 않고 publication을 중단한다. Missed interval은 hold/no catch-up이다.
수신 함수에서도 갱신 전에 기존 입력의 expiry를 확인하므로 tick 사이의 늦은 재발행으로 loss를 숨기지 않는다.

Valid zero charge는 soft constraint여서 새 regen target만 0이고 구동 가능성은 별도다.
Valid zero discharge는 launch도 막는다. 한쪽 limit unknown은 0이나 반대쪽 값으로 보충하지 않는다.
이번 conservative strategy는 양쪽 limits를 모두 요구한다. Known Inhibit/latched health와 충분한
관측이 있으면 capability valid zero/Disabled, 필수 관측 불명에는 unknown/InputsInvalid다.
Actual torque validity와 capability validity는 독립이다.

<a id="adr-0027-power와-torque-envelope"></a>

### Power와 torque envelope

모든 torque/speed는 aggregate driven-wheel 기준이다. Propulsion upper estimate는
`Pdraw = P_reserve + T×omega/eta + k×T²`다. Fixed reserve에는 공유 pack 한계에서 fixture의
auxiliary/idle load 몫을 포함한다. `eta=0.9`는 부하 비례 변환항의 가정 하한이며 모든 손실을
포함한 총 효율 하한은 아니다. `k=0.01 W/(Nm²)`의 torque-current 손실 근사는 정지 때도 유한한
launch 한계를 만든다. Positive quadratic root를 cancellation 없이 계산한다. BatteryState SOC만으로 재계산하지 않는다.

Regen은 `Preturn <= |T|×omega`의 보수적 energy bound로 `Tcharge <= Pcharge/omega`를 적용한다.
이는 실제 회수 효율을 100%로 적분한다는 뜻이 아니다. Actual charge power/loss integration은 없다.
정지/저속에서는 나누기 전에 regen taper를 적용한다. Motor torque/constant mechanical power와
BMS charge acceptance 중 작은 값을 쓰고 0.1 Nm 단위로 내린다.

Fixture: physical −200..300 Nm, motor mechanical propulsion 20 kW/regen 10 kW,
speed maximum 100 rad/s, regen ≤2 rad/s zero·≥5 rad/s full, reserve 200 W,
HV 300..450 V, normal/protection rate 1000/2000 Nm/s, normal delay 50 ms다.
차량 calibration, motor map/FOC/current sensor 모델이나 실차 안전 envelope의 채택이 아니다.
실제 부하/온도/효율 map과 auxiliary power allocation은 M6에 일관되게 연결해야 한다.

물리/제어 경계와 speed·battery 기반 회생 제한의 참고는
[MathWorks regenerative/friction control](https://www.mathworks.com/help/sdl/ug/regenerative-friction-braking-control.html),
torque-speed envelope/효율 map의 참고는
[Motor & Drive 공식 모델](https://www.mathworks.com/help/sps/ref/motordrivesystemlevel.html)이다.
위 식과 수치는 StrataDrive의 fixture 결정이다.

<a id="adr-0027-지연양자화원천-시각"></a>

### 지연·양자화·원천 시각

TorqueResponse.constrain은 직전 interval을 기존 조건으로 진행한 뒤 active/queued/staged goal을
현재 envelope로 제한한다. 축소한 옛 goal을 한계 회복 시 되살리지 않는다. 새로운 큰 목표는 새 delay를
거친다. Bound 밖의 actual은 보호 rate로 수렴하고 즉시 clip하지 않는다. Controller는 residual을
별도 `actual_outside_envelope`로 보고한다. Fault zero는 검출 시각부터 적용하고 대기 goals를 취소한다.

**한계는 target envelope이며 actual response가 즉시 따라왔다는 보장이 아니다.** Full SOC에서
charge-zero가 된 동안에도 유한 시간의 음수 actual residual이 있을 수 있다. M6 energy coupling 전에
headroom/guard band·fault reaction·실제 power/제동 deficit budget을 검증해야 한다. Battery 충전량을
임의 clip하거나 그 residual을 command 0으로 대체해서 문제를 감추지 않는다.

Local source/dependency 30 ms, 두 local acquisition skew 20 ms, limits/permission source 50 ms/
dependency 70 ms를 검사한다. Control period/max gap은 10/30 ms다. Wheel source는 acquisition을
보존하고 capability source는 계산 시각, input은 local/limits/grant/사용한 parent의 oldest dependency다.
Inhibit의 사용하지 않는 zero-valued physical reference는 dependency로 해석하지 않는다.
Capability dependency가 직전 발행 값보다 뒤로 가면 timestamp를 올리지 않고 해당 publication을
unknown으로 생략한다. Receiver의 opt-in 70 ms capability input budget을 명시하며 기존 default 30 ms는 유지한다.

<a id="adr-0027-검증과-다음-단계"></a>

### 검증과 다음 단계

[학습·실행](../learning/vehicle-models-guide.md), [37개 gate 시험](../../tests/unit/drive_controller_test.cpp)과
공유 physics의 4개 추가 시험으로 normal·ASan/UBSan 전체 unit은 334개다.
기존 CLI의 여섯 scenario는 BmsController→명시적 relay/독립 Central fixture→DriveController→
TorqueResponse→Actual/P05→receiver를 확인한다. RC bus는 PowerModel actual이며 wheel speed/
inverter-ready/SOC/thermal은 fixture다. 실제 battery DC energy coupling이 아니다.
기존 isolated Drive model vCAN 3개는 normal·sanitizer 각각 격리 네트워크에서 재실행해 통과했다.
이전 97개 전체 통과 이력을 이번 전체 재검사나 EV gate transport PASS로 바꾸지 않는다.
다음은 actual torque/speed·DC power·battery의 일관된 energy coupling과 모델 시간/부하·guard band 검토다.
Central allocation/마찰 보충·차량 motion/stop·Target timing/OS/RTE/BSW와 full TC는 후속이다.

<a id="adr-0028"></a>

## ADR-0028: 실제 Drive 토크에서 배터리 에너지까지

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-03/12/13/14의 부분 구현이다. 전체 TC-REG/EV/ZON은 NOT RUN이다.

<a id="adr-0028-결정과-경계"></a>

### 결정과 경계

`simulation/drive/DriveEnergyModel`이 실제 aggregate wheel torque·같은 기준 wheel rad/s·별도
auxiliary power를 받아 motor/inverter DC power를 계산한다. 내부의 기존 BatteryModel만 chemical
energy/SOC·battery 저항 발열을 소유한다. Command, capability, BMS 허용량은 적분 입력이 아니다.
TorqueResponse/DriveController의 실제 출력에서 다음 interval의 physical acquisition을 만든다.
ECU application Epoch 재시작은 physical model/누적 에너지를 리셋하지 않는다.

이번 electrical boundary는 **HV가 준비된 이상적 DC 연결**이다. Local HV는 battery terminal의 실제
전압과 같고 inverter-ready는 명시적 fixture다. PowerModel의 dynamic DC-link/접점/프리차지 모델을
동시에 실행하지 않는다. 따라서 capacitor 저장 에너지·배선/접점 손실을 빠뜨린 채 그 회로까지
통합했다고 주장하지 않는다. 실제 circuit coupling과 shutdown 중 에너지/부하 처리는 다음 작업이다.
Wheel speed는 외부에서 유지하는 20 rad/s fixture다. 차량 관성·타이어·주행 저항/정지 모델은 없다.
이 외부 기계 경계는 dynamometer처럼 일을 공급/흡수할 수 있고, command로 speed를 계산하지 않는다.

<a id="adr-0028-전력과-손실"></a>

### 전력과 손실

`Pm = actual_torque × actual_wheel_speed`이며 양수는 기계적 구동 출력, 음수는 제동 입력이다.
부하 비례 conversion loss는 구동 때 `Pm × (1/eta_m − 1)`, 회생 때 `−Pm × (1−eta_g)`다.
여기에 nonnegative `kT² + inverter_idle`을 더하고 `Pdc = Pm + motor_loss`로 계산한다.
Battery terminal은 `Pdc + auxiliary`다. BatteryModel이 `I²R`만 추가해 chemical energy를 갱신한다.
Motor loss를 battery 온도/저항 손실에 다시 더하지 않는다. 별도 motor thermal state는 없다.

Fixture는 eta_m/g=0.92/0.85, k=0.01 W/Nm², inverter idle=50 W, auxiliary=150 W다.
Eta는 추가 copper/idle을 포함한 총 효율이 아니다. 실제 map·calibration은 미결정이다.
기존 Drive gate의 eta 하한 0.9와 k=0.01·fixed reserve 200 W는 이 fixture의 구동 소비를 덮는다.
Reserve는 한계에서 예약하는 몫이고, 실제 에너지 입력에는 idle 50 W와 auxiliary 150 W를 한 번씩만 더한다.
외부 auxiliary가 바뀌면 reserve/배분 계약도 검토해야 한다.

음수 torque여도 motor loss 때문에 Pdc가 양수일 수 있다. Pdc가 음수여도 auxiliary가 더 크면
battery는 방전한다. 저속/standstill에서도 copper/idle은 유지하며 효율로 0을 나누지 않는다.
회생 가용량 계산의 보수적 100% mechanical upper bound와 실제 85% conversion 계산은 역할이 다르다.

[Motor & Drive 공식 설명](https://www.mathworks.com/help/simscape-electrical/ref/motordrivesystemlevel.html)의
system-level energy balance·fixed/torque loss와 [Battery equivalent circuit](https://www.mathworks.com/help/simscape-battery/ref/batteryequivalentcircuit.html)을
참고했다. 위 수식·parameter와 interval 계약은 StrataDrive의 fixture 결정이다.

<a id="adr-0028-시간원천에너지-장부"></a>

### 시간·원천·에너지 장부

Begin에서 알려진 actual torque/speed/auxiliary를 interval 전체에 ZOH한다. End acquisition이나
end torque를 이전 interval에 소급하지 않는다. Demo는 10 ms, model 최대 step은 20 ms다.
이는 TorqueResponse의 연속 piecewise 응답에 대한 sample 기반 전력 근사이며 exact ramp 적분이 아니다.
Known linear torque ramp의 20→10 ms refinement 시험으로 mechanical work 수렴을 확인한다.

세 입력의 model Epoch/sequence/source/dependency·cached value를 독립 검증한다. End 기준 dependency
age ≤30 ms, source skew ≤10 ms다. 계산 source는 begin, input은 세 acquisition의 oldest dependency다.
Battery의 end sensor source와 계산 input을 구분한다. BMS 20 ms 판단이 매 10 ms 갱신됐다고 꾸미지 않는다.
Unknown/invalid/stale·gap/rollback은 latch/unavailable이며 0 입력이나 energy backfill로 바꾸지 않는다.

Motor mechanical work와 loss는 compensated sum으로 누적한다. 검사식은 다음과 같다.

```text
initial_chemical_energy − chemical_energy
  = signed_mechanical_work + motor_loss + auxiliary_energy + battery_ohmic_loss
```

Tolerance는 max(1e−6 J, capacity×2e−12), 50 kWh fixture에서 0.00036 J다.
이는 수치 장부의 허용 오차이며 실차 모델 정확도나 센서 오차 허용치가 아니다.
Capacity/전기적 한계 초과는 기존 BatteryFault/초과 에너지를 전파하며 SOC/power를 clip하지 않는다.

<a id="adr-0028-충전-여유와-잔여-응답"></a>

### 충전 여유와 잔여 응답

Valid charge-zero 뒤 actual 음수 토크는 유한 rate로 줄어든다. 이 구간의 반환 전력도 계속 적분한다.
센서 hotspot 45 °C 주입으로 charge-zero를 만드는 연결 시험과 demo에서 이를 확인한다.
SOC/저장 에너지는 주입하거나 되돌리지 않는다.

기존 BMS SOC soft zero는 0.05/0.95다. 50 kWh에서 물리 empty/full까지 각 9 MJ 여유가 있다.
100 ms 검출 + 20 ms ZOH + 300 Nm/2000 Nm/s 해소라는 제한된 가정에서 100 kW terminal 입력의
최대 chemical flow로 계산한 270 ms reaction budget은 약 27.9 kJ이며 guard band보다 작다.
이 검토는 이번 fixture의 finite traction reaction에 한정한다. 무한한 auxiliary 소비, 센서 오차/고장,
thermal/cell charge-zero 순간의 허용 overrun, hardware trip·차량 braking deficit·shutdown 안전성은 보장하지 않는다.
완충 상태에서 이미 음수 actual이 존재하는 잘못된 초기 조건은 CapacityViolation으로 드러낸다.

<a id="adr-0028-검증과-후속"></a>

### 검증과 후속

[학습·실행](../learning/vehicle-models-guide.md)에 네 demo와 해석을 정리했다.
새 28개 시험으로 normal·ASan/UBSan 전체 unit은 362개다. Analytic power/loss, 별도 aux/heat,
20,000 alternating interval의 장부, interval source/cache/unknown, 경계 초과와 실제
Battery→BMS→명시적 relay/독립 trusted Central fixture→DriveController→Actual/P05 receiver를 검사한다.
Normal·sanitizer·BUILD_TESTING=OFF의 네 demo도 검사한다. 새 wire/transport case는 없다.
이전 vCAN 97개 전체 이력과 직전 Drive 3개 재검사는 보존하며 이번 energy transport PASS로 바꾸지 않는다.
다음은 RC/DC-link·실제 접점/부하와 Battery를 단일 전기·에너지 경계로 연결하는 것이다.
Vehicle motion·Central 배분/마찰 보충·분산 runtime·실차 map/Target timing·전체 차량 TC는 후속이다.

<a id="adr-0029"></a>

## ADR-0029: Battery와 실제 DC-link 회로의 에너지 연결

Date: 2026-10-16. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-03/12/13/14의 부분 구현이다. 실제 Central/Zone runtime·차량 motion과 전체 TC-REG/EV/ZON은 NOT RUN이다.

<a id="adr-0029-결정과-책임"></a>

### 결정과 책임

`simulation/power/EvPowerModel`이 기존 BatteryModel·PowerModel과 공통 motor power 계산을 묶는다.
별도의 배터리 장부를 만들지 않는다. BatteryModel은 chemical energy/SOC·battery 저항 발열,
PowerModel은 접점/커패시터, composition은 motor·경로 손실 장부를 소유한다.
두 물리 모델을 candidate로 계산하고 전체 에너지 검사까지 성공해야 함께 commit한다.
한쪽 실패에 capacitor만 진행하거나 SOC만 바뀌는 부분 commit은 없다.

기존 이상적 경로 DriveEnergyModel과 독립 Power fixture는 설명·회귀 목적으로 유지한다.
Motor conversion/copper/idle 식은 `calculate_motor_power` 하나를 공유한다.
ECU 소프트웨어인 BmsController/PowerController/DriveController는 physical truth가 아닌 별도 sensor port를 소비한다.
Model Epoch/초기 capacitor charge와 SOC는 물리 scenario 초기값이고 ECU session 재시작으로 리셋하지 않는다.

<a id="adr-0029-회로와-입력"></a>

### 회로와 입력

Battery source는 constant Voc=400 V와 Rint=0.05 Ω다. 두 실제 main contactor·precharge 병렬 경로,
DC-link C=0.002 F, precharge 50 Ω·main 0.02 Ω·bleed 100 Ω와 접점 지연 20 ms를 재사용한다.
PowerModel은 기존 held bus-current fixture와 별도로 명시적인 bus-power mode를 제공한다.
두 load 표현을 동시에 사용하지 않는다. Coupled mode의 source voltage는 OCV이고 output pack voltage는
Rint를 거친 실제 terminal voltage다. Pack과 bus voltage를 같은 값으로 두지 않는다.

Motor의 actual torque와 wheel rad/s는 begin acquisition으로 ZOH한다. Inverter가 실제 enabled이면
그 actual의 DC power가 bus의 constant-power load다. Inverter off인데 actual torque가 남아 있으면
입력 오류로 중단한다. Permission Inhibit를 physical torque/전류 0으로 대체하지 않는다.
Standalone speed는 외부 20 rad/s fixture이며 vehicle kinetic energy를 구현한 것은 아니다.

Auxiliary는 이번 회로에서 **pack-side actual current 0.375 A**다. Power는 terminal voltage×current로
계산하므로 이전 ideal-path의 고정 150 W fixture와 구분한다. HV contactor가 열려도 이 branch는 남는다.
OFF를 battery 소비 0으로 해석하지 않는다. ECU/LV sleep·DC/DC·auxiliary 차단 모델은 후속이다.

<a id="adr-0029-적분과-보존"></a>

### 적분과 보존

Auxiliary current를 Ia, 접점 경로 conductance를 gp, bleed를 gd라 하면
`G = gp/(1+Rint×gp)`, `Vs = Voc−Rint×Ia`다.
Path current는 `G×(Vs−Vbus)`, battery current는 path+Ia이며
`C dVbus/dt = path_current − gd×Vbus − Pmotor_dc/Vbus`를 푼다.
P=0·bus=0은 유효하다. 실제 load가 있는데 무전압/수치적으로 불가능한 구간은 오류로 보고한다.

접점 event에서 interval을 나누고, 각 구간은 implicit midpoint로 적분한다.
최대 내부 step 50 µs를 electrical time constant 이하로 제한하고 1 ns 이하 분해능이나
200,000개 초과 substep이 필요한 구간은 거부한다. 이것은 ECU task period/실시간 보장이 아니다.
Constant-power 식의 high-voltage quadratic root를 사용하며 voltage/current를 임의 clip하지 않는다.

BatteryModel의 새 `step_integrated` 입력은 구간 전체의 q=∫I dt, ∫I² dt, endpoint current와
pack branch/auxiliary energy다. Source는 end, oldest dependency는 begin 이하라는 별도 interval 계약이다.
Ending current를 구간 전체에 소급하지 않는다. Heat는 Rint×∫I²dt이며 square(mean I)와 다르다.
양방향 전류의 net charge가 0이어도 저항 발열은 생길 수 있다.
Endpoint electrical sensor와 interval-mean 진단 power도 구분한다.

Flow는 energy identity·Cauchy moment bound·power peak·identity/time·capacity를 검사한다.
Constant-power/integrated-current 입력 mode는 같은 battery scenario에서 바꾸지 않는다.
Thermal update는 interval 평균 heat를 사용한 lumped approximation이다. 전류 시간 파형의 정확한
열 convolution이나 실제 부품 온도 모델을 구현한 것은 아니다.

```text
initial_battery_energy − battery_energy
  = capacitor_energy − initial_capacitor_energy
  + signed_mechanical_work + motor_loss + auxiliary_energy
  + battery_ohmic_loss + precharge_loss + main_path_loss + bleed_loss
```

Coupled tolerance는 max(1e−6 J, capacity×4e−12), 50 kWh에서 0.00072 J다.
이 잔차는 이산 계산의 보존 검사이며 실차 정확도·보호 deadline을 뜻하지 않는다.
고립된 capacitor에 회생하면 capacitor 에너지가 증가하고 battery를 가상 충전하지 않는다.
Capacity/회로 domain을 벗어나면 latch/unavailable과 원래 fault를 보고하며 두 물리 state를 commit하지 않는다.

물리 관계의 참고는 [Capacitor 공식 설명](https://www.mathworks.com/help/simscape/ref/capacitor.html),
[Battery equivalent circuit](https://www.mathworks.com/help/simscape-battery/ref/batteryequivalentcircuit.html)이다.
수치 solver·fixture parameter·적분 port는 StrataDrive의 결정이며 외부 도구와 등가 검증은 하지 않았다.

<a id="adr-0029-연결-fixture와-고장"></a>

### 연결 fixture와 고장

기존 CLI `ev-power`는 actual Battery→BMS limits/local gate→PowerController→접점/회로,
독립 trusted Central request/grant·명시적 limits relay→DriveController→TorqueResponse→실제 motor power를 연결한다.
PowerStatus·DriveActual은 기존 P05 codec/receiver도 통과한다. 실제 Central coordinator/Zone/DDS 구현은 아니다.
Drive의 로컬 HV acquisition은 물리 bus 측정이며 CAN PowerStatus를 측정값으로 복사하지 않는다.
Power current sensor를 unknown/hold해도 internal physical flow는 계산한다. 제어기는 이를 sensor fallback으로 쓰지 않는다.

이번 combined fixture만 opening-current threshold를 0.5 A로 둔다. Nominal aux 0.375 A와 구분하고
20 ms low-current dwell·actual contact-open·실제 잔류 voltage 확인을 거친다. Legacy fixture의 5 A default는 유지한다.
Drive fixed reserve는 500 W다. Normal bus ≥300 V·pack ≤450 V에서 max motor DC 약33.56 kW,
main-path loss 상한 약250.3 W + idle50 W + aux≤168.75 W를 덮는다.
이는 steady target budget이며 capacitor recharge/finite actual residual의 순간 power를 hard-limit한 결과가 아니다.

Normal shutdown에서 Central Inhibit 후 actual torque가 줄고, physical inverter stage는 torque 0 뒤 disable된다.
기존 Drive gate는 활성화 후 Inhibit를 latch하므로 종료 뒤 Drive fault=PermissionInhibit를 유지한다.
이는 power OFF 성공과 별개이며 자동 재허가/재출발을 구현한 것이 아니다.
Weld는 OPEN_CONTACTORS/blocked, current unknown·지속 10 A aux는 WAIT_CURRENT/blocked다.
Timeout을 접점 강제 개방 허가나 성공한 OFF로 해석하지 않는다.

<a id="adr-0029-검증과-후속"></a>

### 검증과 후속

[학습·실행](../learning/vehicle-models-guide.md)에 결과와 재현 명령을 남긴다.
새 29개(Ev circuit 24개·Battery integrated-flow 5개)로 normal·ASan/UBSan 전체 unit은 391개다.
RC analytic/event·step refinement, capacitor 단독 discharge/regen, 10,000 alternating interval 장부,
원천/unknown·mode/epoch/transaction·capacity와 normal/고장 네 combined CLI loop를 검사한다.
정적 분석·production build 및 기존 Power/Drive energy/Drive gate demo 회귀를 구분해 기록한다.
Wire/transport는 추가하지 않으며 과거 vCAN 97개 이력과 gate 단계의 3개 재검사를 보존한다.
다음은 M2의 미결정 parameter·task/monitor 경계·fault/session 수용 항목과 학습자 review를 정리한 뒤 M3 timing 측정이다.
차량 motion/마찰 배분·hardware 보호·정밀 motor/chemistry·RTOS/분산 runtime·full TC는 후속이다.

<a id="adr-0030"></a>

## ADR-0030: 조향 센서 경계와 local response monitor

Date: 2026-10-16. Status: **IMPLEMENTED / Host component checks; 학습자 수용 PENDING**.
[M2 수용 검토](milestone-reviews.md#m2)의 OPEN-M2-01을 구현한다.
Classic stack/실차 안전성 검증이나 M2 전체 완료를 뜻하지 않는다.

후속 구조 변경: [ADR-0032](#adr-0032)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

<a id="adr-0030-문제"></a>

### 문제

기존 SteeringActuator는 command 검사와 delay/rate 응답·Actual 생성을 함께 수행했다.
통신 상실에는 hold했지만, fresh Command와 fresh angle acquisition이 계속되는 동안
조향이 움직이지 않는 경우는 검출하지 못했다. 현재 목표와 Actual의 단순 차이는
정상 dead time·rate limit·saturation에도 커지므로 그 차이만으로 jam을 선언할 수 없다.

<a id="adr-0030-결정"></a>

### 결정

1. 물리 delay/rate/angle 응답을 `simulation/steering/SteeringResponse`로 분리한다.
   Jam/rate variation은 elapsed interval의 물리에, sensor hold/invalid/override는 end acquisition에만 주입한다.
2. `interfaces/steering/AngleMeasurement`에 physical model epoch·sequence·source time·각도를 담는다.
   Application epoch 재시작은 물리 각도나 sensor sequence를 리셋하지 않는다.
3. `vecu/steering/SteeringResponseMonitor`는 issued bounded target과 sensor port만 소비한다.
   Plant header·diagnostic truth·jam flag를 참조하지 않는다. 첫 유효 측정으로 초기 위치를 잡고,
   정상 동작 중 매 측정값으로 예측 상태를 다시 맞추지 않는다.
4. 목표의 기존 50 ms delay를 반영한 FIFO와 정상 rate 범위로 가능한 angle interval을 전파한다.
   Default는 nominal rate의 0.8..1.2배, interval 밖 오차 여유 0.01 rad다.
   Physical maximum으로 clamp한 목표를 사용하므로 허용된 saturation은 residual을 만들지 않는다.
5. Residual 초과가 **새 acquisition의 source time 기준 60 ms** 이어질 때 TrackingError를 latch한다.
   정상 범위로 돌아온 sample은 pending dwell을 취소한다. Pending은 DEGRADED이며 아직 latch가 아니다.
   반복 command는 지연·dwell을 다시 시작하지 않고 cached sensor read는 dwell을 진행시키지 않는다.
6. Sensor missing/만료와 identity/value/time 위반은 SensorUnavailable/SensorInvalid로 구분한다.
   Default age 20 ms, 연속 fresh acquisition gap 30 ms다. Wrong epoch, timestamp 역행·future,
   같은 identity의 값 변경, NaN/범위 밖 값은 사용하지 않는다.
7. 기존 single-owner SteeringActuator를 SIL composition adapter로 유지한다. Sensor acquisition과 monitor 뒤에
   다음 목표를 stage하며 새 출력은 이후 물리 구간에만 적용한다. Fault는 pending motion을 취소하고
   기존 modeled hold/latch를 적용한다. Clock/deadline/communication fault의 기존 정책을 유지한다.
8. CAN ID/DBC/P05/layout은 변경하지 않는다. Fresh valid 측정만 angle Actual로 발행한다.
   Held sensor를 current report time으로 갱신하지 않고 unavailable로 발행한다.
   FAIL_SAFE에서도 새 유효 angle은 관측값으로 발행할 수 있다. Trusted 새 application epoch로만 ECU latch를 초기화한다.

Rate band·threshold/dwell은 명시한 첫 SIL fixture다. 실차 spec, jam 검출 100 ms deadline이나
FTTI를 확정하지 않는다. 기존 stream-loss 100 ms 계약과 tracking 검출 시간을 구분한다.

<a id="adr-0030-근거와-범위"></a>

### 근거와 범위

관측과 정상 모델의 residual을 검출 지표로 쓰는 일반 개념은
[MathWorks model-based condition indicators](https://www.mathworks.com/help/predmaint/ug/model-based-condition-indicators.html)와
[fault detection/diagnosis 구분](https://www.mathworks.com/help/predmaint/ug/decision-models-for-fault-detection-and-diagnosis.html)을 참고했다.
위 bounded-rate predictor와 수치는 프로젝트의 별도 설계이며 해당 문서의 자동차 calibration이 아니다.

TrackingError는 **정상 응답 계약에서 벗어남**을 검출한다. 기계 jam, 구동 능력 저하와 plausible sensor bias/freeze를
이 센서 하나만으로 고유하게 분류하지 않는다. 현재 요구와 같은 angle에서 발생한 jam처럼 excitation이 없으면
검출하지 못할 수 있다. 명령 변화에도 정상 interval이 고정각을 포함하면 구분할 수 없다.
Delay uncertainty·inertia/friction·노이즈/센서 이중화와 독립 watchdog은 미구현이다.
SIL hold는 실제 차량의 가용 조향/안전 정지를 보장하지 않는다.

<a id="adr-0030-검증과-영향"></a>

### 검증과 영향

새 39개: 물리 9개·monitor 21개·adapter 9개를 추가해 전체 unit은 430개다.
기존 Steering 13개를 포함해 normal·ASan/UBSan 전체 unit, production build와 기존 model vCAN 8개를 검사한다.
CLI는 기존 `actuator_demo steering-model`에 normal/jam/slow/sensor-hold/sensor-invalid/transient를 추가한다.
새 executable이나 jam CAN frame은 만들지 않는다. 상세 결과는 [품질 기록](../development-guide.md),
재현/해석은 [학습 안내](../learning/vehicle-models-guide.md)에 보존한다.

영향은 SYS-ARCH-002, SYS-COM-004, SYS-SAFE-001/002/003과 TC-CTRL-001·TC-SAFE-001/002의
component 부분 증거다. 전체 requirement revision/차량 TC Result는 변경하지 않는다.
Brake response detector는 OPEN-M2-02, 실제 task/watchdog/trace는 M3, Zone availability 전달은 M4/M5,
Fault Event/DTC 통합은 M9에 남는다.

<a id="adr-0031"></a>

## ADR-0031: 브레이크 압력 센서와 local response monitor

Date: 2026-10-16. Status: **IMPLEMENTED / Host component checks; 학습자 수용 PENDING**.
[M2 수용 검토](milestone-reviews.md#m2)의 OPEN-M2-02에 대한 component 구현이다.

후속 구조 변경: [ADR-0032](#adr-0032)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

<a id="adr-0031-문제"></a>

### 문제

Fresh Command/Actual stream만으로 가압·감압 능력이 정상인지 알 수 없다.
목표와 측정 압력의 직접 비교도 정상 delay/rise/fall·saturation에 오검출을 만든다.
통신 상실 보호에서 사용한 pressure floor는 물리 고장 뒤의 압력 도달 성공을 보장하지 않는다.

<a id="adr-0031-결정"></a>

### 결정

1. `simulation/brake/BrakePressureResponse`에 기존 delay·별도 rise/fall rate·압력 한계와
   물리 stuck/rate variation을 둔다. 주입은 명시한 elapsed interval에 적용한다.
2. `interfaces/brake/PressureMeasurement`에 model epoch·acquisition sequence/source time·측정 압력을 둔다.
   Hold/invalid/override는 sensor port에 적용하며 application 재시작으로 물리 상태나 acquisition 번호를 초기화하지 않는다.
3. `vecu/brake/BrakeResponseMonitor`는 발행한 bounded target 이력과 local sensor만 읽는다.
   Plant header·truth getter·고장 주입 flag를 읽지 않는다. 첫 측정으로 초기 압력을 잡은 뒤
   정상 예측 범위를 매 측정으로 재설정하지 않는다.
4. 50 ms delayed target과 방향별 정상 rate 범위로 pressure interval을 전파한다.
   가압/감압 각각 nominal의 0.8..1.2배, interval 밖 허용 오차 25 kPa다.
   범위 초과가 새 acquisition의 source time으로 60 ms 지속되면 ResponseError를 latch한다.
   Pending은 DEGRADED, 정상 관측 복귀 시 pending은 해제한다. Cached read는 확인 시간을 진행시키지 않는다.
5. Source age 20 ms 초과·acquisition gap 30 ms 초과는 SensorUnavailable이다.
   Missing, NaN/범위 밖, wrong epoch, future/pre-session time, identity 변경·역행을 검사한다.
   Gap은 관측 연속성 고장을 latch하지만 새로 취득한 개별 유효 압력의 보고까지 막지는 않는다.
6. BrakeActuator는 같은 thread의 SIL composition adapter로 유지한다.
   End acquisition/monitor 뒤에 정상 목표를 stage하고 새 출력은 이후 물리 구간에 적용한다.
   첫 fault에서 normal pending을 취소하고 **increase-only/floor 출력 primitive**를 요청한다.
   이는 plant가 floor 아래에서는 유한 가압하고 위에서는 감압하지 않는 명시적 SIL 가정이다.
   ECU가 hidden actual getter로 보호 목표를 계산하지 않는다. 실제 밸브/펌프 제어 구현은 아니다.
7. 보호 요청 뒤에도 stuck/저하 주입을 계속 적용한다. 따라서 floor에 못 도달할 수 있다.
   `protection_floor_observed`는 새 유효 센서의 floor 이상 여부만 보고하며 센서 무효/캐시일 때 unknown이다.
   이 값이 true여도 감압 성공·센서 정확성·차량 정지나 안전성을 증명하지 않는다.
8. Existing command loss/continuity/clock/gap·새 trusted application epoch 정책을 유지한다.
   Gap interval은 물리를 backfill하지 않는다. 새 epoch는 latch/pending을 지우고 물리 상태를 보존한다.
   Sensor fault의 원인이나 persistent stuck을 재시작으로 수리하지 않는다.
9. CAN ID/DBC/P05/layout은 변경하지 않는다. 새 유효 acquisition만 pressure Actual에 싣고,
   캐시/무효는 unavailable로 발행한다. FAIL_SAFE와 유효 압력은 함께 존재할 수 있다.

<a id="adr-0031-한계와-검증"></a>

### 한계와 검증

ResponseError는 정상 응답 계약 위반이며 기계 stuck과 plausible sensor freeze/bias의 고유 원인 분리가 아니다.
Excitation이 없거나 정상 예측 interval이 고정 압력을 포함하면 stuck을 검출하지 못할 수 있다.
현재 fixed delay·bounded rate 모델 밖의 compliance/온도/유체·누설·ABS·센서 이중화는 미구현이다.
수치는 시험 fixture이며 OEM calibration/FTTI/stream-loss 100 ms 검출 budget으로 채택하지 않는다.

새 시험 40개(plant 10·monitor 16·adapter 14), 기존 Brake adapter 16개와 전체 unit을 검사한다.
CLI는 기존 `brake-model`에 8개 scenario를 둔다. 새 executable/고장 CAN frame은 추가하지 않는다.
기존 model vCAN 8개는 회귀이며 새 pressure fault의 network 시험은 아니다.
[학습 안내](../learning/vehicle-models-guide.md)와 [품질 기록](../development-guide.md)에 결과·재현 절차를 둔다.

SYS-ARCH-002·SYS-COM-004·SYS-SAFE-001/002/003과 TC-CTRL-001·TC-SAFE-001/002의 local 부분 증거다.
전체 system TC는 NOT RUN, M1/M2 학습자 수용은 PENDING이다.
독립 task/watchdog·trace는 M3, Zone/Central 통합은 M4/M5, 차량 검증은 M6/M7, DTC는 M9에 남긴다.

<a id="adr-0032"></a>

## ADR-0032: ECU 판단과 SIL 실행 연결의 분리

Date: 2026-10-16. Status: **IMPLEMENTED / Host component checks; 실제 task/watchdog는 후속**.
2026-10-18 follow-up: Drive torque의 같은 job 취득 제한·보조 시각 관계는 [ADR-0036](#adr-0036)으로 개정했다.
아래는 경계 분리 당시의 결정 기록이다.
ADR-0019/0020/0023/0027/0030/0031의 같은-thread composition을 세분화한다.
기존 wire·물리 수치·통신 상실 정책과 학습자 수용 상태를 변경하지 않는다.

<a id="adr-0032-문제와-결정"></a>

### 문제와 결정

SteeringActuator·BrakeActuator·DriveActuator·DriveController가 physical response 객체를 직접 소유했다.
M3에서 이 `tick` 전체를 ECU execution으로 측정하면 물리 적분/센서 취득 비용까지 포함된다.
ECU 호출 중단과 plant 진행 중단을 따로 시험하기도 어려웠다.

1. 네 `vecu` 클래스에서 물리 객체·모델 header·고장 주입 인자를 제거한다.
   수신 검증·목표/한계·고장 판단·상태 보고만 소유하고 측정은 typed port로 받는다.
2. `interfaces/{steering,brake,drive}/*actuation.hpp`에 출력 mode·bounded target·issued time을 둔다.
   Drive의 envelope/response calibration도 plain interface data다. Calibration의 initial 값은
   기존 fixture 호환/검증을 위해 남기지만 실제 초기 상태는 SIL plant만 적용한다.
3. Trusted 시작 입력은 `ActuatorSession`으로 app/model epoch·enable time을 묶는다.
   Single-owner job을 `prepare(now)`와 `complete(sensor, now)`로 나눈다.
   Prepare는 clock/period/input을 검사하며, complete는 같은 job 시각의 snapshot을 받아 보고한다.
   미완료 prepare를 새 시각에서 건너뛰면 ControlDeadline, 잘못된/반복 complete는 발행하지 않는다.
   Caller는 두 phase 사이에 나중 시각의 RX/센서 갱신을 끼워 넣지 않고 입력을 직렬화해야 한다.
4. `simulation/steering/SteeringSil`, `simulation/brake/BrakeSil`,
   `simulation/drive/DriveActuatorSil`·`DriveSil`이 기존 예제의 연결을 맡는다.
   물리 진행·센서 생성·고장 주입·출력 적용은 이 SIL 코드에서 수행한다.
   실제 runtime은 ECU/plant를 각각 소유해 독립적으로 진행할 수 있다.
5. 기존 endpoint 상실·gap 정책을 회귀 유지한다. SIL helper는 fault를 확인한 시각 전에 보호 motion을
   소급하지 않고, 관측하지 못한 control gap interval은 catch-up하지 않는다.
   별도 실행자가 이미 진행시킨 물리 상태를 ECU 복귀 때 과거 값으로 되돌리지 않는다.
6. Actual은 센서에서만 채운다. Steering/Brake의 지연된 새 측정은 acquisition source time을 보존한다.
   Drive는 현재 wire의 torque timestamp가 별도로 없고 다른 channel의 생성 시각도 함께 다루므로
   **그 job의 end 시각에 새로 취득한 torque만** 유효 scalar로 발행한다. Cached/지연 측정은 torque unavailable,
   30 ms 초과 age·wrong epoch/time/identity/range·missing은 TorqueFeedbackUnavailable로 latch한다.
   Speed/capability의 기존 독립 validity/원천 metadata는 유지한다. 새 fault enum은 기존 값 뒤에 추가한다.
7. CMake의 ECU library는 simulation library에 의존하지 않는다. SIL library가 ECU와 plant를 조합한다.
   기존 예제/통합 fixture/모델 회귀시험은 명시적인 SIL class를 사용한다.
8. `actuator_demo`는 실행 파일 하나를 유지한다. 명령/도움말은 `tools/actuator_demo.cpp`,
   도메인 구현은 `tools/demo/{steering,brake,drive,ev}_demo.cpp`로 나눈다.

<a id="adr-0032-검증과-남은-범위"></a>

### 검증과 남은 범위

Core만 link하는 `ecu_boundary_test` 18개는 simulation include path/plant library 없이 동작한다.
기존 세 actuator 시험 파일에는 ECU 호출 중단 중에도 외부 plant가 계속 진행하고,
복귀 때 이미 발생한 물리 응답을 되돌리지 않는 3개 case를 추가한다.
기존 470개를 포함해 전체 491개 unit, CLI 90개 출력/exit code 비교, 기존 model vCAN 8개를 회귀 검사한다.
실제 실행 결과는 [품질 기록](../development-guide.md), API/읽는 순서는 [학습 안내](../learning/vehicle-models-guide.md)에 둔다.

Prepare/complete는 동기 SIL 경계이며 OS scheduling, mutex/queue나 독립 watchdog의 구현이 아니다.
M3에는 각 ECU phase와 physics 비용을 구분할 trace, release/clock ownership, job deadline,
정지 감시 독립성과 bounded handoff를 별도로 구현·측정해야 한다.
완성된 runner 전체 시간을 ECU execution이라고 보고하지 않는다.
M1/M2 학습자 수용은 PENDING, 32개 요구/29개 system TC 전체 Result는 NOT RUN이다.

<a id="adr-0033"></a>

## ADR-0033: 첫 wall-time ECU 실행과 독립 deadline 감시

Date: 2026-10-16. Status: **M3 첫 Steering Host component 구현·검사 / 다른 task·Target/E2E 후속**.
TBD-04의 부분 결정이다. 전체 task 배치·Target·차량 deadline을 확정하지 않는다.

<a id="adr-0033-결정"></a>

### 결정

[ADR-0032](#adr-0032)의 ECU/plant 분리를 사용해
Steering 한 경로부터 Linux Host의 실제 주기 실행과 계측을 연결한다.
M2의 deterministic SIL과 회귀시험은 그대로 유지한다.

- `vecu/common/periodic_task`는 유한한 absolute release schedule과 독립 completion monitor를 제공한다.
  Period와 relative deadline은 별도 입력이다. 늦은 실행은 최신 release 하나만 선택하고
  이전 job은 skipped로 남긴다. Catch-up burst나 release 시각 재설정으로 지연을 감추지 않는다.
- Monitor는 실행 thread의 callback·ECU 객체·handoff mutex를 사용하지 않는다.
  사전 할당한 job별 lock-free completion timestamp를 관측한다.
  시작하지 않은 job도 deadline에 완료가 없으면 miss다. Late completion은 latch를 지우지 않는다.
- 첫 실행 fixture는 ECU 10 ms, relative deadline **5 ms**, monitor/plant 각각 2 ms,
  120 jobs, 첫 release는 enable + 10 ms다. Deadline 5 ms는 overhead와 fault 검출을 비교할
  **local 실험 설정**이며 period로부터 도출한 값이나 실차 요구가 아니다.
- ECU·monitor·plant는 별도 owner로 실행한다. Monitor의 latch는 plant의 Hold override로 연결한다.
  ECU를 멈춰도 감시와 물리/센서 취득은 진행한다. Plant는 action을 실제 관측한 시각부터 적용하며
  이전 interval을 되돌리지 않는다. 이 override는 실험용 containment이며 차량 안전 정책을 대신하지 않는다.
- Command는 별도 plant/fixture owner가 생성하고 sensor와 함께 latest snapshot으로 넘긴다.
  단일 생산자·단일 소비자의 세 고정 slot을 atomic exchange로 교환하며 읽는 slot을 생산자가 덮어쓰지 않는다.
  잠금 대기·재시도 loop·실행 중 메모리 할당 없이 최신 값을 복사한다. 중간 snapshot 대체 횟수와
  실제 trace drop은 별도로 계수한다. FIFO와 snapshot을 같은 의미로 취급하지 않는다.
- Runtime은 monotonic wall time으로 absolute sleep한다. ECU phase의 논리 job 시각은 start에서 고정하고
  완료 직후 실제 wall-time deadline을 다시 검사한다. 늦은 출력·feedback은 발행하지 않는다.
  Steering core의 최소 호출 guard는 이 fixture에서 1 ms로 두고 release period는 10 ms로 유지한다.
  실제 start jitter 때문에 두 호출 간격이 10 ms보다 조금 짧아지는 것을 task 누락으로 오인하지 않기 위함이다.
  M2의 10 ms 최소 호출 설정과 모델 수치는 변경하지 않는다.

<a id="adr-0033-계측과-검사"></a>

### 계측과 검사

Job release/start/end·deadline·skipped/late completion과 ECU prepare/complete 비용을 기록한다.
Physics/capture 비용은 plant owner에서 별도로 기록한다. 전체 runner 시간을 ECU execution으로 쓰지 않는다.
Trace는 시작 전에 공간을 확보하고 실행 뒤 CSV로 쓴다. File I/O를 계측 구간에 넣지 않는다.
상세 trace와 최소 계측을 같은 workload로 비교하고 clock read 비용도 별도로 관측한다.

Schedule overflow·release 선택, deadline 경계, 미시작/누락/지연 완료·clock 오류와
snapshot의 concurrent payload/identity를 새 unit 14개로 검사했다. 기존 491개를 포함해
normal·ASan/UBSan 각각 전체 505개가 PASS다.
Normal, 최소 계측, bounded overrun과 stall을 각각 normal·sanitizer에서 3회,
BUILD_TESTING=OFF build에서 1회 실행했다. Monitor 검출·plant Hold·late feedback 억제와
누락 job의 분모 포함을 확인했다. 무한 hang의 강제 종료와 process/OS 고장 격리는 이번 thread fixture 범위 밖이다.

[Timing 계약](../requirements/timing-requirements.md)의 Mean/P95/P99/Max·sample/drop/miss와
환경/clock/빌드/계측 조건을 보고한다. 관측 최대값을 WCET bound라고 하지 않는다.
SCHED_OTHER의 Host 결과는 실제 MCU/AUTOSAR OS, RT priority, Target scheduling과 전체 E2E의 증거가 아니다.
TC-PERF-001/002와 SYS-PERF 요구의 부분 component 근거로만 연결한다.

<a id="adr-0034"></a>

## ADR-0034: 여러 Leaf 작업의 주기 실행과 CAN 수신 상실 감시

Date: 2026-10-16. Status: **M3 Host component 구현 / 검사 결과는 품질 기록에 연결**.
2026-10-18 follow-up: 비동기 torque/Actual CAN·6개 stream·RX drain tail은 [ADR-0036](#adr-0036)으로 확장했다.
아래는 다섯 입력 stream을 사용한 첫 결정 기록이다.
[ADR-0033](#adr-0033)의 Steering 실행을 유지하고
Brake·Drive gate·BMS·Power와 실제 SocketCAN RX를 한 finite Host 실험에 연결한다.
기존 Central/Front/Rear 배치와 AUTOSAR stack의 채택 상태를 변경하지 않는다.

<a id="adr-0034-실행과-시계"></a>

### 실행과 시계

- Brake/Drive/Power는 10 ms, BMS는 20 ms, RX는 2 ms absolute release를 사용한다.
  Relative deadline은 각각 5/5/5/8/3 ms로 별도 선택한다. 모두 local 실험 값이다.
  각 runnable에 별도 thread·completion ledger를 두며 monitor와 plant는 각각 별도 owner다.
  Core의 최소 호출 guard는 1 ms이며 실제 runnable period와 구분한다.
- 2.4 s workload와 감시 종료 여유 40 ms를 명시한다. BMS/Power의 초기 release offset은 5/8 ms다.
  BMS의 fresh-input release dwell, 실제 precharge/READY와 Drive gate를 기존 controller가 판단한다.
  외부 speed 20 rad/s, Central request/grant와 limits relay는 명시적인 fixture다.
- 하나의 physical owner가 BrakePressureResponse·Drive torque와 EvPowerModel을 진행한다.
  실제 torque/DC·접점·RC bus·Battery SOC와 센서를 연결하며 초기화 이후 energy owner는 하나다.
  출력·보호 flag는 **적용 기준 시각을 읽기 전에** snapshot으로 취득한다.
  계산 도중 도착한 새 결정은 다음 interval에 적용해 검출 전으로 보호를 소급하지 않는다.
- 모든 clock은 같은 process의 CLOCK_MONOTONIC이다. Source/dependency를 재발행 시각으로 바꾸지 않는다.
  ECU phase, job 전체, 외부 physics를 분리해 기록하며 기록 공간은 실행 전에 확보한다.

<a id="adr-0034-can과-trusted-context"></a>

### CAN과 trusted context

격리된 vCAN에서 Brake/Drive Command, routed BMS limits, Drive permission, Power request를
실제 socket으로 보낸다. RX owner는 poll당 최대 8개를 round-robin으로 읽고 SO_RXQ_OVFL을 보존한다.
각 ECU는 자기 receiver로 CRC/P05·Epoch·source/sequence·parent를 검증한다.
단일 생산자·단일 소비자의 latest snapshot은 소비자별 별도 인스턴스다.
중간 snapshot 대체와 kernel/trace 유실은 같은 지표가 아니다.

Trusted issuer는 원래 발급한 frame과 parent context의 최근 4개 이력을 CAN 밖의 별도 port로 전달한다.
수신한 frame의 exact envelope/payload에 맞는 context만 사용한다.
CAN을 읽어 parent를 자동 생성하지 않으며, 이력이 없거나 만료된 frame은 기존 receiver 검증에서 거부한다.
Application Epoch 1/model Epoch 7은 격리된 fixture 설정이며 실제 영속 session protocol은 후속이다.

<a id="adr-0034-독립-감시와-보호"></a>

### 독립 감시와 보호

Job completion과 유효 application RX age를 별도 감시한다. CRC 실패·duplicate·stale 수신은
last-valid 시각을 갱신하지 않는다. Accepted timestamp를 먼저 capture한 뒤 monitor now를 읽어
동시 publication을 미래 시각으로 오인하지 않는다.
ReceiveWatch의 80 ms threshold와 실제 검출까지의 <=100 ms budget을 따로 검사한다.
Startup acquisition, timeout/clock latch와 late input의 자동 복구 금지를 유지한다.

| 원인 | 첫 fixture의 독립 action |
| --- | --- |
| Brake job/RX job 상실 또는 Brake stream timeout | increase-only/floor 1 MPa 요청 |
| Drive/BMS/Power/RX job 상실 또는 Drive/Power critical stream timeout | 유한 rate의 Drive zero-target 요청 |
| BMS job 상실 | Power runnable의 BMS gate를 unknown/inhibit로 전달 |
| Power job 정지 | Drive zero를 요청하고 마지막 coil 출력을 유지; 맹목적인 contactor open을 하지 않음 |

Power가 실행 가능한 경우 실제 current dwell→open→방전 종료를 기존 controller가 처리한다.
120 ms bounded stall 후 복귀와 통신 상실을 검사한다. 영구 Power 고장, 독립 전기 차단 장치나
차량 전체 제동/정지 성공을 검증한 정책은 아니다. 새 trusted INIT 없이 보호 latch를 풀지 않는다.

<a id="adr-0034-drive-torque-보고의-경계"></a>

### Drive torque 보고의 경계

현재 wire는 torque 자체의 acquisition timestamp를 별도로 갖지 않으며,
speed/capability timestamp는 전체 report source보다 나중일 수 없다.
ADR-0032의 같은 job end 취득 규칙을 유지하므로 **비동기 torque scalar는 CAN에서 unavailable**이다.
측정 값을 job 시각으로 retimestamp하지 않는다. 실제 torque는 독립 physical trace에 보존하고
Drive의 입력 gate·target·보호 응답을 측정한다. Actual CAN 송신/독립 feedback RX의 검증 완료를 주장하지 않는다.
Sampling 동기화 또는 timestamp 계약 개정은 별도 결정과 receiver/ICD/DBC 회귀가 필요하다.

<a id="adr-0034-검증-범위"></a>

### 검증 범위

정상/최소 계측, Brake·Drive·BMS·Power·RX 각각의 120 ms 정지, 지속 CRC 손상을 구분한다.
모든 예정 job을 분모에 포함하고 독립 검출→보호 적용의 순서를 확인한다.
CRC가 틀린 raw traffic이 계속되어도 5개 critical stream은 유효 RX 상실을 검출해야 한다.
기존 Steering 실행, 전체 unit/ASan·UBSan, production build와 정적 분석을 회귀한다.
결과와 실행 방법은 [M3 학습 안내](../learning/runtime-timing-guide.md)와 [품질 기록](../development-guide.md)에 둔다.
고정 부하·CPU 배치/우선순위·Target·전체 E2E는 후속이며 system TC의 NOT RUN은 유지한다.

<a id="adr-0035"></a>

## ADR-0035: 고정 부하와 CPU 배치를 구분하는 Host 실험

Date: 2026-10-16. Status: **M3 Host 실험 구현 / 측정 결과는 품질 기록에 연결**.
2026-10-18 follow-up: [ADR-0036](#adr-0036)은 Actual RX 비용과 drain tail을 추가한다.
아래 실험 protocol은 유지하며 10월 16일 측정과 새 workload 결과를 구분한다.
후속 [ADR-0037](#adr-0037)은 이 비교를 보존하고 owner별 CPU map 실험을 추가한다.
[ADR-0034](#adr-0034)의 ECU 기능·period/deadline·CAN 계약을 유지한다.
TBD-04의 부하/배치 측정 protocol 부분 결정이며 Target/차량 budget 확정은 아니다.

<a id="adr-0035-결정"></a>

### 결정

기존 timing runner에 `--experiment cpu-placement`를 추가한다. 새 executable이나 ECU의 load 분기를 만들지 않는다.
모든 runtime owner 7개를 allowed logical CPU A에 고정하고 아래 조건을 비교한다.

| Layout | Runtime | 별도 load process |
| --- | --- | --- |
| baseline | CPU A | 없음 |
| shared | CPU A | CPU A |
| separate | CPU A | 다른 CPU B |

CPU는 부모의 allowed mask 안에서 선택한다. B는 가능하면 SMT sibling과 다른 physical core를 고른다.
Topology가 없거나 사용자가 같은 core의 다른 logical CPU를 명시한 경우도 실제 topology를 기록하며 물리 격리를 주장하지 않는다.
부모 runner의 mask는 변경하지 않고 runtime child가 exec 전에 affinity를 설정해 모든 thread가 상속한다.
각 owner가 직접 capture한 mask·observed CPU·policy/priority를 결과와 대조한다.
SCHED_OTHER·상속된 nice를 유지하고 RT scheduling/priority 변경은 하지 않는다.

<a id="adr-0035-부하의-의미와-수명"></a>

### 부하의 의미와 수명

별도 process가 10 ms absolute release마다 7 ms wall busy window를 요청한다.
이는 요청 duty 70%이며 실현된 CPU 사용률 70%를 보장하지 않는다. 선점·부하 worker의 누락 cycle도 원래 release와 함께 기록한다.
실제 busy 구간의 thread CPU time과 wall interval을 측정하고, runtime 측정 window에 완전히 포함된 busy 구간의 CPU 합을 하한,
겹치는 busy 구간 전체의 CPU 합을 상한으로 보고한다. 경계 cycle의 CPU를 비례 배분해 만들어내지 않는다.
이 경계는 busy 계산에 한정하며 bookkeeping을 포함한 worker loop 전체의 process CPU 비율은 별도 기록한다.

Run마다 worker를 새로 만들고 ready handshake 후 runtime을 시작한다. Worker는 measurement window 전체에 걸쳐 살아 있어야 한다.
Runtime/analysis 실패에도 finally에서 stop→결과 수집→join을 수행하고, 필요하면 자신이 만든 child만 terminate/kill한다.
강제 종료/worker 오류는 control FAIL이다. 15 s hard limit은 남은 worker를 제한하며 정상 측정 길이는 기존 2.4 s+tail 40 ms다.
Trace와 worker 결과는 실행 중 파일에 쓰지 않고 종료 후 보존한다.

<a id="adr-0035-반복판정"></a>

### 반복·판정

각 layout의 full/minimal trace를 기본 3회, 총 18 runs 실행한다. Layout 순서는 반복마다 회전하며 full/minimal 순서도 번갈아 쓴다.
Warm-up 제외는 0이다. CPU 시간·release 지연·job elapsed·deadline miss/skip은 별개다.
조건별 individual sample로 Mean/P95/P99/Max를 만들며 다른 layout/주기의 sample을 섞지 않는다.
여러 run 사이 공백은 task interval에 포함하지 않는다.

기존 normal 계약은 유지한다. 부하에서 deadline/물리 목표/valid RX 계약 위반이 있으면 FAIL과 nonzero exit를 유지한다.
실패 run도 schedule/interval이 유효하면 모든 job을 통계에 남긴다. 통계에 넣을 수 없는 run은 label을 명시한다.
배치·부하 적용 성공과 ECU 계약 충족을 구분하고, 실패 조건을 조용히 재실행하거나 threshold를 바꿔 PASS로 만들지 않는다.
Full/minimal 차이에는 scheduling/cache와 fault path 차이가 포함될 수 있어 계측 비용의 상한으로 쓰지 않는다.

<a id="adr-0035-범위와-후속"></a>

### 범위와 후속

CPU affinity는 resource reservation이나 fault isolation이 아니다. Monitor와 plant도 같은 CPU를 공유하는 비교이며
host/VM의 다른 process·interrupt·DVFS·cooling은 통제하지 않는다. Controller/plant/transport 비용의 대표 WCET도 아니다.
Sanitizer는 기능/수명 검사이며 성능 비교의 대표 값으로 사용하지 않는다.
결과는 [학습 안내](../learning/runtime-timing-guide.md)와 [품질 기록](../development-guide.md)에 연결한다.
Drive sampling/timestamp 계약, 실제 priority/owner별 배치·Target 검증과 M3 수용 검토는 후속이다.
전체 32개 요구/29개 system TC의 NOT RUN은 유지한다.

<a id="adr-0036"></a>

## ADR-0036: 비동기 Drive Actual의 취득 시각 보존과 CAN 수신

Date: 2026-10-18. Status: **Host component 구현 / 검증 결과는 품질 기록에 연결**.
[ADR-0034](#adr-0034)의 비동기 torque unavailable 후속 결정이다.
Central/Zone/DDS·차량 배포 구조와 기존 task deadline은 유지한다.

<a id="adr-0036-시간-계약"></a>

### 시간 계약

기존 [Drive wire](../interfaces/drive-frame.md)의 Actual SourceTimeNs는 이미 토크 취득 시각이다.
새 유효 torque sample을 job과 같은 시각에만 발행하던 sender 제한을 풀고 원래 sample/value/identity 검사를 유지한다.
같은 sample을 다시 읽는 것은 새 측정이 아니며 torque unavailable로 보고한다. 이때 header source는 진단 생성 시각이다.
유효 Actual의 header를 report generation/TX 시각으로 바꾸지 않는다. Report generation은 runtime trace에 별도 기록한다.
Trace의 generation_ns는 ECU에 전달한 논리 job 시각(phase_ns)이며 실제 직렬화 완료 시각과 구분한다.

Speed와 capability는 독립된 source를 갖는다. Receiver는 각 시각을 session/now와 비교하며 torque 취득보다 늦다는 이유로 제거하지 않는다.
각 age·range·cursor와 capability input≤calculation, oldest dependency budget은 유지한다.
Torque의 엄격히 증가하는 source와 30 ms age, 80 ms latched RX timeout도 유지한다.
보조 feedback·새 report Sequence로 같은 torque의 critical freshness를 갱신하지 않는다.

CAN ID 0x282/64 bytes/schema 2/P05 DataID 0x1202·CRC coverage와 모든 golden byte는 동일하다.
새 timestamp field나 quantization을 추가하지 않는다. 기존 receiver는 더 늦은 보조 시각을 Invalid로 제거할 수 있으므로
sender/consumer 정책을 함께 검토한다. Wire baseline 채택·학습자 review는 여전히 PENDING이다.
CausalSequence는 마지막 수용 Command 문맥이며 지연된 토크 응답의 원인 증명으로 사용하지 않는다.

<a id="adr-0036-실제-송수신"></a>

### 실제 송수신

Physical owner가 bounded Drive output snapshot의 timely report를 별도 Actual socket frame으로 송신한다.
기존 RX worker에 0x282 전용 socket과 별도 DriveReceiver를 두며 payload를 로컬 함수 반환으로 대체하지 않는다.
독립 수신부의 Accepted만 여섯 번째 atomic valid-RX 시각을 갱신한다. Monitor의 80 ms threshold/검출 <=100 ms와
Drive zero latch에 연결하며 ECU job 감시와 구분한다. P05/metadata/state·보조 quality는 실제 receiver가 판정한다.
Task count는 유지하며 round-robin RX budget 8에 Actual도 포함한다.

마지막 2.4 s ECU job의 응답을 비우기 위해 RX를 20 ms 더 실행한다(2 ms×1210 jobs).
마지막 RX deadline 2.423 s 뒤까지 기존 monitor/plant tail 40 ms가 유지된다.
출력·보호 snapshot 취득 뒤 적용 시각을 읽는 인과 순서도 유지한다.
Trace schema는 3으로 구분하고 이전 schema 2 기록의 분석을 보존한다. 이는 CAN wire schema와 별개다.

TX/RX full payload bytes·job generation/acquisition·socket begin/end·raw arrival/Accepted·usable 값을 사전 할당한 owner별 buffer에 보존한다.
실행 후 CSV로 쓰며 모든 Accepted payload를 원래 TX bytes와 producing job에 연결한다. Torque 양자화 한계 0.05 N·m도 확인한다.
Minimal trace도 동일 송수신/검증 경로를 실행하고 aggregate count를 보존한다.

<a id="adr-0036-상실과-범위"></a>

### 상실과 범위

`feedback-replay`는 1.1 s 이후 한 Actual frame의 P05 counter/Sequence/source/value를 그대로 반복한다.
CRC-valid raw traffic이 계속되어도 valid RX는 갱신되지 않고 Actual stream만 상실을 검출해야 한다.
다른 다섯 입력 stream은 계속 수용되며 독립 Drive zero 요청과 유한 물리 응답을 확인한다.
현재 sample의 30 ms source 만료와 communication의 80 ms valid-RX timeout은 별개다. Stale sample으로 fallback하지 않는다.
Late frame이나 normal 입력으로 receiver/protection latch를 자동 복구하지 않는다.

이는 실제 CAN input/Actual feedback의 Host component 실험이며 Actual을 CARLA에 반영하는 Central/Zone/Host bridge의 구현은 아니다.
Physical owner는 실제 actuator·회로·Battery를 계속 진행하고 CAN feedback을 다시 물리 truth에 덮어쓰지 않는다.
앞선 [CPU 부하 실험](../learning/runtime-timing-guide.md)은 다섯 stream workload의 이력이다. 새 RX 작업량과 구분한다.
Owner별 배치/우선순위·Target/E2E·M3 수용은 후속이며 전체 32개 요구/29개 system TC는 NOT RUN이다.
실행 방법은 [Drive Actual 안내](../learning/runtime-timing-guide.md), 실제 검사 수치·실패와 증거는 [품질 기록](../development-guide.md)에 남긴다.

<a id="adr-0037"></a>

## ADR-0037: RX·감시·물리 실행 owner의 CPU 배치 비교

Date: 2026-10-18. Status: **Host 비교 구현 / 결과·제한은 품질 기록에 연결**.
[ADR-0035](#adr-0035)의 같은 CPU 부하에서 RX job이 생략됐고,
[ADR-0036](#adr-0036)의 여섯 stream workload에서도 재현했다.
후속 [ADR-0038](#adr-0038)은 감시·물리 전체 cycle 계측과 RX miss의 시간 대조를 추가한다.

<a id="adr-0037-관측과-결정"></a>

### 관측과 결정

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

<a id="adr-0037-비교-조건"></a>

### 비교 조건

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

<a id="adr-0037-해석과-후속"></a>

### 해석과 후속

Thread가 달라도 같은 CPU의 실행 지연을 공유할 수 있다. RX만 빠른 것과 센서→ECU→송신→수신이 제시간에
완료되는 것은 별개다. `expired_outputs`, Actual의 sent/received/accepted/expired, 모든 task의 miss/skip,
독립 검출·실제 보호 시각을 함께 확인한다. PASS run만 골라 latency를 비교하지 않는다.

Affinity는 CPU 예약이나 물리적 watchdog 격리가 아니다. 이 Host에서 여러 번 통과해도 다른 부하/VM/Target의
실시간 보장은 아니다. Sanitizer는 기능·수명 확인으로 분리한다. Per-owner RT priority, monitor/plant 전체 cycle의
실행 budget과 watchdog 독립성, Target/차량 E2E는 후속이며 M3 전체 수용을 선언하지 않는다.
전체 32개 requirement/29개 system TC의 Result는 NOT RUN이다.
재현 명령·측정은 [CPU 배치 학습 안내](../learning/runtime-timing-guide.md)와 [품질 기록](../development-guide.md)을 따른다.

<a id="adr-0038"></a>

## ADR-0038: 감시·물리 owner의 전체 cycle 계측과 RX 시간 대조

Date: 2026-10-18. Status: **Host 계측 구현 / 실행 budget 채택·M3 수용은 후속**.
후속 [ADR-0039](#adr-0039)가 Host 완료 budget과 교차 guard를 채택했다. 아래는 schema 4의 당시 결정이다.
[ADR-0037](#adr-0037)의 IO 분리 후에도 RX skip이 남았다.
당시 physical.csv는 physics/capture 일부만 재고 뒤의 fixture CAN TX를 포함하지 않아 전체 비용과 지연 위치를 구분하기 어려웠다.

<a id="adr-0038-기록-경계"></a>

### 기록 경계

Monitor는 valid-RX snapshot 읽기 전부터 task/stream 검사·보호 flag·상세 trace 기록 뒤까지 잰다.
Plant/fixture는 외부 보호/출력 snapshot 읽기 전부터 physics·actual 적용·센서 발행·Actual/명령/EV CAN TX·trace 기록 뒤까지 잰다.
Periodic sleep과 end 이후 cycle bookkeeping은 body 밖이다. 입력/보호 snapshot을 먼저 취득한 뒤 application/acquisition 시각을 읽는
기존 인과 순서를 유지한다. Body start를 원천 sensor 시각이나 보고 시각으로 대체하지 않는다.

각 owner에 enable부터 stop(2440 ms tail 끝)까지 2 ms 간격의 **1221개 기회**를 미리 할당한다.
실제 body는 시작 시점에 가장 최근 release에 대응시키고 이전 기회는 `ran=0`, 실행 시각은 0으로 남긴다.
Stop을 늦게 관측한 최종 body는 마지막 slot에 기록하며 관측 window 뒤의 예정 slot을 만들지 않는다.
이것은 관측용 grid이며 새 task deadline이나 watchdog latch를 도입한 것은 아니다.

Essential cycle CSV는 full/minimal 양쪽에 쓴다. 실제 sleep target, sleep 호출 직전, 반환 후 body start, 기존 phase, body end를 기록한다.
Full에서만 CLOCK_THREAD_CPUTIME_ID begin/end를 wall endpoints 안에서 읽는다. 서로 다른 thread의 CPU 절대 시각은 비교하지 않는다.
CPU clock 호출을 포함한 계측 비용을 deadline에서 빼지 않는다. CPU delta와 wall delta 차이도 정확한 scheduler 대기 원인으로 단정하지 않는다.
CSV는 기존 owner별 trace와 마찬가지로 실행 종료·join 뒤에 쓴다. 새 thread/executable은 만들지 않는다.

<a id="adr-0038-분석과-이전-기록"></a>

### 분석과 이전 기록

Trace schema는 **4**, CAN wire schema는 **2**다. Reader는 기존 trace schema 2/3을 원래 의미로 계속 분석한다.
`monitor-cycles.csv`, `plant-cycles.csv`의 전체 schedule·interval·CPU clock·expiry 합계를 검증한다.
Full의 원래 monitor/physical phase 및 physics/Actual TX가 전체 body 안에 있는지도 확인한다.

생략된 release는 이전 body 안, 다음 요청 wake 이전, 요청 wake 이후 중 어디에 있었는지 분류한다.
이 분류는 관측 구간의 위치이며 CPU queue/IRQ/VM 원인의 식별이 아니다. Sleep 호출 자체가 이미 늦은 경우도 따로 남긴다.
RX의 모든 miss(실행 생략·늦은 종료·monitor에서 미완료 관측)를 같은 grid의 두 owner slot 및 앞/뒤 phase와 대조한다.
동시 지연을 기록하되 공통 원인을 자동 추론하지 않는다. RX 단독 stall과 여러 owner의 동시 지연을 구분할 자료다.

정상 계약에 실패해도 유효한 cycle/job 관측은 보존한다. 불완전한 owner trace는 이유와 label을 명시해 owner 통계에서 제외하고,
유효한 ECU/RX job 통계는 유지한다. 여러 run 사이의 공백을 interval percentile에 넣지 않는다.
기존 CPU/owner 배치 비교에 owner별 통계·RX 대응을 추가하며 full/minimal·layout은 섞지 않는다.

<a id="adr-0038-계측-확인용-지연"></a>

### 계측 확인용 지연

기존 fault runner에 `monitor-overrun`, `plant-overrun`을 full/minimal 각각 추가한다. 각 owner의 첫 phase>=1100 ms에서
본문 끝에 한 번 **6 ms sleep**을 넣는다. CPU 부하를 늘리는 주입이 아니며 원래 120 ms ECU stall과 구분한다.
6 ms가 whole-body endpoint 안에 포함되고 이후 기회가 생략된 것을 검사한다. Owner deadline은 아직 미채택이다.

Plant 주입은 기다리는 동안 도착한 출력/Actual의 5 ms 시한을 넘길 수 있다. 각 plant cycle에 expiry delta를 기록하고
전체 count와 대조한다. 이 fault case는 expiry가 첫 후속 cycle에만 있는지, Actual sent+expired=240 및 sent=received=accepted인지,
실제로 송신한 Actual이 기존 TX admission deadline 안인지 검사한다. 주입과 무관한 expiry는 실패다.
Normal과 다른 fault의 기존 expiry 0 조건·ECU deadline·수신 age/timeout은 유지한다.
이 주입의 PASS는 지연/폐기 관측의 성공이며 정상 timing 충족을 뜻하지 않는다.

<a id="adr-0038-후속"></a>

### 후속

작업량·계측이 달라졌으므로 이전 schema의 성능 수치와 합치지 않는다. Actual source/phase/TX/RX의 의미는 유지한다.
관측 후 monitor/plant 전체 cycle budget과 감시 독립성, RT 적용 가능한 실행 환경/Target 검증을 검토한다.
전체 32개 requirement/29개 system TC의 Result는 NOT RUN이며 M3 전체 수용을 선언하지 않는다.
재현은 [전체 cycle 학습 안내](../learning/runtime-timing-guide.md), 실행 결과는 [품질 기록](../development-guide.md)에 남긴다.

<a id="adr-0039"></a>

## ADR-0039: 감시·물리 작업의 완료 시한과 교차 감시

Date: 2026-10-18. Status: **Host fixture 계약 채택·구현 / Target·전체 M3 수용 후속**.
[ADR-0038](#adr-0038)의 계측에서 짧은 body와 실행 누락이 함께 나타났다.
기존 정상 계약은 두 owner의 누락을 판정하지 않아 sanitizer RX 단독 분리가 각각 244개를 생략하고도 PASS였다.
이번 변경은 실행 budget을 명시하고 감시 작업 자체의 공백에서도 보호를 요청한다.

<a id="adr-0039-host-완료-계약"></a>

### Host 완료 계약

| 항목 | 기준 |
| --- | --- |
| Monitor·plant/fixture period | 기존 2 ms |
| 각 release 대비 completion deadline | **4 ms** |
| Guard 대상 | Enable부터 2420 ms까지 각각 **1211 slots** |
| 관측 tail | 기존 2440 ms까지 총 1221 slots; 마지막 guard deadline은 2424 ms |
| 검출 margin | Deadline 이후 <=10 ms, Host fault 시험의 수용 기준 |
| 적용 margin | 첫 owner fault 검출 이후 <=10 ms, plant가 실행 가능한 조건 |
| 정상 수용 | Guard 대상의 missed/skipped 0 + 기존 ECU/RX·수신·물리 계약 |

4 ms는 2 ms 주기와 추가 2 ms 완료 여유를 명시한 첫 Host budget이다. 직전 IO 분리의 body max는 약 0.15 ms
이하였지만 이 수치가 worst-case/Target 보장은 아니다. 원래 ECU 5/8 ms, RX 3 ms, RX budget 8,
유효 수신 threshold 80 ms·실제 검출 <=100 ms는 유지한다. 차량 calibration·전체 E2E/TBD-04는 남는다.

최신 release만 실행하는 기존 정책도 유지한다. 4 ms 안에 다음 작업을 끝냈더라도 **생략한 이전 slot은 별도 miss**다.
단순히 마지막 heartbeat가 최근인지 확인하는 방식으로 누락을 지우지 않는다. 마지막 10개 tail slot은 기록만 하고
guard 대상에서 제외한다. 마지막 guard deadline까지 서로를 관측한 뒤 종료하므로 tail의 tail을 무한히 추가하지 않는다.

<a id="adr-0039-교차-감시와-수신-감시"></a>

### 교차 감시와 수신 감시

기존 `DeadlineMonitor`를 각 owner에 하나씩 둔다. 본문 전체의 end를 찍은 뒤 해당 slot의 완료를 원자로 게시한다.
Monitor는 plant guard를, plant는 monitor guard를 poll한다. 각 guard의 poll cursor는 한 peer만 소유한다.
Peer가 deadline 이후에 늦은 완료를 처음 보더라도 miss를 검출하며 이미 걸린 fault는 해제하지 않는다.
Clock error도 보호 원인이다. 새 thread나 watchdog executable은 추가하지 않는다.

어느 owner fault든 기존 brake floor·torque zero flag를 latch한다. Plant는 peer 검사와 수신 감시를 먼저 수행하고
보호/출력 snapshot을 취득한 뒤 application clock을 읽는다. 다음 구간의 결정을 이전 physics 구간에 소급하지 않는다.
기존 유한 torque ramp와 brake increase-only floor를 사용한다. 이 fault만으로 contactor를 강제 개방하지 않는다.

6개 accepted-RX stream은 monitor와 plant가 **각자 별도의 ReceiveWatch 상태**로 감시한다. 같은 cursor/state를
두 thread가 poll하지 않는다. Accepted 시각 snapshot을 observer clock보다 먼저 취득한다. Raw/CRC-invalid traffic은
입력이 아니다. 두 observer 중 실제 검출이 빠른 기록을 effective loss로 선택하고 그 observer의 원래 last-valid와
detected 시각을 함께 보존한다. 늦게 복귀한 observer의 늦은 진단도 `observers`에 그대로 남긴다.
Monitor 120 ms 정지 중 보호 이후 끊기는 accepted stream도 plant가 <=100 ms로 검출하는지 확인한다.

Plant가 멈추면 monitor는 보호를 요청할 수 있지만 물리 모델은 plant가 돌아올 때까지 진행하지 못한다.
두 owner가 함께 쉬거나 process/OS가 멈추면 실행 가능한 observer가 없다. 복귀 시 늦은 완료는 검출하지만
그 공백 중 실제 출력을 변경했다고 주장하지 않는다. Hardware watchdog·OS/프로세스 분리·RT/Target 검증은 후속이다.

<a id="adr-0039-기록과-고장-시험"></a>

### 기록과 고장 시험

Trace schema는 **5**, CAN wire schema는 **2**다. 이전 trace 2/3/4는 당시의 의미로 계속 읽는다.
CSV는 guarded/deadline/detected를 추가하고 skipped row의 실행 시각은 0으로 유지한다. Tail에는 가짜 deadline을 만들지 않는다.
Metadata는 guard별 observer·first fault·clock error와 각 수신 observer 기록을 담는다. Full trace에는 owner fault mask
(monitor=1, plant=2)와 각 owner의 stream fault mask를 남긴다. CSV는 join 이후에 쓴다.

기존 9조건에 아래 4조건을 full/minimal 각각 실행하여 기본 fault matrix는 **17 runs**다.

| 조건 | 주입 | 확인할 동작 |
| --- | --- | --- |
| monitor-overrun | Body 끝에서 6 ms sleep | Plant가 monitor 복귀 전에 보호 |
| plant-overrun | Body 끝에서 6 ms sleep | Monitor가 정지 중 검출, physics 보호는 복귀 후 |
| monitor-stall | Body 끝에서 120 ms sleep | 독립 보호와 backup 수신 상실 검출이 정지 중 진행 |
| io-overrun | 두 owner가 각각 6 ms sleep | 복귀 후 late completion을 정상으로 숨기지 않음 |

주입은 첫 phase>=1100 ms에서 한 번이다. 검출/적용 margin, latch 유지, 유한 torque 감소·최종 floor를 검사한다.
실제 Actual의 bytes/source/admission 검사도 유지한다. 보호 전이에서 보고를 억제할 수 있으므로
Actual sent+expired는 **Drive의 reported job 수**와 맞춘다. 정상은 기존 240개다.
Plant 지연에서 발생한 expiry는 첫 후속 cycle에만 허용한다. 관련 없는 expiry나 ECU/RX miss는 FAIL이다.

<a id="adr-0039-배치-비교"></a>

### 배치 비교

`guard-placement`는 서로 다른 allowed CPU A/B/C를 선택하고 SCHED_OTHER를 유지한다.
C는 가능하면 A/B와 다른 physical core를 선택한다. 정상 full/minimal·회당 4 layouts를 순환하고 trace 순서를 교대한다.

| Layout | CPU A | CPU B | CPU C | 부하 |
| --- | --- | --- | --- | --- |
| io-control | RX·monitor·plant | ECU 4개 | 사용 안 함 | B |
| rx-separated | Monitor·plant | ECU 4개 | RX | B |
| guard-separated | RX·plant | ECU 4개 | Monitor | B |
| guard-baseline | RX·plant | ECU 4개 | Monitor | 없음 |

부하는 기존 10 ms 중 7 ms wall busy window 한 process다. 실제 affinity/policy·CPU 소비·실행 생존을 검증한다.
더 많은 CPU가 항상 낫다고 가정하지 않는다. 실패와 모든 유효 표본을 보존하고 이전 schema의 수치와 합치지 않는다.
설정은 [reference profile](../../profiles/reference.yaml), 실행/해석은 [학습 안내](../learning/runtime-timing-guide.md)에 둔다.
전체 32개 requirement/29개 system TC는 여전히 NOT RUN이다.

<a id="adr-0040"></a>

## ADR-0040: Steering RTOS 파일럿과 Host 실행 대기 관측

Date: 2026-10-18. Status: **옵션 Host 파일럿 구현 / Jetson·RTE/BSW·실시간 수용 후속**.
[ADR-0022](#adr-0022)의 작은 OS 파일럿을 진행한다.
기존 Linux 실행·CAN 계약·Central/Zone/Leaf 배포 계획은 유지하며 Steering 한 경로만 별도로 비교한다.

<a id="adr-0040-구현체와-실행-경계"></a>

### 구현체와 실행 경계

[Trampoline](https://github.com/TrampolineRTOS/trampoline)의 revision은
`third_party/trampoline.json`으로 고정한다. 생성 도구 GOIL과 가상 하드웨어 ViPer도 같은 소스에서 빌드한다.
Upstream은 OSEK/VDX·AUTOSAR OS 4.2 API alignment를 설명한다. 이 파일럿은 **OIL 2.5 OSEK 설정**이며
R25-11 Classic 적합성이나 ARXML/RTE/BSW 통합 결과가 아니다. 기존 R25-11 P05 wire 구현은 유지한다.
Upstream GPL v2 license 파일과 hash를 기록한다. Upstream checkout·생성 파일·연결 binary는 `build/`에 둔다.
정상 CMake 실행은 다운로드하지 않는다. 사용자가 명시한 build helper의 `--fetch`만 고정 revision을 받는다.
Root 프로젝트의 license나 Target OS를 이번 파일럿으로 변경하지 않는다.

| 실행자 | 책임 |
| --- | --- |
| Trampoline ReleaseDispatch, priority 5 | OS Alarm으로 실행, release 시각 게시 후 Control의 Event 설정 |
| Trampoline Watch, priority 4 | 5 ms 완료 budget 감시, 늦음/미완료 latch와 hold 요청 |
| Trampoline Receive, priority 3 | CAN Command·로컬 sensor channel을 각 8개까지 읽고 bounded mailbox 갱신 |
| Trampoline Control, priority 2 | Event 대기·mailbox snapshot·기존 SteeringActuator prepare/complete·Actual 송신 |
| 별도 Linux plant process | 2 ms 물리 진행·원래 센서 취득·ECU 출력 적용·Actual 수신 감시 |

Mailbox는 OS Resource로 보호하고 Control과 Receive만 접근한다. Control이 대기할 때 Resource를 보유하지 않는다.
OS kernel/Alarm/Event/Resource를 실제 빌드·실행하며 Linux pthread에 이름만 대응한 구현이 아니다.
ECU 판단 library에는 물리 모델을 링크하지 않는다. C ABI adapter가 기존 C++ ECU·codec·SocketCAN을 연결한다.
센서는 inherited Unix SOCK_SEQPACKET의 고정 크기 private packet으로 보낸다. 같은 Host clock의 취득 time/model identity를
그대로 전달하며 이 channel을 양산 sensor protocol로 간주하지 않는다. CAN Command/Actual은 기존 0x180/0x280·32-byte P05다.

Sensor/command 이전에 application clock을 읽지 않는다. Command의 accepted/source 시각, 센서 취득 시각과 Actual generation을
구분한다. Hold를 받은 plant는 실제 적용 시각에 이동을 취소하고 각도를 유지한다. 보호 flag와 실제 물리 적용은 별도다.
Parent Actual receiver의 유효 수신 상실도 hold를 latch한다. 복귀/재수신으로 보호를 자동 해제하지 않는다.
Application epoch 2/model epoch 1은 격리된 시험 fixture다. 실제 session coordinator·OS restart/rejoin은 후속이다.

<a id="adr-0040-가상-시간과-host-시간"></a>

### 가상 시간과 Host 시간

고정한 upstream POSIX target의 SystemCounter 입력은 **10 ms relative usleep timer**다. 수정하지 않았다.
Control/Receive/Watch/ReleaseDispatch는 각각 1 tick Alarm을 사용한다. OS tick이 Host wall time과 일치한다고 가정하지 않는다.
파일럿의 검출 margin 20 ms는 10 ms 감시 tick과 추가 한 tick의 Host dispatch 여유를 둔 시험 값이다.
5 ms budget의 기점은 **ReleaseDispatch가 게시한 실제 monotonic 시각**이다. Alarm 예정→ReleaseDispatch 실행 지연은
이 budget 밖이며 release interval과 첫 release 기준 nominal wall drift로 따로 기록한다.
밀린 Control Event는 합쳐질 수 있어 release별 행을 보존하고 실행하지 못한 행에도 Watch 검출을 남긴다.
놓친 virtual timer signal의 정확한 개수는 이 기록만으로 증명하지 않는다.

기존 [ADR-0039](#adr-0039)의 RX 2 ms/3 ms 시한과 owner 2 ms/4 ms 시한은 유지한다.
RTOS 파일럿의 기능 PASS를 기존 M3 정상 timing PASS로 대체하지 않는다. Hosted RTOS의 실행도 Linux/가상 환경 영향을 받는다.
이번 확인 target은 x86_64 Linux다. ARM64 Jetson 지원·실제 MCU/hypervisor 배포·Target latency는 NOT RUN이다.

<a id="adr-0040-호환-설정과-시험"></a>

### 호환 설정과 시험

POSIX port는 setjmp/longjmp로 별도 task stack을 전환한다. 현재 glibc의 fortified longjmp 검사와 충돌해
생성된 hosted C 쪽에만 `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0`을 적용한다. 일반 CMake 품질 설정은 유지한다. 유효한 stack 크기에서 해당 flag만 제거한 독립 호환 probe로도 abort를 재현했다.
Port의 stack-size 표현에 맞춰 task 49152 bytes/ISR 32768 bytes를 사용하고 overflow warning을 error로 처리한다.
Sanitizer/fiber 연동은 미검증이므로 hosted OS binary를 ASan/UBSan 수용 증거로 쓰지 않는다. 기존 native core/unit 검사는 별도 수행한다.
GOIL 생성 C의 upstream 경고와 직접 작성한 adapter의 정적 분석 결과를 구분한다.

정상, command-loss, CRC-corrupt, Control-stall 4조건을 실행한다. Control-stall은 12-tick Resume Alarm과
WaitEvent를 사용해 Control만 대기시킨다. Host thread 전체를 sleep시키는 주입이 아니다.
Watch가 복귀 전에 검출/hold하고 외부 plant가 진행하는지 확인한다. Late job의 Actual은 폐기한다.
보호 후 센서 Actual을 Command로 대체하거나 원래 취득 time을 새로 찍지 않는다.
Console shim은 자식 실패도 exit 0으로 끝날 수 있으므로 shutdown JSON·OS error·actual/source·물리 trace까지 검사한다.
Launcher는 자기 process group을 정리하며 실제 RTOS PID의 per-application POSIX IPC 이름만 정리한다.

<a id="adr-0040-지연-분석"></a>

### 지연 분석

Runtime ThreadInfo에 native TID를 추가한다. 기존 schema 5 metadata의 추가 필드이며 CAN/schema 계약은 유지한다.
진단 대상은 기존 native multirate Linux thread이며 RTOS 내부 Task별 trace가 아니다.
별도 observer가 `/proc/PID/task/TID/schedstat`의 CPU/queue/time-slice 누적값과 voluntary/involuntary switch를 읽는다.
`CONFIG_SCHED_INFO`와 probe 권한 상태, sample begin/end를 기록한다. 이 관측은 intrusive diagnostic이며 성능 baseline이 아니다.
누락 release 앞과 다음 실행 뒤를 완전히 덮는 표본 두 개가 있을 때만 delta를 계산한다. 경계 여유 시간과 불완전 coverage도 남긴다.
그 구간의 runqueue 대기 증가는 확인할 수 있지만 전부를 한 wakeup에 할당하거나 경쟁 process/IRQ/VM 원인을 단정하지 않는다.
Queue delta 0도 timer 지연의 증명이 아니다. 기본 커널의 timer→wakeup→switch 분리는 커널 trace가 필요하다.
현재 tracefs는 접근 거부, perf는 paranoid=4로 거부된다. 시스템 권한/커널 설정을 바꾸지 않고 원래 오류를 보존한다.
공식 참고: [schedstat](https://www.kernel.org/doc/html/latest/scheduler/sched-stats.html),
[event tracing](https://www.kernel.org/doc/html/latest/trace/events.html).

실행 방법은 [학습 안내](../learning/runtime-timing-guide.md), 최종 결과는 [품질 기록](../development-guide.md)에 둔다.
전체 32개 requirement/29개 system TC는 NOT RUN이며 M3 전체 종료나 AUTOSAR stack 채택을 선언하지 않는다.
후속 [ADR-0041](#adr-0041)은 ARM64 교차 빌드와 RT 권한 사전 점검을 추가한다.
2026-10-19 [ADR-0043](#adr-0043)은 이 최초 relative tick을
선택 가능한 원본 backend로 유지하고, 기본 build를 absolute timerfd로 변경했다. ResumeAlarm은 13 ticks이며 최소 120 ms 검사는 유지한다.
위 12-tick/relative 결과는 당시 이력이다. OS Task/Alarm/Resource와 wire 계약은 유지한다.
ARM64/RT 실행 수용은 계속 후속으로 유지한다.

<a id="adr-0041"></a>

## ADR-0041: ARM64 RTOS 교차 빌드와 Host RT 사전 점검

Date: 2026-10-18. Status: **빌드·점검 도구 구현 / Target 실행·RT timing 수용 후속**.

<a id="adr-0041-결정"></a>

### 결정

[ADR-0040](#adr-0040)의 Steering 파일럿을 다른 Leaf로 확대하기 전에
ARM64 Linux 빌드 가능성과 Host의 RT 시험 권한을 확인한다. Central/Zone/Leaf 배포 계획과 기존 M3 시한은 유지한다.

`tools/build_rtos_pilot.py --architecture aarch64`가 GNU Linux 교차 toolchain으로 기존 C++ library·외부 plant,
Trampoline POSIX OS·ViPer를 빌드한다. GOIL은 생성 작업을 수행하는 **Host 도구**, 나머지 세 실행 파일은
**대상 CPU용 코드**다. OIL의 compiler/assembler/linker를 같은 대상으로 지정한다. Native와 ARM64의 CMake
directory 및 ViPer object/output directory를 분리하고 upstream source는 수정하지 않는다.

일반 build의 다운로드·RTOS 옵션 정책은 유지한다. Toolchain을 자동 설치하지 않는다. 고정 upstream revision,
compiler target/sysroot·source/도구/실행 파일 hash·ELF machine·동적 loader/필요 library/symbol version을 `build.json`에 남긴다.
빌드 실패 후 이전 성공 manifest가 남지 않게 한다. 기존 CMake compiler 또는 output architecture가 다른 directory의
재사용을 거부한다. 실행기는 세 실행 파일의 실제 ELF architecture와 hash를 먼저 확인한 뒤 output/vCAN을 만든다.
다른 CPU용 파일을 실행 실패나 에뮬레이터 실행으로 우회해 native timing 표본에 넣지 않는다.

<a id="adr-0041-빌드와-실행의-구분"></a>

### 빌드와 실행의 구분

ARM64 ELF가 만들어져도 Jetson 지원 판정은 아니다. 현재 toolchain은 일반 GNU/Linux 환경이며 보드별 JetPack/BSP의
sysroot로 확정한 것이 아니다. 실제 loader·glibc/libstdc++ version, POSIX signal/별도 stack 전환,
ViPer fork/IPC, SocketCAN/vCAN와 권한을 선택한 보드에서 검사해야 한다. CAN transceiver/driver와 물리 CAN FD
시험은 별도다. QEMU 실행도 실제 보드의 지연 근거로 사용하지 않는다.

파일럿의 10 ms relative timer, 49152-byte task/32768-byte ISR stack, hosted C의 fortify 예외는 유지한다.
교차 컴파일은 stack 여유·실시간성·AUTOSAR 적합성을 검증하지 않는다. 새 보드에서 fortified longjmp 및 stack/ABI
호환성을 다시 확인한다. RTE/BSW와 session coordinator도 후속이다.

<a id="adr-0041-rt-사전-점검"></a>

### RT 사전 점검

새 실행 파일 대신 기존 `tools/runtime_diagnostics.py`에 `--probe-only`를 추가한다.
M3 workload/vCAN/부하 worker 없이 kernel config, CPU mask, RT priority limit, RT throttling, trace/perf 접근 결과를 기록한다.
FIFO 요청은 별도 자식에서만 잠깐 적용하고 관측·복원한 뒤 종료한다. 부모의 scheduler는 유지한다.
기본 요청 priority는 1이다. `--fifo-priority`는 **권한 확인용**이며 runtime owner별 priority 설정이 아니다.
Probe timeout은 3초이며 syscall errno와 원래 오류를 보존한다. 시스템 설정/권한을 자동 변경하지 않는다.

`PREEMPT_DYNAMIC`과 `PREEMPT_RT`, FIFO 적용 가능 여부, trace 접근 가능 여부를 별도 항목으로 기록한다.
Config를 못 읽으면 RT 여부는 unknown이다. FIFO가 AVAILABLE이어도 M3 workload를 RT로 실행한 결과나 deadline
충족을 뜻하지 않는다. 권한 거부는 BLOCKED로 기록하고 SCHED_OTHER 표본을 RT 결과로 대체하지 않는다.
사전 점검 명령의 exit 0은 **보고서 수집 성공**이며 RT 사용 가능 판정이 아니다.

<a id="adr-0041-다음-수용-조건"></a>

### 다음 수용 조건

1. 선택한 ARM64 보드의 OS/BSP·compiler/sysroot를 고정하고 동일한 기능 4조건과 IPC 정리를 재현한다.
2. RT 시험이 가능한 환경에서 native M3 owner별 policy/priority를 명시하고 실제 적용값을 검사하는 실행 경로를 구현한다.
3. 같은 workload·CPU map·부하·원래 시한으로 일반/RT 조건을 비교한다. Timer→wakeup→switch는 커널 trace로 별도 관측한다.
4. 위 결과와 stack·driver 경계를 검토한 뒤 다른 Leaf 확대 및 M3 수용을 진행한다.

실행 방법은 [학습 안내](../learning/runtime-timing-guide.md), 결과는 [품질 기록](../development-guide.md)에 둔다.
공식 근거: [Trampoline POSIX platform](https://github.com/TrampolineRTOS/trampoline),
[Linux scheduling 권한과 정책](https://man7.org/linux/man-pages/man7/sched.7.html),
[PREEMPT_RT](https://www.kernel.org/doc/html/latest/core-api/real-time/index.html).

후속 [ADR-0042](#adr-0042)로 native owner별 FIFO 적용과 Host 비교를 진행했다.
실제 ARM64 실행·kernel trace와 Target 수용 조건은 유지한다.

<a id="adr-0042"></a>

## ADR-0042: Native M3 owner별 FIFO 설정과 비교

Date: 2026-10-18. Status: **옵션 실행 경로 구현·Host 통합 기준 선택 / 전체 M3 수용 PENDING**. 결과 갱신: 2026-10-19.
[ADR-0041](#adr-0041)의 새 PAM 세션에서 개발 계정의 rtprio 20을 확인했다.
기존 native M3 workload에 Linux FIFO를 적용한다. Trampoline 내부 Task나 그 POSIX tick을 변경하는 작업과 구분한다.

<a id="adr-0042-실행-계약"></a>

### 실행 계약

`actuator_demo multirate-runtime`의 선택 옵션 `owner-fifo=`에 일곱 owner의 priority를 명시한다.
기본 실행은 기존 상속 정책이다. 비교 실행기는 일반 조건이 실제 SCHED_OTHER/0인지도 검사한다.
FIFO는 SCHED_OTHER/0 launcher에서 시작하고 startup 시 `pthread_setschedparam` 뒤 실제 policy/priority를 읽어 확인한다.
요청 범위는 Linux API의 1..99이며 계정의 실제 허용 상한은 별도다. 현재 Host 계정은 20이다.

| Owner | 비교용 FIFO priority | 이유 |
| --- | --- | --- |
| Monitor | 20 | 완료 시한·수신 감시 |
| Plant/fixture | 19 | 교차 감시와 실제 보호 적용·물리/센서 진행 |
| RX | 18 | 2 ms 주기와 3 ms 완료 budget |
| Brake/Drive/Power | 10 | 10 ms 주기의 ECU 판단 |
| BMS | 9 | 20 ms 주기의 ECU 판단 |

이 map은 첫 Host 비교 fixture다. Criticality·WCET에 근거한 양산 우선순위 결정이나 최적값을 주장하지 않는다.
IO owner는 CPU A, ECU 네 owner는 CPU B에 두며 조건 사이에 동일한 map을 유지한다.

일곱 owner 모두 affinity·scheduler 설정과 실제값 취득을 마친 뒤에만 startup gate를 연다.
기존 enable lead 100 ms와 release/시한을 유지하고, coordinator의 준비 대기는 최대 50 ms다.
준비 실패 또는 enable 이후에는 workload를 시작하지 않는다. 시작 gate의 mutex/CV는 측정 window 밖에서만 사용한다.
본문의 기존 bounded RX·latest snapshot·완료 guard와 original source 규칙을 유지한다.

설정 실패는 모든 대기를 깨우고 abort한다. 일반 policy로 fallback하지 않는다. 부분 적용 실패에서도 application body,
plant 진행·CAN 송신은 시작하지 않는다. 실제 관측 policy·priority, owner별 ready/error, startup release와 aborted를 기록하고
nonzero로 종료한다. Coordinator/plant가 공유하는 호출 thread의 원래 policy·priority·affinity는 join/CSV 출력 전에 복원한다.
`run.json` schema 5의 추가 필드 `runtime_scheduling`으로 기록한다. 이전 schema의 분석은 유지한다.

<a id="adr-0042-비교와-증거"></a>

### 비교와 증거

기존 `check_timing.py --experiment scheduler`가 SCHED_OTHER/FIFO × quiet/loaded × full/minimal ×3회를 실행한다.
조건 순서를 repetition마다 회전하고 trace 순서를 번갈아 둔다. CPU B의 부하는 기존 SCHED_OTHER 7/10 ms wall busy window다.
실제 부하 CPU 소비와 생존, 배치·policy control을 별도로 검사한다. 설정/부하 control이 실패한 run도 FAIL로 보존하되
비교 통계에서는 제외한다. 유효한 관측을 가진 timing FAIL은 포함한다. 두 방식 모두 동일한 binary/workload/시한을 쓴다.
Sanitizer는 별도 기능 회귀 build이며 성능 비교 숫자에 합치지 않는다.

원래 [ADR-0039](#adr-0039)의 owner 2 ms/4 ms·1211 slots, RX 2 ms/3 ms·1210 jobs와
ECU 5/8 ms 시한을 완화하지 않는다. Job/owner의 skip·miss·wake/body/CPU·유효 수신·보호 적용을 함께 본다.
RT 권한 거부와 partial setup을 별도 CLI 시험하고 기존 fault 17조건도 일반/FIFO로 검사한다.

FIFO는 Linux scheduling policy다. PREEMPT_RT kernel 적용, memory locking·page-fault 제한, kernel trace,
실제 Jetson/MCU 정시성이나 full AUTOSAR stack을 의미하지 않는다. 기존 RT throttling과 시스템 설정을 유지한다.
현재 실행 환경의 결과로 WCET나 hard real-time을 보장하지 않는다. 전체 32개 requirement/29개 TC는 NOT RUN이다.

공식 API 근거: [pthread_setschedparam](https://man7.org/linux/man-pages/man3/pthread_setschedparam.3.html),
[Linux scheduling](https://man7.org/linux/man-pages/man7/sched.7.html).
실행·결과는 [학습 안내](../learning/runtime-timing-guide.md), [품질 기록](../development-guide.md)에 둔다.

2026-10-19 [수용 검토](milestone-reviews.md#m3)에서 이 IO 배치/FIFO map을 다음 Host 통합 기준으로 선택했다.
기존 상속 기본값을 바꾸지 않고 CLI로 명시한다. 일반 sanitizer의 두 타이밍 실패와 학습자 수용은 OPEN이며,
새 Central/Zone workload의 budget·정상/정지/rejoin은 다시 검증한다.

<a id="adr-0043"></a>

## ADR-0043: Hosted RTOS의 절대 주기 타이머와 명시적 Host 배치

Date: 2026-10-19. Status: **Host 구현·비교 검증 완료 / 원래 native 커널 원인·Target 후속**.
[M3 수용 검토](milestone-reviews.md#m3)의 OPEN-M3-01/02와
[RTOS 파일럿](#adr-0040)의 tick drift를 후속 검토한다.

<a id="adr-0043-확인한-문제와-변경-경계"></a>

### 확인한 문제와 변경 경계

Native multirate는 이미 CLOCK_MONOTONIC/TIMER_ABSTIME을 사용한다.
일반 sanitizer의 두 실패에서 요청 wake 뒤 지연과 네 slot 누락을 관측했지만 커널 원인은 미확정이다.
Native FIFO의 실제 배치·priority·startup 검사는 ADR-0042를 유지한다.

Pinned Trampoline의 ViPer AUTO timer는 relative usleep을 반복한다.
매번의 늦은 wake와 다음 sleep까지의 비용이 다음 예정 시각에 더해지는 구조다.
기존 측정의 약 24–30 ms / 1.6 s drift와 일치하는 누적 경로지만 모든 Host 지연의 원인이라는 뜻은 아니다.
RTOS OS API/Task/Alarm/Resource와 ECU 코드·CAN wire는 유지하고 Linux 가상 timer backend만 교체한다.

<a id="adr-0043-타이머와-관측-계약"></a>

### 타이머와 관측 계약

`vecu/platform/trampoline_posix/viper_timer.c`는 Linux timerfd의 CLOCK_MONOTONIC 절대 시작 시각과
10 ms periodic interval을 사용한다. Read가 여러 expirations를 반환하면 최신 기회에 signal 하나만 보내고
`expirations-1`을 누락으로 기록한다. 밀린 interrupt를 몰아서 보내거나 놓친 OS tick을 실행했다고 표시하지 않는다.
기존 POSIX signal의 비큐잉/coalescing 한계도 남으므로 실제 RTOS release를 distinct timer send와 대조한다.

Build helper의 `--timer-mode`는 `absolute`(새 기본), `relative`(동일 계측의 상대 sleep 대조군),
`upstream`(고정 원본)이다. 원본 checkout은 수정하지 않고 ViPer link의 timer object만 명시적으로 교체한다.
원본 GPLv2 license와 lock은 유지하고 교체 source의 GPL-2.0-or-later 표기·hash·compiler 명령·선택 mode를 build manifest에 기록한다.

각 timer thread는 시작 전에 bounded mmap trace를 생성·prefault한다. Tick 본문에 파일 출력은 없다.
128-byte header/64-byte record, 512 records의 little-endian schema 1이다.
Origin·period·intended target/wake/send·expiration 누락·PID/TID·실제 policy/priority/CPU를 기록한다.
Count 공개는 lock-free다. Trace overflow/error/누락이나 source/build mismatch는 FAIL이며 없던 timer tick을 0 지연으로 보충하지 않는다.
이는 trace page만 준비한 것이며 전체 memory locking/page fault/WCET 보장을 뜻하지 않는다.

<a id="adr-0043-host-배치와-판정-기준"></a>

### Host 배치와 판정 기준

`check_rtos.py --rtos-cpu B --plant-cpu A --fifo`는 자식에서만 설정한다.
RTOS와 그 ViPer 자식/timer는 CPU B FIFO 10, 외부 물리 모델은 CPU A FIFO 19다.
비교 대조군도 같은 CPU map에서 SCHED_OTHER/0을 명시한다. RTOS 내부 Task priority와 Linux priority는 별개다.
권한/실제 설정 오류는 FAIL이고 fallback하지 않는다. Runner/사용자 shell의 policy·affinity는 변경하지 않는다.
이 첫 Host priority map은 최적화·양산 calibration 결과가 아니다.

원래 실제 ReleaseDispatch→Control 완료 5 ms·감시 margin 20 ms·유효 수신 상실 100 ms는 유지한다.
추가 Host 판정은 **원래 timer phase→ReleaseDispatch <=5 ms**, 정상에서는 **phase→Control 완료 <=5 ms**다.
기존 5 ms보다 기점을 앞당긴 추가 fixture 검사이며 차량/Target requirement revision은 아니다.
Relative 대조군도 최초 origin의 nominal phase로 평가해 움직이는 target이 drift를 숨기지 못하게 한다.
Measured window의 skipped expiration/coalesced signal은 0이어야 한다.
`--require-wall-timing`은 위 추가 계약을 실행 verdict에 적용한다. 미지정 시 timing FAIL도 독립 필드에 보존한다.
고장 주입의 늦은 Control 자체는 원래 oracle로 검사하고 정상 성능 표본과 합치지 않는다.

개발 시험에서 absolute tick의 12-tick ResumeAlarm이 suspend 위상 때문에 120 ms보다 짧아졌다.
최소 wall 정지 **120 ms** 검사를 유지하고 ResumeAlarm을 **13 ticks**로 바꾼다.
예상하지 않은 개발 실패는 보존하고 새 비교에 합치지 않는다. 원래 native 120 ms 주입은 변경하지 않는다.

<a id="adr-0043-비교-protocol과-남은-범위"></a>

### 비교 protocol과 남은 범위

계측 relative/absolute × OTHER/FIFO, 동일 CPU A=0/B=1·4 scenario·각 3회의 48 runs를 사전 계획하고 실행했다.
Repetition마다 네 profile 순서를 회전한다. 추가 부하 없음·warm-up 제외 0, 원래 1.6 s window/500 ms enable lead를 사용한다.
Normal phase 지연/nominal drift와 fault 반응을 따로 기록하며 모든 유효 실패를 보존한다.
Native normal/sanitizer FIFO fault 회귀와 같은 observer/CPU 조건의 OTHER/FIFO 대기 관측도 별도 수행한다.
진단 observer는 intrusive이며 정규 성능 비교와 섞지 않는다.

Timerfd의 누락 기록은 별도 owned ViPer 정지 주입으로 확인한다. 이를 정상 timing PASS로 처리하지 않는다.
원본 sanitizer 두 실패를 새 PASS로 교체하지 않는다. 추가 실행이 kernel 원인을 소급 확정하지 않는다.
Tracefs/perf 권한, PREEMPT_RT 비교·Target runtime·동시 process/OS 정지 중 독립 보호는 여전히 후속이다.

구현 commit은 `625b487`, 기능 PASS 뒤 추가 timing 실패가 전체 FAIL로 남도록 한 후속은 `554e91c`다.
후자의 clean source에서 기능 48/48 PASS, 추가 Host timing은 absolute 24/24 PASS·relative 0/24였다.
Native FIFO는 normal/sanitizer 각각 51/51 PASS다. 별도 부하 진단의 OTHER 3/3 FAIL과 FIFO 3/3 PASS도 보존했다.
설정 기록은 `m3_hosted_timer_fixture`에 사후 정리했다. YAML loader는 없으며 측정 당시 설정은 이 ADR와 source/CLI hash다.
재현·수치·제약은 [학습 안내](../learning/runtime-timing-guide.md),
실행 증거는 [품질 기록](../development-guide.md)에 둔다. 전체 M3 수용은 PENDING이다.

공식 근거: [clock_nanosleep과 absolute drift](https://man7.org/linux/man-pages/man2/clock_nanosleep.2.html),
[timerfd의 periodic expiration count](https://man7.org/linux/man-pages/man2/timerfd_create.2.html),
[timer slack과 RT policy](https://man7.org/linux/man-pages/man2/PR_SET_TIMERSLACK.2const.html).

<a id="adr-0044"></a>

## ADR-0044: Central 전원 요청·정상 허가 상태 owner

Date: 2026-10-19. Status: **Host component 구현·시험 / 전체 coordinator·Zone/DDS 통합 후속**.
[ADR-0021](#adr-0021)의 Central 단일
vehicle-management 책임과 [준비 판정](../learning/vehicle-lifecycle-guide.md)을 연결한다.
TBD-06/12/15의 전체 차량·분산 protocol 결정을 완료한 것은 아니다.

<a id="adr-0044-결정"></a>

### 결정

`central/vehicle_management/VehicleManagement`를 단일 owner·외부 clock 기반 runnable로 둔다.
상위 lifecycle 요청, trusted session, 두 Zone의 현재 입력을 받아 기존 BmsPowerRequest와
DrivePermission을 산출한다. Socket/plant/스케줄링/Epoch 발급은 이 library 밖의 책임이다.
Source/now는 첫 component에서 같은 monotonic clock domain이다.

| 상태 | 의미 / 출력 |
| --- | --- |
| INIT | 현재 session의 known input과 실제 OFF를 검사; KeepOff/Inhibit |
| OFF | main/precharge 실제 접점 open·낮은 bus 확인; 유효 Enable 요청을 기다림 |
| STARTING | Parent 안에서 Enable, 실제 precharge·요청 응답 대조; Inhibit |
| NORMAL | 전체 준비 조건 + live 원래 요청 + 확인된 Enable 응답; AllowNormal |
| STOPPING | Inhibit + Shutdown 요청; 실제 접점·잔류 bus와 Shutdown 응답 대기 |
| STOPPED | 종료 확인, KeepOff/Inhibit; 같은 session의 Enable 재개 금지 |
| FAIL_SAFE | 첫 고장 latch, Inhibit + local Shutdown 요청; 새 frame으로 해제 불가 |

STOPPED/FAIL_SAFE 이후에는 더 큰 Epoch의 explicit trusted INIT가 필요하다.
같은 Epoch, 과거 clock으로 reinit하지 않는다. Central INIT는 Leaf/receiver/물리 모델을 자동 reset하지 않는다.
상위 session owner가 필요한 각 participant를 재설정하고 물리 전원 상태는 계속 관측해야 한다.
INIT에서 닫힌 실제 접점은 startup energized fault다. 모든 접점이 open이면서 bus만 남으면
기존 로컬 방전 동작을 기다리고 실제 OFF를 확인한 뒤 Enable을 허용한다.

정상 준비와 별개로 **input health**를 검사한다. 알려진 INIT BMS 0 한계와 OFF/Checks/Precharge
등의 실제 lifecycle은 시작 중에 합법적이다. 이를 HV_READY/NORMAL로 바꾸지 않는다.
처음 필요한 입력이 모이기 전에는 bounded startup 대기, 한 번 모인 뒤에는 필수 입력 상실을 latch한다.
Local protection은 INIT 중에도 즉시 차단한다. 검증된 DEGRADED envelope는 후속이며 이번에는 허용하지 않는다.

<a id="adr-0044-identity만료응답"></a>

### Identity·만료·응답

Upstream `LifecycleRequest`는 trusted ingress가 제공한 Epoch/Sequence/Source/Expiry와 action이다.
최초 sequence 0..9, 이후 증가량 1..10과 증가하는 source를 요구한다. 같은 identity의 action·원천 시각·expiry
변경은 거부한다. 동일 요청의 재관측은 source/deadline을 갱신하지 않는다.
처음 source를 수신한 시각으로 바꾸거나 CAN frame에서 trusted parent를 자동 학습하지 않는다.

Active root/grant 만료와 owner gap을 **새 요청·피드백을 처리하기 전에** 검사한다.
이미 지난 유효 기간을 새 요청으로 숨겨 NORMAL을 유지하지 않는다.
PowerStatus의 CausalSequence와 AcceptedRequestSourceTime을 실제로 발행한 PowerRequest의
Sequence/Source에 함께 대조한다. 과거 root에 속한 응답도 그 root와 child가 아직 유효해야 하며
Enable 응답의 역행은 허용하지 않는다. 최근 발행 요청 16개를 보존한다(10 ms cadence에서 160 ms).
History hit만으로는 부족하며 parent/source age·child expiry를 추가 검사한다.

AllowNormal은 현재 원래 요청, 확인한 Enable child/원래 parent, 출력 lifetime 및 각각의 source/dependency
유효 기간을 모두 넘지 않는다. 경계 포함 age의 다음 1 ns를 exclusive expiry로 표현한다.
InputTime은 현재 요청·응답의 원래 parent와 모든 필수 입력 중 가장 오래된 원천 시각이다.
DrivePermission의 power identity는 관측한 실제 PowerStatus를 가리킨다. Inhibit는 제한 출력이므로
원래 Enable이 만료돼도 재발행할 수 있다. 주행 권한을 연장하는 것은 아니다.

Shutdown 요청의 parent가 만료되면 NormalPath authority를 연장하지 않는다. 로컬 제한 동작으로
LocalProtection Shutdown을 계속 요청한다. 종료 중 새 Enable로 취소하지 않는다.
Shutdown 요청은 접점 open 명령/안전 정지 성공이 아니다. 기존 BMS leaf가 전류 확인·접점 응답·방전을
진행하며 unknown current/용착이면 계속 blocked일 수 있다. Fault별 차량 감속/제동 배분과 최종
protection matrix는 후속이다. 이 Central 모듈이 local 보호를 대체하지 않는다.
유효한 실제 OFF와 고장 상태는 별개다. Shutdown/KeepOff 응답과 physical quality/age로 OFF를 확인할 수 있으면
다른 peer 상실이나 PowerStatus sender fault가 있어도 관측을 보존한다. 이 관측은 FAIL_SAFE latch를 해제하지 않는다.

<a id="adr-0044-첫-functional-sil-값과-검증-경계"></a>

### 첫 functional-SIL 값과 검증 경계

| 항목 | 값 |
| --- | --- |
| Runnable period / 최대 호출 gap | 10 ms / 30 ms |
| 최초 critical input 대기 / ACK 진행 대기 | 각각 80 ms |
| 원래 요청 source age / wire lifetime | 50 ms / 최대 80 ms |
| 출력 명목 lifetime | 60 ms, 모든 원래 권한·입력의 expiry로 추가 축소 |
| 전원 준비 / 종료 대기 | 3 s / 2 s |
| 실제 OFF bus 상한 | 30 V |

실차 calibration이나 wall-time 검출 결과가 아니다. 기존 readiness source/dependency budget은 유지한다.
학습·재현 방법과 component 시험 범위는 [상태 owner 안내](../learning/vehicle-lifecycle-guide.md)에 둔다.
In-process CAN codec/receiver와 실제 RC/접점 모델을 연결하며 Front/Rear health·비Power actual·BMS gate는
명시적 fixture다. 전체 allocation/Zone ingress/queue/DDS, 실제 vCAN·wall-time/Target·차량 TC는 후속이다.
M3 원래 타이밍 실패와 요구사항 32개/시스템 TC 29개 NOT RUN 상태는 바꾸지 않는다.

<a id="adr-0045"></a>

## ADR-0045: 첫 Central 배분과 회생·마찰 전환

Date: 2026-10-19. Status: **Host component 구현·시험 / 차량·Zone/runtime 통합 후속**.
[RG-01](../interfaces/regenerative-braking.md), [ADR-0021](#adr-0021),
[Central 허가 owner](#adr-0044)의 후속이다.
TBD-02/03/06의 첫 fixture 결정을 기록하며 최종 차량 calibration/보호 matrix를 확정하지 않는다.

<a id="adr-0045-입력권한과-책임"></a>

### 입력·권한과 책임

`central/control_allocation`은 단일 owner, 20 ms 외부 clock 기반 normal-path runnable이다.
VehicleRequest의 acceleration·curvature·normalized service braking·명시적 standstill hold와 원래 Epoch/Sequence/Source/Expiry를 받는다.
Target speed 추종/PID는 상위 Controller, local motor gate/압력 response monitor와 보호는 Leaf/Zone의 책임이다.
배분기는 plant·socket·clock issuance를 소유하지 않는다.

현재 trusted VehicleManagement가 NORMAL/allow 상태이고, 독립 BmsReceiver의 current AllowNormal과 별도 lifecycle
parent가 유효해야 한다. Vehicle request root와 permission lifecycle root는 다른 identity다.
필수 Zone/actuator/power/양방향 BMS feedback은 기존 정상 준비 조건으로 다시 검사한다.
Wheel speed는 별도 fresh 입력이며 Drive/Brake actual source skew는 최대 20 ms다.
Capability는 source 30 ms/input 70 ms로 검사하고 실제 torque validity와 구분한다.
Cached acquisition을 새로운 packet 시각으로 바꾸지 않는다.

상위 요청은 source age 30 ms·lifetime 최대 60 ms, 첫 sequence 0..9/후속 증가량 1..10이다.
같은 identity의 내용·source·expiry 변경은 거부한다. Active root와 이전 출력의 **필수** 지원 입력 만료를 새 입력보다 먼저 검사한다.
출력 3개는 allocator Sequence/Source와 vehicle-root CausalSequence를 갖는다. 원래 root, oldest used input과
모든 권한/source/dependency 중 가장 빠른 expiry는 **필수 scoped sideband**다. 기존 32-byte CAN payload에는
이 sideband가 없으므로 Zone admission에서 보존·검사하기 전에는 end-to-end parent expiry 검증으로 표시하지 않는다.

<a id="adr-0045-첫-배분-정책"></a>

### 첫 배분 정책

| 기능 | 정책 |
| --- | --- |
| 조향 | rear-axle curvature → `atan(wheelbase × curvature)`, angle 한계 적용 |
| 추진 | `mass × wheel radius × acceleration`; DC `Tω/η + kT² + reserve`와 motor mechanical power/torque로 제한 |
| 서비스 제동 중재 | 음수 acceleration의 제동 토크와 normalized braking 토크 중 큰 값; 더하지 않음. 양수 추진보다 우선 |
| 회생 | 새 제동 시작 시 valid capability·현재 BMS charge/motor power 한계 내 우선 배분 |
| 마찰 | 동일 wheel Nm 기준에서 배분한 회생 몫과 실제 남은 회생 중 큰 값을 빼고 Pa로 변환 |
| 저속 | 2 rad/s 진입·3 rad/s 이탈 hysteresis로 새 회생 억제 |
| Hold/출발 | 명시적 hold + 0.5 rad/s 이하에서 진입, 요청을 clear할 때까지 유지; 해제 후 actual pressure/negative torque가 release 허용 범위에 들기 전 양수 추진 억제 |

첫 제동 구간에서 회생 목표는 증가시키지 않는다. Capability/요구 감소나 저속 전환으로 줄인 회생을
같은 제동 구간에서 자동 복구하지 않는다. 실제 release를 관측하고 다음 제동이 시작돼야 다시 배분한다.
이는 지연이 다른 두 actuator 사이의 반복 handoff를 제한하는 보수적 첫 정책이며 OEM 최적 배분을 주장하지 않는다.
Capability가 unknown/stale이면 회생 목표 0과 마찰 경로를 사용하되 critical torque/Brake actual 상실은 FAIL_SAFE다.
Capability가 다음 nominal cycle까지 유효하지 않으면 미리 Expiring으로 분류해 회생 목표를 0으로 줄인다.
허용 owner gap 중 optional capability만 만료됐어도 새 frame으로 회생 목표를 복구하지 않고 마찰 경로를 사용한다.
Optional 만료 자체를 필수 Actual/허가 만료와 같은 FAIL_SAFE로 바꾸지 않는다.

초기 회생이 목표까지 올라가는 동안은 계획한 몫을 예약하고 실제 deficit를 기록한다. 회생이 줄어들 때는 아직 남은
실제 회생을 제외해 마찰을 명령한다. 실제 압력이 바로 따라온다고 가정하지 않는다.
Pressure/torque/angle은 wire step 안쪽으로 양자화한다. Command를 actual/회수 에너지로 사용하지 않는다.

<a id="adr-0045-응답보호-경계"></a>

### 응답·보호 경계

`Bactual = K × Pactual − Tdrive_actual`로 signed net braking을 관측한다. 양수 추진 잔여분도 포함하며
`max(0,Brequest−Bactual)`와 반대 방향 excess를 각각 기록한다.
원래 Drive/Brake acquisition 중 오래된 시각으로 50 Nm 초과 오차의 연속 dwell을 검사한다. Cached 읽기는 dwell을 진행시키지 않는다.
첫 dwell 700 ms는 M2 fixture의 전체 +300→−200 Nm 변화 500 ms + delay 50 ms와 관측/control 여유를 위한
**component 시험값**이다. 실제 차량 허용 오차/정지 시간이나 critical loss 100 ms 상한을 바꾸는 값이 아니다.
기존 Leaf의 더 빠른 local response monitor도 변경하지 않는다.

압력 포화로 배분 가능한 제동 토크가 부족하면 부족분을 기록하고, 응답 budget 위반/권한·필수 입력 상실도 latch한다.
이때 새 normal command는 없고 `protection_required`를 반환한다. 이를 Brake release/모든 actual 0/안전 정지 성공으로 해석하지 않는다.
별도 coordinator/Zone local protection 연결과 fault별 실제 반응은 후속이다. Recovery는 더 큰 Epoch의 trusted INIT다.

최종 geometry·타이어/도로·공기저항/경사·관성과 차량 feedback loop는 M6/M7에서 검증한다.
현재 VehicleManagement가 거부하는 BMS sender DEGRADED 정책은 이번에 완화하지 않는다. 첫 배분의 valid zero/limited
constraint 시험은 명시적 정상 sender fixture이며, 실제 BMS SOC/온도 derating과의 허가 envelope 검토는 통합 후속이다.
임의 보호 요구를 normal driving permission 없이 이 경로로 보내는 우회도 추가하지 않는다.

수치/재현/시험 범위는 [학습 안내](../learning/vehicle-lifecycle-guide.md), 보정 fixture는
[Reference YAML](../../profiles/reference.yaml)의 `m4_allocation_fixture`에 기록한다. YAML runtime loader는 없다.
전체 시스템 요구 32개/TC 29개 NOT RUN과 M3 기존 실패는 유지한다.

<a id="adr-0046"></a>

## ADR-0046: Front/Rear normal 명령의 독립 수용 경계

Date: 2026-10-19. Status: **Host component 구현·시험 / gateway·보호 출력·runtime 후속**.
[ADR-0045](#adr-0045)의 scoped sideband를
[ZON-01](#adr-0021)의 두 독립 수신 경계에 연결한다.
이번 결정은 TBD-15의 첫 in-process 의미 계약이며 DDS IDL/인증/clock sync 결정이 아니다.

<a id="adr-0046-책임과-계약"></a>

### 책임과 계약

`interfaces/central/allocated_commands.hpp`에 VehicleRequest·CommandContext·AllocatedCommands와
FrontCommands/RearCommands를 둔다. 기존 Central namespace/API 의미는 유지한다.
Front는 Steering/Brake의 같은 Epoch·Sequence·Source·CausalSequence·mode/origin 묶음,
Rear는 Drive command다. Scope helper는 복사만 하며 원래 root·oldest dependency·expiry를 바꾸지 않는다.
Rear의 power 요청/permission/BMS constraint와 초기 non-driving 경로는 별도 lifecycle 통합 후속이다.

`zone/command_validation/CommandAdmission`은 Zone마다 별도 single owner다.
배분기를 include/link하지 않고 공통 interface와 CAN domain 정의만 사용한다.
명령 수용이 BMS permission/로컬 actuator availability 판정이나 물리 protection을 대신하지 않는다.

Trusted INIT로 Epoch와 공통 monotonic session-enable을 설정하면 Idle이다.
전원 precharge 중 정상 명령 상실로 실패하지 않도록 **trusted `arm(now)`를 별도로** 호출한다.
Packet은 arm/INIT를 수행하지 않는다. Arm은 현재 세션에서 한 번만 가능하고 이후 Waiting/Active다.
초기 정상 주행 시작 조건과 실제 coordinator의 arm 호출은 다음 통합에서 검증한다.

원래 VehicleRequest는 **독립 trusted `authorize_request` callback**으로 승인한다.
명령에 붙은 parent를 복사해 이 callback을 호출하는 구현은 금지한다.
승인은 허용된 Central root handoff라는 caller 전제이며 transport/보안 구현은 아니다.
현재 승인 root 한 개만 유지하고, 새 root 이후 도착한 이전 root 명령은 거부한다.
이미 수용한 이전 명령은 자신의 원래 lease까지만 유효하며 새 root만으로 갱신되지 않는다.
Root 승인과 scoped command의 sequence cursor는 독립이다.

<a id="adr-0046-첫-수용-규칙"></a>

### 첫 수용 규칙

| 검사 | 규칙 |
| --- | --- |
| Scope·kind | Front는 atomic Steering/Brake Command, Rear는 Drive Command. Actual/auxiliary 혼입 거부 |
| Normal mode | NormalPath + Normal만 허용. INIT/DEGRADED/LocalProtection은 이 경로로 우회하지 않음 |
| Root identity | 승인 root와 Epoch/Sequence/Source/Expiry/모든 요구 내용 일치, command CausalSequence 일치 |
| Progress | 최초 sequence 0..9, 후속 증가량 1..10·source 증가; wrap 없음. 동일 identity의 내용·시각·expiry 변경 거부 |
| Range | 첫 SIL envelope: angle ±0.3 rad, pressure 0..1.5 MPa, torque −200..300 Nm. Unknown·NaN/Inf·다음 wire step·wire 양자화 뒤 한계 초과 거부, clamp 없음 |
| Root 요구 | 첫 계약 acceleration −5..2 m/s², absolute curvature ≤1 /m, braking 0..1, 명시적 hold |
| Clock·age | 동일 monotonic domain, session 이전/미래 source 거부; command/root age ≤30 ms, oldest used dependency ≤70 ms |
| Lifetime | Root lifetime ≤60 ms. Output expiry는 root expiry, root/command source-age bound, oldest dependency bound 중 최소 이하 |
| Boundary | Age는 inclusive, Expiry는 exclusive. Age bound는 포화 덧셈 `source + age + 1 ns` 사용 |

Oldest used input은 root source 이하이며, command source는 root source 이상이어야 한다.
명령의 지원 입력별 더 짧은 expiry는 Central이 산출해 보존한다. 이 검증부가 계산 근거의 모든
BMS/actual 입력을 독립 재계산했다고 주장하지 않는다. Zone/Leaf의 로컬 gate는 후속 연결에서도 유지한다.
범위/시간 설정은 첫 fixture이며 실제 차량 calibration이나 cross-node clock 계약이 아니다.

<a id="adr-0046-만료연속성복구"></a>

### 만료·연속성·복구

이전 accepted expiry를 **새 root/packet 처리보다 먼저** 검사한다. Late fresh packet으로
지나간 권한 공백을 숨길 수 없다. Invalid packet/duplicate/root 승인/다른 Zone traffic은
last-valid command RX나 expiry를 갱신하지 않는다. Duplicate는 Unchanged다.
`current_command(now)`도 dispatch 시점에 재검사하며 진단 cache를 정상 출력으로 반환하지 않는다.

Arm 후 첫 valid command가 없으면 80 ms에 timeout latch한다.
Active 명령은 원래 composite expiry에서 latch하며, clock rollback/명시적 continuity loss도 latch한다.
최대 10 ms monitor + 10 ms dispatch/jitter 여유를 더한 초기 검출 budget은 100 ms다.
이는 논리 시간 계약이며 wall-time/독립 watchdog 성능 검증은 후속이다.

Latch 시 normal snapshot을 제공하지 않고 `protection_required`와 fault를 제공한다.
물리 Brake release/hold pressure/Drive zero 출력은 이 component가 생성하지 않는다.
실제 local safety handoff가 다음 단계다. Recovery는 더 큰 trusted Epoch·시간 비후퇴의 INIT,
새 승인 root와 명시적 arm/새 명령을 요구하며 물리 상태를 reset하지 않는다.
각 Zone의 객체 독립 시험은 전체 Central–Zone 재접속 protocol 수용을 의미하지 않는다.

**기존 32-byte CAN에는 원래 parent/expiry가 없다.** Gateway queue와 egress guard가
sideband를 보존·재검사하기 전에는 Leaf까지 expiry가 보장됐다고 표시하지 않는다.
DDS·SocketCAN·full runtime/system TC는 이번 범위 밖이다. 시험/재현은
[학습 안내](../learning/vehicle-lifecycle-guide.md)에 기록한다.

<a id="adr-0047"></a>

## ADR-0047: Zone CAN 전달 직전 검증과 독립 보호 handoff

Date: 2026-10-19. Status: **Host component·분리 vCAN 구현/시험 / 전체 coordinator/runtime 후속**.
[ADR-0046](#adr-0046)의 수용된 scoped command를
정상 CAN 전달과 별도 trusted local protection 경로에 연결한다.

<a id="adr-0047-gateway와-대기열"></a>

### Gateway와 대기열

Zone마다 `CommandGateway`와 전용 port/CAN interface를 둔다. 독립 single owner이며
실제 외부 ingress worker나 DDS thread/queue 배치는 이번에 추가하지 않는다.
Trusted INIT/arm/독립 root 승인·수용 정책은 유지한다. 포트의 동일 monotonic clock으로
호출마다 이전 accepted lease·현재 시각을 검사한다. 최초 감시는 기존 80 ms다.

새로 Accepted된 명령만 capacity 8 FIFO에 원래 CommandContext와 함께 저장한다.
Duplicate/invalid packet은 대기열에 넣지 않는다. Overflow는 backlog 폐기·latch·local protection이다.
Dispatch는 최대 8개를 검사하고 최신 수용 sequence보다 이전 항목을 건너뛴 뒤 최신 묶음 하나만 보낸다.
이미 최신 명령으로 연속성을 유지했다면 오래된 superseded 항목의 만료만으로 전체 fault를 만들지 않는다.
현재 accepted 명령 자체의 만료는 새 입력보다 먼저 latch하는 정책을 유지한다.

Gateway는 원래 actuator Epoch/Sequence/Source/CausalSequence·parent/oldest/expiry를 보존한다.
같은 명령을 100 Hz counter로 다시 만들어 보내지 않는다. 새 frame을 실제 생성할 때 stream별
P05 counter만 사용하며 trusted 새 INIT에서만 초기화한다.
정상 전달 순서는 Front Steering→Brake 두 frame, Rear Drive 한 frame이다.
**Atomic 수용은 두 CAN write의 atomic delivery를 의미하지 않는다.**
양쪽 frame을 먼저 encode하고 각각의 송신 직전·직후에 lease/clock을 다시 검사한다.
첫 write 뒤 만료/실패하면 나머지 정상 전송을 중단하고 Front 전체 보호를 요청하며 partial 여부를 기록한다.
송신 실패 뒤 normal frame을 재시도하거나 시각을 갱신하지 않는다.

<a id="adr-0047-socketcan-경계와-보장-범위"></a>

### SocketCAN 경계와 보장 범위

`socketcan::ZoneGatewayPort`는 기존 domain codec/ABI adapter와 전용 nonblocking Endpoint를 사용한다.
`Endpoint::send_before`는 ABI 직렬화 후 `write` 직전에 exclusive expiry를 검사한다.
만료는 write 없이 false, EAGAIN/I/O 오류는 port에서 실패로 변환해 gateway latch에 연결한다.
기존 `send`의 wire/직렬화 계약은 유지한다.

이는 **최종 userspace enqueue guard**다. Check와 syscall 사이 scheduling, kernel TX queue,
실제 bus delivery나 remote Leaf 수신 시점까지 원래 composite expiry가 보장된다는 뜻은 아니다.
기존 32-byte CAN command에는 parent/expiry가 없다. Remote Leaf lease 표현/검사 또는 별도
trusted deadline 전달 경로, kernel backlog/rejoin 처리는 다음 계약 결정에 남긴다.
실제 버스의 두 frame partial delivery를 rollback했다고 표시하지 않는다.

<a id="adr-0047-local-safety와-leaf-선택"></a>

### Local safety와 Leaf 선택

`LocalSafety`는 첫 protection cause를 latch하고 정상 ingress/dispatch와 독립적으로
ProtectionPort를 호출한다. 수신자 불가/거부이면 Pending이며 poll당 한 번 재시도한다.
Handoff가 수용되면 재요청을 멈추지만 정상 주행 latch는 유지한다.
Trusted coordinator의 `request_protection`도 정상 payload/mode를 우회하지 않는 별도 입력이다.
Gateway와 local monitor의 <=10 ms 실행은 caller 책임이며 이번 wall-time workload 측정 대상은 아니다.

`simulation/runtime/ZoneLeafProtection`은 **명시적 same-host SIL 연결**이다.
Front는 Steering/Brake 둘 다, Rear는 mandatory EV DriveController의 trusted local port를 호출한다.
Leaf는 `request_local_protection`에서 기존 정책을 선택하고 UpstreamProtection을 latch한다.

| 담당 Leaf | 선택하는 기존 출력 | 실제 성공 판정 |
| --- | --- | --- |
| Steering | Hold, 지연된 정상 motion 취소 | 별도 angle sensor/plant |
| Brake | Protect, `max(실제 압력, 설정 floor)`의 SIL primitive; 높은 압력 해제 금지 | 별도 pressure acquisition·floor observed; 요청 자체로 도달 선언 금지 |
| Drive | Zero target/zero envelope, 양수 추진·음수 회생 목표 폐기 | 실제 torque의 zero ramp·관측 residual, 즉시 실제 0 선언 금지 |

Adapter는 plant를 진행하거나 actual을 생성하지 않는다. Initialized Leaf가 해당 보호 출력을
선택했을 때만 handoff를 수용한다. 이 ACK는 물리 도달/차량 정지 ACK가 아니다.
Drive는 이미 clock fault/stopped여도 이 trusted port에서 Zero를 선택하며 기존 fault를 유지한다.
Remote CAN protection signaling이나 AUTOSAR RTE/BSW/OS transport를 구현한 것은 아니다.
그 경로가 끊기면 기존 Leaf 자체 source-age/timeout 보호가 남는다.

Recovery는 더 큰 trusted Epoch/비후퇴 시각 INIT다. Gateway INIT는 Leaf를 reset하지 않는다.
각 Leaf INIT와 계속되는 physical model mapping·전원/health 확인은 coordinator가 별도로 수행해야 한다.
Rear power/permission/BMS constraint 전달·non-driving startup·피드백 감시와 full runtime은 후속이다.
재현/시험 범위는 [학습 안내](../learning/vehicle-lifecycle-guide.md)에 기록한다.

<a id="adr-0048"></a>

## ADR-0048: Rear 전원 전달과 명시적 non-driving startup

Date: 2026-10-19. Status: **Host component·분리 vCAN 구현/시험 / 전체 runtime 후속**.
[ADR-0047](#adr-0047)의 정상 명령 gateway와 별도로
Rear의 PowerRequest·DrivePermission·BMS limits/status를 연결한다. 기존 CAN layout·시한은 유지한다.

<a id="adr-0048-문제와-결정"></a>

### 문제와 결정

프리차지는 실제 bus 전압과 접점으로 완료를 확인하므로 정상 torque command timeout인 80 ms보다
길 수 있다. INIT부터 torque stream을 요구하면 시동 중 fault가 나고, 가짜 zero torque를 보내면
정상 배분 sequence와 source/권한 의미가 섞인다. DriveController에 명시적 `NonDriving` 시작을 추가한다.
기존 caller의 기본값 `Immediate`와 이전 수신/보호 동작은 유지한다.

NonDriving은 normal torque receiver만 아직 시작하지 않는다. Limits·Inhibit permission·local HV/speed는
계속 감시한다. 필수 입력 최초 대기 80 ms, 이후 각 source/dependency/expiry 상실 latch를 유지한다.
미리 도착한 torque packet은 receiver를 arm하거나 sequence를 소비하지 않는다. AllowNormal이 먼저
도착하면 CommandsNotArmed로 latch한다. 실제 HV/inverter 준비와 fresh Inhibit 상태에서 trusted
coordinator가 `arm_normal_commands`를 호출해야 정상 command 대기를 시작한다. 같은 Epoch에서
첫 normal sequence는 0이며 physics·feedback·BMS 수신 상태는 reset하지 않는다.

<a id="adr-0048-rearpowergateway-계약"></a>

### RearPowerGateway 계약

`interfaces/central/power_commands.hpp`에 lifecycle root와 VehicleManagement output 타입을 둔다.
`RearPowerGateway`는 trusted `authorize_request`로 별도 공급받은 lifecycle identity/action과
Central 자식 요청을 대조한다. 수신 CAN에서 parent를 추론하거나 vehicle demand root로 대체하지 않는다.

PowerRequest·DrivePermission·PowerLimits·PowerStatus는 독립 receiver와 마지막 accepted expiry를 가진다.
Source age 50 ms, 해당 dependency age 70 ms, 최초 누락 80 ms를 유지한다. Age는 inclusive,
expiry는 exclusive다. 이전 accepted deadline 상실을 새 입력 수용 전에 검사한다.
유효 0과 unknown, packet Accepted와 항목별 Usable을 구분한다.

| 자원/처리 | 결정 |
| --- | --- |
| 새 accepted 입력 FIFO | 8; overflow는 backlog 폐기·latch·Rear 보호 |
| Dispatch | 최대 8개 검사, stream별 최신 값; Inhibit 우선, limits→PowerRequest→AllowNormal |
| 송신 | 한 dispatch 최대 3 frame, 원래 metadata/expiry 보존; stream별 downstream P05만 별도 진행 |
| Actual status / 실제 송신 power history | 각각 8 / 16개, 원래 identity와 expiry로 검증 |
| 각 write | 전후 source/expiry/clock 확인; 실패·만료 뒤 normal 재전송 없음 |
| 보호 | Drive Zero 선택 + Power local fault/inhibit; Pending은 poll당 한 번 재요청 |

AllowNormal은 별도 arm과 실제 송신된 Enable의 ACK를 모두 요구한다. 참조 PowerStatus의 정확한
sequence/source, HV_READY·actual 접점·condition/voltage, 정상 sender mode를 확인한다.
ACK의 causal sequence와 accepted request source는 실제 전달한 Enable child와 일치해야 한다.
Grant는 status·ACK parent·현재 root의 남은 lifetime을 넘지 않는다. Enable 요청 자체는 HV 준비 증거가 아니다.
Arm 뒤 actual Ready나 정상 PowerStatus mode 상실도 보호에 연결한다.

<a id="adr-0048-검토한-degraded-envelope"></a>

### 검토한 DEGRADED envelope

기존 blanket rejection은 정차 중 실제 Drive의 `Disabled` regen capability와 정상 BMS derating까지
차단했다. 다음 두 경우만 Central input health/normal readiness에서 허용한다.

| Sender | NormalPath + DEGRADED의 추가 필수 조건 |
| --- | --- |
| Drive Actual | known torque −200…300 Nm, speed 0…100 rad/s, capability 0…200 Nm; torque/speed/cap source ≤30 ms, cap input ≤70 ms이며 source 이하; 알려진 Nominal/MotorOrSpeedLimited/ChargeAcceptanceLimited/Disabled reason, Disabled면 cap=0 |
| BMS PowerLimits | charge/discharge 모두 Usable·known·finite 0…100000 W, source ≤50 ms/input ≤70 ms; Nominal/SocLimited/TemperatureLimited/ElectricalLimited/Disabled 중 알려진 reason, Disabled면 해당 값=0, 최소 한 방향은 non-Nominal |

Epoch/session/원래 dependency·quality 검사는 그대로 적용한다. Steering·Brake·Zone health·PowerStatus의
DEGRADED는 여전히 미검토로 차단한다. FAIL_SAFE/LocalProtection·unknown·stale을 허용하지 않는다.
유효 제한 0이 주행 동력을 보장하는 것은 아니며 allocator와 Drive가 실제 power/torque gate를 계속 적용한다.
새 실차 calibration 또는 timing budget 확정이 아니라 현재 Host fixture의 제한된 허가 정책이다.

<a id="adr-0048-신뢰-경계와-남은-작업"></a>

### 신뢰 경계와 남은 작업

`simulation::RearPowerControl`은 trusted gateway TX에서 발급한 exact frame/context를 16개 보관한다.
실제 CAN RX는 일치하는 미만료 발급 기록으로만 별도 parent를 회수한다. Payload/ID/length/BRS/ESI를
대조하며 Linux TX/RX 표시가 다른 optional FDF bit 0x04만 비교에서 제외한다. INIT은 기록을 비우며
gateway/control INIT만으로 Leaf를 reset하지 않는다. Arm/staging은 두 Leaf의 application Epoch도 확인한다.
이는 same-host SIL sideband이며 DDS 인증이나 원격 Leaf 신뢰 프로토콜이 아니다.

Power 보호 ACK는 local fault/inhibit 선택이다. 실제 current dwell·접점 open·bus discharge는 기존
PowerController/물리 모델이 수행하며 즉시 contactor open 또는 실제 torque 0으로 표시하지 않는다.
기존 active Drive의 Inhibit 후 fail-safe/새 INIT 정책은 유지한다. 전 차량 graceful shutdown으로 확대하지 않는다.

Front non-driving startup·전체 coordinator의 독립 ingress/status/rejoin·coordinated stop, 기존 32-byte
normal CAN의 remote Leaf composite lease/보호 전달, DDS·전체 workload timing·Target은 후속이다.
시험·개발 실패와 정확한 fixture 경계는 [학습 기록](../learning/vehicle-lifecycle-guide.md)에 둔다.

<a id="adr-0049"></a>

## ADR-0049: Front non-driving 시작과 두 Leaf/gateway의 arm

Date: 2026-10-19. Status: **Host component·분리 vCAN 구현/시험 / 전체 coordinator 후속**.
[ADR-0048](#adr-0048)의 Rear 초기 구동에 이어
Front도 정상 command 없이 센서 Actual을 제공하며 준비를 기다릴 수 있게 한다.

<a id="adr-0049-leaf-시작과-감시"></a>

### Leaf 시작과 감시

`ActuatorCommandStartup::{Immediate,NonDriving}`을 shared session 계약에 둔다.
SteeringActuator/BrakeActuator와 기존 SIL wrapper의 기본값은 Immediate다.
기존 DriveCommandStartup 이름은 shared enum의 alias로 유지하며 Drive의 동작은 바꾸지 않는다.

NonDriving은 normal command receiver를 아직 시작하지 않는다. Steering/Brake는 Hold를 선택하고
외부 physical model·독립 local sensor로부터 INIT/NoAcceptedInput Actual을 계속 보고한다.
Brake Hold는 압력을 0으로 내리거나 보호 floor로 올리는 명령이 아니다. 주차 제동/차량 정지 보장도 아니다.
Gateway는 기존 Idle 상태에서 대기한다. 가짜 zero command/normal sequence/counter를 만들지 않는다.

센서 freshness/identity/range와 제어 주기·clock 감시는 계속한다. Current fixture의 sensor age20 ms·
sample/control gap30 ms와 주기10 ms는 유지한다. 명령이 없다는 이유로 이 검사를 유예하지 않는다.
각 Leaf는 command ingress·prepare/complete·arm·current sample 조회의 monotonic 시각을 함께 기록한다.
Trusted 새 INIT도 마지막 관측보다 과거로 돌아갈 수 없다.

`can_arm_normal_commands`는 clock 및 오래된 센서/실행 공백을 검사하며 fault를 latch할 수 있는
preflight다. Fault 없음, 미완료 job 없음, 최신 complete의 new valid acquisition과 미만료 source가
필요하다. 단순 cached publication만으로는 arm하지 않는다. `arm_normal_commands`는 trusted caller만
호출하며 같은 Epoch에서 receiver 감시를 시작한다. 최초 정상 명령 대기80 ms는 이때부터다.
Physics·sensor identity·Actual publication sequence는 reset하지 않는다.

Arm 전 CAN packet은 NotInitialized로 거부하고 receiver/P05/application sequence를 소비하지 않는다.
Arm 뒤에는 source가 arm 경계보다 이전인 packet도 기존 SourceBeforeSession으로 거부한다.
과거 session의 receiver diagnostic history는 NonDriving Actual의 causal/origin이나 current sample로 쓰지 않는다.

<a id="adr-0049-front-단위의-trusted-연결"></a>

### Front 단위의 trusted 연결

`simulation::FrontStartupControl`은 same-host single-owner binding이다. Central의 정상 준비/허가 결정은
caller 책임이다. CAN packet에서 준비를 학습하거나 arm callback을 호출하지 않는다.

1. Front scope와 gateway/Steering/Brake의 동일한 nonzero application Epoch를 확인한다.
2. Gateway Idle과 두 Leaf의 새 센서·fault/clock/period 조건을 모두 preflight한다.
3. Gateway와 두 Leaf를 arm한다. 도중 실패하면 gateway latch와 두 Leaf의 Hold/Protect를 선택한다.
4. 성공 뒤에도 원래 gateway의 독립 root·범위·metadata·expiry/각 write guard와 Leaf 감시는 계속한다.

Leaf preflight는 gateway poll 이전에 수행한다. Poll/arm이 더 나중 시각으로 이미 보호를 전달할 수
있으므로, 직접 보호에는 max(context time, gateway observed time)을 사용하고 그 뒤 gateway 보호를
요청한다. 같은 요청을 과거 시각으로 다시 전달해 원래 sensor fault를 ClockError로 덮지 않는다.

Preflight는 독립 객체 세 개의 transition을 atomic하게 만드는 기능이 아니다.
실패 시 normal path를 닫는 정책이며 실제 CAN 두 frame의 atomic delivery/rollback도 제공하지 않는다.
Wrong scope/Epoch·아직 첫 센서가 없는 준비 미완료는 arm 거부다. 감지된 fault/기존 gateway latch와
commit 실패는 Front 전체 보호다. 보호 ACK는 출력 선택이며 물리 압력 도달/차량 정지 ACK가 아니다.
복구는 각 객체의 명시적 새 INIT다. Gateway INIT 하나로 Leaf를 reset하지 않는다.

<a id="adr-0049-정상-종료-검토--후속-구현"></a>

### 정상 종료 검토 — 후속 구현

현재 VehicleManagement의 Stopping은 normal_allowed를 내리고 Inhibit/Shutdown을 산출한다.
Active Drive는 Inhibit를 fault로 latch하고 allocator는 normal output을 중단한다. 따라서 이를
전 차량의 정상 감속·정지·전원 종료가 완성된 흐름으로 표시하지 않는다. 이번 변경에서도 유지한다.

다음 구현에서는 단일 coordinator가 fresh stop root에 묶어 다음 책임을 순서대로 연결해야 한다.

- 정상 제어가 살아 있는 동안 양수 추진을 막고 제동/hold를 지시한다. Actual speed·torque·friction 응답으로 정지/유지 조건을 판정한다.
- 정상 receiver를 조용히 끄는 packet 대신 별도 trusted quiesce/handoff를 정의한다. 원래 Epoch/causal root·시각·deadline을 보존하고 센서·critical input 감시는 유지한다.
- 출력 선택 ACK와 실제 torque/current/접점·bus 상태를 구분해 Inhibit→Power 종료를 연결한다. 즉시 contactor open이나 pressure release를 가정하지 않는다.
- 각 단계 입력 상실·deadline 초과·부분 handoff는 기존 protection으로 보낸다. 고장 latch를 정상 종료 성공으로 바꾸거나 INIT로 지우지 않는다.

차량 정지 threshold/dwell·hold calibration과 stop phase budget은 TBD-02/03/06/12다.
현재 외부 speed0 fixture만으로 실제 감속 완료를 검증할 수 없다. 그 수치를 이번에 임의 확정하지 않는다.
실제 stop owner/Leaf handoff·전체 ingress/status/rejoin, remote normal32-byte CAN lease/보호와 DDS·
full workload timing·Target은 후속이다. 검증 범위는 [학습 기록](../learning/vehicle-lifecycle-guide.md)에 둔다.

<a id="adr-0050"></a>

## ADR-0050: 정상 정지·terminal handoff·HV 종료

Date: 2026-10-19. Status: **Host component 구현/시험 / 전체 분산 coordinator·차량 운동 후속**.
[ADR-0049](#adr-0049)의 정상 종료 검토를 구현한다.
기존 Shutdown→Inhibit는 active Drive의 고장 보호로 이어진다. 정상 종료는 그 전에 실제 정지 조건과
별도 trusted handoff를 요구하며, fault latch를 INIT으로 지워 성공으로 표시하지 않는다.

<a id="adr-0050-단일-stop-owner와-요청의-계보"></a>

### 단일 stop owner와 요청의 계보

`central::NormalStop`은 stop intent를 받아 다음 단계를 소유한다.

| 단계 | Lifecycle 출력 | Vehicle demand / 전환 조건 |
| --- | --- | --- |
| Waiting | 없음 | trusted begin·새 stop intent |
| Braking | Enable 유지 | 비양수 acceleration·명시적 hold·요청 curvature; 기존 allocator로 회생/마찰 배분 |
| HandoffPending | Enable 유지 | 새 actual 정지 조건의 dwell 완료, hold 명령 계속; 미만료 exact token의 trusted ACK 필요 |
| PowerDown | Shutdown | 새 정상 demand 없음; Leaf/gateway의 terminal lease 갱신과 센서 감시 계속 |
| Complete | Shutdown 의도 유지 | VM Stopped/OFF ACK + actual 접점 open·bus≤30 V + 정지 조건 계속 유효 |
| FailSafe | 정상 출력 없음·protection_required | 원래 고장 유지; caller가 독립 보호 경로에 연결 |

Stop intent는 별도 epoch/sequence/source/expiry와 curvature를 가진 trusted 입력이다.
Same identity mutation, sequence 역행/큰 jump, 원천 age50 ms·최대 lifetime80 ms 이탈은 거부한다.
이전 accepted intent가 만료된 뒤 새 intent를 받아 복구하지 않는다.
`StopIssuerSeed`는 기존 lifecycle/vehicle issuer의 다음 sequence를 trusted coordinator가 넘기는 계약이다.
이후 자식 root를 생성하며 각 plan에 원래 stop ancestor를 보존한다. CAN에서 seed/parent를 학습하지 않는다.
자식의 generation source는 현재 계산 시각이며 expiry는 원래 stop expiry/source-age bound를 넘지 않는다.
Allocator/VM/Zone는 계속 독립적으로 자식 root를 수용·대조하고 실제 입력에 따른 더 짧은 expiry를 적용한다.

VM의 Stopping/Stopped에서는 fresh **Shutdown만** 갱신할 수 있게 한다. 종료 phase budget은 재시작하지 않는다.
Enable/KeepOff 취소·자동 재출발은 기존 RestartRequired다. 만료된 stop root의 제한적 local Shutdown 동작도
유지한다. NormalStop/terminal lease가 만료되면 정상 종료 owner는 별도로 latch하므로 재인가의 근거가 되지 않는다.

<a id="adr-0050-첫-host-fixture의-정지-조건"></a>

### 첫 Host fixture의 정지 조건

| 값 | 결정 / 근거 |
| --- | --- |
| 제동 demand | 1 m/s² 감속 요청; 기존 1000 kg/0.3 m 배분 fixture에서 계산, 차량 제어 calibration 아님 |
| 정지 speed deadband | ≤0.01 rad/s; 현재 wheel-speed wire 한 step. 기존 hold 진입0.5 rad/s와 구분 |
| actual torque | 절댓값≤0.1 Nm; 기존 release tolerance/torque wire 한 step, local raw gate도 적용 |
| actual brake pressure | ≥100000 Pa; 기존 hold100 Nm / friction0.001 Nm/Pa |
| 확인 dwell | 60 ms; speed/torque/pressure의 가장 오래된 원래 취득 시각 진행으로 확인, cached read로 진행 금지 |
| Actual source / skew | 기존30 ms / 20 ms 유지; Front local sensor20 ms·Drive local30 ms도 유지 |
| Braking / PowerDown budget | 첫 fixture5 s / 기존 VM과 같은2 s; root 갱신으로 연장하지 않음 |

값들은 재현 가능한 SIL 설정이다. 실제 차량의 standstill/parking hold·노면/경사·센서 calibration,
제동 안전성 또는 정지 거리/FTTI를 확정하지 않는다. Speed script를 vehicle dynamics 검증으로 표시하지 않는다.

<a id="adr-0050-terminal-lease와-로컬-선택"></a>

### Terminal lease와 로컬 선택

`ActuatorStopLease`는 원래 stop epoch/sequence/source/expiry를 갖는 same-host trusted sideband다.
Source는 새 INIT 경계 이후·age≤50 ms, lifetime≤80 ms이며 expiry는 exclusive다.
Duplicate는 lease를 연장할 수 없고, 기존 lease 만료를 새 갱신 전에 검사한다. 최초 sequence는 독립
stop stream 중간일 수 있지만 이후 진행량1…10·strictly increasing source를 요구한다.
HandoffPending token의 deadline은 고정이며 관계없는 새 intent로 늘리지 않는다.

`simulation::NormalStopControl`은 두 Zone normal gateway·Rear power gateway·allocator·세 Leaf를 연결한다.
동일 epoch/scope와 plan을 확인하고 Leaf 선택부터 수행한다. 중간 실패/만료는 전부 보호하며 ACK하지 않는다.
보호 callback은 gateway가 이미 관측한 더 나중 시각을 보존한다. 이 선택은 atomic transaction이 아니다.

- Steering은 Hold로 지연된 motion을 폐기하고 local tracking을 계속한다.
- Brake는 Hold로 pending release를 폐기하고 압력을 보존한다. Response monitor의 지연 목표도 폐기하되 sensor identity/fault는 reset하지 않는다. Floor 상실은 로컬 fault다.
- Drive는 실제 local speed/torque를 다시 확인하고 Zero를 선택한다. Quiescent 상태에서 Inhibit/HV-off는 정상 과정이지만, limits/permission·HV/speed/torque 센서·고장 감시는 유지한다.
- Normal gateway는 backlog를 비우고 정상 ingress/dispatch를 닫는다. Allocator는 Quiesced로 normal output을 종료한다. 재출발은 새 trusted INIT가 필요하다.
- Rear power gateway도 기존 큐를 비우고 Enable/AllowNormal 재인가를 거부한다. Shutdown/limits/status와 기존 current→open→discharge 순서를 계속 전달한다.

Actual의 sensor 취득·publication sequence와 원래 command causal history는 계속된다. Normal command
receiver만 terminal handoff 뒤 중지하며, terminal lease 감시는 계속한다. 유효 0·unknown·FAIL_SAFE를 섞지 않는다.
ACK는 출력 선택이며 실제 torque0·압력 유지·접점 open 성공 ACK가 아니다. 후속 fresh actual로 계속 검증한다.
Complete 후에도 LV ECU/센서·lease가 살아 있는 fixture다. 이 단계는 ECU 전원 차단이나 parking brake 구현이 아니다.

<a id="adr-0050-검증과-남은-범위"></a>

### 검증과 남은 범위

기존 startup 시험을 유지하고 별도3.2 s 논리 시간 시험에서 VM/allocator·Front/Rear gateway·세 Leaf,
angle/pressure/torque plant·PowerController/RC/접점·독립 Actual receiver를 연결한다.
외부 speed20→0 script, Zone health·BMS limits/safety·pack400 V/load0 A는 명시적 fixture다.
단일 host binding/issuer handoff가 실제 DDS coordinator·원격 Leaf lease 구현을 대신하지 않는다.
Stop root·동작 판정/부분 handoff·local pressure/speed/lease 상실·제한적 Shutdown 갱신을 시험한다.
정적 분석·회귀·개발 실패 이력은 [학습 기록](../learning/vehicle-lifecycle-guide.md)과 [품질 기록](../development-guide.md)에 둔다.

전체 ingress/status/rejoin·remote32-byte CAN composite lease/stop 신호, DDS·전체 workload timing·Target,
실제 vehicle deceleration/hold·Battery energy/SOC를 포함한 정상 종료 loop는 후속이다. M4 전체 완료가 아니다.

<a id="adr-0051"></a>

## ADR-0051: 실제 Zone feedback health와 독립 status ingress

Date: 2026-10-19. Status: **Host component 구현·시험 / 분산 runtime·전체 rejoin 후속**.
[ADR-0050](#adr-0050)의 시동/정상 종료 연결에서
항상 정상으로 채웠던 Zone health fixture를 실제 gateway·독립 CAN receiver 상태로 교체한다.

<a id="adr-0051-책임과-상태"></a>

### 책임과 상태

`interfaces/zone`은 typed status/scope와 공통 Leaf feedback health 정책을 소유한다.
`zone/feedback/ZoneFeedbackMonitor`는 Zone별 단일 owner로 10 ms마다 자기 gateway와 담당 입력만 검사한다.
Front는 Steering/Brake Actual, Rear는 Drive Actual·BMS PowerStatus/PowerLimits다.
입력은 독립 receiver의 `current_sample(now)` 결과이며 원래 source/dependency/quality를 보존한다.
공통 정책을 Central도 사용하므로 INIT/검토한 DEGRADED/BMS quality·age 판정을 복제하지 않는다.

| Phase | 의미 | Normal 준비 | 시동·종료 input health |
| --- | --- | --- | --- |
| Waiting | 첫 필수 입력 대기 | false | false |
| Ready | 정상 입력과 Idle gateway, NonDriving에서 arm 가능성 판단 | true | true |
| Active | arm된 gateway의 정상 입력·감시 | true | true |
| Terminal | 실제 gateway가 normal-stop을 선택, 입력·lease 감시 계속 | false | true |
| FailSafe | 입력·gateway·clock/period 고장 latch | false | false |

Ready/Active는 차량 주행 허가가 아니다. Central은 실제 power READY·lifecycle/ACK·모든 원천을 별도로 확인한다.
Terminal은 정상 종료에 필요한 건강한 상태지만 Enable/AllowNormal/새 normal command의 근거가 될 수 없다.
Rear terminal은 normal gateway와 power gateway가 함께 선택해야 한다. 불일치는 보호한다.
Phase·ready flag·metadata 조합과 scope를 수신·Central 판정에서 대조한다.

<a id="adr-0051-상실과-복구"></a>

### 상실과 복구

- 각 입력의 첫 대기는 최대80 ms다. 하나라도 이미 유효했던 입력이 사라지면 첫 대기를 다시 주지 않는다.
- Actual source30 ms, BMS source50 ms/dependency70 ms, 기존 INIT/제한 DEGRADED 정책을 유지한다.
- Leaf의 명시적 FAIL_SAFE/LocalProtection는 첫 입력 대기 중에도 즉시 보호한다. 유효 물리값과 sender health는 별개다.
- 10 ms runnable의 gap>30 ms·clock 역행·gateway 보호·필수 입력 상실은 latch하고 별도 trusted port로 로컬 보호를 선택한다.
- Gateway callback 중 clock이 진행할 수 있으므로 status source와 입력 age는 실제 gateway 관찰 완료 시각으로 검사한다. Callback 뒤30 ms 초과도 deadline fault다.
- Status source는 관찰 cycle 시각이다. 자식 Actual/BMS 시각을 갱신하거나 status에 의해 오래된 원천을 fresh하게 만들지 않는다.

Central은 `ZoneStatusReceiver`를 Front/Rear에 각각 둔다. Source≤30 ms, 첫 수신 timeout80 ms,
Epoch·세션 경계·strictly increasing source·sequence 첫0…9/후속1…10을 검사한다. 중복·mutation·잘못된
scope/phase/metadata는 수용 시각을 갱신하지 않는다. 이전 source가30 ms를 초과하면 늦은 새 status를
검사하기 전에 continuity를 latch한다. 최초 timeout과 명시적 continuity/clock 고장도 자동 복구하지 않는다.
보고받은 FailSafe와 Terminal도 같은 Epoch에서 정상으로 되돌릴 수 없다.

복구는 trusted **더 큰 application Epoch와 비감소 시간의 INIT**만 가능하다. Monitor INIT 전에 담당 gateway도
같은 새 Epoch로 초기화해야 한다. Receiver와 monitor의 INIT는 Leaf/물리/다른 Zone/Central owner를 reset하지 않는다.
전체 coordinator가 각 참여자의 실제 재초기화·readiness·explicit arm을 완료하기 전에는 재주행을 허가하지 않는다.
자동 discovery/reconnect를 INIT 또는 fault clear로 간주하지 않는다.

<a id="adr-0051-검증과-남은-범위"></a>

### 검증과 남은 범위

[학습·검증 기록](../learning/vehicle-lifecycle-guide.md)의 component 시험에서 기존 시동과 정상 종료가 실제
Zone status를 사용한다. Front/Rear Actual 전송 누락·독립 status partition·continuity 상실을 주입하고
Central FAIL_SAFE/Inhibit와 양 Zone 보호 선택을 확인한다. 기존 허가/command expiry가 다음 Central 판단보다
먼저 로컬 보호를 선택할 수 있으므로 시험은 만료 경계에서 보호 관찰을 정상 CAN 재전송보다 먼저 수행한다.
이 논리 순서는 별도 thread 실행이나 worst-case 지연 보장이 아니다.

Same-host typed 전달이며 status wire encoding/CRC·DDS QoS/authentication·cross-node clock mapping은 미구현이다.
현재 monitor 자신이 멈춘 경우 Central의 독립 status source 감시가 폐쇄한다. 완전한 Zone 정지/분단에서
Leaf 쪽 보호를 보장할 remote composite lease/독립 watchdog과 전체 coordinator/runtime·재가입 transaction은 후속이다.
BMS limits/safety·pack/load·speed는 기존 fixture이며 차량 운동/정지 거리·Target timing 검증은 아니다.
Requirement32/system TC29와 M3 전체 수용 상태를 변경하지 않는다.

<a id="adr-0052"></a>

## ADR-0052: 제어 기능의 MBD 개발·검증 경로

후속 관계(2026-10-22): M6 범위 종료는 [검토표](milestone-reviews.md#m6), M8 동등성/자동 생성은 후속이다.

Date: 2026-10-19. Status: **개발 방향 채택 / M6 첫 Python MIL 검증 / M8 동등성·자동 생성 NOT RUN**.
2026-10-22 [ADR-0063](#adr-0063)으로 첫 Python 도구와
M6 plant/MIL을 구현·검증했다. 아래 원래 M6→M8 책임 분리는 유지한다.
사용자 요청으로 MBD(Model-Based Design)를 기존 M6–M8 개발 계획에 추가한다.
M4 Central/Zone 통합과 M3 타이밍 예외 해소를 계속 진행하며 milestone 번호와 Reference ODD는 유지한다.

<a id="adr-0052-결정과-첫-적용-대상"></a>

### 결정과 첫 적용 대상

제어 기능은 요구·interface → 실행 가능한 제어 모델 → MIL 검증 → C++ 구현 → 모델/코드 비교 →
차량 SIL 통합의 순서로 개발한다. 모델을 설계 기준으로 관리하고 parameter·시험·코드와 함께 변경한다.
첫 대상은 **Central 종방향 속도 제어기**다. 기존 [ICD](../interfaces/README.md)의
목표/실제 속도(m/s) → bounded longitudinal acceleration demand(m/s²) 경계를 따른다.
PID의 적분·미분 이산화, saturation·anti-windup·출력 변화율·허가 상실/재시작 상태를 명시한다.
선택한 PI/PID 구조와 각 항의 필요성은 모델 시험으로 설명하고 TBD-11에 기록한다.

출력은 기존 Central allocation을 거쳐 torque/pressure로 배분한다. 모델이 Leaf에 직접 CAN을 보내거나
Zone에 차량 speed controller를 추가하지 않는다. Curvature/조향 제어는 종방향 pilot 검토 뒤 M8에서 확장한다.
기존 BMS·전원 lifecycle·Zone 보호와 session/freshness 검사는 별도 owner의 책임을 유지한다.

<a id="adr-0052-단계와-산출물"></a>

### 단계와 산출물

| 단계 | 수행 범위 | 다음 단계에 필요한 근거 |
| --- | --- | --- |
| M4–M5 준비 | 제어 interface·단위·state/validity·원천 시각·출력 허용 조건과 model/code 실행 경계 정의 | 기존 ICD/owner와 일치하는 입출력 표, 도구 평가·재현 절차 |
| M6 초기 pilot | Simple Vehicle와 actuator 실제 응답을 반영한 종방향 plant·실행 가능한 이산 제어 모델 | 수식/가정·단위·초기 상태·sample time·solver/step·parameter revision |
| M6 MIL | 제어 모델 + plant로 reference 추종·제약·고장 입력을 구현 전 시험 | 고정 stimulus/seed·결과·판정 기준·실패 로그, 학습자의 제어식 설명 |
| M8 component | 검증한 모델과 같은 이산 의미의 C++ 제어기 구현, 공통 vector replay | tick별 출력/내부 상태·모드/유효성·거부 결정의 모델/코드 비교 |
| M8 차량 SIL | 실제 C++ 제어기를 Central→Zone→Leaf→actual→차량 feedback에 연결 | 기존 주행 scenario와 timing/fault 회귀, 모델 가정과 통합 결과의 차이 |
| 후속 선택 pilot | 한 제어 component의 자동 코드 생성과 동일 harness 비교 | 도구/license·생성 설정/버전·재생성·Host/Target 호환·코드 검사·비교 결과 |

M7 CARLA 연결은 기존 계획을 따른다. M6의 모델/가정을 CARLA mapping과 대조하고 M8에서 같은 제어기 계약으로 시험한다.
Model-based design 방법을 채택한 것이 모든 ECU/분산 통신을 모델 도구로 다시 만드는 결정은 아니다.

<a id="adr-0052-검증-계약"></a>

### 검증 계약

MIL은 모델 수준의 제어기/plant loop다. 현재 C++ 물리 모델/단위 시험의 PASS를 새 MIL 결과로 소급하지 않는다.
현재 repository의 Host SIL은 수작업 C++ ECU/물리 모델 시험을 포함한다. MBD pilot의 SIL/동등성 결과에는
어느 제어 모델과 어느 수작업/생성 코드 revision을 비교했는지 별도로 표시한다.

공통 open-loop stimulus를 모델과 코드에 각각 주고, tick별 acceleration output·적분 등 관련 내부 상태와
validity/mode/재시작 결정을 비교한다. Closed-loop 경로와 지표 비교도 수행하되 수치 차이의 원인 분석을 대신하지 않는다.
모델이 구현 함수를 호출해 자기 자신과 비교하는 시험은 독립 설계 기준의 검증으로 보지 않는다.

Sample time·실행 순서·hold/interpolation·초기 상태·parameter·numeric type·NaN 처리·saturation과
상태 reset 규칙을 고정한다. 동등성의 절대/상대 오차와 차량 추종 성능 기준은 별도로 **결과를 보기 전에** 정한다.
Floating-point 수치 비교가 필요할 수 있으며 항상 bitwise 동일성을 요구하지 않는다.
Mode/validity·허가 상실/거부 결정은 명시한 이산 계약대로 일치해야 한다.
기존 scenario·requirement threshold를 모델에 맞춰 조용히 완화하지 않는다.

첫 case는 속도 유지/증가/감소 reference·긴 saturation 뒤 회복·가감속/변화율 경계·정지 부근·
stale/invalid 속도·permission 상실·새 INIT의 controller state 초기화를 포함한다.
개별 fault의 출력 선택은 기존 safety/lifecycle 계약과 함께 검토한다. 이 pilot이 임의의 안전 정지 law를 정하지 않는다.
정확한 parameter/tolerance는 TBD-02/03/04/11/16에서 고정한 뒤 실행한다.

<a id="adr-0052-도구와-범위-관리"></a>

### 도구와 범위 관리

MBD 절차는 채택하지만 MATLAB/Simulink·자동 코드 생성 도구의 구매/설치·사용권 확보는 이번 결정에 포함하지 않는다.
Simulink와 도구 독립 실행 모델(Python 등)을 TBD-16에서 검토한다. License·Host/CI 재현성·model artifact diff·
numeric/solver 설정·기존 C++ harness 연동을 확인하고 M6 pilot 전에 선택한다.
자동 코드 생성은 선택한 제어 component에 한정한 후속 pilot이다. 지원이 없으면 수작업 C++와 모델 비교 경로를 유지한다.
도구 부재로 MBD 계획을 완료 처리하지 않는다. 선택 경로와 남은 항목을 ADR에 기록한다.

AUTOSAR RTE/BSW 생성은 이 제어 알고리즘의 코드 생성과 별도 활동이다. 생성 코드를 채택하면 원본 모델·
도구/설정·수정 금지 경계·재생성 명령·adapter·검증 증거를 관리한다. 현재 C++17/ARM64/RTOS 호환은 시험 전 가정하지 않는다.
PIL은 실제 processor 실행, HIL은 실시간 plant와 hardware 연결의 별도 검증으로 남긴다.
이번 계획이 Target/PIL/HIL이나 MBD tool qualification·안전 표준 준수의 검증 결과를 추가하지 않는다.

<a id="adr-0052-근거와-변경-영향"></a>

### 근거와 변경 영향

[MathWorks MBD 설명](https://www.mathworks.com/solutions/model-based-design.html)은 모델을 개발 과정의 기준으로
활용하고 작은 범위부터 단계적으로 도입하는 접근을 설명한다.
[공식 SIL 설명](https://www.mathworks.com/help/ecoder/software-in-the-loop-sil-simulation.html)은 Host에서 생성 코드를
실행하고 모델 결과와 수치 동등성을 비교하는 범위를 설명한다. 이 문서의 수작업 C++ 비교·단계 배치는 프로젝트 결정이다.
도구 문서를 참고한 사실은 특정 제품 채택이나 그 제품의 SIL을 실행했다는 증거가 아니다.

변경 대상은 [개발 계획](../development-guide.md), [로드맵](../roadmap.md),
[검증 계층](../test-plan/verification-strategy.md#mbd-model-and-code-verification)과 현재 진행 안내다.
기존 requirement32/system TC29·M3/M4 상태·C++/CAN/RTOS 실행 결과는 유지한다.
모델/코드/차량 결과는 revision·환경·입력·판정·실패를 기록한 뒤 해당 기존 TC의 부분 증거로 연결한다.

<a id="adr-0053"></a>

## ADR-0053: Central coordinator의 단일 실행 순서와 same-host binding

Date: 2026-10-19. Status: **Host component 구현·시험 / 독립 runtime·전체 INIT/rejoin 후속**.
[ADR-0051](#adr-0051)의 실제 Zone 상태 감시 뒤,
시험 코드가 직접 호출하던 전원·배분·정상 종료 owner를 하나의 Central API로 연결한다.
[MBD 계획](#adr-0052)은 M6–M8에 유지한다.

<a id="adr-0053-책임과-입력"></a>

### 책임과 입력

`central::VehicleCoordinator`는 VehicleManagement·ControlAllocation·NormalStop을 private member로 소유한다.
각 owner의 상태/검증 정책은 유지하고 coordinator가 호출 순서·부분 실패 보호를 관리한다.
Application Epoch 발급·물리 진행·remote reset·packet authentication은 소유하지 않는다.
기존 출력이나 측정을 재발행하며 source만 갱신하지 않는다.

| API | 입력 / 동작 |
| --- | --- |
| start_session | trusted Epoch/enable, 더 큰 Epoch·비감소 clock, adapter 참여자 preflight 뒤 Central owner 초기화 |
| receive_lifecycle | 별도 trusted lifecycle root를 VM에서 검사하고 Rear에 원래 identity/action 전달 |
| receive_vehicle | Normal/explicit arm 뒤 trusted vehicle root를 allocator에서 검사하고 Front/Rear에 같은 원래 root 전달 |
| receive_stop | 실제 Normal에서 stop intent를 검사하고 issuer의 다음 sequence를 내부에서 인계, 이후 정상 ingress 차단 |
| tick | 같은 cycle의 independent receiver current sample snapshot, 외부 monotonic 시각 |
| request_protection | 별도 trusted 보호 요청, 정상 CAN payload와 분리 |

미초기화·not-ready·잘못된 root·중복·mutation을 구분한다. 중복은 하위 authorize를 반복하거나 수용 시각을 갱신하지 않는다.
Root 수용 과정에서 기존 owner의 권한/지원 만료가 드러나면 coordinator 보호도 즉시 latch한다.
Active 상태에서 직접 Shutdown/KeepOff로 정상 종료를 우회할 수 없다. Stop intent 또는 독립 protection을 사용한다.

<a id="adr-0053-단일-cycle의-순서"></a>

### 단일 cycle의 순서

10 ms 외부 runnable, allocation20 ms를 유지한다. 첫 body 대기/실행 gap·callback 관찰 gap의 상한은30 ms다.
이는 기존 functional component의 gap 계약이며 M3의4 ms guard나 실제 OS 배치/전체 workload timing 검증을 대체하지 않는다.

1. Clock/session·adapter의 실제 gateway/Leaf 상태를 확인한다. 입력은 원천 시각/quality를 보존한다.
2. Stop 진행 중이면 NormalStop plan과 원래 stop authority 안의 lifecycle child를 수용·전달한다.
3. VehicleManagement가 actual OFF/READY·원래 ACK/요청·input health를 판정한다.
4. 최초 Normal 전환에서 Front pair와 Rear를 trusted arm한다. 부분 arm 실패는 모두 보호한다.
5. Rear gateway로 power request/DrivePermission을 전달한다. 실제 CAN·독립 Leaf 수신 경로를 유지한다.
6. Allocation 주기에 실제 permission receiver 결과와 별도 parent context를 조회하고 배분·Front pair/Rear 전송을 수행한다.
7. 정지 actual dwell 완료 후 allocator를 Quiesced로 선택하고 Leaf/Zone terminal handoff를 수행한다. 정확한 ACK 후에만 PowerDown이다.
8. 이후 tick의 Shutdown→actual OFF/접점 open/bus discharge·ACK 확인은 기존 owner가 계속 수행한다.

각 callback 후 monotonic 시각/실행 gap을 다시 확인하고, 각 gateway의 원래 source/expiry guard를 유지한다.
늦은 callback 뒤 다른 정상 단계로 진행하지 않는다. Owner가 early tick으로 출력하지 않으면 예전 출력을 재발행하지 않는다.
이때도 독립 allocation runnable을 감시하며, 마지막에 발급한 power output의 **변경 없는 parent context**만 보관한다.
배분 입력은 매번 실제 permission receiver에서 조회하므로 새 발급 grant로 수신 상실을 덮을 수 없다.

Stop intent 뒤 외부 lifecycle/vehicle root는 차단한다. NormalStop issuer seed는 마지막 수용한 root의 다음 sequence다.
같은 source instant에 새 정상 root와 stop이 들어오면 strictly-new source가 될 때까지 child 발급을 기다리고
새 propulsive normal output을 내지 않는다. 남은 기존 지원/권한이 그 대기를 견디지 못하면 보호하며 만료를 연장하지 않는다.

<a id="adr-0053-same-host-adapter와-실패"></a>

### Same-host adapter와 실패

`simulation::VehicleCoordinatorPort`는 실제 Front/Rear normal gateway·Rear power gateway,
Steering/Brake/Drive/Power controller·Central permission receiver와 clock을 연결한다. Plant를 소유하지 않는다.
Preflight는 scope/Epoch와 Idle/non-terminal gateway·비고장 Leaf·초기화된 permission ingress를 확인한다.
FrontStartupControl/Rear power arm과 NormalStopControl의 기존 trusted Leaf 선택을 재사용한다.
NormalStopControl은 coordinator가 allocator를 이미 quiesce한 경계와 기존 직접 allocator binding을 모두 지원한다.

Front 두 CAN write와 Rear write는 atomic transaction이 아니다. Partial Front면 그 cycle의 Rear batch를 보내지 않는다.
Root/arm/power/command/handoff callback 실패, owner protection, session/clock/gap 오류는 정상 흐름을 폐쇄하고
양 Zone Hold/Protect/Zero와 Power local shutdown 선택으로 연결한다. 정상 frame을 재시도하지 않는다.
보호 선택 ACK가 없으면 runnable당 최대1회 재시도한다. Invalid ingress flood는 이 retry 주기를 늘리지 않는다.
ACK는 출력 선택이며 물리 정지·압력 유지·접점 open 성공을 뜻하지 않는다.

동일 Epoch 재접속/INIT는 latch를 지우지 않는다. 더 큰 trusted INIT도 adapter 참여자 preflight 실패 시
Central의 기존 fault를 보존한다. 새 Epoch로 한 gateway만 바꾸는 것으로 Central을 재초기화할 수 없다.
다만 전체 독립 receiver/Zone/Leaf의 remote INIT transaction과 acknowledgement/timeout을 구현한 것은 아니다.
Caller가 각 receiver/monitor와 참여자를 준비하고 매 cycle 검증된 원천 snapshot을 전달해야 한다.

<a id="adr-0053-검증과-한계"></a>

### 검증과 한계

[학습 기록](../learning/vehicle-lifecycle-guide.md)의 단위20개와 실제 연결 추가5개를 포함해
normal·ASan/UBSan 각각 C++820개를 통과했다. 기존 양 Zone 시동/정상 종료·실제 health/Actual 상실 시험을
수동 Central 호출에서 coordinator로 전환했다. Partial arm·power/Front write·permission ingress 상실과
한 gateway만의 새 Epoch도 주입했다. NormalStop의 실제 Hold/Zero→HV OFF/ACK 완료·lease/센서 상실은 유지했다.

BMS limits/safety gate·pack/load·speed script는 fixture다. Current sample의 집계/Zone status 전달은 same-host이며
독립 Central/Zone thread/process·network partition·persistent session handshake·DDS/Host feedback bridge는 후속이다.
Remote32-byte composite lease/stop/protection, 전체 workload timing·Target/차량 운동 검증도 남아 있다.
M4 전체 완료나 M3 예외 해소·requirement32/system TC29 PASS로 확대하지 않는다.

<a id="adr-0054"></a>

## ADR-0054: trusted 세션 준비·INIT·실행 허용과 owner별 mailbox

Date: 2026-10-19. Status: **Host session component 구현·시험 / 정상 runtime 비동기화 후속**.
[ADR-0053](#adr-0053)의 Central 실행 owner에
명시적인 세션 제어 경계를 추가한다. Central–각 Zone의 병렬 연결과 담당 Leaf 구분을 유지한다.

**후속 구현:** 이 문서의 수치·직렬 fixture 설명은 해당 단계의 이력이다. 정상 owner 비동기 연결·실제 BMS/센서 경로·정상 종료/재가입은 [ADR-0055](#adr-0055)에서 진행했다. 현재 범위·최신 결과의 기준은 [project_status](../project-status.md)다.

<a id="adr-0054-결정과-소유권"></a>

### 결정과 소유권

Central의 `SessionCoordinator`는 영속 issuer에서 **이미 발급한** 더 큰 application Epoch만 받는다.
`EpochStore::issue()`의 lock/fsync는 trusted startup에서 실행하며 runnable·CAN 수신에서 호출하지 않는다.
실패·중단된 grant도 소모한다. Store 상실/손상은 자동 bootstrap/reset하지 않는다.
CAN frame·ACK만으로 새 Epoch나 INIT 권한을 얻을 수 없다.

세션 참여자는 Front Zone, Rear Zone, Steering, Brake, Drive, BMS, Power, Central ingress의8개 role이다.
Zone 역할은 gateway/monitor·own-context, Leaf 역할은 각 controller, ingress는 독립 Actual/permission/Zone status RX를 소유한다.
중앙 세션 owner는 callback/ACK로 상태를 확인하며, 원격 owner의 mutable 상태를 직접 초기화하지 않는다.
현재 실제 actor binding은 직렬 same-host 시험이며 wire topology나 remote INIT 구현을 뜻하지 않는다.

| 단계 | 동작 | 다음 단계 조건 |
| --- | --- | --- |
| Prepare | 정상 producer/ingress 폐쇄·기존 work flush, 독립 보호/물리 회복 계속 | 모든 role의 동일 proposal·fresh Prepared ACK |
| Initialize | 준비 완료 후 공통 future enable 지정, 각 owner가 자기 actor/RX INIT | 모든 role의 정확한 plan·Initialized ACK |
| Central commit | 실제 coordinator의 참여자 preflight 뒤 Central private owner INIT | callback 성공·원래 deadline 이내 |
| Release | 각 owner에 실행 가능 상태 전달 | 모든 Release ACK 뒤 **Central global run gate** 개방 |
| Abort | global gate 폐쇄·Central 보호·best-effort owner 보호 요청 | 더 큰 trusted Epoch의 새 Prepare로만 재시도 |

Local Ready는 global run 허가가 아니다. Runtime caller는 `SessionCentralLoop::run_enabled()`를
모든 정상 입력·정상 runnable 앞에서 검사해야 한다. Release가 일부만 도착해도 Central은 명령을 발급하지 않는다.
통신 복구·일반 packet·같은 Epoch INIT는 이 절차를 대신하지 않는다. Running에서 새 준비를 하려면 먼저 명시적으로 cancel한다.

<a id="adr-0054-시각과-실패-경계"></a>

### 시각과 실패 경계

현재 Host functional 값은 준비2 s, future INIT lead20 ms, enable 뒤 commit window 최대20 ms,
message age30 ms, 세션 owner 관찰 gap30 ms다. Commit deadline은 원래 Prepare deadline을 넘지 않는다.
각 callback 뒤 실제 clock을 재조회하고 exclusive deadline을 먼저 적용한다. Late ACK가 timeout을 이기지 못한다.
Near-uint64-limit 계산도 남은 budget 안에서 수행해 enable/deadline wrap을 차단한다.
이는 실차 calibration·FTTI나 기존 M3의4 ms 완료 guard 변경이 아니다.

ACK는 role·phase·epoch·requested/deadline/enable·source·성공 여부가 정확해야 한다.
중복 ACK/control은 변하지 않는 원래 ACK만 반환하며 시각·deadline을 갱신하지 않는다.
Mutation/wrong role·phase·plan·stale/future는 진행을 만들지 않는다. Negative ACK·clock/gap·timeout·부분 send/commit 실패는 latch한다.
부분 INIT의 rollback은 하지 않는다. 일부 actor가 새 Epoch에 들어가도 global gate는 닫히며 다음 시도에는 더 큰 Epoch가 필요하다.

Abort가 유실돼도 Prepared/Initialized owner는 원래 deadline으로 자체 보호한다.
보호/control-plane service는 run gate가 닫혔거나 세션 fault인 동안에도 호출한다.
Ready 뒤 정상 command/permission lease와 watchdog은 별도 정상 runtime 책임이며 세션 ACK로 갱신하지 않는다.

<a id="adr-0054-mailbox와-물리-reset-조건"></a>

### Mailbox와 물리 reset 조건

Role당 Control/ACK SPSC FIFO를 따로 두며 각 capacity는8이다. Producer/consumer는 각각 정확히1개 owner다.
Acquire/release atomic cursor로 전달하고 overwrite·allocation·blocking을 하지 않는다.
Owner step은 control 최대8개, Central step은 role당 ACK 최대8개를 처리한다.
Overflow는 backlog를 무효화하고 링크 continuity를 영구 latch한다. 양 owner를 join한 뒤 transport를 교체해야 하며
새 Epoch만으로 깨진 queue를 reset하지 않는다. 기존 single-owner CAN RX queue와 용도가 다르다.

`VehicleSessionInit`은 준비 때와 실제 INIT 때 trusted sensor port를 다시 확인한다.
알려진 같은 model Epoch, source/dependency age≤20 ms, wheel speed0..0.01 rad/s,
|torque|≤0.1 Nm, bus0..30 V·모든 contactor open을 요구한다. Unknown/NaN/future/held-stale는 통과하지 않는다.
센서 source·dependency 시각을 덮어쓰지 않으며 물리 정지/방전 완료를 ACK만으로 만들지 않는다.
이 수치는 functional SIL reset precondition이며 차량 calibration은 별도 검토한다.
물리 상태가 위험하면 Prepare를 Pending으로 유지하고 외부 보호·회복을 계속해야 한다.
BMS INIT 뒤에도 기존 release-band/fresh dwell을 다시 통과해야 한다.

Controller INIT는 application 상태만 초기화한다. Model Epoch/SOC/토크·angle·압력·접점/RC plant를 reset하지 않는다.
Steering/Brake/Drive는 NonDriving으로 시작하고 정상 구동 arm은 기존 준비 판정을 따른다.
준비 port는 자기 ingress/work만 quiesce하고, 자기 보호/센서 취득을 계속해야 한다. Actor끼리 교차 호출하는 기존
동기 normal/protection SIL adapter를 여러 스레드에서 동시에 호출하면 안 된다.

<a id="adr-0054-검증-범위와-다음-경계"></a>

### 검증 범위와 다음 경계

[학습 기록](../learning/vehicle-lifecycle-guide.md)의 모듈 시험, 영속 grant 연결, 실제8-role INIT/실패/rejoin·물리 보존을 검사한다.
독립8개 owner thread 시험은 typed mailbox·자기 port 접근만 확인하며 논리 clock/barrier를 사용한다.
정상 VehicleCoordinator/Zone/Leaf workload의 wall-time·SCHED_FIFO·Target timing 시험이 아니다.

현재 caller가 기존 normal actor 접근을 직렬화한다. 기존 EV runtime/demo의 request/grant fixture를 아직 교체하지 않았다.
다음은 normal 요청·arm·전송 결과·status/Actual snapshot·보호 요청을 비동기 owner port로 옮기고 global gate와 연결하는 일이다.
그 뒤 전체 workload의 독립 정지/partition·타이밍을 검사한다. Remote Leaf composite lease/stop/protection wire·DDS/Host feedback bridge는 후속이다.
M4 완료·M3 예외 해소·system TC PASS나 AUTOSAR/실차 안전성 검증을 주장하지 않는다. MBD는 M6–M8 계획을 유지한다.

<a id="adr-0055"></a>

## ADR-0055: M4 정상 운전의 비동기 owner 연결과 재현 근거

Date: 2026-10-19. Status: **Native Host 구현 / component 검증; M4 전체 수용 후속**.
[ADR-0054](#adr-0054)의 세션 경계 위에 정상 운전 경로를 연결한다.
현재 상태와 검증 분모의 기준은 [project_status](../project-status.md), 날짜별 기록은 [quality policy](../development-guide.md)다.

<a id="adr-0055-소유권과-메시지"></a>

### 소유권과 메시지

| Owner | 혼자 수정하는 상태 | 전달하는 값 |
| --- | --- | --- |
| Central | SessionCoordinator·Central ingress·VM/allocator/NormalStop·issued parent history | 원래 lifecycle/vehicle root·power output·scoped command·arm/stop operation |
| Front Zone | Front gateway·Steering/Brake Actual RX·health monitor | 두 Leaf의 CAN enqueue·정확한 operation result·원천 Actual/status |
| Rear Zone | Rear command/power gateway·Drive Actual/BMS RX·health monitor | Drive/Power CAN enqueue·operation result·원천 Actual/BMS/status |
| Steering / Brake / Drive | 해당 controller·command RX·selected output | Actual CAN frame·arm/terminal ACK·물리 출력 snapshot |
| BMS / Power | 해당 controller·limits 또는 lifecycle RX | 실제 sensor 기반 limits/local gate 또는 power status/coil output |
| Physical | angle/pressure/torque·단일 EvPowerModel의 Battery/SOC·RC/접점 | 독립 취득 identity/time/dependency를 가진 sensor snapshots |

Native 실행은9개 독립 thread다. Central ingress의 session role은 Central thread에 같이 배치한다.
다른 owner의 controller/gateway를 직접 호출하지 않는다. 과거 synchronous SIL adapter는 이 실행에서 사용하지 않는다.
Main은 생성·grants 준비와 join 후 결과 취합만 수행한다. 논리 시험은 동일 객체/port를 순서대로 호출한다.

정상 작업·TX result·feedback은 **방향별 capacity8 SPSC FIFO**이며 cycle당 각 link 최대8개를 처리한다.
Sensor/selected actuation과 local BMS→Power gate는 publisher/reader가 각각 하나인 latest snapshot이다.
Phase/control 메시지를 latest-value로 덮어쓰지 않는다. Source time·epoch·sequence·parent·expiry는 그대로 복사한다.
Control/ACK packet과 CAN bytes는 별도 typed 계약이다. DDS IDL/authentication·실제 CAN 전기 특성의 구현을 뜻하지 않는다.

<a id="adr-0055-실행-허가결과보호"></a>

### 실행 허가·결과·보호

1. 세션8-role의 Prepare/INIT/Release ACK가 모두 완료된 뒤 해당 Epoch에서 한 번만 global gate를 연다. 보호로 닫힌 gate를 일반 poll에서 다시 열지 않는다.
2. 실제 BMS release checks/dwell·power OFF/READY·두 Zone/각 Actual의 current sample을 기존 판단 함수가 확인한다.
3. 각 Leaf가 자기 fresh sensor로 arm하고 ACK한다. Zone은 그 ACK 뒤 자기 gateway를 arm한다. Central은 양 Zone ACK를 기다린다.
4. 정상 callback 성공은 **큐 enqueue**다. Epoch/token/operation/Zone/source/deadline을 대조한 TX result를 별도로 받는다.
5. Front Steering/Brake 전송 결과가 모두 성공해야 해당 batch의 Rear 명령을 queue에 넣는다. 부분 성공은 재전송하지 않는다.
6. Negative result·기한 만료·queue continuity·owner/local fault는 정상 gate를 닫는다. Zone·Leaf의 보호 진입도 Central의 후속 인지를 기다리지 않고 atomic gate를 닫는다. 다시 여는 동작은 Central의 새 전체 세션 Release만 소유한다. 별도 atomic protection signal은 정상 FIFO를 거치지 않는다.

Protection selection ACK는 실제 Leaf의 Hold/Protect/Zero·BMS inhibit/Power shutdown 선택을 뜻한다.
압력 도달·실제 토크0·차량 정지·접점 open을 뜻하지 않는다. 이 물리 반응은 별도 sensor/CSV로 관측한다.
Zone/Leaf의 기존 local timeout은 Central ACK를 기다리지 않는다. Overflow link는 join/교체가 필요하며 새 Epoch만으로 복구하지 않는다.
Broken/missing Epoch store는 자동 초기화하지 않는다. CLI의 durable grant/lock/fsync는 thread 시작 전 수행한다.

<a id="adr-0055-주기와-원래-authority-안의-배분"></a>

### 주기와 원래 authority 안의 배분

Leaf/VM/Zone 관측의 nominal 주기는10 ms, BMS/allocation은20 ms다. Physical은1 ms, transport service는200 μs다.
Worker sleep은 절대 release 기준이며 놓친 slot을 burst로 따라잡지 않는다. 실제 callback·센서 시각은 실제 monotonic time이다.
기존 M3처럼 **최소 함수 호출 간격1 ms와 외부10/20 ms release**를 분리한다. Legacy component 기본 guard는 유지한다.
30 ms functional owner gap, source age30/50 ms, dependency70 ms와 원래 expiry는 늘리지 않았다.

동기 호출 시점의 가장 최근 발급 grant와 실제 수신 grant는 다를 수 있다.
Central은16-entry issued history에서 **수신한 permission의 원래 parent**를 조회한다.
Allocation은 해당 nominal release 이후 발급한 grant가 실제 ingress에 들어올 때까지 기다린다.
그 grant의 원래 expiry가 다음20 ms release도 지원하는지 확인한다. 새 발급값으로 수신 상실을 덮지 않는다.
Waiting/arm 중에도 allocation runnable의 감시는 계속하며 grant 대기를 owner 정지로 취급해 숨기지 않는다.

Finite scenario issuer의 lifecycle 요청도 VM release와 맞추고 vehicle root는20 ms allocation release와 맞춘다.
이를 별도 상대 sleep으로 갱신하면 원래 root/ack가 오래돼 다음 command가 발급되기 전에 기존 권한이 만료될 수 있다.
초기 개발 실패는 그대로 보존하고 phase/수신 순서를 수정했다. 원래 age·expiry를 연장해 통과시키지 않았다.
Central은 새 permission ingress에서 allocation만 재개할 수 있으며 VM을 다시 실행하거나 grant 시각을 갱신하지 않는다.

<a id="adr-0055-정상-종료재가입"></a>

### 정상 종료·재가입

NormalStop은 기존 fresh actual dwell로 torque/speed/pressure를 판단한다. 최신 normal batch가 settle된 뒤
allocator를 quiesce하고 Leaf terminal 선택→두 gateway terminal 선택→정확한 ACK 순서로 넘긴다.
Handoff pending 동안 새 Enable/AllowNormal을 계속 발급하지 않는다. 원래 기한 안에서 ACK를 먼저 처리하고
그 뒤 Shutdown child를 발급해 실제 접점 open·bus discharge/OFF를 확인한다. ACK 유실·lease 만료는 보호다.
Fresh stop intent가 끊기면 기존 권한이 만료한다. Intent 갱신은 scenario issuer의 명시적인 새 요청이며 coordinator의 자체 연장이 아니다.

재가입은 gate 폐쇄·물리 정지/방전 확인·더 큰 durable Epoch·전체 INIT/ACK·BMS fresh dwell/HV readiness를 다시 거친다.
SIL Brake의 protection-mode latch는 새 trusted global Epoch release에서만 해제한다.
`BrakePressureResponse::begin()`은 pending demand/mode만 정리하며 압력·model Epoch·sensor sequence를 보존한다.
SOC/energy/RC·토크·조향각을 초기값으로 돌리는 physical scenario reset은 호출하지 않는다.
Same Epoch/일반 CAN frame이나 nominal Hold로 보호를 지울 수 없다.

<a id="adr-0055-선택적-capability와-critical-actual-구분"></a>

### 선택적 capability와 critical Actual 구분

새 permission에 묶인 가장 오래된 dependency가 이전 Inhibit의 dependency보다 과거일 수 있다.
Drive의 monotonic capability cursor는 이를 fresh 값으로 꾸미지 않고 unavailable로 낸다.
Degraded/NormalPath의 **범위 안 torque·fresh speed가 알려진 Actual**은 canonical InputsInvalid/없는 capability와 함께 사용할 수 있다.
회생 가용량은 unknown이므로 allocator가 새 negative demand를 금지하고 friction fallback을 사용한다.
Torque/speed 누락·stale·범위 초과·보호 origin은 계속 critical이다. Disabled/valid-zero capability는 알려진0이어야 한다.
이는 SYS-SAFE-005의 선택적 회생 가용량과 critical Actual 구분이며 wire/schema/P05 변경은 아니다.

<a id="adr-0055-근거와-남은-범위"></a>

### 근거와 남은 범위

[Component 추적표](../test-plan/component-traceability.csv)에서 requirement→함수→실제 GTest→criterion→결과를 연결한다.
[재현 안내](../learning/vehicle-lifecycle-guide.md)와 [최소 공유 근거](../test-plan/evidence/m4_async/README.md)에 실행 명령·대상 commit·환경·입력·수치와 그래프를 둔다.
같은 전체 CTest 결과를 재사용하며 컴포넌트 PASS를 system TC PASS로 올리지 않는다.

현재 native mailbox/CAN frame SIL과 finite trusted input issuer다. Wheel speed는0 rad/s fixture이며 longitudinal motion/controller는 M6–M8다.
SocketCAN에서 실제 remote parent/composite lease/arm/protection을 전달하는 wire 계약·독립 process/DDS/Host bridge는 후속이다.
Owner body의4 ms 초과 관측과 실제 period/loss response를 보고하되 전체 M3 timing 수용·Target/SCHED_FIFO 검증으로 확대하지 않는다.
MBD·AUTOSAR 확장 순서, 기존 M3 timing 예외·학습자 review와32개 요구/29개 system TC의 NOT RUN은 유지한다.

후속 owner/방향별 고장·joined 복구·M3 독립 guard/FIFO cohort는 [ADR-0056](#adr-0056)과 최신 project_status를 따른다. 위 관측 수치는 당시 범위다.

후속 [ADR-0059](#adr-0059)는 in-flight batch가
있는 동안 다음 due allocation을 보류하는 계약을 추가했다. 결과 deadline·기존 applied
command expiry·감시/보호를 연장하지 않으며, 정상 결과 후 fresh 입력으로 기존 release grid를 따른다.

<a id="adr-0056"></a>

## ADR-0056: M4 공통 고장 주입과 독립 실행 감시

Date: 2026-10-20. Status: **Host component 구현·검증 / 전체 M4·M3 수용 후속**.
[ADR-0054](#adr-0054)와 [ADR-0055](#adr-0055)의 소유권·세션 계약을 유지한다.
현재 상태는 [project_status](../project-status.md), 실행 근거는 [M4 fault evidence](../test-plan/evidence/m4_faults/README.md)가 기준이다.

<a id="adr-0056-공통-주입-경계"></a>

### 공통 주입 경계

`M4Fault`는 대상·path·kind·시작·지속·delay·선택 phase를 가진 값이다.
CLI는 `path:kind:target:start_ms:duration_ms:delay_ms[:phase]`를 엄격히 검사하고 thread 시작 전에 고정한다.
같은 정의를 논리 clock/native owner wrapper와 typed mailbox delivery adapter에서 사용한다. M5에서도 시나리오/criterion을 재사용하고 transport adapter는 교체한다.

| 주입 | 실제 중단하는 것 | 계속 실행하는 것 |
| --- | --- | --- |
| owner pause | 해당 owner의 세션 처리·RX·제어·자체 감시·출력·ACK 전체 | 재개 시각을 확인하는 harness; 다른 owner |
| owner overrun | 지정한 전체 owner body를 실제 sleep으로 지연 | 독립 monitor/peer; 논리 시험은 같은 구간 실행 기회 생략 |
| directional drop/delay | 지정한 정상/세션 typed link의 전달 | sender/receiver owner와 그 자체 감시 |
| overflow | 실제 FIFO consumer pop | 실제 producer; bounded FIFO가 가득 차면 기존 permanent failed latch |

Delay는 envelope/payload의 원래 source·epoch·parent·exclusive deadline을 바꾸지 않는다. ACK도 원래 plan을 유지한다.
주입 시작 설정값과 첫 실제 stop/drop/delay/blocked pop·overflow 시각은 다를 수 있어 별도 event로 기록한다.
Owner별 event 저장소와 link의 TX/RX 저장소는 각각 단일 writer이며 join 후에만 합친다. Bounded 기록 누락도 FAIL이다.

<a id="adr-0056-보호와-관측의-소유자"></a>

### 보호와 관측의 소유자

살아 있는 controller는 기존 receiver/health·authority 만료를 검사하고 atomic global gate를 닫는다.
이미 수용한 command도 원래 context expiry에서 보호한다. ingress에서만 유효기간을 검사하지 않는다.
Local BMS inhibit는 Power의 별도 최신 snapshot에도 바로 게시한다.

멈춘 Leaf는 보호 선택 ACK를 낼 수 없다. Physical의 독립 output-application watchdog은 마지막 출력 source+30 ms 뒤
angle hold·pressure floor·torque zero를 적용한다. Power driver는 실제 torque/current와 기존20 ms dwell을 확인한 뒤 코일 해제/방전을 선택한다.
물리 owner/driver가 수행한 동작은 ECU ACK로 집계하지 않는다. 센서 trace의 압력·토크·접점·bus 응답도 선택 ACK와 다르다.

공유 memory의 global gate와 atomic priority protection은 막힌 정상 FIFO를 우회한다.
이 시험의 방향별 partition은 실제 원격 process/네트워크 partition의 격리·전달 보장이 아니다.
Physical 자체가 멈추면 모델 적용도 재개까지 지연된다. OS 전체 정지/Physical와 monitor 동시 정지를 견디는 하드웨어 watchdog은 구현하지 않았다.

<a id="adr-0056-복구"></a>

### 복구

고장 해제/owner resume만으로 같은 Epoch의 latch/gate를 열지 않는다.
CLI가 thread 시작 전 발급한 더 큰 durable grant로 전체 Prepare/INIT/Release·BMS release dwell/HV readiness·arm을 반복한다.
Prepare Ready ACK 뒤 old actor는 common INIT enable을 넘겨 실행하지 않는다. 물리 reset evidence는 INIT에서도 새로 검사한다.

Failed mailbox 교체는 모든 owner 종료·join 뒤 수행한다. 동일 타입 link storage를 재구성하고 session loop를 다시 연결한다.
Actor와 Physical/EvPowerModel은 재생성하지 않는다. SOC/energy·pressure·torque·angle·회로/전원·model Epoch/sequence를 보존한다.
이전 Epoch/늦은 ACK는 새 session plan을 바꾸지 못한다. 물리 trace에 이전 Central snapshot을 새 gate Epoch 상태로 합치지 않는다.

<a id="adr-0056-기존-m3-감시-연결"></a>

### 기존 M3 감시 연결

Opt-in `guards`는 기존 `TaskSchedule`/`DeadlineMonitor`를 재사용한다.
9개 service owner의 대표2 ms 기회에 release→completion4 ms guard를 두고 열 번째 Monitor owner가 독립 poll한다.
Physical은 Monitor의 guard를 poll한다. 각 guard에는 executor와 별도 단일 observer가 있다.
누락 slot은 다음 heartbeat/완료로 채우지 않는다. Monitor가 controller를 직접 수정하지 않고 gate/priority override를 요청한다.
Physical의 실제 override 적용 시각은 별도로 기록한다.

Leaf의 nominal10/20 ms runnable은 원래5/8 ms admission/완료 budget도 검사하며 늦은 normal actuation을 게시하지 않는다.
이 검사는 독립2/4 ms whole-service guard와 구분한다. IO200 μs body 통계·2 ms guard·실제10/20 ms control 주기를 섞지 않는다.

CPU A/B와 FIFO 요청은 start gate 전에 실제 policy/priority/affinity를 대조한다. 적용 실패 시 workload를 시작하지 않고 fallback하지 않는다.
시작 장벽은 release/acquire atomic이며 setup 완료와 abort를 명확히 게시한다.
GCC11 TSan의 timed-CV 경고가 올바른 잠금 최소 예제에서도 재현돼 해당 경로를 제거했다. 기본 ASLR 매핑 오류와 process-local `setarch -R` 실행을 구분해 보존한다.

[사전 프로토콜](protocols/m4-fault-timing-protocol.md)의48회 조건·분모·deadline을 결과 전에 고정한다.
Native monotonic 통계와 logical 경계, normal과 sanitizer, 기능 보호 PASS와 정상 timing FAIL을 별도 보고한다.
기존 OPEN-M3-01/02·Target/RTOS·학습자 수용과32요구/29 system TC NOT RUN은 바꾸지 않는다.

<a id="adr-0056-다음-경계"></a>

### 다음 경계

Remote Leaf의 composite authority/INIT/arm/stop/protection wire 계약(TBD-15), clock/freshness와 DDS/QoS/격리(TBD-05)를 정한 뒤
M5 독립 process/네트워크로 옮긴다. Native fault recipe와 관측점/기준을 같은 시나리오로 재사용하되 atomic bypass를 원격 보장으로 간주하지 않는다.
MBD는 M6 MIL→M8 동등성/제어, AUTOSAR RTE/BSW·Target pilot은 기존 순서를 유지한다.

<a id="adr-0057"></a>

## ADR-0057: M4 공통 release 위상과 owner 모듈 분리

Date: 2026-10-20. Status: **구현·회귀 검사 / timing 예외 OPEN**.
기존 [ADR-0056](#adr-0056)의 시한·miss 집계·보호 조건을 유지한다.

<a id="adr-0057-원본7-fail-조사와-작은-수정"></a>

### 원본7 FAIL 조사와 작은 수정

원본12fc4a5/48회(41 PASS,7 FAIL)의 명령·실제 CPU/policy/priority/load·1211slots×10을 전부 감사했다.
[원본 audit와 최소 raw archive](../test-plan/evidence/m4_followup/README.md)는 재실행/재판정이 아니다.

FIFO Monitor311–315는 guard release에서 약1.528864ms 뒤 실행됐다. Slot316은 start/end0, deadline428838909964538ns,
독립 검출428838910477155ns다. 다음317은316 deadline 전에 완료됐지만316을 소급 완료시키지 않는 계약이므로 진짜 miss다.
실제 Monitor poll 최대2.722310ms와 guard-selected start 간격3.278ms를 구분한다. 약736.5ms 검출로 gate가 닫혀1200ms Drive 주입 전 arm이 실패했고, 원래 fault 시나리오도 올바르게 FAIL했다.

각 thread가 launch 뒤 별도 timer origin을 만든 반면 guard는 network 공통 origin을 사용한 **코드상 위상 불일치**를 확인했다.
원본 추가 지연0.722310ms의 커널 원인은 미확정이다. 요청 wake 시각이나 timer→wakeup→switch trace가 없었다.
Audit/trace hot-path 할당을 발견했지만 이 slot을 할당이 유발했다는 증거는 없다.
OTHER loaded6회는 CPU1의 owners2–7에서 함께 실행 기회가 누락됐고, 완료된 body의 deadline 초과는0이었다.
요청 CPU·FIFO 설정 실패/fallback은 없었다. CPU 경쟁/스케줄링 제약과 부합하지만 개별 wake 지연의 커널 원인을 확정하지 않는다.

Commit603fe24는 `M4ReleaseGrid`로 모든 sleep을 공통 절대 origin에 정렬하고 catch-up을 하지 않는다.
Audit duration/physical·central trace 저장소는 launch 전에 유한 run 크기로 reserve한다.
`requested_wake_ns`를 execution CSV 끝에 추가하고, audit 성장 횟수를 JSON에 더한다(기존 열/CLI 유지).
실제 요청 wake→start와 guard release→start를 구분한다. 재가입 guard도 같은2ms 격자에 올린다.
기존2ms opportunity,4ms deadline,1211slots,100ms lead/20ms tail,독립 검출/물리 적용 각각10ms는 바꾸지 않는다.
원본 위상/추가 지연을 replay한 logical test는 이전 위상에서316 miss, 정렬 후 miss 없음으로 원인 노출을 재현한다.

[사전 고정 프로토콜](protocols/m4-follow-up-protocol.md)의 새48회는42 PASS/6 FAIL이다.
FIFO24/24(Drive stop6/6 포함), OTHER loaded normal0/6이다. 원본41/7을 대체하거나 OPEN-M4-TIM-01을 닫지 않는다.
현재 Host integration의 기존 IO/FIFO 선택은 ADR-0042의 제한된 실험 profile이며, OTHER 부하 조건 전체 요구를 충족했다는 뜻이 아니다.

<a id="adr-0057-별도-동작-보존-리팩터링"></a>

### 별도 동작 보존 리팩터링

Commit77d411c는 다음 책임을 기존 상위 directory 아래 분리했다. 새로운 scheduler/범용 framework는 없다.

| 모듈 | 소유 책임 |
| --- | --- |
| m4_async_runtime.cpp | public config/시나리오 dispatch |
| m4_owner_network.hpp/.cpp | private owner 상태·bindings·물리 적용·시나리오/고장 진행·세션 boot |
| m4_owner_execution.cpp | logical/native 실행·설정·launch·stop/join |
| m4_result.cpp | join 뒤 통계·판정·CSV/JSON |
| owner_messages.hpp / gateway_messages.hpp | canonical data, queue/atomic/controller 구현 의존 제거 |
| local_owner_transport.hpp | same-process SPSC·clock·atomic gate/protection |
| normal_stop_contract.hpp / bms_parent_context.hpp | 구현에서 공유 데이터 계약 추출; 옛 헤더는 include 호환 |
| session_reset.hpp/.cpp | 동기/비동기 공통 복구 predicate; 물리 상태 초기화 없음 |
| cmake/TestCategories.cmake | disjoint unit/integration.logical/runtime.wall; 기존 GTest/CTest 이름·assertion 유지 |

`owner_contract_boundary` compile-only target은 controller/queue header include 경로 없이 canonical contract를 컴파일한다.
기존908+release-grid/guard4=912개 이름이 모두 보존됐다. Label은 unit768/logical135/wall9다.
원본→위상 수정35개, 위상 수정→분리36개 logical physical trace가 byte 단위 동일했다. 신규 rejoin trace1개를 별도로 구분한다.
Normal/ASan·UBSan 각각912/912, 변경 native thread TSan9/9 PASS(ASLR process-local off)다.
리팩터링 후 별도48회도42 PASS/6 FAIL, FIFO24/24다. 두48회를 하나의 성공 cohort로 합치지 않는다.

<a id="adr-0057-남은-원인과-수용-경계"></a>

### 남은 원인과 수용 경계

OPEN-M4-TIM-01은 **partial mitigation, OPEN**이다. 원본 FIFO 추가 wake 원인과 OTHER6개는 미해결이다.
필요한 추가 관측은 같은 CPU map에서 hrtimer expiry/요청 wake→sched_wakeup→sched_switch, runnable/IRQ/preemption·migration,
slot/owner TID correlation이다. 이 Host는 tracefs/perf 권한이 없어 해당 원인 분석은 BLOCKED이며 sysctl/권한을 임의 변경하지 않는다.
새 common-grid wake 기록은 application 구간만 좁힌다. PREEMPT_RT/RTOS·Target 또는 worst-case 상한 증거가 아니다.
기존 OPEN-M3-01/02와 학습자 검토, system32요구/29TC·Target NOT RUN을 유지한다.

<a id="adr-0058"></a>

## ADR-0058: 원격 owner authority와 Host 통신 후보 경계

후속 관계(2026-10-22): 원격 계약은 유지한다. Host 전송 채택은 [ADR-0060](#adr-0060)→[0061](#adr-0061)→[0062](#adr-0062)로 이어졌다. DDS 실패/gate를 해결한 것은 아니다.

Date: 2026-10-20. Status: **원격 계약/Leaf component 구현; middleware 후보 실험·M4 종료 검토**.
[ADR-0054](#adr-0054)/[0055](#adr-0055)/[0056](#adr-0056)의 상태 소유권, 원래 시각, 보호 latch를 유지한다.

<a id="adr-0058-결정과-구현"></a>

### 결정과 구현

[Owner wire v1 ICD](../interfaces/owner-wire-v1.md)는 canonical message contract를512byte 이내 고정 width로 직렬화하고 outer CRC32C로 route·clock·parent/expiry·raw CAN까지 검사한다. CAN/DBC/P05 layout/DataID/counter는 바꾸지 않는다. SYS-COM-002의 interface refinement v0.6으로 기록했다.
Codec library는 controller/local atomic/SPSC 구현을 포함하지 않는다. 구조적 decode와 도메인 admission·trusted peer 검증은 별개다.

`RunLeaseIssuer`는 실제8-role SessionCoordinator의 마지막 Release ACK 뒤에만 global credit를 발급한다.
각 `RunLeaseGate`는 trusted local INIT의 정확한 Plan과 common clock에 묶인다. Source age30ms, maximum life60ms, exclusive expiry를 검사하고
이전 credit 만료를 늦은 새 credit보다 먼저 검사한다. Same-Epoch latch를 해제하지 않는다. 새 전체 INIT만 bind할 수 있다.

`RemoteLeafEndpoint`는 실제 AsyncLeafOwner 하나와 그 **프로세스 내부만의** gate/link를 단독 소유한다.
정상 ingress는 local session+global credit 뒤 허용하지만 실제 arm·센서/요청/command composite context는 기존 actor가 다시 검사한다.
INIT 전후 센서/보호 service를 멈추지 않는다. Credit 만료·명시적 보호·failed FIFO는 실제 actor 보호로 이어진다.
보호 ACK는 해당 Leaf가 실제 선택한 뒤 보내며 sender/token별 duplicate 시각이 불변이다. 멈춘 peer/물리 watchdog의 ACK를 합성하지 않는다.
종료 lease의 source/expiry와 원천 CAN Actual의 payload/source/P05는 전달만 한다.

Host 첫 profile은 동일 kernel CLOCK_MONOTONIC과 trusted launch-domain을 사용한다. Packet으로 offset/Epoch를 학습하지 않는다.
Offset/uncertainty를 포함한 시간 경계 산술은 시험했지만 inner CAN/RX가 다른 clock을 쓰는 runtime은 gate가 거부한다.
Target/다른 kernel의 sync·uncertainty·CAN source mapping은 후속 배포 gate이며 구현 완료로 취급하지 않는다.

Component 시험에서 진단 원인이 `Expired`→`Protection`으로 덮이는 결함을 찾아 최초 원인을 보존했다.
36개 신규 시험(30unit/6logical)과 기존912개 전체를 normal·ASan/UBSan에서 검사했다.
새36개 TSan은 PASS, native9개 TSan 중1개 정상 운전 CommandDelivery FAIL은 별도 OPEN으로 유지한다.
추가1회 trace 진단 PASS는 원래9개 실패를 대체하지 않고 원인을 확정하지 못했다.

<a id="adr-0058-tbd-05-후보-비교-범위"></a>

### TBD-05 후보 비교 범위

DDS 기본 방향을 유지한다. 실험은 **Cyclone DDS11.0.1 direct C API**와 **Zenoh-C1.10.1 stable C API**를 비교한다.
ROS 2 executor/graph를 도입하지 않고 기존 C++17 owner port에 byte adapter를 두는 방향이다.
실험 dependency는 공식 release URL/SHA를 검증해 ignored build 아래에만 설치한다. 일반 build는 dependency/network fetch 없이 유지된다.

| 항목 | DDS 후보 | Zenoh 후보 |
| --- | --- | --- |
| Schema/API | IDL fixed packet512 + length, direct C API | C bytes/key expression, canonical owner packet |
| 연결/격리 | explicit UDP peers, multicast off, domain37 | peer TCP explicit endpoint, multicast scouting off |
| sample policy | RELIABLE KEEP_ALL, volatile,8/1/8 resources, blocking0 | publisher DROP, mutex callback queue8 |
| owner 접점 | owner thread가 bounded take; background DDS thread가 controller를 호출하지 않음 | callback는 고정 queue에 복사만; owner가 bounded take |
| 관측 | write/take 오류 **및 reader rejected/lost status**, 적용 QoS readback | put 오류·callback overflow; 실제 affinity/policy |
| 원래 freshness | reliable 재전송도 원래 expiry/epoch 검사; stale reply는 ACK 아님 | 재접속/queue도 원래 expiry/epoch 검사 |

두 독립 process를 user+network namespace/veth에 배치하고 똑같은100+3 requests/clock/부하로 실제 방향별100% loss/100ms delay와 overflow를 주입한다.
단순 source-preserving **echo**이며 실제 Central allocator/Zone gateway/Leaf Actual 배포가 아니다. Full session/rejoin 또는 멈춘 ECU 보호를 이 실험으로 주장하지 않는다.
[사전 v1](m4-test-protocols.md#m4_middleware_probe_protocol)의36회는30 PASS/6 FAIL로 보존한다.
DDS up-loss3은 총 수신 수만 세어 reliable backlog의 늦은 응답을 놓쳤고, overflow3은 reader rejection 관측이 빠졌다.
[V2](protocols/m4-middleware-probe-protocol-v2.md)는 원래 기준을 유지하며 expired echo와 DDS reader status/readback을 추가한 새36회다.
V2는36/36 PASS다. 공유 근거의 두 결과 묶음에서 실제 분모/판정을 확인한다. 짧은 echo 결과를 성능 우월성/RT/전체 DDS 수용으로 확대하지 않는다.

Host M5 후보는 기존 DDS 방향/Cyclone direct API를 우선한다. 다만 application/C wrapper ASan4/4 PASS와 별개로, wrapper TSan4/4 FAIL·완전 계측 DDS SDK 추가2/2 FAIL을 보존한다. DDS entity-index/hopscotch/GC 경고를 실제 lifetime race 또는 progress-based reclamation의 sanitizer 해석 문제로 구분해야 한다. 억제하거나 단순 false positive로 판정하지 않는다(OPEN-M4-MWTSAN-01). Zenoh 전체 Rust 계측은 toolchain 부재로 미실행이다. 특정 middleware의 배포 수용은 후속 진단 전까지 보류한다. Zenoh는 대안으로 보존하고 채택하지 않는다.
Cyclone/Zenoh 내부 memory·worst-case blocking이 이 probe로 증명된 것은 아니다. M5 adapter에는 별도 bounded application mailbox와 permanent failure latch가 필요하다.
Normal FIFO가 실패하면 정상 dispatch를 멈추고 보호 선택/채널 실패를 별도 기록한다. Write 성공은 enqueue조차 아닌 middleware 수용 결과일 뿐, 실제 ECU/물리 ACK가 아니다.
Session/control·normal work/result·원천 feedback·protection의 독립 bounded lane/QoS와 원래 deadline 검사는 첫 adapter 구현에서 검증해야 한다.
보호를 정상 FIFO와 같은 막힌 lane에만 의존시키거나 shared atomic bypass로 대체하지 않는다. Channel 재생성은 owner stop/join 뒤, 신규 durable Epoch/전체 handshake/arm으로 한다.

<a id="adr-0058-m4m5-gate"></a>

### M4/M5 gate

[M4 exit review](milestone-reviews.md#m4)는 timing 실패·TSan native 기능 실패와 middleware 관측 보완을 함께 대조한다.
현재 전체 M4 종료를 선언하지 않는다. 첫 M5 제어 adapter의 **구현은 아직 시작하지 않았고**, echo probe만 실행했다.
기존32req/29 system TC·Target/remote vehicle runtime NOT RUN, 학습자 직접 재현/설명 REVIEW PENDING을 유지한다.
MBD M6 MIL→M8 동등성, AUTOSAR/RTOS Target pilot 순서도 유지한다.

<a id="adr-0059"></a>

## ADR-0059 — Pending command와 allocation release의 분리

Date:2026-10-20. Status: **ACCEPTED for Host component implementation**.
M4 종료·Host timing·Target 수용은 별도이며 현재 기준은 [project_status](../project-status.md)다.

<a id="adr-0059-문제와-관측"></a>

### 문제와 관측

ADR-0055의 Front 성공→Rear 송신 순서와20ms TX result envelope는 유지한다.
기존 port는 진행 중인 batch가 있으면 `deliver_commands()`를 false로 반환했다.
Coordinator는 다음20ms 배분에서 이를 실제 전달 실패와 동일한 CommandDelivery로 해석했다.
전송 결과가 아직 유효한 대기 상태인지, timeout인지, 적용 중인 명령이 만료됐는지 구분하지 못했다.

`29b8221` 논리 재현의 초기 clock은1s다. 아래는 동일 clock의 **경과 ms**이며,
root 생성과 CAN 명령 생성, 수신 처리와 실제 출력 발행을 구분한다.

| 사건 | Rear result19.8ms 지연 | Front/Rear result 각각12ms 지연 |
| --- | --- | --- |
| 현재 root 생성 / CAN 명령 생성·Front 최초 송신 | 1001 /1005.2 | 1001 /1005.2 |
| Front 수신·Leaf 처리 / Central 결과 도착 | 1005.4 /1005.4 | 1005.4 /1017.4 |
| Rear 최초 송신 / Leaf 처리 | 1005.4 /1005.6 | 1017.4 시도 때 이미 gate 닫혀 송신 거부 |
| Front / Rear 전송 deadline | 1025.2 /1025.4 | 1025.2 /새 Rear envelope 생성 안 됨 |
| 새 명령 내부 expiry | 1031.000001 | 1031.000001 |
| 이전 Rear 명령 expiry | 새 명령으로 대체됨 | 1011.000001, 실제 local service1011.2에서 보호 |
| 다음 nominal allocation / grant ingress 충족 | 1021 /1025.2 | local 보호가 먼저 발생 |
| 수정 전 Central 보호 | 1025.2: 아직 pending이라는 이유 | 1015: local 보호 관측;1017.4ms의 늦은 Front 결과로 복구 안 됨 |
| 수정 후 | pending 보류;1025.4의 exact-expiry 응답은 거부·보호 | 기존 만료 보호 유지 |

TX result는 Zone의 CAN 전달 처리 결과다. `leaf-completed`는 Leaf 수신 처리,
`leaf-output-published`는 해당 명령 identity를 가진 controller 출력 snapshot 발행이다.
Physical owner가 이를 적용하는 별도 step과 angle/pressure/torque/HV 응답은 physical CSV에서 확인한다.
어느 관측도 다른 endpoint의 ACK나 실제 물리 도달로 바꾸어 기록하지 않는다.

<a id="adr-0059-선택한-계약"></a>

### 선택한 계약

1. 정상 batch는 하나만 in flight다. Front/Rear 순서·부분 실패 보호는 그대로다.
2. 다음 배분이 due인데 batch가 진행 중이면 `allocation_ready()`가 false다.
   새 command를 계산·queue·재전송하지 않고 **due release 한 건**을 보류한다.
   보류 중 nominal allocation 기준 시각을 갱신하거나 미처리 release를 FIFO에 쌓지 않는다.
3. Central의 transport/status/VM과 실제 owner runnable은 계속 실행한다.
   `ControlAllocation::poll()`은 원래 request/support expiry와30ms tick-gap을 검사한다.
   poll은 성공적인 allocation tick으로 간주하지 않는다. 기다림으로 감시 시한을 연장하지 않는다.
4. 결과가 원래 시한 안에 완료되면 다음 service에서 **현재 root·fresh feedback·실제 수신 permission**을
   재검증하여 계산한다. 지연 동안 계산해 둔 command를 보내지 않는다.
   external release의 기존20ms grid에 정렬하며 missed release를 burst로 따라잡지 않는다.
5. `service()`의 result timeout/negative/mismatch/overflow와 독립 Zone·Leaf의 명령 만료 보호가 우선한다.
   각 result의 exclusive deadline, 최초 sent, 내부 command expiry·Epoch/token·parent/lease·CAN/P05 불변이다.
   아직 응답을 기다릴 수 있다는 사실은 이전 applied command의 수명 연장 근거가 아니다.
6. 유효기간 내 일시적인 지연은 정상 복귀할 수 있다. 지속적으로 처리량이20ms 주기를 따라가지 못하면
   기존 command/authority가 만료되어 보호할 수 있다. 이를 통과시키기 위한 deadline 증가는 하지 않는다.
7. 같은 Epoch의 latch/gate는 자동 해제하지 않는다. 정상 Stop은 기존 batch settlement를 기다리고,
   고장 복구는 기존 physical readiness·더 큰 durable Epoch·INIT/ACK·readiness·arm을 따른다.

<a id="adr-0059-선택-이유와-범위"></a>

### 선택 이유와 범위

Batch를 병렬 전송하거나 이미 계산한 command를 덮어쓰는 방식은 기존 Front 부분 실패 계약과
권한/sequence 의미를 바꾸므로 선택하지 않았다. Pending을 성공으로 반환하고 새 command를 버리는 방식도
실제로 전송하지 않은 allocation을 완료된 것처럼 기록하므로 사용하지 않았다.
기존 grant ingress 대기 경로에 in-flight 조건과 감시를 추가하는 작은 변경으로 구현했다.
일시 지연 예는 Front0.2ms/Rear19.6ms result delay를1000–1020ms에만 주입한다.
Rear 결과는1025.4ms 도착, 원래 deadline1025.6ms 전에 성공하고 같은 service에서 fresh allocation을 재개한다.
다음 root는1041ms로 nominal20ms 간격을 유지한다. 지속 주입 대조군은 Rear 명령1551.000001ms 만료를 숨기지 않는다.

기존 `PendingRearResultSelectsCommandDeliveryBeforeIndividualExpiry` 이름은 역사적 재현을 위해 유지한다.
Assertion은 “기한 전 CommandDelivery”에서 “기한 전 보류, exact expiry에서 ResultLate 보호”로 변경했다.
기존966개 시험 이름과 안전 시한은 유지한다. 변경 전/후는 [새 근거](../test-plan/evidence/m4_settlement/README.md)에 보존한다.
이 논리 결함 수정은 과거 native TSan untraced 사건의 원인을 확정하는 증거가 아니다.
Host PC와 Jetson 한 대/내부 여러 vECU 배치, MBD·AUTOSAR 순서와 M5 adapter 미착수는 유지한다.

<a id="adr-0060"></a>

## ADR-0060: Central–Front SOME/IP Host component pilot

후속 관계(2026-10-22): Pilot의 grant fixture를 정규 세션으로 보지 않는다. 후속 실제 세션/Host adapter 채택은 [ADR-0061](#adr-0061), Rear 확장은 [0062](#adr-0062)를 따른다.

Date: 2026-10-21. Status: **conditional Host pilot candidate; regular adoption deferred**.

The DDS control gate remains CLOSED. Evaluate SOME/IP using pinned COVESA vSomeIP
3.7.6 in a separate opt-in Linux C++ execution path. Protocol and implementation
are distinct choices; changing protocols does not resolve the historical Cyclone
DDS shutdown or TSan failures. No default production transport/dependency changes.

Reuse owner-wire v1 and actual allocation/Front/Leaf component contracts. Limit
the first binding to TCP methods for readiness, work/result and Actual status;
define the precise [wire table and component fixture boundary](../interfaces/someip-pilot.md).
Use separate netns/veth and mount namespaces to exclude local IPC-only success.
Keep source/expiry, 20ms envelope, capacity8, Epoch/token/operation, route/clock/CRC,
local protection and new-session recovery rules. Discovery does not authorize arm.

Build normal, ASan/UBSan and TSan separately, including SDK and compiled Boost
dependencies. Preserve initial failures and compare only explained corrections
under [the prospective fixed protocol](../test-plan/evidence/m5_someip_pilot/protocol.md).
Do not substitute short pilot success for M4 closure, regular M5 adapter, real IO,
multi-participant session handling, Jetson suitability or whole-system qualification.
Results and adoption verdict belong to the [evidence](../test-plan/evidence/m5_someip_pilot/README.md).

<a id="adr-0061"></a>

## ADR-0061: Host Central–Front SOME/IP owner adapter

Date: 2026-10-21; updated2026-10-22. Status: **limited adoption of Host FIFO Central–Front functional SIL, host10-v1**.
Latest qualification is in the final section below; earlier cohorts/decisions remain historical.

Current Rear extension: [ADR-0062](#adr-0062) accepts the
documented three-process Normal FIFO Host scope. The local Rear statements below
remain historical to the original two-process cohorts.

Extend the opt-in vSomeIP path from component grants to real SessionCoordinator,
RunLeaseIssuer, eight actual participants, VehicleCoordinator, Front/Rear/Leaf
owners and independently continuing local protection. Central and Front are separate
IP processes. A single persistent SIL model retains physical history. Rear and its
Leaf owners remain local to Central for this phase. The [binding](../interfaces/someip-front-adapter.md)
preserves owner-wire identity, CAN/P05, original expiry and20ms envelope.

Use separate bounded ordinary and authority TCP lanes, asynchronous owner results,
and nonce-correlated one-way readiness methods in both directions. The latter avoids
vSomeIP3.7.6's request/response target-cache replacement on reconnect using supported
APIs; no SDK behavioral patch, warning suppression or queue growth is adopted.
Discovery/readiness/send-return never authorizes arm or completes a control request.

[Evidence](../test-plan/evidence/m5_someip_front_adapter/README.md) demonstrates real
8-role Release, RunLease/arm, normal control/Actual, rejection, expiry/protection,
full8/8-queue shutdown and new-Epoch recovery while Central survives. Completed C++
campaign raw40/41 plus the runner-only restart correction3/3 are separate denominators;
the original13 failures across201 runtime attempts remain immutable. SDK and project
ASan/UBSan/TSan instrumented builds were exercised; this is not SDK-wide safety proof.

This is an executable functional integration, with fixed trusted demand and SIL
physical/sensor IO still fixtures. The [native follow-up](../test-plan/evidence/m5_someip_native_watch/README.md)
now connects existing2ms opportunities/4ms independent execution monitoring to the
actual grouped Central/Front owners and persistent physical process. Completion
identity uses the original requested wake. SDK send/probes run outside control-owner
work; SDK threads stayOTHER0 on separateCPU4/5, ownersCPU1/2, physicalCPU3 and
monitorsCPU0. Original authority/message/controller deadlines are unchanged.

New Normal FIFO normal quiet/loaded profiles pass3/3 each in a2540ms measured window.
Keep that limited normal-operation evidence separate from adoption: final functional
Normal12/13, ASan13/13, TSan10/13 and actual adapter48=31/48 do not meet all fault/
recovery conditions. **Do not expand conditional adoption to unrestricted operation.**
Original command expiry still protects in some normal runs; the earliest allocation/
gateway cause is partly unresolved. TSan old placement0/13 and all other raw failures
remain. The61ms historical model cause remainsOPEN despite improved observations and
controlled energy.step reproduction. Next correlate permission/allocation phases and
first gateway cause against original Leaf expiry before one targeted correction/test.

Keep the default transport/dependency selection unchanged. DDS control gate remains
CLOSED with all Cyclone DDS FAIL/OPEN records; SOME/IP is a separate conditional
integration route, not a resolution of those defects. M4 remains Host native IO/FIFO
component limited acceptance / whole NOT CLOSED. Rear network, Jetson, real IO and
whole-system validation are NOT RUN. ADR-0060 remains the historical component-pilot
decision; this ADR supersedes only its statement that no real owner adapter exists.


<a id="adr-0061-2026-10-22-limited-fifo-follow-up"></a>

### 2026-10-22 limited FIFO follow-up

[New evidence](../test-plan/evidence/m5_someip_fifo_refresh/README.md): final Normal
FIFO8/8 and ASan/UBSan/TSan SDK boundary2/2 each. User-approved criteria require
Normal FIFO normal/core protection/shutdown/rejoin; OTHER loaded timing is diagnostic,
and sanitizer wall time is separate from Normal performance. Actual memory/UB/race
reports remain failures. Durable Epoch issuance now precedes a generation's native
watch. Allocation readiness checks usable received authority at actual execution time.
No period, expiry, source age, envelope, native deadline, queue or SDK change.

The saved grant is69,603ns short of the next20ms release. Removing the phase check
caused deterministic early command expiry and was rejected. That renewal defect is
not fixed by the narrower readiness/startup corrections or the later passing cohort.
Functional SIL adoption remains conditional; FIFO acceptance expansion and Rear
connection remain blocked on original-deadline renewal. M4 whole/Jetson/system and
all DDS historical FAIL/OPEN remain separate. Do not reintroduce OTHER loaded timing
as a blocker for this user-approved limited scope.

<a id="adr-0061-2026-10-22-actual-leaf-renewal-qualification-host10-v1"></a>

### 2026-10-22 actual Leaf renewal qualification: host10-v1

[Implementation and evidence](../test-plan/evidence/m5_someip_refresh_delivery/README.md),
source6b2b5a3: adopt the explicit Host10ms renewal profile for this Host adapter.
Keep default legacy20ms component behavior. Management remains10ms/phase+4ms;
fresh VehicleRequest/allocation now run10ms, with permission expiry strictly after
release+18ms (next10ms release +8ms remote handover reserve). Matching usable received
grant and source≥release checks remain. No authority/command/source-age/native/wire
expiry is extended;8ms is admission headroom, not a guarantee for arbitrary20ms delay.
This doubles normal command/request traffic, without increasing queues or VM/Leaf rates.

The real-owner phase replay first FAILS with legacy20: source-age-limited grant defers
allocation, all three Leafs expire. Same acquisition/transport schedule with host10
receives102 commands/Leaf before preceding original expiry, min5.230397ms margin;
interrupted renewal still expires/protects. Historical exact limiting input is unknown,
so the controlled169,603ns deficit does not purport to prove the old69,603ns event's
network delay. Preserved raw historical failures remain failures.

Final Normal FIFO quiet2/2, existing loaded2/2, command-loss/owner-pause/central-stop/
restart-live4/4, instrumented actual SDK ASan/UBSan2/2 and TSan2/2, full Normal/ASan
983/983 each. Four normal runs receive all698 commands per Leaf, minimum13.555378ms
renewal margin. New runner rejects missing/duplicate/late Leaf handover and changed
original expiry. No unexpected SDK/sanitizer errors or forced cleanup. Intentional
owner-pause miss is protection success, not normal timing success.

**Host FIFO Central–Front limited acceptance; Rear integration may proceed next.**
Scope: documented CPU/policy,2540ms window, existing load and eight real participants,
SIL plant/sensors/trusted demand. OTHER loaded timing is diagnostic under the already
approved criteria; sanitizer wall time is separate. All historical OPEN exceptions,
M4 whole NOT CLOSED, DDS gate CLOSED, Rear network/Jetson/system NOT RUN remain.
No new adoption gate requires closing unrelated nonreproduced historical incidents.

<a id="adr-0062"></a>

## ADR-0062: Host Central–Front/Rear SOME/IP owner separation

Date2026-10-22. **Accept the documented Normal FIFO Host functional SIL profile**.
[Evidence](../test-plan/evidence/m5_someip_rear_adapter/README.md),
[wire/ownership contract](../interfaces/someip-rear-adapter.md). This extends ADR-0061's
accepted Central–Front host10-v1 path; it does not resolve historical DDS defects.

Central retains real session/RunLease issuance and allocation. Front uniquely owns
FrontZone/Steering/Brake. A separate Rear process uniquely owns RearZone/Drive/BMS/
Power. Their real8-role controls/ACKs, original permissions/credits/commands/results/
Actual/health/protection cross distinct SOME/IP TCP services in separate netns.
Existing owner-wire/CAN/P05 and Front result→Rear command ordering remain. No direct
call/shared-memory control bypass, fabricated ACK, replacement transport or SDK
redesign is introduced. Common transport/Zone endpoints avoid copying adapters.

Keep actual host10-v1 periods, original source/expiry and next-release+8ms support,
20ms envelope, queues8 and2ms/4ms watch. Observed placement is Central1/FIFO11,
Front2/FIFO18, Rear7/FIFO18, plant3/FIFO19, independent monitors0/FIFO20,
SDK4/5/6 OTHER0, plant auxiliary14 OTHER0. Existing OTHER7ms/10ms load applies to
CPU1/2/7. Qualification is2540ms after readiness plus actual NormalStop/HV-off tail;
this is not an indefinite scheduling guarantee or physical fault isolation.

Protected rejoin closes/counts old ingress during graph retirement/durable Epoch IO.
It never clears overflow or renews messages. Surviving processes stay alive and all
actual participants handshake in a new Epoch before credit/arm. Remote wrappers
respect the existing Prepare Ready quiescence; old credit cannot repeatedly advance
the retired actor across agreed INIT. Real Abort/session faults still protect.

Final implementationa790032: Normal FIFO10/10, ASan/UBSan2/2, TSan1/2. Full C++
Normal/ASan987/987 each; original983 tests retained. Small real-owner INIT repro
FAIL→PASS. Normal4 runs have minimum Steering/Brake/Drive renewal margin
7.766637/7.764243/7.163085ms; post-rejoin minima6.378692/6.376290/5.576097ms.

**TSan normal window remains FAIL/incomplete**, with original short-support→expiry
protection and a secondary TX/probe overflow latch; TSan Rear rejoin passed, actual
memory/UB/race warnings0. Under the user-approved criteria, sanitizer wall timing
is separate from Normal operating performance. Do not promote that FAIL to PASS
or claim full-window TSan qualification. Preserve OPEN-SOMEIP-REAR-01 and all41
raw attempts (34 PASS/7 FAIL); only the fixed Normal FIFO profile is accepted.

Rear Host connection is complete in this finite scope. SIL physics/sensors/trusted
scenario inputs remain fixtures. The old detailed Central watch CSV alias on rejoin
is a recorded observation limitation; crash snapshots/events/new-generation records
are retained. SDK-wide safety, cross-machine clock sync, actual NIC/CAN, Jetson,
M6 and whole-system/M4 closure are not established. DDS gate remains CLOSED and its
FAIL/OPEN records unchanged. M6 model/scenario boundary design is a next candidate,
not work started by this decision.

<a id="adr-0063"></a>

## ADR-0063: M6 actual 기반 Simple Vehicle와 첫 종방향 MIL

후속 관계(2026-10-22): 당시 첫 구현 결정은 유지한다. vehicle/EV 결합은 [ADR-0064](#adr-0064), M6 Host quiet SIL/MIL 종료는 [검토표](milestone-reviews.md#m6)에서 후속 판정했다.

Date: 2026-10-22. Status: **M6 첫 구현 경계 채택 / 유한 검증 결과는 evidence 참조**.

사용자가 완료된 Rear 연결 뒤 M6 진행을 요청했다. M5 3-vECU Host 수용과 과거
DDS/TSan OPEN을 보존하면서 ADR-0052의 M6 plant/MIL 순서로 진행한다.

1. 단일 persistent physical process에 SimpleVehicle를 선택형으로 추가한다.
   기존 실제 actuator 모델의 값만 운동 입력으로 사용하고 계산한 wheel speed를 기존
   Rear Drive 센서/CAN/P05/SOME/IP/Central validator 경로에 되돌린다.
2. flat forward-only inertial longitudinal + kinematic bicycle을 첫 설명 가능한 모델로
   택한다. geometry/force scale은 allocator와 일치, road force는 명시적 가정이다.
   모델 state/source는 ECU rejoin으로 reset하지 않는다.
3. 첫 MBD 도구(TBD-16)는 작은 Python 실행 모델로 결정한다. PI+reference feedforward,
   conditional anti-windup·slew·invalid latch·새 INIT를 고정 vector/closed-loop로 검사한다.
   Simulink/생성 C++/제품 tool qualification은 채택하지 않았다.
4. 실제 이동에서 드러난 NormalStop 인계는 standing-hold pressure 자체의 도달과 기존
   dwell을 요구해 수정한다. 명령/허가/감시 시한과 Leaf monitor를 완화하지 않는다.

구체 수식·책임/clock·parameter·실행 flag는 [ICD](../interfaces/simple-vehicle-model.md),
사전 조건·시도별 원본·결과는 [M6 근거](../test-plan/evidence/m6_simple_vehicle/README.md)에 둔다.
기존 M5 기본 fixture/범위는 유지하며 M6 적용을 opt-in으로 구분한다.

이 결정은 실제30km/h 차량 SIL closed-loop나 M6 전체 종료가 아니다. 현재 실제 ECU의
vehicle demand는 시나리오 fixture다. M6 MIL은 독립 Python 근사 plant이며 기존 C++
actuator/EV library를 실행한 것과 구분한다. C++ controller·공통 vector 동등성·실제 Central
속도 폐루프는 ADR-0052의 M8 책임이다. CARLA(M7), Target/Jetson, M4 전체 수용은 별도다.

공식 운동학/anti-windup 자료는 ICD에 링크했다. 값과 알고리즘은 이 프로젝트의 SIL
선택이며 해당 제품/차량의 calibration이나 성능 보증을 가져온 것이 아니다.

<a id="adr-0064"></a>

## ADR-0064: 차량 운동과 EV의 구간 에너지 결합

후속 관계(2026-10-22): 아래는 당시 구현/FAIL과 물리 시한 후속 결정이다. 이후 [M6 종료 검토](milestone-reviews.md#m6)에서 Host quiet SIL/MIL 범위 종료를 판정했다. 과거100ms FAIL/SDK OPEN은 그대로다.

Date: 2026-10-22. Status: **구현·component 및 일부 Host 기능 검증 / 전체 M6 수용 보류**.

M6 후속으로 actual 기반 차량 운동, 회생/마찰 배분과 실제 EV 전원·배터리 에너지 수지를
연결한다. 기존 SimpleVehicle 거리 적분과 electrical beginning-speed ZOH는0.2s 재현에서
1.792405J 차이가 났다. 새 물리 결합은 같은 구간 motor work를 명시적 interval port로
전달한다. scalar source를 바꾸거나 end speed를 과거 acquisition으로 쓰지 않는다.

`VehicleEvModel`이 candidate vehicle/electrical/Battery를 함께 commit하고, 독립 ledger는
kinetic/friction/road/motor/circuit/auxiliary/ohmic/capacitor/chemical 항을 비교한다.
기존 모델·일반 receiver defaults를 전면 교체하지 않는다. 기존 physical process만 이 결합을
소유하며 session/ACK/permission/control 경계에는 물리 bus 우회를 추가하지 않는다.

실제 주행에서 확인한 EV capability 소실은 Central/Rear receiver의 generic30ms dependency
설정이었다. 이미 정의·지원된 EV70ms를 명시한다. 실제 source30ms,80ms RX timeout,
원래 command expiry·20ms envelope·allocator20ms support 및 host10-v1은 그대로다.
처음 의심한 optional20ms support 가설은 실제 Unavailable 분기로 기각했고 수정하지 않았다.

정상8s quiet FIFO energy cycle와 charge-zero는 실제3-process/8참여자 session으로 통과했다.
Normal owner pause/Rear rejoin도 통과했으나 **command-loss의 기존 physical100ms 기준은 FAIL**이다.
주입 후 local zero-target 선택은 약18ms였고, 관측 torque와 기존2000Nm/s ramp로는 남은
시간 안에 actual zero를 만들 수 없다. SYS-SAFE-004의 zero-target 선택과 실제 물리 응답을
구분한다. 기존100ms raw 판정·모델 rate를 바꿔 통과시키지 않으며 새 profile의 전체 수용을 보류한다.
실제 response budget(TBD-03)/해당 gate 적용 범위의 다음 검토가 필요하다.

ASan 재가입과 TSan 실행에도 wall/transport 실패·SDK queue drop이 남았다. 실제
memory/UB/race 진단0이 기능 실행 완료를 뜻하지 않는다. 원본 분모를 유지하며 SDK 오류를
일괄 면제하지 않는다. 이 실패 때문에 기존에 수용한 M5 범위를 다시 무효화하지 않는다.

상세 [모델 경계](../interfaces/vehicle-energy.md), [protocol/근거와 미완료](../test-plan/evidence/m6_vehicle_energy/README.md)를 따른다.
M6 전체 종료/M7 CARLA/M8 C++ controller·동등성/Jetson·전체 시스템으로 확대하지 않는다.

<a id="adr-0064-2026-10-22-후속-결정--현재-sil-물리-응답-범위"></a>

### 2026-10-22 후속 결정 — 현재 SIL 물리 응답 범위

사용자는 현재 모델에서 계산한 물리 응답 시한 적용을 승인했다.
[M6 physical-response-v1](../interfaces/vehicle-energy.md#physical-response-contract)의230ms는
max(토크149.5ms,제동200ms)+출력4+모델4+관측10+여유12다.
마지막 RX→검출100ms, local 보호 선택4ms와 별도다. 실제 abs(T)<=1Nm와
보호 floor1MPa를 함께 확인하며 finite rate/기존 권한·source/expiry를 유지한다.
[실제 후속 근거](../test-plan/evidence/m6_physical_response/README.md)에 따라
현재 Host quiet 차량·EV·물리 보호 기능을 한정 수용하고 OPEN01의 시한 불일치 범위를 해소한다.
위 이전100ms FAIL/분모와 OPEN02 SDK sanitizer 기능 미완료는 유지한다.
M6 전체 종료는 요구사항/TBD coverage 검토로 별도 판정하며 기존 OPEN 전체 해결을
다음 개발의 일괄 선행 조건으로 추가하지 않는다.


<a id="adr-0065"></a>

## ADR-0065: M7 시뮬레이션 기능 통합과 실시간 수용 분리

Date: 2026-10-29. Status: **사용자 승인 / 실행 결과는 현재 상태에서 별도 판정**.

CARLA fixed10ms는 실제10ms 완료 보장이 아니다. 기존 기능 주행은 동작하지만 실제 wall
연결에서는 엔진 공백으로 원천30ms가 만료됐다. 사용자는 같은 시뮬레이션 시간 기준의
연속 주행을 먼저 완성하고 실제 시간 기준 실시간 연동을 별도 검증하는 순서를 승인했다.

M7 `m7-simulation-time-v1`은 연속 정상·영상·원본 work/단일 EV·보호 Actual 정지·센서/work
누락·pause/reset·Actual-only/single writer의 기능 통합을 수용한다. Controller20ms·Zone/vECU10ms·
world10ms·영상50ms·source30ms와 expiry를 동일 simulation domain에서 유지한다.
원본 timestamp/sequence를 바꾸지 않으며 모든 native 모델·제어도 같은 시간으로 진행한다.
실제 실행 지연은 별도 성능 기록이고, Host 응답 정지는 유한 watchdog/정리로 처리한다.

M6 wall/통신/안전/모델 계약·수치·종료 판정은 유지한다. 실제 CARLA wall 정상 주행과 wall fault
후 실제 보호 제동은 **별도 OPEN**이다. 기존 FAIL을 PASS로 재분류하지 않는다. 기능 수용은
고정 Town03/V1/시험 요청 범위이며 M8 경로 추종·AI·HIL/Target/실시간 수용이 아니다.

[현재 계약](../interfaces/carla-plant-adapter.md#시뮬레이션-시간-연속-실행),
[현재 판정](../project-status.md), [보존한 wall 실패](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/README.md).

<a id="adr-0066"></a>

## ADR-0066: CARLA 파생 HV freshness 예산 분리

Date: 2026-10-29. Status: **사용자 재조정 요청에 따른 CARLA 전용 결정 / 실시간 전체 수용 별도**.

사용자가 프로젝트 진행을 불필요하게 막는 과도한 timing 조건의 재조정을 요청했다.
원래30ms는 현재 fixture의 engineering starting point이며 모든 입력에 대한 실차 한계가 아니다.
[CARLA 공식 문서](https://carla.readthedocs.io/en/0.9.16/adv_synchrony_timestep/)는 model step과
실제 처리 시간을 구분한다. 아래50ms는 공식 CARLA 보장값이 아닌 프로젝트의 예산 결정이다.
기존 wall 반복 실패는 HV 취득 지연과 별개인 oldest dependency30.010378ms에서 재현됐다.
`wall5-hv50-v1`은 HV 취득30ms와 계산 dependency50ms를 분리한다. 추가20ms는 한 Controller
주기의 계산·전달 예산이다. Wheel/Actual/명령·원래 expiry·owner2ms/4ms와 원본 시각은 유지한다.
M6 소스와 기본30ms profile은 변경하지 않으며 기존 실패를 재채점하지 않는다.

값은 새 실제 시험 전에 고정하고 경계·보호·반복 실행으로 검증한다. 부족한 다른 예산을
자동으로 늘리지 않는다. 기능 개발은 ADR-0065에 따라 계속하고 wall 안정화를 M8의
선행 조건으로 추가하지 않는다. OEM/고속·영상·장시간 적합성은 별도다.
[개정 계약과 검증 범위](../interfaces/carla-plant-adapter.md#carla-파생-hv-입력-예산-재조정),
[현재 판정](../project-status.md)을 따른다.
