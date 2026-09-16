# Compute profile design placeholders

Status: **Planned / TBD**. YAML은 설계용 data이며 loader, schema validator, deployment
command는 미구현이다. `null`은 미결정이며 무제한, 비활성화, default 값을 뜻하지 않는다.
`baseline_profile`은 문서상의 참조이며 자동 inheritance가 구현됐다는 뜻이 아니다.

먼저 `reference.yaml`의 workload/requirement/scenario를 고정하고 Thor와 Orin에서
같은 reference를 독립 실행한다. 이후 `thor_premium.yaml`과 `orin_mainstream.yaml`을
별도 실험으로 비교한다. 후보 목록은 적용된 설정이 아니다. Model/hardware에
의존하는 engine은 별도 artifact로 관리하고 공통 model/checksum과 수치 정확도를 추적한다.

향후 resolved profile에는 모든 TBD의 값, profile hash, source commit, board software
stack, model/input settings, scenario/seed, power/thermal 및 측정 조건을 기록한다.
결과는 단순 속도 순위 대신 요구 충족과 feature trade-off로 평가한다.
[Deployment protocol](../docs/architecture/deployment_architecture.md)과
[timing template](../docs/requirements/timing_requirements.md)을 참조한다.
