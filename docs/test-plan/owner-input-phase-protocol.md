# Central 입력 경계와 정지 요청 위상 검증

2026-11-05, base `da19483`. 이전 계측 cohort의 I/O2 Stop-ACK-r1/r4는
AcknowledgedPower에 묶인 grant support가18ms에109276ns/668676ns 부족해
한 회차를 건너뛰었다. 새 Front command의 실제 전달은0.486ms/0.468ms였다.
SDK queue 시각만으로 VM snapshot 전에 채택됐다고 단정하지 않는다.

Central의 SDK ingress를 물리 입력 IO 뒤와 제어 snapshot 직전에 소비한다.
두 pass가 하나의 lane별8건 budget을 공유한다. 우선 authority1/3, normal0/2의
순서·capacity8·원래 source/expiry와 실제 수신 판정은 유지한다.
PowerStatus owner ingress와 VM snapshot에 원본 sequence/causal/source/
accepted-request-source 및 관측 시각을 추가한다. 원래 SDK API 기록과 연결한다.

StopRequest의20ms 주기는 유지하고 VM10ms/+4ms의 동일 enable grid에 맞춘다.
기존 `last_actual+20ms` 방식은 실행 jitter가 누적돼 VM release 직후 갱신될 수
있었다. 새 요청은 실제 실행 시각과 새 sequence로 발행하고 VM에 먼저 공급한다.
놓친 slot은 재생하지 않는다. 최초 정지 요청은 다음 VM release에서 시작하며
그 다음20ms grid로 정렬되는 첫 간격은10ms일 수 있다. 원래 request60ms와
원본 source+50ms+1의 유효성, 자식 expiry,18ms support를 늘리지 않는다.
Allocation10ms, SDK I/O2, owner/SDK/aux 배치·policy, stop/handshake/drain budget도 유지한다.

두 pass 사이 도착과 총 budget, authority 순서, jitter·missed-release·rollback을
단위 검사한다. 기존 deadline 경계 및 제어 검사와 Normal/ASan·UBSan/TSan 빌드,
변경 TU 정적 검사와 Python 회귀 후 source/binary를 고정한다.
Normal/ASan 기능12건(three normal/command-loss/restart-live와 two delay/overflow/close-full),
서비스 Normal6/ASan6/TSan18의30건을 실행한다. 모든 native runtime 후 독립 감사한다.
최초 실패·원본 기록·분모를 유지하며 성공할 때까지 반복하지 않는다. 후보가 실패하면
원인을 확인하고 다른 소스/별도 사전 cohort로 검증한다. SDK 오류 whitelist를 늘리지 않는다.

실험 통과는 해당 Host profile의 서비스 수용 근거다. Native4ms/Target·임의 부하의
실시간 상한이나 Clock/CARLA/기동/보존 및 M9 전체 수용을 대신하지 않는다.
