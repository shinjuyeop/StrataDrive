# Software quality policy

Status: **M1 통신과 M2 Steering/Brake/Drive torque·Battery/BMS/Power·Drive gate·에너지/회로 연결 component에 적용**. Compiler warnings, GoogleTest,
clang-tidy/cppcheck와 ASan/UBSan을 사용했다. 현재 normal·sanitizer 각각 **unit 470개 PASS**다.
Actuator 6개 + EV 6개 DBC/독립 CRC와 C++ payload 36개의 교차 검사가 PASS다.
[Drive 실행 기록](learning/m1_drive_codec.md)과 [BMS 실행 기록](learning/m1_bms_codec.md)에
도구 버전, 검사 범위와 재현 명령을 보존한다. M1 89개와 M2 첫 Steering 2개·Brake 3개·Drive 3개,
총 local vCAN **97개 case**를 검사한다.
Battery/BMS/Power/Drive gate·에너지/회로 단계는 로컬 component 검사이며 CAN wire나 transport 변경은 없다.
97개 vCAN은 앞선 Drive 응답 단계의 증거다. 직전 gate 단계에는 normal·sanitizer 각각 기존 Drive model vCAN 3개를 재검사해 통과했다.

2026-10-13 문서 정리 시 normal·ASan/UBSan build/unit/vCAN과 DBC 검사를 다시 통과했다.
Local observed timeout은 normal 80.019–81.072 ms, sanitizer 80.053–81.065 ms였다.
차량 timing 보장이나 sanitizer의 대표 성능으로 확대하지 않는다. M1 최종 acceptance/학습자
review는 PENDING이었다. 당시 EV C++ 통신과 두 Zone/runtime/차량 TC는 PLANNED / NOT RUN이었다.
문서 52개의 상대 링크/앵커 459개, 요구사항 32개/TC 29개의 정의·추적성,
YAML 3개의 중복 key/책임 배치와 Python syntax를 검사했다. 활성 경로의 낡은 참조를 정리하고
과거 ADR/부분 시험 이력과 목적이 다른 검증 계층은 보존했다.

2026-10-14 [BMS wire 초안](icd/bms_frame_draft.md)의 DBC·6개 goldens/uint64/CRC/canonical
검사를 추가했다. Normal·ASan/UBSan unit 99개, 기존 C++ demo 14개 교차 검증을 통과했다.
48-byte P05 case는 전체 384개 single-bit corruption/잘못된 DataID를 검사한다.
변경 C++ test에 clang-tidy 14 analyzer/bugprone을 적용해 user-source 진단은 없었다.
이 결과는 EV codec/receiver/Drive gate/모델/transport와 전체 TC-EV의 PASS가 아니다.
문서 54개/상대 링크·앵커 478개, 32개 요구와 29개 TC의 추적성, YAML 3개 및
EV rate/age/100 ms monitor budget의 설계 일관성도 검사했다. Python syntax/whitespace 검사를 통과했다.

같은 날 후속 구현에서 BMS value/frame codec·항목별 receiver를 추가했다. Normal·ASan/UBSan
각각 129개 unit이 PASS다. BMS 28개와 기존 Drive/SocketCAN 파일에 추가한 age/adapter case를
포함한다. 전체 12개 DBC/C++ payload 36개를 교차 검증했다.
변경 C++ source/test 10개에 clang-tidy 14의 analyzer/bugprone을 적용해 user-source 진단 없이
통과했다(third-party/header 진단은 제외). Cppcheck 2.7의 warning/performance/portability는
BMS 3개·공통 수신 상태·Drive receiver·SocketCAN adapter·demo의 source 7개에 적용해 통과했다.
EV의 native 48/64-byte 변환과 수동 clock timeout/parent expiry는 Host 단위 범위다.
이 codec 구현 시점에는 EV TX/RX/wall-time budget, Drive의 torque·limits·permission·로컬 HV
통합 gate, BMS/power 모델과 두 Zone/runtime/전체 TC-EV는 NOT RUN이었다.
공통 수신 상태 변경 후 기존 actuator vCAN은 normal·ASan/UBSan 각각 27 case를 재통과했다.
Local timeout은 normal 80.007–81.081 ms, sanitizer 80.029–81.219 ms였다.
이는 기존 6개 actuator frame 회귀이며 새 EV transport의 검증 결과가 아니다.
Fresh `BUILD_TESTING=OFF` build에서 BMS 포함 라이브러리/demo만 생성하고 receiver 예제를 실행했다.
문서 57개/상대 링크·앵커 508개, 요구사항 32개/TC 29개, YAML 3개 및 Python 3개의 syntax와
whitespace도 검사했다. System TC의 Runtime Result는 모두 NOT RUN을 유지한다.

