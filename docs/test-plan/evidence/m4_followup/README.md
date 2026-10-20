# M4 follow-up evidence — timing audit, refactor, remote contracts

Date: 2026-10-20. **현재 상태는 [project_status](../../../project_status.md)**, [M4 exit](../../../m4_exit_review.md)는 NOT CLOSED다.
Component functional PASS, native timing FAIL, race-warning 부재, 학습자 REVIEW PENDING과 system32req/29TC·Target NOT RUN을 구분한다.
원래 [m4_faults](../m4_faults/README.md) 결과/41 PASS·7 FAIL은 수정하지 않았다.

## 실행 묶음과 source

| 묶음 | 실제 source commit | 결과 |
| --- | --- | --- |
| 원본7 FAIL 정적 감사 | 12fc4a51449cd9f14ad1be8b243dea4d8d4d7311 | 원본48회41 PASS/7 FAIL 유지, 새 workload0회;7개 모두 설정/load/12110slot 일관성 확인 |
| phase 수정 | 603fe2405c44b17a96c938d4f797570ff598e770 | normal/ASan·UBSan 각912/912, TSan7/7; 별도48회42 PASS/6 FAIL/0 BLOCKED |
| 책임 분리 | 77d411cd6df6e9b99578227732dfcb133496872e | normal/ASan·UBSan 각912/912, TSan native9/9; 별도48회42 PASS/6 FAIL/0 BLOCKED |
| remote 계약 첫 회귀 | d7115ff87019521659de7055acd37c0d0a84efb6 | normal/ASan·UBSan 각948/948; remote36/36 TSan; native TSan8 PASS/1 FAIL·race 경고0 |
| probe 관측 보완 뒤 최종 회귀 | 5eb1b3b6b3e4d17ad0c19405f993cf843e8afaab | normal/ASan·UBSan 각948/948;68개 함수→시험→판정 연결,66 runtime artifact 검사 |
| middleware probe v1 | d7115ff | 36회30 PASS/6 FAIL(DDS up-loss3/overflow3); 원래 판정 보존 |
| middleware probe v2 | 5eb1b3b | 별도36회36 PASS/0 FAIL/0 BLOCKED; 실제 QoS·thread/CPU·load·tc 적용 검사 |
| middleware wrapper sanitizer | 5eb1b3b, upstream Release DSOs | normal/overflow×2후보:ASan·UBSan4 PASS, TSan4 FAIL·경고/exit66 |
| 완전 DDS 계측 진단 | 5eb1b3b + 별도 DDS11.0.1 TSan Debug SDK | 추가2 FAIL; entity-index/hopscotch/GC 경고 유지 |

Phase/refactor의 FIFO는 각각24/24(Drive stop6/6 포함), OTHER loaded normal은 각각0/6이다. 두 cohort를 합쳐 원본 실패를 대체하지 않는다.
새 release grid/사전 할당으로 원본 phase-crossing 노출을 보완했으나 추가 FIFO wake의 커널 원인·OTHER 실패는 미해결이다.
Latest948개는 unit798/integration.logical141/runtime.wall9이며, 초기912개 이름과 assertion을 모두 보존한다.
위 TSan native1 FAIL은 **CommandDelivery 후 정상 운전 보호 진입**이다(약915.3ms, pressure1MPa/torque0). Race 경고0을 기능 PASS로 바꾸지 않는다.
최초 run에 full event trace가 없어 정확한 실패 경로는 미확정이다. 별도1회 trace 진단은 PASS였고 원래9개 실패를 대체하지 않는다.

환경은 Linux6.8.0-138-generic/x86_64, GCC11.4, CMake4.3.2, Python3.10.12,16 CPUs다.
각 `results.json`/metadata에 source digest·source directory 목록·실제 clock/환경/입력·duration을 보존한다.
603fe24 이전 fingerprint는 cmake directory를 포함하지 않았으며77d411c부터 포함한다. 서로 다른 알고리즘의 digest를 같은 값으로 비교하지 않는다.
상위 최신 문서 commit과 실행 source commit이 달라도 위 원래 source 귀속을 유지한다.

## 파일과 판정 근거

