# M10 Purge slice V1 — 실제 시험 전 후보

[병렬 GC V1](../m10_parallel_gc_v1/README.md)의 5분 실패를 보존한 후속 후보다.
병렬 GC는21.21ms로 짧아졌지만 다음 갱신 전2.565ms CPU 작업 때문에 HV30ms를
넘었다. 원래 입력으로 정확히 재생했으며 추가 여유를0으로만 줄여도 해당 pump는 늦다.
엔진 기본 증분 정리2ms와의 관계를 새 직접 계측으로 확인한다.
[사전 프로토콜](../../perception-purge-slice-v1-protocol.md).

시험 옵션 `--owner-purge-slice`에서만 GC 뒤 남은 정리를 엔진 프레임당0.1ms씩
요청한다. 실제 wall/thread CPU·최장 구간·호출 횟수·완료를22,048바이트 POD에
기록한다. 같은 프레임에 기본2ms 작업을 중복하지 않으며, pending 작업이 없으면
스케줄을 건드리지 않는다. 전체/강제 GC 분기와61.1초 주기는 그대로다. 0.1ms는
요청 예산이며 실제 상한을 보장하지 않는다. 5분에서4회 정리가 모두 끝나고 원래
12220프레임 GC 간격을 유지해야 무결성 검사가 통과한다.

이 옵션에서만 structured preview 추가 여유를2→1ms로 바꾼다. 기존 structured2ms·
text4ms 기본값, 원래 최종 admission·전체5ms 물리·HV30ms·native2/4ms·센서 시각·
이전 held 만료 우선 검사는 유지한다. native/plant287개 파일과 최종 허용·물리 코드를
대조했다. [동등성 검사](code-equivalence.json).

새 모듈 SHA256은 `0520f2a91d3e918510e6f4631d869205bff524f1724adf8d395f8e1647a0066f`다.
Python522개·native admission28개 검사 통과. 새 모듈의 빈 서버 검증과 동결본110개
검사·runtime 복원은 [준비 결과](prepared.json), [최종 준비 검증](readiness-validation.json)에
기록했다. 새 빈 서버 준비는473.68초에 완료됐고 정상 종료·공유6파일·100% 복원을 확인했다.
소스1560개를 동결했고 검증한 추출 중복만 제거했으며 원본 archive는 보존했다. **실제70% 조건의30초→30초→5분은 NOT STARTED**이며 해결·수용을 뜻하지 않는다.

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

시작 도구는 이 후보를 선택한다. 실행마다 자산을 준비하고 sudo 인증 후 새 PID로
70% 임시 상한을 적용한다. `APPLIED`가 실제 적용 표시다. 첫 실패 후 후속 실행을
중단하며, owner 종료·Ctrl+C·최대30분 뒤100%로 복원한다. 비밀번호는 sudo가 직접
받으며 저장하지 않는다. 기존70% 조건·CPU/FIFO 배치·2K2560×1536·D-FINE-M960 CUDA·
카메라10Hz·renderer20Hz/MaxFPS60·준비600초·기동180초·종료30초는 유지한다.

이전 시험 후반 native18슬롯 누락은 별도 미해결이다. 새 후보도 native 누락0과
원래 물리 기준을 만족해야 한다. 품질 제외27550개에서 이어가고 모든 원본·실패를
보존한다. 연속 주행·전체 장면·독립 품질·native 인지 수용·각 Jetson 배포·M10은 OPEN이다.
