# Event-only 진단 전송과 유한 spool

2026-11-03. **wire/spool component·AF_UNIX 분리 process PASS; 전체 M9/TBD-08 OPEN**.
[계약](../../../interfaces/diagnostics.md#event-only-원격-replica와-유한-spool),
[사전 recipe](../../diagnostics-protocol.md#원격-진단-wire유한-spool-fixture),
[ADR-0085](../../../archive/design-decisions.md#adr-0085), C-M9-TX-01–06을 따른다.

## 구현과 범위

Wire v1은 기존 canonical Event와 durable ACK만 전달한다. Stream/registry/ordinal·payload
길이·CRC를 검사하고 최대2048 bytes다. 원격 clear/control은 없다. CRC는 오류 검출이며
인증이 아니다. 같은 unique source/replica store ID와 registry 및 trusted peer를 호출자가
명시적으로 provision해야 한다. 임의 store adoption이나 기존 manifest 변경은 없다.

Non-RT Outbox writer는 기존 FileJournal을 유한 spool로 사용하고 commit된 Event만 준비한다.
Stop-and-wait ACK는 정확한 ordinal/stream/registry/Event CRC에만 진행한다. Inbox는 다음
ordinal을 durable commit한 뒤 ACK한다. 동일 ordinal/bytes는 중복, 다른 bytes나 Event ID를
다른 ordinal에 재사용하면 원본을 덮지 않고 sticky incomplete다. 미래 ordinal/잘못된 frame은
재시도를 기다리며 capacity·commit 실패·불완전 tail에 성공 ACK를 만들지 않는다.

ACK로 원본을 삭제하거나 capacity를 재사용하지 않는다. Sender cursor는 메모리이고 재시작 시
ordinal1부터 재전송한다. Receiver는 기존 durable prefix를 비교한다. 이 단계에는 compaction/
rotation·장기간 보존 용량 수용·실제 DDS/SOME-IP channel이나 live owner routing이 없다.
`healthy()`는 저장/집계 완전성으로, peer liveness/source freshness나 차량 readiness가 아니다.

## 실제 별도 프로세스 결과

원본은 이전 [기동 Release ACK 손실 fixture](../m9_startup_sources/README.md)의 Normal
`release/store` 19개 native Event다. 테스트는 **복사한 별도 source store**만 사용한다.
이전 원본·물리 evidence를 바꾸지 않는다. 원래 SD-4101 한 건·epoch2의 실제 Session/proof/
Passed를 새 검출이나 새 차량 실행으로 세지 않는다. 신규 Outbox record/drain과 오류 경계는
별도 단위 검사에서 시험한다. 이번 process fixture의 목적은 이미 commit된 native 이력의 복제다.

각 round는 새 sender process가 새 receiver process와 AF_UNIX SOCK_SEQPACKET으로 교환한다.
Source/replica ID6001·registry3이며 source와 세 replica prefix의 canonical bytes를 비교한다.

| Round | 실제 주입과 처리 | 보존 결과 |
| --- | --- | --- |
| 1 | Attempt1 ACK 수신 후, Startup Fault1 commit 뒤의 두 번째 ACK를 보내지 않고 receiver 종료 | Source cursor1 / replica durable2 / Fault Failed·count1 |
| 2 | 양쪽 새 process. 미래 ordinal19와 CRC 손상 frame은 ACK 없이 거절. ordinal1부터 replay해 첫2개 Duplicate ACK·나머지17개 최초 commit | Replica19, 원래 새 epoch proof의 source 이력 Passed·count1/generation1·미삭제 |
| 3 | 양쪽 또 새 process.19개 전체 Duplicate ACK | Replica19 그대로, 재시작 Unknown 유지·count1/generation1·미삭제 |

Sender/receiver PID6개를 원본 receipt log에 보존한다. 실제 datagram은81개(Data42/ACK39; Data 중 CRC 손상1개),
round1에서 commit 후 만들어졌으나 보내지 않은 ACK1개도 별도 보존했다. ACK timestamp를
control ACK나 physical completion으로 바꾸지 않는다. 새로 전달된 원래 source의 Passed 이력은
receiver 현재 물리 정상 판정이 아니다. 재시작 뒤 이미 committed된 중복은 ledger를 재평가하지 않는다.

독립 Python auditor는 canonical journal CRC/watermark·각 ordinal 원본 bytes·wire header/
CRC·ACK payload·process 분리·세 prefix·count/generation·Unknown을 확인한다. 잘못된 stream/
registry·미래 ACK·변조 payload·commit 전 ACK·중복 count 증가·replay 정상화·이력 삭제 등
10개 손상을 두 빌드에서 모두 거부했다. Normal/ASan의 wire82개와 store metadata/data12개,
총 **94개**가 byte 동일하다. 실제 PID가 다른 receipt CSV는 byte 동등성 분모에 넣지 않는다.

## 검증 분모와 실패 이력

- 최종 unit/logical **1170/1170**, 영향 ASan/UBSan **234/234**, 실패/skip0.
- 별도 `integration.transport` process fixture **Normal1/1·ASan1/1**. 일반/논리 분모와 합산하지 않는다.
- 기존 M4AsyncWall owner 회귀 **2/2**. 이번 전송의 wall latency/vehicle timing 보장이 아니다.
- 변경 production TU3개 clang-tidy warnings-as-errors / cppcheck warning·performance·portability 통과.
- BUILD_TESTING=OFF Release의 diagnostics_delivery 빌드·source fingerprint 검사2개 통과.
- 이전 M9 증거7묶음 SHA43/153/135/203/183/186/217개 유지. 과거 통과를 이번 재실행으로 세지 않는다.

최초 `probe.xml`은15개 중13개 통과·2개 BAD_COMMAND다. 빌드와 검사를 동시에 실행하여
link 중 실행 파일을 시작하지 못한 실행 관리 오류다. `probe.log.gz`/build 로그를 보존한다.
그 부분 실행의 시작 binary는 중간에 교체되어 exact hash를 확정할 수 없다. 그 뒤 빌드가
끝난 후보의 source/binary hash는 `probe-source/`이며 `probe-2.xml`은16/16이다.
이는15개 unit+초기 process fixture이며 sender는 같은 process에서 Outbox를 재구성했다.
최종 후보는 실제 새 sender process 및 receiver capacity 검사를 추가한 뒤 전부 다시 빌드했다.
최종1170/234와 별도 process1/1은 그 후보의 결과다. 최초 미실행2개를 통과 분모로 바꾸지 않는다.
`before-injection-*`와 `before-injection-source/`는 순서/손상을 실제 process에 추가 주입하기 전
통과 기록이며 최종 분모와 합산하지 않는다. 최종 후보에서는 미래 ordinal19와 CRC 손상을
실제 socket으로 먼저 보내고 원본 prefix2·무ACK를 확인했다. 그 뒤 전체 회귀와 전송·감사를
재실행했다. 기능 budget·판정 오차·기존 source 제어를 완화한 변경은 없다.

[results.json](results.json)은 최종 XML/감사 분모,
[manifest.json](manifest.json)은 base commit·source overlay·fingerprint·binary/tool/config와
원래 native fixture hash를 연결한다. CSV/log/config/inventory는 gzip, wire/store는 원본 bytes다.
Binary 자체 대신 hash를 보관한다. 새 shared thread/queue를 추가하지 않았으며 신규 TSan
실행을 주장하지 않는다. 기존 SPSC 경계의 근거를 유지한다.

## 재현

Base commit에 `sources/` overlay를 적용한다. 이전 `m9_startup_sources` fixture는 base에 있다.
Export 목적지는 존재하지 않는 새 경로다. 별도 transport label은 명시적으로 실행한다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 3
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --output-on-failure --parallel 3
STRATADRIVE_M9_DELIVERY_EVIDENCE="$PWD/build/delivery-export" ctest --test-dir build/m1-angle -R '^DiagnosticsDeliveryProcess\.' --output-on-failure
python3 -B tests/integration/diagnostics/audit_diagnostics_delivery.py build/delivery-export --mutations
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 3
ctest --test-dir build/m1-angle-sanitized -L '^(unit|integration.logical)$' -R 'Diagnostics|^NativePower\.|ControlRecoverySil|Session|M4' --output-on-failure --parallel 2
ctest --test-dir build/m1-angle-sanitized -R '^DiagnosticsDeliveryProcess\.' --output-on-failure
python3 -B docs/test-plan/evidence/m9_delivery_spool/verify-packaged.py
```

`verify-packaged.py`는 임시 경로에 압축을 풀어 보존한 auditor로 두 dataset/각10개 변조 거부를
확인한다. `SHA256SUMS`는 자기 자신을 제외한 묶음 전체를 보호한다.

후속은 실제 middleware 진단 channel·live owner routing·source 재시작 adoption·부하/보존
용량과 compaction 정책이다. 전체 M9/CARLA fault matrix·wall/Target·학습자 수용은 OPEN이다.
