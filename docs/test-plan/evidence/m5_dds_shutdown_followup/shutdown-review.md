# Full-RHC 종료 멈춤과 후속 종료 성공 비교

모두 Cyclone DDS **11.0.1/e54e991**, GCC/G++11.4.0, Ubuntu22.04.5,
Linux6.8.0-138-generic, i7-11700 Host다. normal SDK Release, sanitizer SDK Debug;
probe는 O1/g/frame-pointer/pthread/assertions, 필요한 sanitizer flag를 사용한다.
normal/ASan/TSan SDK SHA는 각각94768951…/2741644d…/96b8129d…로 동일하다.
전체 SHA·명령은 새 raw의 `review-identities.json` 및 각 원본 metadata에 있다.
빌드 최적화 차이 때문에 sanitizer 시간을 일반 성능으로 비교하지 않는다.

## 실행과 실제 관측

| 항목 | qualification v6 raw restart + 별도GDB | qualification v7 coordinated | operating-v1 raw restart | operating-v1 close-saturated |
| --- | --- | --- | --- | --- |
| 소스 identity |probe SHA14e26392…; GDB는 동일 v6 normal binary f65e162c… |probe fd5f44d8…; normal bb8d13c5… |probe8068031f…; normal adb86e4c… |raw restart와 같은 binary |
| CPU/정책/주기 |taskset1/1, OTHER/0,5ms; 과거 내부 thread readback 없음 |1/1, OTHER/0,5ms |1/2, OTHER/0,20ms |1/2, OTHER/0,20ms |
| 관측 |allocation unwind+finest+packet flush+private WHC; GDB6s interrupt 추가 |allocator/finest 끔; private snapshot·flush는 남음 |최소 관측, public QoS/status 및 전체 thread readback |동일; rejected가 양수가 될 때까지 status 조회 |
| 수신 중단/포화 |Zone20개 받은 뒤 take 중단. GDB trace에서 sequence29 반복/full8 RHC 추론; public rejected/lost는 미수집 |송신 quiesce 후150ms 동안 기존 take 계속, 이후 close |Zone20개 뒤 take 중단; close 직전 rejected0/lost0, 포화 확인 없음 |Zone20개 뒤 take 중단; rejected1/lost0을 실제 확인한 뒤 close |
| 상대 송신 |60개까지5ms 계속 송신; 이미 전송된 backlog도 있음. 무한 송신 시험 아님 |old42 quiesce; 새43은 종료 후 재개 |old42 송신은 계속, restart 후43. 같은42의 삭제 marker 뒤 송신은 아래 JSON 참조 |1.6s 동안 계속 송신, 삭제 marker에서 sender alive; 각 build에서 marker 뒤51회 추가 송신 |
| ACK 대기 |로컬 reply writer `wait_for_acks(100ms)` 후 participant delete; rc 미보존 |동일 |동일, rc 미보존 |동일, rc 미보존 |
| 객체 삭제 |participant 재귀 삭제에 맡김; reader close 진입은 GDB/trace 확인. writer→reader 직접 삭제 절차 아님 |동일 |동일 |동일 |
| 실제 대기 thread |main:reader close cond; recv:10ms full-RHC retry; gc:awake-vtime progress; dq.user/dq.builtins cond·tev timed wait |대기 stack 미수집; 반환만 관측 |대기 stack 미수집; 반환만 관측 |대기 stack 미수집; 반환만 관측 |
| 종료 결과 |v6 normal/ASan/TSan 모두 timeout FAIL. GDB별도1회 exit124/후속 readiness timeout; 정상API 반환 아님 |세 build 기능 통과; TSan FAIL |세 build 기능 통과·old42 거부; normal/ASan exit0, TSan 경고 FAIL |세 build API 반환 assertion/기능 통과; normal/ASan exit0, TSan66 FAIL |

실제 JSON·프로세스 exit·환경·동일 Epoch 송신 수는 [close-evidence.json](close-evidence.json).
최근 thread snapshot은 프로세스와 SDK 내부 thread 모두 해당 CPU mask/OTHER0을 확인했다.
CPU1/2는 다른 물리 코어이나 SMT 형제9/10과 IRQ/배경부하 격리는 없다.
두 netns/veth UDP, domain37, multicast off/unicast discovery, volatile RELIABLE,
KEEP_ALL/resources8/1/8/max_blocking_time0, app queue/take budget8은 공통이다.
v6 설정은 소스·command 근거이며 QoS **readback은 당시 없었다**. v1은 실제 readback이다.

