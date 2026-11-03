# M9 Zone/Leaf 소유자별 진단 수집·부분 복구

2026-11-02. **논리 owner 경계 PASS / 전체 M9 OPEN**.
[계약](../../../interfaces/diagnostics.md#zoneleaf-소유자-수집-경계),
[recipe](../../diagnostics-protocol.md#소유자별-검출복구-fixture),
[ADR-0081](../../../archive/design-decisions.md#adr-0081), C-M9-OWN-01–06을 따른다.

## 구현·실행한 경계

ZoneFeedbackMonitor와 Leaf wrapper가 최초 native fault/current·last-healthy 입력 또는
실제로 수용한 context/expiry를 bounded snapshot에 보존한다. 같은 소유자의 별도 observer가
각 SPSC queue에 발행한다. Producer는 Central7/Front20/Rear21/Steering22/Brake23/Drive24다.
개별 INIT는 global Session을 발행하지 않는다. 원본 wire/token/source·parent/child expiry와
선택/ACK를 재관측 시각으로 갱신하지 않는다. Queue/store 실패는 native 보호를 기다리게 하지 않는다.

| 실제 검증 | 결과 |
| --- | --- |
|정상92s|기존4350 controls·정상 StopLease/HV-off·9200 physical samples·local DTC0 |
|Central만10s부터200ms 정지|Zone gateway가 먼저 보호. Leaf expiry는 원인 미상의 보호 전달 Observation이며 새 SD-2001로 꾸미지 않음 |
|Central/Front/Rear를10s부터200ms 정지|live Steering/Brake/Drive의 독립 context expiry 세 건 SD-2001. 그동안 정지한 상위 owner의 fake 검출/ACK0 |
|상위 재개|두 Zone의 실제30ms call guard 초과 SD-4002 두 건. 같은 epoch의 traffic/owner 재개만으로 gate/latch 복구 없음 |
|20s 링크 교체·실제 INIT2|실패한 bounded links를 기존 logical joined 경로로 교체. 같은 physical/battery model epoch7·position/sequence 연속 |
|새 정상 재시험|Zone 실제 tick/full input Control proof·Leaf actual accepted context/healthy body Input proof. 다섯 기록 Passed·count1/generation1·미삭제 |
|Zone feedback 누락 component|실제 ZoneFeedbackMonitor/Gateway에서 SD-2002·last healthy source·복원/INIT만/닫힌 gate/stale 거부와 새 정상 tick 복구 검사. 차량 feedback-loss 통합으로 세지 않음 |

시간은 위 표에서 elapsed이며 absolute simulation은1s를 더한다. Native command expiry는
11.011000001s, 실제 Leaf 검출/선택은11.0112s로199999ns 뒤다. Central/두 Zone은
11.2s까지 실행하지 않는다. Zone deadline은 원래 위반 시각과11.2s의 검출을 구분한다.
첫 원본 physical 표본의 torque≤1Nm/brake≥1MPa는11.221s, 최초 검출 후209.8ms다.
이를 차량 정지 완료로 세지 않는다. 기록된 물리 응답 후에도 INIT 전 gate는 닫힌 상태다.

새 epoch의 Zone 정상 tick은21.0304/21.0404s, Leaf의 첫 정상 수용/body proof는21.7902s다.
Zone monitor 복구는 Central arm/주행 permission을 뜻하지 않는다. 이들은 metadata
**Observation proof**이며 measured0이나 successful output을 물리 Actual로 꾸미지 않는다.
물리 달성은 독립적인 original physical CSV와 대조했다. Fault case는 events30·기록5건·
2400 physical samples다. Native context와 Zone detector CSV도 별도로 보존한다.

서로 다른 code/누락 mask의 복구 대기는32개 fixed slot으로 보존한다. 다음 epoch에서 다른
고장이 생겨도 앞선 key의 Unknown 이력을 덮지 않으며, 이후의 정상 재시험에서 각각 Passed가
된다. 이력/count를 삭제하는 clear는 없다. Clock recovery는 이번 qualified 범위에 없다.

## 검사와 원본

| 검사 | 결과 |
| --- | --- |
|일반 unit + integration.logical|1118/1118·failure/skip0. `normal-verified.xml` |
|영향 ASan/UBSan|124/124·failure/skip0. `asan-verified.xml` |
|최종 Normal/ASan export|각4/4. `export-verified-*.xml` |
|기존 wall owner|2/2. `wall.xml`; local diagnostics wall 실행 검증 아님 |
|독립 journal/native/owner/physical 감사|Normal/ASan 모두 정상·고장 PASS. 고장 손상7개씩 거부 |
|정적 검사|변경 production7 TU clang-tidy/cppcheck exit0. Non-user header warning generation 원본 보존 |
|기타|source fingerprint2/2·Release BUILD_TESTING=OFF owner/runtime 빌드 PASS·이전 세 M9 evidence SHA 유지 |

Main case에서 세 Leaf의 **실제** expiry/success snapshot마다8개 음성 경로를 검사한다.
Gate/faulted·success 없음·epoch/enable 불일치·expired context·71ms child dependency·stale
body는 Passed가 아니다. 유효한 실제 snapshot만 Passed다. Native receiver의 dependency70ms,
정상 body age30ms와 command expiry를 각각 유지한다. Zone은 source 복원만/INIT만/닫힌 gate/
stale sample을 거부한다. Queue full이 native 보호 선택을 바꾸지 않는 것도 검사했다.

On/off는 같은 공개 runtime/recipe의 전 physical 표본·native fault/보호 시각·토크/압력·
위치/에너지/SOC가 일치했다. 이 논리 진단은 wall 성능이나 WCET 개선 주장이 아니다.
기존 SPSC의 TSan 근거는 이전 component evidence를 따르며 이번에 새 wall collector/TSan
cohort를 실행한 것으로 세지 않는다. SD-1001/clear 회귀는 최종 일반/영향 검사에 포함한다.

## 실패와 교정

`probe.xml`의 최초2개 실패를 보존한다. 첫 queue-full 시험은 monitor tick을80ms 건너뛰어
실제 Deadline을 먼저 만들었다. 원래10ms tick을 유지한 뒤 startup input loss를 검사하도록
fixture를 고쳤다. Central-only 시험은 gateway 보호가 먼저인데 Leaf root를 기대했다.
이 경우는 propagation 음성 시험으로 남기고 별도 상위3-owner 정지 recipe를 실행했다.
고장 위치/범위를 바꾼 두 fixture를 같은 결과로 합치지 않는다.

초기 상위 정지 fixture는 실패한 mailbox를 교체하지 않아 INIT2가 실패했다. 이후 custom
scheduler에 원래 logical runner의 joined link 교체 호출을 누락한 실행도 실패했다.
기존 복구 절차를 그대로 호출해 고쳤으며 native latch/gate/INIT 기준을 우회하지 않았다.
상위 재개 시 두 Zone Deadline이 실제로 생기는 점도 최초 기대에서 빠져 있었다. 이를 지우지
않고 각각 별도 DTC와 실제 control 재시험으로 연결했다.

추가 Leaf 음성 검사에서 처음에는 child dependency에도30ms를 요구해 정상 snapshot을
거부했다. 기존 receiver의 계약은 해당 dependency70ms이므로 원래 기준으로 교정했다.
Command expiry/body freshness는 유지한다. 마지막 review에서 다른 key의 pending recovery
덮임을 막고 혼합 고장 회귀를 추가했다. Metadata proof는 물리 Actual로 표현하지 않는다.
첫 compile의 SteeringMessage→ActuatorMetadata 변환 오류도 보존하고 원본 identity 필드를
명시적으로 복사했다. 실패 로그/XML과 중간 artifact는 최종 분모에 더하지 않는다.
최종 source overlay는 보관하지만 실패 iteration별 전체 source snapshot은 저장하지 않았다.

## 재현·후속

`manifest.json`의 base commit 위에 `sources/` overlay를 적용한다. Binary/source/tool SHA,
빌드 설정과 정확한 명령은 manifest/commands를 따른다. 원본 CSV는 gzip이며 `normal/`,
`asan/`을 새 위치에 복사해 풀면 독립 감사를 실행할 수 있다. Store binary는 원형 보존이다.
이 디렉터리에서 `sha256sum -c SHA256SUMS`로 검사한다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 4
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --output-on-failure
STRATADRIVE_M9_OWNER_EVIDENCE=/tmp/new-owner-output build/m1-angle/owner_diagnostics_sil_test
python3 tests/integration/diagnostics/audit_owner_diagnostics.py /tmp/new-owner-output/upstream-pause --mutations
python3 tests/integration/diagnostics/audit_owner_diagnostics.py /tmp/new-owner-output/normal
```

이미 있는 export를 덮어쓰지 않는다. 논리 source snapshot/queue의 부분 연결이며 모든 local
fault root를 포괄하지 않는다. Gateway admission/send·BMS/Power 자체 원인 publisher,
remote transport/spool·production background writer·owner clear service·source restart adoption·
Clock recovery·CARLA30km/h fault matrix·wall/Target·학습자 수용은 OPEN이다.
