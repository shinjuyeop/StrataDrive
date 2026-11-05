# 지연된 배분 작업의 현재 release 검증

2026-11-05, base `da19483`, owner-input-phase 후보 다음의 별도 후보.
선행 후보는 기능12/12, 최초 서비스26/30이었다. StopRequest loss3건은 실제
NormalStop SD-1105 검출을 allocator SD-1002만 인정하던 감사기가 거절했다.
원래 source/expiry, Braking 진입, RequestLost 시각, Coordinator Stop fault의
동일 원인 연결과8개 mutation을 확인한 재감사에서29/30이다. 원본 실패는 유지한다.
남은 TSan normal은 Epoch1의 의도된 Central 종료 전에 발생한 실제 보호다.

그 실행의 allocator는 늦어진 작업을 이전 nominal release로 심사한 뒤 현재
release를 완료로 기록했다. 허용된 command의 원래 expiry가 다음 nominal release
보다 앞서게 됐다. 이 후보는 external release의 심사와 완료 기록을 같은 현재
enable grid에 맞춘다. Port callback 도중 다음 slot으로 넘어가면 재심사하도록
이번 실행을 보류한다. 입력 issuer도 완료를 기다리는 allocator와 독립된 기존
10ms grid에서 실제 새 root를 발행한다. 원래 source/expiry와18ms support는 유지한다.

설정 객체의 기존 불필요한 생성자 복사는 const reference 전달로 제거한다.
두 회귀 시험은 기존 구현에서 실패하고 새 구현에서 통과해야 한다. 전체 Debug,
ASan/UBSan 및 관련 TSan·정적 검사 후 세 native binary와 source를 고정한다.
기능 Normal/ASan12건 및 서비스 Normal6/ASan6/TSan18건을 순서대로 실행한다.
서비스 fault 종류, jitter 사례, 실행 정책과 SDK I/O2는 선행 protocol과 같다.
Native 실행 중 build/분석/다른 native를 겹치지 않고 모든 runtime 후 감사한다.
성공까지 반복하지 않으며 실패와 원본 분모, 사후 감사 변경을 보존한다.

Host의 고정 cohort 통과와 임의 부하에서의 실시간 보장은 다르다. Native4ms,
Target, CARLA subinterval, trusted Clock recovery, bootstrap incident, 보존 및
개인 이해 review의 별도 수용 조건을 이 결과로 닫지 않는다.
