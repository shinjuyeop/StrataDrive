# ADR-0014: 전기차 기능·상태·통신을 재현하는 SIL 범위

Date: 2026-10-13. Status: **EV-01 포함 범위 ACCEPTED / 상세 설계 초안 / 구현 PLANNED / 시험 NOT RUN**.
Owner: 학습자(project owner). 근거: 실차의 프로세스·구조를 재현한다는 사용자 방향과
기존 계층 유지, BMS 추가, Zone을 거치는 상위 feedback 경로에 대한 대화의 합의.
상세 설계/parameter의 학습자 review는 PENDING이다.

## 문제

RG-01은 회생제동을 포함하지만 충전 수용 한계를 fixture로 주입하고 별도 BMS ECU를
제외했다. 차량의 준비·주행·종료·주요 고장 대응을 학습하려면 충전/방전 한계의
producer, 차량 주행 허가와 전원 상태, 상실 시 반응을 명시해야 한다.

## 결정

- 확장 ID는 **EV-01**이다. Central → Zone → Leaf 계층, 당시 단일 Zone,
  Host–Target 실제 Ethernet, Target 내부 DDS/vCAN, 독립 Thor/Orin 비교를 유지한다.
- Steering/Brake/Drive에 **BMS 논리 vECU**를 추가한다. 상위 status/actual은
  CAN → Zone → Central/Host 경로를 따른다. 로컬 센서 제어는 해당 ECU 안에서 처리한다.
- 차량 관리(VCU 역할)는 Zone 내부의 `vehicle_management`, 구동·제동 배분은
  `control_allocation`, 통신 중계는 `gateway`로 책임을 구분한다.
  별도 VCU 계층/보드를 추가하지 않는다. Central은 요청하고 로컬 주행 허가는 Zone이 판단한다.
- Battery/power plant와 BMS controller를 구분한다. 단순 SOC/전압/전류/온도 모델,
  충전·방전 한계, 프리차지/컨택터 상태와 주행 준비·종료 sequence를 포함한다.
- 핵심 기능의 입력·출력·상태·유효성·고장 반응을 검증한다. 정밀 셀 화학/열화/밸런싱,
  인버터 스위칭/모터 전류 제어, 충전기/DC/DC 회로, 바퀴별 ABS/ESC, body/infotainment는
  상세 구현 범위에서 제외한다. 필요한 전원·열·안정화 가정/연결은 명시한다.
- 기존 0–40 km/h ODD와 classical-first 순서를 유지한다. 전원 lifecycle은 system
  severity와 별개이며 기존 FAIL_SAFE recovery와 Host actual-loss containment를 우회하지 않는다.

## 영향

[EV/BMS 설계](../icd/ev_power_bms_design.md)에 역할, lifecycle, semantic interface,
에너지/시간 원칙과 미결정 값을 기록한다. 기존 M1 six-frame codec/receiver 결과는 유지하며
BMS/power wire, Drive 방전 가용량 전달과 DDS status 확장은 **미설계/미구현**이다.
M1은 기존 남은 수용 항목과 EV interface 추가 작업을 구분하고, M2 모델부터 단계적으로 진행한다.
M3 timing, M4 Zone, M5 DDS, M6/M7 plant, M9 diagnostics와 최종 regression 범위를 확장한다.

SYS-COM-003/004와 SYS-PERF-002를 v0.3으로 개정하고 SYS-EV-001–005를 추가한다.
TC-EV-001–005의 Result는 NOT RUN이다. M0 v0.1 검토나 M1 부분 PASS에 소급 포함하지 않는다.

이 ADR은 ADR-0011의 **별도 BMS ECU 제외/충전 fixture만 사용한다는 범위**를 대체한다.
RG-01의 signed torque, 회생/마찰 배분, 실제 출력 기반 에너지와 critical loss 계약은 유지한다.

후속 [ADR-0015 / ZON-01](ADR-0015-front-rear-zones.md)로 당시 다중 Zone 검토 후보를
최종 Front/Rear 두 Zone 설계로 채택했다. 차량 관리·배분과 상위 feedback 집계는 Front,
Drive/BMS 연결·검증은 Rear다. 단일 Zone component 검증 후 분리하며 peer protocol은 TBD-15다.
이 ADR의 EV 기능/계층 원칙은 유지하고 당시 단일 Zone 배치를 위 결정으로 확장한다.
다중 Zone runtime/TC-ZON은 NOT RUN이다.

## 다음 작은 작업

EV 범위/책임/lifecycle 문서 review → BMS와 power semantic/wire 및 freshness 결정
→ M1 기존 수용 항목과 추가 통신 검증 → M2 actuator + Battery/BMS/power component 모델
→ M4 배분/주행 허가 → M6 Simple Plant → M7 CARLA 순서다.
AUTOSAR/안전 분석은 기존 engineering plan의 작은 pilot/검토로 병행한다.

## 설계 근거와 적용 범위

[NXP 구조 설명](https://community.nxp.com/t5/NXP-Tech-Blog/How-electrification-is-changing-vehicle-architectures/ba-p/1491151)은
물리 Zone과 기능 domain을 구분하며 제어 기능을 별도 ECU, Zone/domain 통합 또는 Central에
배치할 수 있음을 설명한다. [Bosch BMS](https://www.bosch-mobility.com/en/solutions/powertrain/fuel-cell-electric/battery-management-system/)는
셀 감시/배터리 전류 측정과 컨택터 제어를 설명한다. 이를 참고한 StrataDrive의 한 가지
Reference architecture이며 모든 양산차의 공통 ECU 배치나 production safety sequence를 주장하지 않는다.
