# M4 Zone 명령 수용: 출처와 유효기간을 지킨다

Date: 2026-10-19. Status: **첫 Host 수용 component 구현·시험 / 후속 gateway·보호 연결은 별도 안내**.
[ADR-0046](../adr/ADR-0046-scoped-zone-command-admission.md),
[공통 계약](../../interfaces/central/allocated_commands.hpp),
[수용 API](../../zone/command_validation/command_admission.hpp),
[구현](../../zone/command_validation/command_admission.cpp),
[시험](../../tests/unit/command_admission_test.cpp)을 함께 읽는다.

## 왜 Zone에서 다시 검사할까

[Central 배분기](m4_control_allocation.md)는 차량 요구를 angle·pressure·torque로 바꾼다.
수신 Zone은 그 계산이 정상이라고 가정해 오래된 명령까지 계속 전달하면 안 된다.
이번 component는 **담당 명령의 출처·순서·범위·현재 유효성**을 판정한다.
Front와 Rear의 상태는 독립이며 다른 Zone의 heartbeat나 traffic으로 복구되지 않는다.
Front는 조향/브레이크 두 명령을 한 allocation의 atomic pair로 받고 Rear는 구동 명령을 받는다.
값이 0인 유효 명령과 값이 없는 unknown도 구분한다.

원래 차량 요구와 actuator 명령의 sequence는 서로 다르다.
명령의 causal sequence는 어느 차량 요구로 계산했는지 가리킨다.
동일 root를 여러 번 계산해도 원래 source와 expiry는 그대로다.
예를 들어 원래 root가 20 ms에 발생했고 명령 expiry가 50 ms라면,
40 ms에 새 root만 승인하거나 packet을 재수신해도 그 명령을 50 ms 이후 사용할 수 없다.

## 호출 순서와 신뢰 경계

```text
trusted session INIT → Idle
trusted coordinator arm → Waiting (첫 명령 80 ms 감시)
독립 trusted VehicleRequest 승인
Central allocation → FrontCommands / RearCommands → receive
수용 성공 → Active → current_command(dispatch 시각)
만료·clock rollback·continuity loss → FailSafe + protection_required
```

INIT와 arm을 분리한 이유는 전원 준비다. Precharge 중에는 정상 주행 명령이 없으므로 Idle에서
기다리고, 실제 readiness/권한을 확인한 상위 절차가 정상 명령 감시를 명시적으로 시작해야 한다.
명령 packet 자체는 arm이나 INIT를 할 수 없다. 실제 coordinator의 시작/보호 경로 연결은 후속이다.

`authorize_request(root, now)`는 명령에 첨부된 parent와 별도로 전달받은 trusted 원래 요구다.
**`receive` packet에서 parent를 꺼내 곧바로 승인하면 이 검사가 무의미해진다.**
승인된 root와 명령의 parent 전체를 대조해 source/expiry/요구 내용 바꿔치기를 거부한다.
아직 DDS 인증/IDL을 구현한 것은 아니며 caller의 신뢰된 handoff를 전제로 하는 component API다.
Permission의 lifecycle root와 VehicleRequest root도 서로 바꾸어 사용하지 않는다.

## 거부와 latch를 구분한다

잘못된 scope/kind/값·mode·Epoch·parent·sequence는 거부하며 정상 수용 기록을 갱신하지 않는다.
중복 명령도 Unchanged이고 last-valid 수신 시각이나 lease를 늘리지 않는다.
잘못된 packet이 계속 들어와도 원래 명령의 만료는 진행한다.

이미 수용한 명령의 expiry가 지나거나 연속성/clock을 잃으면 FailSafe로 latch한다.
**늦은 정상 packet보다 기존 만료를 먼저 검사**하므로 도착이 재개돼도 자동 NORMAL로 복귀하지 않는다.
더 큰 trusted Epoch의 INIT가 필요하고, 물리 조향각/압력/토크를 초기화하지 않는다.
`current_command(now)`가 없다는 사실은 제동 해제나 실제 정지 성공을 뜻하지 않는다.
지금은 fault와 보호 요청을 제공하며 실제 Zone local safety 출력은 다음 구현이다.

첫 age는 command/root 30 ms, 가장 오래된 사용 입력 70 ms, root lifetime 최대 60 ms다.
Age 30 ms는 허용하지만 expiry 시각과 같아지면 사용할 수 없다.
이 차이를 코드에서는 `source + age + 1 ns` bound와 exclusive expiry로 표현한다.
첫 물리 범위는 angle ±0.3 rad, pressure 0..1.5 MPa, torque −200..300 Nm다.
실차 값이나 새 고성능 제어 기법을 추가한 단계는 아니다.

## 검증과 다음 단계

새 **59개 case**를 더해 전체 normal·ASan/UBSan 각각 **C++ 665/665 PASS**다.
Scope·atomic pair·원래 root와 변조·시간 경계·범위·sequence·duplicate flood·만료 전 우선 검사·
독립 Zone loss/reinit·더 좁은 설정·wire 반올림의 한계 초과 거부·uint64 끝의 포화 계산을 확인했다.
실제 ControlAllocation 출력도 20 ms씩 200 ms 논리 시간 동안 두 검증부에 전달했다.
이 시험의 permission/Zone actual/BMS 입력은 기존 allocator fixture이며 전체 차량 실행이 아니다.

```sh
cmake -S . -B build/m4-readiness -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m4-readiness -j 4
ctest --test-dir build/m4-readiness -R 'CommandAdmission|RealAllocatorOutputsPassIndependentScopedZoneAdmission' --output-on-failure
```

후속 [gateway의 bounded queue/egress와 CAN 전달·local safety handoff](m4_zone_gateway.md)는 구현했다.
기존 32-byte CAN payload에 이 sideband가 없으므로
수용 시험을 Leaf까지 원래 만료가 보장된 end-to-end 검증으로 확대하지 않는다.
후속 [Rear 전원/허가/limits·NonDriving/arm](m4_rear_power_startup.md)은 component/vCAN에서 연결했다.
Front startup·정상 종료·실제 독립 ingress/rejoin·전체 workload timing·DDS/M5는 남아 있다. System requirement 32개/TC 29개는 NOT RUN을 유지한다.
