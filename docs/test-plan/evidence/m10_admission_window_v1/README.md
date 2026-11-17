# M10 admission window V1 — 물리30초 PASS, 추가 검사기 오류로 중단

실제30초는 **6000구간·정상5830·INIT170·보호0**으로 원래 물리·영상 검사와 native
정확 재생을 통과했다. 최초 native 오류는 없고 CPU 최고75°C, 카메라9.33Hz,
영상 획득→결과 중앙값78.15ms·p95 85.71ms·100ms 초과2회다. 원본284장 검증과
미래 품질 제외20840개를 보존했다. owner GC는0회여서 GC 효과는 측정되지 않았다.

추가 admission 검사기가 서버 응답의`structured_state`와`wall_preview_reserve_ns`를
개별 receipt에도 요구하는 구현 오류로 FAIL을 냈다. 실제 설정은 binding/final_server에
2ms로 기록됐으며 receipt에는 원래 물리 필드만 있다. 사전 규칙대로 후속30초와5분은
NOT RUN이다. [원래 판정](normal-30s-01/disposition.json)과 동결본의 같은 FAIL 재현을 유지한다.

검사기를 실제 구조에 맞춰 수정했다. 시작·종료 서버 응답에서 설정을 모두 확인하고,
각 원래 receipt에서5ms 구간과 추가2ms까지 원래 expiry/30ms 입력 나이를 검사한다.
필드 누락·잘못된 설정·짧은 유효기간·불완전 수집은 계속 거절한다. 회귀4개와 원본6000개
수정 검사를 통과했다. [수정 코드·검증](auditor-correction/validation.json),
[별도 사후 결과](normal-30s-01/admission-window-corrected.json).
이는 원래 전체 sequence의 FAIL 판정을 바꾼 것이 아니다.

실행 후보는 수신 후 시각을 읽고 structured 경로의 추가 준비 여유를4→2ms로 줄였다.
최종 admission, 원래 expiry/source, HV30ms, 물리5ms/320steps, native2/4ms,
오래된 HV를 먼저 검사하는 순서는 유지한다. 기존 text 경로는4ms다.
모듈 SHA `29df236c28bdc92c29784f0ab7e087f3f18c8bf0187c84aa24a957b6d7e45e98`.
[사전 프로토콜](../../perception-admission-window-v1-protocol.md),
[계산·배치 동일성](code-equivalence.json). 준비 당시 소스1525개·Python516개·동결104개·
C++ admission27개와 빈 서버205.128초 검증을 통과했다. prepared/readiness의 NOT STARTED는
실행 전 기록이며 실제 결과는 [마감 검증](final-validation.json)을 따른다.

첫 실제 준비102.336초 후 인증 대기 기록과, 다시 준비29.768초 후 즉시 인증해 실행한
기록을 각각 보존했다. 공유 파일6개와 부스트100%는 OWNER_EXIT로 복원됐다.
[복원 확인](restoration-confirmation.json), [lease](power-lease.jsonl).
전체 run/raw는 로컬 보존하며 Git에는 bounded review를 남긴다. 외부 전체 백업은 아니다.
무손실 tar 압축과 해시 검증된 추출 중복 정리로 약2.68GB를 확보했다.
[저장 정리](storage-closeout.json).

후속 [V2](../m10_admission_window_v2/README.md)는 같은 실행 모듈로 검사기만 수정해
30초→30초→5분을 다시 검증한다.5분·GC·열 여유·native 인지·전체 장면·독립 품질·
각 Jetson 배포와 M10 종료는 OPEN이다.
