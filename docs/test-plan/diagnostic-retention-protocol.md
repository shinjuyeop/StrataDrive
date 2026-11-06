# Diagnostic offline retention operations

새 선택형 [세션 경계 이관](../interfaces/epoch-retention.md)은 활성 창의 상태 이관·회수를 제공한다.
아래 단일-store archive/restore 계약과 형식은 유지하며 family 자동 삭제/통신 통합은 후속이다.

유한 journal의 기본512-event/64-service-entry 용량과 초과 시 incomplete/clear 차단을 유지한다.
보존은 비활성 store를 독점 flock으로 확보하여 manifest/commit/journal/lock과 존재하는
incomplete/pending을 byte 그대로 보관하는 명시적 운영 작업이다. 살아 있는 writer가 있거나
unknown file·비공개 권한 위반·symlink/hardlink·committed CRC 손상이 있으면 거절한다.
Committed prefix 뒤의 미확정 suffix와 incomplete/pending 표시는 보존하며 제거하지 않는다.
새 writer는 data 쓰기 전에 pending 의도를 영속화한다. pending이 남은 store는 suffix가
없어도 read-only/incomplete이며 archive/restore가 이를 해제하지 않는다.

Archive는 파일별 size/SHA256와 store ID·registry·commit ordinal·event/service 용량·미확정
suffix 수를 기록한다. 임시 파일 fsync→재독 검증→기존 경로를 덮어쓰지 않는 publish→부모
directory fsync를 거친다. 복원은 새0700 directory에만 하고 native writer가 필요로 하는
lock 파일을 마지막에 만든다. 원본 store와 발생 횟수/이력/identity를 바꾸지 않는다.
CRC/hash는 무결성 검사이며 인증 또는 native 의미 검증을 대신하지 않는다. 복원 후 실제
Recorder/서비스의 새 session·현재 정상 관측·명시적 clear 절차가 그대로 필요하다.

```sh
python3 tools/archive_diagnostics.py archive /private/inactive-store /private/archive-001.tar.gz
python3 tools/archive_diagnostics.py verify /private/archive-001.tar.gz
python3 tools/archive_diagnostics.py restore /private/archive-001.tar.gz /private/new-restore-directory
```

새 archive를 만들어도 active journal의 남은 용량은 늘지 않는다. 상한에 도달하기 전에
반드시 운영 검토하며, 이 도구는 active DTC를 삭제하거나 새 store로 자동 교체하지 않는다.
M9 finite-run 범위는 실제 canonical journal36개 보관/복원/독립 재감사와 파일시스템 부정
입력·busy·상충 목적지·suffix 보존 시험으로 검증한다. 장기간 매체 열화/전원 차단·자동
용량 회수/상태 이관/무제한 운영 정책은 별도 수용이다.

2026-11-06 [추가 검증](evidence/milestone-followup/README.md)은 archive sync2경계와
restore sync9경계의 오류, data suffix가 없는 pending의 원형 복원을 포함한다.
목적지의 lock은 이전 content 기록/fsync 이후에만 만들어진다. 마지막 publish/sync 실패는
이미 완전한 목적지가 존재할 수 있으므로 실패만 보고 삭제·덮어쓰지 않는다. Native 의미
검증/서비스 admission과 별개이며 실제 매체/전원 장애나 자동 상태 이관을 완료하지 않는다.
