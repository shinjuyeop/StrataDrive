# ADR-0057: M4 공통 release 위상과 owner 모듈 분리

Date: 2026-10-20. Status: **구현·회귀 검사 / timing 예외 OPEN**.
기존 [ADR-0056](ADR-0056-m4-faults-and-independent-execution-watch.md)의 시한·miss 집계·보호 조건을 유지한다.

## 원본7 FAIL 조사와 작은 수정

원본12fc4a5/48회(41 PASS,7 FAIL)의 명령·실제 CPU/policy/priority/load·1211slots×10을 전부 감사했다.
[원본 audit와 최소 raw archive](../test-plan/evidence/m4_followup/README.md)는 재실행/재판정이 아니다.

FIFO Monitor311–315는 guard release에서 약1.528864ms 뒤 실행됐다. Slot316은 start/end0, deadline428838909964538ns,
독립 검출428838910477155ns다. 다음317은316 deadline 전에 완료됐지만316을 소급 완료시키지 않는 계약이므로 진짜 miss다.
실제 Monitor poll 최대2.722310ms와 guard-selected start 간격3.278ms를 구분한다. 약736.5ms 검출로 gate가 닫혀1200ms Drive 주입 전 arm이 실패했고, 원래 fault 시나리오도 올바르게 FAIL했다.

각 thread가 launch 뒤 별도 timer origin을 만든 반면 guard는 network 공통 origin을 사용한 **코드상 위상 불일치**를 확인했다.
원본 추가 지연0.722310ms의 커널 원인은 미확정이다. 요청 wake 시각이나 timer→wakeup→switch trace가 없었다.
Audit/trace hot-path 할당을 발견했지만 이 slot을 할당이 유발했다는 증거는 없다.
OTHER loaded6회는 CPU1의 owners2–7에서 함께 실행 기회가 누락됐고, 완료된 body의 deadline 초과는0이었다.
요청 CPU·FIFO 설정 실패/fallback은 없었다. CPU 경쟁/스케줄링 제약과 부합하지만 개별 wake 지연의 커널 원인을 확정하지 않는다.

Commit603fe24는 `M4ReleaseGrid`로 모든 sleep을 공통 절대 origin에 정렬하고 catch-up을 하지 않는다.
Audit duration/physical·central trace 저장소는 launch 전에 유한 run 크기로 reserve한다.
`requested_wake_ns`를 execution CSV 끝에 추가하고, audit 성장 횟수를 JSON에 더한다(기존 열/CLI 유지).
실제 요청 wake→start와 guard release→start를 구분한다. 재가입 guard도 같은2ms 격자에 올린다.
기존2ms opportunity,4ms deadline,1211slots,100ms lead/20ms tail,독립 검출/물리 적용 각각10ms는 바꾸지 않는다.
원본 위상/추가 지연을 replay한 logical test는 이전 위상에서316 miss, 정렬 후 miss 없음으로 원인 노출을 재현한다.

[사전 고정 프로토콜](../test-plan/m4_followup_protocol.md)의 새48회는42 PASS/6 FAIL이다.
FIFO24/24(Drive stop6/6 포함), OTHER loaded normal0/6이다. 원본41/7을 대체하거나 OPEN-M4-TIM-01을 닫지 않는다.
현재 Host integration의 기존 IO/FIFO 선택은 ADR-0042의 제한된 실험 profile이며, OTHER 부하 조건 전체 요구를 충족했다는 뜻이 아니다.

## 별도 동작 보존 리팩터링

Commit77d411c는 다음 책임을 기존 상위 directory 아래 분리했다. 새로운 scheduler/범용 framework는 없다.

| 모듈 | 소유 책임 |
| --- | --- |
| m4_async_runtime.cpp | public config/시나리오 dispatch |
| m4_owner_network.hpp/.cpp | private owner 상태·bindings·물리 적용·시나리오/고장 진행·세션 boot |
| m4_owner_execution.cpp | logical/native 실행·설정·launch·stop/join |
| m4_result.cpp | join 뒤 통계·판정·CSV/JSON |
| owner_messages.hpp / gateway_messages.hpp | canonical data, queue/atomic/controller 구현 의존 제거 |
| local_owner_transport.hpp | same-process SPSC·clock·atomic gate/protection |
| normal_stop_contract.hpp / bms_parent_context.hpp | 구현에서 공유 데이터 계약 추출; 옛 헤더는 include 호환 |
| session_reset.hpp/.cpp | 동기/비동기 공통 복구 predicate; 물리 상태 초기화 없음 |
| cmake/TestCategories.cmake | disjoint unit/integration.logical/runtime.wall; 기존 GTest/CTest 이름·assertion 유지 |

`owner_contract_boundary` compile-only target은 controller/queue header include 경로 없이 canonical contract를 컴파일한다.
기존908+release-grid/guard4=912개 이름이 모두 보존됐다. Label은 unit768/logical135/wall9다.
원본→위상 수정35개, 위상 수정→분리36개 logical physical trace가 byte 단위 동일했다. 신규 rejoin trace1개를 별도로 구분한다.
Normal/ASan·UBSan 각각912/912, 변경 native thread TSan9/9 PASS(ASLR process-local off)다.
리팩터링 후 별도48회도42 PASS/6 FAIL, FIFO24/24다. 두48회를 하나의 성공 cohort로 합치지 않는다.

## 남은 원인과 수용 경계

OPEN-M4-TIM-01은 **partial mitigation, OPEN**이다. 원본 FIFO 추가 wake 원인과 OTHER6개는 미해결이다.
필요한 추가 관측은 같은 CPU map에서 hrtimer expiry/요청 wake→sched_wakeup→sched_switch, runnable/IRQ/preemption·migration,
slot/owner TID correlation이다. 이 Host는 tracefs/perf 권한이 없어 해당 원인 분석은 BLOCKED이며 sysctl/권한을 임의 변경하지 않는다.
새 common-grid wake 기록은 application 구간만 좁힌다. PREEMPT_RT/RTOS·Target 또는 worst-case 상한 증거가 아니다.
기존 OPEN-M3-01/02와 학습자 검토, system32요구/29TC·Target NOT RUN을 유지한다.
