# 차량 시동·배분·종료

## 역할과 읽는 순서

Central은 vehicle management·allocation·session의 단일 owner다.
Front는 Steering/Brake, Rear는 Drive/BMS/Power gateway이며 차량 전체 배분을 다시 하지 않는다.
전체 실행 경계는 [아키텍처](../architecture/README.md)를 따른다.

| 순서 | 코드 | 확인할 것 |
| --- | --- | --- |
| 1 | `central/session/`, `interfaces/session/` | trusted Epoch, 8-role Prepare/INIT/Release·정확 ACK·deadline |
| 2 | `central/vehicle_management/` | 원천 power/health·RunLease·READY/permission·FAIL_SAFE latch |
| 3 | `central/control_allocation/` | 검증된 요구·capability·Actual로 angle/torque/pressure 배분 |
| 4 | `zone/command_validation/`, `gateway/` | scope·parent/expiry·atomic pair·bounded TX·partial failure |
| 5 | `zone/feedback/`, `local_safety/` | Leaf별 실제 상태 감시·독립 보호 선택과 receipt |
| 6 | `central/coordinator/`, `simulation/runtime/` | 정상 async 실행·NormalStop·terminal handoff·재가입 |

## 시동과 권한

새 세션은 신뢰한 계획과 durable Epoch에서 시작한다. Application 세션과 physical model
세션은 별도라서 ECU 재가입만으로 모델 위치·SOC를 reset하지 않는다.
Power READY, actual sensor 유효, Release ACK, arm, normal permission은 각각 별도 gate다.
양 Zone과 필수 Leaf가 준비되기 전에 normal output을 내지 않는다.
NonDriving 상태에서도 초기화·상태 보고·보호를 검사한다.

Drive는 BMS limit·Central permission·로컬 HV/speed를 확인한다.
Fresh torque/speed가 있어도 regen capability는 unavailable일 수 있다.
유효한 회생 한계0과 unknown을 구분하고 원래 조건에 맞는 마찰제동 경로를 사용한다.

## 배분·전달·보호

VehicleRequest·상위 명령·하위 명령·Actual·ACK를 따로 기록한다.
원래 source/oldest·parent·expiry를 각 hop에서 보존하고 새 publication으로 기한을 늘리지 않는다.
Pending은 완료가 아니다. 처리 대기 중에도 원래 권한·freshness·deadline을 계속 감시한다.

Steering 송신 후 Brake가 실패하는 부분 성공도 존재한다. 정상 FIFO 포화·partial/error에서
보호 전달을 닫지 않고 latch/priority protection 경로를 실행한다.
Local fault는 Central diagnostics 승인 없이 보호한다. ACK는 선택/처리 증거이며 실제 압력·torque 도달은 별도로 확인한다.

## 작은 same-host 실행

Core를 빌드한 뒤 최초 한 번만 새 Epoch store를 만든다. 아래 출력 경로는 모두 새 경로여야 한다.

```sh
mkdir -p build/m4-manual
build/m1-angle/actuator_demo epoch init build/m4-manual/epochs
build/m1-angle/actuator_demo m4-async logical normal build/m4-manual/epochs build/m4-manual/normal
build/m1-angle/actuator_demo m4-async wall feedback-loss build/m4-manual/epochs build/m4-manual/loss
build/m1-angle/actuator_demo m4-async logical rejoin build/m4-manual/epochs build/m4-manual/rejoin
```

Logical 기능과 wall 관측은 별도다. 이 예제는 실제 SOME/IP 배포를 대신하지 않는다.
실제 IP·SDK·RT 조건과 재실행은 [3-process SOME/IP 근거](../test-plan/evidence/m5_someip_rear_adapter/README.md),
차량/EV 물리 완료는 [M6 최종 실행](../test-plan/evidence/m6_physical_response/README.md)을 따른다.

## 정상 종료와 재가입

NormalStop은 stop intent 뒤 실제 torque·압력·속도 등의 조건과 dwell을 확인하고,
terminal ACK 후 Shutdown/HV-off를 진행한다. 단순히 permission을 내리거나 torque0을
요청하는 것과 실제 정지·전원 OFF는 다르다. Fail-safe 종료와 정상 종료도 별도 판정이다.
명령/Actual loss·process 재시작·이전 세션 replay 뒤에는 새 trusted INIT와 power/health를 재검증한다.
