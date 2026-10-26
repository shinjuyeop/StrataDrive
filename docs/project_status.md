# Project status

Updated: **2026-10-26**. 현재 구현·수용 범위의 대표 문서다.
단계/TBD는 [로드맵](roadmap.md), 종료 판단은 아래 review, 실행 원본·과거 분모는 각 evidence와
[품질 이력](quality_policy.md)을 따른다. 이력의 당시 미구현/FAIL을 현재 상태로 해석하지 않는다.

## Milestone 현황

| 범위 | 현재 판정 | 근거 |
| --- | --- | --- |
| M0 | BASELINED | [M0 검토](m0_baseline.md) |
| M1/M2 | Host 기술 검사 완료, 학습자 review 별도 | [M2 검토](m2_acceptance_review.md) |
| M3 | Host FIFO 기준 사용, 전체 종료/과거 timing 예외 OPEN | [M3 검토](m3_acceptance_review.md) |
| M4 | Host native IO/FIFO component 한정 수용, **전체 NOT CLOSED** | [한정 수용](m4_host_acceptance_review.md), [종료 검토](m4_exit_review.md) |
| M5 | **Central↔Front/Rear 3-vECU SOME/IP Host FIFO 기능 한정 수용, Rear 연결 완료** | [3-vECU/부하·고장·재가입 근거](test-plan/evidence/m5_someip_rear_adapter/README.md), [ADR-0062](adr/ADR-0062-someip-rear-host-adapter.md) |
| M6 | **Host quiet SIL/Python MIL 범위 CLOSED** | [종료 검토표·TBD 분할·제한](m6_exit_review.md) |
| M7-0 | 환경 조사·ICD 초안·M7-1 계획 작성 완료; CARLA runtime NOT RUN | [조사/시험 계획](test-plan/m7_carla_preflight.md), [Plant Adapter ICD](icd/carla_plant_adapter.md) |
| M7-1a | 공식 package/별도 Python 환경·버전/연결·비주행 ego 정상/예외 lifecycle 한정 완료; 원본6시도1PASS/5FAIL 보존 | [실행 근거](test-plan/evidence/m7_carla_1a/README.md) |
| M7-1b | 비주행 RGB/GT/state 수집·tick/센서 lifecycle 완료, fault/pause/reset 부분 검증; 4시도1PASS/3FAIL·native incomplete 보존 | [실행 근거](test-plan/evidence/m7_carla_1b/README.md) |
| M7-1c | test-only Actual/fake backend·원래 Drive 논리 검증 완료: Normal/ASan 각39/39, 관련 기존120/120. 실제 CARLA writer/전송은 NOT RUN | [논리 근거](test-plan/evidence/m7_carla_1c/README.md) |
| M7-1d | world/state10ms·영상50ms 계약 개정 및 비주행 main state600/600·RGB/GT120/120, drop/pause/reset 한정 검증. startup60ms·wall 지연·종료SIGSEGV OPEN | [실행 근거](test-plan/evidence/m7_carla_1d/README.md) |
| M7-1e | wheel 물리 회전각 RPC 원천 확인·4조건×2회 비용 분리·clock 진단 완료. metadata RTF1.014~1.033, 실제 wall 수용 미검증; 빈 서버도 종료139 재현 | [진단/대안](test-plan/evidence/m7_carla_1e/README.md) |
| M7-1f | 별도 functional clock·실제8-role native 세션/credit/Actual 경로·CARLA 비주행 shadow 구현. Normal/ASan 각14/14, 기존144/144와1c39/39. CARLA wheel/actuation은 미연결 | [구현/실행 근거](test-plan/evidence/m7_carla_1f/README.md) |
| M7-1g | 실제 PhysX wheel→native DriveActual→Rear/Central 반환 한정 연결. 내리막400tick·반환396·최대 age10ms. Normal/ASan 각22/22. 평지 음수 측정 연결 FAIL·정상 actuation 미연결 | [원본/실패/남은 gate](test-plan/evidence/m7_carla_1g/README.md) |
| M7-1h | M7 actuator/electrical owner 분리·실제 wheel 기반1ms ZOH 예측 연결. Normal/ASan 각32/32. 평지 SubResolutionNegative 거부 유지; CARLA 실제 work/actuation 미연결 | [구현/실행/제한](test-plan/evidence/m7_carla_1h/README.md) |
| M7-1i | 직접 wheel effort 서버 확장안을 우선 후보로 결정, rad/Nm/Pa 수학 prototype Normal/ASan 각16/16·기존 M7 각71/71. package 직접 포트·brake calibration 부재 확인, 음수 보정 미채택. 새 CARLA 실행/빌드 없음 | [조사/검증/후속](test-plan/evidence/m7_carla_1i/README.md) |
| M7-1j | source build 범위 착수. 공개 PhysX CHECKED SDK·합성 Actual→NoDrive 포트 Normal/ASan 각15/15. 기본 적분 음수45/850 FAIL 보존, 내부20분할 후보에서0/850. 후속 Epic 연결·UE4.26.2 make exit0. 후속 CARLA Client/서버 module build exit0, 직접 연동 미완료 | [빌드/실행/제한](test-plan/evidence/m7_carla_1j/README.md) |
| M7-1j source 실행 | Town03 비렌더링 연결/identity·ego 정상/예외2/2·10ms102샘플 한정 통과. SIGINT130·자원 정리 확인. Town10 준비 한도 초과/강제 종료와 Town03 렌더링 SIGSEGV·검증 코드 초기조건 FAIL 보존. 렌더링 OPEN | [실행·실패·제한](test-plan/evidence/m7_carla_1j_source_smoke/README.md) |
| M7-1j 렌더링 조사 | GDB camera SIGSEGV의 잘못된 Distance Field 참조 관측, 원인 미확정. 같은 바이너리의 GDB1회·native 같은 서버2회 각 RGB/GT30쌍·150tick·actor 정리/설정 복원 한정 통과. 재질 준비/렌더러 안정성 OPEN | [조사·실패·한계](test-plan/evidence/m7_carla_1j_render_diagnosis/README.md) |
| M7-1j 준비 baseline | ego/RGB/GT 유지 중 shader·Distance Field zero를10s 간격2회 확인. 준비 후 GDB1회·새 native2서버 각150tick/30쌍 및 정리/복원, SIGINT130 한정 확인. broad trace timeout·DDC01 대상0/02 수동 중단 보존. 원래 crash root cause OPEN | [후속 검증](test-plan/evidence/m7_carla_1j_render_followup/README.md) |
| M7 후속–M13 | PLANNED / NOT RUN; 정상 CARLA 주행 연결 BLOCKED | [로드맵](roadmap.md) |

