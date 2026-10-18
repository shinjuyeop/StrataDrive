# Software quality policy

Status: **M1 통신·M2 모델·M3 Host 다중 주기/task·CAN 감시·CPU 부하/배치에 적용**. Compiler warnings, GoogleTest,
clang-tidy/cppcheck와 ASan/UBSan을 사용했다. 현재 normal·sanitizer 각각 **C++ unit 521개 PASS**, Python 리포터 **21개 PASS**다.
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

2026-10-16 후속 [ECU/SIL 실행 경계](learning/m2_execution_boundaries.md) 정리에서 네 actuator/Drive core의
physical response 소유/호출을 제거했다. Core `prepare/complete`와 typed actuation/sensor port,
`simulation/`의 명시적 SIL runner로 분리했다. Model injection/truth는 simulation에만 남긴다.
신뢰된 app/model epoch·enable boundary는 ActuatorSession으로 묶고 wire에서 자동 학습하지 않는다.

새 **21개** = core-only 경계 18개 + 기존 actuator 파일의 독립 물리 진행 3개다.
Normal·ASan/UBSan 각각 전체 **491개 unit PASS**, production BUILD_TESTING=OFF build를 통과했다.
Core 경계 executable의 compile include/link 목록에 simulation 경로·plant library가 없음을 확인했다.
ECU 미호출 중 외부 물리 진행·복귀 시 무소급 보호, sensor unknown/identity/source·Actual fallback 금지,
job phase/clock·중복 완료와 gated Drive의 실제 torque port를 확인했다.
Drive torque의 유효 scalar는 같은 job end의 새 acquisition만 보고하며 cached/delayed는 unavailable,
missing/잘못된 identity·time·range/30 ms 초과 age는 TorqueFeedbackUnavailable로 latch한다.
Steering/Brake의 지연된 새 acquisition은 원래 source time을 보존한다.

Normal·sanitizer·production 각각 **90개 CLI 입력**의 stdout/stderr/exit code를 구조 변경 전 binary와 비교해 일치했다.
기존 model vCAN **8개**(Steering 2/Brake 3/isolated Drive 3)도 normal·sanitizer에서 각각 회귀 검사했다.
이는 새 port fault의 network case나 독립 task 정지 감시 시험이 아니다. 기존 all 97개 이력을 유지한다.
Clang-tidy 14 analyzer/bugprone은 변경 C++ source 20개, cppcheck 2.7은 production/demo 13개에 적용했다.
Normal 상세 로그·CLI 비교 목록/스크립트·core-only compile/link는 `build/m1-angle/structure-review/`에 둔다.
최종 build/unit/XML은 normal·sanitizer의 `structure-final-*`, production의 `structure-final-build.txt`,
vCAN은 각 build의 `structure-final-vcan.txt`와 `socketcan-results`에 둔다.
실행 source/DBC/profile·문서 SHA-256과 로그 목록은 `build/m1-angle/structure-review/evidence.json`에 묶는다.
문서 링크/앵커·32개 요구/29개 TC NOT RUN·YAML/Python/whitespace도 검사했다.
M1/M2 학습자 수용은 PENDING이다. 실행 경계를 분리했으며 실제 thread/task/watchdog·RT 계측은 M3에 남는다.

같은 날 후속 문서 대조에서 M2 학습 흐름·수용 검토 표를 현재 ECU phase/SIL API에 맞추고,
Classic ADR의 과거 대응표와 M1 수동 검사 명령을 당시 이력으로 구분했다.
현재 demo 파일 배치·검사 진입점과 Brake 보호 요청/물리 응답의 책임도 정리했다.
문서 87개/상대 링크·앵커 953개, 요구 32개/TC 29개 NOT RUN, YAML 3개/Python 3개와 whitespace 검사는 PASS다.
이 후속은 문서만 변경했으며 C++ 시험을 다시 실행한 기록은 아니다.

2026-10-16 [M3 첫 Steering 주기 실행](learning/m3_steering_timing.md)은 absolute schedule·독립 completion monitor와
SPSC latest snapshot을 구현하고 ECU/monitor/plant owner를 분리했다. 새 unit **14개**를 더해
normal·ASan/UBSan 각각 전체 **505개 PASS**, Python 통계/분모·unavailable 시각 검사 **5개 PASS**다.
Normal/최소 계측/15 ms busy overrun/120 ms stall을 normal·sanitizer에서 각각 3회(**12 runs씩**),
BUILD_TESTING=OFF build에서 1회(**4 runs**) 실행했다. 모든 run의 예정 job은 120개이고 warm-up 제외는 0이다.
이번 최종 계측 실행은 세 build를 순서대로 수행했다. Host의 다른 부하·DVFS·cooling은 통제하지 않았다.

