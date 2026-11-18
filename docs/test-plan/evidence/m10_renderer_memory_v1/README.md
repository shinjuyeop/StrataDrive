# Renderer lifecycle and memory smoke

배포본은 기본 Town10HD 지도를 읽어 초기 시도들을 중단했다. SDK로 Town03_Opt를
명시적으로 읽은 뒤 같은 환경·3개 actor 속성과2K 영상23개를 확인했지만 첫 종료는
30초 초과로 실패했다. 촬영 종료 뒤 동기 대기를 해제한 후속 시도는23개 영상과
종료130을 기록했다. 모든 실패·성공·당시 소스와 원본을 보존했다.

Editor 비교는 준비180초 및 종료30초 제한에 실패했다. 따라서 같은 조건의 성공한
메모리 비교나 통합 제어 통과로 해석하지 않는다. 기존 통합 시험에는 최소 약8.2GB
가용 RAM이 기록돼 RAM 고갈도 입증되지 않았다.

[결과](results.json) · [파일 식별](files.json) · [프로토콜](../../perception-renderer-memory-protocol.md).
원본 영상은 로컬 raw-renderer-smokes.tar, 그 외 기록은 diagnostic-records.tar.gz에
보존한다. 모든 새 RGB는 미래 독립 품질 평가에서 제외한다.
