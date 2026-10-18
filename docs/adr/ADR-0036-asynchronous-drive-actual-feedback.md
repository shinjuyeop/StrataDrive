# ADR-0036: 비동기 Drive Actual의 취득 시각 보존과 CAN 수신

Date: 2026-10-18. Status: **Host component 구현 / 검증 결과는 품질 기록에 연결**.
[ADR-0034](ADR-0034-multirate-runtime-and-can-loss-monitoring.md)의 비동기 torque unavailable 후속 결정이다.
Central/Zone/DDS·차량 배포 구조와 기존 task deadline은 유지한다.

## 시간 계약

기존 [Drive wire](../icd/drive_frame_draft.md)의 Actual SourceTimeNs는 이미 토크 취득 시각이다.
새 유효 torque sample을 job과 같은 시각에만 발행하던 sender 제한을 풀고 원래 sample/value/identity 검사를 유지한다.
같은 sample을 다시 읽는 것은 새 측정이 아니며 torque unavailable로 보고한다. 이때 header source는 진단 생성 시각이다.
유효 Actual의 header를 report generation/TX 시각으로 바꾸지 않는다. Report generation은 runtime trace에 별도 기록한다.
Trace의 generation_ns는 ECU에 전달한 논리 job 시각(phase_ns)이며 실제 직렬화 완료 시각과 구분한다.

Speed와 capability는 독립된 source를 갖는다. Receiver는 각 시각을 session/now와 비교하며 torque 취득보다 늦다는 이유로 제거하지 않는다.
각 age·range·cursor와 capability input≤calculation, oldest dependency budget은 유지한다.
Torque의 엄격히 증가하는 source와 30 ms age, 80 ms latched RX timeout도 유지한다.
보조 feedback·새 report Sequence로 같은 torque의 critical freshness를 갱신하지 않는다.

CAN ID 0x282/64 bytes/schema 2/P05 DataID 0x1202·CRC coverage와 모든 golden byte는 동일하다.
새 timestamp field나 quantization을 추가하지 않는다. 기존 receiver는 더 늦은 보조 시각을 Invalid로 제거할 수 있으므로
sender/consumer 정책을 함께 검토한다. Wire baseline 채택·학습자 review는 여전히 PENDING이다.
CausalSequence는 마지막 수용 Command 문맥이며 지연된 토크 응답의 원인 증명으로 사용하지 않는다.

## 실제 송수신

Physical owner가 bounded Drive output snapshot의 timely report를 별도 Actual socket frame으로 송신한다.
기존 RX worker에 0x282 전용 socket과 별도 DriveReceiver를 두며 payload를 로컬 함수 반환으로 대체하지 않는다.
독립 수신부의 Accepted만 여섯 번째 atomic valid-RX 시각을 갱신한다. Monitor의 80 ms threshold/검출 <=100 ms와
Drive zero latch에 연결하며 ECU job 감시와 구분한다. P05/metadata/state·보조 quality는 실제 receiver가 판정한다.
Task count는 유지하며 round-robin RX budget 8에 Actual도 포함한다.

마지막 2.4 s ECU job의 응답을 비우기 위해 RX를 20 ms 더 실행한다(2 ms×1210 jobs).
마지막 RX deadline 2.423 s 뒤까지 기존 monitor/plant tail 40 ms가 유지된다.
출력·보호 snapshot 취득 뒤 적용 시각을 읽는 인과 순서도 유지한다.
Trace schema는 3으로 구분하고 이전 schema 2 기록의 분석을 보존한다. 이는 CAN wire schema와 별개다.

TX/RX full payload bytes·job generation/acquisition·socket begin/end·raw arrival/Accepted·usable 값을 사전 할당한 owner별 buffer에 보존한다.
실행 후 CSV로 쓰며 모든 Accepted payload를 원래 TX bytes와 producing job에 연결한다. Torque 양자화 한계 0.05 N·m도 확인한다.
Minimal trace도 동일 송수신/검증 경로를 실행하고 aggregate count를 보존한다.

## 상실과 범위

`feedback-replay`는 1.1 s 이후 한 Actual frame의 P05 counter/Sequence/source/value를 그대로 반복한다.
CRC-valid raw traffic이 계속되어도 valid RX는 갱신되지 않고 Actual stream만 상실을 검출해야 한다.
다른 다섯 입력 stream은 계속 수용되며 독립 Drive zero 요청과 유한 물리 응답을 확인한다.
현재 sample의 30 ms source 만료와 communication의 80 ms valid-RX timeout은 별개다. Stale sample으로 fallback하지 않는다.
Late frame이나 normal 입력으로 receiver/protection latch를 자동 복구하지 않는다.

이는 실제 CAN input/Actual feedback의 Host component 실험이며 Actual을 CARLA에 반영하는 Central/Zone/Host bridge의 구현은 아니다.
Physical owner는 실제 actuator·회로·Battery를 계속 진행하고 CAN feedback을 다시 물리 truth에 덮어쓰지 않는다.
앞선 [CPU 부하 실험](../learning/m3_cpu_placement.md)은 다섯 stream workload의 이력이다. 새 RX 작업량과 구분한다.
Owner별 배치/우선순위·Target/E2E·M3 수용은 후속이며 전체 32개 요구/29개 system TC는 NOT RUN이다.
실행 방법은 [Drive Actual 안내](../learning/m3_drive_feedback.md), 실제 검사 수치·실패와 증거는 [품질 기록](../quality_policy.md)에 남긴다.
