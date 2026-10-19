# M4 Front startup: 실제 센서로 기다리고 함께 구동 시작하기

Date: 2026-10-19. Status: **Host component·분리 vCAN 시험 / 전체 M4 runtime 후속**.
[ADR-0049](../adr/ADR-0049-front-nondriving-startup-and-paired-arm.md)의 구현이다.
아래750개와 정상 종료 미구현 설명은 당시 단계 이력이다. [후속 정상 종료](m4_normal_stop.md)에서 별도 terminal handoff를 구현했다.

Front도 Rear처럼 프리차지 동안 정상 command 없이 대기한다. 이때 센서·제어 주기는 계속 살아 있다.
**명령을 기다리는 시간과, 실제 센서를 감시하는 시간은 서로 다른 계약**이다.

| 단계 | Steering/Brake Leaf | Front gateway |
| --- | --- | --- |
| Trusted INIT + NonDriving | Hold, fresh sensor로 INIT Actual 발행 | Idle, 정상 명령 미수용 |
| 전원/차량 준비 대기 | 센서·clock·period 감시, normal command receiver는 미시작 | 기존 root/arm 경계 유지 |
| Trusted pair arm | 두 Leaf에 새 valid acquisition 필요; 같은 Epoch에서 수신 시작 | 두 Leaf와 함께 arm, 최초 명령 대기 시작 |
| 첫 정상 배분 | 첫 command Sequence0; Actual·physical state는 계속됨 | Steering/Brake 묶음 수용 뒤 두 CAN write |
| Fault/부분 arm 실패 | Hold/Protect 선택, sensor/실제 응답은 별도 | latch·정상 전달 중단 |

Brake의 초기 Hold는 기존 압력을 유지하는 SIL 출력 의미다. 압력0을 보내 release하거나 보호 floor를
요청하지 않는다. 정차/주차 유지 성능을 보장하는 제어기는 아직 아니다.

## 읽을 코드

| 파일 | 책임 |
| --- | --- |
| [actuator_session.hpp](../../interfaces/common/actuator_session.hpp) | Immediate/NonDriving 공통 시작 정책; Drive의 기존 이름은 alias |
| [SteeringActuator](../../vecu/steering/steering_actuator.cpp) | receiver 시작 지연·clock/센서 preflight·기존 tracking/hold 유지 |
| [BrakeActuator](../../vecu/brake/brake_actuator.cpp) | receiver 시작 지연·sensor preflight·기존 response/protect 유지 |
| [FrontStartupControl](../../simulation/runtime/front_startup_control.cpp) | scope/Epoch/양쪽 readiness 대조·세 객체 arm·실패 시 두 Leaf 보호 |
| [Front 연결 시험](../../tests/unit/command_gateway_test.cpp) | 한쪽 미준비/만료·잘못된 INIT·gateway commit 실패 |
| [양 Zone 시동 연결](../../tests/unit/rear_power_gateway_test.cpp) | 실제 Front/Rear Leaf Actual→VM→배분→두 gateway |
| [vCAN 시험](../../tests/integration/can/zone_gateway_test.cpp) | pre-arm packet 거부·arm 후 첫 정상 frame의 실제 Leaf 수용 |

새 INIT을 해도 과거 receiver의 diagnostic last_accepted가 남아 있을 수 있다. NonDriving에서는 그
이력을 새 Actual의 causal/origin으로 쓰거나 current command로 노출하지 않는다. 물리 모델과
센서 sequence는 계속되고 Actual publication sequence는 arm에서 reset하지 않는다.

Arm 전 packet은 P05/정상 sequence를 소비하지 않으며, arm 뒤라도 source가 arm보다 과거이면
거부한다. 따라서 startup 동안 가짜 0 명령을 반복할 필요가 없다. Idle은 normal command timeout만
대기할 뿐이다. 센서 상실·clock 역행·제어 주기 공백은 여전히 fault다.

두 Leaf의 preflight가 끝난 뒤에도 gateway/두 Leaf의 transition 자체가 atomic한 것은 아니다.
중간 실패는 정상 경로를 latch하고 둘 다 보호한다. Gateway 호출 중 시각이 전진할 수 있으므로
이미 전달한 보호 시각보다 과거의 callback을 뒤따라 보내지 않는다. 센서 상실을 인위적인 clock
오류로 덮지 않는 회귀도 포함한다. 성공한 CAN frame을 되돌렸다고 가정하지 않는다.
이 연결은 single-owner same-host callback이며 DDS/원격 MCU startup protocol이 아니다.

