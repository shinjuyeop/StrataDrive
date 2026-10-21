# DDS Host 환경·운용 후보 후속 — 2026-10-21

시작 시 `git fetch origin`: HEAD=`origin/main`=`c10688d`, ahead/behind0/0,
작업 트리 clean. **M4 Host native IO/FIFO 한정 수용 / M4 NOT CLOSED / DDS control
gate CLOSED**를 유지한다. 이전 [42회23 PASS/19 FAIL](../m5_dds_qualification/README.md),
OTHER 부하·과거 FIFO/native 실패·Daybreak 중단 이력은 변경하지 않았다.
제품 코드·SDK 버전/알고리즘·2ms/4ms·20ms envelope·원래 expiry는 그대로다.

이번 수정은 선택형 middleware **진단 코드**의 관측, writer/reader 삭제 상태,
transport 준비 절차와 판정 도구다. 정규 Central↔Front adapter는 미착수다.
SDK 경고를 억제하거나 동기화/커널/sudoers/모델 접근 설정을 바꾸지 않았다.

## 설계 / 코드 / 실제 적용값

| 항목 | 설계 문서 | 실행 코드 | 이번 적용 확인 |
| --- | --- | --- | --- |
| 물리 배포 | Host PC + 선택한 Jetson **한 대**; Jetson 안 Central·Front/Rear·Leaf 분리 | M4는 Host owner thread/component, DDS는 두 process/netns echo | x86 Host의 Central/Zone 두 process만 실행. Rear·Leaf·CARLA·Jetson·full INIT 배포 없음 |
| 주기 | reference Central20ms, Zone10ms, Leaf10/20ms | M4 native owner 서비스 기회2ms, VM10ms·배분20ms grid, Monitor2ms/Physical1ms; DDS 기본 발행5ms·take8/poll200µs | A/B/C5ms, D20ms. `next=t+period`라 주기는 최소 간격이며 production absolute grid가 아님 |
| CPU/정책 | Target 배치·RT 정책 TBD | M4 선택형 CPU A/B·owner별 FIFO18/18/10/10/10/9/10/11/19/20; DDS 기본 taskset CPU1·OTHER | 기본 두 process의 main/gc/dq.builtins/dq.user/tev/recv 모두 CPU1·OTHER0·nice0. C/D는 Central1, Zone2; TSan 보조 thread도 적용 mask 확인 |
| QoS | 메시지 종류별 QoS/큐는 TBD-05/15 | 양 방향 VOLATILE/RELIABLE/KEEP_ALL, resources8/1/8, blocking0 | 양쪽 reader/writer public readback 일치. KEEP_ALL depth8은 읽혔지만 depth는 KEEP_ALL에서 용량 의미가 없음 |
| 시간/세션 | 원래 source/parent/expiry, 새 durable Epoch/full handshake | 공통 kernel CLOCK_MONOTONIC, 고정 진단 grant42/43·token·route/CRC 검사 | 모든 accepted ingress/result의 판정 시각 < 원래20ms deadline 및 inner30ms expiry. Echo는 실제 ACK/Actual·보호 결과가 아님 |

대조한 기준: [status](../../../project_status.md), [Host 수용](../../../m4_host_acceptance_review.md),
[M4 종료](../../../m4_exit_review.md), [배포](../../../architecture/deployment_architecture.md),
[DDS 의미 계약](../../../icd/ethernet_dds_icd.md), [owner-wire](../../../icd/owner_wire_v1.md),
[reference.yaml](../../../../profiles/reference.yaml), `dds_channel.c`와 lifecycle runner/probe.
**reference.yaml은 설계 데이터이며 loader가 없다.** 실제 설정은 C++ 상수/환경 변수,
runner의 taskset·CYCLONEDDS_URI다. 오래된 ICD의 “runtime planned”는 정규 배포를 뜻하고,
후속 optional codec/echo가 없다는 뜻으로 읽으면 안 된다. 문서에 이 경계를 보완했다.

Host는 Ubuntu22.04.5, Linux6.8.0-138-generic PREEMPT_DYNAMIC, i7-11700 물리8코어/
SMT16논리 CPU, 한 socket/NUMA node다. sibling은0/8,1/9,…7/15. allowed0–15,
사용자1000/capabilities0, RT limit20이다. CPU1/CPU2는 다른 물리 코어지만 sibling9/10,
IRQ·다른 작업을 격리하지 않았다. cpuset reservation이나 실시간 보장은 없다.
이번에는 FIFO나 관리자 권한이 필요하지 않았다. namespace root는 `unshare -Urnm`의
사용자 namespace 내부 권한이며 Host 관리자 변경이 아니다.

