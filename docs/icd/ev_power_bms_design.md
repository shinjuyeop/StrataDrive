# EV/BMS 기능 설계 — EV-01

Date: 2026-10-13; wire update: 2026-10-14.
Status: **포함 범위 ACCEPTED / 상세 설계 초안 / EV C++ codec·receiver Host 부분 검사 / model·runtime PLANNED / TC NOT RUN**.
[ADR-0014](../adr/ADR-0014-ev-functional-scope.md)의 후속 설계다.
M0 v0.1과 RG-01 이후의 확장이며 기존 검토/실행 결과에 소급 포함하지 않는다.
후속 [ZON-01](../architecture/zonal_partition.md)의 Front/Rear 두 Zone 배치를 반영한다.

## 목표와 구현 깊이

기존 ODD에서 전기차 준비 → 주행 → 회생/마찰제동 → 정지 → 종료 및 선택한 고장 대응을
재현한다. 기능 책임, 상태 전이, 통신 유효성, 실제 모델 출력과 보호 반응을 검증한다.
물리 모델은 그 시험을 판정할 수 있는 수준으로 단순화하고 근거/제약을 기록한다.

| 영역 | 포함 범위 | 상세 구현에서 제외/추후 확장 |
| --- | --- | --- |
| Central | 기존 vehicle-level 요구와 Safety Supervisor, 상태 소비/전원 lifecycle 요청 | ODD 확대와 운전자 인계 의존 |
| Front/Rear Zone | 각 gateway/local protection; Front 단일 vehicle management/allocation/feedback 집계 | 별도 VCU 계층/보드, coordinator failover |
| Steering/Brake/Drive | 주기 실행, delay/saturation/dynamics, actual 및 로컬 고장 대응 | 정밀 기구/유압, 인버터 스위칭/전류 제어 |
| Battery/BMS | 단순 SOC/pack 전압·전류·온도 + 셀 전압·온도 극값 입력, 충전·방전 한계, 센서 invalid와 주요 보호 상태 | 셀별 상세 화학/열화/밸런싱, 정밀 SOC estimator |
| Power | 프리차지/컨택터의 요청과 실제 모델 상태, HV 준비/종료, LV supply 및 interlock 조건 | DC/DC·충전기 회로, 충전 인프라/protocol |
| Thermal/stability | 온도 조건과 derating, ABS/ESC 미구현 가정/연결 명시 | 정밀 열회로, 바퀴별 ABS/ESC/저마찰 성능 |
| Diagnostics/process | fault→검출→local action→actual→DTC, explicit recovery, 요구/시험/변경 추적 | 전체 UDS/OBD, 양산 인증, body/infotainment |

충전 연결/저전압/절연·interlock 상태는 필요한 모델 입력으로 표현한다. 충전 중 주행
금지 같은 lifecycle 조건은 시험한다. 임의 정상 constant로 두는 입력은 가정/fixture로
표시하며 해당 실차 고장 검증 결과로 쓰지 않는다. Parameter는 아래 gate에서 결정한다.

## 역할과 경계

| Producer / 기능 | 입력 → 출력 / 책임 |
| --- | --- |
| Central | 유효 vehicle state/health → vehicle demand 및 별도 power lifecycle 요청; READY를 직접 선언하지 않음 |
| Front `vehicle_management` | lifecycle 요청 + fresh BMS/power/actuator status → 전원 요청과 로컬 drive permission; VCU 역할 |
| Front `control_allocation` | drive permission + vehicle demand + actual/capability → Steering/Brake/Drive demand |
| Front `gateway` | Steering/Brake CAN과 peer DDS, source metadata 보존, Central/Host status 집계 |
| Rear `gateway` / validation | Drive/BMS CAN, scoped demand/constraint 검증, source status 전달; 전체 차량 배분 재수행 금지 |
| BMS vECU | battery/power model 센서 + power 요청 → charge/discharge power limit, health, 실제 power 상태; 로컬 보호 |
| Drive vECU | 유효 torque demand + Zone이 전달한 원천 BMS 한계/permission + speed → local bounded torque actual/capability |
| Battery/power plant | 실제 motor DC power/손실/부하와 power 요청 → battery 에너지 및 센서/컨택터 실제 상태 |
| Host Plant Adapter | Steering/Brake/Drive actual → vehicle plant; BMS 상태는 관측/제약 정보이고 별도 wheel actuation이 아님 |

