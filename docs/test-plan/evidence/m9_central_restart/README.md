# M9 Central ECU process 재기동과 진단 발행자 계승

2026-11-03, base `fcc1e42` + [source overlay](sources/).
Central1 전체 ECU/SDK process를 실제 SIGKILL하고 Central2의 새 SDK client로 재합류했다.
Front/Rear·plant PID와 같은 kernel/clock은 유지했다. **연속성 reconciliation/clear·host reboot/clock
변경·반복 재기동 용량·native4ms/Target·TBD-08·M9/학습자 수용은 OPEN**이다.

Global issuer7→`(1<<32)|7`의 Epoch 경계를 trusted manifest로 고정한다. 원격 source는 actual
accepted credit와 새 원본 Session을 대조한 뒤 ACK 메모리0/ordinal1부터 새 collector로 원형
재전송한다. Source producer/sequence·run/profile·Session/credit 시각은 바꾸지 않는다.
Private lifecycle9100의 fsynced generation2와 fresh merged8002/replica/context source를 사용한다.
이전 merged/9개 replica의 검증 committed prefix만 가져오고 원본 suffix/incomplete는 보존한다.

Central의 저장 전 volatile event 손실 여부/개수는 확인하지 못한다. 새 observer의 SD-5001은
원래 boot 시각·세대1→2·cause_unknown/unmapped를 기록하고 clear를 막는다. 성공한 새 실제
정상 운전·정지/HV-off·모든 원본 replay도 이 marker의 Passed/clear 증거로 만들지 않는다.
Control512/diagnostic2048·FIFO8·pending32·retry100ms·drain2s·원래100ms 물리 판정은 유지한다.

검증 분모와 실제 결과는 [results.json](results.json), 도구·source/binary/config/SDK hash는
[manifest.json](manifest.json), 모든 보관 파일은 [SHA256SUMS](SHA256SUMS)가 기준이다.

| 검사 | 결과 |
| --- | --- |
| 일반 unit/logical/transport | 1206/1206 PASS |
| 기존 runtime.wall | 9/9 PASS |
| 영향 범위 ASan/UBSan | 305/305 PASS (기존 wall8 포함) |
| 실제 native SDK Normal / ASan / TSan | 12/12 · 12/12 · 3/3 PASS |
| 변경 C++ 정적 분석 | clang-tidy/cppcheck 각5 TU PASS |
| Release BUILD_TESTING=OFF / source fingerprint | PASS / 2/2 PASS |

`final-normal/asan`의12개 case와 `final-tsan`의 normal/drop-ack/Central 재기동3개는 각각 원본
result/PCAP/actual owner events/physical/store/capture/SDK log를 포함한다. 원래 `/var/tmp` 저장소는
남겨 두고 artifact copy와 모든 파일의 hash를 대조했다.

독립 Central auditor는 두 실제 process·생존 PID 동일·각 Epoch의8개 실제 accepted Release ACK
수신 시각·원본 Session·actual credit18개·새 SDK client의 모든 source ordinal ACK·fresh replica의
ordinal1·source/replica/merged bytes·old prefix/tail 보고·lifecycle와 미해제 DTC·물리 보호를 비교한다.
12개 변조(issuer/Release/old prefix/tail/gap/boot/credit/fresh ACK/ordinal1/clear/physical/survivor)를
거부한다. 기존 routing/adoption auditor도 각 기존 case에 재실행했다. 최종27개 dataset에서 총239개
변조를 거부했다. Native crash run의 old suffix는
0bytes였고, 실제 비커밋 suffix 보존·ID 충돌·foreign registry는 별도 component 시험 범위다.

초기 실패를 보존했다. `probe-central`은 Central readiness/EpochStore 발급 중 old status가 정상
FIFO8에 쌓여 overflow/새 Session 실패·Front cleanup SIGKILL로 FAIL했다. 기존 명시적 ingress
quiesce를 **새 process 시작 전부터 영속 Epoch 발급 종료까지** 적용해 이전 입력을 계수·차단했다.
이미 관측된 overflow를 지우거나 FIFO를 늘리지 않았다. 그 뒤 `probe-ingress`는 PASS이며 최종
유한 cohort와 구분한다. `before-ingress-fix`와 `before-runner-validation`에 당시 바뀐 source를 보존했다.

최초 C++ build의 misleading-indentation 오류와 Python runner의 indentation 오류도 해당 log와
`before-build-fix` source를 남겼다. Fingerprint 시험의 잘못된 module 경로 호출은 실패로 보존하고
실제 `tests/unit/m4_source_fingerprint_test.py`의2개 검사를 별도로 실행했다. Release는
BUILD_TESTING=OFF이며 기존 명시적 SDK pilot opt-in도 빌드했다. 과거 SDK TSan Rear rejoin 실패와
native guarded4ms0/6은 이번 성공으로 덮어쓰지 않는다. 이전 M9 증거 묶음의 SHA도 모두 재확인했다.

보관물 검증은 SDK 없이 가능하다.

```sh
python docs/test-plan/evidence/m9_central_restart/verify-packaged.py
```

실제 실행은 pinned vSomeIP3.7.6과 해당 normal/asan/tsan SDK 빌드가 필요하다.

```sh
python tests/integration/someip/native_diagnostics_run.py build/central-normal --profile normal
python tests/integration/someip/native_diagnostics_run.py build/central-asan --profile asan
python tests/integration/someip/native_diagnostics_run.py build/central-tsan --profile tsan --fixed-layout --cases normal drop-ack central-process-rejoin
```

실행 전 고정 recipe는 [diagnostics-protocol](../../diagnostics-protocol.md#central-process-재기동-fixture),
현재 계약은 [diagnostics](../../../interfaces/diagnostics.md#central-process-재기동과-trusted-issuer-계승)를 따른다.
