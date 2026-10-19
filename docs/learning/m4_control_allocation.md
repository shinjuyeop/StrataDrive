# M4 Central 제어 요구와 회생·마찰 배분

Date: 2026-10-19. Status: **첫 normal-path component + 응답 모델 연결 시험 / Zone·차량 runtime 후속**.
[ADR-0045](../adr/ADR-0045-first-central-control-allocation.md)의 구현이다.

[VehicleManagement](m4_vehicle_management.md)는 주행 권한과 전원을 관리한다.
이번 **ControlAllocation은 허가된 차량 요구를 Steering angle·Drive torque·Brake pressure로 바꾼다.**
상위 speed PID나 모터 FOC/ABS/ESC를 추가한 것은 아니다. 관측 actual과 command도 계속 구분한다.
코드는 [API](../../central/control_allocation/control_allocation.hpp),
[구현](../../central/control_allocation/control_allocation.cpp),
[시험](../../tests/unit/control_allocation_test.cpp)에 있다.

## 단위를 먼저 맞춘다

첫 fixture는 mass 1000 kg, wheel radius 0.3 m, wheelbase 2.7 m, 압력→토크 계수 `K=0.001 Nm/Pa`다.
실차 수치를 고증한 calibration이 아니라 기존 M2 actuator 범위에 맞춘 명시적 시험값이다.
경사·저항·wheel inertia는 아직 배분의 inverse model에 넣지 않았다.

| 변환 | 첫 계산 |
| --- | --- |
| 가속 요구 1 m/s² | `T = m × a × r = 300 Nm` |
| 경로 curvature 0.1 /m | `angle = atan(2.7 × 0.1)` 약 0.264 rad; 최대 ±0.3 rad |
| 감속 요구 −1 m/s² | 양수 크기의 제동 요구 300 Nm |
| normalized braking 0.4 | `0.4 × 1500 = 600 Nm` |
| 마찰 몫 200 Nm | `P = 200 / 0.001 = 200000 Pa` |

음수 acceleration과 normalized braking은 큰 요구를 선택한다. 예를 들어 300 Nm와 400 Nm라면
400 Nm를 배분한다. 700 Nm로 더하지 않는다. 제동이 선택되면 양수 추진 demand는 함께 유지하지 않는다.
Normalized braking과 실제 pressure, 실제 차량 감속은 같은 값이 아니다.

추진에서는 battery DC 한계에서 reserve를 빼고 `Tω/η + kT²`가 그 안에 드는 토크를 계산한다.
0 rad/s에서도 copper loss가 있으므로 `P/0`으로 무한 토크를 허용하지 않는다.
첫 max propulsion 300 Nm·mechanical 20 kW를 추가로 적용하며 실제 Drive local gate가 다시 검사한다.

## 회생과 마찰을 동시에 다룰 때

총 제동 400 Nm, 회생 capability 200 Nm이면 먼저 `Drive −200 Nm / Brake 200000 Pa`를 요구한다.
현재 BMS charge cap이 1000 W이고 wheel speed가 20 rad/s이면 회생은 최대 50 Nm여서
처음부터 `−50 Nm / 350000 Pa`로 나눈다. Capability 자체가 0/unknown/stale이면 새 회생은 0이다.
Torque actual까지 없는 경우에는 마찰 fallback으로 정상 출력하지 않고 보호를 요청한다.

전환에서는 **실제로 남아 있는 토크**가 중요하다. 예를 들어 다음 관측이 들어왔다고 하자.

| 시점 / 관측 | 다음 요구 |
| --- | --- |
| 실제 회생 200 Nm + 실제 마찰 200 Nm, 회생 cap이 0으로 감소 | Drive 0; 마찰 목표는 아직 200 Nm |
| 실제 회생이 100 Nm로 감소, 마찰 200 Nm | 마찰 목표 300 Nm |
| 실제 회생 0 | 마찰 목표 400 Nm |

Cap이 0이 된 순간부터 마찰 400 Nm를 더하면 남아 있는 실제 회생과 겹칠 수 있다.
첫 계산은 `Ptarget = max(0, Brequest − max(Rselected, Ractual)) / K`다.
초기 회생 build 동안 `Rselected` 몫을 예약하며 아직 실현되지 않은 부분은 deficit로 기록한다.
전환 때 pressure가 늦게 따라오면 그만큼 actual 부족이 생길 수 있다. 즉시 전부 보충됐다고 표시하지 않는다.

첫 정책은 한 제동 구간에서 회생 목표를 올리지 않는다. Cap이 회복돼도 마찰을 쓰던 도중 회생을 다시 얹지 않는다.
실제 pressure/모터 torque가 release 허용 범위에 들어온 뒤 다음 제동에서 회생을 다시 선택한다.
향후 rate·delay를 검증한 더 적극적인 handoff와 효율 최적화로 확장할 수 있지만 이번 결과에 포함하지 않는다.

저속은 2 rad/s 이하에서 회생을 막고 3 rad/s 이상에서 다시 사용할 수 있게 한다.
명시적 `standstill_hold`와 0.5 rad/s 이하 조건에는 100 Nm의 마찰 hold를 요청한다.
진입한 hold는 요청을 clear할 때까지 유지해 작은 속도 상승/잡음으로 자동 해제하지 않는다.
Hold가 없는 acceleration 0은 coast이며 자동 hold로 바꾸지 않는다.
출발에는 actual friction ≤1 Nm·negative motor residual ≤0.1 Nm를 확인한다. Hold/stop 성공 자체는 차량 모델 검증 후속이다.

