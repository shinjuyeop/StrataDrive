# M7-1p — 직접 solver wheel의 native 센서/Actual 반환

2026-10-27. **sensor-only 반환 한정 검증 완료. 정상 native→CARLA actuation/energy/wall 수용은 미완료.**
기준 commit은 `3fa51f3dd05fc5eacf704ba155dd56504b10e32a`(M7-1o)다.
M6 코드/통신·안전 계약/수치/판정과 과거 frozen evidence는 변경하지 않았다.

## 연결한 범위

`post-physics mWheelSpeeds.direct.v1 → local receipt gate → 기존 M7-1g native shadow →
Drive 센서 → vECU CAN/P05 → Rear → Central Actual 반환`이다. CARLA에는 기존 격리 합성
Actual만 적용한다. native 반환 torque/명령을 CARLA로 보내거나 정상 권한을 부여하지 않는다.
native actuator/전기는 stationary fixture이며 `simple_vehicle=false`라 차량 운동은 중복 적분하지 않는다.
그 fixture의 SOC/회생/기계 에너지를 CARLA 결과로 주장하지 않는다. `interval_work_valid=false`다.

새 [local bridge](../../../../tests/integration/carla/m7_1p_bridge.py)는 bind의 run/session/actor/generation/
model/profile을 고정한다.4wheel source ID·순서, frame/ticket/구간 연속성, 완료/clear를 검사하고,
CARLA snapshot의 같은 frame/원래 simulation-end timestamp와 교차 확인한다. 공개 getter fallback,
v/r 재구성, abs/clamp/epsilon, timestamp 재발급은 없다. ns는 원래 seconds를 반올림한다.
native의 fresh-process fixture scope `(1,42,7)`/functional clock과 서버 synthetic Actual의
logical-frame 시각/권한은 서로 다르다. local binding이 원천 provenance를 보존하며, 이것이
실제8-role full Actual authority의 서버 전달 계약을 완성했다는 뜻은 아니다.

기존 native 실행 파일/코드는 변경하지 않았다. Controller20ms·Zone/vECU10ms·Drive30ms,
rear 평균·CAN0.01rad/s 양자화·자기 acquisition 이후 job에만 입력하는 pending 처리를 유지한다.
한 sample의 값/시각을 native에 전달하고8-role service barrier를 받아야 다음 진단 tick으로 간다.
pause/reset/close는 bridge를 폐기한다. 새 binding은 별도 process와 실제 INIT를 거친다.
초기 미무장 관측도 모두 보존하며 startup frame을 분모에서 버리지 않았다.

## 실제 새 서버 실행

모두 pinned UE4.26.2/CARLA0.9.16 source binary, Town03_Opt/mkz_2020/V1/no-render,
world10ms, native sensor shadow다. engine/server/client 재빌드나 계수 변경은 없다.
실제 argv/바이너리 및 실행 script hash/종료 상태는 각 `server-*.json`에 있다.

| 실행 | 관측 / native barrier / Actual 반환 | 결과 |
| --- | --- | --- |
| [live320a](live320a/result.json), 최초 step | 1,394 / 1,393 / 전체 수용 미집계 | FAIL: frame1421 receipt 시 Python snapshot은1420. 당시 cleanup latch 검사도 FAIL. 아래에 보존 |
| [live320b](audit-live320b.json), 수정 후 step | 1,621 / 1,621 / 1,609 | 직접 solver 후륜 음수0, armed1,387, 다음 구간 끝 age 최대20ms, 최대 CAN 양자화 차이0.00499956rad/s |
| [live320response](audit-live320response.json), 기존 response 모델 입력 | 1,621 / 1,621 / 1,609 | 직접 solver 후륜 음수0, armed1,387, 다음 구간 끝 age 최대20ms, 최대 CAN 양자화 차이0.00499728rad/s |
| [live20](audit-live20.json), 실제 음수 대조 | 102 / 101 / 97 | runtime FAIL 유지. launch 첫 tick 음수로 native exit1·다음 frame 차단·backend pause/latch/clear·cached 재사용 거부 확인 |
| [snapshot-loss](audit-snapshot-loss.json) / [최종 반복](audit-snapshot-loss-final.json), 전달 누락 주입 | 각200 / 199 / 195 | runtime FAIL 유지.200번째 snapshot을 local bridge에서 전달하지 않음. native에 입력하지 않고 다음 frame 차단·pause/latch/clear·cached 재사용 거부 확인 |

완료320 실행 각각 정지 hold/출발/음수 motor 감속/마찰 정지/release/좌우 조향을 포함하며,
6개 물리 관측 조건과 기존 Actual/P05/expiry/single writer 검사가 통과했다. 각58/62개 runtime 검사에는
반복 항목이 있다. native 반환 초기 각 actor4개 부재는 INIT 전 과정으로 보존한다. 원래 sensor
취득값은 그대로이고 반환값만 기존 CAN 분해능으로 양자화된다. scope는 기능상 sensor 반환이다.
두 실행 모두250ms wall 대기3회에 frame/source가 유지됐다. 실제 backend pause 및 좌우 physics reset
이후 bridge 폐기/기존 receipt 거부, 다음 binding의 INIT/Release/credit을 확인했다.

20분할의 기존 −0.256rad/s 부근 실제 음수는 조용히 제외하지 않고 실패 receipt에 남겼다.
snapshot-loss는 network 전체 장애가 아니라 **local 전달 누락 주입**이다.200번째 receipt가 있어도
직전 frame의 snapshot 객체/시각을 그대로 보유하고10s 수신 한도 후 거부했다. 이10s는 functional
시험의 wall timeout이며30ms freshness나2/4ms native deadline 완화가 아니다.
두 fault의 마지막 frame은250ms containment 대기 전후 동일하다. 이후 tick/advance 재시도는 없다.
6개 서버 모두 actor 정리/설정 복원 후 소유 process group SIGINT130, forced kill 없음이다.

