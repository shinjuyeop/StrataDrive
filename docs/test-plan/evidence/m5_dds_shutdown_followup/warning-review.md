# 64회 TSan 경고의 사용 경로 분류

대상은658562e가 보존한 operating-v1의58회+readiness-v2의6회다.
두 충돌 stack의 **전체 함수열 쌍**에서 주소/TID/소스 line 이동을 제외해32개 조합,
아래13개 경로군으로 묶었다. 독립 결함 수로 해석하지 않는다.
[index](warning-index.md)의 G번호를 [warnings.json](warnings.json)의 모든 W번호와
원본 archive member/1-based line/양쪽 원문 stack/log SHA로 추적할 수 있다.
파서는64회 및58+6 보존을 assertion으로 확인한다.

모두 OTHER0/CPU1+2/20ms/minimal 실행이다. private inspector 호출과 allocation hook은
꺼졌고 DDS 내부 write/take/discovery/ACK/삭제 경로에서 발생했다. main이 생성 stack에
있다는 이유로 애플리케이션이 해당 내부 포인터를 직접 공유했다고 분류하지 않는다.
예정 adapter 역시 participant/reader/writer를 만들고 public write/take/delete를 사용할
계획이므로, built-in discovery 경고도 실제 사용 경로에 포함된다.

## 분류와 조치

| 경로군·횟수 / G번호 | 충돌과 영향 경로 | 분류·근거·필요 조치 |
| --- | --- | --- |
| PUB-BUCKET5 /G06,18,21,27 |recv/tev의 `ddsrt_chh_lookup:414` vs resize allocation |**구체적 계측 해석 문제**. 초기화→fence→bucket pointer publication이 vendor no_sanitize load/store를 거친다. 이 가시성 공백을 확인했으나 해당 경고의 무해함 전체를 입증하지 않음. 지원되는 TSan 계측/해석 확인 필요 |
| PUB-GUID4 /G12,13,23,28 |`entity_guid_eq:67` vs local/proxy entity 생성 |**구체적 계측 해석 문제**. GUID 초기화 뒤 동일 hash publication을 통해 접근하는 immutable 필드 경로. 일반 mutable proxy 필드로 확대하지 않음. vendor publication 규약/지원 계측 확인 필요 |
| GC-BUCKET13 /G01,02,07,11,14,22 |`gc_buckets_cb` free vs recv/tev/builtins의 index lookup |**SDK 실제 사용 경로 미확정**. 과거 bucket awake-scope 시험은 관련성이 있지만 이 receive/event 호출들의 전체 수명을 대신 입증하지 않는다. lookup awake 범위와 실제 reclaim 의존성 확인 필요 |
| GC-WRITER14 /G04 |`gc_delete_writer` free vs `handle_AckNack` |**SDK 실제 사용 경로 미확정**. Writer 삭제와 원격 ACKNACK가 겹치는 정상 수명 경계. 과거 한 Writer scope 검증을 모든 ACK 분기로 확대하지 않음. 해당 access의 GC 의존성 확인 |
| GC-WHC5 /G03 |`whc_default_free` vs `ddsi_whc_free_deferred_free_list` |**SDK 실제 사용 경로 미확정**. ACK 처리의 잠금 밖 deferred-list 정리가 Writer-owned WHC를 참조한다. Writer/WHC와 deferred list 모두의 수명 보장 확인 |
| GC-MATCH6 /G19 |`ddsi_free_wr_prd_match` vs ACKNACK read |**SDK 실제 사용 경로 미확정**. Writer와 remote-reader match node가 별도 객체다. node removal/참조 유지가 같은 GC scope에 포함되는지 확인 |
| GC-MUTEX3 /G20 |entity mutex destroy vs ACKNACK unlock |**SDK 실제 사용 경로 미확정**. 단순 mutex 초기화 publication 경고와 구분. 마지막 unlock 뒤 GC가 destroy하는 실제 ordering 확인 |
| GC-PARTICIPANT1 /G05 |`ddsi_unref_participant` free vs InfoDST GUID lookup |**SDK 실제 사용 경로 미확정**. reader endpoint 정리가 parent의 마지막 ref를 내리는 경로. parent lookup의 quiescence까지 보장되는지 확인 |
| PUB-TKMAP5 /G09,10,15,16,17 |key equality/serdata eqkey vs tkmap/plist/builtin serdata 생성 |**SDK 실제 사용 경로 미확정**. hash publication 설명은 있으나 tkmap entry→serdata→key의 다단계 소유권까지 이번 자료로 닫을 수 없음. ref/unref·GC 범위를 묶어 질문 |
| PUB-PROXY3 /G24,29,31 |Heartbeat/Data/handle_regular vs proxy parent/flag 초기화 |**SDK 실제 사용 경로 미확정**. immutable GUID와 달리 parent 연결/flag 상태의 이후 변경까지 확인 필요. discovery→DATA 경로에 영향 |
| PUB-LEASE2 /G25,30 |`ddsi_lease_renew` vs `ddsi_lease_new/clone` |**SDK 실제 사용 경로 미확정**. 생성 publication뿐 아니라 renew/교체/만료 수명이 필요. heartbeat와 DATA 둘 다 재현됨 |
| PUB-MUTEX2 /G26,32 |recv mutex lock vs proxy writer allocation |**SDK 실제 사용 경로 미확정**. 초기화 가시성 후보이나 proxy pointer 수명이 미확정. GC-MUTEX의 destroy 경고와 합치지 않음 |
| SHARED-BITFIELD1 /G08 |retransmitting 쓰기 vs 잠금 밖 heartbeat suppression 읽기 |**SDK 실제 사용 경로 미확정, 실제 경합 유력**. 아래 source와 실제 binary의 동일 바이트 접근 근거. 우선 vendor 수정/판정 요청 |

