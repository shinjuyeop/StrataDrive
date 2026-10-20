# ADR-0056: M4 공통 고장 주입과 독립 실행 감시

Date: 2026-10-20. Status: **Host component 구현·검증 / 전체 M4·M3 수용 후속**.
[ADR-0054](ADR-0054-trusted-session-owner-loops.md)와 [ADR-0055](ADR-0055-asynchronous-normal-owner-integration.md)의 소유권·세션 계약을 유지한다.
현재 상태는 [project_status](../project_status.md), 실행 근거는 [M4 fault evidence](../test-plan/evidence/m4_faults/README.md)가 기준이다.

## 공통 주입 경계

`M4Fault`는 대상·path·kind·시작·지속·delay·선택 phase를 가진 값이다.
CLI는 `path:kind:target:start_ms:duration_ms:delay_ms[:phase]`를 엄격히 검사하고 thread 시작 전에 고정한다.
같은 정의를 논리 clock/native owner wrapper와 typed mailbox delivery adapter에서 사용한다. M5에서도 시나리오/criterion을 재사용하고 transport adapter는 교체한다.

| 주입 | 실제 중단하는 것 | 계속 실행하는 것 |
| --- | --- | --- |
| owner pause | 해당 owner의 세션 처리·RX·제어·자체 감시·출력·ACK 전체 | 재개 시각을 확인하는 harness; 다른 owner |
| owner overrun | 지정한 전체 owner body를 실제 sleep으로 지연 | 독립 monitor/peer; 논리 시험은 같은 구간 실행 기회 생략 |
| directional drop/delay | 지정한 정상/세션 typed link의 전달 | sender/receiver owner와 그 자체 감시 |
| overflow | 실제 FIFO consumer pop | 실제 producer; bounded FIFO가 가득 차면 기존 permanent failed latch |

Delay는 envelope/payload의 원래 source·epoch·parent·exclusive deadline을 바꾸지 않는다. ACK도 원래 plan을 유지한다.
주입 시작 설정값과 첫 실제 stop/drop/delay/blocked pop·overflow 시각은 다를 수 있어 별도 event로 기록한다.
Owner별 event 저장소와 link의 TX/RX 저장소는 각각 단일 writer이며 join 후에만 합친다. Bounded 기록 누락도 FAIL이다.

## 보호와 관측의 소유자

살아 있는 controller는 기존 receiver/health·authority 만료를 검사하고 atomic global gate를 닫는다.
이미 수용한 command도 원래 context expiry에서 보호한다. ingress에서만 유효기간을 검사하지 않는다.
Local BMS inhibit는 Power의 별도 최신 snapshot에도 바로 게시한다.

멈춘 Leaf는 보호 선택 ACK를 낼 수 없다. Physical의 독립 output-application watchdog은 마지막 출력 source+30 ms 뒤
angle hold·pressure floor·torque zero를 적용한다. Power driver는 실제 torque/current와 기존20 ms dwell을 확인한 뒤 코일 해제/방전을 선택한다.
물리 owner/driver가 수행한 동작은 ECU ACK로 집계하지 않는다. 센서 trace의 압력·토크·접점·bus 응답도 선택 ACK와 다르다.

공유 memory의 global gate와 atomic priority protection은 막힌 정상 FIFO를 우회한다.
이 시험의 방향별 partition은 실제 원격 process/네트워크 partition의 격리·전달 보장이 아니다.
Physical 자체가 멈추면 모델 적용도 재개까지 지연된다. OS 전체 정지/Physical와 monitor 동시 정지를 견디는 하드웨어 watchdog은 구현하지 않았다.

## 복구

고장 해제/owner resume만으로 같은 Epoch의 latch/gate를 열지 않는다.
CLI가 thread 시작 전 발급한 더 큰 durable grant로 전체 Prepare/INIT/Release·BMS release dwell/HV readiness·arm을 반복한다.
Prepare Ready ACK 뒤 old actor는 common INIT enable을 넘겨 실행하지 않는다. 물리 reset evidence는 INIT에서도 새로 검사한다.

Failed mailbox 교체는 모든 owner 종료·join 뒤 수행한다. 동일 타입 link storage를 재구성하고 session loop를 다시 연결한다.
Actor와 Physical/EvPowerModel은 재생성하지 않는다. SOC/energy·pressure·torque·angle·회로/전원·model Epoch/sequence를 보존한다.
이전 Epoch/늦은 ACK는 새 session plan을 바꾸지 못한다. 물리 trace에 이전 Central snapshot을 새 gate Epoch 상태로 합치지 않는다.

## 기존 M3 감시 연결

Opt-in `guards`는 기존 `TaskSchedule`/`DeadlineMonitor`를 재사용한다.
9개 service owner의 대표2 ms 기회에 release→completion4 ms guard를 두고 열 번째 Monitor owner가 독립 poll한다.
Physical은 Monitor의 guard를 poll한다. 각 guard에는 executor와 별도 단일 observer가 있다.
누락 slot은 다음 heartbeat/완료로 채우지 않는다. Monitor가 controller를 직접 수정하지 않고 gate/priority override를 요청한다.
Physical의 실제 override 적용 시각은 별도로 기록한다.

Leaf의 nominal10/20 ms runnable은 원래5/8 ms admission/완료 budget도 검사하며 늦은 normal actuation을 게시하지 않는다.
이 검사는 독립2/4 ms whole-service guard와 구분한다. IO200 μs body 통계·2 ms guard·실제10/20 ms control 주기를 섞지 않는다.

CPU A/B와 FIFO 요청은 start gate 전에 실제 policy/priority/affinity를 대조한다. 적용 실패 시 workload를 시작하지 않고 fallback하지 않는다.
시작 장벽은 release/acquire atomic이며 setup 완료와 abort를 명확히 게시한다.
GCC11 TSan의 timed-CV 경고가 올바른 잠금 최소 예제에서도 재현돼 해당 경로를 제거했다. 기본 ASLR 매핑 오류와 process-local `setarch -R` 실행을 구분해 보존한다.

[사전 프로토콜](../test-plan/m4_fault_timing_protocol.md)의48회 조건·분모·deadline을 결과 전에 고정한다.
Native monotonic 통계와 logical 경계, normal과 sanitizer, 기능 보호 PASS와 정상 timing FAIL을 별도 보고한다.
기존 OPEN-M3-01/02·Target/RTOS·학습자 수용과32요구/29 system TC NOT RUN은 바꾸지 않는다.

## 다음 경계

Remote Leaf의 composite authority/INIT/arm/stop/protection wire 계약(TBD-15), clock/freshness와 DDS/QoS/격리(TBD-05)를 정한 뒤
M5 독립 process/네트워크로 옮긴다. Native fault recipe와 관측점/기준을 같은 시나리오로 재사용하되 atomic bypass를 원격 보장으로 간주하지 않는다.
MBD는 M6 MIL→M8 동등성/제어, AUTOSAR RTE/BSW·Target pilot은 기존 순서를 유지한다.
