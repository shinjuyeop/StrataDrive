# M10 V6 고정 L 모델·확대 시야 차종 판단과 새 평가 사전 기준

2026-11-09. V1–V5의 source·원본·실패·기준과 기본 S live 모델을 유지한다. 소비된 V4/V5
개발162장만 새 설계에 사용하며 보류 영상/예측을 재생하거나 새 수용 표본으로 세지 않는다.
공식 YOLOX 0.1.1rc0의 L ONNX(216746733byte, SHA256
`7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411`)를 별도 identity로
고정한다. 기존 RGB0–255·letterbox114·FP32·score.35·class-aware NMS.5를 유지한다.
M/S envelope에 L을 발행하지 않는다. 새 가중치 학습·GT/scene 입력·차량 제어 권한은 없다.

후보는 `large-v6` 원본 L과 `large-context-v6` 원본/고정 중앙2배 확대 L이다. Context는
확대의6개 클래스 모두를 사용할 수 있다. 확대 score≥.5는 원본 raw 같은 클래스 지지≥.1,
그 미만은≥.2·IoU≥.3을 요구한다. 강한 body(bicycle/car/motorcycle/bus/truck) 확대는
원본 body-family 지지≥.1을 허용한다. Person에는 다른 클래스의 지지를 대신 쓰지 않는다.
약한 raw proposal 자체를 발행하지 않는다. 확대 안쪽에 완전히 들어온 원본 body와 다른
body 클래스 확대가 IoU>.5로 충돌하면 확대 score≥.5일 때 확대를 남긴다. 그 미만이면 원본을
남긴다. 확대 내부 원본 VRU score<.5는 확대 같은 클래스의 IoU≥.3 지지를 요구한다.
기존 V5의 원본 score<.75 검증보다 낮은 범위에만 적용한다. Person은 다른 클래스와의
중첩만으로 제거하지 않는다. Crop 경계2pixel 거절·각 view/최종100개·모든 raw 유한성 검사를 유지한다.
모든 수치는 descriptor POLICY와 소스에서 일치해야 한다.

기존 전체 지도 query에서 과거0–6/14/18/24/31/35번과 같은 road 또는50m 안쪽을 제외한
첫 적격 위치74/80번을 선택한다. 전체42m nonjunction·폭3.2m·heading15°·frustum·기존
실제 pose2cm/0.1°·projection2m·clearance15cm를 유지한다. 각 실제 site에서 별도 준비99장씩
198개를 모델 없이 검사한다. 모든 계획 actor/rider25pixel/side4·6class×4조건3/3·가림 없는
참조18개와 visible ratio0초과/.95미만을 요구한다. 임시 staging은 V5b 그대로이며 tick 전에
physics-off/최종 pose를 적용한다. 최종 평가의 실제 coverage도 별도로 검사한다.

과거2357개와 모든 성공/실패/부분 준비 RGB를 새 평가에서 제외한다. 준비 PASS 뒤 준비3장의
독립 RGB tensor·CPU/CUDA/OpenCV raw(atol1e-3/rtol1e-4)와 두 완성 후보의 CPU/CUDA
class/count·box.01pixel/score1e-4를 검사하고 source/config/model/plan/기준을 freeze한다.
새 개발81장에서 S/L/L context를 비교하고 relative PASS→F1→recall→precision→ID의 기존
순서로 하나만 지명한다. 보류 서버 시작 전에 개발 점수로 지명을 재구성하고 S와 지명 후보만
새 보류81장에 실행한다. 이미 본 보류/준비/진단 영상을 새로운 holdout으로 재사용하지 않는다.

Strict visible IoU≥.5·Pedestrians12/Rider13 person·최소25pixel/side4와 기존 gate를 유지한다.
절대 precision≥.85·recall≥.8·각 class recall≥.7·near person≥.9·negative FP/frame≤1/3,
상대 precision+.03·micro/class/far/occluded recall 및 near person TP 무하락·negative FP 무증가다.
각 class primary9개 이상·4조건2/3 이상·rider12개 이상·전체7strata·negative3개도 유지한다.
Runtime 검토에는 개발/보류의 absolute/relative/coverage가 모두 필요하며 자동 모델 교체는 없다.

Startup180s·capture900s·shutdown30s·server exit130 기준을 유지한다. 원래 실패/partial source,
모든 cold/init/단계 timing·오류·offline100ms admitted를 보존한다. 원본→RGB/GT/road/coverage/
seal·strict 점수·지명·순서·중복을 재감사한다. 같은 Town·이미 본 자산·유한 정지 배치이며
작은 held walker far26m 범위다. 전체 ODD·새 도시/자산 일반화·공유 GPU 실제wall20Hz·장기
시작/종료 안정성·M11/Target/차량 수용은 별도다.
