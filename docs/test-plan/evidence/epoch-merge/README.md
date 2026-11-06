# 고정 송신원 집합의 세션 경계 병합

2026-11-06. 기준 commit `15d1af9` 이후 변경이다. [계약](../../../interfaces/epoch-retention.md)과
[ADR-0110](../../../archive/design-decisions.md#adr-0110)을 따른다. 고정 membership의
EpochMergedCollector·ContextualOutbox family 지원과 실제 SOME/IP 원본 전송을 검증했다.
현재 상태와 남은 작업은 [프로젝트 상태](../../../project-status.md)에 기록한다.

## 구현과 결과

Root에 stream 목록을 영속화하고 모든 순서 보장 stream의 원본 다음 Session/Attempt가
도착해야 이전 epoch를 닫는다. 대기 중에는 stream당 entry 한 개만 replica에 기록하고
merged commit 전 ACK를 주지 않는다. 재시작은 ordinal1부터 같은 장벽으로 재조정한다.
과거 prefix를 stream별로 한꺼번에 병합하거나 참여자를 timeout으로 제외하지 않는다.
Central context 배포는 merged ACK와 독립적이어야 한다.

새 component 시험12개는 지연 tail·목록 고정·12세션/서로 다른 threshold·Central Attempt와
실패 epoch·대기 한도·미기록 과거 event·원문 변조·다른 run·저장 실패·segment quota를 검사한다.
추가 ContextualOutbox 시험은 실제 SessionCoordinator/RunLeaseGate로 세 세션을 열고,
family 재개방 후 원본 Session과 누적 ordinal을 재전송한다.

실제 SOME/IP fixture는 기존 논리 native owner의 Central pause→보호→INIT2→복구에서
얻은 원본 Central/Front/Rear event를 고정한 뒤 독립 stream으로 전송한다. SDK는 pin된
vSomeIP3.7.6, 서로 다른 IP namespace의 source/collector 프로세스를 사용한다.
Front의 이전 epoch tail을 지연하고 새 epoch 경계의 ACK가 보류된 상태에서 collector를
SIGKILL한 뒤 같은 store로 재시작한다. 새 event나 global Session을 합성하지 않는다.

최종 source는2/6/7 entry, 병합은 중복된 원본 Session을 한 번씩만 세어11 entry다.
Source 세 family와 merged family 모두2 segment를 사용했다. 원본 Fault2건과 그 occurrence의
Passed2건, DTC count1/generation1/uncleared를 유지했다. 의도한 첫 collector 종료-9 이외
source/replacement/capture는0이고 강제 정리0, SDK rejected/dropped0이다.
진단 on/off의 물리2400 sample은 byte 동일하다. 독립 감사는 membership·원본/replica/merged·
지연 tail·이른 ACK·재전송 ACK·프로세스 종료를 확인하고 변조6종을 거절했다.

Debug 전체 회귀는 `runtime.wall`을 제외한 **1,538/1,538**, ASan/UBSan **99/99**,
Python **280/280**이다.
변경 C++4개 translation unit의 clang-tidy는 오류·경고0이다. 세부 sanitizer 결과와
binary/source hash는 [수용 기록](acceptance.json), [독립 감사](merge-audit.json)를 따른다.

## 실패 보존과 수정

`someip.tar.gz`에는 시도4개를 모두 보존한다.

- `someip`: 첫 kill marker 뒤 writer가 다음 replica transaction을 시작해 pending 상태에서
  종료됐다. 재개방은 incomplete로 차단됐다. 미완료 transaction을 자동 복구하지 않았다.
- `someip-frozen`: 영속 경계에서 writer IO를 멈춘 뒤 종료하도록 시험기를 고쳤다.
  최종 원본 전송은 끝났으나 TCP 재접속 중100ms 재시도가 누적되어 SDK queue8에서4건
  드롭됐다. 실패를 그대로 유지한다.
- `someip-backoff`, `someip-final`: 미확인 진단 packet의 retry를100→200→400→800→1000ms로
  backoff하고 Accepted ACK에 초기화했다. 두 실행은 드롭0으로 통과했다. SDK queue8,
  제어/보호 기한과 overflow 실패 규칙은 유지했다. 재시도 정책은 이 전용 fixture의 변경이다.

첫 GTest 빌드의 조건문 brace 경고도 validation archive에 보존했다. 최종 빌드/회귀/감사와
구분한다. 기존 SDK의 연결 종료/정리 로그도 삭제하거나 일반 오류 면제로 분류하지 않는다.

## 재현과 범위

```sh
cmake --build build/m1-angle --target diagnostics_delivery_test remote_diagnostics_context_test
build/m1-angle/diagnostics_delivery_test --gtest_filter='EpochMerge.*'
build/m1-angle/remote_diagnostics_context_test --gtest_filter='RemoteDiagnosticsContext.EpochFamily*'
cmake --build build/m5-someip-normal/project --target someip_epoch_merge_live
python3 tests/integration/someip/diagnostics_run.py build/new-merge-run --cases epoch-merge-restart
python3 tests/integration/diagnostics/audit_epoch_merge.py build/new-merge-run/epoch-merge-restart --output build/new-merge-audit.json --mutations
```

`sources.tar.gz`/`sources.json`은 변경 source snapshot과 hash, `validation.tar.gz`는 빌드·회귀·
sanitizer·정적 검사·초기 실패 log와 build 설정이다. `someip.tar.gz`는 원본 event, 모든 source/
replica/merged family, kill 이전 copy, SDK config/log/pcap, 물리 대조와 실행 결과다.
[SHA256SUMS](SHA256SUMS)에 파일별 hash를 남긴다.

이것은 고정 membership의 원본 전송 검증이다. 실제3-process 제어 런타임의 동적 producer
교체·이전 prefix 종료 증거와 Central spool/context 적용, CARLA 감독 제어의 복구 주행,
단일 epoch 무중단 회전·디스크 삭제 정책·wall/Target/전체 ODD 수용은 남아 있다.
기존 finite MergedCollector의 기본 런타임을 자동 전환하지 않았다.