## 발견한 실패와 수정

`live320a`는 서버 post-physics receipt와 비동기 episode stream의 도착 순서를 같다고 가정해
FAIL했다. 서버 frame1421에 대해 client snapshot1420을 관측했다. 서버 tick은 추가하지 않고
같은 frame의 snapshot만 조회해 기다리도록 수정했다. 미래/누락 frame은 계속 거부한다.
정상320 후속 두 실행에서는 실제 추가 polling이 필요하지 않았다. 지연2회 후 같은 frame 전달,
영구 누락/건너뛴 frame 거부는 별도 controlled replay로 확인했다.

당시 snapshot 검사 예외가 `NativeBridge.observe()` 밖에서 발생해 bridge latch가 세워지지 않았다.
cleanup의 cached-receipt 거부 검사에서 그 원천이 native에 수용돼 검사 FAIL이 났다. 다음 CARLA
tick은 진행하지 않았으며 해당 FAIL을 고치지 않는다. 이제 snapshot 검사 포함 모든 예외에서
bridge/gate를 즉시 latch한다. 수정 후 실제 snapshot-loss 시험은 native 입력/다음 tick 없이
cached-receipt 재수용을 거부했다. 최종 정리 단계는 fixture/RPC/receipt 선행 검사 예외도
무조건 latch하며, 이 보강 후 누락 주입 반복도 같은 결과였다. transport 전체 timeout/강제 native 정지 시험으로 확대 해석하지 않는다.

첫 `ctest -L m7.functional` 호출은0개 선택으로 **NOT RUN**이었다. 로그와 빈 XML을 보존한다.
실제 test 이름 `^M7`로 선택한 후 Normal/ASan 각각60/60을 실행했다. 기존 label 설정은 변경하지 않았다.

## 독립 검증과 재현

- [최종 Normal replay](replay-normal-v2/result.json) / [ASan replay](replay-asan-v2/result.json):
  frozen M7-1o320의1,621개 receipt를 원래 native executable에 공급. 각 세션 INIT/arm/반환 확인.
  metadata/원천/시각/세대/순서/부재/비유한/범위/−1e−9 음수 등29종 거부 및 latch,
  valid receipt 중복 거부, 공개 getter를−999로 바꿔도 직접 solver만 사용하는 경계를 확인했다.
  이는 새 CARLA 실행 수에 더하지 않는다. frozen replay의 최초 timestamp anchor는 기록에서 취득하고,
  live는 별도 world snapshot으로 anchor한다. 중간 replay 결과도 덮어쓰지 않았다.
- [Normal60](native-normal-final.xml) / [ASan60](native-asan-final.xml): 기존 M7 ingress/freshness/
  effort/functional/wheel/external 논리 검사. M6 전체/UE sanitizer/wall timing 실행은 아니다.
- [독립 auditor](../../../../tests/integration/carla/audit_m7_1p_bridge.py)는 runtime bridge를 import하지 않는다.
  원래 receipts·native 입력 line·반환 source/value·권한 mask·다음 구간 age를 대조했다.
  완료 두 실행은 기존 effort/CRC/expiry audit도 수행하고, 각각8종 audit 손상을 거부했다.
  fault 실행은 정상 주행 PASS 대신 **예상 fault containment**만 판정한다.
- [사전 replay](preflight-replay.json)는320 전체 통과/20 첫 launch 거부를 미리 확인한 조사다.
  초기 poll/latch FAIL의 원본과 기대 음수 FAIL은 최종 성공으로 덮어쓰지 않았다.

예: repo root에서 기존 외부 경로를 지정해 실행한다. launcher가 새 서버 소유/정리를 수행하며
credential은 child environment에만 존재하고 argv/증거에 저장하지 않는다.

```bash
python3 tests/integration/carla/m7_1o_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --runtime /path/to/new-owned-runtime --output /path/to/new-evidence \
  --vehicle-substeps 320 --require-solver-wheel \
  --native-wheel-bridge build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow
```

response 비교에는 `--response-fixture /d/shin/stratadrive-tools/m7-source/m7-1o-actuator-fixture`,
누락 주입에는 `--bridge-drop-snapshot`을 추가한다. 각기 별도 새 디렉터리를 사용한다.
독립 audit은 `audit_m7_1p_bridge.py --input DIR --output FILE`이며20분할 fault에는
`--expect-negative`, 누락 주입에는 `--expect-snapshot-loss`를 지정한다.

## 남은 작은 단계

1. **M7-1q:** native8-role 원래 Actual/CAN·source/oldest/expiry·권한 의존성 및 전체 구간
   coverage를 서버 NoDrive admission에 연결한다. synthetic authority를 정상 권한으로 승격하지 않는다.
2. 같은 구간의 solver motor/friction work를 관측하고 단일 EV owner의 commit/실패 원자성을 검증한다.
3. functional 주행/보호 경로 검증 뒤 wall clock mapping·2/4ms deadline/부하를 별도 수용한다.

renderer 안정성·전체 ODD·OEM calibration·실제 network fault·AI/Jetson은 이번 시험으로 닫지 않는다.
[최종 범위/원천 hash](validation.json), [과거 무결성](prior-integrity.json),
[무손실 압축 원본 hash](compression.json), [증거 hash](SHA256SUMS)를 따른다.