후속 EV SocketCAN 작업은 기존 TX/RX/support/runner를 확장했다. 6종류 각각의 normal/faults/
silent/flood와 partial limits, cached dependency/physical input, 비critical 관측, parent expiry/
identity·explicit INIT/rejoin, 3-process 원천 보존 relay의 **EV 36개**를 추가했다.
Harness는 승인된 parent 목록을 stdin으로 공급하며 CAN에서 context를 자동 생성하지 않는다.
RX는 cycle당 8개 dispatch 후 poll하며 overflow 관측 시 실패한다. Kernel overflow 주입과
application queue/실제 coordinator·DDS는 남아 있다. Normal·ASan/UBSan 각각 전체 63개
(기존 actuator 27 + EV 36)를 검사하고 전체 unit 129개와 DBC 교차 검증도 재통과했다.
Clang-tidy 14 analyzer/bugprone은 변경 TX/RX 2개와 support header에 적용해 user-source
진단 없이 통과했고 cppcheck 2.7 warning/performance/portability도 통과했다.
EV critical timeout은 normal **80.021–81.045 ms**, sanitizer **80.052–81.036 ms**,
관측 envelope timeout은 normal **300.282–300.984 ms**, sanitizer **300.275–301.069 ms**였다.
Forward relay도 따로 80..100 ms budget을 판정했다. Actuator 회귀는 normal
80.008–81.034 ms, sanitizer 80.001–81.050 ms였다. 고정된 local fixture의 관측값이며
Target/차량 timing 보장이나 sanitizer의 대표 성능으로 확대하지 않는다.
실제 BMS limit/power 모델·Drive actuation gate와 두 Zone/차량 TC는 NOT RUN이다.

2026-10-14 [M1 session/queue 마무리](learning/m1_session_queue.md)는 영속 Epoch 발급과
fixed-capacity FIFO/continuity latch를 구현했다. 기존 unit 129 + session/queue 14 = 143개,
기존 vCAN 63 + application/kernel overflow 24 + durable restart 2 = 89개를 검사한다.
Unit의 동시 8개 process 발급·손상/상실/busy/I/O/소진과 12개 receiver 복구를 확인했다.
VCan kernel case는 실제 SO_RXQ_OVFL >0을 요구한다. 이전 Epoch의 counter 200이 새 세션의
P05 state를 오염시키지 않는지 unit/독립 process 양쪽에서 검사했다.
M1 기술 구현·자동 검사는 수용 항목별 기록하고 학습자 review/wire 채택은 PENDING으로 남긴다.
Actual Front session/DDS 및 물리 response/system TC 결과는 후속이다.
Normal·ASan/UBSan 각각 143개 unit/89개 vCAN이 PASS다. App overflow report의 최초 usable
RX 대비 시간은 normal 23.601–25.059 ms, sanitizer 23.698–25.513 ms였다.
Kernel drop report는 normal 48.986–51.073 ms, sanitizer 49.257–50.936 ms였고 12종류 모두
실제 nonzero drop을 기록했다. Report latency는 물리 loss onset latency가 아니다.
Critical timeout은 normal 80.013–81.071 ms, sanitizer 80.002–81.184 ms,
관측 timeout은 normal 300.030–301.045 ms, sanitizer 300.422–300.788 ms였다.
Clang-tidy 14 analyzer/bugprone은 변경 source/test 11개와 receiver/queue/support header에
적용해 user-source 진단 없이 통과했다. Cppcheck 2.7은 production/fixture source 10개에 적용했다.
59개 Markdown의 상대 링크·앵커 528개, 32개 요구/29개 TC, YAML 3개와 Python 3개의
정합성·syntax/whitespace를 검사했다. 실제 차량/Target 성능이나 전체 TC PASS로 확대하지 않는다.

2026-10-14 [M2 첫 Steering 모델](learning/m2_steering_model.md)은 unit 13개를 추가했다.
Normal·ASan/UBSan 각각 전체 156개 unit을 통과했다. 기존 M1 89개 vCAN 회귀를 모두 통과했고,
model-normal/model-loss 2개를 별도로 실행해 각각 통과했다. 첫 model verifier에서 expiry의
reference를 RX time에서 Command source time으로 수정하고 두 model case를 다시 통과했다.
유효 Command → delay/rate/saturation → 독립 Actual RX, source-expiry hold/latch/late command
거부를 확인했다. Actual validity와 FAIL_SAFE를 분리하며 full vehicle TC는 NOT RUN이다.
Clang-tidy의 변경 source/test 5개와 cppcheck production/fixture 4개를 최종 user-source 진단 없이
통과했다. BUILD_TESTING=OFF의 model library/demo build와 결정론적 demo도 통과했다.
61개 Markdown의 상대 링크/앵커, 요구사항 32개/TC 29개와 YAML/Python 정합성을 확인했다.
모델 설정은 SIL fixture이며 Target timing/실차 calibration은 별도다.

