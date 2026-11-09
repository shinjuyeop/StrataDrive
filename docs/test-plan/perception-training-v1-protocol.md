# M10 개발 자료 v1의 첫 L6 학습 후보 사전 기준

2026-11-09. 고정한 전용 자료 train813/validation267을 사용한다. 데이터 원본/라벨/분리와
기존 V1–V6 모델·점수·gate는 수정하지 않는다. Validation은 checkpoint 선택에 쓰는 개발
자료이며 quality holdout이 아니다. 예약127번과 과거 보류 영상은 읽거나 수집하지 않는다.
기본 S·기존 runtime·차량 출력은 유지한다. 이번 범위는 첫 학습·offline 내보내기·수치 검증이다.

공식 YOLOX 0.1.1rc0 commit e1052df71842031413f6030723c3607b839c80ce의 L 구조와
loss/SimOTA를 그대로 사용한다. 공식 yolox_l.pth의 byte/hash를 먼저 검사하고 weights_only=True로
읽는다. Classifier의 native [0,1,2,3,5,7] 행을 연속 head [0,1,2,3,4,5]로 복사한다. 나머지 tensor는
strict load와 전 tensor equality로 검증한다. 초기80-class와 이식 직후6-class를 각각 검증해,
클래스 축소 효과와 학습 효과를 구분한다. 새 모델 출력은 [1,8400,11]이며 native 매핑을 명시한다.

`profiles/perception-training-v1.json`에 단일 학습 설정을 고정한다. Seed20261109,24epoch,
batch4·마지막 작은 batch 포함·workers0·모든 train frame을 매 epoch 정확히 한 번 읽는다.
AdamW lr1e-4/weight_decay1e-4,1epoch의 .1→1 warmup 후 cosine .1 floor,gradient clip10,
FP32·TF32 off·deterministic algorithm을 사용한다. 모든 parameter는 학습하고 BatchNorm의
running statistics만 고정한다. 원래RGB0–255·640×384를 좌상단640square/114로 padding한다.
좌우반전 확률 .5만 적용하며 box를 정확히 변환한다. Resize/crop/mosaic/mixup·작은 라벨 삭제·
crowd/ignore 변경은 없다. 모든 nonempty visible positive와 Rider·빈 라벨 프레임을 포함한다.

각 epoch의 validation267개 전부를 RGB만으로 추론한 뒤 독립 scalar IoU로 채점한다.
고정score.35·classwise NMS.5·strict IoU.5, 모든 visible 양성에 대한 per-class 및 micro/macro
F1을 기록한다. 가장 큰 macro F1의 checkpoint를 선택하며 epoch0도 포함하고 동점은 이른
epoch를 택한다. Validation을 보고 hyperparameter·threshold·선택 규칙을 바꾸지 않는다.
모든 epoch prediction·score·loss와 state digest를 보존하고 best/last checkpoint를 남긴다.
3시간 wall budget·실패/부분 실행을 보존하며 성공한 epoch 수를 부풀리지 않는다.

선택 후 checkpoint/freeze hash·새 모델 manifest와 ONNX opset11·고정 FP32 tensor contract를
연결한다. 원래 RGB와 독립 synthetic inputs에서 PyTorch/ONNX CPU/CUDA/OpenCV의 raw 및
최종 native detections를 비교하고 변조/다른 출력 계약을 거절한다. Raw 허용오차는 atol.003/
rtol.003이며 detection count/class는 같고 box최대.1pixel·score최대.0001을 요구한다.
이 검증은 serialization/수치 구현 검사이며 새 quality holdout·wall20Hz·주행 수용이 아니다.
정지 합성 fixture·같은 Town·bus/truck 공유 자산의 제한은 유지한다. 후속 새 개발·보류 평가는
새 수집 protocol과 candidate/source freeze로 진행한다.

근거: [고정 자료](evidence/m10_domain_data_v1/README.md),
[공식 학습 소스](https://github.com/Megvii-BaseDetection/YOLOX/tree/e1052df71842031413f6030723c3607b839c80ce),
[공식 PyTorch 버전 조합](https://pytorch.org/get-started/previous-versions/).
