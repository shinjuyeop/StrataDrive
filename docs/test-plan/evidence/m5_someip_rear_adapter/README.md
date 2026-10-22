# Host Central ↔ Front/Rear SOME/IP 연결

2026-10-22. **문서화한 Normal FIFO Host functional SIL 범위 한정 수용 — Rear 연결 완료**.
시작 HEAD/fetch 후 origin/main은 `da5a6696caa89f3397cab1231cc8998ffe0c4170`, clean이었다.
사용자 변경·이후 원격 변경은 없었다. 최종 실행 소스는 **`a790032`**다.
이 판정은 아래 CPU·부하·관측 시간에 한한다. **TSan 정상 관측 구간은 FAIL/미완료**이며,
사용자가 승인한 sanitizer wall-time/Normal 성능 구분에 따라 Normal FIFO 수용과 별도로
남긴다. 실제 sanitizer 오류는 면제하지 않았고 관측된 memory/UB/race 경고는0이다.
모든 필수 시험이 PASS라고 주장하지 않는다. 전체 M4·Jetson·M6·전체 시스템 수용은 아니다.

[사전 protocol과 수정별 비교 조건](protocol.md), [ICD/소유권](../../../icd/someip_rear_adapter.md),
[기계 판독 집계](results-summary.json), [전체41회 결과표](results.csv),
[Leaf 갱신 여유](renewal-margins.csv), [세션·보호 시간축](timeline.csv),
[고장별 요약/실제 PID](fault-timeline.json), [남은 TSan 실패 시간축](tsan-expiry-axis.json).
[원본 archive](raw-evidence.tar.gz)는4013개 파일이며 [파일 SHA256](raw-manifest.json),
[archive SHA256](archives.json)으로 식별한다. 아래 상대 원본 경로는 archive 내부 경로다.
기존 Front/DDS/과거 실패 근거는 수정하지 않았다.

## 실제 연결과 설정

Central은 coordinator/allocation/Ingress/실제 SessionCoordinator·RunLeaseIssuer만 실행한다.
Front는 FrontZone/Steering/Brake, **Rear는 RearZone/Drive/BMS/Power의 유일한 실행 owner**다.
공통 Zone endpoint와 transport를 재사용하며 adapter를 복제하지 않았다. 별도 persistent
SIL process가 기존 물리·센서 모델을 소유한다. Enable/vehicle demand/stop intent는 시나리오
fixture이며, 정상 Actual/health나 ACK를 생성하는 fixture는 없다.

Central1/Front2/Rear7의 FIFO 우선순위는11/18/18, plant3은FIFO19,
독립 monitor는CPU0/FIFO20다. SDK dispatch/IO/sender는CPU4/5/6 OTHER0,
plant auxiliary는CPU14 OTHER0다. Host는8개 physical core/16 logical CPU이며 siblings는
0↔8 …7↔15다. 실제 사용자 RT limit20/20와 각 thread policy/priority/affinity를
`environment.json`, `lscpu.txt`, 각 사례 `*.runtime.json`, `*.native.watch.json`에 보존했다.
RT 권한·sudoers·커널은 변경하지 않았다. Owner/monitor만 명시적으로 FIFO를 적용했다.

세 netns의10.88.0.1/.2/.3/29를 veth bridge로 연결했다. Central↔Front
0x5344..0x5347/TCP30501..30504와 Central↔Rear0x5348..0x534b/TCP30505..30508은
서로 다른 service/instance binding이며, node별 routing manager·client/diagnosis·network·
`/tmp`·`/dev/shm`을 분리했다. 실제 두 IP 경로의 packet 수, PCAP, socket, netns inode,
PID를 기록했다. 로컬 SDK IPC만으로 성공한 결과가 아니다.