2026-10-14 [M2 첫 Brake 압력 모델](learning/m2_brake_model.md)은 unit 16개와 model vCAN 3개를
추가했다. Normal·ASan/UBSan 각각 전체 **172개 unit / 94개 vCAN**을 통과했다.
가압/감압·delay/saturation·valid-zero release, expiry/continuity/deadline의 protective floor ramp,
이미 높은 압력의 retain·late release 거부·clock/restart를 검사한다.
Maximum delay/300개 목표 변경도 fixed history에 유지되는지 unit에서 확인했다.
Generic model loop/runner를 Steering과 공유하고 Actual source/sequence/causal/state/pressure가
독립 RX에 보존되는지 검사했다. Clang-tidy 14 변경 source/test 5개와 cppcheck 2.7 source 4개는
user-source 진단 없이 통과했다. BUILD_TESTING=OFF library/demo build와 brake-model 실행도 통과했다.
63개 Markdown의 상대 링크/앵커, 32개 요구/29개 TC와 YAML/Python 정합성도 확인했다.
Pressure→wheel torque/차량 감속/ABS/회생 배분과 Target scheduling/full TC는 후속이다.

2026-10-14 [ADR-0021](adr/ADR-0021-central-coordination-and-parallel-zones.md)은 Central의 별도
VCU/allocation/session/feedback bridge와 대등한 두 Zone의 문서·profile 배치를 개정했다.
요구 4개를 v0.5로 기록하고 기존 32개 요구/29개 TC의 owner/interface/fault variant를 갱신했다.
Epoch library를 central/session으로 이동해 normal·ASan/UBSan build와 각 172개 unit을 통과했다.
CPP 발급 동작은 이전 source와 동일함을 확인했다. BUILD_TESTING=OFF build와 독립 production
issuer process의 1→2 발급, 64개 Markdown/상대 링크·앵커/추적성/YAML/Python 검사를 통과했다.
앞선 94개 vCAN 결과는 기존 component/wire 부분 증거다. 실제 새 Central–Zone DDS topology와
vehicle/system TC 결과는 NOT RUN이며 M4/M5 이후 검증한다.

2026-10-15 [첫 Drive torque 응답](learning/m2_drive_model.md)은 ECU adapter와 CAN 독립 물리
모델을 별도 모듈로 구현했다. Unit 20개와 signed normal/positive-loss/negative-loss vCAN 3개를 추가해
normal·ASan/UBSan 각각 전체 **192개 unit / 97개 vCAN**을 통과했다.
Normal delay/rate/양·음 saturation/0 command, source-expiry·continuity·deadline의 zero-target ramp,
late frame/clock/restart, 시간 순서·FIFO/uint64 경계를 검사했다. Actual source/sequence/causal/state와
torque, speed/capability unavailable을 독립 RX에서 확인했다.
Local actuator timeout은 normal 80.002–81.032 ms, sanitizer 80.013–81.052 ms였다.
기존 CAN/P05 계약은 유지하며 BMS/permission/local HV gate, capability/energy와 full vehicle TC는 NOT RUN이다.
실행 로그는 각 build의 `drive-model-unit.txt`, `drive-model-vcan-all.txt`,
`socketcan-results/drive-model-*.log`에 보존한다.
Clang-tidy 14 analyzer/bugprone을 변경 source/test 6개와 관련 header에 적용했다.
단위시험 helper의 혼동 가능한 인자를 구조체로 수정했고 최종 test/물리 모델 재검사에서
user-source 진단이 없었다. Cppcheck 2.7은 production/fixture source 5개를 통과했다.
시간 skip에서 pending goal을 취소하도록 보강한 뒤 양 build의 unit 192개와 model vCAN 8개를
다시 통과했다. BUILD_TESTING=OFF library/demo build와 결정론적 `drive-model` 예제도 통과했다.
67개 Markdown/상대 링크·앵커 631개, 요구사항 32개/TC 29개, YAML 3개/Python 3개의
정합성·syntax/whitespace를 검사했다. 기존 100 ms 검출 상한이나 full TC의 NOT RUN 상태는 유지한다.

2026-10-15 [첫 Battery 물리·관측](learning/m2_battery_model.md)은 unit 30개를 추가했다.
Normal·ASan/UBSan 각각 전체 **222개 unit**을 통과했다. 실제 DC/auxiliary power→chemical energy,
zero/unknown·full/empty·실수 회로해/thermal 해석해, 독립 sensor pair·cache source/batch·explicit reset을 검사했다.
100,000개 교대 power interval에서도 0.00018 J balance tolerance를 만족했다.
Battery fault는 미관측 에너지를 추측하지 않고 current 관측을 unavailable로 만든다.
CAN frame/vCAN case는 추가하지 않았고 앞선 Drive의 97개 증거와 full TC NOT RUN을 유지한다.
실행 로그는 각 build의 `battery-model-unit.txt`, `battery-model-demo.txt`에 보존한다.
Clang-tidy 14 analyzer/bugprone은 model/test/demo 3개와 model header에 적용해 최종 user-source
진단 없이 통과했다. Cppcheck 2.7은 production/demo 2개를 통과했다.
Full에서 한 ULP보다 작은 추가 charge도 capacity 위반으로 보고하는 경계를 보강한 뒤
normal·sanitizer unit 222개를 다시 통과했다. BUILD_TESTING=OFF build와 `battery-model` demo도 통과했다.
69개 Markdown/상대 링크·앵커 654개, 요구사항 32개/TC 29개, YAML 3개/Python 3개의
정합성·syntax/whitespace를 검사했다. 기존 차량 수용 조건과 full TC의 NOT RUN 상태는 유지한다.

