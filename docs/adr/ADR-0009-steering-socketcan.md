# ADR-0009: Steering codec와 Linux SocketCAN 연결

Status: **2026-10-12 Host vCAN 구현·시험 완료 / 학습자 review PENDING**.
관련: [수신부 결정](ADR-0008-steering-receiver.md), [frame 계약](../icd/steering_frame_draft.md),
TBD-01/04/11. Reference v0.1의 requirement나 wire schema를 변경하지 않는다.

## 문제

메모리 안에서 검증한 SteeringFrame을 실제 CAN socket으로 전달하는 코드가 없었다.
수신 종류/ID flags/길이를 정규화하면 잘못된 입력을 정상 Steering frame으로 바꿀 수 있다.
Queue를 무한히 비우는 loop는 반복 frame 중 timeout 검사를 늦출 수 있다.

## 결정

- `interfaces/common/`: 조향과 독립인 P05 Protect/Check.
- `interfaces/steering/`: angle/frame codec과 application receiver. 기존 파일의 내용은 유지한다.
- `interfaces/socketcan/`: Linux 전용 socket 소유·I/O와 SteeringFrame 변환.

[Endpoint](../../interfaces/socketcan/socketcan_endpoint.hpp)는 RAII로 socket을 닫고,
nonblocking/CLOEXEC, CAN_RAW_FD_FRAMES, interface MTU=72 검사와 RX prefilter를 적용한다.
RX용 ID는 하위 11 bit만 filter하고 EFF/RTR flag를 지우지 않는다. 최종 envelope 판정은
SteeringReceiver가 한다. TX endpoint는 수신 filter를 비운다. 별도 process 사이 전달에는
Linux의 기본 local loopback을 사용한다.

Transport의 Frame은 64-byte 저장 공간을 가진다. `recvmsg`가 반환한 ABI 크기로 Classical과
FD를 구분한다. Classical padding을 FD flag로 해석하지 않는다. 조향 표현으로 변환할 때
실제 ID/FD/flags/length를 유지하고 payload의 앞 32 bytes만 복사한다. 길이 64를 32로 고치지 않는다.
이는 [Linux SocketCAN 문서](https://docs.kernel.org/networking/can.html)의 두 ABI 크기/길이 구분을 따른다.

수신 queue가 비면 nullopt, I/O/잘린 ABI frame은 exception으로 보고한다.
`SO_RXQ_OVFL`의 누적 drop 수를 전달하며 demo는 nonzero drop을 continuity fault로 보고 종료한다.
이 값은 socket 생성 이후 누적된 drop 수이며 실제 buffer 크기를 8개로 만드는 설정이 아니다.
근거는 [Linux socket(7)](https://www.man7.org/linux/man-pages/man7/socket.7.html)이다.
Drop을 강제로 발생시킨 fault 시험과 kernel buffer budget 확정은 후속 작업이다.

TX/RX는 독립 C++ process이며 source와 receive time은 같은 Linux CLOCK_MONOTONIC이다.
Python fixture가 명시적으로 Epoch=1을 전달하고 양쪽 socket ready를 확인한다. Receiver의
`start_session` 완료 후 sender를 시작하여 first-frame acquisition 기점을 정한다.
이 handshake는 시험 시작용이며 영속 Epoch coordinator, 서로 다른 time namespace나
Host–Target clock 동기화를 구현한 것은 아니다. Epoch=1 재사용은 격리된 새 시험에서만 사용한다.

RX demo는 한 cycle 최대 8개를 처리하고 `current_sample(now)`로 timeout/source age를 검사한 뒤
1 ms를 쉰다. 별도 application queue는 없으며 Linux socket queue를 사용한다.
Kernel queue가 8개라는 주장은 하지 않는다. 로깅 비용도 있으므로 이것을 production task의
10 ms deadline/priority/affinity 설계나 hard real-time 보장으로 사용하지 않는다.
Timeout 이후에도 관측을 이어가 late frame이 자동 복구하지 않는지 확인한다.
I/O/overflow 종료는 demo의 오류 처리이며 차량 FAIL_SAFE output은 후속 vECU에서 구현한다.

정리 후 TX/RX/helper/Python runner는 `tests/integration/can/`에 모았다.
Participant는 `BUILD_TESTING=ON`일 때만 build한다. 메모리 실행 예제 4개는
`tools/actuator_demo.cpp`의 angle/frame/e2e/receiver 명령으로 합쳤다.
수신 trace는 cycle마다 한 번 flush하고, runner는 participant가 실패해도 수집한 stdout/stderr를 남긴다.
Frame 검사/Counter/수용/timeout 정책은 유지한다. 추가 기준은 [품질 정책](../quality_policy.md#코드예제시험-배치)을 따른다.

위 경로는 2026-10-13 [Brake 확장](ADR-0010-brake-wire-codec.md) 후 이름이다.
당시 `steering_demo`/Steering 전용 integration 배치를 actuator 공통 배치로 확장했다.

## 증거와 다음 범위

[실행 기록](../learning/m1_steering_socketcan.md)에 unit 48개, normal/ASan·UBSan 각각
vCAN 8개 case, compiler/static analysis와 DBC 교차 검증을 기록했다.
Command=0.2 rad, Actual=0.15 rad의 독립 fixture를 사용한다. Actual은 command echo나
dynamics 결과가 아니다. Brake/Drive four-frame 확장, 영속 session, queue overflow 주입,
vECU physical response와 차량 TC는 남아 있다.
