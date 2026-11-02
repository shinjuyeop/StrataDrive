# M8 정지 hold 이후 보호 전환·30km/h 계약 검토

2026-11-02. **PASS_HOLD_TO_PROTECTION_SIMULATION_ONLY**.
Town03 약10km/h의 NormalStop 인계 후 명시적인 SIL 안전 요청을 주입한 실제 CARLA
시험이다.30km/h는 기본 제동 예산 충돌의 계약 시험만 수행했다.
[사전 protocol](protocol.md), [전체 수치](results-summary.json),
[물리 응답 곡선](hold-protection-02.png), [30km/h 검토](../../normal-stop-30-contract-review.md)를 따른다.

## 실제 실행 결과

`hold-protection-02`는 첫 PI release+15s에 NormalStop을 시작하고, 원본 ACK로
처음 PowerDown에 들어간 시각 H의100ms 뒤8-role local protection을 선택했다.

| 검사 | 결과 |
| --- | --- |
| 사건 시 body 속도 / 사건 전 PI | 9.982294km/h / 750 releases; 독립 식 최대 차이0 |
| body·네 wheel 연속 정지 시작 | NormalStop 요청 후2.987999558s |
| 원본 ACK 후 최초 PowerDown job H | 요청 후3.1704s |
| 최초 물리 hold admission | 요청 후3.177999576s |
| 보호 선택 | H+100ms; 요청 후3.2704s |
| 보호 상태 torque0 acquisition / receipt 관측 | 주입 후5.6ms / 약7.6ms |
| brake≥1MPa acquisition / receipt 관측 | 주입 후185.6ms / 약187.6ms |
| 실제 hold / protection 물리 구간 | 10 / 2092 |
| 총 physics / EV settlements | 4000 / 4000 |
| 최대 독립 energy balance 잔차 | 약2.626e-8J |
| 보호 전환 중 body·네 wheel | 정지 유지 |
| 마지막1초 pose drift | 0m |
| owned 서버 종료 | 130; 강제 종료 없음 |

토크는 보호 요청 전에도 이미0이었다.5.6ms는 새 LocalProtection 원본 표본의
acquisition 지연이며 주행 중 토크 차단 시간으로 해석하지 않는다. 보호 이전 hold와
보호 이후의 원본 CAN/owner-wire·source/expiry·8-role 권한을 모두 검사했다.
[Terminal 감사](hold-protection-02-audit.json), [native/solver/EV 감사](hold-protection-02-work.json)를 따른다.
이 모드는 ACK-loss 검출이나 전체 통신 단절을 시험하지 않았으며 NormalStop
Complete/HV-off 수용으로 표시하지 않는다. ECU/센서 수집과 물리/정산은 계속된다.

## 구현·검증

서버 admission은 보호 선택이 마지막 수용 normal/hold보다 뒤이며 동일 released
session·보호 mask255·normal credit0·새 LocalProtection Actual일 때만 hold를 대체한다.
원본 whole-interval freshness와 wheel/expiry를 유지한다. 남은 StopLease packet을
보호 권한으로 쓰거나 normal/hold로 재개하지 않는다. wall hold 수용은 추가하지 않았다.

- C++ unit/logical1215/1215, Python233/233, 영향 범위 ASan/UBSan41/41.
- 보호 후 hold 재개 거절 assertion 추가 후 Release/ASan 해당 component 재검사 통과.
- C++ stop proof8종·보호 authority4종 변조와 normal/hold 재개 거절 확인.
- Raw terminal evidence22종, solver11종·EV7종 변조 거절.
- CLI 직렬화: Release/ASan 각각4001 원본 관측; hold10/protection2093 관측 검증.
- 기존 NormalStop·입력 누락: 최종 native binary에 각각4001관측 replay, JSON 전체 일치.
- 기존 M8 evidence1135파일과 v1 model hash 불변. 서버 설치89파일 hash 확인.

CLI/replay의2093 protection 관측은 최종 settlement 행을 포함한다. 새 물리 실행이나
2093개의 보호 물리 구간으로 세지 않는다. 최종 정확한 구간 수는 실제 work 감사의2092다.
`replay-stop-02/`, `replay-input-02/`가 최종 binary에 대한 기존 시나리오 동등성이다.
앞선 이름에 `final`이 있는 replay는 직렬화 수정 전 실행이므로 최종 근거로 쓰지 않는다.

