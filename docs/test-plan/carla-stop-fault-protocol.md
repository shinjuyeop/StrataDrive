# M8 정지 인계 후 보호 전환과30km/h 계약 검토

2026-11-02. 실행 전 고정 기준. 기존 Town03 약10km/h/40s/4000ticks,
NoDrive320·원본 단일 EV·8-role simulation 경로를 사용한다.

`--speed-loop --speed-terminal stop-protection`은 기존 첫 PI release+15s에
NormalStop을 요청한다. 원본 세 ECU ACK로 Central이 처음 PowerDown에 들어간
시각을 H로 기록하고 H+100ms에 기존 local protection을8개 participant 모두에
선택한다. 이는 명시적인 SIL 안전 요청 주입이다. ACK 소실이나 실제 하드웨어 고장을
검출했다고 세지 않는다. 다른 ECU/acquisition과 물리/EV 정산은 계속한다.

- 주행 사건 시9–11km/h, PI750 releases의 원본 입력/식 일치.
- 주입 전에 원본 StopLease/accepted ACK로 실제 hold 물리 구간이 있어야 한다.
- H는 최초 PowerDown 관측으로 확인하며 주입은 정확히 H+100ms다.
- 보호 선택은 마지막 수용 hold보다 뒤, 동일 released session의8-role mask255,
  normal credit0, 원래 LocalProtection Actual/source로 입증한다.
- source/whole-interval age·wheel freshness·exclusive expiry는 기존 그대로다.
  과거 hold proof가 export에 남아 있어도 보호 선택의 근거로 사용하지 않는다.
- 주입 후 torque0·brake≥1MPa acquisition≤230ms, 관측≤260ms.
- 주입 후 normal/StopLease authority 재개를 거절한다. 잘못된 보호 시각/role mask/
  credit/session, 누락·거절 ACK와 만료 stop authority를 거절한다.
- 사건 후5s 이내 body≤.001m/s·네 solver wheel0의 연속1초 정지, 마지막1초 pose
  drift≤1mm. 주입 전후 정지 유지도 확인한다. HV-off Complete로 판정하지 않는다.
- 실제4000 physics/4000 EV 정산, original native/work/EV 독립 감사와 서버exit130.
- 기존 normal-stop/input-loss 원본4001개씩을 최종 native에 재생하여 JSON 전체
  동등성 확인. replay는 새 물리 실행으로 세지 않는다.

30km/h는 기존 NormalStopConfig의1m/s²·제동5s·확인60ms·shutdown2s를 유지하여
낙관적인 무지연 일정 감속 입력에서도 BrakingTimeout이 발생함을 C++ 계약 시험으로
확인한다. 정지 시간 v/a=8.333s, 거리 v²/(2a)=34.722m에 acquisition/actuator/확인
여유가 별도로 필요하다.10km/h는2.778s/3.858m다. 제동 제한을 늘리거나 감속을
키우는 대안은 문서로 비교하고, 실제30km/h 성능 수용이나 설정 변경으로 세지 않는다.
전체 통신 단절·ACK-loss 물리 응답, wall/Target, 전체 Reference/M8는 후속이다.
