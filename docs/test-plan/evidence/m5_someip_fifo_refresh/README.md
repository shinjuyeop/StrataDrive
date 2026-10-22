# Host FIFO allocation / startup follow-up

2026-10-22. **Host functional SIL 조건부 채택 유지. FIFO 통합 수용 확대 및 Rear 연결 진행은 보류.**
최종 지정 FIFO8/8은 통과했지만, 이번 목표였던 과거 정상 command 갱신 중단의
69,603ns short-support 경로는 아직 수정하지 못했다. 수신 허가의 실제 유효성 검사와
영속 Epoch 발급/감시 시작 순서는 수정했다. 후속 PASS로 과거 FAIL을 닫지 않는다.

시작 HEAD와 fetch한 origin/main은 모두 `e977366d2ecde16bfc3a825f1eea6ffd3a29f6c6`,
작업 트리는 깨끗했고 이후 변경은 없었다. 구현은 `45a3352`(허가 검사/관측/회귀),
`7fe4bbd`(Epoch 저장소와 native 시작 순서)로 분리했다. 최종 SDK 실행 소스는 `7fe4bbd`다.
[사전 protocol](protocol.md), [기계 판독 집계](results-summary.json), [전체 실행표](results.csv),
[시간축](timeline.csv), [raw 파일 해시](raw-manifest.json)를 함께 사용한다.

## 승인된 수용 범위

사용자가 이번 요청에서 승인한 조정을 적용하며 추가 승인은 요청하지 않았다.
실제8참여자 세션·Release ACK·RunLease·arm·독립 보호·새 Epoch를 사용하는 Host
Central↔Front functional SIL만 대상이다. Normal FIFO 정상 무부하2/부하2와
command-loss/owner-pause/central-stop/restart-live 각1이 필수다. OTHER 부하 timing은
지원 한계 진단이며 이 한정 FIFO 진행의 차단 조건에서 제외한다. 실제 sanitizer
메모리·UB·경합 오류는 FAIL, sanitizer wall time은 Normal 운용 성능과 별도다.
미실행 기능을 검증 완료로 표시하지 않는다. M4 전체 종료·Rear 네트워크·Jetson·실제 IO·
전체 시스템 수용은 별도다. DDS 실패/OPEN·제어 gate CLOSED는 그대로다.

## 확인한 원인과 수정

### 1. 과거 갱신 중단: 분기는 확인, 해결은 OPEN

이전 `someip-native-qualified-normal/overflow-1`은 주입 전 정상 운전 실패다.
원본은 이전 native-watch archive에 그대로 있으며 새 폴더의 역사적 발췌/해시도 보존했다.

| 사건 | monotonic ns | 의미 |
|---|---:|---|
| 마지막 Commands 원래 source |532747835633794|새로 찍지 않음|
| Front 요청 token143 원래 sent |532747835634299|20ms envelope 시작|
| Front 결과 수용 |532747836410479|sent 이후776,180ns; 다음 배분의 in-flight 원인 아님|
| 다음 예정 allocation |532747851408166|실제 session enable과20ms grid로 복원|
| 다음 vehicle root 게시 |532747851414256|token146; 새 Commands는 생성되지 않음|
| 최신 permission 원래 source |532747855410737|management power/permission 공통 source|
| 그 permission의 원래 expiry |532747871338563|원본 전송 deadline과 더 긴 power expiry로 좁힌 값|
| 이전 명령 inner expiry |532747858840282|원래 source 이후23.206488ms|
| Steering expiry 검출 |532747859008926|정상 명령 미갱신 후 발생|
| Central fault / Front 보호 선택 |532747859012394 /532747859014544|후속 보호|

`release+20ms=532747871408166`이므로 실제 expiry가 **69,603ns 부족**하다.
직전 management 출력의 source는 release보다 이르고, 다음 출력은 위 expiry 검사에서
보류된다. 다음 management 예정 시각은 이전 명령 expiry 뒤다. 정확한 release/source/
expiry를 실제 AsyncCoordinatorPort·CAN codec/receiver에 넣은 최소 회귀가 **reason3
(short support)**를 확인한다. 나머지 receiver 문맥은 명시적인 단위 fixture이며,
역사적 전체 입력/스케줄/SDK 실행을 재현했다고 주장하지 않는다. 원본의 빠진 branch
기록을 사후 생성한 것이 아니라 저장된 값과 같은 코드 분기를 대조한 근거다.