모든 inter-ECU command/result/Actual/health/전원·허가/session/protection은 owner-wire
bytes와 SOME/IP를 통과한다. SIL sensor/output 공유 버스의 기존 released-Epoch fence는
물리 override의 세대 구분만 담당하며, ECU 세션/arm/credit 권한을 만들지 않는다.
감시 공유 채널도 실행 진행/고장 관측만 전달한다. 원래8개 참여자 ACK255, actual preflight,
RunLease/arm과 **Front 결과 확인 후 Rear 배분**을 유지한다. SD·TCP·probe·send-return은
제어 권한/처리 완료가 아니다.

`host10-v1`: 실제 allocation10ms, management10ms/phase+4ms, 다음 release 뒤8ms
허가 지원 검사, 원래20ms envelope·source age·내부 expiry·CAN/P05·Epoch/token을 유지했다.
RX/TX는 peer/lane별8, SDK endpoint8192 bytes다. 네트워크 대기는 비동기이며 owner는
응답을 기다리며 멈추지 않는다. 그룹 owner의 실행 기회2ms/감시4ms는 controller10/20ms
주기와 구분한다. 같은 thread가 실행하는 owner들은 별도 실행자로 중복 계산하지 않았다.

Normal 관측은 readiness부터2540ms, 뒤이어 실제 NormalStop→Leaf handoff→실제 HV-off를
완료하고 SDK stop/join을 확인한다. 원래 shutdown2s를 위한 별도2500ms 관측 tail이며,
제어 시한 연장이 아니다. 종료/원본 파일 dump는 guarded control 수명 뒤에 수행한다.

## 발견한 결함과 수정

| 근거 / 수정 | 수정 전 실제 관측 | 수정 및 확인 |
| --- | --- | --- |
| `1145720` 3-process 구현 | Rear 로컬 소유권/네트워크 경계가 없었음 | 역할·service binding, Rear endpoints와 실행 감시, real NormalStop 추가. 개발 normal1/1 |
| `b667609` 보호된 재가입 중 ingress | 살아 있는 Front 피드백이 Central graph 정리·durable Epoch IO 동안 RX8을 넘김 | 이미 보호/gate closed인 전환에만 ingress를 닫아 기존/도착 메시지를 lane별 정산. 새 graph/감시 준비 후 재개, 실제 새 handshake. overflow latch를 지우거나 큐를 늘리지 않음 |
| 주입/관측 전제조건 |10 batches 뒤에도 Drive 실제 torque가0; 보호 압력 ramp 완료 전 cleanup | Central validator의 실제 positive Drive Actual·released Brake 확인 후 주입. 실제 물리 보호를 관측한 뒤 cleanup; 원래100ms 판정 유지 |
| `77fba74` 재가입 진단 시각 | INIT **요청** 때 지운 보호 시각이 실제 enable 전 이전 상태로 재설정됨 | 실제 positive local Zone INIT ACK 뒤 진단 시각만 새 세대로 구분; 이전 값은 event에 보존. 제어 reset을 추가하지 않음 |
| `a790032` 원격 wrapper의 quiescence 위반 | TSan 재가입의 Brake negative INIT ACK, enable+17us. 작은 실제 owner 재현도 INIT/Release FAIL | Prepare Ready가 이미 정지시킨 이전 actor에 old-credit 보호를 반복 적용하지 않음. 원래 actor의 quiescence를 존중. 진짜 session fault/Abort는 계속 보호를 호출 |

마지막 결함은 `quiescence-before.txt`의 실제 owner 회귀 **0/1 FAIL**에서
`quiescence-after.txt`의 관련 **23/23 PASS**로 검증했다. 원래 live old credit을 enable+10us에
서비스하면 이전 actor의 clock을 진행시켜 원래 enable에서 INIT를 거부하던 경로다.
새 INIT/Release/credit 이전에는 gate가 열리지 않으며, 다음 quiescent proposal의 실제 Abort도
출력을 보호하는 assertion을 추가했다. SessionParticipant/제어기 clock 검사는 바꾸지 않았다.
과거 TSan trace에는 private actor last-observed 값이 없으므로 당시 거부의 내부 predicate까지
소급 확정하지 않는다. 실제 최종 TSan 재가입은 통과했다.