SDK는 CycloneDDS11.0.1/e54e991, 기존 세 libddsc SHA 그대로다. GCC/G++11.4.0,
CMake4.3.2. Probe는 C11/C++17, O1/g/frame-pointer/Wall/Wextra/Werror/pthread,
assert 활성화. Normal SDK Release, ASan+UBSan/TSan SDK Debug·공식 SANITIZER;
codec 정적 library는 기존 Debug별 빌드다. 따라서 sanitizer 간 지연 차이를 sanitizer
하나의 비용으로 분리할 수 없다. 전체 library 계측·loader maps·입력 SHA/캐시는 raw에 있다.
선택형 private inspector는 정확한 pin의 진단 object이며 최소 관측에서 호출하지 않는다.

Domain37, netns/veth `sdc=10.88.0.1/30`, `sdz=10.88.0.2/30`, loopback up,
UDP/unicast peer2개·multicast off·ParticipantIndex auto. Finest 적용 로그는 실제
선택 interface/주소·RTPS2.5·discovery lease10s·동기 recv delivery·NackDelay100ms,
PreEmptiveAckDelay10ms, WHC low1KiB/init30KiB/high500KiB/adaptive를 기록한다.
XML에서 바꾸지 않은 SDK default와 명시값을 구분했다. Security/ICEORYX/TCP는 이 SDK
build에서 OFF다. 현재 격리된 진단망 구성이며 인증된 운용망 검증이 아니다.
DDS discovery lease10s는 application20ms expiry/≤100ms loss 조건을 대체할 수 없다.

## 적절한 선택과 미완료 운용 결정

RELIABLE은 요청/결과의 재전송 관측에, KEEP_ALL은 유실/포화 노출에, VOLATILE은
늦게 합류한 peer에 오래된 명령을 자동 전달하지 않는 데 적절한 **후보**다.
큐8과 write blocking0은 제한된 mailbox와 호출자 대기 회피 의도를 나타낸다.
다만 max_blocking_time0은 write 전체 WCET=0이나 즉시 overflow 통지가 아니다.
SDK pin의 writer throttle은 WHC **bytes watermark**를 사용한다. readback resource8만으로
전송 전체 버퍼가8이라고 주장할 수 없다. 관측 WHC unacked16200bytes, overflow의
reader rejection25·writer 실패0이 이를 뒷받침한다. SDK/RHC 재시도 횟수인 rejected와
고유 유실 메시지 수를 동일시하지 않는다. 모든 수집된 reader lost는0이었다.

5ms는20ms 배분보다4배 발행하는 부하 시험으로 유효하다. 실제 Zone 실행을 재현하지
않는 echo200µs polling과 결합했으므로 운용 성능 증거는 아니다. CPU1 공용 또한
경합 노출용으로 유효하나 Jetson의 vECU 격리 배치를 대표하지 않는다. 모든 thread를
FIFO로 높이거나 queue를 늘리지 않았다. 후보 D는 별도 물리 코어·20ms·최소 관측으로
통신 준비 이후의 **Host request/result lane**을 시험할 출발점이다.

| 메시지 종류 | 보관/유실/재시도 요구와 남은 결정 |
| --- | --- |
| 정상 명령 | pending batch·원래 source/parent·Epoch/token/expiry 보존. 늦은 재전송 거부, 임의 최신값 덮어쓰기로 명령 결손 은폐 금지. bounded request lane 후보8; 실패 latch/독립 보호 필요 |
| 결과/ACK | 실제 실행 결과만 원래 operation/role/token에 대응. 늦은 ACK가 다음 요청을 완료하면 안 됨. exact duplicate 의미·원래 deadline 보존. middleware write 성공은 실행 ACK 아님 |
| 상태/Actual | per-source 측정 identity/time·unknown·의존 freshness 유지. 주기 관측의 최신값 history 후보는 가능하지만 이벤트/critical 상태와 구분하고 loss/최대 age를 검증해야 함. 아직 KEEP_LAST 채택하지 않음 |
| 세션/credit | Prepare→INIT→Release의 전체8-role ACK, 새 durable Epoch·원래 단계 deadline. 중복 idempotence·재시도 budget은 별도 lane에서 검증. DDS 자동 discovery/reconnect나 이번 readiness가 authority를 부여하지 않음 |
| 보호 | 정상 lane 포화와 독립 전달·로컬 감시 필요. 원래20ms·issuer/Epoch/token 불변. actor 선택 뒤에만 ACK;8개 identity tombstone/issuer/Epoch 보존, 가득 차도 보호 선택·새 ACK 미발행. 만료 재시도 거부, 새 INIT 전 자동 복구 금지 |

