# ADR-0031: 브레이크 압력 센서와 local response monitor

Date: 2026-10-16. Status: **IMPLEMENTED / Host component checks; 학습자 수용 PENDING**.
[M2 수용 검토](../m2_acceptance_review.md)의 OPEN-M2-02에 대한 component 구현이다.

후속 구조 변경: [ADR-0032](ADR-0032-ecu-and-sil-execution-boundaries.md)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

## 문제

Fresh Command/Actual stream만으로 가압·감압 능력이 정상인지 알 수 없다.
목표와 측정 압력의 직접 비교도 정상 delay/rise/fall·saturation에 오검출을 만든다.
통신 상실 보호에서 사용한 pressure floor는 물리 고장 뒤의 압력 도달 성공을 보장하지 않는다.

## 결정

1. `simulation/brake/BrakePressureResponse`에 기존 delay·별도 rise/fall rate·압력 한계와
   물리 stuck/rate variation을 둔다. 주입은 명시한 elapsed interval에 적용한다.
2. `interfaces/brake/PressureMeasurement`에 model epoch·acquisition sequence/source time·측정 압력을 둔다.
   Hold/invalid/override는 sensor port에 적용하며 application 재시작으로 물리 상태나 acquisition 번호를 초기화하지 않는다.
3. `vecu/brake/BrakeResponseMonitor`는 발행한 bounded target 이력과 local sensor만 읽는다.
   Plant header·truth getter·고장 주입 flag를 읽지 않는다. 첫 측정으로 초기 압력을 잡은 뒤
   정상 예측 범위를 매 측정으로 재설정하지 않는다.
4. 50 ms delayed target과 방향별 정상 rate 범위로 pressure interval을 전파한다.
   가압/감압 각각 nominal의 0.8..1.2배, interval 밖 허용 오차 25 kPa다.
   범위 초과가 새 acquisition의 source time으로 60 ms 지속되면 ResponseError를 latch한다.
   Pending은 DEGRADED, 정상 관측 복귀 시 pending은 해제한다. Cached read는 확인 시간을 진행시키지 않는다.
5. Source age 20 ms 초과·acquisition gap 30 ms 초과는 SensorUnavailable이다.
   Missing, NaN/범위 밖, wrong epoch, future/pre-session time, identity 변경·역행을 검사한다.
   Gap은 관측 연속성 고장을 latch하지만 새로 취득한 개별 유효 압력의 보고까지 막지는 않는다.
6. BrakeActuator는 같은 thread의 SIL composition adapter로 유지한다.
   End acquisition/monitor 뒤에 정상 목표를 stage하고 새 출력은 이후 물리 구간에 적용한다.
   첫 fault에서 normal pending을 취소하고 **increase-only/floor 출력 primitive**를 요청한다.
   이는 plant가 floor 아래에서는 유한 가압하고 위에서는 감압하지 않는 명시적 SIL 가정이다.
   ECU가 hidden actual getter로 보호 목표를 계산하지 않는다. 실제 밸브/펌프 제어 구현은 아니다.
7. 보호 요청 뒤에도 stuck/저하 주입을 계속 적용한다. 따라서 floor에 못 도달할 수 있다.
   `protection_floor_observed`는 새 유효 센서의 floor 이상 여부만 보고하며 센서 무효/캐시일 때 unknown이다.
   이 값이 true여도 감압 성공·센서 정확성·차량 정지나 안전성을 증명하지 않는다.
8. Existing command loss/continuity/clock/gap·새 trusted application epoch 정책을 유지한다.
   Gap interval은 물리를 backfill하지 않는다. 새 epoch는 latch/pending을 지우고 물리 상태를 보존한다.
   Sensor fault의 원인이나 persistent stuck을 재시작으로 수리하지 않는다.
9. CAN ID/DBC/P05/layout은 변경하지 않는다. 새 유효 acquisition만 pressure Actual에 싣고,
   캐시/무효는 unavailable로 발행한다. FAIL_SAFE와 유효 압력은 함께 존재할 수 있다.

## 한계와 검증

ResponseError는 정상 응답 계약 위반이며 기계 stuck과 plausible sensor freeze/bias의 고유 원인 분리가 아니다.
Excitation이 없거나 정상 예측 interval이 고정 압력을 포함하면 stuck을 검출하지 못할 수 있다.
현재 fixed delay·bounded rate 모델 밖의 compliance/온도/유체·누설·ABS·센서 이중화는 미구현이다.
수치는 시험 fixture이며 OEM calibration/FTTI/stream-loss 100 ms 검출 budget으로 채택하지 않는다.

새 시험 40개(plant 10·monitor 16·adapter 14), 기존 Brake adapter 16개와 전체 unit을 검사한다.
CLI는 기존 `brake-model`에 8개 scenario를 둔다. 새 executable/고장 CAN frame은 추가하지 않는다.
기존 model vCAN 8개는 회귀이며 새 pressure fault의 network 시험은 아니다.
[학습 안내](../learning/m2_brake_fault_monitor.md)와 [품질 기록](../quality_policy.md)에 결과·재현 절차를 둔다.

SYS-ARCH-002·SYS-COM-004·SYS-SAFE-001/002/003과 TC-CTRL-001·TC-SAFE-001/002의 local 부분 증거다.
전체 system TC는 NOT RUN, M1/M2 학습자 수용은 PENDING이다.
독립 task/watchdog·trace는 M3, Zone/Central 통합은 M4/M5, 차량 검증은 M6/M7, DTC는 M9에 남긴다.
