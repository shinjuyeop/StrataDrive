# Host 영상 인지 계약

`m10-perception-host-v1`은 M10의 첫 **2D RGB 객체 검출·tracking Host 프로파일**이다.
학습된 주행 판단은 M11이다. 거리·속도·충돌 위험·주행 가능 영역을 2D box로 추측하지 않는다.
전체 ODD 인지 성능, 실시간/Jetson 수용과 차량 제어 연결은 이 프로파일의 완료 조건이 아니다.

## 모델과 입력

[고정 프로파일](../../profiles/perception-host-v1.json)은 OpenCV Zoo의 YOLOX-S COCO 사전학습
ONNX FP32를 commit·SHA256·크기와 함께 지정한다. 가중치는 명시적인 fetch 명령으로만 받으며
추론 생성자에서 다운로드하지 않는다. Apache-2.0 license와 출처를 함께 보존한다.
CPUExecutionProvider·4개 intra-op/1개 inter-op thread를 명시한다. GPU로 실행했다고 표시하지 않는다.

선택형 `--execution cuda`는 [별도 Host 실행 descriptor](../../profiles/perception-cuda-host-v1.json)를
검사한다. ORT1.23.2·CUDA device0·FP32/TF32 off·HEURISTIC convolution·2GiB allocator limit와
CPU node fallback 금지를 고정한다. Semantic/model/threshold 계약은 동일하다. Provider option
readback과 같은 RGB의 CPU/CUDA raw tensor·box 동등성을 확인한다. 첫 cold 추론도 분모에 남는다.
등록 provider 목록에 CPU가 보여도 graph의 CPU 배정은 명시적 금지 설정으로 거절한다.
GPU 사용 불가/설정 불일치는 초기화 실패이며 몰래 CPU로 재실행하지 않는다.
[ORT CUDA 설정](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)을 따른다.

Camera는 640×384 RGB8·20Hz·수평 FOV90° pinhole이다. Calibration revision과 실제 pose는
별도 식별하며 frame metadata는 epoch, clock instance, camera, frame, 취득 ns를 가진다.
CARLA BGRA→RGB 변환은 sensor adapter에서 한 번 수행한다. 입력은 RGB immutable bytes다.
GT instance/semantic/depth·actor 정답은 추론 입력 type에 없다.

명백한 영상 정보 상실은 추론 전에 unavailable로 처리한다. RGB→8bit luma 표준편차<2,
luma≤5 비율>98%, luma≥250 비율>98% 중 하나면 flat/blackout/whiteout이다. 이는 초기 Host
입력 건전성 fixture이며 렌즈 일부 가림·흐림·미검출·전체 ODD를 검출한다는 보장이 아니다.
균일한 영상에서 검출0개를 정상 빈 도로로 해석하지 않기 위한 별도 검사다.

전처리는 원본 RGB 순서·좌상단 배치·114 padding·bilinear resize, `[1,3,640,640]` float32
0..255다. Mean/std나 /255는 적용하지 않는다. 출력 `[1,8400,85]`를 stride8/16/32 grid로
복원하고 objectness×class confidence≥0.35, class별 IoU>0.5 NMS를 적용한다.
COCO class0/1/2/3/5/7(person/bicycle/car/motorcycle/bus/truck)만 내보낸다.
Score 내림차순·동점 anchor 순서이며 NMS 전1000개, 후100개 초과는 **unavailable**이다.
잘라낸 목록을 완전한 정상 결과로 내보내지 않는다. Image 밖/padding box는 원본 경계로 clip하고
면적0을 제외한다. NaN/Inf·잘못된 shape/score·decode overflow는 전체 결과를 무효로 한다.

## 출력·신선도·세션

고정 native4K/모델960 후보에는 [별도 비동기 경계](perception-async-native-v1.md)를 추가했다.
해당 결과는 아래의 기존 S/640 schema와 구분하며 runtime을 자동 교체하지 않는다.

