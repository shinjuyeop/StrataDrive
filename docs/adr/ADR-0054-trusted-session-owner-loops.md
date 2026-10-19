# ADR-0054: trusted 세션 준비·INIT·실행 허용과 owner별 mailbox

Date: 2026-10-19. Status: **Host session component 구현·시험 / 정상 runtime 비동기화 후속**.
[ADR-0053](ADR-0053-central-coordinator-and-same-host-binding.md)의 Central 실행 owner에
명시적인 세션 제어 경계를 추가한다. Central–각 Zone의 병렬 연결과 담당 Leaf 구분을 유지한다.

**후속 구현:** 이 문서의 수치·직렬 fixture 설명은 해당 단계의 이력이다. 정상 owner 비동기 연결·실제 BMS/센서 경로·정상 종료/재가입은 [ADR-0055](ADR-0055-asynchronous-normal-owner-integration.md)에서 진행했다. 현재 범위·최신 결과의 기준은 [project_status](../project_status.md)다.

## 결정과 소유권

Central의 `SessionCoordinator`는 영속 issuer에서 **이미 발급한** 더 큰 application Epoch만 받는다.
`EpochStore::issue()`의 lock/fsync는 trusted startup에서 실행하며 runnable·CAN 수신에서 호출하지 않는다.
실패·중단된 grant도 소모한다. Store 상실/손상은 자동 bootstrap/reset하지 않는다.
CAN frame·ACK만으로 새 Epoch나 INIT 권한을 얻을 수 없다.

세션 참여자는 Front Zone, Rear Zone, Steering, Brake, Drive, BMS, Power, Central ingress의8개 role이다.
Zone 역할은 gateway/monitor·own-context, Leaf 역할은 각 controller, ingress는 독립 Actual/permission/Zone status RX를 소유한다.
중앙 세션 owner는 callback/ACK로 상태를 확인하며, 원격 owner의 mutable 상태를 직접 초기화하지 않는다.
현재 실제 actor binding은 직렬 same-host 시험이며 wire topology나 remote INIT 구현을 뜻하지 않는다.

| 단계 | 동작 | 다음 단계 조건 |
| --- | --- | --- |
| Prepare | 정상 producer/ingress 폐쇄·기존 work flush, 독립 보호/물리 회복 계속 | 모든 role의 동일 proposal·fresh Prepared ACK |
| Initialize | 준비 완료 후 공통 future enable 지정, 각 owner가 자기 actor/RX INIT | 모든 role의 정확한 plan·Initialized ACK |
| Central commit | 실제 coordinator의 참여자 preflight 뒤 Central private owner INIT | callback 성공·원래 deadline 이내 |
| Release | 각 owner에 실행 가능 상태 전달 | 모든 Release ACK 뒤 **Central global run gate** 개방 |
| Abort | global gate 폐쇄·Central 보호·best-effort owner 보호 요청 | 더 큰 trusted Epoch의 새 Prepare로만 재시도 |

Local Ready는 global run 허가가 아니다. Runtime caller는 `SessionCentralLoop::run_enabled()`를
모든 정상 입력·정상 runnable 앞에서 검사해야 한다. Release가 일부만 도착해도 Central은 명령을 발급하지 않는다.
통신 복구·일반 packet·같은 Epoch INIT는 이 절차를 대신하지 않는다. Running에서 새 준비를 하려면 먼저 명시적으로 cancel한다.

## 시각과 실패 경계

현재 Host functional 값은 준비2 s, future INIT lead20 ms, enable 뒤 commit window 최대20 ms,
message age30 ms, 세션 owner 관찰 gap30 ms다. Commit deadline은 원래 Prepare deadline을 넘지 않는다.
각 callback 뒤 실제 clock을 재조회하고 exclusive deadline을 먼저 적용한다. Late ACK가 timeout을 이기지 못한다.
Near-uint64-limit 계산도 남은 budget 안에서 수행해 enable/deadline wrap을 차단한다.
이는 실차 calibration·FTTI나 기존 M3의4 ms 완료 guard 변경이 아니다.

