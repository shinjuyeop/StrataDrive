# M8 S01·S03 고정 경로 검증 프로토콜

실제 실행 전에 고정한 Town06_Opt SIL fixture다. S02의 source/expiry,
Pure Pursuit, PI, NoDrive vehicle320, solver work/single EV, eight-role
INIT/RunLease/admission 계약은 [곡선 프로토콜](carla-route-protocol.md)과 같다.
ActorSnapshot localization과 미리 고정한 경로·속도 참조를 사용한다.
Planner/인지/localization 구현, 전체 Reference 시나리오, wall 수용,
보호 정지의 실제 제동 및 HV-off NormalStop은 별도다.

| 항목 | S01 | S03 |
|---|---|---|
| 파일 | `m8_straight30_v1.json` | `m8_combined_v1.json` |
| SHA256 | `d4a00933dacfabc7574a1737b2e602b57fed19eb16f5ec8b0a900af61c84e533` | `9403807df84667d8f4364e8e0a1e5bdce86b6f302f0da053cfb999e7068b45d5` |
| 시작 | road40 lane−7 s50 | road40 lane−7 s240 |
| 점 수 / 길이 | 721 / 360.000006m | 679 / 358.113535m |
| 곡률 상한 | 0.00001/m | 0.0225/m |
| 완료 진행거리 | 300m | 345m |
| physics 구간 | 6000×10ms | 8000×10ms |

모든 점은 non-junction Driving lane, 폭≥3m다. S03은 road40 직선,
road71 곡선, road6 lane7 직선으로 이어진다. 곡률≥0.001/m 구간은
진행거리 약230.50–330.61m다. 마지막 점은 junction 진입 전이다.
SDK next(0.5)는 도로 기준 거리이므로 외측 lane의 실제 점 간 거리는
S03에서 0.48–0.75m를 허용한다. S01·S02의 기존 간격 조건은 유지한다.
경로 파일은 SHA256까지 고정하며 시작 후 변경하지 않는다.

S01은 최초 정상 control release를 t=0으로 0→30km/h 20s,
30 유지20s, 30→0 15s다. plateau는 [25,35)s, 정지는 [57,59)s다.
S03은 0→30km/h 10s, 첫 plateau [15,25)s다. 매20ms 제어에서 현재
검증된 pose의 rear-axle projection이 처음180m 이상이면 감속 요청을 latch한다.
그 시각 ts부터30→20km/h를6s에 걸쳐 선형 전환한다. 두 번째 plateau는
[ts+11,ts+21)s다. 처음330m 이상인 제어 시각 te에서 정지를 요청하고
20→0을8s에 걸쳐 전환한다. 정지 평가는 [te+10,te+12)s다.
요청값30/20/0과 연속 제어 목표를 별도로 기록한다. 감속 요청은25s 이후,
정지 요청은 두 번째 plateau 이후여야 한다. 감속 요청 시각은 관측/평가 결과에
맞춰 이동시키지 않는다.80000ms native horizon은 S03에만 명시적으로 허용한다.

각10s plateau는100Hz body1000개,50Hz original decoded control-wheel500개,
20Hz body-state200개를 모두 평가한다. 각2s 정지 구간은 각각200/100/40개다.
최대 plateau/정지 오차≤1km/h, 양수 연속 목표 대비 동시각 overspeed≤10%를
세 stream 모두 만족해야 한다. Ramp 오차도 보고한다. S03 첫 plateau의
모든20Hz 표본은 직선(곡률≤0.00001/m), 두 번째는 곡선(≥0.001/m)이어야 한다.
첫 곡선 진입 시 body 속도는20±1km/h여야 한다. 완료 표본은 최종 직선이어야 한다.

최초 정상 제어부터 완료까지 원본 snapshot을5frame마다20Hz로 평가하며
누락/보간/선별 없이 rear-axle 위치와 경로 projection을 독립 재계산한다.
nearest-rank P95 횡오차≤0.3m, heading≤3deg. S01 전 구간은 직선이어야 한다.
완료 후 최종 wheel0과 마지막 work settlement까지 확인한다.
독립 검증기는 기록된 marker 시각을 신뢰하지 않고 원본 pose projection과
제어 release로 재계산한다. source/frame 위조, 요청 누락·조기전환·시각 이동,
계산 목표 변경, geometry/trace 손상은 거절해야 한다.

모든 실패·성공 실행의 raw trace, 실행 source/binary/config hash, lifecycle과
서버 종료를 보존한다. Town06 cold asset 준비에는 명시적 route startup600s를
사용한다. 기존 RPC/제어 age/종료 제한과 성능 임계값은 완화하지 않는다.

## S03 v2 — 구동 상한에 맞춘 출발과 경로 개정

2026-10-30, `S03-01`의 v1 전체 주행·정산·정리는 완료했으나 첫 plateau에서
body 최대오차5.32610km/h, wheel4.97676km/h로 **FAIL**이었다. 원본과 v1 정의는
그대로 보존한다. 10s startup의0.83333m/s²는1696kg×0.355m 기준501.733Nm를
요구해 기존 propulsion300Nm 상한을 넘는다. 실제 work 감사에서도 최대300Nm를
확인했다. v1의 감속·곡선 plateau 통과가 첫 plateau 실패를 상쇄하지 않는다.

v2는 별도 schema/file/header로 구분하며 v1 결과를 재해석하지 않는다.
S01에서 검증한20s startup(관성 토크250.867Nm)을 사용하고 road40 lane−7의 시작점을
s240에서s190으로50m 앞당겨 필요한 직선 거리와 두 plateau를 확보한다.
PI 계수·구동 상한·원천 age·감속6s·정지8s·오차/overspeed/P95 기준은 유지한다.

- `m8_combined_v2.json`, schema`m8-reference-v2`, native header`PROFILE S03v2`.
- SHA256 `696f12a9bfc128958f73f8d0da17f1a7ad265dc5e27c611760f023cdfd387638`.
- 779점,408.113538m. 곡선 약280.50–380.61m, 완료395m,8000×10ms 그대로다.
- 최초 target0→30은20s, 첫 plateau[25,35)s. 감속 marker230m, 정지 marker380m.
- 두 번째 plateau[ts+11,ts+21)s, 정지[te+10,te+12)s는 v1과 같다.
  감속 요청은35s 이후, 정지는 두 번째 plateau 이후여야 한다.
- 새 경로와 이 기준은 v2 실제 실행 전에 고정한다. v1 FAIL, v2 판정, 두 실행의
  source/binary/route hash를 구별한다. 이는 fixture 개정이며 일반 Planner나
  actuator 포화에 대한 제어기 anti-windup 문제를 해결했다는 주장은 아니다.