이 보류를 단순 삭제하지 않았다. 앞서 받은 grant도 허용하는 후보는 전체 Normal과
ASan에서 각각45개 기존 assertion을 깨뜨렸다. 논리 trace에서 command expiry
1821000001, 다음 allocation1821000000, Front 다음 root 수신1821200000이었다.
**다음 nominal release보다1ns 긴 허가는 실제 원격 인계까지 지원하지 않는다.**
이 후보는 철회했다. 시한·source를 연장하거나 expired command를 사용하지 않았다.
어떤 입력 의존성이 과거 grant expiry의 최솟값을 만들었는지와, 이를 원래10/20ms
주기에서 충분히 일찍 갱신하는 management/입력 phase 수정은 아직 남았다.
기존 OTHER/FIFO monitor 사례에서 Leaf expiry가 최초 보호보다 늦었던 사건도 별도 OPEN이다.

### 2. 실제 만료된 허가를 ready로 반환하던 검사 수정

BmsReceiver는 만료 때 identity를 보존하면서 내용을 canonical unavailable/품질 Stale로
반환할 수 있다. 기존 allocation_ready는 identity만 비교해 이미 만료된 delayed release를
ready로 반환했다. baseline 구현에서 새 시험이 `true != false`로 실패했고 최종 구현에서
통과했다. **현재 시각의 expiry와 bms_permission_allows_normal**을 함께 검사한다.
원래 source≥release, 다음20ms support, 정확한 수신 identity, in-flight settlement는 유지한다.
후단 ControlAllocation도 기존 보호를 유지하므로 이 수정은 잘못된 준비 판정을 막는 것이며,
위 과거 정상 갱신 실패를 해결했다는 뜻은 아니다.

### 3. 영속 Epoch 발급을 native 감시 전에 완료

첫 고정 FIFO cohort의 owner-pause는 주입 전 Epoch0에서 실패했다. Central watch origin
598302757517476, 최초4ms deadline598302861517476, 검출598302861528057,
Epoch-issued598302941716927이었다. watch 시작과 owner loop 사이의 영속 EpochStore.issue
경로는 file/directory fsync를 수행한다. 약184.2ms의 시작 구간이100ms lead를 넘었다.
기존 기록으로 fsync와 ready-marker IO 각각의 지연을 분리하지는 못한다.

첫 세션과 보호 후 재가입 모두 **기존 durable issue를 마친 다음 새 세대 watch를 생성**한다.
정상 owner가 시작된 뒤의 실행 기회/4ms deadline은 바꾸지 않았다. 새 ACK/권한을 만들거나
store 검증을 우회하지 않는다. 최종 관측에서 store 호출43.650–52.029ms였고, 보존된
12개 Central 세대 기록 모두 return≤guard origin이었다. Central-stop의 강제 종료된
Central은 bounded event buffer를 flush하지 못하므로 이 비교 기록이 없다. 재가입 최초
세대 guard는 final summary alias 대신 보존된 after-front-crash channel에서 확인했다.

### 관측과 trace 호환성

`permission-issued`와 `allocation-readiness`는 bounded 기존 sink에 저장하며 owner 안에서
파일 쓰기/flush를 하지 않는다. 후자는 예정 release(sent), 허가 원래 source/expiry,
이전 command source(payload_source)/expiry(deadline), 보류 reason을 연결한다.
비transaction 행은 **token0/operation-1**, peer는 permission sequence다. reason2는
source가 release..now 밖,3은 support 부족/실제 만료,4는 usable matching RX 부재다.
생성된 명령은 기존 central-enqueued/result 행으로 연결한다. 기존 allocation-deferred와
원래 assertion을 유지한다. 초기 관측 구현의 token 충돌/기존 행 누락으로 발생한4개
회귀 실패도 보존했고 수정했다. `gateway-protection`은 gateway 원인 관측,
`leaf-first-fault`는 첫 로컬 보호를 관측했을 때의 Leaf fault snapshot이며,
그 Leaf 코드가 최초 원인이라는 뜻은 아니다.

