# M2 Drive local gate와 회생 가용량

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 직접 재현·이해 review PENDING**.
[ADR-0027](../adr/ADR-0027-drive-local-gate-and-capability.md)의 구현이다.

후속 [ECU/SIL 실행 경계 정리](m2_execution_boundaries.md) 뒤 ECU의 `prepare/complete`와
`simulation/`의 SIL `tick`을 구분해서 읽는다. 물리 진행·고장 주입은 SIL 쪽 책임이다.

## 이번 단계의 역할

기존 [Drive torque 응답](m2_drive_model.md)은 목표를 주면 지연·변화율·물리 한계에 따라 움직이는 fixture다.
이번 **DriveController는 그 목표를 실제로 사용해도 되는지 검사하고 현재 한계 안으로 제한**한다.
PID/FOC/current control을 추가한 것은 아니다. 배터리에 충전된 에너지를 아직 적분하지 않는다.

| 입력 | 확인할 것 |
| --- | --- |
| DriveCommand | 올바른 Epoch·P05·sequence·mode·range, source ≤30 ms |
| Routed DriveBatteryLimits | 양방향 valid power, 원천 BMS health, source ≤50 ms / dependency ≤70 ms |
| Central DrivePermission | 허가·원래 expiry·별도 trusted parent, 참조 power source와 dependency |
| 실제 wheel speed | 전진 wheel rad/s, 모델 Epoch·acquisition·range·age |
| 실제 Drive HV | bus voltage와 inverter-ready/local fault; CAN PowerStatus를 측정값으로 사용하지 않음 |

전기 회로의 **HV_READY**, Central의 **허가**, Drive의 **로컬 입력**은 각각 필요하다.
상위가 허가했다고 실제 bus가 0 V이거나 inverter가 고장인 상태에서 토크를 적용하면 안 된다.
새 class에 이 입력을 생략하는 permissive mode는 없다. 기존 DriveActuator는 isolated fixture로 유지한다.

코드는 [DriveController API](../../vecu/drive/drive_controller.hpp),
[구현](../../vecu/drive/drive_controller.cpp), [로컬 센서 port](../../interfaces/drive/drive_local_sensors.hpp),
[시험](../../tests/unit/drive_controller_test.cpp)에 있다.

## 정상 토크와 가용량

Torque는 aggregate driven-wheel Nm, speed는 같은 기준 rad/s다. 따라서 `Pmechanical = T×omega`로
W를 구한다. 모터축 rpm/기어비나 차량 m/s를 그대로 곱하지 않는다.

회생 가용량은 **지금 허용되는 음수 토크의 양수 크기**다. Command, 실제 토크, 가용량은 다르다.
200 Nm 가용량이 있다고 200 Nm를 실제로 제동 중인 것도 아니고, command −200이 actual −200인 것도 아니다.
제동 배분을 하는 Central이 이 가용량과 실제 응답을 함께 사용해야 한다. 배분 runtime은 후속이다.

