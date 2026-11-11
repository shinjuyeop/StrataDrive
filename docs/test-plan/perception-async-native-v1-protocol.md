# M10 native4K 비동기 component 검증 V1

2026-11-11 사용자 합의: 차량 상태·제어와 영상 인지는 독립 실행하며 원래 취득 시각과
유효성을 유지한다. ROS 2/Gazebo는 구조 설명의 예시다. 이번에는 기존 SOME/IP·CARLA·
Zone/Leaf 반환 경로를 바꾸거나 ROS로 이관하지 않는다.

## 변경과 시간 계약

[프로파일](../../profiles/perception-async-native-v1.json)의 native3840×2304/모델960·
D-FINE-M FP32/BASIC·class vector를 유지한다. 기존 S/C++640와 모든 동결 소스는 수정하지 않는다.
새 `AsyncNativePerception`은 callback의 immutable BGRA를 latest1 slot에 받고 별도 owner에서
색상 변환·영상 검사·resize·CUDA 추론·완성 decoder를 수행한다. Snapshot에는 native pixel box와
별도 schema/candidate/model identity를 사용하며 기존640 receiver로 위장하지 않는다.

Mailbox lock 안에서 대용량 copy·색상 변환·모델 호출을 하지 않는다. Backend는 한 번에1개이며
pending1/current1이다. 과부하는 pending을 최신으로 대체하고 집계한다. 실행 중 call을 강제로
취소하거나 새 입력이 왔다는 이유만으로 정상 완료를 전부 폐기하지 않는다. 새 session·입력 오류·
명시적 invalidate·close는 generation을 바꾸어 이전 완료가 가용성을 복원하지 못하게 한다.

Source 취득+100ms와 callback 진입 receipt+100ms를 모두 exclusive로 검사한다. 두 clock은
서로 차감하지 않는다. 결과 완성·재조회로 취득 시각이나 유효기간을 갱신하지 않는다.
Clock regression은 latch하며 새 clock/worker가 필요하다. Backend hang 때 close timeout을
정상 종료로 보고하지 않는다. 인지 unavailable을 빈 도로·제어 허가로 바꾸지 않는다.

## 사전 실행 분모

실제 CUDA 모델을 각 조건마다 새로 초기화하고 `none/slow/exception/blocked`를 각각6초 실행한다.
원래 cold call을 포함하며 준비·초기화 비용은 별도 기록한다. `slow`는 모든 호출에150ms 대기,
`exception`은 모든 호출 실패, `blocked`는 첫 backend를 주기 작업이 모두 끝날 때까지 멈춘다.
입력·완료·거절·overwrite·late·error·cancel·모든 주기 job/누락 슬롯을 보존한다. 실패 실행은
삭제하거나 덮어쓰지 않으며 수정 후에는 별도 attempt 경로를 쓴다.

Media는 앞선4K `pilot-6-01`의 이미 소비한 개발3장 original BGRA만 사용한다. 원본 frame/source/
SHA와 새 playback identity를 모두 기록한다. GT·보류·새 촬영·새 품질 점수는 사용하지 않는다.
미래 RGB 제외5629개는 그대로다. 압축 해제는 측정 전에 끝내며 실제 renderer·SDK transport와
callback 진입 전 copy는 이 실험에서 측정하지 않는다.

독립 state owner는10ms logical tick을 관측 clock에 전달하고, camera owner는50ms마다 최신
state frame에 media를 제공하며, observational control consumer는20ms마다 state/result를 조회한다.
각 thread의 실제 wall 시각·주기 누락·관측 Hz를 기록한다. 누락 시 catch-up 실행을 하지 않는다.
이 consumer는 실제 vehicle controller·Zone·Leaf/Actual에 연결되지 않으며 actuation을 출력하지 않는다.

## Component 판정

- Offered=accepted+rejected, accepted=started+overwritten+cancelled+expired pending,
  started=completed, completed=published+late+errors+obsolete가 유한 종료 시 일치한다.
- 각 backend 실행 구간 안에서 state/control job이 모두 실제 관측된다. `blocked`에서는 모든
  주기 owner가 첫 backend의 해제 전에 끝나야 한다. 한 결과를 기다리는 barrier를 두지 않는다.
- 정상 조건에 backend error·clock fault·owner error가 없어야 한다. 정상 조건의 fresh 결과가
  0개여도 architecture component만 판정하고, `fresh_output_observed=false`를 명시한다.
- Slow/blocked는 overwrite와 late를 관측하고 publication0이어야 한다. Exception은 모든 완료가
  error이고 publication0이다. 모든 consumed 결과는 동일 입력/call의 schema·원본 identity·
  native box와 일치하며 원래 source/receipt deadline 안에 조회된 것이어야 한다.
- 중단·session·clock·입력 오류·pending 만료 경계는 결정론적 단위 테스트로 별도 검사한다.

이 PASS는 비동기 **component 동작**이다. 실제50/100Hz 제어 수용, 인지20Hz, 실차/Target·
ROS/Gazebo/CARLA live 연결, 주행 안전·새 독립 품질 수용을 뜻하지 않는다. 후속은 실제 카메라와
기존 제어 경로를 연결하여 source age·수신·적용 deadline·원래 보호 동작을 함께 검증하는 것이다.
