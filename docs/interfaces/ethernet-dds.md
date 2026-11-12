# Ethernet / DDS ICD baseline

이 문서는 DDS 후보의 의미·QoS 검토 계약이다. 현재 Host Central–Front/Rear 제어 통신은
[채택된 SOME/IP 경로](someip-rear-adapter.md)를 사용한다. `IF-DDS-*`는 보존한 semantic ID다.
Target 통신 방식은 TBD-05/15이며 DDS로 확정하지 않았다.

DDS 정규 제어 adapter는 미채택이고 control gate는 CLOSED다. 선택형 Host 진단에는
Cyclone DDS 11.0.1 direct C API·고정512byte Packet IDL·owner-wire codec/netns echo가 있다.
[종료·TSan 미해결 기록](../test-plan/evidence/m5_dds_shutdown_followup/README.md)과
[환경·QoS 검토](../test-plan/evidence/m5_dds_operating_profile/README.md)를 보존한다.
SOME/IP 채택은 이 과거 실패의 해결 판정이 아니다.
현재 구현·수용 범위는 [프로젝트 상태](../project-status.md)를 따른다.

[ZON-01 v0.5 / ADR-0021](../archive/design-decisions.md#adr-0021)에서 Central은
별도 vehicle management/allocation/session/feedback bridge를 소유하고 각 Zone과 독립 통신한다.
Front↔Rear application relay는 정상 경로에 필요하지 않다. 전체 DDS 제어용 IDL/runtime은 미구현이다.

M4 [scoped command 수용 component](../learning/vehicle-lifecycle-guide.md)는
`interfaces/central/allocated_commands.hpp`의 in-process 계약을 사용한다.
Front atomic Steering/Brake·Rear Drive와 원래 vehicle root·oldest dependency·exclusive expiry를 보존한다.
독립 trusted root 승인·명시적 arm, scope/range/mode/progress/age/expiry와 local latch를 검사한다.
이는 DDS serialization/integrity/authentication/clock sync 구현이 아니다.
후속 [CAN gateway/local protection](../learning/vehicle-lifecycle-guide.md)은 원래 source/expiry 보존·각 write guard와
same-host Leaf의 Hold/Protect/Zero 선택을 연결했다. 두 독립 vCAN interface도 시험했다.
[Rear power/permission/BMS limits·초기 구동](../learning/vehicle-lifecycle-guide.md)도 in-process/실제 vCAN에서 연결했다.
공통 `power_commands.hpp`의 lifecycle root는 독립 trusted 입력이며 CAN에서 추론하지 않는다.
[Front startup](../learning/vehicle-lifecycle-guide.md)의 pair arm/실제 Leaf 수용도 same-host/vCAN에서 시험했다.
[정상 종료](../learning/vehicle-lifecycle-guide.md)는 별도 trusted stop intent·issuer seed·terminal lease/ACK의 in-process 계약을 사용한다.
원래 source/expiry를 보존한다. DDS의 remote 제어/stop 경로는 미구현이며, Host SOME/IP의 INIT/rejoin·lease·보호 구현과 구분한다.

## Central 내부 의미 계약

| Interface | Producer → Consumer | 의미 / validation |
| --- | --- | --- |
| IF-CENTRAL-VEHICLE-REQUEST | Classical Controller → Central allocation | target speed/acceleration/curvature/braking demand; source/trajectory identity, Epoch/sequence/freshness/mode 검사 |
| IF-CENTRAL-POWER-REQUEST | lifecycle requester → Central vehicle management | enable/shutdown 요청; non-driving handshake, correlation/Epoch/deadline; 요청으로 READY 선언 금지 |

두 interface는 기존 IF-DDS-VEHICLE-CMD/IF-DDS-POWER-REQUEST의 의미를 유지하며 endpoint와
현재 ID를 개정했다. Central 내부 transport는 in-process/IPC/DDS 중 TBD-05다. ADAS/control과
VCU 기능은 같은 Target에서도 별도 validation/fault 책임을 갖는다. Controller의 50 Hz/20 ms는
유지하고 Central coordinator의 task/monitor budget은 TBD-04/05/14다.
Vehicle-level speed/acceleration/curvature/braking demand는 torque/pressure actual이 아니다.
Central allocation이 원천 actual/capability/permission을 검증해 actuator demand를 만들고
각 Zone을 거쳐 Leaf로 전달한다. [공통 의미](README.md)를 적용한다.

## Central–Front/Rear 독립 경로 — ZON-01 v0.5

| Interface | Producer → Consumer | 의미 / validation |
| --- | --- | --- |
| IF-DDS-FRONT-CMD | Central allocation → Front | scoped Steering/Brake demand; 원래 parent/source/expiry, integrity/range/mode 검증 |
| IF-DDS-REAR-CMD | Central allocation/vehicle management → Rear | Drive demand, BMS constraints/permission/power request/speed; parent identity/expiry 보존 |
| IF-DDS-FRONT-STATUS | Front → Central state/VCU/bridge | Steering/Brake actual/health; 각 원천 time/sequence/validity/causal identity |
| IF-DDS-REAR-STATUS | Rear → Central state/VCU/bridge | Drive actual/capability, BMS/power status; 원천/의존 identity/time/clock/validity 보존 |
| IF-DDS-FRONT-SESSION | Central session ↔ Front | trusted INIT/rejoin/Epoch/monitor-enable/correlation |
| IF-DDS-REAR-SESSION | Central session ↔ Rear | 위와 동일; 다른 Zone heartbeat로 session/health 추론 금지 |

IF-DDS-ZONE-STATUS는 Front/Rear status의 공통 family 의미다. Zone publication의 starting point는
100 Hz/10 ms이며 BMS의 critical/observation cadence와 per-source freshness는 독립 보존한다.
각 link의 command/status/session envelope와 실제 Leaf 원천/의존 freshness를 별도로 검사한다.
재발행/새 CAN counter로 parent request의 유효 기간이나 cached actual/BMS age를 연장하지 않는다.
Central vehicle management의 power 요청/permission은 실제 컨택터/HV 상태를 대신하지 않는다.

Critical loss는 각 수신 방향/원천별 <=100 ms 검출과 local protection을 적용한다.
Central requester/VCU 정지, 각 Zone 정지, 한쪽 link partition을 별도 시험하며 다른 link의
heartbeat로 정상화하지 않는다. Leaf 자체 timeout과 Host per-source actual gate를 유지한다.
Recovery는 trusted 새 Epoch/명시적 INIT와 required power/health 재검증을 요구한다.
Schema/IDL/topic, rate/source-age/monitor budget, clock/skew, QoS/queue/overflow, trusted handshake는
TBD-15/05/14다. 이 표는 DDS 의미 계약이다. Host SOME/IP의 두 Zone runtime·지정 기능 시험은 연결됐으며, 전체 TC 판정은 요구사항 추적성을 따른다.

## Host bridge contracts

IF-HOST-SENSOR는 Host→Central sensor timestamp/frame ID/source clock/ego state validity를 전달한다.
IF-HOST-ACTUATOR는 Leaf→담당 Zone→Central feedback bridge→Host Plant Adapter 경로다.
Central bridge는 원천 actual을 집계/전달하며 값/validity/time을 command로 합성하지 않는다.
Host는 actual stream별 loss를 <=100 ms에 검출하고 유효 actual set이 없으면 tick을 gate한다.
IF-HOST-EV-STATUS도 BMS→Rear→Central bridge→Host 경로의 관측 정보이며 wheel actuation이 아니다.
Protocol/serialization/source clock sync/skew/Host acknowledgement는 M5에 설계하고 M6/M7에
검증한다(TBD-02/04/05/07). Battery/power physical sensor coupling과 상위 status 통신은 별개다.

## Middleware decision criteria and timing

M4에서 DDS와 Zenoh 후보를 같은 command/status/session 의미 계약·입력 부하·fault 조건으로
비교하고 **M5 runtime 착수 전** middleware, ROS 2 integration 또는 direct API,
구현체, isolation(Docker network vs netns/veth), Host bridge transport를 결정한다.
판단 기준은 두 Jetson stack 호환성, dependency/학습 비용, discovery 재현성,
QoS와 bounded queue/freshness 제어, tracing/clock 접근성, reconnect 시험 가능성이다.
새 middleware 선택이 Central/Zone/vECU 책임을 바꾸는 이유가 되어서는 안 된다.

비교 항목은 정상 지연/지터·자원 사용, 느린 consumer/queue 포화에서 오래된 command 배제,
각 방향의 단절 검출, trusted 새 Epoch/INIT 재연결과 source/parent expiry 보존이다.
구현체/version/schema/queue 설정, clock 조건, run 길이·반복 수와 판정 기준을 비교 전에 고정한다.
DDS QoS 항목과 Zenoh의 설정이 같은 의미를 갖는다고 가정하지 않고 application 계약으로 검증한다.
Transport가 제공하는 delivery/reconnect 기능도 receiver의 Epoch/freshness/local protection을 대체하지 않는다.

결정할 QoS는 reliability, history/depth/resource limit, deadline/lifespan/liveliness,
durability/ownership이다. Reliable delivery가 오래된 command의 적용을 정당화하지 않는다.
DDS deadline/liveliness는 application freshness/timeout 검사를 대체하지 않는다.
Application integrity 방식을 DDS에도 CRC로 할지 여부는 CAN의 정책을 무조건 복제하지
않고 M5에 정한다. Sequence width/wrap/restart, schema compatibility, multicast/routing,
queue backpressure도 함께 고정한다. Service를 추가하면 request/response correlation,
idempotency/deadline/retry/partial failure 계약을 별도로 정의한다.

관련 요구: SYS-ARCH-001/002/003, SYS-COM-002/003/004, SYS-SAFE-003, SYS-CTRL-001/002.
[Deployment](../architecture/README.md),
[TBD register](../roadmap.md#open-m0-decisions).
