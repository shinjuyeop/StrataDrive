# ADR-0060: Central–Front SOME/IP Host component pilot

후속 관계(2026-10-22): Pilot의 grant fixture를 정규 세션으로 보지 않는다. 후속 실제 세션/Host adapter 채택은 [ADR-0061](ADR-0061-someip-front-owner-adapter.md), Rear 확장은 [0062](ADR-0062-someip-rear-host-adapter.md)를 따른다.

Date: 2026-10-21. Status: **conditional Host pilot candidate; regular adoption deferred**.

The DDS control gate remains CLOSED. Evaluate SOME/IP using pinned COVESA vSomeIP
3.7.6 in a separate opt-in Linux C++ execution path. Protocol and implementation
are distinct choices; changing protocols does not resolve the historical Cyclone
DDS shutdown or TSan failures. No default production transport/dependency changes.

Reuse owner-wire v1 and actual allocation/Front/Leaf component contracts. Limit
the first binding to TCP methods for readiness, work/result and Actual status;
define the precise [wire table and component fixture boundary](../icd/someip_pilot.md).
Use separate netns/veth and mount namespaces to exclude local IPC-only success.
Keep source/expiry, 20ms envelope, capacity8, Epoch/token/operation, route/clock/CRC,
local protection and new-session recovery rules. Discovery does not authorize arm.

Build normal, ASan/UBSan and TSan separately, including SDK and compiled Boost
dependencies. Preserve initial failures and compare only explained corrections
under [the prospective fixed protocol](../test-plan/evidence/m5_someip_pilot/protocol.md).
Do not substitute short pilot success for M4 closure, regular M5 adapter, real IO,
multi-participant session handling, Jetson suitability or whole-system qualification.
Results and adoption verdict belong to the [evidence](../test-plan/evidence/m5_someip_pilot/README.md).
