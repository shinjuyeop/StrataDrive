# 실행 명령

저장소 루트에서 실행했다. Export 목적지는 처음에 존재하지 않은 별도 경로다.

```sh
cmake --build build/m1-angle --parallel 3
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --parallel 3 --output-on-failure --output-junit /d/shin/StrataDrive/build/m9-vehicle-work/normal.xml
cmake --build build/m1-angle-sanitized --target native_diagnostics_sil_test m4_async_runtime_test m4_fault_test control_diagnostics_sil_test control_recovery_sil_test owner_diagnostics_sil_test --parallel 3
ctest --test-dir build/m1-angle-sanitized -L '^(unit|integration.logical)$' -R 'Native.*Diagnostics|Control.*Sil|OwnerDiagnosticsSil|M4AsyncRuntime|M4Fault|M4ExecutionWatch|M4ReleaseGrid' --parallel 2 --output-on-failure --output-junit /d/shin/StrataDrive/build/m9-vehicle-work/asan.xml
STRATADRIVE_M9_NATIVE_EVIDENCE=/d/shin/StrataDrive/build/m9-vehicle-normal build/m1-angle/native_diagnostics_sil_test --gtest_output=xml:/d/shin/StrataDrive/build/m9-vehicle-work/export-normal.xml
STRATADRIVE_M9_NATIVE_EVIDENCE=/d/shin/StrataDrive/build/m9-vehicle-asan build/m1-angle-sanitized/native_diagnostics_sil_test --gtest_output=xml:/d/shin/StrataDrive/build/m9-vehicle-work/export-asan.xml
ctest --test-dir build/m1-angle -R '^M4AsyncWall\.' --output-on-failure --output-junit /d/shin/StrataDrive/build/m9-vehicle-work/wall.xml
python3 build/m9-vehicle-work/run-static.py
python3 tests/unit/m4_source_fingerprint_test.py
cmake -S . -B build/m9-diagnostics-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build build/m9-diagnostics-release --target m4_async_runtime --parallel 2
```

각 Normal/ASan export에 아래 감사를 실행했다. `<export>`는 위의 새 출력 root다.

```sh
python3 -B tests/integration/diagnostics/audit_native_vehicle.py <export>/bms-input-loss --mutations
python3 -B tests/integration/diagnostics/audit_native_vehicle.py <export>/power-input-loss --mutations
python3 -B tests/integration/diagnostics/audit_native_diagnostics.py <export>/central-pause --mutations
python3 -B tests/integration/diagnostics/audit_native_diagnostics.py <export>/normal
```

정적 분석은 compilation database의 include/define으로 production4 TU를 검사했다. 전체 tree의
warning0 또는 새 wall/Target 수용으로 올리지 않는다. ASan59개는 별도 경계이며 일반1137개와
중복 분모로 합치지 않는다. 같은 predicate Reader로 이전 control2/clear1/owner2 cohort를
압축 해제 후 재감사했다. Packaged source auditor로도 새 보관 자료를 재감사했다.
Source/binary/tool SHA·build cache 설정은 manifest에 있으며 CSV 동일 hash는 압축 전 기준이다.
