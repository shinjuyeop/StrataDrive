# M7 종료·보호 정지·clock 일괄 검증

2026-10-28. **전체 M7 NOT CLOSED**. 고정 시나리오의 자연 보호 정지와 client-loss 이후
SIGINT 종료 문제를 각각 수정·검증했다. 정상 wall owner/clock agreement와 wall fault 이후
CARLA 연속 보호 제동은 OPEN이다. M6 코드·계약·결과·수용 판정은 변경하지 않았다.

## 실행 분모와 판정

| 실행 | 결과 | 범위 |
| --- | --- | --- |
| 수정 전 `client-loss-before` | FAIL | 정상199receipt/정산 후 exit73. SIGINT30s 초과, 강제−9. 원본·gdb 진단 보존 |
| 최초 `suite` | 5 PASS / 1 FAIL | client-loss, camera, 영상 client-loss, loading-abort, wall-gap 통과. 보호 정지는279receipt 뒤 zero-work witness 조건에 걸려 중단 |
| ABI2 `suite-v2` | 6/6 PASS_CASE_ONLY | 위6개 전체 재실행, 독립 Actual/solver/EV·정지·종료·clock 감사 포함 |
| INIT 이력 초기화 `suite-v3` | 3/3 PASS_CASE_ONLY | 보호400구간 및 새 INIT, zero-only13receipt, 기본 비활성2 lifecycle 회귀 |
| CTest 일반 / ASan·UBSan | 각각89/89 | M7 관련 전체 검사, 신규 hold3개 포함. 전체 UE sanitizer나 새 TSan 실행 아님 |

`server-*.json`의 status/argv/binary hash와 각 result/audit가 판정 원본이다. 이 분모는 과거
실행이나 서로 다른 binary의 반복을 합쳐 “한 번에 전부 성공”으로 표시하지 않는다.
초기 C++ 검사 compile 실패(unused helper)와 수정 후 로그도 보존했다. 보조 비교 script의
첫 실행은 괄호 문법 오류로 실패했고 수정한 script의 결과만 `physics-comparison.json`이다.

## 원인과 수정 경계

**client-loss:** pinned CarlaEngine의 primary/secondary synchronous wait가 engine exit latch를
확인하지 않았다. probe process의 실제 exit73은 finally/pause/reset/close/settings 복원을 건너뛴다.
서버 SIGINT 후 game thread가 wait를 취소하고 adapter 입력을 지우며 world의 physics 등록을
막는다. UWorld tick-start delegate에서 단순 return하는 것만으로는 이후 physics를 막지 못한다.
post-tick snapshot/receipt도 발행하지 않는다. tick cue나 callback을 인위적으로 실행하지 않는다.
수정 전 gdb의 불완전 심볼 stack을 특정 함수의 완전한 역추적으로 과장하지 않는다.

v2에서 영상 없는 client-loss는 **1.917749s**, 영상 포함은 **1.967951s**에 exit130으로 종료했다.
cancel 로그의 frame은 각각243/247로 단절 당시와 같았다. loading-abort는3.772354s에 종료했다.
원래30s 상한은 불변이다. 이 시험은 사용자 SIGINT에 대한 종료 응답이며, 단절 자체의 자동 물리
보호 제동이나 renderer의 모든 crash 원인 해결이 아니다.

**자연 정지:** PhysX NoDrive는 비영 steering을 유한 입력으로 간주해 sleeping actor를 깨운다.
원래 보호 run도 index278에서 스스로 잠들었지만 동일한 steer hold 때문에 다음 frame에 깨어났다.
명시적 `--held-steer-sleep`에서 직전/현재 보호 Actual·drive0·완전히 같은 steer/양의 friction
조건을 모두 충족할 때만 이 steer wake 조건을 생략한다. drive와 외부 접촉의 wake는 유지한다.
force sleep·pose/velocity setter·epsilon·음수 clamp는 사용하지 않는다. sleep은 PhysX 모델의
상태이며 실차/OEM 정지나 전체 ODD의 수학적 보증으로 확대하지 않는다.

최초 수정은 기존 sleeping work witness의 steer0 조건을 만족하지 않아 index279에서 fail-closed했다.
ABI2는 명시적인 `protected_steer_hold`를 기록한다. server/solver flag와 이전 frame의 scope,
원래 보호 Actual, 정확히 같은 네 바퀴 effort를 독립 감사한다. ABI1 과거 자료의 steer0 규칙은
유지한다. ABI2의 보호 run은 **400receipt/400정산, 보호200구간, 자연 sleep index278부터122구간
body/wheel exact0, 마지막100구간 pose/quaternion 동일**이다. v3도 같은 결과를 확인했다.
잔류 속도1e-30, pose 변조, hold 누락, 이전 effort·보호 변조5종을 거부했다.

