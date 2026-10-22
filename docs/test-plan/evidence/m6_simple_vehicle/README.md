# M6 Simple Vehicle / 종방향 MIL 첫 구현

2026-10-22. **M6 첫 모델·통합 경계 검증 완료, M6 전체 종료 아님**.
시작 HEAD와 fetch 후 origin/main은 `ae3bb4f`, clean이었다. 저장소/상위 AGENTS.md 없음.
사용자 변경은 없었고 기존 M5 수용·DDS/TSan FAIL/OPEN 근거를 수정하지 않았다.
구현 `b0819ab`, NormalStop 수정 및 최종 C++ 실행 소스 **`13d1e87`**,
모델/도구 계약 `bf152b2`. 최종 Normal SDK cohort는 커밋 직전에 실행했으며
`plan.json`의 실제 source hash·바이너리 SHA가 동일 C++ 내용임을 식별한다.

[사전 protocol/수정별 비교](protocol.md), [ICD](../../../icd/simple_vehicle.md),
[ADR-0063](../../../adr/ADR-0063-simple-vehicle-and-longitudinal-mil.md),
[기계 판독 결과](results-summary.json), [전체 SDK9회](results.csv),
[시간축](timeline.csv), [Leaf 갱신 여유](renewal-margins.csv),
[MIL과 실제 runtime 그래프](model-and-runtime.svg), [SDK 경고 원문 위치](sdk-warnings.csv).
원본은 [archive](raw-evidence.tar.gz), [파일 manifest](raw-manifest.json), [archive 식별자](archives.json)에 있다.
아래 raw 상대 경로는 archive 내부다. 과거 evidence를 덮어쓰지 않았다.

## 구현 범위

Central·Front·Rear 실제3-process SOME/IP와 기존8참여자 INIT/Release ACK/RunLease/arm,
CAN/P05·원래 source/expiry·20ms envelope·host10-v1·native2ms/4ms를 유지했다.
선택형 `--simple-vehicle`에서 persistent SIL owner가 실제 actuator torque/pressure/angle을
사용해 전진 속도·rear-axle x/y/yaw를 계산한다. 같은 실제 wheel speed가 Drive sensor→
CAN Actual→Rear→SOME/IP→Central validator로 돌아온다. ACK나 정상 상태를 합성하지 않는다.
EV power/circuit/Battery가 전기 에너지·SOC를 단독 소유하고 차량 모델은 kinetic/work만 계산한다.
ECU 새 Epoch가 물리 model epoch7·position·sequence를 reset하지 않는다.

실제 ECU vehicle demand는 기존 **0.2m/s²/curvature0.02 fixture**다. C++ 속도 controller가
추가된 것이 아니다. 별도 Python PI/plant MIL이30/20/0km/h reference를 검증한다.
MIL은2ms logical plant,20ms PI,50ms sensor이며 실제 Host local wheel acquisition 약0.5ms와
구분한다. Python60ms age를 실제 Drive30ms 계약에 적용하지 않았다.
M7 CARLA20Hz/실제 Drive source-age 연결은 별도 설계 대상이다.

물리 가정: flat/forward/no-slip,1000kg·r0.3m·wheelbase2.7m·0.001Nm/Pa,
rolling100N+drag0.4v². Geometry/force scale은 기존 allocator fixture와 맞췄다.
후진·경사·타이어·OEM calibration·M6 전체 EV scenario coverage는 미검증이다.
`reference.yaml`은 기록이며 실행 loader가 아니다. 실제 값/방식은 ICD의 코드 경로에 있다.

## 발견과 수정 전후

