# Milestone roadmap

현재 구현·수용·OPEN은 [project_status](project_status.md), 실행 이력은 각 evidence와
[품질 기록](quality_policy.md)을 따른다. 이 문서는 단계별 산출물과 TBD의 대표 문서다.
**M6 Host quiet SIL/Python MIL 범위 CLOSED**: [종료 검토표](m6_exit_review.md).
기존 M4 전체 NOT CLOSED, M5 Host FIFO 한정 수용, SDK sanitizer OPEN·Target/system NOT RUN은 유지한다.

| Milestone | 산출물 / 현재 gate |
| --- | --- |
| M0 | Architecture/requirement/ICD baseline — BASELINED |
| M1/M2 | DBC/vCAN·actuator/EV component — 기술 검사 완료, 학습자 review 별도 |
| M3 | 실행 감시·FIFO 기준 — 과거 timing 예외/전체 수용 OPEN |
| M4 | Central·양 Zone·owner/session/protection — Host IO/FIFO component 한정 수용, 전체 NOT CLOSED |
| M5 | 실제 Central↔Front/Rear SOME/IP IP 경계·8참여자·보호/재가입 — 해당 Host FIFO 기능 한정 수용, DDS CLOSED |
| M6 | Simple Vehicle+EV actual/lifecycle/energy·물리 응답·종방향 모델/MIL — **Host quiet SIL/MIL 범위 CLOSED** |
| M7 | M7-0 Host 조사·Plant Adapter ICD 초안/시험 계획 작성 완료; M7-1a/b 환경·비주행 수집과 M7-1c fake Actual/Drive 논리 범위 완료; M7-1d world/state10ms·영상50ms 개정·비주행 수집 검증. M7-1e wheel/clock/비용 진단, M7-1f 별도 functional clock/실제8-role native shadow 구현·한정 검증. M7-1g 실제 wheel→native Actual 반환, M7-1h actuator/electrical 분리·실제 wheel ZOH 예측 한정 검증. 평지 음수 측정 FAIL·native crash OPEN, 정상 actuation/주행·Target 미완료 |
| M8 | Classical driving, M6 종방향 모델→C++ 공통 vector 동등성/차량 SIL, route/waypoint·lateral control — NOT RUN |
| M9 | Fault/Diagnostics/DTC 통합. Local fault 보호는 이미 각 component에서 구현 |
| M10/M11 | Physical AI perception/temporal planner·classical fallback |
| M12 | Thor 또는 Orin의 독립 reference 비교/최적화 |
| M13 | 전체 SIL/V&V/regression·추적성·제약 공개 |

## 다음 작업

