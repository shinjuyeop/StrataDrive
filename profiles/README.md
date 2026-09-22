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
