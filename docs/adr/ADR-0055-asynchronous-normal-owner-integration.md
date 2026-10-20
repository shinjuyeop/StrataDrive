# ADR-0055: M4 정상 운전의 비동기 owner 연결과 재현 근거

Date: 2026-10-19. Status: **Native Host 구현 / component 검증; M4 전체 수용 후속**.
[ADR-0054](ADR-0054-trusted-session-owner-loops.md)의 세션 경계 위에 정상 운전 경로를 연결한다.
현재 상태와 검증 분모의 기준은 [project_status](../project_status.md), 날짜별 기록은 [quality policy](../quality_policy.md)다.

## 소유권과 메시지

| Owner | 혼자 수정하는 상태 | 전달하는 값 |
| --- | --- | --- |
| Central | SessionCoordinator·Central ingress·VM/allocator/NormalStop·issued parent history | 원래 lifecycle/vehicle root·power output·scoped command·arm/stop operation |
| Front Zone | Front gateway·Steering/Brake Actual RX·health monitor | 두 Leaf의 CAN enqueue·정확한 operation result·원천 Actual/status |
| Rear Zone | Rear command/power gateway·Drive Actual/BMS RX·health monitor | Drive/Power CAN enqueue·operation result·원천 Actual/BMS/status |
| Steering / Brake / Drive | 해당 controller·command RX·selected output | Actual CAN frame·arm/terminal ACK·물리 출력 snapshot |
| BMS / Power | 해당 controller·limits 또는 lifecycle RX | 실제 sensor 기반 limits/local gate 또는 power status/coil output |
| Physical | angle/pressure/torque·단일 EvPowerModel의 Battery/SOC·RC/접점 | 독립 취득 identity/time/dependency를 가진 sensor snapshots |

Native 실행은9개 독립 thread다. Central ingress의 session role은 Central thread에 같이 배치한다.
다른 owner의 controller/gateway를 직접 호출하지 않는다. 과거 synchronous SIL adapter는 이 실행에서 사용하지 않는다.
Main은 생성·grants 준비와 join 후 결과 취합만 수행한다. 논리 시험은 동일 객체/port를 순서대로 호출한다.

정상 작업·TX result·feedback은 **방향별 capacity8 SPSC FIFO**이며 cycle당 각 link 최대8개를 처리한다.
Sensor/selected actuation과 local BMS→Power gate는 publisher/reader가 각각 하나인 latest snapshot이다.
Phase/control 메시지를 latest-value로 덮어쓰지 않는다. Source time·epoch·sequence·parent·expiry는 그대로 복사한다.
Control/ACK packet과 CAN bytes는 별도 typed 계약이다. DDS IDL/authentication·실제 CAN 전기 특성의 구현을 뜻하지 않는다.

## 실행 허가·결과·보호

1. 세션8-role의 Prepare/INIT/Release ACK가 모두 완료된 뒤 해당 Epoch에서 한 번만 global gate를 연다. 보호로 닫힌 gate를 일반 poll에서 다시 열지 않는다.
2. 실제 BMS release checks/dwell·power OFF/READY·두 Zone/각 Actual의 current sample을 기존 판단 함수가 확인한다.
3. 각 Leaf가 자기 fresh sensor로 arm하고 ACK한다. Zone은 그 ACK 뒤 자기 gateway를 arm한다. Central은 양 Zone ACK를 기다린다.
4. 정상 callback 성공은 **큐 enqueue**다. Epoch/token/operation/Zone/source/deadline을 대조한 TX result를 별도로 받는다.
5. Front Steering/Brake 전송 결과가 모두 성공해야 해당 batch의 Rear 명령을 queue에 넣는다. 부분 성공은 재전송하지 않는다.
6. Negative result·기한 만료·queue continuity·owner/local fault는 정상 gate를 닫는다. Zone·Leaf의 보호 진입도 Central의 후속 인지를 기다리지 않고 atomic gate를 닫는다. 다시 여는 동작은 Central의 새 전체 세션 Release만 소유한다. 별도 atomic protection signal은 정상 FIFO를 거치지 않는다.

Protection selection ACK는 실제 Leaf의 Hold/Protect/Zero·BMS inhibit/Power shutdown 선택을 뜻한다.
압력 도달·실제 토크0·차량 정지·접점 open을 뜻하지 않는다. 이 물리 반응은 별도 sensor/CSV로 관측한다.
Zone/Leaf의 기존 local timeout은 Central ACK를 기다리지 않는다. Overflow link는 join/교체가 필요하며 새 Epoch만으로 복구하지 않는다.
Broken/missing Epoch store는 자동 초기화하지 않는다. CLI의 durable grant/lock/fsync는 thread 시작 전 수행한다.

## 주기와 원래 authority 안의 배분

Leaf/VM/Zone 관측의 nominal 주기는10 ms, BMS/allocation은20 ms다. Physical은1 ms, transport service는200 μs다.
Worker sleep은 절대 release 기준이며 놓친 slot을 burst로 따라잡지 않는다. 실제 callback·센서 시각은 실제 monotonic time이다.
기존 M3처럼 **최소 함수 호출 간격1 ms와 외부10/20 ms release**를 분리한다. Legacy component 기본 guard는 유지한다.
30 ms functional owner gap, source age30/50 ms, dependency70 ms와 원래 expiry는 늘리지 않았다.

