# SOME/IP 입력 snapshot 순서와 full-queue 종료 검증

Base `81be788`, 2026-11-04. Central의 bounded ingress service를
`AsyncCoordinatorPort::feedback()`의 snapshot 생성 앞으로 옮긴다. 기존에는
호출자가 snapshot을 복사한 뒤 `VehicleCoordinator::tick()` 내부 `healthy()`에서
수신을 처리해 VM이 한 회차 전 값을 사용할 수 있었다. Original source, expiry,
18ms support, VM10ms/+4ms, allocation10ms, mailbox8과 fault latch는 유지한다.
관리 주기 뒤 도착한 Actual까지 이 수정으로 해결됐다고 주장하지 않는다.

`close-full`은 첫 FIFO8을 거부한 직후 보호 ACK만으로 endpoint를 닫지 않고,
기존20ms cleanup 구간 동안 추가 bounded8 요청도 명시적으로 거부한다.
새 명령을 Leaf에 전달하지 않으며 SDK 오류 판정 규칙을 완화하지 않는다.
원래 cleanup deadline을 기록하고 매 iteration에서 종료를 검사한다. Host scheduling
overshoot와 SDK stop/join은 실제 시각으로 기록하며20ms의 강제 wall 상한으로 해석하지 않는다.
판정은 sender 생존·새 Epoch 정상 재시작·첫8+추가8 거부·Central16건 negative 결과,
expiry/late0과 drain 시각을 모두 요구한다. 기존 실패 원본은 수정하지 않는다.

먼저 새 snapshot/원래 deadline 단위 시험의 수정 전 실패를 보존하고,
Normal·ASan/UBSan·TSan에서 AsyncOwner/AsyncZoneOwner를 검사한다.
Python oracle의 missing/changed/expired/early-drain 반례를 검사한다.
변경 C++ TU에 현재 compilation database로 cppcheck/clang-tidy를 실행한다.

소스·binary 고정 후 기존 Normal6/ASan6/TSan18 서비스30개와 Normal/ASan 기능 회귀12개를
각각 한 번 실행한다. 기능 회귀는 three-ECU normal/command-loss/restart-live와
two-ECU delay/overflow/close-full이다. 서비스는 split-owner-io/owner-fifo/separate-aux-io를
사용한다. 모든 runtime 뒤 독립 감사를 실행하며 runtime 중 빌드/감사를 하지 않는다.
실패 재시도·제외·온도 기준 대기는 하지 않는다. CPU 주파수/온도는 별도로 관측한다.
기능·sanitizer·Host timing·Native4ms/Target 수용과 학습자 review를 분리한다.