상위 피드백은 **Leaf → CAN FD → 담당 Zone → Front 집계 → Central / Host**다.
BMS 원천 상태/한계는 Rear→Front, Front가 배분한 constraint/permission은 Rear→Drive로 전달한다.
Central↔BMS, BMS↔Drive의 application 직접 우회 경로는 만들지 않는다.
모터의 전력과 배터리의 전류 사이 물리 coupling, ECU 로컬 센서 신호는 simulation plant
내부 경계다. ECU의 상위 status 통신과 구분하며 Zone이 물리 센서 제어 loop를 대신하지 않는다.

Battery/power model은 논리 plant, BMS는 controller다. M2 component 시험은 모델 센서와
actual power를 명시적 fixture로 공급한다. M6/M7의 모델 배치/단일 energy owner/clock은
TBD-07에 결정한다. 동일 에너지를 Host/Target에서 이중 적분하거나 actuator dynamics를
중복 적용하지 않는다. 별도 보드 대신 기존 Target의 논리 ECU로 배포한다.

## Front/Rear 두 Zone — ZON-01

최종 두 논리 Zone과 Front의 차량 전체 단일 coordinator를 **채택**했다.
후륜 구동 단일 모터 Reference에서 Front는 Steering/aggregate Brake, Rear는 Drive/BMS를 연결한다.
Battery pack은 차체 하부 등가 모델이며 BMS controller의 접속 위치를 Rear로 가정한다.
Front Brake controller는 전륜만 제동한다는 뜻이 아니다. Physical calibration은 TBD-02/07이다.

[분할 설계](../architecture/zonal_partition.md)는 peer command/status/session, 원천 freshness,
독립 loss/local protection과 trusted INIT/rejoin을 정의한다. Rear가 전체 요구를 다시 배분하거나
cached BMS/actual을 fresh한 값으로 만드는 것을 금지한다. Drive/BMS 로컬 보호는
Front 왕복 경로나 Central 승인을 기다리지 않는다.

단일 Zone에서 component/통신을 확인한 뒤 M4/M5에 Front/Rear를 분리한다.
Peer schema/QoS/queue/clock/skew/monitor margin/rejoin은 TBD-15이며 runtime은 PLANNED다.
TC-ZON-001–003은 NOT RUN이다. 기존 M0/M1 또는 TC-EV 부분 증거로 대체하지 않는다.
별도 하드웨어를 요구하지 않으며 같은 Target의 물리 고장 독립성을 주장하지 않는다.

## 전원 lifecycle과 driving gate

전원 상태 초안은 **OFF → CHECKS → PRECHARGE → HV_READY → SHUTDOWN → OFF**다.
차량 driving 여부와 system severity는 별도 정보다. INIT/NORMAL/DEGRADED/FAIL_SAFE를
이 전원 enum으로 대체하거나 READY와 NORMAL을 같은 의미로 쓰지 않는다.

| 상태 | 의미 / 다음 정상 전이의 조건 |
| --- | --- |
| OFF | HV 연결 안 됨; BMS/로컬 monitor를 위한 LV 가정은 명시; normal torque 금지 |
| CHECKS | 요청/epoch, 센서·통신·LV/interlock/충전 연결 확인; 초기 actual 발행은 NORMAL을 기다리지 않음 |
| PRECHARGE | 접속 준비 요청 후 bus/pack 상태와 실제 응답을 확인; 요청 자체로 완료 선언 금지 |
| HV_READY | 실제 HV 준비와 필요한 fresh status 확인; normal driving은 별도 INIT/permission gate까지 통과해야 허용 |
| SHUTDOWN | 주행 종료/토크 해소와 실제 power 응답을 확인한 후 OFF; 시간/응답/정지 조건은 TBD-12 |

