# M9 Front/Rear ECU 재기동과 진단 발행자 세대

2026-11-03, base `b6f79a2` + [source overlay](sources/).
실제 native3-ECU의 Front 또는 Rear **전체 ECU/SDK process**를 SIGKILL한 뒤 원래 명시적 rejoin과
새 Epoch2로 재합류했다. 전달 객체만 reopen하는 이전 시험과 구분한다. 생존 Central·다른 Zone·
plant는 계속 실행한다. **Central 자체 process 재기동·host 전원/clock 변경·임의 반복 재시작 용량·
연속성 reconciliation/clear·native4ms/Target·TBD-08·M9/학습자 수용은 OPEN**이다.

Private `ProducerLifecycle` journal9101/9102는 lifetime flock·explicit bootstrap·canonical start/
close history와 fsynced generation commit을 사용한다. 발행자 ID는
`((generation-1)<<32)|logical_source`이며 첫 세대의 기존20–33을 유지한다. 새 ID는 순번1에서
시작하고 원래 발행자의 순번을 재사용하지 않는다. Private lifecycle epoch는 process 세대다.
실제 global Session은 원래 Central/EpochStore/8-role handshake가 발급한다.

Destructor는 clean-close하지 않는다. 실제 owner 생산 종료·queue/pending·durable ACK drain 뒤
명시적 close만 기록한다. Unclosed 이전 start는 previous_unclean이다. 저장 전 이벤트 손실은
확인할 수 없으므로 새 source의 sequence1로 SD-5001/monitor10/native_reason1의 연속성 미확인
incident를 남긴다. Detected는 원래 새 process boot 시각이다. Cause_unknown/unmapped로 clear를
막고 손실 event 개수·원인을 만들어 넣지 않는다. Incident count1은 잃은 event 수가 아니다.
원래 observer는 sequence2부터 시작한다. 새 process/INIT/정상만으로 기존 고장을 Passed로
만들지 않는다. 연속인 source의 원래 proof에 의한 새 Epoch recovery와 구분한다.

두 세대의18개 source/replica와2개 context stream을 명시적으로 provision한다. Fixture는 두 process
세대까지만 실행하며 임의 반복 재시작 수용을 주장하지 않는다. 대상이 아닌 ECU의 두 번째 source
store는 비어 있다. 새 process는 `CommittedReplay`로 이전 검증 prefix를 그대로 재전송한다.
Uncommitted suffix/incomplete는 지우지 않고 완전성을 별도 보고한다. 일반 Outbox의 incomplete
차단은 유지한다. 원격 ACK는 원래 replica/merged commit 뒤이며 global context는 원래 ordinal1/2다.
Control/진단 FIFO8·pending32·retry100ms·drain2s·모든 제어/물리 예산을 유지한다.

## 판정과 독립 근거

| 검사 | 결과 / 범위 |
| --- | --- |
| 최종 native Normal | 11/11 |
| 최종 native ASan/UBSan | 11/11 |
| 최종 SDK-instrumented TSan | 3/4; Rear process rejoin은 새 Session의 제어 정상 구간에서 보호 선택으로 실패 |
| 최종 독립 raw 감사 | 통과25 dataset; 변조212개 거부; TSan 실패1개는 미통과로 보존 |
| unit/logical/transport | 1202/1202 |
| 기존 runtime.wall | 최초8/9; physical guard 미통과 후 동일 기준 단독1/1; 원래 실패 분모 보존 |
| 영향 ASan/UBSan | 301/301; 포함 wall8개와 transport3개를 합산하지 않음 |
| volatile queue SIGKILL | Normal1/ASan1; 실제 저장 전 fault는 복원되지 않으며 새 marker만 기록 |
| 정적/Release/fingerprint | clang-tidy/cppcheck6 TU·Release libraries·fingerprint2개 통과 |

TSan Rear 재합류도 진단 store·재전송·ACK는 완료됐지만 정상 정지/새 Leaf renewal을 충족하지
못해 전체 runtime 판정은 실패다. Sanitizer/SDK 경고는 없었다. 이전의 제어/wall 안정성 OPEN을
유지하며 진단 부분 성공을 전체 성공으로 올리지 않는다.

