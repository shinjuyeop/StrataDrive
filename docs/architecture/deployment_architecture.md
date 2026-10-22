# Deployment and compute-tier architecture

Status: 배포 경계 **DEFINED**, runtime **PLANNED**. 실행 가능한 container/systemd/network 설정은 M0에 없다.

2026-10-22 현재 Host 구현 경계: [3-process SOME/IP adapter](../icd/someip_rear_adapter.md)는
문서화한 Normal FIFO functional SIL 범위에서 Central·Front·Rear를 별도 netns/veth process로
연결한다. Central은 중앙 조정/배분/세션/RunLease, Front는 FrontZone/Steering/Brake,
Rear는 RearZone/Drive/BMS/Power의 유일한 owner다. 별도 지속 SIL 물리 process가 모델을 소유한다.
[검증 근거](../test-plan/evidence/m5_someip_rear_adapter/README.md)의 CPU1/2/7 owners,
physical3, monitors0, SDK4/5/6 배치와 제한된 부하/시간에만 해당한다. TSan 정상 관측 구간
FAIL은 별도로 보존한다. M4는 여전히 Host IO/FIFO component 한정 수용이며 전체 종료가 아니다.
DDS 진단은 정규 제어 adapter가 아니고 기존 FAIL/OPEN/CLOSED를 유지한다.
Target 배포는 PLANNED이며 Host+Jetson 한 대 내부 여러 vECU라는 원래 배포는 변경하지 않는다.

## Physical deployment

| Node | 역할 | 미결정 사항 |
| --- | --- | --- |
| Host PC | x86 Ubuntu, CARLA, road/traffic/pedestrian/vehicle plant, simulated Camera/IMU/GNSS, ScenarioRunner/OpenSCENARIO, fault/test orchestration, logging/PASS-FAIL | Ubuntu/Python/CARLA client/server/ScenarioRunner 호환 버전, GPU 사양 TBD |
| Target 대안 A | Jetson AGX Thor, 전체 Central Vehicle Compute → Zone Controller → Leaf ECU stack, Premium Compute Profile | 보드 variant, OS/JetPack/CUDA/TensorRT, power/thermal 설정 TBD |
| Target 대안 B | Jetson Orin NX, 동일 Vehicle SW Architecture, Mainstream Compute Profile | 보드 RAM variant, 보드별 software stack, power/thermal 설정 TBD |

Host와 선택한 Jetson 사이에 실제 Ethernet을 사용한다. Thor와 Orin은 함께 차량을
구성하지 않는다. 보드별 독립 실험과 동일 scenario replay로 비교한다. 같은
architecture/source revision을 목표로 하되 서로 다른 보드에 동일 binary/engine이나
동일 JetPack 버전이 호환된다고 가정하지 않는다.

## Target logical nodes

원래 Target 계획: Central의 별도 VCU/coordinator → 각각 DDS → Front Zone / Rear Zone.
Host Central↔Front/Rear SOME/IP의 제한된 FIFO 수용을 전체 Target protocol 결정으로 확대하지 않는다.
Front CAN/vCAN → Steering / aggregate Brake; Rear CAN/vCAN → Drive / BMS.
Central이 vehicle management/allocation/session과 상위 feedback 집계를 단독 소유한다.

[EV-01](../icd/ev_power_bms_design.md)은 같은 Target에 BMS 논리 Leaf를 추가한다.
차량 관리(VCU 역할)/allocation/gateway를 기능적으로 구분하며 독립 process/task와 isolation은
TBD-04/05다. Battery/power model의 실제 배치/단일 energy owner는 TBD-07에 정한다.
[ZON-01](../adr/ADR-0015-front-rear-zones.md)로 두 Zone과 후륜 구동 packaging을 채택했다.
단일 Zone component 검증 후 M4/M5에 논리 Front/Rear를 분리한다. Central–Zone protocol과 독립
통신 loss/rejoin 설정은 TBD-15이며 runtime/TC-ZON 시험은 PLANNED / NOT RUN이다.

Central Vehicle Compute/Front/Rear를 Docker network 또는 Linux network namespace + veth pair로 별도
Ethernet node처럼 구성할 계획이다. Central 내부 ADAS/VCU interface와 DDS discovery/QoS, multicast/routing, namespace
안의 CAN 접근성, feedback bridge 배치, least-privilege device/capability와 observability는
선택 후 검증한다. 단순 localhost function call로 Ethernet 경계를 대체하지 않는다.
Front/Rear에 각각 별도 CAN/vCAN 경로를 두며 process/link의 독립 중단을 주입한다.
동일 Target 자원 공유는 유지하므로 물리 전원/CPU 고장 독립성이나 failover를 주장하지 않는다.

