# 영상 인지 실행과 평가

M10 Host 프로파일의 입력은 RGB이고 출력은 원본 영상 pixel 좌표의 객체·관측 이력이다.
거리/trajectory/차량 command는 만들지 않는다. [계약](interfaces/perception.md)과
[실행 근거](test-plan/evidence/m10_perception/README.md)의 정확도·timing 한계를 먼저 확인한다.

현재 모델 비교와 Jetson 배포/최적화의 순서는 [모델 선정 안내](perception-model-selection.md)를
따른다. S는 초기 연동 기준이며, [사전학습5종 개발 비교](test-plan/evidence/m10_model_screen_v1/README.md)를
모델 최종 선정이나 보드 성능 검증과 구분한다.

공식 L의 [V8 새 지도 평가](test-plan/evidence/m10_quality_v8/README.md)는 개발 PASS·보류
FAIL을 기록했다. 원본·실패한 준비와 동일 조건 복구·선정 순서는 근거 묶음에서 재감사한다.

[사전학습 비교 V2](test-plan/evidence/m10_model_screen_v2/README.md)는 공식 D-FINE-M·
RT-DETRv4-S·DAMO legacy를 추가한6종 비교다. 개발324장으로 confidence를 고정한 뒤
Town04 개발81장을 확인했다. 모델별 남은 FP/class recall과 과거 보류 실패를 보존하며
최종 Reference를 확정하지 않았다.0.35 미만 탐색값은 별도 offline detection으로 처리하고
기존 runtime profile은 유지한다. 전체 raw 재생 명령은 해당 근거의 `check-archive.py`를 따른다.

후속 [오류 분석](test-plan/evidence/m10_model_diagnostics_v1/README.md)과
[클래스별 confidence 검증](test-plan/evidence/m10_class_calibration_v1/README.md)은 개발 자료만
사용했다. 새 품질 평가 후보는 D-FINE-M의 `[.60,.40,.70,.50,.50,.60]`(class0/1/2/3/5/7)이다.
calibration·소비한 Town04 개발의 절대 기준은 PASS지만 상대 FAIL을 유지한다.
파생 후보 프로파일은 offline 전용이다. [V9 새 도로 평가](test-plan/evidence/m10_quality_v9/README.md)에서
이를 그대로 고정해 개발 P95.20%/R92.25%·절대/상대 PASS, 새 보류 P86.09%/R76.74%·
상대 PASS/절대 FAIL을 확인했다. 보행자/오토바이 recall50%가 남아 기본 S를 유지한다.
원본459쌍·모든 raw 모델 출력·새 source 재감사와 미래 제외5449개를 보존한다.
다음 후보는 개발 자료에서 검증하고 소비한 보류를 다시 설계/수용에 쓰지 않는다.


[960 입력·car confidence 후속](test-plan/evidence/m10_resolution_v2/README.md)은 원래 수치
실패/1280 탈락과 car 회귀 거절을 보존했다. 별도 고정한 후보는486개 개발/설계에서 P95.15%/
R91.34%다. [파생 profile](../profiles/perception-resolution-candidates-v1.json)은 offline 전용이고,
원본 RGB640×384를960으로 보간·BASIC FP32/vector를 고정한다. 기존 runtime 실행 명령은 S를
유지한다. 다음 새 개발/보류 수용과 실제 deadline·각 Jetson 배포/측정은 후속이다.


[CARLA 원본 해상도 비교](test-plan/evidence/m10_camera_resolution_v1/README.md)는 모델960과
confidence를 유지하고 source640×384부터3840×2304까지 실제 촬영했다.4K를 품질 평가 전에
기술 기준으로 고정했고, 같은 개발 배치 각81장에서640은P98.37%/R93.80%,4K는129TP/0FP/0FN이다.
수치15건 중14PASS/1FAIL과 종료 실패3쌍·사전 복구를 보존했다. 전체180쌍·미래 제외5629개다.
[4K source profile](../profiles/perception-camera-source-candidates-v1.json)은 다음 새 평가용이며
기존 S/runtime640은 유지한다.4K 순차 health/resize/추론 P95 약93.64ms로 live20Hz는 미수용이다.
이후 native ingress/전처리 검증은 아래 후속 기록으로 이어진다. 새 준비·개발/보류와 전체 wall 수용은 남아 있다.
새 학습·보드 최적화·실제 Jetson 배포는 수행하지 않았다.

## 환경과 모델

4K 후보의 비동기 실행은 [별도 계약](interfaces/perception-async-native-v1.md)과
[재생 근거](test-plan/evidence/m10_async_native_v1/README.md)를 따른다. 상태/조회 owner와
변환·추론을 분리했고 정상/지연/오류/정지를 검사했다. 정상 재생에서 실제 차량 제어가 아닌
상태 producer100Hz·조회 consumer50Hz를 관측했다.4K BGRA 변환/queue까지 포함하면43건 모두
100ms 기한을 초과했으며 인지20Hz·유효 출력 공급은 미완료다. 이전 RGB-only 약94ms와
측정 범위를 구분한다. 먼저 PC 변환·전처리 비용과 실제 ingress/제어 연결을 후속 검증한다.

GPU 없이 저장된 trace·동결 source를 재감사하는 명령은 아래와 같다. 모델 추론·live camera를
재실행하지 않으며, 이미 사용한 개발 media와 미래 제외5629개를 유지한다.

