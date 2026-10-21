# M5 SOME/IP(vSomeIP) Central↔Front 파일럿

2026-10-21. **판정: 조건부 — Host 두 노드 component 파일럿의 지정 기능·계측 경로는 통과,
정규 transport 채택/제어 adapter 연결은 보류.** 실행 가능한 별도 파일럿과 재현 도구를
추가했다. DDS 실패를 해결하거나 기존 gate를 대체한 결과가 아니다.
M4 Host IO/FIFO 한정 수용·전체 NOT CLOSED, DDS gate CLOSED·정규 DDS adapter 미착수,
Jetson/전체 시스템 NOT RUN을 유지한다.

시작 시 clean main과 fetch한 origin/main은 `017e3b0471c2fa344a1a34049b7a73d2a5cf5b54`로
같았다. 구현 `30a250c`, 수신·종료 진단 보완 `bf5c341` 뒤 살아있는 Central 재가입 시험을 추가했다. 기존 로컬 변경은 없었으며
제품 `central/zone/vecu/interfaces/simulation` 코드는 수정하지 않았다.

## 구현과 실제 경계

[코드](../../../../tests/integration/someip/pilot.cpp), [빌드 도구](../../../../tests/integration/someip/build.py),
[runner](../../../../tests/integration/someip/run.py), [wire 표/ICD](../../../icd/someip_pilot.md),
[ADR-0060](../../../adr/ADR-0060-someip-host-component-pilot.md)를 함께 본다.

- 공식 vSomeIP3.7.6 / `4187431d2815bd351845a09d01aa85b2a3163cab`, Boost1.85.0을
  ignored build 아래 고정했다. SOME/IP와 vSomeIP, DDS와 Cyclone DDS는 각각 protocol과
  implementation의 구분이다. 기본 build에는 새 SDK/network dependency가 없다.
- Central의 실제 ControlAllocation → owner-wire → TCP method → Front CommandGateway →
  실제 Steering/Brake CAN/P05 receiver·actor로 연결했다. 결과는 실제 처리된 frames와
  Epoch/token/operation을 반환하며, 상태는 실제 actor가 만든 원본 Steering Actual bytes다.
- Allocator의 support/Rear/management/permission과 두 Leaf의 zero sensor는 명시적 SIL
  fixture다. 전체 vehicle closed loop나 실제 Host IO/CAN device 시험이 아니다.
  local fixture grant는 discovery와 별개다. 전체8-role Release ACK·RunLease·RUNNING을
  만들지 않았고 네트워크 요청으로 INIT/Release/arm을 승인하지 않는다.
- 명령 원래 sent/source/deadline·inner expiry, exclusive20ms envelope, CRC/route/domain,
  Epoch/token/operation과 final CAN write guard를 보존했다. 일반 result가 늦으면 FAIL이다.
  SDK 전송 성공을 처리 완료로 사용하지 않는다. 서비스 준비는 발견+실제 양방향 수신이며,
  event/subscription은 이 binding에 없다.

## 실행 결과 — 분모와 실패 원본 보존

사전 [protocol](protocol.md)과 실행 전 amendment에 비교 가설·횟수·시간제한을 기록했다.
각 case의 원본 로그/exit/설정/패킷/transactions는 [raw.tar.gz](raw.tar.gz)에 있다.
[기계 판독 요약](results-summary.json)은 raw runner exit를 그대로 집계한다.

| Cohort | 실제 실행 | 결과 / 해석 |
| --- | ---: | --- |
| attempt-01 | normal1 | **0 PASS /1 FAIL**. 기본 nPDU 설정에서 두 결과 왕복 후 원래20ms 초과; capture 준비 결함도 기록 |
| attempt-02 | normal3+기타7 | raw runner10 PASS. **SDK client-ID 오류 로그가 있어 수용 근거로 사용 불가**; 당시 oracle 누락을 후속 수정. 원본 PASS JSON은 변경하지 않음 |
| normal-final | normal3+기타7 | **10/10 PASS**, 정상24 command pairs의48 parent/command 결과 모두 원래 시한 내, CAN48 frames |
| asan-final | 8 cases | **8/8 PASS**, ASan/UBSan/LSan 경고0 |
| tsan-final | 8 attempts | **0/8 PASS**, runtime 주소 mapping 오류/초기 SIGSEGV로 사용 경로 검증 불가 |
| tsan-fixed-layout | 8 cases | **7 PASS /1 FAIL**, TSan 경고0. close-busy의 무제한 진단 송신이 SDK8192-byte queue drop 유발 |
| bounded-busy-normal/asan/tsan | 각 close-busy1 | **3/3 PASS**, 요청10=거부2+의도한 peer 종료 후 만료8, pending peak8, API stop/join 반환, SDK error·sanitizer 경고0 |
| boundary-normal/asan/tsan | 각 normal1 | **3/3 PASS**, 최종 status Epoch·method 검사 경로 회귀 |
| rejoin-normal/asan/tsan | 각 normal1+restart-live1 | **6/6 PASS**, 같은 Central PID/SDK application에서 Front 소실→새 Epoch43 재발견·양방향 준비·old bytes 거부·신규8 cycles |

