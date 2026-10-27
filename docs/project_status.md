# Project status

Updated: **2026-10-27**. 현재 구현·수용 범위의 대표 문서다.
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
| M7-1k | 실제 UE NoDrive 0 effort 서버 포트·별도 Client 구현. 최종156개 검사(반복 포함)/13개10ms receipt, 직접 외부 writer·일반 tick 거부, pause/실제 physics reset·새 INIT 한정 검증. 독립 audit 손상8/8 거부, default-off 비주행2/2·102샘플. 초기 build2FAIL/시험1FAIL 보존. 정상 driving/work 미완료 | [실행·실패·gate](test-plan/evidence/m7_carla_1k/README.md) |
| M7-1l | 읽기 전용 rest geometry5개 INIT 자세·COM/body/actor/프로젝트 반사 교차 검증, 독립 손상7/7 거부·reset 후 geometry 무효화. 실제 COM과 공개 COMNudge 구분. 새 binary의1k 회귀156개/13receipt 통과. build1FAIL·단위 가정 audit1FAIL 보존. brake V1/H1은 제안·미채택, 정상 gate 유지 | [실행·모델 선택안](test-plan/evidence/m7_carla_1l/README.md) |
| M7-1m | 사용자 수용 V1 가상 EV·별도 서버 opt-in nonzero effort 한정 검증. 새2서버 각각1,621 receipt/38검사·독립 손상9/9 거부. 보호 Brake Actual hold100/100 exact0. 각487frame rear 음수로 native forward gate FAIL, full Actual/work/wall 미연결 | [실행·실패](test-plan/evidence/m7_carla_1m/README.md) |
| M7-1n | 동일 binary·동일 원래 Actual 대조: 기본3/1에서 rear 음수487frame 재현, 내부20/20 새2서버는 각각3frame(출발 첫 tick)으로 감소하나 native forward gate FAIL. 각1,621receipt/42검사·손상10/10 거부.20분할 정상 미채택 | [대조·실패](test-plan/evidence/m7_carla_1n/README.md) |
| M7-1o | 저속 tire 반력/명시적 적분의 출발 진동 확인. 정착·response 입력·40/80분할 FAIL 보존.320분할과 직접 solver ω 읽기로 새2서버 stress 및 response 입력 각1,621frame 음수0. 공개 getter의 저속 보정과 solver 원천 분리. 정상8-role/work/wall 미연결 | [원인·수정·검증](test-plan/evidence/m7_carla_1o/README.md) |
| M7-1p | 직접 solver→기존 native 센서/CAN·Rear·Central 반환 한정 연결. 새320분할 step/response 서버 각1,621관측·1,609반환, 다음 구간 끝 age 최대20ms. 실제20분할 음수/주입 snapshot 누락 시 다음 tick 차단. Normal/ASan 각60/60, metadata 손상29종 거부. 최초 snapshot 수신 지연/정리 검사 FAIL 보존. full Actual actuation/work/wall은 미완료 | [실행·실패·제한](test-plan/evidence/m7_carla_1p/README.md) |
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

**M7-1p에서 직접 solver wheel의 native Actual 반환을 한정 검증했다.
정상 주행은 full Actual actuation/authority·work/wall gate로 계속 BLOCKED다.**
[M7-1p](test-plan/evidence/m7_carla_1p/README.md)의 새320분할 step/response 서버는 각1,621개 원천을
기존8-role fixture에 공급하고1,609개 DriveActual 반환을 확인했다. source를 새로 찍지 않고
다음10ms 구간 끝 age 최대20ms로30ms 요구를 유지한다.20분할의 실제 출발 음수와200번째 snapshot
전달 누락 주입은 다음 tick을 차단했다. pause/reset 뒤 기존 bridge는 폐기하고 새 INIT를 요구한다.
CARLA actuation은 여전히 격리 합성 Actual이며 native 반환 torque를 CARLA에 적용한 결과가 아니다.
[M7-1o](test-plan/evidence/m7_carla_1o/README.md)는 타이어 반력에 의한 내부 회전 부호 진동을
계측하고 물리 계수 변경 없이 적분 간격을 줄였다. 최종320분할의 새2서버와 기존 response
모델 입력은 각1,621frame/4wheel 직접 solver 음수0이다. 앞바퀴 중간 계산의 미세 음수는 보존했다.
기존 `omega_rad_s` 공개 API는 무구동·저속 보정값일 수 있어 새 `solver_omega_rad_s`와 구분한다.
다음은 실제8-role full Actual interval/authority를 서버 적용 gate에 연결 →
solver 구간 work/단일 EV → wall timing이다.320분할은 이 후속 격리 통합 후보이며 기본 asset3/1,
M6 코드·수용·30ms freshness는 유지한다.
[M7-1m](test-plan/evidence/m7_carla_1m/README.md)는 M6 합산0.001Nm/Pa의 가상 law를4륜 균등 배분하고,
기존1l geometry에 고정한 이상 Ackermann/rear50:50 모델을 별도 서버 옵션으로 적용했다.
각1,621receipt의 두 새 서버에서 출발·음수 motor 감속·마찰 정지·hold/release·좌우 조향을 관측했다.
보호 Brake Actual도 적용했지만 각487frame은 raw rear 음수로 native 전진 입력 unavailable이다.
값을 보정하거나 native loop에 공급하지 않았다. 후속 [M7-1n](test-plan/evidence/m7_carla_1n/README.md)의
동일 입력 대조에서 내부20분할은 rear 음수487→3frame으로 줄었지만 출발 첫 tick의 약−.256rad/s가
새2서버에서 동일하게 남았다.20분할은 정상 미채택이며 후속 원인 분리·수정 결과는 위1o를 따른다.
[1l geometry](test-plan/evidence/m7_carla_1l/README.md)의 실제 COM/COMNudge 구분은 유지한다.
V1은 실제 MKZ 유압 calibration이나 기존 M6 응답/에너지 수용을 승계하지 않는다.
[M7-1k](test-plan/evidence/m7_carla_1k/README.md)는 원본 CAN/P05 receiver를 UE 도구체인으로
컴파일하고, opt-in ego를 실제 NoDrive로 전환한다. 합성 Actual 세 값이 모두0인 경우만
허용하며 실제8-role 주행 authority나 brake calibration은 아니다. 최종13개 receipt의 원래 source와
raw signed wheel을 보존했고 work는 unavailable이다. 실제 reset 후 pending 폐기·재무장 차단,
별도 client의 직접 제어/velocity/pose/physics 거부와 기존 flag-off 비주행 lifecycle을 확인했다.
rest geometry는1l 범위까지 확인했다. 근거 있는 brake 모델 → nonzero effort/보호 Brake Actual 및 raw wheel →
실제8-role full Actual interval → solver work/단일 EV → wall timing 순서다.
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
서버 NoDrive/writer/frame 포트는 1k의0 effort 범위까지 진행했다. 실제 geometry/brake calibration → 보호 Brake Actual과 raw wheel
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
