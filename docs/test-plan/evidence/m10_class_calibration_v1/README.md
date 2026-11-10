# M10 pretrained class confidence calibration V1

2026-11-10. **새 품질 평가의 개발 후보는 D-FINE-M class-v1로 고정**했다.
최종 Reference와 runtime 모델을 채택한 것은 아니다. 기본 S와 기존 실패를 유지한다.
[사전 기준](../../perception-class-calibration-v1-protocol.md),
[고정 grid](../../../../profiles/perception-class-calibration-grid-v1.json),
[오류 분석](../m10_model_diagnostics_v1/README.md)을 따른다.

## 고정 설정과 결과

공식 사전학습 가중치·native640 RGB·FP32/batch1·80-class top300/noNMS를 유지했다.
기존 confidence0.35 하한을 유지하고 class별0.35/0.40/0.50/0.60/0.70만 탐색했다.
원래 scalar V2 결과와 bytes는 그대로다.

| 모델 | person0 | bicycle1 | car2 | motorcycle3 | bus5 | truck7 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| D-FINE-M class-v1 | .60 | .40 | .70 | .50 | .50 | .60 |
| RT-DETRv4-S class-v1 | .40 | .40 | .60 | .50 | .60 | .60 |

| 고정 vector / 영역 | TP / FP / FN | 정밀도 | 재현율 | 절대 기준 | 상대 기준 |
| --- | ---: | ---: | ---: | --- | --- |
| D-FINE / calibration324 | 460 / 40 / 56 | 92.00% | 89.15% | PASS | FAIL |
| D-FINE / 소비한 Town04 개발81 | 115 / 13 / 14 | 89.84% | 89.15% | PASS | FAIL |
| RT-DETRv4 / calibration324 | 457 / 76 / 59 | 85.74% | 88.57% | PASS | FAIL |
| RT-DETRv4 / 소비한 Town04 개발81 | 114 / 18 / 15 | 86.36% | 88.37% | FAIL | FAIL |

D-FINE의 원래 scalar0.50 calibration은 TP465/FP129/FN51·P78.28%/R90.12%다.
class별 설정은 FP를89건(약69%) 줄이며 TP5건이 감소했다. Town04의 원래0.50은
TP119/FP16/FN10이다. 새 설정의 precision/recall tradeoff를 함께 보고하며 개선만 추리지 않는다.

| class recall | D-FINE cal / Town04 개발 | RT-DETRv4 cal / Town04 개발 |
| --- | ---: | ---: |
| person | 72.02 / 76.19% | 76.19 / 80.95% |
| bicycle | 96.67 / 80.00% | 81.67 / 60.00% |
| car | 99.24 / 96.97% | 98.48 / 100.00% |
| motorcycle | 97.92 / 100.00% | 91.67 / 100.00% |
| bus | 95.00 / 100.00% | 100.00 / 100.00% |
| truck | 95.83 / 100.00% | 95.83 / 91.67% |

**상대 기준 FAIL은 유지한다.** D-FINE calibration의 bus recall95%는 S100%보다 낮다.
Town04에서 S의 공통0.35 P86.92% 대비 새 D-FINE P89.84%의 향상은2.92786%p로3%p에
미달한다. RT-DETRv4의 Town04 bicycle60%도70% 미만이다. 기준·반올림 경계를 조정하지 않았다.
파생 profile의 next-fresh-quality candidate는 두 개발 영역 절대 기준을 모두 만족한 D-FINE이며,
상대 FAIL·기존 V6/V8 보류 FAIL을 상쇄하지 않는다.

## 선택과 검증의 범위

V2 개발324장·516 positive GT만 fit에 사용했다. 모델당5⁶=15,625개, 총31,250개 scorecard를
모두 보존했다. 기존 strict scorer는 class별 독립이고 native export에 class간 NMS가 없어
class별 TP/FP/FN·negative FP·near-person을 정확히 합성할 수 있다. 선택 vector의 모든
실제 raw frame을 다시 decode/채점해 합성 결과와 정확히 같음을 확인했다.