2026-10-15 [첫 BMS 한계·보호 판단](learning/m2_bms_controller.md)은 unit 33개를 추가했다.
Normal·ASan/UBSan 각각 전체 **255개 unit**과 기존 CLI의 `bms-control`을 통과했다.
Platform-neutral sensor port를 추출하고 ECU와 plant 의존성을 분리했다. 방향별 SOC/온도/전압
derating·10 W floor, cell 극값/pack mean, hard fault 후보의 즉시 inhibit·개별 acquisition dwell,
release hysteresis·명시적 새 app Epoch/INIT·physical model/SOC 유지, sensor unknown/cache/skew/
age/identity/clock/deadline과 기존 P05/receiver의 valid zero/usable-RX를 검사했다.
Demo는 20 ms 수동 시계로 plant→sensor port→controller→codec→receiver를 실행한다.
새 socket transport/vCAN case는 추가하지 않았고 이전 97개 증거 및 full TC NOT RUN은 유지한다.
실행 로그는 각 build의 `bms-control-unit.txt`, `bms-control-demo.txt`에 보존한다.
Clang-tidy 14 analyzer/bugprone은 controller/model/test 2개/demo의 source 5개와 관련 header에
적용해 최종 user-source 진단 없이 통과했다. Cppcheck 2.7 production/demo 3개도 통과했다.
BUILD_TESTING=OFF build/demo와 문서 71개/상대 링크·앵커 676개, 요구사항 32개/TC 29개,
YAML 3개/Python 3개의 정합성·syntax/whitespace를 검사했다.
실차 calibration·hardware protection·Power lifecycle/Drive gate·SOC estimator의 검증 결과가 아니다.

2026-10-15 [첫 Power lifecycle](learning/m2_power_lifecycle.md)은 Power 37개와 BMS local gate 1개를
추가했다. Normal·ASan/UBSan 각각 전체 **293개 unit**과 기존 CLI의 네 `power-model` scenario를 통과했다.
RC 해석해·지연 event 전후 적분·실제 부하/반환 전류, negative/precharge/positive 실제 sequence,
fresh acquisition dwell·BMS source-age/cache/unknown, current wait/open actual/discharge voltage,
LV·weld/stuck/부분 센서·canonical unknown·trusted parent/expiry/identity/deadline/restart를 검사한다.
초기 테스트의 late Enable 수용 기대를 receiver timeout latch의 원래 계약에 맞춰 수정했다.
종료한 physical OFF와 센서 health FAIL_SAFE도 독립적으로 유지한다.
LocalState와 PowerState를 구분하고 request source/causal과 physical batch/dependency를 보존한다.
`power-unit.txt`, `power-demo-normal.txt`, `power-demo-bms-trip.txt`, `power-demo-weld.txt`,
`power-demo-blocked.txt`는 각 build에 보존한다. Demo의 actual current/contactor/RC 응답은
PowerModel에서 오고 SOC/온도/400 V는 명시적 fixture다. Battery SOC 에너지 통합은 미검증이다.
Clang-tidy 14 analyzer/bugprone을 production 3개/test 2개/demo source 6개와 관련 header에 적용해
최종 user-source 진단 없이 통과했다. Cppcheck 2.7 production/demo 4개도 통과했다.
BUILD_TESTING=OFF build/네 demo와 문서 73개/상대 링크·앵커 700개, 요구사항 32개/TC 29개,
YAML 3개/Python 3개의 정합성·syntax/whitespace를 검사했다.
새 wire/transport/vCAN case는 없고 이전 97개 증거 및 full vehicle TC NOT RUN을 유지한다.
실차 calibration/부품 정격/hardware 차단 안전성·Drive 실제 gate·독립 OS task 결과가 아니다.

