# M10 V5 VRU 다중 시야 후보와 새 도로 평가 사전 기준

2026-11-09. V4의 코드·원본·점수·실패와 기본 live S 모델을 보존한다. 이번 후보는 고정
YOLOX-M과 기존 score.35·RGB unscaled tensor·NMS.5를 사용한다. 새 가중치나 GT 입력은 없다.
소비된 V4 개발81장만 설계에 사용하며 해당 결과는 새 수용 평가가 아니다. V4 보류 영상/예측은
설계 재생에 사용하지 않는다. 후보를 고정한 뒤 새 위치·개발/보류를 검사한다.

`medium-vru-v5`는 M 원본과 고정 중앙2배 확대를 사용하고 확대 결과의 person/bicycle/motorcycle만
합친다. `medium-consensus-v5`는 확대 VRU의 원본 raw 같은 클래스 objectness×probability≥.20,
IoU≥.30 지원을 요구한다. 확대 score≥.75이면 VRU-family 약한 지원≥.10을 허용한다.
약한 raw proposal은 검출로 발행하지 않는다. 원본의 score<.75 VRU가 확대 내부에 완전히 보일
때에는 확대 같은 클래스와 IoU≥.30도 요구한다. 원본의 강한/확대 밖 검출은 이 검사를 면제한다.
거의 같은 body box의 bicycle/car/motorcycle/bus/truck 간 IoU>.85 충돌은 높은 score 하나를 남긴다.
Person은 다른 클래스와 겹친다는 이유로 억제하지 않는다. 모든 조건은 descriptor의 POLICY와
대조하고 각 view최대100·최종100개·잘린 crop 경계2pixel 거절을 유지한다.

이전 모든 실제 카메라0–6/14/18/24와 같은 road 또는50m 안쪽의 site를 제외한다. 기존265개
완전 지도 query에서 전체42m nonjunction·폭3.2m·heading15°·시야 조건을 통과한 첫 두 위치는
31/35번이다. 영상/모델 점수로 위치를 고르지 않는다. 고정 Town03의 정지 fixture이며 전체 ODD·
독립적인 도시 일반화는 아니다. 도로 pose/clearance·개발/보류 자산·거리·작은 held walker far26m는
유지한다. 각 실제 site에서 별도 준비81개와 가림 없는 참조18개, 총198개를 모델 없이 검사한다.
모든 actor/rider25pixel/side4·각 class×조건3/3·가림 ratio0초과/.95미만을 요구한다.
준비 PASS 뒤 독립 RGB tensor·CPU/CUDA/OpenCV raw 비교와 코드/모델/계획/기준을 freeze한다.

이전1873개와 이번 모든 성공/실패/진단 준비 RGB를 평가에서 제외한다. 새 개발81장에서 S와
두 후보를 비교해 기존 relative PASS→F1→recall→precision→ID 순서로 하나만 봉인한다.
보류 서버 시작 전에 개발 예측으로 지명을 재계산하고 S와 지명 후보만 새81장에 실행한다.
모든 계획 actor/rider·조건 coverage는 실제 평가에서도 다시 검사한다. 이미 소비한 V4 보류나
준비를 새 holdout으로 재사용하지 않는다. 실패도 원래 source/probe·raw·판정과 함께 보존한다.

Strict visible IoU≥.5, Pedestrians12/Rider13 person, 최소25pixel/side4와 기존 절대/상대 기준을
낮추지 않는다. Precision≥.85·recall≥.8·class recall≥.7·near person≥.9·negative FP/frame≤1/3,
상대 precision+.03와 micro/class/far/occluded recall·near person TP 무하락·negative FP 무증가다.
Class별 primary9개 이상·각4조건2/3 이상·rider12개 이상·전체7strata·negative3개도 유지한다.
새 후보의 runtime 검토에는 개발/보류 absolute/relative·coverage가 모두 필요하며 자동 교체는 없다.
모든 cold/init/단계 시간·모델 오류와 offline100ms admitted를 기록하고 실제wall20Hz와 구분한다.

품질/준비 서버의 startup180s·capture900s·shutdown30s와 실제 exit130 기준을 유지한다.
시작/종료 재시도는 같은 설정의 실패를 보존하고 정상 종료한 표본만 검사한다. Raw→RGB/GT/
road/coverage/seal·점수·지명·순서·중복을 재감사한다. C++ 발행·차량 제어·metric fusion은 별도다.

첫35번 준비는 카메라 뒤 임시 spawn의 구조물 충돌로25쌍에서 FAIL이었다. 최종 pose/거리/
가시성 기준은 바꾸지 않고 임시 spawn만 계획 XY의 z+50+10×index로 옮긴 staging-v5b를
적용한다. World tick 전에 physics-off와 최종 pose를 적용하며 요청 staging도 원본에 기록한다.
원래31번99쌍·35번 부분25쌍과 실패를 보존하고 두 site를 새 source freeze로 전체 재수집한다.
