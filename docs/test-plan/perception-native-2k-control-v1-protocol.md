# Native 2K control boundary 기능 검증 기준

이 단계는 Host component/보존 기록 replay/논리 SIL이다. 새 CARLA 촬영·품질 평가·속도 튜닝을
수행하지 않는다. [계약](../interfaces/perception-native-2k-control-v1.md)을 기준으로 최종 소스를
묶은 뒤 아래 검사를 재실행한다. 개발 중 테스트 수정과 최종 source archive 검증을 구분한다.

## TC-PER-085 — 원본 기한과 수신 타입

- 고정2K/모델/threshold/class/box/최대100개, 실제 INIT와 두 clock을 검사한다.
- Source/receipt의 정확한100ms 경계, 미래·overflow·변조·역행·중복·오래된 결과 복원을 거절한다.
- Atomic export는 원래 packet receipt를 유지한다. 느린 backend 동안 state/read가 독립 진행하고
  late·exception·close·새 session 뒤의 in-flight 완료가 유효 결과로 나오지 않는다.
- 정상 empty와 unavailable을 구분한다. 반복 조회는 입력/이력을 갱신하지 않는다.

## TC-PER-086 — 추적과 보존된 실측 결과 재생

- Class별 IoU≥0.3, 동률 결정, one-to-one, 실제10개 history, 공백 reset을 검사한다.
- 기존 `m10_latency_2k_v1`의 baseline/tensor/balanced **전 조건**을 재생한다. 사용한 report를
  SHA로 고정하고 전체 consumer 분모를 유지한다. 아직 actual state가 없는 첫 조회는
  unavailable로 별도 계수하며 가상의 시각을 만들어 C++에 넣지 않는다.
- 유효 결과는 원본 model-call/result/receipt와 일치해야 하고, C++의 가용성은 모든 유효 state
  조회에서 원본과 같아야 한다. 기존 Python ImageTracker를 원래640 canonical 좌표로 실행한
  이력과2K C++ 이력을 비교한다. Track ID의 세션 내 재사용도 거절한다.
- Replay PASS는 원본 결과의 재현이다. 기존 balanced의 live FAIL이나 품질 판정을 바꾸지 않는다.
- 최소25개 semantic 변조와5개 text parser 변조, 원래 wall expiry, gap 후 재생 거절을 확인한다.

## TC-PER-087 — 보호·Actual·명시적 복구

기존 supervised speed/PI/배분·Central/Front/Rear/Leaf·P05 feedback·물리 owner를 그대로
사용하는9초 logical 시나리오다. Camera typed fixture20Hz와 보호 monitor50Hz는 논리 시간의
시험 입력 주기이며 실제 카메라 또는 CPU deadline 달성 수치가 아니다.

1. Shadow 공급 중단: 정상 제어 지속. 미연결 실행과 명령의 원천/expiry·물리 torque/brake/speed/energy 동일.
2. Required 정상 empty 입력: 정상 제어 지속. Empty를 clear road 또는 허가 발행으로 해석하지 않음.
3. Camera3–4초 중단: original expiry 후 첫20ms monitor에서 보호. 기한을 늘리거나 새 grace를 주지 않음.
4. 해상도 오류, 원래 receipt 만료, 잘못된 epoch, 명시적 unavailable: 각각 보호.
5. 동일 release 전 오류→정상 입력: first loss와 latch 보존.
6. Camera 복원 뒤 새 INIT 없음: available은 회복되지만 정상 권한은 계속 닫힘.
7. 별도 복구 조건에서6.5초 명시적 global INIT: 더 큰 epoch의 실제 release/권한/정상 Actual로 복구.

주행 중 고장 전 정상 wheel을 확인한다. 보호 요청 release에서 RunGate가 닫히고,
기존 Zone 양쪽 ACK는 검출+100ms 이내여야 한다. 실제 신규·fresh torque≤0.1Nm 및
brake≥0.9MPa 관측은 검출+500ms 이내여야 한다. 이는 선언한 논리 fixture의 actuator 검사이며
차량 정차 시간·거리 또는 wall latency 수용이 아니다. 복구 후 첫 고장 기록을 임의로 갱신하지 않는다.

## 회귀·증거

새 C++ receiver/SIL을 normal 및 ASan+UBSan으로 검사하고 기존640 receiver/경계,
speed Supervisor/coordinator 회귀와 전체 perception Python 테스트를 실행한다.
최종 소스와 fixture/report를 archive/hash로 보존하고 별도 경로에서 새 C++ build·실행과
Python import/test·보존 기록 replay를 확인한다. 외부 문서 변경을 함께 커밋하지 않는다.
Source archive는 이 기능 검증의 최종 재현 묶음이며 이전 live 실행의 사전 동결을 소급해서 주장하지 않는다.