- [baseline/analysis.json](baseline/analysis.json), [misses.csv](baseline/misses.csv), [FIFO 전후11slots](baseline/fifo-window.csv):7개 실패의 실제 명령·load·원본 SHA·slot/deadline/start/end/detection. [원본 최소 raw archive](baseline/original-failures.tar.gz)는43개 파일(전체48 요약+7 FAIL의 원본 execution/events/result/command/load/runtime)이며 분석을 byte 동일하게 재현했다.
- [phase/results.json](phase/results.json), [refactor/results.json](refactor/results.json), 각 `timing-results.csv`/`owner-timing.csv`: 분모48, 실제2.54s·1211slots/owner, CPU0/1·OTHER/FIFO·부하·3회 반복, 검출/적용 시각. Timing 중 build/다른 검증을 병행하지 않았다.
- [phase-logical-equivalence.json](phase-logical-equivalence.json), [refactor-logical-equivalence.json](refactor-logical-equivalence.json), [remote-logical-equivalence.json](remote-logical-equivalence.json), [최종 회귀의 동일성](remote-final-logical-equivalence.json): 원본→수정35개, 수정→분리36개, 분리→remote36개 physical CSV byte 동일. 관측 열 추가와 wall time 수치는 동일성 비교에 섞지 않았다.
- [remote/results.json](remote/results.json), [component_results.csv](remote/component_results.csv): 최종948개 두 build·68개 trace links. 각 단계 `verification/functional-tests.csv`는 전체 실제 시험 이름/판정이고 `functional-raw.tar.gz` 안에 원본 `normal|sanitized/{unit.xml,ctest.txt,...}`를 byte 그대로 보존한다. 최초 remote 결과는 `remote-initial/`에 별도 보존한다.
- [TSan native 실패 로그](remote-initial/verification/m4-remote-tsan-wall.log), [새36개 결과](remote-initial/verification/m4-remote-tsan-contract.log), [별도 진단](remote-initial/tsan-diagnostic/wall-normal.json): process-local ASLR off, source d7115ff. Default-ASLR 매핑 오류와 구분하며 시스템 ASLR/sysctl 변경은 하지 않았다.
- [정상 고장/복구 CSV](refactor/overflow-rejoin.csv), [그래프](refactor/overflow-rejoin.svg), [Drive pause/별도 watchdog](refactor/drive-stop-events.csv): 원래 source/deadline·모델/SOC/energy와 stopped ECU ACK 부재를 확인한다. Shared global gate/atomic 우회 효과는 원격 전달 보장이 아니다.
- `middleware/v1|v2/`: 전체36개 결과/metadata·조건별 요약·대표 normal/loss/overflow CSV·qdisc/thread/load·raw archive. Bare echo는 Actual/보호 ACK가 아니다. 늦은 응답과 reader rejection의 관측 보완 전후를 별도 묶음으로 보존한다.
- [release 위상 그래프](baseline/release-phase.svg), [middleware source-age 그래프](middleware/receipt-age.svg): 원본 missed slot과 별도 source603fe24 run을 비교하고, 늦은 echo/포화 입력을 원래30ms expiry와 대조한다. 이 graph는 kernel wake 원인이나 차량 Actual 응답이 아니다.
- `middleware/m4-probe-sanitizers/`의 commands/results/raw archive는 wrapper ASan4 PASS·TSan4 FAIL; `middleware/m4-dds-full-tsan/`은 SDK 전체 계측 추가2 FAIL·실제 loader 경로/SDK SHA/전체 stack을 보존한다. 경고 suppression은0이다.
- `static/`: Release build와 production4개의 clang-analyzer/cppcheck 원본. Analyzer 오류0, enum별 명시적 range registry에서 동일한 반환식의 branch-clone5개 경고는 보존했다.
- `artifacts.json`: 공유 파일 SHA256와 각 raw 위치/환경/source provenance. 기존 m4_faults의 manifest는 바꾸지 않았다.

정상 물리 fixture는 speed0rad/s, modelEpoch7, 초기angle0.1rad/pressure0.2MPa/torque0/SOC0.63/25°C, acceleration0.2m/s²/curvature0.02m⁻¹/aux0.25A다.
완전 차량 운동·타이어/ABS·OEM calibration이 아니다. Native source→RX/검출/출력 적용과 logical 경계 시각을 구분한다.

## 재현

필요: GTest/컴파일러/CMake/Python+matplotlib, native FIFO의 기존 rtprio20/CPU0·1 접근. 별도 source 재현은 해당 commit의 detached worktree를 사용한다. 현재 작업 tree를 과거 commit으로 바꾸지 않는다.

원본 실패의 **결정적 사후 감사**(재실행·재판정 없음):

