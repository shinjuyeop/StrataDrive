# ADR-0051: 실제 Zone feedback health와 독립 status ingress

Date: 2026-10-19. Status: **Host component 구현·시험 / 분산 runtime·전체 rejoin 후속**.
[ADR-0050](ADR-0050-controlled-stop-and-terminal-handoff.md)의 시동/정상 종료 연결에서
항상 정상으로 채웠던 Zone health fixture를 실제 gateway·독립 CAN receiver 상태로 교체한다.

## 책임과 상태

`interfaces/zone`은 typed status/scope와 공통 Leaf feedback health 정책을 소유한다.
`zone/feedback/ZoneFeedbackMonitor`는 Zone별 단일 owner로 10 ms마다 자기 gateway와 담당 입력만 검사한다.
Front는 Steering/Brake Actual, Rear는 Drive Actual·BMS PowerStatus/PowerLimits다.
입력은 독립 receiver의 `current_sample(now)` 결과이며 원래 source/dependency/quality를 보존한다.
공통 정책을 Central도 사용하므로 INIT/검토한 DEGRADED/BMS quality·age 판정을 복제하지 않는다.

| Phase | 의미 | Normal 준비 | 시동·종료 input health |
| --- | --- | --- | --- |
| Waiting | 첫 필수 입력 대기 | false | false |
| Ready | 정상 입력과 Idle gateway, NonDriving에서 arm 가능성 판단 | true | true |
| Active | arm된 gateway의 정상 입력·감시 | true | true |
| Terminal | 실제 gateway가 normal-stop을 선택, 입력·lease 감시 계속 | false | true |
| FailSafe | 입력·gateway·clock/period 고장 latch | false | false |

Ready/Active는 차량 주행 허가가 아니다. Central은 실제 power READY·lifecycle/ACK·모든 원천을 별도로 확인한다.
Terminal은 정상 종료에 필요한 건강한 상태지만 Enable/AllowNormal/새 normal command의 근거가 될 수 없다.
Rear terminal은 normal gateway와 power gateway가 함께 선택해야 한다. 불일치는 보호한다.
Phase·ready flag·metadata 조합과 scope를 수신·Central 판정에서 대조한다.

## 상실과 복구

- 각 입력의 첫 대기는 최대80 ms다. 하나라도 이미 유효했던 입력이 사라지면 첫 대기를 다시 주지 않는다.
- Actual source30 ms, BMS source50 ms/dependency70 ms, 기존 INIT/제한 DEGRADED 정책을 유지한다.
- Leaf의 명시적 FAIL_SAFE/LocalProtection는 첫 입력 대기 중에도 즉시 보호한다. 유효 물리값과 sender health는 별개다.
- 10 ms runnable의 gap>30 ms·clock 역행·gateway 보호·필수 입력 상실은 latch하고 별도 trusted port로 로컬 보호를 선택한다.
- Gateway callback 중 clock이 진행할 수 있으므로 status source와 입력 age는 실제 gateway 관찰 완료 시각으로 검사한다. Callback 뒤30 ms 초과도 deadline fault다.
- Status source는 관찰 cycle 시각이다. 자식 Actual/BMS 시각을 갱신하거나 status에 의해 오래된 원천을 fresh하게 만들지 않는다.

Central은 `ZoneStatusReceiver`를 Front/Rear에 각각 둔다. Source≤30 ms, 첫 수신 timeout80 ms,
Epoch·세션 경계·strictly increasing source·sequence 첫0…9/후속1…10을 검사한다. 중복·mutation·잘못된
scope/phase/metadata는 수용 시각을 갱신하지 않는다. 이전 source가30 ms를 초과하면 늦은 새 status를
검사하기 전에 continuity를 latch한다. 최초 timeout과 명시적 continuity/clock 고장도 자동 복구하지 않는다.
보고받은 FailSafe와 Terminal도 같은 Epoch에서 정상으로 되돌릴 수 없다.

복구는 trusted **더 큰 application Epoch와 비감소 시간의 INIT**만 가능하다. Monitor INIT 전에 담당 gateway도
같은 새 Epoch로 초기화해야 한다. Receiver와 monitor의 INIT는 Leaf/물리/다른 Zone/Central owner를 reset하지 않는다.
전체 coordinator가 각 참여자의 실제 재초기화·readiness·explicit arm을 완료하기 전에는 재주행을 허가하지 않는다.
자동 discovery/reconnect를 INIT 또는 fault clear로 간주하지 않는다.

## 검증과 남은 범위

[학습·검증 기록](../learning/m4_zone_feedback_health.md)의 component 시험에서 기존 시동과 정상 종료가 실제
Zone status를 사용한다. Front/Rear Actual 전송 누락·독립 status partition·continuity 상실을 주입하고
Central FAIL_SAFE/Inhibit와 양 Zone 보호 선택을 확인한다. 기존 허가/command expiry가 다음 Central 판단보다
먼저 로컬 보호를 선택할 수 있으므로 시험은 만료 경계에서 보호 관찰을 정상 CAN 재전송보다 먼저 수행한다.
이 논리 순서는 별도 thread 실행이나 worst-case 지연 보장이 아니다.

Same-host typed 전달이며 status wire encoding/CRC·DDS QoS/authentication·cross-node clock mapping은 미구현이다.
현재 monitor 자신이 멈춘 경우 Central의 독립 status source 감시가 폐쇄한다. 완전한 Zone 정지/분단에서
Leaf 쪽 보호를 보장할 remote composite lease/독립 watchdog과 전체 coordinator/runtime·재가입 transaction은 후속이다.
BMS limits/safety·pack/load·speed는 기존 fixture이며 차량 운동/정지 거리·Target timing 검증은 아니다.
Requirement32/system TC29와 M3 전체 수용 상태를 변경하지 않는다.