총 **57 attempts: raw exit 기준47 PASS /10 FAIL**이다. 그중 attempt-02의10개는 위에
설명한 SDK 오류로 수용에서 제외한다. 실패를 후속 PASS로 덮거나 성공까지 반복하지 않았다.
Build/configure 실패와 Python 준비 실패는 runtime 분모 밖에 따로 보존했다.

| 지정 고장/수명 조건 | 관측과 판정 |
| --- | --- |
| 늦은 상대 / 준비 timeout | 500ms 늦은 시작 후 실제 왕복 준비; 상대 없는3s 준비 timeout 뒤 stop/join 반환. warm-up sleep으로 준비 선언하지 않음 |
| duplicate/old Epoch/CRC/route/domain/expired | normal8 cycles 뒤 각각 거부. duplicate는 추가 CAN 적용 없음; 원래30ms 지난 명령이 원래20ms 시한으로 거부·보호 |
| 수신 소비30ms 지연 | 세 빌드 모두 원래 명령 거부, CAN0, 종료 전 실제 보호 선택. sanitizer에서도 시한 연장 없음 |
| 소비120ms 정지+9개 전송 | Front highwater8·overflow latch, CAN0, 원래 backlog 거부. 종료 시 보호 호출을 고장 보호 증거로 세지 않음 |
| 정상 종료 / 지속 송신 중 종료 | 실제 stop_offer/release→clear handlers→stop→start thread join 반환. 수정된 지속 송신에서는 상대가 살아 있는 동안 Front 반환; 강제 kill 아님 |
| 중단·새 세션 | Front42에 의도적 SIGKILL(정상 종료/LSan 통과로 세지 않음), 새 Front43·Central43 시작, 보존한 epoch42.packet 원본 그대로 거부, 새 session8 command pairs 처리 |
| 살아있는 Central 재가입 | Central process/SDK application 유지, Front42만 중단, availability loss 실제 관측 뒤 별도 로컬 Epoch43 권한, 새 Front43 재발견/양방향 준비, 원본 old42 bytes 거부·신규8 pairs |

일반 normal-final의 parent/command 수신 지연은 이48개 표본에서 **1.067–4.612ms**였다.
ASan/TSan 표본은 각각1.137–4.509 /2.291–4.877ms지만 **일반 성능 결과와 합산하지 않는다**.
정상 API stop 측정은 normal-final0.218–0.494ms, ASan0.815–1.222ms,
TSan fixed-layout1.018–1.672ms였다. 이는 짧은 관측값이며 WCET/운전 중 재연결 보장이 아니다.

## 발견·수정 및 남은 SDK 해석

1. 기본 nPDU retention5ms/방향(공식 문서)과 두 순차 왕복의 약21.75ms 지연이 맞았다.
   네 공식 nPDU timing을0으로 설정하고 원래 시한을 유지했다. 초기 capture/ID 오류도 함께
   고쳤으므로 **nPDU만의 효과를 분리한 통계적 성능 실험은 아니다**.
2. 두 host가 같은 diagnosis를 쓰면 vSomeIP의 `is_valid_client_id` 규칙에 맞지 않았다.
   Central0x13/0x1311, Front0x14/0x1422로 분리하고 `[error]` 로그도 runner FAIL에 포함했다.
3. user namespace 안 tcpdump의 setgroups 실패를 보존했다. 같은 namespace의 AF_PACKET
   수집기로 바꿨다. 관리자 권한·host 설정 변경은 없다. [IP proof](ip-proof.json)는 실제
   veth에서0x5344 서비스의0x10/20/30 요청·응답을 두 방향 각각1/16/8개 확인한다.
4. 진단 송신기가 peer 종료 뒤 결과를 버리며 계속 전송하던 결함을 capacity8·20ms 미완료
   정산·송신 latch로 수정했다. SDK queue를 늘리거나 error 판정을 완화하지 않았다.
5. restart는 원본 bytes 재사용, 로그는 Epoch별 분리, protection은 종료 전 계수로 검증했다.
   status의 application Epoch와 method 검사도 추가했다.
6. TSan 시작 실패는 process-local `setarch x86_64 -R` 비교로 해소했다. 동일 binary/SDK다.
   Linux 전역 ASLR/커널 보안/sudoers는 변경하지 않았다. 수정 후 실제 사용 경로의 TSan
   경고는0이며, SDK 내부 전체의 race freedom을 증명한 것은 아니다.

정상 종료 로그 일부에는 vSomeIP `Maximum wait time for send operation exceeded`가 있다.
핀된 `tcp_server_endpoint_impl.cpp:996–1024`는 `is_sending_ && _error`가 false인 **else 전체**에서
그 문구를 출력한다. 따라서 문구만으로 실제 timer timeout을 확정할 수 없다. 이 실행의
응용 결과는 이미 수신됐고 API 반환도 계측됐다. 경고는 삭제/억제하지 않았으며, 실제 send
상태별 의미와 일반적인 drain 보장은 미검증이다. [문의 초안](support-draft.md)에 정확한
경로·질문을 남겼다. SDK patch나 광범위한 내부 재설계는 하지 않았다.

