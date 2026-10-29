# M6 차량 운동 / EV 에너지 통합

2026-10-22. **구현·component 검증 및 일부 Host 기능 PASS / 전체 M6 수용 보류**.
시작/fetch 후 HEAD·origin/main `f57e18c`,clean이었다. 상위/저장소 AGENTS.md 없음,
사용자 변경 없음. 최종 실행 소스 **`d242861`**이며 구현 `07563b8`, receiver 수정 `b3424de`다.
기존 M5 한정 수용·M6 첫 MIL·DDS/과거 FAIL/OPEN은 변경하지 않았다.

[사전 protocol/수정별 비교](protocol.md), [에너지 경계](../../../interfaces/vehicle-energy.md),
[ADR-0064](../../../archive/design-decisions.md#adr-0064),
[기계 판독 전체 결과](results-summary.json), [실제 SDK12회](results.csv),
[에너지 항과 전체 runtime 판정](energy-accounting.csv), [시간축](timeline.csv),
[갱신 여유](renewal-margins.csv), [Normal 실패 축](failure-axis.json),
[sanitizer 실패 축](sanitizer-failure-axis.json), [실제 곡선](energy-and-protection.svg),
[SDK 원문 오류/경고 위치](sdk-warnings.csv).
원본은 [archive](raw-evidence.tar.gz),[파일 manifest](raw-manifest.json),[archive SHA](archives.json)에 있다.
아래 raw 상대 경로는 archive 내부다. 과거 evidence는 덮어쓰지 않았다.

## 실제 구현과 수정

Persistent physical owner의 `VehicleEvModel`이 기존 SimpleVehicle와 EvPowerModel을
후보 상태로 계산해 함께 commit한다. 실제 torque/pressure/angle과 실제 이동거리로 계산한
같은 구간 motor work를 전기 변환에 전달한다. interval 결과의 source=end와 원래 oldest
motion dependency를 명시하며, sensor/명령 source를 새로 찍지 않는다. Brake/steering의
오래된 dependency도 Battery flow까지 보존한다. 오류 때 vehicle만 먼저 움직이지 않는다.

관성·friction·road·motor/inverter·RC/contact·auxiliary·battery ohmic·capacitor·chemical
항의 ledger와 별도 offline 재계산을 추가했다. 새 ledger는 제어 입력이나 권한을 만들지 않는다.
기존 ordinary EV step/ZOH와 generic receiver defaults는 유지한다.

실제 normal cycle에서 capability200Nm/charge30000W가 와도 회생이 거의 즉시0으로
줄었다. 첫 fixed20ms-support 가설은 실제 Unavailable(1) 분기/잔여25ms로 기각했다.
원래 wire source가4.25ms, dependency가30.38ms인 시점에 Central receiver가 capability를
지웠다. EV/allocator는 기존70ms dependency를 정의했지만 Central/Rear DriveReceiver는
기본30ms를 사용했다. 두 EV receiver에 기존70ms 옵션을 명시했다.
**Torque/wheel/capability source30ms·80ms RX timeout·20ms support 검사·원래 command
expiry·20ms envelope는 변경하지 않았다.**

| 비교 원본 | 결과 / 해석 |
| --- | --- |
| `quadrature-before.txt` | 기존 T300Nm/v3m/s/20ms*10의 electrical616.133107J vs vehicle617.925513J,1.792405J mismatch FAIL |
| `quadrature-after.txt`,최종 vehicle 계약 | 같은 interval work로 PASS. 최종11개 vehicle/fixture 계약은 전체 회귀에 포함 |
| `contract-test.txt` | 새 friction-only receivedDC==0 가정8/9. 초기 RC/capacitor branch 교환도 receivedDC에 포함돼0.003744J; 원본 보존 후 실제 mechanical0/positive bus load/energy balance로 바로잡음 |
| `dev-nominal`, `dev-capability-axis`, `dev-wire-axis` | 모두 normal/시한/종료는 PASS, 실제 regen/energy 기준 FAIL. 원래 raw exit1 유지 |
| `capability-before.txt` | 첫 RX를100ms에 줘80ms RX timeout을 먼저 유발한 새 시험 준비 결함; capability predicate 근거에서 제외 |
| `capability-before2.txt` → `capability-after.txt` | 실제 AsyncCoordinatorPort에서40ms dependency 소실0/1 FAIL → 관련17/17 PASS. original source30ms 초과는 계속 거부 |

## 고정 실제 SDK 결과

모두 실제 Central·Front·Rear netns/TCP와 기존8개 참여자의 INIT/Release ACK/credit/arm을
사용했다. `energy-cycle-v1`은 arm 기준 가속2s/타력0.6s/제동1.9s/hold의 scenario demand다.
C++ 속도 PI 구현이나30km/h 추종 시험은 아니다. CPU/FIFO는 아래에 명시한다.
정상 관측8s+기존 shutdown tail2.5s,2ms opportunity/4ms guard·host10-v1은 그대로다.

| 최종 소스 d242861 | 결과 | 완료/실패 범위 |
| --- | --- | --- |
| Normal FIFO nominal cycle / charge-zero | **각1/1 PASS** | 실제 regen+friction·BMS0W/마찰 stop·HV-off·SDK stop/join |
| Normal FIFO owner-pause / Rear restart-live | **각1/1 PASS** | 독립 감시·보호, 생존 Central/Front 유지·새 Epoch2의 실제8ACK/arm 후 cycle 재개 |
| Normal FIFO command-loss | **0/1 FAIL** | 원래 expiry/zero-target 선택은 동작. 기존 actual torque/brake100ms 기준 미충족 |
| 실제 SDK ASan/UBSan normal / Rear restart-live | **1/1 PASS /0/1 FAIL** | 재가입 후 일부 기능 수행·energy ledger PASS이나 Central4ms miss/보호/후속 queue drop, 정상 관측·stop 미완료 |
| 실제 SDK TSan normal / Rear restart-live | **0/1,0/1 FAIL** | normal 초기20ms result timeout 뒤4ms miss; rejoin 새 Epoch arm/일부 갱신 뒤 gateway/negative result·보호. 전체 cycle/stop 미완료 |

최종 실제 SDK **5 PASS/4 FAIL /9회**다. 개발3회 FAIL까지 전체는 **5 PASS/7 FAIL /12회**다.
raw exit·분모·기존 assertion은 보존했다. actual memory/UB/race 진단은0이나 미완료 기능을
검증 완료로 세지 않았다. queue drop/broken pipe 등 예상 밖 SDK `[error]`도 FAIL에 남겼다.
SDK stop/join은 살아 있는 프로세스에서 반환했고 forced cleanup0이다. 주입 Rear SIGKILL은
정상 종료에 포함하지 않는다. 정상 실패 뒤 보호가 동작한 사실을 normal PASS로 합치지 않는다.

## 실제 에너지와 갱신

| Normal 실제 물리 항 | nominal cycle | charge-zero |
| --- | ---: | ---: |
| 최고 실제 속도 |1.69115m/s(약6.09km/h)|1.69023m/s|
| 배터리 received DC |194.028433J|0J|
| 마찰 소산 |776.281239J|1245.216557J|
| 도로 저항 소산 |379.528533J|368.598605J|
| 최종 kinetic energy |0J|0J|
| max combined residual |9.67157e-9J|2.38460e-8J|

두 경우 모두 actual output/센서→Drive CAN/P05→Rear SOME/IP→Central validator 경로다.
charge-zero는 초기 SOC0.96을 실제 Battery가 관측시키고 기존 BMS ramp가0W를 발행했다.
정상 nominal의 음의 실제 torque/양의 wheel speed·실제 friction 동시 응답과 low-speed
capability0/actual torque0 전환을 확인했다. SOC 순증가를 회생 근거로 쓰지 않았다.
combined budget0.001J, coupling1e-6J, vehicle balance1e-5J를 사전 고정했고 변경하지 않았다.
같은 오류 검사는 매 model step에 적용하며 CSV는 bounded10ms 기록의 관측 최대다.

정상 cycle 최소 Leaf 갱신 여유는12.183756ms,charge-zero는9.016162ms,
Normal 새 Epoch 재가입은10.855225ms다(각 run의 세 Leaf 최소).
이는 이전 명령의 **원래 expiry − 다음 명령 실제 Leaf 수용**이며 future worst-case bound가 아니다.
Rear 재가입 뒤 physical model epoch7/sequence·누적 energy·position을 reset하지 않았다.

## 남은 차단 / 시간 계약의 구분

**OPEN-M6-ENERGY-01 — 새 높은 torque 조건과 기존 physical100ms gate의 양립성.**
command-loss injection611255322688253ns,직전 torque170.5Nm,local zero-target 선택은
주입+**18.336023ms**다. 선택 전 normal torque가 더 증가했고 첫 physical trace의
complete 조건(torque<=1Nm/pressure>=100kPa)은주입+**122.706671ms**였다.
약102.206ms에도 torque22.4542Nm가 남아 있어 단순10ms sampling 오차만의 실패가 아니다.
기존2000Nm/s zero ramp로 약187Nm를 줄이는 데만약94ms가 필요하다. 원래 expiry 이후
선택 latency와 합치면100ms 안에 actual zero는 양립하지 않는다. rate/expiry/gate를 바꾸거나
낮은 torque에서 다시 주입해 기존 FAIL을 PASS로 만들지 않았다.

SYS-SAFE-004는 timeout 때 **local zero target 선택**을 요구하고 실제 torque dynamics/
response deadline은 TBD-03으로 구분한다. 기존 좁은 Host fixture의 actual100ms 판정은
그대로 FAIL이다. 다음 검토는 이 M6 torque 범위의 실제 response budget과 해당 gate 적용
범위를 구체화하는 것이다. 이 판단 전 새 energy profile 전체를 수용하지 않는다.

**OPEN-M6-ENERGY-02 — 계측 조건의 wall/transport 기능 미완료.**
ASan 재가입 새 Epoch의 Central owner slot3120이4ms를 놓치고 LocalProtection을 선택했다.
이후 SDK feedback queue drop이 발생했다. TSan normal은 token22/operation2의 원래
20ms result deadline611329547731424ns를 지나 timeout611329547861038ns가 먼저 나왔고,
이후 Front native miss/보호·SDK errors가 이어졌다. TSan 재가입은 새 Epoch에서 Rear local
보호와 negative result가 먼저 관측됐다. 정확한 내부 rejection predicate는 이 근거로 확정하지 않는다.
SDK 전체 결함/경합이나 새 energy 적분이 최초 원인이라고 단정하지 않는다.
실행된 범위·원본을 남기고 같은 조건을 반복하지 않았다. sanitizer wall-time과 Normal 성능을
구분하지만 unexpected SDK errors/미실행 기능을 PASS로 면제하지 않는다.

## 회귀·준비 검증

- 최종 전체 C++ **Normal1011/1011·ASan/UBSan1011/1011**,각1회.
  기존999 이름/assertion 보존 + VehicleEnergy10/fixture1/receiver1.
- TSan 변경 경계 **28/28 PASS**(vehicle/fixture11 + async owner17).
  첫 build는 CMake 재생성 전 새 target 미등록으로 exit2/runtime NOT RUN이었다.
  configure 후 실제28개를1회 실행했다. 원래 build exit는 그대로다.
- Python 새 energy verdict10/10 + 기존 model8/8 + pilot24/24 = **42/42 PASS**.
  build/ 없는 tracked dependency subset export도42/42. 전체 checkout/SDK 실행으로 주장하지 않는다.
- `component_traceability.csv`에 component evidence5행을 추가했다. 실제 SDK 판정은 별도
  results/energy CSV에 연결하며 C++ PASS로 실패 SDK case나 전체 TC-REG를 수용하지 않는다.

## 환경·재현·계측

Host8physical/16logical,CentralCPU1/FIFO11·Front2/FIFO18·Rear7/FIFO18,
plant3/FIFO19·monitor0/FIFO20,SDK4/5/6 OTHER0·plant auxiliary14 OTHER0다.
실제 RTlimit20/20와 per-thread policy/affinity/priority는 environment/lscpu/runtime/watch JSON에 있다.
세 IP10.88.0.1/.2/.3/29,각 netns/routing identity/IPC resource 분리를 유지하고 실제 TCP
packet/pcap/socket을 보존했다. Authority/control에 SIL/감시 공유 채널을 쓰지 않는다.

Pinned vSomeIP3.7.6/4187431d2815bd351845a09d01aa85b2a3163cab,SDK source clean,
Boost1.85/GCC11.4. SDK/Boost library SHA는 앞선 M6와 같고 project·SDK core/cfg/sd/e2e·
Boostfilesystem/atomic sanitizer symbol 및 실제 ldd/maps/compile command를 기록했다.
libc/libstdc++ 비계측,mmap SIL IPC 전체 안전성 미입증,TSan 기존 process-local fixed layout이다.
annotation/suppression/SDK patch는 추가하지 않았다.

최종 SDK 원문 warning/error1297줄 중 `[error]`134줄은 원래 FAIL로 남겼다.
단순 startup/SD/종료 warning과 queue-limit drop/broken pipe를 같은 면제로 처리하지 않았다.
M4 전체·Jetson·실제 IO·M7 CARLA·M8 C++ PI/동등성·장시간/부하·동적 charge-loss 조합은 NOT RUN이다.
새8s quiet 범위의 일부 기능 결과로 기존 수용 범위를 확대하거나 역사적 OPEN을 닫지 않았다.

```bash
mkdir -p build
python3 tests/integration/someip/build.py normal  # 새 checkout의 pinned SDK 준비
flock -n build/.m4-exclusive.lock cmake --build build/m5-someip-normal/project --target someip_front_adapter --parallel 4
python3 tests/integration/someip/front_run.py build/m6-energy-new --three --fault-zone rear --native-watch --fifo --simple-vehicle --energy-cycle nominal --profile normal --cases normal command-loss owner-pause restart-live
python3 tests/integration/someip/front_run.py build/m6-zero-new --three --fault-zone rear --native-watch --fifo --simple-vehicle --energy-cycle no-charge --profile normal --cases normal
python3 tests/integration/someip/front_run.py build/m6-energy-asan-new --three --fault-zone rear --native-watch --fifo --simple-vehicle --energy-cycle nominal --profile asan --cases normal restart-live
python3 tests/integration/someip/front_run.py build/m6-energy-tsan-new --three --fault-zone rear --native-watch --fifo --simple-vehicle --energy-cycle nominal --profile tsan --fixed-layout --cases normal restart-live
python3 tests/unit/m6_energy_test.py
```

새 output을 사용한다. 실제 argv·exit·source/binary SHA는 각 plan/command/result와
`final-checks.json`; 마지막 setup 보완은 `boundary-followup.json`이다. 최초 실행 driver는
`final-checks-executed.py`,재현 driver에는 새 target configure를 명시했다.
실패/timeout/누락/예상 밖 SDK·sanitizer 오류는 저장 후 exit1이며 raw 판정을 바꾸지 않는다.