위 요구는 [ADR-0058](../../../adr/ADR-0058-remote-owner-authority-and-dds-probe.md)/owner-wire에서
온 것이다. 보호 ACK identity8개는 DDS resource8과 별개다. 모든 종류를 현재 두 topic에
섞어 같은 QoS로 처리하는 운용 설계는 미완료다. 8이 충분한 capacity라는 분석도 없다.

## 수정·비교 결과

[사전 protocol](protocol.md)과 후속 [readiness protocol](readiness-protocol.md)을 실행 전에
저장했다. [행별 결과](results.csv), [packet](packets.csv), [실제 thread](threads.csv),
[QoS readback](qos.csv), [warning/분모](analysis.json), [전체 원본](raw.tar.gz).
각 cohort는 build 전에 plan/NOT RUN rows/source snapshot을 저장하고 빌드 후 순차 실행했다.
35s outer/기존12s readiness·10s transition·15s wait,600s/512MiB 및 exclusive lock을
유지했다. source-stability는 두 cohort 모두 true다.

| 일반 빌드, 각3회 | 통과 | 해석 |
| --- | ---: | --- |
| A: CPU1/1·5ms·전체 관측 |0/3|매번 초기17개 만료; reader rejection2. 방향은 down1회/up2회 |
| B: CPU1/1·5ms·최소 관측 |2/3|1회 초기17개 만료. 관측 비용만으로 전체 원인 설명 불가 |
| C: CPU1/2·5ms·최소 관측 |3/3|각60 왕복, 전체 결과 RTT max0.572ms 미만 |
| D: CPU1/2·20ms·최소 관측 |3/3|각60 왕복, max0.573ms 미만; C 대비 주기 이점은 이 작은 표본에서 입증 안 됨 |
| A + 명시적 양방향 transport 준비 |3/3|동일60명령/20ms 판정 유지. 아래 확인된 시작 원인에 대한 별도 후속 |

전체 관측은 allocation hook의 매번 stack unwind·finest packet log·메시지별 flush·
private WHC snapshot을 포함한다. 최소 관측은 allocator/finest/private 조회를 끄고
고정2048 event buffer에 판정 시각을 남긴 뒤 delete 전에 저장한다. QoS와 상태/thread는
setup/종료 시 수집한다. 이 비교는 관측 수준 묶음의 효과이며 flush·unwind 각각의 비용을
분리한 실험은 아니다. SDK 내부 thread 계측과 TSan 자체 부하도 남는다.

**확인된 진단 결함:** `partial`의 단일 `deleted` 변수가 reply writer 삭제 뒤 reader의
take도 중단했다. 계측한 수정 전1회는 received20/삭제 뒤0·rejected104였지만 원래
oracle는 PASS였다. 원본 PASS는 그대로 보관하고 이 관측 결함을 별도로 표시했다.
reader/writer 삭제 상태를 분리하고 기존 assertion에 “삭제 뒤 수신 계속”을 추가했다.
수정 후 세 build 모두 삭제 뒤40개를 추가 수신·reader rejection0, 실제 다음 write 실패와
송신 실패 latch는 유지했다. Normal은 그40개 중4개가 늦어 거부됐으며 이를 숨기지 않았다.

**확인된 이번 전달 실패 위치:** A1 zone trace에 첫 DATA `no heartbeat seen yet`,
첫 NACK1792554861.863245→다음1792554861.963297(100.052ms)·seq1 retransmit가 남는다.
packet0 ingress age100.784ms, writer max0.149ms. A2/A3도 받는 쪽 trace에서 동일
첫-heartbeat 순서를 확인했다. 핀 source `ddsi_receive.c`는 reliable reader가 첫
heartbeat를 보기 전 DATA를 받지 않는 분기가 있다. 그 뒤 sequence hole/retransmission이
20ms를 넘겼다. CPU/observer는 이 startup ordering의 빈도에 영향을 주지만 이 사례를
“100ms CPU 스케줄 대기”로 확정할 수 없다. B3는 최소 관측이라 같은 내부 경로는 가설이다.
과거19 FAIL 모두의 원인으로 확대하지 않는다.

