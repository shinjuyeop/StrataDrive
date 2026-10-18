# ADR-0044: Central 전원 요청·정상 허가 상태 owner

Date: 2026-10-19. Status: **Host component 구현·시험 / 전체 coordinator·Zone/DDS 통합 후속**.
[ADR-0021](ADR-0021-central-coordination-and-parallel-zones.md)의 Central 단일
vehicle-management 책임과 [준비 판정](../learning/m4_normal_drive_readiness.md)을 연결한다.
TBD-06/12/15의 전체 차량·분산 protocol 결정을 완료한 것은 아니다.

## 결정

`central/vehicle_management/VehicleManagement`를 단일 owner·외부 clock 기반 runnable로 둔다.
상위 lifecycle 요청, trusted session, 두 Zone의 현재 입력을 받아 기존 BmsPowerRequest와
DrivePermission을 산출한다. Socket/plant/스케줄링/Epoch 발급은 이 library 밖의 책임이다.
Source/now는 첫 component에서 같은 monotonic clock domain이다.

| 상태 | 의미 / 출력 |
| --- | --- |
| INIT | 현재 session의 known input과 실제 OFF를 검사; KeepOff/Inhibit |
| OFF | main/precharge 실제 접점 open·낮은 bus 확인; 유효 Enable 요청을 기다림 |
| STARTING | Parent 안에서 Enable, 실제 precharge·요청 응답 대조; Inhibit |
| NORMAL | 전체 준비 조건 + live 원래 요청 + 확인된 Enable 응답; AllowNormal |
| STOPPING | Inhibit + Shutdown 요청; 실제 접점·잔류 bus와 Shutdown 응답 대기 |
| STOPPED | 종료 확인, KeepOff/Inhibit; 같은 session의 Enable 재개 금지 |
| FAIL_SAFE | 첫 고장 latch, Inhibit + local Shutdown 요청; 새 frame으로 해제 불가 |

STOPPED/FAIL_SAFE 이후에는 더 큰 Epoch의 explicit trusted INIT가 필요하다.
같은 Epoch, 과거 clock으로 reinit하지 않는다. Central INIT는 Leaf/receiver/물리 모델을 자동 reset하지 않는다.
상위 session owner가 필요한 각 participant를 재설정하고 물리 전원 상태는 계속 관측해야 한다.
INIT에서 닫힌 실제 접점은 startup energized fault다. 모든 접점이 open이면서 bus만 남으면
기존 로컬 방전 동작을 기다리고 실제 OFF를 확인한 뒤 Enable을 허용한다.

정상 준비와 별개로 **input health**를 검사한다. 알려진 INIT BMS 0 한계와 OFF/Checks/Precharge
등의 실제 lifecycle은 시작 중에 합법적이다. 이를 HV_READY/NORMAL로 바꾸지 않는다.
처음 필요한 입력이 모이기 전에는 bounded startup 대기, 한 번 모인 뒤에는 필수 입력 상실을 latch한다.
Local protection은 INIT 중에도 즉시 차단한다. 검증된 DEGRADED envelope는 후속이며 이번에는 허용하지 않는다.

## Identity·만료·응답

Upstream `LifecycleRequest`는 trusted ingress가 제공한 Epoch/Sequence/Source/Expiry와 action이다.
최초 sequence 0..9, 이후 증가량 1..10과 증가하는 source를 요구한다. 같은 identity의 action·원천 시각·expiry
변경은 거부한다. 동일 요청의 재관측은 source/deadline을 갱신하지 않는다.
처음 source를 수신한 시각으로 바꾸거나 CAN frame에서 trusted parent를 자동 학습하지 않는다.

Active root/grant 만료와 owner gap을 **새 요청·피드백을 처리하기 전에** 검사한다.
이미 지난 유효 기간을 새 요청으로 숨겨 NORMAL을 유지하지 않는다.
PowerStatus의 CausalSequence와 AcceptedRequestSourceTime을 실제로 발행한 PowerRequest의
Sequence/Source에 함께 대조한다. 과거 root에 속한 응답도 그 root와 child가 아직 유효해야 하며
Enable 응답의 역행은 허용하지 않는다. 최근 발행 요청 16개를 보존한다(10 ms cadence에서 160 ms).
History hit만으로는 부족하며 parent/source age·child expiry를 추가 검사한다.

AllowNormal은 현재 원래 요청, 확인한 Enable child/원래 parent, 출력 lifetime 및 각각의 source/dependency
유효 기간을 모두 넘지 않는다. 경계 포함 age의 다음 1 ns를 exclusive expiry로 표현한다.
InputTime은 현재 요청·응답의 원래 parent와 모든 필수 입력 중 가장 오래된 원천 시각이다.
DrivePermission의 power identity는 관측한 실제 PowerStatus를 가리킨다. Inhibit는 제한 출력이므로
원래 Enable이 만료돼도 재발행할 수 있다. 주행 권한을 연장하는 것은 아니다.

Shutdown 요청의 parent가 만료되면 NormalPath authority를 연장하지 않는다. 로컬 제한 동작으로
LocalProtection Shutdown을 계속 요청한다. 종료 중 새 Enable로 취소하지 않는다.
Shutdown 요청은 접점 open 명령/안전 정지 성공이 아니다. 기존 BMS leaf가 전류 확인·접점 응답·방전을
진행하며 unknown current/용착이면 계속 blocked일 수 있다. Fault별 차량 감속/제동 배분과 최종
protection matrix는 후속이다. 이 Central 모듈이 local 보호를 대체하지 않는다.
유효한 실제 OFF와 고장 상태는 별개다. Shutdown/KeepOff 응답과 physical quality/age로 OFF를 확인할 수 있으면
다른 peer 상실이나 PowerStatus sender fault가 있어도 관측을 보존한다. 이 관측은 FAIL_SAFE latch를 해제하지 않는다.

## 첫 functional-SIL 값과 검증 경계

| 항목 | 값 |
| --- | --- |
| Runnable period / 최대 호출 gap | 10 ms / 30 ms |
| 최초 critical input 대기 / ACK 진행 대기 | 각각 80 ms |
| 원래 요청 source age / wire lifetime | 50 ms / 최대 80 ms |
| 출력 명목 lifetime | 60 ms, 모든 원래 권한·입력의 expiry로 추가 축소 |
| 전원 준비 / 종료 대기 | 3 s / 2 s |
| 실제 OFF bus 상한 | 30 V |

실차 calibration이나 wall-time 검출 결과가 아니다. 기존 readiness source/dependency budget은 유지한다.
학습·재현 방법과 component 시험 범위는 [상태 owner 안내](../learning/m4_vehicle_management.md)에 둔다.
In-process CAN codec/receiver와 실제 RC/접점 모델을 연결하며 Front/Rear health·비Power actual·BMS gate는
명시적 fixture다. 전체 allocation/Zone ingress/queue/DDS, 실제 vCAN·wall-time/Target·차량 TC는 후속이다.
M3 원래 타이밍 실패와 요구사항 32개/시스템 TC 29개 NOT RUN 상태는 바꾸지 않는다.
