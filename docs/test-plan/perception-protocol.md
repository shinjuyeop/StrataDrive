# 영상 인지 Host 검증 프로토콜

프로파일 `m10-perception-host-v1`, 2026-11-06. 실행 전에 모델·전후처리·threshold·camera·
source100ms와 wall100ms·평가 IoU0.5를 고정한다. 기존 Reference 전체 workload의 null을
이 fixture의 결정으로 대체하지 않는다.

| ID | 검사 | 판정 |
| --- | --- | --- |
| TC-PER-001 | RGB 순서/padding/scale·YOLOX shape/decode/NMS·NaN/Inf·overflow·빈 정상 출력 | 결정적 fixture 예상값과 일치; 잘못된 출력 unavailable |
| TC-PER-002 | epoch/clock/model/camera/calibration·frame/source 단조·expiry·clock 역행 | 원천 연장/잘못된 session 수용0 |
| TC-PER-003 | queue overwrite·늦은 완료·backend exception·실행 중 INIT·stop | drop/timeout/error 분모 보존, 과거 generation publication0 |
| TC-PER-004 | image-space tracking·gap·class 변화·session·history | GT 없는 관측만 사용, 과거 box를 현재 검출로 발행0 |
| TC-PER-005 | 실제 ONNX RGB replay→C++ receiver | 결과별 동일 identity/count·expiry·box 수용; 변조 거절 |
| TC-PER-006 | CARLA paired RGB/instance·평가 분리·TP/FP/FN·원본 hash | functional capture/inference 증거와 정확도 측정을 분리 |
| TC-PER-007 | pre/infer/post/submit→complete wall latency·throughput·late/drop·source age | N/Mean/P95/P99/Max와 원래 budget misses 보고; wall/Target PASS로 승격 금지 |
| TC-PER-008 | 명시적 준비3회·cold 비용·준비 timeout/clock/stop·sensor INIT gate | 뒤2회<100ms와 전체<10s; probe publication0; late READY 복원0; 생성 비용 별도 |
| TC-PER-009 | BGRA latest ingress·snapshot lineage·원본 receipt·camera loss | 순서/크기/보정 오류 거절; queue 대기 포함100ms; source 정지에도 wall 만료 |
| TC-PER-010 | 실제 CARLA/CUDA 공유 GPU·moving image actor·고장4조건·독립 감사 | 원천 frame5 취득·전체 분모·오류/late 출력0·500ms source pause 만료·정리; 실제 wall Hz 별도 |
| TC-PER-011 | 사전 고정6class·3기상·거리/가림·negative·중첩, development/holdout 분리 | 각81배치·원본 pair/actor lineage·가시성 coverage·서버 정리; 반복 frame을 새 표본으로 세지 않음 |
| TC-PER-012 | 차량 class 중복 억제·중앙 확대 후보의 원본 좌표/유한성/용량 | 고정 geometry/NMS, VRU 비억제, crop 경계 절단 거절; offline 전용 |
| TC-PER-013 | 사전 freeze·개발셋 지명·보류 취득·raw 재구성·점수 재계산·변조 | 같은 데이터/코드·선택 hash·순서 검증; gate FAIL 보존·자동 runtime 승격0 |
| TC-PER-014 | Pedestrians12/Rider13 person 정답·조건별 coverage·작은 정답/visible IoU 진단 | 사전 고정 v2 정답·strict gate; 제외/가림 진단으로 TP/acceptance 변경0 |
| TC-PER-015 | 안정화 뒤 실제 actor pose·새 v2 입력/후보/분리 평가 | 계획2cm/0.1° 대조·v1 영상 재사용0·동일 개발셋 비교·선택 후 보류 취득·전체 원본 재구성 |
| TC-PER-016 | 별도 준비셋 자산/가시성·가림 참조·서버 전 NW 거절 | 모델 점수 없이 모든 actor 최소 지원; 참조 대비 visible ratio0초과/95%미만; FAIL 보존 뒤 평가 전 배치 수정 |
| TC-PER-017 | 별도 M model hash·독립 tensor/raw·새 S/M 비교·보류 순서 | CPU/CUDA/OpenCV 수치 gate; S 계약으로 M 발행 거절; 고정 절대/상대 gate·원본 재구성 |
| TC-PER-018 | 도로 waypoint·deterministic 분기·경로 전체 junction·camera frustum·명시 pose | 모든 실제 site의 road/lane 대조·projection≤2m·clearance오차≤15cm·pose2cm/0.1°; 중간 junction 회귀 검사 |
| TC-PER-019 | 실제 두 site의 준비·이륜차 Rider·부분 가림·raw 재구성 | 각99개·class×조건3/3·모든 계획 actor/rider25pixel/side4·참조18개·실패 보존·미래 평가 RGB 재사용 거절 |
| TC-PER-020 | 준비 봉인·1711개 제외·품질 freeze·보류 이전 지명 | 모델·gate·명시 pose 고정; 보류 서버 시작 전에 개발 점수에서 지명 재구성; 잘못된 schema와 미지명 보류는 RPC 이전 거절 |
| TC-PER-021 | 새 도로 평가 RGB/GT·strict 점수·실제 actor/rider 지원 재감사 | 원본→RGB/GT/road pose/seal·score/selection·실행 순서와 중복 재구성; 품질 FAIL도 보존; 자동 runtime 교체 없음 |
| TC-PER-022 | 약한 raw 지지·양방향 시야 검증·body class 충돌·완성 후보 수치 비교 | raw 지지만으로 발행0·person 중첩 보존·유한/용량 검사·CPU/CUDA box .01pixel/score1e-4; 고정 M offline 전용 |
| TC-PER-023 | 미사용 도로 선택·모델 없는 준비·임시 spawn staging·새 수집 | 기존 site/road/50m 제외·모든 actor/rider·가림 참조·tick 전 최종 pose·요청 staging lineage; 실패/원래 source 보존 |
| TC-PER-024 | V5 prospective freeze·개발 지명·새 보류·원본/이력 재감사 | 준비322개 포함2195개 제외·개발만 지명·raw/strict 점수/순서 재구성·보류 FAIL 유지·자동 runtime 교체0 |
| TC-PER-025 | 고정 L model bytes/hash·별도 offline identity·독립 수치 비교 | S/M envelope로 L 발행 거절; 독립 RGB·CPU/CUDA/OpenCV raw 및 완성 후보 class/count/box/score 동등성 |
| TC-PER-026 | 전체 class 확대·약한 지지·시야 간 body 불일치·작은 VRU | raw 자체 발행0·person 지지는 person만 허용·person/rider 중첩 보존·distinct body와 유한/용량 검사 |
| TC-PER-027 | 새74/80번 준비·개발 지명·보류·원본/설계 재감사 | 기존2357개+모든 준비 제외·개발 relative 우선 지명·보류에는 S/지명만·strict gate/실패 보존·자동 runtime 교체0 |
| TC-PER-028 | 개발 데이터의 deterministic 시야/기상/자산·actual raw/pose·source freeze |22자산8m4방향 최소 지원·Rider·실제 도로/pose·모든 원본/시작 실패와 가림 참조 보존; 모델 없는 데이터 준비 |
| TC-PER-029 | 모든 visible 양성·작은 fragment·COCO RLE/category·PNG/RGB | 작은 객체를 배경 음성/crowd로 바꾸지 않음·기존 품질 기준 별도·독립 COCO API area/bbox·해시/마스크 변조 거절 |
| TC-PER-030 | Train/validation road·RGB·family/episode·가능한 blueprint 분리·새 경로 재감사 | 무작위 frame 분할0·bus/truck 공유 명시·127번 holdout 미수집·원래 FAIL과 추가 자료 유지·사전 split gate·자동 모델 승격0 |
| TC-PER-031 | 초기 가중치/native 행 이식·고정813/267·실제24epoch와 모든 양성 | 원본 모든 tensor strict 대조·작은 양성과 빈 프레임·정확한 반전/좌표·마지막 batch·BN 통계 고정·finite loss/gradient·실제 가중치 변화 |
| TC-PER-032 | 모든 epoch score·고정 validation macro F1/동점 선택·독립 재채점 | epoch0 포함·모든 prediction/원래 하락 보존·점수/선택 재현·새 quality holdout 미접근·기본 S 유지 |
| TC-PER-033 | 새11채널 ONNX/manifest·CPU/CUDA/OpenCV 수치·retained tensor/압축 감사 | 기존85채널/변조 거절·16probe raw/detection·267장 CPU/CUDA count 동등성·체크포인트/source/data binding·역전파 재실행과 구분 |

