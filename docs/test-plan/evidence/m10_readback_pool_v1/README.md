# M10 4K render-target 재할당 후속

4K 영상의 반복 버퍼 재할당을 없앤 조건에서 실제 카메라는 **15.63Hz**였다.
기준11.25–11.38Hz보다 약37–39% 높지만, 유효 인식 조회는16.10%로 낮아졌다.
비동기 readback까지 결합한 조건은13.71Hz/유효 조회0%로 **FAIL**이다.
**영상 속도 개선과 전체 인식 경로 수용은 다르며, 기본 실행 설정을 바꾸지 않는다.**

| 조건 | world wall Hz | camera wall Hz | simulation/wall | 유효 조회 | 발행/추론 | 소비 frame | 판정 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pool-baseline-01 | 77.604 | 15.631 | 0.7760 | 52/323 (16.10%) | 97/100 | 53 | PASS |
| pool-deferred-01 | 68.166 | 13.706 | 0.6817 | 0/367 (0.00%) | 0/99 | 0 | **FAIL** |

둘 다 같은 계측 바이너리·3840×2304 BGRA·Epic·D-FINE-M960 FP32·threshold·개발 fixture다.
[사전 기준](../../perception-readback-pool-v1-protocol.md)에 따라 다음 두 console 설정만 추가했고,
실제 값이 각각2/1임을 로그에서 검사했다:

- `r.SceneRenderTargetResizeMethod=2`
- `r.SceneRenderTargetResizeMethodForceOverride=1`

엔진이 요청된 최대 크기의 렌더링 버퍼를 유지하므로 메모리 사용과 재할당의 trade-off다.
Camera output 해상도를 줄이지 않았다. 원래 조건은 첫/마지막 readback 완료 사이에
재할당 로그398–400줄(엔진 중복 출력 포함), 후속 두 조건은0줄이다.
GPU 메모리 peak·장기 안정성·영상 품질 동등성·Jetson 적합성을 측정했다고 주장하지 않는다.

Pool-baseline의 capture→SDK callback 평균은52.55ms로 기준 약71ms보다 짧았다.
하지만 SDK callback 작업 평균15.92ms와 receipt→backend return 평균61.96ms가 더 필요하다.
Source clock이 더 빠르게 진행하면서 consumer가 읽을 때 남은 유효시간은 짧아졌다.
원래 acquisition+100ms와 원래 offer receipt+100ms는 둘 다 유지했다. 유효조회16.10%는
50Hz 관측 표본 비율이며 연속 가용시간이나 정확도 수치가 아니다.

Pool-deferred는 capture→callback70.04ms, receipt→backend return115.39ms, late99개다.
입력100개 중1개는 상태 초기화 전에 도착해 거절됐다. 다섯 source 구간 소비 수는
pool-baseline [12,9,9,14,9], pool-deferred [0,0,0,0,0]이다. 재시도·시각 갱신·기한 연장 없이
이 실패를 유지한다. 각 실행 GPU capture101개/수신 raw100개, stop 뒤 경계 capture1개 미수신,
primary 예정 frame 누락0이며 종료130/강제 종료0/시작 복구0이다.

다음 성능 작업은 **4K GPU→SDK 전달·raw materialization·CPU 전처리·추론 대기열의
전체 capture-to-result 지연 단축**이다. 렌더링 FPS만 높이거나 유효기간을 늘려 성공으로
만들지 않는다. 반복 검증, 실제시간1×/wall20Hz, unavailable의 기존 보호 경로 연결,
새 독립 품질 평가와 각 Jetson 배포는 남아 있다. 보드 최적화는 후속 원칙을 유지한다.
느린 시뮬레이션을 목표로 합의한 것이 아니라 현재 실시간 성능이 부족한 상태다.

이전 source574개를 포함한580개, raw200개/3,436,042,240B의[4개 LFS archive](raw-archives.json),
누적 미래 제외7613개를 보존했다. [fresh-source 검증](validation.json)은 성공/실패 의미와
모든 원본·BGRA/RGB hash·native/Pillow exact 입력을 재생한다. 무결성 PASS는 실행 FAIL이나
전체 실시간 미수용을 바꾸지 않는다. Python345개·[변조32건 거절](report-mutation-check.json),
이전 묶음의 C++ Debug/Release/ASan12개씩·변조64건을 포함한다.

재감사:

```sh
OMP_WAIT_POLICY=PASSIVE build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_readback_pool_v1/check-evidence.py \
  docs/test-plan/evidence/m10_readback_pool_v1 /tmp/readback-pool-audit-new.json
```