```bash
mkdir -p build/replay-original
tar -xzf docs/test-plan/evidence/m4_followup/baseline/original-failures.tar.gz -C build/replay-original
python3 tests/integration/runtime/analyze_m4_failures.py build/replay-original build/replay-analysis
cmp build/replay-analysis/analysis.json docs/test-plan/evidence/m4_followup/baseline/analysis.json
```

새 source의 전체 normal/ASan·UBSan·durable CLI·representative fault 회귀:

```bash
python3 tests/integration/runtime/check_m4_faults.py --raw-dir build/reproduce-final --output build/reproduce-evidence
ctest --test-dir build/m4-readiness -L unit --output-on-failure
ctest --test-dir build/m4-readiness -L integration.logical --output-on-failure
```

과거603fe24 또는77d411c source의 **같은 native48 조건**은 그 worktree에서 functional runner 뒤 실행한다. 새 directory 필수이며 실패를 대체하지 않는다:

```bash
python3 tests/integration/runtime/check_m4_faults.py --raw-dir build/reproduce-final --output build/reproduce-evidence --reuse --timing-dir build/reproduce-timing --run-timing
```

TSan 변경 thread/contract 검사(항상 처음부터 full trace를 남긴다):

```bash
cmake -S . -B build/reproduce-tsan -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_TSAN=ON
cmake --build build/reproduce-tsan --target m4_fault_test m4_async_runtime_test session_coordinator_test periodic_task_test remote_leaf_test remote_contract_test -j4
STRATADRIVE_M4_RESULTS="$PWD/build/reproduce-tsan-traces" setarch x86_64 -R ctest --test-dir build/reproduce-tsan -L runtime.wall --output-on-failure --output-junit "$PWD/build/reproduce-tsan-wall.xml"
setarch x86_64 -R ctest --test-dir build/reproduce-tsan -R 'Remote|PeerFixture' --output-on-failure
```

Middleware dependency preparation/build(Host GNU x86_64 only; no global install):

```bash
python3 tests/integration/middleware/prepare_dependencies.py build/reproduce-deps
cmake -S . -B build/reproduce-probes -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DSTRATADRIVE_MIDDLEWARE_PROBES=ON -DCMAKE_PREFIX_PATH="$PWD/build/reproduce-deps/install" -DSTRATADRIVE_ZENOH_INCLUDE="$PWD/build/reproduce-deps/zenoh-c/include" -DSTRATADRIVE_ZENOH_LIBRARY="$PWD/build/reproduce-deps/zenoh-c/lib/libzenohc.so"
cmake --build build/reproduce-probes --target dds_candidate_probe zenoh_candidate_probe -j4
python3 tests/integration/middleware/run_probe.py --build build/reproduce-probes/tests/integration/middleware --output build/reproduce-middleware
```

[고정 v1](../../m4_middleware_probe_protocol.md)/[별도 v2](../../m4_middleware_probe_protocol_v2.md)를 따른다. `unshare -Urnm`/veth/tc 사용이 막히면 해당 run은 BLOCKED로 남고 기존 결과를 성공으로 대체하지 않는다.
Dependency 입력은 공식 [Cyclone release](https://github.com/eclipse-cyclonedds/cyclonedds/releases/tag/11.0.1)/[Zenoh-C release](https://github.com/eclipse-zenoh/zenoh-c/releases/tag/1.10.1)와 pinned URL/SHA를 기록한다. DDS [QoS API](https://cyclonedds.io/docs/cyclonedds/latest/api/qos.html)의 수용은 application expiry나 ECU ACK를 대신하지 않는다.

## 미해결/미실행

OPEN-M4-TIM-01과 기존 OPEN-M3-01/02, OPEN-M4-TSAN-01·OPEN-M4-MWTSAN-01 유지. SDK 경고는 false positive나 실제 제품 race로 확정하지 않았다. 억제 없이 원본 stack을 보존한다. DDS의 progress-based bucket reclamation/TSan happens-before 해석을 검토해야 한다. Zenoh 전체 Rust 계측은 cargo/Rust toolchain 부재로 미실행이다. Kernel timer/wakeup/switch trace는 권한 제약으로 미실행이다.
다른-kernel clock/Target/RTOS·Zenoh 내부 sanitizer·Host bridge·전체 Central/Front/Rear/Leaf 원격 제어/rejoin·시스템TC는 미실행이다.
M4 technical exit/첫 M5 controller adapter는 [검토의 차단 항목과 선택지](../../../m4_exit_review.md#남은-차단과-필요한-결정)를 따른다. 학습자 검토가 완료됐다고 기록하지 않는다.
