# ADR-0021: Central 조정 기능과 대등한 Front/Rear Zone

Date: 2026-10-14. Status: **배치 변경 ACCEPTED / protocol·runtime PLANNED / system 시험 NOT RUN**.
Owner: project owner. 사용자 요청으로 Front의 차량 전체 조정 기능을 Central의 별도
component로 이동하고 Central↔Front, Central↔Rear를 독립 application 경로로 채택한다.

## 변경 이유와 범위

ADR-0015의 Front는 Zone gateway와 VCU 역할을 함께 맡았다. 차량 전체 요구 배분과
지역별 연결 책임을 더 명확히 학습하기 위해 이제 둘을 분리한다.
**Front/Rear 두 Zone, 담당 Leaf, 단일 조정 owner, Central–Zone–Leaf 계층은 유지한다.**
Front 경유 Rear command/status, Front vehicle management/allocation/session/Host bridge 배치만
이 결정으로 대체한다. M0 문서 결과와 기존 M1/M2 실행 결과를 새 topology 증거로 소급하지 않는다.

## 결정

- Central의 별도 `vehicle_management`가 전원 lifecycle·정상 주행 허가를 판단한다.
- Central의 별도 `control_allocation`이 Controller의 vehicle-level 요구를 한 번만 배분한다.
  ADAS planner/controller와 VCU 기능의 interface·validation·fault 책임은 분리한다.
- Central `session`이 trusted Epoch/INIT를 소유한다. 기존 Linux EpochStore library는 재사용한다.
  현재 M1 harness의 local 발급 검사는 유지하고 실제 coordinator/배포 경로는 M4/M5에 구현한다.
- Central `feedback_bridge`가 두 Zone의 per-source actual/EV status를 집계해 Central consumer와
  Host에 전달한다. 집계 주기나 다른 Zone heartbeat로 누락 원천의 age/validity를 덮지 않는다.
- Front는 Steering/aggregate Brake, Rear는 Drive/BMS의 gateway·validation·monitor·local protection을
  담당한다. 두 Zone은 Central로 직접 status를 보고하고 각자 scoped command/session을 받는다.
- 정상 제어/feedback/INIT 경로에 Front↔Rear application relay를 요구하지 않는다.
  향후 peer service는 별도 계약과 근거가 필요하다. Ethernet switch/backbone의 물리 forwarding과
  application 배치가 같은 개념은 아니다. 물리 배선/가상 network 방식은 TBD-05/15다.
- Zone/Leaf는 Central 응답 없이 local protection을 계속 수행한다. 하나의 Zone·link 정지가
  다른 Zone의 link failure를 뜻하지 않지만 차량 전체 normal gate는 원천 상실을 보고 FAIL_SAFE로 간다.
  Central/coordinator redundancy/failover와 실제 보호 출력은 별도 범위/TBD다.

## Interface와 요구 개정

| 이전 | 현재 |
| --- | --- |
| IF-DDS-VEHICLE-CMD: Controller→Front | IF-CENTRAL-VEHICLE-REQUEST: Controller→Central allocation |
| IF-DDS-POWER-REQUEST: Central→Front | IF-CENTRAL-POWER-REQUEST: lifecycle requester→Central vehicle management |
| Front→Rear command / Rear→Front status / Front↔Rear session | Central↔Front 및 Central↔Rear 독립 command/status/session |
| Front aggregate→Host | 각 Zone→Central feedback bridge→Host |

기존 IF-DDS-REAR-CMD/STATUS/SESSION ID는 유지하고 endpoint 의미를 개정한다.
대칭 Front CMD/STATUS/SESSION ID를 추가한다. IDL/배포 schema가 아직 없으므로 CAN wire 변경은 없다.
SYS-ARCH-003, SYS-CTRL-008, SYS-SAFE-005, SYS-EV-003을 **v0.5**로 개정한다.
기존 requirement 수/ID와 29개 TC는 유지하며 owner/경로/변형을 변경한다.
100 ms 검출 상한, per-source freshness/parent expiry, local 보호와 actual-only plant gate는 유지한다.

## 검증과 후속

[현재 Zone 계약](../architecture/zonal_partition.md), [interface 목록](../icd/interface_overview.md),
[요구 개정](../requirements/system_requirements.md), profile과 traceability/scenario/TC를 일치시킨다.
이번 변경은 문서/설계 데이터와 owner 설명의 변경이다. 이미 구현한 CAN codecs/receivers와
Steering/Brake component 모델, BMS typed parent 검사는 그대로 재사용한다.
M4는 Central 단일 coordinator + 각 Zone routing/local monitor, M5는 독립 DDS 링크·trusted INIT·
Host bridge, M6/M7는 physical model/closed-loop를 검증한다. Runtime/system Result는 NOT RUN이다.

참고: [Bosch Zone ECU](https://www.bosch-mobility.com/en/solutions/control-units/zone-ecu/)와
[NXP zonal architecture](https://www.nxp.com/company/about-nxp/smarter-world-blog/BL-HOW-ZONAL-EE-ARCHITECTURES)는
중앙 기능과 지역별 연결 계층을 설명한다. 이 배치는 StrataDrive의 선택이며 모든 차량의
동일한 물리 topology나 안전성/고장 독립성을 보장하는 규칙으로 해석하지 않는다.
