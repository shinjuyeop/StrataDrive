# M6 SIL 물리 보호 응답 시한

2026-10-22. **검증된 Host quiet 차량·EV 에너지·물리 보호 기능 한정 수용**.
`OPEN-M6-ENERGY-01`의 모델/판정 시한 불일치를 해소했다. M6 전체 종료가 아니다.
시작/fetch 후 HEAD·origin/main729455f, clean, 사용자 변경/AGENTS.md 없음을 확인했다.
구현5f1ef49, 서비스 시각 해석 수정02d78ec, 최종 offline 판정a32de13이다.

[사전 protocol/추가 실행 이유](protocol.md), [실행 설정 JSON](../../../../profiles/m6_sil_response_v1.json),
[전체 결과](results-summary.json), [실제 SDK3회](results.csv), [시간축](timeline.csv),
[최종 물리 판정](response-result.json), [곡선](physical-response.svg),
[옛 로그 별도 재분석](old-reanalysis.json), [새 raw offline 재평가](offline-reanalysis.json),
[환경](environment.json), [계측/링크](instrumentation.json), [실제 SDK Ninja 빌드](sdk-build.json),
[SDK 경고 원문 위치](sdk-warnings.csv), [경고 시간대 대조](warning-analysis.json).
원본·재현 driver·XML·plan/명령/설정·IP/스레드·PCAP은 [archive](raw-evidence.tar.gz),
[파일 manifest](raw-manifest.json), [archive 식별자](archives.json)에 있다.
아래 raw 경로는 `build/m6-physical-response/` 아래이며 archive에도 같은 하위 경로로 보존한다.

## 시한과 산정

| 구간 | M6 SIL 판정 | 의미 |
| --- | --- | --- |
| 마지막 유효 command 수신→검출 | <=100ms 유지 | 원래 command-expired/source/expiry 및 matching valid-input을 연결 |
| 로컬 검출 회차→보호 선택 ACK | <=4ms | 기존 synchronous local protection/2ms 기회·4ms 감시에서 별도 검사. post-service 관측 시각을 검출 순간으로 사용하지 않음 |
| 최초 로컬 목표 선택→양쪽 물리 출력 인계 | <=4ms | 양 Zone 선택 시차도 포함. 양쪽 실제 applied-source와 step 전후 구간으로 확인 |
| 최초 로컬 목표 선택→실제 토크·압력 완료 관측 | <=230ms | abs(T)<=1Nm **AND 실제 압력>=1MPa**; 목표/ACK만으로 완료 아님 |
| 주입→전체 응답 | 실제 시간축 보고 | 주입과 마지막 RX는 다름. 보수적인 RX 기점 연쇄 예산100+4+230=334ms는 해당 profile 한정 |

실행 모델: Drive −200..+300Nm, 보호 감소율2000Nm/s, 허용오차1Nm.
양수 `(300−1)/2000=149.5ms`, 음수 `(200−1)/2000=99.5ms`.
정상 rate1000Nm/s/지연50ms는 그대로며 보호는 pending normal delay를 취소한다.
Brake max1.5MPa, 초기0.2MPa, 정상 해제로0까지 가능, 보호 floor1MPa,
rise5MPa/s/fall10MPa/s. 최저0→floor는200ms, 초기0.2MPa→floor는160ms다.
높은 압력은 보호가 낮추지 않으며 보호 자체 지연은0이다.

구동/제동은 병렬이므로 `max(149.5,200)=200ms`다.
**200 + 양쪽 출력 전달4 + 모델 실행4 + 기존 CSV 관측10 + 명시 여유12 =230ms**.
양쪽 출력 적용이 최초 선택+4ms를 넘으면 별도 FAIL하므로 Zone 선택 시차를 숨기지 않는다.
4ms model gap 초과/누락/미완료도 FAIL이다. 설정은 이번 SIL·Host quiet 범위의 시험 계약이며
차량/OEM/Jetson의 물리 보장이 아니다. 정상 입력/토크 감소율/명령·허가의 원래 시한을 바꾸지 않았다.

