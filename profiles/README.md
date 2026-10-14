# Compute profile design baseline

Status: Reference 계약 **DEFINED**, tier별 override **PLANNED / TBD-09**.
YAML은 설계용 data이며 loader, schema validator, deployment
command는 미구현이다. `null`은 미결정이며 무제한, 비활성화, default 값을 뜻하지 않는다.
`baseline_profile`은 문서상의 참조이며 자동 inheritance가 구현됐다는 뜻이 아니다.

`reference.yaml`의 ODD/scenario/수치 acceptance/logical rate/state는 **Reference Baseline v0.1**로
정의했다. 값은 engineering starting point이며 실측이나 양산차 기준이 아니다. 먼저 future AI
workload와 보드 조건의 TBD를 고정하고 Thor와 Orin에서
같은 reference를 독립 실행한다. 이후 `thor_premium.yaml`과 `orin_mainstream.yaml`을
별도 실험으로 비교한다. 후보 목록은 적용된 설정이 아니다. Model/hardware에
의존하는 engine은 별도 artifact로 관리하고 공통 model/checksum과 수치 정확도를 추적한다.

2026-10-13 [RG-01 회생제동 확장](../docs/icd/regenerative_braking_design.md)을 현재 설계에
추가했다. YAML의 `design_extensions`는 M0 v0.1 이후의 requirement revision을 구분한다.
Drive timeout은 이전 양·음수 demand를 무효화하는 zero motor torque target으로 개정했고,
`regenerative_braking`에 공통 책임/부호/에너지 단위와 미결정 모델 parameter를 기록했다.
Thor/Orin 공통 reference에 적용할 설계이며 runtime loader/회생 구현/검증 완료가 아니다.

[EV-01](../docs/icd/ev_power_bms_design.md)을 v0.3 requirement extension으로 추가했다.
[ZON-01 v0.5](../docs/adr/ADR-0021-central-coordination-and-parallel-zones.md)은 v0.5 requirement revision이다.
`architecture`는 최종 Front/Rear 두 Zone과 단일 Zone component 검증 단계를 구분한다.
후륜 구동 packaging에서 Central이 차량 관리·배분·session·피드백 집계를 소유하고 Rear는 Drive/BMS를 연결한다.
Central–Zone schema/QoS/clock/rejoin은 TBD-15이며 runtime switch나 배포 구현이 아니다.
`ev_power_bms`의 lifecycle·부호·단위는 설계 의미이며 parameter는 TBD-12/13/14다.
2026-10-14 [BMS wire 초안](../docs/icd/bms_frame_draft.md)에서 BMS control/limit 50 Hz,
power actual/permission 100 Hz, battery 관측 10 Hz를 제안했다. YAML도 이 논리 설계 값을 담는다.
`wire_draft`의 50 ms source/70 ms dependency/80 ms timeout은 후속 측정 대상 시작값이다.
Drive 보조 source/input age config를 분리·시험했다. 기본 30 ms를 유지하고 EV capability input
70 ms는 명시적 opt-in이다. EV codec/receiver와 local vCAN 36개 case를 검사했으며
실제 model/Zone task·cross-node rate/timeout 보장으로 확대하지 않는다.
Trusted coordinator/startup/cross-node budget은 TBD다. 로컬 모델의 셀 전압·온도 극값 입력은
범위로 정했고 threshold/dwell은 TBD-13이다. [BMS 실행 안내](../docs/learning/m1_bms_codec.md)를 참조한다.

`m1_local_can_fixture`는 [영속 Epoch/queue 기술 검사](../docs/learning/m1_session_queue.md)의 설정이다.
Capacity 32/ingress·dispatch 8/polling sleep 1 ms는 local fixture 값이다. 운영 store 경로와
실제 Central coordinator/Zone DDS INIT protocol은 후속이며 이 YAML이 runtime loader나 Target timing 보장은 아니다.

`m2_steering_fixture`는 [첫 조향 응답 모델](../docs/learning/m2_steering_model.md)의 시험 설정이다.
Command/model 각도 범위, rate/delay, control gap과 source-loss hold를 기록한다.
C++ fixture와 값이 일치하지만 YAML loader는 없으며 OEM calibration은 TBD-02/03이다.

`m2_brake_fixture`는 [첫 Brake 압력 모델](../docs/learning/m2_brake_model.md)의 설정이다.
정상 delay/rise/fall과 물리 한계, loss 시 max(actual, floor) ramp를 기록한다.
차량 안전 제동 calibration/ABS/pressure→wheel torque는 TBD-02/03/06의 후속 작업이다.

향후 resolved profile에는 모든 TBD의 값, profile hash, source commit, board software
stack, model/input settings, scenario/seed, power/thermal 및 측정 조건을 기록한다.
결과는 단순 속도 순위 대신 요구 충족과 feature trade-off로 평가한다.
[Deployment protocol](../docs/architecture/deployment_architecture.md)과
[timing contract](../docs/requirements/timing_requirements.md)을 참조한다.

각 `null`의 owner/rationale/결정 milestone은 [TBD register](../docs/roadmap.md#open-m0-decisions)에
있다. Reference의 wire/actuator/timing/mapping TBD는 해당 comment ID에 귀속된다.
Tier profile의 모든 `null`과 candidate 선택은 TBD-09(M5 stack, M10 workload, M12 비교)다. `acceptance_thresholds`
override는 공통 SYS requirement를 완화하는 필드가 아니며 추가 compute/resource 목표를
결정할 자리다. 공통 기준 변경은 requirement revision이 필요하다.

20 Hz camera/sensor baseline과 30→20 FPS optimization 후보는 다른 개념이다. 후자는
향후 workload에서 30 FPS를 선택한 경우의 후보일 뿐 현재 Reference 값을 30으로 뜻하지
않는다. 숫자를 바꾸면 요구사항/시나리오/ICD와 함께 revision/rationale을 기록한다.