| 원본 | 발견 / 수정 | 실제 확인 |
| --- | --- | --- |
| `mil-attempt1` exit1 | PI만으로 정지 직전71.95s의 reference0.0198413,actual0.0304410m/s; overspeed53.42% | reference·판정은 유지. reference derivative feedforward와 감속120ms preview(50+50+20ms) 추가 |
| `mil-attempt2`, `mil-final` | PI+conditional anti-windup/slew·source 검증 유지 | 각87logical s,1741sample. 최종 plateau별200sample, max0.049180/0.046337/0.005251km/h, max overspeed1.2233% |
| `sdk-dev-normal/normal-1` exit1 | 실제 이동 후 Brake terminal Hold 갱신 거부. 첫 인계 때 압력 하강 | `stop-before.txt`의 새 논리 재현0/1 FAIL. 최초 안정 dwell 후보만으로는 해결 안 됨 |
| `sdk-normal/normal-1` exit1 | 안정된300kPa는 **이전 감속 목표**; delayed100kPa 목표가 인계 직전에 적용 | 실제 standing-hold 목표100kPa(+wire1step1000Pa)에 도달한 후 기존60ms dwell 요구.5s braking/2s shutdown·Leaf guard·원래 권한은 유지 |
| `stop-final.txt` / `sdk-final-normal` | 실제 목표 도달·stable acquisition으로 인계 | 관련18/18, 실제 정상 stop/HV-off/SDK stop·join PASS.10ms/20ms renewal을 늘리지 않음 |
| `sdk-normal/command-loss-1` exit1 | 기존 정상 torque 조건은 충족했으나 rolling force를 넘기 전 주입; 새 차량 이동 기준 FAIL | M6에서 실제 validated wheel speed>=0.1rad/s 후 주입. 시한/거부 기준 변경 없음; 최종 원래 expiry 보호 PASS |

첫 SDK 정상 실패에서 정상205batches와 세 Leaf 갱신은 성공했으며4ms miss는0이었다.
실패를 정상 PASS와 합치지 않았다. Brake monitor private state는 기존 raw에 없어 그 predicate
전부를 소급 측정했다고 주장하지 않는다. 실제 압력/time axis·Brake negative result와 최소
논리 회귀를 근거로 인계 조건을 좁혔으며 Leaf 검사/SDK 코드를 억제하거나 바꾸지 않았다.

초기 build의 새 target configure 누락, gtest macro 괄호 경고, pressure codec include 누락은
로그로 보존했다. include 실패 직후 실행한 `stop-after.txt`는 stale binary여서 수용에서 제외한다.
`stop-after2`는 첫 stability 후보17/17이며 최종 해결 근거가 아니다. 전체 원본/실패를 재분류해 숨기지 않는다.

## 최종 고정 검증

| 시험 | 결과 / 범위 |
| --- | --- |
| 실제3-ECU Normal FIFO normal / Rear command-loss / Rear restart-live | **각1/1,3/3 PASS**. 정상2540ms·shutdown tail2500ms·runner timeout20s |
| 실제 SDK ASan+UBSan normal / TSan normal | **각1/1 PASS**, diagnostic0. TSan 기존 `setarch x86_64 -R`; Normal 성능과 별도 |
| 최종 전체 C++ Normal / ASan+UBSan | **각999/999 PASS**, 각1회. 기존987 이름/assertion 보존 + vehicle10/stop2 |
| TSan 변경 경계 | **28/28 PASS**, vehicle10 + NormalStop/lease18; SDK 전체 안전성 증명 아님 |
| Python model/verdict / 기존 pilot bookkeeping | **8/8 +24/24 PASS**; SDK 실행 아님 |
| build/ 없는 tracked dependency export | **8/8 +24/24 PASS**. 전체 checkout/SDK 실행이 아님; 원래 lock 준비 시험 포함 |
| 최종 MIL | **1/1 PASS**,3 plateau·600steady samples, 전체1741sample,87logical s |

최종 SDK **5/5 PASS**, 개발/후보 포함 **6 PASS/3 FAIL /9회**다. 실패 raw exit를 바꾸지 않았다.
MIL 개발 FAIL1회/수정 비교PASS1회/최종PASS1회를 별도 보존한다.
첫 fresh export는 headers와 기존 historical JSON을 누락해 pilot22 PASS/2 ERROR였다.
실제 필요한 tracked dependency를 포함한 export로만1회 비교했다(`fresh2-python.json`).
프로젝트 동작 오류가 아니며 첫 실패도 archive에 있다.

Normal 실제 최고속도0.159519m/s, 이동0.143854m, 마지막 speed0이었다.
Central validator는 실제 양수 wheel speed와 연속 feedback을 관측했다. 실제 SDK 테스트를
30km/h 주행/MIL 결과로 확대하지 않는다. 재가입도 model epoch/sequence·누적 거리를 보존했다.
정상 control 후 command-loss에는 원래 expiry와 실제 torque0/brake 보호를 관측했고,
새 Epoch2에는 실제8ACK/arm 뒤 세 Leaf 갱신·정상 stop을 완료했다.

