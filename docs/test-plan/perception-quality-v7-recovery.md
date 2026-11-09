# V7 zero-frame startup 실패 뒤 별도 복구 실행

원래의 동일-budget 자동 재시도1회가 소진됐다. development-01/02는 각각 readiness와
RPC port의180s 제한을 실패했고210s 부근 강제 종료·exit-9·0frame이었다. 이 두 FAIL과
원래 orchestrator의 종료를 보존하며 성공 판정으로 바꾸지 않는다. 아직 평가 RGB나 새
모델 점수를 얻지 않았다. 따라서 후보/품질 기준을 변경하는 복구는 아니다.

두 시작과 겹친 과거11개 archive의 대용량 무결성 읽기가 모두 끝난 뒤 별도 복구 run03을
1회 수행한다. I/O 경합은 관측된 동시 작업이며 단독 원인이라고 단정하지 않는다. 원래
소스200개·plan·model·quality freeze·180/900/30s·exit130과 모든 가시성/숫자 gate를 유지한다.
기존 자동 재시도 범위 밖의 추가 실행이라는 편차를 이 문서와 recovery-before-launch.json에
기록한다. 이 실행도 실패하면 동일 자동 반복으로 감추지 않고 원인을 다시 조사한다.

이후 holdout은 원래 절차대로 개발 점수/지명을 봉인한 다음에만 수집한다. Server 시작 안정성·
wall20Hz·runtime/차량 승격은 이번 성공 여부와 별도로 미완료다.
