# Domain data v1 학습 split의 작은 보행자 가림 추가 준비

모델 없는 학습 split의 WetCloudyNoon 작은 walker0010은 기존 .6/.85/1.2m target lateral에서
가림이 너무 적거나25pixel/side4 미달이었다. 기존 원본·추가 영상·FAIL·기준을 유지한다.
Train31에서 target .85m를 유지하고 car occluder -.60/-.65/-.70/-.75/-.80/-.85m의6단계를
동일 target/camera의 참조와 함께12장 추가한다. 참조 RGB 반복을 피하도록 각 pair camera yaw를
.15도씩 결정적으로 바꾸며 pair 안에서는 동일하다. 모델/예측을 사용하지 않는다.

원래1068장과 모두 합쳐1080장(train813/validation267)을 구성한다. 입력 descriptor는 기존
four-site schema를 유지하되 실제 추가 수집은 train31만 실행한다. Validation과127번 quality
holdout은 추가 수집하지 않는다. 원래 split FAIL도 남기고 final-split-coverage.json에서 기존
최소 지원·0초과/.95미만 가림 기준을 다시 요구한다. 실패 표본과 작은 양성 조각도 유지한다.
학습·모델 정확도·runtime 승격은 별도다.
