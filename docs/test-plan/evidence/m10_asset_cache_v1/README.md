# Observed asset cache V1

원래 파일 읽기 기록으로 고른 약7.85GB만 NVMe에 임시 배치하는 단일5분 후보다.
원본 파일은 삭제하지 않고 같은 위치에 보존하며, 종료 후 원래 inode와 내용으로
복원한다. 물리·제어·GC·센서·모델 및 기한은 packaged renderer V1과 같다.

[사전 프로토콜](../../perception-asset-cache-v1-protocol.md).
저장 위치 검증과 원래 물리 판정, 전체 M10 종료를 각각 구분한다.

## Recorded outcome

Final record: [PASS_EVIDENCE_AND_RESTORATION_ONLY](final-validation.json). This retains the original physical verdict; it does not close M10.

- `normal-300s-01`: FAIL / not accepted; [original disposition](normal-300s-01/disposition.json).
