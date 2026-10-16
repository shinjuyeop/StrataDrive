# ADR-0028: 실제 Drive 토크에서 배터리 에너지까지

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-03/12/13/14의 부분 구현이다. 전체 TC-REG/EV/ZON은 NOT RUN이다.

## 결정과 경계

`simulation/drive/DriveEnergyModel`이 실제 aggregate wheel torque·같은 기준 wheel rad/s·별도
auxiliary power를 받아 motor/inverter DC power를 계산한다. 내부의 기존 BatteryModel만 chemical
energy/SOC·battery 저항 발열을 소유한다. Command, capability, BMS 허용량은 적분 입력이 아니다.
TorqueResponse/DriveController의 실제 출력에서 다음 interval의 physical acquisition을 만든다.
ECU application Epoch 재시작은 physical model/누적 에너지를 리셋하지 않는다.

이번 electrical boundary는 **HV가 준비된 이상적 DC 연결**이다. Local HV는 battery terminal의 실제
전압과 같고 inverter-ready는 명시적 fixture다. PowerModel의 dynamic DC-link/접점/프리차지 모델을
동시에 실행하지 않는다. 따라서 capacitor 저장 에너지·배선/접점 손실을 빠뜨린 채 그 회로까지
통합했다고 주장하지 않는다. 실제 circuit coupling과 shutdown 중 에너지/부하 처리는 다음 작업이다.
Wheel speed는 외부에서 유지하는 20 rad/s fixture다. 차량 관성·타이어·주행 저항/정지 모델은 없다.
이 외부 기계 경계는 dynamometer처럼 일을 공급/흡수할 수 있고, command로 speed를 계산하지 않는다.

## 전력과 손실

`Pm = actual_torque × actual_wheel_speed`이며 양수는 기계적 구동 출력, 음수는 제동 입력이다.
부하 비례 conversion loss는 구동 때 `Pm × (1/eta_m − 1)`, 회생 때 `−Pm × (1−eta_g)`다.
여기에 nonnegative `kT² + inverter_idle`을 더하고 `Pdc = Pm + motor_loss`로 계산한다.
Battery terminal은 `Pdc + auxiliary`다. BatteryModel이 `I²R`만 추가해 chemical energy를 갱신한다.
Motor loss를 battery 온도/저항 손실에 다시 더하지 않는다. 별도 motor thermal state는 없다.

Fixture는 eta_m/g=0.92/0.85, k=0.01 W/Nm², inverter idle=50 W, auxiliary=150 W다.
Eta는 추가 copper/idle을 포함한 총 효율이 아니다. 실제 map·calibration은 미결정이다.
기존 Drive gate의 eta 하한 0.9와 k=0.01·fixed reserve 200 W는 이 fixture의 구동 소비를 덮는다.
Reserve는 한계에서 예약하는 몫이고, 실제 에너지 입력에는 idle 50 W와 auxiliary 150 W를 한 번씩만 더한다.
외부 auxiliary가 바뀌면 reserve/배분 계약도 검토해야 한다.

음수 torque여도 motor loss 때문에 Pdc가 양수일 수 있다. Pdc가 음수여도 auxiliary가 더 크면
battery는 방전한다. 저속/standstill에서도 copper/idle은 유지하며 효율로 0을 나누지 않는다.
회생 가용량 계산의 보수적 100% mechanical upper bound와 실제 85% conversion 계산은 역할이 다르다.

[Motor & Drive 공식 설명](https://www.mathworks.com/help/simscape-electrical/ref/motordrivesystemlevel.html)의
system-level energy balance·fixed/torque loss와 [Battery equivalent circuit](https://www.mathworks.com/help/simscape-battery/ref/batteryequivalentcircuit.html)을
참고했다. 위 수식·parameter와 interval 계약은 StrataDrive의 fixture 결정이다.

## 시간·원천·에너지 장부

Begin에서 알려진 actual torque/speed/auxiliary를 interval 전체에 ZOH한다. End acquisition이나
end torque를 이전 interval에 소급하지 않는다. Demo는 10 ms, model 최대 step은 20 ms다.
이는 TorqueResponse의 연속 piecewise 응답에 대한 sample 기반 전력 근사이며 exact ramp 적분이 아니다.
Known linear torque ramp의 20→10 ms refinement 시험으로 mechanical work 수렴을 확인한다.

세 입력의 model Epoch/sequence/source/dependency·cached value를 독립 검증한다. End 기준 dependency
age ≤30 ms, source skew ≤10 ms다. 계산 source는 begin, input은 세 acquisition의 oldest dependency다.
Battery의 end sensor source와 계산 input을 구분한다. BMS 20 ms 판단이 매 10 ms 갱신됐다고 꾸미지 않는다.
Unknown/invalid/stale·gap/rollback은 latch/unavailable이며 0 입력이나 energy backfill로 바꾸지 않는다.

Motor mechanical work와 loss는 compensated sum으로 누적한다. 검사식은 다음과 같다.

```text
initial_chemical_energy − chemical_energy
  = signed_mechanical_work + motor_loss + auxiliary_energy + battery_ohmic_loss
```

Tolerance는 max(1e−6 J, capacity×2e−12), 50 kWh fixture에서 0.00036 J다.
이는 수치 장부의 허용 오차이며 실차 모델 정확도나 센서 오차 허용치가 아니다.
Capacity/전기적 한계 초과는 기존 BatteryFault/초과 에너지를 전파하며 SOC/power를 clip하지 않는다.

## 충전 여유와 잔여 응답

Valid charge-zero 뒤 actual 음수 토크는 유한 rate로 줄어든다. 이 구간의 반환 전력도 계속 적분한다.
센서 hotspot 45 °C 주입으로 charge-zero를 만드는 연결 시험과 demo에서 이를 확인한다.
SOC/저장 에너지는 주입하거나 되돌리지 않는다.

기존 BMS SOC soft zero는 0.05/0.95다. 50 kWh에서 물리 empty/full까지 각 9 MJ 여유가 있다.
100 ms 검출 + 20 ms ZOH + 300 Nm/2000 Nm/s 해소라는 제한된 가정에서 100 kW terminal 입력의
최대 chemical flow로 계산한 270 ms reaction budget은 약 27.9 kJ이며 guard band보다 작다.
이 검토는 이번 fixture의 finite traction reaction에 한정한다. 무한한 auxiliary 소비, 센서 오차/고장,
thermal/cell charge-zero 순간의 허용 overrun, hardware trip·차량 braking deficit·shutdown 안전성은 보장하지 않는다.
완충 상태에서 이미 음수 actual이 존재하는 잘못된 초기 조건은 CapacityViolation으로 드러낸다.

## 검증과 후속

[학습·실행](../learning/m2_drive_energy.md)에 네 demo와 해석을 정리했다.
새 28개 시험으로 normal·ASan/UBSan 전체 unit은 362개다. Analytic power/loss, 별도 aux/heat,
20,000 alternating interval의 장부, interval source/cache/unknown, 경계 초과와 실제
Battery→BMS→명시적 relay/독립 trusted Central fixture→DriveController→Actual/P05 receiver를 검사한다.
Normal·sanitizer·BUILD_TESTING=OFF의 네 demo도 검사한다. 새 wire/transport case는 없다.
이전 vCAN 97개 전체 이력과 직전 Drive 3개 재검사는 보존하며 이번 energy transport PASS로 바꾸지 않는다.
다음은 RC/DC-link·실제 접점/부하와 Battery를 단일 전기·에너지 경계로 연결하는 것이다.
Vehicle motion·Central 배분/마찰 보충·분산 runtime·실차 map/Target timing·전체 차량 TC는 후속이다.
