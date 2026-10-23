# M7-1h — signed wheel validity와 별도 actuator/electrical 포트

2026-10-23. HEAD `7a2b0fa` + 기존 미커밋 M7 작업에서 수행했다.
**M7 전용 actuator/electrical owner 구현·한정 검증 완료. 평지 일반 연결과 정상 CARLA 제어 주행은 미완료**다.
M6 코드·wire·주기·freshness·종료 판정과1a~1g 원본 evidence를 변경하지 않았다.
소스 빌드, CARLA actuation, AI/Jetson 작업은 수행하지 않았다.

## 변경한 경계

`--external-wheel-plant`는 기존 `--wheel-shadow`와 구분되는 명시적 opt-in이다.
기존 모드의 stationary PhysicalOwner 대신 M7 전용 `ActuatorElectrical`을 생성한다.
기존20ms Controller/10ms Zone·leaf/20ms BMS와8-role native 권한·Actual 경로는 유지한다.

```text
CARLA 원래 4wheel acquisition
  ├─ strict validity → ECU LocalSensors → DriveActual/P05 → Rear → Central
  └─ 원래 source의 history → 각 1ms 구간 시작 이전 sample 선택
       + 이전 구간까지의 실제 actuator response torque
       → EvPowerModel(ZOH) → circuit/battery model → BMS/Power 관측
```

새 owner는 SteeringResponse/BrakePressureResponse/DriveSilPlant와 EvPowerModel을 합성한다.
SimpleVehicle/VehicleEvModel은 생성·step하지 않는다. 같은 실행에 기존 PhysicalOwner를 병행하지 않는다.
actuator·battery·circuit 설정은 명시한 기존 M6 functional fixture 값이며 CARLA/OEM calibration이 아니다.
ECU output은 actuator 응답 모델에만 적용하며 CARLA 입력으로 우회하지 않는다.

**에너지 의미:** `EvPowerModel::step`의 기존 beginning-speed ZOH를 재사용한다.
`ΔW = Tactual(begin) × ωacquired(begin 또는 이전) × Δt`이며 held wheel의 source/oldest를 유지한다.
`MODEL_ZOH_UNAPPLIED`, `carla_work_valid=false`를 매 native 결과에 기록한다.
CARLA에는 이 torque가 적용되지 않았으므로 계산값은 **모델 예측**, CARLA의 실제 motor work/회생/SOC가 아니다.
1g의 wheel0 전기 fixture와 구분되지만 full `IntegratedMotorWork`/apply receipt 포트는 후속이다.
전체 vehicle/electrical 에너지 보존 수용이나 M6 energy fidelity 승계를 주장하지 않는다.

## 정지 부근 signed wheel 결정

[기존 codec](../../../../interfaces/drive/drive_value_codec.hpp)은 범위를 **반올림 전** 검사한다.
0.01rad/s CAN resolution은 음수 측정값을0으로 바꿀 수 있는 오차 허용 근거가 아니다.
1g에서 관측한 최소-4.78e-7rad/s를 보편적 noise bound로 확정하지 않았다.

| 관측 | M7 분류 / 처리 |
| --- | --- |
| 모든 값 finite·범위 내, 두 rear>=0 | 원래 rear 산술평균을 그대로 forward sensor에 전달. port에서 재양자화하지 않음 |
| rear에 음수, 양쪽 rear가 abs(value)<0.005rad/s | `SubResolutionNegative`: 기존0.01 resolution의 zero bin에 해당한다는 **진단만** 제공. forward 값 unavailable, latch/next tick 거부 |
| 그 외 rear 음수/혼합 방향 | `ReverseOrMixed`: 기존 전진 ODD 밖, 거부. 평균으로 상쇄하지 않음 |
| 결측·NaN·range·잘못된 identity/time | 원래 source 검사와 거부 유지 |

0.005는 기존 resolution/2인 진단 경계이며 accepted 범위를 넓히지 않는다.
float 오차인지 실제 미세 역회전인지 현재 정보로 확정할 수 없으므로 abs/clamp/epsilon/0 대입을 하지 않는다.
raw signed wheel·actor/frame/run/source는 항상 trace에 남긴다. 평지 문제는 **미해결**이다.

## 시간·원자성·출력 보호

* CARLA observation당 최대5개 원래 acquisition을 유지해 구간 **begin 이하**의 최신 sample을 선택한다.
  sample(end)를 이전 구간에 소급하지 않는다. ECU 센서 포트와 전기 구간 선택 시점은 구분한다.
* 기존 EV max age30ms/skew10ms·native Drive freshness는 그대로다. 전기 step은1ms 이내,
  모델 gap/결측/identity/미래 값/변조 cached sample을 거부하고 latch한다.
* actuator·회로·Battery·출력 cursor를 후보 상태로 계산한 뒤 함께 commit한다.
  전기 계산 또는 뒤따르는 output 검증 실패 시 모델 상태를 부분적으로 전진시키지 않고 센서를 unavailable로 만든다.
* output의 leaf/type·trusted application·source를 검사한다. BMS의 no-actuation publication은
  actuator watchdog을 갱신하지 않는다. 새 output의 과거/미래 application·미래/초기화 이전 시각·NaN을 거부한다.
* 출력 상실30ms 이후 기존 응답 모델에 zero torque/1MPa 보호 pressure를 선택한다.
  Power output 상실은 measured current/torque와 기존 dwell 후 coil을 해제한다. 모델 파라미터와
  nominal actual response를 사용하며 실제 차량 보호 응답의 수용 결과는 아니다.
