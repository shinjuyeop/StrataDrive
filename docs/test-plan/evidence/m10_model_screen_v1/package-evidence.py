from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import tarfile
import subprocess

root = Path('build/m10-model-screen-v1')
evidence = Path('docs/test-plan/evidence/m10_model_screen_v1')
evidence.mkdir(parents=True, exist_ok=True)
load = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
frozen = load(root / 'freeze.json')
models = load(Path('profiles/perception-model-screen-v1.json'))['models']
summaries = []
for name in frozen['candidates']:
    score = load(root / f'{name}-score.json')
    run = load(root / f'{name}-run.json')
    summaries.append(dict(candidate=name, micro=score['micro'], per_class=score['per_class'],
                          near_person=score['near_person'], riders=score['riders'], gates=score['gates'],
                          absolute_development_gates=score['absolute_development_gates'],
                          latency=run['latency'], after_first_latency=run['after_first_latency'],
                          initialization_ms=run['model_initialization_wall_ns'] / 1e6,
                          admitted=run['admitted'], model_valid=run['model_valid'], errors=run['errors'],
                          peak_process_rss_kib=run['peak_process_rss_kib'], model=models[name]))
base, large = summaries[0], summaries[2]
summary = dict(schema='m10-pretrained-screen-summary-v1', created_utc=datetime.now(timezone.utc).isoformat(),
               scope='consumed DEVELOPMENT only; initial fixed-confidence screen; not independent acceptance',
               frames=324, gt_objects=516, candidate_frames=1620, source_freeze_files=len(frozen['sources']),
               cold_calls_excluded=0, candidates=summaries, best_development_f1='yolox-l',
               large_precision_gain=large['micro']['precision'] - base['micro']['precision'],
               existing_precision_gain_min=0.03,
               existing_precision_gain_pass=large['micro']['precision'] - base['micro']['precision'] >= 0.03,
               previous_large_v6_holdout_failure_retained=True, default_model='YOLOX-S',
               optimal_model_finalized=False, new_training=False, new_capture=False,
               holdout_access=False, fresh_acceptance=False, runtime_promotion=False,
               jetson_execution=False, board_optimization='DEFERRED by user',
               future_rgb_exclusion_count_unchanged=4333,
               checks=dict(python_tests=168, ctest_debug=13, ctest_release=13, ctest_asan_ubsan=13,
                           numeric_candidate_probes=15, raw_rgb_rehash_and_score_replay='PASS',
                           independent_upstream_references='PASS', rtdetr_byte_identical_reexport='PASS'))
