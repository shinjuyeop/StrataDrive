# M7 통합 검증 및 종료 검토

2026-10-28. **전체 M7 NOT CLOSED.** 고정 시나리오의 native Actual→CARLA→solver work→단일 EV
기능 연결에 보호 Actual의 연속 적용·고정 시나리오의 자연 완전 정지와
로딩/클라이언트 단절 시 종료 교착 수정을 추가 검증했다.
실시간 실행 기회와 wall fault→보호 전환 수용은 완료되지 않았다.
하위 단계를 계속 늘리는 대신 이 문서의 남은 gate를 기준으로 관리한다.
M6 Host quiet SIL/Python MIL의 구현·계약·결과·종료 판정은 변경하지 않는다.

## 이번 통합 범위

[실행 원본·실패·집계](test-plan/evidence/m7_carla_integrated/README.md),
[재현 runner](../tests/integration/carla/m7_integrated_run.py),
[ICD](icd/carla_plant_adapter.md)를 함께 따른다.
Controller20ms·Zone/vECU10ms·world/state10ms·영상50ms·Drive source-age30ms 및
원래 exclusive expiry를 유지했다. V1 가상 EV 계수·320 내부 분할·원래 solver wheel source도 유지한다.

입력은 시험용 **상위 VehicleRequest** 일정이다. 실제 Central 배분→Zone→vECU 응답→
CAN/P05 Actual 반환과 서버의 권한 검사를 모두 거친다. Actual이나 CARLA effort를 시험 일정으로
직접 대체하지 않는다. 원래 native root request의 source time으로 단계별 입력을 독립 검증한다.
M8 route-following Controller나 AI 주행을 구현한 것은 아니다.

| 검토 gate | 현재 판정 / 근거 |
| --- | --- |
| 고정 환경·모델·단일 writer | CARLA0.9.16 source/Client `294096e-dirty`, UE4.26.2 pin, Town03_Opt/mkz_2020, V1 모델 hash 고정. 외부 writer/tick·synthetic stage 거부 유지 |
| 정상 주행·제동·에너지 | 9s/900구간에서 좌조향 가속→signed 회생→마찰 제동/휠 정지→우조향 재출발 관측. 독립 raw-wire·solver 방정식·work/EV 장부 감사. Reference 전체 속도/ODD 수용 아님 |
| 영상·state·lifecycle | 통합 evidence의 실제 실행별 판정 적용. RGB/학습·평가 GT 분리, frame/source timestamp 검증, 누락 차단·pause/reset/새 INIT 확인 |
| 실시간2ms/4ms·clock | **NOT ACCEPTED.** 실제 owner 호출별 계측과 독립 monitor를 추가하고, 의도적으로 입력을 보류한 구간에서 원래2ms/4ms deadline 위반→native 보호 선택→다음 tick 차단을 검증했다. CARLA 대기 중 owner 실행·simulation↔wall uncertainty·연속 정상 wall 실행은 미완료 |
| 보호 Actual 제동 | **기능 경로 검증 완료.** trusted safety 요청 후 원래 LocalProtection Actual로200개 physics 구간·EV 정산을 계속하며 감속·휠 정지 관측. 정상 재개·누락·stale/future/다른 출처 거부. 명시적 opt-in 보호 hold에서 차체 자연 완전 정지까지 한정 검증. wall fault 자동 연동은 OPEN |
| 시작·종료 안정성 | 준비 후 네트워크 경합 수정은 M7-1s FIXED_LIMITED 유지. 별도 sync RPC/game-thread 종료 교착을 재현·수정하고 로딩 중 SIGINT30s 내 종료 확인: **FIXED_LIMITED**. client-loss 동기 tick 대기도 수정 후 영상 유/무 종료 확인. 원래180s 준비 timeout/강제−9와 renderer 별도 원인은 보존 |
| Reference 경로 | 54m 직선 후보 좌표/곡률·맵 hash 고정. M8의30km/h 적합성·추종/정지 시험은 NOT RUN |

## 이번에 해결한 문제

1. spawn 직후 첫 physics tick 전 ActorSnapshot에는 새 ego가 아직 없을 수 있다.
   index0은 `valid=false`로 남기고, 이후 누락은 실패 처리한다. 초기 좌표/속도를 조작해 채우지 않는다.
2. 기본 UE float `sensor_tick=0.05`에서 첫 영상 간격60ms를 재현했다.
   M7 전용 flag와 정확한 camera role/종류/주기를 모두 만족하는 센서만 actor tick을 매 frame 실행하고,
   원래 CARLA frame counter의5배수에서 실제 취득한다. capture나 timestamp를 사후 보정하지 않는다.
   기본 CARLA 센서 동작은 이 opt-in 조건 밖에서 유지된다. 내부 센서 스케줄을 조정했으며
   native/M6 계약·차량 운동·에너지 코드는 변경하지 않았다.