## 구현·시험한 범위

Central은 조정·배분·SessionCoordinator/영속 Epoch·RunLease 발급을 소유한다.
Front는 FrontZone/Steering/Brake, Rear는 RearZone/Drive/BMS/Power를 별도 프로세스에서
단독 소유한다. 실제 IP/SOME/IP/owner-wire/CAN/P05 경계를 통해 실제8참여자의
INIT/Release ACK/credit/arm, 명령·Actual/health·보호·새 Epoch 재가입을 연결했다.

Persistent SIL physical process가 actuator·센서·SimpleVehicle·EV/Battery를 소유하고
동일 구간 motor work로 차량/전기 에너지를 결합한다. 실제 wheel feedback이 Central에 돌아온다.
SIL 입력 시나리오와 물리·센서 bus는 fixture이며 명령·권한 전달을 우회하지 않는다.
실제 C++ 속도 폐루프는 미구현이다. Python 종방향 PI/MIL은 별도 모델이며 M8 동등성과 구분한다.
[배포/실행 경계](architecture/deployment_architecture.md), [M6 모델 계약](icd/vehicle_energy.md)을 따른다.

## 검증 결과와 한계

M6 최종 [물리 응답 근거](test-plan/evidence/m6_physical_response/README.md):
전체 C++ Normal/ASan 각1018/1018, 실제 계측 TSan 경계35/35,
Python/무build export 각54/54. SDK 신규3회2PASS/1FAIL이며 수정 후 command-loss1/1과
영향 없는 nominal1/1이 수용 근거다. 과거 원본·분모는 합쳐 PASS로 바꾸지 않았다.
100ms loss 검출/230ms 실제 보호 응답의 기점·모델 범위는 [물리 계약](icd/vehicle_energy.md#physical-response-contract)에 있다.
M6는 quiet 범위이며 M5의 제한된 부하 수용을 다른 workload로 확장하지 않는다.

| 남은 문제/제한 | 현재 처리와 근거 |
| --- | --- |
| OPEN-M6-ENERGY-01 | 현재 모델/응답 판정 불일치 범위 해소. 옛100ms FAIL·옛1MPa 미관측은 보존 |
| OPEN-M6-ENERGY-02 | 실제 instrumented SDK의 wall/송수신·SDK 오류/기능 미완료 OPEN. 경계 sanitizer PASS로 대체하지 않음; [원본](test-plan/evidence/m6_vehicle_energy/README.md) |
| M4·M3 과거 timing/FIFO/native/physical pause | 역사적 OPEN 유지. 후속 통과로 과거 원인 해소를 주장하지 않음; [M4 검토](m4_exit_review.md), [native 근거](test-plan/evidence/m5_someip_native_watch/README.md) |
| DDS | **정규 제어 gate CLOSED, adapter 미착수**. 종료/20ms/TSan FAIL·접근 제한 이력 보존; [DDS 후속](test-plan/evidence/m5_dds_shutdown_followup/README.md). 제한된 작업을 우회·재시도하지 않음 |
| Target/전체 시스템 | Jetson·실제 IO·Host–Target 검증,32req/29system TC는 NOT RUN. 학습자 설명/수용은 기술 판정과 별도 |

## 다음 작업

**M7-1j는 준비된 Town03 비주행 반복 baseline을 확보했다. 원래 렌더링 crash 원인과 정상 actuation은 OPEN이다**.
[M7-1j](test-plan/evidence/m7_carla_1j/README.md)에서 공개 CARLA source를 확보하고 공개 PhysX3.4
CHECKED SDK·합성 Actual→NoDrive 물리 포트를 구현했다. Normal/ASan 각15/15, 독립 CSV
손상8/8 거부를 확인했다. 외부 SDK 자체는 sanitizer 미계측이며 UBSan vptr만 제외했다.
기본 적분 출발 음수45/850 FAIL을 보존하고 차량 내부3/10/20/40분할을 비교했다.
world10ms를 유지한20분할 후보는 정지·출발·음수 torque 감속·마찰 정지에서 음수0/850이었다.
이는 독립 synthetic 차량의 결과이며 stock CARLA 평지 실패 해결·native8-role 주행 성공이 아니다.

사용자가 source build 후속 진행을 지시했으므로 별도 범위 승인은 더 필요하지 않다.
Epic–GitHub 연결 후 UE fork 접근을 확인했고, `carla` branch의 UE4.26.2 commit
`e9d9e60c85f643e10eeb03f42f61554d18dcb30f`를 고정했다.
[엔진 빌드 근거](test-plan/evidence/m7_carla_1j_ue_build/README.md): Setup/프로젝트 생성 완료,
중단했던 make를 재개해 전체 exit0, UE4Editor 및 도구 생성·ldd missing0 확인.
engine tracked source 변경은 없다. 후속 [CARLA 기본 빌드](test-plan/evidence/m7_carla_1j_carla_build/README.md)에서
의존성 설치 확인·별도 venv의 Client wheel과 서버 module build exit0/import·ldd missing0을 확인했다.
libpng URL404/PROJ include/PIC 실패3시도와 최소 build patch를 보존했다.
후속 [source 실행](test-plan/evidence/m7_carla_1j_source_smoke/README.md)에서 Client/Server
294096e-dirty 일치와 Town03 비렌더링 ego 정상/예외2/2, 본 관측102개의10ms tick을 검증했다.
Episode 설정 복원 후 SIGINT130으로 종료했고 포트/소유 프로세스가 정리됐다. exit0 판정은 아니다.
Town10 최초 준비1800s 한도 초과/수동 강제 종료, Town03 렌더링 시작 SIGSEGV와 시작 INI/Episode
읽기값을 동일하게 가정한 harness FAIL을 보존했다. 비렌더링 성공으로 렌더링 FAIL을 닫지 않는다.
이전 fork404와 UE4_ROOT 누락 build 실패는 당시 evidence로 보존한다.
시스템 의존성과 전용 Python/0.9.16 content를 준비했다. 후속
[렌더링 조사](test-plan/evidence/m7_carla_1j_render_diagnosis/README.md)에서 camera 경로 SIGSEGV의
유효하지 않은 Distance Field 내부 참조를 GDB로 관측했다. 같은 바이너리에서 GDB1회와
native 같은 서버2회가 각각150tick/RGB·GT30쌍 수신·정리/복원에 성공했지만 원인은 미확정이다.
체크무늬 재질·shader 준비 지속·첫60ms 간격도 남아 있으며 native supervisor exit143/종료 wait status
미확보를 별도 기록했다. engine 수정이나 요구 완화는 하지 않았다.
후속 [준비/반복 검증](test-plan/evidence/m7_carla_1j_render_followup/README.md)에서 넓은 추적의 world timeout과
DDC01 대상0/02 광범위 cooked cache 수동 중단을 보존했다. 실제 ego/RGB/GT를 유지하며
shader/Distance Field zero를10s 간격2회 확인했고 준비 후 GDB1회·별도 새 native2서버에서
각150tick/30쌍 수집·정리/복원을 확인했다. native SIGINT130이며 full stability 수용이 아니다.
원래 잘못된 참조의 원인은 재현되지 않아 OPEN이고 기존 누락 content 경고도 남는다.
다음은 이 제한된 baseline의 서버 NoDrive/writer/frame 포트 → 실제 geometry/brake calibration → 보호 Brake Actual과 raw wheel
검증 → interval work/EV 연결 순서다. 합성 pressure table은 calibration이
아니며 numerical subdivision은 이 독립 시험의 후보 설정이다. epsilon/clamp는 추가하지 않았다.
source 영상은 위 최소 수신 진단만 검증했다. 완전 센서 delivery·정상 주행·에너지 수용은 NOT RUN이고 기존 M6는 유지한다.

[M7-1h](test-plan/evidence/m7_carla_1h/README.md)에서 별도 actuator/electrical owner를 구현했다.
차량 운동을 중복 적분하지 않고, 전기 모델에 각1ms 구간 begin 이전의 실제 wheel 원천을 넣는다.
400tick의3,989구간을 독립 ZOH oracle로 확인했다. 이 에너지는 CARLA에 적용되지 않은 모델 예측이다.
Normal/ASan 각32/32, 기존 관련144/144·1c39/39. 미세 음수는 zero-bin 진단 후 거부하며
평지 문제를0 clamp로 감추지 않았다. rad/Nm/Pa 변환·applied Actual receipt/interval work와
정지 부근 signed sensor의 근거 있는 오차/validity 결정이 남는다.1h 당시 source build는 하지 않았다.

[M7-1g](test-plan/evidence/m7_carla_1g/README.md)에서 직접 PhysX omega를 기존 Drive 센서에
연결했다. 내리막400tick에서 원래 vECU·CAN/P05·Rear·Central Actual 반환을 확인했다.
중력 이동이며 controller가 CARLA를 가속한 결과는 아니다. fractional timestamp의 pending
덮어쓰기 버그를 수정했으며 Normal/ASan 각22/22와 기존 관련144/144·1c39/39를 확인했다.
평지에서는 미세 음수 wheel로 기존 전진 전용 검증이 거부한다. 정지 잡음/측정 분해능 계약,
실제 CARLA work 연결, rad/Nm/Pa 역변환·full Actual interval gate가 남는다.1h의 포트 분리는 위 범위만 수용한다.
임의 epsilon/clamp나 명령 우회는 추가하지 않았다.6live 시도의 실패3개와 서버 종료139를 보존했다.

[M7-1f](test-plan/evidence/m7_carla_1f/README.md)에서 별도 opt-in simulation-clock shadow를
구현했다. 원래 native8-role actor의 INIT/Release ACK/RunLease/arm·Actual 반환 경로를
stationary SIL fixture로 실행하며 CARLA10ms tick 전 barrier를 확인한다.100ms Host 지연·
250ms pause에도 logical age/권한을 유지하고, 누락·중복은 다음 tick을 차단한다.
1f 당시에는 CARLA wheel을 입력으로 사용하지 않았고,1g가 센서 입력만 연결했다. Actual의 CARLA 적용은 미연결이다.
M6 wall runtime·2ms/4ms guard·30ms freshness는 그대로다. 기능 검증의 시간 진행 경로는
확보했지만 calibrated normal driving이나 실제 wall 성능 수용은 미완료다.

[M7-1e 진단](test-plan/evidence/m7_carla_1e/README.md)에서 physics-on wheel 회전각 RPC 원천을
확인했다.1g에서는 직접 omega를 선택해 각도 차분을 사용하지 않는다. 전체 ODD/측정 validity는 미검증이다. 영상 audit을 뺀1e 정적 수집은
RTF1.014~1.033, 각400tick에서30ms 초과0이지만 max26.654ms로 실제 ECU 여유는 작다.
전체 실행에서 platform→monotonic 고정 offset 가정은 불일치했다.1f의 simulation clock은
이 mapping을 사용하지 않는 별도 모드이며, 현재 M6 wall 실행 계약을 변경한 것은 아니다.

[M7-1d](test-plan/evidence/m7_carla_1d/README.md)는 사용자 승인으로 world/state10ms·영상50ms를
채택했다. 본 관측 state600/600·RGB/GT 각120/120, 누락·pause/reset을 한정 검증했다.
최초 camera 간격60ms는 startup 변동으로 보존하며 첫 oracle FAIL과 수정 후 확인 실행을 구분한다.
1d 당시 논리 sampling 충돌은 제거했으나 실제 ECU 적합은 NOT RUN이었다.1g wheel 논리 경로의 한정 검증과 wall 수용을 구분한다.1d 최종 nominal RTF0.764923,
pause 제외 snapshot 완료 간격>30ms12/798이며 wall100Hz 수용이 아니다.
[M7-1c](test-plan/evidence/m7_carla_1c/README.md)의 native Drive stale/latch 결과와 M6 계약은 유지한다.
실제 Central→Zone→vECU→CARLA 전송·writer/권한·calibration·중복 dynamics/energy는 미검증이다.

**OPEN-M7-1D-01:** actor0·world 설정 복원 확인 뒤 서버 SIGTERM 종료 중 native SIGSEGV/139.
M7-1e의 빈 서버SIGTERM/빈 서버SIGINT/진단 후SIGTERM 새3프로세스에서도139를 관측했다.
센서/reset 없이 재현되며 root cause는 미확정이다. 현재 서버/포트는 정리됐다.
M7-1a/b/c의 원본 실패와 OPEN-M7-1B-01/02는 그대로 유지한다.
정상 CARLA 주행 연결은 wheel 정지 잡음/ODD validity·full Actual dependency/interval·calibration 입증 전까지
**BLOCKED**다. wall 모드에는 source clock mapping·native2ms/4ms guard 검증도 별도로 필요하다.
functional 모드의 성공으로 wall gate를 면제하지 않는다. M6 종료·코드·수치·판정은 변경하지 않았다.