동기 호출 시점의 가장 최근 발급 grant와 실제 수신 grant는 다를 수 있다.
Central은16-entry issued history에서 **수신한 permission의 원래 parent**를 조회한다.
Allocation은 해당 nominal release 이후 발급한 grant가 실제 ingress에 들어올 때까지 기다린다.
그 grant의 원래 expiry가 다음20 ms release도 지원하는지 확인한다. 새 발급값으로 수신 상실을 덮지 않는다.
Waiting/arm 중에도 allocation runnable의 감시는 계속하며 grant 대기를 owner 정지로 취급해 숨기지 않는다.

Finite scenario issuer의 lifecycle 요청도 VM release와 맞추고 vehicle root는20 ms allocation release와 맞춘다.
이를 별도 상대 sleep으로 갱신하면 원래 root/ack가 오래돼 다음 command가 발급되기 전에 기존 권한이 만료될 수 있다.
초기 개발 실패는 그대로 보존하고 phase/수신 순서를 수정했다. 원래 age·expiry를 연장해 통과시키지 않았다.
Central은 새 permission ingress에서 allocation만 재개할 수 있으며 VM을 다시 실행하거나 grant 시각을 갱신하지 않는다.

## 정상 종료·재가입

NormalStop은 기존 fresh actual dwell로 torque/speed/pressure를 판단한다. 최신 normal batch가 settle된 뒤
allocator를 quiesce하고 Leaf terminal 선택→두 gateway terminal 선택→정확한 ACK 순서로 넘긴다.
Handoff pending 동안 새 Enable/AllowNormal을 계속 발급하지 않는다. 원래 기한 안에서 ACK를 먼저 처리하고
그 뒤 Shutdown child를 발급해 실제 접점 open·bus discharge/OFF를 확인한다. ACK 유실·lease 만료는 보호다.
Fresh stop intent가 끊기면 기존 권한이 만료한다. Intent 갱신은 scenario issuer의 명시적인 새 요청이며 coordinator의 자체 연장이 아니다.

재가입은 gate 폐쇄·물리 정지/방전 확인·더 큰 durable Epoch·전체 INIT/ACK·BMS fresh dwell/HV readiness를 다시 거친다.
SIL Brake의 protection-mode latch는 새 trusted global Epoch release에서만 해제한다.
`BrakePressureResponse::begin()`은 pending demand/mode만 정리하며 압력·model Epoch·sensor sequence를 보존한다.
SOC/energy/RC·토크·조향각을 초기값으로 돌리는 physical scenario reset은 호출하지 않는다.
Same Epoch/일반 CAN frame이나 nominal Hold로 보호를 지울 수 없다.

## 선택적 capability와 critical Actual 구분

새 permission에 묶인 가장 오래된 dependency가 이전 Inhibit의 dependency보다 과거일 수 있다.
Drive의 monotonic capability cursor는 이를 fresh 값으로 꾸미지 않고 unavailable로 낸다.
Degraded/NormalPath의 **범위 안 torque·fresh speed가 알려진 Actual**은 canonical InputsInvalid/없는 capability와 함께 사용할 수 있다.
회생 가용량은 unknown이므로 allocator가 새 negative demand를 금지하고 friction fallback을 사용한다.
Torque/speed 누락·stale·범위 초과·보호 origin은 계속 critical이다. Disabled/valid-zero capability는 알려진0이어야 한다.
이는 SYS-SAFE-005의 선택적 회생 가용량과 critical Actual 구분이며 wire/schema/P05 변경은 아니다.

## 근거와 남은 범위

[Component 추적표](../test-plan/component_traceability.csv)에서 requirement→함수→실제 GTest→criterion→결과를 연결한다.
[재현 안내](../learning/m4_async_owners.md)와 [최소 공유 근거](../test-plan/evidence/m4_async/README.md)에 실행 명령·대상 commit·환경·입력·수치와 그래프를 둔다.
같은 전체 CTest 결과를 재사용하며 컴포넌트 PASS를 system TC PASS로 올리지 않는다.

현재 native mailbox/CAN frame SIL과 finite trusted input issuer다. Wheel speed는0 rad/s fixture이며 longitudinal motion/controller는 M6–M8다.
SocketCAN에서 실제 remote parent/composite lease/arm/protection을 전달하는 wire 계약·독립 process/DDS/Host bridge는 후속이다.
Owner body의4 ms 초과 관측과 실제 period/loss response를 보고하되 전체 M3 timing 수용·Target/SCHED_FIFO 검증으로 확대하지 않는다.
MBD·AUTOSAR 확장 순서, 기존 M3 timing 예외·학습자 review와32개 요구/29개 system TC의 NOT RUN은 유지한다.

후속 owner/방향별 고장·joined 복구·M3 독립 guard/FIFO cohort는 [ADR-0056](ADR-0056-m4-faults-and-independent-execution-watch.md)과 최신 project_status를 따른다. 위 관측 수치는 당시 범위다.

후속 [ADR-0059](ADR-0059-pending-command-allocation-settlement.md)는 in-flight batch가
있는 동안 다음 due allocation을 보류하는 계약을 추가했다. 결과 deadline·기존 applied
command expiry·감시/보호를 연장하지 않으며, 정상 결과 후 fresh 입력으로 기존 release grid를 따른다.