`reference.yaml`은 기록이며 loader가 아니다. runner는 명시적 M6 energy normal/command-loss에만
위 JSON을 읽어 plan/result/`physical-response-contract.json`에 저장하고 marker용 threshold를
물리 fixture에 전달한다. oracle는 같은 JSON과 compiled `response-model.json`을 대조한다.
기존 M5와 다른 fault profile의100ms 판정은 일괄 변경하지 않았다.

## 수정 범위와 관측

제어/모델 수식·rate·기존 deadline/queue/SDK는 변경하지 않았다. 공통 PhysicalOwner header에는
owner-thread 전용 readonly snapshot과 기존 brake initializer의 단일 getter만 추가했다.
2ms opportunity/4ms guard, host10-v1,20ms envelope, 실제8참여자/Release ACK/RunLease/arm,
CAN/P05·원래 source/expiry와 독립 보호를 유지했다.

테스트 plant가 주입 후 최대1024개 사전 할당 기록을 약500us model step마다 수집하고 종료 후 쓴다.
기존10ms CSV와 분리한 `physical-response.csv`는 실제 torque/pressure·Epoch, 원래 output source,
Actuation.issued_time, PhysicalOwner가 실제 소비한 source, step 전후 시각을 보존한다.
첫 완료 **모델 샘플**도 연속 물리 crossing의 정확한 시각이 아니다. 직전 미완료~최초 완료로
구간을 제시하고 실제 API 적용도 성공한 step 전후 구간으로 기록한다. 첫 완료 marker는 한 번만 쓴다.

처음 실제 command-loss는 새 oracle의 잘못된 시각 의미 때문에 FAIL했다.
`pre_shutdown_protection`은 동기 보호 처리 **후** 관측인데 Actuation 선택보다2.7/3.5us 늦었다.
이 값을 검출 순간으로 간주한 비교를 수정했다. owner step 진입~최초 fault 관측 event로 검출을
bracket하고, 실제 Drive command-expired와 matching 마지막 유효 RX도 별도 확인한다.
기준을 완화하거나 FAIL 원본을 PASS로 바꾸지 않았다. 변경된 fault 경로만1회 추가 실행했다.

## 실제 시간축

| 항목 | 과거 d242861 (raw FAIL) | 새02d78ec command-loss |
| --- | ---: | ---: |
| 마지막 유효 RX→Drive expiry 검출 |24.196565ms|24.195330ms|
| 주입→Drive expiry 검출 |18.330246ms|18.728234ms|
| 주입→Rear 선택 ACK |18.336023ms|18.731325ms|
| 검출→Drive output zero 선택 |정밀 output 기록 없음|0.001329ms|
| 로컬 검출 회차 진입→선택 ACK |정밀 구간 없음|Drive0.005639ms / Brake0.006041ms|
| 주입→양쪽 물리 적용 구간 |미관측|19.106227..19.109442ms|
| 주입→abs(T)<=1 모델 crossing 구간 |10ms 샘플만 존재|113.102424..113.619305ms|
| 주입→실제 압력1MPa crossing 구간 |원본 종료 전 미완료|219.105731..219.603944ms|
| 주입→토크·1MPa 동시 최초 모델 완료 |미관측|219.603944ms|
| 최초 선택→동시 최초 모델 완료 |미관측|200.924944ms (<230)|
| 주입→새 조건의 첫10ms CSV 완료 |미관측|220.129856ms|
| 주입→옛 조건(토크·100kPa) 첫10ms 관측 |122.706671ms (>100,FAIL)|새 완료 조건과 구분|

새 실제 보호 적용 때 토크189.501986Nm/압력0Pa였다. 낮은 토크에서 주입하도록 바꾸지 않았다.
범위 전체의+300/−200Nm와 brake0Pa는 실제 모델 결정론적 계약으로 따로 확인했다.
과거 로그는 토크·100kPa의122.707ms를 보여주지만1MPa 전에 끝났다. 새 기준 소급 PASS가
아니라 **INCOMPLETE**이며 이전 raw exit1/원본·분모는 그대로다.

## 시험과 분모

