# M10 4K immutable snapshot 복사·단계별 지연

실제4K 프레임 복사 평균을 **14.15ms→2.77–2.80ms**로 줄였지만 전체 영상 처리 성능은
개선되지 않았다. 카메라는15.56→12.74–12.96Hz, capture→backend 평균은125.45→127.98–129.33ms다.
**컴포넌트 개선만 확인했으며 기본 runtime으로 승격하지 않는다.**

| 조건 | camera wall Hz | simulation/wall | 복사 평균 ms | capture→backend 평균 / P95 ms | 유효 조회 | 발행/호출 | 소비 frame |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| copy-baseline-01 | 15.561 | 0.7740 | 14.149 | 125.452 / 136.820 | 62/317 (19.56%) | 95/100 | 60 |
| copy-prefault-01 | 12.741 | 0.6346 | 2.799 | 129.330 / 240.823 | 137/394 (34.77%) | 93/100 | 93 |
| copy-prefault-02 | 12.957 | 0.6453 | 2.767 | 127.976 / 237.244 | 140/388 (36.08%) | 93/100 | 93 |

[사전 기준](../../perception-frame-copy-v1-protocol.md)에 따라 같은 계측/렌더링 설정에서
bytes 복사1회와 미리 할당한 복사2회를 실행했다. baseline의156.57ms 최대 복사 지연도 포함한다.
최신 SDK의 raw_data는 Image allocation을 소유하지 않는 readonly memoryview를 반환한다.
따라서 borrowed view를 worker에 넘기지 않고 SDK Image를 실제 복사 동안 pin한 뒤 독립적인
immutable bytes를 전달한다. Python GIL은 memcpy 동안만 놓는다. Extension은 올바른 owner와
아직 release되지 않은 readonly view를 단독 소유한 내부 SDK callback용이며 범용 buffer API가 아니다.

각120개 사전 할당 slot은 한 번만 공개하고 재사용하지 않는다. enable 전 allocation은
약1.03–1.05초/4,246,732,800B다. 유한 Host 원본 수집 실험의 상한이며 production queue나
Jetson 메모리 요구가 아니다. Recorder는 같은 immutable object를 참조한다. Capacity 초과는
원본 보존 fallback 후 FAIL이며 이번 실행에서는0건이다.

전처리 산술·모델을 바꾸지 않고 gray/health/resize/tensor/inference/decode를 따로 측정했다.
개선 조건의 resize 평균14.19–14.80ms/P9550.46–52.03ms, tensor 평균5.15–5.17ms,
추론 평균35.59–35.69ms가 남았다. 관측 consumer는 약50Hz로 돌아가지만 카메라20Hz는 아니다.
[Synthetic64회](synthetic.json)의 복사 평균10.23–10.26→1.67–1.88ms와1ms heartbeat 결과도
별도로 남겼으며 실제 CARLA 성능 수치와 혼합하지 않는다.

원래 acquisition source-clock+100ms와 최초 offer receipt wall-clock+100ms를 각각 유지했다.
Source-clock100ms는 simulation 시간이며 capture부터100ms wall 완료를 보증하지 않는다.
이번 [전체 지연](end-to-end.json)은 같은 Host monotonic clock의 실제 GPU capture와 backend
return을 frame identity로 연결한 별도 wall 측정이다. 전체100회 호출과 late를 포함한다.
유효 조회는50Hz 관측 표본 비율이고 정확도·연속 가용시간이 아니다. 더 느려진 source clock에서
표본 비율이 높아질 수 있으므로 이 비율만으로 성능 개선을 판단하지 않는다.

모델은 같은 D-FINE-M960 FP32 후보,3840×2304 BGRA/Epic/postprocess/FOV90·기존 threshold,
Town04_Opt 개발38번 fixture다. 실제 on_tick 상태·비동기 world fixed10ms·client tick0회와
active1/pendinglatest1/current1 계약은 유지한다. 각각 GPU capture101개/수신100개,
종료 경계 미수신1개·primary 예정 누락0·정상 종료130·강제 종료/시작 복구/재시도0회다.
다섯 source 구간의 fresh 소비와 원본 보존을 확인한 유한 관측 PASS이며 실시간 수용이 아니다.

품질 평가·GT·새 보류·학습·실제 제어·ROS/각 Jetson 배포를 실행하지 않았다.
현재 측정으로 GPU/CPU 자원 경합의 원인을 확정하지 않는다. 남은 전처리 resize/tensor,
렌더링/전달과 추론을 함께 줄여야 한다. 느린 시뮬레이션을 목표로 합의한 것이 아니며
실제시간1×·wall20Hz·전체100ms, unavailable 보호 연결·새 독립 품질·장기 운용은 OPEN이다.
보드별 최적화는 후속으로 유지한다.

기존580개 bytes를 포함한595개 source, 원본300장/5,154,416,640B의5개 LFS archive,
누적 미래 제외7913개를 보존했다. Python352개·C++ Debug/Release/ASan12개씩,
새 복사 C API ASan+UBSan4개(ASan leak detection 제외)와 report 변조66건 거절을 기록했다.
[후속 뷰포트 실험](../m10_viewport_v1/README.md)까지의 최종 Python 집합은354개다.
[모듈 복원](restore.json)을 확인했고, 최종 복원은 후속 묶음에도 기록했다.

[독립 검증](validation.json)은 압축 원본 전부의 BGRA/RGB hash, native/Pillow/staged 입력
bit-exact 일치와 실제 snapshot copy 일치, 원래 통계·단계별 시간·전체 지연·기한 판정을
새 임시 경로의 archived source에서 재생한다. LFS pointer만으로 원본 검증 성공으로 세지 않는다.
[변조 검사](report-mutation-check.json)는 state/receipt/deadline, raw, stage, GPU clock 등의 손상을 거절한다.

```sh
OMP_WAIT_POLICY=PASSIVE build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_frame_copy_v1/check-evidence.py \
  docs/test-plan/evidence/m10_frame_copy_v1 /tmp/frame_copy-audit-new.json
```
