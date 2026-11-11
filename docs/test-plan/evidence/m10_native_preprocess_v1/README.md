# M10 native4K 전처리 개선·실제 비동기 카메라

2026-11-11. **전처리 동등성·기록 영상 비동기 재생 PASS, 실제 CARLA fresh-output gate FAIL.**
모델·영상100ms 기한·confidence·기본 S/runtime640은 유지한다. M10은 OPEN이며20Hz,
새 독립 품질·실제 제어·Thor/Orin 배포를 수용한 결과가 아니다.

## 변경과 고정 조건

[사전 전처리 기준](../../perception-native-preprocess-v1-protocol.md)에 따라 CPU의
BGRA 채널 재배열 복사와 전체 float64 밝기 통계를 줄였다. PIL BGRX로 원본 RGB를 읽고,
BGRA 회색조의256-bin 정수 count/moment로 동일한 건강 판정을 수행한다. std=2 경계는
원래 NumPy reduction으로 처리한다. OpenCV4 threads는 producer enable 전에 설정한다.
Pillow11.3.0·OpenCV4.11.0·NumPy1.23.5 및 PIL bilinear960 tensor 산술은 고정한다.

`FastNativeBackend`는 기존 `AsyncNativePerception`과 같은 별도 native4K typed 결과를
사용한다.3840×2304 원본·D-FINE-M960 FP32/ORT_BASIC·TF32 off·고정 confidence와
실행1/대기1/current1, **원래 source+100ms AND offer receipt+100ms exclusive**는 그대로다.
학습·TensorRT·보드별 최적화는 수행하지 않았다.

부모503개 파일을 유지한 전처리 freeze509와 live freeze514를 실행 전에 고정했다.
모델 SHA는 `b865ac0f2597afd6fcb9e887ed7738e98e7690ecb4d5cebf42724a3e6b384884`다.
모든 첫/cold call을 포함했고, 초기화 시간은 보고서에 별도로 남겼다.

## 동등성과 재생 결과

기존 개발4K pilot3+comparison81, 총84장의 RGB와 모델 입력 tensor가 **바이트 단위 동일**하다.
건강 통계 오차는1e-10 이내다. 전체16,777,216 RGB 색상의 grayscale 동등성,
alpha 무시·std2·black/white98% 경계도 검사했다. GT·과거 보류는 읽지 않았다.

84장 쌍별 BGRA 변환+health+resize+tensor P95는 **103.358→42.020ms**다.
첫 호출을 포함하며 disk/decompression/모델 추론은 제외한다. 두 경로 모두 OpenCV4 threads다.

| 6초 재생 조건 | 모델 호출 | 발행 / late / error | pending overwrite | 소비된 고유 frame |
| --- | ---: | ---: | ---: | ---: |
| 정상 | 85 | 46 / 39 / 0 | 35 | 21 |
| 추가150ms 지연 | 25 | 0 / 25 / 0 | 94 | 0 |
| owner 종료까지 backend 정지 | 1 | 0 / 1 / 0 | 118 | 0 |
| 25ms 뒤 예외 | 120 | 0 / 0 / 120 | 0 | 0 |

각 조건에서 synthetic state600·camera120·관측 consumer300 jobs, skipped slot0을 보였다.
실제 ONNX111개 호출의 최종 검출은 기존3장 CUDA 출력과 count/class 동일,
score atol1e-4/native box atol0.6px 이내다. 새 full300 수치 평가나 품질 평가를 뜻하지 않는다.
정상 offer receipt→backend return P95는 **116.561ms**로,
[원래 component](../m10_async_native_v1/README.md)의202.676ms보다 줄었다.
46건 발행 중 관측 consumer가21개 frame을 읽었다. 발행 자체가100ms를 갱신하지 않아
소비 전에 만료될 수 있다. 전체20Hz 처리나 실시간 보장으로 해석하지 않는다.

## 실제 카메라: 실패 보존

[live 사전 기준](../../perception-carla-native-async-v1-protocol.md)으로 Town04_Opt/Epic,
소비된 개발 site38의 첫 person case를 한 번 실행했다. CARLA와 CUDA는 같은 RTX3090을 쓴다.
원래 frame5 patch·실제 SDK·4K/FOV90/postprocess를 연결했고, 다른 tick writer나 차량 명령은 없다.
이 실행은 **관측 SIL**이며 움직이는 차량/기존 Zone–Leaf controller 통합은 아니다.

