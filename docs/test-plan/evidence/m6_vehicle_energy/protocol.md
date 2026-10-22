# M6 vehicle/EV energy integration — prospective protocol

2026-10-22. HEAD/origin/main f57e18cff5a05352b49629aceef09fdf79831c05,
fetch 후 동일, clean. 상위/저장소 AGENTS.md 없음. 사용자 변경 없음.
M5 Host 한정 수용, M6 첫 모델/MIL 및 과거 FAIL/OPEN을 유지한다.

## 범위와 고정 수치

실제 actuator actual→SimpleVehicle→EV circuit/Battery를 단일 physical owner에서
같은 interval mechanical work로 결합한다. ECU source/expiry·20ms envelope,
host10-v1(10ms/18ms support), 큐8,2ms opportunity/4ms guard는 유지한다.
Vehicle torque/pressure/angle은 구간 시작 actual/ZOH이며 speed는 vehicle이 적분한다.
새 work port는 interval 결과(source=end, dependency<=begin)이고 측정 sample로 가장하지 않는다.
원래 speed acquisition은 그대로 보존한다. 실패 시 후보 vehicle/electrical 상태를 commit하지 않는다.

판정은 실행 전에 고정한다:
- 차량 Δkinetic = motor work − friction work − road work, residual<=1e-5J.
- electrical mechanical work − vehicle motor work <=1e-6J.
- battery chemical draw = Δcapacitor + Δkinetic + friction + road + motor/inverter loss
  + battery ohmic + auxiliary + precharge/main/discharge loss; residual<=0.001J.
- 기존 electrical ledger의 capacity*4e-12J 수치 guard도 유지한다.
- battery received DC와 negative mechanical work는 별도로 집계한다. SOC 증가만으로
  회생을 입증하지 않는다(auxiliary/idle/copper loss 때문에 SOC 순감소가 가능하다).
- 실제 regen에서 torque<−1Nm/positive speed, negative mechanical work와 received DC>1J,
  실제 friction pressure>1kPa의 동시 관측을 요구한다.
- charge-zero는 initial SOC0.96을 실제 Battery sensor→BMS(기존 .95 charge-SOC zero)로
  전달한다. 실제 charge limit=0/capability=0, negative torque 미발생, friction 감속/stop 요구.

## 새 시험 fixture profile energy-cycle-v1

기존 fixed-demand/M5/M6 profile은 보존한다. 새 --energy-cycle nominal|no-charge는
--three --simple-vehicle --native-watch를 필요로 하며 quiet FIFO CPU/priority는 기존값이다.
Central 실제 arm 기준으로 phase를 고정한다:
0–2s acceleration2m/s² (기존300Nm 한도 그대로),2–2.6s coast0,
2.6–4.5s mixed/low-speed brake−1m/s² 및 explicit hold,
4.5s 이후 accel0/hold. Curvature0.02 유지. 실제 모든 command/result/Actual은 network/codec 경유.
5000ms 이상 arm 후 실제 정상 cycle 관측을 완료하고 기존 NormalStop/HV-off를 요청한다.
readiness 기준 관측8000ms, 기존 shutdown tail2500ms. 이는 새 scenario 관측 길이이며
명령/권한/deadline/braking5s/shutdown2s의 연장이 아니다.
runner supervisor25s, quiescence 관측11s, process scenario13s, persistent plant18s 상한.
native guard는 관측8000+tail2500ms 전체를 포함한다. 미완료/누락/강제 cleanup은 FAIL이다.
재가입 후에는 실제 새 arm부터 phase를 시작하고5000ms 이상 관측한다.
transport trace만 새 유한 관측에 맞춰 bounded storage를 사전 할당한다(제어 큐 변경 없음).

## 유한 실행 목록

1. legacy quadrature mismatch 최소 논리 재현1회(새 coherent-ledger assertion 수정 전 FAIL),
   interval work/metadata/transaction/propulsion/regen/friction/stop/refinement 관련 C++ 계약.
2. 개발 중 변경 경계와 필요한 실제 SDK 비교만 실행. 구체 실패/수정과 연결해 추가 실행 기록.
3. 최종 Normal FIFO quiet:
   nominal normal1, no-charge normal1, nominal command-loss1, owner-pause1, Rear restart-live1.
   fault는 기존 정상 전제조건과 실제 이동 후 주입. 정상 성능과 보호 성공을 별도 판정한다.
4. 최종 실제 SDK ASan/UBSan·TSan 각각 nominal normal1/restart-live1.
   기존 fixed-layout TSan, fully instrumented SDK/Boost 경계 기록. wall-time은 Normal과 별도.