## 종료 교착·보호 Actual 후속 수정

[실행·실패·독립 감사](test-plan/evidence/m7_carla_recovery/README.md).
보호 요청의 인과 검증은 [순서 보완 후 실행](test-plan/evidence/m7_carla_recovery/causal-followup/README.md)이
최신 근거다. 이전3회는 요청을 physics 완료 후 주입했으므로 요청 인과 검증 근거에서 제외하고
물리 응답 관측 자료로 보존한다. 보완 후에는 advance 전에 요청하고 이후 native 선택/Actual을 검증했다.
RPC worker가 game thread의 sync callback을 기다리는 중에 game thread가 worker join을 기다리던
교착을 수정했다. 종료 신호로 대기를 먼저 취소하며, 대기 중인 mutation을 실행하지 않는다.
실제 pinned header component 원본 TIMEOUT/수정5개 통과와 fresh CARLA 로딩 중단을 대조했다.

M7 native fixture는 보호를 선택한 뒤에도 기존 owner/Actual service를 계속한다.
Plant Adapter는 정상 credit을 다시 열지 않고 같은 Release/epoch의 LocalProtection Actual만
별도 검사·적용한다. 이전 normal proof, 합성 명령, 갱신한 sensor timestamp로 대체하지 않는다.
원래 wire/P05·source age·solver/단일 EV 장부와 single writer 경계를 독립 감사했다.
정상900구간·RGB/GT 각180개 회귀도 확인했다. M6는 변경하지 않았다.

## 남은 문제를 닫는 작업

**남은 주 작업은 정상 wall owner/수신 실행과 clock agreement를 연결하고, wall fault 이후 CARLA에 보호 Actual을 연속 적용하는 것이다.**
terminal native 응답은 아래 후속 실행에서 연결했다.
현재 Python/RPC/전체 solver JSON 진단 loop의 지연을 단순 timeout 증가로 해결할 수 없다.

- native owner/감시의 wall 실행을 CARLA 응답 대기와 분리한다. 실제2ms 실행 기회·4ms 완료를
  monotonic 기준으로 계측하고, 지연 시 normal 권한을 닫는 경로를 검증한다. trace는 비동기 수집하되
  frame별 work 정산 증거를 잃지 않아야 한다. 최적화 전후 동일 시나리오의 물리/work 비교를 유지한다.
- 독립 wall 지연 검출→native 보호 선택→다음 tick 차단은 아래 한정 시험으로 연결했다.
  actuator/전기 분리와 terminal native timer/service 연결은 아래 후속 결과를 따른다. 정상 수신 경로 연결은 남는다.
  Actual/work 자체가 없을 때는 다음 tick 차단을 유지하며 그 차단을 물리 안전 정지로 수용하지 않는다.

현 loop의 native 요청 응답 시간은 짧아도, RPC/trace 대기 중 owner를 호출하지 않는 구조는 남는다.
단순 heartbeat만 추가하거나 멈춘 simulation clock으로 wall freshness를 갱신해서는 해결되지 않는다.
새 wall runtime은 원래 clock agreement·source provenance와 실제 job 실행 증거가 필요하다.

## Wall guard 후속 결과

[실행 원본·중단·sanitizer 제한](test-plan/evidence/m7_carla_wall_guard/README.md).
별도 opt-in `WALL_ARM` 진단에서 기존 M4 schedule/deadline monitor를 그대로 사용했다.
원래8-role poll 및 physical step의 실제 CLOCK_MONOTONIC 시작/완료만 기록하고,
stdin polling/monitor heartbeat/과거 logical subjob을 실행 기회로 채우지 않는다.
선언한 첫 release 전100ms는 진단 준비 구간이며 이전 INIT/정상 실행을 감시했다고 주장하지 않는다.

실제 CARLA199구간·199정산 후 다음 입력을 보류하자 독립 monitor가9개 owner의 미완료를 검출했다.
검출→local 보호 선택0.961ms, 검출→adapter pause 확인4.722ms를 관측했다.
이는1회 관측치이며 보장 상한이 아니다. native가 자체적으로 기존 Central/Zone/leaf 보호를 선택하고
credit0·local selection mask255를 읽었다. 이 mask는 원격 ProtectionAck나 새 Actual이 아니다.
마지막 완료 barrier의 logical time은 유지하고 다음 frame 권한을 영구 차단했다.
시험 입력에 `PROTECT`/압력값을 넣지 않았으며, 별도 wall→simulation 시각 변환도 만들지 않았다.