선택형 `SD_TRANSPORT_READY=1`은 normal 진단에서 양쪽 writer/reader match 뒤 **같은
endpoint로 구별된 준비 record를 한 번씩 주고받아 실제 수신을 확인**한다. 이후 두
ready marker가 있어야 go가 열리고, 그때부터60개 명령을 새로 만든다. 기다리는 중
원래 명령을 버리거나 기한을 연장하지 않는다. 실제 준비 소요1.292–10.010ms(일반3회),
기존10s setup cap 이내이며 fixed sleep 추가가 없다. 별도 준비 미송신1회는 원래 약10s
제한으로 FAIL, go 없음/owner 명령0/두 process 종료 기록으로 negative control PASS다.
legacy 기본 cold-start 시험·assertion은 유지한다. 이는 session/arm 구현이 아니다.

**종료 조건:** 후보 D에서 peer-stop, SIGKILL, raw restart, quiesce/drain restart,
callback 중 reader-delete, partial writer-delete, reader 포화 중 close를 각 build1회씩
구분했다. 세 build 모두 기능 조건은 충족했다. 포화 close는 reader rejection>0 확인 후
시작했고 Central은 살아 있으며 delete 요청 뒤에도51회씩 송신했다. 별도 overflow는
400ms take 중단 뒤 stale20개를 거부했고 SDK rejected25/lost0, ingress 최대8이었다.
raw/coordinated restart 모두 새43 수신·원래42 old/stale 거부다. 기존150ms drain grace와
100ms ack wait는 원래 값이다. **새 sleep/timeout 연장으로 close를 고친 것이 아니다.**
이번 미재현은 과거5ms/full-RHC/GC close timeout의 해소 증거가 아니다.

## 분모·sanitizer·회귀

- cohort-v1은38회: Normal20회=16 PASS/4 FAIL; ASan9회=기능9 PASS;
  TSan9회=기능9 PASS,8회에58 warning으로 FAIL. 원본 종합26 PASS/12 FAIL 유지.
  ASan/TSan peer-kill 각1회는 종료 계측이 잘렸으므로 **sanitizer INCOMPLETE**다.
  `sanitizer_clean` 원본 bool은 관측 경고 없음만 뜻하며, 새 `sanitizer_verdict`로 구분했다.
- readiness-v2는6회: Normal A3 PASS, ASan D1 PASS, TSan D1 기능 PASS/6 warning FAIL,
  준비 미송신 negative1은 의도한 FAIL/negative control PASS. TSan 경고 총64 occurrences는
  독립 결함64개가 아니다. bucket/index/free/mutex·lease/TKMAP·heartbeat/WHC 계열을 보존했다.
- 위44회 + 계측한 partial 수정 전1회 = **새 runtime attempts45회**. 기존42회에 합쳐
  수용률을 만들지 않는다. 새 SDK build/setup 실패 없음; unit compiler-shim 실패는 별도다.
- ASan/TSan overflow에서 실제 wall-time으로 늦은20개를 원래 expiry로 거부, availability
  loss 기록, 잘못 수용한 expired packet0. echo에는 actuator가 없어 physical 보호 ACK는
  **미검증**이다. 관련 기존 실제 actor component를 따로 ASan/TSan 각11/11 PASS로 확인했다
  (logical clock: composite expiry 보호·late command/ACK·Stop/Power/permission·FIFO latch).
- lifecycle Python7 + middleware Python22 = **관련29/29 PASS**. 원래137개 전체 재실행은
  하지 않았다. 강제 readiness timeout unit은 두 실제 대기 child의 kill/wait/exit/FAIL 저장과
  생존 process0을 검사한다. 새 DDS 준비 미송신도 실제 timeout cleanup 분기를 밟았다.
- 세 profile 진단 C/C++ 빌드, 기존 C channel의 공유 QoS header 엄격 컴파일 PASS.
  production source 불변으로 전체973/native40/timing48을 관성적으로 다시 실행하지 않았다.

## SDK 근거·남은 조치

