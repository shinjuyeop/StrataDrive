# 실행 명령과 범위

저장소 루트에서 실행했다. 최초/중간 build·probe·export의 실패와 교정은 README를 따른다.
최종 export의 목적지는 처음에 존재하지 않는 경로다. 기존 결과에 덮어쓰지 않는다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 3
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --parallel 3 --output-on-failure --output-junit /d/shin/StrataDrive/build/m9-native-work/normal-verified.xml
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --target native_diagnostics_test native_diagnostics_sil_test diagnostics_journal_test diagnostics_test control_diagnostics_sil_test control_recovery_sil_test owner_diagnostics_test owner_diagnostics_sil_test command_gateway_test rear_power_gateway_test bms_controller_test power_lifecycle_test --parallel 3
cmake --build build/m1-angle-sanitized --target speed_request_test normal_stop_test vehicle_coordinator_test --parallel 3
ctest --test-dir build/m1-angle-sanitized -R 'Diagnostics|ControlRecoverySil|BothZones/CommandGatewayTest|^CommandGateway\.|^ZoneLeafProtection\.|^FrontStartupTest\.|^RearPower|^BmsController|^Power(LifecycleTest|ControllerTiming|Configuration|Plant)\.|^NativePower\.' --parallel 2 --output-on-failure --output-junit /d/shin/StrataDrive/build/m9-native-work/asan-complete.xml
STRATADRIVE_M9_NATIVE_EVIDENCE=/d/shin/StrataDrive/build/m9-native-verified-normal build/m1-angle/native_diagnostics_sil_test --gtest_output=xml:/d/shin/StrataDrive/build/m9-native-work/export-verified-normal.xml
STRATADRIVE_M9_NATIVE_EVIDENCE=/d/shin/StrataDrive/build/m9-native-verified-asan build/m1-angle-sanitized/native_diagnostics_sil_test --gtest_output=xml:/d/shin/StrataDrive/build/m9-native-work/export-verified-asan.xml
python3 tests/integration/diagnostics/audit_native_diagnostics.py build/m9-native-verified-normal/central-pause --mutations
python3 tests/integration/diagnostics/audit_native_diagnostics.py build/m9-native-verified-normal/normal
python3 tests/integration/diagnostics/audit_native_diagnostics.py build/m9-native-verified-asan/central-pause --mutations
python3 tests/integration/diagnostics/audit_native_diagnostics.py build/m9-native-verified-asan/normal
ctest --test-dir build/m1-angle -R '^M4AsyncWall\.' --output-on-failure --output-junit /d/shin/StrataDrive/build/m9-native-work/wall.xml
python3 tests/unit/m4_source_fingerprint_test.py
cmake -S . -B build/m9-diagnostics-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build build/m9-diagnostics-release --target diagnostics_journal m4_async_runtime --parallel 2
python3 build/m9-native-work/run-static.py
cppcheck --project=build/m9-native-work/compilation-subset.json --enable=warning,performance,portability --error-exitcode=1 --suppress=missingIncludeSystem
```

`run-static.py`는 source11개의 compilation database include/define을 사용한다. Clang-tidy는
exit0, 추가 style 포함 cppcheck는 exit1(README의10개 advisory)이며 경고/성능/이식성
별도 검사는 exit0이다. Final ASan 선택206개의 실행 파일15개를 모두 다시 빌드/링크했고
`asan-selected-binaries.json`과 manifest에 그 binary hash를 보존한다.

압축 CSV는 원본 바이트를 새 위치에 풀어 감사한다. Manifest의16개 동일 산출물 SHA도
압축 전 바이트 기준이다. 최종 패키지를 별도 임시 위치에 풀어 packaged source auditor로
재감사했다. 이전 네 묶음 SHA와 새 package SHA 확인 로그는 원본을 따른다.