v3의 유일한 추가 서버 변경은 bind 시 LastEffort/보호 hold 이력을 명시적으로 초기화하고 binding에
그 상태를 노출한 것이다. pause/reset/close 후 같은 서버에서 새 ego/INIT, 빈 hold 이력,
새 stage 없는 advance 거부, 재생성 ego 종료를 확인했다. v2의6-case 판정을 최종 binary에서
모두 다시 실행했다고 표기하지 않는다.

## 회귀와 clock 결과

[물리 대조](physics-comparison.json): 기존 정상 driving-b와 v2 camera-a의900개 physics는
세션별 generation만 제외하고 정확히 같다. 모든 원래 Actual 값·320-step solver trace·signed motor
work도 같았다. 기존 보호 run과 v2는 index0..278의 physics/solver가 같고,279부터 의도한 sleep
유지로 달라진다.400개 Actual 값 및 motor work는 모두 같다. EV의 마지막 binary64 반올림 차이를
완전 일치로 주장하지 않으며 원래0.00072J 장부 허용 기준으로 독립 검증한다.
RGB/GT는 각각180개, 기존 frame/source/identity와 TRAIN_EVAL_ONLY 분리를 검증했다.

새 `physics_acquisition_begin_ns/end_ns`는 같은 Host CLOCK_MONOTONIC의 실제 post-physics
취득 bracket이다. cached receipt 조회 때 재발행하지 않고 simulation/CAN 시각도 바꾸지 않는다.
정상 camera run에서 의도적 index150/250ms pause를 제외한899개 중629개는 취득 bracket 시작→
다음 native 처리 완료가30ms를 초과했고 최대171.556438ms였다.899개 owner 입력 공백 모두2ms를
초과했으며 최대175.123817ms였다. 취득 bracket 자체 최대22.285211ms, 고정 offset 교집합 없음.
이는 원래 CAN source-age나 개별 job4ms latency를 직접 측정한 수치가 아니며, JSON/감사/파일
기록을 포함한 진단 loop의 clock 연결 장애 증거다. **정상 wall runtime/clock mapping 미수용**이다.

원래 native clock/authority에 단순 offset을 더하거나 terminal local 보호 Actual을 서버에 넘기지
않는다. 다음 필수 묶음은 실제 wall owner/수신 분리, 비동기 trace와 완전 work 증거 보존,
원천 clock agreement/uncertainty, in-flight fault containment와 CARLA 연속 보호 제동이다.
기존 최소 command expiry 여유1ns를 wall jitter budget으로 사용할 수 없다.

## 재현 및 보존

설치/실행 명령은 [도구 설명](../../../../../tools/carla/m7_nodrive/README.md), 판정 계약은
[ICD](../../../../icd/carla_plant_adapter.md), gate는 [종료 검토](../../../../m7_exit_review.md)를 따른다.
CARLA294096e/UE4.26.2 pin, Town03_Opt/mkz_2020/ClearNoon, fixed seed, world10ms/영상50ms/
Controller20ms/Zone·leaf10ms/Drive30ms, V1 계수와320 내부 분할은 유지했다.

`solver-build*/manifest.json`은 원본 source/archive와 생성물/compiler/module hash를 기록한다.
원본 UE/PhysX source·static archive는 수정하지 않았고, 외부 생성 copy/module만 설치했다.
UE/CARLA 전체 proprietary source·binary와 owner key는 저장소에 넣지 않는다. observer ABI1
중간 실패와 ABI2 최종 module의 manifest, 자체 header/observer source는 각각 보존한다.

- v2 CARLA module: `c23dbbe3177a51e0652e38d3282ce63f253220a7e03442fa59bd2383510f3f6c`
- v3 CARLA module: `f2b169da12b58fa17f6ba629e1ee2a78562aa3800bc009bf73bfe39548cae56e`
- ABI2 PhysXVehicles module: `f036d6c03ac51347d076e64dc827787f693685da5451cd552cde536227a6b3ce`
- 실행 native binary(기존과 동일): `5810f0f30e0caa67bda733176bad8e6260c2574654279c69567078a7e168bf52`

`archive-*.json`은 lossless gzip 전 원본 SHA256/크기이며 `SHA256SUMS`는 보존 파일 hash다.
`suite*/sources`와 각 `*-runtime/probe`는 실제 실행한 project Python source다. 재감사는 저장소
root에서 `python3 tests/integration/carla/audit_m7_closeout.py <archived-case-dir> --kind
sleep|client-loss|clock --output <new-json>`로 실행한다. `audit_m7_1r_work.py`와 보호/정상 감사도
같은 case directory를 받는다. 원래 실패 trace/로그는 수정하지 않는다.
