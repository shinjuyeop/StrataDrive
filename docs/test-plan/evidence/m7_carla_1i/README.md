# M7-1i — 직접 wheel effort 방식과 정지 센서 계약 검토

2026-10-23. 시작 시 HEAD `7a2b0fa` + 기존 미커밋 M7 작업이었으며, 작업 중 이전1a~1h 묶음이
`5017785`로 커밋된 것을 확인했다. 완료 시 비교 기준은 `5017785`, 이번1i는 미커밋 변경이다.
이전 evidence468개와 보호 대상 M6 파일의 불변 여부를 다시 확인했다.
**변환 방식 조사·오프라인 prototype 검증 완료. 정상 CARLA actuation/주행은 미완료**다.
이번에는 CARLA 서버 실행·source build·설치 변경·실제 제어 입력을 수행하지 않았다.
M6 구현/계약/기존 수용과1a~1h 원본을 변경하지 않았다.

## 결정과 근거

| 항목 | 판단 |
| --- | --- |
| stock `VehicleControl` 역변환 | 정상 연결 경로로 미채택. wheel Actual 뒤 engine/clutch/gear 동특성이 붙으며 현재 공개 관측으로 정확한 제거/역변환을 입증하지 못함 |
| 우선 구현 후보 | 서버의 `PxVehicleNoDrive` 기반4wheel effort 포트. 엔진 없이 suspension/tire/wheel/chassis를 유지하고 signed motor Nm·friction Nm·steer rad를 별도로 받는 구조 |
| 현재 package 적합성 | 설치된0.9.16 Python binding에는 이 직접 effort 포트가 없음. 소스 확장/빌드가 필요하며 이번에는 하지 않음. 다른 backend가 원천적으로 불가능하다는 증명은 아님 |
| Pa→Nm | 수치 미확정. wheel max brake800Nm는 상한이며 hydraulic pressure와 연결하는 근거가 아님. 실제 데이터/명시적 가상 brake 모델 수용 전 table unavailable |
| 정지 미세 음수 | sensor noise로 단정 불가. 전진 ODD와 strict validity 유지, epsilon/abs/clamp 미채택. 실제 보호 brake 적용 후 물리 관측으로 재시험 |

설치 binding은 [새 read-only audit](binding-and-trace-audit.json)으로 조사했다.
`Vehicle`과 telemetry의 전체 공개 멤버를 기록했고, 이전400+33+400개 frame을 재분석했다.
**과거833개 sample의 재분석**이며 새 runtime 성공833개가 아니다. API 이름 검사만으로
capability 부재를 판단하지 않고 다음 공식 소스/문서와 대조했다.

