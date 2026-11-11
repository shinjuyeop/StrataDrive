# 인식 모델 선정과 Jetson 배포의 순서

2026-11-10 사용자 지시를 반영한다. 지금은 사전학습 모델을 비교해 공통 Reference 후보를
선정한다. Jetson AGX Thor/Orin NX에 각각 독립 배포할 것을 고려하지만 보드 최적화는
실제 배포·동일 Reference 측정 뒤에 한다. [기존 배포 원칙](archive/design-decisions.md#adr-0003)을 따른다.

## 현재 판단

YOLOX-S는 초기 RGB→추론→C++ 경계 검증을 위한 기준 모델이다. 여러 계열을 비교하여 최적으로
확정한 모델이 아니다. 추가 학습 L6도 최종 품질 기준을 통과하지 못했다. 이제 추가 학습보다
공개 사전학습 모델의 비교를 먼저 진행한다.

[개발 비교 V1](test-plan/evidence/m10_model_screen_v1/README.md)은 이미 소비한4개 도로의
개발 영상324장·516개 visible GT를 같은5개 모델에 입력했다. 새 보류를 사용하지 않았다.
모든 모델은 FP32/batch1이며 confidence.35다. 모델 고유 입력 크기·전처리·후처리는 유지했다.

| 사전학습 모델 | 정밀도 | 재현율 | F1 | Host P95 ms | ONNX MB |
| --- | ---: | ---: | ---: | ---: | ---: |
| YOLOX-S | 91.38% | 75.97% | 82.96% | 10.30 | 35.86 |
| YOLOX-M | 93.67% | 83.14% | 88.09% | 11.95 | 101.26 |
| YOLOX-L | 94.23% | 88.57% | 91.31% | 17.34 | 216.75 |
| RT-DETRv2-R18 | 59.41% | 93.02% | 72.51% | 12.10 | 80.46 |
| NanoDet-Plus416 | 51.98% | 40.70% | 45.65% | 7.81 | 3.80 |

이번 설정에서는 L의 균형이 가장 좋다. RT-DETR은 놓치는 객체가 적지만 FP328개가 남았고,
NanoDet은 작은 파일·낮은 Host 지연과 낮은 재현율을 함께 기록했다. 공통 confidence를 사용한
초기 비교이므로 모델별 score calibration/최적 설정이나 전체 모델 계열의 우열을 확정하지 않는다.
Jetson 지연·전력·메모리의 순위도 이 Host 표로 판단하지 않는다.

L만 개발 전체 절대 기준을 모두 통과했다. 그래도 S 대비 정밀도 향상은2.85%p로 기존 상대
기준3%p에 미달한다. 이전 [V6의 L 보류 실패](test-plan/evidence/m10_quality_v6/README.md)는
그대로 유효하다. 이번 개발 결과로 그 실패를 상쇄하거나 기본 모델을 교체하지 않는다.
기본 S를 유지하는 것은 교체 검증이 끝나지 않았다는 뜻이며 최적 모델이라는 뜻이 아니다.

후속 [V8 새 Town04 평가](test-plan/evidence/m10_quality_v8/README.md)에서도 L을 검증했다.
새 개발81장은 P93.55%/R89.92%로 절대/상대 PASS였으나, 지명 뒤 취득한 새 보류81장은
P79.65%/R69.77%로 FAIL이다. 보류 person R54.76%·bicycle46.67%·motorcycle25%와
near person2/3이 기준 미달이고 motorcycle recall은 S33.33%보다 낮았다. 전체 개선만으로
이 실패를 상쇄하지 않는다. L이 최종 적합 모델이라는 결론을 내리지 않았다.

새 Town04의 개발 자료는 후속 후보 설계에 사용할 수 있지만 소비한 보류는 설계/재선정이나
새 수용 평가에 재사용하지 않는다. 추가 학습과 보드 최적화를 필수 다음 작업으로 두지 않는다.

## 사전학습 후보 확대와 confidence 비교 V2

[V2 개발 비교](test-plan/evidence/m10_model_screen_v2/README.md)는 S/L·RT-DETRv2-R18에
공식 D-FINE-M, RT-DETRv4-S, ModelScope DAMO TinyNAS-L25-S legacy를 추가했다.
각 모델의 가중치·FP32/native 전후처리를 고정했다. 기존 개발324장으로 사전8점 confidence
grid를 비교하고 **모든 모델의 설정을 봉인한 뒤** Town04 개발81장을 확인했다.
새 보류 수용이나 신규 RGB 수집이 아니다.

| 모델 | 선택 confidence | 앞선4개 도로 P / R | Town04 개발 P / R | 절대 기준: 앞선 도로 / Town04 |
| --- | ---: | ---: | ---: | --- |
| YOLOX-S | 0.40 | 93.03 / 75.00% | 91.00 / 70.54% | FAIL / FAIL |
| YOLOX-L | 0.35 | 94.23 / 88.57% | 93.55 / 89.92% | PASS / PASS |
| RT-DETRv2-R18 | 0.50 | 84.06 / 85.85% | 88.10 / 86.05% | FAIL / FAIL |
| D-FINE-M | 0.50 | 78.28 / 90.12% | 88.15 / 92.25% | FAIL / PASS |
| RT-DETRv4-S | 0.50 | 94.10 / 83.53% | 92.62 / 87.60% | FAIL / FAIL |
| DAMO legacy-S | 0.35 | 67.63 / 81.40% | 74.10 / 79.84% | FAIL / FAIL |

D-FINE의 Town04 재현율과 RT-DETRv4의 precision/Host 지연은 후속 검토 가치가 있다.
그러나 D-FINE은 앞선 도로에서 FP129개가 남고, RT-DETRv4는 앞선 도로의 person66.07%·
bicycle61.67%, Town04 bicycle60%가 기준70%에 못 미친다. L의 과거 V6/V8 보류 FAIL은
이 개발 결과와 별도로 유지한다. 아직 전체 조건을 충족한 최종 Reference를 지명하지 않았다.

공통0.35 결과도 모두 보존했다. 예를 들어 RT-DETRv4의 앞선 도로 P72.98%/R91.09%는
선택0.50에서 P94.10%/R83.53%가 된다. 모델 간 score 척도가 다르므로 공통 threshold
한 점이나 한 도로 결과로 우열을 확정하지 않는다. 이 개발 비교에서 기준을 조정하지 않았다.
0.35 미만 탐색값은 별도 offline 자료형이고 기본 runtime의0.35 계약은 유지한다.

후속 [오류 분석](test-plan/evidence/m10_model_diagnostics_v1/README.md)은 D-FINE calibration
누락51건 중49건, RT-DETRv4 누락85건 중84건에서 맞는 클래스·IoU0.5 박스가 신뢰도0.50
미만으로 제외됐음을 확인했다. D-FINE FP129건 중98건은 positive GT와 IoU0.1도 겹치지
않았고95건은 V4의 반복 배경에 집중됐다. 선택한 세 사례는 원본 instance 영상과 GT를
재구성해 Buildings/Walls·Static/Poles·Bus 영역임을 확인했다. 다른 클래스 겹침을 의미 원인으로
단정하거나 GT/FP를 바꾸지 않았다.

별도 [클래스별 confidence 실험](test-plan/evidence/m10_class_calibration_v1/README.md)은
원래 가중치·입력·native top300을 유지한 채 모델당15,625개 조합을 개발324장에서 비교했다.
class0/1/2/3/5/7 순서로 D-FINE은 `[.60,.40,.70,.50,.50,.60]`, RT-DETRv4는
`[.40,.40,.60,.50,.60,.60]`을 고정했다.0.35 하한과 기존 절대/상대 기준을 유지했다.

| 고정 클래스별 설정 | Calibration P / R | 이미 소비한 Town04 개발 P / R | 절대 기준 cal / Town04 | 상대 기준 cal / Town04 |
| --- | ---: | ---: | --- | --- |
| D-FINE-M | 92.00 / 89.15% | 89.84 / 89.15% | PASS / PASS | FAIL / FAIL |
| RT-DETRv4-S | 85.74 / 88.57% | 86.36 / 88.37% | PASS / FAIL | FAIL / FAIL |

D-FINE의 calibration FP는129→40으로 줄었다. 그래도 calibration에서 bus recall95%가
S100%보다 낮고, Town04 precision 향상은2.93%p로3%p에 미달한다. RT-DETRv4의 Town04
bicycle recall60%도 남았다. Town04는 이미 소비한 개발 regression이며 새 보류나 독립 수용이
아니다. 이 결과를 보고 설정을 다시 조정하지 않았다.

새 보류 평가에 넣을 **개발 후보는 D-FINE-M 클래스별 설정으로 고정**한다.
[파생 후보 프로파일](../profiles/perception-class-calibration-candidates-v1.json)은 기존 model/
전처리/source/selection SHA와 설정을 묶으며 runtime profile이 아니다. 이어서 새 quality
protocol에서 S와 이 단일 후보·기존 gate를 고정해 새 준비/개발/보류를 취득했고, 아래 V9 결과를 따른다.
최종 Reference 채택은 미완료이며 과거 calibration 상대 기준 FAIL과 기본 S를 유지한다.

## 지금 확인하는 배포 고려 사항

- 모델·가중치·출처 revision·license·SHA256을 고정하고 재현 가능한 추론 입력/출력을 둔다.
- ONNX graph의 opset·custom domain·입출력·별도 가중치·배포 도구 경로를 확인한다.
- 모델과 전후처리를 live 수신 계약에서 분리하여, 나중에 보드별 runtime을 연결할 수 있게 한다.
- Thor/Orin NX에서 각각 빌드·배포·검증할 기록을 남긴다. 두 보드의 동일 binary/engine을 가정하지 않는다.

V1의5개 graph는 custom domain이 없고 ORT CPU/CUDA 검사를 통과했다. RT-DETR에는
opset16 GridSample9개, NanoDet에는 graph input으로 노출된 initializer158개가 있다.
이 정보는 후속 변환 때 확인할 항목이다. TensorRT import나 Jetson 지원을 확인한 결과는 아니다.

V2의6개 graph도 custom domain/외부 initializer가 없고 ORT CPU/CUDA를 통과했다.
D-FINE에는 GridSample12개, RT-DETRv4에는9개가 있다. 모델별 opset·operator·입출력
목록은 [배포 고려 기록](test-plan/evidence/m10_model_screen_v2/deployment-review.json)에 둔다.
각 보드의 TensorRT import·정확도·전체 stack 성능은 실제 배포 때 확인한다.

## 후속 순서

1. 개발 비교 결과를 바탕으로 후속 후보·공통 Reference 조건을 고정한다. 더 넓은 모델 탐색이
   필요하면 개발 자료에서 수행하고 최종 평가와 구분한다. 추가 학습을 필수로 두지 않는다.
2. 새 지도 조사·사전 조건으로 독립 평가 자료를 마련해 정확도와 live 경로를 검증한다.
   이미 소비한 V1–V9 보류 영상/예측을 설계·재선정·새 수용 평가에 쓰지 않는다.
3. M12에서 동일 Reference를 Thor/Orin NX에 각각 배포하고 실제 전체 시스템 성능을 측정한다.
4. 그 다음에 보드별 TensorRT engine·FP16/INT8·모델/입력/rate 변경을 검토하고 재검증한다.

현재 보드별 engine 생성·양자화·전력/클록 조정·보드 최적화와 실제 배포는 미실행이다.
V2에는 confidence calibration을 포함했다. 새 학습·crop/ensemble은 실행하지 않았다.

## 고정 후보의 새 도로 평가 V9

[V9 새 평가](test-plan/evidence/m10_quality_v9/README.md)는 전체 미사용 경로38/85를 지도만으로
선정하고 모델 없는 준비198장·새 개발/보류 각81장을 평가했다. 고정 D-FINE-M은 개발
P95.20%/R92.25%로 절대·상대 PASS다. 봉인 이후 취득한 보류는 P86.09%/R76.74%로,
상대 PASS지만 전체 recall과 person/motorcycle 각50%가 절대 기준에 미달한다.
따라서 최종 Reference 미채택·기본 S·M10 OPEN을 유지한다. 설정을 보류에서 다시 고르지 않았다.

모든459개 raw pair·실패/별도 복구·full model raw324개·새 source 재감사를 보존한다.
미래 RGB 제외는5449개다. 다음은 개발 자료의 작은 VRU/Rider 누락과 입력 해상도/사전학습
후보 효과를 검증해 새 설정을 고정하는 일이다. 보류는 독립된 새 도로/새 RGB로 다시 취득한다.
Thor/Orin 각각의 전체 stack 배포를 고려하되 보드별 최적화는 배포·측정 이후에 수행한다.


## 입력 해상도와 car-confidence 후속 후보

[입력 해상도 비교](test-plan/evidence/m10_resolution_v2/README.md)는 기존 가중치로640/960/1280을
시도했다. 원래 수치 실패와640 cache reference 오류·복구를 보존하고,1280은 수치 미달로 제외했다.
새 BASIC backend의640/960은 native CPU/CUDA6건을 통과했다.960은 개발405장에서 P94.66%/
R90.70%로 개선됐지만, 소비한 V9 개발의 car recall32/33→31/33 때문에 원래 후보는 거절했다.

별도 고정한 car confidence.70→.60 후속은486개 개발/설계에서 P95.15%/R91.34%·모든 site
절대 gate와 S-relative·640 무회귀를 통과했다. V9 개발도 변경 설계에 사용했으므로 독립 검증이
아니다. [파생 후보 프로파일](../profiles/perception-resolution-candidates-v1.json)은 새960 ONNX/
전처리/BASIC/vector/backend와 근거 SHA를 고정한다. 새 학습이나 보드 최적화는 하지 않았다.
다음은 이 단일 후보의 모델 없는 준비·새 개발/보류 평가다. 최종 모델 채택·runtime 교체는 미완료다.


[CARLA 원본 해상도 비교](test-plan/evidence/m10_camera_resolution_v1/README.md)는 모델960과
confidence를 유지하고 source640×384부터3840×2304까지 실제 촬영했다.4K를 품질 평가 전에
기술 기준으로 고정했고, 같은 개발 배치 각81장에서640은P98.37%/R93.80%,4K는129TP/0FP/0FN이다.
수치15건 중14PASS/1FAIL과 종료 실패3쌍·사전 복구를 보존했다. 전체180쌍·미래 제외5629개다.
[4K source profile](../profiles/perception-camera-source-candidates-v1.json)은 다음 새 평가용이며
기존 S/runtime640은 유지한다.4K 순차 health/resize/추론 P95 약93.64ms로 live20Hz는 미수용이다.
이후 native ingress/전처리 검증은 아래 후속 기록으로 이어진다. 새 준비·개발/보류와 전체 wall 수용은 남아 있다.
새 학습·보드 최적화·실제 Jetson 배포는 수행하지 않았다.

후속 [비동기 component](test-plan/evidence/m10_async_native_v1/README.md)는 이 고정 모델과
4K media를 유지해 상태 수신/조회와 인지를 분리했다. 정상 BGRA→RGB/전처리/추론에서는43개
완료가 모두100ms를 초과했다. 따라서 비동기 구조의 동작과 유효한 인지 공급을 따로 판정한다.
현재는 PC 변환·전처리 병목과 실제 ingress/기존 제어 연결을 먼저 해결해야 하며, 품질 후보를
과거 보류에서 다시 선택하거나 기한을 늘리지 않는다. 새 독립 품질·각 Jetson 배포는 여전히 후속이다.

2026-11-11 후속 [전처리 개선·실제4K ingress](test-plan/evidence/m10_native_preprocess_v1/README.md)는
개발84장의 RGB/tensor를 그대로 유지하며 전처리 P95를103.36→42.02ms로 줄였다.
비동기 재생은46회 발행/21개 frame 소비로 개선됐지만, 실제 CARLA/Epic과 GPU를 공유하면
37개 완료가 모두 late여서 fresh-output gate FAIL이다. 실제 camera13.60Hz·관측 consumer50Hz,
world67.72Hz이며 원본60개를 포함한 미래 제외는5689개다. 다음은 실제 부하에서100ms 내
공급을 확보한 뒤 실제 상태/보호·제어 연결과 새 독립 품질 평가를 진행하는 것이다.
기존 모델/기한/runtime·M10 OPEN·Jetson 최적화 후속 원칙을 유지한다.
