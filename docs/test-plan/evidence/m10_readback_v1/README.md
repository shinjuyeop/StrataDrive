# M10 CARLA GPU readback V1

4K/Epic와 원래100ms 기한을 유지하고 GPU readback을 계측했다. Blocking query를
제거하면 카메라 wall Hz는 증가했지만, 유효 인식 조회는 감소했고 반복1건은 FAIL이다.
**비동기 readback을 기본값으로 승격하지 않는다.** 후속 재할당 비교는
[render-target pool 근거](../m10_readback_pool_v1/README.md)에 있다.

| 조건 | world wall Hz | camera wall Hz | simulation/wall | 유효 조회 | 발행/추론 | 소비 frame | 판정 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| baseline-01 | 56.150 | 11.248 | 0.5615 | 175/436 (40.14%) | 94/100 | 94 | PASS |
| deferred-01 | 62.961 | 12.635 | 0.6296 | 100/397 (25.19%) | 97/99 | 87 | PASS |
| deferred-02 | 64.075 | 12.851 | 0.6408 | 26/392 (6.63%) | 21/100 | 21 | **FAIL** |
| baseline-02 | 56.781 | 11.376 | 0.5678 | 195/443 (44.02%) | 99/100 | 98 | PASS |

각100장 원본을 보존했다. deferred-01의1장은 실제 상태 초기화 전 도착해 추론에
들어가지 않았다. 모든 실행의 GPU capture101개/SDK 수신100개이며, 마지막 경계 뒤
capture1개는 stop 이후 미수신으로 명시했다. 예정한 primary 카메라 frame 누락은0이다.
다섯100-source-frame 구간의 소비 수는 각각 [19,20,20,19,16], [13,19,20,18,17],
[0,0,0,1,20], [18,20,20,20,20]이다. 실패를 재시도하거나 기한을 늘리지 않았다.

기준 경로의 blocking query 평균은22.55/22.75ms다. Deferred는 이 구간이0이며 GPU fence
대기가 worker로 이동했다. GPU 작업 자체가 사라진 것은 아니다. Capture→SDK callback
평균은71.21/71.60/70.34/70.79ms로 거의 줄지 않았다. 원래 offer receipt→backend return
평균은60.32/62.02/107.16/60.31ms다. Deferred-02는 late79개이며 CPU 전처리 평균33.12ms와
대기열 지연이 증가했다. 단일 원인이나 장기 안정성을 확정하지 않는다.

새 opt-in RGB 경로는 게임 스레드에서 stream/header/영상 크기를 값으로 보관한다.
비동기 완료 task는 Sensor UObject를 참조하지 않는다. CaptureScene→GPU copy 순서,
원래 frame/timestamp/pose를 유지하고 GPU readback은 최대3개, trace는4096개로 제한한다.
두 비교 경로 모두100us fence polling과 같은 계측/전송 코드를 사용한다. 따라서 기존
무계측 바이너리와 완전히 동일한 경로라는 주장은 하지 않는다. Flag가 없으면 기존
PixelReader 경로를 사용한다. 실제 모델·전처리·입력과 active1/pending1/current1은 그대로다.

원본 external source/engine/archive는 수정하지 않고 unity object를 격리 빌드했다.
기존 export10310개는 모두 남고11개가 추가됐다. 설치 모듈 SHA는
`7e444c0c745577b957aec93d3feba6b35d031119a9410c26f6fb4ad02a23c751`이다.
6개 비교 종료 후 원래 모듈 SHA
`099f15274e768049c774166b17eb55838e672f9098f7d9e9f89aeddab6f81134`로 복원했다.
[빌드 manifest](build/manifest.json), [복원 결과](restore.json)를 보존한다.

[사전 기준](../../perception-readback-v1-protocol.md)의180/900/30s 예산을 지켰고
모든 서버 exit130, 강제 종료0, 시작 복구0이다. 실패한 client도 원본100장과 전체 판정을
보존했다. Source565개를 그대로 포함한574개를 고정했고 raw400개/6,871,859,200B는
[7개 LFS archive](raw-archives.json)에 있다. 미래 제외는7413개다.

[validation.json](validation.json)은 fresh archive의 원래 clock/원래 두 기한/상태 age,
실패 원인, 전체 wall 통계, 모든 raw BGRA/RGB 및 native/Pillow exact tensor를 검증한다.
무결성 PASS가 deferred-02의 실행 FAIL을 뒤집지 않는다. [audit-outcome.py](audit-outcome.py)는
유일한 실패 기준을 명시적으로 유지한 채 후속 invariant도 검사한다. [변조 검사](report-mutation-check.json)는
성공/실패 보고서와 GPU trace의64개 변조를 모두 거절했다. Python 최종345개와 C++/boundary
12개씩 Debug/Release/ASan을 통과했다. 입력·품질·주행·wall20Hz·Jetson 수용은 별도다.

재감사:

```sh
OMP_WAIT_POLICY=PASSIVE build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_readback_v1/check-evidence.py \
  docs/test-plan/evidence/m10_readback_v1 /tmp/readback-audit-new.json
```
