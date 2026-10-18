# M4 Central 정상 주행 준비 조건

Date: 2026-10-19. Status: **첫 순수 판단 component 구현·시험 / coordinator 통합 전**.
[ADR-0021](../adr/ADR-0021-central-coordination-and-parallel-zones.md)의 Central
`vehicle_management`를 시작한다. M3 전체 수용과 Target timing은 계속 PENDING이다.

## 무엇부터 만드는가

이전 EV 예제는 시험용 코드가 power request와 DrivePermission을 만들었다.
실제 Central에서는 먼저 **필요한 입력이 모두 준비됐는가**, 다음으로 **현재 요청과
차량 상태에서 주행을 허용해도 되는가**를 판단해야 한다. 이번 코드는 첫 질문만 다룬다.

코드는 [API](../../central/vehicle_management/normal_drive_readiness.hpp),
[구현](../../central/vehicle_management/normal_drive_readiness.cpp),
[단위 시험](../../tests/unit/normal_drive_readiness_test.cpp)에 있다.
`normal_drive_readiness` library는 socket·thread·plant를 소유하지 않는다.
새 CLI/demo를 추가하지 않았으며 기존 EV fixture의 허가 코드는 아직 교체하지 않았다.

| 입력 경로 | 각각 필요한 입력 | 첫 판정 정책 |
| --- | --- | --- |
| Front | Zone 자체 health | 올바른 session, NORMAL/NormalPath, 명시적 ready |
| Front | Steering Actual, Brake Actual | 각각 fresh·known actual, INIT 또는 NORMAL, local protection 없음 |
| Rear | Zone 자체 health | Front와 별도로 확인 |
| Rear | Drive Actual torque | fresh·known torque, INIT 또는 NORMAL, local protection 없음 |
| Rear | 원래 BMS PowerStatus | 정상 sender, HV_READY, 실제 main 접점 closed·precharge open·known bus, LV/interlock/isolation 정상·충전 연결/fault 없음 |
| Rear | 원래 BMS PowerLimits | 정상 sender, charge/discharge 양쪽 usable·finite·0 이상 |

Steering angle 0, Brake pressure 0, Drive torque 0과 BMS charge limit 0은 알려진 값이다.
Unknown으로 대체하지 않는다. Charge limit 0은 회생 불가를 뜻할 수 있지만 정상 구동 전체를
무조건 막지는 않는다. 배분기와 Drive local gate가 방향별 실제 한계를 적용한다.
Wheel speed/regen capability는 후속 배분 입력이며 이번 준비 판정의 torque Actual과 구분한다.

## 준비됨과 허가됨의 차이

결과는 모든 차단 이유와, 모두 준비됐을 때 결정에 사용한 가장 오래된 원천 시각이다.
Front heartbeat가 새로 들어와도 Steering Actual이 없으면 `SteeringActual` 차단이 남는다.
Rear 장애는 Rear 입력으로 따로 보고하며 Front의 데이터를 지우거나 Front 연결 장애로 바꾸지 않는다.
필수 source가 하나라도 불가하면 차량 전체 준비 결과는 false다.

**`ready()`는 DrivePermission도 차량 NORMAL 상태도 아니다.** 이 함수에는 상태 기억이나
FAIL_SAFE 복구 기능이 없다. 다음 vehicle-management owner가 trusted INIT·원래 lifecycle
요청·parent expiry·고장 latch를 함께 검사해야 한다. 장애 뒤 입력이 새로 보이는 것만으로
그 owner가 NORMAL로 자동 복귀해서는 안 된다. 함수의 준비 결과만 직접 wire 허가로 쓰지 않는다.

초기 known Actual을 허용하는 이유도 이 구분에 있다. Leaf가 허가 전에 0 torque 같은
non-driving Actual을 발행할 수 있어야 한다. 모든 Actual이 NORMAL이 될 때까지 기다리면
Drive는 허가를 기다리고 Central은 Drive의 NORMAL을 기다리는 순환 의존이 생긴다.
Zone 자체 health와 BMS의 정상 상태는 별도로 요구한다. 검증된 DEGRADED 정책은 아직 없으므로
이번 준비 조건에서는 DEGRADED를 허용하지 않는다.

## 원천 시각과 수신 책임

입력은 매 판정 cycle의 `current_sample(now_ns)` 결과다. Receiver의 P05·sequence·range 검사와
timeout/continuity latch를 통과해야 한다. `last_accepted()` 진단 이력을 current sample처럼
포장하지 않는다. Zone health도 향후 각 Zone의 trusted ingress monitor가 검증해야 한다.
새 `ZoneHealthSnapshot`은 in-process 계약이며 DDS schema/완성된 health receiver가 아니다.

| 항목 | 이번 component의 최대 age |
| --- | --- |
| 각 Zone health source | 30 ms — 첫 in-process 후보, 실제 Zone 통신 budget은 TBD-15 |
| 각 actuator Actual source | 30 ms — 기존 actuator receiver 기준 |
| BMS source | 50 ms — 기존 critical EV 기준 |
| BMS 원래 physical/input dependency | 70 ms — 기존 EV dependency 기준 |

Age 경계는 포함하고 다음 1 ns부터 차단한다. 다른 Epoch, 세션 이전·미래 source,
`input > source`, unknown/stale quality도 차단한다. 설정은 기준보다 좁힐 수 있으며
임의로 넓혀 검사에 통과시키지는 않는다. Wire/physical calibration은 해당 receiver 책임이다.

예를 들어 현재 100 ms에 PowerStatus source가 100 ms여도 그 physical input이 20 ms라면
dependency age 80 ms로 차단한다. 새 전송 시각이 오래된 측정을 갱신하지 않는다.
모든 입력은 현재 같은 monotonic clock domain을 전제한다. 분산 clock mapping/skew·monitor
주기·queue budget·실제 검출 상한은 M4/M5 통합에서 검증할 항목이다.

## 검사와 다음 순서

새 unit 16개는 7개 필수 source 각각의 상실·다른 Epoch·미래/과거·경계·fault를 반복 확인한다.
Known zero/INIT actual, stale dependency 재발행, 양방향 limits quality, 충전 연결·actual 접점,
전체 차단 이유와 oldest input도 검사했다. Normal·ASan/UBSan 각각 전체 C++ **539/539 PASS**다.
Wire는 바꾸지 않았으며 이번 vCAN·wall-time 통합 실행은 없다. 시스템 요구사항/TC는 NOT RUN이다.

```sh
cmake -S . -B build/m4-readiness -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m4-readiness -j 4
ctest --test-dir build/m4-readiness -R '^NormalDriveReadiness\.' --output-on-failure
```

다음은 이 결과를 사용하는 **stateful vehicle-management owner**다. Trusted session/INIT와
상위 lifecycle 요청을 받아 power Enable/Shutdown을 만들고, actual power 응답과 요청 identity를
대조한 뒤 parent deadline을 넘지 않는 허가를 만든다. INIT 동안의 power checks와 normal torque
허가, critical loss의 FAIL_SAFE latch와 명시적 재초기화를 따로 시험한다.
그다음 allocation 및 Front/Rear routing/local monitor를 연결하고 DDS transport는 M5에서 추가한다.
