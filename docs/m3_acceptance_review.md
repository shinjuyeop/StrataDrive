# M3 수용 검토: Host 실행·타이밍·보호 동작

Review ID: **M3-REV-20261019** / Date: **2026-10-19**.
판정: **Host 실행 기준 선택·기술 검토 완료 / 타이밍 예외 OPEN / 전체 M3 수용 PENDING**.
수행: Codex의 계약·코드·보존된 실행 증거 대조. Milestone은 **IN PROGRESS**로 유지한다.

다음 Host 통합의 기준으로 IO 동반 CPU 배치와 owner별 FIFO 설정을 선택한다.
기존 실행의 기본 정책을 변경하지 않으며 명시적 CLI 옵션으로 적용한다.
정상 비교 24회와 FIFO 고장 회귀는 통과했지만 일반 우선순위 sanitizer의 실패 2건은 남아 있다.
이 선택은 해당 Host fixture에서 후속 통합을 시작할 기준이며 전체 timing 충족이나 학습자 수용 판정은 아니다.

## 검토 범위와 근거

측정 구현은 `7843a7e`, 직전 결과 문서는 `66c1dc3`이다. 이번 집계 수정은 `da185c3`이다.
검토 기준은 [timing 계약](requirements/timing_requirements.md),
[다중 주기·CAN 감시](adr/ADR-0034-multirate-runtime-and-can-loss-monitoring.md),
[비동기 Actual](adr/ADR-0036-asynchronous-drive-actual-feedback.md),
[owner 완료 guard](adr/ADR-0039-owner-completion-guards.md),
[native FIFO](adr/ADR-0042-native-owner-fifo-scheduling.md)다.
기존 [학습 원칙](learning/README.md)과 [품질 정책](quality_policy.md)을 적용한다.

대상은 x86_64 Host의 finite Linux/vCAN 실행과 별도 Steering hosted OS 파일럿이다.
Native multirate는 Brake/Drive/BMS/Power·RX·monitor·plant 일곱 owner를 실행한다.
Steering은 별도 native/RTOS fixture로 검사했으며 모든 Leaf가 한 차량 runtime에 통합된 결과는 아니다.
Central request/grant·relay·고정 speed 20 rad/s는 fixture다.
Central/두 Zone·DDS·차량 운동·CARLA·Target timing 및 RTE/BSW는 후속 범위다.

| 수용 항목 | 대조한 근거와 판정 |
| --- | --- |
| Release·실행·완료·누락 분모 | Absolute release와 개별 시한, skipped row·monitor tail을 유지. 정상 비교의 eligible/miss/skip 대조 PASS |
| Clock·원천 시각·Actual | Local CLOCK_MONOTONIC, 실제 torque 취득→보고 생성→socket TX→독립 RX를 보존. Local 부분 검사 PASS; cross-node/E2E 미실행 |
| 작업 정지·유효 수신 상실 | ECU/RX stall, CRC-invalid·Actual replay, owner overrun/stall·교차 guard·수신 이중 감시의 FIFO 회귀 PASS |
| 보호 요청·물리 적용·관측 | 검출→plant 보호 목표 적용과 유한 pressure/torque 응답을 구분. Plant/process 전체 정지 중 출력 변경은 보장하지 않음 |
| 실제 CPU·policy·startup·복원 | Native 92회의 설정·배치·부하 control PASS. 별도 CLI 3건의 예상 거부 PASS; 부분 설정 실패 시 workload 미실행 |
| 일반/FIFO 비교 | 동일 binary·workload·시한의 24/24 PASS. 선택한 Host 배치/FIFO의 근거로 사용 |
| Sanitizer 회귀 | OTHER 15/17, FIFO 17/17. OTHER 두 타이밍 실패 OPEN; sanitizer 결과를 성능 표본에 합치지 않음 |
| Hosted OS·ARM64 | Trampoline 기능 회귀 4/4, ARM64 교차 빌드 PASS. Hosted tick drift와 보드 runtime은 미해소/미실행 |
| 전체 시스템·학습자 수용 | 32개 requirement/29개 system TC는 NOT RUN. 직접 재현·설명 기록은 PENDING |

