# M7-1r — 완전한 solver work와 단일 EV 정산

2026-10-27. 기준 commit `6046af0`. **제한된 native Actual→CARLA→solver work→EV 기능 연결 완료.**
최종 새2서버 각400receipt/400정산·319정상 권한 구간을 확인했다. 일반 주행·회생·wall/renderer
수용은 아니다. 기존 native 모드 회귀 중 서버 종료 SIGSEGV1회는 별도 OPEN으로 보존한다.
M6 구현·계약·검증 수치/판정, V1 계수, 기존20/10ms 주기·Drive30ms freshness는 변경하지 않았다.

## 구현과 책임

- 기존8-role Central→Zone→vECU→Actual CAN/P05→Zone→Central→Plant Adapter 경로를 유지한다.
  명령은 인과/권한 검사에만 쓰고 NoDrive setter 입력은 반환된 Actual뿐이다.
- pinned PhysX3.4 `updateNoDrive`의 진입/종료와320개 wheel 적분 전후를 읽는다. 원래 raw
  `mWheelSpeeds`·drive/brake/tire/damping·float dt를 보존한다. tire callback의 호출 수로 완전성을
  추정하지 않는다. ordinal/count/block·overflow·전후 연속성·실제 setter·최종 solver 값을 검사한다.
- wheel별 signed discrete motor work는 `Σ τ_drive × ω_after × dt_solver`다. 구동 wheel의
  NoDrive 회전각 적분과 같은 post-solver ω이며 공개 corrected getter를 사용하지 않는다.
  이는 chassis/tire/brake 전체의 기계 에너지 보존이나 연속시간 적분 정확도를 승인하는 값이 아니다.
- 기존 단일 `EvPowerModel::step_integrated_motion`에만 전달한다. 새 모드는 ZOH 전기 계산을
  함께 수행하지 않고 SimpleVehicle을 만들지 않는다. 기존 actuator 응답은 그대로1ms에서 계산한다.
  work 총량을 보존해1ms 모델 경계에 배분하고 마지막1ms 미만 잔여도 해당 frame 안에서 정산한다.
  원래 wheel/CAN 취득 시각·oldest dependency는 유지한다. 실제 setter 적용 witness와 CAN Actual의
  source를 구분하며 새 CAN Actual을 만들지 않는다. 상세 계약은 [ICD v15](../../../interfaces/carla-plant-adapter.md).
- frame checkpoint로 actuator/EV 모델 상태·cursor·장부를 함께 복원한다. 이미 실행한 CARLA physics나
  native 내부 메시지를 되돌리는 것은 아니다. 실패하면 그 rig를 폐기하고 새 process/INIT가 필요하다.
  서버는 receipt 뒤 `settle_work` ACK가 올 때까지 다음 stage를 막고 누락·중복·J/identity 불일치를 latch한다.
- `-StrataM7SolverWork`/`--native-solver-work` opt-in만 이 경로를 쓴다. 기존1q mode는 ZOH 예측/
  work invalid를 유지한다. 완전한 새 receipt만 `interval_work_valid=true`, 전체 주행 수용 flag는 false다.

UE source/static archive는 수정하지 않았다. hash로 고정한 외부 source copy에 project-owned
observer를 삽입하고 PhysXVehicles module을 빌드했다. 원본 module backup은 외부 build 디렉터리에
보존했다. [빌드 manifest](solver-build-manifest.json), [설치/원본40파일 확인](installation-audit.json).
frozen1q의 비계측 실행과 새 계측 실행의400개 상태/effort가 [정확히 일치](original-module-trajectory-comparison.json)했다.
관측 전용·정산 연결·기존 모드도 이 고정 시나리오에서는 [같은 물리 궤적](trajectory-comparison.json)이었다.

## 실제 시험 결과

Town03_Opt/mkz_2020/V1, world10ms, vehicle320, 비렌더링, source client/server `294096e-dirty`.
고정 VehicleRequest(acceleration0.2m/s², curvature0.02/m)의 출발/전진 범위다.

