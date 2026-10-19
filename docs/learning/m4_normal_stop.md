# M4 정상 종료: 제동·정지 확인·Hold/Zero 인계·HV 종료

Date: 2026-10-19. Status: **Host component·vCAN 회귀 / 전체 차량·분산 runtime 후속**.
[ADR-0050](../adr/ADR-0050-controlled-stop-and-terminal-handoff.md)의 구현이다.

이번 흐름은 **명령을 0으로 보냈다는 사실과 실제로 멈춘 상태를 구분**한다.
정상 종료의 phase/권한을 연결한 단계이며 PID·ABS·차량 감속 feedback law를 새로 구현한 것은 아니다.

1. NormalStop이 제동 intent를 받고 Enable을 유지한다. 기존 allocator가 회생/마찰과 저속 hold를 계산한다.
2. 새 Actual의 speed·torque·pressure가 정지 조건을 만족한 채60 ms 진행됐는지 확인한다.
3. Trusted callback으로 두 gateway/allocator·세 Leaf를 terminal 상태로 넘긴다. 지연된 정상 목표·큐를 취소한다.
4. 선택 ACK 뒤에만 Shutdown을 요청한다. Drive는 정상적인 Inhibit를 받아 Zero를 유지한다.
5. 기존 PowerController가 current dwell→접점 open→bus discharge를 수행한다. 실제 OFF와 ACK가 있어야 Complete다.

정상 종료 때문에 기존 fault를 초기화하지 않는다. 중간 실패는 별도 protection으로 가고,
정상 출력이 없다는 사실을 Brake release나 물리 정지 성공으로 바꾸지 않는다.

후속 [실제 Zone 상태 감시](m4_zone_feedback_health.md)에서 아래 연결 시험의 Zone health fixture를
실제 gateway/원천 feedback monitor와 독립 status receiver로 교체했다. 아래 수치·fixture 설명은 최초 구현 이력이다.

후속 [단일 Central coordinator](m4_vehicle_coordinator.md)가 아래 실제 연결 시험의 Central 호출 순서를 소유한다.
아래 수치/직접 호출 설명은 최초 단계 이력이며 전체 독립 runtime·INIT/rejoin은 계속 후속이다.

## 코드에서 볼 책임

| 파일 | 역할 |
| --- | --- |
| [normal_stop.hpp](../../central/vehicle_management/normal_stop.hpp) | stop intent·phase·원래 authority와 bounded 자식 root 생성 |
| [actuator_stop_lease.hpp](../../interfaces/common/actuator_stop_lease.hpp) | terminal 인계 lease·immutable duplicate·expiry/source/epoch 검사 |
| [normal_stop_control.cpp](../../simulation/runtime/normal_stop_control.cpp) | 실제 Leaf/allocator/Zone 인계와 부분 실패 보호; same-host binding |
| [vehicle_management.cpp](../../central/vehicle_management/vehicle_management.cpp) | 기존 전원 owner, 종료 중 Shutdown 갱신만 허용; Enable 취소 거부 |
| [command_gateway.cpp](../../zone/gateway/command_gateway.cpp) | terminal 이후 정상 큐·전송 중지, 독립 lease 감시 |
| [rear_power_gateway.cpp](../../zone/gateway/rear_power_gateway.cpp) | 정상 재인가 차단, Shutdown·limits/status 전달 유지 |
| [brake_pressure_response.cpp](../../simulation/brake/brake_pressure_response.cpp) | normal Hold에서 pending release를 폐기하고 physical pressure 보존 |
| [normal_stop_test.cpp](../../tests/unit/normal_stop_test.cpp) | 원천 시간/dwell·입력 상실·단계 budget·잘못된 ACK/만료/issuer 경계 |
| [연결 시험](../../tests/unit/rear_power_gateway_test.cpp) | 시동·normal drive에서 정상 종료까지의 실제 component 연결과 fault 주입 |

## 정지 조건의 의미

Speed≤0.01 rad/s와 |torque|≤0.1 Nm는 현재 wire의 한 step을 사용한 첫 deadband다.
Hold 진입 속도0.5 rad/s가 정지 완료 판정으로 쓰이지 않게 구분한다. Pressure≥0.1 MPa는 기존
hold100 Nm와 friction 환산0.001 Nm/Pa의 설정이다. 감속 요청1 m/s²·확인60 ms·제동5 s/전원 종료2 s도
Host 시험 설정이다. 실차 standstill/주차 유지나 경사로 안전성의 calibration으로 확대하지 않는다.

