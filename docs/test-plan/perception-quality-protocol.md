# M10 정확도 확장·후보 비교 프로토콜 v1

2026-11-07. [장면 계획](../../profiles/perception-quality-plan-v1.json)과
[판정 설정](../../profiles/perception-quality-protocol-v1.json)을 새 데이터의 추론 전에 고정한다.
이는 Host 인지 개선을 위한 **잠정 engineering gate**이며 차량 안전·전체 ODD 수용 기준이 아니다.
기존 모델/threshold·원래 평가 기록은 유지한다. 학습자 최종 수용과 M11 판단/제어 연결은 별도다.

## 데이터와 정답

각 partition은81개 배치다:6개 class(person/bicycle/car/motorcycle/bus/truck)×3개 조명/기상
(ClearNoon/WetCloudyNoon/ClearSunset)×4조건(near/medium/far/occluded)=72,
배경 negative3, 차량 중첩3, 보행자/자전거 중첩3을 더한다. 보행자·자전거를 차량 중복 억제로
지우는 문제를 별도로 관측한다. 야간/강우·전체 도로 분포는 포함하지 않는다.

Development는거리12/24/42m와 가림16m, holdout은14/28/48m와 가림18m다.
Camera spawn0/1과 물체 orientation을 분리하고, 가능한 class는 blueprint도 바꾼다.
Bus asset과 같은 Town03은 공유하므로 지리·asset 독립 일반화로 해석하지 않는다.

Epic quality·RGB postprocess enabled·640×384/FOV90·원래10ms world tick을 고정한다.
Accuracy capture의 두 sensor는 매 tick 취득하고, 매 배치40tick settling 뒤10tick 중 **5번째**
원본 frame의 RGB/instance 한 쌍만 고른다. 이미지/정답을 보고 고르는 절차는 없다.
이는 반복20frame을 독립 표본으로 세지 않기 위한 수집이며20Hz timing 시험이 아니다.
RGB와 instance frame/time을 대조하고 SDK/server version·map/pose/weather/actor·hash·정리를 기록한다.

Instance의 semantic/instance ID로 visible box를 만들며25pixel·side4pixel 미만은 제외 수를 보고한다.
완전 가림/시야 밖 대상을 평가에서 몰래 삭제하지 않고 계획한 target의 가시성 coverage 결손으로 남긴다.
계획한 actor ID와 mask ID/class도 대조한다. Visible box@IoU0.5이며 COCO mAP나 amodal recall이 아니다.
RGB-only manifest와 정답/stratum metadata를 분리하고, 데이터 seal에 각 hash를 고정한다.
모델은 RGB와 원래 identity만 받고 정답/actor/stratum을 읽지 않는다.

## 사전 고정 gate

| 구분 | 기준 |
| --- | --- |
| Coverage | partition별81쌍·7종 stratum·negative3개; class별 visible primary target≥9배치 |
| 잠정 절대 정확도 | micro precision≥0.85, micro recall≥0.80, 모든 class recall≥0.70 |
| 근거리 보행자 | near person recall≥0.90 |
| 배경 오검출 | negative FP/frame≤1/3 |
| 후보 상대 개선 | baseline 대비 precision≥3%p 개선, micro/per-class recall 감소0 |
| 중요한 조건 | far/occluded **primary target** recall 감소0, near person TP 감소0, negative FP 증가0 |

여러 gate를 평균으로 상쇄하지 않는다. Fail을 이유로 기준을 낮추지 않는다. 품질은 raw model과
100ms deadline-admitted 출력을 따로 보고하며 위 정확도 gate는 raw에 적용한다. Cold call도
latency 분모에 남긴다. 실험 후보는 startup/live20Hz·차량 authority 수용을 획득하지 않는다.

## 비교 후보와 보류 평가

1. Baseline: 기존 고정 YOLOX-S FP32/score0.35/class NMS0.5.
2. `vehicle-nms-v1`: baseline 출력의 car/bus/truck 사이 IoU>0.75 중복만 낮은 score 순으로 억제.
   같은 class NMS를 다시 하지 않고 person/bicycle/motorcycle은 이 억제에서 제외한다.
