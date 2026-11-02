# M8 추진 배분 포화와 참조 필요조건

2026-11-01. **PASS_PROPULSION_FEEDBACK_FIXED_S03_SIMULATION_ONLY**.
선택형 v2의 양수 추진 적분 억제, 관성 토크 필요조건, 고정 Town06 S03 v2의
simulation-time 기능 검증이다. 전체 Reference/M8, 동적 가용력·경사/도로 저항,
제동 측 anti-windup, 실제 fault 정지·NormalStop/HV-off, wall/Target 수용은 아니다.

## 변경과 고정 조건

성공한 Central 배분은 epoch/parent request/selection 시각·요청 acceleration·요청/선택
양수 토크를 남긴다. `SpeedRequest(..., true)`는 정확히 직전 요청의 이력을 받아
포화 중 양수 error 적분을 보류한다. 첫 release는 보수적 보류다. 누락/잘못된
parent/epoch/time/값은 latch한다. 선택 이력은 Actual/permission이 아니며 wheel30ms,
request30ms/input60ms, pose와 child expiry, 가속도·slew·PI 계수는 그대로다.
CAN 양자화 전 토크를 사용해 단순 양자화로 포화를 만들지 않는다.

`--propulsion-aware` 및 native `_AW` header로 선택한다. 기존 flag 없는 v1과 증거는
그대로다. 원본 v1 SHA256은 `181297fb101d0f7dc69222489956a3bdcc701924556fa2210e4ff5705975e858`.
별도 모델 v2 SHA256은 `b0f968a9bd4d8940ff245d454462f7041aecc9006080764da5bcd067c7b335ed`.
실제 두 실행의 native binary는 동일하며 SHA256은
`d30dd32f834ff7ff28cb1989e357c14e57cad7c682f508cf23580ac4e656d82c`다.

20s startup250.867Nm는 기존1696kg/.355m/300Nm 안이다. S03 v1의10s startup501.733Nm는
runtime/output 생성과 서버 기동 전에 거절했다([원본 CLI 판정](S03-v1-preflight-reject.json)).
이는 필요조건이며 동적 추종 보장은 아니다. 경로·marker·target·평가 window와 기존
오차 기준은 [사전 protocol](../../propulsion-saturation-protocol.md)을 따른다.

## 결과

| 검사 | 결과 |
| --- | --- |
| v2 Python/C++ 공통7224 events | Release·ASan/UBSan PASS, 실제 최대 수치 차이0 |
| 외부 flag=false | 원본 v1과7224 events 비교 PASS |
| 합성 plant 각2500 steps | 각 sensor replay의 C++ 동등성 PASS |
| C++ unit/logical 회귀 | 1212/1212 + 새 CTest 동등성1/1 |
| ASan/UBSan 영향 범위 | 75/75 |
| Python unit | 233/233 |
| Native route/header/horizon CLI | 15/15, S03_AW 거절 포함 |
| 원본 M8 evidence | 이전866개와 v1 model hash 불변 |
| 실제 S03 | 8000 physics/8000 EV settlements,3960 controls,7919 normal intervals |
| 선택 이력/독립 PI | 7920 allocations,3960 controls 모두 일치; 양수 적분 보류39회 |
| 증거 손상 | 추진12종, 경로28종, solver11종, EV7종 거절 |
| 실제 pose-stale | 200 physics/199 settlements 후 다음 tick 차단 |
| 서버 종료 | 두 실행 모두130, 강제 종료 없음 |

합성 plant는 target1m/s, 가용 가속도0–15s .12m/s²·이후1.5m/s²,
저항.08*v,20ms Euler로 고정했다. v1/v2 최대 integral은1.04203/0.079993,
최대 속도1.69332/0.999992m/s, 최종 속도1.000378/0.999992m/s다.
이 결과를 CARLA 추종 오차의 개선율로 해석하지 않는다.

