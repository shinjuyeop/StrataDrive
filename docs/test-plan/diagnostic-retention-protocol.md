# Diagnostic offline retention operations

유한 journal의 기본512-event/64-service-entry 용량과 초과 시 incomplete/clear 차단을 유지한다.
보존은 비활성 store를 독점 flock으로 확보하여 manifest/commit/journal/lock과 존재하는
incomplete/pending을 byte 그대로 보관하는 명시적 운영 작업이다. 살아 있는 writer가 있거나
unknown file·비공개 권한 위반·symlink/hardlink·committed CRC 손상이 있으면 거절한다.
Committed prefix 뒤의 미확정 suffix와 incomplete 표시는 보존하며 제거하지 않는다.

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
