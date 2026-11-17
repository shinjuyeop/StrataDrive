# M10 GC owner4 V1 — 물리4 / 영상2코어 비교 준비

[Recovery V3](../m10_gc_recovery_v3/README.md)는30초 두 번을 통과했지만,5분 시험에서
GC 뒤 기존 입력을 계속 상속하다60.242초에 HV 입력이 만료됐다. 당시 실제 다음 갱신
시각의 재생에서는 추가 preview300us와0 모두 wheel 기한으로 거절됐다.
이 후보는 영상 쪽 물리 코어 하나와 SMT sibling을 owner로 옮겨 GC 지연을 비교한다.
**70% 물리 본시험은 NOT STARTED**다. [사전 프로토콜](../../perception-gc-owner4-v1-protocol.md).

| 역할 | 논리 CPU | 물리 코어 수 |
| --- | --- | --- |
| 물리 owner | 2,3,4,5,10,11,12,13 | 4 |
| 렌더러·영상 공유 | 6,7,14,15 | 2 |
| native ECU | 1,9 | 1 |
| 관측·실행기 | 0,8 | 1 |

SMT sibling을 같은 역할에 두고 역할 간 중첩을 금지한다. Native FIFO18, 나머지SCHED_OTHER,
실제 runtime·모듈·native binary·모델·라이브러리·CV/resize4를 유지한다.
기존1271개 소스와 엔진·모듈 입력의 동일성을 검사했고 변경한 기존5개 파일은 CPU 배치
감사와 launcher/test 대상에 한정된다. [동등성](code-equivalence.json) ·
[실제 Host topology](cpu-plan-validation.json).

Python545개·동결133개 검사를 통과했다. C++29개는 동일 소스·모듈·입력을 확인해 재사용한다.
추가 감사기8개를 저장소 밖·PYTHONPATH 없는 독립 프로세스로 실행했다.
새 동결 감사기로 V3 실제6000개 기록의 기존3코어 감사 결과가 동일함을 확인하고,
새4코어 감사기는 그 기록을 의도대로 거절한다. 이전 기록을 새 배치의 물리 수용으로 세지 않는다.
[연결 검사](runner-wiring.json) · [기존 기록 회귀](prior-case-audits-01/validation.json) ·
[준비](prepared.json) · [최종 검사](readiness-validation.json).

100% 조건에서 양쪽 실제 모델 준비를 영상 CPU6,7,14,15에 배치했다. 고정 라이브러리 읽기는
owner 경로1.223초·renderer1.207초였고, 원래3회 준비는 각각2428.950 /38.152 /36.346ms와
118.393 /36.825 /36.985ms였다. 원래10초·후속100ms 기준, worker 종료와 오류 없음도 확인했다.
[실제 모델 경로](model-paths-01/validation.json). 준비 성공은70% 물리 안정성의 증거가 아니다.

같은2코어 빈 renderer는530.733초에 준비돼 별도600초 준비 기준과 종료·복원을 통과했다.
이때 이전 시험의 raw 압축 후처리가 겹쳤다. 해당 압축만 낮은 우선순위로 조정한 뒤
최대180초 자동 재개 조건으로38.043초 일시 대기시켰으며 실제 재개를 확인했다.
[준비 I/O 조건](preparation-io-context.json) · [자동 재개](compaction-pause.json).
따라서 이 시간은 무부하 startup 비교가 아니다. 물리 시험 서버의180초 준비 기한은 그대로다.
실제 launcher는 매번 자산을 다시 준비한다.

물리5ms·native2/4ms·HV30ms·원래 시각·held 만료 우선·최종 gate·추가 preview300us,
GC61.1초/12220프레임·증분 정리100us 요청,2560×1536·D-FINE-M960 CUDA·목표10Hz·
renderer20Hz/MaxFPS60을 유지한다. GC 생략·강제 사전 실행·주기 연장·기한 완화는 없다.
Owner 병렬 여유 증가와 영상 쪽 경합 악화를 함께 측정해야 한다.

1644파일 source SHA256은 `a99706c90429502914648f98fd16c5616b4b09a522c6db91aeb4561d1d6c6ffc`,
재사용 모듈 SHA256은 `1feab7bc7a1c6788ec50fa507226ac01c99393d7b420912bba2e3cc1411a8eff`다.
원본 동결 archive를 보존하고 byte가 일치하는 검사 추출본만 [정리](preparation-storage.json)한다.
누적 미래 품질 제외37860개를 이어받는다. [체크섬](SHA256SUMS).

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

자산 준비 후 sudo 인증하고 APPLIED를 확인한다. 같은70%에서30초→30초→5분을 검사하며
첫 실패에 후속 실행을 중단한다. 실행기 종료·Ctrl+C·최대30분 뒤100%로 복원한다.
70%와4/2코어는 유한 Host 실험 조건이며 production 기본값이나 Jetson 최적화가 아니다.
5분 안정성·냉각 여유·연속 주행·전체 장면·native 인지 수용·독립 품질·각 Jetson 배포·
M10 종료는 OPEN이다. 후속 분석 추천은 GPT-6 Astra / xhigh다.