최종 native SHA256은
`bc7d88ee15d27c881dd3fcf50a7dfa38c70f66a4a0eab9ffe3f6571932a84404`다.
실패/성공 producer는 각각 `producer-hashes.json`/`producer-02-hashes.json`,
실행 전 source는 `source-producer*.tar.gz`와 manifest, 실제 실행 binary/child Python은
`runtime-*/probe`에 있다. 서버 binary는 두 실행에서 동일하다. `source-final.tar.gz`는
마지막 테스트 보강과 문서까지 포함한 dirty tree snapshot이다. build/evidence를 제외했고
커밋하거나 push하지 않았다. `implementation.diff`는 직전 m8_stop 최종 source 대비다.

## 보존한 실패

첫 `hold-protection-01`은 C++ 내부 proof의 StopLease/ACK를 새 모드 JSON에 출력하지
않아 최초 hold stage에서 서버가 `bootstrap_cannot_drive_or_resume`로 latch했다.
1898 physics/1898 settlements 뒤 다음 구간은 실행되지 않았다. 서버는 정상 종료130이다.
[완료 구간 독립 solver/EV 검사](hold-protection-01-prefix.json)는 이1898구간만 검증한다.
전체 native 감사나 실제 보호 전환의 성공으로 세지 않는다. 표준 work 감사는 예상하지
않은 incomplete interval을 거절했다(`failed-run-work-01`). 원본 FAIL은 유지했다.

동일 누락을 `cli-serialization-01`로 재현한 뒤 새 mode의 JSON에 원본 packet을 넣었다.
서버 gate·lease lifetime·Actual source는 바꾸지 않았다. 수정 뒤 CLI와 실제 두 번째
실행이 통과했다. 첫 component 실패도 새 모드 내부 proof export 분기 누락을 잡았고,
이를 수정한 뒤 별도 JSON 출력 누락이 실제 서버에서 드러난 것이다.

`build-contract-01`은 GoogleTest assertion 매크로의 중괄호 누락 경고를 error로
처리한 실패다. 중괄호를 추가했다. `asan-build-01`은 마지막에 존재하지 않는 별도
wall target을 요청한 실패이며 wall tests가 포함된 실제 target으로 다시 빌드했다.
마지막 hold 재개 검사의 첫 assertion은 export에서 옛 packet이 사라진 뒤에도 특정
거절 사유를 기대해 실패했다. 실제로는 앞선 terminal guard가 이미 거절했다. 마지막으로
수용한 원본 hold packet을 명시적으로 보관·재생하도록 시험을 고쳐 보호 latch 자체의
거절을 확인했다. production 동작은 바꾸지 않았다. 모든 시도·명령·시각·로그는
`validation/`에 있다.

## 30km/h 판정과 다음 단계

현재1m/s²/5s는 이상적30km/h 감속8.333s부터 만족할 수 없다. 실제 NormalStop에
낙관적 입력을 준 C++ 시험에서5s BrakingTimeout과 latch를 확인했다. 잔여 속도는
이상적으로도12km/h다.10km/h 입력은 같은 조건에서 handoff에 도달했다.
[수치](contract-review.json)는 일정 감속 계산이며 실제 차량 모델 결과가 아니다.

기본 설정은 유지했다. 다음 후보는 별도30km/h fixture의1m/s²·제동10s·shutdown2s다.
검증된20s startup과 긴 Town06 직선으로 고정 사건/평가 기준을 먼저 정의해야 한다.
30km/h 실제 정지·ACK/전체 통신 손실의 물리 응답·전체 Reference/M8·Planner/localization·
wall/Target는 후속이다. 과거 UE renderer/GC 실패 원인도 OPEN으로 유지한다.

## 재현

저장소 root에서 기존 source CARLA/SDK/NoDrive fixture를 사용하고 새 경로를 지정한다.

```bash
ctest --test-dir build/m7-functional -L 'unit|integration.logical' --output-on-failure
python3 tests/integration/carla/check_m8_stop_cli.py \
  docs/test-plan/evidence/m8_stop/stop-01 \
  build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --output build/stop-cli-replay.json
python3 tests/integration/carla/m7_1o_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --runtime build/m8-stop-fault-replay/runtime --output build/m8-stop-fault-replay/run \
  --native-actual build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --vehicle-substeps 320 --solver-work --held-steer-sleep --simulation-continuous \
  --speed-loop --speed-terminal stop-protection --ticks 4000
python3 tests/integration/carla/audit_m8_stop.py build/m8-stop-fault-replay/run \
  --output build/m8-stop-fault-replay/terminal.json
python3 tests/integration/carla/audit_m7_1r_work.py build/m8-stop-fault-replay/run \
  --output build/m8-stop-fault-replay/work.json
python3 tests/integration/carla/check_m8_stop_corruptions.py build/m8-stop-fault-replay/run \
  --output build/m8-stop-fault-replay/mutations.json
```

보관 증거를 덮어쓰지 않는다. `SHA256SUMS`는 이 디렉터리 보관 파일의 무결성 목록이다.
