# Native4K 비동기 오류 응답 fixture V2

2026-11-11. [V1](perception-async-native-v1-protocol.md)의 정상·slow·blocked는 component
PASS다. 원래 `exception-01`은6초 동안 state600/camera120/control300 작업과120/120
예외·publication0을 관측했지만, 즉시 끝나는 예외 call 안에 다른 주기 job이 겹치지 않아
`no independent state/control work during inference`로 **FAIL**이다. 이 실행·소스·분모는 보존한다.

이 별도 V2는 실제 runtime/worker/가중치/입력/기한/판정 수치를 바꾸지 않는다. 오류 fixture에만
**각 호출25ms 대기 후 RuntimeError**를 사전에 정의한다.20ms consumer·10ms state 작업이
오류 응답 대기 중에도 실행되는지 V1의 동일 overlap 판정으로 확인한다. 즉시 예외의 단위 테스트와
원래 FAIL을 대체하지 않는다. 단일6초 재생을 별도 `exception-delayed-01`에 저장한다.

[V2 프로파일](../../profiles/perception-async-native-fault-v2.json)과
`probe_async_native_fault_v2.py`를 추가한503 source freeze를 **재생 전에** 생성한다.
V1의500개 source bytes는 그대로다. 초기화·cold/예외/모든 주기 작업·입력·완료를 보존하고,
동일한 V1 trace auditor로 재검사한다. Source/receipt100ms·출력0·모든 completion error와
실제 overlap 요구는 유지한다. 새 품질·실제 차량 제어·live camera/20Hz/Jetson 수용이 아니다.
