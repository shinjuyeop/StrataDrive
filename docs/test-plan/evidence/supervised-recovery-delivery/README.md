# 감독 제어 복구·명시적 해제와 Epoch 송수신 연결

2026-11-06, 기반 commit `02638f035f2aa991832d10a6c0b8b1a833fea1d6` 이후 변경이다.
선언한 M9 유한 기능 범위를 유지하며 다음 두 연결을 검증했다.

| 항목 | 결과 |
| --- | --- |
| 감독 SD-1002 / monitor4 | 새 INIT·같은 clock/config·최종 요청/dependency 수락·해당 요청의 실제 배분 성공 후 qualified Passed |
| 정상 정지 전환 | trusted NormalStop 제동/hold 요청만 provenance 전환; 같은 세션 주행 복귀와 양의 가속 거절 |
| 명시적 clear | 40초 논리 SIL, 입력 상실→복원 후 보호 유지→INIT2 복구→안전 정차/HV off→clear→writer 재기동→INIT3→재고장 |
| 원본 감사 | 53개 원본 Event = journal의 모든 Event, 명시적 Clear 1개; fault epoch1/3, 새 proof epoch2/3; 재발 generation2/count1 |
| 송수신 활성 창 | 40세션/160 Event, source40 segment·replica20 segment의 다른 threshold; ACK 유실·전체 재전송에도 count40/generation1 |
| 실제 SOME/IP | vSomeIP3.7.6, 별도 IP namespace/process; ordinal16 INIT2 영속화 직후 replica SIGKILL·재시작; 32개 전체 원문/ACK 일치 |
| 물리 분리 | 실제 SDK 전달과 동시에 논리 owner 실행; 진단 on/off 물리4,000개 CSV byte 동일; 실행 제어1,222개 |
| Debug 회귀 | 1,524개 모두 통과; 이후 배분 성공 qualification 보강의 복구5개 재검사와 추가 cold-reader1개 통과, 총1,525개 고유 검사 |
| ASan/UBSan | 관련162개 고유 검사 모두 통과, 누수/UB 중단 옵션 사용 |
| 기타 | Python280개, clang-tidy9개 translation unit, 독립 감사 변조6조건 거절 |

복구 음성 시험13조건은 이전 진단 세션, 다른 epoch/enable, wheel 누락/변조, 오래된 관측,
BMS 누락, INIT만 존재, 다른 clock/config/radius, 만료 요청을 거절한다. 최종 성공 snapshot의
짧아진 expiry와 원본 force dependency를 별도로 검사한다. 일반 Speed observer의 제한 전
PI request를 감독 복구로 대신 쓰지 않는다. 이미 clear된 과거 fault에 INIT3의 fresh proof가
다시 관측돼도 clear/count는 유지되고 실제 재고장이 새 generation을 만든다.

통신은 event-only Outbox/Inbox family opt-in이다. Root stream7001, source/replica 각각2개 segment,
최종32 entry/활성17 entry다. 원본 Session2는 ordinal16이며 강제 종료 후 Duplicate ACK로 회수했다.
새 event를 과거 ordinal에 덮거나 같은 ID를 새 ordinal로 옮기지 않는다. 저장 실패/회전 실패,
미기록 이전 epoch, quota, 원격 clear/review는 성공 ACK를 주지 않는다.

SDK stdout의 interface-up, multicast SD550ms, 주입된 연결 종료·재연결 및 모든 ACK 이후 정상
종료 callback 경고도 원문 그대로 보존했다. 이를 queue 포화/기한 초과/정상 제어 실패의 허용으로
확장하지 않는다. 이 시험의 기준은 원래 diagnostics pilot의 전달·저장·실제 재가입·on/off 물리
동등성이다. Wall 제어 deadline이나 전체 SDK 경고 해소를 주장하지 않는다. Receiver ingress의
rejected/dropped는0, highwater≤8이며 publisher/replacement/capture는 정상 종료했다.

초기 실패도 `validation.tar.gz`에 보존했다. 최초 시험의 내부 PI expiry가 반드시 더 길다는 가정,
normal stop에서도 Run gate가 반드시 닫힌다는 가정, INIT3의 새 proof를 세지 않은 기대값을 수정했다.
발견된 정상 정지 provenance 연결 오류는 코드로 수정했다. GTest 같은 줄 EXPECT_THROW/중괄호,
일시적으로 잘못 배치한 qualification 변수, CLI positional 인자, 감사 스크립트 중복 keyword의
빌드/실행 실패 로그도 보존하며 최종 성공 결과와 구분한다.

## 자료와 재현

- `acceptance.json`: 분모·최종 판정·실행 binary SHA256.
- `sources.json`, `sources.tar.gz`: 기반 commit에 적용한 변경 파일의 원본과 hash.
- `validation.tar.gz`: Debug/ASan/UBSan/Python/tidy 원본 로그·XML·초기 실패와 CMake 설정.
- `recovery.tar.gz`: 원본 Event, Clear가 든 store, 논리 물리/owner CSV와 실행 결과.
- `someip-epoch.tar.gz`: 송수신 family·강제 종료 직후 복사본·SDK 원문 로그·namespace/config·pcap.
- `recovery-audit.json`, `epoch-delivery-audit.json`: 별도 decoder의 원문 감사와 변조 결과.
- `SHA256SUMS`: 이 디렉터리 산출물의 SHA256.

```sh
cmake --build build/m1-angle --target control_recovery_sil_test diagnostics_delivery_test
build/m1-angle/control_recovery_sil_test --gtest_filter='SupervisedRecoverySil.*'
# 고정 SDK 설치/build가 있는 환경에서 실행. 출력 경로는 새 경로여야 한다.
python3 tests/integration/someip/diagnostics_run.py build/new-epoch-delivery --cases epoch-restart
python3 tests/integration/diagnostics/audit_epoch_delivery.py \
  build/new-epoch-delivery/epoch-restart --output build/new-epoch-delivery/audit.json --mutations
```

다중 ECU의 ContextualOutbox/MergedCollector 전체 전환에는 늦은 이전 세션 event를 안전하게
수용할 순서 장벽이 남는다. 단일 epoch 무중단 회전·디스크 삭제/외부 보존·실제 매체 전원 차단은
후속이다. 새 감독 복구의 CARLA 주행 시험·전체 ODD·실제 학습 모델·wall/Target도 별도다.
[감독 계약](../../../interfaces/supervised-speed-proposal.md)과
[기록 이관 계약](../../../interfaces/epoch-retention.md)을 따른다.