**기존 정상 runner의 owner 실행은 아직 CARLA 대기에 묶여 있다.** 아래 terminal 후속 모드만 독립 진행한다.
기존 coupled `ActuatorElectrical::step()`은 work가 있어야 actuator도 진행한다.
아래 새 경로는 실제 response 모델을 독립 진행하므로 work 없이도 새로운 actuator 취득을 만들 수 있다.
이전 Actual을 restamp하거나 관측 work 없이 전기 정산을 진행하는 것은 허용하지 않는다.
다음은 원래 ECU service/timer에 새 경로를 연결하고 clock mapping/불확실성·in-flight fault를
검증하는 작업이다. 위 wall 진단은 완료 barrier에서만 수행했으며 RPC 진행 중 차단/연속 제동 수용은 아니다.

## Actuator 응답과 관측 EV 정산 분리

[구현·검사·기존 출력 재생](test-plan/evidence/m7_carla_wall_guard/deferred-response/README.md).
M7 모델 계층에 `DeferredObservedWork`를 추가했다. `advance_actuators()`는 work 수신을 기다리지
않고 원래 Steering/Brake/Drive response를1ms 이하 구간으로 진행한다. `settle_observed_frame()`은
완료된 work와 해당 과거 구간의 실제 coil 이력으로 단일 EV만 정산한다. 전체 frame의 EV commit은
원자적이며 실패해도 이미 진행한 actuator를 되돌리지 않는다. 두 API의 mutation owner는 하나다.

work가 없는250개1ms 구간에서도 보호 response를 계속하며 모델 시각의230ms 안에 torque0·pressure1MPa를
검사했다. EV/HV/BMS 값과 시각은 동결하고 wheel 부재를0으로 채우지 않았다.128개 이력 슬롯이
넘치면 전기 정산은 실패로 고정하지만 actuator 보호는 계속한다.128은 저장 공간 상한이며
freshness 완화가 아니다. Power의 기존50/70ms source/dependency 경계 밖 전류는 opening dwell에
쓰지 않는다. 잘못된/중복 work·혼합 모드·sensor identity 변조 및 재개도 거부한다.

30ms 단위 지연 정산 component 대조에서 원래 방식과 SOC·signed motor work·손실·전압·전류가
정확히 일치했다. 원래 native 실행 모드는 유지했으며 기록된 정상900구간과 보호400구간의 입력을
재생한 모든 native 출력(terminal 포함901/401개)도 정확히 일치했다.
이 당시 결과는 **모델 계층 분리 완료**이며 아래 terminal wall 후속 실행과 구분한다.
새 CARLA 실행·2ms/4ms 수용·wall fault 이후 CARLA 물리 제동 완료를 주장하지 않는다.

## Terminal wall service와 보호 Actual 지속

[실행·실패·독립 감사](test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md).
`--wall-response` opt-in은 기존 wall fault 이후 **같은 native 세션/모델**을 terminal 분기로 넘긴다.
원래 Central/Zone/leaf 보호를 먼저 선택하고 single mutation owner가 monotonic timer로
8-role service와 response를 실행한다. 입력 read/WORK 수신을 기다리지 않는다. 응답 적분의1ms 이하
내부 분할을 ECU job으로 세지 않으며 지연 뒤 과거 owner poll을 재생하지 않는다.
원래 Controller20ms/Zone·leaf10ms/BMS20ms 설정과 CAN/P05 source·epoch를 유지한다.

fresh CARLA199구간/199정산 후 입력 보류→독립 deadline 검출→native 보호 선택→adapter pause를
실행했다. 이후300ms 동안 steering/brake/drive의 새 LocalProtection Actual을 각각30회 관측했다.
토크0·압력1MPa 첫 동시 관측은209.053ms였다. 이는 native 응답 모델 관측이며 CARLA 차체 제동이 아니다.
EV time/장부와 마지막 wheel 시각은 유지하고, 만료한 wheel을 새 취득으로 발행하지 않았다.
해당 terminal 구간에서 owner0..9 각각150개 완료, 완전한 구간의 누락/late0을 관측했다.
단일 짧은 구간이며 정상 전체 실행의 실시간 수용이나 보장 상한으로 확대하지 않는다.

일반/ASan 각86/86, TSan6/6 및 실제 terminal process 검사에서 race 경고는 없었다.
TSan process에서는 owner0..3의 완료 누락을 각각6/7/2/1개 관측·보존했다. sanitizer 통과와 timing
통과를 구분하며 그 누락을 뒤늦은 poll로 채우지 않았다. 기존 정상/보호 입력 재생901/401개 출력은
정확히 같았다. 최초 fractional clock 시험에서 새 보호 output을 이전 substep에 넣어 거부된 오류를
수정했다. handoff anchor에서 먼저 보호를 선택해 source 이후에만 적용하며 실패 로그도 보존했다.

