# M10 Rider 정답 v2의 사전 고정 평가

2026-11-07. [Plan v2](../../profiles/perception-quality-plan-v2.json),
[protocol v2](../../profiles/perception-quality-protocol-v2.json), 코드·모델·이전 영상 제외 목록을
새 수집/추론 전에 freeze한다. [V1](perception-quality-protocol.md)의 원본과 실패는 그대로 보존한다.
이번 비교는 Host engineering gate이며 전체 ODD·안전·주행·live20Hz 수용이 아니다.

## 정답과 평가 단위

- Person은 CARLA Pedestrians12와 Rider13을 같은 class0으로 매핑한다. 같은 instance의
  두 person 태그는 한 box로 합치고, bicycle/motorcycle은 class1/3의 별도 box로 유지한다.
- 정답은 실제 semantic/instance mask의 tight visible box다. 16bit instance ID와 계획한 actor를
  대조한다. 영상에 보이지 않는 물체 부분을 GT/actor bounding box로 추정하여 채우지 않는다.
- 포함 조건은 기존 최소25 visible pixel·box side4pixel이다. 미달 객체와 완전 비가시 target은
  각각 excluded와 coverage 결손으로 보고하며 분모에서 몰래 삭제하지 않는다.
- 주 판정은 같은 class·IoU≥0.5의 score 순서 일대일 matching이다. unmatched prediction은
  모두 FP다. 작은 excluded 객체에 맞는 prediction을 빼는 값은 **별도 진단값**이며 gate에는
  적용하지 않는다. 이 진단도 included 우선, excluded당 prediction 최대1개로 제한한다.
- 가려진 정답의80% 이상을 포함해도 IoU0.5에 미달한 prediction은 별도 diagnostic으로만 기록한다.
  TP로 바꾸거나 amodal 정확도라고 부르지 않는다. `occluded`는 계획상 가림 배치이며 실측 가림률이 아니다.

## 새 수집과 provenance

Town03_Opt/Epic/postprocess on/RGB640×384/FOV90, world10ms와 매 tick 센서를 유지한다.
Partition별81배치(6class×3기상×4거리/가림=72, negative3·차량 중첩3·VRU 중첩3)이며
40tick settling 뒤10tick 중5번째 원본 RGB/instance pair를 선택한다. Actor physics는 꺼진다.

Camera spawn2/3을 사용하고, 개발은거리13/25/38m·가림17m, 보류는15/27/40m·가림19m다.
이전 far42/48m와 범위가 다르므로 수치를 직접 합산해 개선으로 주장하지 않는다. 이전 원거리
자전거가25pixel 기준에 미달했던 문제를 반영해 v2는 **35m 이상 범위의 유효 표본 coverage**를
새로 고정한다. 기존25pixel 하한이나 정확도 threshold를 낮추지 않는다.
Car/person/bicycle/motorcycle/truck asset과 방향도 계획에서 고정한다. Bus와 같은 Town은 공유한다.
새 frame/pose 표본이며 완전히 새로운 asset/지리/ODD 일반화를 뜻하지 않는다.

객체 생성 직후 SDK cache의0좌표를 기록하지 않도록, settling과 capture tick 후의 실제 pose를
읽는다. 계획 위치 오차≤2cm, yaw≤0.1°를 capture와 독립 prepare 양쪽에서 확인한다.
Pose/paired timestamp/hash·정리 실패는 전체 수집 FAIL이다. Startup180s/capture900s/종료30s의
기존 quality budget을 유지하며 실패를 사후 timeout 연장으로 바꾸지 않는다.

이전 v1 개발/보류162개 RGB hash를 모두 제외하고 v2 partition 사이 byte 중복도 거절한다.
RGB-only 입력과 GT/stratum 파일을 분리하며, 실행 모델에는 정답/계획한 actor 정보를 주지 않는다.

## 후보와 사전 gate

같은 pinned YOLOX-S FP32/score0.35/CUDA이며 후보는 다음 두 가지로 제한한다.

1. `center-refine-v2`: base와 중앙320×192 crop의2배 추론을 합친다. Crop 가장자리2pixel에
   닿은 결과는 버리고 원래 영상 좌표로 복원하며 같은 class NMS0.5만 적용한다.
2. `vru-refine-v2`: 모든 base box를 그대로 보존한다. Crop의 person/bicycle/motorcycle만
   추가하며, 이미 선택한 같은 class box와 IoU>.5인 crop box는 추가하지 않는다. Crop의
   car/bus/truck은 추가하지 않는다. 높은 crop score로 기존 base box를 교체하지 않는다.

두 후보 모두 v1에서 TP 회귀를 일으킨 차량 class 간 억제를 하지 않는다. 후보 전체 입력/출력의
유한성·용량과 source identity를 검사한다. Crop 실패는 전체 후보 실패이며 base 성공으로 숨기지 않는다.
Live 경로와 typed v1 수신기로 발행하지 않는 offline 비교다.

기존 잠정 gate를 그대로 유지한다: precision≥.85, recall≥.80, 각 class recall≥.70,
near-person recall≥.90, negative FP/frame≤1/3. 상대 gate는 precision≥3%p 개선과
micro/각 class/far·occluded target recall 무회귀, near-person TP/negative FP 무회귀다.
Coverage는 각 class visible primary≥9에 더해 **각 class×near/medium/far/occluded에서≥2/3**,
유효 rider≥12를 요구한다. 표본이 없는 조건을 전체 class 평균으로 통과시키지 않는다.

모든 cold call과100ms late를 보존하고 raw/admitted를 분리한다. 위 정확도 gate는 strict raw에
적용하며 small-ignore/covered-miss 진단값으로 대체하지 않는다. Offline latency는 wall20Hz 수용이 아니다.

## 지명과 보류 검증

Development의 baseline·두 후보를 같은 sealed dataset에서 평가한다. 상대 gate PASS 우선,
F1→recall→precision→ID 순서로 하나만 지명하고, selection을 보류 서버 시작 전에 복사한다.
모두 실패한 경우의 지명은 진단용이며 승격이 아니다. 보류셋에는 baseline과 지명 후보만 실행한다.
보류 결과를 보고 다른 후보·threshold·정답 정책을 탐색하지 않는다.

각 데이터의 원본→RGB/GT/metadata/seal 재구성과 score/selection 재계산, actual pose와
원래 freeze/선택 hash를 추가 auditor에서 확인한다. 기술 감사 PASS·정확도 gate·coverage는
독립 판정이다. 절대/상대 gate를 모두 통과해도 새 runtime profile 검토가 필요하며 자동 승격은 없다.
