# 지연 수신 권한의 freshness와 현재 slot 지원 검증

2026-11-05, base `da19483`. Stop deadline polling 후보 이후 별도 고정 cohort.
선행 후보의 TSan actual-loss-r3는 주입 전에 DrivePermissionLost로 보호됐다.
원래 due828060288689328 이후 발행한 grant146은 current release828060298689328
직후 수신됐다. source가 current보다 앞이라는 이유로 거절했지만 원래
expiry828060318913270은 current+18ms를 넘었다. 이 권한을 사용하지 못한 채
grant145가 만료됐고 grant147은 만료 이후에 도착했다.

새 권한 판정은 원래 기다리는 due release 이후 source인지 확인한다. 남은
유효기간은 실제 실행할 current nominal release+기존18ms를 엄격히 넘어야 한다.
두 기준을 함께 검사하고 current received identity/quality, 실제 now 유효성,
pending command 완료 조건을 유지한다. 완료된 job의 권한 재사용, 원래 expiry
연장, 과거 job 재생은 허용하지 않는다. Callback 중 slot이 바뀌면 다시 보류한다.
기존 두 인자 port 호출은 보수적인 기존 source>=current 조건을 유지한다.

`allocation-readiness` trace의 `source`는 원래 due, `sent`는 current
release다. `original_source`와 `inner_deadline`는 실제 grant source/expiry다.
일반 transport 단계의 필드 의미는 바꾸지 않는다. 새 source 조건 전 회귀 실패와
변경 후 통과, short support·재사용·잘못된 release 순서 거절을 검증한다.

전체 Debug/ASan·UBSan, 관련 TSan, 변경 구현의 cppcheck/clang-tidy,
Python 및 CARLA adapter 논리 검사를 먼저 실행한다. 이후 source와 Normal/ASan/TSan
binary를 고정하고 기능12건, 서비스 Normal6/ASan6/TSan18건을 순서대로 실행한다.
실행 설정과 fault/jitter 분모는 선행 stop-deadline-poll protocol과 같다.
Native 중 build·다른 runtime·무거운 분석은 실행하지 않는다. 감사는 모든 runtime
종료 뒤 실행하며 실패도 모두 보존한다. 이전 후보를 덮어쓰거나 성공까지 반복하지 않는다.

SDK queue overflow와 불완전 TCP capture는 별도 실패로 유지한다. SDK 오류 허용,
deadline 변경, 증거 누락 면제는 없다. 이 결과만으로 M9 전체·native4ms·Target·
CARLA subinterval·trusted Clock recovery·bootstrap incident·전체 fault/보존 범위나
학습자 이해 review가 완료됐다고 판정하지 않는다.
