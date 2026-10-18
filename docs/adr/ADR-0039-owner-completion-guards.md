# ADR-0039: 감시·물리 작업의 완료 시한과 교차 감시

Date: 2026-10-18. Status: **Host fixture 계약 채택·구현 / Target·전체 M3 수용 후속**.
[ADR-0038](ADR-0038-whole-owner-cycle-observation.md)의 계측에서 짧은 body와 실행 누락이 함께 나타났다.
기존 정상 계약은 두 owner의 누락을 판정하지 않아 sanitizer RX 단독 분리가 각각 244개를 생략하고도 PASS였다.
이번 변경은 실행 budget을 명시하고 감시 작업 자체의 공백에서도 보호를 요청한다.

## Host 완료 계약

| 항목 | 기준 |
| --- | --- |
| Monitor·plant/fixture period | 기존 2 ms |
| 각 release 대비 completion deadline | **4 ms** |
| Guard 대상 | Enable부터 2420 ms까지 각각 **1211 slots** |
| 관측 tail | 기존 2440 ms까지 총 1221 slots; 마지막 guard deadline은 2424 ms |
| 검출 margin | Deadline 이후 <=10 ms, Host fault 시험의 수용 기준 |
| 적용 margin | 첫 owner fault 검출 이후 <=10 ms, plant가 실행 가능한 조건 |
| 정상 수용 | Guard 대상의 missed/skipped 0 + 기존 ECU/RX·수신·물리 계약 |

4 ms는 2 ms 주기와 추가 2 ms 완료 여유를 명시한 첫 Host budget이다. 직전 IO 분리의 body max는 약 0.15 ms
이하였지만 이 수치가 worst-case/Target 보장은 아니다. 원래 ECU 5/8 ms, RX 3 ms, RX budget 8,
유효 수신 threshold 80 ms·실제 검출 <=100 ms는 유지한다. 차량 calibration·전체 E2E/TBD-04는 남는다.

최신 release만 실행하는 기존 정책도 유지한다. 4 ms 안에 다음 작업을 끝냈더라도 **생략한 이전 slot은 별도 miss**다.
단순히 마지막 heartbeat가 최근인지 확인하는 방식으로 누락을 지우지 않는다. 마지막 10개 tail slot은 기록만 하고
guard 대상에서 제외한다. 마지막 guard deadline까지 서로를 관측한 뒤 종료하므로 tail의 tail을 무한히 추가하지 않는다.

## 교차 감시와 수신 감시

기존 `DeadlineMonitor`를 각 owner에 하나씩 둔다. 본문 전체의 end를 찍은 뒤 해당 slot의 완료를 원자로 게시한다.
Monitor는 plant guard를, plant는 monitor guard를 poll한다. 각 guard의 poll cursor는 한 peer만 소유한다.
Peer가 deadline 이후에 늦은 완료를 처음 보더라도 miss를 검출하며 이미 걸린 fault는 해제하지 않는다.
Clock error도 보호 원인이다. 새 thread나 watchdog executable은 추가하지 않는다.

어느 owner fault든 기존 brake floor·torque zero flag를 latch한다. Plant는 peer 검사와 수신 감시를 먼저 수행하고
보호/출력 snapshot을 취득한 뒤 application clock을 읽는다. 다음 구간의 결정을 이전 physics 구간에 소급하지 않는다.
기존 유한 torque ramp와 brake increase-only floor를 사용한다. 이 fault만으로 contactor를 강제 개방하지 않는다.

6개 accepted-RX stream은 monitor와 plant가 **각자 별도의 ReceiveWatch 상태**로 감시한다. 같은 cursor/state를
두 thread가 poll하지 않는다. Accepted 시각 snapshot을 observer clock보다 먼저 취득한다. Raw/CRC-invalid traffic은
입력이 아니다. 두 observer 중 실제 검출이 빠른 기록을 effective loss로 선택하고 그 observer의 원래 last-valid와
detected 시각을 함께 보존한다. 늦게 복귀한 observer의 늦은 진단도 `observers`에 그대로 남긴다.
Monitor 120 ms 정지 중 보호 이후 끊기는 accepted stream도 plant가 <=100 ms로 검출하는지 확인한다.