Normal은 모두 120개 완료/miss 0이었다. Overrun은 실행 119개·skip 1개·miss 2개,
stall은 실행 109개·skip 11개·miss 12개였으며 누락 job을 분모에서 빼지 않았다.
Normal build의 첫 검출은 deadline 뒤 **1.073–1.242 ms**, 독립 Hold 적용은 검출 뒤 **1.999–2.006 ms**였다.
둘 모두 ECU의 injected sleep/busy work 종료 전이었다. Late injected feedback은 발행하지 않았고
새 sensor acquisition·Command/Actual causal identity와 output issued/applied time을 확인했다.
복귀 뒤 timely FAIL_SAFE 진단 발행은 유지했다. Sensor-gap latch의 unavailable은 측정으로 집계하지 않으며
진단 생성 시각과 유효 각도의 acquisition source를 구분하는 회귀 검사를 더했다.
이 값은 default SCHED_OTHER의 local 관측이며 100 ms CAN loss·차량 반응/Target 보장으로 확대하지 않는다.

Normal/full의 360개 job elapsed는 Mean **0.015845 ms**, P95 **0.015552 ms**, P99 **0.067195 ms**, Max **0.072855 ms**였다.
Minimal 계측과의 평균 차이는 **+0.000231 ms**였다. 별도 실행의 scheduler/cache 잡음도 포함하므로
이 차이를 계측 비용의 상한으로 보거나 deadline에서 빼지 않는다. ECU phase와 외부 physics 비용은 별도 지표다.
Sanitizer 수치는 기능/메모리 검사이며 대표 성능 증거로 사용하지 않는다.

변경 C++ source/test 4개에 clang-tidy 14 analyzer/bugprone, production/demo 3개에 cppcheck 2.7을 적용했다.
최종 trace field 변경 뒤 해당 runtime source를 다시 검사했다. User-source 진단 없이 통과했으며 기존 header/NOLINT filter는 유지했다.
TSan은 PIE/non-PIE 두 시작 시도 모두 Host의 `unexpected memory mapping`으로 실행되지 않았다. Race 검사는 NOT RUN이다.
세 slot의 동시 payload 무결성 stress test와 ASan/UBSan 결과를 TSan PASS로 대신하지 않는다.

각 build의 `m3-result/`에 CSV/run 환경·설정·source/profile/binary hash·summary/artifact manifest를 보존한다.
Normal·sanitizer의 `m3-final-unit.txt/xml`, Python `m3-final-python.txt`, 각 build의 `m3-result.txt`와
`m3-final-*` build/static 로그, normal의 `m3-static-clang.txt`·`m3-final-clang.txt`·`m3-final-cppcheck.txt`에 적용 범위를 남긴다.
최종 소스·문서·로그 연결은 `build/m1-angle/m3-evidence.json`에 묶는다. 이번에 CAN wire/receiver/DBC는 변경하지 않았고
vCAN 재실행은 하지 않았다. 기존 M2 model 8개·전체 97개는 앞선 실행 이력이다.
이 첫 실행 시점 다른 ECU/통신 감시는 후속이었으며 아래 확장에서 검사했다. M3는 IN PROGRESS이고 32개 요구/29개 전체 system TC는 NOT RUN이다.

2026-10-16 후속 [M3 다중 주기·실제 CAN 감시](learning/m3_multirate_runtime.md)는 Brake/Drive/Power 10 ms·BMS 20 ms와
SocketCAN RX 2 ms를 별도 thread로 실행했다. 유효 RX monitor 7개·trusted issuer history 4개 unit을 추가해
normal·ASan/UBSan 각각 전체 **516개 PASS**, 리포터의 원천 참조/80..100 ms 경계·clock 검사 3개를 더해 Python **8개 PASS**다.
BUILD_TESTING=OFF build도 통과했다. 기존 Core·wire/receiver·DBC 계약은 변경하지 않았다.

정상/full·정상/minimal, Brake/Drive/BMS/Power/RX 각각의 120 ms stall과 지속 CRC 손상의 8조건을 실행했다.
최종 소스에서 normal·sanitizer 각각 2회(**16 runs씩**), production 1회(**8 runs**)로 총 **40 runs PASS**다.
공통 Linux helper 추출과 snapshot/보호 flag 취득→clock read 순서 수정 뒤 기존 Steering 4조건도
normal·sanitizer 각각 1회(**8 runs 합계**) 회귀했다. 빌드/정적 분석을 끝낸 뒤 계측을 세 build에서 순서대로 실행했으며
warm-up 제외는 0이다. Host 다른 부하·DVFS/cooling은 통제하지 않았다.

Normal의 task miss/skip은 모두 0이었다. 아래는 normal build의 full 계측 2회 job elapsed(ms)이며,
ECU prepare/complete 또는 tick 비용과 외부 물리 계산은 별도 trace 지표다. 서로 다른 주기의 sample을 합치지 않는다.

