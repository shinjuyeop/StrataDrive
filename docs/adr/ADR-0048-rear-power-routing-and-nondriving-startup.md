# ADR-0048: Rear 전원 전달과 명시적 non-driving startup

Date: 2026-10-19. Status: **Host component·분리 vCAN 구현/시험 / 전체 runtime 후속**.
[ADR-0047](ADR-0047-zone-can-egress-and-local-protection.md)의 정상 명령 gateway와 별도로
Rear의 PowerRequest·DrivePermission·BMS limits/status를 연결한다. 기존 CAN layout·시한은 유지한다.

## 문제와 결정

프리차지는 실제 bus 전압과 접점으로 완료를 확인하므로 정상 torque command timeout인 80 ms보다
길 수 있다. INIT부터 torque stream을 요구하면 시동 중 fault가 나고, 가짜 zero torque를 보내면
정상 배분 sequence와 source/권한 의미가 섞인다. DriveController에 명시적 `NonDriving` 시작을 추가한다.
기존 caller의 기본값 `Immediate`와 이전 수신/보호 동작은 유지한다.

NonDriving은 normal torque receiver만 아직 시작하지 않는다. Limits·Inhibit permission·local HV/speed는
계속 감시한다. 필수 입력 최초 대기 80 ms, 이후 각 source/dependency/expiry 상실 latch를 유지한다.
미리 도착한 torque packet은 receiver를 arm하거나 sequence를 소비하지 않는다. AllowNormal이 먼저
도착하면 CommandsNotArmed로 latch한다. 실제 HV/inverter 준비와 fresh Inhibit 상태에서 trusted
coordinator가 `arm_normal_commands`를 호출해야 정상 command 대기를 시작한다. 같은 Epoch에서
첫 normal sequence는 0이며 physics·feedback·BMS 수신 상태는 reset하지 않는다.

## RearPowerGateway 계약

`interfaces/central/power_commands.hpp`에 lifecycle root와 VehicleManagement output 타입을 둔다.
`RearPowerGateway`는 trusted `authorize_request`로 별도 공급받은 lifecycle identity/action과
Central 자식 요청을 대조한다. 수신 CAN에서 parent를 추론하거나 vehicle demand root로 대체하지 않는다.

PowerRequest·DrivePermission·PowerLimits·PowerStatus는 독립 receiver와 마지막 accepted expiry를 가진다.
Source age 50 ms, 해당 dependency age 70 ms, 최초 누락 80 ms를 유지한다. Age는 inclusive,
expiry는 exclusive다. 이전 accepted deadline 상실을 새 입력 수용 전에 검사한다.
유효 0과 unknown, packet Accepted와 항목별 Usable을 구분한다.

| 자원/처리 | 결정 |
| --- | --- |
| 새 accepted 입력 FIFO | 8; overflow는 backlog 폐기·latch·Rear 보호 |
| Dispatch | 최대 8개 검사, stream별 최신 값; Inhibit 우선, limits→PowerRequest→AllowNormal |
| 송신 | 한 dispatch 최대 3 frame, 원래 metadata/expiry 보존; stream별 downstream P05만 별도 진행 |
| Actual status / 실제 송신 power history | 각각 8 / 16개, 원래 identity와 expiry로 검증 |
| 각 write | 전후 source/expiry/clock 확인; 실패·만료 뒤 normal 재전송 없음 |
| 보호 | Drive Zero 선택 + Power local fault/inhibit; Pending은 poll당 한 번 재요청 |

AllowNormal은 별도 arm과 실제 송신된 Enable의 ACK를 모두 요구한다. 참조 PowerStatus의 정확한
sequence/source, HV_READY·actual 접점·condition/voltage, 정상 sender mode를 확인한다.
ACK의 causal sequence와 accepted request source는 실제 전달한 Enable child와 일치해야 한다.
Grant는 status·ACK parent·현재 root의 남은 lifetime을 넘지 않는다. Enable 요청 자체는 HV 준비 증거가 아니다.
Arm 뒤 actual Ready나 정상 PowerStatus mode 상실도 보호에 연결한다.

## 검토한 DEGRADED envelope

기존 blanket rejection은 정차 중 실제 Drive의 `Disabled` regen capability와 정상 BMS derating까지
차단했다. 다음 두 경우만 Central input health/normal readiness에서 허용한다.

| Sender | NormalPath + DEGRADED의 추가 필수 조건 |
| --- | --- |
| Drive Actual | known torque −200…300 Nm, speed 0…100 rad/s, capability 0…200 Nm; torque/speed/cap source ≤30 ms, cap input ≤70 ms이며 source 이하; 알려진 Nominal/MotorOrSpeedLimited/ChargeAcceptanceLimited/Disabled reason, Disabled면 cap=0 |
| BMS PowerLimits | charge/discharge 모두 Usable·known·finite 0…100000 W, source ≤50 ms/input ≤70 ms; Nominal/SocLimited/TemperatureLimited/ElectricalLimited/Disabled 중 알려진 reason, Disabled면 해당 값=0, 최소 한 방향은 non-Nominal |

Epoch/session/원래 dependency·quality 검사는 그대로 적용한다. Steering·Brake·Zone health·PowerStatus의
DEGRADED는 여전히 미검토로 차단한다. FAIL_SAFE/LocalProtection·unknown·stale을 허용하지 않는다.
유효 제한 0이 주행 동력을 보장하는 것은 아니며 allocator와 Drive가 실제 power/torque gate를 계속 적용한다.
새 실차 calibration 또는 timing budget 확정이 아니라 현재 Host fixture의 제한된 허가 정책이다.

## 신뢰 경계와 남은 작업

`simulation::RearPowerControl`은 trusted gateway TX에서 발급한 exact frame/context를 16개 보관한다.
실제 CAN RX는 일치하는 미만료 발급 기록으로만 별도 parent를 회수한다. Payload/ID/length/BRS/ESI를
대조하며 Linux TX/RX 표시가 다른 optional FDF bit 0x04만 비교에서 제외한다. INIT은 기록을 비우며
gateway/control INIT만으로 Leaf를 reset하지 않는다. Arm/staging은 두 Leaf의 application Epoch도 확인한다.
이는 same-host SIL sideband이며 DDS 인증이나 원격 Leaf 신뢰 프로토콜이 아니다.

Power 보호 ACK는 local fault/inhibit 선택이다. 실제 current dwell·접점 open·bus discharge는 기존
PowerController/물리 모델이 수행하며 즉시 contactor open 또는 실제 torque 0으로 표시하지 않는다.
기존 active Drive의 Inhibit 후 fail-safe/새 INIT 정책은 유지한다. 전 차량 graceful shutdown으로 확대하지 않는다.

Front non-driving startup·전체 coordinator의 독립 ingress/status/rejoin·coordinated stop, 기존 32-byte
normal CAN의 remote Leaf composite lease/보호 전달, DDS·전체 workload timing·Target은 후속이다.
시험·개발 실패와 정확한 fixture 경계는 [학습 기록](../learning/m4_rear_power_startup.md)에 둔다.
