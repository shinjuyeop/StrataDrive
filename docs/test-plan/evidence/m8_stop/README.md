# M8 저속 NormalStop/HV-off와 속도 입력 누락 정지

2026-11-01. **PASS_LOW_SPEED_TERMINAL_SIMULATION_ONLY**.
Town03 V1, NoDrive320, 기존 단일 EV와8-role simulation-time 경로에서 약10km/h로
주행하다 NormalStop 또는 Central 현재 속도 입력 누락을 선택한 실제 CARLA 실행이다.
[사전 protocol](protocol.md), [전체 수치](results-summary.json), [원본 응답 곡선](terminal-response.png)을 따른다.

## 결과

| 항목 | NormalStop | 현재 속도 입력 누락 |
| --- | --- | --- |
| 실제 physics / EV settlements | 4000 / 4000 | 4000 / 4000 |
| 사건 전 독립 PI 검증 | 750 releases, 최대 차이0 | 750 releases, 최대 차이0 |
| 사건 시 body 속도 | 9.982294km/h | 9.982294km/h |
| body≤.001m/s + 네 solver wheel0의 연속 정지 시작 | 2.987999558s | 2.107999577s |
| StopLease/accepted ACK 인계 | 3.177999575s | 해당 없음 |
| Complete / 원본 PowerStatus Off | 3.777999562s | 수용하지 않음 |
| 원본 protection torque0 / brake≥1MPa acquisition | 해당 없음 | 16ms / 206ms |
| 위 torque / brake의 receipt 관측 | 해당 없음 | 약18ms / 208ms |
| 마지막1초 pose drift | 0m | 0m |
| 정상 owned 서버 종료 | 130 | 130 |

NormalStop HV-off 시 원본 PowerStatus의 세 접촉기는 모두 open, bus27V였다.
기존1m/s² 감속·제동5s·정지 확인60ms·shutdown2s를 그대로 사용했다.
원본 stationary Actual과 세 ECU의 StopLease 선택 ACK,8-role release/RunLease를
동시에 확인한 hold 물리 구간은2102개다. `stop-01-audit.json`의
`normal_stop_intervals=2103`은 마지막 settlement 관측1개를 포함한 관측 수이며
물리 구간 분모는 [work 감사](stop-01-work.json)의2102를 사용한다.

입력 누락은 첫 PI release+15s의 해당20ms job에서 Feedback fault와 local protection을
선택했다. Central SpeedRequest에 전달하는 현재 Drive Actual만 빠지고 원래 wheel/
actuator acquisition과 다른 ECU traffic은 계속한다. 전체 통신 단절이나 command
만료 timeout 시험으로 해석하지 않는다. 두 실행 모두 사건 이후 새 PI 요청을 내지 않는다.
강제 pose/velocity 설정이나 정지를 위한 physics pause를 사용하지 않았다.

[NormalStop 감사](stop-01-audit.json), [입력 누락 감사](input-loss-01-audit.json),
[정상정지 solver/EV](stop-01-work.json), [입력 누락 solver/EV](input-loss-01-work.json)를 참조한다.
두 work 감사의 최대 에너지 balance 잔차는 각각 약2.05e-8J,2.26e-8J다.

## 검증과 producer

- 최종 C++ unit/logical1214/1214, Python233/233 통과.
- 영향 범위 ASan/UBSan22/22, 최종 설정 검증 변경 후 정지 시험1개 재검사 통과.
- C++ 원본 stop proof 의미 변조8종과 normal 재개 거절 확인.
- raw terminal evidence16+12종, 각 실행 solver11종·EV7종 변조 거절.
- 이전 M8 evidence1008개 및 원본 v1 model hash 불변.
- 서버 generation89파일 설치 hash, CARLA/UE 빌드와 canonical 설치 manifest 갱신 확인.