## 요청과 관측은 어떻게 추적하나

VehicleRequest root는 acceleration/curvature/braking/hold, Epoch/Sequence/원래 Source/Expiry다.
Permission의 lifecycle root와 서로 다른 identity이며 하나로 바꿔 쓰지 않는다.
새 counter로 원래 요청이나 지원 입력을 갱신하지 않는다. Same identity의 내용/시각/expiry 변경은 거부한다.

출력에는 Steering/Brake/Drive command와 함께 원래 vehicle root, 가장 오래된 사용 입력, 최소 expiry가 있다.
Capability가 실제 음수 demand를 허용할 때만 그 dependency도 출력 만료를 제한한다.
다음 20 ms cycle까지 유지되지 못할 capability는 Expiring으로 분류해 미리 회생을 줄인다.
Optional capability 만료만으로 전체 고장 latch를 만들지 않고 마찰 경로를 사용한다.
필수 actual/허가/원래 request 만료는 새 데이터보다 먼저 검사하고 latch하는 정책을 유지한다.
추진에 쓰지 않는 cached capability를 필수 추진 dependency로 취급하지 않는다.
Wheel speed/capability 시각은 torque acquisition보다 늦을 수도 있으며, 각각의 source age를 검사한다.

**기존 32-byte CAN command에는 이 parent/expiry sideband가 없다.**
후속 [Zone admission](m4_zone_command_admission.md)이 이를 확인·보존한다. CAN egress 연결 전이므로 이번 codec/receiver 시험을 Leaf까지 end-to-end expiry 검증으로 표시하지 않는다.
입력은 매 cycle의 `current_sample(now)`이며 진단용 last accepted cache를 제어 입력으로 바꾸지 않는다.

Actual net braking은 `K × Pactual − Tdrive_actual`이다. 아직 양수 추진 100 Nm가 남아 있다면 이를
회생 100 Nm로 잘못 더하지 않는다. 관측의 원래 acquisition 시각도 decision에 보존한다.
50 Nm 초과 deficit/excess가 원천 시각 기준 700 ms 지속되면 latch한다. Cached 관측은 dwell을 진행시키지 않는다.
이 700 ms는 full signed motor reversal 550 ms 등을 포함한 첫 component budget이며 실제 차량 요구가 아니다.
기존 Leaf local response monitor와 critical stream loss 100 ms 상한을 완화하지 않는다.

압력 포화로 부족해지거나 권한/필수 입력·연속성을 잃어도 새 normal output을 중단하고
`protection_required`를 반환한다. **출력 없음은 Brake 0·actual 0·정지 성공이 아니다.**
Coordinator/Zone의 보호 동작으로 연결해야 하며, latch는 더 큰 Epoch의 trusted INIT로만 해제한다.

## 검증한 범위와 재현

새 unit 36개를 더해 normal·ASan/UBSan 각각 C++ 전체 **606/606 PASS**다.
권한/서로 다른 root·expiry, 7개 source 상실, 단위·제동 우선순위·zero/unknown capability·BMS power,
저속/hold·release·saturation·skew·cached source·response dwell·wire 양자화를 검사했다.
실제 VehicleManagement의 INIT/Enable 응답→AllowNormal을 기존 BmsReceiver로 받아 배분하는 시험도 있다.

응답 모델 시험은 최대 **3.6 s 논리 시간 / 20 ms cycle**이며 다음을 확인한다.

1. 별도 DriveSilPlant/TorqueResponse와 BrakePressureResponse를 진행하고 각각 sensor를 취득한다.
2. Actual을 CAN encode→독립 Drive/Brake receiver→allocator로 전달한다.
3. Allocated command도 CAN encode→command receiver→별도 plant 출력 적용 순서로 사용한다.
4. 정상은 회생+마찰, cap 0, cap 회복, 실제 release 후 출발, 다시 제동을 검사한다.
5. 별도 slow pressure/hold-stuck 주입은 response budget에서 보호를 요청하고 actual을 0으로 바꾸지 않는다.

Pressure wire 해상도는 **1000 Pa**, torque는 **0.1 Nm**다. 배분기의 관측값은 unquantized plant truth가 아니라
receiver가 받은 actual이다. 두 수치의 양자화 오차도 별도로 대조한다. Command 양자화는 한계 안쪽으로 한다.

Steering actual/Zone health·BMS power/limits·permission은 응답 모델 시험의 명시적 fixture다.
Speed는 외부 고정 20 rad/s이며 차량 관성·타이어·경사·Battery energy/SOC·full Leaf response monitor를 연결한 전체 loop가 아니다.
실제 BMS derating의 sender DEGRADED를 허용하는 VehicleManagement 정책도 이번에 바꾸지 않았다.
Normal sender의 valid zero/limited constraint로 첫 배분을 시험한 것이며 그 통합 envelope는 후속 검토다.
SocketCAN/vCAN·DDS·wall-time 실행·Target/system TC는 이번에 실행하지 않았다.

```sh
cmake -S . -B build/m4-readiness -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m4-readiness -j 4
ctest --test-dir build/m4-readiness -R '^ControlAllocation' --output-on-failure
```

후속 [Front/Rear scoped admission](m4_zone_command_admission.md)은 구현했다. 다음은 CAN routing·독립 ingress/loss/rejoin과 protection handoff다.
그 과정에서 기존 EV runtime fixture를 coordinator로 교체하고 BMS non-protection derating 허가 envelope·
초기 non-driving command 경로를 확인한다. 새 workload timing과 차량 response budget은 다시 검증한다.