순서는 absolute+relative PASS → absolute PASS → macro F1 → minimum class recall →
micro F1 → 고정 class 순서의 높은 threshold vector다. Absolute PASS vector는 D-FINE666개,
RT-DETRv4 46개였고 두 기준 모두 PASS인 vector는 두 모델 모두0개였다. 실패를 포함한 모든
scorecard와 두 선택을 `selection.json`에 보존했다.

두 설정을 봉인한 뒤 numerical check와 Town04 regression을 수행했다. Town0481장은
이미 V2와 진단에 소비한 개발 자료다. 새 보류·독립 check·fresh acceptance로 해석하지 않는다.
Regression 뒤 vector를 재조정하지 않았다. `regression.json`에 모든 frame/오류/primary count가 있다.

V7 preparation-development의 동일3 RGB probe에서 모델2종×3=6 numerical check를 통과했다.
기존 upstream PyTorch raw, ORT CPU/CUDA full300의 exact class·box0.1px·score1e-4와
모든5개 scalar/선택 vector의 count/class/box/score가 일치했다. TF32 off·ORT1.23.2·CPU node
fallback 금지 등 기존 Host 설정을 유지했다. 신경망 재학습/재export는 없다. 새 vector의
전체 wall latency/live20Hz/Jetson 성능을 측정한 실행은 아니다.

## Source와 감사 보완

진단367개·class calibration372개 source를 각각 결과 계산 전에 고정했다. 원래 calibration
audit는 반환된 dataclass tuple box와 저장 JSON array를 Python 객체로 바로 비교해 실패했다.
원래 source/선택/score/실패 `audit.log`는 유지하고, 별도
[감사 annex](../../perception-class-calibration-v1-audit-annex.md)의375 source freeze로
같은 frozen fit/regression을 temporary JSON에 쓴 뒤 read-back JSON candidate tree를 정확히
비교했다. 숫자 tolerance·필드 삭제·설정 변경 없이31,250 scorecard와810개 selected raw를 재생했다.
`audit-annex.json`이 PASS이며 첫 실패 로그도 남아 있다.

최종 Python201개 PASS, 새 project source의 Ruff와 문서 링크/CSV/whitespace를 검사했다.
기존 frozen V1/V2·V7/V8·training source도 유지했다. C++/runtime 변경이 없어 전체 core,
CARLA/20Hz 또는 sanitizer/Target 실행을 새로 수행한 것으로 올리지 않는다.

## 파생 후보와 재현

[파생 후보 profile](../../../../profiles/perception-class-calibration-candidates-v1.json)은 모델/
checkpoint/source/전처리/adapter/selection/numeric/regression SHA와 vector를 묶는다.
기존 runtime profile이 아니며 자동 승격하지 않는다. 다음 새 quality protocol에서 S와 이
단일 D-FINE 후보·기존 gate를 고정하고 모델 없는 준비와 새 개발/보류를 취득한다.
최종 채택·각 Jetson 전체 stack 배포/측정·그 뒤 보드 최적화는 후속이다. 미래 RGB 제외
inventory4990개는 유지한다. 새 RGB·학습·보류·보드 작업은 하지 않았다.

`experiment.tar.gz`는 frozen source·필요한 원본 raw810개·개발405개 RGB·세 sensor pair와
mask annex·native ONNX2종·수치 probe 입력/참조·모든 실패/선택/점수를 함께 보존한다.
원본 PTH와 이전 나머지4종 dense raw는 [V2 원본](../m10_model_screen_v2/README.md)에 있다.
`archive-files.json`은 내부 파일 SHA, `SHA256SUMS`는 외부 artifact SHA를 확인한다.
`sources.tar.gz`는375 frozen source다. 큰 experiment 압축은 Git LFS다.

LFS 원본을 받은 뒤 다음 명령은 새 경로에서 실제 archived source를 새 subprocess로 실행해
진단·mask·전체 검색/선택/점수를 재생하고 RGB와 파생 profile을 검증한다. GPU 신경망 추론이나
학습을 재실행하는 명령은 아니다.

```sh
PYTHONPATH=. build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_class_calibration_v1/check-archive.py \
  docs/test-plan/evidence/m10_class_calibration_v1 \
  build/m10-class-calibration-v1-archive-recheck.json
```
