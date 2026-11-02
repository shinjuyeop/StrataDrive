# 고정 경로 Pure Pursuit

M8 첫 횡방향 제어기는 `central/lateral/pure_pursuit.{hpp,cpp}`의 독립 C++
component다. 호출자는 세션 시작과20ms release를 소유한다. 경로는 초기 생성 때
고정하며 실행 중 교체하지 않는다. 이 구현은 일반 경로 계획기나 localization이 아니다.

## 좌표와 입력

`RoutePoint`와 `RoutePose`는 project world의 x/y, y-left 좌표다. Pose의 위치는
rear-axle center이며 yaw는 라디안이다. epoch, sequence와 **원천 acquisition 시각**을
받는다. CARLA adapter는 ActorSnapshot의 actor 원점을 실제 axle offset과 full rotation으로
변환한다. 부호 변환과 geometry 측정은 [실행 프로토콜](../test-plan/carla-route-protocol.md)을 따른다.

입력 누락, 다른 epoch, future/presession/30ms 초과 source, sequence/source 중복·회귀,
missed release, 비유한 입력,40km/h 초과·음수 speed는 출력을 거절하고 fault를 latch한다.
새로운 epoch의 명시적 `start_session`만 상태를 초기화한다.

## 계산과 연결

rear-axle를 가장 가까운 경로 segment에 투영한다. 이전 progress−2m부터+20m까지만
탐색하며 초기 progress≤2m·횡거리≤0.3m·heading≤3deg를 요구한다. 실행 중 거리>1.5m,
heading>0.5rad 또는 progress가0.5m보다 뒤로 가면 거절한다.

Lookahead는 max(4m,1.2s×speed)다. 해당 경로점을 차량 좌표로 바꿔
`curvature = 2*y_local / (dx²+dy²)`를 얻고, wheelbase로 bicycle angle을 계산한다.
angle±0.3rad와1rad/s slew를 적용한 뒤 다시 curvature로 반환한다.
미세한 경로 polyline 오차를 포함한 analytical circle·좌우 부호와 kinematic 추종 시험을 둔다.

CARLA functional fixture는 기존 SpeedPI와 같은 Controller release에서 계산한다.
결과는 기존 `VehicleRequest.curvature_inv_m`에 넣고 ControlAllocation→Steering owner→
Actual→native/server admission→NoDrive 경로를 따른다. 조향 actuator를 직접 쓰지 않는다.
요청 source는 계산 시각이고, input dependency는 wheel/pose 원천 중 가장 오래된 시각이다.
기존 command context의 oldest/expiry와 PI source60ms 상한을 유지한다.

## 판정 범위

[고정 Town04 곡선 프로토콜](../test-plan/carla-route-protocol.md)에 따라 원본 자세에서
횡오차와 heading을 독립 재계산하고, 원본 wheel·body speed와 모든 child 명령의 lineage를
검사한다. 이 판정은 M8 종방향 Python/C++ 모델 동등성 시험과 별개다.
S01/S03의 고정 fixture는 [별도 프로토콜](../test-plan/carla-reference-protocol.md)을 따른다.
S03 v2는 현재 검증된 rear-axle projection이230m/380m에 처음 도달하는20ms release에서
20km/h/정지 요청을 latch한다. 연속 target은 각각6s/8s에 걸쳐 전환한다.
요청값·event elapsed time·계산 target을 따로 기록하며 독립 검증기는 원본 pose로
event를 재계산한다. 초기 가속은 기존300Nm 구동 상한을 고려한20s다.
이 참조 생성기는 시험 fixture다. 인지 기반 localization, Planner와 wall 실시간 성능,
하위 구동 포화를 반영하는 anti-windup은 추가 작업이 필요하다.