5. 변경 경계 TSan1회, 최종 전체 C++ Normal·ASan/UBSan 각1회(기존999 이름/assertion 보존).
   새 oracle/fixture/runner Python + 기존 model/pilot 회귀. build/ 없는 tracked source export 확인.

실제 energy.csv는 bounded 기록 후 종료 시 저장한다. 최초 보호·명령 expiry·session/arm·
물리 energy/source/model identity와 실제 thread/IP 설정을 보존한다. 모든 build/test는
build/.m4-exclusive.lock. wall 측정 중 빌드/검색/분석을 병행하지 않는다.
실패/timeout/누락/예상 밖 SDK·sanitizer 오류는 원본 보존 후 exit1. 같은 조건을
통과할 때까지 반복하지 않는다. OTHER/extreme/복합고장/48회/M7/M8/Jetson은 이번 범위 밖이다.

## 개발 비교 기록1 (후속 실행 전)

`quadrature-before.txt`: T300Nm/v3m/s/20ms*10에서 기존 electrical616.133107J,
vehicle617.925513J로1.792405J 차이, coherent-work assertion FAIL.
`quadrature-after.txt`: interval motion work 경계로 같은 비교 PASS.
첫9개 계약 중 friction-only의 receivedDC==0 assertion은0.003744J로 FAIL이었다.
이 시험은 초기 bus400V/closed contacts 조건이며 received DC에는 RC/capacitor branch
교환도 포함된다(PowerModel의 branch_j 집계). 기계 회생과 배터리 DC 유입을 같게 놓은
새 시험의 가정이 잘못됐다. 원본은 보존하고, 실제 torque/work0·positive bus load·
독립 combined ledger로 friction-only를 판정하도록 바로잡는다. 기존 시험/assertion은 변경하지 않는다.

## 개발 비교 기록2 — 짧은 regen episode (추가 실행 전)

`dev-nominal/normal-1`은 실제 normal/renewal/native/stop PASS이나 energy 기준 FAIL이다.
음의 실제 torque는2sample/최대−7.505662Nm, 기계 회수0.552436J, received DC0J였다.
valid capability200Nm/charge30000W가 계속 도착해도 episode가 바로0으로 수축했다.
후보 원인은 Host10ms 갱신인데 allocator optional capability 사전 지원 검사는
고정20ms를 쓰고, 한번0으로 수축한 episode는 실제 release 전 회복하지 않는 경로다.
새 bounded regen-admission enum/원래 capability source/input/expiry 전이만 추가하고
같은 nominal1회에서 실제 분기와 metadata를 확인한다. 정상/energy 실패 원본을 보존한다.

## 개발 비교 기록3 — 관측으로 첫 가설 기각

`dev-capability-axis`도 energy FAIL이며 정상/시한/종료는 PASS다. 첫 brake 직후의 실제
regen-admission은Expiring(4)이 아니라Unavailable(1)였다. 유효한 capability의 잔여 지원도
약25ms여서 고정20ms 검사가 최초 원인이라는 가설은 이 run에서 기각한다.20ms 검사는 바꾸지 않는다.
Central/Rear DriveReceiver가 EV dependency budget을 명시하지 않아 기본30ms를 사용함을
확인했다(기존 receiver optional70ms 지원과 EV/allocator dependency70ms 계약은 이미 존재).
원래 wire capability source/input을 bounded event로 추가한 동일 nominal1회와
40ms-old dependency의 실제 AsyncOwner 수신 회귀로 stale/미발행을 구분한다.

## 개발 비교 기록4 — 확인된 receiver 설정 결함 (수정 후 실행 전)

`dev-wire-axis`에서 capability의 실제 wire source는 약4.25ms, dependency는30.38ms
경과한 allocation에서Unavailable(1)이 됐다. 예: allocation610872481715154ns,
wire source610872477463445ns / input610872451331400ns. 원래70ms EV dependency
계약 안이지만30ms receiver current_sample이 optional capability를 지운다.
`capability-before2.txt`는 실제 AsyncCoordinatorPort 경로에서40ms dependency가
소실되는 FAIL을 재현했다. 첫 before는 첫RX100ms로 자체80ms timeout을 먼저 유발한
시험 준비 결함이어서 소실 분기의 근거에서 제외했다(원본 보존).
Central/Rear DriveReceiver에 기존 지원되는70ms dependency만 명시한다.
Torque/wheel/capability source30ms,80ms timeout,원래 output expiry,20ms optional
지원 검사는 그대로다. 새 expiry를 만들지 않으며 늦은 source를 수용하지 않는다.
관련 회귀 후 고정된 최종 Normal5/SDK sanitizer4 시험을 실행한다.
