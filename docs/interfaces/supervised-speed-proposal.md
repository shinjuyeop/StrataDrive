# M8 가용력 목표와 M10 속도 제안 Host 계약

`m10-speed-proposal-v1`은 M10 착수용 **상태 입력 기반 속도 제안** 프로파일이다. 인지 이미지
모델·학습된 planner·localization을 구현/검증했다는 뜻이 아니다. 기존 M8 PI/배분/보호와
frozen Python 모델은 유지하고 선택형 `SupervisedSpeedRequest`에서 연결한다.

## 입력과 출력

Host 입력 tensor는 binary64 `[4,6]`, 오래된 순서의20ms state4개다. 실제 ML 실행의 FP32/FP16
변환·오차는 모델 도입 때 별도 검증한다. 각 행의 feature 순서는 다음과 같다.

| Feature | 단위·뜻 |
| --- | --- |
| speed_mps | 실제 신뢰된 wheel 기반 전진 속도,0..40/3.6m/s |
| route_speed_mps | 신뢰된 현재 경로의 속도 상한, 같은 범위 |
| propulsion_n / braking_n | 각각 사용 가능한 구동/제동 힘의 보수적 추정,0이상 N |
| road_load_min_n / road_load_max_n | 경사·구름/공기 저항·추정 오차를 포함한 저항의 하한/상한,N |

양수 저항은 전진을 방해한다. 내리막 중력은 음수가 될 수 있다. 각 행의 source는 producer가
보존한 취득 시각이며 epoch·clock instance와 valid를 별도로 전달한다. NaN·순서 오류·누락은
0으로 대체하지 않는다. 가용 힘을 과거 selected torque 또는 actuator Actual로 추측하지 않는다.
실제 BMS/차량 저항 추정 adapter의 연결과 보수성 검증은 후속이다.

모델 출력은 `[16] speed_mps`, scalar risk `[0,1]`, valid다. 출력 속도는 원래 최신 source를
기준으로0..1.5초의100ms 간격이다. 최신 route 상한과 기존 가속[-5,+2]m/s² 범위를 검사한다.
Risk는 이 초기 프로파일의 점수이며 검증된 충돌 확률이 아니다. Host 기본 임계값0.2는
fixture 계약이고 실차 보정값이 아니다. Steering·토크·압력·permission 출력은 없다.

`bind_speed_proposal`이 신뢰된 입력에서 epoch·clock·history·최신 source와 route ceiling을
붙인다. Sequence와 model revision은 adapter가 공급한다. 모델은 시각이나 권한을 생성하지
않는다. Expiry는 최신 취득+30ms+1ns, 현재 age≤30ms이며, history 앞쪽60ms는 모델 문맥으로
따로 보존한다. 이를 현재 물리 피드백으로 재사용하지 않는다. 동일 inference 재사용이 유효해도
기존 배분기가 요구하는 입력 원천의 단조 증가를 만족하지 못하면 새 정상 명령을 내지 않는다.

## Supervisor와 기존 제어 연결

- 정상 권한과 valid/fresh/identity/route/범위를 통과한 제안을 사용한다. 같은 sequence의 변조,
  sequence/source 역행, 세션 중 model revision 교체는 거절한다.
- 모델이 없거나 invalid/stale이면 동일 epoch·clock의 fresh classical 목표가 있을 때 사용한다.
- 유효한 높은 risk는 Protection이다. 권한 상실 또는 fallback도 없으면 Protection이다.
- 선택한 목표는 가용력 governor→기존 SpeedRequest PI→ControlAllocation으로 간다. 어느 단계든
  실패하면 새 정상 명령이 없고 wrapper는 더 새로운 INIT까지 latch한다. 호출자가 기존 coordinator의
  보호 경로로 연결해야 한다. 직전 정상 명령을 연장하거나 성공한0명령으로 해석하지 않는다.

Route 상한·가용력·speed 취득·제안 원천 중 가장 오래된 현재 dependency와 가장 이른 expiry를
DerivedVehicleRequest에 전달한다. 계산 완료 시각으로 입력 권한을 갱신하지 않는다.

## 가용력 governor

기본 질량1000kg·가용력 사용 비율0.9·최대 목표 추종 차이0.5m/s는 명시적인 Host 설정이다.
제어 주기는 기존20ms다. 저항 범위 `[Lmin,Lmax]`, 구동/제동 가용력 `P,B`, 질량 `m`, 비율 `f`에 대해:

```text
amin = max(-5, (-f*B - Lmin)/m)
amax = min( 2, ( f*P - Lmax)/m)
```

모든 저항 값에서 이 가속 구간의 힘을 감당할 수 있다. 목표 증가량은 이 구간과 실제 속도 주변의
추종 차이 한도의 교집합으로 제한한다. 정속조차 보장할 수 없거나 교집합이 없으면 보호를 요구한다.
이 계산은 상류 목표의 필요 조건이며 PI·actuator 응답 성능/제동 거리 보장이 아니다. 기존 제동
용량·응답 보호를 유지한다. 가용력 원천의 동일 ID 변조·역행·만료와 놓친20ms 실행도 latch한다.

## 검증과 다음 단계

현재는 Host component·기존 배분 연결과100초 point-mass 합성 시험이다. 실제 CARLA/Target의
새 프로파일 수용이나 trained-model 성능으로 확대하지 않는다. 모델 도입 시 scenario/seed,
route revision, feature adapter, sensor/calibration, model weights hash, precision, software revision,
clock instance, 모든20ms 입력/출력·fallback 이유를 고정하고 보존해야 한다.

인지 모델의 이미지 shape·전처리, temporal learned planner의 학습/평가, 실제 모델 지연과 fallback의
물리 정지 검증은 M10–M11 후속이다. [실행 근거](../test-plan/evidence/remaining-improvements/README.md)를 따른다.
