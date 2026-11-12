# Native 2K 수신·추적·보호 Host 계약

2026-11-12. `m10-native-2k-boundary-v1`은 기존 D-FINE-M960 FP32 / 2560×1536
개발 경로의 선택형 기능 연결이다. [기존 지연 비교](../test-plan/evidence/m10_latency_2k_v1/README.md)의
모델·전처리·임계값·원래100ms 기한을 유지한다. S/640과4K 타입, 기존 기본 실행기는 변경하지 않는다.

## 원본 시각을 보존하는 경계

`BoundaryWorldPerception`은 기존 준비·추론 owner를 상속한다. `boundary_observation()`은
같은 잠금 안에서 현재 immutable `NativeResult`, 원래 callback receipt, wall expiry,
실제 관측 state와 read 시각을 함께 선택한다. 수신 시각은 기존 owner가 packet에서 저장했던
expiry−100ms로 복원한다. 완료·발행·조회 시각으로 바꾸지 않는다. Consumer에서 추론·영상 변환·
trace 탐색·저장·drain을 실행하지 않는다. 이 Python API 자체가 차량 제어 주기를 보장하지는 않는다.

`Native2kFrame`은 별도 C++ 타입이다. Schema/candidate 숫자1은 각각
`m10-async-native-2k-perception-v1` / `dfine-m-960-car-v1-camera2k-v1`의 검증된 변환을 의미한다.
모델 SHA는 `b865ac0f2597afd6fcb9e887ed7738e98e7690ecb4d5cebf42724a3e6b384884`,
camera/calibration은1/1, box는 원본2K의 half-open pixel 좌표다. Class0/1/2/3/5/7의
최소 score는 각각0.6/0.4/0.6/0.5/0.5/0.6이며,100개 이하의 모든 검출을 검사한다.
정상 빈 검출은 available이지만 장애물이 없다는 보장은 아니다.

신뢰된 INIT가 epoch, source clock, monotonic wall clock, 두 enable 시각을 공급한다.
영상이 세션을 시작하지 않는다. 수신자는 다음을 매 수신·조회에서 독립 검사한다.

- 원래 촬영+100ms와 원래 callback receipt+100ms의 **exclusive** 만료. Overflow, 미래 시각,
  세션 이전 취득, clock/model/calibration 불일치, 변경한 expiry를 거절한다.
- 독립 state owner가 공급한 실제 state receipt의 wall age<100ms. Source와 wall을 서로 빼지 않는다.
- 두 현재 시각과 state receipt의 역행은 latch한다. 거절된 INIT는 현재 상태를 바꾸지 않는다.
- 새 수신은 frame/source가 증가해야 한다. 같은 결과의 반복 조회는 `snapshot()`이며 새 수신이 아니다.
  오류·명시적 unavailable·만료는 현재 결과와 active track을 지운다. 마지막 수신 watermark는 남는다.

동일 Host에서 원래 monotonic 좌표를 공유하는 경계다. 다른 PC/Jetson의 wall 시각을 직접
비교할 수 없으며 clock mapping과 전송 지연/단절 계약은 배포 통합 때 별도로 필요하다.
현재 `frame_line`/`ReplayCursor`/`perception_2k_replay`는 원본 숫자를 손실 없이 전달하는
**offline fixture adapter**다. Production IPC 또는 SOME/IP 서비스 구현으로 표시하지 않는다.

## 추적

수신된 새 프레임에서만 같은 class끼리 greedy IoU≥0.3 매칭한다. IoU 동률은 기존 track ID,
검출 순서로 결정하고 한 track/검출은 한 번만 배정한다. 최근10개 실제 관측만 보존한다.
관측마다 원래 frame/source/box/score가 남고, 반복 poll은 history를 추가하지 않는다.

Empty/invalid/unavailable/expiry 또는100ms를 넘는 source/receipt gap은 연속성을 끊는다.
다음 프레임 수신 시 이전 결과가 이미 만료됐다면 조회 사이의 공백도 반영한다. Session 안에서
새 ID는 단조 증가하며 새 INIT에서만 초기화한다. 따라서 현재 약48%의 fresh 공급에서는
history가 자주 끊길 수 있다. 만료된 track의 위치를 예측하거나 계속 유효하게 유지하지 않는다.
이는 영상 좌표의 이력이며 거리·상대 속도·충돌 위험·metric world model이 아니다.

## 보호 연결과 복구

`Native2kControl`은 수신부를 소유하며, 같은 C++ control owner가 기존 coordinator release 전에
`release(now, coordinator)`를 호출한다. 모델이나 Python callback에서 coordinator를 호출하지 않는다.

| 모드 | unavailable 처리 | 정상 권한 |
| --- | --- | --- |
| `Shadow` (기본) | 결과와 최초 상실 원인/두 시각 기록 | Coordinator를 변경하지 않음 |
| `Required` (명시적 선택) | 원래 조건으로 즉시 latch, 다음 control release에서 기존 `request_protection` 호출 | 스스로 권한을 열지 않음 |

Required에서 수신 오류가 난 뒤 같은 release 전에 유효 결과가 도착해도 latch가 남는다.
공급이 회복돼 available=true가 되어도 정상 주행을 재허용하지 않는다. 이미 수용된 더 큰
**실제 global INIT**를 caller가 다시 연결해야 한다. 가짜 perception-only epoch 교체는 허용된
운영 절차가 아니다. 새 세션 후에도 기존 RunLease·permission·BMS·wheel·배분 검사를 모두 거친다.
보호 요청·Zone ACK·actuator Actual은 서로 다른 사건이며, ACK를 물리 정차로 해석하지 않는다.

이 단계의 기존 속도 목표와 명령은 계속 신뢰된 차량 상태/고정 SIL 경로에서 나온다.
2D 검출로 목표 속도나 토크를 계산하지 않으며, 기존 wheel/command 기한을 늘리지 않는다.
이 보호 monitor가 영상 기반 planner의 dependency 전달을 대신하지는 않는다. 앞으로 영상에서
목표/명령을 도출할 때에는 fusion의 가장 오래된 원천과 가장 이른 expiry를 끝까지 전달해야 한다.
기존 coordinator의 보호 진단은 사용하지만 새 perception 전용 DTC/서비스 복구 심사는 후속이다.

## 검증 범위와 다음 연결

[검증 기준](../test-plan/perception-native-2k-control-v1-protocol.md)과
[실행 근거](../test-plan/evidence/m10_native_2k_control_v1/README.md)를 따른다.
Python owner의 지연·오류·세션 변경, C++의 두 clock/추적, 보존된 실제 카메라 결과의 재생,
synthetic2K typed 입력을 사용하는 기존8-role 논리 SIL을 구분한다. SIL은 원본 P05 Actual의
취득 시각·토크·제동을 검사한다. 영상 모델에서 실제 CARLA 차량까지 live 연결한 결과가 아니다.

다음은 이 경계를 실제 control owner의 유한 mailbox/IPC에 연결한 CARLA shadow 실행이다.
먼저 수신 비용·drop·source/receipt/state age와 보호 요청/Actual을 같은 실행에서 기록한다.
실측 가용성 공백이 있으므로 Required를 기본 주행 모드로 승격하지 않는다. 독립 품질,
장시간 wall 실시간성, metric fusion/planner, Thor/Orin NX 각각의 배포는 계속 OPEN이다.

후속 실제 owner 연결은 [same-host shadow IPC](perception-shadow-ipc-v1.md)를 따른다.
원래 Host Required 검증을 실제 wall 제어 수용으로 확대하지 않는다.
