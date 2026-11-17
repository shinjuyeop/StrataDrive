# M10 admission window V2 — 실제 기록 구조에 맞춘 검사기

[V1](../m10_admission_window_v1/README.md)의 원래30초 물리 시험은 오류·보호 전환 없이
통과했지만, 추가 검사기가 receipt에 없는 서버 설정 필드를 요구해 후속 시험이 중단됐다.
원래 FAIL과 NOT RUN은 보존하고 수정 검사 결과는 별도로 기록한다.

수정본은 binding/final_server에서 설정을 확인하고, 원래 receipt에서는5ms 구간과
추가2ms 준비 여유를 원래 expiry/30ms 입력 나이로 검사한다. 실제 분리 구조와 누락·변경·
짧은 유효기간·수집 누락 회귀4개, 원본6000개에 대한 수정 검사와 동결본 재검증을 통과했다.
[동결본의 기존 기록 검사](prior-capture-frozen-audit.json),
[사전 프로토콜](../../perception-admission-window-v2-protocol.md).

실행 C++·제어·물리·모델은 바뀌지 않는다. 모듈
`29df236c28bdc92c29784f0ab7e087f3f18c8bf0187c84aa24a957b6d7e45e98`와 기존27개 C++
admission 검사, 빈 서버 및 실제30초 기동·종료 검증을 재사용한다. Python518개,
동결106개·소스1535개를 확인했다. [준비 결과](prepared.json),
[파일 검증](readiness-validation.json). 새로운 본시험은 **NOT STARTED**다.

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

현재 시작 도구는 V2를 선택한다. 자산 준비 후 sudo 비밀번호까지 입력하면 새 PID로
70% 임시 상한을 연결하고30초→30초→5분을 검사한다. 첫 실패에 중단하고 종료 또는
최대30분 뒤100%로 복원한다. 준비 후5분 초과·이전 시도 존재·동결 변경은 거절한다.
매 실행의 자산 준비는 유지하며, 새로운 별도 사전 빈 서버 검증을 수행했다고 주장하지 않는다.

HV30ms·물리5ms·native2/4ms,2K/D-FINE-M960·카메라10Hz·렌더러20Hz,
owner serial GC/61.1초와 기존 배치·종료·원본 보존 조건은 같다. 미래 품질 제외는20840개에서
이어간다.5분 안정성·GC·후반 native 누락·열 여유·인지 수용·전체 장면·독립 품질·각 Jetson
배포와 M10 종료는 OPEN이다.
