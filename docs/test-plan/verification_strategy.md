# Verification strategy

Status: case contract **DEFINED**, runtime implementation **PLANNED**, 모든 runtime result는
**NOT RUN**이다. M0 document review 결과와 vehicle/SIL verification을 구분한다.
TC ID의 유일한 정의 목록은 아래 표, S/F ID 정의는 [scenario baseline](scenario_baseline.md)이다.

## Verification layers

| 검증 계층 / directory | 계획된 검사 | 증거 범위 |
| --- | --- | --- |
| Document review / M0 | architecture 경계, 요구사항, ICD field, 추적성, TBD 담당자 | 설계 검토일 뿐 runtime verification 아님 |
| Unit / tests/unit | CRC/counter golden vectors, 상태 전환, 한계값, dynamics 불변 조건 | Linux software 로직 |
| Integration / tests/integration | vCAN/DDS 계약, timeout/재연결, process isolation | application 통신; 실제 CAN의 전기적 동작에 대한 증거 아님 |
| SIL / tests/sil | Simple Plant 이후 CARLA actual-feedback loop, route tracking | 정해진 scenario/ODD 안의 simulator behavior |
| Fault / tests/fault | loss/corruption/delay/jam/AI invalid/overrun 주입과 복구 | detection, local reaction, DTC, state, plant response 관측 |
| Performance / tests/performance | task timing tail, overload, reference와 tier별 비교 | 지정한 환경의 observed statistics; static WCET proof 아님 |

GoogleTest/pytest는 첫 구현과 함께 도입 예정이다. M0에서 설치하거나 빈 테스트를
PASS 처리하지 않는다. Regression은 scenario/seed/config/commit을 고정하고 이후
interface/schema/parameter 변경 시 영향 requirement와 baseline 재검토를 포함한다.

## Defined test cases

각 case의 requirement/component/interface는 [traceability](traceability.md)에 있다.
수치와 상세 입력/window는 scenario/timing/safety 계약을 적용한다. 아래 milestone은
구현/실행 계획이며 부분 시험과 end-to-end 결과는 별도 Result ID로 남긴다.

| Test ID | 설정 / 동작 | 관측 가능한 acceptance | Future milestone |
| --- | --- | --- | --- |
| TC-ARCH-001 | 두 보드에 동일 architecture/reference 독립 배포 | Central–Zone logical Ethernet, Zone–vECU vCAN, Host physical Ethernet; 다른 보드 의존 없음 | M0 topology review; M5/M12 runtime |
| TC-COM-001 | F01 정상 후 Steering Actual 중단 | last-valid RX부터 Zone loss <=100 ms, FAIL_SAFE/Host gate, command fallback 부재 | M2/M4; M6/M7/M9 통합 |
| TC-COM-002 | F02 CRC/duplicate/out-of-order/stale/epoch/restart/wrap | reject/accepted snapshot 유지, valid age 미갱신; 지속 invalid 시 timeout | M1/M2/M4/M5 |
| TC-COM-003 | F03 Drive command만 상실, 다른 task/feedback 정상 | <=100 ms local detection, old demand 무효/zero-propulsive target, M2에서 고정할 torque 감소 envelope | M1/M2/M4/M6/M9 |
| TC-COM-004 | F04 Central command/diagnostics 단절; 하위 loss 추가 variant | <=100 ms Zone local timeout, Central 승인 없는 보호, 하위 단절 시 vECU 보호 | M4/M5/M6/M7/M9 |
| TC-COM-005 | actual cached replay/aggregate heartbeat; steering/brake/drive 각 missing/invalid/stale variant | 원천 time/sequence/validity 보존; 각 stream <=100 ms loss 검출, raw fallback 없음, 다음 tick gate | M1 metadata; M4/M5/M6/M7 |
| TC-CTRL-001 | 같은 demand에 steering delay/jam/brake response 변화; writer/topology audit | Vehicle/actuator command와 actual 분리, actual 변화가 plant input에 반영; CARLA writer는 Plant Adapter 하나 | M2/M6/M7 |
| TC-CTRL-002 | S01 직선 30 km/h | 정상 공통 metric/ODD/route completion/loop invariant | M6 precursor; M7/M8 acceptance |
| TC-CTRL-003 | S02 완만한 곡선 30 km/h | 정상 공통 metric/ODD/route completion/loop invariant | M6 precursor; M7/M8 acceptance |
| TC-CTRL-004 | S03 직선→곡선→직선, 30→20 request | 두 plateau speed, route lateral/heading, continuous target 대비 overspeed, 감속 반영 | M6 precursor; M7/M8 acceptance |
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

일부 단계만 통과해 전체 requirement를 VERIFIED로 바꾸지 않는다. 미구현은 PLANNED,
실행 결과는 NOT RUN, 실행 시 필수 TBD 미해결은 BLOCKED다. 반복 횟수/실행 환경과
window를 실행 전에 고정한다(TBD-04/07/11). 실제 run에만 PASS/FAIL을 부여한다.

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
`benchmark/results/raw/` 등 Git 대상 외부에 보관하고, 향후 검토된 summary는
`benchmark/results/`에 둔다. 현재 실측 결과 파일은 만들지 않는다.

## M0 review and results boundary

[M0 baseline summary](../m0_baseline.md)에 exit checklist, 문서 점검 증거와 범위를 기록한다.
M0 review PASS는 runtime TC의 PASS가 아니다. Result ID는 실제 시험 이후에만 부여하고,
현재 traceability의 Future Result는 모두 NOT RUN으로 유지한다. 학습자의 이해 기록은
[학습 원칙](../learning/README.md)에 따라 별도로 남긴다.
