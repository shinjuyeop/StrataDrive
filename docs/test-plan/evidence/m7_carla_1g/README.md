# M7-1g — 실제 wheel 센서와 native Actual 반환 연결

2026-10-23. HEAD `7a2b0fa` + 기존 미커밋 M7-1a~1f 작업에서 수행했다.
**부분 연결 완료, 정상 제어 주행은 미완료**다. M6 구현·계약·종료 판정은 변경하지 않았다.
CARLA 소스 빌드, 임의 rad/Nm/Pa 계수, AI/Jetson 작업은 하지 않았다.

## 실제로 연결한 경로

```text
CARLA PhysX wheel omega (4개, 단일 telemetry RPC)
  → 원래 frame/run/actor/sim-time 검사 → rear 두 wheel의 산술평균
  → native LocalSensors → Drive vECU → 원래 DriveActual CAN/P05
  → Rear Zone → Central feedback → 읽기 전용 audit
```

실제8-role의 Prepare/INIT/Release/RunLease·Central 요청→Zone→vECU 경로는1f의 원래 actor를
사용한다. CARLA omega만 ECU 센서에 연결했다. torque/steer/pressure·전기 모델은 여전히
M6 actuator/electrical **시험 fixture**다. 해당 Actual을 CARLA에 적용하지 않는다.
CARLA 이동은 경사면 중력에 의한 무동력 관측이며 controller 가속 성공이 아니다.
fixture 에너지는 wheel=0을 사용하므로 실제 CARLA 운동의 에너지로 사용할 수 없다.
rear 평균은 기존 프로젝트 센서 포트의 관측 연결일 뿐 mkz의 drivetrain/축 배분 calibration이 아니다.

## 공식 근거와 실측의 구분

앞선1e/1f 계획이 놓친 `get_telemetry_data().wheels[].omega`를 설치 패키지에서 발견했다.
각도 차분 대신 직접 물리 각속도를 선택했다. 과거 evidence의 당시 조사 기록은 수정하지 않았다.