우리 코드의 동기화/수명 결함으로 **확인된 것0**, 진단 전용 결함으로 **확인된 것0**,
SDK 실제 사용 경로 미확정55회, 구체적인 계측 가시성 공백9회다. 이9회도 경고를
없애거나 PASS로 바꾼 것이 아니다. **모든64회는 FAIL**, 메모리 gate는 CLOSED다.
ASan 성공·시각 선후·반복에서 미발생은 이 분류의 면제 근거가 아니다.

## SHARED-BITFIELD의 새 근거

원본 `cohort-v1/tsan-close-saturated/zone-42.stderr:146`은 GC thread의
`ddsi_writer_clear_retransmitting` 2-byte write와 tev의
`ddsi_heartbeat_xevent_cb` 1-byte read를 **같은0x7b580000197c**에서 보고한다.
해당 객체는 built-in Writer 생성 stack에 연결된다. 새 진단이 테스트 flag를 켠
것이 아니며 SDK heartbeat가 flag의 false 값을 읽는 것만으로도 이 경로에 진입한다.

- [`ddsi_endpoint.h`:85–94](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/include/dds/ddsi/ddsi_endpoint.h#L85): `retransmitting`과 `test_suppress_heartbeat`는 연속 bitfield다.
- [`ddsi_proxy_endpoint.c`:810–820](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_proxy_endpoint.c#L810): writer lock 안에서 retransmitting을 지운다.
- [`ddsi_hbcontrol.c`:590–600](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_hbcontrol.c#L590): writer lock을 푼 다음 suppression bit를 읽는다.
- 실제 실행된 TSan library SHA96b8129d…의 disassembly: clear는 offset`0x17c`를 byte load/`and0xf7`/byte store한다. heartbeat도 같은 offset을 byte load한다. TSan write2/read1 계측이 더 큰 단위를 표시하더라도 실제 메모리 접근 바이트가 겹친다. `raw.tar.gz`의 두 `.asm`과 `disassembly.json`에 명령/해시를 보존했다.

이는 생성/GC 가시성만의 문제가 아니라 살아 있는 Writer의 인접 bitfield 접근 문제라는
강한 근거다. 관측된 경합의 기능적 피해와 vendor가 지원하는 수정은 아직 미확정이다.
현재 built-in Writer가 그 경로를 실행하므로 진단용 flag라는 이름만으로 제외할 수 없다.
이 유형을 일반 annotation이나 모든 atomic의 교체로 숨기지 않았다.

## 계측 해석의 좁은 범위와 공식 근거

pin의 `hopscotch.c:477–498,532–534`는 초기화/fence 후 포인터를 게시하고,
`410–416,347–400`은 이를 읽는다. `entity.c:56–70`에서 GUID를 먼저 초기화한다.
`ddsrt/atomics/gcc.h`의 관련 load/store는 volatile 접근과 `no_sanitize("thread")`를
사용한다. 그래서 일반 TSan acquire/release edge와 같지 않다는 구체적 근거가 있다.
정확한 source SHA/발췌는 새 raw의 `source-review.json`에 있다. 이 설명을55회 전체,
ARM64/Jetson 또는 모든 mutable 필드로 확대하지 않는다.

공식 [1252 답변](https://github.com/eclipse-cyclonedds/cyclonedds/issues/1252#issuecomment-1103780286)과
[2039 답변](https://github.com/eclipse-cyclonedds/cyclonedds/issues/2039#issuecomment-2196511627)은
hash/GC와 TSan의 해석 차이를 설명하면서 실제 경합을 숨길 위험도 지적한다.
[1417 설계 설명](https://github.com/eclipse-cyclonedds/cyclonedds/issues/1417#issuecomment-1256352842)의
awake/vtime 기반 지연 해제를 위 경로별로 확인해야 한다.
[PR2162](https://github.com/eclipse-cyclonedds/cyclonedds/pull/2162)는 atomic·bitfield를 다루는
관련 작업이지만 **closed/unmerged**다. 그 proxy-reader 사례가 이 Writer의 같은
결함이라는 확인도 없으므로 패치를 가져오지 않는다. 지원되는 최소 변경과 경로별
판정을 문의하고, 답변 전에는 같은 SDK 시험을 반복하지 않는다.
