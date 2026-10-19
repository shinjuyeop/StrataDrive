# M4 Central coordinator: 시동·배분·정지를 한 실행 흐름으로

Date: 2026-10-19. Status: **Host component 구현·회귀 / 독립 runtime·전체 rejoin 후속**.
설계는 [ADR-0053](../adr/ADR-0053-central-coordinator-and-same-host-binding.md)을 따른다.

지금까지 만든 전원 판단·배분·정상 종료를 시험 코드가 직접 순서대로 호출했다.
이번에는 **누가 언제 호출하고, 한 단계가 실패했을 때 어디로 전달할지**를 Central coordinator가 관리한다.
기존 owner의 검증과 실제 gateway/Leaf 수신 경로는 계속 사용한다.

## 한 cycle에서 일어나는 일

1. 담당 receiver의 current sample을 원래 source/quality 그대로 모은다. Clock/session·실제 gateway/Leaf도 확인한다.
2. 정상 정지 중이면 stop plan을 먼저 계산한다. 그 외에는 원래 수용한 lifecycle/vehicle 요청을 사용한다.
3. VehicleManagement가 power actual/ACK와 입력 건강을 판단한다. 준비됐을 때만 Front/Rear를 명시적으로 arm한다.
4. PowerRequest/DrivePermission을 Rear gateway로 전달한다.
5. 20 ms allocation 시점에는 **실제로 수신한 permission**과 Actual/BMS를 검사해 Front pair·Rear 명령을 전달한다.
6. 정지 조건이 확인되면 allocator·Leaf/gateway를 terminal 상태로 넘기고, ACK 뒤 Shutdown·actual OFF를 확인한다.

외부 `tick`은10 ms다. Plant/sensor/Zone monitor·CAN RX를 진행하는 caller가 current snapshot을 넘긴다.
Coordinator가 sensor 취득 시각을 바꾸거나 plant를 계산하는 구조가 아니다.

## 공부할 구분

**Coordinator와 상태 owner는 역할이 다르다.** VM은 전원/허가, allocator는 angle/torque/pressure,
NormalStop은 정지/인계의 상태를 소유한다. Coordinator는 세 owner를 private로 소유하고 호출 순서와 보호를 연결한다.
차량 전체 로직을 Zone에 복제하지 않는다.

**발급한 허가와 수신한 허가는 다르다.** 방금 AllowNormal을 발급했어도 실제 permission ingress가 끊기면
새 발급값으로 receiver 결과를 대체하지 않는다. 마지막 output은 변하지 않는 parent context 확인에만 쓰고
배분은 실제 current sample을 요구한다. 같은 parent가 필요한 이유와 원천 age/expiry를 함께 살펴본다.

**여러 전송은 한 번에 성공하지 않는다.** Front Steering은 전달됐지만 Brake가 실패할 수 있다.
Coordinator는 Rear normal batch를 계속 보내지 않고 두 Zone의 독립 보호를 선택한다.
정상 패킷 재전송으로 부분 실패를 감추지 않는다. 보호 ACK도 실제 차량이 멈췄다는 의미와 구분한다.

**정지 요청 뒤에는 정상 요청이 우선권을 되찾지 않는다.** Stop owner가 원래 요청 안에서 child root를 만들고,
다음 sequence도 coordinator가 마지막 정상 root에서 인계한다. 같은 source instant와 기존 지원 만료 경계를
그대로 지키므로, 늦은 stop/root로 만료된 권한을 다시 살릴 수 없다.

## 코드 읽는 순서

| 파일 | 역할 |
| --- | --- |
| [vehicle_coordinator.hpp](../../central/coordinator/vehicle_coordinator.hpp) | trusted 입력·tick·port·상태 조회 API |
| [vehicle_coordinator.cpp](../../central/coordinator/vehicle_coordinator.cpp) | 10/20 ms 순서·owner/issuer 인계·실패 latch·보호 재시도 |
| [vehicle_coordinator_port.cpp](../../simulation/runtime/vehicle_coordinator_port.cpp) | 실제 gateway·Leaf·permission RX에 연결하는 same-host adapter |
| [normal_stop_control.cpp](../../simulation/runtime/normal_stop_control.cpp) | 실제 Leaf/Zone terminal 선택, 부분 인계 보호 |
| [vehicle_coordinator_test.cpp](../../tests/unit/vehicle_coordinator_test.cpp) | 호출 순서·root/INIT·실패·clock/period·stop 우선권의 독립 component 시험 |
| [실제 모델 연결 시험](../../tests/unit/rear_power_gateway_test.cpp) | 실제 VM/배분/정지·양 Zone/Leaf/RC·angle/pressure/torque·CAN receiver와 coordinator 연결 |

새 demo 실행 파일은 추가하지 않았다. 새 모듈 unit을 한 파일에 두고 실제 모델 연결 case는 기존 파일을 확장했다.

## 확인한 결과와 남은 일

Normal·ASan/UBSan **각 C++820/820 PASS**다. 이전795개에 coordinator20개·실제 연결5개를 추가했다.
기존 시동/정상 정지3.2 s 논리 시간·Actual 누락/상태 partition·lease/압력/속도 상실 흐름도 coordinator로 전환했다.
추가 case는 부분 arm·Power write 실패·Front partial write·Central permission ingress 상실·한 gateway만 새 Epoch다.
정적 분석·build/vCAN·개발 중 실패와 수정 근거는 [품질 기록](../quality_policy.md)에 둔다.

현재 연결은 **같은 Host에서 외부 시각으로 호출하는 component**다. Independent runnable/thread/process나 DDS를
새로 실행한 결과가 아니며, 기존 EV demo/runtime request/grant fixture를 아직 교체하지 않았다.
새 Epoch의 전체 INIT/rejoin handshake·status/Actual ingress 및 Host feedback bridge를 실행 경계로 묶는 일이 다음이다.
그 뒤 새 workload에서 timing과 독립 정지/partition을 시험한다. Remote Leaf lease/보호와 Target 검증도 남아 있다.
MBD는 계획한 M6 모델/MIL→M8 C++ 동등성·차량 SIL 순서를 유지한다.