TC-PER-031–033은 [학습 기준](perception-training-v1-protocol.md)과 [실제 학습·수치/원본 재현](evidence/m10_training_v1/README.md)을 따른다.

TC-PER-028–030은 [개발 데이터 기준](perception-domain-data-v1-protocol.md)과 [원본·분리/COCO 근거](evidence/m10_domain_data_v1/README.md)를 따른다.

TC-PER-025–027은 [V6 기준](perception-quality-v6-protocol.md)과 [새 평가 근거](evidence/m10_quality_v6/README.md)를 따른다.

TC-PER-022–024는 [V5 기준](perception-quality-v5-protocol.md)과 [새 평가 근거](evidence/m10_quality_v5/README.md)를 따른다.

TC-PER-011–013은 별도 [정확도 확장 프로토콜](perception-quality-protocol.md)을 따른다.
아래 초기60pair/20Hz fixture와 분모·기상·수집 rate를 합치지 않는다.
TC-PER-014–015의 새 평가·정답·pose·coverage는 [V2 프로토콜](perception-quality-v2-protocol.md)을 따른다.

CARLA는 전용 새 서버·Town03_Opt·ClearNoon·640×384·90°·20Hz camera를 사용한다.
Parked scene에서 physics-disabled actor와 단일 tick owner로 RGB/instance를 모은다.
장면 normal, small/far, partial occlusion을 고정 위치/seed로 구분한다. Metadata·sensor 원본과
frame pairing을 확인하고 정답은 별도 파일로만 저장한다. GT 최소 visible25pixel·box side4pixel
미만은 제외하되 개수와 이유를 보고한다. 추가 corruption replay는 black image/drop/late/wrong
identity를 검사하며 검은 영상의 정상 inference와 시스템이 인지 실패를 검출하는 능력을 혼동하지 않는다.