Speed·SOC 등으로 회생을 제한하고 friction을 함께 제어하는 참고는
[MathWorks 공식 예제](https://www.mathworks.com/help/sdl/ug/regenerative-friction-braking-control.html)에 있다.
Motor torque-speed envelope와 효율 map은
[Motor & Drive 모델 설명](https://www.mathworks.com/help/sps/ref/motordrivesystemlevel.html)을 참고한다.
우리의 한계 식·threshold는 아래 SIL 시험용 parameter다.

### 구동 전력에서 토크 한계로

다음 upper estimate가 BMS discharge power 이하가 되도록 양수 토크를 제한한다.

```text
Pdraw_upper = fixed_power_reserve + T × omega / eta + k × T²
```

Fixed reserve는 pack 한계를 함께 쓰는 auxiliary/idle load의 예약 몫이다. Fixture는 200 W다.
`eta=0.9`는 부하 비례 변환항의 하한 가정이고 `k=0.01 W/(Nm²)`는 torque-current 손실 근사다.
모든 항을 합친 총 효율이 항상 90% 이상이라는 뜻은 아니다. 실제 shared-load budget과 손실 map은 후속이다.

정지 때는 `T×omega=0`이어도 토크를 내는 데 전류/손실이 필요하다. `P/omega`만 계산하면
0으로 나누거나 정지 토크를 무제한으로 만드는 오류가 생긴다. 이 fixture는 `kT²` 때문에 정지에서도
유한한 한계를 갖는다. 1000 W discharge에서 reserve 200 W를 빼면 800 W가 남고,
정지 토크는 약 282.8 Nm, 20 rad/s에서는 약 35.4 Nm다. Motor torque/기계 power 한계도 함께 적용한다.
Valid 0 W discharge는 정지 출발도 막는다. 아직 actual electrical current/FOC를 검증한 것이 아니다.

### 충전 한계에서 회생 한계로

```text
Tregen <= min(motor speed envelope, charge_power_limit / omega)
```

실제 회수 power는 손실이 있으면 기계적 power보다 작다. 이번 limiter는 최악에 전부 배터리로
돌아올 수 있다고 보고 `Preturn <= |T|×omega`의 상한을 쓴다. 회수 효율 100%로 에너지를 적분한다는 뜻은 아니다.
20 rad/s에서 3000 W 충전 허용이면 회생 가용량은 최대 150 Nm다. Motor 한계가 더 작으면 그 값을 쓴다.
Source/측정 입력은 계산에 사용한 실제 원천을 보존하고 BmsBatteryState SOC만 읽어 한계를 대신 만들지 않는다.

저속에서는 나누기 전에 taper를 적용한다. Fixture는 ≤2 rad/s에서 회생 0, 2..5 rad/s에서
선형 증가, ≥5 rad/s에서 full torque envelope다. 정지 유지는 마찰 브레이크의 후속 책임이다.
속도 hysteresis, 실제 효율·전류/온도 map과 calibration을 확정한 것이 아니다.

| Fixture | 값 |
| --- | --- |
| Command / physical torque | −300..500 / −200..300 Nm |
| Motor mechanical propulsion / regen | 20 / 10 kW |
| Operational speed maximum | 100 rad/s |
| Local HV operating range | 300..450 V + ready/no fault |
| Normal / protection response | 1000 / 2000 Nm/s, 정상 목표 delay 50 ms |
| Control period / max gap | 10 / 30 ms |
| Local source age / dependency age / skew | 30 / 30 / 20 ms |

## 0과 unknown, 목표와 actual

| 상황 | 처리 |
| --- | --- |
| Normal BMS의 valid charge 0 | 회생 가용량 0/ChargeAcceptanceLimited, 구동 한계는 독립 |
| 저속/정지 | 회생 가용량 0/MotorOrSpeedLimited |
| Known Inhibit 또는 local latch, 필수 관측 known | 사용 금지 0/Disabled |
| Speed/HV/limits/permission unknown·stale | capability unknown/InputsInvalid; old 값으로 fallback하지 않음 |
| Actual torque known, capability unknown | actual을 별도로 계속 보고하며 sender FAIL_SAFE와 구분 |

예를 들어 BMS charge limit가 갑자기 0이 되면 **목표는 0, 실제 토크는 유한 rate로 감소**한다.
예전 delay FIFO에 있던 −200 Nm가 나중에 다시 적용되면 안 된다. 공유 TorqueResponse의
`constrain`이 active/queued/staged goals를 현재 envelope 안으로 제한한다. 한계가 회복돼도
이미 축소한 옛 목표를 되살리지 않는다. 새 큰 목표는 다시 정상 delay를 거친다.

Bound 밖의 actual은 protection rate로 수렴하며 `actual_outside_envelope`로 노출한다.
**잔여 음수 actual 동안 배터리 충전이 즉시 0이 됐다고 주장하지 않는다.** Full SOC/headroom/
power reaction·braking deficit budget을 energy coupling 전에 검토해야 한다. SOC/전력을 clip해서
장부를 맞추거나 command 0을 actual 0으로 바꾸지 않는다.

## INIT, fault와 원천 시각

Startup에는 known zero Command·Inhibit·센서를 먼저 보내 순환 의존을 피한다. Fresh Inhibit와
알려진 HV OFF는 non-driving INIT로 유지할 수 있다. 첫 입력들의 도착 순서만으로 정상화/활성화하지 않는다.
각 critical stream은 기존 80 ms startup monitor를 유지하므로 실제 coordinator의 INIT 순서는 후속 계약이다.

활성화 뒤 허가 상실/만료, BMS protection, 필수 입력 loss, HV/inverter fault, overspeed나
continuity/deadline에는 zero-target을 latch한다. 정상 센서나 fresh Enable만으로 복귀하지 않는다.
새 trusted application Epoch가 필요하며 physical torque/model Epoch는 계속 유지한다.
Clock rollback은 physics/output을 중단하고 missed interval은 hold한다. 늦은 새 입력을 받기 전에
기존 age/expiry를 검사해서 tick 사이의 loss를 숨기지 않는다.

Wheel SourceTime은 acquisition time, CapabilitySourceTime은 계산 시각이다.
CapabilityInputTime은 사용한 local/limits/permission/parent의 **가장 오래된 dependency**다.
Cached sample의 source/input/value는 불변이다. 물리 속도가 같아도 새 acquisition과 old hold를 구분한다.
한 grant의 추가 ancestor 때문에 dependency가 이전 발행보다 뒤로 가면 capability를 unknown으로 생략한다.
Timestamp를 올려 freshness를 꾸미지 않는다. Receiver는 capability dependency 70 ms를 명시적으로
선택하고 wheel/capability source·actual torque의 30 ms 정책은 유지한다.

## 실행과 범위

```sh
cmake -S . -B build/m1-angle
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
build/m1-angle/actuator_demo drive-gated normal
build/m1-angle/actuator_demo drive-gated charge-zero
build/m1-angle/actuator_demo drive-gated permission-loss
build/m1-angle/actuator_demo drive-gated hv-loss
build/m1-angle/actuator_demo drive-gated speed-stale
build/m1-angle/actuator_demo drive-gated limits-stale
```

Demo는 BmsController의 실제 계산 결과를 명시적 relay fixture에서 원천 보존한 뒤 전달한다.
Central grant/parent는 독립 fixture다. HV voltage는 PowerModel의 actual, inverter-ready·wheel speed·
SOC/thermal/cell spread는 명시적 sensor fixture다. 초기 130 ms까지 zero/Inhibit를 보낸다.
이후 구동→회생을 요청하며 normal은 SOC 제한·회복·저속 taper, charge-zero는 SOC 1 주입으로
회생만 막히는 경우다. 나머지 네 case는 local zero/latch와 valid zero/unknown 차이를 보여 준다.

Gate 단계 시점 normal·ASan/UBSan 전체 unit은 334개였다(새 gate 37개 + physics 4개).
여섯 demo, 정적 분석/production build와 [품질 기록](../quality_policy.md)을 구분한다.
기존 isolated Drive model vCAN 3개도 normal·sanitizer 각각 재검사해 통과했다. 실행은 기존 안내와 같이
`unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --build-dir build/m1-angle --family model --model drive`다.
Sanitizer는 build-dir을 `build/m1-angle-sanitized`로 바꾼다. 이전 97개 전체 vCAN 기록은 별도 이력이며
이번 세 case의 재검사를 EV gate의 transport/전체 차량 통합 시험으로 확대하지 않는다.

이 문서의 `drive-gated` 예제는 actual DC/SOC 충전을 적분하지 않는다. 이후 [Drive energy loop](m2_drive_energy.md)는
이상적 HV 경로에서 실제 torque·speed·손실과 BatteryModel SOC를 연결했다. Interval/oldest dependency,
shared reserve·finite residual/headroom을 검토했다. [실제 RC/접점 연결](m2_ev_power_circuit.md)도
별도 combined loop로 구현·시험했다. 다음은 M2 수용 검토와 M3 timing 준비다.
Central 배분/vehicle motion·정지, Target timing, 실제 RTE/OS/BSW와 전체 차량 TC는 후속이다.