정상 주행 허가는 fresh critical input, 실제 HV readiness, actuator availability, 유효
system state, 충전 연결 해제 등의 조건을 로컬에서 확인한다. Drive도 수신 permission과
자신의 필요한 입력을 검증한다. HV_READY 상태만으로 torque를 허용하지 않는다.
초기 non-driving actual/센서와 power 상태는 주행 허가 전에 발행하여 startup 순환 의존을 피한다.

고장 시 선택할 제한/zero-target/전원 차단/controlled shutdown은 고장별 matrix로
TBD-12에 결정한다. 모든 fault에서 즉시 컨택터를 여는 정책을 가정하지 않는다.
Fault clear/new frame/전원 정상화만으로 latched FAIL_SAFE를 해제하지 않고 explicit INIT
재검증과 필요한 power 검사를 거친다. 기존 actual-loss Host tick gate는 simulation containment다.
물리 출력 반응은 유효 actual을 관측할 수 있는 component/plant 시험에서 별도로 판정한다.

## Semantic interface 초안

아래 이름은 의미 계약이다. 후속 [BMS wire 초안](bms_frame_draft.md)에서 6개 EV frame의
ID/DLC/P05/단위와 timing 시작값을 제안했다. [C++ EV codec/항목별 receiver](../learning/m1_bms_codec.md)와
DBC 교차 검증·SocketCAN unit과 EV 독립 process/vCAN 36개 case를 수행했다.
Actual coordinator/DDS/component runtime은 미구현이다.
기존 actuator six-frame에는 BMS/power 정보를 추가하지 않았다.

| Interface / 방향 | 필요한 의미 |
| --- | --- |
| IF-DDS-POWER-REQUEST / Central → Front | power enable/shutdown 요청, request identity/epoch/deadline; 운행 torque command와 별도 |
| IF-CAN-BMS / Rear → BMS | power 요청; integrity/sequence/epoch/freshness, correlation |
| IF-CAN-BMS / BMS → Rear | battery state, charge/discharge limits, power actual state/health와 원천 metadata |
| IF-CAN-DRIVE-CONSTRAINT / Rear → Drive | 원천 BMS charge/discharge limit + permission; 생성/의존 input time 보존, local 검증 |
| IF-DDS-ZONE-STATUS / Front → Central | BMS/power 상태와 drive permission, actuator actual/capability; source별 validity/age |
| IF-HOST-EV-STATUS / Front → Host | 관측용 BMS/power 상태/한계/energy lineage; actuation stream과 구분 |
| IF-MODEL-BMS / plant → BMS | modeled pack voltage/current/temperature, 셀 전압·온도 극값과 power feedback; 로컬 센서 의미, application CAN 피드백 아님 |
| IF-MODEL-DRIVE-POWER / power plant → Drive | Drive 자체 HV bus 실제 sensor와 source/validity/identity; permission만으로 물리 준비 완료 선언 금지, 상세 threshold 후속 |

| BMS 의미 필드 | 단위 / 표현 원칙 |
| --- | --- |
| SOC | [0,1] fraction; 표시용 % 변환은 별도, 초기/용량/추정 방식 TBD-13 |
| Voltage / Current / Temperature | V / A / °C; 프로젝트 current 부호는 방전 양수·충전 음수, OEM 공통 부호를 주장하지 않음 |
| ChargePowerLimit / DischargePowerLimit | W, 각각 nonnegative; 유효 0은 허용 없음, invalid/unknown과 구분 |
| PowerState / Contactor feedback / Health | 요청과 실제 모델 상태를 분리; commanded closed를 actual closed로 간주하지 않음 |
| Metadata | schema/producer/epoch/sequence, source clock/time, validity, causal request 또는 model input identity |

