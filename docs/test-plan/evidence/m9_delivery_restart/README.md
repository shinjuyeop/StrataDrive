# M9 진단 전달 객체 재개와 durable prefix 복구

2026-11-03, base `72b35be` + [source overlay](sources/).
실제 native Central/Front/Rear의 원래 observer·SDK application을 유지하면서 non-RT 전달 객체와
journal을 다시 열고 원본 context/이력을 재개했다. 별도 process에서는3개 commit 경계의 실제
SIGKILL을 검증했다. **전체 ECU process 재기동의 producer adoption·commit 전 SPSC/pending
손실 조정·M9/TBD-08·native4ms/Target·학습자 수용은 OPEN**이다.

`ContextualOutbox::restore`는 마지막 원본 Central Session을 실제 endpoint의 accepted credit와
다시 대조한다. 빈 store/credit만으로 context를 만들지 않으며 만료 credit를 연장하지 않는다.
새 Outbox는 ACK watermark0/ordinal1부터 재전송한다. 중복 Session/fault는 현재 Unknown을
바꾸거나 count/generation을 늘리지 않는다. 새 Passed/clear는 발행하지 않는다.

`MergedCollector`는 명시된 독립 replica들과 하나의 merged Recorder를 관리한다. 기동 시
replica에만 committed된 prefix를 대조해 merged를 보충하고 projection을 Unknown으로 둔다.
Store ID/registry/event-only/incomplete 검사를 통과해야 한다. 동일 EventId의 다른 bytes와
merged 저장 실패는 원본을 보존하며 거부한다. ACK는 양쪽의 durable commit 뒤에만 만든다.

Native 기본5개와 Front/Rear source·Central collector·세 ECU 전달 객체 reopen4개가 고정 cohort다.
추가4개에는 command-loss와 최초 Fault ACK 유실을 함께 적용했다. Control owner/SDK는
연속이며 source별 context-admitted flag를 다시 대조한다. 무고장 peer의 `all` reopen은 실제
owner quiesce 뒤에 수행한다. FIFO8/pending32/retry100ms/drain2s·원래100ms 물리 oracle를
유지한다. 재개가 drain deadline을 연장하지 않는다. 이전 객체로 온 future ACK는 진행시키지
않고 stale counter에 남긴다. Writer CPU15/SCHED_OTHER0의 실제 배치와 원본 store를 보존했다.

최종 Normal9/9·ASan9/9, 단독 SDK TSan5/6이다. TSan `both-restart`는 고장 주입 전 normal
prerequisite에서 실패했고 Central 강제 cleanup도 실패 원본에 남아 있다. Race/SDK 경고가 없어도
PASS로 세지 않는다. Normal/ASan에서는 같은 사례가 통과했다. 기본 검사1206/1206(988 unit·
207 logical·2 transport·9 기존 wall), 영향 ASan296/296, 정적 분석3 TU와 Release library/fingerprint
검사가 통과했다. Process evidence capture만 보강한 뒤 Normal/ASan 해당 시험을 각각 재실행했다.

[results.json](results.json)은 실제 분모·모든 초기 실패·독립 감사 결과를 기록한다.
[manifest.json](manifest.json)은 source/binary/config/SDK/tool hash와 검증 범위를 묶는다.
Normal 기본 검사에는 unit/logical/transport와 기존 runtime.wall이 포함된다. Native4ms guard는
이번에 다시 실행하지 않았으며 이전 native 배선의0/6 실패를 계속 OPEN으로 둔다. 서로 다른
실행 범위를 합산해 wall/Target 수용으로 표시하지 않는다.

## 독립 판정과 실패

PCAP을 TCP stream으로 재조립해11개 진단 stream의 모든 Data/ACK·service/direction·ordinal/
CRC와 source/replica/merged 원본 bytes를 대조한다. 실제8-role Release ACK와9개 endpoint의
accepted RunLease를 원래 control TCP에 대조한다. Detector/deadline/root/Zone ACK·정상 선행
물리 표본·100ms 보호/정지 판정도 기존 기준을 유지한다. Central의 원인 미지 Observation은
원본대로 남긴다. 새 recovery/clear를 만들어 채우지 않는다.

Reopen checkpoint 전후의 prefix bytes가 동일하고 최종 이력에도 남아야 한다. Source는 실제
TCP에서 ordinal1을 다시 전송해야 한다. 복구 직후 record는 Unknown/count1/generation1/
uncleared다. Collector 재개 전의 key는 중복 replay 뒤에도 Unknown을 유지한다. 독립 auditor는
기존5/8개 변조에 restart bytes/condition 변조2개를 추가한다.

최초 probe4개는 process/physical 판정4/4, 당시 독립 auditor2/4였다. Collector/all 재개로 중복
packet이 늘었을 때 service 번호를 control 번호로 바꾼 packet1개가 기존 auditor에서 무시됐다.
진단 method는 진단 service에 속해야 한다는 검사를 추가했다. 실패 stderr/당시 auditor source를
남겼고 native probe source2개는 당시 plan의 SHA와 맞춰 보존했다. 초기 실패를 지우지 않는다.

첫 SDK TSan cohort는 ASan root 검사와 동시 실행 중2/6만 통과했다. 나머지는 선언한 고장 주입
전에 기존 normal prerequisite/owner protection 조건을 충족하지 못했다. TSan 경고와 SDK 오류는
없었지만 실패로 보존한다. ASan 종료 뒤 같은 source/binary/config로 별도 TSan cohort를 실행해
동시 검사 영향과 기능 결과를 구분한다. 실시간 안정성/부하 수용을 뜻하지 않는다.

별도 process 시험은 parent가 fsynced transaction을 확인한 뒤 source commit·replica-only
commit·merged reconcile의 child에 각각 SIGKILL을 보낸다. Destructor로 복구하지 않는다.
새 process의 exact bytes/두 store ACK·Unknown/count1 검사는 GoogleTest에 보존되고, 독립
Python parser는 export된 fresh/replica/merged journal과 canonical Data/ACK를 확인한다.
Component fixture의 단순 event는 native observer 실행과 별도 분모다.

## 재현

Base에 `sources/` overlay를 적용하고 기존 pinned SDK3.7.6 profile을 빌드한다.
각 cohort는 새 output directory에서 순서대로 실행한다. TSan은 다른 부하 시험과 분리한다.

```sh
cmake --build build/m5-someip-normal/project --target someip_front_adapter --parallel 3
python3 -B tests/integration/someip/native_diagnostics_run.py build/restart-normal --profile normal
python3 -B tests/integration/someip/native_diagnostics_run.py build/restart-asan --profile asan
python3 -B tests/integration/someip/native_diagnostics_run.py build/restart-tsan --profile tsan --fixed-layout --cases normal drop-ack source-restart rear-restart collector-restart both-restart
python3 -B docs/test-plan/evidence/m9_delivery_restart/verify-packaged.py
```

ASan/TSan binary도 각 profile에서 먼저 빌드한다. 실제 full ECU kill/rejoin을 검증하려면 원래
제어 epoch/rejoin 절차와 새로운 producer identity/sequence·commit 전 손실 조정부터 고정해야 한다.
현재 시험을 그 수용으로 올리지 않는다.
