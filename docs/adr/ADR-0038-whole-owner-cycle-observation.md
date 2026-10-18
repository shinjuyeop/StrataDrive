# ADR-0038: 감시·물리 owner의 전체 cycle 계측과 RX 시간 대조

Date: 2026-10-18. Status: **Host 계측 구현 / 실행 budget 채택·M3 수용은 후속**.
[ADR-0037](ADR-0037-runtime-owner-cpu-placement.md)의 IO 분리 후에도 RX skip이 남았다.
당시 physical.csv는 physics/capture 일부만 재고 뒤의 fixture CAN TX를 포함하지 않아 전체 비용과 지연 위치를 구분하기 어려웠다.

## 기록 경계

Monitor는 valid-RX snapshot 읽기 전부터 task/stream 검사·보호 flag·상세 trace 기록 뒤까지 잰다.
Plant/fixture는 외부 보호/출력 snapshot 읽기 전부터 physics·actual 적용·센서 발행·Actual/명령/EV CAN TX·trace 기록 뒤까지 잰다.
Periodic sleep과 end 이후 cycle bookkeeping은 body 밖이다. 입력/보호 snapshot을 먼저 취득한 뒤 application/acquisition 시각을 읽는
기존 인과 순서를 유지한다. Body start를 원천 sensor 시각이나 보고 시각으로 대체하지 않는다.

각 owner에 enable부터 stop(2440 ms tail 끝)까지 2 ms 간격의 **1221개 기회**를 미리 할당한다.
실제 body는 시작 시점에 가장 최근 release에 대응시키고 이전 기회는 `ran=0`, 실행 시각은 0으로 남긴다.
Stop을 늦게 관측한 최종 body는 마지막 slot에 기록하며 관측 window 뒤의 예정 slot을 만들지 않는다.
이것은 관측용 grid이며 새 task deadline이나 watchdog latch를 도입한 것은 아니다.

Essential cycle CSV는 full/minimal 양쪽에 쓴다. 실제 sleep target, sleep 호출 직전, 반환 후 body start, 기존 phase, body end를 기록한다.
Full에서만 CLOCK_THREAD_CPUTIME_ID begin/end를 wall endpoints 안에서 읽는다. 서로 다른 thread의 CPU 절대 시각은 비교하지 않는다.
CPU clock 호출을 포함한 계측 비용을 deadline에서 빼지 않는다. CPU delta와 wall delta 차이도 정확한 scheduler 대기 원인으로 단정하지 않는다.
CSV는 기존 owner별 trace와 마찬가지로 실행 종료·join 뒤에 쓴다. 새 thread/executable은 만들지 않는다.

## 분석과 이전 기록

Trace schema는 **4**, CAN wire schema는 **2**다. Reader는 기존 trace schema 2/3을 원래 의미로 계속 분석한다.
`monitor-cycles.csv`, `plant-cycles.csv`의 전체 schedule·interval·CPU clock·expiry 합계를 검증한다.
Full의 원래 monitor/physical phase 및 physics/Actual TX가 전체 body 안에 있는지도 확인한다.

생략된 release는 이전 body 안, 다음 요청 wake 이전, 요청 wake 이후 중 어디에 있었는지 분류한다.
이 분류는 관측 구간의 위치이며 CPU queue/IRQ/VM 원인의 식별이 아니다. Sleep 호출 자체가 이미 늦은 경우도 따로 남긴다.
RX의 모든 miss(실행 생략·늦은 종료·monitor에서 미완료 관측)를 같은 grid의 두 owner slot 및 앞/뒤 phase와 대조한다.
동시 지연을 기록하되 공통 원인을 자동 추론하지 않는다. RX 단독 stall과 여러 owner의 동시 지연을 구분할 자료다.

정상 계약에 실패해도 유효한 cycle/job 관측은 보존한다. 불완전한 owner trace는 이유와 label을 명시해 owner 통계에서 제외하고,
유효한 ECU/RX job 통계는 유지한다. 여러 run 사이의 공백을 interval percentile에 넣지 않는다.
기존 CPU/owner 배치 비교에 owner별 통계·RX 대응을 추가하며 full/minimal·layout은 섞지 않는다.

## 계측 확인용 지연

기존 fault runner에 `monitor-overrun`, `plant-overrun`을 full/minimal 각각 추가한다. 각 owner의 첫 phase>=1100 ms에서
본문 끝에 한 번 **6 ms sleep**을 넣는다. CPU 부하를 늘리는 주입이 아니며 원래 120 ms ECU stall과 구분한다.
6 ms가 whole-body endpoint 안에 포함되고 이후 기회가 생략된 것을 검사한다. Owner deadline은 아직 미채택이다.

Plant 주입은 기다리는 동안 도착한 출력/Actual의 5 ms 시한을 넘길 수 있다. 각 plant cycle에 expiry delta를 기록하고
전체 count와 대조한다. 이 fault case는 expiry가 첫 후속 cycle에만 있는지, Actual sent+expired=240 및 sent=received=accepted인지,
실제로 송신한 Actual이 기존 TX admission deadline 안인지 검사한다. 주입과 무관한 expiry는 실패다.
Normal과 다른 fault의 기존 expiry 0 조건·ECU deadline·수신 age/timeout은 유지한다.
이 주입의 PASS는 지연/폐기 관측의 성공이며 정상 timing 충족을 뜻하지 않는다.

## 후속

작업량·계측이 달라졌으므로 이전 schema의 성능 수치와 합치지 않는다. Actual source/phase/TX/RX의 의미는 유지한다.
관측 후 monitor/plant 전체 cycle budget과 감시 독립성, RT 적용 가능한 실행 환경/Target 검증을 검토한다.
전체 32개 requirement/29개 system TC의 Result는 NOT RUN이며 M3 전체 수용을 선언하지 않는다.
재현은 [전체 cycle 학습 안내](../learning/m3_owner_cycles.md), 실행 결과는 [품질 기록](../quality_policy.md)에 남긴다.
