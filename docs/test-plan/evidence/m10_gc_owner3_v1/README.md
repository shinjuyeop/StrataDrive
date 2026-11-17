# M10 GC owner 3코어 V1 — 실제 비교 전 후보

[분할 정리 V1](../m10_purge_slice_v1/README.md)은 정리 작업을 최장0.153ms로 나눴지만
5분 시험의60.226초 HV 만료를 해결하지 못했다. 첫 본 GC19.108ms가 시작할 때
held HV 입력의 의존 나이가 이미10.019ms였다. GC가 끝난 뒤 남은 만료 여유는0.873ms였다.
계산·시각·만료 기준은 유지하고 본 GC 시간을 줄일 CPU 배치를 비교한다.
[사전 프로토콜](../../perception-gc-owner3-v1-protocol.md).

| 역할 | 이전 물리 코어 | 후보 물리 코어 | 후보 논리 CPU |
|---|---:|---:|---|
| 물리 owner | 2 | 3 | 2,3,4,10,11,12 |
| native | 1 | 1 | 1,9 |
| 렌더러·영상 | 4 | 3 | 5,6,7,13,14,15 |
| 관측 | 1 | 1 | 0,8 |

SMT 형제도 역할 간 겹치지 않는다. 정상 구간에서 렌더러·영상의 평균 사용량은 약1.90코어였지만,
순간 지연 여유를 보장하지 않으므로 영상 지연·실제 카메라 Hz도 함께 비교한다.
소유한 프로세스의 affinity만 바꾸며 다른 프로세스·IRQ·scheduler 정책·Jetson 설정은 바꾸지 않는다.

모듈 `0520f2a91d3e918510e6f4631d869205bff524f1724adf8d395f8e1647a0066f`,
native·모델·resize·엔진은 재사용한다. 분할 정리100us 요청·structured 추가 여유1ms·
원래 최종5ms 물리·HV30ms·native2/4ms·센서 시각·held 만료 우선 순서와 GC61.1초를 유지한다.
GC4회·정리 완료·12220프레임 주기, 실제 owner/renderer/observer/native/pipeline 마스크와
정책을 검사한다. 기존2코어 검사는 여전히 CPU4의 GC 관측을 거절한다.
[동등성](code-equivalence.json), [CPU 배치 확인](cpu-plan-validation.json).

Python526개·동결본114개 검사를 통과했고 동일 C++28개 근거를 재사용한다.
새3코어 빈 renderer는305.75초에 준비됐으며 종료·공유6파일 복원을 확인했다.
1576개 파일의 동결본 SHA256은 `d18e60eeedf97c4da2aae471ecfd48ede027d4a889e77673d315621213965cc4`이다.
[준비 결과](prepared.json), [최종 준비 검증](readiness-validation.json).
**본시험은 NOT STARTED**이며 개선·안정성 수용을 뜻하지 않는다.

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

시작 도구는 이 후보를 선택한다. 자산 준비 후 sudo 인증하고 APPLIED를 확인한다.
70% 조건에서30초→30초→5분을 검사하며 첫 실패에 후속 실행을 중단한다.
owner 종료·Ctrl+C·최대30분 뒤 원래100%로 복원한다. 새 PID와 원래 helper를 사용하며
비밀번호를 저장하지 않는다. 기존2K2560×1536·D-FINE-M960 CUDA·목표 카메라10Hz·
renderer20Hz/MaxFPS60·CV/resize4 threads·기동/종료/원본 보존 기준은 유지한다.

분할 정리 V1의 native150만슬롯 누락·지연0은 한 번의 관측이다. 이전18슬롯 누락의
지속적 해결이나91°C에서의 냉각 여유는 확정하지 않는다. 연속 주행·전체 장면·독립 품질·
native 인지 수용·각 Jetson 배포·M10 종료는 OPEN이다.
