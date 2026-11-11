# M10 native4K 비동기 owner component

2026-11-11. **영상 변환·추론을 상태 갱신/제어 쪽 조회와 분리했고 지연·정지·오류 중 독립 진행을
확인했다. 현재4K 처리 비용에서는 유효 인지 출력이0건이므로 주행·실시간 인지 수용은 아니다.**
[사전 기준](../../perception-async-native-v1-protocol.md) ·
[오류 fixture V2](../../perception-async-native-fault-v2-protocol.md) ·
[데이터/실행 경계](../../../interfaces/perception-async-native-v1.md)를 따른다.

## 구현과 검증 범위

`AsyncNativePerception`은3840×2304 BGRA의 latest1 pending·single inference·immutable current를
별도로 소유한다. 대용량 copy를 mailbox lock 밖으로 옮기고 색상 변환·health·PIL960 resize·
CUDA·decoder는 전용 thread에서 실행한다. Consumer가 backend를 기다리지 않는다. Source
취득+100ms **및** callback receipt+100ms를 exclusive로 유지하며 clock/session/입력 오류와
bounded close를 검사한다. 새 schema/candidate/model SHA·native pixel box를 사용한다.
기존 S/640 C++ receiver에 다른 모델/좌표를 위장하지 않는다.

모델은 이전 D-FINE-M960 FP32/BASIC·TF32off·CPU node fallback 금지·vector
`[.60,.40,.60,.50,.50,.60]` 그대로다. ONNX SHA는
`b865ac0f2597afd6fcb9e887ed7738e98e7690ecb4d5cebf42724a3e6b384884`다.

실행은 **이미 소비한 개발 pilot3장의 original BGRA를 미리 읽어 두고 새 source clock으로 재생한
component 시험**이다. 원본과 playback의 frame/source/SHA를 함께 기록한다. 실제 CARLA world·
SDK transport·ROS/Gazebo·차량 controller·Zone/Leaf/Actual에는 연결하지 않았다. State는
관측용 synthetic10ms producer이고 control은 state/result 조회만 하는 consumer다.
새 RGB·GT/보류·새 품질 평가·학습·Jetson 최적화는 없다. 미래 RGB 제외5629개는 그대로다.

## 실행 결과와 원래 실패

각 조건6초, cold/startup 제외0이며 모든 입력·작업·backend return·오류·종료를 보존했다.
각 실행에서 state600/camera120/control조회300개 job을 관측했고 scheduled slot 누락은0개다.

| 조건 | Backend 완료 | Late / error | Pending 교체 | Publication | Component 판정 |
| --- | ---: | ---: | ---: | ---: | --- |
| 정상 | 43 | 43 / 0 | 76 | **0** | PASS: 분리·집계 |
| 각 call150ms 지연 | 20 | 20 / 0 | 99 | 0 | PASS |
| 첫 backend6초 정지 | 1 | 1 / 0 | 118 | 0 | PASS |
| 원래 즉시 예외 | 120 | 0 / 120 | 0 | 0 | **FAIL: call 중 overlap 미관측** |
| 별도 V2:25ms 뒤 예외 | 120 | 0 / 120 | 0 | 0 | PASS |

정상/slow/blocked는 각각 pending 만료1개를 추가로 기록했다. 즉시 예외는 call이 너무 짧아
다른 주기 job과 겹치지 않은 원래 fixture FAIL이다. 원래 실행·500 source를 유지하고, 사전
별도 V2에만 오류 응답25ms 대기를 선언해503 source로 재실행했다. 실제 worker와 모든100ms
기한/overlap 요구는 바꾸지 않았다. 두 오류 시험은 실제 모델 호출 전 예외를 주입하므로,
총304 backend 완료 중 **실제 ONNX 실행은64건**, 오류 주입은240건이다.

정상에서 state599/control299개 job이 backend 실행 구간 안에 관측됐다. 완전 정지 조건에서는
첫 backend를 해제하기 전에 주기 owner600/120/300개 작업이 모두 끝났다.25ms 오류 응답
조건에서도 state269/control134개 job이 오류 call 구간에 관측됐다. 모든 유한 종료의 input/
overwrite/pending-expiry/completion/late/error 분모와 immutable 결과를 독립 감사했다.

