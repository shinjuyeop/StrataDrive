# ADR-0058: 원격 owner authority와 Host 통신 후보 경계

Date: 2026-10-20. Status: **원격 계약/Leaf component 구현; middleware 후보 실험·M4 종료 검토**.
[ADR-0054](ADR-0054-trusted-session-owner-loops.md)/[0055](ADR-0055-asynchronous-normal-owner-integration.md)/[0056](ADR-0056-m4-faults-and-independent-execution-watch.md)의 상태 소유권, 원래 시각, 보호 latch를 유지한다.

## 결정과 구현

[Owner wire v1 ICD](../icd/owner_wire_v1.md)는 canonical message contract를512byte 이내 고정 width로 직렬화하고 outer CRC32C로 route·clock·parent/expiry·raw CAN까지 검사한다. CAN/DBC/P05 layout/DataID/counter는 바꾸지 않는다. SYS-COM-002의 interface refinement v0.6으로 기록했다.
Codec library는 controller/local atomic/SPSC 구현을 포함하지 않는다. 구조적 decode와 도메인 admission·trusted peer 검증은 별개다.

`RunLeaseIssuer`는 실제8-role SessionCoordinator의 마지막 Release ACK 뒤에만 global credit를 발급한다.
각 `RunLeaseGate`는 trusted local INIT의 정확한 Plan과 common clock에 묶인다. Source age30ms, maximum life60ms, exclusive expiry를 검사하고
이전 credit 만료를 늦은 새 credit보다 먼저 검사한다. Same-Epoch latch를 해제하지 않는다. 새 전체 INIT만 bind할 수 있다.

`RemoteLeafEndpoint`는 실제 AsyncLeafOwner 하나와 그 **프로세스 내부만의** gate/link를 단독 소유한다.
정상 ingress는 local session+global credit 뒤 허용하지만 실제 arm·센서/요청/command composite context는 기존 actor가 다시 검사한다.
INIT 전후 센서/보호 service를 멈추지 않는다. Credit 만료·명시적 보호·failed FIFO는 실제 actor 보호로 이어진다.
보호 ACK는 해당 Leaf가 실제 선택한 뒤 보내며 sender/token별 duplicate 시각이 불변이다. 멈춘 peer/물리 watchdog의 ACK를 합성하지 않는다.
종료 lease의 source/expiry와 원천 CAN Actual의 payload/source/P05는 전달만 한다.

Host 첫 profile은 동일 kernel CLOCK_MONOTONIC과 trusted launch-domain을 사용한다. Packet으로 offset/Epoch를 학습하지 않는다.
Offset/uncertainty를 포함한 시간 경계 산술은 시험했지만 inner CAN/RX가 다른 clock을 쓰는 runtime은 gate가 거부한다.
Target/다른 kernel의 sync·uncertainty·CAN source mapping은 후속 배포 gate이며 구현 완료로 취급하지 않는다.

Component 시험에서 진단 원인이 `Expired`→`Protection`으로 덮이는 결함을 찾아 최초 원인을 보존했다.
36개 신규 시험(30unit/6logical)과 기존912개 전체를 normal·ASan/UBSan에서 검사했다.
새36개 TSan은 PASS, native9개 TSan 중1개 정상 운전 CommandDelivery FAIL은 별도 OPEN으로 유지한다.
추가1회 trace 진단 PASS는 원래9개 실패를 대체하지 않고 원인을 확정하지 못했다.

## TBD-05 후보 비교 범위

DDS 기본 방향을 유지한다. 실험은 **Cyclone DDS11.0.1 direct C API**와 **Zenoh-C1.10.1 stable C API**를 비교한다.
ROS 2 executor/graph를 도입하지 않고 기존 C++17 owner port에 byte adapter를 두는 방향이다.
실험 dependency는 공식 release URL/SHA를 검증해 ignored build 아래에만 설치한다. 일반 build는 dependency/network fetch 없이 유지된다.

