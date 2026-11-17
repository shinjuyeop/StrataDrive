# M10 admission window V1 — 수신 후 시각과 추가 준비 여유

[GC V2](../m10_owner_gc_v2/README.md)는 첫30초 PASS, 두 번째30초는28.053초 HV 만료로
실패했다. 두 실행에 GC가 없어 이번 실패는 GC 정지로 설명되지 않는다. 원래 native와
gate를 재생해 명령의 전체 구간 유효성 대기와 수신 전/후 시각 순서 문제를 분리했다.

후보는 수신 후 현재 시각을 읽고, 기존 opt-in structured 경로의 추가 준비 여유만
4→2ms로 줄인다. 최종 admission 본문, 명령 expiry, 원래 source, HV30ms,
물리5ms/320steps, native2/4ms, 오래된 HV를 먼저 검사하는 순서는 유지한다.
기존 text 경로의 여유는4ms다. 모든 receipt에서 실제2ms 설정과 원래 전체 구간
유효성을 추가 감사한다. [사전 프로토콜](../../perception-admission-window-v1-protocol.md).

기존 두30초의 admission→적용 최대는0.426/0.400ms였다. 적용 이후 물리까지 포함한
획득 최대는2.468/3.748ms로, **2ms는 추가 준비 여유**이며 전체 처리 시간의 상한이 아니다.
기존 입력에 대한50us 간격 재생에서 다음 예정 시각 뒤0.5ms 폭의 더 이른 허용 구간을
확인했다. 새 동작의 장기 성공 여부는 실제 실행으로만 판정한다.

모듈 SHA `29df236c28bdc92c29784f0ab7e087f3f18c8bf0187c84aa24a957b6d7e45e98`.
[원래 계산·배치 동일성](code-equivalence.json), C++ admission27개와 Python516개 통과.
소스1525개·동결104개 검사를 통과했고 빈 서버 자산 준비205.128초·정상 종료·원본 파일6개
복원을 확인했다. [prepared.json](prepared.json),
[readiness-validation.json](readiness-validation.json). 본시험은 **NOT STARTED**다.

준비 완료 후 실행 명령:

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

도구 이름은 유지하되 현재 선언된 이 후보를 선택한다. 매 실행마다 빈 영상 서버를
준비하고 sudo 인증 후 새 PID로70% 임시 상한을 연결한다. 준비 후5분 초과·이전 실행
존재·동결 파일 변경은 거절한다.30초→30초→5분, 첫 실패 중단, 종료/최대30분 후100%
복원과 공유 파일6개 복원이 적용된다. 기존 시험에 덮어쓰거나 자동 재시도하지 않는다.

2K/D-FINE-M960·카메라10Hz·렌더러20Hz·GC직렬/61.1초는 유지하고 미래 품질 제외는
20556개에서 이어간다. GC 효과·5분 안정성·후반 native 누락·열 여유·인지 수용·전체 장면·
독립 품질·각 Jetson 배포와 M10 종료는 OPEN이다.
