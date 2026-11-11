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
| TC-PER-034 | 고정 epoch17 L6/native11채널·별도 offline envelope·새 준비 numeric | 이전 model/manifest byte/hash·기존85채널 식별자 혼용 거절·CPU/CUDA/OpenCV raw와 완성 count/class/box/score 동등성 |
| TC-PER-035 | 새215/127 map-only road·실제 준비/평가·모든 actor/Rider | 과거3973+모든 준비 제외·거리/episode/RGB 분리·실제 mask/pose/road 재구성·최소 지원·원래 실패와 준비 기준 보존 |
| TC-PER-036 | 단일 후보·원래 absolute/relative·지명 후 보류·시작 실패/복구 | 전체/class/stratum 엄격 채점·개발 실패도 descriptive holdout 유지·소스/계획/모델·제한 무변경·cold/late/실패·순서/압축 재감사·자동 runtime 교체0 |
| TC-PER-037 | 사전학습5종·동일 개발324장·native 전후처리·배포 고려 | 공식 model/hash/license·CPU/CUDA/독립 참조·top300 set 대응·보류 거절·공통 confidence 초기 비교와 최종/Jetson 수용 분리 |
| TC-PER-038 | 새 Town04 지도372곳·모델 없는 준비·실패/별도 복구 | first eligible7/25·다른 road/50m·초기 가림 FAIL198장과 종료 FAIL99장 보존·가림차20cm 외 변경0·동일 제한 복구·모든 원본 제외 |
| TC-PER-039 | 고정 공식 L·새 개발/보류162장·원본/점수/순서 | source/model/plan 사전 고정·unchanged absolute/relative·개발 지명 후 보류 취득·raw/GT/pose/visibility/score와 압축 재감사·과거/현재 FAIL과 기본 S 유지 |
| TC-PER-040 | 공식 D-FINE-M·RT-DETRv4-S·DAMO legacy 가중치와 native FP32 추론 | 출처/SHA·weights-only strict load·byte 동일 재export·RGB 색상 회귀·PyTorch/ORT CPU/CUDA 전체 raw와8개 threshold 검출 동등성·초기 실패 보존 |
| TC-PER-041 | 개발324장 confidence calibration과 봉인 후 Town04 개발81장 | 사전8점 grid/동점 규칙·모든 모델 선택 봉인 후 check 실행·별도 offline detection/기본0.35 계약 유지·보류 거절·GT/분모/기준 무변경 |
| TC-PER-042 | 모델6종의 raw2430개와19440개 threshold set·원본 source 재실행 | 모든 cache hash·전체 threshold 재구성·선택/점수/실행 순서·압축/새 source 경로 감사·각 Jetson 전체 stack 배포 고려와 실제 보드 수용 분리 |
| TC-PER-043 | D-FINE/RT-DETRv4의810개 native top300·FP/FN·Rider 겹침 | 기존 strict matching/count/GT 유지·낮은 score와 위치/다른 class 겹침 분리·일대일 maximum matching 상한·전체 오류와 크기/조건별 분모 보존 |
| TC-PER-044 | V4 개발 FP 세 사례의 원본 RGB/instance·CityObjectLabel | 사전 case/source SHA·원본 RGB byte 일치·전체 frame GT 재구성·ROI tag histogram·Buildings/Static/Bus 확인으로 기존 GT/FP 변경0 |
| TC-PER-045 | 클래스별5점×6class·모델당15625 조합·사전 gate/동점 규칙 | 기존 scalar/source/weights 유지·0.35 하한·class 독립 합성의 실제 raw/primary 대조·전체31250 scorecard와 봉인·소비한 Town04를 새 수용으로 승격0 |
| TC-PER-046 | 고정 혼합 vector의6 numeric probe·파생 identity·새 source 감사 | CPU/CUDA/upstream full300·5개 scalar/선택vector exact class와box/score tolerance·810 raw replay·초기 JSON 비교 실패와 보완 annex 보존·최종/runtime 자동 교체0 |
| TC-PER-047 | Town04 전체 route 미사용 도로·고정 준비198장과 모든 실패 | 지도만으로 최초 적격38/85 선택·기존4990 RGB와 모든 준비 제외·계획 actor/Rider/가림 지원·동일 예산의 별도 종료 복구 보존 |
| TC-PER-048 | 고정 S/D-FINE-M native 수치6건과 새 개발/보류 각81장 | full300·기존 S raw와 완성 검출 수치·class vector 고정·모든 raw 출력 재해석·기존 절대/상대 gate·개발 지명 뒤 보류 취득·자동 승격0 |
| TC-PER-049 | 모든 V9 raw·GT/pose/visibility·점수·실패·압축 새 source 감사 | 실패한 준비99장은 diagnostic만 재생·채택 불가·전 시도 RGB 제외 합집합·원래 종료 실패와 모델 품질 판정 보존·Jetson 수용과 구분 |
| TC-PER-050 | 불변 가중치·640/960/1280 native 위치 cache와 수치 실패 | cached640 원본과 regeneration 차이·원래 FAIL/2개 profile·CPU fallback 금지·수치 미달1280 제외·vendor와 원래 source byte 보존 |
| TC-PER-051 | 검증된640/960·405 개발 지명 이후81 소비 개발 회귀 | full300 native6건·모든 raw/기존 gate·site 절대 기준·640 class 무회귀·car32/33→31/33 원래 거절 보존 |
| TC-PER-052 | car confidence.70→.60 단일 별도 revision·설계486장 | 새 source freeze·native3건·원래 vector/JSON 일치 뒤 재해석·기준 무완화·486장 전부 설계 자료 명시·새 개발/보류 필요·자동 교체0 |
| TC-PER-053 | 원본1458/파생486 raw·실패·새 source 압축 재현 | object SHA/경로 무결성·primary/지명/순서 재계산·cached640 오류/복구와1280 FAIL·개발 적격과 독립 수용/Jetson 구분 |
| TC-PER-054 | 실제 source640/1280/1920/2560/3840·native frame/GT | 원본 pixel 직접 취득·손실 없는 raw/stored hash·동일 FOV/aspect·native support와 canonical box·runtime640 불변 |
| TC-PER-055 | 고정960 모델·실제 orig sizes·최대 source 사전 지명 | native3probe×5source·full300/완성 vector·14PASS1FAIL 보존·본 비교 전에4K 봉인·cold/late·실제 비용과20Hz 구분 |
| TC-PER-056 | 전180쌍·native162 raw·정답·종료 실패/복구·압축 새 source | 원본mask 재구성·legacy640 정답81건 일치·전 시도 제외5629개·사전 bounded recovery·개발 품질과 독립 수용/Jetson 구분 |