단순 pack model의 한계를 명시하고 셀별 측정/보호는 등가 sensor/fault input으로 표현한다.
전체 status 한 개의 validity만으로 모든 한계/센서를 유효하게 만들지 않는다.
용량, voltage/thermal 모델, SOC/온도 한계 곡선, fault threshold/dwell은 parameter 근거와
fixture/OEM 근사 여부를 기록한다. 숫자는 이번 범위 결정에서 만들지 않는다.

## 로컬 셀 극값 입력

Pack 평균만으로 셀 과전압/저전압·국부 고온 조건을 가리지 않도록 **최소·최대 셀 전압과
최소·최대 셀 온도**를 IF-MODEL-BMS에 포함한다. 이는 M2 구현 범위이며 아직 모델 코드는 없다.

| 로컬 입력 | 단위 / 계약 |
| --- | --- |
| MinCellVoltage / MaxCellVoltage | V; finite, `0 <= min <= max`, 허용 범위·저/과전압 threshold와 dwell은 TBD-13 |
| MinCellTemperature / MaxCellTemperature | °C; finite, `min <= max`, 허용 범위·저/고온 derating과 dwell은 TBD-13 |
| 각 극값 pair의 validity/source time | 전압 pair와 온도 pair는 독립; unknown을 평균/정상 constant로 대체하지 않음 |
| Model input identity | trusted Epoch + model batch sequence/acquisition; cached 재발행에서 보존하고 가장 오래된 dependency 시각에 포함 |

첫 모델은 등가 극값과 fault injection으로 셀 불균형/센서 상실/온도 경계를 표현한다.
Threshold를 사용하는 한계 계산·보호 판단은 필요한 극값의 validity/age까지 확인한다.
셀별 화학·회로·열전달과 balancing을 구현하지 않으며 그 동작을 검증했다고 주장하지 않는다.
원천 값과 limit reason/protection 결과는 model trace에 남겨 시험에서 대조한다.
현재 6개 CAN frame의 pack 관측/limit/status layout은 유지한다. Raw 셀 극값을 상위에
전부 발행하는 추가 진단 메시지는 별도의 소비·시험 필요가 생길 때 검토한다.

## 한계, freshness와 보호

Drive는 battery power 한계와 motor/speed envelope를 함께 적용한다. Power(W)를 곧바로
torque(N·m)와 비교하지 않고 효율/속도/reference를 정의한다. 0/저속에서 나눗셈으로
무한 torque를 만들지 않으며, 실제 torque 응답의 제한/전환 budget은 TBD-03/13이다.
Zone 배분과 Drive local cap을 모두 검증하고 BMS의 report는 actuator actual을 대체하지 않는다.

Status 생성 시각과 가장 오래된 dependency source 시각을 구분한다. Zone의 새 sequence/
TX timestamp나 Drive의 새 계산 시각으로 cached BMS sensor/limit/permission을 fresh하게
만들지 않는다. Clock domain, 개별 source validity/age 및 bridge progress를 보존한다.
Invalid/stale critical constraint에서는 새 normal motor demand를 허용하지 않고 local
보호를 선택한다. Torque 해소/마찰 배분/전원 반응은 고장별 검증된 matrix를 적용한다.