| 실제 실행 | 결과 | 구분 |
| --- | --- | --- |
| 동일 최대 토크/최저 압력 모델의 old100ms replay |0/1, expected FAIL|원본 `replay-old100.txt`; 과거 사건 동일 재현 주장은 아님|
| 같은 모델 new230ms replay |1/1 PASS|원래 rate/target 그대로|
| 최초 SDK Normal FIFO command-loss |0/1 FAIL|물리 완료200.395ms이나 새 관측기 시각 해석 오류. raw exit1 유지|
| SDK Normal FIFO nominal energy cycle |1/1 PASS|8s 관측+기존 정상 stop/HV-off/SDK stop/join|
| 시각 해석 수정 후 SDK Normal FIFO command-loss |1/1 PASS|원래 expiry/물리 토크·1MPa/정리 모두 PASS|
| 전체 C++ Normal / ASan+UBSan |각1018/1018 PASS, 각1회|기존1011 이름 보존 + 새 모델 계약7; 메모리/UB 진단0|
| 변경 경계 TSan |35/35 PASS,1회|새 모델7 + 기존 vehicle/fixture11 + async owner17; race 진단0|
| 최종 Python / build 없는 전체 git archive |각54/54 PASS|응답12+energy10+model8+pilot24; 실제 SDK 시험 아님|

이번 실제 SDK 전체 **2 PASS /1 FAIL /3회**. 수정 후 변경 사례1/1과 영향 없는 nominal1/1이
필수 Normal 근거다. nominal은5f1ef49, 수정 command-loss는02d78ec에서 실행했다.
두 C++ 차이는 fault가 처음 관측될 때의 bounded event1개이며 정상/물리/제어 알고리즘은 동일하다.
최종a32de13은 offline handoff 검사를 추가한 Python/시험/protocol 변경만이다.
보존된 raw의 최종 oracle 재평가도 별도 결과이며 첫 FAIL의 raw 판정은 변경하지 않았다.

정상 cycle: 실제8ACK/arm,세 Leaf 각726/726 수신, 최소 이전-expiry 여유
Steering12.902174/Brake12.899646/Drive12.273536ms. 최대 속도1.691127m/s,
received DC194.015030J/friction776.297495J/road379.521583J, final kinetic0,
max independent combined residual1.630e-8J. 정상 보호/누락/4ms miss0.
세 실제 실행 모두 예상 밖 SDK error/메모리·UB·race 진단/강제 cleanup0, native miss0.
SDK warning171줄은 원문을 보존했다: network-up18,SD550ms9,multicast handler lifecycle7,
SDK stop 이후 socket/SD 정리137. 마지막 항목은 최초 stop_begin 뒤>=0.162ms에 나온다
(벽시계/monotonic 대조의 근사값). SD handler 알림 일부는 운전 중 발생했으나 TCP 명령·결과·
Actual의 완료와 갱신을 직접 확인했다. SDK warning을 포괄 suppression하지 않았고,
`Maximum wait time...`/queue-drop/[error]는 이번3회에 없었다.

## 실행·계측 경계와 재현

Host8physical/16logical SMT. CentralCPU1/FIFO11,FrontCPU2/RearCPU7 FIFO18,
physicalCPU3/FIFO19,독립 monitorCPU0/FIFO20,SDK dispatch/IO/senderCPU4/5/6 OTHER0,
plant auxiliaryCPU14 OTHER0. 실제 per-thread policy/priority/affinity/netns는 raw `*.runtime.json`.
사용자 기존 RT20 권한 유지, OS/권한 변경 없음. netns/veth10.88.0.1/.2/.3/29의 실제 TCP,
PCAP/소켓/독립 routing resource와 persistent SIL 물리 bus를 그대로 사용했다.

vSomeIP3.7.6/4187431d2815bd351845a09d01aa85b2a3163cab,SDK worktree clean,
Boost1.85·SDK 라이브러리 SHA는 이전과 동일. 이번 SDK 실행은 **Normal 비계측**이다.
ASan/UBSan 전체와 TSan 경계는 연결된 프로젝트/모델 코드 계측이며 vSomeIP를 링크하지 않는다.
ASan/UBSan/TSan symbol·빌드 옵션·바이너리 SHA는 instrumentation.json에 있다.
기존 계측 SDK의 기능 미완료를 SDK TSan PASS로 바꾸지 않는다. system libc/libstdc++도 계측 밖이다.

