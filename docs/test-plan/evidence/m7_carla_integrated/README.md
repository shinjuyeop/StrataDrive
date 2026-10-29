# M7 통합 검증 — 정상 기능, 센서, fault와 종료 판정

2026-10-27. 기준 commit `06284e5`. **전체 M7 NOT CLOSED**;
[종료 검토](../../../project-status.md#m7-종료-조건)가 현재 판정을 대표한다.
M6 구현·계약·수용 수치, V1 계수, 기존 Controller20ms/Zone·vECU10ms/Drive30ms/expiry는 불변이다.

## 실행 결과

[전체15서버 집계](run-summary.json): launcher 성공10/실패5, SIGINT130은12회,
강제−9는3회다. 최초 실패와 진단 실패를 분모에서 빼지 않았다. 마지막 UE/CrashReportClient0,
2200/2201/2202 port FREE를 확인했다. 원래 renderer SIGSEGV 원인의 해소를 주장하지 않는다.

| 실행 | 실제 결과 |
| --- | --- |
| [driving-a](driving-a/result.json) | FAIL,0receipt. spawn 직후 첫 snapshot에 ego가 아직 없는데 접근한 시험 코드 오류. pause/reset/close·SIGINT130 |
| [driving-b](driving-b/result.json) | 초기 unavailable 처리 후900receipt/900정산·819정상 권한 구간. [독립 work](driving-b-audit.json), [통합 audit](driving-b-integrated-audit.json) |
| [camera-a](camera-a/result.json) | FAIL,8receipt/8정산. 기본 sensor_tick=.05의 첫 간격이6frame/60ms. 원본을 보존하고 전용 취득 스케줄 수정 |
| [suite-a camera-a](suite-a/server-camera-a.json) | 새 빌드 첫 startup180s readiness FAIL, 주행 NOT RUN. SIGINT30s 초과/강제−9 |
| [suite-a normal-a](suite-a/normal-a/result.json) | 수정된 module,900receipt/900정산·819정상 구간. [독립 work](suite-a/normal-a-audit_m7_1r_work.json) |
| [suite-a RGB 누락](suite-a/rgb-drop/result.json) | 기대 차단:209receipt/209정산. RGB41/GT42, RGB1개 실제 전달 폐기 후 gap 감지·다음 tick 차단. 원래 missing frame/timestamp 보존. [독립 감사](suite-a/rgb-drop-audit_m7_integrated.json) |
| [suite-a state 누락](suite-a/snapshot-stop/result.json) | 기대 차단:200receipt/199정산. 이전 snapshot을 그대로 반환한 주입에서 다음 tick 금지. 마지막 미정산 work를 성공으로 세지 않음 |
| [suite-a work 누락](suite-a/work-missing/result.json) | 기대 차단:200receipt/199정산. 불완전320-substep packet 거부, native exit1·다음 tick 금지 |
| [suite-a zero](suite-a/zero/result.json) |156개 runtime 검사/13receipt, [기존 독립 audit](suite-a/zero-audit.json)의 손상8종 거부. zero-only fixture이며 정상 native 권한 증거와 구분 |
| [suite-a disabled](suite-a/disabled/result.json) | 확장 flag-off read-only 거부, ego/주행 없음 |
| [suite-a loading-abort](suite-a/server-loading-abort.json) | 준비 전 get_world200ms timeout 확인 후 종료 요청. SIGINT30s 초과/강제−9,FAIL |
| [suite-b camera-a](suite-b/camera-a/result.json), [camera-b](suite-b/camera-b/result.json) | 새2서버 각각900receipt/900정산·819정상 구간, 각각RGB180/GT180.5frame 간격/원래 state timestamp 일치. [A audit](suite-b/camera-a-audit_m7_integrated.json), [B audit](suite-b/camera-b-audit_m7_integrated.json) |
| [suite-b normal-b](suite-b/normal-b/result.json) | 명시적 FixedSeed 최종 runner,900receipt/900정산·819정상 구간. [독립 work](suite-b/normal-b-audit_m7_1r_work.json) |
| [loading-diagnostic](server-loading-diagnostic.json) | 로딩 중단/종료−9 재현. 소유 child에만 debugger supervisor 권한을 부여하고 원래30s 안에서 GDB10s stack capture 시도했으나 symbol loading 중 timeout. root cause 미확정, 정상 종료 PASS 아님 |

[suite A](suite-a/suite.json)는 실패 포함, [suite B](suite-b/suite.json)는3case 모두 한정 통과다.
기존 native 회귀는 Normal/ASan 각각 **70/70**:
[Normal log](runtime-logs/native-normal.log.gz), [ASan log](runtime-logs/native-asan.log.gz).
추가1case는 INIT 뒤 일정 변경과 잘못된 요청 일정을 거부하는 시험이다.
[통합 metadata oracle](integrated-oracle.json)은 요청 변조·GT 주행 사용·RGB restamp/누락·
actor 오류·GT 용도 변경·invalid 영상7종을 모두 거부했다. 정상 work audit마다 기존11 solver/7 energy
손상 거부를 포함한다. 새 TSan/UE 전체 sanitizer를 실행하지 않았다.

## 동결 설정과 관측

CARLA/UE pin·40개 native 원본 불변·설치 변경2파일은 [설치 감사](installation-audit.json)에 있다.
[UE build](runtime-logs/carla-build.log.gz)는 exit0이며 수정은 CARLA Sensor.h/.cpp의 전용 frame5
취득 옵션뿐이다. UE tracked source는 깨끗하며 M6 수신기/codec 원본40파일은 그대로다.
[반복 설치](runtime-logs/install-repeat.log.gz)도 성공했다. solver observer·V1 law는 변경하지 않았다.

시험 입력은 [고정 상위 요청 일정](../../../../tests/integration/carla/scenarios/m7_integrated_v1.txt)이다.
INIT 전에 읽고 원래20ms Controller release에서만 선택한다. Actual/하위 명령 직접 주입이 아니다.
Town03_Opt spawn0/mkz_2020/ClearNoon/traffic 없음, world10ms/solver320, 카메라50ms다.
최종 suite-b부터 launcher의 `-FixedSeed`로 UE RandInit/SRandInit0을 명시했다. 앞선 report의
`seed:0`은 실제 engine seed 설정의 근거가 없던 metadata 표기였다. 앞선 원본을 수정하지 않았으며
그 실행의 engine seed 고정을 주장하지 않는다. 랜덤 scenario/TrafficManager는 사용하지 않았다.

[경로 후보](route-candidate.json)는28점/2m 간격/54m 직선, road5→6/lane−2, 교차로 진입 전 종료다.
[read-only generator](../../../../tests/integration/carla/m7_route_candidate.py)를 독립 재실행해 byte 일치를
확인했다. 좌표 UE m/yaw deg·곡률1/m, map XODR hash를 기록했다. M8 30km/h 적합성/추종은 NOT RUN.

[물리/전기 비교](physics-comparison.json): 정상5실행의 각900개 physics는 generation identity를
제외하고 **정확히 일치**한다. 매 실행 negative motor work114구간, chemical energy 감소70구간,
총 motor work2120.781720020654J, 주행 경로 길이 약4.77215m다. 최종SOC 약0.62995440188459이며
분수 ns의1ms 정산 경계에 따른 마지막 binary64 차이를 “완전 일치”로 주장하지 않는다.
독립 에너지 balance는 기존0.00072J 기준으로 검사했다. 새 epsilon을 추가하지 않았다.

제동 구간에서 네 휠 회전이 정확히0인92frame을 관측했다. 이때 차체 전방 속도는
약−0.001105~0.001908m/s를 포함하므로 완전한 차체 정지를 수용한 것은 아니다.
최대 전방 속도 약1.259m/s의 짧은 고정 시험이며 Reference0–40km/h 전체 검증이 아니다.

RGB/GT는320×240/FOV90,ego x1.6/z1.7m/pitch−8deg에 설치했다. 실제 payload SHA와 frame·
timestamp·sensor/ego identity·arrival monotonic·validity를 보존했다. 각 stream 첫 BGRA 원본은
`*-first.bgra.gz`에 있고 나머지는 metadata/hash다. 전체 영상 데이터셋 수집/AI 학습은 하지 않았다.
GT는 TRAIN_EVAL_ONLY이며 상위 요청/Actual 생성에 사용되지 않았다.

## 시간·보호·lifecycle의 한계

원래 whole-interval source-age 최대20ms·최소 command expiry 여유1ns는 simulation clock 결과다.
[최종 비렌더 계측](suite-b/normal-b-audit_m7_integrated.json)에서 native 응답 사이 실행 공백은
평균31.668ms/P95 62.115ms/P99 65.170ms/최대325.245ms(의도한250ms pause 포함)였다.
명시적 pause 영향 index150/151을 제외해도898/898 공백이2ms를 넘고 최소2.321ms였다.
원래2ms 실행 기회는 이 연결에서 수용할 수 없다. 개별 job4ms deadline은 미계측이며
roundtrip을 개별 job latency라고 주장하지 않는다. simulation time과 wall time을 직접 차감하지 않았다.
이 계측은 JSON320-step trace/검사/파일 기록을 포함하는 진단 경로이고 production 성능 수용이 아니다.

fault case의 PASS는 **다음 tick 차단/clear/latch/reset**에 한정된다. native admission은 정상 arm
이후 비정상 Actual mode/authority를 거부한다. 실제 LocalProtection Actual을 계속 적용하여
차체를 정지시키는 통합 경로는 미구현이다. M7-1m 합성 보호 Brake Actual 시험을 이 경로의
수용 근거로 대신하지 않는다. 기존 M6 안전/정지 요구를 약화시키지 않았다.

cold-loading180s 준비 실패와 종료30s 실패를 재현했다. 원래 M7-1s accept/close 경합 수정은
FIXED_LIMITED로 유지하지만 별도 cold-loading 문제를 닫지 않는다. GDB 진단도 기존 종료 한도 안에서
중단했고 Host Yama/ASLR 설정은 변경하지 않았다. [GDB 원본](runtime-logs/loading-diagnostic/shutdown-gdb.log.gz)은
stack을 확보하지 못했으므로 원인을 추정해 확정하지 않는다.

## 재현과 무결성

```bash
python3 tests/integration/carla/m7_integrated_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --native build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --runtime /path/to/new-runtime --output /path/to/new-evidence
```

기존 디렉터리를 덮어쓰지 않는다. 모든 case는 새 서버이고 모호한 tick은 재시도하지 않는다.
기존 cold-loading gate가 해결되기 전 전체 suite가 실패할 수 있으며 이를 PASS로 감추지 않는다.
실행별 argv·artifact hash·probe source snapshot을 보존했다. native 실행 파일은 외부 runtime에 있고
저장소에는 hash와 재빌드 source를 둔다. suite source는 실행 시작 시 고정했고 최종 runner의 추가
shutdown diagnostic 옵션은 별도 실행으로 검증했다.

[archive manifest](archive-manifest.json)는 JSONL/server/client/readiness/build/test log의 원본SHA와
무손실 gzip SHA를 연결한다. 압축 후 원본 hash를 재검사했다. 과거 M7/M6 evidence는 변경하지 않았다.
`SHA256SUMS`는 이 디렉터리의 최종 파일들을 대상으로 하며 staged Git blob까지 확인한다.