| 실제 측정 | 결과 |
| --- | --- |
| 실제 world snapshot | 304개, 평균67.719Hz, step10ms |
| 카메라 callback | 예정 frame5 전부60개, 평균13.599Hz |
| 별도 관측 consumer | 249개, 평균49.999Hz |
| 모델 완료 | 37개 전부 late, 발행/소비0, 오류0 |
| pending overwrite | 23개; 원본 취득/receipt 유지 |
| receipt→return | P95221.497ms, 최대689.516ms; cold 포함 |
| 전처리 / 추론 | 각 P9586.307 /44.519ms |
| 카메라·source 정지 후 |100ms 이후10개 unavailable 조회 |
| 서버 종료 | exit130, forced stop 없음; 전체73.373초 |

Capture의 prospective fresh-consumption gate가 실패했으므로 capture와 server의 **FAIL을 유지**한다.
source 연속성·정확한60개 취득·37개 완료 분모·독립 진행 검사는 통과했지만 유효 출력은 없다.
Backend return까지만 보면37개 중2개는 receipt100ms 미만(최소89.512ms)이다. 최종 admission은
그 이후 원래 source와 wall 기한을 함께 검사한다. 현재 trace는 최종 판정 시각의 두 clock을
별도 저장하지 않으므로37개 late의 정확한 clock별 원인을 나누어 단정하지 않는다.
Replay에서 동작한 비동기 분리가 공유 GPU/CPU 부하의 성능 문제를 자동 해결하지는 않는다.
SDK `raw_data` bytes materialization은 offer 진입 전에 있고, callback 전체 P95는13.842ms다.
따라서 receipt budget을 센서 취득→호스트 전체 wall latency라고 표현하지 않는다.

64-frame 유한 진단 recorder는 production latest1 mailbox와 별개로 원본 bytes 참조를 보존한다.
이 실행의60×35,389,440B는 약2.12GB RAM이며 hashing/compression은 측정 후 수행했다.
대용량 recorder를 배포용 queue 설계로 채택하지 않는다. 모든60장과 기존5629개를 합친
미래 제외 목록은 **5689개**다. 실패·첫 프레임도 새 holdout으로 재사용하지 않는다.

## 보관과 재검사

- `equivalence.json`:84개 입력 SHA/tensor SHA·건강 통계·쌍별 시간. 실제 tensor 재생은 기존
  [4K 원본 archive](../m10_camera_resolution_v1/README.md)의 개발 RGB가 필요하다.
- `none/slow/blocked/exception-01`: 모든 호출·periodic trace·오류·counter 원본.
- `live-01`: 원래 FAIL report·UE/SDK log·취득/호출/관측 trace. `raw-camera.tar.gz`는 원본60개
  BGRA zlib packet 전체를 담은 Git LFS artifact(1,021,022,741B)다.
- `sources.tar.gz`:514개 source bytes. `parent-freeze.json`→`freeze.json`→`live-freeze.json`은
  실행 전 append-only 관계를 보존한다. 후속 검사 코드/문서는 `SHA256SUMS`로 별도 검사한다.
- `check-evidence.py`: 새 임시 디렉터리에 source를 복원해4개 trace와111개 검출을 재감사하고,
  live의 **기대한 실패 지점**을 확인한다. 진단 copy의 status guard만 우회해 그 앞의 조건을
  재생하며 원본 FAIL·fresh-output gate를 바꾸지 않는다. 정지 source expiry도 별도로 확인한다.
  이어서60개 압축·BGRA·RGB hash와5689개 제외 union을 모두 재구성한다.

```sh
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_native_preprocess_v1/check-evidence.py \
  docs/test-plan/evidence/m10_native_preprocess_v1 build/native-preprocess-recheck.json
```

Python 전체250개와 C++/boundary Debug·Release·ASan/UBSan 각12개를 검사한다.
검사 결과와 fresh archived-source/raw 감사는 `validation.json`에 연결한다.
다음은 실제 렌더링 부하에서 변환/추론·queue 대기 비용을 더 낮추거나 시뮬레이터와 추론의
실행 자원을 분리해100ms 내 fresh 공급을 확보하는 것이다. 그 뒤 원래 dependency age와
보호 경계를 유지하며 실제 상태/제어 연결, 사전 고정한 새 준비·개발/보류 평가를 진행한다.
