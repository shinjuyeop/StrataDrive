# M10 v3 자산·가시성 준비와 모델 비교 사전 기준

2026-11-07. [V2](perception-quality-v2-protocol.md)의 strict visible IoU0.5,
Pedestrians12/Rider13→person, 최소25pixel/side4, score0.35와 절대·상대 품질 gate를 유지한다.
기존 v1/v2와 준비셋 RGB를 제외하고 새 개발81·보류81배치를 사용한다.

먼저 별도 camera spawn4에서 개발·보류 자산/방향의6class×4조건×3기상144개와
가림 없는 참조36개, 총180개 준비 장면을
수집한다. 모델을 실행하지 않고 모든 계획 actor의 spawn·settled pose·visible support를 확인한다.
이전 서버를 crash시킨 European HGV는 서버 시작 전에 거절한다. 준비 FAIL이면 최종 평가를
freeze하지 않는다. 같은 pose에서 가림 물체를 제거한 참조와 비교해 가림 장면의 target visible
support가0 초과·참조의95% 미만인지도 검사한다. 준비 영상은 평가에 재사용하지 않는다. 다른 camera spawn의 가시성은
보장하지 않으므로 최종 개발/보류의 class×조건≥2/3 coverage도 별도로 유지한다.

최종 camera spawn은 개발5/보류6이다. Near12/14m, medium20/22m, occluded16/18m,
far는 person28/30m·bicycle/motorcycle34/36m·car/bus/truck38/40m이다. 준비셋은 이보다1m 멀리
배치한다. 첫 준비에서 held walker 가림3개가20pixel이어서 평가 전 target의 right를0.85→1.2m로
옮긴 v3b로 전체 준비를 재수집한다. 원래 FAIL/원본/계획을 보존한다.
이 유한 class별 거리 범위를 전체 ODD나 v2와 동일 분포라고 해석하지 않는다.

후보는 baseline S, `medium-v3`(YOLOX-M), `medium-refine-v3`(M+고정 중앙2배 확대)다.
[모델 출처](../../third_party/megvii-yolox/README.md)의 hash를 사용하고 RGB unscaled tensor,
class별 NMS0.5·max100·확대 경계2pixel을 고정한다. Cross-class 억제는 없다.
M은 별도 offline envelope에 실제 model hash를 기록한다. 기존 live/C++ 프로파일의 S identity로
발행하지 않는다. CPU/CUDA·독립 OpenCV tensor/raw 비교를 준비셋에서 수행한다.

준비 PASS 이후 코드·모델·계획·프로토콜·제외 목록을 freeze한다. 개발셋에서만 두 후보를 비교하고
기존 relative PASS→F1→recall→precision→ID 순서로 하나를 봉인한다. 해당 selection을 보류 서버
시작 전에 복사한다. 보류에는 baseline과 지명 후보만 실행한다. 품질/coverage가 실패해도 표본·gate를
바꾸거나 다음 후보로 재탐색하지 않는다. 원본에서 정답·점수·선택을 재구성한다.

모든 cold·초기화·단계 시간을 보존하며 offline100ms admitted와 strict raw 점수를 분리한다.
이 실험으로 live20Hz·주행/metric fusion·vehicle permission을 수용하지 않는다. 후보 채택에는
개발·보류의 절대·상대 gate와 coverage가 모두 필요하며 자동 runtime 교체는 없다.