Dwell은 speed/torque/pressure 중 가장 오래된 원래 취득 시각으로 진행한다. 같은 센서를 읽은
횟수나 gateway publication 시각이 아니다. Source30 ms·상호 skew20 ms, 기존 BMS50/70 ms를 유지한다.
Local gate는 raw sensor로 다시 검사하므로 CAN 양자화가 실제 local 조건을 우회하지 못한다.

## 인계는 수신 감시를 없애는 동작이 아니다

Normal command receiver를 끝내도 별도의 stop lease와 센서·clock/period 감시는 계속한다.
Lease는 새 INIT 이전 source를 허용하지 않고 source50 ms/최대80 ms·exclusive expiry를 검사한다.
동일 identity의 expiry 변경이나 늦게 도착한 새 lease로 이전 상실을 숨길 수 없다.

Leaf는 Hold/Zero를 선택하고 지연된 명령과 monitor의 pending prediction을 함께 비운다.
Sensor sequence·Actual publication·fault는 reset하지 않는다. 이후 regular CAN command는 거부한다.
Brake가 높은 압력을 이미 갖고 있다면 normal Hold는 이를 내리지 않는다. 압력 상실·속도 재상승,
미확인 torque·BMS/permission 상실이나 lease 만료는 여전히 고장이다.

VM은 Stopping/Stopped에서 새 Shutdown lease만 받을 수 있다. Enable로 되돌아갈 수 없고
새 요청으로 shutdown timeout을 다시 시작하지 않는다. 기존 독립 VM의 restrictive local shutdown과
새 NormalStop의 실패/lease latch를 구분한다.

## 연결 시험과 한계

별도 **3.2 s 논리 시간/10 ms step·배분20 ms**에서 다음을 연결했다.
실제 VM/NormalStop/allocator·두 normal gateway/Rear power gateway·Steering/Brake/Drive controller,
별도 angle/pressure/torque plant·PowerController/RC/접점·독립 CAN Actual receiver다.

1200 ms에 stop intent를 넣고, 외부 wheel-speed script를20→0 rad/s로 낮춘다. 실제 torque·pressure는
명령 echo가 아니라 기존 지연/rate plant의 sensor·CAN receiver에서 얻는다. Stop 확인 뒤 정상 frame
전송이 멈추고, actual torque/pressure를 유지하면서 Inhibit→접점 open·bus≤30 V/ACK→Complete로 간다.
이후 positive torque·pressure release CAN이나 arm으로 재출발할 수 없음을 검사한다.

같은 흐름에 terminal lease 갱신 누락·새 압력 센서0·local speed0.02 rad/s·인계 도중 clock 지연/만료를
주입했다. Fresh power/lease나 이미 받은 부분 ACK로 실패를 정상 종료로 바꾸지 않는다.
Pressure 센서 override가 실제 physical pressure를0으로 바꾼 것은 아니며 원인 고유 진단도 하지 않는다.

Speed script는 차량 운동 모델이 아니다. 실제 감속·타이어/경사/노면·parking hold·배터리 에너지/SOC,
독립 ingress/status·DDS coordinator·원격 Leaf·전체 workload timing/Target은 후속이다.
Complete는 HV 접점/잔류 전압 상태이며 LV ECU/센서 전원을 껐다는 뜻이 아니다.

전체 normal·ASan/UBSan **각 C++773/773 PASS**다. Stop/lease16·VM Shutdown 갱신1·Rear terminal1·연결5개를 더했다.
분리 vCAN5/5와 기존 local transport97/97도 각각 PASS다. 새 stop wire를 검증한 것은 아니다.
정적 분석·개발 실패와 재현 로그는 [품질 기록](../quality_policy.md)에 둔다.

```sh
cmake -S . -B build/m4-readiness -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m4-readiness -j 4
ctest --test-dir build/m4-readiness --output-on-failure
```

Sanitizer는 `build/m1-angle-sanitized`에 `-DSTRATADRIVE_SANITIZERS=ON`을 설정한다.
기존 `zone_gateway_vcan_test`의 Front case는 정상 인계 뒤 실제 CAN으로 온 다음 command 거부도 확인한다.
별도 remote stop wire를 추가한 것은 아니다. 전체 M4와 system requirement/TC 결과는 계속 구분한다.