## 설정·계측 범위

| 구분 | 설정 근거와 실제 관측 |
| --- | --- |
| 설계값 | reference.yaml의 Central20ms / Front·Steering·Brake10ms. 이 YAML을 실행기가 읽지는 않음 |
| 적용 요청 | JSON TCP30501, SD UDP30490, max payload512, SDK byte queues8192, nPDU0, CPU1/2·OTHER0 |
| 실행 관측 | `/proc` thread snapshot의 main/dispatcher/IO/SD thread 모두 해당 CPU 및 policy0/priority0; IP socket과 netns 식별자·패킷 기록. Queue8192는 실패 로그에서도 실제 한도 확인. App queue peak8 |
| Host | i7-11700,8 physical/16 logical; CPU1/2는 다른 core, SMT sibling9/10 미격리. Linux6.8.0-138, GCC11.4, Boost1.85 |
| 빌드 | RelWithDebInfo의 최종 `-O2 -g -DNDEBUG`(앞의-O1보다 뒤에 적용); pilot/SDK C++20, 제품 libs C++17. Boost b2 별도 flags 원본 보존 |
| sanitizer | SDK core/cfg/sd/e2e 및 Boost filesystem/atomic와 연결된 프로젝트 라이브러리에 해당 sanitizer flags; shared ELF의 실제 __asan/__ubsan/__tsan 심볼 확인. e2e SDK library는 빌드했으나 이 payload 경로에서 사용하지 않음 |
| 계측 밖 | 시스템 libc/libstdc++/loader/kernel은 재빌드하지 않음. Boost Asio header는 SDK에 함께 계측. GCC의 fence 계측 제약과 upstream의-Wno-tsan compile diagnostic 옵션은 남아 있음; runtime suppression 없음 |
| 관측 비용 | per-message flush/할당 추적 없음; CSV는 buffered. SDK warning 및 PCAP 수집 비용은 존재. SDK dynamic allocation, OS socket buffering과 head-of-line blocking이 없어졌다는 주장은 없음 |

[build provenance](build-provenance.json)에 exact SHA·linkage·flags·compiler와 최종 source hash,
raw에는 compile_commands/CMakeCache·초기 configure 실패를 보존했다. nPDU는 로드된 JSON과
소스 경로로 확인했으며 별도의 SDK getter readback을 추가한 것은 아니다.

## 재현과 한계

```bash
python3 tests/integration/someip/build.py normal
python3 tests/integration/someip/build.py asan
python3 tests/integration/someip/build.py tsan
python3 tests/integration/someip/run.py build/someip-repro-normal --profile normal --normal-repeats 3
python3 tests/integration/someip/run.py build/someip-repro-asan --profile asan
python3 tests/integration/someip/run.py build/someip-repro-tsan --profile tsan --fixed-layout
PYTHONPATH=tests/unit python3 -m unittest someip_pilot_test dds_lifecycle_test middleware_probe_test -v
```

Output directory는 새 경로여야 한다. 독점 build lock의 부모는 자동 생성한다.
실제 Git checkout의 build/ 없는 상태에서 **Python37/37 PASS**(새8+기존29)다.
이는 SDK mock/bookkeeping 시험이며 실제 SDK 캠페인과 별개다. 실제 dummy child를 timeout시켜
kill/wait/실패 원본 보존 분기를 검증했다. 앞선 Git metadata 없는 archive 시험은4 failures/
17 errors로 실패했고 수정 대상이 아닌 준비 방법의 오류로 남겼다.
SDK 없는 기본 CMake configure도 PASS. 전체973/native40/timing48은 **재실행하지 않았다**.

조건부 권고는 **SOME/IP/vSomeIP를 다음 Host adapter 후보로 유지**하는 것이다. 현재 남은 비용은
애플리케이션의 실제 session/Release/RunLease·독립 protection lane·status 유실/순서 복구·
거부 시 Central 보호 연결과, 환경의 Jetson CPU/clock/network/authentication/부하 검증이다.
운전 중 TCP 단절/재전송의20ms 보장과 SD/event lifecycle은 아직 검증하지 않았다.
다음 한 단계는 **실제 Session/RunLease와 독립 보호 lane을 연결한 Host adapter 경계 시험**이다.
이는 이번 두 노드 fixture를 정규 시스템 RUNNING으로 바꾸는 승인이나 구현 완료 선언이 아니다.

새 Daybreak/콘텐츠 제한 안내는 없었다. 이전 DDS 접근 중단 이력을 유지하고 차단된 요청을
재시도하지 않았다. `/proc/sys/vm/mmap_rnd_bits` 읽기 거부는 기록 후 재시도하지 않았다.
외부 문의/게시/메시지 전송은 하지 않았다.