TC-PER-037은 [사전학습 비교 기준](perception-model-screen-v1-protocol.md)과 [5종 개발 결과](evidence/m10_model_screen_v1/README.md)를 따른다.
TC-PER-040–042는 [V2 사전 비교 기준](perception-model-screen-v2-protocol.md)과 [6종·calibration/개발 확인 근거](evidence/m10_model_screen_v2/README.md)를 따른다.
TC-PER-043–044는 [진단 기준](perception-model-diagnostics-v1-protocol.md), [mask annex](perception-model-diagnostics-v1-mask-annex.md), [원본 오류 분석](evidence/m10_model_diagnostics_v1/README.md)을 따른다.
TC-PER-045–046은 [class calibration 기준](perception-class-calibration-v1-protocol.md), [감사 보완](perception-class-calibration-v1-audit-annex.md), [고정 후보 검증](evidence/m10_class_calibration_v1/README.md)을 따른다.
TC-PER-038–039는 [V8 기준](perception-quality-v8-protocol.md), [준비 revision](perception-quality-v8-preparation-revision.md), [종료 실패 복구](perception-quality-v8-recovery.md)와 [새 지도 평가 근거](evidence/m10_quality_v8/README.md)를 따른다.

TC-PER-034–036은 [V7 기준](perception-quality-v7-protocol.md)과 [새 개발/보류·복구 원본 근거](evidence/m10_quality_v7/README.md)를 따른다.

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

TC-PER-047–049는 [V9 사전 기준](perception-quality-v9-protocol.md)과 [새 D-FINE-M 평가 근거](evidence/m10_quality_v9/README.md)를 따른다. 지도/준비 복구는 각각 별도 사전 annex에 남기며 원래 실패와 고정 gate를 유지한다.

TC-PER-050–053은 [해상도 V1 기준](perception-resolution-v1-protocol.md), [수치 조사 annex](perception-resolution-v1-numeric-annex.md), [검증된 V2 기준](perception-resolution-v2-protocol.md), [car 후속 기준](perception-resolution-car-v1-protocol.md), [전체 근거](evidence/m10_resolution_v2/README.md)에 연결한다.

