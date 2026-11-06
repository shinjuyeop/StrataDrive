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
선택형 native 경로는 실제 receiver의 BMS 전력 제한과 wheel 취득을 연결한다. 저항 범위는
명시적인 고정 SIL 보정값이며, 온라인 경사/저항 추정과 전체 ODD 보수성 검증은 후속이다.

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
  실패하면 새 정상 명령이 없고 wrapper는 더 새로운 INIT까지 latch한다. native `--supervised-speed` 경로에서는 실패한 release에서 기존 coordinator와8개 actor의
  보호 경로를 선택한다. 다른 호출자는 같은 연결을 구현해야 한다. 직전 정상 명령을 연장하거나 성공한0명령으로 해석하지 않는다.

Route·speed 취득·제안의 현재 dependency와 BMS의 원래 물리 dependency를
DerivedVehicleRequest에 별도로 전달한다. 배분된 명령은 두 원천 중 가장 오래된 시각과 가장 이른 expiry를 갖는다. 계산 완료 시각으로 입력 권한을 갱신하지 않는다.

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

## Native 실행 연결

`m7_wheel_shadow --native-solver-work ... --sim-horizon-ms 60000 --speed-profile v1
--supervised-speed 0:200`으로 선택한다. 마지막 값은 고정 저항 하한:상한 N이며 선택한 시나리오
전체를 덮는 보정값이어야 한다. Python 실행기 `m7_1o_run.py`도 같은 옵션을 전달한다.
현재 Python 연결 범위는 simulation-time speed loop의 nominal/input-loss다.
기존 옵션을 생략한 M8/CARLA 경로와 wire format은 유지한다. 실제 모델은 없으므로
Supervisor는 fresh classical fallback을 사용한다. 실제 학습 성능으로 표시하지 않는다.

`AvailableForceEstimator`는 현재 readiness와 BMS 품질/epoch/취득을 검사한다. 구동력은 기존
배분기와 공유하는 DC-load·기계출력·최대토크 식을 wire 해상도로 내림하여 계산한다.
제동력은 마찰제동 용량만 사용하고 optional regen은 더하지 않는다. 과거 selected torque나
실제 소비 토크를 가용 최대힘으로 사용하지 않는다. Road load는 실시간 측정이라고 표시하지 않는다.

가용력의 기본 `Snapshot30ms` 계약은 그대로다. 새 `ReceiverPowerLimits`에서는 서로 다른
원천의 기존 계약을 구분한다.

- 현재 휠 age≤30ms, PI가 계산한 결과의 wheel 기반 validity≤60ms+1ns.
- BMS limits message≤50ms, 원래 물리 input≤70ms. 각 configured budget이 더 작으면 그것을 따른다.
- Force expiry는 wheel/limits message/물리 input expiry의 최솟값이다. 입력 시각을 계산 시각으로
  교체하지 않는다. 현재 actuator/zone 상태와 permission은 배분기가 매 release에 별도 검사한다.
- `VehicleInputDependency.power`는 BMS 원천을 별도로 보존한다. 기존 speed/route30ms gate와
  request30ms gate는 바뀌지 않는다. 원본 power dependency·expiry의 변조/역행/만료를 거절하고,
  최종 child 명령의 oldest/expiry에는 이 dependency도 포함한다. 새로운 wire field는 없다.

매20ms Supervisor→governor→PI→기존 coordinator/allocator가 실행되고 배분 피드백은 다음
PI release의 방향별 anti-windup에 전달된다. 실패 시 새 정상 요청을 발행하지 않고 같은 release에
기존 보호를 선택한다. 입력 복구만으로 latch가 풀리지 않고 더 새로운 실제 INIT가 필요하다.

## 진단

기존 SD-1002에 component=Speed(1), monitor=SupervisedSpeed(4), subject=Protection(4)을
추가한다. `native_reason=(ProposalReason<<8)|ReferenceFault`이며 reason 값0..10은
Accepted/Missing/Invalid/Stale/Identity/Hazard/NoFallback/Authority/Reference/Controller/CapacityInput이다.
ReferenceFault0..5는 None/Session/Clock/Input/Capacity/Tracking이다. 첫 검출 시각은 latch 후에도
고정하며 기존 보호 선택·ACK·원본 Actual 관측이 그 occurrence를 참조한다. 기존 PI/배분 진단도 유지한다.
새 monitor는 아직 qualified Passed/서비스 clear adapter를 제공하지 않는다. 입력 복구·INIT·프로세스
재시작으로 DTC가 지워졌다고 표시하지 않으며 일반 Speed monitor의 clear 근거를 재사용하지 않는다.

## 검증과 다음 단계

[Native 연결 검증](../test-plan/evidence/runtime-speed-connection/README.md)과
[초기 Host 검증](../test-plan/evidence/remaining-improvements/README.md)을 구분한다.
전체 ODD·온라인 저항 추정·실제 학습 모델과 새 monitor의 qualified 복구/clear는 후속이다.
모델 도입 시 scenario/seed, route revision, feature adapter, sensor/calibration, model weights hash,
precision, software revision, clock instance, 모든20ms 입력/출력·fallback 이유를 고정하고 보존한다.
