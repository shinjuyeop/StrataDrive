# M8 별도30km/h NormalStop 사전 프로토콜

2026-11-02. `m8_stop30_v1.json`/`normal-stop30-a1-t10-v1`을 별도 고정 profile로 사용한다.
Town06 S01과 동일한721점 직선·OpenDRIVE/geometry, 원본 Pure Pursuit+v1 SpeedPI,
20s의0→30km/h ramp, 첫 PI release+35s NormalStop 요청을 사용한다.6000 ticks/60s다.
정지 요청 후 새 PI는 발급하지 않고 기존 owner NormalStopRequest를20ms마다 갱신한다.
감속1m/s²·제동10s·확인60ms·shutdown2s를 coordinator 생성 시 명시적으로 주입한다.
기존 default/저속1m/s²·5s는 유지한다. 프로파일 hash와 실제 적용한 config를 기록한다.

사전 수용 기준:
- frozen route/profile hash, 원본 map/geometry/pose·wheel/CAN source와 시간 연결.
- 첫35s의1750 PI release 및 Pure Pursuit 계산을 독립 구현과 대조한다.
- plateau[25,35)s의 원본 body1000/wheel500 표본, 각각 최대 속도 오차≤.5km/h.
- 정지 요청 시 body29–31km/h. 고정 직선에서 제어 시작부터 요청 후10s까지20Hz 횡오차 P95≤.3m,
  heading P95≤3deg. 정지 후 rear-axle progress240–270m;300m S01 완료로 세지 않는다.
- 요청 후10s 이내 body≤.001m/s·네 solver wheel0의 연속1초 정지 및 StopLease/ACK 인계.
- 원본 handoff ACK→PowerDown 후2s 이내 Complete·PowerOffConfirmed,
  원본 PowerStatus Off·세 접촉기 open·bus≤30V. 요청 후 합계12s 이내.
- stationary terminal Actual0Nm·brake hold·original causal,8-role RunLease와 원본
  StopLease/ACK·whole-interval freshness/expiry를 유지한다. 마지막1초 pose drift≤1mm.
- 모든6000 physics/6000 단일 EV 정산과 native/work 독립 감사·손상 거부·서버exit130.
- 기본5s의30km/h 이상 입력 BrakingTimeout, 명시적10s 후보의 이상 입력 handoff를
  C++로 비교한다. 기존 저속 두 실행의 native JSON 전체 replay 동등성을 확인한다.

본 실행은 nominal30km/h 고정 fixture의 기능 검사다.30km/h fault matrix,
ACK/전체 통신 손실, Planner/localization,전체 Reference/M8,wall/Target 수용은 별도다.
실패 시 원본과 사전 기준을 보존하고 gate·평가 window를 사후 완화하지 않는다.