공식 [11.0.1 release](https://github.com/eclipse-cyclonedds/cyclonedds/releases/tag/11.0.1)는
현재 pin이며 그 release note에 이번 full-RHC close 해결 근거는 없다.
[공식 configuration reference](https://cyclonedds.io/docs/cyclonedds/latest/config/config_file_reference.html)는
thread별 scheduling 설정과 sync/async delivery, writer linger를 설명한다. writer linger는
reader/GC 종료 보장과 다르고 Internal 옵션을 임의 변경해 지원되는 수정이라고 할 수 없다.
신뢰성·history의 [공식 설명](https://cyclonedds.io/docs/cyclonedds-cxx/0.10.2/api/core.html)은
오래된 sample의 재전송이 원래 application deadline을 보장한다는 의미가 아니다.

이번 증거에 연결된 pin source는 [receive](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_receive.c),
[writer throttle](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_transmit.c),
[reader](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsc/src/dds_reader.c)다.
VOLATILE historical-data wait는 이 pin에서 바로 반환하므로 readiness 대용으로 사용하지 않았다.
SDK 소스 읽기는 위 관측 경로에 한정했고, 전체 내부 안전성 검증으로 확장하지 않았다.

| 분류 | 상태 / 다음 조치 |
| --- | --- |
| 애플리케이션 진단 | partial reader 정지 결함 수정·검증. QoS/status/readback 공백 보완. match-only startup은 opt-in 실제 양방향 준비로 보완. 정규 session/adapter는 여전히 없음 |
| 환경/구성 | CPU1 공용·과한 관측은 스트레스에는 유효, 운용 대표성 불충분. D 및 data readiness가 Host 후보. IRQ/SMT/background load·실제 owner 통합·새 workload timing 미검증 |
| SDK | 현재 pin에서 startup heartbeat/retransmit 지연 확인. transport bootstrap으로 이번 시작 실패를 회피하지만 이후 packet loss의100ms 재전송/20ms 실패 가능성은 남음. 종료 멈춤 미재현/OPEN, TSan64 경고 unresolved |
| Target | Jetson 보드/JetPack/compiler/ABI, PREEMPT_RT 대조, core/IRQ/priority/isolation, NIC/SocketCAN, namespace/CAN 접근, discovery/firewall, power/clocks/thermal/load, clock sync/uncertainty, 메시지별 QoS·큐 산정·보호 독립 lane 모두 결정/검증 필요 |

**다음 한 단계:** 기존 full-RHC close GDB 근거와 이번 포화/지속 송신 대조·정확한
pin/build/config 및 경고별 원본을 묶어 SDK 측에서 지원하는 종료 절차/수정의 근거를
확보한다. 지원되는 변경이 정해지면 raw/full-RHC close와 해당 경고 경로만 사전 고정
대조한다. 외부 issue/메시지는 이번에 게시하지 않았다. 근거 없는 atomic 변경·경고 억제·
큐 증설은 없다. **종료와 설명되지 않은 메모리 경고 gate가 미충족이므로 DDS 제어 연결 불가.**
M4 예외·학습자 REVIEW PENDING·Jetson/system NOT RUN을 유지한다.

접근: 이전 Daybreak 인증 안내를 인계했다. 이번 새 Daybreak/인증 안내는 없었다.
공식 writer API의 한 URL open은 도구에서 “URL … is not accessible via this tool”로
실패하여 해당 URL 조회를 중단했다. 같은 요청을 재표현/다른 세션/수동 명령으로 재시도하지
않았다. 제한 원인은 응답에 없으며 일반 접근 오류와 Daybreak라고 단정할 수 없다.
알려진 발생 범위·요청·안내·완료/미완료 항목은 raw의 access-log에 보존했다.

## 재현·보존

```bash
python3 tests/integration/middleware/check_dds_operating_profile.py build/m5-dds-profile-new
python3 tests/integration/middleware/check_dds_operating_profile.py --readiness build/m5-dds-ready-new
python3 -m unittest discover -s tests/unit -p 'dds_lifecycle_test.py'
python3 -m unittest discover -s tests/unit -p 'middleware_probe_test.py'
```

새 output 경로를 사용한다. 설치/SDK fetch를 수행하는 runner가 아니므로 이전 pin/build
의존성이 있어야 한다. 정확한 원본 재실행은 각 archived `sources/`·`runner.py`를 사용한다.
readiness-v2 뒤에는 CLI의 `--readiness` 노출·sanitizer 완료 분류·회귀만 추가했다.
그 뒤 SDK 시험을 새로 셌다고 주장하지 않는다. archive는 원본 plan/source/hash/명령·
stdout/stderr/trace/CSV/maps/thread/QoS와 setup timeout, focused protection XML을 담고,
재빌드 가능한 바이너리는 SHA만 보존한다. [offline analyzer](analyze.py)는 원본 판정을
바꾸지 않고 CSV/경고를 추출한다. 전체 원본 SHA는 [manifest](manifest.json)에 있다.
