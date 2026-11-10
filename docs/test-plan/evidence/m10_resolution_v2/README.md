# M10 입력 해상도 비교와960 car-confidence 후속 후보

2026-11-10. **사전학습 D-FINE-M 가중치를 유지하고 모델 입력을 비교한 뒤, 개발용 후속 후보를 고정했다.**
640·960의 수치/개발 검증과 별도 car confidence 변경을 완료했다.1280은 수치 FAIL로 품질
평가에서 제외했다. 신규 학습·camera RGB·과거 holdout 접근·보드 최적화·runtime 교체는 없다.
기본 S와 M10 OPEN, [V9 새 보류 FAIL](../m10_quality_v9/README.md)은 그대로다.

## 개발 결과와 후보 판단

| 자료 | 설정 | TP/FP/FN | Precision | Recall | 절대 기준 |
| --- | --- | --- | ---: | ---: | --- |
| 개발405 | 기존 S | 485/51/160 | 90.49% | 75.19% | FAIL |
| 개발405 | 640 / 원래 vector | 575/53/70 | 91.56% | 89.15% | PASS |
| 개발405 | 960 / 원래 vector | 585/33/60 | 94.66% | 90.70% | PASS |
| 개발405 | 960 / car .60 | 586/33/59 | 94.67% | 90.85% | PASS |
| 소비한 V9 개발81 | 기존 S | 98/13/31 | 88.29% | 75.97% | FAIL |
| 소비한 V9 개발81 | 640 / 원래 vector | 119/6/10 | 95.20% | 92.25% | PASS |
| 소비한 V9 개발81 | 960 / 원래 vector | 120/3/9 | 97.56% | 93.02% | PASS |
| 소비한 V9 개발81 | 960 / car .60 | 121/3/8 | 97.58% | 93.80% | PASS |

V2는 V4–V8 개발405장의 점수와960 지명을 봉인한 뒤, 이미 소비한 V9 개발81장을 회귀했다.
960은 양쪽 절대·전체 S-relative 기준과 앞선5개 site의 절대 기준을 통과했다. 작은 GT(box
area<32²)의 개발405 재현율은234/300(78%)→249/300(83%), V9 개발은51/60→53/60이다.
Rider는 앞선405에서96/135→95/135, V9 개발에서21/27→22/27로 일괄 개선은 아니다.

원래960의 V9 개발 car recall은640의32/33→31/33이다. 새 miss2건을 포함한 net1 감소이며
전체 TP 증가는 이 회귀를 상쇄하지 않는다. 사전 고정한640 대비 class 무하락 gate를 실패해
**원래 V2는 `eligible_for_next_fresh_quality_test=false`**다. S-relative PASS와 별개다.
원래 코드·점수·nomination·거절을 보존했다.

개발 오류 분석에서 두 car miss는 native IoU.915/.945지만 score.6765/.4983으로.70에서
제외됐다. [별도 car V1 기준](../../perception-resolution-car-v1-protocol.md)을 고정한 뒤
**car confidence만.70→.60**으로 한 번 변경했다. 기존.35 하한과 다른5개 class, GT/primary
matching·모델/전후처리·gate는 그대로다. 검색·추가 export·학습은 없다.

후속 설정은405장에서 TP586/FP33/FN59, V9 개발81장에서121/3/8이다. Car recall은32/33으로
회복됐고 양쪽 절대·S-relative·640 무회귀와 모든6개 site 절대 gate가 PASS다. 전체486개
개발/774 GT는 **TP707/FP36/FN67·P95.15%/R91.34%**다. 기존640은694/59/80·P92.16%/
R89.66%다. 이 변경은 V9 DEVELOPMENT 오류를 보고 설계했으므로 **486장 전부 설계 자료**다.
81장을 독립/맹검/보류라고 부르지 않는다. 다음에는 후보를 고정한 새 개발·새 보류가 모두 필요하다.

고정 후보 `dfine-m-960-car-v1`의 [파생 프로파일](../../../../profiles/perception-resolution-candidates-v1.json)은
ONNX78,671,426byte·SHA256 `b865ac0f2597afd6fcb9e887ed7738e98e7690ecb4d5cebf42724a3e6b384884`,
class0/1/2/3/5/7 vector `[.60,.40,.60,.50,.50,.60]`과 backend/adapter/결과 SHA를 묶는다.
`runtime_promotion=false`, `independent_acceptance=false`다. 최종 Reference 채택이나 차량 수용이 아니다.

## 원래 수치 실패·cache 원인·제한된 복구

[원래 V1 기준](../../perception-resolution-v1-protocol.md)은640/960/1280 세 입력을 선언했다.
엄격한 checkpoint state load 뒤 learned parameter와 위치 cache/anchor 이외 state의 SHA는
같았다.960/1280은 native 위치/anchor cache만 재생성했고 vendor source는 바꾸지 않았다.
original camera640×384를 PIL bilinear로 확대하므로 새로운 sensor detail을 추가한 것은 아니다.

최초 full300 수치 검사는 FAIL이다.640 ONNX는 원래 checkpoint cache인데 reference는640
cache를 재생성한 오류가 있었다. 저장된 float32 anchor와 CPU native regeneration의 최대
차이는0.0002018213이고 일부 낮은 score를 바꾼다. 별도 cached640 reference가 원래 V9의
upstream3건과 일치함을 확인했다. 이 수정으로 원래 잘못된 reference를 PASS로 바꾸지 않는다.

