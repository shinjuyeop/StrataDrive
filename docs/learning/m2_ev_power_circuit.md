# M2: 프리차지 회로와 배터리 에너지를 함께 계산하기

Date: 2026-10-16. Status: **Host functional SIL component 구현·시험 / 직접 재현·이해 review PENDING**.
[ADR-0029](../adr/ADR-0029-coupled-battery-and-dc-link.md)의 연결 모델이다.

## 이번에 달라진 점

이전 [Drive energy](m2_drive_energy.md)는 이상적인 전선으로 Battery와 Drive를 연결했다.
이번 [EvPowerModel](../../simulation/power/ev_power_model.hpp)은 실제 모델의 main/precharge 접점·저항·
DC-link capacitor를 사이에 두고 **Battery → 전원 회로 → inverter → 실제 torque**를 연결한다.
구현은 [composition](../../simulation/power/ev_power_model.cpp), [회로](../../simulation/power/power_model.cpp),
[단위 시험](../../tests/unit/ev_power_model_test.cpp)에 있다.

| 저장량·손실 | 계산/소유하는 곳 |
| --- | --- |
| Battery chemical energy·SOC·내부저항 heat | BatteryModel |
| DC-link 저장 에너지 `½CV²`·실제 접점 | PowerModel |
| Motor conversion/copper/idle 손실 | 공통 motor power 계산 |
| Precharge·main·bleed 저항 손실 | 회로의 실제 전류·전압 적분 |

배터리에서 나간 에너지 전부가 모터로 가는 것은 아니다. 프리차지 때는 capacitor를 충전하고,
일부는 저항 열로 바뀐다. C=0.002 F에 400 V를 충전하면 저장량은 **160 J**다.
무부하·완충에 가까운 이상적 RC 시험에서는 battery chemical 약320 J 중 약160 J가 capacitor,
나머지가 precharge·battery 저항 열이다. 실제 demo에는 auxiliary 등 추가 소비도 있다.

## 왜 전류의 마지막 값만 곱하면 안 될까?

프리차지 전류는 처음 크고 갈수록 작아진다. 마지막 전류×구간 길이는 실제 전하 이동량을 놓친다.
그래서 회로가 **∫I dt**와 **∫I² dt**를 계산해 BatteryModel에 전달한다.

- SOC/chemical energy 변화: `Voc × ∫I dt`
- Battery 내부저항 손실: `Rint × ∫I² dt`

전류가 +10 A와 −10 A를 같은 시간 흘렀다면 net charge는 0이어도 발열은 생긴다.
평균 전류 0의 제곱으로 발열을 계산하면 이 열이 사라진다. Ending current는 end sensor로 보고하며,
이 구간 적분이나 다음 순간의 전류와 같은 의미로 쓰지 않는다.

회로는 접점이 바뀌는 시각에서 구간을 나누고, 최대 50 µs의 implicit midpoint step을 사용한다.
ECU는 여전히 10 ms, BMS 판단은 20 ms다. 작은 solver step이 OS task의 실행 주기를 뜻하지 않는다.
RC analytic response와 50→25 µs refinement 시험으로 근사를 확인했다. 정확한 연속 해석해 모델은 아니다.

## Pack voltage와 bus voltage, 회생 에너지의 위치

Pack voltage는 Battery 내부저항 뒤 전압, bus voltage는 main/precharge 경로 뒤 capacitor 전압이다.
구동 중에는 저항 강하로 bus가 더 낮고, 회생 중에는 반환 전류 때문에 더 높을 수 있다.
Drive는 자기 실제 bus를 확인한다. Central 허가/PowerStatus가 그 측정을 대신하지 않는다.

컨택터가 열린 상태에서 motor가 반환한 에너지는 우선 고립된 capacitor에 저장될 수 있다.
이때 battery SOC를 올리면 틀린 장부다. 반대로 고립된 capacitor를 bleed로 방전하면 capacitor
에너지가 열로 바뀌며 battery에서 같은 에너지를 다시 빼지 않는다.

전기적으로 불가능한 load나 capacity 초과를 발견하면 두 물리 모델을 함께 commit하지 않는다.
전압·SOC를 잘라 성공처럼 보이게 하지 않는다. 잘못된 입력/시간의 gap은 0이나 나중 적분으로 채우지 않는다.