## 실제 시험 결과

| 구분 | 결과 | 판정 범위 |
|---|---:|---|
| 관측만 추가한 pre-fix SDK Normal FIFO normal |1/1|진단; 과거 expiry 미재현|
| 조기 grant 후보 전체 Normal / ASan |935/980 각각|철회 후보;45 FAIL 각각 보존|
| phase 복원 후 trace 호환성 전체 Normal / ASan |976/980 각각|관측 결함4 FAIL 각각 보존|
| 최종 공통 코드 관련 논리 회귀 |30/30|기존 pending/trace assertion 포함|
| 최종 공통 코드 전체 Normal |979/980|기존 OTHER wall physical-pause 정상 진입 전 실패;재시도 없음|
| 최종 공통 코드 전체 ASan/UBSan |980/980|메모리/UB 보고 없음|
|45a3352 첫 지정 Normal FIFO |6/8|command-loss arm 거부,owner-pause 시작 전 감시 실패|
|45a3352 ASan / TSan SDK |2/2 각각|normal+command-loss; 별도 분모|
|**7fe4bbd 최종 Normal FIFO** |**8/8**|무부하2,부하2,핵심4 모두 통과|
|**7fe4bbd 최종 ASan / TSan SDK** |**2/2 각각**|normal+command-loss;메모리/UB/경합 보고 없음|

전체 새 SDK 요청은 **25회23 PASS/2 FAIL**이다. 최종 source12/12와 혼합하지 않는다.
최종4 정상 실행의 Front Commands 결과347개는 원래 sent→Central 수용0.368–2.370ms였다.
전체 원래 guard/정상 관측 구간을 완료했고 불필요한 보호·native miss가 없었다.
owner-pause의 의도된 miss는 정상 timing PASS가 아니라 보호 oracle PASS다.
주입 후 최초 deadline598571437188625→검출598571437190930(2,305ns 뒤); 멈춘 owner의
후속 복귀/Leaf ACK와 살아 있는 독립 감시/물리 보호는 구분된다. central-stop은 실제
Central crash 뒤 Front 보호, restart-live는 살아 있는 Central의 Epoch2/실제8ACK/arm/
이전 Epoch 거부를 확인했다. 강제 crash 자체를 orderly stop으로 세지 않는다.
모든 살아 있는 종료 경로는 실제 SDK stop/join 반환과 raw exit로 판정했다.

최초 command-loss의 양 Leaf arm 거부는 명령 발급 전이며 native miss0이었다.
Front IO busy3607/4357이라는 관측은 있으나 starvation/센서 원인으로 확정하지 않는다.
최종 통과만으로 이 실패의 원인을 해결했다고 표시하지 않는다. 이 사례의 command-loss
기능은 미실행이었고, 최종 동일 이름 시험에서 별도로 실행됐다.

공통 코드45a3352 이후7fe4bbd는 adapter 시작 순서/관측만 바꿨다. 따라서 공통 전체 회귀를
관성적으로 네 번째 실행하지 않았다. 기존48/native40, 새로운 OTHER 부하, 모든 SDK 조합,
추가 queue/close 경계, 과거61ms 모델 사건은 NOT RUN이다. 기존 assertion/분모·DDS42/23/19,
과거 TSan12/13+3/3·native48=31/48 등 이전 원본은 변경하지 않았다.

## 적용 환경과 계측

기존 Linux Host i7-11700 8물리/16SMT, 허용CPU0..15, 원래 uid1000 RT limit20/20이다.
CPU1 Central FIFO11,CPU2 Front FIFO18,CPU3 물리 FIFO19,CPU0 monitor FIFO20;
SDK/sender는CPU4/5 OTHER0,물리 auxCPU6 OTHER0. 실제 TID/정책/priority/affinity는 각
runtime/native JSON에 있다. 부하는 기존CPU1/2 OTHER7ms busy/10ms이고 원래2540ms
관측·2ms 기회·4ms 감시·20ms allocation/envelope·원래 inner expiry를 유지했다.
두 netns/veth10.88.0.1↔10.88.0.2, TCP30501–30504/SD30490 pcap·socket·maps를 보존했다.
local Rear/Leaf와 SIL 물리/센서 IO fixture, fixed trusted demand 범위는 그대로다.

