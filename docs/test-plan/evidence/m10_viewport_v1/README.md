# M10 작은 main viewport·4K 센서 유지 실측

사용하지 않는 main viewport만128×128로 줄인 두 실행은 **13.25/13.07Hz**였다.
[직전 복사 개선 조건](../m10_frame_copy_v1/README.md)의12.74/12.96Hz에 비해 전체 목표를
해결할 변화가 없었다. Capture→backend 평균126.94/127.94ms·P95263.75/253.73ms로
**실시간 수용은 OPEN이며 화면 설정을 원래대로 복원했다.**

| 조건 | camera wall Hz | simulation/wall | 복사 평균 ms | capture→backend 평균 / P95 ms | 유효 조회 | 발행/호출 | 소비 frame |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| viewport-small-01 | 13.249 | 0.6602 | 2.748 | 126.936 / 263.748 | 129/379 (34.04%) | 93/100 | 93 |
| viewport-small-02 | 13.071 | 0.6515 | 2.828 | 127.939 / 253.725 | 134/384 (34.90%) | 93/100 | 92 |

[사전 기준](../../perception-viewport-v1-protocol.md)은 `-ResX=128 -ResY=128 -ForceRes -windowed`만
추가한다. 첫 capture 전에128×128 main render target이 실제 생성됐음을 검사했다.
인식 센서의3840×2304 BGRA 출력과 Epic 설정·postprocess는 유지했다. 별도 main viewport
변경이므로 센서 출력 크기 유지와 영상 내용/품질 동등성은 별개이며 품질 동등성을 주장하지 않는다.
기존 blocking query·최대 render-target 유지2/1·120개 일회용 snapshot을 그대로 사용했다.
두 실행 모두 측정 구간 재할당 로그0줄이다.

실행 옵션이 외부 GameUserSettings.ini를 저장하므로 실행마다 원본853×640 설정을
byte-for-byte 복원했다. [원래 설정 hash](environment-before.json), 첫 번째/두 번째 종료 후
설정과 [최종 복원 hash](settings-restore-02.json), [원래 CARLA 모듈 복원](restore.json)을 보존한다.
공용 기본 profile·동결된 과거 source·M9/native 경로를 변경하지 않았다.

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

기존595개 bytes를 포함한601개 source, 원본200장/2,565,877,760B의4개 LFS archive,
누적 미래 제외8113개를 보존했다. Python354개·report 변조44건 거절을 기록했다.
직전 묶음과 합쳐 신규 실제5회·원본500장·변조110건이다. C++12개씩 및 새 복사 C API
ASan+UBSan4개 검증은 [직전 묶음](../m10_frame_copy_v1/README.md)에 있다.

[독립 검증](validation.json)은 압축 원본 전부의 BGRA/RGB hash, native/Pillow/staged 입력
bit-exact 일치와 실제 snapshot copy 일치, 원래 통계·단계별 시간·전체 지연·기한 판정을
새 임시 경로의 archived source에서 재생한다. LFS pointer만으로 원본 검증 성공으로 세지 않는다.
[변조 검사](report-mutation-check.json)는 state/receipt/deadline, raw, stage, GPU clock 등의 손상을 거절한다.

```sh
OMP_WAIT_POLICY=PASSIVE build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_viewport_v1/check-evidence.py \
  docs/test-plan/evidence/m10_viewport_v1 /tmp/viewport-audit-new.json
```