Critical BMS/power stream loss는 SYS-COM-003 v0.3의 <=100 ms 검출 상한을 적용한다.
[BMS wire timing 초안](bms_frame_draft.md#first-sil-timing--수신-정책-초안)은 critical source
50 ms/dependency 70 ms, RX 80 ms+monitor/margin 20 ms와 비critical 관측 경로를 구분한다.
BMS control/model sampling 50 Hz와 관측 publication 10 Hz도 별개다. 실제 더 느린 sensor와
cross-zone budget의 수용은 TBD-14/04/15이며 측정 전이다.
**Drive 보조 source age는 <=30 ms를 유지하며 capability dependency age는 별도 설정으로 분리·시험했다.**
기본 dependency age도 30 ms다. EV input 70 ms는 명시적 opt-in이며 full Drive/BMS gate 연결은 남는다.
선택한 rate가 그 정책과 맞지 않으면 근거를 남겨 wire/receiver/profile/test revision을
함께 검토한다. Startup grace와 물리 응답/전원 차단 deadline도 loss 검출 상한과 별개다.

## 에너지와 물리 모델

Battery model의 상태 변화는 실제 model power에 따른다. Command나 허용 limit를
사용한 에너지 적분은 금지한다. Drive mechanical actual power, motor/inverter 변환 손실,
battery charge/discharge power와 부하의 reference/sign을 명시한다.
Battery 에너지 초기값/용량과 누적 구동 소비·회수·손실/보조 부하를 동일 simulation clock의
단일 owner가 적분한다. 충전·방전 cap과 motor actual이 충돌하면 deficit/model violation을
기록하며 battery power만 clip해서 불일치를 숨기지 않는다.

RG-01 회수 에너지(J)와 SOC는 서로 다른 값이다. SOC 계산 방식/usable capacity, 효율,
전압/온도 응답과 적분 오차는 TBD-13이다. Full/empty 경계에서 에너지를 생성하지 않고
허용 power와 actual response를 제한해야 한다. Missing/invalid 입력은 측정 불가로 기록한다.
마찰제동을 충전으로 집계하지 않는다. 온도는 첫 fixture 입력에서 시작할 수 있지만 실제
thermal response 시험은 thermal model을 정의·실행한 이후에만 PASS로 표시한다.

## 요구·시험과 실행 순서

SYS-EV-001–005 및 SYS-COM-003/004, SYS-PERF-002 v0.3을 적용한다.
EV-S01/02, EV-F01/02와 TC-EV-001–005는 [scenario](../test-plan/scenario_baseline.md),
[verification](../test-plan/verification_strategy.md), [traceability](../test-plan/traceability.md)에
연결하며 Result는 모두 NOT RUN이다.

1. M1: 의미/critical stream 목록, BMS/power/constraint wire, source-age/rate/INIT handshake를 결정한다.
   기존 six-frame 수용 항목과 EV 추가 vector/receiver/vCAN case를 구분한다.
2. M2: actuator 실제 응답과 Battery/BMS/power model, local limit/protection을 component별 구현한다.
3. M3: 새 task/stream의 clock/rate/timeout/jitter 측정; M4: Front 단일 coordinator 확인 후 Front/Rear 분할.
4. M5: Central/peer DDS request/status와 Host bridge; M6: Simple Plant lifecycle/energy/response 검증.
5. M7: CARLA mapping; M9: fault→DTC integration; M12/M13: 동일 EV feature/config와 최종 regression.

TBD-12(power sequence/고장 반응), TBD-13(battery/limit/energy 모델), TBD-14(새 interface와
timing)는 [roadmap register](../roadmap.md#open-m0-decisions)에 owner/gate를 둔다.
TBD-14의 frame inventory/range/P05/논리 rate·age는 ADR-0016 초안으로 구체화했으며
Host C++ 교차 검증/항목별 receiver와 EV local vCAN을 구현·시험했다. Wire 최종 수용,
실제 trusted coordinator와 clock/runtime budget은 남는다.
TBD-15의 두 Zone 채택/mapping/단일 owner는 결정했고 peer protocol/timing/rejoin은 남아 있다.
실행 전에 해당 test의 값/판정식을 고정하며 미해결 값이 있는 시험을 PASS로 표시하지 않는다.

## 설계 참고

[NXP](https://community.nxp.com/t5/NXP-Tech-Blog/How-electrification-is-changing-vehicle-architectures/ba-p/1491151)는
Zone/domain 기능 분할과 power distribution을 설명한다.
[Bosch BMS](https://www.bosch-mobility.com/en/solutions/powertrain/fuel-cell-electric/battery-management-system/)는
셀/전류 감시와 컨택터 제어를,
[Orion BMS](https://www.orionbms.com/manuals/utility_o2/profile_limits_basic_settings.html)는
충전/방전 current limit와 회생 충전 조건을 설명한다. 본 문서의 power 인터페이스,
상태 이름과 ECU 배치는 프로젝트의 설계 선택이다.