위 PASS는 명시한 유한 component 실행에 적용한다. 전체 system requirement의 VERIFIED 판정으로 확대하지 않는다.

## 선택한 Host 실행 기준과 분모

기존 [reference.yaml](../profiles/reference.yaml)의 `m3_multirate_runtime_fixture`와
`m3_native_fifo_fixture` 값을 사용한다. YAML은 설계 기록이며 loader는 없다.

| Owner | CPU 역할 | FIFO priority | 주기 / 완료 시한 (ms) | Run당 eligible jobs |
| --- | --- | --- | --- | --- |
| Brake | Work B | 10 | 10 / 5 | 240 |
| Drive | Work B | 10 | 10 / 5 | 240 |
| BMS | Work B | 9 | 20 / 8 | 120 |
| Power | Work B | 10 | 10 / 5 | 240 |
| RX | IO A | 18 | 2 / 3 | 1210 |
| Monitor | IO A | 20 | 2 / 4 | 1211 guarded slots |
| Plant/fixture | IO A | 19 | 2 / 4 | 1211 guarded slots |

이번 Host는 IO A=CPU 0, Work B=CPU 1의 서로 다른 physical core를 사용했다.
다른 Host에서는 allowed mask·topology와 실제 owner 설정을 다시 확인한다. 우선순위는 초기 fixture이며 최적값을 입증하지 않았다.
Owner 순서의 CLI 값은 `owner-cpus=1,1,1,1,0,0,0`, `owner-fifo=10,10,9,10,18,20,19`다.
계정 rtprio 상한 20을 받는 새 PAM 실행 세션과 SCHED_OTHER/0 launcher를 사용한다.
일곱 owner의 실제 설정·ready 확인 후에만 시작하며 실패 시 일반 policy로 대체하지 않는다.
호출 thread의 policy·priority·affinity는 join/파일 출력 전에 복원한다.

정상 workload는 2400 ms, 감시 tail은 40 ms, warm-up 제외는 0이다.
Monitor/plant는 각각 총 1221 slots를 관측하고 마지막 10개를 guard 분모에서 제외한다.
Guard는 enable부터 2420 ms까지 1211 slots, 마지막 시한은 2424 ms다.
최신 release를 실행해도 생략된 이전 slot은 miss로 남긴다.
정상 비교 24회의 분모는 Brake/Drive/Power 각각 **5760**, BMS **2880**, RX **29040**,
monitor/plant guarded slot은 각각 **29064**이며 이 범위의 missed/skipped는 모두 0이다.
주입 시험은 주입된 누락을 0으로 요구하지 않고 해당 정지 검출·보호·관련 없는 누락 여부를 검사한다.

유효 RX threshold는 80 ms, 마지막 accepted RX부터 실제 검출까지 상한은 100 ms다.
Raw/CRC-invalid/replay는 accepted age를 갱신하지 않는다. Owner 시한 이후 검출 margin과
첫 검출 이후 보호 목표 적용 margin은 각각 10 ms의 Host 기준이다.
후자는 plant가 실행 가능한 주입 조건에서 검사하며 실제 압력 도달·차량 정지 시한과 다르다.

## 보존된 결과와 타이밍 예외

| 실행 묶음 | 결과 |
| --- | --- |
| Normal build 일반/FIFO × quiet/loaded × full/minimal × 3회 | 24/24 PASS |
| Normal build OTHER / FIFO 고장 회귀 | 각각 17/17 PASS |
| ASan/UBSan OTHER / FIFO 고장 회귀 | 15/17 / 17/17 PASS |
| 별도 hosted OS Steering 회귀 | 4/4 PASS |
| 합계 | **94/96 PASS, 2 FAIL 보존** |

Native FIFO는 비교 12회와 두 build 고장 회귀 34회를 합쳐 46/46 PASS다.
CLI 권한 없음·부분 설정 거부·중복 옵션 3건은 예상 거부 검사이며 96회 분모에 넣지 않는다.

