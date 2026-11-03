# M9 미확인 과거 이력의 서비스 수용과 현재 recording 상태 해제

2026-11-03, base `b0c5b81` + [source overlay](sources/).
현재 recording 검사 → 명시적 `AcceptUnknownHistory` → 영속 Review → 별도 Passed → 명시적
clear를 로컬 trusted service component에 연결했다. 원래 SD-5001의 cause_unknown/unmapped·
boot·세대·원형 bytes와 incident count1은 보존한다. 과거 손실이 없었다고 선언하거나 잃은 event를
재구성하지 않는다. **실제 native 서비스 요청 인증/인가·quiesce·최신 물리 evidence adapter·remote
clear/RPC·host reboot/clock 변경·native4ms/Target·TBD-08·M9/학습자 수용은 OPEN**이다.

`ContinuityInspector`는 fixed manifest 전체의 frozen source/replica 원형 bytes/semantic validity·
commit ordinal·ACK 완료·pending/queue loss 없음·원래 incident보다 높은 실제 global Session·
최신 정지/normal-dispatch 차단을 검사한다. 서비스 호출자는 해당 frozen 경계를 소유해야 한다.
Review는 정확한 incident/revision/proof와 모든 stream의 producer/ordinal/tip EventId/CRC를
기록한다. CRC는 인증이 아니다. 심사 전 Passed나 재시작 전 proof/Review의 duplicate는 새 현재
상태를 승격하지 않는다. 다른 미심사 incident·일반 unmapped 원인·incomplete·용량 초과는 차단한다.

로컬 service journal에만 registry4/tag2를 추가했다. 기존 Event/Clear bytes와 remote wire1/
registry1–3은 유지하고 local Review/Clear를 원격 Data로 수용하지 않는다. 원래 파일을 자동
이주/repair하지 않는다. Review와 clear는 기존64개 maintenance 예산을 공유한다. Runtime
FIFO8/pending32/retry100ms/drain2s·원래100ms 물리 판정·4ms 예산은 바꾸지 않았다.

| 검사 | 결과 |
| --- | --- |
| 일반 unit/logical/transport | 1215/1215 PASS |
| 기존 runtime.wall | 9/9 PASS |
| 영향 ASan/UBSan | 314/314 PASS (기존 wall8 포함) |
| 실제 native SDK Normal / ASan / TSan | 11/12 · 12/12 · 3/3 PASS |
| local Review/Clear remote Data 거부 확장 | 1/1 PASS; 위 일반 분모와 중복 |
| 변경 production 정적 분석 | clang-tidy/cppcheck 각3 TU PASS |
| Release BUILD_TESTING=OFF / source fingerprint | PASS / 2/2 PASS |

**Normal Central 재합류1건은 FAIL**이다. 새8-role Epoch2/진단 commit·ACK는 완료했지만 정상
제어 중 owner poll 간격88,577,464ns·RX overflow/rejected16과 보호 선택이 관측돼 정상 정지가
완료되지 않았다. Root scheduling 원인은 확정하지 않았다. 기준을 늘리거나 재실행으로 이 실패를
대체하지 않았다. ASan/TSan의 Central 성공과 다른 분모로 보존한다. 기존 native4ms 미통과도 유지한다.

서비스 fixture는 주입 가능한 logical monotonic clock99/run10/profile1이다. 실제 typed coordinator/
8-participant Release와 accepted RunLease gate·두 ContextualOutbox(source500/501)·별도 replica의
원형 전달/ACK를 사용한다. ServiceEvidence의 정지 값은 component typed fixture 입력이며 실제
native plant/실차 정지나 wall 성능 측정으로 세지 않는다. 서비스 writer child가 Proof/Review/Passed/
Clear의 fsynced commit을 알린 직후 parent가 실제 SIGKILL한다. 네 독립 store를 새 writer가 열면
count1/generation1·condition Unknown·commit된 disposition/tombstone만 유지해야 한다.
Normal/ASan의4컷씩을 별도로 보관한다. Native 회귀는 Review를 자동 발행하지 않는다.

독립 [감사 도구](sources/tests/integration/diagnostics/audit_continuity_review.py)는 canonical tag0/1/2·
registry4/watermark·원래16 Release ACK/4 accepted credit·source/replica/cut CRC·명시적 수용·
Passed/clear 순서/revision·실제 SIGKILL/Unknown·원형 미확인 사실을 비교하고12개 변조를 거부한다.
실제 native 경로도 기존 PCAP/저널 auditor로 별도 재감사한다. 최종 service2개와 통과한 native26개
dataset에서 총251개 변조를 거부했다. [results.json](results.json)은 초기
실패·최종 분모와 [manifest.json](manifest.json)의 source/binary/config/tool hash를 연결한다.
[SHA256SUMS](SHA256SUMS)는 모든 보관 파일의 무결성 기준이다. 이전 M9 증거14묶음·2635파일의 SHA를 재확인하고 수정하지 않았다.
Native runner의 넓은 source inventory에 포함됐지만 해당 native case가 호출하지 않은 service
auditor는 이후 full EventId 결속 검사를 강화했다. 당시 파일은 before-audit-binding-fix에
보존하고 native_source_variants에 차이를 명시했다. Native가 호출한 기존 auditor는 동일하다.

초기 component9개 중1개는 일반 unknown Observation을 만들며 다른 occurrence/key를 재사용해
거부됐다. 빈 occurrence로 교정했다. 초기 전체 회귀1215개 중3개는 (1) 심사 없이 Recording proof만
넣고 Passed를 기대한 옛 가정, (2) 재시작 전 proof로 append failure까지 도달하리라는 새 시험의
잘못된 가정, (3) registry4를 미지원으로 가정한 시험이었다. 현재 규칙에 맞춰 각각 차단 유지,
재시작 후 새 proof, 미지원 registry5로 수정했다. GTest macro의 brace 누락으로 실패한 초기 두
build와 당시 source도 보존했다. 제품 차단/예산을 완화해 통과시키지 않았다.

```sh
python docs/test-plan/evidence/m9_continuity_review/verify-packaged.py
STRATADRIVE_CONTINUITY_REVIEW_TEST_DIR="$PWD/build/service-review" ctest --test-dir build/m1-angle -R 'ContinuityReviewTest\.' --output-on-failure
python tests/integration/diagnostics/audit_continuity_review.py build/service-review --mutations
```

새 출력 폴더를 사용한다. 원본 `/var/tmp` native 저장소는 유지하고 artifact copy와 파일별 hash를
대조했다. 세부 [계약](../../../interfaces/diagnostics.md#연속성-미확인-incident의-로컬-서비스-심사)과
[사전 고정 recipe](../../diagnostics-protocol.md#연속성-로컬-서비스-심사-fixture)를 따른다.
