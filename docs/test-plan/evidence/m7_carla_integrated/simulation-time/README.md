# M7 시뮬레이션 시간 연속 실행 증거

실행일: **2026-10-29**. [ADR-0065](../../../../archive/design-decisions.md#adr-0065)의
`m7-simulation-time-v1`을 실제 CARLA source server에서 실행했다.
고정 Town03_Opt/V1의 기능 범위는 **수용**한다. 현재 단계 판정은
[프로젝트 상태](../../../../project-status.md), 실행 계약은
[CARLA ICD](../../../../interfaces/carla-plant-adapter.md#시뮬레이션-시간-연속-실행)를 따른다.

## 실행 결과와 분모

[suite.json](suite-a/suite.json)의 7개 case 모두 `PASS_CASE_ONLY`, suite는
`COMPLETE_BOUNDED_SUITE`, `simulation_profile_accepted=true`다.
고장은 의도한 차단 검출을 PASS로 센다. 정상 주행 성공이나 물리 정지를 뜻하지 않는다.

| Case | 완료 physics / EV 정산 | 확인한 결과 |
| --- | ---: | --- |
| continuous | 6000 / 6000 | 한 세션60s, 정상5919구간, 가속·회생·제동·재출발6주기/30phase, 마지막 휠 정지 |
| continuous-cameras | 6000 / 6000 | 같은 연속 시나리오, RGB1200/GT1200, 누락0·원본 frame/timestamp 일치 |
| protected-sleep | 400 / 400 | 정상119·보호200구간, RGB80/GT80, index278부터 자연 sleep122구간·마지막100구간 동일 pose |
| rgb-drop | 208 / 208 | 의도한 RGB1개 누락 검출, 다음 tick 차단 |
| snapshot-stop | 200 / 199 | 이전 snapshot의 원본 timestamp를 유지한 채 stale 입력 거부 |
| work-missing | 200 / 199 | 불완전 work를 model job/다음 tick 전에 거부 |
| native-stall | 200 / 199 | 소유 native child의 SIGSTOP, 실제10s 응답 감시 후 다음 tick 차단 |

정상 연속 case는 중간 reset/teleport 없이 동일 run/session/actor/physics generation을 유지했다.
Controller20ms·Zone/vECU10ms·CARLA physics10ms는 동일 simulation domain에서 진행한다.
기존 source-age30ms·expiry와 원본 acquisition/frame/timestamp를 유지했다.
고정 VehicleRequest → Central → Zone → vECU Actual → Plant Adapter → NoDrive →
solver work → 단일 EV 경로이며 command를 Actual로 대체하지 않는다. GT는 제어 입력이 아니다.

Actual-only/single writer/ticket 단회 사용, 의도한 wall pause 중 무tick·무restamp,
종료 latch, reset 후 새 INIT, ego 제거, native·server 종료와 설정 복원을 확인했다.
보호 case는 원래 LocalProtection Actual의 drive0·brake floor≥1MPa를 계속 적용했다.
자연 정지는 velocity epsilon·강제 sleep·pose setter 없이 확인했다.
정상 연속 case의 마지막 **휠 정지**를 보호 case의 **차체/pose 정지**와 혼동하지 않는다.

마지막 세 고장 case는 완료된 physics1구간의 EV 정산을 끝내지 못했다.
별도 `*-partial-work-audit.json`은 원본200구간과 실제 정산199개를 검사한다.
미정산 구간을 0으로 만들거나 work를 추정하지 않았으며, 완전한 energy ledger·보호 제동·
실제 정지로 수용하지 않는다. `native-stall`의10s는 기존 Host 응답 watchdog이며
Drive30ms 또는 실제 wall2ms/4ms deadline을 대체하지 않는다.

## 독립 검증과 실제 실행 시간

원본 CAN/P05·Actual·solver320 substep·signed work·EV/SOC는 `audit_m7_1r_work.py`,
시나리오30phase·센서는 `audit_m7_integrated.py`, 보호 선택은 `audit_m7_protection.py`,
원본 clock·자연 정지는 `audit_m7_closeout.py`, 연속성·lifecycle은
`audit_m7_simulation.py`로 각각 검사했다. 결과 JSON은 `suite-a/`에 있다.

- Normal **114/114**, ASan/UBSan **114/114**. 새 horizon opt-in 시험을 포함한다.
  로그는 `build-checks/`에 있다. 이번에 TSan이나 M6 전체 시험을 재실행한 것은 아니다.
- [연속성 손상 시험](simulation-corruptions.json): 정상 원본 baseline 후 중복 source frame,
  physics frame 건너뜀, 숨은 reset, session 변경, interval restamp, 정상 권한 상실 **6/6 거부**.
  기존 work/energy/보호 감사의 손상 검출 결과도 각 JSON에 보존했다.
- 비영상60s의 실제 loop **213.878446891s**, 영상60s의 실제 loop **244.368764682s**.
  시뮬레이션 시간/실제 시간은 각각 약0.281/0.246이다. 원본 trace 기록·검증과 의도한 pause를
  포함한다. 서버 준비·별도 감사까지 포함한 case 시간은 `suite.json`의 `elapsed_seconds`다.
  CARLA 단독 benchmark 또는 실시간 상한으로 사용하지 않는다.

`full_m7_closed=false`, `wall_realtime_accepted=false`, probe의
`normal_driving_enabled=false`는 일반 주행·wall 실시간 수용을 열지 않는 기존 경계다.
이번에 수용한 것은 명시한 기능 profile뿐이다.
[기존 실제 wall 실패](../../m7_carla_wall_guard/carla-runtime/README.md)는 그대로 OPEN이며,
M6 코드·주기·안전/통신 계약·기존 검증 수치와 판정을 변경하지 않았다.
M8 속도/경로 폐루프, Reference30km/h, AI, 장시간/전체 map 안정성, Target/HIL은 이번 범위 밖이다.

## Source와 보관 방식

구현 기준 commit은 `76bd14f4081908f55ecfcb854f395b52e85947eb`다.
문서 재구성 commit `5cc77ac`의 새 경로를 따른다. CARLA/UE를 이번에 재빌드하지 않았다.
CARLA `294096eb1c38eabf246e4f3a9cdab704e33a7f4c` + 기존 NoDrive patch,
UE `e9d9e60c85f643e10eeb03f42f61554d18dcb30f`, 실제 client/server `294096e-dirty`다.
각 `server-*.json`과 `runtime-a/`에 원래 실행 인수·source/binary 식별·종료 로그가 있다.
Native ELF는 중복 보관하지 않고 원래 SHA를 남겼다.

`suite-a/sources/`는 suite 시작 시 snapshot이다. 실행 중 감사 보완을 추가했으므로
이를 최종 source인 것처럼 덮어쓰지 않았다. 최종본은 `final-sources/`와
[final-source-sha256.json](final-source-sha256.json)에 있다.
추가한 protected-sleep 센서 감사와 세 고장의 partial-work 감사는 원래 결과에 별도로 실행했고,
현재 runner도 다음 실행부터 이 검사를 포함한다. 최종 simulation auditor는 정상 baseline과
6개 손상 검사를 재실행했다. Probe/native actuation source는 실행 뒤 변경하지 않았다.

[artifact-manifest.json](artifact-manifest.json)은 원본 경로·크기·SHA와 보관 파일 SHA를 기록한다.
짧은 trace/log는 무손실 gzip, 긴 두 trace는 원본 gzip bytes를48MiB 단위로 나눴다.
`trace-parts.json`에 순서와 전체 SHA가 있다. `SHA256SUMS`는 보관물 전체의 무결성 목록이다.

## 저장 증거 복원과 재검사

저장소 루트에서 실행한다. 복원 대상은 **새 외부 디렉터리**여야 한다.

```sh
evidence="$PWD/docs/test-plan/evidence/m7_carla_integrated/simulation-time"
(cd "$evidence" && sha256sum --quiet -c SHA256SUMS)
restored="/tmp/m7-simulation-restored-$(date +%Y%m%d-%H%M%S)"
python3 "$evidence/restore_traces.py" "$restored"
python3 tests/integration/carla/audit_m7_simulation.py \
  "$restored/suite-a/continuous" --case continuous \
  --output "$restored/restored-continuous-audit.json"
```

복원은 두 긴 gzip trace의 전체 byte 수와 SHA를 확인한다. 원래 solver/energy 감사도
`python3 tests/integration/carla/audit_m7_1r_work.py "$restored/suite-a/continuous" --output ...`로
재실행할 수 있다. 감사 파일은 보관 원본 밖에 쓴다.
이번 보관물의 두 trace 복원 SHA 일치와 복원한 continuous6000구간의 재감사도 확인했다.
실제 확인 결과는 [restore-check.json](restore-check.json)에 있다.

## CARLA 실제 suite 재현

Native 준비는 [실행 안내](../../../../carla-guide.md)를 따른다.
아래 runtime/output은 새 경로를 사용한다. GPU·RPC2200/2201/2202가 사용 가능해야 한다.
모든 physics320 substep 원본을 보관하므로 실행 로그를 위한 여유 공간이 필요하다.

```sh
run_dir="$PWD/build/m7-simulation-$(date +%Y%m%d-%H%M%S)"
python3 tests/integration/carla/m7_integrated_run.py --simulation-time \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --native "$PWD/build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow" \
  --runtime "$run_dir/runtime" --output "$run_dir/suite" --held-steer-sleep
```

연속 case의 전체 probe supervisor만1200s로 분리했다. 짧은 case300s·RPC/native응답10s·
시작180s·종료30s는 그대로다. 기본10s native horizon은 유지하고 solver-work/Actual export의
명시적 opt-in만60s까지 허용한다. Timeout 뒤 동일 tick을 모호하게 재시도하지 않는다.