3. `center-refine-v1`: 같은 모델에 고정 중앙 crop `[160,96,320,192]`를2배 확대해 한 번 더 추론.
   확대 영상의 가장자리2pixel에 닿은 box는 버리고 원래640×384 좌표로 복원한다. Base와 합친 뒤
   class NMS0.5와 위 차량 계열 NMS를 적용한다. 과부하/잘못된 출력은 전체 후보 unavailable이며
   crop 실패를 정상 base 성공으로 감추지 않는다.

가중치·점수 threshold는 동일하다. 두 후보는 별도 offline experiment이며 현재 live v1이
자동 선택하지 않는다. 변경된 후처리를 기존 v1 프로파일 결과로 표시하거나 C++ 경계에 발행하지 않는다.
RGB 순서·letterbox는 [고정 OpenCV Zoo demo](https://github.com/opencv/opencv_zoo/blob/a74cdfad334b102cbd8daed769fbe1d4cb1c327a/models/object_detection_yolox/demo.py)와 확인했다.

모델 추론 전에 protocol/plan/실행·평가 소스 hash를 freeze한다. Development의 세 결과만으로
상대 gate PASS 우선, micro F1→recall→precision→ID 순서로 후보 하나를 지명한다.
모든 후보가 실패했어도 가장 나은 후보의 **진단용** 보류 평가를 할 수 있으며 승격을 뜻하지 않는다.
지명 파일의 hash를 서버 실행 전에 보존하고 그 뒤 holdout을 새로 취득한다. Holdout에서는
baseline과 지명된 후보만 실행한다. 새로운 설정으로 holdout을 반복 탐색하지 않는다.

절대·상대 gate가 모두 통과해야 새 runtime profile/interface 검토의 후보가 된다.
미통과 시 개선 수치와 회귀를 공개하고 기본 v1을 유지한다. 좁은 합성 자료의 점수만으로
실차/전체 ODD 정확도나 학습자의 최종 수용을 선언하지 않는다.

## 실행 후 정답 검토와 감사

V1 실행에서 CARLA `Rider=13`을 정답 생성기가 누락한 사실을 확인했다. `Pedestrians=12`만
person으로 변환하므로 영상에 보이는 탑승자의 정상 person 검출도 FP로 셀 수 있다. 원본 mask와
해당 SDK의 `ObjectLabel.h`를 대조했다. V1의 person FP 전부를 모델의 의미적 오류로
해석하지 않는다. 가림의 visible box와 모델이 예측하는 전체 물체 box 차이도 별도다.
V1의 정답·gate·점수는 수정하지 않는다.

별도 `quality_annotation.py`의 v2는 tags12/13을 person으로 합치고, 같은 instance의 person과
이륜차는 class별로 분리한다. 최소25pixel/side4 조건은 유지한다. Synthetic mask 회귀 검사와
162개 원본의 재생으로 차량 정답이 변하지 않는지 확인한다. `review_quality_annotations.py`의
재계산은 **사후 진단용**이다. 후보를 다시 지명하거나 v1 FAIL을 PASS로 바꾸지 않는다.
V2와 가림 box/ignore 규칙을 검수하고 새 partition·freeze로 다시 검증해야 한다.
이미 본 holdout을 새 보류 평가로 재사용하지 않는다.
[실행 근거](evidence/m10_quality/README.md)에 원본과 진단 이미지를 보존한다.

`audit_quality_experiment.py`는 기존 frozen scorer를 바꾸지 않는 추가 검사다. 모든 BGRA/instance에서
RGB·GT·metadata·seal을 재구성하고, 저장 점수와 지명을 재계산한다. Nomination의 모든 후보가
같은 development metadata를 사용했는지, partition 사이 RGB byte 중복이 없는지, 선택 hash가
holdout 서버 실행 전 복사되어 결과까지 연결되는지 확인한다. 이 감사의 PASS는 정확도 PASS가 아니다.