## 검증한 범위

기존 726개에 Steering startup9·Brake startup9·Front binding6개를 더해 normal·ASan/UBSan
**각 C++ 750/750 PASS**다. Default Immediate 회귀·기존 receiver/source-age/보호 시험도 포함한다.
초기1 s 대기·미리 온 packet/과거 source·첫 정상 sequence·cached/stale/없는 센서·clock/INIT 역행·
control gap·arm 기준80 ms·과거 causal 억제/physical 보존을 확인했다.

이전 Rear 연결 시험은 **1.6 s 논리 시간/10 ms step·배분20 ms**의 양 Zone 연결로 확장했다.
Front Actual fixture를 실제 Steering/Brake controller·별도 angle/pressure plant·독립 CAN Actual receiver로
교체했다. VM/PowerController·접점/RC·mandatory Drive/TorqueResponse·allocator와 두 scoped gateway를 사용한다.

프리차지가80 ms를 넘는 동안 초기 angle0.1 rad·pressure0.2 MPa를 보존하고 정상 command는0개다.
실제 HV_READY/ACK 뒤 trusted pair arm/Rear arm, 세 normal command의 첫 Sequence0을 확인한다.
그 뒤 요청 curvature에 따른 angle 변화·압력의 실제 release·양수 torque 응답을 확인한다.
Actual을 command echo나 plant truth 직접 입력으로 대체하지 않는다.

Zone health·BMS limits/safety gate·pack400 V/load0 A·외부 speed0 rad/s는 여전히 fixture다.
Full BMS/SOC/energy·차량 관성/감속·실제 분산 coordinator·독립 ingress/status worker를 전부 검증한 것은 아니다.
마지막 Rear protection은 기존처럼 torque 잔류/닫힌 접점을 보존하고 Power WaitCurrent로 진행한다.
이 상실 이후 Central/Front까지 이어지는 전체 반응은 다음 runtime 통합에서 다룬다.

분리 vCAN은 **각5/5 PASS**다. 새 Front case는 실제 CAN의 pre-arm Sequence9 packet을 거부한 뒤
trusted arm 후 gateway가 보낸 Sequence0 두 frame을 실제 Leaf receiver가 수용하는지 검사한다.
이 vCAN case의 센서는 명시적 acquisition fixture이며, 물리 반응은 위 component 시험의 범위다.
기존 local transport도 normal/sanitizer 각각97/97 PASS다. Requirement32/system TC29는 NOT RUN이다.

```sh
cmake -S . -B build/m4-readiness -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m4-readiness -j 4
ctest --test-dir build/m4-readiness --output-on-failure
unshare --user --map-root-user --net bash -c '
  ip link add vcan_front type vcan && ip link add vcan_rear type vcan &&
  ip link set vcan_front mtu 72 up && ip link set vcan_rear mtu 72 up &&
  exec build/m4-readiness/zone_gateway_vcan_test'
```

Sanitizer는 `build/m1-angle-sanitized`에 `-DSTRATADRIVE_SANITIZERS=ON`을 설정해 같은 target을 실행한다.
기존 transport는 격리 netns에서 `python3 tests/integration/can/check_socketcan.py --build-dir <build-dir>`로 검사한다.
Production build·정적 분석과 로그/문서 검사 범위는 [품질 기록](../quality_policy.md)에 둔다.

## 다음: 정상 정지와 전원 종료 구분

현재 Shutdown→Inhibit는 active Drive의 고장 latch를 만든다. Allocator도 normal_allowed가 내려가면
정상 출력을 중단한다. 이것은 전체 차량의 정상 종료가 완성됐다는 뜻이 아니다.
[ADR의 후속 검토](../adr/ADR-0049-front-nondriving-startup-and-paired-arm.md#정상-종료-검토--후속-구현)처럼
정상 제어 중 제동/hold→fresh actual 정지 증거→명시적 local handoff→Inhibit/전원 종료를 연결해야 한다.
후속 [NormalStop/ADR-0050](m4_normal_stop.md)에서 첫 Host fixture의 owner·조건·budget을 정해 연결했다.
실차 motion/hold calibration과 차량 운동 검증은 남아 있다.

Remote normal CAN의 composite lease/보호 전달·전체 ingress/status/rejoin·DDS·통합 workload timing과 Target도
후속이다. 이번 component 결과를 M4 전체 완료나 M3 타이밍 예외 해소로 표시하지 않는다.