Plant가 멈추면 monitor는 보호를 요청할 수 있지만 물리 모델은 plant가 돌아올 때까지 진행하지 못한다.
두 owner가 함께 쉬거나 process/OS가 멈추면 실행 가능한 observer가 없다. 복귀 시 늦은 완료는 검출하지만
그 공백 중 실제 출력을 변경했다고 주장하지 않는다. Hardware watchdog·OS/프로세스 분리·RT/Target 검증은 후속이다.

## 기록과 고장 시험

Trace schema는 **5**, CAN wire schema는 **2**다. 이전 trace 2/3/4는 당시의 의미로 계속 읽는다.
CSV는 guarded/deadline/detected를 추가하고 skipped row의 실행 시각은 0으로 유지한다. Tail에는 가짜 deadline을 만들지 않는다.
Metadata는 guard별 observer·first fault·clock error와 각 수신 observer 기록을 담는다. Full trace에는 owner fault mask
(monitor=1, plant=2)와 각 owner의 stream fault mask를 남긴다. CSV는 join 이후에 쓴다.

기존 9조건에 아래 4조건을 full/minimal 각각 실행하여 기본 fault matrix는 **17 runs**다.

| 조건 | 주입 | 확인할 동작 |
| --- | --- | --- |
| monitor-overrun | Body 끝에서 6 ms sleep | Plant가 monitor 복귀 전에 보호 |
| plant-overrun | Body 끝에서 6 ms sleep | Monitor가 정지 중 검출, physics 보호는 복귀 후 |
| monitor-stall | Body 끝에서 120 ms sleep | 독립 보호와 backup 수신 상실 검출이 정지 중 진행 |
| io-overrun | 두 owner가 각각 6 ms sleep | 복귀 후 late completion을 정상으로 숨기지 않음 |

주입은 첫 phase>=1100 ms에서 한 번이다. 검출/적용 margin, latch 유지, 유한 torque 감소·최종 floor를 검사한다.
실제 Actual의 bytes/source/admission 검사도 유지한다. 보호 전이에서 보고를 억제할 수 있으므로
Actual sent+expired는 **Drive의 reported job 수**와 맞춘다. 정상은 기존 240개다.
Plant 지연에서 발생한 expiry는 첫 후속 cycle에만 허용한다. 관련 없는 expiry나 ECU/RX miss는 FAIL이다.

## 배치 비교

`guard-placement`는 서로 다른 allowed CPU A/B/C를 선택하고 SCHED_OTHER를 유지한다.
C는 가능하면 A/B와 다른 physical core를 선택한다. 정상 full/minimal·회당 4 layouts를 순환하고 trace 순서를 교대한다.

| Layout | CPU A | CPU B | CPU C | 부하 |
| --- | --- | --- | --- | --- |
| io-control | RX·monitor·plant | ECU 4개 | 사용 안 함 | B |
| rx-separated | Monitor·plant | ECU 4개 | RX | B |
| guard-separated | RX·plant | ECU 4개 | Monitor | B |
| guard-baseline | RX·plant | ECU 4개 | Monitor | 없음 |

부하는 기존 10 ms 중 7 ms wall busy window 한 process다. 실제 affinity/policy·CPU 소비·실행 생존을 검증한다.
더 많은 CPU가 항상 낫다고 가정하지 않는다. 실패와 모든 유효 표본을 보존하고 이전 schema의 수치와 합치지 않는다.
설정은 [reference profile](../../profiles/reference.yaml), 실행/해석은 [학습 안내](../learning/m3_owner_cycles.md)에 둔다.
전체 32개 requirement/29개 system TC는 여전히 NOT RUN이다.