| Task | Samples | Mean | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| Brake | 480 | 0.029995 | 0.091016 | 0.096215 | 0.101209 |
| Drive | 480 | 0.071357 | 0.184090 | 0.198146 | 0.201208 |
| BMS | 240 | 0.010297 | 0.023323 | 0.025128 | 0.038002 |
| Power | 480 | 0.061046 | 0.100879 | 0.108182 | 0.114536 |
| RX | 2400 | 0.053212 | 0.148148 | 0.154004 | 0.171159 |

Full/minimal 평균 차이는 task에 따라 음수도 나왔다. 별도 실행의 scheduling/cache 잡음을 포함하므로 계측 비용의 상한으로
해석하거나 deadline에서 빼지 않는다. 자세한 역할별 비교는 `summary.json`의 `trace_overhead_comparison.by_task`에 둔다.
Sanitizer 수치는 기능/메모리 검증에만 사용한다.

Normal build의 stall에서 Brake/Drive/Power는 각각 miss 12·skip 11, BMS miss 6·skip 5, RX miss 60·skip 59였다.
누락 job을 분모에 남겼고 다른 task는 miss 0이었다. 최초 검출은 해당 deadline 뒤 **1.055–1.294 ms**,
독립 보호 적용은 검출 뒤 **1.820–2.022 ms**였으며 모두 stalled job 복귀 전이었다.
초기 개발 검사에서 보호가 검출보다 수백 ns 먼저 적용된 것으로 찍힌 run은 FAIL로 보존했다.
새 snapshot/flag를 취득한 뒤 적용 clock을 읽도록 수정해 소급 적용을 막았으며 최종 suite는 그 순서를 검사한다.

마지막 valid application RX→loss 검출은 normal **80.002–81.996 ms**, sanitizer **80.005–82.019 ms**,
production **80.010–81.993 ms**였다. CRC 손상 packet이 계속 들어와도 valid age는 갱신하지 않았다.
유한 torque 잔여 응답·Brake increase-only floor와 Power 정지 중 접점 유지/복귀 후 measured-current 종료를 검사했다.
정상 precharge/READY·BMS fresh release dwell→gated Drive와 실제 SOC 감소/회로 energy 잔차도 확인했다.
이는 5개 입력 stream의 local Host/vCAN 증거이며 실제 CAN arbitration·Zone/Central·Target/차량 안전 정지 증거가 아니다.
비동기 Drive torque는 원천 acquisition을 보존해 현 wire에서 unavailable이다. 실제 torque는 physical trace에 있고
Actual CAN TX→독립 feedback RX는 sampling/timestamp 계약 검토 뒤 별도로 검사해야 한다.

Clang-tidy 14 analyzer/bugprone은 변경 runtime·demo·test C++ 5개, cppcheck 2.7은 production/demo 3개에 적용해 통과했다.
기존 user-source/header/NOLINT filter 범위를 유지했다. TSan은 앞서 기록한 Host 시작 오류 때문에 여전히 **NOT RUN**이다.
각 build의 `m3-multi-recorded/`에 최종 40 runs의 CSV·run/environment·source/profile/binary hash·summary/artifact manifest를 보존한다.
보고서 환경 설명의 모델/deadline을 family별로 수정해 재기록했으며 앞선 `m3-multi-final/` 40 runs도 보존한다.
Steering 회귀는 normal·sanitizer의 `m3-steering-recorded/`, unit은 `m3-multi-unit.txt/xml`, Python은 normal의
`m3-multi-python.txt`, build는 각 build의 `m3-multi-final-build.txt`에 기록했다.
정적 분석은 normal의 `m3-multi-final-clang.txt`·`m3-multi-cppcheck.txt`, 최종 증거 연결은
`build/m1-angle/m3-multirate-evidence.json`이다. 이전 실패/검토 로그는 별도 directory에 유지한다.
Markdown 91개·상대 링크/앵커 1015개, 요구 32개/TC 29개, YAML 3개·Python 5개 syntax/정합성을 검사했다.
기존 M1/M2 97개 vCAN은 이 40 runs와 별도 이력이다.
이 단계에서 후속이던 고정 부하·CPU 배치 비교는 아래에 기록한다. Owner별 우선순위·Drive 관측 계약·M3 수용과 Target/E2E는 후속이다.
전체 32개 요구/29개 system TC는 NOT RUN이며 M1/M2 학습자 수용 기록은 PENDING이다.

