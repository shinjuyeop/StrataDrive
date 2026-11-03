# M9 SD-1001 복구·명시적 clear·재고장

2026-11-02. **SimpleVehicle 연속 논리 SIL PASS**.
[계약](../../../interfaces/diagnostics.md), [recipe](../../diagnostics-protocol.md#sd-1001-연속-복구-fixture),
[ADR-0080](../../../archive/design-decisions.md#adr-0080), C-M9-REC-01–05를 따른다.
SYS-DIAG-001/TC-DIAG-001 전체와 TBD-08 수용은 OPEN이다.

## 관측한 흐름

Run2001·producer7·simulation instance2001·profile1, 기존 Host10ms/20ms SpeedPI와
기본 NormalStop 제동5s/shutdown2s를 쓴다. 기존 source age30ms/skew20ms·검출
기준과 물리/배터리 모델은 바꾸지 않았다. 아래 시각은 **absolute simulation**이며
elapsed는1s를 뺀다. 이 시험의 clear는 명시적 service intent를 시험 driver가 전달한다.

| 시각 | 실제 경로와 DTC |
| --- | --- |
|11.000s /11.002s|SpeedRequest argument 누락 / native 검출 SD-1001 Failed·count1 |
|13.000s|argument 복원; 실제 traffic이 돌아와도 epoch1 latch/보호 유지 |
|21.000s|실제8-role trusted INIT2 요청; 요청/INIT만으로 Passed 없음 |
|21.7812s|실제 성공 SpeedRequest와 Coordinator accepted root·current readiness/permission 일치. Input Actual proof→Passed 한 번; 기존 이력 유지 |
|25.000s 이후|실제 NormalStop을20ms마다 갱신; Complete/Stopped·HV-off 도달 |
|29.000s|actual stationary·세 contactors open/HV≤30V·dispatch 억제 확인 후 명시적 선택 clear1건 durable commit |
|30.000s|writer만 재시작; tombstone/count 보존·현재 condition Unknown; clear ID replay는 Duplicate |
|32.000s|실제 trusted INIT3 요청; 같은 물리 모델·배터리 계속 실행 |
|37.000s /37.001s|두 번째 argument 누락 / native 재검출. Failed·generation2/count1 |
|41.000s|종료. 최초 fault/proof/clear와 새 fault 모두 journal에 보존 |

두 번의 원본 local 선택/ACK를 해당 epoch에서 연결했다. 실행 뒤 current epoch로만
필터링해 첫 고장의 선택을 잃지 않도록, 단일 thread 논리 driver에서 원본 log cursor를
진행한다. 새 관측 시각으로 선택/ACK/source를 바꾸지 않는다. Normal/ASan 양쪽에서
events51·명시적 clear1·committed transactions52다. 4000 physical/4000 EV 표본의
model epoch7·sequence/position·기존 vehicle/coupling/combined energy balance를 검사했다.
회생으로 chemical energy가 증가하는 구간도 실제 received_dc ledger로 정산한다.

## 검증

| 검사 | 결과와 원본 |
| --- | --- |
|일반 unit + integration.logical|1109/1109; failure/skip0. `normal.xml` |
|영향 ASan/UBSan|152/152; failure/skip0. `asan-final.xml` |
|최종 source의 복구 export|Normal/ASan 각3/3. `export-normal.xml`, `export-asan.xml` |
|기존 wall owner 회귀|2/2. `wall.xml`; wall diagnostics 검증은 아님 |
|독립 canonical journal/원본 감사|Normal/ASan 각 PASS·8개 mutation 거부. `audit-final-*.json` |
|이전 evidence 보존·호환|이전 component/hook SHA 전부 유지. 새 reader로 이전 정상/입력 누락 감사 PASS·입력 누락 mutation8 거부 |
|정적 검사|변경 production6 TU clang-tidy/cppcheck exit0. `compilation-subset.json`; clang의 non-user header warning generation 메시지 원본 보존 |
|기타|source fingerprint2/2; Release BUILD_TESTING=OFF의 diagnostics/control/runtime 빌드 PASS |

10개 복구 음성 경로(epoch/enable·input/identity/source·stale·INIT만·power 누락·diagnostics
session 누락·미수용 request) 뒤 원본 정상 증거만 Passed를 한 번 만들었다. 입력 복원만
하고 INIT를 하지 않는16s 별도 실행은 Failed/보호를 유지했다. 실제 이동 중·current input
누락·stale source의 clear 증거를 거절하고 revision·dispatch·moving 값·untrusted clear도
거부했다. 동일 native event를 받은 별도 MemoryJournal에서 append 실패를 주입해
StorageFailure/미삭제/incomplete를 확인했다. 실제 FileJournal commit/restart는 주 실행에서
검사했고 crash/물리 저장 실패 경계는 이전 component evidence를 따른다.

최초 검사 `first.xml`은 recovery/clear 흐름을 통과한 뒤 chemical energy 단조 감소를
잘못 요구해 실패했다. 원본 `failure-first/`를 보존한다. 회생을 허용하는 기존 cumulative
EV/vehicle balance 식으로 고쳤으며 tolerance/제어 budget은 바꾸지 않았다.
첫 Python 감사는 두 번째 INIT의 detector release도 첫 epoch와 같은2ms일 것으로 잘못
고정해 실패했다(`audit-first.log.gz`). 고정20ms 검출 경계와 원본 detector log 일치로
바로잡았다. 두 번째 실제 검출은1ms다. Native SpeedRequest의 const 설정 때문에 optional
copy-assignment가 금지된 build 실패도 보존하고 copy-construction으로 수정했다.
중간 판정은 최종 시험 수에 합산하지 않는다. 최종 source overlay와 실패 iteration의
전체 source snapshot은 구분하며 실패 당시 전체 snapshot은 저장하지 않았다.

이전 정상 dataset에 loss 전용 mutation 옵션을 잘못 붙인 감사 호출도 실패 로그
`compatibility-first.log.gz`에 남겼다. 정상은 기본 감사, input-loss만 mutation 감사로 재실행했다.
이 오류는 이전 journal/모델/감사 판정의 변경이 아니다.

## 재현과 경계

`manifest.json`의 base commit 위에 `sources/` overlay를 적용한다. Compiler/library/test
binary SHA와 tool versions, 정확한 명령·config는 manifest/commands를 따른다. Raw CSV는
gzip이며 `normal/`, `asan/`을 새 디렉터리에 복사해 풀면 독립 감사를 재실행할 수 있다.
Store binary는 원형으로 보존한다. 이 디렉터리에서 `sha256sum -c SHA256SUMS`로 검사한다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 4
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --output-on-failure
STRATADRIVE_M9_RECOVERY_EVIDENCE=/tmp/new-recovery build/m1-angle/control_recovery_sil_test
python3 tests/integration/diagnostics/audit_speed_recovery.py /tmp/new-recovery --mutations
```

Export destination이 이미 있으면 덮어쓰지 않고 거절한다. 같은 producer가 계속 살아 있고
writer만 재시작한다. Source emitter process의 occurrence 채택/restart, production background
writer·원격 clear 인증/UI·wire/spool·다른 code의 recovery·CARLA30km/h fault matrix·wall/Target
진단 latency는 이 검증에 포함하지 않는다. Writer 재시작은 clear 뒤 tombstone 보존을 검증한
범위이며 clear 전 재시작의 Unknown을 새 proof로 재평가하는 service 경로는 후속이다.
RT owner는 bounded snapshot/publish만 수행하고
파일 I/O/clear는 owner step 밖이다. 개인 이해 review와 전체 M9 종료는 별도다.
