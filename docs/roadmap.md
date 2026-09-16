# Milestone roadmap

Status: **M0 — Architecture & Requirement Baseline**, bootstrap/design draft.
M1–M13은 모두 Planned이며 이번 요청에서 착수하지 않는다. 아래 acceptance는 후보로,
각 milestone 시작 전에 학습자가 requirement/contract와 함께 확정한다.

| Milestone | Planned focus | Proposed acceptance evidence |
| --- | --- | --- |
| M0 | Architecture / Requirement / ICD Baseline | 문서/구조/traceability 검토, 주요 TBD 결정, 학습자의 설명과 baseline 승인 |
| M1 | DBC + vCAN | Frame/signal 계약, CRC/counter golden vectors, vCAN encoding/decoding |
| M2 | Steering / Brake / Drive vECU | 주기 task/queue/state/dynamics와 local timeout/fault의 작은 테스트 |
| M3 | Real-Time Timing & Scheduling Measurement | execution/period/jitter/tails/miss 측정, clock/overhead 조건 기록 |
| M4 | Virtual Zone Controller | validation/allocation/local safety, CAN feedback loss와 rejoin |
| M5 | Central Compute + DDS | 논리 Ethernet 분리, DDS command/status, QoS/freshness 시험 |
| M6 | Simple Vehicle Plant | Zone/vECU actual response를 통과한 closed-loop와 mapping 검증 |
| M7 | CARLA Integration | Host–Target 실제 Ethernet, single ego writer, feedback-driven CARLA motion |
| M8 | Classical Autonomous Driving | route/waypoint, Pure Pursuit 또는 Stanley, longitudinal PID의 기준 scenario |
| M9 | Fault / Diagnostics / DTC | Fault Event/DTC/state/local action/plant response를 연결한 fault regression |
| M10 | Physical AI Perception | pretrained detection/segmentation/tracking, TensorRT 통합과 accuracy/latency 기준 |
| M11 | Learned Temporal Planner | 0.5–1초 history, trajectory/speed/risk 출력, Safety/Classical fallback 시험 |
| M12 | Thor vs Orin Compute-Tier Optimization | 동일 Reference 비교 후 tier별 구성 최적화, 공통 requirement 재검증 |
| M13 | Final SIL / V&V / Regression | scenario/fault/performance regression, traceability 결과와 한계 공개 |

Fault architecture는 M0부터 다루며 local fault behavior는 M2/M4 등의 component와
함께 설계한다. Fault handling을 M9까지 미룬다는 뜻이 아니다. 각 단계에서
[학습 절차](learning/README.md)와 [quality policy](quality_policy.md)를 적용한다.

## Open M0 Decisions

모든 항목의 owner는 학습자(project owner), 상태는 OPEN / TBD다. 파일 생성만으로
이 설계 값이 승인된 것으로 간주하지 않는다.

| Priority | Decision | Needed before / how to decide |
| --- | --- | --- |
| 1 | 초기 ODD, 최소 scenario, speed/accuracy/deviation acceptance | Requirement baseline; 간단한 route와 fault scenario를 문장으로 정의 |
| 2 | Vehicle command / actuator feedback 물리량, unit, frame, CARLA mapping | M1/M2 contract; steering/brake/drive 책임과 dynamics 중복 검토 |
| 3 | task periods, clock domains, simulation tick/multirate, latency/timeout budget | M1–M3; 100 ms 예시를 budget으로 분해하고 측정 endpoint 결정 |
| 4 | actuator별 DEGRADED/FAIL_SAFE/RECOVERY와 startup 동작 | M1/M2; actuator 상실 시 가능한 동작과 복귀 조건 정의 |
| 5 | CAN ID/DLC/signal, CRC/alive counter, queue/restart policy | M1; DBC와 golden vectors 계약부터 검토 |
| 6 | direct DDS vs ROS 2, vendor/QoS, Docker vs netns/veth, Host bridge transport | M4/M5; discovery, latency, 구현/학습 비용 비교 |
| 7 | CARLA 0.9.16 exact build, Ubuntu/Python/ScenarioRunner compatibility | M7 전; 공식 호환 정보와 소규모 재현 확인, M0 설치 없음 |
| 8 | Reference workload, board variants/stack/power/cooling, 측정 protocol | M10/M12 전; 동일 model/input/feature/requirement와 보드별 조건 기록 |
| 9 | C++ standard/toolchain, CI 범위, small model size/license policy | 첫 구현/fixture 추가 전; 작고 검토 가능한 선택 |

M0 완료 조건은 파일 생성만이 아니다. 주요 경계와 첫 구현에 필요한 계약/requirement의
TBD를 해결하거나, 보류 이유/담당/결정할 milestone을 기록해야 한다. 학습자가
architecture와 trade-off를 설명하고 baseline을 승인한 뒤 다음 단계로 진행한다.
