# M7-1d — world/state 10ms, RGB/GT 50ms

2026-10-23. 사용자 승인에 따른 M7 시간 계약 개정과 **비주행 수집의 한정 검증**이다.
논리 주기 분리는 확인했으나 **실제 시간 기준 Drive30ms 적합·정상 주행 연결은 미검증/BLOCKED**다.
서버 종료에서 native crash가 발생했으므로 전체 lifecycle 안정성 PASS로 쓰지 않는다.
기존 M6/M7-1a/b/c 코드·증거·수용 수치는 보존했다. M6 실행 JSON/모델은 변경하지 않았다.

## 결정과 재현 조건

- [ICD](../../../interfaces/carla-plant-adapter.md), [시간 계약](../../../requirements/timing-requirements.md),
  [ADR-0001 후속](../../../archive/design-decisions.md#adr-0001)에 world/state100Hz·영상20Hz를 채택했다.
  Controller20ms·Zone/vECU10ms·Drive30ms·native2ms/4ms 및20ms transport 계약은 유지한다.
  `profiles/reference.yaml`의 미사용 `simulation_sensor` 의미 항목만 world/state/camera로 분리했다.
  기존 M6 executable profile이나 이전50ms 실행 결과를 소급 변경하지 않았다.
- [공식 synchrony 문서](https://carla.readthedocs.io/en/0.9.16/adv_synchrony_timestep/)는
  world 고정 간격·단일 client tick·물리 substep과 simulation/wall time의 차이를 설명한다.
  [센서 문서](https://carla.readthedocs.io/en/0.9.16/ref_sensors/)의 `sensor_tick`은 simulation
  seconds 기준 촬영 간격이다. 아래 결과는 문서 보장이 아닌 실제 Host 관측이다.
- [환경](environment.json): 기존 공식0.9.16 서버/번들 cp310 wheel venv, Ubuntu22.04.5,
  RTX3090/driver580.178.04. 새 다운로드·설치·source build 없음. [1a artifact](../m7_carla_1a/package.json)
  및 [1b wheel/환경](../m7_carla_1b/environment.json)을 재사용했다.
- Town10HD_Opt/mkz_2020 첫 spawn, ClearNoon, traffic0, ego physics/autopilot off.
  두 카메라800×600/FOV90, actor-relative `(1.5,0,1.7)m` Rigid, lens_k/kcube0.
  world0.01s, camera0.05s, substep max0.01/max10, offscreen Vulkan Low, rendering enabled.
  실제 motion/wheel/actuation fidelity는 시험하지 않았다.
- 단일 owner thread가 tick→snapshot→bounded callback queue 소비를 수행한다. source는
  원래 CARLA frame/sim seconds와 round(ns), receipt/delivery는 Host monotonic이다.
  두 clock의 mapping이 없으므로 wall source age를 계산하지 않는다. state는 actor origin이다.
  GT는 training_evaluation, RGB/state는 online 파일로 분리했다. 전송 ACL 검증은 아니다.
- 실행 전 고정한 profile은 각 summary에 있다. nominal800tick=startup100/main600/drain100,
  drop/reset 각400tick=100/200/100. cleanup1tick은 별도다. 최종 callback 대기3s는 수집 종료용이며
  Drive30ms timeout을 대신하지 않는다. 최대64개 queue, full pixel은 저장하지 않고 hash/GT histogram을 남긴다.

[수집기](../../../../tests/integration/carla/m7_1d_multirate.py)는 기존1b의 state/schema/queue helper를
명시적으로 import한다. [독립 oracle](../../../../tests/integration/carla/analyze_m7_1d.py),
[oracle 변조 검사](../../../../tests/integration/carla/check_m7_1d_oracle.py), [source SHA](sources.json).
실행 기준 HEAD7a2b0fa+미커밋 M7-1a/b/c/d, [작업 전 상태](before.json).

서버는 environment.json의 command/cwd로 실행한다. 저장소 root에서:

```sh
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -I tests/integration/carla/m7_1d_multirate.py --output /d/shin/stratadrive-tools/carla-0.9.16/m7-1d/new-attempt
python3 tests/integration/carla/analyze_m7_1d.py /d/shin/stratadrive-tools/carla-0.9.16/m7-1d/new-attempt
python3 tests/integration/carla/check_m7_1d_oracle.py /d/shin/stratadrive-tools/carla-0.9.16/m7-1d/new-attempt
```

원본은 repository 밖 같은 경로에 보존했다. 저장소 JSONL은 gzip만 적용했으며, 임시 디렉터리로
복사·해제하면 동일 oracle로 재검사할 수 있다. output 덮어쓰기를 허용하지 않는다.

## 실제 결과와 실패

[시도 목록](attempts.json), [첫 실행](attempt-01/summary.json), [확인 실행](attempt-02/summary.json).
runtime collection2회 모두 exit0/COLLECTED. **첫 oracle FAIL을 유지**한다.
수정 oracle의 같은 원본 재평가와 별도 확인 실행은 한정 PASS이며, 이를 원래2/2 전체 PASS로 합치지 않는다.

| 항목 | attempt02 실제 관측 / 판정 |
| --- | --- |
| world/state | 수집800frame 연속+1/10ms, main state600/600; 원래 sim timestamp 보존. 논리 cadence PASS |
| RGB/GT | main 각120/120,5frame/50ms, 같은 frame의 timestamp/pose 일치; steady 수집 PASS |
| 누락 주입 | main state195/200, RGB/GT 각39/40. state 연속5개와 영상 각1개를 실제 수집 pipeline에서 버림; exact missing 보존 PASS |
| freshness replay | 위 실제 trace의 원래 source time으로 simulation-time age 재계산. 40/50ms에서 unavailable, 다음 새 state의 age0. 기존 ECU/latch 실행 증거가 아님 |
| pause | nominal wall250.283434ms, reset 후250.299626ms 동안 frame/sim time 불변. ECU wall timeout/재가입 NOT RUN |
| reset | 실제 fresh-client reload, 새 episode/run/epoch, main state200/200·영상 각40/40. 이전3stream metadata replay 거부; old Actual/INIT/arm NOT RUN |
| 정리 | sensor stop·queue close/clear·callback quiet·owned actor0, world 설정 복원; 별도 client 최종 probe도 vehicle/sensor0 |
| 서버 종료 | 이후 명시적 SIGTERM 중 native SIGSEGV, launcher139. 종료 안정성 FAIL / OPEN-M7-1D-01 |

수치/원본은 [최종 독립 재계산](attempt-02/offline-verification.json), [reset](attempt-02/reset.json),
각 case의 result와 ticks/packets에 있다. 위 주기 tolerance1µs는 double 시간 비교용으로만 사용하며
freshness 판정은 원래 round(ns)에서 **age<=30,000,000ns**다. 실제 nominal sample age0은
같은 snapshot 시각에 수행한 논리 replay 결과로, 전송/ECU 계산 지연0의 증거가 아니다.
fault 후 새 측정의 availability 회복을 기존 Drive latch 해제로 해석하지 않는다.

**첫 oracle 오류와 startup 변동:** 첫 카메라 frame 다음 간격은 두 실행의 모든 case에서
6world frame(약60ms), 이후5frame이었다. 최초 oracle는 첫 capture의 modulo5 위상이
영구적이라고 가정하여 [FAIL](attempt-01-oracle.txt)했다. [당시 oracle](analyze-initial.py)를 보존했다.
수정 oracle는 사전100tick startup의 마지막50tick에서10capture 연속 stride5를 확인하고
그 위상을 main 전에 고정한다. main 데이터로 위상을 재학습하지 않는다. 모든 startup capture,
6frame gap, steady 위상 밖 첫 capture와 steady grid상 미관측1개를 별도로 기록한다.
이 startup 미관측은 고정 위상 기준이며 물리 sensor packet drop 원인으로 단정하지 않는다.
startup을 포함한 최초 capture부터 엄격한50ms cadence는 **불충족**이며 sensor readiness gate가 필요하다.
원래 Drive freshness를 완화한 수정이 아니다. [첫 원본 재평가](attempt-01/offline-verification.json)는
새 runtime 실행으로 세지 않는다. 두 번째 실행 도중 oracle를 먼저 호출한
[incomplete 거부](attempt-02-oracle.txt)도 별도 보존하고, 완료 뒤 [최종 호출](attempt-02-oracle-final.txt)과 구분했다.

## Wall time과 정상 주행 차단

nearest-rank percentile, full collection 범위(startup/main/drain 포함)의 관측값이다.
RTF 분자는 nominal8sim s/reset4sim s, 분모는 첫 tick begin→마지막 수집 tick end다.
callback 소비/hash/histogram 및 pause는 포함하고 최종3s drain wait·cleanup/reload는 제외한다.

| case (attempt02) | wall s / RTF | snapshot 완료 간격 P99 / Max (의도 pause 제외) | >30ms 간격 |
| --- | --- | --- | --- |
| nominal | 10.458570118 / 0.764923 | 30.604963 / 87.892831ms | 12/798 |
| drop | 5.059783072 / 0.790548 | 29.359689 / 53.910206ms | 3/399 |
| after_reset | 5.665277019 / 0.706056 | 31.934475 / 280.911725ms | 5/398 |

첫 실행도 nominal RTF0.852126, pause 제외 >30ms1/798을 기록했다.
이 workload에서 wall100Hz가 유지됐다고 볼 수 없으며, 실제 ECU30ms 적합 판정은 **NOT RUN**이다.
완료 간격과 source freshness는 서로 다른 지표다. 획득 시각 mapping/uncertainty·각 hop의
latency·소비 시점·native2ms/4ms guard를 실제 경로로 측정하기 전 정상 주행을 허용하지 않는다.
고정10ms simulation tick을 wall10ms로 relabel하거나 callback arrival을 acquisition으로 쓰지 않는다.

wheel 관련 설치 API inventory는 각 result에 있다: get/set_wheel_pitch_angle,
get_wheel_steer_angle/set_wheel_steer_direction. 이는 API 이름 확인이며 pitch의 물리 의미,
누적 회전/각속도·슬립·work 지원을 검증한 결과가 아니다. VehicleState의 body velocity나
v/r를 measured wheel feedback으로 사용하지 않았다. torque/pressure/steer calibration,
실제 Actual 경로·중복 actuator/motion/energy 제거는 계속 OPEN이다.

## 종료 실패와 다음 단위

[최종 probe](final-probe.json)는 async/fixed_delta=None 복원·actor0을 확인했다.
그 뒤 서버 PID2720620에 SIGTERM을 보냈고 [로그](server-stdout.txt)에 RequestExit,
Operation canceled, Signal11과 Segmentation fault가 기록됐다. [종료 결과](shutdown.json)는
exit139이며 현재2000/2001/2002 listener는 없다. **OPEN-M7-1D-01: 종료 중 native crash 원인 미확정**.
기존 OPEN-M7-1B-01/02와 동일 원인으로 단정하거나 해소하지 않는다. 새 source build/SDK patch는 하지 않았다.

후속은 (1) source clock·wheel telemetry 적합성 조사, (2) 영상/rendering/수집 비용을 분리한
wall timing 진단과 종료 crash 재현, (3) 별도 functional mode에서10ms Actual interval/protection
연결 설계다. 어느 경우도 기존 M6 runtime의2ms/4ms guard를10ms로 늘리지 않는다.
calibration/권한·원천·native guard gate가 준비된 뒤 실제8-role 정상 주행 연결을 별도 수행한다.

[oracle negative](oracle-negative.json)는 timestamp 변조/world delta50ms/본 관측 state 누락/
카메라 위상 변조/online GT 혼입5개를 임시 복사본에서 모두 거부했다. C++/M6 전체 회귀는
기존 코드 변경이 없어 새로 실행하지 않았다. Python 문법·문서 링크·source/evidence hash 검사는
[정적 검증](validation.json)에 둔다. 모든 보관 파일은 [SHA256SUMS](SHA256SUMS)로 검증한다.