[results.json](results.json)에 초기/최종 분모·실패·감사와 모든 실행을 구분한다.
[manifest.json](manifest.json)은 source/binary/config/SDK/tool hash·분모를 묶는다.
최종 native Normal/ASan은 기존9개와 Front/Rear process rejoin2개다. TSan은 normal/drop-ack와
두 process rejoin의 유한4개 cohort이며 SDK instrumentation을 확인한다. Native4ms guard는
이번에 재실행하지 않았고 이전0/6 실패의 OPEN 상태를 유지한다.

독립 Python parser가 원본 manifest/commit/frame CRC·suffix를 읽고 실제 PCAP TCP를 재조립한다.
두 Session마다 원래8개 Release ACK·총18개 actual endpoint credit를 control wire에 대조한다.
새 SDK client ID가 이전 세대의 ordinal1부터 재전송해야 하며 source/replica/merged는 원형 bytes와
EventId를 유지한다. Unused 세대는 빈 journal, source 순번은 해당 ID 안에서1부터 연속이다.
Private start/start/close와 survivor start/close, 원래 boot 시각, 새 세대별 marker4개(Front) 또는5개
(Rear)를 대조한다. 생존 ECU PID는 동일해야 한다. 원래100ms torque/brake 보호·새 Session의 정상
정지/HV-off를 검사한다. 발행자 재사용·marker 제거·boot 변조·credit·새 handshake·old replay·
물리·lifecycle·tail 보고의9개 변조를 거부한다. Mapped되지 않은 원인은 임의 root로 바꾸지 않는다.

별도 실제 process 시험은 lifecycle/Session을 commit한 뒤 SPSC에 원본 fault를 publish하고 writer
전에 SIGKILL한다. 새 발행자가 그 ID를 재사용하지 않고 별도 연속성 marker만 기록해야 한다.
사라진 fault는 어느 source journal에도 없어야 한다. Normal/ASan export는 독립 parser가 대조한다.
이 component event는 native actual observer 실행 분모와 합산하지 않는다.

## 실패와 한계

초기 Front/Rear control prototype은2/2, 독립 감사가 연결된4개 cohort도 통과했다. 강제 종료될
process의 credit/placement sidecar가 userspace buffer에 남지 않도록 원래 non-RT writer에서
flush했다. 이 파일 IO를 RT runnable에 넣지 않았다. 원본 journal의 commit 절차는 그대로다.

첫 전체 root 검사는1202개 unit/logical/transport가 통과하고 기존 wall9개 중 physical guard1개가
미통과였다. 실패 원본과 isolated 재확인을 별도 보존한다. 첫 native Normal11/11, ASan10/11이며
ASan Front rejoin은 진단 전달 완료 후 기존 제어가 정상 구간에서 보호를 선택해 실패했다.
실패를 sanitizer 경고 없음이나 성공 재실행으로 지우지 않는다. 제어/물리 한도를 바꾸지 않았다.

초기 clang-tidy14가 GCC13 headers를 선택해 C++20 chrono를 파싱하지 못했다. 실제 compiler인
GCC11 headers를 지정한 뒤 plant의 기존 M6 환경설정이 누락될 때 null을 stod에 전달하는 경로도
검출했다. 필수 두 설정을 확인한 뒤 파싱하도록 고쳤다. 정상 값/튜닝/물리 oracle는 유지한다.
최종6 TU(새 lifecycle/delivery/owner/native/배선/front adapter)의 clang-tidy/cppcheck, Release library,
source fingerprint를 검사하며 초기 분석 실패 로그도 남긴다.

## 재현

Base에 `sources/` overlay를 적용하고 pinned SDK3.7.6의 해당 normal/asan/tsan profile을 빌드한다.
각 cohort는 새 output path에서 순서대로 실행하고 TSan/wall은 다른 검사와 분리한다.

```sh
cmake --build build/m5-someip-normal/project --target someip_front_adapter --parallel 3
python3 -B tests/integration/someip/native_diagnostics_run.py build/adoption-normal --profile normal
python3 -B tests/integration/someip/native_diagnostics_run.py build/adoption-asan --profile asan
python3 -B tests/integration/someip/native_diagnostics_run.py build/adoption-tsan --profile tsan --fixed-layout --cases normal drop-ack front-process-rejoin rear-process-rejoin
python3 -B docs/test-plan/evidence/m9_producer_adoption/verify-packaged.py
```

같은 kernel monotonic clock instance의 Front/Rear fault/rejoin fixture이며 Central failover·host
power-cycle·30km/h CARLA fault matrix·연속성 reconciliation/clear·실제 부하/용량 수용은 별도다.
