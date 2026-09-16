# Verification strategy

Status: **Planned**. M0의 문서/구조 검토를 vehicle/SIL 시험 통과로 표현하지 않는다.
실행 test source와 test result는 아직 없다. 아래 TC ID는 향후 case 후보이며 NOT_RUN이다.

## Verification layers

| Layer / directory | Planned checks | Evidence boundary |
| --- | --- | --- |
| Document review / M0 | architecture boundary, requirements, ICD fields, traceability, TBD ownership | 설계 검토일 뿐 runtime verification 아님 |
| Unit / tests/unit | CRC/counter golden vectors, state transitions, bounds, dynamics invariants | Linux software logic |
| Integration / tests/integration | vCAN and DDS contracts, timeout/reconnect, process isolation | application communication; real CAN electrical evidence 아님 |
| SIL / tests/sil | Simple Plant 이후 CARLA actual-feedback loop, route tracking | 정해진 scenario/ODD 안의 simulator behavior |
| Fault / tests/fault | loss/corruption/delay/jam/AI invalid/overrun injection and recovery | detection, local reaction, DTC, state, plant response 관측 |
| Performance / tests/performance | task timing tails, overload, reference and tier comparisons | 지정한 환경의 observed statistics; static WCET proof 아님 |

GoogleTest/pytest는 첫 구현과 함께 도입 예정이다. M0에서 설치하거나 빈 테스트를
PASS 처리하지 않는다. Regression은 scenario/seed/config/commit을 고정하고 이후
interface/schema/parameter 변경 시 영향 requirement와 baseline 재검토를 포함한다.

## Candidate cases

| Test ID | Proposed setup / action | Observable acceptance candidate | Stage |
| --- | --- | --- | --- |
| TC-ARCH-001 | 각 보드에 동일 architecture/reference를 독립 배포; topology 검토 | Central–Zone logical Ethernet, Zone–Leaf vCAN 및 타 보드 의존성 부재; versions recorded | M0 review; M5/M12 runtime |
| TC-COM-001 | 정상 steering feedback 후 송신 중단; last valid RX/loss onset 기록 | Zone 검출 latency가 검토된 threshold 이내; 현재 100 ms 예시는 TBD | M4 fault; M9 integration |
| TC-COM-002 | CRC 오류/duplicate/out-of-order/stale command 주입, restart/wrap case | reject 기록, valid-age 미갱신, 정책에 따른 timeout/rejoin | M1/M2/M4 |
| TC-CTRL-001 | 동일 demand에서 steering delay/jam 또는 brake response 변화 | actual feedback이 달라지면 adapter input/plant motion도 계약대로 변함; direct controller CARLA writer 없음 | M6/M7 |
| TC-AI-001 | inference timeout, NaN, stale history, infeasible trajectory; fallback 입력도 손실 | AI rejection → valid classical fallback 또는 안전 정책; AI raw actuator output 없음 | M11 |
| TC-SAFE-001 | actuator별/복합 interface loss와 fault-clear 재연결 | 가용 actuator에 맞춘 state/action, bounded reaction, RECOVERY gate; numerical limits TBD | M9 |
| TC-DIAG-001 | named fault를 onset/duration 지정하여 주입하고 clear | event→DTC→state correlation 및 local action, debounce/persistence/recovery policy 일치 | M9 |
| TC-PERF-001 | fixed reference workload, warm-up 후 반복 및 overload runs | E2E Mean/P95/P99/Max, sample/drop/miss count, jitter, environment/clock uncertainty 기록; threshold TBD | M3 instrumentation; M7/M12 E2E |

초기 unit/vector/integration 결과와 end-to-end 결과는 다른 Result ID로 연결한다.
일부 단계만 통과해 requirement 전체를 verified로 바꾸지 않는다.

## Test case template

- Test ID / version / requirement IDs / component / interface IDs: TBD
- Purpose / verification method / prerequisites: TBD
- Scenario ID / ODD / seed / initial state / input and model/profile hashes: TBD
- Environment / build / board / clock / simulator mode / tool versions: TBD
- Steps and injection target / onset / duration / recovery: TBD
- Observable oracle / numerical threshold / tolerance / measurement endpoints: TBD
- Required artifacts / run duration / repetition / invalid-run rules: TBD
- Expected normal, fault and edge-case behavior: TBD

## Result template

Result ID (`RES-<test-suffix>-<run-id>`), Test ID/version, Requirement IDs, timestamp,
commit, resolved profile hash, board/environment, scenario/seed, command/procedure,
metric units/clock uncertainty, log/trace/checksum locations, observed vs expected,
verdict와 reviewer를 기록한다.

Verdict는 PASS / FAIL / BLOCKED / NOT_RUN이다. Threshold나 환경이 부족하면 BLOCKED,
미실행이면 NOT_RUN이다. TBD인 numeric acceptance를 PASS로 표시하지 않는다. Raw data는
`benchmark/results/raw/` 등 Git 대상 외부에 보관하고, 향후 검토된 summary는
`benchmark/results/`에 둔다. 현재 실측 결과 파일은 만들지 않는다.

## M0 review checklist

- 지정된 모든 directory와 README, requirement/architecture/ICD/ADR/learning 문서가 있다.
- Planned/TBD와 implemented/measured를 구분하며 M1 이후 구현을 포함하지 않는다.
- Thor/Orin 독립성, actual-feedback closed-loop, AI/control 경계가 일관된다.
- 요구 → component → interface → case 연결과 미실행 Result 칸이 있다.
- Safe behavior, time base, units, QoS/CRC 등의 open questions와 owner가 있다.
- .gitignore가 large artifact를 제외하고 small-model exception 정책이 있다.
- CMake는 의존성 다운로드나 컴파일 없이 configure된다. 학습자가 설계를 설명할 수 있다.

기술적 checklist 확인과 학습자의 이해/설계 승인은 별개다. M0 baseline 승인은
[roadmap](../roadmap.md)의 미결정 사항을 학습자가 검토한 뒤 진행한다.