2026-10-16 [고정 부하·CPU 배치 비교](learning/m3_cpu_placement.md)는 기존 timing runner와 runtime의 owner별 affinity 기록을 확장했다.
CPU 선택/조건 순서·all-owner mask·busy CPU 경계·run 사이 interval·실패 통계 보존의 Python 8개를 추가해 **16개 PASS**다.
Normal·ASan/UBSan 각각 기존 C++ **516개 PASS**, production BUILD_TESTING=OFF build도 PASS다.
Clang-tidy 14 analyzer/bugprone은 runtime C++ 2개와 `simulation/runtime` header filter에 적용했고,
cppcheck 2.7 warning/performance/portability는 기존 production/demo 3개 compile entry에 적용해 user-source 진단 없이 통과했다.
TSan은 앞선 Host 시작 오류 때문에 여전히 NOT RUN이다.

모든 runtime owner를 CPU 0에 고정하고 부하 없음/busy worker CPU 0/busy worker CPU 1을 비교했다.
현재 allowed 0–15와 topology(package 0/core 0 및 1, sibling 0·8 및 1·9)를 기록했다. 별도 physical core가 보이지만 resource reservation은 아니다.
부하는 10 ms마다 7 ms wall busy window를 요청하고 실제 busy thread CPU와 worker loop process CPU를 별도 측정한다.
SCHED_OTHER·상속 nice를 유지했다. Layout 순서를 회전하고 full/minimal 순서도 바꿔 normal·production 각각 3회(**18 runs씩**),
sanitizer 1회(**6 runs**)로 최종 **42 runs**를 순서대로 실행했다. Warm-up 제외는 0이며 빌드/정적 분석은 계측 전에 끝냈다.

배치·부하 수명/CPU 측정은 **42/42 PASS**였고 worker 강제 종료·누락 cycle은 없었다.
기존 ECU normal 계약은 **28 PASS / 14 FAIL**이다. Baseline·separate는 모두 통과했고 shared는 모두 실패했다.
Normal·production shared RX는 각각 **48개 miss/skip**, sanitizer는 **18개 miss/skip**이었다. 다른 runnable의 miss는 0이었다.
독립 monitor가 RX miss를 latch해 Drive가 처음 활성화되기 전에 zero 보호로 들어갔다.
따라서 이 shared 배치의 정상 구동·timing 계약은 충족하지 못했다. 실행 성공/데이터 수집을 ECU 계약 PASS로 대신하지 않았다.

아래는 normal build의 layout/trace별 RX individual sample 통계다. 각 조건의 예정 job은 3600개이며 miss는 모두 skip이었다.
Response time은 실제 실행한 job의 release→end이며 skipped job에 가짜 duration을 부여하지 않는다.

| Layout / trace | Executed / eligible | Miss / skip | Response P99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- |
| baseline / full | 3600 / 3600 | 0 / 0 | 0.337464 | 0.404273 |
| baseline / minimal | 3600 / 3600 | 0 / 0 | 0.319541 | 0.373310 |
| shared / full | 3577 / 3600 | 23 / 23 | 0.760680 | 1.535098 |
| shared / minimal | 3575 / 3600 | 25 / 25 | 0.881875 | 1.889200 |
| separate / full | 3600 / 3600 | 0 / 0 | 0.339223 | 0.372659 |
| separate / minimal | 3600 / 3600 | 0 / 0 | 0.189907 | 0.521037 |

P99/Max가 deadline 3 ms보다 작아도 skip이 있는 조건은 실패다. 이 표의 Max는 WCET bound가 아니다.
Normal build의 measurement busy CPU 하한/상한 관측 범위는 **66.51–69.46%**, bookkeeping을 포함한 worker loop CPU 비율은
**67.47–69.40%**였다. 요청 70%를 실측 CPU 사용률로 대체하지 않는다. Runtime window 경계의 partial cycle CPU는 비례 추정하지 않았다.
실패 run도 schedule/interval이 유효해 모든 job을 통계에 남겼고 통계에서 제외한 run은 0이었다.
Full/minimal 차이는 layout별로만 비교하며 fault 뒤 코드 경로·scheduler/cache 잡음도 포함해 계측 비용 상한으로 쓰지 않는다.
Sanitizer 수치는 기능/수명 검증이며 대표 성능 비교에 쓰지 않는다. Host 다른 process·interrupt·DVFS/cooling은 통제하지 않았다.

기존 fault matrix 회귀는 normal·sanitizer 각각 multirate 8 + Steering 4 = **12 runs씩 PASS**다.
최종 CPU campaign은 각 build의 `m3-placement-result/`에 CSV·run/environment·worker cycle·summary/artifact SHA를 남긴다.
예비 `build/m1-angle/m3-placement-probe/`는 6 runs 중 shared/minimal 1건 FAIL을 포함해 별도로 보존한다.
회귀는 normal·sanitizer의 `m3-placement-multi-regression/`·`m3-placement-steering-regression/`이다.
Unit은 `m3-placement-unit.txt/xml`, build는 `m3-placement-build.txt`, Python은 normal의 `m3-placement-python.txt`,
정적 분석은 normal의 `m3-placement-clang.txt`·`m3-placement-cppcheck.txt`에 기록한다.
Source/profile/binary/artifact와 최종 문서·검사 로그 연결은 `build/m1-angle/m3-placement-evidence.json`에 둔다.
Drive 비동기 torque CAN 보고 계약과 RX/monitor/plant budget·owner별 배치/우선순위를 검토해야 한다.
기존 deadline을 완화하지 않았으며 M3는 IN PROGRESS다. 전체 32개 요구/29개 system TC는 NOT RUN이다.