* wheel/명령/에너지 근거가 invalid면 다음 NON_DRIVING tick도 발급하지 않는다.
  새 model/run은 새 object·INIT가 필요하고, 동작 중 sensor 수신으로 latch를 해제하지 않는다.

## 실제 실행

Server/bundled Python client0.9.16, world10ms, mkz_2020 physics ON, camera0/traffic0.
1g와 같은 Town03_Opt road73/lane1/s30 경사 spawn 및 Town10HD_Opt 평지 fixture다.
초기화 뒤 apply/teleport/force/velocity API 호출0, 단일 tick owner·250ms pause·마지막 duplicate 거부를 유지한다.

| 시도 | 결과 |
| --- | --- |
| [01 external slope](attempt01-external-slope/oracle.json) | 400tick, Actual wheel 반환396·armed fixture322. 3,989개1ms ZOH 구간 검증. 모델 work3017.486449415207J, 독립 누적 차이<=4.55e-13J |
| [02 external flat](attempt02-external-flat/capture/summary.json) | FAIL. index32에서 rear=-2.4058085301703613e-8rad/s. `SubResolutionNegative` 거부, native exit1. 에너지를 wheel0으로 대체하거나 추가 tick 발급하지 않음 |
| [03 final slope](attempt03-final-slope/oracle.json) | application/time output 검사 보강 후 최종 binary400tick·3,989구간 한정 PASS. 반환396·armed322, 모델 work3017.486449415207J·누적 오차4.55e-13J로01과 일치 |

원래 source의 최대 반환 age는01에서10ms, 전기 구간 끝까지 wheel dependency age는10.000089ms였다.
소수점 simulation timestamp를 native grid로 고치지 않았기 때문에 정수10ms를 약간 넘을 수 있으며
원래30ms age와10ms source skew 검사는 그대로 통과했다. 수집 끝의 아직 오지 않은 subjob은 계산하지 않았다.
무동력 중력 이동은 약16.657m이며 실제 CARLA 주행 controller/energy 연결 성공으로 해석하지 않는다.

총3live 시도 중2개 수집/예측 완료·1개 평지 연결 FAIL이며, **서버 종료139는3/3**이다.
actor 잔존0·설정 복원·포트 정리와 종료 실패를 각 process.json에 따로 기록한다.
기존 OPEN-M7-1D-01을 닫지 않는다. 같은 client reload·실제 wall deadline·카메라 부하·live world reset은 이번 시험 범위가 아니다.

## 검증

* [Normal](tests-normal-final.txt) / [ASan](tests-asan-final.txt) 각각 **32/32**: 기존1f14+1g8, 신규1h10.
  signed zero-bin 거부, held 원천 보존, 결측/미래/NaN/역회전/identity, 원래30ms dependency 만료,
  cached mutation, 실패 시 rollback,8-role/전기 work, 미래 endpoint 금지, fractional timestamp,
  출력 상실 뒤 실제 torque 감소와 pressure floor를 검사했다.
* [기존 관련 회귀](regression.json) **144/144**, 기존1c **39/39**. M6 전체 suite 재실행/재수용은 아니다.
* [최종 전기 oracle 변조](oracle-negative-final.json)7/7 및 [wheel oracle 변조](wheel-oracle-negative.json)7/7 거부.
  미래 source·가짜 wheel0·work/누적/구간/oldest 변조·CARLA work 허위 표기를 검출한다.
  전기 oracle은 `T×ω×dt`/시각/누적을 독립 계산한다. 모델 balance 필드만으로 전체 에너지 보존을 PASS로 쓰지 않는다.
* 초기31/31 cohort와 출력 상실 test 추가 후32/32를 구분해 보존했다. 이전 코드·evidence는
  [1h 전 source archive](m7_sources_before_1h.tar.gz)와 기존 SHA256SUMS로 확인한다.
  현재 source hash는 `sources-harness.json`, 실행 artifact는 `SHA256SUMS`다.

## 재현과 다음 단계

```bash
cmake -S . -B build/m7-functional -DBUILD_TESTING=ON -DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON -DSTRATADRIVE_M7_CONTRACT_TESTS=ON
cmake --build build/m7-functional --target m7_external_test m7_wheel_shadow m7_functional_test m7_wheel_test -j 6
ctest --test-dir build/m7-functional -R 'M7(External|Wheel|FunctionalNative|FrameClock)' --output-on-failure
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -I tests/integration/carla/m7_1g_wheel.py --server /d/shin/stratadrive-tools/carla-0.9.16/server --map Town03_Opt --fixture slope --native build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow --native-mode external-wheel-plant --output /tmp/m7-external-new-run
python3 tests/integration/carla/analyze_m7_1h.py /tmp/m7-external-new-run --output /tmp/m7-external-new-run/oracle.json
```

다음 M7-1i는 **정상 actuation을 가능하게 할 모델·변환 방식 결정**이다. 준비된 actuator/전기
포트와 CARLA의 engine/clutch/steering/brake dynamics 사이의 중복을 제거하고, rad/Nm/Pa 변환 근거,
정지 부근 signed sensor의 수용 가능한 오차/validity, applied Actual receipt·interval work를 정해야 한다.
패키지의 검증 가능한 역변환과 직접 wheel torque/timestamp를 노출하는 서버 확장 후보를 비교한다.
새 source build는 별도 범위다. 정규화 계수나 측정 오차를 임의로 정해 주행 gate를 열지 않는다.
