# M10 GC recovery V2 — 첫30초 물리 통과·감사 실행 오류

**첫30초 물리 검사는 PASS, 원래 전체 sequence는 FAIL이다.** 추가 라이브러리 감사기가
별도 Python 프로세스에서 `physical_ai`를 찾지 못해 결과 파일을 만들지 못했다.
동결본 재현에서도 같은 import 오류가 발생했고 실행기가 종료됐다. 두 번째30초와5분은
NOT RUN이다. 원래 실패와 누락된 감사 결과를 성공으로 덮어쓰지 않는다.
[원래 sequence](sequence-disposition.json), [오류와 사후 검증](normal-30s-01/posthoc-auditor/validation.json).

| 실제70% 첫30초 | 결과 |
| --- | --- |
| 물리 | 6000구간: 정상5838·INIT162·보호0 |
| Native | 최초 오류 없음; eligible150010·누락0·지연0 |
| 영상 | 원본281장·추론277회·약9.233Hz |
| 원본 획득→결과 | 중앙80.387ms·p95 87.149ms·최대131.025ms·100ms 초과1회 |
| CPU | 관측 최고76°C·열 제한 증가0 |
| GC | 본 GC0회;300us 회복 효과 미측정 |

[물리 감사](normal-30s-01/audit.json), [부하 분석](normal-30s-01/analysis.json),
[기한 원본 집계](normal-30s-01/native-gap-analysis.json).
유한 시나리오는 초반 가감속 뒤 정지 유지한다. 연속 주행이나 native 인지 수용은 아니다.

V1에서 막힌 모델 준비는 이번 실제 시험에서 통과했다. Owner 라이브러리 읽기1.551초,
모델 호출495.830 /39.293 /35.841ms였고 worker는 정상 종료했다. Renderer 읽기도1.552초다.
[두 경로 원본 준비 기록](normal-30s-01/startup-summary.json). 이 한 번의 통과가 차가운 캐시나
메모리 압박에서 영구 해결을 보장하지 않는다.12파일·1,909,074,752byte 읽기30초와
원래 모델 준비10초·후속100ms·물리5ms·HV30ms 제한은 그대로다.

원본 동결 감사기에 그 동결본의 root 경로만 제공한 결과와, bootstrap을 수정한 현재
감사기의 독립 실행 결과가 완전히 같다. 모두 같은6000개 기록에서
`PASS_GC_RECOVERY_PREFETCH_INTEGRITY`다. 이는 **사후 검사기 수리 검증**이며,
기존 sequence FAIL이나 미실행된 후속 시험을 PASS로 바꾸지 않는다.
원래7개 추가 감사 재현·물리 exact replay·최초 오류 재생·전체 archive 검사는 통과했다.

원래537개 Python·125개 동결 검사와 재사용 C++29, 실제 모델 준비 경로 검증은
[준비 기록](prepared.json)에 남긴다. 원본1611파일 동결 SHA256은
`388000a8b327746e3edca541df3c561a2c737fcd5f452580ea2428b54b1b9174`다.
[사전 프로토콜](../../perception-gc-recovery-v2-protocol.md)의 조건과 판정은 변경하지 않는다.

실행기 종료로70→100%가 복원됐고 공유6파일도 원래 해시와 일치한다.
[복원](restoration-confirmation.json), [최종 근거 검사](final-validation.json).
원본 영상281장은 모두 보존하며 미래 품질 제외는34522개다. 전체 run/source/raw archive는
로컬에 유지하고 [제한된 검토 묶음](normal-30s-01/bounded-review.json)을 별도 제공한다.
무손실 raw 압축으로2.365GB, 해시 대조한 중복 추출본·spool 삭제로4.774GB를 회수했다.
[정리 근거](storage-closeout.json), [체크섬](SHA256SUMS).

다음 [Recovery V3](../m10_gc_recovery_v3/README.md)는 감사기 import 경로만 수정하고,
저장소 밖·PYTHONPATH 없는 subprocess 검사와 동결본 검사를 추가한다.
5분 안정성·전체 장면·native 인지·독립 품질·각 Jetson 배포·M10 종료는 OPEN이다.
