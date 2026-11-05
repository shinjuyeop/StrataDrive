# M9 Clock·Power lifecycle·유한 운용 후속

2026-11-05. Base `158ff4c1cd70a3e937556bfc152d61c3d538829e`.
[집계](acceptance.json), [source](sources.json), [무결성](SHA256SUMS)을 따른다.
M9 전체/Target/무제한 장기 운용 수용을 선언하지 않는다.

Clock은 명시적 same-instance trusted 재검증 revision과 실제 새8-role Release 이후
100ms의 현재 정상 source 진행을 요구한다. 실제 BMS controller와 차량의 SessionParticipant
clock rollback을 검증했다. 입력 복원/INIT만 한 대조군은 Unknown을 유지하고, 별도 재검증을
거친 경우에만 원래 occurrence의 Control proof/Passed를 기록한다. Count/history와 untrusted
fault 시각을 유지하며 자동 clear하지 않는다. 다른 host/kernel clock과 원격 재검증 service는
이 로컬 API/논리 SIL 수용 범위 밖이다.
[Clock protocol](../../clock-recovery-protocol.md)을 따른다.

Power는 PrechargeTimeout/RequestLost/ShutdownCurrentBlocked/StartupEnergized/DischargeTimeout의
실제8-role 차량 연결을 각각 입력 복원만 하는15s와20s 새 INIT 뒤24s까지의 복구로 실행했다.
네 자체 Power 원인은 원래 phase와2s/300ms/1s timeout을 유지한다. RequestLost 주입은
실제 Zone→Power packet drop이며, 상위 transaction/command expiry가 먼저 보호하여 실제
Front/Rear CommandLoss 두 DTC를 기록한다. 도달하지 않은 Power watchdog DTC를 만들지
않는다. 전체 차량 실제 torque/brake·정지·HV-off, 원본 입력/source, durable DTC와 새 Ready
복구를 독립 감사했다. 센서 소비 사본/요청 전달 고장이며 모든 실제 부품 복합 고장 시험으로
확대하지 않는다. [Power protocol](../../power-lifecycle-vehicle-protocol.md)을 따른다.

Debug/ASan·UBSan/TSan 각각 Power10+Clock2개 차량 실행을 보존한다. 영향 범위 각각88개가
통과했고, 전체 Debug unit/logical/transport1336개가 통과했다. 뒤에 추가한 packet identity
변경 경계37개는 세 build에서 각각 재검사했다. Native deadline 성능을 sanitizer의 wall 실행과
섞지 않는다. Canonical journal·native sample·physical trace 독립 감사는 각 profile12개와
94개 변조 거절을 통과했다. 서비스 SDK 전체 sanitizer 수용으로 확대하지 않는다.

`archive_diagnostics.py`는 비활성 store의 독점 flock을 요구한다. 기존 archive/복원 목적지를
덮어쓰지 않고 source/commit/journal/incomplete/pending을 원형 보존한다. 새 복원 directory에만
native lock 파일을 마지막으로 발급한다. 실제 canonical36개를 보관·복원하여 byte 동일성과
독립 재감사를 확인했고8개 파일시스템 부정/경계 시험을 통과했다. Archive는 capacity 회수,
자동 rollover, DTC clear 또는 native semantic replay를 대신하지 않는다.
[보존 protocol](../../diagnostic-retention-protocol.md)을 따른다.

서비스의 긴 관측은 [soak protocol](../../service-soak-protocol.md)을 따른다. 기준500ms1회와
Epoch2/3 각각60s의 quiet3회는 원본 TCP·서비스·순서·배치·응답 독립 감사까지 통과했다.
긴 profile은 실제 wheel feedback으로0.5m/s 저속을 유지한 뒤 원래 정지 기한을 적용한다.
긴 trace는 사전 할당하고 원본 epoch/token/sender/receiver+CRC로 상관한다. 별도 CPU0에서
원본 packet을 유한 메모리에 모아 종료 후 쓰며 실제 socket drop/overflow0을 요구한다.
실제 SO_RCVBUF는425984bytes다.8MiB 요청이 그대로 적용됐다고 가정하지 않는다.