| 실행 | 관측/판정 |
| --- | --- |
| [관측 전용](observe-01/result.json) | 400개 완전한 work receipt. EV 연결 전 진단이며 당시 top-level work flag false는 유지했다. [11종 손상 거부](observe-01-work-audit.json) |
| [최초 정산 연결](energy-01/result.json) | 400receipt/400정산. [독립 work/EV 검사](energy-01-audit.json). 이후 report의 새 mode 명칭/flag를 명시했다. |
| [최종 A](energy-final-a/result.json), [최종 B](energy-final-b/result.json) | 각각400receipt/400정산·319정상 구간·4empty INIT. 각각128,000개 solver block(512,000 wheel 적분)을 관측. actor/설정 복원·SIGINT130. |
| [work 누락](work-missing-01/result.json), [work 중복](work-duplicate/result.json) | 각각200tick 뒤 다음 WORK 입력에서 native가 거부, 이전199frame만 정산. 다음 physics tick 없음. native exit1은 기대된 거부. |
| [ACK 누락](ack-missing/result.json), [ACK J 불일치](ack-energy/result.json) | 200tick 뒤 native 모델 정산은200회, 서버가 수용한 ACK는199회. 다음 stage/ACK에서 latch, 다음 tick 없음. |
| [ACK 중복 최종](ack-duplicate-final/result.json) | 200번째 ACK를 한 번 수용한 뒤 동일 ACK를 거부. 정산/수용 각200회이며201번째 tick 없음. [독립 검사](ack-duplicate-final-audit.json) |
| [기존 native 모드](legacy-native/result.json) | 400tick/319정상 기능 검사는 통과했으나 **서버 종료−11 FAIL**. 원래 runner의 COMPLETE 표기를 종료 수용으로 인정하지 않는다. |
| [기존 native 재실행](legacy-native-repeat/result.json) | 400tick/319정상, [기존 oracle 손상6종 거부](legacy-native-repeat-audit.json), SIGINT130. 앞선 종료 실패를 닫는 근거는 아니다. |
| [기존 zero 모드](legacy-zero/result.json) | 156개 runtime 검사/13receipt, [기존 oracle 손상8종 거부](legacy-zero-audit.json), SIGINT130. |

최종 A/B의 motor work는 각각 **74.65267507976446J**, 최종 SOC는 **0.6299940397683207**다.
최대 에너지 balance 잔차는 A **1.0303211×10⁻⁸J**, B **9.1872607×10⁻⁹J**로 기존 M6 기준
0.00072J 안에 있다. raw solver 방정식 재계산 최대 차이는 약5.96×10⁻⁸rad/s다(별도 binary32
산술 검산이며 음수/freshness 허용 오차가 아니다). 구동 substep의 후륜 평균 최소값은
0.000111716941319rad/s이며 전진 범위 위반은 없었다. work의 음수 절댓값/0 clamp는 사용하지 않았다.

[A 독립 검사](energy-final-a-audit.json)와 [B 독립 검사](energy-final-b-audit.json)는 원본 wire
CRC/P05·권한/명령 인과·setter, 모든 substep의 방정식/연속성,1ms 분할 work 합, 단일 EV 누적 J,
SOC·chemical/motor/circuit/aux/ohmic/capacitor 장부를 교차 확인한다. 각11개 solver 손상 및7개
energy 손상을 거부했다. source age 최대20ms, 최소 command expiry 여유1ns는 기존과 같으며
wall jitter 여유가 아니다. 성공 receipt의 sleeping-return 경로는 이번 실제 출발 시나리오에서
관측되지 않았으므로 그 분기의 live 수용이나 실제 회생 수용으로 확대하지 않는다.

Normal/ASan은 각각 [69/69](normal-01.log) / [69/69](asan-01.log)다. 기존64개와 새5개가
signed work 보존·fractional 경계·누락/잘못된 scope/역회전·중간 실패의 frame rollback·잔여 정산·
중복 commit을 검사한다. M6 전체 회귀, UE 자체 sanitizer/TSan, wall2/4ms는 새로 실행하지 않았다.