```sh
cmake --build build/m5-someip-normal/project --target someip_front_adapter --parallel 4
python3 tests/integration/someip/front_run.py build/m6-response-reproduce \
  --three --fault-zone rear --native-watch --fifo --simple-vehicle \
  --energy-cycle nominal --profile normal --cases command-loss normal
python3 tests/unit/m6_physical_response_test.py
```

재현에는 기존 pinned SDK/project build와 Host userns/netns/실제 RT 권한이 필요하다.
빌드/시험은 각각 `flock build/.m4-exclusive.lock`로 독점하고 runner는 자체 lock을 잡는다.
최초 checkout은 build 디렉터리를 먼저 만들거나 기존 build script를 사용한다. Python lock 회귀는
build 없는 checkout에서 직접 동작함을 확인했다. 자세한 configure/전체/경계 명령은 raw
`final-regression.py`,`final-bookkeeping.py`와 checks의 argv에 보존했다.
wall 측정 중 build/검색/분석을 병행하지 않았다. timeout/누락/오류/강제 정리는 여전히 exit1이다.

## 수용 범위와 다음 단계

`OPEN-M6-ENERGY-01`은 **현재 모델의 유한 ramp와 시험 시한 불일치 및 실제 command-loss
물리 응답 증거** 범위에서 해소됐다. 옛100ms FAIL이 오류 없는 실행으로 바뀐 것은 아니다.
기존 M5 수용/DDS 역사적 OPEN/M4 전체 보류/Jetson 미검증을 유지한다.
`OPEN-M6-ENERGY-02`의 SDK sanitizer 시한·송수신/SDK 오류·미완료는 OPEN이며 이번에
그 SDK 전체 조건을 재실행하지 않았다. 경고0을 기능 PASS로 바꾸지 않았다.
charge-zero/owner-pause/rejoin은 해당 실행/제어/physics를 바꾸지 않아 이전 PASS를 보존,
이번 NOT RUN. 새로운 부하·복합고장/48회/Jetson/M7/M8도 NOT RUN이다.

로드맵 M6 산출물 대조:

| 종료 항목 | 확보한 근거 | 남은 범위 |
| --- | --- | --- |
| Simple Vehicle/EV actual·lifecycle·energy | 기존 M6 첫 구현/에너지 + 이번230ms 응답 | 명시한 flat/forward/no-slip/quiet profile 한정; 전체 EV scenario/calibration 수용 아님 |
| 실행 가능한 종방향 제어 모델/MIL | 기존 Python87logical s/3plateau·추종/제약 PASS, 도구·sample time/solver/parameter 고정 | 실제 C++ SDK demand는 scenario fixture; M8 C++ controller/동등성을 구현한 것은 아님 |
| 파라미터/TBD·요구사항별 종료 판정 | TBD-03의 현재 보호 출력 모델 범위 확정 | **M6 종료 검토표**에서 나머지 TBD-02/03/07/12/13/16의 모델 범위·제외·요구사항 coverage를 기존 근거와 대조/확정해야 함 |
| 계측 runtime 기능 | boundary sanitizer PASS | OPEN02 실제 SDK 기능 미완료를 별도로 유지; 새 기능 진행의 일괄 선행 조건으로 삼지 않음 |
| M7/M8 이후 | 미실행 | CARLA20Hz/source-age·single ego writer/Host–Target mapping, C++ control/equivalence는 후속 milestone |

다음 한 단계는 **M6 종료 검토표 작성과 요구사항/TBD별 잔여 coverage 확정**이다.
새 극단 시험이나 과거 OPEN 전체 해결을 자동 선행 조건으로 추가하지 않는다.

계측 준비 결함도 보존했다. 최초 `build/m4-contract-tsan-final`의 실제 옵션은 OFF였고
__tsan 심볼/링크가 없었다. 해당35/35·raw exit0은 일반 기능 결과로만 분류하고 **TSan
수용에서 제외**했다. 별도 `build/m6-response-tsan`에 ON/Debug/-fno-pie/-no-pie를 명시한
실제 계측35개 결과를 위 TSan 행의 근거로 사용한다. `setarch x86_64 -R` 조건을 유지하며
이 고정 주소 배치의 한계를 명시한다. 기존 계측 SDK 실패를 재실행한 것이 아니다.
