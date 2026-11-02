# M8 별도30km/h NormalStop·HV-off

2026-11-02. **PASS_SEPARATE_STOP30_NOMINAL_SIMULATION_ONLY**.
Town06_Opt 고정 직선에서30km/h로 주행하다 기존 NormalStop owner 경로로 정지했다.
별도 `normal-stop30-a1-t10-v1`에만 감속1m/s²·제동10s·확인60ms·shutdown2s를
생성 시 주입했다. 기존 default5s, 저속 profile, v1 PI와 server admission은 유지한다.
[실행 전 protocol](protocol.md), [전체 수치](results-summary.json),
[물리 응답 곡선](stop30-01.png)을 따른다.

## 실제 실행과 독립 판정

`m8_stop30_v1.json`은 S01과 동일한721점 직선·map/geometry를 사용한다.
20s의0→30km/h 가속 뒤 첫 PI release+35s에 정지를 요청하고 이후 PI는 발급하지 않는다.
6000ticks/60s 동안 기존20ms NormalStopRequest, 원본 StopLease/ACK·Actual·PowerStatus,
8-role RunLease·whole-interval freshness/expiry를 계속 사용한다.

| 검사 | 결과 |
| --- | --- |
| 요청 시 body 속도 | 29.952689941km/h |
| body·네 solver wheel 연속1초 정지 시작 | 요청 후8.477998988s |
| 원본 ACK 뒤 최초 PowerDown job | 요청 후8.6704s |
| 첫 물리 terminal hold admission | 요청 후8.677999006s |
| Complete·원본 PowerStatus Off | 요청 후9.277998992s |
| ACK 후 shutdown | .607598992s /2s 예산 |
| HV-off 상태 | 접촉기3개 open·bus27V |
| 마지막1초 pose drift | 0m |
| physics / 단일 EV settlements | 6000 /6000 |
| 실제 terminal hold 물리 구간 | 1552 |
| 원본 PI / 독립 Pure Pursuit | 1750 /1750; PI 식 최대 차이0 |
| plateau body1000 / wheel500 최대오차 | .074841797 /.030900000km/h |
| 경로900개20Hz 횡오차 / heading P95 | .001689639m /.007804996deg |
| 정지 후 rear-axle progress | 242.204983m |
| 최대 독립 EV balance 잔차 | 5.61413e-8J |
| owned 서버 종료 | 130; 강제 종료 없음 |

10s 제동 및 ACK 이후2s shutdown 제한을 모두 만족했다.
[Terminal/route 감사](stop30-01-audit.json), [native/solver/EV 감사](stop30-01-work.json)를 따른다.
terminal 감사의 `normal_stop_intervals=1553`은 마지막 settlement 행을 포함한 관측 수다.
물리 구간 수1552와 구분한다. 정지한242m를 기존 S01의300m 완료로 세지 않는다.

## 검증과 호환성

- C++ unit/logical1217/1217, Python237/237, 영향 범위 ASan/UBSan33/33.
- Release/ASan CLI 각각 원본100개 입력의 새 mode/config/proof JSON과 scope guard8개 검증.
- [Terminal 원본 변조20종](stop30-01-mutations.json), solver11종·EV7종을 모두 거절.
- 기존 저속 NormalStop·입력 누락 각각4001관측을 최종 binary로 재생해 native JSON 전체 일치.
- 두 기존 저속 원본을 변경한 공통 감사로 다시 검사해 기존 판정도 유지.
- 기존 M8 evidence1305파일과 v1 model SHA256 불변; 설치된 서버89파일 확인.

CLI100개 입력과 기존8002개 replay는 새 물리 실행으로 세지 않는다.
이상적30km/h 입력의 C++ 시험은 기본5s timeout과 별도10s handoff를 비교한다.
실제 실행에서는 정지·인계가5s를 넘으며 별도10s가 적용된 것을 확인했다.

native SHA256은 `7a592bff4afc254661b6892b8c0004ffc8eea8afab73adcb731593d74456e6be`다.
`producer-hashes.json`·`source-producer.tar.gz`·manifest는 실행 전 기록이다.
실제로 실행한 binary와 child Python은 `runtime-stop30-01/probe/`에 보존했다.
서버 binary는 기존 세대 그대로이며 재빌드/재설치하지 않았다. 실행 이후 수정은
독립 감사·그 감사의 회귀 시험·plot·문서뿐이며 물리 producer는 바꾸지 않았다.
`source-final.tar.gz`는 최종 dirty tree snapshot, `implementation.diff`는 직전
m8_stop_fault 최종 snapshot 대비 변경이다. build/evidence를 제외했다. commit/push는 하지 않았다.

