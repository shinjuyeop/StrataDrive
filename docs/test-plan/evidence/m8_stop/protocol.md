# M8 CARLA 주행 중 보호와 NormalStop 프로토콜

2026-11-01. 기존 Town03 V1, NoDrive320, 단일 EV, 원래 simulation-time8-role
경로에서 각각4000 ticks를 실행한다. 기존0→10km/h10s·plateau profile을 사용하고
첫 SpeedPI release 이후15s에 아래 사건을 고정한다. PI/배분/actuator/감시 수치는 유지한다.

- `normal-stop`:20ms마다 새로운 원본 NormalStopRequest를 발급하고 일반 PI·Enable root를
  중단한다. 기존1m/s² 감속·제동 timeout5s·정지 확인60ms·shutdown timeout2s를 사용한다.
  원본 StopLease→LeafRequest→accepted LeafResult→fresh stationary Actual 인계를 검증한다.
  기존8-role release/RunLease와 whole-interval freshness는 계속 필요하다.
- `input-loss`:동일 시각에 Central SpeedRequest로 전달하는 현재 Drive Actual만 누락한다.
  실제 wheel/actuator acquisition과 다른 ECU traffic은 계속한다. SpeedRequest의 Feedback
  fault와 기존 local protection을 선택한다. 명령 만료 timeout 또는 전체 통신 단절 시험이 아니다.
  이미 유효기간이 부족한 정상 Actual로 다음 물리 구간을 진행하지 않는다.

NormalStop의 terminal Actual은 NormalPath/Init,0Nm, wheel≤.01rad/s,
pressure≥100kPa여야 한다. 기존 command의 causal sequence를 유지하며 별도 원본 stop
lease와 세 하위 ECU의 실제 선택 ACK를 확인한다. 새로운 packet을 합성하거나 ACK를
원래 CAN Actual의 causal sequence로 대체하지 않는다. 만료/오류/lease 변조/정상 복귀를 거절한다.
새 server admission은 opt-in functional 경로에 한정하고 wall 경로는 확대하지 않는다.

사전 수용 기준:
- 사건 시점 차체 속도9–11km/h, 직전 실제 속도 폐루프 동작 확인.
- 정상 정지는 기존 phase deadline 안에 Complete·PowerOffConfirmed, 원본 PowerStatus의
  Off·세 접촉기 open·bus≤30V와 actual0Nm·brake hold를 확인한다.
- 입력 누락은 해당20ms job에서 invalid/fault를 기록하고 새 PI 요청을 발급하지 않는다.
  torque0과 brake≥1MPa의 원본 acquisition은 보호 선택 후230ms 이내, receipt 관측은260ms 이내.
- 두 실행 모두 사건 후5s 이내 body≤.001m/s 및 네 solver wheel0 확인,
  마지막1초 동일 pose(변위≤1mm)와 정지 유지. 물리를 강제로 정지시키거나 sensor 값을 고치지 않는다.
- 모든4000구간의 원본 work·EV 정산, 실제 actuator source/expiry·RunLease/StopLease
  감사, 무중복 physics/정산, 서버 종료130을 확인한다. NormalStop만 HV-off 완료로 센다.
- C++ 원본 인계/ACK 손상·만료·고장 unit, 독립 raw-wire 감사의 손상 거부를 포함한다.
  기존 정상·보호/원천 검사와 unit/logical 회귀를 유지한다.

첫 command withholding 합성 시험은 다음 interval의 정상 command expiry 부족으로
거절되었다. 이를 기존 gate를 늘려 통과시키지 않고 scope를 위 input-loss로 명확히
분리한다. 이전/실패 실행은 새 evidence에 보존한다. 전체 Reference/M8,30km/h stop,
wall/Target, 실제 hardware 기능 안전 수용은 별도다.
