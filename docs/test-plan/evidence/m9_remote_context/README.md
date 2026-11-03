# M9 원격 publisher의 trusted context admission component

2026-11-03, base `1b2626c` + [source overlay](sources/). 실제 native process 간 context 전송
배선에 앞서 admission/store 경계를 구현했다. **M9/TBD-08·native 3-ECU 전송 수용은 OPEN**이다.

`ContextualOutbox`는 trusted Central의 원본 Session과 실제 receiver gate가 수용한 RunLease
snapshot을 대조한다. Local Ready/7개 Release ACK는 global Session을 만들지 않는다.
실제 SessionCoordinator/8개 SessionParticipant/StartupDiagnostics/RunLeaseIssuer와 canonical
owner codec/RunLeaseGate를 사용한 결정적 component fixture다. Physical plant/native wall 차량
반응이나 SDK/IP 전송을 이번에 실행했다는 뜻은 아니다.

원격 endpoint의 snapshot accessor는 owner에서 값만 복사한다. Writer에서만 bounded32 대기와
FileJournal/Outbox를 사용한다. 원래 clock·Session/Event ID·epoch/enable·completion/mask를
보존하고 context→local event 순서로 durable commit한다. `submit` Accepted는 volatile 수집
성공이며 durable ACK가 아니다. 실제 committed prefix만 전송할 수 있다.

지연 context는 만료된 credit의 과거 고장을 기록하지만 gate를 갱신하지 않는다. Context 전에
Proof/Passed를 대기시켜 소급 수용하지 않는다. 잘못된 issuer/run/profile/clock/plan/full mask는
거부한다. Context 변조·queue/identity 손실·capacity/commit·enable 충돌은 incomplete이며
과거 미해결 event를 새 epoch로 건너뛰지 않는다. 대기를 남긴 정상 종료는 store를 invalidate한다.
Commit 전 메모리의 abrupt process loss·source 재시작 adoption/손실 조정은 후속이다.

두 source의 독립 stream101/102는 같은 Central 원본을 보존한다. 각각 Session1/Fault1,
병합은 **unique event3개/고장2개**다. 원격 ACK는 해당 stream/ordinal/event CRC에만 유효하다.
Receiver/Source 재개 시 Unknown은 동일 Session/fault 중복 replay로 바뀌지 않는다.
이 fixture의 고정 run10/producer20·30·31/clock99는 독립 시험 ID이며 production 할당 정책이 아니다.

## 실행과 검증

최종 일반 unit/logical **1185/1185**, 영향 ASan/UBSan **276/276**, 집중 **13/13**(두 빌드),
기존 M4AsyncWall **2/2**, source fingerprint **2/2**, BUILD_TESTING=OFF Release library가 통과했다.
집중13개는 기본/ASan 분모에도 포함되며 합산하지 않는다. Native Leaf endpoint의 실제
Ready/credit/expiry/INIT reset snapshot은 기존 통합 case에 assertion을 추가했다.
Clang-tidy warnings-as-errors·변경 header filter와 cppcheck warning/performance/portability는
production2개와 Zone endpoint header를 포함하는 test1개, 총3개 TU에 적용했다. Clang은 외부
header warning1개를 suppress했으며 사용자 source 진단은 없다. Cppcheck는 googletest library
설정을 명시했다. 새 코드는 single writer이고 기존 SPSC 구현은 바꾸지 않아 TSan은 새로 실행하지 않았다.

[normal](normal/)·[asan](asan/)의4개 journal과 원본 Event3개를 독립 Python parser로 대조했다.
두 profile의 원본·manifest/commit/journal **15개 artifact가 byte 동일**하다. 각 감사는 원본
변조2개·replica journal 손상·유효 CRC를 다시 계산한 잘못된 stream 등4개 변조를 거부했다.
이는 실제 네트워크/인증 증거가 아니라 canonical store/context의 독립 검증이다.

[results.json](results.json)은 분모/감사, [manifest.json](manifest.json)은 base·source fingerprint·
source/binary/config/tool hash, `logs/`는 최초 실패·중간 실행·최종 실행을 보존한다.
이전 M9 evidence9묶음의 SHA43/153/135/203/183/186/217/306/654개도 전부 유지했다.

## 실패와 검토 이력

- 최초 GTest compile은 assertion macro의 중괄호 누락 warning-as-error로 실패했다.
  Public Outbox 우회를 없애고 wrapper를 추가할 때 `acknowledged` 누락으로 한 번 더 실패했다.
  각각 후보 source와 build log를 보존했다.
- 새 epoch fixture가 Running 상태에서 cancel 없이 begin을 요청해1개가 실패했다. 실제 기존
  session 계약대로 cancel/Abort 후 재기동하도록 fixture를 고쳤고 budget은 유지했다.
- Cppcheck의 최초3-TU 시도는 GTest macro를 해석하지 못했다. 설치된 googletest library 설정을
  명시해 해결했다. 기존 no-tests build는 재configure 전 새 target을 몰라 실패했으며 동일 설정으로
  재configure 후 Release library를 빌드했다.
- Diff review에서 미확인 context의 Proof/Passed 소급 수용을 차단하고13번째 검사를 추가했다.
  수정 전 source/1184·275 중간 로그를 최종1185·276과 구분해 보존했다.

## 재현

Base에 sources overlay를 적용한다. SDK는 이 component에 필요하지 않다. Output 경로는 새
경로여야 하며 환경변수를 지정하지 않은 기본 시험은 export를 남기지 않는다.

```sh
cmake -S . -B build/context -DCMAKE_BUILD_TYPE=Debug
cmake --build build/context --parallel 3
ctest --test-dir build/context -L '^(unit|integration.logical)$' --parallel 3 --output-on-failure
STRATADRIVE_CONTEXT_EVIDENCE="$PWD/build/context-export" build/context/remote_diagnostics_context_test
python3 -B tests/integration/diagnostics/audit_remote_context.py build/context-export --mutations
python3 -B docs/test-plan/evidence/m9_remote_context/verify-packaged.py
```

ASan은 기존 `STRATADRIVE_SANITIZERS=ON`과 manifest의 selector를 사용한다. Source snapshot은
실제 owner에서 복사한 값이어야 하며 CRC나 이 검사를 peer 인증으로 사용하지 않는다.
다음은 native Central/Front/Rear publisher에 실제 context 운반·다중 stream 수집을 배선하는 것이다.
Source 재시작 adoption·부하/보존 용량·정규 DDS·Clock/Target/CARLA matrix·학습자 수용은 OPEN이다.
