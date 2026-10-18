# ADR-0045: 첫 Central 배분과 회생·마찰 전환

Date: 2026-10-19. Status: **Host component 구현·시험 / 차량·Zone/runtime 통합 후속**.
[RG-01](../icd/regenerative_braking_design.md), [ADR-0021](ADR-0021-central-coordination-and-parallel-zones.md),
[Central 허가 owner](ADR-0044-central-vehicle-management-lifecycle.md)의 후속이다.
TBD-02/03/06의 첫 fixture 결정을 기록하며 최종 차량 calibration/보호 matrix를 확정하지 않는다.

## 입력·권한과 책임

`central/control_allocation`은 단일 owner, 20 ms 외부 clock 기반 normal-path runnable이다.
VehicleRequest의 acceleration·curvature·normalized service braking·명시적 standstill hold와 원래 Epoch/Sequence/Source/Expiry를 받는다.
Target speed 추종/PID는 상위 Controller, local motor gate/압력 response monitor와 보호는 Leaf/Zone의 책임이다.
배분기는 plant·socket·clock issuance를 소유하지 않는다.

현재 trusted VehicleManagement가 NORMAL/allow 상태이고, 독립 BmsReceiver의 current AllowNormal과 별도 lifecycle
parent가 유효해야 한다. Vehicle request root와 permission lifecycle root는 다른 identity다.
필수 Zone/actuator/power/양방향 BMS feedback은 기존 정상 준비 조건으로 다시 검사한다.
Wheel speed는 별도 fresh 입력이며 Drive/Brake actual source skew는 최대 20 ms다.
Capability는 source 30 ms/input 70 ms로 검사하고 실제 torque validity와 구분한다.
Cached acquisition을 새로운 packet 시각으로 바꾸지 않는다.

상위 요청은 source age 30 ms·lifetime 최대 60 ms, 첫 sequence 0..9/후속 증가량 1..10이다.
같은 identity의 내용·source·expiry 변경은 거부한다. Active root와 이전 출력의 **필수** 지원 입력 만료를 새 입력보다 먼저 검사한다.
출력 3개는 allocator Sequence/Source와 vehicle-root CausalSequence를 갖는다. 원래 root, oldest used input과
모든 권한/source/dependency 중 가장 빠른 expiry는 **필수 scoped sideband**다. 기존 32-byte CAN payload에는
이 sideband가 없으므로 Zone admission에서 보존·검사하기 전에는 end-to-end parent expiry 검증으로 표시하지 않는다.

## 첫 배분 정책

| 기능 | 정책 |
| --- | --- |
| 조향 | rear-axle curvature → `atan(wheelbase × curvature)`, angle 한계 적용 |
| 추진 | `mass × wheel radius × acceleration`; DC `Tω/η + kT² + reserve`와 motor mechanical power/torque로 제한 |
| 서비스 제동 중재 | 음수 acceleration의 제동 토크와 normalized braking 토크 중 큰 값; 더하지 않음. 양수 추진보다 우선 |
| 회생 | 새 제동 시작 시 valid capability·현재 BMS charge/motor power 한계 내 우선 배분 |
| 마찰 | 동일 wheel Nm 기준에서 배분한 회생 몫과 실제 남은 회생 중 큰 값을 빼고 Pa로 변환 |
| 저속 | 2 rad/s 진입·3 rad/s 이탈 hysteresis로 새 회생 억제 |
| Hold/출발 | 명시적 hold + 0.5 rad/s 이하에서 진입, 요청을 clear할 때까지 유지; 해제 후 actual pressure/negative torque가 release 허용 범위에 들기 전 양수 추진 억제 |

첫 제동 구간에서 회생 목표는 증가시키지 않는다. Capability/요구 감소나 저속 전환으로 줄인 회생을
같은 제동 구간에서 자동 복구하지 않는다. 실제 release를 관측하고 다음 제동이 시작돼야 다시 배분한다.
이는 지연이 다른 두 actuator 사이의 반복 handoff를 제한하는 보수적 첫 정책이며 OEM 최적 배분을 주장하지 않는다.
Capability가 unknown/stale이면 회생 목표 0과 마찰 경로를 사용하되 critical torque/Brake actual 상실은 FAIL_SAFE다.
Capability가 다음 nominal cycle까지 유효하지 않으면 미리 Expiring으로 분류해 회생 목표를 0으로 줄인다.
허용 owner gap 중 optional capability만 만료됐어도 새 frame으로 회생 목표를 복구하지 않고 마찰 경로를 사용한다.
Optional 만료 자체를 필수 Actual/허가 만료와 같은 FAIL_SAFE로 바꾸지 않는다.

초기 회생이 목표까지 올라가는 동안은 계획한 몫을 예약하고 실제 deficit를 기록한다. 회생이 줄어들 때는 아직 남은
실제 회생을 제외해 마찰을 명령한다. 실제 압력이 바로 따라온다고 가정하지 않는다.
Pressure/torque/angle은 wire step 안쪽으로 양자화한다. Command를 actual/회수 에너지로 사용하지 않는다.

## 응답·보호 경계

`Bactual = K × Pactual − Tdrive_actual`로 signed net braking을 관측한다. 양수 추진 잔여분도 포함하며
`max(0,Brequest−Bactual)`와 반대 방향 excess를 각각 기록한다.
원래 Drive/Brake acquisition 중 오래된 시각으로 50 Nm 초과 오차의 연속 dwell을 검사한다. Cached 읽기는 dwell을 진행시키지 않는다.
첫 dwell 700 ms는 M2 fixture의 전체 +300→−200 Nm 변화 500 ms + delay 50 ms와 관측/control 여유를 위한
**component 시험값**이다. 실제 차량 허용 오차/정지 시간이나 critical loss 100 ms 상한을 바꾸는 값이 아니다.
기존 Leaf의 더 빠른 local response monitor도 변경하지 않는다.

압력 포화로 배분 가능한 제동 토크가 부족하면 부족분을 기록하고, 응답 budget 위반/권한·필수 입력 상실도 latch한다.
이때 새 normal command는 없고 `protection_required`를 반환한다. 이를 Brake release/모든 actual 0/안전 정지 성공으로 해석하지 않는다.
별도 coordinator/Zone local protection 연결과 fault별 실제 반응은 후속이다. Recovery는 더 큰 Epoch의 trusted INIT다.

최종 geometry·타이어/도로·공기저항/경사·관성과 차량 feedback loop는 M6/M7에서 검증한다.
현재 VehicleManagement가 거부하는 BMS sender DEGRADED 정책은 이번에 완화하지 않는다. 첫 배분의 valid zero/limited
constraint 시험은 명시적 정상 sender fixture이며, 실제 BMS SOC/온도 derating과의 허가 envelope 검토는 통합 후속이다.
임의 보호 요구를 normal driving permission 없이 이 경로로 보내는 우회도 추가하지 않는다.

수치/재현/시험 범위는 [학습 안내](../learning/m4_control_allocation.md), 보정 fixture는
[Reference YAML](../../profiles/reference.yaml)의 `m4_allocation_fixture`에 기록한다. YAML runtime loader는 없다.
전체 시스템 요구 32개/TC 29개 NOT RUN과 M3 기존 실패는 유지한다.