```sh
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_async_native_v1/check-evidence.py \
  docs/test-plan/evidence/m10_async_native_v1 build/m10-async-recheck.json
```

저장소 루트에서 실행한다. 기본 C++ 빌드에는 Python/ONNX/CARLA가 필요 없다.
영상 경로의 재현 환경은 `physical_ai/requirements-host.txt`다. 독립 가상환경을 권장한다.

```sh
python3 -m venv build/perception-venv
build/perception-venv/bin/pip install -r physical_ai/requirements-host.txt
build/perception-venv/bin/python -m physical_ai.perception.artifact build/perception/yolox.onnx
```

Download는 명시적 명령에서만 실행한다. 기존 파일이 있으면 크기·SHA256을 검사하고 다르면
거절한다. 런타임은 고정 FP32 CPU provider를 사용하며 artifact 경로 교체로 다른 가중치를
몰래 읽지 않도록 검증한 byte 자체로 세션을 만든다. [모델 출처·license](../third_party/opencv-zoo-yolox/README.md)를 따른다.

## Component와 수신 경계

```sh
cmake -S . -B build/perception-check -DCMAKE_BUILD_TYPE=Debug \
  -DSTRATADRIVE_PERCEPTION_TESTS=ON \
  -DPython3_EXECUTABLE="$PWD/build/perception-venv/bin/python"
cmake --build build/perception-check --target perception_receiver_test perception_replay --parallel 2
ctest --test-dir build/perception-check -R 'Perception|perception' --output-on-failure
```

명시적인 Python 경로가 필요하다. 다른 Python에 numpy/OpenCV가 없으면 configure에서 거절한다.
이 시험은 모델 다운로드 없이 전후처리·bounded worker·고장·session·tracking·C++ 경계를 검사한다.
`perception_replay`의 text 입력은 시험 도구이며 실제 CAN/SOME-IP wire가 아니다.

## CARLA 데이터 수집

