# SOME/IP 진단 channel과 새 logical source

2026-11-03. **실제 TCP/SDK·logical owner 부분 PASS; 전체 M9/TBD-08 OPEN**.
[계약](../../../interfaces/diagnostics.md#someip-진단-channel과-새-logical-owner),
[사전 recipe](../../diagnostics-protocol.md#someip-진단-channel새-logical-owner-fixture),
[ADR-0086](../../../archive/design-decisions.md#adr-0086), C-M9-SIP-01–06을 따른다.

## 실행 경계

기존 pinned vSomeIP3.7.6/4187431d2815bd351845a09d01aa85b2a3163cab을 사용한다.
별도 diagnostic application/service Publisher0x5d10·Replica0x5d11, instance/interface1,
Data0x0101/ACK0x0102·MT_REQUEST_NO_RETURN1·reliable TCP다. 기존 control0x534x,
owner-wire·원래 제어/검출/권한·SDK queue 설정은 변경하지 않는다. Source/replica는 각 case에
명시적으로 새 store7001/registry3를 만든다. 고정 test ID는 격리 case 사이에 합치지 않는다.

Callback은 binding/크기 검증 후 유한 FIFO8에 넣는다. 원래 logical owner는 기존 SPSC에
Event를 publish하고 별도 writer가 기존 Outbox/Recorder로 fsync·SDK send를 수행한다.
Source worker는 producer 종료를 acquire한 뒤 남은 queue까지 비워야 종료한다. SDK callback에
파일 I/O·control/clear가 없다. Payload2048/local4096, SDK external/local queue16384는 진단
application만의 설정이다. 기존 control512/1024·8192와 구분한다. 실제 surviving-node counter는
drop/reject0·highwater≤8이며 SIGKILL한 첫 replica의 종료 시점 SDK counter는 얻을 수 없다.

Source는 archived journal이 아니라 **매번 새로 실행한** SimpleVehicle graph의8-role INIT/
full Release·Central Speed/Stop/Coordinator observer다. Logical1ms마다20µs Host pacing을
넣으며1:1 wall 실행이 아니다. Native Event는 Simulation/instance7001, publisher/replica CSV는
monotonic, PCAP은 wall clock이다. Source 시각을 다시 쓰거나 서로 다른 clock을 빼 latency를
만들지 않는다. Immutable Event의 Recorded는 이번에도 sidecar commit 시각으로 덮지 않는다.

별도 netns/veth10.89.0.1/30↔10.89.0.2/30·TCP40510/40511을 사용한다. 각 process의 /tmp와
/dev/shm도 별도 mount이므로 SDK local IPC 우회가 없다. Runtime PID/netns/thread/affinity/
policy·maps·socket·config를 보존한다. Scheduler/Target RT 성능 수용이나 실제 control traffic을
IP로 바꾼 native Central/Front/Rear owner 통합을 뜻하지 않는다. 정규 DDS gate는 CLOSED다.

## 최종 결과

| Case | 새 source와 원본 판정 | 전송·replica 결과 |
| --- | --- | --- |
| normal | logical92s·4350 controls·DTC0·실제 정상 정지/HV-off |12 Event·9200 physical 표본·원본과 동일한 journal |
| loss | logical13s·elapsed10s SpeedRequest argument 누락·SD-1001 한 건 |15 Event·1300 표본·Failed/count1/generation1·미삭제 |
| drop-ack | 같은 native fault의 최초 durable ACK 한 번 생략 |100ms 재시도·Duplicate ACK·이력/count 유지·Failed |
| restart | 최초 Fault commit 뒤 replica SIGKILL, 새 client0x2222로 같은 store 재시작 |prefix2 보존·새 TCP 연결·15 Event 완성·Unknown/count1/generation1·미삭제 |

SDK **Normal4/4·ASan4/4·TSan live loss1/1**이다. TSan은 process-local `setarch -R` 실행이며
global ASLR 설정은 변경하지 않았다. 모든 완료 node와 capture가 정상 종료했고 강제 정리는0이다.
Restart의 첫 replica exit-9는 명시한 fault 주입이며 cleanup 성공이나 일반 정상 exit로 바꾸지 않는다.
TSan1개 경계의 경고0을 전체 SDK·모든 profile·Target 수용으로 확대하지 않는다.

Fault case의 원래 absolute Simulation 시각은 detector11.002s,5개 Leaf 선택11.0022s,
두 Zone ACK11.0024s, Central callback ACK11.005s, 실제 torque/brake acquisition11.211s다.
검출/보호100ms·Actual230ms budget은 그대로다. Parent ACK를 Leaf selection으로 기록하지
않는다. 물리 response는 전체 차량 정지/HV-off 선언과 다르다. ACK 손실·재연결이 새 Passed/
clear를 만들지 않는다. Replica 상태는 원래 source 이력의 projection이며 현재 물리 readiness가 아니다.

모든 실행에서 source Event가 producer 실행 중 commit되었고, fault도 source 실행 중 회수했다.
진단 on/off의 전 physical·model identity/sequence·권한·SOC/energy·torque/brake/bus/contactors가
같다. Source와 replica의 canonical bytes도 같다. SDK send-return/request 수는 retry/중복 때문에
Event 수보다 클 수 있다. 그 수를 unique occurrence나 durable 전달 수로 사용하지 않는다.

독립 Python auditor는 PCAP TCP stream의 SYN/연결·byte overlap/누락·SOME/IP header/
client/direction과 Event/ACK CRC를 복원한다. 원래 journal·최초 detector·Leaf/Zone 원본 log·
Parent ACK·fresh Actual·physical/energy를 대조한다. Normal각8개·fault각10개 변조를 거부했다.
최종9개 dataset 모두 감사 통과다. Clock/context·false live source·원본 변조·ACK 누락·물리
reset·이력 삭제 등을 거부한다. 정상/ASan·TSan 사이의 store6+physical2, 총40개 artifact는 byte
동일하며 PCAP/host timing·PID/receipt counter를 그 분모에 넣지 않는다.

기본 일반 unit/logical **1172/1172**, 영향 ASan/UBSan **239/239**, 기존 M4AsyncWall **2/2**,
source fingerprint 검사2개, 변경 transport/demo TU2개 clang-tidy warnings-as-errors·cppcheck
warning/performance/portability, BUILD_TESTING=OFF Release의 SDK library 빌드가 통과했다.
ASan selector를 `Diagnostic`으로 넓혀 신규 binding2개와 기존 singular Diagnostic 시험3개를
포함했다. 이239개와 SDK4개·TSan1개·기존 wall2개는 별도 분모다.

이전 M9 evidence8묶음의 SHA43/153/135/203/183/186/217/306개는 유지했다.
[results.json](results.json)은 최종 분모/감사, [manifest.json](manifest.json)은 base commit·
source overlay/fingerprint·binary/SDK library/tool/config를 묶는다. CSV/log/PCAP/maps는 gzip,
store canonical bytes는 원본이다. Binary 자체 대신 hash와 SDK commit/build flags를 보관한다.

## 실패와 수정 전 기록

1. 최초 SDK compile은 PUBLIC include가 기존 owner_transport.hpp를 가려 실패했다.
   `build-sdk-normal.log.gz`와 `compile-probe-source/`는 실패 직후 include 수정 전 후보를
   보존한다. 새 target의 include root를 interfaces/로 바꿨다. 다른 owner transport는 수정하지 않았다.
2. 최초 실제 전송 probe는 내부 runtime/복제/on-off 동등성이 통과했지만 기본1.2s 주입을
   사용했다. 독립 감사가 사전10s recipe 불일치를 거부했다. `probe/` 원본·`probe-source/`
   source/binary hash·`audit-probe*`를 보존하며 **이 probe를 요구 검증 PASS로 세지 않는다**.
   `c.injection_ns=10s`를 명시했고 허용 오차/원래100ms·230ms 기준을 바꾸지 않았다.
3. Clang14는 GCC13 C++20 chrono 표준 헤더를 parse하지 못해 정적 분석1회가 실패했다.
   새 demo에는 C++20 기능이 없으므로 불필요한 표준 지정을 제거해 프로젝트 C++17을 쓴다.
   `before-language-*`/`before-language-source/`에 당시 정적 분석·source/binary hash·감사를
   보존했다. 새 binary로 SDK Normal4/ASan4/TSan1을 모두 재실행했고 journal/physical72개가
   수정 전 후보와 byte 동일하다. 기존 다른 SDK target의 C++20은 바꾸지 않았다.

중간 통과를 최종 분모와 합산하지 않는다. 이전 성공 raw cohort는 build/m9-someip-{normal,
asan,tsan}에 남아 있으며 공개 묶음은 후보 hash/감사와 최종 raw cohort를 포함한다.

## 재현

Base commit에 `sources/` overlay를 적용하고 기존 pinned SDK build 경로를 사용한다.
처음 SDK를 준비할 때 `tests/integration/someip/build.py <profile>`이 새 target도 빌드한다.
기존 SDK를 쓸 때는 아래처럼 target만 빌드할 수 있다. Output은 새 경로여야 한다.

```sh
cmake -S . -B build/m5-someip-normal/project
cmake --build build/m5-someip-normal/project --target someip_diagnostics_live --parallel 3
python3 tests/integration/someip/diagnostics_run.py build/diag-normal --profile normal --cases normal loss drop-ack restart
python3 -B tests/integration/diagnostics/audit_someip_diagnostics.py build/diag-normal/loss --mutations
cmake --build build/m5-someip-asan/project --target someip_diagnostics_live --parallel 3
python3 tests/integration/someip/diagnostics_run.py build/diag-asan --profile asan --cases normal loss drop-ack restart
cmake --build build/m5-someip-tsan/project --target someip_diagnostics_live --parallel 3
python3 tests/integration/someip/diagnostics_run.py build/diag-tsan --profile tsan --fixed-layout --cases loss
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --output-on-failure --parallel 3
ctest --test-dir build/m1-angle-sanitized -L '^(unit|integration.logical)$' -R 'Diagnostic|^NativePower\.|ControlRecoverySil|Session|M4' --output-on-failure --parallel 2
python3 -B docs/test-plan/evidence/m9_someip_live/verify-packaged.py
```

`verify-packaged.py`는 임시 경로에만 압축을 풀고 보존한 auditor로 최종9개 dataset과 변조
거부를 재검사한다. `SHA256SUMS`는 자기 자신을 제외한 공개 묶음을 보호한다.

다음은 native Central/Front/Rear publisher의 trusted global context·다중 stream/source adoption
통합이다. Local Ready를 global Release로 만들지 않는다. 정규 DDS·Clock recovery·부하/보존
용량·Target/CARLA 전체 fault matrix·학습자 이해 수용은 OPEN이다.