2026-10-15 [Drive local gate/capability](learning/m2_drive_gate.md)는 gate 37개와 공통 TorqueResponse
추가 4개를 더했다. Normal·ASan/UBSan 각각 전체 **334개 unit PASS**다. 원천 limits의 명시적 relay,
trusted parent/permission·local HV/speed·known zero/unknown·startup 순서·directional power/low-speed
envelope·pending 목표 축소/회복·finite actual residual·loss/clock/deadline/새 Epoch를 검사했다.
구동은 정지 copper loss와 shared fixed reserve를 포함한 power upper estimate, 회생은 반환 power의
보수적 mechanical upper bound를 사용한다. 실제 효율 map/전류 제어/배터리 충전 적분은 시험하지 않았다.
기존 CLI의 `drive-gated` 여섯 scenario를 normal·sanitizer·BUILD_TESTING=OFF build에서 실행했다.
각 build의 `drive-gate-unit.txt`, `drive-gated-*.txt`와 production `drive-gate-build.txt`에 결과를 보존한다.
Clang-tidy 14 analyzer/bugprone은 controller/physics/test 2개/demo source 5개와 관련 header에 적용하고,
최종 변경 controller를 다시 검사했다. Cppcheck 2.7 production/demo 3개도 user-source 진단 없이 통과했다.
Signed zero 정규화의 redundant-assignment 진단은 중복 조건 대입을 없애 해결했다.
문서 75개/상대 링크·앵커 727개, 요구사항 32개/TC 29개와 NOT RUN 추적성, YAML 3개/Python 3개의
정합성·syntax/whitespace도 검사했다.
기존 isolated Drive model vCAN 3개는 normal·sanitizer 각각 재실행해 PASS했다. 처음 host namespace의
`ip link add`는 권한 오류였으나 기존 문서의 `unshare --user --map-root-user --net`로 해결했다.
`drive-gate-vcan-regression.txt`와 각 build의 `socketcan-results`에 결과를 보존한다.
새 EV gate transport case는 없으며 이전 vCAN 97개 전체를 재사용한 새 PASS로 표시하지 않는다.
Actual DC/Battery SOC coupling, 공유 부하/충전 headroom·잔여 회생 budget, 실제 Central/Zone runtime,
차량 motion/마찰 보충·실차 calibration·Target OS timing과 전체 TC-REG/EV/ZON은 미검증이다.

2026-10-15 [첫 Drive/Battery energy 연결](learning/m2_drive_energy.md)은 새 28개 시험으로 normal·ASan/UBSan
각각 전체 **362개 unit PASS**다. 기계적 power→motor conversion/copper/idle→실제 DC→auxiliary·Battery
chemical energy/저항 heat를 구분한다. Analytic 구동/회생·작은 회생의 순방전·standstill, actual delay,
원천 identity/cache/age/skew·missing/역행/gap, full/empty capacity fault·no clipping과 20,000 interval 장부를 검사했다.
초기 시험의 skew 기대는 실제 sequence rollback과 분리하고, BMS input이 매 10 ms 새 값이라는 기대는
원래 20 ms multirate 계약에 맞춰 수정했다. Timestamp를 정규화해 통과시키지 않았다.
Fixture의 gate upper power estimate/공유 reserve·SOC guard band/finite reaction budget을 교차 확인했고,
20→10 ms ZOH refinement와 실제 Battery 관측→BMS→명시적 relay/독립 trusted grant→Drive→P05 receiver loop도 검사했다.
`drive-energy-unit.txt`, `drive-energy-{normal,charge-zero,near-full,auxiliary}.txt`에 결과를 보존한다.
Normal·sanitizer·BUILD_TESTING=OFF에서 네 demo와 SOC 증감·잔여 actual 반환·charge-zero·auxiliary·장부를 확인했다.
Clang-tidy 14 analyzer/bugprone을 model/test/demo source 3개와 관련 header에 적용했다.
Cppcheck 2.7 model/demo 2개도 검사했으며 최종 user-source 진단은 없다.
에너지 모델의 validation loop는 std::find_if로 정리했다. Compiler warnings-as-errors·production build와
문서 77개/상대 링크·앵커 754개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace를 검사했다.
Wire/transport/기존 torque physics 변경이 없어 새 vCAN 실행은 없고 이전 97개 이력·gate 단계의 3개 재검사를 유지한다.
현재 coupling은 이상적 energized HV와 외부 fixed-speed의 component다. Dynamic RC/접점·capacitor/path
에너지·shutdown 부하, vehicle motion·마찰 보충·실차 calibration/정확도·Target timing과 full TC는 미검증이다.