CPU1/2/7에70% busy demand를 주는 부하3회를 같은 후보에서 고정했다. 첫 실행은 실제
Drive command expiry로 정상 서비스 전에 실패했다. [실패 원인 대조](loaded-failure-analysis.json)는
Front enqueue→ACK7.138231ms, Rear enqueue 당시 잔여5.101871ms, 다음 Rear enqueue가
기존 만료보다1.572072ms 늦었음을 원본으로 확인한다. Native detector는 원래 만료 후
0.262904ms에 동작했고 SD-2001의 원본 byte가 Central merged journal에 동일하게 남았다.
검출 후167.122294ms의 첫 물리 표본에서 저속 정지·torque0·제동을 확인했지만, 종료 시
bus250.353V여서 HV-off/전체 서비스 완료를 주장하지 않는다. 정상 장시간 부하 수용은 OPEN이다.
이 분석은 원래 runtime FAIL을 변경하지 않는다. 최종 고정 cohort는 **6/7**이다. 기준+quiet는
**4/4**, loaded는 **2/3**이며 통과한6건은 네 독립 감사와 변조 거절도 모두 통과했다.
Loaded2/3의 실제 competing CPU 점유는 약67–69%였다. 전체7건의 capture drop/overflow는0이다.
정상 장시간 부하 전체를 통과로 분류하지 않으며 실패 후 같은 후보를 추가 재시도하지 않았다.

첫 native 후보는1/7 통과였다. 기존+.2m/s² 입력을60s 유지해 원래 정지 기한을 초과했고
SDK trace 소진/실제 CRC 충돌이 있었다. 후보2는 baseline과 quiet1까지만 실행했으며,
후자는 실제 ECU/서비스 성공 뒤 Leaf input trace 소진 때문에 실패했다. 나머지5개는 미실행이다.
후보3은 baseline과 quiet3개 runtime을 실행했고 quiet1/2의 TCP byte gap을 확인했다.
진행 중인 quiet3은 정상 종료시켰으며 해당 후보의 loaded3개는 미실행이다. 초기/중단된
후보의 분모·실패·원본 source와 로그를 모두 별도 보존하며 최종 후보와 합치지 않는다.

초기 Power 기대값은 local RequestLost가 먼저 발생한다고 잘못 가정해5개 중1개가 실패했다.
실제 earlier CommandLoss 순서를 보존하도록 기대값만 교정했다. 초기 Clock 차량 시험은
Attempt를 쓰는 store에 registry2를 지정하여 첫 append부터 거절됐다. 기존 기동 계약대로
registry3을 사용한 뒤 통과했다. 초기 binary hash는 별도로 수집하지 않아 최종 binary로
표시하지 않는다. 초기 compile 경고와 잘못된 sanitizer target 이름의 build 실패도 보존한다.

정적 검사는6개 변경 production TU의 clang-tidy/cppcheck를 통과했다. SDK TU는 설치된
clang-tidy14와 GCC13 C++20 chrono header 호환 오류를 보존하고, 동일 include/define에서
프로젝트 C++17 구문으로 별도 분석했다. 실제 native binary는 원래 C++20 build로 통과했다.

재현은 새 출력 directory를 사용한다.

```sh
cmake --build build/m1-angle --target clock_recovery_test clock_recovery_vehicle_test power_lifecycle_vehicle_test --parallel 2
STRATADRIVE_CLOCK_VEHICLE_EVIDENCE="$PWD/build/clock-fresh" build/m1-angle/clock_recovery_vehicle_test
STRATADRIVE_POWER_VEHICLE_EVIDENCE="$PWD/build/power-fresh" build/m1-angle/power_lifecycle_vehicle_test
python3 tests/integration/diagnostics/audit_clock_recovery.py build/clock-fresh/revalidated --mutations
python3 tests/integration/diagnostics/audit_power_lifecycle_vehicle.py build/power-fresh/9-recover --mutations
python3 tests/integration/diagnostics/service_soak_suite.py build/soak-fresh
```

부하에서의 순차 Front/Rear 갱신 지연과 실제 CARLA silent packet-loss의 subinterval 물리 연결은
남아 있다. 기존10ms 전체 구간
command authority를 연장하거나 다음 tick 거절을 실제 정지로 보고하지 않는다. 자동 장기
상태 이관/용량 회수·hardware/Target·학습자 설명 수용도 이 유한 검증과 구분한다.