TC-PER-054–056은 [카메라 원본 기준](perception-camera-resolution-v1-protocol.md), [사전 복구 한도](perception-camera-resolution-v1-recovery.md), [4K 개발 비교 근거](evidence/m10_camera_resolution_v1/README.md)에 연결한다.

TC-PER-066–068은 [native4K 준비·가용성 사전 기준](perception-native-startup-v1-protocol.md)과
[실행/전체 원본 근거](evidence/m10_native_startup_v1/README.md)에 연결한다. 명시적 합성 준비와
sensor cold 분모·10/13/20Hz 진단·240장씩의 유한 실제 반복을 구분하며 기존100ms/Reference20Hz를 유지한다.

TC-PER-069는 [원래 저장 overflow 이후의 유한 Host 메모리 기록 기준](perception-native-memory-v1-protocol.md)을 따른다.
원래232장 실패와 누락된 per-decision trace를 성공으로 재해석하지 않으며 새 revision은 실패 시에도
최종 worker/decision trace를 보존한다. 이 recorder는 생산 인지 큐와 별도인 유한 진단 도구다.


TC-PER-070–072는 [실제 비동기 월드 사전 기준](perception-world-async-v1-protocol.md)과
[동기/비동기 실행 근거](evidence/m10_world_async_v1/README.md)를 따른다. 실제 snapshot의
누락/역순·상태100ms 침묵·원래 두 기한·원자적 관측을 검증하고, 같은4K 조건에서 sync1회와
async2회를 비교한다. 클라이언트 tick0회·실제 상태 진행과 전체 raw/LFS payload 감사를
구분하며 wall20Hz·품질·주행·보드 수용으로 확대하지 않는다.


TC-PER-073–075/C-M10-PER-69–71은 [GPU readback 사전 기준](perception-readback-v1-protocol.md),
[재할당 후속 기준](perception-readback-pool-v1-protocol.md), [전체 실행 근거](evidence/m10_readback_pool_v1/README.md)에 연결한다.
원래 acquisition/receipt100ms·4K/Epic를 유지하며 CPU stage clock과 SDK frame/time을 대조한다.
성공4회/실패2회·원본600장·future exclusion7613·source565→574→580을 보존한다.
모든 wall 통계/실패 판정/원본 BGRA·RGB/정확한 입력을 재감사하고 변조96건을 거절한다.
카메라15.63Hz 조건도 유효 조회16.10%이므로 기본값·wall20Hz·전체 인식 경로 수용으로 올리지 않는다.


TC-PER-076–078/C-M10-PER-72–74는 [복사 사전 기준](perception-frame-copy-v1-protocol.md),
[뷰포트 후속 기준](perception-viewport-v1-protocol.md), [전체 실측](evidence/m10_viewport_v1/README.md)에 연결한다.
SDK owner lifetime·일회용 immutable copy·선행 할당·단계 identity/clock과 원래 기한을 검사한다.
4K/Epic 유지5회/500장·source580→595→601·미래 제외8113·Python354·변조110건을 보존한다.
복사는 약2.8ms이나 전체 약127–129ms/camera 약13Hz이므로 기본값·wall20Hz·실제시간1× 수용은 OPEN이다.


TC-PER-079–081/C-M10-PER-75–77은 [2K/4K 비교 기준](perception-source-compare-v1-protocol.md),
[해상도 guard 수정 기준](perception-source-compare-v2-protocol.md), [원본·비교·한계](evidence/m10_source_compare_v2/README.md)에 연결한다.
2K typed owner/전처리 exact/ASan+UBSan, 같은 새 모듈의4K1회·2K2회 전체 지연과 원래 기한을 검사한다.
개발81쌍씩의 GT/전체 예측·미세조건 차이를 재생하고 모든724개 raw와 최초 zero-camera FAIL을 보존한다.
Python370·native sanitizer3·변조112건 PASS다. 원래621/626개 봉인에서 공통 도우미1개 누락을
보충 보관하지만 사전 봉인 완료로 소급 인정하지 않는다. 재현 PASS는20Hz·새 독립 품질·차량·Jetson
수용을 대신하지 않는다. 기본값과100ms 기한을 유지하고 실제시간1×는 목표로 남긴다.