실제 S03의30/20km/h plateau body 최대오차는0.077184/0.027828km/h,
양수 목표 최대 overspeed3.483045%, stop window 오차0이다.
원본 active-route20Hz 표본1333개, 누락0, 횡오차 P95 0.034105m,
heading P95 0.534945deg다.230m 감속 요청37.8s, 곡선 진입45.388s의
속도19.875696km/h,380m 정지 요청63.32s,395m 완료66.688s다.
원본 wire/Actual·whole interval·solver work/단일 EV 정산도 통과했다.
PI saturation 입력46회에는 첫 bootstrap이 포함된다. 실제 추가 양수 적분 보류는39회다.
이 경로에서 모든 성능이 기존 모드보다 개선됐다는 주장은 하지 않는다.
[그림](S03.png), [route](S03-route.json), [selection/PI·손상 검사](S03-saturation.json),
[work/EV](S03-work.json), [전체 summary](results-summary.json)를 참조한다.

pose-stale의 마지막 물리 구간1개는 EV 미정산 상태다. 최종 body 속도는 약0.429m/s이며
다음 tick 차단을 실제 제동 정지나 HV-off로 세지 않는다.
[고장 route](pose-stale-route.json)와 [work/정산 분모](pose-stale-work.json)를 따른다.
기존 UE renderer/GC 종료 실패의 원인 해결도 주장하지 않는다.

## 실패·원본 보관

`validation/targeted-01.txt`의 최초 unit FAIL을 보존한다. 음수 error에서 적분이 감소하는지
검사하면서 임의로 `integral<0.2`를 기대해 실제0.824에서 실패했다. 감소 전/후 비교로
시험을 고쳤으며 controller 식을 변경하지 않았다. 재빌드 후75/75 통과했다.
`partial-oracle-01`은 첫1000개 행을 사용한 감사 개발 확인이며 전체 주행 수용 분모가 아니다.
기존 S03 v1 성능 FAIL은 이전 `m8_reference` evidence에 그대로 있다.

`S03/`, `pose-stale/`는 original compressed trace/result/events/config,
`runtime-*/probe`는 실제 실행 binary와 child Python snapshot이다.
`server-*.json`은 argv/실행 artifact hash/종료 상태를 기록한다.
`equivalence-*`에는 두 독립 구현의 입력·출력과 합성 plant를 보존했다.
`source-implementation.tar.gz`는 작업 중 snapshot, `source-final.tar.gz`와
`source-final-manifest.json`은 최종 source·문서 snapshot이다. source archive는
기존 evidence/build/runtime를 제외하며 dirty tree 기반이다. 커밋하거나 push하지 않았다.
`SHA256SUMS`는 이 디렉터리의 보관 파일을 검증한다.

## 재현

저장소 root에서 기존 source CARLA/SDK와 NoDrive fixture를 사용한다.
새 runtime/output 경로를 선택하고 기존 증거를 덮어쓰지 않는다.

```bash
ctest --test-dir build/m7-functional -L 'unit|integration.logical' --output-on-failure
python3 -m unittest discover -s tests/unit -p '*_test.py'
python3 tests/integration/longitudinal/check_propulsion_pi.py \
  build/m7-functional/speed_pi_replay --output build/m8-saturation-replay/model
python3 tests/integration/carla/m7_1o_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --runtime build/m8-saturation-replay/runtime-S03 --output build/m8-saturation-replay/S03 \
  --native-actual build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --vehicle-substeps 320 --solver-work --held-steer-sleep --simulation-continuous \
  --route-profile tests/integration/carla/scenarios/m8_combined_v2.json \
  --route-startup-seconds 600 --ticks 8000 --propulsion-aware
python3 tests/integration/carla/audit_m8_route.py build/m8-saturation-replay/S03 \
  --case nominal --output build/m8-saturation-replay/route.json
python3 tests/integration/carla/audit_m8_saturation.py build/m8-saturation-replay/S03 \
  --mutations --output build/m8-saturation-replay/saturation.json
python3 tests/integration/carla/audit_m7_1r_work.py build/m8-saturation-replay/S03 \
  --output build/m8-saturation-replay/work.json
```

고장 시험은 새 runtime/output으로 같은 runner에 `--native-fault pose-stale`를 추가하고
route 감사에 `--case pose-stale`를 사용한다. 원본 argc/환경/로그는 각 validation JSON을 따른다.