ACK는 role·phase·epoch·requested/deadline/enable·source·성공 여부가 정확해야 한다.
중복 ACK/control은 변하지 않는 원래 ACK만 반환하며 시각·deadline을 갱신하지 않는다.
Mutation/wrong role·phase·plan·stale/future는 진행을 만들지 않는다. Negative ACK·clock/gap·timeout·부분 send/commit 실패는 latch한다.
부분 INIT의 rollback은 하지 않는다. 일부 actor가 새 Epoch에 들어가도 global gate는 닫히며 다음 시도에는 더 큰 Epoch가 필요하다.

Abort가 유실돼도 Prepared/Initialized owner는 원래 deadline으로 자체 보호한다.
보호/control-plane service는 run gate가 닫혔거나 세션 fault인 동안에도 호출한다.
Ready 뒤 정상 command/permission lease와 watchdog은 별도 정상 runtime 책임이며 세션 ACK로 갱신하지 않는다.

## Mailbox와 물리 reset 조건

Role당 Control/ACK SPSC FIFO를 따로 두며 각 capacity는8이다. Producer/consumer는 각각 정확히1개 owner다.
Acquire/release atomic cursor로 전달하고 overwrite·allocation·blocking을 하지 않는다.
Owner step은 control 최대8개, Central step은 role당 ACK 최대8개를 처리한다.
Overflow는 backlog를 무효화하고 링크 continuity를 영구 latch한다. 양 owner를 join한 뒤 transport를 교체해야 하며
새 Epoch만으로 깨진 queue를 reset하지 않는다. 기존 single-owner CAN RX queue와 용도가 다르다.

`VehicleSessionInit`은 준비 때와 실제 INIT 때 trusted sensor port를 다시 확인한다.
알려진 같은 model Epoch, source/dependency age≤20 ms, wheel speed0..0.01 rad/s,
|torque|≤0.1 Nm, bus0..30 V·모든 contactor open을 요구한다. Unknown/NaN/future/held-stale는 통과하지 않는다.
센서 source·dependency 시각을 덮어쓰지 않으며 물리 정지/방전 완료를 ACK만으로 만들지 않는다.
이 수치는 functional SIL reset precondition이며 차량 calibration은 별도 검토한다.
물리 상태가 위험하면 Prepare를 Pending으로 유지하고 외부 보호·회복을 계속해야 한다.
BMS INIT 뒤에도 기존 release-band/fresh dwell을 다시 통과해야 한다.

Controller INIT는 application 상태만 초기화한다. Model Epoch/SOC/토크·angle·압력·접점/RC plant를 reset하지 않는다.
Steering/Brake/Drive는 NonDriving으로 시작하고 정상 구동 arm은 기존 준비 판정을 따른다.
준비 port는 자기 ingress/work만 quiesce하고, 자기 보호/센서 취득을 계속해야 한다. Actor끼리 교차 호출하는 기존
동기 normal/protection SIL adapter를 여러 스레드에서 동시에 호출하면 안 된다.

## 검증 범위와 다음 경계

[학습 기록](../learning/m4_session_bootstrap.md)의 모듈 시험, 영속 grant 연결, 실제8-role INIT/실패/rejoin·물리 보존을 검사한다.
독립8개 owner thread 시험은 typed mailbox·자기 port 접근만 확인하며 논리 clock/barrier를 사용한다.
정상 VehicleCoordinator/Zone/Leaf workload의 wall-time·SCHED_FIFO·Target timing 시험이 아니다.

현재 caller가 기존 normal actor 접근을 직렬화한다. 기존 EV runtime/demo의 request/grant fixture를 아직 교체하지 않았다.
다음은 normal 요청·arm·전송 결과·status/Actual snapshot·보호 요청을 비동기 owner port로 옮기고 global gate와 연결하는 일이다.
그 뒤 전체 workload의 독립 정지/partition·타이밍을 검사한다. Remote Leaf composite lease/stop/protection wire·DDS/Host feedback bridge는 후속이다.
M4 완료·M3 예외 해소·system TC PASS나 AUTOSAR/실차 안전성 검증을 주장하지 않는다. MBD는 M6–M8 계획을 유지한다.
