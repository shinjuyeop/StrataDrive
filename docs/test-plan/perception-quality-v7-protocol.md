# M10 V7: 고정 L6 학습 후보의 새 개발·보류 평가 사전 기준

2026-11-09. Epoch17로 고정한 첫 L6 ONNX와 기존 S를 비교한다. 학습·재지명·threshold 수정이나
과거 보류 예측 재생을 하지 않는다. 모델 hash/native 매핑은 이전 학습 evidence와 같아야 한다.
새 후보 출력11채널은 기존85채널 runtime으로 발행하지 않는다. 기본 S는 유지한다.

원래265개 map-only 조사와 기존 route/pose 규칙을 사용한다. 이미 본 site/road와 최소50m
떨어진 미사용 road만 허용한다. 예약127번/road6을 holdout으로 유지하고 다음215번/road20을
새 development로 지정한다. 같은 Town·고정 합성 fixture의 새 road/RGB/episode 평가이며,
학습/검증과 공유한 actor blueprint를 포함하므로 자산/도시 전체 ODD 독립 일반화는 아니다.

먼저 실제 두 camera site의 모델 없는 preparation99장씩을 수집해 모든 계획 actor/Rider의
visible25pixel/side4·pose2cm/0.1°·road projection2m/clearance15cm·occluded/reference를
검사한다. 원래640×384/FOV90/Epic/postprocess·world10ms·settle40/capture10/선택tick5와
physics-off·tick 전50m staging을 유지한다. 접지·동적 주행 수용은 아니다. 실패와 부분 수집은
그대로 남긴다. Startup180/capture900/shutdown30s와 정상exit130을 유지하며 zero-frame
startup 실패만 동일 budget/source/plan으로1회 자동 재시도할 수 있다.

과거3973개 RGB와 모든 이번 preparation/거절 영상을 final evaluation에서 제외한다.
준비99장은 actor거리+1m/camera높이+.05m로 실제 평가81장과 분리한다. 준비 visibility만
보고 gate 통과를 확인하며 모델 예측으로 장면을 고르지 않는다. 고정 패널과 모든 RGB 건전성도
검토한다. Source/plan·모델/numeric·exclusion을 고정한 후 development81장을 새로 수집한다.

Candidate는 baseline S와 단일 trained-v1 L6다. L6는 raw full view·score.35·classwise NMS.5,
head→native[0,1,2,3,5,7]만 사용한다. Crop/ensemble/새 postprocessing이 없다. 준비 개발 RGB의
고정3개 입력에서 CPU/CUDA/OpenCV raw 및 완성 native detections를 대조한다. Raw atol1e-3/
rtol1e-4,완성 count/class 동일·box.01pixel/score1e-4를 요구한다. 학습 때의 PyTorch/ONNX
검증·고정 source/checkpoint/data lineage도 연결한다. 정확도와 수치 구현 검증을 구분한다.

기존 V6의 absolute/relative/coverage·visible tight IoU.5·작은 객체 primary-ignore=false와
Rider 정의를 그대로 유지한다. P>=.85/R>=.8,모든 class recall>=.7,near person>=.9,
negative FP/frame<=1/3이다. 상대 기준은 S 대비precision+.03,전체/class/far/occluded recall
무하락·near person TP 무하락·negative FP 무증가다. 진단용 small-ignore/covered miss는
TP나 gate를 바꾸지 않는다. Held person far26m와 준비27m 범위도 유지한다.

개발 점수·상대 비교를 봉인해 단일 후보를 지명한 다음에만 holdout81장을 수집한다. 개발이
실패해도 고정 후보의 descriptive holdout 결과는 남길 수 있으며 실패를 PASS로 바꾸지 않는다.
보류에는 S/지명 후보만 실행한다. 보류를 본 뒤 모델·기준·계획을 수정하지 않는다. 새 개선에는
별도 개발과 다시 새 보류가 필요하다. 모든 cold/startup 및 per-frame 지연과 오류를 남기며,
이번 offline replay를 전체wall20Hz나 새 runtime/차량 수용으로 해석하지 않는다.

두 partition 모두 absolute/relative gate를 통과해야 새 runtime profile/interface 검토가
가능하다. 자동 승격은 없다. 원본/pose/정답·score/selection/order·새 경로 압축 재감사를 남기고
M10의 전체wall20Hz·시작/종료 안정성·주행 통합 잔여 항목은 별도 유지한다.

[고정 학습 모델](evidence/m10_training_v1/README.md),
[기존 정확도 기준](perception-quality-v6-protocol.md)을 따른다.