v7은 송신 중지/소비 유지라는 더 좁은 계약이다. grace150ms가 독립적인 해결이라는
주장은 하지 않는다. v1은 배치·주기·관측·진단 코드가 함께 달라 과거 실패와의
단일 변수 비교가 아니다. 특히658562e의 writer/reader 삭제 flag 분리는 `partial`
전용 오류 수정이며, `restart`의20개 후 take 중단 경로를 고친 것이 아니다.
이번에 SDK runtime을 반복하지 않았고 과거 timeout은 **미재현·OPEN**이다.

## SDK 소스와 GDB의 연결

원본 `restart-gdb/zone-42.json`의 line13–28은 recv,67–76은 gc,
78–91은 main stack이다. `.trace` line1524는 user reader unlink를 기록한다.
sequence29는20개 소비+8개 대기 뒤 다음 메시지이며 같은 sample이 계속 재전달된다.
공개 rejected 계수는 없으므로 당시 queue occupancy를 직접 계측한 것으로 쓰지 않는다.

1. [`dds_reader_close`:58–70](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsc/src/dds_reader.c#L58)은 reader 제거를 요청하고 asleep으로 전환한 뒤 GC callback 완료를 기다린다. ACK wait가 포착된 멈춤 위치가 아니다.
2. [`ddsi_delete_reader`:1629–1641](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_endpoint.c#L1629)은 index unlink 후 GC를 enqueue한다. proxy 연결 제거와 status callback은1570–1612의 GC callback에 있다.
3. [`deliver_locally_fastpath/allinsync`:214–270](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_deliver_locally.c#L214)은 store 실패 시 재시도한다. [`remote_on_delivery_failure_fastpath`:2175–2187](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_receive.c#L2175)은 잠금을 잠시 풀지만 awake scope를 끝내지 않고10ms 후 TRY_AGAIN을 반환한다.
4. [`threads_vtime_check`/GC:77–99,192–214](https://github.com/eclipse-cyclonedds/cyclonedds/blob/e54e991/src/core/ddsi/src/ddsi_gc.c#L77)는 해당 awake thread의 진행 전에는 삭제 callback을 실행하지 않는다. reader interrupt도 이 pin에서 dummy다.

이 연결은 관측된 대기 고리를 설명하며 SDK liveness 문제를 우선 의심할 근거다.
모든 interleaving에서 영구 deadlock임을 입증하거나 새 성공의 정확한 탈출 분기를
확인한 것은 아니다. ACK wait return code와 API별 반환 시각도 원본에 없다.

## 종료 계약 판정

공식 [11.0.1 entity API](https://cyclonedds.io/docs/cyclonedds/11.0.1/api/entity.html#c.dds_delete)는 participant의 자식까지 삭제하는 현재 사용법을 지원한다.
문서에는 상대의 quiesce를 보장해야 한다는 삭제 전제나 full-RHC 삭제의 시한은 없다.
이 사실만으로 bounded 종료가 보장된다고 주장하지 않는다.
사용자 callback은 SDK 삭제를 재진입 호출하지 않고 context는 participant 반환 뒤까지
유지된다. 따라서 [2374의 listener 자기 대기](https://github.com/eclipse-cyclonedds/cyclonedds/issues/2374)는 현재 GDB와 다른 경로다.

협조하는 sender를 멈추고 take를 유지하는 계약은 이미 좁은 성공 근거가 있다.
상대가 계속 보내거나 죽거나 가득 찬 RHC에서 나가야 하는 계약을 그것으로 대체할 수
없다. API 삭제 순서 변경, Internal delivery knob, SDK 임의 패치에 대한 지원 근거가
없어 새 후보 시험은 NOT RUN이다. `SIGKILL`, GDB timeout, runner finally kill/wait는
관리 정리이며 DDS 정상 반환과 분리한다. Python timeout 분기는 실제 child 시험으로
검증됐지만 SDK 멈춤 해결과 무관하다.
