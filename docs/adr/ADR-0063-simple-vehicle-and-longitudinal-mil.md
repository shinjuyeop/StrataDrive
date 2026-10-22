# ADR-0063: M6 actual 기반 Simple Vehicle와 첫 종방향 MIL

Date: 2026-10-22. Status: **M6 첫 구현 경계 채택 / 유한 검증 결과는 evidence 참조**.

사용자가 완료된 Rear 연결 뒤 M6 진행을 요청했다. M5 3-vECU Host 수용과 과거
DDS/TSan OPEN을 보존하면서 ADR-0052의 M6 plant/MIL 순서로 진행한다.

1. 단일 persistent physical process에 SimpleVehicle를 선택형으로 추가한다.
   기존 실제 actuator 모델의 값만 운동 입력으로 사용하고 계산한 wheel speed를 기존
   Rear Drive 센서/CAN/P05/SOME/IP/Central validator 경로에 되돌린다.
2. flat forward-only inertial longitudinal + kinematic bicycle을 첫 설명 가능한 모델로
   택한다. geometry/force scale은 allocator와 일치, road force는 명시적 가정이다.
   모델 state/source는 ECU rejoin으로 reset하지 않는다.
3. 첫 MBD 도구(TBD-16)는 작은 Python 실행 모델로 결정한다. PI+reference feedforward,
   conditional anti-windup·slew·invalid latch·새 INIT를 고정 vector/closed-loop로 검사한다.
   Simulink/생성 C++/제품 tool qualification은 채택하지 않았다.
4. 실제 이동에서 드러난 NormalStop 인계는 standing-hold pressure 자체의 도달과 기존
   dwell을 요구해 수정한다. 명령/허가/감시 시한과 Leaf monitor를 완화하지 않는다.

구체 수식·책임/clock·parameter·실행 flag는 [ICD](../icd/simple_vehicle.md),
사전 조건·시도별 원본·결과는 [M6 근거](../test-plan/evidence/m6_simple_vehicle/README.md)에 둔다.
기존 M5 기본 fixture/범위는 유지하며 M6 적용을 opt-in으로 구분한다.

이 결정은 실제30km/h 차량 SIL closed-loop나 M6 전체 종료가 아니다. 현재 실제 ECU의
vehicle demand는 시나리오 fixture다. M6 MIL은 독립 Python 근사 plant이며 기존 C++
actuator/EV library를 실행한 것과 구분한다. C++ controller·공통 vector 동등성·실제 Central
속도 폐루프는 ADR-0052의 M8 책임이다. CARLA(M7), Target/Jetson, M4 전체 수용은 별도다.

공식 운동학/anti-windup 자료는 ICD에 링크했다. 값과 알고리즘은 이 프로젝트의 SIL
선택이며 해당 제품/차량의 calibration이나 성능 보증을 가져온 것이 아니다.
