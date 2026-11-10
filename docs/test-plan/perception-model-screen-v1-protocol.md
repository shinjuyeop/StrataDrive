# M10 사전학습 모델 계열 비교 V1

2026-11-10. 사용자 지시에 따라 지금은 Jetson 배포 가능성을 고려한 Host 모델 선정 자료를
만든다. AGX Thor/Orin NX의 실제 배포·TensorRT engine 생성·FP16/INT8·보드별 최적화는
후속 M12다. 동일 Reference를 각 보드에 독립 배포한다는 기존 구조를 유지한다.

## 범위와 후보

기본 YOLOX-S는 초기 연동 기준이며 최적 모델로 확정한 상태가 아니다. 추가 학습을 계속하기
전에 공개 사전학습 YOLOX-S/M/L, RT-DETRv2-R18, NanoDet-Plus-1.5x416을 비교한다.
기존 추가 학습 L6는 이번 사전학습 모델 순위에서 제외한다. 모델별 공식 출처·revision·license·
크기·SHA256·tensor/pre/postprocess·ONNX op/domain을 기록하고 추론 전에 고정한다.
각 모델의 실제 ONNX graph 검사와 Host 실행을 배포 준비 근거로 사용하되, TensorRT 변환이나
Jetson에서의 지원/성능을 확인한 것으로 표시하지 않는다. Custom op 또는 배포 제약은 숨기지 않는다.

## 개발 자료와 실행 고정

이미 소비한 V4/V5/V6/V7의 **development만 각81장, 합계324장**을 사용한다. 경로는
`build/m10-quality-v4g/development-data`, `build/m10-quality-v5b/development-data`,
`build/m10-quality-v6/development-data`, `build/m10-quality-v7/development-data`다.
RGB/GT/metadata hash와 partition=development를 검사하고 전체 목록을 사전에 봉인한다.
보류 이미지·예측은 읽거나 재채점하지 않는다. 이 비교는 개발 자료의 탐색이며 독립 수용 평가가 아니다.

동일 원본 RGB640×384와6class(native0/1/2/3/5/7), visible-instance IoU≥.5를 사용한다.
Rider는 기존 person 정답을 그대로 따른다. 모델 고유 전처리와 입력 크기를 보존한다
(YOLOX640 letterbox, RT-DETR640 direct resize, NanoDet416 centered letterbox).
입력 크기 차이를 결과에 명시하며 같은 tensor를 강제하여 모델을 오용하지 않는다.
FP32·batch1, 공통 confidence≥.35, 최종 최대100개로 고정한다. YOLOX classwise NMS.5,
NanoDet 공식 class-agnostic NMS.6 후6class 필터, RT-DETR 공식 top300/no-NMS 후6class/score 필터를 사용한다.
Crop·ensemble·threshold 탐색·추가 학습·정답 수정은 하지 않는다.

RTX3090/동일 ORT CUDA 환경에서 후보별 새 process 하나로 순차 실행한다. 자동 CPU node
fallback을 금지한다. CUDA가 지원하지 않는 graph는 실패와 원인을 기록하고 CPU 결과를 CUDA
결과로 대체하지 않는다. 모델 생성·cold 첫 추론·각 단계 지연·전체 분모와 process RAM을 남긴다.
모델 순서는 S/M/L/RT-DETR/NanoDet이며 cold 포함/이후 지연을 구분한다. 이 Host timing으로
보드 순위나 전체wall20Hz를 판정하지 않는다.

## 검증과 판단

이전 V7 개발 준비의 고정 앞3장만 수치 probe로 사용한다. CPU/CUDA raw 및 완성 detection을
대조한다. NanoDet은 고정 공식 OpenCV 구현, RT-DETR은 원래 PyTorch 모델/공식 postprocessor와
ONNX 결과를 비교하여 전처리·class map·좌표 복원을 확인한다. 실패/수정 이력도 보존한다.
새 decoder에는 좌표·class·threshold·중복·nonfinite·overflow와 데이터 분리 회귀를 둔다.

수치 검사 첫 시도는 RT-DETR의 top300을 위치별 정수 label까지 동일해야 한다고 검사해
FAIL이었다. 개발 준비 probe1의 낮은 score.05455 부근 두 후보가193/194번째 순서만 바뀐
것을 별도 원본 덤프로 확인했다. 모든300개를 class·box≤.1pixel·score≤1e-4로 각각 한 번씩
대응시키는 set 비교로 바로잡고 원래 FAIL/덤프를 남긴다. 낮은 후보를 제거하거나 confidence·
정확도 기준을 바꾸지 않는다. 완성6class detection은 count/class 동일·box.1pixel·score1e-4,
NanoDet 공식 시각화의 정수 box에만1.01pixel 허용을 쓴다. 나머지 raw tensor는 atol/rtol .003/.003이다.

기존 strict matching을 재사용해 전체/도로별 P/R/F1,6class recall, near person·far·occluded·
negative FP와 Rider TP를 기록한다. 기존 절대 기준(P≥.85/R≥.8/class R≥.7/near person≥.9/
negative FP/frame≤1/3)을 함께 표시한다. 점수가 높아도 현재 runtime을 교체하지 않는다.
개발 결과로 후속 후보를 제안할 수 있으나 최종 모델 확정에는 고정 후보와 **새 독립 평가**가 필요하다.
이전 보류를 새 평가로 재사용하거나 기존 실패를 지우지 않는다.

모델 선정 자료·재현 가능한 adapter/runner·원본 예측·source/model/data freeze·검사와 배포 고려
사항을 남긴다. M10 기본 S와 기존 계약은 유지하고, 다음 작업은 비교 결과에 따라 결정한다.