## 실행과 읽을 결과

```sh
cmake -S . -B build/m1-angle
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
build/m1-angle/actuator_demo ev-power normal
build/m1-angle/actuator_demo ev-power weld
build/m1-angle/actuator_demo ev-power current-unknown
build/m1-angle/actuator_demo ev-power aux-blocked
```

| 예제 | 기대 결과 |
| --- | --- |
| normal | 약0.7 s READY → 구동·회생으로 SOC 변화 → 약2.5 s 종료 요청 → torque 0/전류 하강·dwell → 접점 open → 잔류 전압 하강 후 OFF |
| weld | positive 접점 용착; OPEN_CONTACTORS/blocked 유지, OFF라고 보고하지 않음 |
| current-unknown | power current sensor 상실; WAIT_CURRENT/blocked, unknown을 0 A로 대체하지 않음 |
| aux-blocked | 실제 pack-side aux 10 A 유지; 전류 하강 조건을 만족하지 않아 WAIT_CURRENT/blocked |

Auxiliary는 실제 pack-side **0.375 A current fixture**라 전력이 terminal voltage에 따라 변한다.
HV가 OFF여도 auxiliary는 계속 소비한다. `auxiliary_j`와 SOC는 이후에도 변할 수 있다.
이번 combined fixture만 opening-current threshold를 0.5 A로 설정했다. 기존 standalone default는 5 A다.
이는 현 차량의 안전한 opening threshold를 확정한 것이 아니다.

정상 종료 뒤 `drive_fault=4`는 활성화 후 Central Inhibit를 latch한 기존 Drive 정책이다.
`power_fault=0, phase=OFF, blocked=0`인 전원 종료 성공과 구분한다. 다시 구동하려면 trusted INIT/새 app Epoch가 필요하다.
Inverter enabled는 actual stage fixture이며 residual torque가 남았는데 off로 바꾸면 모델 오류로 드러낸다.

`cap_j`, `precharge_loss_j`, `main_loss_j`, `discharge_loss_j`, `auxiliary_j`를 함께 읽는다.
`returned_dc_j`는 pack branch DC 반환량이지 순수한 SOC 증가량이 아니다.
`sensor_current=unknown`이어도 내부 물리 장부는 계속 계산할 수 있다. PowerController는 그 내부 값을
sensor fallback으로 사용하지 않는다. 별도 local HV acquisition과 Battery 센서도 독립이다.

## 검증 범위와 다음 순서

전체 보존식은 **Battery chemical 감소 = capacitor 증가 + signed mechanical work + motor/auxiliary/
battery/precharge/main/bleed 손실·소비**다. `balance_j`는 이 식의 수치 잔차다.
허용치는 50 kWh fixture에서 0.00072 J이며 실차 모델 오차나 보호 성능을 뜻하지 않는다.
Drive reserve 500 W는 nominal HV 범위의 steady path/idle/aux 손실 몫이다. Capacitor transient와
finite actual residual은 실제 flow로 계속 계산하며 순간 hard power 제한을 구현한 것은 아니다.

새 29개 시험으로 normal·ASan/UBSan 전체 unit은 391개다. 네 combined demo와 기존 demo 회귀,
정적 분석/production build·문서 검사는 [품질 기록](../quality_policy.md)에 남긴다.
전체 차량 TC는 NOT RUN이다. 속도는 외부 20 rad/s이고 Central request/grant·relay는 fixture다.
차량 관성·타이어·마찰제동·정밀 chemistry/inverter switching·LV sleep은 아직 없다.

[M2 수용 검토](../m2_acceptance_review.md)에서 task/monitor 경계·parameter·fault/session과 component 증거를 대조했다.
후속 [Steering jam/tracking local monitor](m2_steering_fault_monitor.md)를 구현·시험했고 [Brake response monitor](m2_brake_fault_monitor.md)도 후속 구현·시험했다. 다음은 M2 직접 재현·수용과 M3 task/trace 설계다.
학습자 직접 재현·이해 review와 **M3 실행 주기·지터·deadline 측정**은 별도다.
M2 전체를 이 연결 하나로 완료 처리하지 않는다.