추가 부하의 Drive release→완료 지연은 다음과 같다. 단위는 ms이며 각 셀은 독립 3회에서
수집한 720개 job 관측의 nearest-rank p99다. Run별 p99의 평균이나 단계별 percentile 합이 아니다.

| Trace | OTHER p99 / max | FIFO p99 / max | 시한 |
| --- | --- | --- | --- |
| Full | 1.946878 / 2.638265 | 0.065454 / 0.099024 | 5 |
| Minimal | 2.449738 / 2.493961 | 0.073157 / 0.090526 | 5 |

Quiet/minimal RX max는 OTHER 0.342025 ms, FIFO 1.065564 ms로 모두 3 ms 안이었다.
부하는 Work B의 SCHED_OTHER 7/10 ms wall busy window이며 실제 CPU 비율 경계는 약 0.664–0.688이었다.
Host는 i7-11700·Linux 6.8.0-138-generic PREEMPT_DYNAMIC, governor powersave다.
Power/clocks/cooling·background는 고정하지 않았다. 짧은 관측과 세 번의 반복으로 WCET·hard real-time을 보장하지 않는다.
Full/minimal은 별도 관측이며 그 차이를 시한에서 빼지 않는다.

두 FAIL은 모두 sanitizer OTHER·full trace다. 다음 시각은 enable 기준 ms다.

| Run / 원래 실패 | 관측과 보호 동작 |
| --- | --- |
| `power-stall-full-1` / `unplanned owner deadline miss` | Plant slot 1035(release 2070) 생략, 다음 요청 wake 지연 2.053252. Monitor 검출 2074.100001, floor 목표 plant 적용 2076.057343. 그때 압력은 이미 1.3 MPa. Power 정지 때문에 먼저 적용한 zero 목표는 1104.230218, 실제 torque 0 관측은 1200.234945 |
| `rx-stall-full-1` / `Drive gate never enabled before fault` | Plant slots 210/721·monitor slot 721 생략. 요청 wake 지연 2.073495/2.054862/2.111280. 첫 검출 424.154572, floor/zero 목표 적용 426.067791. 그때 압력 0.3 MPa, 1 MPa 이상 첫 관측 566.313704; torque는 이미 0 |

총 4개 guarded slot 누락이다. RX 시험은 계획한 1100 ms 주입 전에 보호되어 Drive가 활성화되지 않았다.
보호가 실행된 사실은 원래 시험 조건의 실패를 없애지 않는다. Plant body max는 각각 0.238077/0.205986 ms였지만
이 사실만으로 timer·IRQ·runqueue의 원인을 특정할 수 없다. 이 cohort의 kernel trace는 없다.
별도 observer 실험의 runqueue 증가를 이 두 run의 원인으로 소급하지 않는다.
Runtime abort/trace drop·설정 control 실패는 없었고 시한 완화나 재실행 PASS로 원본을 교체하지 않았다.

`floor_applied_ns`/`zero_applied_ns`는 물리 owner가 보호 목표를 받은 시각이다.
Actual이 그 목표에 도달한 시각은 `physical.csv`에서 따로 확인해야 한다.
특히 이미 torque 0인 RX 실패는 주행 중 감속 성공의 증거로 쓸 수 없다.

## 이번 검토의 집계 수정과 증거

여러 run을 합친 nested `guarded_deadlines.observed_start_interval_ms`가 실행 사이의 대기 시간을
포함하는 오류를 발견했다. 기존 `pooled_job_metrics`로 run 경계를 보존하도록 수정하고
guarded slot·tail·skip을 포함한 회귀 검사를 추가했다. Python은 **60개 PASS**다.
수정 전 회귀 검사의 interval 수는 예상 3개 대신 4개로 실패했다.

보존된 96회를 수정한 리포터로 재분석했다. 비교 8조건×2 owner의 해당 16개 분포만 바뀌었고,
각 분포의 interval 표본은 3632→3630이다. 개별 run의 owner 통계·판정, Drive/RX 응답 지연,
job 분모·miss/skip·trace 비교는 동일했다. 새 workload 실행은 **0회**다.
이번 변경은 리포터와 회귀 검사이며 native runtime/binary·주기·시한은 수정하지 않았다.
직전 C++ normal/sanitizer 각각 523개·static/build PASS는 기존 검사 이력으로 유지한다.

