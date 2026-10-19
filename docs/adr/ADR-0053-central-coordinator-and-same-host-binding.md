# ADR-0053: Central coordinator의 단일 실행 순서와 same-host binding

Date: 2026-10-19. Status: **Host component 구현·시험 / 독립 runtime·전체 INIT/rejoin 후속**.
[ADR-0051](ADR-0051-zone-feedback-health-and-status-ingress.md)의 실제 Zone 상태 감시 뒤,
시험 코드가 직접 호출하던 전원·배분·정상 종료 owner를 하나의 Central API로 연결한다.
[MBD 계획](ADR-0052-model-based-design-development-path.md)은 M6–M8에 유지한다.

## 책임과 입력

`central::VehicleCoordinator`는 VehicleManagement·ControlAllocation·NormalStop을 private member로 소유한다.
각 owner의 상태/검증 정책은 유지하고 coordinator가 호출 순서·부분 실패 보호를 관리한다.
Application Epoch 발급·물리 진행·remote reset·packet authentication은 소유하지 않는다.
기존 출력이나 측정을 재발행하며 source만 갱신하지 않는다.

| API | 입력 / 동작 |
| --- | --- |
| start_session | trusted Epoch/enable, 더 큰 Epoch·비감소 clock, adapter 참여자 preflight 뒤 Central owner 초기화 |
| receive_lifecycle | 별도 trusted lifecycle root를 VM에서 검사하고 Rear에 원래 identity/action 전달 |
| receive_vehicle | Normal/explicit arm 뒤 trusted vehicle root를 allocator에서 검사하고 Front/Rear에 같은 원래 root 전달 |
| receive_stop | 실제 Normal에서 stop intent를 검사하고 issuer의 다음 sequence를 내부에서 인계, 이후 정상 ingress 차단 |
| tick | 같은 cycle의 independent receiver current sample snapshot, 외부 monotonic 시각 |
| request_protection | 별도 trusted 보호 요청, 정상 CAN payload와 분리 |

미초기화·not-ready·잘못된 root·중복·mutation을 구분한다. 중복은 하위 authorize를 반복하거나 수용 시각을 갱신하지 않는다.
Root 수용 과정에서 기존 owner의 권한/지원 만료가 드러나면 coordinator 보호도 즉시 latch한다.
Active 상태에서 직접 Shutdown/KeepOff로 정상 종료를 우회할 수 없다. Stop intent 또는 독립 protection을 사용한다.

## 단일 cycle의 순서

10 ms 외부 runnable, allocation20 ms를 유지한다. 첫 body 대기/실행 gap·callback 관찰 gap의 상한은30 ms다.
이는 기존 functional component의 gap 계약이며 M3의4 ms guard나 실제 OS 배치/전체 workload timing 검증을 대체하지 않는다.

1. Clock/session·adapter의 실제 gateway/Leaf 상태를 확인한다. 입력은 원천 시각/quality를 보존한다.
2. Stop 진행 중이면 NormalStop plan과 원래 stop authority 안의 lifecycle child를 수용·전달한다.
3. VehicleManagement가 actual OFF/READY·원래 ACK/요청·input health를 판정한다.
4. 최초 Normal 전환에서 Front pair와 Rear를 trusted arm한다. 부분 arm 실패는 모두 보호한다.
5. Rear gateway로 power request/DrivePermission을 전달한다. 실제 CAN·독립 Leaf 수신 경로를 유지한다.
6. Allocation 주기에 실제 permission receiver 결과와 별도 parent context를 조회하고 배분·Front pair/Rear 전송을 수행한다.
7. 정지 actual dwell 완료 후 allocator를 Quiesced로 선택하고 Leaf/Zone terminal handoff를 수행한다. 정확한 ACK 후에만 PowerDown이다.
8. 이후 tick의 Shutdown→actual OFF/접점 open/bus discharge·ACK 확인은 기존 owner가 계속 수행한다.