**Clock/적용 경계:** terminal local time은 마지막 barrier + handoff 이후 실제 monotonic 경과다.
`LOCAL_TERMINAL_RESPONSE_NOT_CARLA`로 분리 기록하며 simulation clock과 동기됐다고 주장하지 않는다.
기존 FrameClock은 terminal latch로 닫고, 이 Actual을 서버 stage/advance에 전달하지 않는다.
따라서 정상 wall loop/clock uncertainty, in-flight RPC fault, CARLA 연속 보호 제동은 OPEN이다.
이번 서버는 정상 cleanup 후 SIGINT 약2.920s에 종료했다. 이 당시 결과는 client-loss 종료 문제의 해결 근거가 아니며 아래 일괄 검증과 구분한다.

대화 중단으로 camera 실행기가 사라진 실행은 미완료로 보존했다. 남은 전용 서버에 SIGINT를
보냈지만30초 안에 종료하지 않아 강제 종료했다. 기존 로딩 중 RPC 교착 수정은 이 별도
client-loss/동기 대기 종료 문제의 해결 근거가 아니었다. 아래에서 별도 재현·수정했다.

원래 renderer Distance Field crash 원인은 여전히 미확정이다. 이번 짧은 영상 시험이 성공해도
모든 content/장시간 안정성을 주장하지 않는다. 정지 시 휠 회전0과 차체의 작은 잔류 속도는
구분해 기록했다. 새 stationary 허용 오차를 임의로 만들거나 음수를0으로 바꾸지 않았다.

M8 Controller/30km/h 경로 적합성, M9 diagnostics, AI 학습·Jetson 배포는 각 후속 milestone의
범위이며 M7 검증을 진행할 때마다 새 선행 작업으로 추가하지 않는다.

## 종료·정지·clock 일괄 검증 (2026-10-28)

[수정 전 실패·중간 실패·최종 실행 및 재현](test-plan/evidence/m7_carla_recovery/batch-closeout/README.md).

- **client-loss 종료 FIXED_LIMITED:** 정상199구간/정산 후 probe를 cleanup 없이 exit73으로
  종료했다. 수정 전에는 SIGINT30s 후 강제−9가 필요했다. game thread의 synchronous tick 대기가
  engine exit를 확인하도록 수정하고 종료 시에만 world physics 등록과 post-tick 발행을 차단했다.
  없는 client의 tick을 조작해 만들지 않는다. 수정 후 영상 유/무 모두 원래 frame을 유지하며 종료했다.
- **보호 정지 FIXED_LIMITED:** PhysX NoDrive는 같은 비영 조향각도 매번 wake 입력으로 취급했다.
  `--held-steer-sleep`에서 연속한 두 구간 모두 원래 보호 Actual이며 drive0·동일 steer·동일 양의
  friction brake인 경우에만 그 wake 조건을 생략한다. 힘/속도/pose/타이어식은 바꾸지 않는다.
  자연 수면 후 기존 steer 유지가 재기동시키던 문제를 고정 Town03/V1 시나리오에서 해결했다.
  400receipt/400정산, 첫 sleep index278부터122구간 body/wheel exact0, 마지막100구간 pose 동일.
  이는 PhysX sleep 모델의 정지이며 연속체의 엄밀 정지/OEM·전체 ODD 수용은 아니다.
- **work 증거:** 최초 수정은 sleeping zero-work 검증기의 기존 steer0 조건에 걸려 index279에서
  fail-closed했다. observer ABI2에 보호 hold witness를 추가하고 server/solver 및 이전 구간의
  원래 Actual/동일 effort를 독립 검사했다. ABI1 과거 evidence는 원래 규칙으로 검사한다.
  미세 잔류 속도·pose 변조·hold 누락·이전 effort/보호 변조5종을 거부했다.
- **clock은 미수용:** 새 post-physics 취득을 Host CLOCK_MONOTONIC begin/end로 감쌌다.
  cached receipt도 최초 bracket을 유지하며 simulation/CAN 시각을 바꾸지 않았다. 이 bracket은
  clock mapping 후보 관측일 뿐이다. 고정 offset의 교집합은 없고, 의도적 pause를 제외해도
  현재 RPC/전체 trace 경로의 취득→다음 native 처리와 owner 호출 공백이 원래 budget을 초과한다.
  단순 offset·heartbeat·timeout 증가로 정상 wall 연결을 승인할 수 없다.

남은 필수 작업은 하나의 통합 작업으로 수행한다: **정상 wall owner/수신 분리 + 원천별 clock
agreement/uncertainty + in-flight fault 차단 + CARLA 보호 Actual 연속 적용**. 이를 연결한 다음
동일 suite의 정상/영상·고장·정지·에너지 회귀와 원래2ms/4ms·30ms를 함께 판정한다.
현재 functional 시간의 native 입력을 wall로 재표기하거나 terminal local Actual을 서버에 넘기는
단축 경로는 구현하지 않았다. M7 전체는 계속 NOT CLOSED이며 별도 새 milestone을 추가하지 않는다.