원본은 `build/m3-fifo-comparison/`, `build/m3-fifo-{other-faults,fifo-faults,asan-other-faults,asan-fifo-faults}/`,
`build/m3-fifo-rtos-regression/`에 있다. 각 environment/source/binary·CSV/summary/artifact manifest를 보존했다.
검토 전 감사는 구현 commit의 blob·현재 source/binary·manifest를 대조했다.
`build/m3-acceptance-review/`에 그 감사 `m3-fifo-evidence.*`와 수정 후 `reanalyze.py`·`reanalysis.json`·`reanalysis.txt`를 둔다.
원본 summary/hash는 교정된 값으로 덮어쓰지 않았다. 상세 실행 명령·과거 실패·build 한계는
[품질 기록](quality_policy.md#2026-10-19--native-owner별-fifo-실행과-동일-부하-비교)과
[학습 안내](learning/m3_native_fifo.md)에 있다. `build/`는 git 제외 경로이며 clone에 원본 로그가 포함되지는 않는다.

## 남은 항목과 다음 단계

| 항목 | 닫기 위해 필요한 증거 / 책임 단계 |
| --- | --- |
| OPEN-M3-01 일반 sanitizer 타이밍 실패 | 두 원본 run·4개 skip을 보존하고 wake 지연 원인을 추가 관측. 원인·영향·개선 또는 적용 범위 제한의 근거와 새 cohort 회귀를 검토한다. 새 PASS만으로 닫지 않는다. **M3 timing 담당** |
| OPEN-M3-02 추가 지연 분석 | Trace/perf 접근 준비 후 같은 TID/clock의 timer→wakeup→switch 대조, observer overhead·miss·실제 부하를 기록. PREEMPT_RT 비교는 후속 실험이며 FIFO 적용과 구분한다. **M3 진단 후속** |
| OPEN-M3-03 학습자 수용 | Period/deadline·skip·source/accepted age·보호 목표/Actual·일반/FIFO 결과를 직접 재현하고 설명한다. **Project owner; M1/M2 review도 PENDING** |
| Target timing·hosted OS | Board OS/BSP/sysroot·ELF ABI/stack/IPC/SocketCAN과 실제 ARM64 runtime·tick drift 검증. 교차 빌드 PASS를 실행 PASS로 바꾸지 않는다. **Target 배포/M5·M12 및 OS 확장 전** |
| Cross-node·전체 E2E | Central/각 Zone task budget·clock uncertainty·QoS와 원천 인과 경로를 연결한 측정. **M4/M5/M7** |

Kernel trace 미확보·PREEMPT_RT 미실험·Target 미실행은 해당 증거의 공백이다.
PREEMPT_RT 채택을 새로운 필수 요구로 추가하거나 기존 Host 시험을 Target 시험으로 대체하지 않는다.
TBD-04는 Host fixture 값만 부분 결정했고 차량/Target·E2E의 전체 budget은 열린 상태다.

다음 구현은 **M4의 Central coordinator 입출력·상태 계약과 순수 판단 로직부터** 준비할 수 있다.
Central이 vehicle management/allocation/session을 소유하고 Front(Steering/Brake), Rear(Drive/BMS)를
각각 연결한다. Original source/dependency·parent expiry·유효 0/unknown·local loss/rejoin을 먼저 정의한다.
이 설계·기능 준비와 M3 timing 예외 해소를 병행할 수 있으나 M3 전체 수용 완료로 표시하지 않는다.
새 통합 workload의 task/queue/monitor budget을 먼저 정하고 정상·정지·재가입을 다시 시험해야 한다.
Central/Zone 추가 뒤에도 기존 보호 경로의 독립성과 실제 적용을 재확인한다.
실제 DDS transport는 M5, 차량 closed-loop/control은 후속 milestone이다.