(root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')

artifact_files = [p for p in root.iterdir() if p.is_file() and p.suffix in ('.json', '.log', '.txt', '.png', '.py')]
for p in artifact_files:
    shutil.copy2(p, evidence / p.name)
shutil.copytree(root / 'reference-01', evidence / 'reference-01', dirs_exist_ok=True)

doc = '''# M10 사전학습5종 개발 비교 V1

2026-11-10. 사용자 지시에 따라 **Jetson 배포 가능성을 고려하고 보드별 최적화는 후속**으로
둔 상태에서5개 사전학습 모델을 같은 개발 영상324장에 실행했다. 추가 학습·새 수집·보류
접근·runtime 교체는 없다. [현재 선정 순서](../../../perception-model-selection.md)와
[사전 기준](../../perception-model-screen-v1-protocol.md)을 따른다.

## 같은 입력의 결과

V4/V5/V6/V7의 development 각81장,516개 visible GT다. 이미 소비한 개발 자료이므로
새 일반화/수용 평가가 아니다. RGB640×384·6class·FP32/batch1·confidence.35와 기존 strict
visible IoU.5 matching을 유지했다. 각 모델의 공식 전처리/입력 크기/후처리를 보존했다.
YOLOX640, RT-DETR640 direct resize, NanoDet416 centered letterbox다. COCO mAP가 아니다.

| Model | TP/FP/FN | P | R | F1 | 개발 절대 gate | P95 ms | Cold 포함 Max ms |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
'''
for row in summaries:
    m = row['micro']
    doc += f"| {row['candidate']} | {m['tp']}/{m['fp']}/{m['fn']} | {m['precision']:.2%} | {m['recall']:.2%} | {m['f1']:.2%} | {row['absolute_development_gates']} | {row['latency']['p95_ms']:.3f} | {row['latency']['max_ms']:.3f} |\n"
doc += '''
L은 이 고정 조건에서 가장 높은 F1과 전체 절대 개발 gate PASS를 보였다. S 대비 P 향상은
**2.85%p**로 기존 상대 기준3%p에는 미달한다. [V6 L의 보류 FAIL](../m10_quality_v6/README.md)을
이 결과로 지우지 않는다. 기본 S 유지는 교체 검증 미완료라는 뜻이며 최적 모델 확정이 아니다.
RT-DETR은 R93.02%와 FP328개를 함께 기록했고, NanoDet은 낮은 Host 지연과 R40.70%를
함께 기록했다. 공통 score.35는 계열별 최적 calibration 탐색이 아니므로 보편적인 모델 순위를
주장하지 않는다. Jetson에서의 지연·메모리·전력 순위도 미측정이다.

| Class recall | S | M | L | RT-DETRv2-R18 | NanoDet416 |
| --- | ---: | ---: | ---: | ---: | ---: |
'''
classes = {'0': 'person', '1': 'bicycle', '2': 'car', '3': 'motorcycle', '5': 'bus', '7': 'truck'}
for cls, name in classes.items():
    doc += '| ' + name + ' | ' + ' | '.join(f"{row['per_class'][cls]['recall']:.2%}" for row in summaries) + ' |\n'
doc += '''
Rider GT108개 중 S/M/L/RT-DETR/NanoDet은 각각62/71/82/90/34개를 검출했다. Near person은
각12/12/12/12/11 TP(분모12)다. 각 도로와 stratum·전체 오류/지연은 원래 score/run JSON에 있다.

## 수치·실행·배포 고려

공식 ONNX 또는 공식 COCO checkpoint를 사용했고 모델 byte/hash·출처·Apache-2.0 license와
tensor contract는 [registry](../../../../profiles/perception-model-screen-v1.json)에 고정했다.
RT-DETR checkpoint는 해시 확인 후 weights_only=True로 읽고 전체 state를 strict load했다.
공식 inference 모듈과 postprocessor를 고정 batch1/opset16으로 내보냈다. 재export한 모델은
**byte 동일**하다. RT-DETR export/참조 환경과 ORT CUDA 환경은 분리했다.

V7 개발 준비의 첫3장만 사용해5model×3probe CPU/CUDA raw·완성 검출15건을 통과했다.
NanoDet은 공식 OpenCV decoder/demo, RT-DETR은 공식 PyTorch/postprocessor 결과와도
대조했다. 첫 수치 검사는 RT-DETR 낮은 top300 후보의 순서를 정수 label까지 동일하게
요구하여 FAIL이었다. 원본 덤프에서 score.05455 후보2개의193/194 위치 교환만 확인했다.
모든300개를 class·box≤.1pixel·score≤1e-4로 한 번씩 대응시키는 set 검사를 추가해
다시 통과했다. 원래 FAIL과 덤프를 보존했으며 threshold/모델/GT는 바꾸지 않았다.

모든5개 후보는324/324 model-valid·error0이고 cold 첫 frame만100ms admission을 넘었다.
모델 생성/첫 추론 비용을 숨기지 않았다. Host ORT CUDA/TF32 off·자동 CPU node fallback
금지·동일 순차 실행이며 stage timing·provider readback·최대 process RSS를 기록했다.
RSS는 CUDA 메모리 전체나 보드 RAM budget 측정이 아니다. Offline timing은 live20Hz 수용이 아니다.

ONNX checker와 graph/domain 검사는 모두 PASS·custom domain0이다. RT-DETR은 GridSample9개,
NanoDet은 overridable initializer158개를 보존한다. 이는 후속 TensorRT 변환 때 확인할 정보이며
Jetson/특정 TensorRT 버전의 지원이나 성공을 보증하지 않는다. 현재 engine 생성·FP16/INT8·
클록/전력 조정·보드별 최적화·실제 Jetson 실행은 하지 않았다.

## 원본 검토·감사·재현

코드/config **192개**와324개 RGB·GT/metadata/seal hash를 추론 전에 고정했다. 실행은 RGB만
모델에 입력하고, 정답은 별도 scorer만 읽는다. 모든324장 raw RGB hash·sealed GT와 strict
점수 재계산을 통과했다. 이번 감사는 기존 정답 mask를 다시 만드는 작업이 아니라, 이전
감사로 봉인된 GT를 그대로 사용한 비교 재현이다. 원래 instance 원본은 이전 evidence에 있다.
새 영상이 없어 다음 RGB 제외 목록4333개는 변하지 않았다.

4개 도로의 near person/far person/far truck/occluded bus 중 첫 ClearNoon 사례16장과
5model 출력을 같은 좌표에 겹쳐80cell을 직접 확인했다. 일부 배경 person FP·far miss를
진단했으며 이 검토로 점수나 후보를 조정하지 않았다. 정지한 같은 Town fixture이며 동적
주행·새 도시/자산 일반화를 수용하지 않는다.

![V4 개발 같은 장면5모델](v4-comparison.png)
![V5 개발 같은 장면5모델](v5-comparison.png)
![V6 개발 같은 장면5모델](v6-comparison.png)
![V7 개발 같은 장면5모델](v7-comparison.png)

Python **168개**, Debug/Release/ASan+UBSan perception **각13개**, Ruff·문서 링크·whitespace가
PASS다. C++ 변경은 없고 Python 자체는 sanitizer로 계측하지 않았다. 전체 core/M7·실제20Hz·
차량/Target 검증은 재실행하지 않았다. 압축 묶음을 새 경로에 풀어 모델/GPU 없이 모든
RGB·source·strict score를 재검사했다.

- `summary.json`, `*-run.json`, `*-score.json`: 실제324장×5개 예측·원래 분모·점수·지연.
- `freeze.json`, `numeric-01.json`, `numeric-02.json`, `reference-01/`: 사전 고정과 최초 FAIL·수정 검사.
- `deployment-review.json`, `reexport.json`, 환경 txt: graph/호환 고려·export 재현·실제 환경.
- `audit.json`, `archive-recheck.json`, `SHA256SUMS`: RGB/source/score 재현과 압축 무결성.
- `experiment.tar.gz`: frozen source192개·개발 RGB/GT/seal324개·새2종 모델/RT checkpoint·참조/실패/로그.
  기존 S/M/L 모델 byte는 재복제하지 않았다. 공식 URL과 hash는 provenance에 기록했다.

```sh
build/m10-perception/cuda-venv/bin/python \\
  docs/test-plan/evidence/m10_model_screen_v1/check-archive.py \\
  docs/test-plan/evidence/m10_model_screen_v1 build/m10-screen-recheck-new.json
```

다음은 사전학습 후보/공통 Reference 조건을 정리하고 새로운 독립 평가를 계획하는 단계다.
추가 학습은 필수가 아니며 보드 최적화는 동일 Reference의 실제 보드 비교 뒤에 진행한다.
'''
(evidence / 'README.md').write_text(doc)

extras = [Path(p) for p in ['docs/perception-model-selection.md', 'docs/project-status.md', 'docs/roadmap.md',
          'docs/perception-guide.md', 'profiles/README.md', 'profiles/perception-startup-host-v1.json',
          'profiles/perception-carla-rgb-host-v1.json']]
sources = {**frozen['sources'], **{str(p): sha(p) for p in extras}}
(evidence / 'sources.json').write_text(json.dumps(dict(base_commit='2beea441d602a9229a8149f1dcd69bc37033ffcf',
    frozen_source_count=len(frozen['sources']), final_related_source_count=len(sources), files=sources), indent=2) + '\n')
with tarfile.open(evidence / 'experiment.tar.gz', 'w:gz', compresslevel=6) as tar:
    for relative in sorted(sources):
        tar.add(relative, arcname='project/' + relative, recursive=False)
    for spec in frozen['datasets'].values():
        data = Path(spec['path'])
        for name in spec['files']:
            tar.add(data / name, arcname='project/' + str(data / name), recursive=False)
        for row in load(data / 'rgb.json')['frames']:
            image = data / row['rgb_path']
            tar.add(image, arcname='project/' + str(image), recursive=False)
    for p in root.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or 'deps' in p.parts:
            continue
        if 'rtdetr-source' in p.parts or p.name == 'rtdetr-reexport.onnx':
            continue
        tar.add(p, arcname='project/' + str(p), recursive=False)
print('Packaged', (evidence / 'experiment.tar.gz').stat().st_size, 'bytes', len(sources), 'related source files')