2026-10-16 [RC/접점·Battery energy 연결](learning/m2_ev_power_circuit.md)은 새 29개(circuit 24개·Battery
integrated-flow 5개)를 추가해 normal·ASan/UBSan 각각 전체 **391개 unit PASS**다.
Actual motor DC·Rint/source·main/precharge/bleed·capacitor를 연결하고 구간 current/current-square 적분으로
단일 Battery chemical energy를 갱신했다. RC analytic/event/end-point·50→25 µs refinement,
isolated capacitor regen/discharge·10,000 alternating interval 장부·power/capacity domain과 atomic commit,
identity/source/dependency/cache/unknown·epoch/clock·mean-square heat와 mode 변경 거부를 검사했다.
기존 CLI `ev-power`의 normal/weld/current-unknown/aux-blocked 네 loop를 normal·sanitizer·production에서 실행했다.
PowerStatus·DriveActual/P05 receiver, 실제 READY·구동/회생 SOC 증감·정상 OFF와 고장 blocked·접점·residual·energy를
독립 로그 assertion으로 확인했다. 각 build의 `ev-circuit-unit.txt`, `ev-circuit-{scenario}.txt`에 결과를 보존한다.
기존 Power 4개·Drive energy 4개·Drive gate 6개 demo도 세 build에서 회귀 실행했다.
로그는 `ev-circuit-regression-{family}-{scenario}.txt`이며 production은 BUILD_TESTING=OFF다.
Clang-tidy 14 analyzer/bugprone을 production 4개/test 2개/demo source 7개와 관련 header에 적용하고
변경 뒤 해당 source를 재검사했다. Cppcheck 2.7 production/demo 5개도 최종 user-source 진단 없이 통과했다.
Earliest contact event 선택은 std::accumulate로 정리했고 기존 362개 회귀도 통과했다.
Combined fixture의 opening current 0.5 A·reserve 500 W와 standalone default 5 A·200 W를 구분한다.
OFF 후 auxiliary 소비와 Drive PermissionInhibit latch는 별도다. Thermal은 interval 평균 heat 근사이며
50 µs solver step을 ECU task/RTOS 보장으로 해석하지 않는다.
문서 79개/상대 링크·앵커 781개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace를 검사했다.
새 wire/transport/vCAN case는 없으며 기존 vCAN 97개 이력과 gate 단계의 3개 재검사를 유지한다.
Vehicle motion/마찰 배분·실제 Central/Zone·LV sleep·정밀 부품 calibration·Target timing과 full TC는 미검증이다.

2026-10-16 [M2 수용 검토](m2_acceptance_review.md)는 기존 working tree의 주기·입출력·감시,
fixture parameter, fault/session과 요구사항의 component 증거를 대조했다.
Normal·ASan/UBSan 각각 전체 unit **391개**, model vCAN **8개**(Steering 2/Brake 3/isolated Drive 3)를 재실행해 통과했다.
기존 actuator/Battery/BMS demo 5개와 combined EV scenario 4개도 각 build에서 실행했다.
Combined 종료 phase/fault/접점·current unknown·actual zero·energy 잔차를 독립 assertion으로 확인했다.
각 build의 `m2-review/`에 build/unit/JUnit/inventory·demo·vCAN 로그를 보존하고,
normal build의 `m2-review/evidence.json`에 base commit과 미커밋 runtime source/DBC/profile hash를 기록했다.
Runtime 코드·시험 모듈·의존성은 추가하지 않았다. 기존 vCAN all 97개 이력은 유지하며 이번 재실행 범위는 8개다.
문서 80개/상대 링크·앵커 817개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace를 검사했다.
수용 검토에서 Steering jam/tracking·Brake stuck/slow-response detector를 **M2 미완료 OPEN-M2-01/02**로 기록했다.
Tick gap guard는 멈춘 task의 독립 검출이 아니며 scheduler/watchdog·trace·deadline 측정은 M3에 남긴다.
M2는 IN PROGRESS, M1 wire/학습자 설명·직접 재현은 PENDING, system Result는 NOT RUN을 유지한다.

2026-10-16 [Steering response monitor](learning/m2_steering_fault_monitor.md)는 물리 9개·monitor 21개·기존 adapter 9개,
새 39개를 더해 normal·ASan/UBSan 각각 전체 **430개 unit PASS**다.
물리 delay/rate/jam과 angle acquisition을 별도 모듈로 분리하고 local monitor가 issued bounded target 이력과
독립 sensor만으로 정상 rate band·residual/dwell을 검사하도록 했다. 기존 Steering 13개도 회귀 통과했다.
양방향 stall, 정상 rate band 양끝·지연/방향 전환/포화, transient pending 해제, fresh-source confirmation,
unknown/cache/identity/clock·bounded history, valid Actual과 sensor fallback 금지·새 epoch를 시험했다.
기존 CLI `steering-model`의 normal/jam/slow/sensor-hold/sensor-invalid/transient 6개와
Brake/isolated Drive/combined EV normal 회귀 3개를 normal·sanitizer·production에서 실행했다.
로그 assertion으로 jam 130→190 ms, slow 140→200 ms의 pending→검출, sensor unavailable와 transient 회복을 확인했다.
Production BUILD_TESTING=OFF build도 통과했다. 각 build의 `steering-monitor-build.txt`, `steering-monitor-<scenario>.txt`,
`steering-monitor-regression-*.txt`에 결과를 보존하며 unit 로그는 normal/sanitizer의 `steering-monitor-unit.txt`다.
기존 model vCAN 8개도 normal·sanitizer에서 각각 재실행해 통과했고 로그는 `steering-monitor-vcan.txt`다.
Jam을 넣은 새 SocketCAN case는 없으며 기존 all 97개 이력과 이번 8개 회귀를 구분한다.
Clang-tidy 14 analyzer/bugprone을 production 3개·test 3개·demo 1개와 관련 header에 적용하고,
cppcheck 2.7 production/demo 4개도 user-source 진단 없이 통과했다.
문서 82개/상대 링크·앵커 846개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace도 검사했다.
Threshold/rate/dwell은 fixture이며 기계 jam의 고유 원인 진단, 실차 조향 안전성이나 100 ms tracking 검출 보장이 아니다.
M2 OPEN-M2-01의 component 증거를 추가했고 Brake OPEN-M2-02·학습자 수용, M3 task/watchdog/trace는 남긴다.