2026-10-18 [비동기 Drive Actual CAN 연결](learning/m3_drive_feedback.md)은 기존 header SourceTimeNs의 torque 취득 의미를 사용했다.
Sender는 새 유효 sample의 원래 취득 시각을 보존하고 cached torque는 unavailable 진단으로 보고한다.
Receiver의 보조 source를 torque 시각과 묶던 조건을 session/now·각 age/cursor로 개정했다.
CAN schema 2/ID·length/P05 DataID·CRC coverage와 golden payload는 유지하고 DBC 설명/ICD·ADR을 함께 갱신했다.
기존 receiver는 더 늦은 보조 시각을 Invalid로 제거할 수 있으므로 양쪽 정책 검토가 필요하다.

Core/receiver의 지연된 새 torque·cache 미갱신·독립 보조/torque age·같은 sample 재발행/future/regression 5개를 더해
normal·ASan/UBSan 각각 C++ **521개 PASS**다. Trace의 원래 bytes/source·generation·uint64 parse·replay count 검사 5개를 더해
Python **21개 PASS**다. 새 valid TorqueMeasurement를 값/시각과 함께 반환하며 초기화는 기존 typed ActuatorSession을 사용한다.
BUILD_TESTING=OFF build도 통과했다. Clang-tidy 14 analyzer/bugprone은 변경 C++ 7개와 runtime/Drive header filter에,
cppcheck 2.7 warning/performance/portability는 production/demo 5개 compile entry에 적용해 통과했다.
확대한 header filter에서 초기화 인자 순서 진단을 확인해 typed Session으로 정리했다. 최초 진단 로그도 보존한다.
TSan은 앞서 기록한 Host 시작 오류 때문에 여전히 NOT RUN이다.

Actual을 실제 socket으로 송신하고 기존 RX worker의 0x282 socket/별도 DriveReceiver로 검증했다.
독립 monitor에 여섯 번째 valid RX를 추가했으며 Actual replay에서도 다른 5개 입력은 계속 정상 수용된다.
RX budget 8·ECU period/deadline은 유지하고 마지막 response를 수신하는 20 ms drain tail(1210 RX jobs)을 명시했다.
Trace schema 3과 CAN schema 2는 별개다. Minimal trace도 동일 송수신·receiver 경로와 count를 실행한다.

최종 9조건(normal full/minimal·worker stall 5·CRC 손상·Actual replay)을 normal·sanitizer 각각 2회(**18 runs씩**),
production 1회(**9 runs**)로 실행해 **45 runs PASS**다. 기존 Steering 4조건도 normal·sanitizer 각각 1회(**8 runs 합계**) 회귀했다.
빌드/정적 분석 뒤 세 build의 계측을 순서대로 실행했으며 warm-up 제외는 0이다. Host 다른 부하·DVFS/cooling은 통제하지 않았다.
정상 run마다 **240 TX = 240 RX = 240 Accepted**, expired Actual 0이었다. Full trace는 모든 Accepted의 64-byte payload·torque/source를
원래 TX와 producing job의 sensor에 연결한다. Torque 양자화 차이 <=0.05 N·m와 원래 정수 ns를 검사한다.

아래는 각 build의 normal/full individual sample을 합친 **토크 source→소프트웨어 RX(ms)**다.
ECU job 비용·논리 job/report 시각→TX·socket TX→RX와 물리 settling time은 서로 구분한다.
Trace generation_ns는 phase_ns이며 실제 직렬화 완료 시각을 뜻하지 않는다.

| Build | Samples | Mean | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| normal | 480 | 4.484734 | 6.045365 | 6.052930 | 6.060372 |
| ASan/UBSan | 480 | 5.914341 | 6.046427 | 6.057854 | 6.075002 |
| production BUILD_TESTING=OFF | 240 | 2.197888 | 4.019047 | 4.042298 | 6.006025 |

