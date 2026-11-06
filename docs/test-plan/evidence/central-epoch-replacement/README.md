# Central 교체와 진단 발행자 승계

2026-11-06. [계약](../../../interfaces/epoch-retention.md)과
[ADR-0112](../../../archive/design-decisions.md#adr-0112)을 따른다. 선택형 epoch 기록 경로에서
Central을 실제 SIGKILL한 뒤 새 발행자·새 INIT로 재가입하고, 기존 family와 원본 순번을 유지한다.
기본 finite 경로와 기존 milestone·wall/Target 판정을 바꾸지 않는다.

## 구현·검증 범위

- Central startup/observer의 publisher pair를 신뢰된 epoch lineage에 고정한다. 과거 원본은
  이전 pair로 검증하고 현재 writer는 자기 epoch에만 append한다. ID 재사용·교차 역할·
  잘못된 과거 Session·선행 epoch append를 거절한다.
- 새 Central은 lifecycle과 기존 family14개의 lifetime 독점 잠금을 얻고 이력을 검증한다.
  이 경계 뒤에만 새 spool 경계를 수락한다. Pending/incomplete를 자동 수리하거나 새 store로
  우회하지 않는다. 실제 운행 context는 별도의 새 INIT/Release/RunLease로만 수락한다.
- 살아 있는 Front/Rear의 PID·producer·sequence는 유지한다. 새 issuer를 수락한 source는
  ordinal1부터 재전송하고 새 Central은 이전 원문에 Duplicate ACK를 반환한다. 새 context의
  배포는 merged ACK 대기와 독립적이다. 이전 원격 tail이 새 checkpoint 뒤로 밀리지 않는다.
- Central의 volatile 유실 가능성은 continuity DTC1개로 남긴다. 원문 일치나 재가입으로
  자동 Passed/clear하지 않으며 잃은 event 개수를 추측하지 않는다.

실제 SOME/IP 실행은 ECU별 namespace와 독립 plant, CPU1/2/7 owner·plant3·비실시간 writer15의
기능 프로파일이다. SDK queue8·제어/보호 기한과 기존 오류 판정을 유지한다. 초기 정상 제어와
prefix receipt 이후에 SIGKILL을 주입하며, 임의 fsync 도중 중단의 자동 복구를 수용하지 않는다.

| 실행 | 판정 |
| --- | --- |
| `central-initial` | 통과. Central 교체·기존14개 family 보존·merged32개·continuity1개·독립 변조16개 거절 |
| `central-drop-ack` | **주입 검증 실패**. Runtime은 통과했지만 원격 Fault가 없어 ACK 생략이 실행되지 않았고 독립 감사가 거절 |
| `central-ack-retry` | 통과. 새 Session ACK1개를 실제 생략하고 동일 ordinal의 Duplicate 재전송 확인 |
| `front-regression` | 통과. 기존 Front 교체 경로 회귀·독립 감사 |

두 Central 정상 교체 실행의 옛 수집기 원본과 새 최종 prefix, 후속 SDK client의 context 재전송과
모든 surviving source ordinal의 ACK, 각 epoch의 실제 Release8개와 accepted RunLease18개를
독립적으로 비교한다. [실행별 판정](acceptance.json)과 [감사 결과](audits.json)에 분모를 보존한다.

## 발견한 문제와 수정

기존 `--diagnostic-drop-ack`는 원격 Fault만 대상으로 삼았다. Central crash에서는 원격 이벤트가
주로 보호 Observation이어서 최초 실행에 주입이 없었다. 이를 통과로 세지 않는다. Central 교체는
새 epoch2 Session의 ACK1개, Front/Rear 교체는 기존 Fault ACK를 대상으로 구분했다. Runner는
실제 생략이 없으면 실패하고 auditor는 생략한 같은 stream/ordinal의 후속 Duplicate를 요구한다.

초기 unit fixture는 이미 Session이 있는 동일 epoch에 다른 publisher Session을 추가하려다
원래 ledger에서 거절됐다. 잘못된 최초 Session을 가진 별도 family로 fixture를 수정해 spool의
history binding 거절을 검증했다. 초기 실패 log는 validation archive에 남긴다.

검증 결과는 Debug **1,553/1,553** (`runtime.wall` 제외), ASan/UBSan **114/114**
(delivery53·context40·epoch16·process5), Python **280/280**다. 변경 C++3개의 clang-tidy 진단은0개다.
새 unit5개와 실제 성공 실행3개를 포함하며, 미실행 ACK 주입1개를 성공 분모에 넣지 않는다.
기존 정상·Rear ACK-loss 증거의 재감사도 통과했다. 이 재감사를 새로운 차량 실행으로 세지 않는다.

## 재현·보관

```sh
cmake --build build/m1-angle --target diagnostics_delivery_test remote_diagnostics_context_test
cmake --build build/m5-someip-normal/project --target someip_front_adapter
python3 tests/integration/someip/front_run.py build/new-central-epochs --three --diagnostics --diagnostic-epochs --isolated-ecus --cases central-rejoin --diagnostic-drop-ack
python3 tests/integration/diagnostics/audit_native_epochs.py build/new-central-epochs/central-rejoin-1 --mutations
```

`someip.tar.gz`는 성공·실패 시도의 원본 runtime 결과/pcap/config/log/물리·제어 CSV와 모든 family,
SIGKILL 직후 이전 Central copy를 포함한다. `validation.tar.gz`는 build/회귀/sanitizer/정적 검사/
독립 감사 및 실패 log·build 설정이다. `sources.tar.gz`와 `sources.json`은 최종 변경 source/hash이며
ACK 주입 수정 전 두 runtime source는 validation의 `ack-injection-fix.patch`를 역적용해 복원한다. [SHA256SUMS](SHA256SUMS)로 무결성을 확인한다.

기존 finite terminal service를 family에 연결하는 작업과 CARLA 감독 복구 주행은 남아 있다.
실제 역할 증감, 단일 epoch 무중단 기록 이관·디스크 삭제, 전체 ODD·wall·Target 수용이나
학습 모델 도입을 완료한 것으로 표시하지 않는다.
