# M10 GC recovery preview V1 — 실제 비교 전 후보

[Owner3 V1](../m10_gc_owner3_v1/README.md)의5분 실패에서 GC 뒤 세 정상 프레임이
기존 wheel/actuator 시각을 상속했고 다음 갱신을 기다리다 HV30ms가 만료됐다.
이 후보는 **명시적 opt-in에서 추가 preview 여유만1ms→300us**로 바꾼다.
[사전 프로토콜](../../perception-gc-recovery-v1-protocol.md).

원래 최종 Admission class와 물리 직전 BeforeTick 검사, 물리5ms·HV30ms·native2/4ms·
센서 시각·기존 held 만료 우선 순서는 같다. 기본 경로의 여유도 그대로다.
[코드 동등성](code-equivalence.json)은 이 경계와 기존 native·엔진·모델의 동일성을 확인한다.
오류 전 정상11874구간의 최종 preview 검사→적용 최대251.494us를 고려해300us를
선택했지만, 미래 지연 상한이나 실제 회복 성공을 뜻하지 않는다.

Python529개·C++29개·동결본117개 검사를 통과했다. 원래 gate를 유지하는 실제 staging
회귀와 잘못된 flag/readback·CPU 중첩·짧은 물리 구간의 거절을 포함한다.
모듈은 `1feab7bc7a1c6788ec50fa507226ac01c99393d7b420912bba2e3cc1411a8eff`이며,
1592파일 동결본은 `b0056abdf8978ef0e127d8b7c8dc612a47129e4724d965e8d70e6eddc00982f6`다.
빈 renderer는304.618초에 준비됐고 정상 종료·공유6파일·부스트100% 복원을 확인했다.
[준비 결과](prepared.json), [최종 준비 검사](readiness-validation.json).
**본시험은 NOT STARTED**다.

예비250us 후보의 첫 빌드는300초 초과로 실패했으며 설치하지 않았다. 원본과 로그를
보존했다. 최종300us 모듈은 제어·서버 종료 후 소유한 offline archive reader만
약81초 멈춘 상태에서 별도 빌드했고 reader를 복구했다.
[빌드 시도](build-attempts.json). 실패한 빌드를 성공 근거로 재사용하지 않는다.

물리 owner3코어 / 렌더러·영상3코어 / native1 / 관측1의 SMT 분리 배치와
GC61.1초·12220프레임·증분 정리100us 요청을 유지한다. 카메라2560×1536·
D-FINE-M960 CUDA·목표10Hz·renderer20Hz/MaxFPS60·CV/resize4도 같다.

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

자산 준비 뒤 sudo 인증하고 APPLIED를 확인한다.70% 조건에서30초→30초→5분을
검사하며 첫 실패에 후속 실행을 중단한다. owner 종료·Ctrl+C·최대30분 뒤 원래100%로
복원한다.70%는 임시 시험 조건이다. 원본 보존·미래 품질 제외34241개를 유지한다.
5분 안정성·native 인지 수용·전체 장면·독립 품질·각 Jetson 배포·M10 종료는 OPEN이다.

최종 실행 경로 검토에서 이전 판정 이름·동결본 감사 도구 참조를 수정했다. 첫 준비 동결본은
[교체 이력](preparations/freeze-01-superseded/superseded.json)에 보존했고, 실제 실행 전제와
8개 재감사 경로의 일치를 [확인](runner-wiring.json)한 뒤 다시 동결·117개 검사를 통과했다.
모듈·529개 회귀·29개 C++ 검사와 빈 renderer 검증은 동일한 코드의 근거를 재사용한다.

검사 후 두 동결본의 중복 추출과 실패 빌드의 동일한 원본 모듈 복사본만 해시 확인 후
삭제했다. [최종 추출 정리](preparation-storage.json), [실패 빌드 정리](failed-build-storage.json).
소스 archive·실패 당시 코드·원본 모듈의 보존 위치는 각 기록에 남겼다.
