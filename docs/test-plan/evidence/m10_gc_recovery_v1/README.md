# M10 GC recovery V1 — 모델 준비 실패, 제어 미시작

첫30초 시도는 **인지 모델 준비10초 제한 초과로 FAIL**이다. 물리 구간·native 시작·카메라
원본은 모두0이며, 후속30초와5분은 NOT RUN이다.300us preview의 GC 회복 효과는 측정하지
못했다. [원래 판정](sequence-disposition.json), [원본 분석](normal-30s-01/startup-analysis.json).

준비10.000121초 동안 첫 호출이 완료되지 않았다. 관측된 고장 페이지 수 증가가 가장 큰
스레드는20개 샘플 모두 D 상태였고, major fault370개 증가·CPU227.756ms·scheduler 대기
증가0을 기록했다. 같은 샘플의 GPU 사용률은0%였다. 디스크 페이지 읽기가 준비 지연에
기여한 근거지만 원본에는 함수 stack·파일 mapping이 없어 정확한 라이브러리는 식별하지 못했다.

worker 종료5초 제한 후에도 준비 작업이 busy였고 클라이언트는SIGSEGV(-11)로 종료됐다.
crash stack이 없어 직접 원인을 확정하지 않는다. 두 CARLA 서버는 모두 요청 종료130으로
끝났고 강제 종료는 없었다.8개 감사 결과의 원래 FAIL을 동결본에서 동일하게 재현했다.
제어 기록이 없어 native replay 성공을 주장하지 않는다.
[원본 보존·복원 검증](final-validation.json), [전체 시작 기록 묶음](normal-30s-01/bounded-review.json).

100%로 복원한 뒤의 [별도 I/O 진단](startup-io-diagnostics/README.md)은 원본 라이브러리의
첫 호출470.632ms·major fault17, 동일한 차가운 복사본의2925.138ms·1045를 기록했다.
복사본을 순차 읽고 해시 확인하는 데11.921초가 들었고, 이후 첫 호출352.733ms·major fault0을
기록했다. 총 시작 시간을 줄였다는 뜻이나70%·CARLA 동시 조건의 완전 재현은 아니다.

원본0장으로 미래 품질 제외는34241개다. 실행기 종료에 따라 부스트100%와 공유6파일을
[복원](restoration-confirmation.json)했다. 소스1592개 동결본
`b0056abdf8978ef0e127d8b7c8dc612a47129e4724d965e8d70e6eddc00982f6`와 실행 전
**Python529·동결117·C++29** 준비 근거를 그대로 보존한다. 원래 모듈은
`1feab7bc7a1c6788ec50fa507226ac01c99393d7b420912bba2e3cc1411a8eff`다.
예비250us 빌드 초과와 교체한 최초 동결본도 기존 [빌드 이력](build-attempts.json)·
[교체 이력](preparations/freeze-01-superseded/superseded.json)에 남아 있다.

후속 [Recovery V2](../m10_gc_recovery_v2/README.md)는 같은 모듈과300us preview를 유지하고
모델 시작 전에 고정 라이브러리 바이트만 읽는 준비를 추가한다. 추론·control warmup을 추가하지
않으며 원래 준비10초·후속100ms·물리5ms·HV30ms·시각·만료 우선 순서를 유지한다.
5분 HV 만료·worker 정리 실패 가능성·native 인지 수용·독립 품질·각 Jetson 배포·M10은 OPEN이다.

원본 archive를 보존하고 byte 검증한 추출본·진단용 라이브러리 복사본만 삭제해
1.938GB를 회수했다. [저장 정리](storage-closeout.json), [최종 체크섬](SHA256SUMS).
