# M10 native4K CPU resize·실제 fresh-output 검증

2026-11-11. **모델 입력 동일성을 유지한 CPU 개선으로 실제 CARLA 관측에서27개 유효 결과를
발행·소비했다.** 초기4개 완료는 late이며 모두 보존한다. 전체20Hz·장기 운용·새 독립 품질·
실제 차량 제어·각 Jetson 배포는 아직 미수용이고 기본 S/runtime640과 M10 OPEN은 유지한다.

## 구현과 사전 기준

[프로토콜](../../perception-native-kernel-v1-protocol.md)을 실행 전에 고정했다.
원본3840×2304·D-FINE-M960 FP32/ORT_BASIC·TF32 off·고정 confidence와 latest1 owner,
**원래 source+100ms AND receipt+100ms exclusive**는 그대로다. 새 학습·TensorRT·보드별
최적화나 source timestamp 갱신은 없다.

`native_resize_v1.cpp`는 BGRA를 직접 읽어 RGB960을 계산한다. 전체4K RGB 중간 복사를 없애고,
[Pillow11.3.0의 계수·두 단계22-bit 반올림](https://github.com/python-pillow/Pillow/blob/11.3.0/src/libImaging/Resample.c)을
유지하며4개 CPU thread로 행을 나눈다. OpenMP PASSIVE, GIL을 해제하는 ctypes CDLL,
`-ffp-contract=off`와 일반 C++17을 사용한다. 특정 CPU ISA·GPU·보드에 맞춘 코드는 없다.
원본 source/license/provenance는 `third_party/pillow-11.3.0`에 보관했다. 빌드/실행은 이 x86
Host에서 검증했으며 ARM/Jetson에서는 별도 빌드·동등성 검증이 필요하다.

하나의 인지 owner가 scratch/output을 소유하며 `NativeResize` instance를 동시 호출하지 않는다.
기존 BGRA grayscale/health와 NumPy float32 tensor 산술은 유지한다. 최종 완료 기록은512개로
제한하고 overflow를 센다. 실제 판정 시각의 source/wall·queue 시작·backend return을 기록하여
원천만 만료/receipt만 만료/둘 다 만료를 독립 재계산한다. 기존 입력·가용성·만료 로직은 유지한다.

부모514개 파일을 보존하고 새19개를 더한 **533-file freeze**에 source, profile, 빌드 manifest와
실제 사용한 shared library를 함께 고정했다. 모델 SHA는
`b865ac0f2597afd6fcb9e887ed7738e98e7690ecb4d5cebf42724a3e6b384884`다.

## 입력 동등성·재생

기존 개발4K84장의 모델 tensor/건강 판정은 전부 **exact**이며, 이전 보관 tensor SHA와도 같다.
Seeded noise·alpha/색상·경계 impulse·constant0/255·checkerboard의1/4-thread 결과를
Pillow와 비교했다. 원래 owner21개 회귀와 clock별 원인·overflow 검사를 함께 통과했다.

같은84장 쌍별 측정의 변환/전처리 P95는 **38.971→16.891ms**다.
Disk/decompression/inference는 제외하고 첫 호출은 포함한다. 이전 회차의42ms와는 실행이 다르다.

| 6초 replay 조건 | 실제/주입 backend 호출 | 발행 / late / error | overwrite | 고유 소비 frame |
| --- | ---: | ---: | ---: | ---: |
| 정상 |115|114 /1 /0|5|112|
| 추가150ms 지연 |30|0 /30 /0|90|0|
| backend 정지 |1|0 /1 /0|118|0|
|25ms 뒤 예외 |120|0 /0 /120|0|0|

실제 모델 호출146개는 기존3장 CUDA 출력과 count/class 동일·score atol1e-4·native box0.6px
이내다. 새 full300 수치/품질 평가가 아니다. State600/camera120/consumer300 jobs를 각 조건에서
실행했고 모든 cold call·원래 packet/기한·누락 분모를 유지했다. 정상 receipt→backend return
P95는 **40.640ms**, 최대344.892ms이며 유일한 late는 첫 호출이다. Cold 제외 성능으로 바꾸지 않는다.

## 실제 CARLA 비교

각각 새 Town04_Opt/Epic 서버, 소비된 개발 site38의 같은 person fixture와4K/FOV90/postprocess,
frame5 취득·고정10ms world·같은 RTX3090을 사용했다.180..184 world ticks의 유한 관측 시험이다.
기존 방식 baseline은 사전 선언한 **진단 전용**이며 fresh0도 기록할 수 있다. 개선 kernel은
fresh 소비가 반드시 필요하다. 이 scope 차이를 baseline의 품질/성능 수용으로 해석하지 않는다.
이전 [37개 모두 late의 FAIL](../m10_native_preprocess_v1/README.md)은 그대로 남아 있다.

| 실제 측정 | 기존 Pillow baseline | Native kernel |
| --- | ---: | ---: |
| 실제 world snapshots / 평균 Hz |183 /67.615|181 /63.870|
| 예정 camera 취득 / 평균 Hz |36 /13.565|36 /12.933|
| 관측 consumer / 평균 Hz |161 /49.999|167 /49.999|
| 모델 완료 |23|31|
| 발행 / 고유 소비 |0 /0|**27 /27**|
| late / overwrite |23 /13|4 /5|
| late 원인 |둘 다21, receipt만2|둘 다3, source만1|
| receipt→최종 admission P95 |201.765ms|115.755ms|
| receipt→backend return P95 |201.739ms|115.727ms|
| 전체 전처리 구성 |convert P9513.030 + preprocess P9570.315ms|결합 preprocess P9526.549ms|
| inference P95 |44.136ms|39.891ms|
| queue 대기 평균 / P95 |39.542 /63.758ms|4.990 /42.236ms|
| 센서·source 정지 후 만료 확인 |10회 unavailable|10회 unavailable|
| 서버 정상 종료 / 전체 시간 |130 /53.493s|130 /68.785s|

단계별 percentile을 더해서 전체 percentile로 해석하지 않는다. 두 유한 실행의 자원 상황은
완전히 같다고 보장하지 않으며 이 비교를 통계적 성능 보장으로 확대하지 않는다.
Kernel의 처음4개 완료는 모두 late, 이후27개 완료가 연속 발행·소비됐다. 첫 inference는
403.669ms이고 뒤의 backlog까지 남겼다. Source-only late는 원래 영상 source age가110ms인
반면 receipt→최종 판정은95.145ms였다. 원래 source 기한이 실제로 거절했고 연장하지 않았다.

평균50Hz는 **관측 소비자**의 진행이다. 차량 controller/Actual·Central–Zone–Leaf의 새 주행
연결은 아니다. Camera 약13Hz와 cold 포함 admission P95>100ms 때문에 전체wall20Hz나
항상 유효한 인지 공급을 수용하지 않는다. SDK raw_data materialization은 offer 전에 있으며
callback P95는 baseline14.608/kernel13.020ms다. Sensor→host 전체 wall age로 가장하지 않는다.

## 원본·검증·다음 단계

72개 callback 원본을 전부 보존했다. 각 실행의40-frame 유한 진단 recorder는 production
latest1 mailbox와 별개이며, 실제36×35,389,440B≈1.27GB RAM을 사용한다. 저장/압축은 측정
후에 수행했다. 임시 raw는 root filesystem에 두고 UE 시작 중 archive 작업을 하지 않았다.
미래 제외 union은 **5761개**이며 실패·초기·진단·보류 소비 자료는 fresh holdout에 재사용하지 않는다.

- `freeze.json`, `parent-freeze.json`, `sources.tar.gz`: 실행 전 source533개·실제 library·빌드 SHA.
- `equivalence.json`:84장 tensor와 health exact·전처리 시간. `reference/equivalence-v1.json`과
  기존 [4K 개발 원본](../m10_camera_resolution_v1/README.md)에 연결한다.
- Replay4개와 `baseline-01`/`kernel-01`: 모든 호출·clock별 admission·실제 world/consumer trace,
  서버/SDK log. cold0 제외, 내부 오류0, camera 누락0, overflow0, 종료130을 확인한다.
- `raw-camera.tar.gz`:72개 BGRA zlib 원본 전체, Git LFS **1,224,854,511B**.
- `check-evidence.py`: 새 디렉터리에 source533개를 복원하고4개 replay·2개 live·모든 clock별
  판정·146개 이전 CUDA 검출을 재생한다.72개 raw의 압축/BGRA/RGB SHA 및 제외 union을
  재구성하고, **그72개 실제 입력도 원래 Pillow와 native tensor/health exact**인지 검사한다.
  GPU/시뮬레이터·새 모델 추론 없이 수행하는 감사다. 새 품질 평가를 뜻하지 않는다.
- Python278개, 기존 C++/boundary 설정별12개, native kernel의 standalone ASan+UBSan,
  Ruff·문서/traceability·부모 source 무결성 결과는 `validation.json`과 로그에 연결한다.

```sh
OMP_WAIT_POLICY=PASSIVE build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_native_kernel_v1/check-evidence.py \
  docs/test-plan/evidence/m10_native_kernel_v1 build/native-kernel-recheck.json
```

다음은 명시적 startup 준비/가용성, 반복·장시간 live 부하와 렌더링/SDK source age를 검증하고
실제 상태·보호 경로와 연결하는 것이다. 새 준비·개발/보류 품질과 Thor/Orin 각각의 전체 stack
배포도 남아 있다.2D box를 직접 actuator command로 바꾸거나 기존 wheel/command 기한을 늘리지 않는다.
