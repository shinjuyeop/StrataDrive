# CARLA V1 속도 제어 연결 프로토콜

실행 전 고정한 M8 기능 연결 범위. 기존 Town03_Opt spawn0·MKZ2020·V1 model hash,
NoDrive vehicle320, observed solver work와 single EV, eight-role INIT/RunLease,
native/server admission을 유지한다. 서버는 기존 runner가 실행·정리한다.

- `--speed-loop`는 solver-work simulation-continuous에만 허용한다. 4,000개10ms
  physics interval과 마지막 work settlement, 단일 session이다. wall 모드는 불가하다.
- 새 제어 경로는 trusted current Drive Actual의 rear wheel 평균×0.355m를 사용한다.
  allocation은 명시적으로 V1 mass1696kg/radius0.355m를 받는다. 기존 기본1000kg/0.3m,
  PI 상수와 원천 시각을 보존한다. 현재 Drive feedback 수신과 생성된 request의
  source age는 각각30ms이며 permission/command의 기존 경계도 유지한다.
  계산된 request의 별도 센서 의존성은 기존 PI 모델의60ms 경계로 제한한다.
- 첫 정상 arm 뒤20ms controller release를 원점으로 target0→10km/h(10s),
  10km/h 유지(10s), 10→0(10s),0 유지로 고정한다. Steering curvature0이다.
  경로/횡제어가 없는 출발점 주변 연결 시험이며 Reference30km/h/전체 M8 수용이 아니다.
- 독립 판정: [15,20)s plateau 오차≤1km/h, [35,38)s 정지 오차≤1km/h,
  양수 목표 대비 동시각 overspeed≤10%. Body forward speed와 controller wheel speed를
  별도 판정한다. 원래 timestamp에 대응하며 보간/절댓값 wheel/새 source 합성을 금지한다.
- 제어 release20ms·sequence 증가·original source·expiry·출력[-5,2]·slew2를 검사한다.
  feedback/physical trace의 분모를 저장하고 native command→Actual→solver work와
  EV balance는 기존 독립 감사도 통과해야 한다. 새 epoch/reset 없이 전체 구간을 실행한다.
- 끝은 실제 wheel 정지·hold 상태에서 기존 barrier pause/reset/close로 정리한다.
  CARLA admission은 아직 normal-stop HV-off proof를 지원하지 않으므로 이번 범위의
  정지 유지와 SimpleVehicle의 NormalStop power-off를 같은 판정으로 표시하지 않는다.
- 실제 CARLA 결함은 기존 snapshot withholding과 missing solver work를 각각200번째
  frame에 주입한다. 추가 physics tick 없음·work/source 복구 금지·소유 actor/settings/
  server 정리를 검증한다. 실제 차량 제동 완료나 wall deadline 수용으로 세지 않는다.
- 실패 원본·source/binary hash·설정·tool version을 보존한다. 결과 후 임계값을 완화하지 않는다.
  UE 종료 실패는 물리/제어 통과와 따로 보고하며 전체 실행 PASS로 덮지 않는다.

## 실제 CARLA 실행 전 설계 수정

초안의 sensor-root30ms 방식은 합성 stationary wheel/native admission 시험에서
frame81에 다음10ms 구간을 덮지 못했다. 센서→20ms PI→10ms ECU Actual→다음 physics
구간의 지연을 request 생성 시각과 같은 것으로 취급한 문제다. 위상 검사202개도
해당 경계를 통과하지 못했다. 실패 기록은 보존하며 실제 주행 결과로 세지 않는다.

CARLA 경로는 기존 Controller20ms release에서 request를 생성하고, 별도 typed input에
원천 acquisition과 source+60ms+1ns의 exclusive expiry를 보존한다. Central은 요청의
30ms 경계와 input 경계를 모두 검사하고 기존 CommandContext의 oldest/expiry에
포함한다. 새 wire 필드나 서버 admission 변경은 없다. SimpleVehicle의 sensor-root
방식은 유지한다. 현재 센서를30ms보다 늦게 받거나 frozen source를 재사용하는 것은
여전히 거절한다. 위 변경은 실제 CARLA 첫 실행 전에 고정한 것으로, 추종 오차·속도·
slew·단일 session 판정 임계값은 초안과 같다.