vSomeIP3.7.6 commit4187431d2815bd351845a09d01aa85b2a3163cab,Boost1.85.0,GCC11.4,
실제 compile/link 명령·바이너리 SHA·ldd·SDK/Boost 계측 심볼을 raw에 보존했다.
프로젝트와 vSomeIP core/cfg/sd/e2e 및 Boost filesystem/atomic의 각 sanitizer 계측을 확인했다.
시스템 libc/libstdc++는 비계측이며 TSan은 기존 setarch -R fixed-layout이다.
진단 경고 없음은 이 실행 경계의 결과이지 SDK 전체 안전성 증명이 아니다. ASan/TSan
성능을 Normal 성능으로 사용하지 않는다. 모든 작업은 기존 exclusive lock을 사용했고
부하 측정 중 빌드·대규모 검색을 병행하지 않았다. sudo/권한/OS/SDK 설정 변경,
경고 suppression,외부 문의/게시,Daybreak 재시도는 없었다.

## 판정과 다음 한 단계

필수 FIFO 기능 시험은 최종8/8이나, **관측된 정상 갱신 중단 자체의 수정 전 FAIL→수정 후
PASS는 확보하지 못했다.** 따라서 아직 Host FIFO 한정 수용/Rear 진행 가능으로 선언하지 않는다.
차단은 애플리케이션의 원래 grant support와 배분/원격 인계 시점 관계이며, OTHER 부하나
sanitizer wall time을 새 차단으로 추가하지 않는다. SDK 교체/4ms 확대/큐 증설의 근거는 없다.

다음 한 단계는 저장된 short-support 입력에서 permission_expiry의 제한 입력을 특정하고,
management/Actual 관측 순서를 원래10/20ms 안에서 재배치하는 최소 replay다. 성공 조건은
원래 expiry 전 새 명령이 실제 수신되며 이전 명령/권한을 연장하지 않는 것이다. 이것이
불가능한 phase임이 확인되면 필요한 발행/관측 phase 또는 갱신 주기 변경을 **별도 Host
profile 변경**으로 제시해야 한다. 이번에 그런 profile 변경을 적용하거나 Rear를 구현하지 않았다.

## 재현

```sh
# pinned SDK가 없는 checkout에서도 build.py가 build/와 lock을 준비한다.
python3 tests/integration/someip/build.py normal
python3 tests/integration/someip/build.py asan
python3 tests/integration/someip/build.py tsan
python3 tests/integration/someip/front_run.py build/new-fifo-quiet --profile normal --native-watch --fifo --cases normal --normal-repeats 2
python3 tests/integration/someip/front_run.py build/new-fifo-loaded --profile normal --native-watch --fifo --loaded --cases normal --normal-repeats 2
python3 tests/integration/someip/front_run.py build/new-fifo-faults --profile normal --native-watch --fifo --timing --cases command-loss owner-pause central-stop restart-live
python3 tests/integration/someip/front_run.py build/new-asan-boundary --profile asan --native-watch --fifo --cases normal command-loss
python3 tests/integration/someip/front_run.py build/new-tsan-boundary --profile tsan --fixed-layout --native-watch --fifo --cases normal command-loss
# 실행 없이 보존된 원본 재집계
python3 docs/test-plan/evidence/m5_someip_fifo_refresh/analyze.py build/someip-fifo-refresh /tmp/fifo-offline
```

새 재실행 승인이 아니라 재현 recipe다. 정확한 전체 CTest/빌드/실행 argv와 원본 exit,
실패 로그·CSV·pcap은 raw archive에 있다. archive를 임의 새 디렉터리에 풀면
`someip-fifo-refresh` 하위 경로를 analyzer의 첫 인수로 준다. raw 결과를 수정하지 않는다.
