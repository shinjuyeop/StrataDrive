# M9 진단 집계·Linux 저장 component 검증

2026-11-02. **Host component PASS / 실제 monitor·차량 DTC 통합 NOT RUN**.
[계약](../../../interfaces/diagnostics.md), [프로토콜](../../diagnostics-protocol.md),
[C-M9-DIAG 추적성](../../component-traceability.csv)을 따른다.

## 구현과 판정 범위

`central/diagnostics/`의 Ledger·EventQueue·Recorder·FileJournal을 추가했다.
Qualified typed fault의 즉시 집계, immutable event ID·occurrence 분리, source 순서의
최초/최근 원인 보존, 역순 evidence 연결, 재발, restart/Unavailable의 Unknown 재평가,
fresh stationary/inhibited·revision 검사와 atomic clear를 검증했다.
Clear는 observed latch를 바꾸지 않고 durable tombstone을 추가한다.

기본 한계는 queue256, ledger events512/records64/occurrences128/clears64다.
유한 queue·기록 한계·identity mutation·저장 실패를 silent eviction으로 처리하지 않는다.
SPSC thread 시험은20000개 payload의 ID/내용을 확인한다. 새 writer/background scheduler와
실제 control owner 호출부는 아직 연결하지 않았다.

Linux store는 explicit bootstrap·lifetime flock·frame sequence/length/CRC32와
fsynced journal + atomic/fsynced commit watermark를 사용한다. Committed clear 재생,
과거 watermark 뒤 data, partial tail, committed truncation, checksum/metadata 손상,
symlink/hardlink·중복 writer, 실패 commit과 durable incomplete marker를 확인했다.
실패 시험은 `pending`을 directory로 만들어 실제 commit syscall을 실패시켰다.
물리 전원 차단·파일시스템 고장 내구성 검증은 아니다.

## 실행 분모와 도구

| 검사 | 결과 / 원본 |
| --- | --- |
| Normal unit + integration.logical | **1090/1090**, 실패/skip0. 새 진단38개 포함. `regression.xml`, `normal-regression.log.gz` |
| ASan/UBSan 진단 경계 | **38/38**, 실패/skip0. `asan.xml`, `asan-final.log.gz` |
| TSan queue/drain 경계 | **3/3**, 실제 filter 분모3. `tsan.xml`, `tsan-final.log.gz` |
| clang-tidy | 변경 production TU2개, 진단0. `clang-tidy.log.gz` |
| cppcheck | 실제 compilation database의 변경 TU2개, 진단0. `cppcheck.log.gz`, `compilation-subset.json` |
| Release / BUILD_TESTING=OFF | `diagnostics`, `diagnostics_journal` 두 library 빌드 통과. `release-*.log.gz` |
| Source fingerprint 회귀 | CMake/source 탐색 Python2/2. `source-fingerprint.log.gz` |

이전 실행의 Normal32개·중간37개 통과는 최종38개와 합산하지 않는다.
초기 cppcheck의 file-filter 지정은 파일을 찾지 못했다. 최종 검사는 compilation database에서
두 TU를 추출한 명시적 subset으로 실행했다. 이를 최초 검사 성공으로 소급하지 않는다.
전체 build 이후 새 진단 경계만 재빌드하고 최종 Normal1090개를 실행했다.
`runtime.wall`, Python 전체, CARLA/SDK/Target 시험은 이번에 실행하지 않았다.

`results.json`은 원본 XML의 분모, `versions.json`은 compiler/CMake/static-analysis/kernel,
`manifest.json`은 base commit + 검증 source overlay·한계·schema/registry revision이다.
원본 로그/XML의 시각은 고쳐 쓰지 않았다. Source snapshot은 `sources/`에 있다.
`SHA256SUMS`는 이 evidence 디렉터리의 파일을 검증한다.

## 재현

저장소 루트, `manifest.json`의 base commit에 `sources/` overlay를 적용한 source가 기준이다.
시스템 GTest1.11.0과 현재 Host 도구를 사용한다. 외부 다운로드는 하지 않는다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --output-on-failure
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --target diagnostics_test diagnostics_journal_test --parallel 2
ctest --test-dir build/m1-angle-sanitized -R '^Diagnostics' --output-on-failure
cmake -S . -B build/m9-diagnostics-tsan -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_TSAN=ON -DCMAKE_CXX_FLAGS=-fno-pie -DCMAKE_EXE_LINKER_FLAGS=-no-pie
cmake --build build/m9-diagnostics-tsan --target diagnostics_test --parallel 2
setarch x86_64 -R build/m9-diagnostics-tsan/diagnostics_test --gtest_filter='DiagnosticsQueue.*:DiagnosticsRecorder.QueueHealth*'
cmake -S . -B build/m9-diagnostics-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build build/m9-diagnostics-release --target diagnostics diagnostics_journal --parallel 2
clang-tidy -p build/m1-angle central/diagnostics/diagnostics.cpp central/diagnostics/diagnostics_journal.cpp --quiet
```

cppcheck에는 현재 `compile_commands.json`에서 두 diagnostics TU를 추출한 subset을 사용한다.
보관한 subset의 absolute build path는 당시 환경을 나타내므로 다른 checkout에서는 다시 추출한다.

## 남은 경계

이 시험은 synthetic numeric ID·typed Proof·ServiceEvidence를 사용했다. Actual/ACK의
qualification, stream validity와 dispatch 억제 여부를 실제 monitor에서 가져오는 hook은
후속이다. Code별 실제 enum 매핑·최초 검출 시각·복구 predicate, 정상 false-DTC0과 기존
저속 input-loss/NormalStop의 event→보호→Actual→DTC는 아직 통합 검증하지 않았다.

원본 response dwell·기본5s/별도30km/h10s·ACK/lane 손실은 기존 계약을 유지한다.
다음 tick 차단이나 typed proof 주입을 실제 제동/정지/HV-off로 세지 않는다.
30km/h fault recipe·실제 부하의 queue/store 용량 적합성·cross-process spool/전송·
자동 reconciliation은 후속이다. 일부 component PASS로 SYS-DIAG-001/TC-DIAG-001 전체,
TBD-08 최종 수용·개인 이해 review·wall/Target/표준 적합성을 완료하지 않는다.
