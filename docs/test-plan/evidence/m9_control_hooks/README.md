# M9 Central 검출 hook·SimpleVehicle 진단 연결

2026-11-02. **SpeedRequest/NormalStop detector 연결·논리 SimpleVehicle PASS**.
[계약](../../../interfaces/diagnostics.md), [프로토콜](../../diagnostics-protocol.md),
[C-M9-CTRL 추적성](../../component-traceability.csv)을 따른다. 전체 M9/system TC 수용은 아니다.

## 실제 실행과 결과

Source 내부의 bounded snapshot으로 최초 판정/PI reason·원본 request/input·StopLease·
phase/적용 config를 보존했다. 같은 Central owner의 ControlDiagnostics가 queue에 발행한다.
Source controller는 DTC 결과·파일 I/O를 기다리지 않으며 logger callback을 호출하지 않는다.

| 실제 논리 실행 | 판정과 원본 |
| --- | --- |
| 정상92s·기존87s 속도 profile |4350회 SpeedPI·9200 physical samples, 정상 StopLease/인계·Actual Off/HV-off, DTC0·진단 events12 |
| 현재 speed argument 누락 | elapsed10s에 SpeedRequest argument만 누락.461 controls·1300 physical samples, SD-1001 한 건·events15·count1·journal commit |
| On/off 비교 | 동일 입력 누락 fixture의 모든 controller output/state trace와 원본 authority·물리·에너지 값이 정확히 일치 |

정상/누락 실행은 `normal/`, ASan 대응 실행은 `asan/`에 각각 보존했다.
각 `diagnostics.csv`는 canonical journal payload와 필드별 대조했다. Source acquisition,
Leaf 선택·Zone ACK와 Central ACK 확인은 서로 다른 원본 시각이다.

Input-loss의 injection은11.000s absolute simulation, detector11.002s, 실제 다섯 Leaf
선택11.0022s, 두 Zone ACK11.0024s, Central ACK 확인11.005s다. 첫 조건 충족
wheel/torque/pressure acquisition은11.211s, Central 관측은11.2112s다.
따라서 주입→검출2ms, 검출→선택0.2ms, 검출→Central ACK3ms, 검출→Actual209ms다.
Actual의 torque0Nm·brake1MPa와 이후230ms 기준의 물리 응답·계속 닫힌 gate·model epoch7·
에너지 연속성을 확인했다. 그때 wheel11.56rad/s이므로 이 반응을 차량 정지 완료로 세지 않는다.

NormalStop의 braking/shutdown timeout·feedback/hold/request 상실·handoff expiry·
후속 clock rollback과 Coordinator 인계 rejection은 실제 detector component에서 DTC로
연결했다. 이 fixture의 짧은80ms/40ms budget은 detector 경계 시험 설정이며 기본5s/2s나
별도30km/h10s를 바꾸지 않는다. 실제 차량30km/h timeout/ACK-loss 시험 결과가 아니다.

## 검증 분모

| 검사 | 결과 |
| --- | --- |
| 일반 unit + integration.logical |1104/1104, failure/skip0. 신규 연결14개 포함. `normal.xml` |
| 영향 ASan/UBSan |147/147, failure/skip0. `asan.xml` |
| 최종 진단 경계 |52/52 Normal·ASan/UBSan 각각. Timeout Violation을 phase start가 아닌 실제 deadline으로 구분한 뒤 재검증. `final-focused*.xml` |
| 기존 wall owner 회귀 |2/2, `wall.xml`. 진단 opt-in은 wall에서 거절하며 전체 wall 수용으로 확대하지 않음 |
| 강화된 on/off 비교 | Normal/ASan 각각1개, controller 필드까지 직접 대조. `onoff*.xml` |
| Canonical journal·원본 감사 | Normal/ASan의 정상·입력 누락4실행 모두 PASS. `audit-*.json` |
| 감사 손상 거부 |각 input-loss8/8: owner 누락·ACK 오분류·code·판정 retimestamp·Actual torque/age·epoch·journal CRC |
| Python source fingerprint |2/2 |
| Release / BUILD_TESTING=OFF |`control_diagnostics`와 dependency 빌드 통과 |