출력은 half-open `[x1,y1,x2,y2)` **원본 image pixel** box·class·confidence다.
정상 결과의 빈 목록은 `valid=true`다. 검출 실패/timeout과 구분하며 빈 목록도 도로가 안전하다는
증거가 아니다. Model hash·profile revision·calibration·camera·epoch·clock·frame·취득 ns를 보존한다.

Expiry는 **취득+100ms, exclusive**다. Completion/publish/consumer 시각은 별도이며 취득을
갱신하지 않는다. 이 수치는 영상 경계 전용으로 기존 wheel/command30ms 계약을 늘리지 않는다.
Host processing budget도100ms이며 monotonic wall의 submit→완료에 적용한다. Simulation ns와
wall ns를 차감하지 않는다. Offline replay의 source clock과 wall 처리 지연은 별도로 보고한다.
20Hz 입력에서 처리량 부족/overload를 숨기지 않으며 100ms budget은50ms throughput 보장이 아니다.

Worker는 single inference owner·대기1개 latest-frame queue다. 새 frame이 대기를 대체하면 drop을
기록한다. 실행 중 추론을 강제 중단하거나 늦은 출력을 정상 완료로 바꾸지 않는다. Completion 때
generation·현재 source age·wall budget을 재검사한다. Session 전환 중 과거 완료는 폐기한다.
정지 시 join timeout이면 worker가 멈췄다고 보고하지 않는다. Inference exception은 unavailable이다.

### 명시적 준비와 실제 카메라 수신

선택형 [startup descriptor](../../profiles/perception-startup-host-v1.json)는 기존 모델·threshold를
유지하고 `require_preparation=True` worker에 별도의 준비 단계를 추가한다. `prepare()`는 동일한
추론 owner에서 고정 synthetic RGB gradient를 정확히3회 실행한다. 첫 cold call도 모두 기록한다.
전체 준비10s exclusive, 뒤2회 각각100ms exclusive를 만족해야 `READY`다. Model 생성 비용은
별도로 측정하며 이10s에는 포함되지 않는다. `NOT_REQUESTED/PREPARING/FAILED/CANCELLED`에서는
INIT·센서 제출을 열지 않는다. 준비 성공 후에도 명시적 INIT가 필요하며 probe는 센서/track/C++
출력으로 발행하지 않는다. 준비 실패·clock 역행·timeout은 같은 worker에서 재시도하지 않는다.
Timeout 뒤 돌아온 backend가 READY를 복원하지 못하며, thread 정지는 실제 join 성공으로만 판정한다.
READY는 모델 실행 준비 상태다. 현재 영상의 가용성·정확도·운행 허가를 의미하지 않는다.

기존 기본 경로와 offline CLI는 준비를 생략하고 첫 cold sensor call을 원래 분모에 포함한다.
선택형 준비 경로는 startup3회와 센서 처리 분모·시간을 **둘 다** 보고한다. 이전 v1 측정의 cold
call을 삭제하거나 성공으로 바꾸지 않는다.

`BgraCameraIngress`는640×384 BGRA callback을 immutable copy로 보관하는 latest1 slot이다.
추론·disk IO를 callback에서 실행하지 않는다. Tick owner는 실제 snapshot의 frame/source를
최대128개 기억하며, 일치하는 callback만 RGB로 변환해 worker의 별도 latest1 queue에 넘긴다.
아직 tick이 완료되지 않은 callback은 기다리고, 관측되지 않은 오래된 frame·timestamp 불일치·
layout/단조성 오류는 무효화한다. SDK floating timestamp 반올림 비교 허용오차는1µs이며 원천
timestamp를 snapshot 값으로 교체하지 않는다. 관측 clock의 연속 tick10ms 오류는 latch한다.

이 경로의 wall budget은 adapter `offer` 수신 시각부터 완료까지100ms다. Queue·RGB 변환 시간을
포함하며 pump 시각으로 갱신하지 않는다. Snapshot도 같은 receipt+100ms에 만료되므로 source
simulation clock이 멈춘 경우에도 이전 결과를 무기한 유지하지 않는다. Receipt가 없는 기존
`submit` 호출은 submit 시각을 사용한다. 원래 source+100ms 검사도 함께 유지한다.
Camera 오류·닫힘은 pending/current와 실행 중 generation을 무효화한다.