2026-10-16 [Brake pressure response monitor](learning/m2_brake_fault_monitor.md)는 plant 10개·monitor 16개·기존 adapter 14개,
새 40개를 더해 normal·ASan/UBSan 각각 전체 **470개 unit PASS**다. 기존 Brake adapter 16개도 유지했다.
독립 pressure sensor/물리 응답 경계와 별도 rise/fall 정상 band·residual/source-time dwell을 구현했다.
가압/감압 stuck·slow, 정상 rate 양끝·지연/포화/방향 전환, transient pending 해제, unknown/cache·identity/time,
bounded history, 새 epoch·persistent stuck과 plausible sensor freeze를 시험했다.
보호 floor 요청 뒤에도 물리 stuck을 적용하고 요청/fresh 관측/실제 제동 성공을 구분한다.
관측 gap은 fault를 latch하지만 개별 유효한 새 압력은 FAIL_SAFE 상태와 함께 보고할 수 있다.

기존 CLI `brake-model`의 normal/stuck-rise/slow-rise/stuck-release/slow-release/sensor-hold/sensor-invalid/transient 8개와
Steering normal/jam·isolated Drive·combined EV normal 회귀 4개를 normal·sanitizer·production에서 실행했다.
별도 로그 assertion으로 rise stuck 120→180 ms, slow rise 130→190 ms, release stuck/slow 370→430 ms의 pending→검출,
보호 중 stuck 잔존·floor unknown·transient 해제를 확인했다. Production BUILD_TESTING=OFF build도 통과했다.
각 build의 `brake-monitor-build.txt`, `brake-monitor-<scenario>.txt`, `brake-monitor-regression-*.txt`에 보존하며,
normal/sanitizer의 `brake-monitor-unit.txt`, `brake-monitor-unit.xml`에 전체 unit 결과를 둔다.
기존 model vCAN 8개도 normal·sanitizer에서 각각 재실행했고 `brake-monitor-vcan.txt`와 `socketcan-results`에 결과를 둔다.
이는 새 pressure fault network case가 아닌 기존 정상/통신 상실 회귀다. All 97개는 앞선 전체 실행 이력이다.
Clang-tidy 14 analyzer/bugprone은 production 3개·test 3개·demo 1개, cppcheck 2.7은 production/demo 4개에 적용했다.
문서·추적성/YAML·Python/whitespace 검사와 실행 source/DBC/profile SHA-256은
`build/m1-angle/brake-monitor-doc-check.txt`, `brake-monitor-evidence.json`에 보존한다.
M2 OPEN-M2-01/02의 component 구현 공백은 해소했고 직접 재현·학습자 수용은 PENDING이다.
실차 calibration/고유 기계 원인 진단·vehicle stop·독립 task/watchdog는 검증한 결과가 아니다.
32개 요구/29개 system TC 전체 Result는 NOT RUN이며 M3 task/trace·측정 설계가 다음 구현이다.

2026-10-16 예제 구조 정리에서 단일 `actuator_demo` 실행 파일을 유지하고 명령 분기/도움말과
`tools/demo/`의 Steering·Brake·Drive·EV 구현을 분리했다. Normal·ASan/UBSan·BUILD_TESTING=OFF build에서
각각 **90개 CLI 입력의 stdout/stderr/exit code가 이전 binary와 동일**했다. Clang-tidy analyzer/bugprone을
변경된 source 5개에 적용해 통과했다. 기존 runtime library/시험 case는 이 단계에서 변경하지 않았다.
비교 binary·명령 목록/스크립트·build/static 로그는 `build/m1-angle/structure-review/`와 각 build의
`structure-demo-build.txt`에 둔다. 문서 링크/추적성/YAML/Python/whitespace 검사도 통과했다.

| 영역 | 향후 정책 | 적용 시점 / 증거 |
| --- | --- | --- |
| Compiler | 직접 관리하는 GCC/Clang target에 `-Wall -Wextra -Werror` 적용 | 첫 C++ target부터 적용; 검토된 최소 범위의 예외는 문서화하고 third-party에 global flag 적용 지양 |
| Static analysis | clang-tidy와 cppcheck | 처음 적용할 코드와 함께 규칙을 검토하고 도구 버전 고정 |
| Dynamic analysis | ASan과 UBSan | Host의 계측된 test job에서 사용; Target 지원은 별도 검증 |
| Unit tests | C++는 GoogleTest, Python은 pytest | 구현과 함께 동작/계약 시험 작성 |
| System tests | Integration Test, SIL Regression, Fault Regression, Performance Regression | Milestone별로 추적 가능한 case와 검토된 threshold 사용 |
| CI | 초기에 필요하면 configure/문서 검사만 수행 | M0에는 CI workflow 없음; 실제로 수행하지 않은 차량 시험을 PASS로 표시하거나 의존성이 많은 골격을 만들지 않음 |

