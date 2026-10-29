# CARLA Plant Adapter 계약

기준: `m7-plant-draft-v28`. **시뮬레이션 기능 수용과 실제 wall 실시간 gate를 분리한다.**
이 문서는 현재 적용하는 소유권·actuation·clock·solver/EV·센서 계약을 정리한다.
구현/수용 결과는 [프로젝트 상태](../project-status.md), 실행은 [CARLA 안내](../carla-guide.md),
이전 제안·실패·개정 이유는 [계약 이력](../archive/carla-history.md#icd)에 있다.
M6의 통신·안전·물리 수용 기준과 CAN/P05·owner-wire v1은 변경하지 않는다.

## 소유권과 적용 경로

Central → Front/Rear Zone → vECU → Actual CAN/P05 → 담당 Zone → Central feedback bridge →
Plant Adapter → CARLA의 반환 경로를 유지한다. 명령·목표·permission·ACK를 Actual로 바꾸지 않는다.
Adapter는 ego actuation의 단일 writer이며 별도 client/TrafficManager/ScenarioRunner tick은 금지한다.
서버 격리·opt-in owner 인증은 전용 시험 guard이며 stock CARLA 전체 보안 인증을 뜻하지 않는다.

| 상태 | 유일한 책임 |
| --- | --- |
| 세션·배분·권한·로컬 보호 | 원래 Central/Zone/Leaf의 실제8-role INIT/Release ACK·RunLease·credit·arm |
| actuator 응답·센서 | native SIL physical owner, Leaf가 Actual 보고. Adapter에서 delay/ramp를 중복 적용하지 않음 |
| 차량 motion·wheel inertia·tire/suspension | CARLA NoDrive. SimpleVehicle/VehicleEvModel motion을 동시에 적분하지 않음 |
| Battery/SOC·HV/접점·손실 | 단일 EV owner. 관측 work 정산과 ZOH 예측을 중복 실행하지 않음 |

`set_target_velocity`·teleport·clamp·합성 wheel·두 번째 motion plant로 계약을 우회하지 않는다.
지원하지 않거나 불완전한 값은0으로 채우지 않고 unavailable/latch 처리한다.

## Sample·세션·frame

각 sample은 schema/run/plant epoch·source/epoch·sequence·clock·acquisition·oldest dependency·
validity/reason·frame identity를 보존한다. 새 envelope/counter·cached 조회로 원천을 갱신하지 않는다.
Run UUID/session/ego actor/physics generation/model/profile을 trusted INIT에서 바인딩한다.
Payload의 자기 선언만으로 권한·geometry·calibration을 승인하지 않는다.

의미 port는 describe/configure → accept_actual → prepare_step → commit_step → observe와
pause/reset/close다. Simulator handle/type은 backend 안에 둔다. 이것이 별도 공통 wire ABI를
확정한 것은 아니다. 실제 확장 RPC·guard는 [NoDrive 설치 안내](../../tools/carla/m7_nodrive/README.md)를 따른다.

## V1 가상 EV mapping

[승인 모델](../../tools/carla/m7_nodrive/virtual_ev_v1.json)은 실제 MKZ 유압 calibration이 아닌
선택한 가상 law다. 모델 hash·실측 geometry·wheel 순서/축·physics generation을 고정한다.

| Actual 입력 | V1 적용 |
| --- | --- |
| equivalent angle ±0.3rad, 프로젝트 좌+ | 실측 wheelbase/front track으로 이상 Ackermann. CARLA 우+는 부호 반전, rear0 |
| aggregate signed motor −200..300Nm | front0, rear 각T/2. Engine/gear/clutch/추가 lag/filter 없음 |
| aggregate pressure0..1.5MPa | 합산0.001Nm/Pa를4륜 각25%의 nonnegative brake capacity로 배분 |
| geometry | mass1696kg·radius0.355m·실측 wheel bone/COM·front steer/각800Nm brake readback과 고정 모델 비교 |

Plugin 경계까지 rad/Nm/Pa·SI를 유지하고 UE 내부 torque만 Nm×10000으로 변환한다.
Ackermann은 `δL=atan2(L*tanδ,L-W*tanδ/2)`, `δR=atan2(L*tanδ,L+W*tanδ/2)`다.
Drive와 friction을 분리하고 회생을 friction으로 적용한 뒤 배터리에도 중복 회수하지 않는다.
범위 초과는 clamp하지 않는다. Geometry/모델이 바뀌면 기존 수용을 승계하지 않는다.

## Functional 적용과 lifecycle

원래 CAN/P05 Actual·source/oldest·parent Command·permission·Release/credit이 **전체 다음10ms**를
덮는지 검사한다. Command는 proof이며 적용 입력은 Actual이다. Arm 후 비정상 mode/authority는 거부한다.
전용 INIT offset8ms·기본 Controller 시작 위상14ms는 functional 경계이며 wall jitter 여유가 아니다.

하나의 run/plant/actor/frame/token에4wheel의 steer/motor/friction을 원자적으로 stage한다.
Pre-physics ACK는 staged 상태일 뿐 적용/에너지 증거가 아니다. 같은 token 재조회는 tick하지 않는다.
물리 직전 다시 source/expiry·scope/latch를 검사한다. NoDrive setter는 지속 API이므로 post-physics
receipt의 같은 effort를 검증한 후 잔존 setter를 지운다. Receipt에는 frame·원래 begin/end·적용 effort·
Actual proof·solver coverage·generation을 남긴다. Timeout/모호한 tick은 재시도하지 않고 latch한다.

Pause는 tick 중단·pending token 폐기, reset은 잔존 입력 제거·새 physics generation/epoch·명시적 INIT다.
자동 재무장하지 않는다. Close는 sensor stop → 소유 actor 정리·설정 복원 → 소유 서버 종료다.
실패한 rig는 폐기하고 새 process/INIT로 시작한다. 진행된 CARLA physics를 rollback할 수는 없다.
`--held-steer-sleep`은 연속한 원래 보호 Actual·drive0·동일 steer·동일 양의 friction 조건에서만
반복 steer setter의 wake를 생략한다. 자연 PhysX sleep witness를 검사하며 velocity/pose를 조작하지 않는다.

## 시간 계약

| 대상 | 주기·의미 |
| --- | --- |
| world/state | synchronous=true, fixed_delta_seconds=0.01. 매 frame 새 World/ActorSnapshot |
| RGB/semantic GT | 50ms, 전용 frame5 취득. 원래 frame/simulation timestamp 유지 |
| Planner / Controller | 50/20ms. 영상마다 Controller 위상을 재시작하지 않음 |
| Zone·Steering/Brake/Drive | 원래10ms; BMS owner20ms |
| 원천·감시 | Drive30ms·skew10ms·원래 expiry, owner 실행 기회2ms/완료4ms 유지 |
| NoDrive 내부 | 320분할. World/ECU rate·freshness와 별개 |

CARLA의 원래 elapsed seconds와 ns 반올림, frame·platform·Host monotonic을 각각 기록한다.
Nominal grid·도착 시각·상수 offset으로 원래 취득을 고쳐 쓰지 않는다.
Functional clock은 simulation barrier 검사다. 느린 wall loop를 실시간 실행으로 세지 않는다.
Terminal local 응답의 `barrier + 실제 handoff 경과`도 CARLA와의 clock agreement가 아니다.
다른 Host/kernel의 uncertainty·clock mapping은 별도 미수용 경계다.

## Solver work와 단일 EV

`-StrataM7SolverWork`의 native/320분할 opt-in만 완전한 관측 work를 정산한다.
기존1q/ZOH 예측 모드는 `interval_work_valid=false`이며 실제 CARLA work로 승격하지 않는다.

- Pinned PhysX3.4 NoDrive의 각 적분 전후 raw omega·drive/brake/tire/damping·원래 solver dt,
  단일 호출·4wheel·순서/개수·연속성·setter·최종 direct getter를 검사한다.
- Motor work는 `Σ tau_drive_Nm * omega_solver_after_rad_s * dt_solver_s`인 signed discrete 값이다.
  Frame 끝 속도의 ZOH가 아니다. Friction loss와 전체 chassis/tire 기계 에너지 보존은 별도다.
- V1 모터 축 속도는 후륜 평균이다. 원래 전진 모델0..100rad/s 밖이면 EV 연결을 거부한다.
  음수 절댓값·epsilon·clamp를 허용하지 않는다. Sleeping0 work는 실제 return/wheel/hold witness가 필요하다.
- UUID/session/actor/generation/frame/ticket·Actual proof와
  `PhysX3.4.NoDrive.integrator.postOmega.v1` source를 유지한다.
  원래 `work_end_ns`와 명목 `begin+10ms`의 분수 반올림 차이를 숨기지 않는다.
- 원래320개 work를 ordinal bin의 겹침 비율로 native1ms 전기 구간에 보수 배분하고 끝 잔여도 정산한다.
  Work 합·원래 dt를 유지하며 배분을 새 wheel 취득으로 사용하지 않는다.
- 단일 EV의 `step_integrated_motion`만 호출한다. Frame checkpoint에서 중간 실패 시
  EV/actuator state·ledger를 복원하고 sensor invalid로 처리한다. 외부 physics rollback은 아니다.
- 유효 receipt 뒤 `settle_work`의 frame/ticket/end·누적 motor J·balance ACK 전 다음 stage를 금지한다.
  누락·중복·불일치는 clear/latch다. 기존 EV balance 기준0.00072J를 유지한다.

Compact 모드는 bounded raw journal에 원래320개 증거를 남기고 tick 경로의 JSON/audit를 분리한다.
Overflow·원본 회수/검사 실패는 FAIL이다. Raw/compact·wire·EV 교차 검사 후에만 수용한다.
Journal1024·receipt950 한도이며 compact runner는 abrupt client-loss와의 조합을 거부한다.
RAM journal은 crash-durable 로그가 아니다.

## 좌표계와 센서

프로젝트는 x forward/y left/z up·yaw 좌+·rear-axle center 기준이다. CARLA는 y right다.
`S=diag(1,-1,1)`로 `p_project=S*p_carla`, `R_project=S*R_carla*S`를 적용한다.
각속도 같은 axial vector는 `det(S)*S`, deg는 rad로 변환한다.
Actor origin·COM·rear axle을 같다고 가정하지 않고 검증한 geometry transform을 사용한다.

RGB는 BGRA8 원본과 AI용 RGB8 변환을 구분한다. Semantic GT는 raw class ID/label-map version을
보존하고 TRAIN_EVAL_ONLY로 분리한다. GT로 상위 요청·Actual을 생성하지 않는다.
Stream은 run/plant/frame/sensor ID로 join한다. Callback 도착 순서를 capture 순서로 가정하지 않는다.
Bounded queue·누락 mask·기한을 검사하고 가장 가까운 frame이나 restamp로 메우지 않는다.
VehicleState는 해당 snapshot의 pose/velocity/acceleration이고 wheel 센서와 별개다.
Reset 시 temporal history를 비우며 추정값을 measured Drive 입력으로 바꾸지 않는다.
통합 시험의 RGB/GT는320×240/FOV90·ego x1.6/z1.7m/pitch−8deg다. AI Reference 확정은 아니다.

## 시뮬레이션 시간 연속 실행

[ADR-0065](../archive/design-decisions.md#adr-0065)에 따라 `m7_integrated_run.py --simulation-time`을
명시적으로 선택한다. 기존 FunctionalRig·원본8-role 권한/Actual·단일 EV work 경로를 사용한다.
모든 native 제어·actuator·EV의 시각을 원본 CARLA simulation domain으로 진행하며 위
주기·source30ms·expiry·skew를 유지한다. 계산이 늦으면 실제 실행시간이 늘어난다.
대기 중 새 frame/source/권한을 만들지 않고, 과거 wall job의 재생으로 실시간 완료를 주장하지 않는다.

`--simulation-continuous --ticks 6000`은 같은 INIT/actor/generation의60s 유한 시험이다.
10s 기본 horizon은 유지하며 긴 horizon은 solver-work functional export에만 허용한다.
고정 상위 VehicleRequest로 가속·회생·제동·재출발을6회 반복하고 중간 reset/pose/속도 조작은 없다.
최종 wheel 정지와 보호 상태의 자연 차체 정지는 별도 시험·판정이다.

원본320 substep을 noncompact gzip trace로 매 frame 보존한다. 기존1024 journal을 늘리거나
덮어쓰지 않는다. 영상 metadata는 stream마다 최대1201개,60s 기대치는 RGB/GT 각1200개다.
GT는 학습/평가 전용이며 실제 원본 timestamp와 frame으로 대조한다.

Host 응답 정지는 기존10s native/receipt 한도와 supervisor로 검출한다. 긴 시험의 전체 실행
한도1200s는 시험 실행 예산이며, 짧은 시험300s·서버 준비180s·종료30s는 그대로다.
정지·누락 시 다음 tick을 막고 pause/reset/close한다. 차단을 실제 보호 제동으로 세지 않는다.
완료 physics의 work를 잃은 경우 미정산 구간도 그대로 남긴다. 유효 LocalProtection Actual로
물리를 계속 진행한 별도 시험에서만 reset 이전 자연 제동/정지를 수용한다.

실제 wall30ms·owner2ms/4ms·wall fault 후 실제 제동은 아래 별도 profile에서 검증한다.
이 profile은 해당 수치의 면제나 M6 계약 변경이 아니다. 최신 검증과 종료 범위는
[프로젝트 상태](../project-status.md)를 따른다.

## 실제 CARLA wall 연결

`--wall-native`/`-StrataM7WallNative`는 functional과 별도 opt-in이다.
같은 Linux kernel CLOCK_MONOTONIC의 새 INIT·`M7MONO01` domain만 허용한다.

1. `CarlaWork`는 원래 frame/model step/320-bin work와 **별도 applied/acquired monotonic bracket**,
   oldest dependency·적용 Power coil bits/source를 전달한다. Model-domain oldest와 wall dependency를 섞지 않는다.
2. EV는 원래 model step에서1ms 정산, actuator/ECU는 실제 wall timer에서 진행한다.
   대기 중 EV time/관측은 동결한다. 완료 work를 한 번 정산하고 늦은 도착을 새 sensor 시각으로 쓰지 않는다.
3. 공유 ABI3는 같은 build/Host·0600 파일의 magic/size/run/session/actor/generation/application/model origin과
   model step을 검사한다. ABI1/2 또는5ms/10ms 혼합 연결은 거부한다.
   방향마다3 exclusive slot·단일 reader/writer·acquire/release 소유권 교환이다. 외부 보안 채널 계약은 아니다.
4. FIFO18 native owner는 실제1ms wake마다 service한다. 과거 job catch-up 없이10owner의2ms/4ms를 독립 계측한다.
   Receipt/sensor ingress를 ECU 소비 전에 반영한다. IO는 owner mutation을 멈추지 않는다.
5. Game thread `PumpWall`만 physics를 발급한다. External stage/advance/EV ACK·legacy writer는 잠금 중 거부한다.
   다음 model step coverage와 선택 preview의 추가4ms 여유·물리 직전/직후 expiry/latch를 검사한다.
6. Fault 뒤에도 이미 완료된 work는 한 번 정산하며 ACK 전 다음 물리는 금지한다.
   정상 승인 뒤 terminal protection은 같은 session/Release·mask255·credit0·새 LocalProtection Actual을 요구한다.
   Torque는 정확히0만 허용한다. Stale wheel을 fresh로 바꾸지 않으며 normal/nonzero/regen은 원래30ms gate를 유지한다.
7. 초기화 실패에서 unavailable Steering/Brake Actual에 적용 권한을 주지 않는다.
   Pause/reset/close는 원래 clear/latch·새 INIT 경계다. Cached 조회는 acquisition을 갱신하지 않는다.
8. Wall 수신은 physics 승인 여부와 분리한다. 원래 session/Release와4ms 이내 proof를 확인하고
   원본 Actual/permission을 CAN/P05 receiver에 전달한다. 수신만으로 actuation 권한을 주지 않는다.
   수신 이력은 최대4096개의 사전 할당 원본 byte/timestamp로 기록하고 종료 후 JSON으로 회수한다.
   Physics를100ms 보류하는 fault에서도 game thread 수신은 계속된다. Game thread 자체가 멈추면
   수신을 대신 실행하거나 과거 counter를 합성하지 않는다.

Native horizon19s·원래 schedule10000 slot 이내이며 model/receipt/journal 한도는 그대로다.

### 비영상 wall5ms profile

기본 world10ms와 기능 profile은 유지한다. `--wall-step-ms 5`/`-StrataM7Wall5ms`는
nonvideo wall-native에만 허용하는 별도200Hz plant다. Controller20ms·Zone/vECU10ms·
owner2ms/4ms·Drive30ms는 그대로다. 영상 동시 사용과 functional5ms는 거부한다.
Physics/원본320-bin solver dt/EV interval/공유 identity/독립 감사가 모두 같은5ms를 사용한다.

Plant release는 `initial + (frame_index+1)×5ms`다. 예정 시각 전 실행은 없으며 늦어진
physics는 이전 work 정산과 현재 원본 Actual의 전 구간 유효성이 모두 충족될 때만 진행한다.
이것은 과거 ECU job 재생이나 source timestamp 변경이 아니다. 실제 적용→취득 종료가5ms를
넘으면 독립 감사는 더 긴 실제 구간으로 age/expiry를 검사한다. 모델 시간과 wall 시간,
실제 진행 비율을 별도로 보고한다.

Wall snapshot에서는 중복 저속 tire callback JSON만 제외한다. 실제320 substep의 force/omega/dt와
원본 solver journal, work 및 단일 EV 정산은 유지한다. NullRHI/inline render는 해당 비영상
실행 옵션이며 영상 경로의 지연 해결을 의미하지 않는다. 짧은 비영상 시험을 장시간·영상·
전체 wall fault 수용으로 확대하지 않는다. 실제 결과는 [프로젝트 상태](../project-status.md)를 따른다.

### CARLA 파생 HV 입력 예산 재조정

2026-10-29 사용자 요청에 따라 `wall5-hv50-v1`을 별도 opt-in으로 정의한다.
`--wall-native --wall-step-ms 5 --wall-hv-dependency-ms 50`에만 적용하며 기본값은30ms다.
M6 기본 동작·계약·과거 판정은 유지한다. M8 전 정리에서 문자열 치환으로 생성하던 M7
controller/owner 복사본을 공통 `DriveController`/`AsyncLeafOwner`의 명시적 설정으로 합쳤다.
`hv_dependency_age_ns` 미설정은 기존 `local_age_ns`를 따르며 명시적 값은30/50ms만 허용한다.
Drive의 `BeforeIo` 센서 관측은 wall rig에서만 선택하고 기본 `ControlTick` 순서는 유지한다.
이 설정으로 새 timestamp를 만들거나 이전 sample의 만료 검사를 생략하지 않는다.

| 입력/감시 | 기존 | 새 profile | 이유 |
| --- | --- | --- | --- |
| Wheel 취득/source 및 input age | 30ms | 30ms | 차량 운동 관측의 직접 freshness |
| HV 취득/source age | 30ms | 30ms | 새 물리 work 취득 없이 전압 관측 갱신 금지 |
| HV 계산의 oldest input dependency age | 30ms | **50ms** | 30ms 직접 원천 예산에 한 Controller 주기20ms의 계산·전달 여유를 별도 배정 |
| Local wheel/HV source skew | 20ms | 20ms | 두 관측의 시간 정렬 유지 |
| Actual·명령·부모 expiry·RunLease·owner2ms/4ms | 기존값 | 동일 | 권한과 실행 감시를 HV 계산 예산과 분리 |

50ms는 CARLA용 engineering allocation이며 OEM calibration/차량 전체 안전 한계가 아니다.
입력의 원래 source·dependency·sequence는 보존하고, 이전 sample의 만료를 새 sample로 숨기지
않는다. `age == limit`은 허용, 초과는 기존 보호 latch/새 INIT 규칙을 따른다.
100ms physics loss는 이 예산으로 정상 처리하지 않는다. 영상·M6·기능 simulation profile에는
적용하지 않는다. 전체 실시간 성공을 위해 다른 기준을 연쇄적으로 늘리지 않는다.

새 실행 전 고정한 검증은 source30ms/dependency50ms 경계 및+1ns 거부, wheel/M6 기존30ms,
cached identity 불변·늦은 새 입력의 fault 은폐 거부, 정상900구간2회 및100ms gap/명시적
보호 각1회다. 원본 CAN/work·HV 시각·owner timing·서버 종료를 모두 검사하며 과거 실패의
재채점으로 PASS를 만들지 않는다. 장시간·고속·영상·실차 수용은 이 시험 범위 밖이다.
