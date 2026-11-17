# M10 GC recovery V2 — 라이브러리 시작 읽기 후보

[V1](../m10_gc_recovery_v1/README.md)은 첫 모델 준비10초 제한을 초과해 제어 시작 전에
실패했다. 이 후보는 **같은300us 모듈**을 유지하며 명시적 opt-in으로 CUDA/cuBLAS/cuDNN
12파일·1,909,074,752byte를 모델 생성 전에 순차 읽고 해시 확인한다.
[사전 프로토콜](../../perception-gc-recovery-v2-protocol.md).

추론·카메라·제어 호출은 추가하지 않는다. 라이브러리 파일·버전·loader와 모델 계산은 같다.
별도 읽기30초 제한이나 해시 검증에 실패하면 모델을 시작하지 않는다. 읽기 시간은 모두
기록하고 원래3회 준비·총10초·후속 호출100ms·renderer30초 기준은 유지한다.
읽기는 페이지를 고정하지 않으므로 이후 메모리 압박에서도 항상 빠르다고 보장하지 않는다.

[실제 두 준비 경로](model-paths-01/validation.json)는100%·CARLA 없는 조건에서 통과했다.
owner 읽기1.179초 뒤357.670 /33.515 /33.725ms, renderer 읽기1.162초 뒤
115.714 /34.277 /35.109ms였다. 이 실행은 캐시가 준비된 상태의 코드 연결 검증이다.
별도 차가운 복사본의11.921초 읽기 비교는 V1 진단에 보존하며 실제70% 시험을 대신하지 않는다.

Python537개·동결본125개를 통과했다. 내용 변경·경로 이탈·시간 초과·잘못된 flag·
누락된 양쪽 읽기 기록을 거절하는 검사를 포함한다. 원래 C++29개와 빈 renderer 기동·종료
검증은 동일한 테스트 코드·모듈·argv의 근거를 재사용했고 새 native 모듈은 빌드하지 않았다.
[동등성](code-equivalence.json), [준비](prepared.json), [최종 검사](readiness-validation.json).
1611파일의 동결본 SHA256은 `388000a8b327746e3edca541df3c561a2c737fcd5f452580ea2428b54b1b9174`이다.
동일 모듈 SHA256은 `1feab7bc7a1c6788ec50fa507226ac01c99393d7b420912bba2e3cc1411a8eff`다.
**본시험은 NOT STARTED**다.

물리5ms·HV30ms·native2/4ms·원래 source 시각·held 만료 우선 순서와 최종 물리 검사는 같다.
owner3/image3/native1/관측1코어·SMT 분리, 병렬 GC61.1초·12220프레임·증분 정리100us,
2560×1536·D-FINE-M960 CUDA·목표 카메라10Hz·renderer20Hz/MaxFPS60·CV/resize4를 유지한다.

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

자산 준비 후 sudo 인증하고 APPLIED를 확인한다.70% 조건에서30초→30초→5분을 검사하며
첫 실패에 후속 실행을 중단한다. 실행기 종료·Ctrl+C·최대30분 뒤100%로 복원한다.
미래 품질 제외34241개와 모든 실패 원본을 보존한다.5분 안정성·전체 장면·native 인지 수용·
독립 품질·각 Jetson 배포·M10 종료는 OPEN이다. 긴 backend 정지 시 worker 종료가 실패한
V1 현상도 해결된 것으로 세지 않는다.

동결본 검증 후 동일한 추출본만 삭제했다. 원본 소스 archive와 재사용 모듈은 보존한다.
[추출본 정리](preparation-storage.json), [최종 체크섬](SHA256SUMS).
