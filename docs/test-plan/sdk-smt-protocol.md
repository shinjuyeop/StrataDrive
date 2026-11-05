# SDK 동일 물리 코어의 SMT 사용 후보

2026-11-05, allocation-release 후보의 후속 실행 환경 비교다. 해당 후보의 원래
분모는 기능12/12·서비스27/30이며,4441개 명령의 release 심사/실행 불일치는0이다.
TSan3건은 계속 실패다. 정상-r3에서 SDK 권한 수신 대기와 순차 Front→Rear 전달이
겹쳐 Rear 수신이 기존 expiry를282079ns, 거절 판정이289689ns 넘긴 사례를 보존한다.

기존 SDK I/O2는 ECU별 하나의 논리 CPU4/5/6을 공유한다. 이 후보는 스레드 수와
SCHED_OTHER를 유지하면서 동일 물리 코어의 두 SMT sibling을 허용한다. 이 Host는
Central4/12, Front5/13, Rear6/14다. Owner1/2/7, plant3, auxiliary8의 물리 코어와
분리한다. 추가 물리 코어 또는 독립 성능 두 배라고 해석하지 않는다.
Topological package/core와 실제 모든 thread affinity/policy를 별도로 대조한다.
Sibling이 없거나 허용되지 않으면 실행 전 거절하고 다른 코어로 대체하지 않는다.

`--sdk-smt`는 명시적 후보 옵션이다. 기본 profile은 바꾸지 않는다. SDK 원본,
실행 파일, control period, original source/expiry, timeout, ACK/SDK 오류 판정은
직전 후보 그대로다. Launcher와 감사기 변경을 단위/negative 검사한 뒤 소스 hash를
고정하고 Normal6·ASan6·TSan18의 서비스30건을 한 번씩 실행한다. 모든 native runtime
뒤 독립 감사한다. 이전 실패와 분모를 유지하며 성공까지 재시도하지 않는다.

이 후보의 유한 표본은 해당 Host profile의 관측이며 임의 부하·Target의 실시간 상한,
M9의 다른 구현·운영·이해 review 수용을 대신하지 않는다.
