# 진단 계약 검증 프로토콜

2026-11-02. **집계/store component 부분 검증 / 실제 monitor·차량 통합 NOT RUN**. SYS-DIAG-001 / TC-DIAG-001의
Host component·기능 SIL 분해안이다. 새 system TC/Result ID를 발급하거나 과거 시험을
DTC 통합 PASS로 올리지 않는다. Oracle은 [진단 계약](../interfaces/diagnostics.md)이다.
계약 검토 후 아래 component → 기존 경로 연결 →30km/h 고장 통합 순서로 실행한다.

M9-2의 [실제 실행·추적성](evidence/m9_diagnostics_component/README.md)은 synthetic typed event를
사용한 집계/중복·역순/재발·Unknown/clear·bounded failure·journal/commit 복원과 SPSC 검사다.
DG-03/04/05/06/19의 원본 검출기/ACK/packet→DTC 연결과 DG-10의 실제 pause/reset 전달,
30km/h 물리 fault matrix는 아직 실행하지 않았다. DG-14의 실제 용량 적합성/장치 crash,
cross-process spool과 원격 전송도 후속이다. 일부 component PASS를 DG 전체 PASS로 올리지 않는다.

## Component 수용 조건

아래 ID는 protocol case이며 실행 가능한 test 이름은 [component 추적표](component-traceability.csv)의
C-M9-DIAG-*에서 연결한다. 검출/선택 규칙의
원본 회귀와 새 진단 집계/storage 검사를 구분한다.

| Case | 입력·경계 | 기대 결과 |
| --- | --- | --- |
| DG-01 정상/초기화 | INIT wait, 정상 주행·NormalStop, cap0, 정상 포화 | confirmed DTC0; startup 허용 구간과 fault를 혼동하지 않음 |
| DG-02 즉시 확정 | qualified SpeedRequest Feedback/Source | SD-1001 한 occurrence; 추가 debounce0, 원본 detect/선택 시각 유지 |
| DG-03 원본 debounce | Brake response의 threshold 직전/정확히 도달/회복, cached polling | 기존 fresh-sample dwell 확정 전 DTC0, 확정 시 SD-3001 하나; cached sample로 count/dwell 증가 없음 |
| DG-04 boundary | source age30ms/30ms+1ns, exclusive expiry 전/동일 시각, timeout 직전/동일 시각 | 원본 monitor와 동일 결과; PI60ms로 gate 완화 없음 |
| DG-05 제동 예산 | 동일 이상적30km/h 입력에 기본5s / 명시적10s config | 원본 NormalStop 결과와 code 일치; SD-1101에 적용 config와 phase 기점 보존 |
| DG-06 ACK 구분 | pending, missing, rejected, 잘못된 epoch/lease/role, expired | pending만으로 DTC 생성 안 함; 실제 Handoff reject/expiry는 SD-1102; 없는 ACK/PowerDown 성공을 합성하지 않음 |
| DG-07 중복/재발 | 동일 ID replay, 같은 occurrence 반복, pass 후 새 fault | 중복 count 불변; 새 qualified occurrence만+1; 최초 원인/시각 보존 |
| DG-08 source 분리 | Front/Rear, command/status, Brake/Drive 동시 loss | 독립 key/occurrence; link를 통한 원인·전파 추적, aggregate 한 개로 뭉개지 않음 |
| DG-09 cause 보존 | 원본 fault 후 UpstreamProtection/ClockError 관측 | 원본 evidence 유지; 전파는 관계, 새 clock fault는 별도 기록; root 미도착은 cause_unknown |
| DG-10 clock | simulation pause/reset, wall clock instance 변경, rollback | domain/instance 보존; 잘못된 latency는 not_comparable; wall 검증으로 확대하지 않음 |
| DG-11 역순/과거 event | 보호/Actual이 검출보다 먼저 collector 도착, 이전 epoch 지연 회수 | causal ID로 연결; detect timestamp/현재 session 권한 변경 없음 |
| DG-12 restart | durable record replay, 새 collector instance/새 INIT | 이력/count 유지, 현재 condition/latch Unknown; replay는 재발 아님 |
| DG-13 journal crash | append·commit·clear 전후 crash, tail partial, 중간 손상, sequence gap, payload mutation | committed prefix만 복원; 손실/손상 명시; false durable/false clear 없음 |
| DG-14 bounded failure | queue full, record capacity, count 한계, disk full/write 오류 | 조용한 drop/evict/wrap 없음; gap health 증거 유지; 기록 실패 중에도 기존 보호 선택·Actual 경로 실행 |
| DG-15 pass | fresh traffic 하나, INIT만 성공, response tracking disabled | Passed로 단정하지 않음; code별 재시험 필요; missing monitor는 Unknown |
| DG-16 clear 거절 | Failed/Unknown, moving/invalid hold, 정상 dispatch 중, stale revision, store 오류 | clear 실패, 이력·제어 latch 불변 |
| DG-17 clear 성공/경합 | qualified pass+stationary/inhibited, clear 중 새 fault, clear-all 일부 fault, request replay | 조건 충족만 durable tombstone; 경합/부분 실패는 거절; 중복 요청 idempotent |
| DG-18 clear 후 재발 | 새 fault와 clear 전 occurrence의 지연 전송 | 새 generation count1, 과거 이력 연결; 늦은 과거 event로 새 generation 생성 안 함 |
| DG-19 F02 rejection | invalid/duplicate/stale packet과 정상 valid traffic 또는 지속 loss | raw Observation 보존, last-valid 갱신 없음; rejection만으로 confirmed DTC 생성 안 함, 실제 timeout은 SD-2001 |
| DG-20 unmapped fault | registry에 없는 실제 reason, root 없이 protection만 도착 | 원본 증거/UNMAPPED 표시; 가짜 root code·정상 판정 없음, 해당 scope 통합 수용 보류 |