Owner-pause의 authority RX8 overflow는 의도한 소비 중단 뒤의 결과다. 해당 owner의 실제
native fault **604162493185470ns** 뒤 overflow **604162508242256ns**, 추가5개 거부를
확인했다. 판정은 이 순서·대상·거부 수·원래 상한과 독립 물리 보호를 모두 요구한다.
정상 운전 overflow나 fault 이전 overflow를 면제하지 않는다.

## 최종 실행 결과

| 최종 소스 a790032의 실제 시험 | 결과 | 판정 범위 |
| --- | --- | --- |
| Normal FIFO 정상 무부하 / 기존 부하 | **2/2 / 2/2 PASS** | CPU1/2/7에 기존 OTHER7ms busy/10ms 부하; actual feedback/model, 정상 stop/HV-off/SDK join |
| Rear command-loss / owner-pause / Central-stop / Rear restart-live | **각1/1, 총4/4 PASS** | 정상 전제조건 뒤 주입, 원래 expiry/독립 보호/종료/새 Epoch |
| Front command-loss / Front restart-live | **각1/1, 총2/2 PASS** | 새3-process 경로에서 기존 대표 경계 회귀 |
| ASan+UBSan normal / Rear restart-live | **2/2 PASS** | 실제 SDK·프로젝트 경로, 오류0 |
| TSan normal / Rear restart-live | **0/1 FAIL / 1/1 PASS** | 경합 경고0. normal32 batches 뒤 원래 만료로 보호,2540ms와 정상 종료 구간 미완료 |
| 최종 전체 C++ Normal / ASan+UBSan | **각987/987 PASS** | 기존983개 이름/assertion 유지 + 필요한4개 추가. 각1회 |
| Python runner/oracle | **24/24 PASS** | 실제 SDK 시험과 별개. build/ 없는 tracked dependency export에서도24/24 |

최종 runtime은 **13 PASS/1 FAIL =14회**다. 개발/철회 후보까지 전체는
**34 PASS/7 FAIL =41회**이며 원래 exit를 유지한다. 이전 후보는 final cohort에서 제외했다.
Normal10/10의 기능 수용과 sanitizer wall-time 결과를 합쳐 전체 PASS로 표시하지 않는다.
일부 주입은 의도된 SIGKILL이며 orderly stop에 포함하지 않는다. 살아 있는 프로세스의
stop/join은 반환했고, 최종14회에 supervisor timeout/forced cleanup/예상 밖 SDK 오류/
sanitizer warning은 없다. 추가48회·극단/복합 부하·SDK 조합 탐색은 NOT RUN이다.

| 실제 Leaf | Normal 무부하/부하4회 최소 갱신 여유 | Normal 재가입2회 새 Epoch 최소 여유 |
| --- | ---: | ---: |
| Steering | 7.766637ms | 6.378692ms |
| Brake | 7.764243ms | 6.376290ms |
| Drive | 7.163085ms | 5.576097ms |

여유는 **이전 명령의 원래 expiry − 다음 명령 실제 Leaf 수용 시각**이다. 세 Leaf의
Epoch/source로 명령을 찾고 token·원래 sent/expiry·Zone 수신·Leaf enqueue/수용·accepted
result를 연결한다. Rear 송신보다 Front accepted result가 먼저인지도 검사한다.
현재/이전 Epoch 사이를 하나의 갱신 간격으로 이어 붙이지 않는다. 전체 Normal의 가장 작은
양수 여유는 **5.576097ms**이며, 미래의 최악 지연 보장을 주장하지 않는다.

Rear feedback은 기존 Central validator로 들어간다. 정상4회 permission 최솟값 관측은
SteeringActual596회, DriveActual153회, acknowledged PowerRequest34회였다. BMS/Power
교환과 Drive Actual도 실제 허가 생성의 제한 입력이며 로컬 함수 호출로 우회하지 않는다.