| Leaf | Normal 정상 최소 이전-expiry 대비 수용 여유 | Normal 재가입 후 최소 여유 |
| --- | ---: | ---: |
| Steering |13.706382ms|11.003712ms|
| Brake |13.703937ms|11.001287ms|
| Drive |13.211365ms|10.357072ms|

Sanitizer 여유/시각은 CSV에서 별도 비교한다. 무제한 운용이나 worst-case bound가 아니다.
최종5회에는 native miss0, forced cleanup0, unexpected SDK error0, sanitizer diagnostic0이다.
Rear crash의 의도한 SIGKILL은 정상 종료에 세지 않고 생존 프로세스의 실제 stop/join을 검사했다.

## 환경 / 계측 / 제한

Host8physical/16logical, CPU Central1/FIFO11,Front2/FIFO18,Rear7/FIFO18,
plant3/FIFO19,independent monitor0/FIFO20. SDK4/5/6 OTHER0,plant aux14 OTHER0.
실제 RTlimit20/20와 각 thread 적용값은 environment/lscpu/runtime/watch JSON에 있다.
이번은 quiet만 실행했다. 기존 부하profile/48회/OTHER 진단/새복합고장/Jetson은 재실행하지 않았다.

SDK COVESA vSomeIP3.7.6 /4187431d2815bd351845a09d01aa85b2a3163cab,Boost1.85,GCC11.4.
SDK/Boost library SHA가 기존 M5와 같고 SDK source clean이다. 새 project binary와 SDK
core/cfg/sd/e2e·Boostfilesystem/atomic sanitizer symbols 및 실제 process maps/ldd/
compile_commands를 보존했다. libc/libstdc++ 비계측, mmap SIL IPC 전체 안전성 미입증,
TSan fixed-layout과 실행된 유한 경로만의 결과다. annotation/suppression/SDK patch 없음.

최종 raw SDK warning308줄을 보존했다: startup interface/route32,SD multicast lifecycle26,
실제 fault/stop 시작 뒤 socket/reset/cancel250. 발생 timestamp를 동일 run clock sample로
연결했다. 예상 밖 `[error]`, `Maximum wait time for send operation exceeded`는0이다.
550ms SD의 pinned SDK multicast timer/lifecycle 의미는 기존 Rear 근거와 같으며 TCP 전달,
처리 완료와 native/renewal 결과는 별도로 확인했다. 경고를 삭제하거나 sanitizer를 면제하지 않았다.

M5 Host 한정 수용/과거 TSan FAIL·OPEN-SOMEIP-REAR-01/DDS CLOSED·역사적 OPEN은 유지한다.
M4 전체 종료, Target/Jetson, 장시간/부하 M6 profile, 전체 EV/회생 에너지 scenario,
M7 CARLA, M8 C++ controller·동등성·전체 차량 SIL은 **NOT RUN**이다.
다음 단계는 M6 차량/EV energy와20Hz sensor boundary의 남은 scenario 범위를 고정하는 것이다.
M8 실제 controller나 M7 CARLA를 자동으로 시작하지 않았다.

## 재현

새 output directory를 사용한다. configure/build는 기존 SDK setup이 있으면 아래처럼 수행한다.
새 checkout의 SDK는 기존 `python3 tests/integration/someip/build.py normal|asan|tsan`으로 준비한다.

```bash
mkdir -p build
flock -n build/.m4-exclusive.lock cmake --build build/m5-someip-normal/project --target someip_front_adapter --parallel 4
python3 tests/integration/someip/front_run.py build/m6-new-normal --three --fault-zone rear --native-watch --fifo --simple-vehicle --profile normal --cases normal command-loss restart-live
python3 tests/integration/someip/front_run.py build/m6-new-asan --three --fault-zone rear --native-watch --fifo --simple-vehicle --profile asan --cases normal
python3 tests/integration/someip/front_run.py build/m6-new-tsan --three --fault-zone rear --native-watch --fifo --simple-vehicle --profile tsan --fixed-layout --cases normal
flock -n build/.m4-exclusive.lock python3 models/longitudinal/mil.py build/m6-new-mil
python3 tests/unit/m6_model_test.py
python3 tests/unit/someip_pilot_test.py
```

정확한 최종 build/test argv·exit는 raw `final-checks.json`, 코드/실행계측은
`instrumentation.json`, `*-compile-commands.json`, `*-build-options.txt`,각 SDK `plan.json`이다.
시험/timeout/누락·unexpected error는 결과를 저장하고 exit1이며 새 성공으로 원래 실패를 지우지 않는다.