## 보존한 실패와 감사 교정

첫 물리 실행은 성공했다. 첫 독립 감사 `audit-stop30-01`과 그 baseline을 쓰는
`mutations-stop30-01`은 wheel plateau499개를 발견해 실패했다.
[실패 판정](stop30-01-audit-attempt01.json)과 [집계 진단](plateau-diagnosis.json)을 보존했다.
첫 구현은[25,35)s 원본 wheel source 중 **PI가 소비한 표본**만 셌다.
35s에 PI가 종료되므로 마지막 pre-event acquisition이 새 PI에 소비되지 않았다.

원본 Drive Actual에는 같은 구간의1000개100Hz 표본이 모두 있었다. 최종 감사는
각20ms 구간에 원본 표본2개가 있는지와 원본 물리 wheel의 양자화 오차를 검사한 뒤
첫 표본을 선택해50Hz500개를 평가한다. 마지막 구간도 포함한다. 시간 구간·표본 수·
성능 허용 오차는 유지했다. 누락을 허용하거나 표본을 합성하지 않았다.
마지막 표본 누락·물리 값 불일치 거절과 마지막 구간 평가의 회귀 시험2개를 추가했다.
수정한 `audit-stop30-02`와 `mutations-stop30-02`가 통과했다. 물리 실행은 반복하지 않았다.

개발 중 `build-01`은 NormalStopConfig include 누락, `build-02`/`build-all-01`/
`asan-build-01`은 GoogleTest 매크로 주변 중괄호 누락의 경고→error였다. 수정 후 최종
Release/ASan 빌드가 통과했다. `component-01`은 빌드 실패 뒤 옛 binary를 실행했으므로
새 기능 검증 근거에서 제외한다. `component-02`는 합성 route의360m 점 간격이 기존5m
제한을 위반했다. fixture를5m 간격으로 수정한 `component-03`25개가 통과했다.
고정 실제721점 route와 production guard는 바꾸지 않았다. CLI 첫 wrong-horizon 검사도
간격 오류를 먼저 검사했던 것을 고쳐 `cli-02`에서는 `route profile scope` 거절을 확인했다.
모든 시도·명령·시각은 `validation/`에 보존한다.

## 범위와 다음 단계

고정 nominal30km/h 직선의 simulation-time 수용이다. 동일 참조에서 timeout·입력 손실,
ACK/전체 통신 손실 등30km/h fault matrix는 후속이다. 전체 Reference/M8·
Planner/localization·wall/Target 수용과 과거 UE renderer/GC 원인 규명도 OPEN이다.
[ADR-0075](../../../archive/design-decisions.md#adr-0075)를 따른다.

## 재현

저장소 root에서 기존 source CARLA/SDK/NoDrive fixture와 새 output/runtime 경로를 사용한다.

```bash
ctest --test-dir build/m7-functional -L 'unit|integration.logical' --output-on-failure
python3 -m unittest discover -s tests/unit -p '*_test.py'
python3 tests/integration/carla/check_m8_stop30_cli.py \
  build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --output build/m8-stop30-replay/cli
python3 tests/integration/carla/m7_1o_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --runtime build/m8-stop30-replay/runtime --output build/m8-stop30-replay/run \
  --native-actual build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --vehicle-substeps 320 --solver-work --held-steer-sleep --simulation-continuous \
  --route-profile tests/integration/carla/scenarios/m8_stop30_v1.json \
  --route-startup-seconds 600 --ticks 6000
python3 tests/integration/carla/audit_m8_stop.py build/m8-stop30-replay/run \
  --output build/m8-stop30-replay/terminal.json
python3 tests/integration/carla/audit_m7_1r_work.py build/m8-stop30-replay/run \
  --output build/m8-stop30-replay/work.json
python3 tests/integration/carla/check_m8_stop_corruptions.py build/m8-stop30-replay/run \
  --output build/m8-stop30-replay/mutations.json
```

보관 증거를 덮어쓰지 않는다. `SHA256SUMS`는 이 디렉터리 보관 파일의 무결성 목록이다.