기존 회귀의 출발점은 `tests/unit/speed_request_test.cpp`, `normal_stop_test.cpp`,
`vehicle_coordinator_test.cpp`, `command_admission_test.cpp`, `command_gateway_test.cpp`,
`brake_response_monitor_test.cpp`, `steering_response_monitor_test.cpp`다.
현재 회귀 PASS는 새 진단 기능을 검증하지 않는다. 새 구현 시 실제 test/function·결과·
evidence를 component 추적표에 연결하고, 영향 경계의 Normal/ASan·UBSan 검사를 실행한다.
새 동시성 경계를 추가하면 해당 writer/queue의 TSan도 검증한다.

## 기존 경로 연결

먼저 기존 저속 input-loss/NormalStop과 논리 시간 command loss에 event→DTC를 연결한다.
기존 정상·보호 출력과 원본 source/expiry/권한 결과가 유지되는지 비교한다.
DTC writer 지연/실패가 기존 protection selection을 막거나 timeout을 늘려서는 안 된다.
새 replay 결과는 새 물리 실행으로 세지 않는다.

정상 경로는 원래 profile/config로 **confirmed DTC0 + recording gap0**이어야 한다.
고장 경로는 code/key/count/native reason·clock/인과·제어 state·Actual을 함께 판정한다.
기존 log에 DTC가 없다는 사실을 DTC0 PASS로 읽지 않는다.

## 30km/h 고장 통합의 사전 고정 항목

출발 참조는 기존 [30km/h NormalStop fixture](carla-stop30-protocol.md)다. 아래 표는
주입 종류와 oracle의 구분이며 **실제 주입 위치·시각·기간/profile hash가 고정된 실행 recipe가 아니다**.
각 case 실행 전 recipe와 expected code set을 manifest로 고정해야 한다.

| 고장 종류 | 고정할 주입 경계 | 예상 진단·구분 |
| --- | --- | --- |
| 현재 speed 입력 손실 | Central SpeedRequest 인자만 누락; 실제 sensor/다른 traffic 유지 | SD-1001; 실제 command/전체 통신 손실이라고 부르지 않음 |
| NormalStop 제동 시간 초과 | config5s를 별도 profile로 명시; 정상10s control case와 분리 | SD-1101; timeout 뒤 실제 보호/정지·에너지 별도 판정 |
| Brake actuator 응답 고장 | 실제 sensor/actuation 경계의 stuck/지연; command·sensor delivery는 유지 | 원본 response monitor가 확정하면 SD-3001; stopping timeout과 구분, 제동 성공을 가정하지 않음 |
| Stop 인계 ACK 손실 | 특정 Leaf→Zone 또는 Zone→Central의 실제 ACK lane만 차단; 요청/Actual은 유지 | missing 역할/lease·원본 deadline 명시; 최초 실제 detector에 따른 SD-1102 또는 SD-2001 set을 recipe에서 고정 |
| 실제 command/status 통신 손실 | Front/Rear·방향·lane과 살아 있는 owner/센서 명시 | 실제 owner의 SD-2001/SD-2002와 root/전파 연결. ACK-only와 별도 |

ACK가 이미 수용된 뒤의 보호 요청 주입은 기존 stop-protection 시험이며 ACK-loss가 아니다.
ACK/통신 차단 뒤 어떤 expiry/monitor가 먼저 실패하는지는 실제 scheduling·authority에
달려 있다. 기대 code를 결과를 보고 고르지 않는다. 먼저 component에서 결정 순서를
검토하고 full recipe의 code·phase·기점을 고정한 다음 물리 실행한다.

각 recipe에는 다음을 포함한다.

- source/binary/config/profile/route/map hash·seed, clock domain/instance, session/role,
  발생 위치·시각·지속, 원본 last-valid/source/expiry와 expected detector/first reason.
- 검출·보호 요청/실제 선택/ACK·Actual acquisition/관측·body/wheel 정지·HV 상태·
  solver work/단일 EV 정산·DTC enqueue/durable commit을 각각 판정하는 기준.
- 해당 source/timeout의 원래 검출 budget과 물리 budget. 검출100ms를 모든 phase에
  재사용하지 않으며 저속 정지5s를30km/h 고장 전체에 자동 적용하지 않는다.
- 가용 actuator의 기대 동작, unavailable일 때 주장할 수 없는 결과, tick gate 시
  완료 physics/EV 분모·미정산 구간과 containment 판정. Tick 차단은 정지 성공이 아니다.
- store 지연·회수/restart·원인 해소·INIT·clear 후 재발의 검증과 원본 evidence 보관 위치.

전체 M9 종료에는 위 recipe의 실제 기능 SIL과 정상 false-DTC0, 고장별 trace 완전성,
재시작·clear/복구·손실 검증이 필요하다. 이번 설계 문서 작성으로 system TC, wall 실시간,
Target·전체 Reference 수용을 올리지 않는다.