[CARLA Host 경로](carla-guide.md#준비된-host-경로)의 준비된 source build를 사용한다.
전용 새 서버·빈 port2300–2302가 필요하다. 기존 주행 서버에 연결하지 않는다.
정지한 차량/보행자·단일 tick owner로 세 장면의 RGB/instance60쌍을 수집한다.
Actor physics는 꺼져 있으며 `apply_control`이나 기존 NoDrive 제어에 접근하지 않는다.

```sh
python3 tests/integration/perception/run_capture.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --rgb-postprocess enabled --quality Low \
  --output build/perception-capture
build/perception-venv/bin/python tests/integration/perception/prepare_dataset.py \
  build/perception-capture/dataset/capture.json build/perception-dataset
```

SDK Python은 표준 라이브러리와 기존 `carla`만 사용하고 추론 환경은 별도다.
원본 BGRA·metadata·hash는 유지하고 RGB-only `rgb.json`과 `evaluation-only-gt.json`을 분리한다.
초기 postprocess disabled 표본에는 검은 하늘/엔진 warning overlay가 있었다. 후속 enabled Low/Epic
표본에서는 해소되었으며, 두 설정의 평가 결과도 따로 보존한다. 수집 PASS는 pair·timestamp·
단일 tick·정리 검사이지 정상 ClearNoon ODD 이미지 품질 수용이 아니다. 서버의 기존 asset은 수정하지 않는다.

## 실제 추론·정답 평가·부하

아래의 출력 경로는 새 디렉터리/파일이어야 한다. 이전 실패를 덮어쓰지 않는다.

```sh
build/perception-venv/bin/python -m physical_ai.perception.run \
  --dataset build/perception-dataset/rgb.json --model build/perception/yolox.onnx \
  --output build/perception-results \
  --boundary build/perception-check/tests/integration/perception/perception_replay
build/perception-venv/bin/python tests/integration/perception/evaluate.py \
  --dataset build/perception-dataset/rgb.json \
  --truth build/perception-dataset/evaluation-only-gt.json \
  --run build/perception-results --output build/perception-evaluation.json
build/perception-venv/bin/python tests/integration/perception/stream_probe.py \
  --dataset build/perception-dataset/rgb.json --model build/perception/yolox.onnx \
  --output build/perception-stream --fault none
```

`--fault slow`는 실제 모델 앞에150ms 지연, `--fault exception`은 playback frame10부터 backend
예외를 넣는다. 각자 새 output 경로를 사용한다. 20Hz 미디어 재생은 실제 camera acquisition latency
시험이 아니다. 원래 영상 frame/time과 새 playback source를 모두 기록한다.

`result.json`은 expected/attempted/model_valid/admitted/late/errors, pre/inference/post/total wall
Mean/P95/P99/Max·N, throughput·process CPU/RSS·runtime/source hash를 기록한다.
첫 추론을 warmup 명목으로 빼지 않는다. `predictions.jsonl`은 원본 identity·모든 결과와 관측 track을 보존한다.
`boundary-input.txt`/`boundary-output.json`은 같은 결과의 C++ 수락/거절 근거다.

평가의 `raw_model`은 late 결과도 포함한 모델 TP/FP/FN, `admitted_output`은 실제 deadline을 통과한
결과만의 값이다. 둘 다 visible-instance@IoU0.5이며 COCO mAP가 아니다. Empty valid는 무검출이고
안전한 빈 도로라는 뜻이 아니다. Flat/blackout/whiteout만 별도 image-health로 거절한다.
`quality_acceptance=NOT_SET`, `wall_acceptance=NOT_CLAIMED`를 functional PASS와 구분한다.

`check_onnx.py`는 실제 ONNX Runtime/OpenCV raw tensor 동등성을 검사하고,
`check_corruptions.py`는 모델 입력 건전성과 감사 변조를 검사한다. `render_results.py`로
원본 RGB 위에 raw model·평가 전용 GT를 겹친 PNG를 만들 수 있다. 모두 `--help`에서 인자를 확인한다.

## 선택형 Host CUDA

호환 NVIDIA driver가 있는 Host에서 CPU 환경과 별도 가상환경을 만든다. 일반 환경의 ORT를
교체하지 않는다. 모델·dataset·threshold는 그대로 두고 실행 descriptor만 명시적으로 선택한다.

```sh
python3 -m venv build/perception-cuda-venv
build/perception-cuda-venv/bin/pip install -r physical_ai/requirements-cuda-host.txt
build/perception-cuda-venv/bin/python -m physical_ai.perception.run \
  --dataset build/perception-dataset/rgb.json --model build/perception/yolox.onnx \
  --output build/perception-cuda-results --execution cuda \
  --boundary build/perception-check/tests/integration/perception/perception_replay
build/perception-cuda-venv/bin/python tests/integration/perception/check_cuda.py \
  --dataset build/perception-dataset/rgb.json --model build/perception/yolox.onnx \
  --output build/perception-cuda-equivalence.json
```

`stream_probe.py`도 `--execution cuda`를 지원한다. TF32·CPU node fallback을 끄고 옵션을
readback한다. 미설치/cuDNN 로딩 오류는 실패로 기록한다. Cold call 비용을 분모에서 빼지 않으며
이 측정만으로 startup·CARLA와의 동시 GPU 부하·Jetson이나 실시간20Hz를 보장하지 않는다.

## 명시적 준비와 live 카메라 shadow

`--prepare`를 지정하면 synthetic probe3회·준비 전체 시간·모델 생성 비용을 별도로 기록한 뒤
센서 재생을 시작한다. 미지정 경로의 cold-call 분모는 유지한다. `--repeats 10`은 같은60frame을
10회 재생하는 처리량 시험이며 새로운 정확도 표본600개를 의미하지 않는다.

```sh
build/perception-cuda-venv/bin/python tests/integration/perception/stream_probe.py \
  --dataset build/perception-dataset/rgb.json --model build/perception/yolox.onnx \
  --output build/perception-prepared-stream --execution cuda --prepare --repeats 10
```

실제 카메라 경로는 동일 Python에서 준비된 CARLA SDK와 CUDA 런타임을 사용할 수 있어야 한다.
이 환경의 SDK wheel은cp310이므로 Python3.10 가상환경에 로컬 wheel을 `pip install --no-deps`로
설치한다. 원래 SDK 전용 환경은 변경하지 않는다. 아래 runner는 전용 서버를 생성·종료하며
기존 서버를 재사용하지 않는다. Output은 항상 새 경로다.

```sh
python3 tests/integration/perception/run_capture.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --mode live --camera-clock frame5 --rgb-postprocess enabled \
  --probe-python build/perception-cuda-venv/bin/python \
  --model build/perception/yolox.onnx --execution cuda --frames 600 --fault none \
  --boundary build/perception-check/tests/integration/perception/perception_replay \
  --output build/perception-live
python3 tests/integration/perception/audit_live.py \
  build/perception-live/dataset/live.json build/perception-live/audit.json
```

`--fault slow`는 센서 추론에150ms를 더하고, `exception`/`blackout`/`silence`는 후반 절반에
예외/검은 영상/입력 전달 중단을 넣는다. 각각 새 서버·새 output에서 실행한다. 끝에는 source를
멈춘 채500ms 소비를 관측하여 wall expiry를 확인한다. 준비 probe에 센서 fault를 넣지는 않는다.

`live.json`은 startup3회, 모든 camera callback·원본 frame/source, ingress/worker drop,
실제 backend call·소비/track·tick/wall 시각을 기록한다. `samples.tar.gz`는 일부 원본 RGB만
보존한다. 전체 live RGB dataset이나 GT 정확도 평가가 아니다. `audit_live.py`는 원천·분모·
exclusive expiry·고장 후 출력 차단과 서버 종료를 별도로 검사한다. 강제 종료한 서버는 실패다.
원래 frame 기준50ms 취득과 실제 wall20Hz 처리량은 다르며, 보고서의 `actual_camera_hz`와
callback 간격·late/drop을 함께 읽는다. [후속 근거와 실패](test-plan/evidence/m10_live_perception/README.md)를 따른다.

## 확장 정확도 비교와 재감사

[확장 프로토콜](test-plan/perception-quality-protocol.md)은 개발/보류 각81개 배치를 사용한다.
`run_capture.py --mode quality --plan profiles/perception-quality-plan-v1.json --partition development
--quality Epic`은 별도 Epic 정확도 수집이며 위 Low/live20Hz 시험과 다르다. Holdout에는 서버
실행 전에 고정한 `--selection`이 반드시 필요하다. `prepare_quality.py`는 RGB와 평가용
GT/stratum을 분리하고, `quality_benchmark.py freeze/score/select`가 코드·점수·지명을 고정한다.
`run_quality.py`는 RGB-only 입력으로 baseline·차량 class NMS·중앙 확대를 CUDA에서 실행한다.
기존 live runner가 실험 후보를 자동 선택하지 않는다.

이번 v1에는 Rider13 정답 누락이 있다. 따라서 새 수용 평가의 기준으로 그대로 재사용하지 않는다.
원래 실행은 재현·진단용으로 보존하며 수정 v2 정답과 새 partition의 사전 검증이 필요하다.
[결과 묶음](test-plan/evidence/m10_quality/README.md)의 `experiment.tar.gz`는 원래
`build/m10-quality/` 상대 경로를 포함한다. **동일 소스의 깨끗한 작업 사본**에서 LFS 원본과
`SHA256SUMS`를 확인한 뒤 풀고 다음처럼 감사한다. 기존 실행 디렉터리 위에 풀지 않는다.

```sh
tar -xzf docs/test-plan/evidence/m10_quality/experiment.tar.gz
python3 tests/integration/perception/audit_quality_experiment.py \
  build/m10-quality build/m10-quality/re-audit.json
python3 tests/integration/perception/review_quality_annotations.py \
  build/m10-quality build/m10-quality/annotation-v2-recheck
```

첫 명령은 모든 원본 BGRA/instance→RGB/GT/metadata/seal 재구성, 같은 개발셋·보류 선택 hash,
예측 점수·지명 재계산과 partition RGB 중복 검사를 수행한다. 추가 auditor의 PASS와
정확도 gate FAIL을 구분한다. 두 번째 명령은 tags12/13을 합치는 v2의 **사후 진단**이며 새로운
holdout 검증이나 후보 재지명이 아니다. 모든 출력 파일/디렉터리는 새 경로여야 한다.

## Rider v2의 새 평가 경로

[V2 프로토콜](test-plan/perception-quality-v2-protocol.md)은 Rider13을 포함하는 정답,
조건별 coverage와 실제 settling 뒤 actor pose 대조를 사전에 고정한다. 수집은
`run_capture.py --mode quality-v2 --plan profiles/perception-quality-plan-v2.json --quality Epic`으로
분리한다. 초기 European HGV는 현재 M7 NoDrive 구성에서 spawn SIGSEGV를 일으켜 실패를 보존했다.
추론 전에 truck asset만 호환 모델로 바꾸고 다시 freeze한 fixture revision은 `v2b`다.

`quality_benchmark_v2.py freeze/score/select`, `prepare_quality_v2.py`, `run_quality_v2.py`를
함께 사용한다. V1 scorer에 v2 결과를 넣지 않는다. Freeze 이후 소스/plan 변경은 거절되며,
보류 수집은 반드시 해당 개발셋의 `--selection`을 사용한다. 모델 입력은 RGB-only다.
`center-refine-v2`는 class 간 차량 NMS를 제거하고, `vru-refine-v2`는 모든 base box를
보존하며 crop의 person/bicycle/motorcycle만 추가한다. 자동 live 적용은 없다.

[실행 묶음](test-plan/evidence/m10_quality_v2/README.md)의 archive는 실패한 원래
`build/m10-quality-v2/`와 완전 재수집한 `build/m10-quality-v2b/`를 모두 포함한다.
LFS·SHA256SUMS를 확인한 깨끗한 동일 소스 작업 사본에서 다음처럼 재감사한다.

```sh
tar -xzf docs/test-plan/evidence/m10_quality_v2/experiment.tar.gz
python3 tests/integration/perception/audit_quality_v2.py \
  build/m10-quality-v2b build/m10-quality-v2b/re-audit.json
```

모든 raw→RGB/GT/seal·실제 pose·이전 영상 제외·partition 분리·점수/지명을 재구성한다.
실제 GPU 재생의 정확한 인자는 archive의 `run-development.py`와 실행 로그/JSON에 있다.
이미 평가한 v2 holdout은 재현에만 사용하고, 새 후보의 새로운 holdout으로 부르지 않는다.

<a id="m10-v3"></a>

## V3 별도 준비셋과 모델 비교

[V3 기준](test-plan/perception-quality-v3-protocol.md)은 준비셋에서 자산 spawn·settled pose·
최소 visible support와 가림 없는 참조를 먼저 검사한다. `run_capture_v3.py --mode quality-v3`
`--partition preparation --plan profiles/perception-quality-preparation-v3.json --quality Epic`으로
수집하고 `preflight_quality_v3.py capture.json prepared-dir preparation-acceptance.json`을 실행한다.
알려진 NW truck은 서버 시작 전에 거절한다. 가시성 FAIL의 원본은 보존하고 최종 평가 전에만
계획을 수정한다. 실제 개발/보류의 조건별 coverage는 다시 검사한다.

S는 기존 고정 모델을 사용하고 M은 [별도 provenance](../third_party/megvii-yolox/README.md)의
101259744byte/SHA를 검증한다. 가중치는 build 안에만 둔다. 모델 backend는 RGB만 받고,
runner는 준비 보고서와 사전 계획의 적합성도 검사한다. 평가 GT/`benchmark.json`은 scorer가 읽는다.
M 결과의 실제 hash를 offline envelope에 기록하며 기존 S live/C++ 계약에 발행하지 않는다.

준비 PASS 후 `check_quality_models_v3.py prepared-dir/rgb.json model.onnx model-check.json`으로
CPU/CUDA/OpenCV 비교를 실행한다. 준비 영상 hash를 제외 목록에 넣고 `quality_benchmark_v3.py freeze`
명령을 실행한다. 준비 승인·수치 비교 파일은 freeze와 같은 디렉터리에 있어야 한다.
그 뒤 개발 수집→`prepare_quality_v3.py`→정답 검수→`run_quality_v3.py`의 baseline/M/M 확대→
`quality_benchmark_v3.py score/select` 순서다. 보류 수집에는 해당 `--selection`을 전달하고,
baseline과 지명 후보만 실행한다. 모든 출력 경로는 새로 만든다.

[실행 묶음](test-plan/evidence/m10_quality_v3/README.md)을 깨끗한 동일 소스 작업 사본에 풀어 재감사한다.
기존 실행 디렉터리 위에 풀지 않는다. Archive에는 가중치가 없고 raw·prediction과 원래 실패도 있다.

```sh
tar -xzf docs/test-plan/evidence/m10_quality_v3/experiment.tar.gz
python3 tests/integration/perception/audit_quality_v3.py \
  build/m10-quality-v3c build/m10-quality-v3c/re-audit.json
```

정확한 실제 명령은 archive의 `run-development.py`, 각 `server.json`과 실행 로그를 따른다.
재감사는 raw→RGB/GT/seal·준비 실패/수정·분리·model SHA·점수/지명을 검증하며 GPU는 필요 없다.
새 GPU 재생은 별도 가중치와 고정 CUDA 환경을 준비한다. 소비한 보류셋으로 새 후보를 고르지 않는다.

<a id="road-preparation-v4"></a>

## 실제 site의 도로 맞춤 준비

[V4 기준](test-plan/perception-road-preparation-v4-protocol.md)은 모델 점수 없이 도로 경로·카메라
시야·실제 차로와 actor/rider 가시성을 먼저 검사한다. `run_quality_server_v4.py --stage survey`는
별도 서버에서 전체 map route를 조회한다. 저장된 survey의 엄격한 선택은 `select_road_sites_v4.py`,
명시 pose 계획 생성은 `quality_plan_v4.py`다. 현재 계획은14/24번의 실제 두 site를 사용한다.

`run_quality_server_v4.py --stage preparation --plan profiles/perception-road-preparation-v4.json`
`--partition development` 또는 `holdout`으로 각99개를 수집한다. 기존 guide와 같은 engine/source/
SDK Python·output·port 인자가 필요하다. 새 출력 경로를 사용하고 server exit130과 cleanup을 확인한다.
`prepare_quality_road_v4.py capture.json copied-plan.json profiles/perception-road-exclusion-v4.json output-dir`
은 raw에서 RGB·GT를 만들고 모델 없이 준비 기준을 판정한다. `review_quality_road_v4.py`는 고정24장
패널과 전체 RGB 건전성 검사를 만든다. `development/holdout` 이름은 **미래 평가 위치의 준비**다.

[실행 묶음](test-plan/evidence/m10_road_preparation_v4/README.md)에는 초기 실패부터 최종 v4c까지
모두 있다. 동일 소스의 깨끗한 작업 사본에서 LFS/SHA256SUMS를 확인하고 새 경로에 푼다.

```sh
tar -xzf docs/test-plan/evidence/m10_road_preparation_v4/experiment.tar.gz
python3 tests/integration/perception/audit_quality_road_v4.py \
  build/m10-road-preparation-v4c build/m10-road-preparation-v4c/re-audit.json
```

Auditor는 map 선택/계획·실제 pose/차로·raw RGB/GT·가림 참조·모든 준비 실패를 재검사한다.
`prepared-plan-seal.json`은 미래 계획·준비 보고서·제외 목록의 연결이며 모델 수용이나 권한이 아니다.
다음 정확도 평가는 `future-evaluation-exclusion.json`의1387개를 제외하고 별도 quality freeze를
만든 뒤 새 RGB를 수집해야 한다. 작은 held walker의 far26m 한정을 유지하며 실제 평가의
coverage도 다시 확인한다. 이번 준비에는 모델 추론/점수/후보 교체가 없다.

<a id="quality-v4"></a>

## 도로 맞춤 새 정확도 평가

[V4 품질 기준](test-plan/perception-quality-v4-protocol.md)은 위 준비 봉인을 읽고 실제 평가의
새81+81쌍과 별도 quality freeze를 사용한다. 후보 구현은 기존 S/M/M 확대 그대로이며
V4는 도로 배치와 평가 경로의 버전이다. 원래1387개와 거절/진단/metadata 실패324개를 합친1711개 RGB를 고정한
`profiles/perception-quality-exclusion-v4.json`으로 평가에서 제외한다.

준비의 개발99장으로 `check_quality_models_v3.py`를 실행해 `model-check.json`을 새 평가
디렉터리에 둔다. `quality_benchmark_v4.py freeze experiment-freeze.json`은 준비 PASS,
봉인된 plan·모든 과거 RGB 제외·수치 비교·사전 기준을 대조한 뒤 소스 hash를 고정한다.
`run_quality_evaluation_v4.py`는 기존 engine/source/SDK Python/output/plan/partition 인자에
`--freeze`가 필요하다. 개발은 지명 없이 수집하고, 보류는 `--selection`을 서버 시작 전에 요구한다.
보류 지명은 원래 개발 예측에서 점수·순위를 다시 계산해 검사한다.

`prepare_quality_v4.py capture.json prepared-dir experiment-freeze.json`은 실제 도로/pose와
raw RGB/GT를 재구성하고 모든 계획 actor/rider의 포함을 `visibility.json`에 기록한다.
`review_quality_v4.py prepared-dir output-dir partition`은 정답 패널과 전체 RGB 건전성을 만든다.
`run_quality_v4.py`의 인자는 v3와 같으며 RGB-only runner와 별도 scorer를 사용한다.
개발 세 후보를 `quality_benchmark_v4.py score/select`로 지명한 뒤 보류에는 baseline과
지명 후보만 실행한다. 실제 명령·실패는 [실행 묶음](test-plan/evidence/m10_quality_v4/README.md)에 있다.

```sh
tar -xzf docs/test-plan/evidence/m10_quality_v4/experiment.tar.gz
python3 tests/integration/perception/audit_quality_v4.py \
  build/m10-quality-v4g build/m10-quality-v4g/re-audit.json
```

동일 최종 소스와 baseline의 불변 준비 근거가 있는 깨끗한 작업 사본에서 LFS/SHA256SUMS를
확인한 뒤 새 경로에 푼다. 재감사는 GPU 없이 raw→RGB/GT/road/coverage/seal·점수·지명·
실행 순서·중복을 재구성한다. 감사 PASS와 모델 품질·live20Hz·차량 수용은 구분한다.

V4 metadata 연결 누락은 원래 S 예측·실패를 보존하고 raw→준비→점수 회귀를 추가해 새 freeze로
재수집했다. 최종162개는 가시성/coverage PASS·모델 품질 FAIL이다. 다음 평가에는 결과 묶음의
`future-evaluation-exclusion.json`1873개를 사용하며 소비한 V4 보류로 새 후보를 재지명하지 않는다.

<a id="quality-v5"></a>

## VRU 다중 시야 후보와 새 도로 평가

[V5 기준](test-plan/perception-quality-v5-protocol.md)은 기존 모델/숫자 gate를 유지하면서
M 원본/중앙 VRU 확대와 양방향 약한 클래스 지지·body 충돌 억제 후보를 비교한다.
`quality_road_v5.py`는 기존 전체 지도 query에서 과거 road/site/50m를 제외해31/35번을 선택한다.
`run_road_server_v5.py`·`prepare_road_v5.py`로 두 실제 site의 별도99장씩을 먼저 검사한다.
임시 spawn은 `quality_staging_v5.py`의 요청 pose를 기록하고 world tick 전에 최종 pose로 옮긴다.
원래 staging 충돌과 startup 실패를 그대로 남긴다.

최종 준비 뒤 `check_quality_models_v3.py`로 독립 tensor/raw를 대조하고
`check_quality_v5_views.py`로 준비3장의 두 완성 정책 CPU/CUDA를 대조한다.
`quality_benchmark_v5.py freeze`는 preparation source/원본 PASS·수치 검사·평가 제외2195개를
대조하고127개 source/config를 고정한다. `run_quality_evaluation_v5.py`는 `--freeze`와
개발/보류 partition을 요구하고, 보류에는 개발 점수에서 재계산한 `--selection`이 필요하다.
`prepare_quality_v5.py`·`review_quality_v5.py`로 실제 pose/actor/rider/GT와 RGB를 검사하고,
`run_quality_v5.py`의 RGB-only 결과를 `quality_benchmark_v5.py score/select`로 평가한다.
개발 세 후보·보류 S/지명 후보만 실행하며 live/C++ 발행은 없다.

[실행 묶음](test-plan/evidence/m10_quality_v5/README.md)의 LFS/SHA256SUMS를 확인한 깨끗한
동일 소스 작업 사본에서 새 경로에 압축을 푼다. baseline의 이전 불변 evidence도 필요하다.

```sh
tar -xzf docs/test-plan/evidence/m10_quality_v5/experiment.tar.gz
python3 tests/integration/perception/audit_quality_v5.py \
  build/m10-quality-v5b build/m10-quality-v5b/re-audit.json
```

감사는 GPU 없이 최종 준비198장·평가162장의 raw→RGB/GT/road/coverage/seal·strict 점수·
지명·실행 순서·중복을 재구성한다. `build/m10-quality-v5b/audit-history.py`는 원래 설계 점수와
최초 준비/부분25장·실패·322개 준비 제외를 검증하는 보존 script다. 이미 결과 파일이 있으므로
별도 출력 경로 또는 기록 함수 교체로 재검사한다. 압축 해제 재검사 절차는 묶음의
`archive-recheck.json`과 `check-archive.py`에 기록한다.

새 개발 절대·상대 PASS와 새 보류 FAIL을 보존하며 S를 유지했다. 같은 Town/이미 본 자산의
정지 fixture이고 작은 held walker far26m 범위다. 다음 평가는 `future-evaluation-exclusion.json`
2357개를 제외하고 새 후보/새 보류를 봉인한다. 전체wall20Hz·시작/종료 안정성·차량 수용은 별도다.

<a id="quality-v6"></a>

## 고정 L 모델·확대 시야 차종 판단과 새 평가

[V6 기준](test-plan/perception-quality-v6-protocol.md)은 공식 L 가중치를 별도 offline model SHA로
고정한다. [모델 출처/라이선스](../third_party/megvii-yolox-large/README.md)의 ONNX를 내려받아
216746733byte와 SHA256을 대조한다. 기존 RGB0–255/letterbox114·FP32·score.35를 유지한다.
`large-v6`는 원본 L, `large-context-v6`는 전체 class 중앙 확대의 원본 약한 지지와 시야 간
body 판단을 사용한다. 기본 S/C++ 계약에는 자동 적용하지 않는다.

`quality_road_v6.py`의74/80번 site에서 `run_road_server_v6.py`·`prepare_road_v6.py`로
99장씩 먼저 검사한다. 준비198장 PASS 뒤 `check_quality_models_v6.py`·
`check_quality_v6_views.py`로 준비3장의 독립 raw와 두 완성 정책 수치를 대조한다.
`quality_benchmark_v6.py freeze`는 준비 source·실제 원본·과거/준비2555개 RGB 제외와 모든
기준을 대조해152개 source/config를 봉인한다. `run_quality_evaluation_v6.py`에는 `--freeze`,
보류에는 서버 시작 전에 개발 점수로 재계산한 `--selection`이 필요하다.
`prepare_quality_v6.py`·`review_quality_v6.py`로 실제 coverage와 RGB를 다시 검사하고
RGB-only `run_quality_v6.py` 결과를 `quality_benchmark_v6.py score/select`로 평가한다.
지명 순서는 relative PASS→F1→recall→precision→ID이며 보류에는 S와 지명 후보만 실행한다.

[실행 묶음](test-plan/evidence/m10_quality_v6/README.md)의 LFS/SHA256SUMS를 확인한 깨끗한
동일 소스 작업 사본에서 새 경로에 압축을 푼다. 이전 불변 evidence도 필요하다.

```sh
tar -xzf docs/test-plan/evidence/m10_quality_v6/experiment.tar.gz
python3 tests/integration/perception/audit_quality_v6.py \
  build/m10-quality-v6 build/m10-quality-v6/re-audit.json
```

감사는 GPU 없이 준비198개·평가162개의 raw→RGB/GT/road/coverage/seal·strict 점수·지명·
순서·중복을 재구성한다. 묶음의 `check-archive.py`는 새 임시 경로 압축 해제와 소비된 개발162장의
`design-history.py` 재생까지 검사해 새 `archive-recheck.json`을 기록한다. 기존 보고서를 유지하며 다음처럼 새 출력 경로를 지정한다. Model weights는 archive에 없으며 재감사에는 필요하지 않다.

```sh
python3 docs/test-plan/evidence/m10_quality_v6/check-archive.py \
  docs/test-plan/evidence/m10_quality_v6 build/m10-v6-recheck-new.json
```

다음 후보의 새 평가에서는 `future-evaluation-exclusion.json`2717개를 제외한다. 이미 본 보류를
새 holdout으로 재사용하지 않고 같은 Town/자산의 정지 fixture·held walker far26m 범위를 유지한다.

<a id="domain-data-v1"></a>

## 전용 개발·학습 데이터

[사전 수집 기준](test-plan/perception-domain-data-v1-protocol.md)과 [실행 근거](test-plan/evidence/m10_domain_data_v1/README.md)는
RGB/instance640×384·모델 없는 자산/가시성 준비와 시야/기상/거리·train/validation 분리를 고정한다.
`domain_plan_v1.py`·`domain_extension_v1.py`가 명시 pose를 만들고 `run_domain_server_v1.py`가
같은180/900/30s budget으로 전용 서버를 실행한다. 원래 source와 실패도 snapshots에 보존한다.
`prepare_domain_v1.py`·versioned extension extractor는 raw/pose/semantic/Rider를 재구성한다.

`physical_ai.perception.domain_data_v1`은 작은 fragment도 양성으로 보존하고 기존 최소 품질
지원 여부를 별도로 표시한다. PNG 원래 RGB와 mask area/box·COCO6category/native class를
검사한다. 일반화한80-class trainer/head/ONNX 출력과 자동 연결하지 않는다. Archive의
`export/images/`·`export/annotations/`·`export/dataset.json`이 학습 입력 자료다.

LFS/SHA256SUMS를 확인한 동일 소스의 깨끗한 작업 사본에서 새 경로에 푼다.

```sh
tar -xzf docs/test-plan/evidence/m10_domain_data_v1/experiment.tar.gz
python3 tests/integration/perception/audit_domain_v1.py \
  build/m10-domain-data-v1 build/m10-domain-data-v1/re-audit.json
```

감사는 GPU/모델 없이 모든 raw·mask·pose·PNG/COCO·분리·지원 행렬과 원래 실패를 재구성한다.
공식 COCO API의 pinned QA wheel과 배포 SHA·실행 script도 archive에 보존했다. 새 임시 경로
재감사는 아래처럼 기존 보고서를 유지하며 새 출력 경로를 지정한다.

```sh
python3 docs/test-plan/evidence/m10_domain_data_v1/check-archive.py \
  docs/test-plan/evidence/m10_domain_data_v1 build/m10-domain-recheck-new.json
```

`DomainDataset(Path('build/m10-domain-data-v1/export'), 'train')`과 `'validation'`이 annotation·
PNG/RGB·split을 검증하며 `samples()`가 RGB/metadata/native labels를 반환한다. 모든 nonempty
visible 양성을 유지하고 quality_eligible=false를 crowd/배경으로 바꾸지 않는다. 원래 실패·작은
지원 부족과 bus/truck 자산 공유·정지 clearance fixture의 범위를 결과와 함께 읽는다.
Train/validation은 미래 quality holdout이 아니며127번은 미수집이다. 새 모델에는 별도 학습·
수치 동등성·새 개발/보류 평가가 필요하다. 모델·기본 S runtime의 자동 교체는 없다.

<a id="training-v1"></a>

## 고정 개발 자료의 첫 L6 학습 후보

[학습 기준](test-plan/perception-training-v1-protocol.md)과 [실제 학습/내보내기 근거](test-plan/evidence/m10_training_v1/README.md)는
train813/validation267과 공식 L checkpoint·native6개 행 이식·24epoch FP32 설정을 고정한다.
새 head11채널/manifest는 기존80-class runtime과 별도다. 기본 S를 자동 교체하지 않는다.

독립 Python3.10 venv에 공식cu124 index의 torch2.5.1/torchvision0.20.1과
`physical_ai/requirements-training-v1.txt`의 나머지 package를 설치한다. 원래 RGB가 있는 data
archive를 풀고 LICENSE·공식 초기 가중치434357141byte/SHA256을 확인한다. 전체 환경은
evidence archive의 `environment.txt`를 따른다. 새 output directory에서 재실행한다.

```sh
PYTHONNOUSERSITE=1 build/m10-training-v1/venv/bin/python \
  tests/integration/perception/train_domain_v1.py \
  --data build/m10-domain-data-v1/export \
  --pretrained build/m10-training-v1/upstream/yolox_l.pth \
  --output build/m10-training-reproduction/run-01
```

`export_training_v1.py`는 completed run과 best checkpoint/freeze·data hash를 검사해 새 ONNX,
manifest와16개 numeric probes를 만든다. `check_training_v1.py`는 CPU/CUDA 별도 실행과
OpenCV CPU probe·267개 validation을 검사한다. CPU/CUDA에서 서로 다른 pinned venv를 써
훈련 torch CUDA libs와 기존 ORT CUDA libs의 중복 로딩을 피했다. 수치 기준과 실패는 유지한다.

같은 source checkout과 두 LFS evidence의 SHA를 확인한 뒤, 새 경로 추출 재감사는 다음과 같다.

```sh
PYTHONNOUSERSITE=1 build/m10-training-v1/venv/bin/python \
  docs/test-plan/evidence/m10_training_v1/check-archive.py \
  docs/test-plan/evidence/m10_training_v1 build/m10-training-recheck-new.json
```

이는 모든 epoch prediction/score/선택과 best/last 실제 tensor·BN buffers를 재감사한다.
새 경로에 source와 모델·data export를 풀며24epoch 역전파 자체를 재실행한 것은 아니다.
개발 validation 수용과 새 quality holdout·전체wall20Hz·차량 수용을 구분한다.

<a id="quality-v7"></a>

## 고정 학습 L6의 새 도로 품질 평가

[V7 사전 기준](test-plan/perception-quality-v7-protocol.md), [별도 시작 복구 편차](test-plan/perception-quality-v7-recovery.md)와
[실제 새 개발/보류 결과](test-plan/evidence/m10_quality_v7/README.md)는 epoch17 모델을 그대로
고정한다. `quality_candidates_v7.py`는 native6개의11채널을 기존85채널과 구분하고 raw full view를
사용한다. 기존 score/NMS·strict IoU/모든 absolute/relative gate·기본 S를 유지한다.

`quality_road_v7.py`는 원래 map-only query로 미사용215/127번을 재현한다. Versioned 서버와
extractor는 준비99장/site·실제81장/site·동일 budget·모든 실제 actor/Rider mask와 pose를
검사한다. 모든 준비/거절 RGB를 final exclusion에 넣고 source/model/numeric을 봉인한다.
개발 score와 단일 후보 지명을 봉인한 다음에만 보류를 수집하며 실패를 판정에서 지우지 않는다.

L6 ONNX bytes는 이전 `m10_training_v1/experiment.tar.gz`의 `build/m10-training-v1/export/`에 있다.
새 artifact는 모델 가중치를 중복 저장하지 않고 이전 모델 manifest와 exact hash를 연결한다.
최종 지명·strict score·raw/visibility·clock·source 순서와 새 경로 감사는 GPU/모델 없이 재현한다.
같은 source checkout과 모든 기존 evidence의 LFS/SHA를 확인한 후 새 출력 파일을 지정한다.

```sh
python3 docs/test-plan/evidence/m10_quality_v7/check-archive.py \
  docs/test-plan/evidence/m10_quality_v7 build/m10-v7-recheck-new.json
```

이 재감사는 모델 재추론이나 전체wall20Hz/시작 안정성·차량 수용을 재실행한 것이 아니다.
서버 시작 실패2회와 동일 조건의 별도 복구 실행도 archive와 사전 복구 record에 남겼다.
소비한 개발 자료로 회귀를 개선할 수 있으나 기존 보류를 다시 수용 표본으로 사용할 수 없다.

2026-11-11 후속 [전처리 개선·실제4K ingress](test-plan/evidence/m10_native_preprocess_v1/README.md)는
개발84장의 RGB/tensor를 그대로 유지하며 전처리 P95를103.36→42.02ms로 줄였다.
비동기 재생은46회 발행/21개 frame 소비로 개선됐지만, 실제 CARLA/Epic과 GPU를 공유하면
37개 완료가 모두 late여서 fresh-output gate FAIL이다. 실제 camera13.60Hz·관측 consumer50Hz,
world67.72Hz이며 원본60개를 포함한 미래 제외는5689개다. 다음은 실제 부하에서100ms 내
공급을 확보한 뒤 실제 상태/보호·제어 연결과 새 독립 품질 평가를 진행하는 것이다.
기존 모델/기한/runtime·M10 OPEN·Jetson 최적화 후속 원칙을 유지한다.
