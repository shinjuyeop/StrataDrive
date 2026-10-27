# M7-1k — 실제 UE NoDrive 최소 서버 경계

2026-10-26 KST. [준비 baseline](../m7_carla_1j_render_followup/README.md)의 다음 단계다.
**실제 서버의0 effort 진단 포트 한정 검증 완료, 정상 주행은 BLOCKED**다.
M6 구현·계약·종료 판정, 원래 요구 주기/freshness 및 과거 evidence는 변경하지 않았다.

## 구현과 환경

[설치 도구/구체 RPC 계약](../../../../tools/carla/m7_nodrive/README.md),
[ICD v8](../../../icd/carla_plant_adapter.md)을 따른다.
고정 CARLA commit `294096eb1c38eabf246e4f3a9cdab704e33a7f4c`,
UE4.26.2 `e9d9e60c85f643e10eeb03f42f61554d18dcb30f`다.
관측 Client/Server identity는 둘 다 **`294096e-dirty`**이며 wheel 배포 이름0.9.16과 구분한다.
관측 identity가 같아도 서로 다른 확장 빌드를 구분하려면 아래 source/artifact hash를 사용한다.

`UM7NoDriveMovement`는 기존4W component를 상속하고 명시적으로 bind한 ego만 실제
`PxVehicleNoDrive`로 전환한다. 그 ego에서는 stock engine/gear/control 처리를 건너뛴다.
원래 receiver/codec12개의24개 hpp/cpp를 byte 그대로 별도 `M7Native` UE 모듈로 컴파일했다.
UE clang10/libc++ C++17을 사용하며 독립 public SDK의 clang14 바이너리를 링크하지 않았다.
engine tracked source 변경은0이다. 직접 extension의 sanitizer 시험은 **NOT RUN**이다.

원래 Client와 module은 [별도 백업](baseline-backup.json)에 보존했다.
공식 BuildPythonAPI 스크립트가 build venv에도 새 wheel을 설치하므로 빌드 후 원래 wheel로
복원했다. [artifact 검사](artifacts.json)는 기존 Client의 설치 `.so`가 백업 wheel과 byte 일치함을
확인한다. 확장 Client는 `/d/shin/stratadrive-tools/m7-source/m7-nodrive-venv`에 별도 설치했다.
실행 flag와 외부 owner key를 함께 요구하며 키 값은 evidence/저장소에 기록하지 않았다.
설치된52개 파일과 원본24개 native 소스의 hash를 확인하고 installer 재실행의 동일 content를 확인했다.

## 빌드·실패 기록

[전체 시도별 요약/원본 로그 위치·hash](builds.json):

| 시도 | 실제 결과 |
| --- | --- |
| Server build01 | exit2 FAIL. unity build에서 원래 codec의 익명 `Field` 타입 충돌. batch lambda의 raw vector와 일반 ResponseError 반환 형식 충돌 |
| Server build02 | exit2 FAIL. 전체 Carla module의 unity를 끄자 기존 소스의 누락 include/로그 선언 의존성 오류 발생. 이 소스들을 정리하지 않고 원래 unity 방식을 유지하기로 결정 |
| Server build03 | exit0. 원본 native 코드만 별도 non-unity 모듈로 분리. batch는 원래 vector 응답 형식으로 거부. [설치 소스 hash](source-build03.json) |
| Client build01 | exit0. 별도 `m7_nodrive` JSON-string RPC와 Python binding 추가. 이후 서버 진단 확장에서도 이 Client 사용 |
| Server build04 | exit0. physics generation 감시와 실제 reset/latch 추가. [소스 hash](source-build04.json) |
| Server build05 | exit0. route별 거부 count와 registry 종료 readback 추가. [최종 소스 hash/130개 RPC 결정](source-build05.json) |

원본 compiler 로그는 외부 경로에 남겼다. `builds.json`의 진단·hash는 실패를 보존하며
성공 뒤 옛 FAIL을 PASS로 바꾸지 않는다. 기본/새 module의 dependency는 engine binary 경로를
포함해 확인했다. 그 경로 없이 `.so`에 단독 ldd를 실행하면 Core module이 not found였으며,
engine 경로를 지정한 검사와 실제 로딩에서 해소됐다. warnings0 또는 전체 UE 안전성을 주장하지 않는다.
중간 빌드03/04의 binary hash는 별도 채집하지 않았으며 최종05의 binary/wheel hash는
[artifacts.json](artifacts.json)에 고정했다.

## 실제 실행

모두 전용 localhost2200, `Town03_Opt`, `vehicle.lincoln.mkz_2020`, traffic/TM 없음이다.
CARLA 시작 INI DisableRendering과 Episode no_rendering을 구분한다. 이번 센서/렌더링 시험은 없다.
NoDrive ego는 **physics enabled**다.0 effort에서도 중력·접촉에 의한 운동은 가능하며
이 짧은 실행은 정지 안정성·보호 Brake hold 시험이 아니다.

