# Visual tags V2: fresh preparation, one 5-minute attempt

V1의30초 두 번은 원래 검사와 재생을 통과했다.5분 시도는 영상 서버 준비180초
초과로 제어 시작 전에 종료됐고 새 영상은0개다. 원래 실패를 보존한다.

같은 모듈·설정으로 자산 준비 직후5분 한 번만 실행한다. 짧은 두 시험은 V1의
완료 결과를 재사용하며 다시 실행하지 않는다. 영상/물리 시작 중 별도 검색·빌드·
압축 I/O를 겹치지 않는다. 결과는 실행 후 생성되는 원래 disposition을 따른다.

[사전 프로토콜](../../perception-visual-tags-v2-protocol.md),
[V1 기록](../m10_visual_tags_v1/README.md). 기한·입력시각·품질 기준을 바꾸지 않으며,
이 진단 하나로 전체 M10을 닫지 않는다.

## Recorded outcome

Final record: [PASS_EVIDENCE_AND_RESTORATION_ONLY](final-validation.json). This retains the original physical verdict; it does not close M10.

- `normal-300s-01`: FAIL / not accepted; [original disposition](normal-300s-01/disposition.json).
