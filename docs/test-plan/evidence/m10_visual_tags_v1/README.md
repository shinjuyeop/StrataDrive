# M10 owner visual tags V1

물리 서버의 렌더링 전용 태그 생성을 생략하고 owner4/image2로 원래30초→30초→5분
시험을 진행한다. 현재 판정은 실행 뒤 생성되는 `sequence-disposition.json`을 따른다.
시험 전 준비와 source 동결은 실제 물리 통과가 아니다.

[진단 근거](../m10_gc_feedback_v1/README.md)에서 동일 지도 상태·라벨과 GC 단계의
소폭 단축을 확인했다. Recovery V3의 물리/native object,5ms·HV30ms·2/4ms 기한,
ECU 주기·100ms 인지 기한·원래 시각·보유 입력 만료 순서는 그대로다. renderer에는
옵션을 넣지 않는다. 양쪽 모델의2코어 준비 검증은 owner4 후보에서 재사용했으며,
새 검증인 것으로 세지 않는다. 매 실행의 자산 준비는 새로 한다.

새 모듈 SHA: `bdfb14908db58cd49e2abefcc59f6e5c213faf75e0a7577d40e66b08410bd980`.
관련 Python37개, 동결본137개와8개 감사기의 독립 실행 경로 검사를 통과했다.
source1662개 동결본 SHA:
`c84dbdbb0d18d77d77f08b2d11b760109c35dc9a5f6bc617f406af6286b9dcd6`.

[사전 프로토콜](../../perception-visual-tags-v1-protocol.md), [준비 기록](prepared.json),
[동결본 검사](frozen-tests.json), [실행·재감사 연결 검사](runner-wiring.json).
설치된 제한 전용 helper가70% 적용과100% 복원을 자동 수행한다.
첫 원래 실패에 후속 실행을 중단하고 실패 원본을 보존한다.

이 유한 시나리오는 초반 가감속 뒤 정지 유지한다. 전체 장면·typed native 인지 연결·
새 독립 품질·M10 종료는 별도이며, 각 Jetson의 배포는 M12 범위다.

## Recorded outcome

Final record: [PASS_EVIDENCE_AND_RESTORATION_ONLY](final-validation.json). This retains the original physical verdict; it does not close M10.

- `normal-30s-01`: PASS finite diagnostic; [original disposition](normal-30s-01/disposition.json).
- `normal-30s-02`: PASS finite diagnostic; [original disposition](normal-30s-02/disposition.json).
- `normal-300s-01`: FAIL / not accepted; [original disposition](normal-300s-01/disposition.json).
