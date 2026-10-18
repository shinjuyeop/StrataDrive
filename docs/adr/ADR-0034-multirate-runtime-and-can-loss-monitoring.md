# ADR-0034: 여러 Leaf 작업의 주기 실행과 CAN 수신 상실 감시

Date: 2026-10-16. Status: **M3 Host component 구현 / 검사 결과는 품질 기록에 연결**.
2026-10-18 follow-up: 비동기 torque/Actual CAN·6개 stream·RX drain tail은 [ADR-0036](ADR-0036-asynchronous-drive-actual-feedback.md)으로 확장했다.
아래는 다섯 입력 stream을 사용한 첫 결정 기록이다.
[ADR-0033](ADR-0033-first-wall-time-execution-and-monitor.md)의 Steering 실행을 유지하고
Brake·Drive gate·BMS·Power와 실제 SocketCAN RX를 한 finite Host 실험에 연결한다.
기존 Central/Front/Rear 배치와 AUTOSAR stack의 채택 상태를 변경하지 않는다.

## 실행과 시계

- Brake/Drive/Power는 10 ms, BMS는 20 ms, RX는 2 ms absolute release를 사용한다.
  Relative deadline은 각각 5/5/5/8/3 ms로 별도 선택한다. 모두 local 실험 값이다.
  각 runnable에 별도 thread·completion ledger를 두며 monitor와 plant는 각각 별도 owner다.
  Core의 최소 호출 guard는 1 ms이며 실제 runnable period와 구분한다.
- 2.4 s workload와 감시 종료 여유 40 ms를 명시한다. BMS/Power의 초기 release offset은 5/8 ms다.
  BMS의 fresh-input release dwell, 실제 precharge/READY와 Drive gate를 기존 controller가 판단한다.
  외부 speed 20 rad/s, Central request/grant와 limits relay는 명시적인 fixture다.
- 하나의 physical owner가 BrakePressureResponse·Drive torque와 EvPowerModel을 진행한다.
  실제 torque/DC·접점·RC bus·Battery SOC와 센서를 연결하며 초기화 이후 energy owner는 하나다.
  출력·보호 flag는 **적용 기준 시각을 읽기 전에** snapshot으로 취득한다.
  계산 도중 도착한 새 결정은 다음 interval에 적용해 검출 전으로 보호를 소급하지 않는다.
- 모든 clock은 같은 process의 CLOCK_MONOTONIC이다. Source/dependency를 재발행 시각으로 바꾸지 않는다.
  ECU phase, job 전체, 외부 physics를 분리해 기록하며 기록 공간은 실행 전에 확보한다.

## CAN과 trusted context

격리된 vCAN에서 Brake/Drive Command, routed BMS limits, Drive permission, Power request를
실제 socket으로 보낸다. RX owner는 poll당 최대 8개를 round-robin으로 읽고 SO_RXQ_OVFL을 보존한다.
각 ECU는 자기 receiver로 CRC/P05·Epoch·source/sequence·parent를 검증한다.
단일 생산자·단일 소비자의 latest snapshot은 소비자별 별도 인스턴스다.
중간 snapshot 대체와 kernel/trace 유실은 같은 지표가 아니다.

Trusted issuer는 원래 발급한 frame과 parent context의 최근 4개 이력을 CAN 밖의 별도 port로 전달한다.
수신한 frame의 exact envelope/payload에 맞는 context만 사용한다.
CAN을 읽어 parent를 자동 생성하지 않으며, 이력이 없거나 만료된 frame은 기존 receiver 검증에서 거부한다.
Application Epoch 1/model Epoch 7은 격리된 fixture 설정이며 실제 영속 session protocol은 후속이다.

## 독립 감시와 보호

Job completion과 유효 application RX age를 별도 감시한다. CRC 실패·duplicate·stale 수신은
last-valid 시각을 갱신하지 않는다. Accepted timestamp를 먼저 capture한 뒤 monitor now를 읽어
동시 publication을 미래 시각으로 오인하지 않는다.
ReceiveWatch의 80 ms threshold와 실제 검출까지의 <=100 ms budget을 따로 검사한다.
Startup acquisition, timeout/clock latch와 late input의 자동 복구 금지를 유지한다.

| 원인 | 첫 fixture의 독립 action |
| --- | --- |
| Brake job/RX job 상실 또는 Brake stream timeout | increase-only/floor 1 MPa 요청 |
| Drive/BMS/Power/RX job 상실 또는 Drive/Power critical stream timeout | 유한 rate의 Drive zero-target 요청 |
| BMS job 상실 | Power runnable의 BMS gate를 unknown/inhibit로 전달 |
| Power job 정지 | Drive zero를 요청하고 마지막 coil 출력을 유지; 맹목적인 contactor open을 하지 않음 |

Power가 실행 가능한 경우 실제 current dwell→open→방전 종료를 기존 controller가 처리한다.
120 ms bounded stall 후 복귀와 통신 상실을 검사한다. 영구 Power 고장, 독립 전기 차단 장치나
차량 전체 제동/정지 성공을 검증한 정책은 아니다. 새 trusted INIT 없이 보호 latch를 풀지 않는다.

## Drive torque 보고의 경계

현재 wire는 torque 자체의 acquisition timestamp를 별도로 갖지 않으며,
speed/capability timestamp는 전체 report source보다 나중일 수 없다.
ADR-0032의 같은 job end 취득 규칙을 유지하므로 **비동기 torque scalar는 CAN에서 unavailable**이다.
측정 값을 job 시각으로 retimestamp하지 않는다. 실제 torque는 독립 physical trace에 보존하고
Drive의 입력 gate·target·보호 응답을 측정한다. Actual CAN 송신/독립 feedback RX의 검증 완료를 주장하지 않는다.
Sampling 동기화 또는 timestamp 계약 개정은 별도 결정과 receiver/ICD/DBC 회귀가 필요하다.

## 검증 범위

정상/최소 계측, Brake·Drive·BMS·Power·RX 각각의 120 ms 정지, 지속 CRC 손상을 구분한다.
모든 예정 job을 분모에 포함하고 독립 검출→보호 적용의 순서를 확인한다.
CRC가 틀린 raw traffic이 계속되어도 5개 critical stream은 유효 RX 상실을 검출해야 한다.
기존 Steering 실행, 전체 unit/ASan·UBSan, production build와 정적 분석을 회귀한다.
결과와 실행 방법은 [M3 학습 안내](../learning/m3_multirate_runtime.md)와 [품질 기록](../quality_policy.md)에 둔다.
고정 부하·CPU 배치/우선순위·Target·전체 E2E는 후속이며 system TC의 NOT RUN은 유지한다.