Sanitizer는 기능/메모리 검사이고 위 차이를 대표 성능 개선/악화로 해석하지 않는다. Local single-clock·vCAN 경계이며 Target/차량 E2E가 아니다.
Replay run의 raw TX/RX는 240개였으나 Accepted는 110개에서 멈췄다. Actual loss 검출은 normal **81.988–82.062 ms**,
sanitizer **81.850–81.857 ms**, production **81.863 ms**였다. Raw CRC-valid replay가 계속되어도 valid age는 갱신하지 않았다.
6개 stream 전체의 fault별 valid RX loss 범위는 normal **80.009–82.062 ms**, sanitizer **80.002–81.981 ms**,
production **81.786–81.982 ms**였다. Source 30 ms 만료/current_sample unavailable과 RX 80 ms timeout latch는 별개다.
Late feedback 자동 복구를 허용하지 않았고 독립 zero 요청 뒤 실제 torque는 유한하게 감소했다.

새 workload의 CPU placement smoke는 normal·sanitizer 각각 1회(**12 runs 합계**) 실행했다.
배치·부하 적용은 **12/12 PASS**, ECU 계약은 **6 PASS / 6 FAIL**이다. Normal은 baseline/separate 통과·shared 2건 실패(RX miss/skip 7/8),
sanitizer는 baseline 2건 통과·shared 2건 실패(RX miss/skip 15/9)·separate 2건 실패(RX miss/skip 1/2)였다.
일부 critical stream의 최초 valid reference를 취득하지 못한 경우도 FAIL로 남겼다. 실패 run의 유효 job 관측은 모두 통계에 보존했다.
이는 새 RX 작업량/계측에서의 1회 smoke이며 10월 16일 3회 성능 비교와 구분한다. 기존 deadline을 완화하거나 실패 조건을 제외하지 않았다.

기존 M1 actuator 40 + EV 49 + M2 model 8 = **97 cases**를 normal·sanitizer 각각 모두 재실행해 통과했다.
Cantools 40.7.1의 기존 `build/m1-dbc-venv/bin/python`으로 12개 DBC·독립 CRC·C++ 36개 payload를 양 build와 교차 검증해 통과했다.
시스템 Python에는 cantools가 없었고 기존 전용 환경을 사용했다. 설치나 버전 변경은 하지 않았다.
Unit/build/Python/static/DBC는 각 build의 `m3-feedback-unit.txt/xml`·`m3-feedback-final-build.txt`, normal의 `m3-feedback-python.txt`·
`m3-feedback-final-clang.txt`·`m3-feedback-final-cppcheck.txt`, 양 build의 `m3-feedback-dbc.txt`에 남긴다.
각 build의 `m3-feedback-result/`에 45 runs의 trace/environment/source/profile/binary/artifact hash, 양 build의 `m3-feedback-steering/`·
`m3-feedback-placement/`에 회귀/부하 실패를 보존했다. VCan stdout은 `m3-feedback-vcan.txt`, 원래 trace 사본은 `m3-feedback-vcan-artifacts/`다.
최종 코드/문서/검사 로그 연결은 `build/m1-angle/m3-feedback-evidence.json`에 둔다. 예비 9 runs와 최초 static 진단도 별도 보존한다.
Markdown 95개·상대 링크/앵커 1069개, 요구 32개/TC 29개, YAML 3개와 Python 5개의 syntax/정합성을 검사했다.
전체 32개 요구/29개 system TC의 Result는 NOT RUN이다. Actual consumer를 차량에 반영하는 Central/Zone/Host bridge와
owner별 실행 budget/배치·우선순위·Target 검증 및 M3 수용은 후속이다. M1/M2 학습자 수용 기록도 PENDING이다.

2026-10-18 후속 [owner별 CPU 배치 비교](adr/ADR-0037-runtime-owner-cpu-placement.md)는
7개 owner의 선택적 CPU map·실제 affinity/policy 확인을 추가했다. 기존 상속 동작과 세 layout의 CPU 실험은 유지한다.
원래 RX source·CAN wire·8-frame budget·2 ms period/3 ms deadline과 ECU 설정·보호 기준을 변경하지 않았다.
실행된 RX body가 짧아도 다음 release까지 CPU를 얻지 못해 이전 job을 생략할 수 있다.
배치별 정상 계약을 확인하며 시한/skip 기준을 완화하거나 실패 조건을 골라 제외하지 않았다.

Normal·BUILD_TESTING=OFF production 각 3회(**24 runs씩**), ASan/UBSan 1회(**8 runs**)를 순서대로 실행했다.
CPU A=0·B=1이며 노출된 topology는 서로 다른 physical core다. Loaded 세 layout 모두 B에 같은 7/10 ms 요청 부하를 둔다.
IO baseline은 같은 IO map의 무부하 대조군이다. 부모는 고정하지 않고 runtime thread가 자기 mask를 설정한다.
Warm-up 제외는 0이고 layout/trace 순서를 회전했다. Host/VM의 다른 부하·IRQ·DVFS/cooling은 통제하지 않았다.
배치·부하 control은 **56/56 PASS**, 정상 ECU 계약은 **31 PASS / 25 FAIL**이다.
측정 window의 실제 busy CPU 하한 최소~상한 최대는 normal **67.08–69.08%**, production **66.92–68.76%**,
sanitizer **64.92–67.73%**였다. 요청 duty 70%를 실현된 일정 CPU 사용률로 간주하지 않는다.
아래는 full/minimal 합산 **계약 PASS/runs; RX skipped jobs**이며 normal·production의 layout당 예정 RX jobs는 7260개,
sanitizer는 2420개다. 이번 RX miss 수는 모두 skip 수와 같았고 실행하지 않은 duration을 만들지 않았다.

