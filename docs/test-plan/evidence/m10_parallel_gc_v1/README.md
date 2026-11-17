# M10 parallel GC V1 — 동일 모듈에서 기본 병렬 GC 비교

[직전 V2](../m10_admission_window_v2/README.md)는 30초 두 번을 통과했지만 5분 시험의
첫 직렬 GC 38.24ms 안에서 HV30ms를 넘겼다. 네 번 모두 32.55–38.62ms였고 거의 전부
실제 thread CPU 시간이었다. 원래 실패·raw·정확 재생은 그대로 보존한다.

이 후보는 **owner 직렬 GC 옵션 하나만 제거**한다. 엔진 기본 parallel=1을 실제
GC readback으로 확인하고 주기는 원래 61.1초를 유지한다. renderer GC 설정은 같고
GC 주기를 늘리거나 강제 실행·억제하지 않는다. 기존 검사기는 직렬·병렬 정책 모두를
검사한다. 병렬 journal의 통과 및 잘못된 정책 거절 회귀도 추가했다.

실행 모듈은 `29df236c28bdc92c29784f0ab7e087f3f18c8bf0187c84aa24a957b6d7e45e98`를
재사용한다. 수신 후 시각·structured 추가 여유2ms, 원래 최종 admission·전체5ms 물리·
HV30ms·native2/4ms·센서 원래 시각·이전 held 입력 만료 우선 순서는 바꾸지 않는다.
기존 병렬 조건의17–22ms 정지는 당시 GC 상관관계였으므로 이번 직접 측정이 필요하다.
[사전 프로토콜](../../perception-parallel-gc-v1-protocol.md).

Python518개·동결106개·소스1546개, 원래27개 C++ admission 검사 재사용,
모듈119입력·18생성 파일과 외부 runtime 동일성을 확인했다.
[준비 결과](prepared.json), [동결 검사](frozen-tests.json), [파일 검증](readiness-validation.json). 동일 모듈의 V1 빈 서버 검증과 이후 실제 기동·종료 기록을 재사용하며,
새로운 별도 빈 서버 검증을 수행했다고 주장하지 않는다. 새 본시험은 **NOT STARTED**다.

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

현재 시작 도구는 이 후보를 선택한다. 실행마다 자산을 준비한 뒤 sudo 인증을 받으며,
그 후 새 owner PID에70% 임시 상한을 연결한다. `APPLIED`가 실제 적용 표시다.
30초→30초→5분을 검사하며 첫 실패 후 다음 실행을 중단한다. 실행기 종료 또는
최대30분 뒤 원래100%로 복원한다. 자산 준비 후5분 초과·이전 본시험 존재·동결 변경은
거절한다. root helper·PID/UID/start tick 결합·복원 조건은 이전과 같다.

2K2560×1536·D-FINE-M960 CUDA·카메라10Hz·렌더러20Hz/MaxFPS60,
기존 CPU/FIFO 배치·준비600초·기동180초·종료30초·전체 원본 보존을 유지한다.
실측 중 별도 빌드·검사·압축을 실행하지 않는다. 미래 품질 제외는 V2의24195개에서
이어간다.5분 안정성·냉각 여유·native 인지 수용·전체 장면·독립 품질·각 Jetson 배포와
M10 종료는 OPEN이다.