Full regression 뒤 CSV에 ACK/source producer/roles를 추가해 SIL4개를 Normal/ASan 각각
재실행했다(`export*.xml`). 그 뒤 deadline annotation과 직접 controller 비교를 보완하고
최종52개 경계를 각각 실행했다. 중간/최종 분모를 더해 시험 수를 부풀리지 않는다.
최종 binary의 SHA를 고정한 뒤 원본 보관용 정상/입력 누락2개를 Normal/ASan에서 다시
실행했다(`final-export*.xml`). 저장한 journal/CSV/owner/physical은 이 마지막 export의 원본이다.

clang-tidy는 변경 production8 TU에 대해 exit0이다. Header warning generation 메시지는
원본 로그에 남겼다. cppcheck는 Coordinator 생성자의 기존 `AllocationConfig allocation`
값 전달 performance finding1개로 exit1이며, HEAD baseline source에서도 동일하게 재현했다.
새 source finding은 없다. 이를 static warning0으로 보고하지 않는다. 대상은
`compilation-subset.json`, 비교 원본은 `cppcheck-baseline.log.gz`다.

첫 build의 GTest macro 조건문 brace warning을 수정했다. 첫 연결52개 중1개는 Central
`protect()` true 관측11.005s를 Leaf 선택으로 잘못 분류한 코드/기대 때문에 실패했다.
원본 local 선택과 ACK를 구분해 수정했으며 최초 `probe.log.gz`/`probe.xml`을 보존한다.
이후 ACK 분리52/52와 최종 경계 결과를 별도로 보존했다. Snapshot/source 원본은 최종
검증 revision이며 최초 실패 iteration 전체 source snapshot은 보관하지 않았다.

## 재현과 근거

`manifest.json`의 base commit에 `sources/` overlay를 적용한 source와 시스템 GTest1.11.0이 기준이다.
이 검증의 store schema/registry는 v1이고 run1001/1002·producer7·simulation instance=run,
profile1과 numeric dictionary는 [계약](../../../interfaces/diagnostics.md)에 있다.
Binary SHA·source overlay·당시 도구와 raw/XML/log를 보존한다. 로그/XML의 시각을 고쳐 쓰지 않았다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --output-on-failure
STRATADRIVE_M9_CONTROL_EVIDENCE=/tmp/m9-new-output ctest --test-dir build/m1-angle -R '^ControlDiagnosticsSil\.' --output-on-failure
python3 tests/integration/diagnostics/audit_control_diagnostics.py /tmp/m9-new-output/normal
python3 tests/integration/diagnostics/audit_control_diagnostics.py /tmp/m9-new-output/input-loss --mutations
```

`STRATADRIVE_M9_CONTROL_EVIDENCE`의 normal/input-loss가 이미 있으면 덮어쓰지 않고 거절한다.
ASan은 별도 build와 `-DSTRATADRIVE_SANITIZERS=ON`, 영향 target/filter는 `commands.json`을 따른다.
보관 raw CSV는 gzip이며 감사할 때 새 디렉터리에 풀어 실행한다. `store/`의 binary는 그대로다.
이 evidence 디렉터리에서 `sha256sum -c SHA256SUMS`로 파일을 검사한다.

## 후속과 한계

이 결과는 in-process owner/mailbox·CAN/P05·실제 ECU controller와 SimpleVehicle/EV의
논리 시간 SIL이다. CARLA/server·실제 network 진단 전송·Target·wall 진단 latency 검증이 아니다.
Local owner selection은 기존 raw log를 실행 뒤 변환했고 journal도 실행 뒤 commit했다.
현재 root fault 판정은 실제 SpeedRequest/NormalStop이며 일반 Zone/Leaf 자체 fault enum의
DTC publisher·spool·live writer는 후속이다. Code별 `ConditionPassed`/clear를 자동 발행하지 않는다.

다음은 code별 recovery evidence와 Zone/Leaf 수집 경계를 정하고,30km/h 입력 손실·제동
timeout·실제 ACK/lane 손실 recipe의 위치·시각·기대 code/물리 응답을 실행 전에 고정하는 것이다.
SYS-DIAG-001/TC-DIAG-001 전체·TBD-08 최종 수용·개인 이해 review는 OPEN으로 유지한다.
