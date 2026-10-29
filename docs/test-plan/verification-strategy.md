# 검증 전략

현재 구현·수용은 [프로젝트 상태](../project-status.md), 대표 실행은 [검증 안내](README.md)를 따른다.
아래29개 system TC는 정의된 계약이며 전체 runtime Result는 **NOT RUN**이다.
Component/Host 부분 통과와 전체 system·Target 판정을 구분한다. 과거 실행 집계를 이 문서에 누적하지 않는다.

## 검증 계층

| 계층 | 확인 대상 | 한계 |
| --- | --- | --- |
| Document review | 요구·구조·interface·TBD·추적성 | Runtime 결과가 아님 |
| Unit | codec/golden·수신 상태·경계·모델 불변 조건 | Linux component logic |
| Integration | vCAN·세션·SOME/IP·process/link·queue·재가입 | 실제 CAN 전기/Target 실행을 대체하지 않음 |
| SIL / MIL | 독립 모델·실제 Actual 기반 차량/EV·CARLA mapping | 해당 fixture/ODD·clock 범위 |
| Fault | loss/corruption/delay/jam/overrun·복구 | 검출·보호 선택·실제 출력·차체 응답을 별도 관측 |
| Performance | 부하·배치·timing tail·miss·resource | 환경별 관측 통계, WCET 보장 아님 |

Logical clock의 상태/expiry와 monotonic wall 실행을 따로 판정한다.
송신 enqueue·RX·dispatch·처리/선택 ACK·결과 수신·실제 actuator 적용은 서로 다른 관측점이다.
Miss/skip·timeout·설정 실패와 원래 분모를 보존한다. Sanitizer 경고0은 기능/timing 통과가 아니다.

Scenario/config/seed·source/dirty/binary/tool version과 환경을 고정하고 정상/fault·실패·정리를 기록한다.
`--reuse`는 원본 source fingerprint와 실제 시험 commit이 같을 때만 추출에 사용한다.
Golden/독립 CRC·모델·solver/EV oracle을 구현과 분리하고, source/expiry를 바꿔 실패를 감추지 않는다.
[Component 추적표](component-traceability.csv)는 함수/구체 test/판정/evidence를 연결한다.

## MBD model and code verification

