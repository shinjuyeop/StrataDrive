# 세션 경계 진단 기록 이관

`EpochRecorder`는 Linux 로컬 단일 writer의 선택형 저장기다. 기존 `FileJournal`과
SOME/IP Outbox/Inbox의 stream ID·ordinal·ACK 계약은 유지한다. Outbox/Inbox가 family를
선택할 수 있고 전용 SOME/IP `epoch-restart` 시험에 연결했다. ContextualOutbox도 family를
선택할 수 있다. 고정 송신원 집합의 `EpochMergedCollector`와 전용 `epoch-merge-restart` 시험을
추가했다. 기본 다중 ECU 런타임의 기존 MergedCollector는 유한 저장기를 사용한다.

## 이관 조건과 보존

기본 활성 창은 events512/records64/occurrences128/service64다. 현재 segment의 영속 entry가
256개 이상이면 **실제로 수신한 더 새로운 Session 또는 Attempt**에서 다음 segment로 옮긴다.
저장기가 운행 epoch나 세션을 만들어 내지 않는다. 한 세션 안에서 기존 한도를 넘으면 원래처럼
incomplete로 남는다. 기록 때문에 제어 owner를 정지하거나 재시작하지 않는다.

Checkpoint는 DTC key·generation·revision·count·최초/최종 occurrence와 원본 event ID·검출
시각·cleared 상태를 이어받는다. 미해제 DTC마다 마지막 Fault 원문을 유지한다. 현재 조건과
latch는 Unknown으로 시작하며 pass 권한·과거 service approval을 새 세션에 옮기지 않는다.
새 세션에서 해당 마지막 occurrence에 대한 fresh proof→Passed→명시적 clear가 필요하다.
이관 전 이미 해제된 기록은 해제 상태를 유지하고 재고장은 다음 generation을 만든다.

누락·unmapped 또는 미해제 continuity incident를 checkpoint로 세탁하지 않는다. 이 경우
이관은 보류하고 기존 유한 창의 실패 규칙을 적용한다. 이전 epoch의 미기록 event를 뒤늦게
신규 event로 수용하지 않는다. 이미 기록된 동일 event/clear/review의 재전송은 보관된 원문과
비교해 durable Duplicate로 응답한다. 같은 ID의 다른 내용은 Conflict/incomplete다.

## 저장·복원

Root는 private0700, 파일은0600이고 root lifetime flock을 잡는다. `manifest`에 정책과
store identity를 고정한다. `current`는 활성 segment와 이전 segment 누적 watermark다.
번호별 directory에는 기존 canonical FileJournal과 두 번째부터 `checkpoint`가 있다.

1. Root `pending`에 다음 segment/current 의도를 쓰고 file·directory fsync한다.
2. 새 directory에 FileJournal과 checkpoint를 영속화한다.
3. 이관을 일으킨 실제 새 Session/Attempt를 successor에 commit한다.
4. Root pending을 current로 rename하고 directory fsync 후 성공을 알린다.

중단 시 pending·부분 successor·원본을 지우거나 자동 수리하지 않는다. Root pending 또는
incomplete가 있으면 추가 정상 기록/새 clear가 차단된다. Rename 이후 ACK 유실은 successor가
보일 수 있다. 이때 기존 durable receipt와 새로운 서비스 요청을 구분한다. 마지막 directory
sync 실패도 successor에 기록하며, 이미 보관된 predecessor에 실패 표식을 덧붙이지 않는다.

재기동은 모든 predecessor의 CRC·identity·정책·원본 transaction을 검증하고, 그 projection에서
계산한 checkpoint와 다음 segment의 checkpoint bytes를 비교한다. 누락·손상 이력을 건너뛰지 않는다.
CRC는 오류 검출이며 인증이 아니다. 모든 writer는 family의 독점 잠금 계약을 따라야 한다.

## 실행

```sh
cmake --build build/m1-angle --target diagnostic_epoch_store
build/m1-angle/diagnostic_epoch_store init /private/new-family 10000
build/m1-angle/diagnostic_epoch_store append /private/new-family < canonical-entries.hex
build/m1-angle/diagnostic_epoch_store inspect /private/new-family
```

입력은 기존 `diagnostics::encode(Entry)`의 소문자 hex 한 줄이다. 모델 출력이나 임의 JSON을
진단 이벤트로 변환하는 도구가 아니다. Native admission/service adapter가 만든 원본을 사용한다.
출력 receipt의 durable/watermark와 프로세스 종료 코드를 함께 확인한다. Inspect도 독점 writer
잠금으로 재개방하며, 발견된 pending은 incomplete로 보존할 수 있다.

## 전송과 재전송

Family의 root store ID는 stream ID로 고정하고 ordinal은 모든 segment의 committed entry 누적값이다.
물리 segment의 store ID를 wire stream ID로 사용하지 않는다. Checkpoint는 전송 entry가 아니다.
원본 Event와 ACK packet 형식은 그대로이며 registry4를 명시적으로 지원한다. Clear/ContinuityReview는
여전히 원격 Event packet이 아니고, 과거 segment에 이 transaction이 있는 family도 전송기로 거절한다.

`Outbox(EpochRecorder&)`와 `Inbox(EpochRecorder&)`는 공통 DeliveryStore를 통해 원본 event-only
기록을 사용한다. Sender restart는 ordinal1부터 재전송한다. Inbox는 현재 cumulative watermark보다
앞선 순번을 보류하고, 과거 순번은 보관 원문 전체가 같을 때만 Duplicate ACK를 준다. 같은 ID를 새
순번으로 옮기거나 payload를 바꾸면 sticky incomplete다. Segment 회전 후에도 event 수를 무한 vector로
평탄화하지 않는다. Segment별 끝 순번과 한 개의 cold reader만 보존한다. Cold replay와 live append가
같은 독점 잠금 아래 reader를 공유한다.