각 callback 후 monotonic 시각/실행 gap을 다시 확인하고, 각 gateway의 원래 source/expiry guard를 유지한다.
늦은 callback 뒤 다른 정상 단계로 진행하지 않는다. Owner가 early tick으로 출력하지 않으면 예전 출력을 재발행하지 않는다.
이때도 독립 allocation runnable을 감시하며, 마지막에 발급한 power output의 **변경 없는 parent context**만 보관한다.
배분 입력은 매번 실제 permission receiver에서 조회하므로 새 발급 grant로 수신 상실을 덮을 수 없다.

Stop intent 뒤 외부 lifecycle/vehicle root는 차단한다. NormalStop issuer seed는 마지막 수용한 root의 다음 sequence다.
같은 source instant에 새 정상 root와 stop이 들어오면 strictly-new source가 될 때까지 child 발급을 기다리고
새 propulsive normal output을 내지 않는다. 남은 기존 지원/권한이 그 대기를 견디지 못하면 보호하며 만료를 연장하지 않는다.

## Same-host adapter와 실패

`simulation::VehicleCoordinatorPort`는 실제 Front/Rear normal gateway·Rear power gateway,
Steering/Brake/Drive/Power controller·Central permission receiver와 clock을 연결한다. Plant를 소유하지 않는다.
Preflight는 scope/Epoch와 Idle/non-terminal gateway·비고장 Leaf·초기화된 permission ingress를 확인한다.
FrontStartupControl/Rear power arm과 NormalStopControl의 기존 trusted Leaf 선택을 재사용한다.
NormalStopControl은 coordinator가 allocator를 이미 quiesce한 경계와 기존 직접 allocator binding을 모두 지원한다.

Front 두 CAN write와 Rear write는 atomic transaction이 아니다. Partial Front면 그 cycle의 Rear batch를 보내지 않는다.
Root/arm/power/command/handoff callback 실패, owner protection, session/clock/gap 오류는 정상 흐름을 폐쇄하고
양 Zone Hold/Protect/Zero와 Power local shutdown 선택으로 연결한다. 정상 frame을 재시도하지 않는다.
보호 선택 ACK가 없으면 runnable당 최대1회 재시도한다. Invalid ingress flood는 이 retry 주기를 늘리지 않는다.
ACK는 출력 선택이며 물리 정지·압력 유지·접점 open 성공을 뜻하지 않는다.

동일 Epoch 재접속/INIT는 latch를 지우지 않는다. 더 큰 trusted INIT도 adapter 참여자 preflight 실패 시
Central의 기존 fault를 보존한다. 새 Epoch로 한 gateway만 바꾸는 것으로 Central을 재초기화할 수 없다.
다만 전체 독립 receiver/Zone/Leaf의 remote INIT transaction과 acknowledgement/timeout을 구현한 것은 아니다.
Caller가 각 receiver/monitor와 참여자를 준비하고 매 cycle 검증된 원천 snapshot을 전달해야 한다.

## 검증과 한계

[학습 기록](../learning/m4_vehicle_coordinator.md)의 단위20개와 실제 연결 추가5개를 포함해
normal·ASan/UBSan 각각 C++820개를 통과했다. 기존 양 Zone 시동/정상 종료·실제 health/Actual 상실 시험을
수동 Central 호출에서 coordinator로 전환했다. Partial arm·power/Front write·permission ingress 상실과
한 gateway만의 새 Epoch도 주입했다. NormalStop의 실제 Hold/Zero→HV OFF/ACK 완료·lease/센서 상실은 유지했다.

BMS limits/safety gate·pack/load·speed script는 fixture다. Current sample의 집계/Zone status 전달은 same-host이며
독립 Central/Zone thread/process·network partition·persistent session handshake·DDS/Host feedback bridge는 후속이다.
Remote32-byte composite lease/stop/protection, 전체 workload timing·Target/차량 운동 검증도 남아 있다.
M4 전체 완료나 M3 예외 해소·requirement32/system TC29 PASS로 확대하지 않는다.
