# ADR-0011: 회생제동을 포함한 Drive–Brake 설계

Date: 2026-10-13. Status: **회생제동 포함 범위 ACCEPTED / 상세 설계 초안 / 구현 PLANNED / 시험 NOT RUN**.
Owner: 학습자(project owner). 근거: 사용자의 회생제동 포함 설계 결정.

후속 [EV-01 / ADR-0014](ADR-0014-ev-functional-scope.md)가 별도 BMS 제외/충전 fixture만
사용하는 범위를 대체한다. 아래 최초 결정은 역사적 기록이며 RG-01의 토크·배분 계약은 유지한다.

## 문제

Reference Baseline v0.1은 Drive를 전진 구동 토크, Brake를 마찰제동 압력으로 정의하고
회생제동을 제외했다. 전기 구동 SIL을 확장하려면 회생 토크와 마찰제동을 함께 배분하고,
회생 가용량의 변화와 실제 회수 에너지를 구분할 계약이 필요하다.

## 결정

- 확장 ID는 **RG-01**이다. 전진 ODD는 유지하고 회생제동을 포함한다.
- Drive Command/Actual은 driven-wheel 기준 signed motor torque(N·m)를 사용한다.
  전진 구동은 양수, 전진 중 회생 감속은 음수다. 후진 요구를 추가하는 것은 아니다.
- Brake Command/Actual은 마찰제동 압력(Pa)을 유지한다. 현재 Brake DBC/codec을 변경하지 않는다.
- Zone은 총 제동 요구를 공통 wheel 기준으로 변환하고, 유효한 회생 가용량 안에서
  Drive와 Brake에 배분한다. Drive는 actual torque와 회생 가용량/유효성 정보를 제공한다.
- 회생 가용량 0과 critical Drive Actual 상실은 구분한다. Critical loss의 FAIL_SAFE와
  Host tick gate는 유지한다. Drive command timeout은 양수·음수 demand 모두 무효화하고
  local **zero motor torque target**을 선택한다.
- 첫 모델은 속도·충전 수용 한계의 단순 모델과 actual 기반 에너지 집계를 포함한다.
  상세 배터리 화학 모델, 별도 BMS ECU, ABS/ESC 및 바퀴별 배분은 이번 확장에 추가하지 않는다.

## 영향과 미결정 사항

[회생제동 설계](../icd/regenerative_braking_design.md)에 의미, 배분, 보호 및 시험을 정의한다.
Drive wire의 signed scaling/layout, capability freshness, 압력→토크 calibration,
응답/전환 budget, 효율과 충전 한계는 TBD-01/02/03/06/07에서 결정한다.
통합 속도 입력의 전달 경로는 TBD-01/05다.
기존 32-byte 배치가 Drive 추가 정보를 충분히 표현하는지는 M1에서 검토한다.

SYS-SAFE-004를 v0.2로 개정하고 SYS-CTRL-008/009와 SYS-SAFE-005를 v0.2로 추가한다.
기존 M0 v0.1의 15개 exit review 결과는 역사적 기록으로 유지하며 RG-01에 적용하지 않는다.
기존 Steering/Brake wire 시험은 회생제동 검증 증거가 아니다.

## 구현 순서

Brake application receiver → 회생을 포함한 Drive wire/receiver → M2 actuator·충전 수용 모델
→ M4 Zone 배분 → M6 Simple Plant → M7 CARLA mapping 순서로 진행한다.
이번 결정은 설계 문서 변경이며 회생제동 runtime 구현이나 시험 완료를 뜻하지 않는다.
