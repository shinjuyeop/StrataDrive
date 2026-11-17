# M10 owner GC V1 — 영상 서버 기동 실패, 제어 미시작

2026-11-17 실제 실행은 영상 서버가 기존 180초 준비 제한을 넘겨 실패했다.
물리 owner·모델 준비·카메라·native 제어는 시작하지 않았다. 영상과 제어 구간은
모두 0이며, GC 개선 효과를 측정하지 못했다. 다음 30초와 5분은 NOT RUN이다.
[원래 판정](sequence-disposition.json), [기동 분석](normal-30s-01/startup-analysis.json),
[증거 검증](final-validation.json).

종료 진단에서 메인 스레드가 `D` 상태, `folio_wait_bit_common`, read syscall 안에 있었다.
기동 중 관측된 메인 상태 421개 중 323개가 디스크 대기였고 major fault 최댓값은
2531이었다. 엔진의 캐시 읽기 측정은 5.99MB/s로, 이전 따뜻한 실행의 2993.01MB/s와
차이가 컸다. 통제된 디스크 벤치마크는 아니며, 차가운 자산 I/O가 유력한 기동 원인이다.
CPU 최고는 66°C였다. 30초 종료 제한 뒤 renderer를 강제 종료한 사실도 보존한다.

첫 오류에서 실행을 중단했고, 공유 파일 6개는 원본으로 복원했다. 부스트 상한은 실행기
종료에 따라 100%로 복원됐다. 원본 archive 재검사는 FAIL 판정·소스 1501개·영상 0개·
미래 품질 제외 19991개를 그대로 확인했다. 제어 기록이 없어 제어 replay는 수행할 수 없다.
원본 run과 host 시계열은 로컬에, 설정·기동·종료 진단은
`normal-30s-01/retained-metadata.tar.gz`에 보관한다.
[복원 확인](restoration-confirmation.json).

이전 PID 2388345의 단순 대기 만료와 이번 실제 기동 실패는 별개다.
[대기 만료 기록](startup-timeout-01/recovery.json),
[최초 시작 도구](launcher-validation.json)를 보존한다. `prepared.json`과
Python 508개·동결 96개 검사는 실제 실행 전 준비 기록이다.

다음 [GC V2](../m10_owner_gc_v2/README.md)는 매번 별도 빈 영상 서버에서 자산을 준비한 뒤
같은 GC 후보·같은 제어 기준을 시험한다. 본시험의 180초 기동 제한은 그대로다.
원래 HV 만료·후반 native 누락 18건·최고 90°C·각 Jetson 배포·M10 전체는 OPEN이다.