## 실제 처리 비용과 남은 gate

| 정상6초 재생 측정 | 관측값 |
| --- | ---: |
| State producer 평균 주파수 | 100.000Hz |
| Camera offer 평균 주파수 | 20.001Hz |
| Observational consumer 평균 주파수 | 50.003Hz |
| State interval P95 / max | 11.118 / 17.868ms |
| Consumer interval P95 / max | 21.014 / 27.280ms |
| BGRA→RGB 변환 P95 | 38.131ms |
| Health/resize/tensor P95 | 93.469ms |
| CUDA inference P95 | 20.228ms |
| Callback receipt→backend return P95 / max | **202.676 / 440.453ms** |
| Model 초기화 | 562.04ms |

Stage별 percentile의 합은 전체 percentile이 아니다. 기존 약94ms는 이미 RAM에 있는 RGB에서
시작한81장 순차 처리이며 이번3장 재생의 BGRA 변환·queue 포함 측정과 범위가 다르다.
원본 decode/파일 읽기·renderer·실제 SDK 전송/callback 진입 전 copy는 이 재생 비용에 없다.
Python thread를 분리해도 공유 자원·GIL·OS jitter나 deadline 충족이 자동 보장되지는 않는다.
위 평균 주파수는 실제 차량 제어의 deterministic50/100Hz 수용이 아니다.

**정상43회 모두100ms를 넘었으므로 publication0/fresh-output=false**다. 비동기로 제어 쪽
조회는 진행할 수 있지만 현재 경로로 최신 인지를 공급할 수는 없다. Unavailable을 clear road로
사용하지 않는다. 다음은 PC 변환·전처리 비용을 별도 version으로 개선하고, 실제 ingress와
기존 제어 경로에서 원천 age·수신/적용 기한·보호를 검증하는 것이다.100ms를 늘려 통과시키지 않는다.
새 독립 개발/보류·live 인지20Hz·M11 metric fusion·각 Thor/Orin 전체 stack 배포는 남아 있다.

## 회귀와 재현

새23개를 포함한 Python **243개**, Debug/Release/ASan+UBSan perception 각**13개**, Ruff가 PASS다.
ASan/UBSan은 기존 C++ 검사이며 Python thread를 sanitizer로 검사한 것은 아니다. 동결 부모493개와
V1의500개 소스 bytes를 유지했다. Native adapter의 실제64개 결과를 이전 개발3장의 CUDA raw에서
다시 얻은 검출과 native box0.6pixel/score1e-4로 대조했다. 이는 adapter 검출 동등성 확인이며
새 full300 reference·새 품질 수용 시험이 아니다.

`sources.tar.gz`에는503개 소스가 있고, 실행5건의 원본 JSON/log·두 freeze·기존 CUDA reference3개·
원래 numeric metadata·단위/CTest/Ruff log·SHA256SUMS를 함께 보존했다. 큰 기존 모델/BGRA는
[원본 해상도 근거](../m10_camera_resolution_v1/README.md)의 archive에 이미 보존되어 있다.
이 묶음은 새로 모델을 실행하지 않고도 fresh archived source에서 trace와 검출 대조를 재감사한다.

```sh
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_async_native_v1/check-evidence.py \
  docs/test-plan/evidence/m10_async_native_v1 build/m10-async-recheck-new.json
```

원래 모델/BGRA를 복원한 환경에서 실제 정상 재생을 다시 수행하려면 새로운 output 경로를 쓴다.
기존 모델 초기화·cold call은 그대로 기록하며 새 실행을 기존 결과에 합치지 않는다.

```sh
PYTHONPATH=.:tests/integration/perception build/m10-perception/cuda-venv/bin/python \
  tests/integration/perception/probe_async_native_v1.py \
  --media build/m10-camera-resolution-v1/pilot-6-01/dataset/rgb.json \
  --model build/m10-resolution-v2/models/dfine-960.onnx \
  --models build/m10-resolution-v2/models.json \
  --freeze docs/test-plan/evidence/m10_async_native_v1/freeze.json \
  --output build/m10-async-native-replay-new --fault none
```