Sanitizer를 사용한 timing은 대표 성능 증거로 볼 수 없다. 결과에는 build type,
compiler/option, 활성화된 계측을 기록한다. Real-time priority, affinity, kernel 선택,
최적화에는 변경 전후 증거가 필요하며 효과를 미리 보장하지 않는다.
Linux 측정만으로 hard real-time 인증을 주장하지 않는다.

코드를 수용하기 전에 학습자가 변경을 설명하고 diff를 검토하며 관련 검사를 직접
실행한다. Edge/fault 동작도 확인하고 결과를 요구사항에 연결한다. 미실행 test를
PASS로 표시하지 않는다. 의존성을 추가하기 전에 버전과 license를 검토하며,
M0에서는 대형 의존성을 설치하지 않는다.

Toolchain/compiler/CI/test 버전은 TBD-11(M1), board 지원/측정 환경은 TBD-09(M5/M12)로
관리한다. Owner와 rationale은 [TBD register](roadmap.md#open-m0-decisions)를 따른다.

## 코드·예제·시험 배치

- 재사용 기능은 `interfaces/`와 해당 runtime component에 둔다.
- 학습/확인 예제는 영역별 실행 프로그램으로 묶는다. 세 actuator와 EV/BMS는
  `tools/actuator_demo.cpp` 하나에 기존 아홉 명령 + BMS 세 명령 + Linux Epoch 명령을 제공한다.
  기존 기능의 작은 변경마다 별도 demo를 추가하지 않는다.
- 단위 시험 파일은 모듈별로 유지한다. 기존 모듈의 조건/경계/fault 추가는 같은 파일의 case로 추가하고,
  새로운 독립 모듈이 생기면 시험 파일을 만든다.
- 통합 시험의 participant/helper/runner는 같은 영역 아래 모은다.
  세 actuator SocketCAN은 `tests/integration/can/`이며 새 fault는 기존 runner의 case로 확장한다.
- DBC 검사와 환경 확인은 `tools/`에 둔다. 목적과 확인 범위가 완전히 겹치는 임시 코드만 정리한다.
  표현/수용/transport의 서로 다른 검증 계층은 유지한다.

CMake의 `BUILD_TESTING=OFF`는 단위 시험과 통합 시험용 TX/RX build를 제외한다.
Fresh build에서 라이브러리와 `actuator_demo`만 생성되는 것을 확인했다.
기존 예제 4개의 정상/거부 출력 17개를 통합 프로그램과 비교했고 명령 오류 7개/도움말도 확인했다.
단위 시험 파일은 이 정리로 추가하거나 합치지 않았다.
정리 후 normal/ASan·UBSan 각각 unit 48개와 vCAN 8개 case를 통과했고,
통합 demo/TX/RX source 3개의 static analysis와 DBC 교차 검증도 통과했다.
수신 로그의 cycle flush와 실패 trace 보존을 보완한 범위는 [실행 기록](learning/m1_steering_socketcan.md#예제시험-정리와-재검증)에 남겼다.

## Design and evidence review

[개발·학습 계획](engineering_plan.md)의 표준 참고 활동에도 기존 review와 변경 관리를
적용한다. Automotive SPICE의 추적성과 일관성 관점을 참고하며 평가 등급을 주장하지 않는다.
안전 분석의 가정·Goal 후보와 기존 requirement의 검토 연결은
[concept study](safety/concept_study.md)에 남긴다. 분석 초안을 승인된 safety concept이나
기존 requirement의 도출 근거로 소급해서 표시하지 않는다.

AUTOSAR pilot은 입력 ARXML/설정, schema/release, generator/compiler 버전, 실행 명령과
결과를 기록한다. 직접 작성한 코드와 생성·third-party 코드를 구분하고 재생성 가능성을
검토한다. 도구 채택 전에 license와 지원 환경을 확인한다. 정적 분석이나 단위 시험의
성공만으로 AUTOSAR 적합성, ISO 26262 준수, 실차 안전성 검증을 선언하지 않는다.

분석 또는 실험에서 baseline 변경이 필요하면 이유, 영향 requirement/ICD/profile/test,
재검증 범위를 기록한다. ASIL, FTTI, safe state와 같은 미결정 값을 임의로 확정하지 않는다.
학습자의 review와 자동 문서 검사는 별도 기록이며 한쪽 결과가 다른 쪽을 대신하지 않는다.
