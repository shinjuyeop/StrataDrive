# M10 GC recovery V3 — 감사기 독립 실행 수정

[V2](../m10_gc_recovery_v2/README.md)의 첫30초 물리 검사는 통과했지만 추가 감사기의
Python import 경로 오류로 원래 sequence는 실패했다. 후속30초와5분은 실행되지 않았다.
수정한 검사기와 올바른 root 경로를 제공한 원래 동결 검사기는 실제6000개 기록에서 같은
결과를 냈다. 실패 기록과 원본281장·미래 품질 제외34522개는 그대로 보존한다.

이 후보는 감사기가 자신의 저장소 root를 import 경로에 추가하도록 수정한다.
판정 로직·실제 runtime·모델 준비·라이브러리 읽기·모듈·CPU 배치·기한은 동일하다.
[동등성 검사](code-equivalence.json)는 기존1272개 소스의 불변과 감사기 bootstrap만의
변경, 새 subprocess 회귀검사2개와 launcher 대상 변경을 확인한다.

Python539개·동결127개 검사를 통과했고, 추가 감사기8개를 저장소 밖·PYTHONPATH 없는
별도 프로세스에서 실행했다. 누락된 입력에서도 결과 파일에 FAIL을 남기는 경로를 검사한다.
[실행 연결 검사](runner-wiring.json), [준비](prepared.json), [최종 검사](readiness-validation.json).
C++29개·빈 renderer·실제 모델 양쪽 준비 경로 검증은 동일 코드·모듈·argv 확인 후 재사용했다.
새 live 실행 증거로 세지 않는다. 실제 launcher는 매번 자산 준비를 다시 수행한다.
새 동결본의 감사기8개를 보존한 실제6000개 기록에 독립 실행한 결과도 모두 기존 결과와
일치했다. [동결 CLI의 실제 기록 검사](retained-case-audits-01/validation.json).

1625파일 동결 SHA256은 `db505ed53ac956217864c5b4dcfbe277389d245bca61e043d3cdf3022195fa88`이다.
동일 모듈 SHA256은 `1feab7bc7a1c6788ec50fa507226ac01c99393d7b420912bba2e3cc1411a8eff`다.
**본시험은 NOT STARTED**다. [사전 프로토콜](../../perception-gc-recovery-v3-protocol.md).

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

자산 준비 뒤 sudo 인증하고 APPLIED를 확인한다.70%에서30초→30초→5분을 검사하며 첫
원래 판정 실패에 후속 실행을 중단한다. 실행기 종료·Ctrl+C·최대30분 뒤100%로 복원한다.
물리5ms·native2/4ms·HV30ms·원래 source 시각·held 만료 우선·최종 물리 검사는 유지한다.
추가 admission preview300us, owner3/image3/native1/관측1코어·SMT 분리, 병렬GC61.1초,
증분 정리100us,2560×1536 D-FINE-M960 CUDA·카메라 목표10Hz·renderer20Hz/MaxFPS60이다.

5분 GC 회복·전체 장면·native 인지 수용·독립 품질·각 Jetson 배포·M10 종료는 OPEN이다.
동결본 원본은 보존하며 검증된 추출본만 [정리](preparation-storage.json)한다.
[최종 체크섬](SHA256SUMS).