* [CARLA0.9.16 구현](https://github.com/carla-simulator/carla/blob/0.9.16/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Vehicle/CarlaWheeledVehicle.cpp#L829):
  physics scene read lock 안에서4wheel의 `mWheelsDynData.getWheelRotationSpeed(w)`를 읽는다.
* [PhysX3.4 API](https://github.com/NVIDIAGameWorks/PhysX-3.4/blob/master/PhysX_3.4/Include/vehicle/PxVehicleWheels.h):
  wheel rotation speed 단위는 rad/s다. angle unwrap/차분 구간 추정은 이 입력에 필요하지 않다.
* [CARLA RPC payload](https://github.com/carla-simulator/carla/blob/0.9.16/LibCarla/source/carla/rpc/VehicleTelemetryData.h)는
  frame/time을 포함하지 않는다. 단일 tick owner가 tick 완료 후 RPC 전후 같은 snapshot을 확인해
  해당 frame에 결부한다. 서버 timestamp 내장 센서로 주장하지 않는다. 임의 외부 client를 차단하는 인증 시험도 아니다.
* 같은 소스의 `torque`는 `DebugWheelTorque`다. 실측에서 `torque ≈ -long_force × radius`이고
  내리막 최대 잔차는0.000479Nm였다. 이는 타이어 접촉 반력 성격과 일치하는 **추론**이며,
  native Drive Actual/모터축 torque로 사용할 근거가 아니다.
* [공식 Python API](https://carla.readthedocs.io/en/0.9.16/python_api/)의 VehicleControl은 normalized
  throttle/brake/steer다. 설치 메서드 목록과 source에서 per-wheel Nm/Pa 제어 포트를 확인하지 못했다.
  engine/gear/clutch dynamics가 켜진 기존 vehicle에 단순 `Nm/max`, `Pa/max`를 적용하지 않는다.

[공식 source 원문·URL·SHA](sources/manifest.json)7개와
[설치 모듈/실제 wheel index](environment.json)를 남겼다. 소스 tag와 runtime 관측을 대조한 것이며,
실행 binary가 해당 source로 재현 빌드됐음을 증명한 것은 아니다.
OpenDRIVE map survey의 첫 raw pitch 정렬 오류는 [원본](map-survey.json)에 보존하고,
forward-vector.z로 교정한 [결과](map-survey-corrected.json)를 사용했다.

## 시간·입력 계약

* functional domain `0x4d3746554e435449`, scope(run1/application42/plant7), trusted actor ID 고정.
  source는 원래 snapshot elapsed seconds를 ns로 반올림한다. raw seconds도 저장한다.
* 4wheel telemetry는 source=oldest로 공급한다. 각속도 차분값이 아니다. 뒤쪽 index2/3의 평균을
  원래 nonnegative Drive port에 넣고 원래 CAN0.01rad/s 양자화를 거쳐 반환한다.
  역회전·NaN·범위 초과·잘못된 actor/frame/scope·중복·누락은 거부한다. abs/clamp/restamp 없음.
* native0.2ms ingress/1ms fixture와10ms CARLA 시각은 정확히 정렬되지 않을 수 있다.
  최대2개 대기 샘플을 원래 source 순으로 보존하고 `source<=job_time`일 때만 소비한다.
  이전 작업에 미래 sample을 소급하거나, 아직 소비하지 않은 이전 sample을 덮어쓰지 않는다.
* Controller20ms/Zone·leaf10ms/BMS20ms 및 기존30ms freshness/credit 조건은 그대로다.
  이번 live oracle은 반환 wheel의 age+다음10ms<=30ms를 확인한다. 전체 Actual의
  oldest/expiry/support·1c apply admission이나 wall2ms/4ms deadline 수용을 대체하지 않는다.
* pause 동안 STEP/tick을 모두 멈추며 source/lease 갱신도 없다. fault는 process latch다.
  새 process/scope의 INIT 필요. 이번 live world reset·source timestamp 서버 확장은 NOT RUN이다.

## 실행 결과와 실패

동일0.9.16 server/bundled Python3.10 client, physics ON,10ms fixed tick, ego
`vehicle.lincoln.mkz_2020`, cameras0/traffic0. 경사 fixture는 Town03_Opt road73/lane1/s30의
pose에서 z+0.35m로 초기 spawn했다. 설정/physics readback·pose·메서드 목록·raw frame은 각 capture에 있다.

| 시도 | 결과 | 의미 |
| --- | --- | --- |
| [01 slope](attempt01-slope/process.json) | FAIL | packaged startup map 인자가 무시돼 Town10HD_Opt가 반환됨. 맵 불일치 시 중단, actor 생성 없음 |
| [02 slope](attempt02-slope/oracle.json) | wheel 관측400/400, native NOT RUN | fresh client process의 load_world 성공. 실제 비영 각속도·동일 frame 반복 RPC 확인 |
| [03 native slope](attempt03-native-slope/capture/summary.json) | FAIL, index11에서 보호 | ns 단위 grid 오차로 미소비 sample이 덮어써져 source가50ms 이상 정체. 원래 freshness 경로가 gate를 닫음 |
| [04 native slope](attempt04-native-slope/oracle.json) | 관측/반환 경로 한정 PASS400/400 | 대기열 수정 후396개 반환 wheel,322개 armed fixture frame. 최대 source age10ms, 기존 CAN 양자화 오차0. 250ms pause 및 duplicate 후 tick0 확인 |
| [05 native flat](attempt05-native-flat/capture/summary.json) | FAIL, index32에서 거부 | 초기 접지 때 rear omega=-2.4058085301703613e-8rad/s. 기존 전진 전용 범위를 보존하여 거부 |
| [06 flat 관측](attempt06-flat-observation/oracle.json) | wheel 관측400/400, native NOT RUN | 총74frame에 rear 음수, 최소-4.784922111866763e-7rad/s. 최대 절대5.396442475102958e-7rad/s. 단순 초기1회 현상으로 단정 불가 |

02/04의 무동력 이동은 y방향 약16.657m, 최고 전방속도8.692605m/s, 최고 wheel39.102882rad/s다.
body speed/radius로 wheel을 만들지 않았다. slip/contact/airborne가 섞인 관측이며 slip 보정·
전 범위 부호/정밀도 calibration이나 실제 역주행 시험은 아니다.

**6시도 모두 서버 SIGTERM 종료139**. 자기 actor 잔존0·설정 복원과 포트 정리는 확인했으나
종료 성공으로 집계하지 않는다. 기존 OPEN-M7-1D-01 유지. startup map 문제는 fresh-client
load로 우회했으며 같은 client의 reload crash가 해결됐다고 주장하지 않는다.

## 코드 검증과 보존

Normal/ASan **각22/22**: 기존1f14 + 신규 wheel8. 실제 원천/반환 양자화·미래 입력 금지·
fractional timestamp·missing/actor/source/scope/reverse/NaN·moving INIT 거부를 확인했다.
[최종 Normal](tests-pending-fix.txt), [최종 ASan](tests-asan-pending-fix.txt),
[기존 회귀](regression.json): 기존 관련144/144 +1c39/39. M6 전체 suite를 새로 실행한 것은 아니다.
[독립 raw oracle 변조시험](oracle-negative.json)은 source restamp/값/actor/frame/permit/drive/credit
변조7/7을 거부했다. reader 테스트를 실제 actuation single-writer 수용으로 확대하지 않는다.

최초 build는 CMake 재구성 전 target 없음으로 실패했다. 최초 native tests19/21은 잘못 쓴
시험 기대값(CAN resolution0.0001 대신 실제0.01, Prepare1s 대신 실제2s) 때문에 실패했다.
기존 코드·계약은 그대로 두고 기대값을 교정했다. 그 뒤 live03에서 위 실제 pending 버그를 발견했다.
초기 로그·[시험 원본](wheel_test_initial.cpp)·[수정 전 native](native_before_pending_fix.tar.gz)를 보존했다.
1f helper 확장 전 [source archive](m7_1f_sources_before_extension.tar.gz)도 보존했다.
1a~1f evidence를 수정하지 않는다. 이번 최종 코드 hash는 `sources-harness.json`, evidence는 `SHA256SUMS`다.

## 재현

```bash
cmake -S . -B build/m7-functional -DBUILD_TESTING=ON -DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON -DSTRATADRIVE_M7_CONTRACT_TESTS=ON
cmake --build build/m7-functional --target m7_wheel_test m7_wheel_shadow m7_functional_test -j 6
ctest --test-dir build/m7-functional -R 'M7(Wheel|FunctionalNative|FrameClock)' --output-on-failure
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -I tests/integration/carla/m7_1g_wheel.py --server /d/shin/stratadrive-tools/carla-0.9.16/server --map Town03_Opt --fixture slope --native build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow --output /tmp/m7-wheel-new-run
python3 tests/integration/carla/analyze_m7_1g.py /tmp/m7-wheel-new-run
```

기존 port 점유 시 중단하며 전용 서버만 종료한다. 원본 output 경로는 덮어쓰지 않는다.
oracle exit0은 센서/반환 한정이며 JSON의 server_shutdown FAIL을 별도로 읽어야 한다.

## 다음 작업 / 정상 주행 차단 사유

1. **M7-1h 센서 의미:** 정지 부근 signed omega·측정 분해능·validity를 정의한다. 실제 음수 잡음과
   역회전을 어떻게 구분할지 근거를 확보하고 simulator sensor port에서 처리할 계약을 정한다.
   이번 작업은 임의 epsilon/abs/0 clamp를 추가하지 않았다.
2. **actuator-only backend 분리:** 실제 wheel 입력을 받는 새 M7 물리/전기 포트와 work interval을
   분리한다. 현재 fixture의 wheel0 에너지/동특성을 CARLA 에너지로 승계하지 않는다.
3. **rad/Nm/Pa actuation 방식 확정:** packaged engine/clutch/gear와 기존 actuator dynamics의 중복,
   brake hydraulic→wheel torque 근거, steering 역변환을 해결한다. 패키지 역변환의 검증 가능한
   범위와 timestamp/직접 wheel torque를 노출하는 서버 확장안을 비교해야 한다. 소스 빌드는 별도 범위다.
4. 이후 원래3Actual provenance·interval/expiry를 받아 **Plant Adapter만 apply→ACK→tick**하도록
   연결하고 가속/제동/조향·loss/pause/reset 보호 응답을 시험한다.

따라서 wheel→Actual 반환의 실제 연결은 가능함을 확인했으나, 평지 일반 연결 및 정상 제어 주행은
여전히 BLOCKED다. CARLA throttle을 Central command에서 직접 만들어 성공처럼 보이게 하지 않았다.