실제 CARLA fixture는 기존 설치의 `StrataM7SensorFrame5`·`StrataM7NativeProbe` 두 flag와
camera `role_name=m7_frame5`를 함께 적용해 **원래 frame%5=0에서 취득**한다. 부동소수
`sensor_tick=.05`만 사용한 긴 실행의40/60ms 간격 실패는 보존한다. 이 fixture는 native owner
bind/제어 RPC를 호출하지 않으며 parked actors의 physics를 끈다. C++ 검증은 실제 소비 결과의
사후 typed replay다. IPC·차량 제어 연결로 해석하지 않는다.
[실행 근거](../test-plan/evidence/m10_live_perception/README.md)를 따른다.

`--rgb-postprocess enabled`는 [별도 CARLA RGB descriptor](../../profiles/perception-carla-rgb-host-v1.json)의
Low/ClearNoon/frame5 설정과 실제 sensor attribute readback을 검사한다. Geometry640×384/FOV90과
모델/threshold는 같다. 초기 disabled 설정에서 관측한 검은 하늘·HUD 경고가 후속 표본에서 해소되었다.
Low/Epic 진단 수집과 정확도 수치를 모두 보존하며, renderer 품질 전체 수용이나 정확도 개선을
자동 선언하지 않는다. Disabled 경로는 초기 결과 재현용으로 남는다.

Central의 별도 C++ receiver는 승인된 session/model/calibration을 고정하고 schema·identity·원래
expiry·box·score·count·단조 frame/source를 재검사한다. Reject는 current snapshot을 무효로 하며
이전 frame을 fresh로 재발행하지 않는다. 다음 더 새로운 유효 frame은 인지 가용성을 회복할 수 있지만
차량 FAIL_SAFE/permission을 해제하지 않는다. Clock 역행은 새 INIT까지 latch한다.
Accepted snapshot은 `now<expiry`일 때만 읽을 수 있다. 이 receiver는 actuator/제어 권한이 없다.

## Tracking과 downstream

Class별 greedy IoU≥0.3 matching과 최근10frame(정상 주기500ms) 이력을 제공한다.
ID는 session 안에서만 유효하고 새 epoch/clock에서 reset한다. Source gap>100ms에는 기존 track을
버리며 현재 검출되지 않은 물체를 가짜 fresh 검출로 보간하지 않는다. 같은 frame/source 역행을 거절한다.
History에는 실제 관측 원천과 box만 있다. 이미지 속도를 차량 상대 m/s로 해석하지 않는다.

M11은 이 2D 출력만으로 metric trajectory를 만들 수 없다. Localization·metric fusion·보정된 risk·
인지 상실 시 유효 classical 입력의 정의를 추가해야 한다. 기존 상태 `[4,6]` 속도 제안에 2D box나
GT를 0/default feature로 끼워 넣지 않는다. 인지 invalid이면 그 인지를 요구하는 planner도 unavailable이다.

## 검증

[검증 프로토콜](../test-plan/perception-protocol.md)의 단위·고장·Python→C++ replay·실제 ONNX·
CARLA RGB/instance pair와 독립 evaluator를 구분한다. TP/FP/FN@IoU0.5는 visible-instance box
기준이며 COCO mAP와 다르다. 작은/가려진 물체 제외 수를 공개한다. 정확도 수용 threshold는
이번 초기 프로파일에서 미정으로 남기며 측정 결과에 맞춰 threshold를 바꾸지 않는다.

출처: [OpenCV Zoo 모델·license](https://github.com/opencv/opencv_zoo/tree/a74cdfad334b102cbd8daed769fbe1d4cb1c327a/models/object_detection_yolox),
[CARLA instance sensor](https://carla.readthedocs.io/en/latest/tuto_G_instance_segmentation_sensor/).
