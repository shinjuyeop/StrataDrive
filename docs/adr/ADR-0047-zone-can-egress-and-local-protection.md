# ADR-0047: Zone CAN 전달 직전 검증과 독립 보호 handoff

Date: 2026-10-19. Status: **Host component·분리 vCAN 구현/시험 / 전체 coordinator/runtime 후속**.
[ADR-0046](ADR-0046-scoped-zone-command-admission.md)의 수용된 scoped command를
정상 CAN 전달과 별도 trusted local protection 경로에 연결한다.

## Gateway와 대기열

Zone마다 `CommandGateway`와 전용 port/CAN interface를 둔다. 독립 single owner이며
실제 외부 ingress worker나 DDS thread/queue 배치는 이번에 추가하지 않는다.
Trusted INIT/arm/독립 root 승인·수용 정책은 유지한다. 포트의 동일 monotonic clock으로
호출마다 이전 accepted lease·현재 시각을 검사한다. 최초 감시는 기존 80 ms다.

새로 Accepted된 명령만 capacity 8 FIFO에 원래 CommandContext와 함께 저장한다.
Duplicate/invalid packet은 대기열에 넣지 않는다. Overflow는 backlog 폐기·latch·local protection이다.
Dispatch는 최대 8개를 검사하고 최신 수용 sequence보다 이전 항목을 건너뛴 뒤 최신 묶음 하나만 보낸다.
이미 최신 명령으로 연속성을 유지했다면 오래된 superseded 항목의 만료만으로 전체 fault를 만들지 않는다.
현재 accepted 명령 자체의 만료는 새 입력보다 먼저 latch하는 정책을 유지한다.

Gateway는 원래 actuator Epoch/Sequence/Source/CausalSequence·parent/oldest/expiry를 보존한다.
같은 명령을 100 Hz counter로 다시 만들어 보내지 않는다. 새 frame을 실제 생성할 때 stream별
P05 counter만 사용하며 trusted 새 INIT에서만 초기화한다.
정상 전달 순서는 Front Steering→Brake 두 frame, Rear Drive 한 frame이다.
**Atomic 수용은 두 CAN write의 atomic delivery를 의미하지 않는다.**
양쪽 frame을 먼저 encode하고 각각의 송신 직전·직후에 lease/clock을 다시 검사한다.
첫 write 뒤 만료/실패하면 나머지 정상 전송을 중단하고 Front 전체 보호를 요청하며 partial 여부를 기록한다.
송신 실패 뒤 normal frame을 재시도하거나 시각을 갱신하지 않는다.

## SocketCAN 경계와 보장 범위

`socketcan::ZoneGatewayPort`는 기존 domain codec/ABI adapter와 전용 nonblocking Endpoint를 사용한다.
`Endpoint::send_before`는 ABI 직렬화 후 `write` 직전에 exclusive expiry를 검사한다.
만료는 write 없이 false, EAGAIN/I/O 오류는 port에서 실패로 변환해 gateway latch에 연결한다.
기존 `send`의 wire/직렬화 계약은 유지한다.

이는 **최종 userspace enqueue guard**다. Check와 syscall 사이 scheduling, kernel TX queue,
실제 bus delivery나 remote Leaf 수신 시점까지 원래 composite expiry가 보장된다는 뜻은 아니다.
기존 32-byte CAN command에는 parent/expiry가 없다. Remote Leaf lease 표현/검사 또는 별도
trusted deadline 전달 경로, kernel backlog/rejoin 처리는 다음 계약 결정에 남긴다.
실제 버스의 두 frame partial delivery를 rollback했다고 표시하지 않는다.

## Local safety와 Leaf 선택

`LocalSafety`는 첫 protection cause를 latch하고 정상 ingress/dispatch와 독립적으로
ProtectionPort를 호출한다. 수신자 불가/거부이면 Pending이며 poll당 한 번 재시도한다.
Handoff가 수용되면 재요청을 멈추지만 정상 주행 latch는 유지한다.
Trusted coordinator의 `request_protection`도 정상 payload/mode를 우회하지 않는 별도 입력이다.
Gateway와 local monitor의 <=10 ms 실행은 caller 책임이며 이번 wall-time workload 측정 대상은 아니다.

`simulation/runtime/ZoneLeafProtection`은 **명시적 same-host SIL 연결**이다.
Front는 Steering/Brake 둘 다, Rear는 mandatory EV DriveController의 trusted local port를 호출한다.
Leaf는 `request_local_protection`에서 기존 정책을 선택하고 UpstreamProtection을 latch한다.

| 담당 Leaf | 선택하는 기존 출력 | 실제 성공 판정 |
| --- | --- | --- |
| Steering | Hold, 지연된 정상 motion 취소 | 별도 angle sensor/plant |
| Brake | Protect, `max(실제 압력, 설정 floor)`의 SIL primitive; 높은 압력 해제 금지 | 별도 pressure acquisition·floor observed; 요청 자체로 도달 선언 금지 |
| Drive | Zero target/zero envelope, 양수 추진·음수 회생 목표 폐기 | 실제 torque의 zero ramp·관측 residual, 즉시 실제 0 선언 금지 |

Adapter는 plant를 진행하거나 actual을 생성하지 않는다. Initialized Leaf가 해당 보호 출력을
선택했을 때만 handoff를 수용한다. 이 ACK는 물리 도달/차량 정지 ACK가 아니다.
Drive는 이미 clock fault/stopped여도 이 trusted port에서 Zero를 선택하며 기존 fault를 유지한다.
Remote CAN protection signaling이나 AUTOSAR RTE/BSW/OS transport를 구현한 것은 아니다.
그 경로가 끊기면 기존 Leaf 자체 source-age/timeout 보호가 남는다.

Recovery는 더 큰 trusted Epoch/비후퇴 시각 INIT다. Gateway INIT는 Leaf를 reset하지 않는다.
각 Leaf INIT와 계속되는 physical model mapping·전원/health 확인은 coordinator가 별도로 수행해야 한다.
Rear power/permission/BMS constraint 전달·non-driving startup·피드백 감시와 full runtime은 후속이다.
재현/시험 범위는 [학습 안내](../learning/m4_zone_gateway.md)에 기록한다.
