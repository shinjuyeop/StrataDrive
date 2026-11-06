# 세션 경계 진단 기록 이관

`EpochRecorder`는 Linux 로컬 단일 writer의 선택형 저장기다. 기존 `FileJournal`과
SOME/IP Outbox/Inbox의 stream ID·ordinal·ACK 계약은 변경하지 않는다. 기본 통신 런타임은
계속 기존 유한 저장기를 사용한다. 이 문서는 신규 저장기의 적용 가능한 범위를 정의한다.

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

## 남는 경계

회수하는 것은 **활성 메모리·event/service 창**이다. 원본 파일을 자동 삭제해 디스크를 비우지
않는다. 기본 segment 상한1024, 설정 가능 최대10000에서 증거를 보존하며 Capacity로 실패한다.
이력 조회/재시작 비용은 보관량에 비례하고 실시간 작업이 아니다. 기존 단일-store archive 도구는
family/checkpoint 형식을 받지 않는다. Family 보관·외부 이관/삭제 정책, 단일 장시간 epoch 중
무중단 회전, 통신 ordinal을 포함한 운영 통합과 실제 전원/매체 검증은 후속이다.

[구현·시험 근거](../test-plan/evidence/remaining-improvements/README.md)를 따른다.