Rear 재가입에서 Central PID2338586과 Front PID2338587은 유지됐다. Front 재가입에서는
Central2338761/Rear2338763이 유지됐다. 기존 global 보호→durable Epoch2→각8 Release
ACK→credit/arm→실제 세 Leaf 갱신→NormalStop이 이어졌고 old-Epoch packet1개를 거부했다.
Front의 정상 출력을 Rear 재가입 동안 유지했다고 주장하지 않는다.

Owner 정지 중에는 해당 actor가 ACK하지 않으며 살아 있는 독립 native monitor/plant가
보호한다. ECU 프로세스 kill은 그 ECU monitor도 사라지므로 persistent plant 및 나머지
ECU가 보호 주체다. Central kill에서 살아 있는 Front/Rear 양쪽의 실제 선택과 물리 torque/
brake 보호를 확인했다. 각 고장 원본은 `final3-normal-{rear,front}/CASE-1/`에 있다.

SDK warning은 지우지 않았다. [전체 최종 warning 위치/시각](sdk-warnings.csv)은940줄이다.
92줄은 interface/route up,807줄은 실제 주입/보호/종료 경계 뒤의 socket/reset/cancel 등,
40줄은 SD multicast timer/재가입 관련이다. 나머지1줄은 ASan 재가입 사례의 최초 readiness
전 SD queue112 **bytes** 관측이며, SDK queue_train은 buffer size를 더한 뒤 이미 전송 중이면
warning을 출력한다. Queue-limit drop의 ERROR 분기와 다르다. 원본 위치는 pinned SDK의
`implementation/endpoints/src/server_endpoint_impl.cpp:441`이다.
550ms SD 경고는500ms cyclic offer의110% 수신 timer에서 multicast leave/join을 수행하는
`implementation/service_discovery/src/service_discovery_impl.cpp:3006` 경로다. 실제 두 TCP
application 경로/처리 완료를 별도 검증했으며 이 경고를 장시간 discovery 보장으로 해석하지
않는다. 이번 최종 사례에 `Maximum wait time for send operation exceeded`는0건이다.
경고를 포괄적으로 숨기거나 sanitizer 진단을 이 분류에 넣지 않았다.

## 남은 TSan wall-time 실패와 수용 경계

`final3-tsan/normal-1`은 실제 FAIL이다. permission110은 SteeringActual의 원래
source604057810199233ns +30,000,001ns = **604057840199234ns**로 제한됐다.
release604057825520988ns +18ms 지원에 **3,321,754ns 부족**해 reason3으로 보류됐다.
다음 management에서는 reason4(usable matching received grant 없음)였고 이전 명령은
연장되지 않았다. 최초 Central Allocation 보호604057840219337ns 뒤 세 Leaf도 원래
expiry를 감지했다. RX overflow 시각/거부는0이지만 이후 TX/probe overflow latch도 남았다;
이를 최초 원인으로 바꾸지 않으며 정확한 TX lane은 이 summary로 특정할 수 없다.
모델은 torque0/보호 brake로 진행했고 native4ms miss나 sanitizer 경고는 없었다.

**OPEN-SOMEIP-REAR-01**: 계측 조건의 정상 관측 구간 미완료/허가 지원 부족 및 후속 TX
포화. 이 raw FAIL을 PASS로 고치거나 경고 suppression·시한/큐 증설로 통과시키지 않았다.
고정된 Normal FIFO cohort의 통과 범위는 수용하되, TSan full-window 정상 운전 검증 완료를
주장하지 않는다. 이전 TSan normal PASS도 최종 source PASS로 옮겨 세지 않는다.