첫 NormalStop native SHA256은
`df02115bbef75de23801c3437bd3d9d54112b5e7f83e284b645a9c4d7d0f20de`다.
그 뒤 `FunctionalRig::speed_profile`의 enum/scope 검증을 상태 변경 앞으로 옮겨
거절된 중복/잘못된 설정이 terminal mode를 바꾸지 않도록 했다. 최종 binary
`e21ddc363fe3c95289e5781c6d0204d8ea203f4beb4d8b7e5f68fa004495baad`에 첫 실행의
원본 work/sensor 입력을 다시 넣어4001 native JSON 전체가 정확히 일치함을 확인했다.
[Replay 판정](stop-final-replay/verdict.json)은 새 물리 실행으로 세지 않는다.
입력 누락은 이 최종 binary의 실제 CARLA 실행이다.

두 실행의 서버 binary는 동일하다. `producer-hashes.json`, `final-native-hash.json`,
`server-*.json`과 각 `runtime-*/probe`의 실행 binary/child Python snapshot을 보관한다.
`install-previous.json`은 이전 설치, `install-manifest.json`은 새 설치이며
`installed-integrity.json`은89개 설치 파일 확인 결과다. 기존 renderer/GC 실패 원인
해결이나 wall 경로 수용 확대를 의미하지 않는다.

## 실패와 보관 범위

`validation/build-01`의 첫 컴파일 실패는 LeafResult를 OwnerPayload에서 직접 찾은
오류다. 실제 LeafReport 안의 variant에서 읽도록 고쳤다.
`validation/component-01`의 첫 command withholding 시험은 다음10ms 구간을 덮지
못하는 기존 command expiry 때문에 거절됐다. 이 gate를 완화하지 않고 이번 fault를
위 Central 현재 속도 입력 누락으로 분리했다. 명령 만료의 물리 정지를 통과로 기록하지 않는다.

`stop-01/`, `input-loss-01/`는 compressed original trace/result/events,
`validation/`은 성공/실패 명령·시각·출력이다. `source-final.tar.gz`와 manifest는
최종 dirty tree source/문서 snapshot이며 build/runtime/기존 evidence를 제외한다.
첫 producer 당시 source snapshot은 별도로 생성하지 않았으므로 최종 archive를 첫
producer의 동일 source라고 주장하지 않는다. 해당 binary 원본과 최종 exact replay를
별도로 보관했다. `implementation.diff`는 직전 m8_saturation 최종 source 대비 변경이다.
커밋하거나 push하지 않았다. `SHA256SUMS`로 이 디렉터리의 보관 파일을 검사한다.

이번 수용은 고정 약10km/h에 한정한다. 정지 인계 중 추가 고장/protection 전환,
ACK/전체 통신 손실,30km/h의 감속/deadline 계약, 전체 Reference/M8,
Planner/localization·wall/Target는 후속이다.

## 재현

저장소 root에서 기존 CARLA source/SDK/fixture를 사용한다. 새 runtime/output 경로를
사용하고 이 보관 증거를 덮어쓰지 않는다. 실제 argv는 `validation/*.json`을 따른다.

```bash
ctest --test-dir build/m7-functional -L 'unit|integration.logical' --output-on-failure
python3 -m unittest discover -s tests/unit -p '*_test.py'
python3 tests/integration/carla/m7_1o_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --runtime build/m8-stop-replay/runtime-stop --output build/m8-stop-replay/stop \
  --native-actual build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --vehicle-substeps 320 --solver-work --held-steer-sleep --simulation-continuous \
  --speed-loop --speed-terminal normal-stop --ticks 4000
python3 tests/integration/carla/audit_m8_stop.py build/m8-stop-replay/stop \
  --output build/m8-stop-replay/stop-audit.json
python3 tests/integration/carla/audit_m7_1r_work.py build/m8-stop-replay/stop \
  --output build/m8-stop-replay/stop-work.json
```

입력 누락은 별도 runtime/output에 `--speed-terminal input-loss`를 사용한다.
이미 보관한 실행의 독립 감사는 directory 인수에 `docs/test-plan/evidence/m8_stop/stop-01`
또는 `input-loss-01`을 사용하고 출력만 새로운 build 경로에 쓴다.