[수치 조사 annex](../../perception-resolution-v1-numeric-annex.md)는 GT/품질을 읽지 않고 두
ORT profile만 사전에 정했다. DISABLE_ALL은 CPU-node fallback 금지 조건으로 session을
만들 수 없어 FAIL이다. 그 실패 후 사전 선언된 BASIC만 재개했다. BASIC은640/960의6건이
PASS,1280은3건 중1건이 full300 box.1pixel/score1e-4 기준을 실패했다. 낮은 score·비대상
class proposal도 삭제하지 않았고 허용 오차·confidence를 늘리지 않았다. V1은 계속 FAIL이다.

[새 V2 기준](../../perception-resolution-v2-protocol.md)은 수치로 통과한640/960만 따로 동결했다.
FP32/batch1·TF32off·HEURISTIC·2GiB arena·CPU fallback 금지를 유지하고 BASIC을 고정했다.
새 backend에서 full300 exact-class 일대일 unordered set, native PyTorch/ORT CPU/CUDA와
완성 vector 검출 **6건이 PASS**다. 후속 car vector도960의3probe에서 같은 기준이 PASS다.

Source freeze는 원래467개, V2 477개, car 후속481개다. 원래 소스/실패를 수정하지 않았다.
V1의 원래3종 품질 추론은0건이며 V2만972건을 실행했다. 원래 S486개 raw도 모두 재해석했다.
그 뒤960 raw486개에서 원래 vector/JSON 일치를 먼저 확인하고 후속 vector를 파생했다.

## 지연·배포 범위

| 실제 V2 실행 | Attempted | Valid | <100ms admitted | P95 ms | Cold 포함 Max ms | 생성 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection / 640 | 405 | 405 | 404 | 16.891 | 207.641 | 481.3 |
| selection / 960 | 405 | 405 | 404 | 30.473 | 112.286 | 217.4 |
| regression / 640 | 81 | 81 | 81 | 16.463 | 94.406 | 218.2 |
| regression / 960 | 81 | 81 | 80 | 31.254 | 107.511 | 213.9 |

새 car vector는 저장된 raw 재해석이므로 위 지연/원래 admission은 맥락 자료다. 새 filter의
실제 deadline·live 성능을 수용한 것이 아니다. Cold/init/error/late를 제거하지 않았으며 raw
압축 저장 I/O는 추론 시간에서 제외했다. 원래640과960의 입력 tensor는4,915,200/11,059,200byte다.

Host RTX3090의 수치·정확도·offline 지연 결과다. 전체wall20Hz·시작/종료 안정성·차량 통합,
Thor/Orin 각각 전체 Central–Zone–Leaf 배포·실측은 후속이다. Board engine/FP16/INT8/전력·
클록 최적화나 TensorRT import를 수행하지 않았다. 원래 source/opset·GridSample 등 변환
고려 항목은 기존 모델 registry 및 이번 models manifest에 남긴다.

## 감사·재현

모든486개 개발 RGB는 이미 소비한 자료이며 준비/이전 평가 제외5449개는 그대로다. 새 보류
RGB/GT/예측을 설계에 읽지 않았다. 모델·metadata reader는 development partition만 허용한다.

원본 raw1458개(S486+D-FINE972), 후속 vector486개와 GT/primary·site gate·nomination/
실행 순서를 재생했다.216개 Python과 Debug/Release/ASan+UBSan perception 각13개가 PASS다.
car 수정 후 전체 Python216개를 다시 확인했다. C++ 변경은 없으며 Python은 sanitizer 계측이 아니다.
Ruff는 shared API의 의도된 re-export2건에만 `resolution_v2_common.py:F401` 예외를 주고
검사했다. 초기 fixture 인자 오류·annex 상대경로 오류·모든 원래 수치/세션 FAIL도 보존한다.

`experiment.tar.gz`는 동일한 원본/모델/동결 source를 여러 경로에서 참조하는 중복을 줄이기
위한 content-addressed object 묶음이다. `paths.json`이 원래 project 경로와 SHA256을 연결하고,
`check-archive.py`가 object hash를 검사해 새 project를 구성한다. 새 source를 실제 subprocess로
실행해 모든 점수/실패/후보를 확인하며 재추론·GPU는 사용하지 않는다.

- `v1-*`: 원래 export/reference/수치 FAIL·cache 진단·제한된 두 profile와 복구 기록.
- `v2-*`: 검증된640/960 source·모델·native6probe·원래 점수·지명·car 회귀 거절.
- `car-*`, `candidate-profile.json`: 별도 source freeze·native3probe·개발 설계/파생 후보.
- `paths.json`, `sources.json`/`sources.tar.gz`, `experiment.tar.gz`, `SHA256SUMS`: 동결 source, 원본 RGB/seal/native raw/모델과 모든 실패.
- `archive-recheck.json`: 독립된 새 경로 재감사 결과. 감사 PASS와 새 품질 수용은 별개다.

```sh
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_resolution_v2/check-archive.py \
  docs/test-plan/evidence/m10_resolution_v2 build/m10-resolution-recheck-new.json
```

다음은 이 단일 후보와 기존 S·원래 기준을 새 protocol에 고정하고 모델 없는 준비·새 개발·
지명 봉인·새 보류 평가를 수행하는 일이다. 이번 개발 설계 점수로 과거 V9 보류 FAIL을 상쇄하지 않는다.
