# ADR-0046: Front/Rear normal 명령의 독립 수용 경계

Date: 2026-10-19. Status: **Host component 구현·시험 / gateway·보호 출력·runtime 후속**.
[ADR-0045](ADR-0045-first-central-control-allocation.md)의 scoped sideband를
[ZON-01](ADR-0021-central-coordination-and-parallel-zones.md)의 두 독립 수신 경계에 연결한다.
이번 결정은 TBD-15의 첫 in-process 의미 계약이며 DDS IDL/인증/clock sync 결정이 아니다.

## 책임과 계약

`interfaces/central/allocated_commands.hpp`에 VehicleRequest·CommandContext·AllocatedCommands와
FrontCommands/RearCommands를 둔다. 기존 Central namespace/API 의미는 유지한다.
Front는 Steering/Brake의 같은 Epoch·Sequence·Source·CausalSequence·mode/origin 묶음,
Rear는 Drive command다. Scope helper는 복사만 하며 원래 root·oldest dependency·expiry를 바꾸지 않는다.
Rear의 power 요청/permission/BMS constraint와 초기 non-driving 경로는 별도 lifecycle 통합 후속이다.

`zone/command_validation/CommandAdmission`은 Zone마다 별도 single owner다.
배분기를 include/link하지 않고 공통 interface와 CAN domain 정의만 사용한다.
명령 수용이 BMS permission/로컬 actuator availability 판정이나 물리 protection을 대신하지 않는다.

Trusted INIT로 Epoch와 공통 monotonic session-enable을 설정하면 Idle이다.
전원 precharge 중 정상 명령 상실로 실패하지 않도록 **trusted `arm(now)`를 별도로** 호출한다.
Packet은 arm/INIT를 수행하지 않는다. Arm은 현재 세션에서 한 번만 가능하고 이후 Waiting/Active다.
초기 정상 주행 시작 조건과 실제 coordinator의 arm 호출은 다음 통합에서 검증한다.

원래 VehicleRequest는 **독립 trusted `authorize_request` callback**으로 승인한다.
명령에 붙은 parent를 복사해 이 callback을 호출하는 구현은 금지한다.
승인은 허용된 Central root handoff라는 caller 전제이며 transport/보안 구현은 아니다.
현재 승인 root 한 개만 유지하고, 새 root 이후 도착한 이전 root 명령은 거부한다.
이미 수용한 이전 명령은 자신의 원래 lease까지만 유효하며 새 root만으로 갱신되지 않는다.
Root 승인과 scoped command의 sequence cursor는 독립이다.

## 첫 수용 규칙

| 검사 | 규칙 |
| --- | --- |
| Scope·kind | Front는 atomic Steering/Brake Command, Rear는 Drive Command. Actual/auxiliary 혼입 거부 |
| Normal mode | NormalPath + Normal만 허용. INIT/DEGRADED/LocalProtection은 이 경로로 우회하지 않음 |
| Root identity | 승인 root와 Epoch/Sequence/Source/Expiry/모든 요구 내용 일치, command CausalSequence 일치 |
| Progress | 최초 sequence 0..9, 후속 증가량 1..10·source 증가; wrap 없음. 동일 identity의 내용·시각·expiry 변경 거부 |
| Range | 첫 SIL envelope: angle ±0.3 rad, pressure 0..1.5 MPa, torque −200..300 Nm. Unknown·NaN/Inf·다음 wire step·wire 양자화 뒤 한계 초과 거부, clamp 없음 |
| Root 요구 | 첫 계약 acceleration −5..2 m/s², absolute curvature ≤1 /m, braking 0..1, 명시적 hold |
| Clock·age | 동일 monotonic domain, session 이전/미래 source 거부; command/root age ≤30 ms, oldest used dependency ≤70 ms |
| Lifetime | Root lifetime ≤60 ms. Output expiry는 root expiry, root/command source-age bound, oldest dependency bound 중 최소 이하 |
| Boundary | Age는 inclusive, Expiry는 exclusive. Age bound는 포화 덧셈 `source + age + 1 ns` 사용 |

Oldest used input은 root source 이하이며, command source는 root source 이상이어야 한다.
명령의 지원 입력별 더 짧은 expiry는 Central이 산출해 보존한다. 이 검증부가 계산 근거의 모든
BMS/actual 입력을 독립 재계산했다고 주장하지 않는다. Zone/Leaf의 로컬 gate는 후속 연결에서도 유지한다.
범위/시간 설정은 첫 fixture이며 실제 차량 calibration이나 cross-node clock 계약이 아니다.

## 만료·연속성·복구

이전 accepted expiry를 **새 root/packet 처리보다 먼저** 검사한다. Late fresh packet으로
지나간 권한 공백을 숨길 수 없다. Invalid packet/duplicate/root 승인/다른 Zone traffic은
last-valid command RX나 expiry를 갱신하지 않는다. Duplicate는 Unchanged다.
`current_command(now)`도 dispatch 시점에 재검사하며 진단 cache를 정상 출력으로 반환하지 않는다.

Arm 후 첫 valid command가 없으면 80 ms에 timeout latch한다.
Active 명령은 원래 composite expiry에서 latch하며, clock rollback/명시적 continuity loss도 latch한다.
최대 10 ms monitor + 10 ms dispatch/jitter 여유를 더한 초기 검출 budget은 100 ms다.
이는 논리 시간 계약이며 wall-time/독립 watchdog 성능 검증은 후속이다.

Latch 시 normal snapshot을 제공하지 않고 `protection_required`와 fault를 제공한다.
물리 Brake release/hold pressure/Drive zero 출력은 이 component가 생성하지 않는다.
실제 local safety handoff가 다음 단계다. Recovery는 더 큰 trusted Epoch·시간 비후퇴의 INIT,
새 승인 root와 명시적 arm/새 명령을 요구하며 물리 상태를 reset하지 않는다.
각 Zone의 객체 독립 시험은 전체 Central–Zone 재접속 protocol 수용을 의미하지 않는다.

**기존 32-byte CAN에는 원래 parent/expiry가 없다.** Gateway queue와 egress guard가
sideband를 보존·재검사하기 전에는 Leaf까지 expiry가 보장됐다고 표시하지 않는다.
DDS·SocketCAN·full runtime/system TC는 이번 범위 밖이다. 시험/재현은
[학습 안내](../learning/m4_zone_command_admission.md)에 기록한다.