| Layout | Normal | Production | ASan/UBSan |
| --- | --- | --- | --- |
| colocated | 0/6; 47 | 0/6; 51 | 0/2; 50 |
| rx-isolated | 1/6; 1 | 2/6; 0 | 2/2; 0 |
| io-isolated | 6/6; 0 | 4/6; 3 | 2/2; 0 |
| io-baseline | 6/6; 0 | 6/6; 0 | 2/2; 0 |

RX만 이동해도 normal/production의 실제 output expiry가 각각 10/20개, Actual TX expiry가 17/17개 남았다.
Normal의 rx-isolated에는 Power miss도 1개 있었다. RX 자체의 miss 0만으로 전체 계약을 PASS로 바꾸지 않는다.
함께 이동한 IO 조건의 expiry는 모두 0이며, PASS 정상 run마다 **240 TX=240 RX=240 Accepted**였다.
Production IO의 잔여 RX skip 3개는 실패로 보존한다. Full run의 한 skip 근처에서는 monitor와 physical capture도
각각 약 4.27/4.31 ms 간격을 보였다. 공통 실행 지연의 관측이며 kernel/VM 원인을 식별한 scheduler trace는 아니다.

IO-isolated의 RX **실행된 job response(release→종료, ms)**는 아래와 같다. 실패 run의 유효 job도 포함했다.
같은 layout 안에서만 trace mode를 나누며 skip을 percentile에서 가짜 duration으로 대체하지 않는다.

| Build / trace | Executed / scheduled | Mean | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| normal full | 3630/3630 | 0.113605 | 0.193476 | 0.228865 | 0.992502 |
| normal minimal | 3630/3630 | 0.118963 | 0.200799 | 0.243726 | 0.714671 |
| production full | 3629/3630 | 0.108668 | 0.151443 | 0.233031 | 1.700965 |
| production minimal | 3628/3630 | 0.080966 | 0.124059 | 0.205948 | 0.287464 |

Production minimal의 작은 Max도 생략된 2개 job을 지우지 않는다. 고장 뒤 실행 경로 차이·scheduler/cache 간섭이 있으므로
layout 사이 body 비용 차이를 최적화 성능으로 해석하지 않는다. Sanitizer 1회는 기능/수명 확인이며 대표 성능 비교가 아니다.
Affinity는 CPU 예약/하드웨어 watchdog 격리가 아니며 IO 분리가 잔여 miss를 모두 해결했다고 선언하지 않는다.

고정 IO map `1,1,1,1,0,0,0`에서 기존 normal full/minimal·worker stall 5·CRC 손상·Actual replay를
normal·sanitizer 각각 1회(**18 runs 합계**) 실행해 모두 통과했다. 이 회귀에는 추가 CPU 부하가 없다.
기존 상속 동작의 normal fault matrix도 1회(**9 runs**) 통과했다. 기존 3-layout CPU 실험은 normal 1회(**6 runs**)로
control 6/6 PASS, 계약 4 PASS/2 FAIL(shared RX skip·Drive 미활성화)을 기록했다. 모두 별도 directory로 남긴다.

Normal·sanitizer C++ **각각 521개 PASS**, 배치 map/실제 thread 대응/순서/입력 검사 4개를 더한 Python **25개 PASS**다.
CLI malformed/duplicate/outside-mask 거부 **24조건**에서 socket/output directory 생성 전에 거부한 것을 확인했다.
3개 build와 변경 C++ 2개(runtime/dispatcher)의 clang-tidy 14 analyzer/bugprone·runtime header filter,
cppcheck 2.7 warning/performance/portability를 통과했다. 직전 M1/vCAN 97조건·DBC 검사는 위 이력을 따르며 이번에는 재실행하지 않았다.
RT policy probe는 즉시 종료하는 별도 child에 FIFO priority 1을 요청했고 **EPERM**, RLIMIT_RTPRIO=(0,0)이었다.
부모는 SCHED_OTHER/nice 0을 유지했다. RT priority 실제 실행 검증과 기존 Host 오류의 TSan은 **NOT RUN**이다.