* [CARLA0.9.16 API](https://carla.readthedocs.io/en/0.9.16/python_api/),
  [DefaultMovementComponent](https://github.com/carla-simulator/carla/blob/294096eb1c38eabf246e4f3a9cdab704e33a7f4c/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Vehicle/MovementComponents/DefaultMovementComponent.cpp):
  normalized input을 stock movement component에 전달한다. `set_wheel_steer_direction`은
  physics-on steering 입력이 아니다.1g의 CarlaWheeledVehicle.cpp/API 원본 근거도 유지한다.
* [PhysX3.4 NoDrive](https://github.com/NVIDIAGameWorks/PhysX-3.4/blob/5e42a5f112351a223c19c17bb331e6c55037b8eb/PhysX_3.4/Include/vehicle/PxVehicleNoDrive.h),
  [공식 차량 가이드](https://github.com/NVIDIAGameWorks/PhysX-3.4/blob/5e42a5f112351a223c19c17bb331e6c55037b8eb/PhysX_3.4/Documentation/PhysXGuide/_sources/Manual/Vehicles.txt):
  개별 wheel drive/brake torque와 steer angle을 제공한다. setter 값은 다음 호출까지 지속되므로
  frame/expiry/owner 검사를 갖춘 서버 측 wrapper가 추가로 필요하다.
* [PhysX vehicle update](https://github.com/NVIDIAGameWorks/PhysX-3.4/blob/5e42a5f112351a223c19c17bb331e6c55037b8eb/PhysX_3.4/Source/PhysXVehicle/src/PxVehicleUpdate.cpp):
  NoDrive의 signed motor 입력과 nonnegative brake를 분리하며 engine dynamics가 없다.
  wheel inertia/damping·tire/suspension은 여전히 vehicle plant 책임이다.

새 소스6개는 [manifest](sources/manifest.json)에 exact commit/URL/SHA256을 고정했다.
이 upstream PhysX commit이 **현재 packaged UE의 exact 소스**라는 보장은 없으므로 확장 빌드 시
fork/commit/scale 검증을 별도로 요구한다. UE5/PhysX5 문서는0.9.16 근거로 사용하지 않았다.

## 구현·실제 시험

[wheel_effort.hpp](../../../../tests/integration/carla/m7_1i/wheel_effort.hpp)는 CARLA와 독립적인
수학 prototype이다. 이상 Ackermann·이상 open differential의 rear50/50·명시적 per-wheel
pressure table을 사용한다. geometry/table은 **합성 test vector**이며 mkz calibration이 아니다.
Nm→kg·cm²/s²의10000배는 차원 변환으로 별도 검증했다. 음수 motor를 friction에 합치지 않는다.

기존1c Actual/P05 boundary 뒤 fake backend로 연결했다. Command frame은 모든 actuator에서
거부하고 원래 source/oldest/expiry·CAN bytes를 보존한다. 범위를 벗어난 유효 Actual도 apply/tick
전에 거부한다. `CarlaDriving`은 Disabled이며1f/1g/1h live harness에는 연결하지 않았다.

* [Normal](tests-normal-final.txt) / [ASan](tests-asan-final.txt) 신규 **각16/16**.
  독립 조향 기하 invariant, signed torque/마찰 분리, 비대칭 wheel speed의 power conjugacy,
  table 누락/역행/상한·NaN/overflow·외삽 거부, 원래 Actual 경계와 driving 차단을 검사했다.
  초기 Normal14/14 후 식별 불가능성·pressure 범위 거부2개를 추가했다. 초기 로그도 보존한다.
* [기존 M7 회귀](m7-regression.json):1c39+1f14+1g8+1h10, Normal/ASan **각71/71**.
  전체 M6 suite 또는 실제 ECU/CARLA control 전달의 새 수용은 아니다.
* [첫 회귀 시도](regression-attempt01.json)는 Normal71 완료 후 ASan1c binary 미빌드로
  실행 중단했다. 실패 원본을 보존하고 해당 target 빌드 후 ASan을 실행했다. 미실행을 PASS로 쓰지 않았다.
* [기존 evidence 무결성](historical-integrity.json):1a~1h SHA256 대상468개 모두 불변.
  기본 M7 옵션OFF build의 target 목록에 새 test가 나타나지 않음을 확인했다.

## 정지 센서와 실제 주행의 남은 조건

과거 평지 관측400개에서 rear 음수74개, 최소 평균-4.784922111866763e-7rad/s였다.
1h native 평지에서는33번째 관측(index32)의-2.4058085301703613e-8rad/s에서 멈췄다.
이 값은 보편적 error bound가 아니다. 당시에는 **CARLA에 보호 Brake Actual이 적용되지 않은
자유 낙하/접지 상태**였다. 정상 brake-hold의 센서 오류를 검증한 시험으로 해석하지 않는다.

PhysX update의 brake lock/vehicle sleep은 실제 물리 상태를0으로 만들 수 있다. 이는 client
측 negative-to-zero 처리 허용과 다르다. 현 package에는 frame-stamped contact/sleep/effort
receipt가 없고, 현재 음수가 부동소수점 오차인지 실제 미세 역회전인지 확정할 근거도 없다.
원래 source/값을 보존한 strict rejection을 유지한다. **brake 적용 시 해결된다는 live 결과는 없다.**

[ICD v6](../../../archive/carla-history.md#icd-m7-1i--직접-wheel-effort-확장안)에
stage ACK와 post-physics receipt 구분, single-use frame token, expiry·pause/reset,
signed motor work/friction loss 분리와 단일 EV owner 전환 조건을 정리했다.
1h의 `MODEL_ZOH_UNAPPLIED`는 여전히 예측이다. interval work와 SOC/회생 수용은 NOT RUN이다.
기존 서버 종료139/동일 client reload 문제·wall2ms/4ms 수용도 이번 조사로 해결되지 않았다.

## 다음 구현을 나눌 단위

1. **M7-1j-a, 별도 source build 범위:** CARLA0.9.16 fork/UE/PhysX commit을 고정하고 단일 ego
   NoDrive movement component·4wheel effort/관측 포트 구현. 기존 stock drivetrain과 동시 실행 금지.
   현재 source build 제외 범위를 바꾸는 명시적 작업 지시가 선행한다.
2. **M7-1j-b, calibration artifact:** 실제 local geometry/휠 부호·축별 한계 확인, pressure→torque
   근거 데이터 또는 가상 hydraulic/disc 모델과 수용 기준 확정. 임의 M6 gain 복사 금지.
3. **M7-1j-c, 연결 시험:** 원래8-role Actual 반환→유일 adapter→frame receipt→단일 tick 연결.
   보호 brake-hold/정지·출발·정지, reverse/mixed·누락·pause/reset·중복 writer 거부부터 검증한다.
4. 그 뒤 solver interval work를 EV에 한 번만 전달하고 actual-only 가속/제동·에너지 시험을 수행한다.
   M8 controller 폐루프·AI/Target은 이 한정 연결과 별도다.

```bash
cmake -S . -B build/m7-functional -DBUILD_TESTING=ON -DSTRATADRIVE_M7_CONTRACT_TESTS=ON -DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON
cmake --build build/m7-functional --target m7_effort_contract_test -j 6
ctest --test-dir build/m7-functional -R '^M7Effort' --output-on-failure
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -I tests/integration/carla/m7_1i_audit.py --repo /d/shin/StrataDrive --output /tmp/m7-1i-new-audit.json
```

실행 artifact hash는 `SHA256SUMS`, 소스/binary hash는 `sources-harness.json`에 둔다.

이번 변경 파일은 root `CMakeLists.txt`, `tests/integration/carla/m7_1i/{CMakeLists.txt,
wheel_effort.hpp,effort_test.cpp}`, `tests/integration/carla/m7_1i_audit.py`, root `README.md`,
`docs/{project_status.md,roadmap.md,icd/carla_plant_adapter.md,test-plan/m7_carla_preflight.md}`와
이 evidence 디렉터리다. 기존 runtime/harness와 M6 파일은 수정하지 않았다.