## 실패·수정·남은 문제

1. [native build01](native-build-01.log)은 incomplete State를 header의 inline unique_ptr reset에서
   파괴하려 해 실패했다. 정의를 cpp로 옮긴 뒤 후속 build/69개 시험을 통과했다.
2. [최초 ACK 중복 실행](ack-duplicate/result.json)은 첫 ACK 수용 후 중복 거부까지 동작했지만,
   probe의 집계 증가가 break 뒤에 있어 수용 횟수를199로 잘못 기록했다. 독립 검사가
   [집계 불일치를 거부](audit-ack-duplicate.log)했다. 원본은 그대로 보존했고 증가 위치를 수정하여
   `ack-duplicate-final`에서200회로 재검증했다. 서버/EV 정산 법칙 변경은 없다.
3. **OPEN-M7-1R-EXIT-01:** legacy-native의 SIGINT 종료 중 SIGSEGV−11. [원본 스택](legacy-native-exit-Diagnostics.txt)은
   `carla::multigpu::Listener::OpenSession`과 Asio accept completion을 가리킨다. `listener.cpp`의
   Stop(cancel/close/stop/reset)와 callback의 무조건 OpenSession 재등록 사이 경쟁이 조사 후보이며
   근본 원인 확정/수정은 아니다. source 종료 안정성은 여전히 OPEN이다. observer 함수가 스택에
   없다는 이유만으로 관련성을 배제하지 않는다. 같은 module의 fresh 재실행은130으로 종료했다.
4. 기존 runner는 probe exit0만 보고 서버−11도 COMPLETE/exit0으로 반환했다. 이번에는 실제
   server exit130 및 강제 종료 여부도 판정하여 비정상 종료를 `SERVER_EXIT_FAIL`로 처리하도록 수정했다.
   앞선 원본 JSON/로그는 고치지 않았다. 최초 전체 종료 점검 assertion 실패도 이−11을 탐지한 결과다.

13개 소유 서버 중12개가 SIGINT130,1개가−11이며 강제 kill은 없었다. [종료/자원 점검](cleanup-audit.json)은
실패를 별도로 표시하고 최종 UE process 종료·2200/2201/2202 port 해제를 확인한다. 정상 실행과
fault containment의 pause/reset/actor 제거/설정 복원 결과는 각 result.json에 있다.

## 보존·재현·후속

- 기존 evidence **2,168파일**과 plain SHA256SUMS **1,561항목**이 [모두 불변](frozen-prior-audit.json)이다.
  새 raw JSONL은 [무손실 gzip](compression.json), 원본 server/client 로그와 실행한 Python snapshot은
  [해시/복사본](provenance-copies.json)으로 보존한다. 실패 frame/로그를 제외하지 않는다.
- `server-*.json`의 argv·실행 binary/script hash와 [suite argv](suite-argv.json)가 실행 근거다.
  원래 solver source/UE binary/venv는 기존 외부 경로에 두고 저장소에 vendoring하지 않는다.
  [SHA256SUMS](SHA256SUMS)는 새 evidence 전체를 고정한다.
- 재현: `tools/carla/m7_nodrive/build_solver_observer.py --engine <UE> --output <external-dir> --install`,
  기존 installer/CarlaUE4 build, native build 뒤 기존 runner의 `--native-actual <exe> --solver-work`를
  사용한다. engine process가 없는 상태에서만 module 설치/`--restore`가 가능하다.
- 다음 **M7-1s**는 종료−11의 최소 재현/원인 분리·수정 검증을 먼저 진행한다. 그 뒤 같은 native
  Actual 경로의 가속→감속→정지·재출발, 보호 제동, signed 회생을 각각 작은 시나리오로 확인한다.
  이후 wall2/4ms·계측 비용/clock uncertainty를 검증한다. 전체 ODD·renderer·AI/Jetson은 별도 gate다.
