# ADR-0059 — Pending command와 allocation release의 분리

Date:2026-10-20. Status: **ACCEPTED for Host component implementation**.
M4 종료·Host timing·Target 수용은 별도이며 현재 기준은 [project_status](../project_status.md)다.

## 문제와 관측

ADR-0055의 Front 성공→Rear 송신 순서와20ms TX result envelope는 유지한다.
기존 port는 진행 중인 batch가 있으면 `deliver_commands()`를 false로 반환했다.
Coordinator는 다음20ms 배분에서 이를 실제 전달 실패와 동일한 CommandDelivery로 해석했다.
전송 결과가 아직 유효한 대기 상태인지, timeout인지, 적용 중인 명령이 만료됐는지 구분하지 못했다.

`29b8221` 논리 재현의 초기 clock은1s다. 아래는 동일 clock의 **경과 ms**이며,
root 생성과 CAN 명령 생성, 수신 처리와 실제 출력 발행을 구분한다.

| 사건 | Rear result19.8ms 지연 | Front/Rear result 각각12ms 지연 |
| --- | --- | --- |
| 현재 root 생성 / CAN 명령 생성·Front 최초 송신 | 1001 /1005.2 | 1001 /1005.2 |
| Front 수신·Leaf 처리 / Central 결과 도착 | 1005.4 /1005.4 | 1005.4 /1017.4 |
| Rear 최초 송신 / Leaf 처리 | 1005.4 /1005.6 | 1017.4 시도 때 이미 gate 닫혀 송신 거부 |
| Front / Rear 전송 deadline | 1025.2 /1025.4 | 1025.2 /새 Rear envelope 생성 안 됨 |
| 새 명령 내부 expiry | 1031.000001 | 1031.000001 |
| 이전 Rear 명령 expiry | 새 명령으로 대체됨 | 1011.000001, 실제 local service1011.2에서 보호 |
| 다음 nominal allocation / grant ingress 충족 | 1021 /1025.2 | local 보호가 먼저 발생 |
| 수정 전 Central 보호 | 1025.2: 아직 pending이라는 이유 | 1015: local 보호 관측;1017.4ms의 늦은 Front 결과로 복구 안 됨 |
| 수정 후 | pending 보류;1025.4의 exact-expiry 응답은 거부·보호 | 기존 만료 보호 유지 |

TX result는 Zone의 CAN 전달 처리 결과다. `leaf-completed`는 Leaf 수신 처리,
`leaf-output-published`는 해당 명령 identity를 가진 controller 출력 snapshot 발행이다.
Physical owner가 이를 적용하는 별도 step과 angle/pressure/torque/HV 응답은 physical CSV에서 확인한다.
어느 관측도 다른 endpoint의 ACK나 실제 물리 도달로 바꾸어 기록하지 않는다.

## 선택한 계약

1. 정상 batch는 하나만 in flight다. Front/Rear 순서·부분 실패 보호는 그대로다.
2. 다음 배분이 due인데 batch가 진행 중이면 `allocation_ready()`가 false다.
   새 command를 계산·queue·재전송하지 않고 **due release 한 건**을 보류한다.
   보류 중 nominal allocation 기준 시각을 갱신하거나 미처리 release를 FIFO에 쌓지 않는다.
3. Central의 transport/status/VM과 실제 owner runnable은 계속 실행한다.
   `ControlAllocation::poll()`은 원래 request/support expiry와30ms tick-gap을 검사한다.
   poll은 성공적인 allocation tick으로 간주하지 않는다. 기다림으로 감시 시한을 연장하지 않는다.
4. 결과가 원래 시한 안에 완료되면 다음 service에서 **현재 root·fresh feedback·실제 수신 permission**을
   재검증하여 계산한다. 지연 동안 계산해 둔 command를 보내지 않는다.
   external release의 기존20ms grid에 정렬하며 missed release를 burst로 따라잡지 않는다.
5. `service()`의 result timeout/negative/mismatch/overflow와 독립 Zone·Leaf의 명령 만료 보호가 우선한다.
   각 result의 exclusive deadline, 최초 sent, 내부 command expiry·Epoch/token·parent/lease·CAN/P05 불변이다.
   아직 응답을 기다릴 수 있다는 사실은 이전 applied command의 수명 연장 근거가 아니다.
6. 유효기간 내 일시적인 지연은 정상 복귀할 수 있다. 지속적으로 처리량이20ms 주기를 따라가지 못하면
   기존 command/authority가 만료되어 보호할 수 있다. 이를 통과시키기 위한 deadline 증가는 하지 않는다.
7. 같은 Epoch의 latch/gate는 자동 해제하지 않는다. 정상 Stop은 기존 batch settlement를 기다리고,
   고장 복구는 기존 physical readiness·더 큰 durable Epoch·INIT/ACK·readiness·arm을 따른다.

## 선택 이유와 범위

Batch를 병렬 전송하거나 이미 계산한 command를 덮어쓰는 방식은 기존 Front 부분 실패 계약과
권한/sequence 의미를 바꾸므로 선택하지 않았다. Pending을 성공으로 반환하고 새 command를 버리는 방식도
실제로 전송하지 않은 allocation을 완료된 것처럼 기록하므로 사용하지 않았다.
기존 grant ingress 대기 경로에 in-flight 조건과 감시를 추가하는 작은 변경으로 구현했다.
일시 지연 예는 Front0.2ms/Rear19.6ms result delay를1000–1020ms에만 주입한다.
Rear 결과는1025.4ms 도착, 원래 deadline1025.6ms 전에 성공하고 같은 service에서 fresh allocation을 재개한다.
다음 root는1041ms로 nominal20ms 간격을 유지한다. 지속 주입 대조군은 Rear 명령1551.000001ms 만료를 숨기지 않는다.

기존 `PendingRearResultSelectsCommandDeliveryBeforeIndividualExpiry` 이름은 역사적 재현을 위해 유지한다.
Assertion은 “기한 전 CommandDelivery”에서 “기한 전 보류, exact expiry에서 ResultLate 보호”로 변경했다.
기존966개 시험 이름과 안전 시한은 유지한다. 변경 전/후는 [새 근거](../test-plan/evidence/m4_settlement/README.md)에 보존한다.
이 논리 결함 수정은 과거 native TSan untraced 사건의 원인을 확정하는 증거가 아니다.
Host PC와 Jetson 한 대/내부 여러 vECU 배치, MBD·AUTOSAR 순서와 M5 adapter 미착수는 유지한다.
