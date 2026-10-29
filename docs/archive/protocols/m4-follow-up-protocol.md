# M4 timing 보완·구조 정리 후속 시험 프로토콜

Date: 2026-10-20. 결과 실행 전에 고정한다. 기존 [48회 프로토콜](m4-fault-timing-protocol.md)과12fc4a5의41 PASS/7 FAIL은 변경하지 않는다.

1. 원본48회 중7 FAIL의 모든 slot/설정/load·첫 검출·주입 전 보호를 정적 감사한다. 재실행/판정 변경은0회다.
2. 공통 release origin·hot audit/trace 사전 할당·requested wake 관측을 작은 기능 수정 commit으로 구분한다.
   원래2ms opportunity/4ms deadline·miss/skip·검출/물리 적용10ms·100ms fault 기준은 유지한다.
   기존 FIFO 지연0.722310ms와1.528864ms phase crossing을 logical replay하고 공통 위상 대조를 검사한다.
3. 수정 후 전체 normal/ASan·UBSan, native TSan7개와 같은48회 cohort를 새 commit/새 raw directory에서 실행한다.
4. 이후 책임/계약/복구 모듈/CTest label 분리는 별도 동작 보존 commit으로 한다.
   전체 normal/ASan·UBSan 및 TSan, 동일48회 native cohort를 별도 실행한다. 두 cohort를 합쳐 실패를 숨기지 않는다.

각 cohort 조건/순서/3회 반복/CPU0·1/priority/load/2.54s·lead100ms·1211 slots·tail20ms는 기존 runner/프로토콜과 같다.
정상은 원래 zero miss/skip와 기능/설정/load PASS, 고장은 원래 독립 검출/물리 적용과 주입 전 다른 실패 없음이 기준이다.
Normal/sanitizer·논리/실제 시각을 분리한다. Timing 동안 build/다른 시험을 병행하지 않는다.
Requested wake는 기존 execution CSV 뒤에 열을 추가한다. Audit buffer growth는 JSON timing 안에 추가하며 기존 열/키/CLI는 유지한다.
Miss를 후속 heartbeat로 메우지 않고 fresh source/parent/epoch/expiry·latch/새 세션·모델 보존 계약은 바꾸지 않는다.

Logical 기준은12fc4a5 normal 원본의35개 physical trace를 byte 단위 대조한다. Event/execution의 관측 열 추가는 별도로 기록한다.
구조 정리 전/후도 같은 physical trace와 상태/판정을 대조한다. 환경이 다른 wall 수치를 byte 동등으로 비교하지 않는다.
권한/환경 BLOCKED는 분모에 남기고 기존 OPEN-M3와 OPEN-M4-TIM-01을 새 성공만으로 닫지 않는다.
Remote 계약·M4 exit는 별도 검토하며 전체 system TC/Target·학습자 review 상태는 올리지 않는다.