| 항목 | DDS 후보 | Zenoh 후보 |
| --- | --- | --- |
| Schema/API | IDL fixed packet512 + length, direct C API | C bytes/key expression, canonical owner packet |
| 연결/격리 | explicit UDP peers, multicast off, domain37 | peer TCP explicit endpoint, multicast scouting off |
| sample policy | RELIABLE KEEP_ALL, volatile,8/1/8 resources, blocking0 | publisher DROP, mutex callback queue8 |
| owner 접점 | owner thread가 bounded take; background DDS thread가 controller를 호출하지 않음 | callback는 고정 queue에 복사만; owner가 bounded take |
| 관측 | write/take 오류 **및 reader rejected/lost status**, 적용 QoS readback | put 오류·callback overflow; 실제 affinity/policy |
| 원래 freshness | reliable 재전송도 원래 expiry/epoch 검사; stale reply는 ACK 아님 | 재접속/queue도 원래 expiry/epoch 검사 |

두 독립 process를 user+network namespace/veth에 배치하고 똑같은100+3 requests/clock/부하로 실제 방향별100% loss/100ms delay와 overflow를 주입한다.
단순 source-preserving **echo**이며 실제 Central allocator/Zone gateway/Leaf Actual 배포가 아니다. Full session/rejoin 또는 멈춘 ECU 보호를 이 실험으로 주장하지 않는다.
[사전 v1](../test-plan/m4_middleware_probe_protocol.md)의36회는30 PASS/6 FAIL로 보존한다.
DDS up-loss3은 총 수신 수만 세어 reliable backlog의 늦은 응답을 놓쳤고, overflow3은 reader rejection 관측이 빠졌다.
[V2](../test-plan/m4_middleware_probe_protocol_v2.md)는 원래 기준을 유지하며 expired echo와 DDS reader status/readback을 추가한 새36회다.
V2는36/36 PASS다. 공유 근거의 두 결과 묶음에서 실제 분모/판정을 확인한다. 짧은 echo 결과를 성능 우월성/RT/전체 DDS 수용으로 확대하지 않는다.

Host M5 후보는 기존 DDS 방향/Cyclone direct API를 우선한다. 다만 application/C wrapper ASan4/4 PASS와 별개로, wrapper TSan4/4 FAIL·완전 계측 DDS SDK 추가2/2 FAIL을 보존한다. DDS entity-index/hopscotch/GC 경고를 실제 lifetime race 또는 progress-based reclamation의 sanitizer 해석 문제로 구분해야 한다. 억제하거나 단순 false positive로 판정하지 않는다(OPEN-M4-MWTSAN-01). Zenoh 전체 Rust 계측은 toolchain 부재로 미실행이다. 특정 middleware의 배포 수용은 후속 진단 전까지 보류한다. Zenoh는 대안으로 보존하고 채택하지 않는다.
Cyclone/Zenoh 내부 memory·worst-case blocking이 이 probe로 증명된 것은 아니다. M5 adapter에는 별도 bounded application mailbox와 permanent failure latch가 필요하다.
Normal FIFO가 실패하면 정상 dispatch를 멈추고 보호 선택/채널 실패를 별도 기록한다. Write 성공은 enqueue조차 아닌 middleware 수용 결과일 뿐, 실제 ECU/물리 ACK가 아니다.
Session/control·normal work/result·원천 feedback·protection의 독립 bounded lane/QoS와 원래 deadline 검사는 첫 adapter 구현에서 검증해야 한다.
보호를 정상 FIFO와 같은 막힌 lane에만 의존시키거나 shared atomic bypass로 대체하지 않는다. Channel 재생성은 owner stop/join 뒤, 신규 durable Epoch/전체 handshake/arm으로 한다.

## M4/M5 gate

[M4 exit review](../m4_exit_review.md)는 timing 실패·TSan native 기능 실패와 middleware 관측 보완을 함께 대조한다.
현재 전체 M4 종료를 선언하지 않는다. 첫 M5 제어 adapter의 **구현은 아직 시작하지 않았고**, echo probe만 실행했다.
기존32req/29 system TC·Target/remote vehicle runtime NOT RUN, 학습자 직접 재현/설명 REVIEW PENDING을 유지한다.
MBD M6 MIL→M8 동등성, AUTOSAR/RTOS Target pilot 순서도 유지한다.