이 fixture는 차량 주행·collision avoidance·전체 Reference ODD 성능 시험이 아니다.
모든 모델 실행 결과·원래 실패·source/config/weights/input hash·tool version·시간 clock을 보존한다.
정확도는 TP/FP/FN 및 class별 precision/recall, latency는 wall 측정이다. Quality acceptance는
NOT_SET, native controller/NoDrive 연동·metric fusion·M11 planner·M12 보드는 NOT RUN이다.

최종 수집 seed는 UE4 `-FixedSeed`의0이고 Python actor 선택/배치에는 난수를 쓰지 않는다.
Source clock instance는 실제 CARLA episode ID다. 탐색 실행의 임의 seed 표기와 고정 clock7은
최종 수집의 원천 identity로 사용하지 않는다.

실제 ONNX Runtime/OpenCV DNN의 FP32 raw tensor를 같은 세 장면에서 대조한다.
전처리 tensor는 독립 RGB/padding 구성과 byte 동일해야 하며 모델 output tolerance는
사전 고정 `atol=1e-3, rtol=1e-4`다. 이는 구현 동등성이며 검출 정확도 기준이 아니다.

선택형 Host CUDA도 같은 raw tolerance를 적용하고 class/count 일치·score abs1e-4·원본 pixel
box abs0.01을 추가 검사한다. TF32를 끄고 CPU node fallback을 금지한다. 동일 dataset/model과
threshold를 유지하며 첫 cold call도 timing 분모에 포함한다. CUDA provider 생성·library 로딩
실패를 CPU 성공으로 바꾸지 않는다. RTX3090 Host 결과는 Jetson/공유 CARLA GPU 부하 수용이 아니다.
