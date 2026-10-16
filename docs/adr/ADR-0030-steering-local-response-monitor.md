# ADR-0030: 조향 센서 경계와 local response monitor

Date: 2026-10-16. Status: **IMPLEMENTED / Host component checks; 학습자 수용 PENDING**.
[M2 수용 검토](../m2_acceptance_review.md)의 OPEN-M2-01을 구현한다.
Classic stack/실차 안전성 검증이나 M2 전체 완료를 뜻하지 않는다.

## 문제

기존 SteeringActuator는 command 검사와 delay/rate 응답·Actual 생성을 함께 수행했다.
통신 상실에는 hold했지만, fresh Command와 fresh angle acquisition이 계속되는 동안
조향이 움직이지 않는 경우는 검출하지 못했다. 현재 목표와 Actual의 단순 차이는
정상 dead time·rate limit·saturation에도 커지므로 그 차이만으로 jam을 선언할 수 없다.

## 결정

1. 물리 delay/rate/angle 응답을 `simulation/steering/SteeringResponse`로 분리한다.
   Jam/rate variation은 elapsed interval의 물리에, sensor hold/invalid/override는 end acquisition에만 주입한다.
2. `interfaces/steering/AngleMeasurement`에 physical model epoch·sequence·source time·각도를 담는다.
   Application epoch 재시작은 물리 각도나 sensor sequence를 리셋하지 않는다.
3. `vecu/steering/SteeringResponseMonitor`는 issued bounded target과 sensor port만 소비한다.
   Plant header·diagnostic truth·jam flag를 참조하지 않는다. 첫 유효 측정으로 초기 위치를 잡고,
   정상 동작 중 매 측정값으로 예측 상태를 다시 맞추지 않는다.
4. 목표의 기존 50 ms delay를 반영한 FIFO와 정상 rate 범위로 가능한 angle interval을 전파한다.
   Default는 nominal rate의 0.8..1.2배, interval 밖 오차 여유 0.01 rad다.
   Physical maximum으로 clamp한 목표를 사용하므로 허용된 saturation은 residual을 만들지 않는다.
5. Residual 초과가 **새 acquisition의 source time 기준 60 ms** 이어질 때 TrackingError를 latch한다.
   정상 범위로 돌아온 sample은 pending dwell을 취소한다. Pending은 DEGRADED이며 아직 latch가 아니다.
   반복 command는 지연·dwell을 다시 시작하지 않고 cached sensor read는 dwell을 진행시키지 않는다.
6. Sensor missing/만료와 identity/value/time 위반은 SensorUnavailable/SensorInvalid로 구분한다.
   Default age 20 ms, 연속 fresh acquisition gap 30 ms다. Wrong epoch, timestamp 역행·future,
   같은 identity의 값 변경, NaN/범위 밖 값은 사용하지 않는다.
7. 기존 single-owner SteeringActuator를 SIL composition adapter로 유지한다. Sensor acquisition과 monitor 뒤에
   다음 목표를 stage하며 새 출력은 이후 물리 구간에만 적용한다. Fault는 pending motion을 취소하고
   기존 modeled hold/latch를 적용한다. Clock/deadline/communication fault의 기존 정책을 유지한다.
8. CAN ID/DBC/P05/layout은 변경하지 않는다. Fresh valid 측정만 angle Actual로 발행한다.
   Held sensor를 current report time으로 갱신하지 않고 unavailable로 발행한다.
   FAIL_SAFE에서도 새 유효 angle은 관측값으로 발행할 수 있다. Trusted 새 application epoch로만 ECU latch를 초기화한다.

Rate band·threshold/dwell은 명시한 첫 SIL fixture다. 실차 spec, jam 검출 100 ms deadline이나
FTTI를 확정하지 않는다. 기존 stream-loss 100 ms 계약과 tracking 검출 시간을 구분한다.

## 근거와 범위

관측과 정상 모델의 residual을 검출 지표로 쓰는 일반 개념은
[MathWorks model-based condition indicators](https://www.mathworks.com/help/predmaint/ug/model-based-condition-indicators.html)와
[fault detection/diagnosis 구분](https://www.mathworks.com/help/predmaint/ug/decision-models-for-fault-detection-and-diagnosis.html)을 참고했다.
위 bounded-rate predictor와 수치는 프로젝트의 별도 설계이며 해당 문서의 자동차 calibration이 아니다.

TrackingError는 **정상 응답 계약에서 벗어남**을 검출한다. 기계 jam, 구동 능력 저하와 plausible sensor bias/freeze를
이 센서 하나만으로 고유하게 분류하지 않는다. 현재 요구와 같은 angle에서 발생한 jam처럼 excitation이 없으면
검출하지 못할 수 있다. 명령 변화에도 정상 interval이 고정각을 포함하면 구분할 수 없다.
Delay uncertainty·inertia/friction·노이즈/센서 이중화와 독립 watchdog은 미구현이다.
SIL hold는 실제 차량의 가용 조향/안전 정지를 보장하지 않는다.

## 검증과 영향

새 39개: 물리 9개·monitor 21개·adapter 9개를 추가해 전체 unit은 430개다.
기존 Steering 13개를 포함해 normal·ASan/UBSan 전체 unit, production build와 기존 model vCAN 8개를 검사한다.
CLI는 기존 `actuator_demo steering-model`에 normal/jam/slow/sensor-hold/sensor-invalid/transient를 추가한다.
새 executable이나 jam CAN frame은 만들지 않는다. 상세 결과는 [품질 기록](../quality_policy.md),
재현/해석은 [학습 안내](../learning/m2_steering_fault_monitor.md)에 보존한다.

영향은 SYS-ARCH-002, SYS-COM-004, SYS-SAFE-001/002/003과 TC-CTRL-001·TC-SAFE-001/002의
component 부분 증거다. 전체 requirement revision/차량 TC Result는 변경하지 않는다.
Brake response detector는 OPEN-M2-02, 실제 task/watchdog/trace는 M3, Zone availability 전달은 M4/M5,
Fault Event/DTC 통합은 M9에 남는다.