M7-0의 [환경 조사·M7-1 계획](test-plan/m7_carla_preflight.md)과
[Plant Adapter ICD 초안](icd/carla_plant_adapter.md)을 기준으로 M7-1a 환경/버전 확인 →
M7-1b 비주행 RGB/GT/state 수집 → M7-1c actual-only·freshness 거부 시험을 수행한다.
[M7-1a 실행](test-plan/evidence/m7_carla_1a/README.md)에서0.9.16 package/Client3.10 설치·
양쪽 버전/연결·ego lifecycle을 확인했다. 실패 원본 보존, CARLA source build 없음.
[M7-1b](test-plan/evidence/m7_carla_1b/README.md)도 main200세트·tick/lifecycle을 검증했다.
native reload/server crash OPEN을 보존한다. [M7-1c](test-plan/evidence/m7_carla_1c/README.md)는
test-only boundary Normal/ASan 각39/39·기존120/120을 확인했다.
[M7-1d](test-plan/evidence/m7_carla_1d/README.md)는 사용자 승인으로 world/state10ms·영상50ms로 개정했다.
main state600/600·영상각120/120·drop/pause/reset 한정 검증. startup60ms와 첫 oracle FAIL 보존,
wall100Hz 미충족·실제 ECU freshness NOT RUN·종료SIGSEGV OPEN-M7-1D-01을 기록했다.
[M7-1e](test-plan/evidence/m7_carla_1e/README.md)는 wheel 물리 회전각 RPC·metadata 수집의 속도 개선을
확인했다. clock 고정 offset 불일치·빈 서버 종료139는 남는다.
[M7-1f](test-plan/evidence/m7_carla_1f/README.md)는 별도 opt-in functional clock과 실제8-role
native 세션/credit/Actual 경로를 stationary SIL fixture로 실행하고 CARLA 비주행 tick에 barrier를
연결했다. [M7-1g](test-plan/evidence/m7_carla_1g/README.md)는 직접 PhysX omega를 native Drive 센서에
연결해 내리막400tick에서 Actual 반환을 확인했다. [M7-1h](test-plan/evidence/m7_carla_1h/README.md)는
actuator/electrical owner를 분리하고 원래 wheel acquisition으로1ms ZOH 모델 예측을 계산한다.
평지 미세 음수는 zero-bin 진단만 추가하고 거부를 유지한다. 다음 M7-1i는 actuation 방식·중복
dynamics 제거·정지 sensor 오차/validity의 근거와 applied Actual/interval work 계약 확정이다.
functional 정상 주행은 full Actual dependency·actuation mapping 입증 전까지 BLOCKED다.
wall 주행에는 source clock mapping/실제 deadline 수용이 추가로 필요하다.
캐시 restamp·요구 완화·command 우회는 해결안이 아니다. [M6 선행 조건](m6_exit_review.md#다음-한-단계--m7-최초-접속-계약과-환경-확인)을 유지하고,
SDK/M4/DDS의 역사적 OPEN 전체를 이 첫 비주행 시험의 선행 조건으로 추가하지 않는다.
Jetson BSP/ABI/권한/NIC·clock/실제 배포 검증은 별도 후속이다.

## Engineering activities

[개발·학습 계획](engineering_plan.md)을 기존 milestone에 연결한다. 아래 표는 학습과
검토 활동의 배치이며 위 milestone의 번호·구현 범위·기존 acceptance를 변경하지 않는다.
추가 안전 분석과 RTE/BSW·Target pilot은 **PLANNED**다. Host의 [Steering OS 파일럿](learning/m3_rtos_pilot.md)은 별도로 구현했다. M0 exit review의 PASS에 포함하지 않는다.
Steering의 [AUTOSAR R25-11 P05 Protect/Check](learning/m1_autosar_e2e_profile5.md)는
M1 Host에서 직접 구현·시험했다. 이 부분 결과를 전체 AUTOSAR pilot 완료로 확대하지 않는다.
[ADR-0022](adr/ADR-0022-leaf-classic-development-methodology.md)로 Leaf의 Classic 개발 체계를
채택했다. Steering부터 ECU 소프트웨어와 SIL 물리 모델 경계를 설계하고 Brake/Drive/BMS로 확장한다.
ECU/SIL 코드 분리는 완료했다. 실제 Classic stack 채택·RTE/BSW pilot은 후속이며 기존 component 결과를 전체 stack pilot PASS로 바꾸지 않는다.

| 관련 단계 | 함께 수행할 학습·검토 | 남길 근거 |
| --- | --- | --- |
| M1 준비 / M1 | Item Definition 초안과 첫 HARA 사례 검토; Steering interface와 AUTOSAR 개념 대응; toolchain 타당성 조사 | 가정·열린 질문, SWC/Port/Runnable/Task 대응, toolchain 지원·제약과 wire 계약 영향 |
| M2–M4 | Leaf의 ECU/물리 모델 경계와 Steering SWC/Port/Runnable/Event/Task 설계; local protection 검토; 작은 AUTOSAR pilot과 stack 채택 여부 검토 | 설계 대응·입출력 계약, actuator response/fault/timing 증거, 설정·생성·실행 기록, 채택·보류 ADR |
| M6–M8 | MBD 종방향 제어 pilot: 제어 모델/plant·MIL→C++ 구현→동등성/차량 SIL; 자동 생성은 선택 후속 | 모델/parameter·sample time/solver·공통 vector·수치/상태 비교·추종/제약·fault 결과; 도구 TBD-16 |
| M5–M8 | 선택한 배포 환경과 closed-loop에서 계약 검증; 차량 거동으로 안전 분석의 가정 재검토 | clock/통신/plant 한계와 실제 관측 구간, 변경된 가정 및 requirement revision |
| M9 | local protection과 diagnostics를 연결하고 분석한 fault의 coverage 검토 | fault→검출→보호→actual response→DTC 연결과 미검증 경로 |
| M10–M11 | SOTIF 관점의 인식·판단 한계, triggering condition, fallback 검토 | scenario/ODD 범위, AI 출력 검증과 fallback의 실제 결과 |
| M12–M13 | compute profile 변경의 timing·보호 동작 영향과 최종 추적성 검토 | profile별 regression, 검증된 범위와 남은 위험·제약 |

AUTOSAR 도구가 미확보되거나 Target 호환성이 부족하면 pilot의 보류 근거를 기록한다.
기존 Linux vECU 개발을 AUTOSAR 적용 완료로 표시하지 않는다. 안전 분석에서 새로운
요구사항이나 architecture 변경이 필요하면 기존 revision 절차로 검토한다.

## Open M0 Decisions

모든 owner의 최종 책임은 **학습자(project owner)**다. 아래 역할 표시는 별도 인력/위임을
뜻하지 않는다. 남은 상세값은 **TBD**이며 각 gate에서 해소한다. TBD-15의 topology/owner는 부분 결정했다.
해당 milestone 전까지 보류할 수 있는 상세값이며 M0 계층/경로/의미 계약의 미결정은 아니다.
문서/YAML의 미결정 값은 아래 ID에 귀속된다. Template의 `TBD`는 향후 기록 필드이지
별도의 design decision이 아니다.

| ID | 미결정 사항 / owner 역할 | 결정 milestone / gate | 보류 rationale / 영향 |
| --- | --- | --- | --- |
| TBD-01 | CAN ID/DLC/layout/scaling/ranges, CRC/counter/epoch/source-age metadata, queue/restart/startup handshake, timeout threshold / interface 담당 | **M1**, DBC/codec 및 vector test 전; task 검증 M2/M3 | M0는 의미/검출 상한을 고정하고 encoding을 M1 산출물로 유지; 100 ms에 polling/실행 margin 포함 |
| TBD-02 | units의 raw scaling, allocation/calibration 값, frame/geometry 변환, feedback skew/age 한계, dynamics 중복 방지 / plant·interface 담당 | **M1** wire 범위; **M2** actuator 의미 구현; **M6** simple mapping; **M7** CARLA mapping 전 | M6 SIL geometry/force·actual mapping은 종료 검토의 부분 결정; M7 좌표/SI 의미·actual-only port는 [ICD 초안](icd/carla_plant_adapter.md)으로 결정. M7-1c prototype의 source/oldest/expiry 보존과 interval 검사만 검증. M7-1g 직접 rad/s·rear 평균·원래 CAN0.01rad/s 반환을 한정 검증. 1h에서 정지 부근 음수를 zero-bin 진단 후 unavailable로 결정, 음수→0 보정은 미채택. 실제 CARLA geometry/역변환·측정 오차 한계/OEM calibration은 미결정, 정상 apply 전 gate |
| TBD-03 | actuator delay/saturation/dynamics/초기값, Steering/Brake timeout 물리 출력, Drive zero-target 후 torque 감소/ramp/반응 deadline, recovery dwell / vECU 담당 | **M2**, 각 actuator 정상/fault test 전; M6/M7 재검증 | M6 현재 모델의 finite 응답/standing hold·230ms 물리 budget 확정; M7 actuator 응답은 기존 physical owner, 차량 운동은 CARLA로 소유권 결정. 1h에서 기존 응답 모델을 합성한 별도 M7 actuator/electrical owner 구현, 차량 운동 중복 적분 없음. output loss 모델 응답 검사. CARLA engine/steering 중복 제거·실제 work port·외부 물리 응답 budget은 미검증, raw fallback/무제한 torque 유지 금지 |
| TBD-04 | task/E2E deadline/budget, source-age 한계, clock sync/uncertainty, trace/overhead/queue schedule, watchdog 독립성, priority/affinity, multirate ordering, timing warmup/duration/repetitions / timing 담당 | **M1** timeout encoding budget; **M3** 측정 protocol/task budget; **M5/M7** cross-node/E2E 전 | 부분 결정: ADR-0033/0034 Host task 10/20/2 ms·deadline 5/8/3 ms, monitor/plant 2 ms와 RX threshold 80 ms·검출 <=100 ms; ADR-0035/37 부하·배치와 ADR-0038의 whole-cycle/CPU·1221개 기회·RX 대응 기록; ADR-0039 Host owner deadline 4 ms·1211 guard slots·교차 보호·이중 수신 감시 채택; ADR-0042 Host FIFO fixture 비교 수행; M7-1d world/state10ms·영상50ms·단일 owner로 개정, Controller20/Zone10ms·Drive30ms 유지. [ICD](icd/carla_plant_adapter.md)의 wheel 원천·clock/Actual interval·native guard gate OPEN. M7-1c 원래 Drive40ms 보호·latch 검증. M7-1e platform→monotonic 상수 offset 불일치. M7-1f 별도 opt-in logical clock/8-role native shadow 구현·검증; source30ms/credit60ms 유지, wall deadline 수용과 구분. M7-1g 원래 wheel source 보존·future 입력 금지·반환 age<=10ms 한정 검증, fractional timestamp pending 손실 수정. 1h 전기1ms 구간 begin 이전 wheel 선택·source/oldest·원래30ms age/10ms skew 보존. full Actual dependency와 차량/Target E2E 미결정 |
| TBD-05 | middleware 구현체/API·schema/integrity·격리·bridge/discovery / communication 담당 | M5 Host 적용; M7 Target 연결 전 재검증 | Host SOME/IP/vSomeIP3.7.6 direct C++·netns/veth/owner-wire는 ADR-0060→0061→0062로 한정 채택. DDS/Cyclone 종료·TSan gate CLOSED는 별도 보존; Target은 미검증 |
| TBD-06 | Central allocation/conflict arbitration, availability/rejoin/local protection 상세, DEGRADED envelope, local↔Central state reconcile / Central VCU·Zone safety 담당 | **M4**, local fault/재연결 시험 전 | 정상 torque/brake 충돌과 actuator availability 검증 필요; critical loss는 M0에서 FAIL_SAFE로 고정 |
| TBD-07 | exact CARLA/Ubuntu/Python/ScenarioRunner 호환 build, map/route/seed/geometry/curve, Host GPU, tick/apply ordering 및 fidelity / simulation 담당 | **M7 통합 전**, route suitability M8 확인 | M7-0 Host Ubuntu22.04.5/RTX3090 24GB 확인, CARLA0.9.16·Client0.9.16/Python3.10·ScenarioRunner v0.9.16 후보. UE5 전환 보류. [공식 근거/실측](test-plan/m7_carla_preflight.md); M7-1a artifact/연결·M7-1b 카메라800×600/FOV90/20Hz smoke 검증. bundled wheel 별도 venv·fresh client reset 경로 한정, 동일 client native reload/server crash OPEN, M7-1d SIGTERM 중 native crash OPEN-M7-1D-01 추가. Town10HD_Opt/mkz_2020 smoke 사용. M7-1d world/state10ms·영상50ms 개정. M7-1e physics-on wheel 회전각 RPC 확인, no-render/render/camera/audit 비용 비교. M7-1f 비주행 native shadow/tick barrier 검증. M7-1g 직접 omega RPC 원천·Town03_Opt 무동력 wheel/반환 경로 확인. timestamp는 single-owner frame bracket으로 결부하며 서버 내장 아님. 1h 별도 actuator/electrical 포트로 내리막400tick 재검증. 평지 음수 측정·역변환/calibration·wall timing OPEN, ODD 유지 |
| TBD-08 | DTC code/debounce/persistence/clear, diagnostic aggregation cadence/storage / diagnostics 담당 | **M9**, event→DTC 통합 전 | local fault/protection은 M2/M4부터 구현, DTC 통합이 선행 조건 아님 |
| TBD-09 | board/RAM/platform stack/power/cooling, reference AI model/checksum/input/precision/feature, profile override, accuracy/resource threshold와 benchmark protocol / compute·AI 담당 | **M5** 첫 Target 호환 stack; **M10** model/reference workload; **M12** board별 비교 전 | 두 보드 독립 배포 원칙 유지. M7-0 Host 자원만 조사; GT는 학습/평가 전용, M7-1 camera smoke 설정은 AI Reference 확정 아님. Jetson·model/feature·동일 binary/engine/JetPack 호환 미검증 |
| TBD-10 | perception/learned-planner shape/risk/history/calibration, AI fallback timing/feasibility/recovery / AI·safety 담당 | **M10/M11**, AI 통합 시험 전 | classical M8 baseline 후 확장; AI로 actuator 직접 제어 금지는 확정 |
| TBD-11 | C++ standard/compiler/CI/test tool versions, artifact size/license/storage policy; control 알고리즘/tuning, speed transition slope/duration, scenario repetitions / toolchain·control 담당 | **M1** 첫 code/tool 전; **M8** control/정상 시험 전; **M10** 첫 model fixture 전 | 작은 변경과 설명 가능한 도구 선택; 5 s settling + 10 s steady window와 수치 requirement 변경은 revision 필요 |
| TBD-12 | EV 전원 sequence/주행 허가/INIT handshake, LV·충전 연결·interlock와 고장별 torque/power reaction, shutdown/복구 threshold·budget / vehicle management·safety 담당 | **M1** 의미/handshake; **M2** power component 시험 전; **M4/M6** gate/vehicle 검증 전 | M6 SIL의 실제8-role startup/RunLease/arm·정상 stop/HV-off·재가입 검증 완료. 외부 차량/LV/charging/Target 반응은 후속; READY≠권한≠물리 완료 |
| TBD-13 | battery usable capacity/initial SOC, pack·셀 극값 voltage/thermal 모델·threshold/dwell, charge/discharge 곡선·효율/부하/에너지 오차, motor power→torque / model 담당 | **M2** Battery/BMS/Drive 시험 전; **M6/M7** 일관성/매핑 재검증 | M6 SIL의 Battery/BMS·회로·vehicle 구간 work/장부 및 charge-zero 검증 완료. M7-1h 원래 wheel 기반 ZOH 모델 예측 포트·원자적 commit 구현. CARLA applied work/전체 에너지 보존은 미수용. 차량 chemistry/thermal/OEM calibration·M7 mapping은 미결정; 단일 owner/clock 유지 |
| TBD-14 | EV wire 수용·coordinator, trusted startup/parent·model identity 전달, clock/각 hop budget, DDS/Host status / interface·timing 담당 | **M1** wire/session 수용 전; **M2/M3** sampler/task/timing; **M5** DDS/Host bridge 전 | **부분 구현:** ADR-0016/17 6개 frame/P05와 항목별 receiver Host 검사; source 50/input 70/RX 80 ms 초안, Drive input age opt-in 분리와 local vCAN 36개 검사 완료; Host 독립3-vECU/실제 session·원천 전달은 구현; 다른 kernel/Target budget은 남음 |
| TBD-15 | 남은 Central–Zone schema/QoS/queue/clock/skew/source-age·monitor budget/INIT-rejoin/routing config / architecture·communication 담당 | **M4** 각 Zone/local test 전, **M5/M6** DDS/plant 통합 검증 전 | **부분 결정:** ZON-01 Front/Rear, 후륜 구동 packaging, Central 별도 단일 coordinator 및 Host typed8-role Prepare/INIT/Release(ADR-0054)·방향별 bounded SPSC/정상 owner 연결(ADR-0055); owner-wire v1/global60ms credit·30ms source age·20ms receipt·common kernel monotonic·원천 CAN/P05/parent/expiry/역방향 ACK 계약 component 검사. Host SOME/IP 3-vECU 세션/격리는 한정 수용; 다른 kernel clock/Target·DDS는 별도 gate, calibration TBD-02/07; 별도 하드웨어 불필요 |
| TBD-16 | MBD 모델 도구/license·model artifact/Host harness·solver/sample time/numeric 설정·모델/코드 동등성 기준·선택적 generator / control·model·toolchain 담당 | **M6** MIL pilot 시작 전 도구/모델 설정; **M8** C++ 비교 실행 전 tolerance/초기 상태/공통 vector, 자동 생성 채택 전 재생성/호환 확인 | M6 Python/binary64·독립 plant·solver/sample/reference/초기 상태·MIL을 ADR-0063으로 결정/검증. M8 C++ 동등성 tolerance·generator 도입은 미결정; M6 종료 검토 참조 |

RG-01의 추가 상세값도 기존 owner/gate에 귀속된다. 범위 결정으로 TBD가 해소되지는 않는다.

| 기존 ID | 회생 설계에서 결정할 항목 / gate |
| --- | --- |
| TBD-01 | M1 Drive signed scaling/범위/layout/Data ID, capability validity/reason/source freshness와 frame 구성 |
| TBD-02 | M2/M6 공통 wheel 기준/geometry, 압력→마찰 torque calibration, capability age/skew와 에너지 산출 단위 변환 |
| TBD-03 | M2 양·음수 motor response/zero-target ramp, 속도별 회생 한계, 충전 수용/효율 fixture, 저속 hold와 energy integration 오차 |
| TBD-04 | M1/M3 capability freshness/monitor timing budget; critical loss 검출 상한 유지 |
| TBD-05 | M5 vehicle state→Zone→Drive 속도 입력/원천 metadata 전달과 ZoneStatus capability schema |
| TBD-06 | M4 회생/마찰 전환/arbitration, actual 보정, 감속 부족·과다/전환 budget와 local protection envelope |
| TBD-07 | M7 signed Drive Actual과 friction Brake Actual을 한 번씩 적용하는 CARLA mapping 및 에너지 모델 fidelity |

추가 TBD는 owner / 결정 milestone / rationale을 이 표에 등록한다. M3/M6/M7/M8 evidence로
수치 변경 시 [requirement revision](requirements/system_requirements.md)에 이전/새 값과
rationale/Result/영향 test를 기록하고 profile/ICD/scenario를 함께 갱신한다.


TBD-02/03/07/12/13/16의 **M6 결정값·소유권·근거와 M7 이후 gate의 구분**은
[M6 종료 검토](m6_exit_review.md#tbd의-m6-결정과-후속-경계)에 모았다. ID 전체를 CLOSED로
덮어쓰지 않는다. 새 수치/범위 변경은 원래 requirement revision·profile/ICD/evidence 절차를 따른다.
