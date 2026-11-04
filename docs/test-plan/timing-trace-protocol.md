# SOME/IP 동시 계측 슬롯과 SDK 직접 계측 검증

2026-11-04, base `81be788`와 feedback-order 후보 위의 별도 변경이다.
먼저 실행한 feedback-order 서비스30개(29개 통과)와 기능12개(12개 통과)는
별도 소스·실패 분모로 보존한다. 실패한 TSan Actual-loss 후보는 주입 전에 Epoch2에서
권한 대기5.036076ms 뒤 기존 명령 expiry보다3,792ns 늦은 Front 수신을 보였다.
Rear 결과의 기존 send-begin/return 간격은2.591727ms, 같은 구간 thread CPU는39,949ns다.
그 뒤 권한 frame의 sender queue 대기는2.850925ms다. 기존 기록 잠금/스케줄링/SDK 내부
대기를 이 수치만으로 구분하지 않는다.

SDK timing의 공용 mutex/push_back을 시작 시 할당한131072개 슬롯과 atomic reservation으로
바꾼다. 포화하면 원본 슬롯을 덮지 않고 trace 오류로 실패한다. 예약은 완료 publication이
아니므로 모든 sender/SDK writer join 뒤에만 읽고 저장한다. Lock-free reservation은
wait-free 실행 또는 wall deadline 보장을 뜻하지 않는다.

Sender는 SDK 호출 직전/직후 wall/thread CPU 시각을 직접 읽고 호출이 돌아온 뒤 기록한다.
Trace append를 SDK call 시간에 포함하지 않는다. 두 시계의 순차 읽기 비용은 남으므로
정밀한 kernel scheduler wait로 해석하지 않는다. Source·expiry·주기·CPU/policy·SDK
구현/설정·queue8과 trace capacity는 유지한다.

Normal/ASan·UBSan/TSan 단위에서 동시 writer 완전성, 포화 후 비덮어쓰기,
한 writer가 copy 중 멈춰도 다른 슬롯이 진행하는 경계를 검사한다.
실제 SDK TUs의 compiler/cppcheck/clang-tidy와 Python bookkeeping을 검사한다.
소스·binary 고정 후 기존 서비스 Normal6/ASan6/TSan18의30개 및 Normal/ASan의
overflow/close-full4개를 실행한다. 네 기능 runtime을 먼저 실행하고 서비스 runtime30개
뒤에 독립 감사를 수행한다. 실패 제외·성공할 때까지 재시도·온도 기준 대기는 하지 않는다.
Host 관측과 이전 후보 비교는 외부 부하/냉각을 통제한 통계적 성능 입증으로 올리지 않는다.
