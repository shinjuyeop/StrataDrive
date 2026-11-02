# M8 배분 포화 피드백과 참조 타당성 프로토콜

2026-11-01. 이번 범위는 기존300Nm/전력/제동 해제 배분 제한의 **선택 결과**를
이전20ms PI 주기와 연결하는 anti-windup과 실행 전 관성 토크 필요조건 검사다.
배분 선택은 actuator Actual이나 새 주행 권한이 아니다. 기존 원천/expiry, 배분·하위
ECU gate, PI 계수·가속도/변화율 제한, 차량 정산을 유지한다.

`model.py`의 v1과 기존 evidence는 동결한다. 별도 `model_v2.py`는 기존 조건부 적분에
`이전 배분에서 positive propulsion이 제한됨 && 현재 error>0`이면 적분을 보류하는
조건만 추가한다. 음수 error의 적분은 기존 조건을 만족할 때 허용한다. External saturation이
false이면 v1과 동일해야 한다. 출력은 이전 integral로 계산하며 외부 제한은 다음 주기에
반영된다. 제동 측 anti-windup이나 물리 actuator 지연 보상은 이번 범위가 아니다.

Central allocation은 성공한 선택에서만 epoch/parent request sequence/selection 시각,
요청 acceleration, 요청/선택 propulsion Nm와 limited flag를 기록한다. 실패는 이를
제거한다. SpeedRequest opt-in은 정확히 이전 요청의 feedback, 같은 epoch,
이전 release 이상·현재 release 미만·30ms 이하의 selection 시각과 단조성을 확인한다.
누락·다른 parent·변조·future는 output 없이 latch된다. 첫 제어는 이전 선택이 없으므로
positive 적분을 보수적으로 보류한다. 이것은 유효한 이전 계산 이력이며 새 sensor source나
permission으로 취급하지 않는다. 기존 wheel/pose input dependency는 갱신하지 않는다.

실행 전 검사는 각 선형 ramp의 `m*r*dv/dt`가 고정 propulsion300Nm/braking1500Nm 안인지
판정한다. 기존1696kg/.355m에서10s startup501.733Nm는 서버 기동 전에 거절하고,
20s startup250.867Nm는 필요조건을 통과한다. Road load/grade/실시간 BMS derating은
고정 필요조건만으로 보장할 수 없으며 target을 실제 속도에 맞춰 변경하지 않는다.
`--propulsion-aware` opt-in으로 사용하며 기존 v1 실패 재현 경로는 유지한다.

검증은 사전 고정한다.
- Python/C++ v2 event별 출력·전체 state 오차는 기존 abs+relative1e-12.
  false feedback v1 동등성, saturation/unwind/recovery와 fault/new INIT를 포함한다.
- 합성 plant는 target1m/s,0–15s 가속도 가용량.12m/s²,이후1.5m/s²,
  저항.08*v,20ms Euler,50s다. v2 최대 integral/overshoot가 v1보다 작고 최종오차<.01m/s.
  같은 sensor replay를 C++에도 넣는다. 이는 분리된 포화 실험이며 CARLA 수용이 아니다.
- C++ selection/epoch/source/parent/permission/fault latch·전력/토크/제동 해제 제한 시험.
- 실제 CARLA는 기존 S03 v2 경로·target·모든 성능 기준을 그대로 사용한다.
  이전 배분 선택과 각 PI 적분을 원본 trace로 독립 계산한다. native/work/EV 감사도 유지한다.
  포화 입력을 누락·변조·다른 요청으로 치환하면 oracle가 거절해야 한다.
- 실제 pose-stale는 다음 tick 차단으로 판정하며 제동/HV-off 정지로 세지 않는다.

실패·성공·source/model/binary/config hash를 새 evidence에 보존한다.
