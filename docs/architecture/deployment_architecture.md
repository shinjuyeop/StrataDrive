# Deployment and compute-tier architecture

Status: **Planned**, 실행 가능한 container/systemd/network 설정은 M0에 없다.

## Physical deployment

| Node | 역할 | 미결정 사항 |
| --- | --- | --- |
| Host PC | x86 Ubuntu, CARLA, road/traffic/pedestrian/vehicle plant, simulated Camera/IMU/GNSS, ScenarioRunner/OpenSCENARIO, fault/test orchestration, logging/PASS-FAIL | Ubuntu/Python/CARLA client/server/ScenarioRunner 호환 버전, GPU 사양 TBD |
| Target alternative A | Jetson AGX Thor, 전체 Central → Zone → Leaf stack, Premium Compute Profile | board variant, OS/JetPack/CUDA/TensorRT, power/thermal setup TBD |
| Target alternative B | Jetson Orin NX, 동일 Vehicle SW Architecture, Mainstream Compute Profile | board RAM variant, board-specific software stack, power/thermal setup TBD |

Host와 선택한 Jetson 사이에 실제 Ethernet을 사용한다. Thor와 Orin은 함께 차량을
구성하지 않는다. 보드별 독립 실험과 동일 scenario replay로 비교한다. 같은
architecture/source revision을 목표로 하되 서로 다른 보드에 동일 binary/engine이나
동일 JetPack 버전이 호환된다고 가정하지 않는다.

## Target logical nodes

Central Vehicle Compute → Virtual Ethernet / DDS → Virtual Zone Controller
→ SocketCAN / vCAN → Steering / Brake / Drive vECU.

Central/Zone을 Docker network 또는 Linux network namespace + veth pair로 별도
Ethernet node처럼 구성할 계획이다. DDS discovery/QoS, multicast/routing, namespace
안의 CAN 접근성, feedback bridge 배치, least-privilege device/capability와 observability는
선택 후 검증한다. 단순 localhost function call로 Ethernet 경계를 대체하지 않는다.

vCAN은 CAN frame 기반 application contract 시험용이다. CAN FD electrical behavior,
실제 arbitration 지연, bus load/bitrate, transceiver/error confinement를 물리적으로
검증하지 않는다. 필요 지연/손실은 명시적 fault model로만 주입하고 실측 bus evidence와
혼동하지 않는다. [Linux SocketCAN 문서](https://docs.kernel.org/networking/can.html)를 참조한다.

## Fair comparison protocol

1. [Reference Config](../../profiles/reference.yaml)의 TBD를 먼저 고정한다.
2. 동일 scenario/seed/requirements, sensor input, model/checksum/precision, feature set,
   input resolution/rate, SW revision을 각 보드에 각각 적용한다.
3. Platform versions, board/RAM, power mode, clocks, cooling, ambient condition,
   warm-up, run duration, repetitions, background load, clock uncertainty를 기록한다.
4. Reference 결과를 수집한 뒤 Premium/Mainstream 변경을 각각 명시적으로 적용한다.
5. 최적화된 결과는 reference와 별도 표시하고 모든 공통 requirement와 정확도를 재검증한다.

Metric: AI latency, Camera-to-trajectory latency, FPS, CPU/GPU utilization, RAM,
power, temperature, control jitter, deadline miss. 수집 도구, sampling rate와
pass threshold는 TBD이며 unavailable sensor는 0 대신 N/A + 이유로 기록한다.

Thor에서는 Premium feature 확장, Orin에서는 Mainstream resource optimization을
탐색한다. FP16 → INT8, Medium → Small, 1080p → 720p, 30 FPS → 20 FPS, segmentation
optional disable, temporal hidden size reduction, optional feature gating은 **후보**다.
정확도/closed-loop behavior 비용 없이 공짜 성능 개선이라고 가정하지 않는다.
목표는 순위가 아니라 각 compute budget에서 requirement를 만족하는 feature configuration이다.

## Open deployment questions

- direct DDS 또는 ROS 2 기반 통합, DDS vendor 및 isolation 방식
- 실제 Ethernet 주소/방화벽/discovery 구성과 Host feedback transport
- Host/Target clock sync 방식과 측정 오차; real-time policy/affinity/kernel 필요성
- 공통 reference workload가 두 보드에서 실행 가능한지와 보드별 compatible stack
- CI는 Host부터 시작할지, hardware runner/배포 복구 절차를 언제 추가할지

결정 근거: [ADR-0003](../adr/ADR-0003-compute-tier-strategy.md).
