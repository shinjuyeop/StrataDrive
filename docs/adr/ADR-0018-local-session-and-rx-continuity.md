# ADR-0018: 영속 Epoch 발급과 수신 연속성 오류

현재 배치: [ADR-0021](ADR-0021-central-coordination-and-parallel-zones.md). Epoch owner/배치는 2026-10-14 ADR-0021의 Central session으로 개정하고 library를 central/session으로 이동했다. 아래 zone/session/Front 설명은 당시 배치이며 발급 동작/record/FIFO/시험 결과는 유지한다.

Date: 2026-10-14. Status: **M1 local 구현·검사 / wire 채택·학습자 review PENDING**.
Owner: project owner. SYS-COM-002/003/004, SYS-SAFE-002와 EV 원천/재시작 계약에 연결한다.

## 문제와 결정

Fixture의 고정 Epoch만으로는 프로세스가 재시작한 뒤 이전 세션을 구분하는 발급 책임을
검증하지 못한다. SocketCAN dispatch budget만으로 application queue의 용량·overflow 정책도
정해지지 않는다. Continuity가 끊긴 뒤 새 packet으로 정상 수용을 재개하면 손실을 숨길 수 있다.

- `zone/session/EpochStore`를 Linux 로컬 startup 발급기로 구현한다. 최종 발급 owner는
  Front session coordinator이며 M1 harness가 이 library를 호출한다. Vehicle management/
  DDS handshake와 정상 주행의 physical health gate는 M4/M5의 별도 기능이다.
- 새 namespace의 explicit initialize만 저장소를 만든다. 정상 issue는 기존 record/lock을
  요구하고 손상·상실·busy·I/O 오류·uint32 소진 시 실패한다. 초기 record 0 이후 1부터
  발급하며 wrap/reset하지 않는다. 사용되지 못한 발급 번호도 다음 실행에서 건너뛴다.
- Stable lock file의 nonblocking `flock`, 임시 record의 file fsync → atomic rename →
  directory fsync를 사용하고 commit 이후에만 번호를 반환한다. 파일은 magic/version,
  uint32 Epoch와 complement를 담는다. 삭제/backup rollback은 자동 복구하지 않는다.
- Domain과 독립인 fixed-capacity FIFO를 common에 둔다. M1 fixture capacity 32,
  cycle당 ingress 8/dispatch 8, polling sleep 1 ms다. Queue full/kernel drop count 변화는
  backlog를 버리고 latch한다. 새 trusted Epoch로 queue/receiver를 초기화한다.
- Receiver의 ContinuityError는 current sample을 닫고 raw 진단 history를 보존한다.
  늦은 정상 메시지로 해제하지 않는다. Kernel-drop 복구는 깨끗한 새 socket도 필요하다.
  통신 monitor 상태를 차량 FAIL_SAFE/물리 보호 출력과 같은 것으로 표시하지 않는다.
- 재시작 시험에서 발견한 이전 Epoch의 P05 state 오염을 수정한다. CRC/canonical decode로
  확인한 다른 Epoch의 메시지는 현재 P05 check state에 반영하지 않는다. 기존 P05 wire와
  정상 같은-Epoch의 transport 검사 정책은 유지한다.

## 증거와 범위

Unit은 저장소 동시 프로세스 발급/손상/상실/소진/lock/I/O failure, FIFO/latch,
12개 receiver의 continuity loss와 새 Epoch·old counter를 검사한다.
기존 CAN runner는 실제 발급 번호를 trusted CLI/stdin으로 제공한다. Local vCAN은
기존 63개 + application/kernel overflow 24개 + process/session restart 2개를 검사한다.
Kernel fixture는 SO_RCVBUF 축소·ingress 중단·burst 뒤 실제 SO_RXQ_OVFL >0을 확인한다.
가상의 drop 값을 SocketCAN 결과로 표시하지 않는다.

실행 기록과 M1 technical exit 항목은 [M1 session/queue 안내](../learning/m1_session_queue.md)에 둔다.
Physical power-cut, storage rollback 방지, 실제 Target scheduling·차량 response, Front/Rear DDS,
full TC-COM/TC-SAFE/TC-EV는 별도다. Wire/학습자의 이해 review를 자동 PASS로 처리하지 않는다.

근거: [Linux fsync](https://man7.org/linux/man-pages/man2/fsync.2.html)의 directory 동기화,
[flock](https://man7.org/linux/man-pages/man2/flock.2.html)의 lock lifetime/nonblocking semantics,
[socket](https://man7.org/linux/man-pages/man7/socket.7.html)의 SO_RCVBUF/SO_RXQ_OVFL을 참고했다.
