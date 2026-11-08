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
