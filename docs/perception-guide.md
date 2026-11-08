# 영상 인지 실행과 평가

M10 Host 프로파일의 입력은 RGB이고 출력은 원본 영상 pixel 좌표의 객체·관측 이력이다.
거리/trajectory/차량 command는 만들지 않는다. [계약](interfaces/perception.md)과
[실행 근거](test-plan/evidence/m10_perception/README.md)의 정확도·timing 한계를 먼저 확인한다.

## 환경과 모델

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
