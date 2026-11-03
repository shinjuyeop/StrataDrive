# Linux 로컬 연속성 서비스 연결

2026-11-03. SO_PEERCRED UID/PID·boot capability·고정 Session/incident/revision의 요청을
frozen source/replica/ACK 검사→Recording proof→영속 Review→별도 Passed에 연결했다.
Clear는 별도 요청으로 그 Passed ID·동일 전체 cut·새 정지 Actual을 다시 검사한다.
요청은 evidence/actor/임의 manifest·INIT/actuator 권한을 만들지 않는다.

실제 Linux Unix peer/서버 process와 SIGKILL4컷을 검증했다. Clock99와 Actual 값은 결정적
주입이며 실제3-ECU 서비스 운용/RT·SDK quiesce/plant 물리 정지 수용은 아니다.
시험의 생산자는 이미 종료했고 실제 Outbox ACK를 보존한 뒤 별도 writer가 journal lifetime
flock을 소유한다. 실행 중인 native ECU를 서비스 모드로 정지시키는 adapter는 후속이다.

| 분모 | 결과 |
| --- | --- |
| 최종 일반 unit/logical/transport | 1223/1223 |
| 기존 runtime.wall | 9/9 |
| 최종 서비스 ASan/UBSan | 8/8; 별도 Unix writer4컷 포함 |
| 최종 서비스 TSan | 고정 주소 배치7 unit+1 process=8/8; SDK 전체 수용 아님 |
| 앞선 넓은 ASan/UBSan | 336/336; 아래 두 최종 수정 전의 별도 실행 |
| 독립 감사 | Normal/ASan/TSan 각각4컷·11쌍 원본 Actual·16 Release ACK·4 accepted credit |
| 변조 거절 | 각각16종=48개 |
| clang-tidy/cppcheck | 현재 compile DB의 변경 production2 TU 각각 PASS |
| Release / BUILD_TESTING=OFF | PASS |
| source fingerprint 회귀 | 2/2 |

넓은 ASan336개 실행 뒤 Release 경고 수정과 Passed source 취득 시각 보존을 반영했다.
영향 받은 서비스8개를 ASan에서 다시 실행했고 최종 일반1223·TSan8·정적/Release 검사도
새 source에서 수행했다. 서로 다른 binary/source의 실행을 하나의 재실행으로 표시하지 않는다.
기존 native3-ECU SDK campaign은 이번에 재실행하지 않았다. 이전 Normal11/12의
Central88.6ms owner gap/overflow 실패는 이전 bundle에 그대로 남아 있다.

첫 compile은 misleading-indentation 경고로 실패했다. 초기 서비스 시험6/7과 진단용 process
0/1은 거부된 Unix packet을 읽지 않고 close하여 거부 응답이 유실된 문제로 실패했다.
Credential 거절 경로에서 최대 한 packet을 nonblocking으로 폐기하도록 고쳤다. 정상 인가된
요청을 추가로 읽어 버리지 않는다. 초기 Release의 vector header 확장 경고는20byte 고정 header와
명시적 copy/reserve로 고쳤다. Review 이후 새 관측 시각은 Passed.Observed에만 쓰고 원래 proof의
Source identity/acquisition은 보존하도록 추가 검사했다. 초기 logs와 수정 전 source를 보존했다.

TSan은 오래된 build tree에 새 target이 없어 build exit2였고, 새 tree의 기본 주소 배치에서는
unexpected memory mapping으로 exit66였다. 둘 다 SUT test를 실행하지 못한 시도다. ASLR을
끄는 `setarch x86_64 -R`의 별도 실행과 최종8개 통과를 구분한다. 허용 오차·FIFO·pending·
retry/drain·정지 age/skew·maintenance 예산은 늘리지 않았다.

[manifest.json](manifest.json)은 source overlay·base commit·binary/config/tool hash와 scope,
[results.json](results.json)은 원본 분모·실패·최종 감사와 이전15개 M9 bundle의2738파일 무결성을
기록한다. `logs/`와 초기/최종 process/source archive를 함께 보존한다. 수정 전 source/binary hash는
`before-release-and-binding-fix.tar.gz`와 해당 log metadata에 있다. 최종 수용은
`process-core-final`, `process-asan-final`, `process-tsan-final` 세 archive를 기준으로 한다.

저장소/SDK 없이 무결성과 최종 세 archive의 독립 감사·48개 변조 거절을 재현한다.

```sh
python3 -B docs/test-plan/evidence/m9_continuity_service/verify-packaged.py
```

현재 source에서는 `cmake --build build/m1-angle --target remote_diagnostics_context_test diagnostics_delivery_process_test` 후
새 `STRATADRIVE_CONTINUITY_SERVICE_TEST_DIR`를 지정하여 `ctest --test-dir build/m1-angle -R ContinuityServiceTest --output-on-failure`를 실행한다.
그 export directory에 `tests/integration/diagnostics/audit_continuity_service.py <directory> --mutations`를 적용한다.
[고정 recipe](../../diagnostics-protocol.md#linux-로컬-연속성-서비스-요청-fixture),
[현재 계약](../../../interfaces/diagnostics.md#linux-로컬-서비스-요청과-actual-취득-연결),
[ADR-0093](../../../archive/design-decisions.md#adr-0093)를 따른다.
실제3-ECU 서비스 조합·원격 인가/운용·다른 고장 조합·TBD-08·native4ms/Target·M9/학습자 수용은 OPEN이다.