세 build의 `m3-owner-results/`에 최종 56 runs의 trace/environment/source/profile/binary/artifact hash,
normal·sanitizer의 `m3-owner-faults/`에 고정 배치 18 runs, normal의 `m3-owner-inherited-faults/`·`m3-owner-legacy-placement/`에
상속 fault 9/기존 CPU 실험 6 runs를 보존했다. 예비 8 runs는 normal의 `m3-owner-probe/`이며 최종 수치에 포함하지 않는다.
Unit stdout은 각 build의 `m3-owner-ctest-console.txt`, Python/CLI/static/RT probe는 normal의
`m3-owner-{python,cli,clang,cppcheck,rt-probe}.txt`다. 최종 무결성·코드/문서 연결은 `build/m1-angle/m3-owner-evidence.json`에 둔다.
Monitor/plant의 physics 일부만이 아닌 전체 cycle budget, RT 적용 가능한 환경/Target timing과 M3 수용 검토는 남는다.
전체 32개 requirement/29개 system TC의 Result는 NOT RUN이며 M1/M2 학습자 수용도 PENDING이다.
이번 문서 검사는 Markdown 96개·상대 링크/앵커 1086개, YAML 3개·Python 5개의 syntax/정합성을 통과했다.

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
- 학습/확인 예제는 `actuator_demo` 실행 파일 하나로 묶는다.
  [진입점](../tools/actuator_demo.cpp)은 명령 분기·도움말을,
  `tools/demo/{steering,brake,drive,ev}_demo.cpp`는 각 도메인의 명령 구현을 맡는다.
  ECU 판단은 `vecu/`, 물리 모델과 SIL 연결은 `simulation/`에 둔다.
  기존 기능의 작은 변경마다 별도 demo를 추가하지 않는다.
- 단위 시험 파일은 모듈별로 유지한다. 기존 모듈의 조건/경계/fault 추가는 같은 파일의 case로 추가하고,
  새로운 독립 모듈이 생기면 시험 파일을 만든다.
- 통합 시험의 participant/helper/runner는 같은 영역 아래 모은다.
  세 actuator SocketCAN은 `tests/integration/can/`이며 새 fault는 기존 runner의 case로 확장한다.
- DBC 검사와 환경 확인은 `tools/`에 둔다. 목적과 확인 범위가 완전히 겹치는 임시 코드만 정리한다.
  표현/수용/transport의 서로 다른 검증 계층은 유지한다.

CMake의 `BUILD_TESTING=OFF`는 단위 시험과 통합 시험용 TX/RX build를 제외한다.
Fresh build에서 라이브러리와 `actuator_demo`만 생성되는 것을 확인했다.
아래는 2026-10-12 최초 예제 통합의 이력이다. 최신 구조 정리의 491개 unit·90개 CLI 비교 범위는 위 2026-10-16 기록을 따른다.
당시 기존 예제 4개의 정상/거부 출력 17개를 통합 프로그램과 비교했고 명령 오류 7개/도움말도 확인했다.
단위 시험 파일은 이 정리로 추가하거나 합치지 않았다.
정리 후 normal/ASan·UBSan 각각 unit 48개와 vCAN 8개 case를 통과했고,
통합 demo/TX/RX source 3개의 static analysis와 DBC 교차 검증도 통과했다.
수신 로그의 cycle flush와 실패 trace 보존을 보완한 범위는 [실행 기록](learning/m1_steering_socketcan.md#예제시험-정리와-재검증)에 남겼다.

## 현재 코드에서 검사하기

Repository root에서 실행한다. CMake는 `compile_commands.json`을 생성하므로 정적 분석에도
현재 target의 include 경로·define을 사용한다. M1 학습 문서의 수동 `-I` 명령은 당시 검사 이력이며,
현재의 도메인별 demo·ECU/SIL 파일 전체를 포함하지 않는다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized -j 4
ctest --test-dir build/m1-angle-sanitized --output-on-failure
```

예제의 명령 구현을 검사할 때는 dispatcher만 검사하지 않고 네 도메인 source를 포함한다.
다음은 demo 5개 source에 한정한 clang-tidy 명령이다. ECU/plant 변경 시에는 해당 구현·시험 source도
대상에 추가하고 검사 목록·도구 버전·결과를 기록한다.

```sh
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' tools/actuator_demo.cpp tools/demo/*_demo.cpp
```

Cppcheck도 현재 compilation database의 include/define과 변경 production/demo 범위를 사용한다.
GoogleTest macro의 기존 도구 제약은 위 기록처럼 따로 관리하며, 일부 source의 PASS를 전체 repository 결과로 확대하지 않는다.
SIL 실행 API와 core-only 경계 시험의 읽는 순서는 [실행 경계 안내](learning/m2_execution_boundaries.md)에 있다.
M3의 wall-time 실행과 report 재현은 [첫 Steering timing 안내](learning/m3_steering_timing.md)를 따른다.

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