| 실행 | 결과/근거 |
| --- | --- |
| Server01 / attempt01 | [FAIL 원본](attempt01/result.json). NoDrive bind와23개 검사를 통과했지만 `apply_batch_sync(..., True)`의 내부 별도 tick 거부 예외를 harness가 예상하지 못해 중단. receipt0. 자기 ego 종료·설정 복원 확인 |
| Server01 / attempt02 | [한정 PASS](attempt02/result.json):150개 검사(반복 포함)·13개10ms receipt. batch 제어 거부와 추가 tick 거부를 분리. [독립 audit](audit02.json) 손상8/8 거부. 이 버전에는 실제 physics reset 시험이 없음 |
| Server02 / attempt03 | [한정 PASS](attempt03/result.json):154개 검사·13개 receipt, 실제 physics reset 후 generation 증가·pending 폐기·자동 재무장 금지. [audit](audit03.json) 손상8/8 거부 |
| Server03 / **최종 attempt04** | [한정 PASS](attempt04/result.json):**156개 검사(반복 포함)·13개 receipt/2개 session**. 별도 client의 직접 control/velocity/transform/physics 요청과 batch/tick·설정/reload 거부. [실행한 harness](harness-attempt04.py), [독립 audit](audit04.json) 손상8/8 거부 |
| Server04 / default-off | flag 없이 [확장 RPC disabled](disabled.json). 기존 source smoke로 [physics-disabled ego 정상/예외2/2·102개10ms 샘플](default-off/result.json), [독립 audit](default-off-audit.json) 확인. 정상 stock 주행 수용을 뜻하지 않음 |

서버 [01](server01.json)/[02](server02.json)/[03](server03.json)/[04](server04-default-off.json)는
모두 actor·설정 정리 후 소유 PID에 SIGINT를 보내 tool exit130으로 종료했다. exit0이라고
기록하지 않는다. 전용2200/2201/2202 listen 잔존0을 확인했다. completion 기록 시각은 실제
종료 관측을 정리한 시각이며 정밀 wall benchmark가 아니다. 원본 server log 위치/hash를
각 JSON에 남겼다. 기존 Vulkan unknown-vendor handled ensure와 content 경고는 계속 보였고
새 fatal/SIGSEGV는 이 짧은 실행에서 관측하지 않았다. 원래 renderer crash 원인은 **OPEN**이다.

## 최종 확인 범위

합성 fixture는 세 actuator의 원래 CAN/P05 Actual bytes를 생성한다. server는 자기 선언
`validated=true`나 scalar effort를 받지 않는다. 그러나 이것은 실제8-role authority가 아니다.
application epoch 불일치 시험은 현재 session+1 fixture이며, 새 INIT 뒤 이전 session ticket
거부도 별도 확인했다. 이를 실제 old native Actual 전송/재가입 전체 시험으로 확대하지 않는다.

- CRC·잘못된 epoch/sequence 재전송·future source·누락·whole-interval age30ms·exclusive expiry 거부.
- nonzero rad/Nm/Pa 거부.0 Actual만 stage하고 ACK 중에는 frame/physics 진행 없음.
- frame/ticket single-use, 잘못된 ticket·중복 stage/tick 거부, 조회는 재적용 없음.
- 실제 post-physics frame·simulation begin/end와 원래 source/oldest/expiry/CAN bytes 보존.
- final server의 `tick_cue`2회, `set_episode_settings`1, `load_new_episode`1, batch2,
  직접 control/target_velocity/transform/simulate_physics 각각1회 거부를 route별 관측.
- pause에서 pending 폐기, close로 자기 ego 종료, 새 session/INIT. 실제 reset에서 generation1→2,
  pending 폐기·latch·setter0 유지·자동 재무장 없음.
- setter readback은 적용 demand이며 새 Actual로 보고하지 않음. raw signed ω를 보정하지 않음.
  최종52개 wheel endpoint 샘플의 음수는0이지만 .12s+.01s 진단이므로 평지 문제 해결 근거가 아님.

[감사 도구](../../../../tests/integration/carla/audit_m7_1k_server_probe.py)는 원래 payload CRC와
metadata를 별도로 해석하고 frame/구간·원본 보존·cleanup·receipt scope를 확인한다.
손상된 frame/source byte/expiry/work claim/epoch/중복/NaN wheel/잔존 setter8종을 거부한다.
`interval_work_valid=false`, solver substep work observation도 false다. energy owner가 없는
0 effort 진단만 다음 관측 tick을 허용한다. 정상 주행의 incomplete work→latch 계약을 바꾸지 않는다.

## 남은 gate와 다음 작업

readback은 wheel order0/1/2/3의 bone FL/FR/RL/RR, radius0.355m, 각 max brake800Nm,
COM 기준 wheel x/y offset을 제공한다. 단순 x 차로 L≈2.86047m, front y 차로 W≈1.59292m다.
이는 해당 asset의 **readback**이며 차량 기준점/실제 조향 부호·잔차·유압 보정 완료가 아니다.
800Nm만으로 Pa→Nm을 식별하지 않았다. pressure table·gain·epsilon/clamp를 임의 채택하지 않았다.

1. wheel/COM/actor/rear-axle 좌표와 순서 검증, 근거 있는 brake 모델/보정 artifact 선정.
2. 그 artifact가 준비되면 nonzero steering/drive/friction을 작은 격리 시험으로 적용하고 보호 Brake Actual과 raw wheel을 확인.
3. 실제 Central→Zone→vECU→Actual 반환의 trusted source/parent/expiry와 full interval을 이 서버 포트에 연결. 합성 fixture를 정상 경로로 사용하지 않음.
4. solver 구간 work·단일 EV 연결과 외부 Actual 응답 budget, transport timeout 실주입·ambiguity 복구, native wall timing을 각각 검증.

실제8-role normal driving·pressure calibration·구간 work/EV·wall deadline·렌더링 안정성·Jetson/AI는
**NOT RUN/미수용**이다. 센서 timestamp restamp, freshness 완화, command 우회, M6 수치 변경은 없다.
geometry/brake 모델 작업에는 착수 가능하지만 정상 주행 gate는 계속 **BLOCKED**다.