ACK는 successor와 family current의 fsync 완료 뒤에만 반환한다. 실패·미완료 의도·보관 한도 초과는
ACK를 주지 않는다. Source/replica의 회전 threshold가 달라도 원본 순번과 DTC 집계는 같다.
[검증](../test-plan/evidence/supervised-recovery-delivery/README.md)은 40세션의 독립 threshold와
실제 SOME/IP에서 새 세션 영속화 직후의 SIGKILL·재시작·유실 ACK 재전송을 포함한다.

## 여러 송신원의 세션 순서

`EpochMergedCollector`는 사전에 지정한 최대32개 replica family를 받는다. Root의
`merge-sources`에 정렬된 stream ID 집합을 CRC·fsync와 함께 저장한다. 기존 history에 목록이
없거나 재시작 때 목록을 변경하면 거절한다. 수신 traffic이나 timeout으로 참여자를 제외하지 않는다.
모든 event는 replica 경로를 거치며 Central의 직접 merged append도 허용하지 않는다.

각 stream은 단조 증가하는 epoch의 원본 Session 또는 Attempt로 다음 epoch를 시작한다.
Collector는 stream당 미병합 entry 한 개만 영속화하고, 현재 epoch의 원본을 먼저 병합한다.
모든 stream의 다음 entry가 더 새로운 경계에 도달해야 가장 작은 다음 epoch로 이동한다.
같은 epoch의 Attempt를 Session보다 먼저 처리하므로 Central의 준비 실패 epoch를 건너뛰어
가짜 global Session을 만들 필요가 없다. 뒤늦은 미기록 과거 epoch는 Conflict/incomplete다.

ACK는 replica와 merged 양쪽에 원문이 영속화된 뒤에만 반환한다. 경계에서 기다리는 replica
entry에는 NotReady/no ACK를 반환하며 후속 순번도 받지 않는다. 다음 retry에서 ACK를 받을 수 있다.
프로세스 재시작은 replica별 ordinal1부터 같은 장벽으로 재조정한다. 이미 병합된 원문은 durable
Duplicate이며, replica에만 남은 원문은 빠진 순서대로 병합한다. Projection은 Unknown으로 시작하고
재전송으로 DTC count·generation·clear를 바꾸지 않는다. 원본 목록을 무한 vector로 복사하지 않는다.

Central의 원본 Session 배포는 이 ACK 대기와 독립적이어야 한다. ContextualOutbox는 실제
RunLease evidence로 Session을 수락하고 이전 pending event를 먼저 기록한다. Context 배포까지
merged ACK에 종속시키면 Central Attempt와 원격 Session이 서로 기다리는 교착이 생긴다.

[검증 근거](../test-plan/evidence/epoch-merge/README.md)는 서로 다른 회전 threshold·12세션
reconciliation·목록 누락·저장 실패·한도를 검사한다. 실제 SOME/IP 시험은 원래 native
Central/Front/Rear 관측을 고정한 세 stream의 전송이다. Front의 이전 tail을 지연하고 새 경계의
ACK를 보류한 채 수집기를 SIGKILL한 뒤 원본을 끝까지 병합한다. 제어 실행은 논리 시간이고,
3-process native 제어 런타임의 live family 전환이나 wall 수용을 의미하지 않는다.

```sh
cmake --build build/m5-someip-normal/project --target someip_epoch_merge_live
python3 tests/integration/someip/diagnostics_run.py build/new-merge-run --cases epoch-merge-restart
python3 tests/integration/diagnostics/audit_epoch_merge.py build/new-merge-run/epoch-merge-restart --output build/new-merge-audit.json --mutations
```

새 시험기의 diagnostic retry는 ACK가 없으면100→200→400→800→1000ms로 backoff하고,
Accepted ACK에100ms로 돌아온다. SD availability만으로 TCP 재접속 완료를 판단하지 않는다.
SDK queue8·원래 제어 기한은 그대로이며 overflow는 실패다. 기존 native 런타임의 retry 정책을
일괄 변경한 것은 아니다.

## 남는 경계

회수하는 것은 **활성 메모리·event/service 창**이다. 원본 파일을 자동 삭제해 디스크를 비우지
않는다. 기본 segment 상한1024, 설정 가능 최대10000에서 증거를 보존하며 Capacity로 실패한다.
이력 조회/재시작 비용은 보관량에 비례하고 실시간 작업이 아니다. 기존 단일-store archive 도구는
family/checkpoint 형식을 받지 않는다. Family 보관·외부 이관/삭제 정책, 단일 장시간 epoch 중
무중단 회전과 실제 전원/매체 검증은 후속이다. 새 장벽은 고정 membership 전용이다. 기존 native
런타임의18개 이전/후속 producer slot을 그대로 참여자로 넣으면 아직 시작하지 않은 송신원까지
기다리게 된다. 실제 producer 교체·이전 prefix 종료 증거·Central local spool/context 배포를 연결한
동적 membership과 live 런타임 전환은 별도로 구현·검증해야 한다. 이를 timeout으로 우회하지 않는다.

[구현·시험 근거](../test-plan/evidence/remaining-improvements/README.md)를 따른다.
