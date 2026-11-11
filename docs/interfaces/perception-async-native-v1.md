# Native4K 비동기 인지 경계

2026-11-11. [사용자 합의와 사전 기준](../test-plan/perception-async-native-v1-protocol.md)에 따라
영상 인지와 차량 상태 수신·제어를 독립 실행한다. ROS 2/Gazebo는 이 구조의 설명 예시이며,
현재 프로젝트의 SOME/IP·Central–Zone–Leaf·Actual 반환 경로를 유지한다.

## 실행과 데이터 소유권

- World/state owner가 실제 snapshot의 frame/source를 관측 clock에 전달한다. 인지 owner는
  world tick을 실행하지 않으며 tick owner가 인지 완료를 기다리는 barrier를 추가하지 않는다.
- SDK callback은3840×2304 BGRA layout·원천 identity를 검사하고 immutable packet을 넘긴다.
  Mutable buffer copy도 mailbox lock 밖에서 수행한다. Callback에서 이미지 검사·변환·추론·
  저장을 하지 않는다. Native live 연결 때 sensor FOV/calibration·취득 주기는 별도로 검증해야 한다.
- `AsyncNativePerception`은 실행 중1개·대기1개·current1개만 소유한다. 대기 packet은 최신으로
  교체하고 overwrite를 기록한다. BGRA→RGB·원본 영상 검사·PIL960 resize·고정 CUDA 모델·
  완성 decoder는 인지 thread에서 실행한다. Backend 초기화는 producer enable 전에 끝낸다.
- Consumer는 `snapshot()`으로 immutable 결과를 조회한다. `drain()`·`close()`·모델 호출을
  제어 job에서 실행하지 않는다. 느린 backend와 독립 실행해도 CPU/GPU·GIL·OS 자원 경쟁이나
  실제 deadline 충족까지 자동으로 보장되지는 않는다.

Source 취득+100ms와 callback entry receipt+100ms를 모두 exclusive로 검사한다. Queuing·
callback copy·색상 변환·전처리·추론이 receipt budget에 포함된다. SDK 전송과 callback 진입 전
copy는 별도다. 반복 조회나 새 envelope는 원래 취득 시각·expiry를 갱신하지 않는다.

두 clock은 직접 차감하지 않는다. Simulation pause 때에도 monotonic wall 만료가 작동한다.
Session 변경·입력 오류·close는 이전 in-flight 결과가 availability를 복원하지 못하게 한다.
Clock regression은 latch한다. Backend가 멈추지 않으면 bounded close는 false를 반환한다.

`NativeResult`는 별도 schema/candidate/모델 SHA와 **3840×2304 native pixel box**다.
기존 S/640 `PerceptionResult`·C++ receiver와 호환되는 것으로 위장하지 않는다.
Unavailable은 빈 검출·clear road·주행 허가가 아니다. 실제 planner 연결 때에는 원래 영상 시각의
metric world model과 fusion이 필요하며,2D box를 직접 차량 command로 변환하지 않는다.
여러 입력을 합칠 때 가장 오래된 dependency를 보존하며 기존 wheel/command 기한을 늘리지 않는다.

## 현재 검증 범위

[실행 기록](../test-plan/evidence/m10_async_native_v1/README.md)은 이미 소비한 개발3장 BGRA를
재생한 component 시험이다. State producer100Hz·observational control consumer50Hz·
camera offer20Hz와 CUDA owner를 독립 thread로 실행했다. 이 consumer는 실제 차량 제어기가 아니다.
실제 CARLA renderer·SDK ingress·Zone/Leaf·차량 운동/보호를 연결한 시험도 아니다.

정상6초에서 state600/control300/camera120개 job을 관측했다. 인지43개 완료는 모두100ms
기한을 초과해 **publication0**이었다. Callback→backend return P95는202.68ms이고,
모델 추론 자체 P95는20.23ms다. 비동기 분리는 동작하지만 현재4K CPU 변환·전처리 비용으로
유효한 인지를 공급하지 못했다. 이 결과를50/100Hz 실제 제어 또는 live 인지20Hz 수용으로 올리지 않는다.

다음은 PC의 native 변환·전처리 비용 개선을 별도 version으로 검증하고, 실제 카메라·기존 제어
경로 연결에서 수신/적용 시각·원천 age·누락·보호 동작을 각각 측정하는 것이다.
CARLA의 고정 step/단일 tick owner와 노드의 비동기 실행은 함께 사용할 수 있다.
Thor/Orin 각각의 전체 stack 배포·보드 최적화는 이후 단계다.
