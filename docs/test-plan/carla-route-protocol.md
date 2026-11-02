# M8 곡선 30km/h 첫 연결 프로토콜

실제 실행 전 고정한 S02 후보 한 개의 simulation-time 검증이다. S01 직선,
S03 속도 전환 복합 경로, Planner/인지/localization 구현, wall 수용은 별도다.

- `scenarios/m8_curve30_v1.json`: Town04_Opt road6 lane-1에서 시작한 단일
  non-junction successor 경로721점. OpenDRIVE longitudinal parameter0.5m 간격이며
  곡선의 lane offset 때문에 실제 점 간 거리는0.48–0.53m이다. 폭≥3m,
  곡률≤0.008/m, completion rear-axle progress300m. map/경로 hash를 보존한다.
- 기존 MKZ2020 NoDrive vehicle320, solver work/single EV, eight-role INIT/RunLease,
  native/server admission, source/expiry 계약을 유지한다. Allocation은 실제
  mass1696kg, radius0.355m, wheelbase2.860470886230469m를 명시한다.
- ActorSnapshot은 SIL localization fixture다. actor/body 원점을 rear-axle로
  취급하지 않는다. 실제 rest axle offset(-1.3886322021484376,
  7.6293945e-8,0.3595409393310547)m를 full rotation으로 변환하고 live geometry와
  1mm 이내 일치시킨다. UE y/yaw 부호를 반전해 project left-positive로 바꾼다.
  Spawn 뒤 bind 전 초기 tick 한 번으로 실제 actor snapshot을 확보한다.
- POSE actor/epoch/frame/source는 WHEEL snapshot과 정확히 같아야 한다.
  native job은 future acquisition을 소비하지 않는다. 제어 입력 age≤30ms,
  pose sequence/source 단조 증가,20ms release. 결함은 latch된다.
  request source는 계산 release, input source는 wheel/pose 중 가장 오래된 원천이며
  input expiry는 source+60ms+1ns. 기존 child context에 보존한다.
- Pure Pursuit: nearest segment의 rear-axle projection, lookahead=max(4m,1.2s×v),
  curvature=2*y_local/distance². bicycle angle±0.3rad, slew1rad/s.
  초기 횡오차≤0.3m·heading≤3deg, 이후 거리≤1.5m·heading≤0.5rad를 요구한다.
- 기존 PI 상수 유지. 최초 정상 control release를 원점으로0→30km/h20s,
  30 유지20s,30→0 15s,0 유지.6000×10ms physics와 마지막 work settlement.
- 속도: [25,35)s 곡선 plateau 전체10s에서 최대오차≤1km/h, [57,59)s
  정지오차≤1km/h, 양수 목표 대비 동시각 overspeed≤10%(시작·감속 포함).
  body forward와 original decoded wheel을 별도 판정한다.
  Baseline20Hz state 값도 별도 보고한다.100Hz body와50Hz control-wheel의 모든 원본
  sample은 더 조밀한 보조 판정이며 동일 임계값을 만족해야 한다. Ramp 최대 절대오차도 보고한다.
- 횡/heading: 최초 control부터 completion300m까지 20Hz, 최초 binding frame을
  기준으로5frame마다 sampling. startup/ramp 포함, 누락/보간/선별 금지.
  원본 snapshot에서 rear-axle와 nearest segment를 독립 재계산한다.
  nearest-rank ceil(0.95N) P95: 횡오차≤0.3m, heading≤3deg.
  plateau의 모든 표본은 곡률≥0.001/m 구간이어야 한다.
- pose-stale 결함은200번째 observation의 실제 pose source만10ms 과거로 바꾼다.
  frame/source 불일치로 다음 physics advance 없이 거절해야 한다. 실제 제동 완료나
  HV-off NormalStop 수용으로 표시하지 않는다.
- 원본 trace, 실행 source/binary/config hash, 실패와 정리 결과를 보존한다.
  제어 성능 실패를 실행 완료로 덮지 않으며 결과 후 임계값을 완화하지 않는다.

첫 실행은 Town04 초기 shader/texture/mesh 생성 중 기존180s readiness 제한을
초과했다. 차량 생성·bind·주행 전 실패이며 SIGINT30s 뒤 SIGKILL 종료−9 기록을
유지한다. 후속 실행은 route 전용 명시 옵션 `--route-startup-seconds 600`으로
준비 시간만 늘린다. 주행·RPC·source·종료 제한과 성능 임계값은 변경하지 않는다.

첫6000구간 실행은 주행을 마쳤지만 원래 rendering 설정 복원 중 UE distance-field/GPUScene
SIGSEGV로 전체 FAIL이었다. 독립 work 감사에서도 observation2102에서 구간 에너지
차이1.3234e-11J가 기존1e-11J 경계를 넘었다. 누적65,536J 이상에서 두 누적값을 빼
구간량을 기록하는 audit의 정밀도 손실을 별도150kJ 단위시험으로 재현했다.
후속 binary는 이미 EV step에 전달한 원래 solver 구간 적분량을 audit에 직접 기록한다.
누적 EV 계산·정산·balance·추종 수치·감사 허용오차는 그대로며 실패 원본을 보존한다.