재가입의 이전 Central guard 상세 CSV는 기존 writer의 최종-generation alias가 덮어쓰는
제약이 있다. `after-*-crash-*.watch.bin/json`, 기존 events와 새 generation CSV는 보존됐다.
원래 pre-injection 정상 조건·latch/snapshot으로 구분하며 이전 generation의 전체 상세 CSV가
보존됐다고 주장하지 않는다. 이 관측 제약도 무기한 실행/SDK 전체 안전성 주장과 별개다.

M4 Host IO/FIFO component 한정 수용/전체 NOT CLOSED, DDS gate CLOSED·기존 FAIL/OPEN,
과거 모델61ms 사건은 그대로다. Jetson, 실제 NIC/CAN 장치, 전체 차량/Target clock sync,
M6 모델·전체 시스템 및 장시간 profile은 미검증이다. 다음 후보는 이3-ECU 경계를 바탕으로
M6 물리·센서/시나리오 교체 범위를 설계하는 것이며 여기서 구현을 시작하지 않았다.
TSan 시간축/송신 정산과 guard CSV 세대 보존은 별도 후속 진단 항목이다.

## 빌드·계측·재현

COVESA vSomeIP **3.7.6 / 4187431d2815bd351845a09d01aa85b2a3163cab**, SDK tree clean,
Boost1.85, GCC11.4. 기존 분리 build/install을 사용했고 기본 의존성·SDK 내부는 변경하지 않았다.
`instrumentation.json`, `final-binaries.json`, `*-project-commands.txt`, `*-ldd.txt`, 각 process
maps에 실제 식별자·명령·계측/link를 보존했다. 프로젝트와 SDK core/cfg/sd/e2e 및 Boost
filesystem/atomic의 sanitizer symbol을 확인했다. 시스템 libc/libstdc++는 비계측이며 mmap
SIL IPC 전체나 미실행 SDK 경로의 race-free를 보증하지 않는다. TSan은 기존
`setarch x86_64 -R` process-local fixed-layout 조건이다. suppression/annotation은 추가하지 않았다.

재현은 새 output 경로를 사용한다. 모든 runner/build는 `build/.m4-exclusive.lock`을 사용한다.
새 checkout에서 pinned dependency는 기존 `build.py normal|asan|tsan`으로 준비한다.

```bash
python3 tests/integration/someip/build.py normal
python3 tests/integration/someip/front_run.py build/rear-quiet --three --fault-zone rear --native-watch --fifo --profile normal --cases normal --normal-repeats 2
python3 tests/integration/someip/front_run.py build/rear-load --three --fault-zone rear --native-watch --fifo --loaded --profile normal --cases normal --normal-repeats 2
python3 tests/integration/someip/front_run.py build/rear-faults --three --fault-zone rear --native-watch --fifo --timing --profile normal --cases command-loss owner-pause central-stop restart-live
python3 tests/integration/someip/front_run.py build/front-regression --three --fault-zone front --native-watch --fifo --timing --profile normal --cases command-loss restart-live
python3 tests/integration/someip/front_run.py build/rear-asan --three --fault-zone rear --native-watch --fifo --profile asan --cases normal restart-live
python3 tests/integration/someip/front_run.py build/rear-tsan --three --fault-zone rear --native-watch --fifo --profile tsan --fixed-layout --cases normal restart-live
python3 tests/unit/someip_pilot_test.py
```

실제 argv·횟수·source/binary hash·부하/정책은 각 `plan.json` 및 `*.command.json`을 우선한다.
실패/timeout/결과 누락/SDK 오류/sanitizer 진단은 원본 저장 후 runner exit1이며,
강제 cleanup을 정상 stop으로 세지 않는다. 전체 회귀의 정확한 명령/종료 코드는
`full-regression-results.json`, 원본 XML/text에 있다. 초기 gtest 컴파일 경고와 그 직후
stale-binary9/9는 최종 검증에서 제외했고, build 없는 export는 전체 checkout/실제 SDK 실행으로
오인하지 않도록 `fresh-python.json`에 그 범위를 명시했다.
