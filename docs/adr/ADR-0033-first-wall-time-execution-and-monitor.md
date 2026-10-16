# ADR-0033: 첫 wall-time ECU 실행과 독립 deadline 감시

Date: 2026-10-16. Status: **M3 첫 Steering Host component 구현·검사 / 다른 task·Target/E2E 후속**.
TBD-04의 부분 결정이다. 전체 task 배치·Target·차량 deadline을 확정하지 않는다.

## 결정

[ADR-0032](ADR-0032-ecu-and-sil-execution-boundaries.md)의 ECU/plant 분리를 사용해
Steering 한 경로부터 Linux Host의 실제 주기 실행과 계측을 연결한다.
M2의 deterministic SIL과 회귀시험은 그대로 유지한다.

- `vecu/common/periodic_task`는 유한한 absolute release schedule과 독립 completion monitor를 제공한다.
  Period와 relative deadline은 별도 입력이다. 늦은 실행은 최신 release 하나만 선택하고
  이전 job은 skipped로 남긴다. Catch-up burst나 release 시각 재설정으로 지연을 감추지 않는다.
- Monitor는 실행 thread의 callback·ECU 객체·handoff mutex를 사용하지 않는다.
  사전 할당한 job별 lock-free completion timestamp를 관측한다.
  시작하지 않은 job도 deadline에 완료가 없으면 miss다. Late completion은 latch를 지우지 않는다.
- 첫 실행 fixture는 ECU 10 ms, relative deadline **5 ms**, monitor/plant 각각 2 ms,
  120 jobs, 첫 release는 enable + 10 ms다. Deadline 5 ms는 overhead와 fault 검출을 비교할
  **local 실험 설정**이며 period로부터 도출한 값이나 실차 요구가 아니다.
- ECU·monitor·plant는 별도 owner로 실행한다. Monitor의 latch는 plant의 Hold override로 연결한다.
  ECU를 멈춰도 감시와 물리/센서 취득은 진행한다. Plant는 action을 실제 관측한 시각부터 적용하며
  이전 interval을 되돌리지 않는다. 이 override는 실험용 containment이며 차량 안전 정책을 대신하지 않는다.
- Command는 별도 plant/fixture owner가 생성하고 sensor와 함께 latest snapshot으로 넘긴다.
  단일 생산자·단일 소비자의 세 고정 slot을 atomic exchange로 교환하며 읽는 slot을 생산자가 덮어쓰지 않는다.
  잠금 대기·재시도 loop·실행 중 메모리 할당 없이 최신 값을 복사한다. 중간 snapshot 대체 횟수와
  실제 trace drop은 별도로 계수한다. FIFO와 snapshot을 같은 의미로 취급하지 않는다.
- Runtime은 monotonic wall time으로 absolute sleep한다. ECU phase의 논리 job 시각은 start에서 고정하고
  완료 직후 실제 wall-time deadline을 다시 검사한다. 늦은 출력·feedback은 발행하지 않는다.
  Steering core의 최소 호출 guard는 이 fixture에서 1 ms로 두고 release period는 10 ms로 유지한다.
  실제 start jitter 때문에 두 호출 간격이 10 ms보다 조금 짧아지는 것을 task 누락으로 오인하지 않기 위함이다.
  M2의 10 ms 최소 호출 설정과 모델 수치는 변경하지 않는다.

## 계측과 검사

Job release/start/end·deadline·skipped/late completion과 ECU prepare/complete 비용을 기록한다.
Physics/capture 비용은 plant owner에서 별도로 기록한다. 전체 runner 시간을 ECU execution으로 쓰지 않는다.
Trace는 시작 전에 공간을 확보하고 실행 뒤 CSV로 쓴다. File I/O를 계측 구간에 넣지 않는다.
상세 trace와 최소 계측을 같은 workload로 비교하고 clock read 비용도 별도로 관측한다.

Schedule overflow·release 선택, deadline 경계, 미시작/누락/지연 완료·clock 오류와
snapshot의 concurrent payload/identity를 새 unit 14개로 검사했다. 기존 491개를 포함해
normal·ASan/UBSan 각각 전체 505개가 PASS다.
Normal, 최소 계측, bounded overrun과 stall을 각각 normal·sanitizer에서 3회,
BUILD_TESTING=OFF build에서 1회 실행했다. Monitor 검출·plant Hold·late feedback 억제와
누락 job의 분모 포함을 확인했다. 무한 hang의 강제 종료와 process/OS 고장 격리는 이번 thread fixture 범위 밖이다.

[Timing 계약](../requirements/timing_requirements.md)의 Mean/P95/P99/Max·sample/drop/miss와
환경/clock/빌드/계측 조건을 보고한다. 관측 최대값을 WCET bound라고 하지 않는다.
SCHED_OTHER의 Host 결과는 실제 MCU/AUTOSAR OS, RT priority, Target scheduling과 전체 E2E의 증거가 아니다.
TC-PERF-001/002와 SYS-PERF 요구의 부분 component 근거로만 연결한다.
