# M4 고장·M3 실행 감시 시험 프로토콜

Date: 2026-10-20. **실행 전에 고정하는 조건**이며 결과는 별도 evidence에 기록한다.
이 프로토콜은 Host component다. M3 기존 실패·학습자 review와 전체 system TC의 NOT RUN을 변경하지 않는다.

## 기능 판정

Owner 정지는 세션·RX·제어·자체 감시·출력·ACK 전체를 호출하지 않는다. 방향별 drop/delay는 owner를 계속 실행한다.
공통 recipe는 `path:kind:target:start_ms:duration_ms:delay_ms[:phase]`이며 상대 시각의 기준은 run 시작이다.
Duration0은 지속 고장이다. 실제 주입은 첫 정지/차단/지연/수신 정체 시각으로 기록한다.
Delay는 payload·source·original deadline을 수정하지 않고 도착만 늦춘다. Overflow는 실제 정상 producer의 FIFO를 consumer가 비우지 못하게 한다.

고장 주입·valid RX/source/deadline·검출·gate 폐쇄·Leaf 선택·Zone ACK·물리 output watchdog·실제 반응을 별도 event/CSV로 기록한다.
단절 시험의 검출·정상 차단은 실제 주입 이후100ms 이내, command expiry는 원래 exclusive deadline부터 다음 service 기회 이내다.
Prepare는 원래2s, INIT/Release는 enable+최대20ms, operation 결과는 원래 authority와20ms result budget 중 빠른 기한을 따른다.
멈춘 owner의 ACK는 주입 구간에 없어야 한다. 살아 있는 경로의 선택과 missing ACK mask를 구분한다.
물리 watchdog은 마지막 출력 source+30ms 이후 적용하며 멈춘 ECU의 보호로 집계하지 않는다.
Power 출력 driver는 토크0/전류5A 미만·기존20ms dwell 확인 뒤 코일 해제/방전을 선택한다. 접점/전압은 실제 모델 응답을 기다린다.

고장 해제 후 같은 Epoch gate/latch가 열리면 FAIL이다. 복구는 더 큰 사전 발급 durable Epoch·전체 준비/INIT/Release·readiness/arm이 필요하다.
실패한 mailbox는 모든 owner가 종료·join한 뒤에만 교체한다. 물리/SOC/energy/model identity는 재생성하지 않는다.
Actual/source는 실제 취득 시각이고, 이전 Central 관측을 새 Epoch의 상태로 합치지 않는다.

## M3 연결과 prospective cohort

기능 묶음 통과 뒤 기존 `TaskSchedule`/`DeadlineMonitor`를 연결한다.
전체 service owner의 대표 기회는2ms, release→완료4ms다. 자기 완료 기록과 독립 observer의 miss/late 검출은 분리한다.
추가 monitor는 다른 owner guard를, Physical은 monitor guard를 poll한다. 각 poll cursor는 단일 observer만 소유한다.
감시의 보호는 gate 폐쇄/priority request와 물리 override이며, 멈춘 ECU가 ACK한 것으로 표시하지 않는다.
Guard deadline 후 검출≤10ms, Physical 실행 가능 시 검출 후 적용≤10ms를 사용한다. 임계값 완화 없이 실패도 보존한다.
단순 body>4ms 관측과 실제 독립 deadline 검출을 별도 판정한다. 누락 slot은 이후 heartbeat/완료로 채우지 않는다.
Leaf 제어 runnable은 원래 nominal10/20ms release와5/8ms budget도 별도 기록하며, 늦은 시작/완료에서는 정상 actuation을 게시하지 않는다.
독립 observer의2/4ms service guard와 각 제어 runnable의 admission/완료 검사는 서로 다른 판정이다.

Native 측정은 run2540ms, guard lead100ms·period2ms·deadline4ms·1211 slots·20ms tail이다.
정상은 guarded skip/miss0·기능/설정/부하 control PASS, 고장은 지정한 검출·보호·원래 authority·ACK 부재 판정 PASS를 요구한다.
논리 clock 시험은 별도이며 wall 통계에 합치지 않는다. ASan/UBSan의 성능도 normal과 합치지 않는다.

| 고정 조건 | 실행 계획 |
| --- | --- |
| 정상 cohort | normal/ASan·UBSan × OTHER/FIFO × quiet/loaded ×3회 =24회 |
| 고장 cohort | Drive owner pause200ms / Monitor overrun6ms × 두 build × 두 policy ×3회 =24회 |
| CPU map | CPU A=0: Front/Rear Zone·Physical·monitor, CPU B=1: Central·다섯 Leaf; 상속 affinity 밖이면 설정 실패 |
| FIFO priority | monitor20, Physical19, Zones18, Central11, actuator/Power10, BMS9; OTHER는 priority0 |
| 부하 | CPU B에 별도 OTHER process,10ms마다7ms busy; 실제 CPU time≥100ms·affinity·생존·busy window 수를 확인 |
| 순서 | repetition마다 policy/load/시나리오 순서를 회전; build 분모·실패 유지 |
| 설정 실패 | policy/CPU 적용 실패는 workload 시작 금지·원래 오류 기록; OTHER fallback 없음 |

정상/고장 총48개 요청을 분모에 남긴다. 권한 부재는 BLOCKED, 유효하게 실행한 timing/기능 실패는 FAIL이다.
본 cohort 전에 OTHER/FIFO 정상 각1회의 설정 smoke를 별도 분모로 기록한다. 이 smoke로48개 결과를 대체하지 않는다.
실패한 run을 조용히 재실행해 교체하지 않는다. 코드 수정 후 재검증 cohort는 별도 대상 commit/분모로 남긴다.
Kernel trace/Target/실제 remote process·network partition·M5 DDS는 별도다. 공유 memory gate와 atomic protection은 방향별 mailbox 차단을 우회할 수 있다.