vCAN은 CAN frame 기반 application contract 시험용이다. CAN FD의 전기적 동작,
실제 arbitration 지연, bus load/bitrate, transceiver/error confinement를 물리적으로
검증하지 않는다. 필요 지연/손실은 명시적 fault model로만 주입하고 실측 bus evidence와
혼동하지 않는다. 실제 bus가 필요한 검증은 별도 후속 범위다.

## Fair comparison protocol

1. [Reference Config](../../profiles/reference.yaml)의 M0 ODD/rate/acceptance를 유지하고
   해당 비교 단계의 workload/보드 조건 TBD-09를 먼저 고정한다.
2. 동일 scenario/seed/requirements, sensor input, model/checksum/precision, feature set,
   input resolution/rate, SW revision을 각 보드에 각각 적용한다.
3. Platform versions, board/RAM, power mode, clocks, cooling, ambient condition,
   warm-up, run duration, repetitions, background load, clock uncertainty를 기록한다.
4. Reference 결과를 수집한 뒤 Premium/Mainstream 변경을 각각 명시적으로 적용한다.
5. 최적화된 결과는 reference와 별도 표시하고 모든 공통 requirement와 정확도를 재검증한다.

측정 항목은 AI latency, camera-to-trajectory latency, FPS, CPU/GPU utilization, RAM,
power, temperature, control jitter, deadline miss다. 수집 도구, sampling rate와
pass threshold는 TBD-09 (M10/M12)이며 unavailable sensor는 0 대신 N/A + 이유로 기록한다.

Thor에서는 Premium feature 확장, Orin에서는 Mainstream resource optimization을
탐색한다. FP16 → INT8, Medium → Small, 1080p → 720p, 30 FPS → 20 FPS, optional segmentation
비활성화, temporal hidden size 축소, optional feature gating은 **후보**다.
정확도/closed-loop behavior 비용 없이 공짜 성능 개선이라고 가정하지 않는다.
목표는 순위가 아니라 각 compute budget에서 requirement를 만족하는 feature configuration이다.

## Open deployment questions

- 기본 DDS와 Zenoh 후보 비교, direct API 또는 ROS 2 기반 통합, 구현체 및 isolation 방식
- 실제 Ethernet 주소/방화벽/discovery 구성과 Host feedback transport
- Host/Target clock sync 방식과 측정 오차; real-time policy/affinity/kernel 필요성
- 공통 reference workload가 두 보드에서 실행 가능한지와 보드별 compatible stack
- CI는 Host부터 시작할지, hardware runner/배포 복구 절차를 언제 추가할지

결정 근거: [ADR-0003](../adr/ADR-0003-compute-tier-strategy.md).

미결정 배포 항목의 owner/milestone/rationale은 [TBD register](../roadmap.md#open-m0-decisions)의
TBD-04(clock/timing), TBD-05(middleware/network), TBD-07(Host/CARLA), TBD-09(board/workload),
TBD-11(toolchain/CI)에 있다. Middleware 선택 기준과 M4 비교/M5 결정 gate는
[DDS ICD](../icd/ethernet_dds_icd.md)에 정의한다. Premium/Mainstream은 같은 architecture의
각 독립 실험 profile이며 Reference config를 먼저 공통으로 측정한다.

## Host OS pilot

[Trampoline POSIX Steering 파일럿](../learning/m3_rtos_pilot.md)은 개발 Host에서 별도로 실행한다.
추가 MCU나 Jetson OS 전환은 이번 변경에 포함하지 않는다.
[ARM64 교차 빌드·RT 사전 점검](../adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)을 추가했다.
일반 ARM64 Linux 산출물과 실제 Jetson BSP/ABI·실행 지원은 구분한다. Target OS/virtual target 채택과 timing은 후속 검토다.
물리 모델과 ECU는 별도 process이고 둘 다 Host 자원을 공유한다. Hardware fault 독립성이나 실시간 보장은 주장하지 않는다.


2026-10-22 [M6 선택형 Simple Vehicle](../icd/simple_vehicle.md)는 위 persistent Host SIL
physical owner 내부에 actual 기반 차량 운동을 추가했다. ECU/command/session 소유권은 같다.
실제 wheel-speed acquisition을 Rear Drive sensor→CAN Actual→SOME/IP→Central로 연결하며
물리 state는 ECU Epoch 재가입으로 reset하지 않는다. 기존 fixed-zero M5 fixture와
`--simple-vehicle` 경로를 구분한다. Python MIL은 별도 논리 실행이며 실제 Central controller가 아니다.
