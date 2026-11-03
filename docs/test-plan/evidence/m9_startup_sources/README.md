# Release 전 기동 시도 진단

2026-11-03. **Prepare·INIT·Release 세 phase logical SIL PASS; 전체 M9/TBD-08 OPEN**.
[계약](../../../interfaces/diagnostics.md#release-전-기동-시도와-실제-session),
[사전 recipe](../../diagnostics-protocol.md#release-전-기동-시도-진단-fixture),
[ADR-0084](../../../archive/design-decisions.md#adr-0084), C-M9-BOOT-01–06을 따른다.

## 경계와 결과

기존 정상 Session은 실제8-role Release 뒤에만 발생한다. 이번에는 권한 없는 trusted
Attempt를 그 전에 기록하고 원래 session detector의 최초 plan/state/reason/call/previous/
deadline/accepted ACK mask를 보존한다. Observer 때문에 추가 clock read나 제어 쓰기를 하지 않는다.
Run/clock6001·physical model7·Host10ms·명시적 store registry3이며 schema1은 유지한다.
Central7, local40–47, native30–33은 각 소유자의 별도 SPSC queue를 사용한다.

세 case는 Drive session ACK의 prepare/init/release를 각각 elapsed0–2.5s 동안 누락한다.
6s 실행 중3s에 기존 joined link를 교체하고 실제8-role INIT2를 수행한다. Native phase budget과
controller threshold/보호/권한은 그대로다. 아래 시간은 absolute simulation이며 wall 지연이 아니다.

| 원본 결과 | Prepare ACK 손실 | INIT ACK 손실 | Release ACK 손실 |
| --- | --- | --- | --- |
| 최초 원래 deadline | 3.000s | 1.041s | 1.041s |
| SD-4101 Timeout root | Central1 + participant8 | Central1 + participant8 | Central1 |
| Central accepted mask | 239 (Drive 제외) | 239 | 239 |
| 실패 epoch1의 Session / Passed | 0 / 0 | 0 / 0 | 0 / 0 |
| 새 epoch2의 Attempt / 실제 Session | 1 / 1 | 1 / 1 | 1 / 1 |
| 최종 Passed·미삭제 record | 9 | 9 | 1 |
| journal events / physical samples | 30 / 600 | 35 / 600 | 19 / 600 |

모든 record는 count1/generation1을 유지한다. Abort/Participant 보호 전달은 별도 Observation이며
root로 만들지 않는다. INIT/Release 실패에서도 원래 physical history의 gate/contacts/torque/
bus가 복구 전 inhibited 상태임을 확인한다. ACK 경로 복원만으로 Failed나 native latch가 풀리지
않는다. 새로운 Attempt의 Unknown은 복구가 아니며 실제 전역 Release와 해당 source의 정상
completion 뒤에만 Control proof/Passed를 기록한다. 기동 handshake 정상과 실제 차량/HV Ready는
별도 의미다. Native DTC의 기존 qualified dispatch/BMS Active/Power HV Ready 기준은 유지한다.

정상92s는4350 controls, Attempt1/Session1/DTC0이다. 세 phase 각각 collector on/off의 전
physical 표본·identity·energy·권한·원래 fault 시각이 같다. 연속으로 실패한 두 proposal도
서로 다른 occurrence로 기록하며 반복 관측은 중복 집계하지 않는다. Queue overflow는 원래
보호를 늦추거나 Release를 만들지 않는다. Release 전 proof/Passed/clear는 거부한다.

## 검증 분모

- 최종 일반 unit/logical **1154/1154**, 영향 ASan/UBSan **218/218**, 실패/skip0.
- 세 phase export fixture 및 정상/설정 검사: Normal **8/8**, ASan **8/8**.
- 기존 M4AsyncWall owner 회귀 **2/2**. Startup collector의 wall 지원을 뜻하지 않는다.
- 변경 production TU8개 clang-tidy warnings-as-errors / cppcheck warning·performance·portability 통과.
- BUILD_TESTING=OFF Release의 diagnostics_journal/m4_async_runtime 빌드와 source fingerprint 검사2개 통과.
- 독립 auditor는 두 빌드의 세 phase journal/source/physical을 대조하고 각10개 손상을 거부한다.
  두 빌드의 manifest/journal/commit·records/physical/source·native runtime CSV **24개**가 byte 동일하다.
- 이전 M9 증거6묶음의 SHA는43/153/135/203/183/186개 모두 유지한다. 과거 실행을 재실행으로 세지 않는다.

[results.json](results.json)은 최종 XML·독립 감사의 분모를 모으고,
[manifest.json](manifest.json)은 base commit·source overlay·fingerprint·binary/tool/config를 연결한다.
CSV/log는 gzip이며 store의 canonical bytes는 원본 그대로다. Binary 자체 대신 hash를 보관한다.
이번에는 새 TSan cohort를 실행하지 않았다. 이전 queue 경계의 TSan 근거를 확장 주장하지 않는다.

## 실패와 수정 이력

1. 최초 test compile은 같은 줄의 EXPECT_THROW 두 개로 생성 label이 중복되어 실패했다.
   `build-tests.log.gz`와 `compile-failed-source.cpp`에 보존했다. 줄을 분리한 뒤 빌드했다.
2. 최초 runtime probe는7개 중 Prepare recovery1개가 실패했다. 어떤 actor도 INIT하지 않은
   실패에 보호 ACK를 요구한 공통 verdict가 원인이었다. 실패 plan의 enable0·첫 epoch Release
   부재·복구 전 전 physical 표본의 gate closed/|torque|≤.1Nm/contacts0/bus≤30V를 요구하도록
   판정했다. Native timeout·응답 budget은 변경하지 않았다. `probe.xml`, `probe.log.gz`,
   `probe-source/`에 당시 source와 binary hash가 있다. ASSERT가 export보다 먼저 실패하여
   실패 Prepare의 raw journal은 내보내지 못했고 임시 store는 정리되었다. 보존되지 않은 raw를
   최종 자료로 대체하지 않는다. 수정 후 `probe-2.xml`은7/7이다.
3. 최초 독립 감사는 Participant Ready enum을6으로 잘못 예상해 실패했다. 실제 native enum5로
   수정했다. `audit-probe-source.py`/`audit-probe.err.gz`를 보존했다. 제어/검출 기준 변화는 없다.
4. 최종 diff 검토에서 이전 실패 뒤 성공 Release 없이 새 로컬 실패를 관측할 때 seen flag가
   새 proposal을 막을 수 있음을 수정했다. Epoch 증가 자체로 새 관측을 허용하고 두 연속 실패/
   반복 관측 검사를 추가했다. `before-recurrence-*`는 그 전1153/217 통과 기록이며 최종 분모와
   합산하지 않는다. 최종 빌드·회귀·export·감사는 그 수정 후 실행이다.
5. 추가 fingerprint 검사 명령의 경로 오타1회는 `fingerprint-invocation-error.log.gz`, 올바른
   `tests/unit/m4_source_fingerprint_test.py`의2/2 결과는 `fingerprint-final.log.gz`다.

## 재현

Base commit에 `manifest.json`의 `sources/` overlay를 적용한다. Bootstrap은 새 경로의 registry3만
사용하며 기존 registry1/2 store는 자동 변경하지 않는다. Export 목적지는 존재하지 않는 경로다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/m1-angle --parallel 3
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --output-on-failure --parallel 3
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 3
ctest --test-dir build/m1-angle-sanitized -L '^(unit|integration.logical)$' -R 'Diagnostics|^NativePower\.|ControlRecoverySil|Session|M4' --parallel 2 --output-on-failure
STRATADRIVE_M9_STARTUP_EVIDENCE="$PWD/build/startup-export" ctest --test-dir build/m1-angle -R 'StartupDiagnosticsSil|StartupDiagnosticsConfiguration' --output-on-failure
python3 -B tests/integration/diagnostics/audit_startup_diagnostics.py build/startup-export/prepare --mutations
python3 -B tests/integration/diagnostics/audit_startup_diagnostics.py build/startup-export/init --mutations
python3 -B tests/integration/diagnostics/audit_startup_diagnostics.py build/startup-export/release --mutations
python3 -B docs/test-plan/evidence/m9_startup_sources/verify-packaged.py
```

`verify-packaged.py`는 임시 경로로만 압축을 풀고 보존한 source auditor로6개 dataset과10개
변조 거부를 재검사한다. `SHA256SUMS`는 이 파일을 제외한 묶음 전체의 무결성이다.

Remote wire/spool·proposal 이전 bootstrap·source 재시작 adoption·Clock 복구·전체 scalar 영속
schema·전체 차량/CARLA30km/h fault matrix·wall/Target·학습자 이해 수용은 OPEN이다.