Status: **M6 Host quiet SIL/Python MIL 범위 종료 / M8 코드 동등성·차량 폐루프 NOT RUN**.
[M6 종료 검토표](../archive/milestone-reviews.md#m6)가 기존 근거와 현재 완료/미실행 범위를 구분한다. [ADR-0052](../archive/design-decisions.md#adr-0052)와
[개발 계획](../development-guide.md)을 따른다. 첫 대상은 Central 종방향 속도 제어기다.
현재 C++ 단위/plant·Host SIL PASS와 새 제어 모델 MIL·동등성 결과를 구분한다.

| 계층 | 실행 대상 / 비교 | 필요한 증거 |
| --- | --- | --- |
| M6 MIL | 실행 가능한 제어 모델 + 종방향 plant | 고정 reference/초기 상태·외란·parameter·sample time/solver에서 추종·제약·fault/state 판정 |
| M8 component SIL / 동등성 | 모델과 컴파일된 수작업 C++에 동일한 input vector replay; 생성 코드 채택 시 같은 harness 추가 | 출력/관련 내부 상태의 수치 오차·mode/validity·허가/거부·INIT 전환 대조, model/code revision과 실패 로그 |
| M8 차량 SIL | 실제 Central controller→allocation→Zone→Leaf→actual→Simple Vehicle/CARLA | 기존 scenario·추종 성능과 fault/timing, 모델 가정·multirate/통신 지연·mapping의 영향 |
| 선택 후속 생성 pilot | 고정 model/tool/config에서 재생성한 code + adapter | 재생성 재현·build/정적 검사·동일 vector/회귀, 생성 코드와 수작업 code의 출처 구분 |

입력 vector는 source time·validity·permission·세션 경계도 포함한다. 속도 유지/증가/감소·지속 saturation 후 회복·
가감속/출력 변화율 경계·정지 부근·stale/invalid speed·허가 상실·새 INIT를 시험한다.
각 case는 제어식/상태 계약과 기존 requirement/TC에 연결하고, 정확한 숫자/매핑은 pilot 전에 고정한다.
초기 연결 대상은 기존 TC-CTRL-002–004 및 TC-COM-005/TC-ZON-003의 해당 부분이며 전체 system Result는 유지한다.

Sample/step·실행 순서·초기 state·parameter·precision·invalid/NaN·saturation/anti-windup과
절대/상대 오차·불일치 판정 규칙을 **결과를 보기 전에** 결정한다(TBD-16; timing TBD-04, tuning TBD-11).
모델과 C++가 같은 production 함수를 호출하는 비교를 독립 설계 검증으로 표시하지 않는다.
모델/코드의 tick별 동등성과 차량 closed-loop 성능·실시간 실행은 별도 판정이다.
도구 선택/생성 설정 변경 시 golden vector·모델/코드 비교와 영향 회귀를 다시 검토한다.
PIL/HIL·Target timing·안전 표준 적합성 결과는 이 계획으로 추가되지 않는다.

## Defined test cases

각 case의 requirement/component/interface는 [traceability](requirements-traceability.md)에 있다.
수치와 상세 입력/window는 scenario/timing/safety 계약을 적용한다. 아래 milestone은
구현/실행 계획이며 부분 시험과 end-to-end 결과는 별도 Result ID로 남긴다.

| Test ID | 설정 / 동작 | 관측 가능한 acceptance | Future milestone |
| --- | --- | --- | --- |
| TC-ARCH-001 | 두 보드에 동일 architecture/reference 독립 배포 | Central–Zone logical Ethernet, Zone–vECU vCAN, Host physical Ethernet; 다른 보드 의존 없음 | M0 topology review; M5/M12 runtime |
| TC-ZON-001 | ZON-S01 Front/Rear topology와 routing, vehicle-wide 배분 호출/plant writer audit | Central→각 Zone, Front→Steering/Brake 및 Rear→Drive/BMS; Central 별도 단일 VCU/배분, 원천 metadata 보존, 담당 Zone 우회·중복 actuation 없음 | M4/M5; M6/M7 loop; M12 독립 보드 |
| TC-ZON-002 | ZON-F01 각 Central–Zone link 방향별 loss/partition, Front/Rear/coordinator process 정지, Leaf 정지+Zone heartbeat, delay/replay | 각 critical stream <=100 ms 독립 loss 검출, reject는 valid age 미갱신; 원천 actual/dependency age 보존, local protection/Host gate, raw fallback 없음; physical response TBD-03/12/15 | M4/M5; M6/M7/M9 통합 |
| TC-ZON-003 | ZON-F02 startup missing source, 각 Zone/Leaf/coordinator restart, wrong epoch/late parent request, clear/rejoin | trusted INIT/session과 required power/health 재검증; parent 유효 기간 보존, payload로 epoch 자동 학습/자동 NORMAL 복귀 금지; handshake/budget TBD-12/14/15 | M4/M5/M6/M7 |
| TC-COM-001 | F01 정상 후 Steering Actual 중단 | last-valid RX부터 Zone loss <=100 ms, FAIL_SAFE/Host gate, command fallback 부재 | M2/M4; M6/M7/M9 통합 |
| TC-COM-002 | F02 CRC/duplicate/out-of-order/stale/epoch/restart/wrap | reject/accepted snapshot 유지, valid age 미갱신; 지속 invalid 시 timeout | M1/M2/M4/M5 |
| TC-COM-003 | F03 양수 구동/음수 회생 각각에서 Drive command만 상실, 다른 task/feedback 정상 | <=100 ms local detection, old demand 무효/zero motor torque target, M2에서 고정할 양·음수→0 응답 envelope | M1/M2/M4/M6/M9 |
| TC-COM-004 | F04 Central command/diagnostics 단절; 하위 loss 추가 variant | <=100 ms Zone local timeout, Central 승인 없는 보호, 하위 단절 시 vECU 보호 | M4/M5/M6/M7/M9 |
| TC-COM-005 | actual cached replay/aggregate heartbeat; steering/brake/drive 각 missing/invalid/stale variant | 원천 time/sequence/validity 보존; 각 stream <=100 ms loss 검출, raw fallback 없음, 다음 tick gate | M1 metadata; M4/M5/M6/M7 |
| TC-CTRL-001 | 같은 demand에 steering delay/jam/brake response 변화; writer/topology audit | Vehicle/actuator command와 actual 분리, actual 변화가 plant input에 반영; CARLA writer는 Plant Adapter 하나 | M2/M6/M7 |
| TC-CTRL-002 | S01 직선 30 km/h | 정상 공통 metric/ODD/route completion/loop invariant | M6 precursor; M7/M8 acceptance |
| TC-CTRL-003 | S02 완만한 곡선 30 km/h | 정상 공통 metric/ODD/route completion/loop invariant | M6 precursor; M7/M8 acceptance |
| TC-CTRL-004 | S03 직선→곡선→직선, 30→20 request | 두 plateau speed, route lateral/heading, continuous target 대비 overspeed, 감속 반영 | M6 precursor; M7/M8 acceptance |
| TC-REG-001 | 전진 감속 중 회생 단독/회생+마찰/마찰 단독; actual response 지연 변화 | 공통 wheel 기준 배분, valid regen limit 준수, actual 기반 보정; plant 중복 반영 없음; 응답 오차 TBD-02/03/06 | M2/M4/M6/M7 |
| TC-REG-002 | 회생 한계 감소/0 및 충전 수용 0; Brake saturation/slow response 추가 | Drive local cap 준수, 마찰 재배분, 부족분/원인 기록, envelope 이탈 보호; 전환 budget TBD-03/06 | M2/M4/M6/M7 |
| TC-REG-003 | 감속→저속→정지/hold, 다시 출발 | 저속 마찰 전환/hold, 정지에서 회생 에너지 0; 경계/hysteresis/압력/오차 TBD-03/06 | M2/M4/M6/M7 |
| TC-REG-004 | Capability invalid/stale/cached replay/valid 0; 별도로 Drive Actual loss | capability와 actual validity 분리, 새 회생 demand 억제, cached age 보존; actual loss는 <=100 ms 검출/FAIL_SAFE/Host gate | M1/M2/M4/M6/M7 |
| TC-REG-005 | known actual torque/speed/효율/charge cap fixture; command≠actual, friction-only, 정지, invalid sample | J 집계가 actual 기계적 에너지/충전 한계 이내, friction 제외, invalid는 측정 불가; 수치 적분 오차 TBD-02/03 | M2/M6; M7 mapping review |
| TC-EV-001 | EV-S01 전원 준비→주행→정지→종료; 센서/actuator actual 없는 startup variant | 요청≠power actual, READY≠NORMAL, 유효 health/실제 HV 전까지 normal torque 금지; non-driving INIT 순환 의존 없음; 종료 실제 응답/조건 TBD-12 | M1 handshake; M2/M4/M6/M7 |
| TC-EV-002 | EV-F01 BMS/power/constraint corruption/replay/epoch/valid 0/unknown/loss; Zone 재발행과 Drive cached dependency | reject/invalid 구분, 원천 time/age/validity 보존, critical loss <=100 ms 검출, local protection; rate/age/startup/clock/margin TBD-14 | M1 vectors/receiver/vCAN; M2/M3/M4/M5/M6/M7 |
| TC-EV-003 | EV-S02 SOC/온도/모터속도별 charge/discharge cap 변화, valid 0, Brake saturation/응답 지연 | Drive local 한계/permission 준수와 Central 배분, 실제 응답/부족분, W→N·m 변환 및 zero/low speed 경계; parameter/budget TBD-03/13 | M2/M4/M6/M7 |
| TC-EV-004 | EV-F01/02 precharge timeout/contactor mismatch/sensor invalid/LV/interlock와 Central 단절; clear/reinitialize | Central acknowledgement 없는 고장별 로컬 반응과 actual trace, 자동 복귀 금지; power 재검증과 기존 severity/Host gate; matrix/threshold/deadline TBD-12/14 | M2/M4 component; M6/M7/M9 integration |
| TC-EV-005 | EV-S02 actual DC power/효율/부하 fixture, 구동/회생/full/empty/invalid와 command≠actual | 단일 owner/clock의 battery energy/SOC balance, cap/경계/손실 준수, 마찰 회수·이중 집계 없음; 불일치 clip으로 은폐 금지, 오차 TBD-13 | M2/M6; M7 mapping review |
| TC-AI-001 | inference timeout/NaN/stale/infeasible; fallback input 상실 | AI reject→유효 classical fallback 또는 보호 상태; raw actuator 출력 없음; 전환 budget TBD-10 | M11 |
| TC-SAFE-001 | F01–F04 및 Brake/Drive actual loss/복합 loss/clear | 가용 actuator에 맞춘 FAIL_SAFE/local action, Central 기록과 독립; 물리 세부값 TBD-03/06 | M2/M4 local; M6/M7/M9 integration |
| TC-SAFE-002 | startup missing stream, epoch mismatch, fault clear/new frame/reinitialize | INIT 정상 출력 억제; startup 100 ms unavailable 검출; FAIL_SAFE→NORMAL 자동 복귀 없음; 명시적 INIT gate | M1 handshake; M2/M4/M6/M7 |
| TC-DIAG-001 | fault onset/duration 지정 후 clear/reconnect | fault→event/DTC/state correlation, local action, debounce/persistence 규칙 TBD-08 | M9 |
| TC-PERF-001 | timing trace, 고정 workload/overload | endpoint/clock/causal lineage, Mean/P95/P99/Max/sample/drop/miss/uncertainty 보고; deadline TBD-04 | M3 부분; M5/M7/M12 E2E |
| TC-PERF-002 | logical multirate trace; simulation pause/reset/slow Target | 20/50/100 Hz logical 설정, source frame 재사용 식별; clock별 age, epoch reset, wall-time miss 숨김 없음 | M3/M6/M7 |

SYS-COM-003 coverage는 Steering/Brake/Drive command RX, 세 actual RX, Central→Zone,
각 Host actual stream을 모두 포함한다. TC-SAFE-001에서 actuator별 command/feedback loss를
parameterize하며 F01–F04의 대표 사례만 실행하고 전체 stream이 검증됐다고 선언하지 않는다.
유효하지 않은 actual 자체는 즉시 거부하며 stream loss는 last-valid RX부터 <=100 ms에 검출한다.

SYS-COM-003/004 v0.3의 EV 추가 coverage는 TC-EV-002/004에서 BMS/power/Drive constraint의
critical stream 목록(TBD-14)에 따라 parameterize한다. 미구현 status source와 cached
dependency를 기존 actuator heartbeat로 대체하지 않는다. SYS-PERF-002 v0.3의 BMS task/
publication rate는 실행 전에 결정하며 100 Hz actuator rate와 자동으로 같다고 가정하지 않는다.
ZON-01 v0.5의 독립 Central–Zone routing은 TC-ZON-002/003에서 SYS-COM-003/004, SYS-SAFE-002/003과
SYS-EV-001/004 coverage를 확장한다. Peer heartbeat, BMS source, 각 actuator actual을
독립 판정하며 timeout 물리 반응과 detection 결과는 별도 기록한다.

일부 단계만 통과해 전체 requirement를 VERIFIED로 바꾸지 않는다. 미구현은 PLANNED,
실행 결과는 NOT RUN, 실행 시 필수 TBD 미해결은 BLOCKED다. 반복 횟수/실행 환경과
window를 실행 전에 고정한다(TBD-04/07/11). 실제 run에만 PASS/FAIL을 부여한다.

## Safety analysis and AUTOSAR evidence

[Concept study](../safety/concept-study.md)의 hazardous event 후보와 기존 TC의 연결은
coverage 검토용이다. 승인된 Safety Goal에서 도출된 검증 관계가 아니다. 검출 시험,
local reaction 시험, actual actuator response와 차량 거동 시험의 결과를 구분한다.
Feedback loss 검출이나 simulator tick gate 성공만으로 물리적 위험 회피를 입증하지 않는다.
추가 요구사항·시험이 필요하면 ID/revision과 traceability를 함께 검토한다.

AUTOSAR pilot의 OS 예제, RTE 생성, BSW 통신과 기존 closed-loop 통합은 각각 수행한
범위만 기록한다. 실제 사용한 release, 설정, generator, build/runtime 환경을 결과에
연결한다. Virtual driver/Host 실습의 결과를 MCU/Jetson runtime 또는 실제 CAN timing의
검증으로 확대하지 않는다. RG-01의 추가 TC와 F03 variant는 별도 후속 설계 변경이며
기존 M0 review나 AUTOSAR pilot의 실행 결과로 표시하지 않는다.

## Test case template

- Test ID / version / Requirement ID / Component / Interface ID: TBD
- 목적 / 검증 방법 / 사전 조건: TBD
- Scenario ID / ODD / seed / 초기 상태 / 입력 및 model/profile hash: TBD
- 환경 / build / 보드 / clock / simulator mode / 도구 버전: TBD
- 절차와 주입 대상 / 시작 시점 / 지속 시간 / 복구: TBD
- 관측 가능한 판정 기준 / 수치 threshold / 허용 오차 / 측정 endpoint: TBD
- 필요한 artifact / 실행 시간 / 반복 횟수 / 무효 실행 판정 규칙: TBD
- 정상, fault, edge case의 예상 동작: TBD

## Result template

Result ID (`RES-<test-suffix>-<run-id>`), Test ID/version, Requirement IDs, timestamp,
commit, resolved profile hash, board/environment, scenario/seed, command/procedure,
metric units/clock uncertainty, log/trace/checksum locations, observed vs expected,
verdict와 reviewer를 기록한다.

Verdict는 PASS / FAIL / BLOCKED / NOT RUN이다. Threshold나 환경이 부족하면 BLOCKED,
미실행이면 NOT RUN이다. TBD인 numeric acceptance를 PASS로 표시하지 않는다. Raw data는
`build/` 또는 `benchmark/results/raw/` 등 Git 대상 외부에 보관한다.
현재 component의 작은 공유 summary·CSV·그래프는 `docs/test-plan/evidence/`에 두고,
향후 차량 benchmark summary는 `benchmark/results/`에 둔다. 미실행 시험의 결과 파일을 만들어 PASS로 표시하지 않는다.

## M0 review and results boundary

[M0 baseline summary](../archive/milestone-reviews.md#m0)에 exit checklist, 문서 점검 증거와 범위를 기록한다.
M0 review PASS는 runtime TC의 PASS가 아니다. Result ID는 실제 시험 이후에만 부여하고,
현재 traceability의 Future Result는 모두 NOT RUN으로 유지한다. 학습자의 이해 기록은
[학습 원칙](../learning/README.md)에 따라 별도로 남긴다.
