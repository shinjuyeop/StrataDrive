# ADR-0050: 정상 정지·terminal handoff·HV 종료

Date: 2026-10-19. Status: **Host component 구현/시험 / 전체 분산 coordinator·차량 운동 후속**.
[ADR-0049](ADR-0049-front-nondriving-startup-and-paired-arm.md)의 정상 종료 검토를 구현한다.
기존 Shutdown→Inhibit는 active Drive의 고장 보호로 이어진다. 정상 종료는 그 전에 실제 정지 조건과
별도 trusted handoff를 요구하며, fault latch를 INIT으로 지워 성공으로 표시하지 않는다.

## 단일 stop owner와 요청의 계보

`central::NormalStop`은 stop intent를 받아 다음 단계를 소유한다.

| 단계 | Lifecycle 출력 | Vehicle demand / 전환 조건 |
| --- | --- | --- |
| Waiting | 없음 | trusted begin·새 stop intent |
| Braking | Enable 유지 | 비양수 acceleration·명시적 hold·요청 curvature; 기존 allocator로 회생/마찰 배분 |
| HandoffPending | Enable 유지 | 새 actual 정지 조건의 dwell 완료, hold 명령 계속; 미만료 exact token의 trusted ACK 필요 |
| PowerDown | Shutdown | 새 정상 demand 없음; Leaf/gateway의 terminal lease 갱신과 센서 감시 계속 |
| Complete | Shutdown 의도 유지 | VM Stopped/OFF ACK + actual 접점 open·bus≤30 V + 정지 조건 계속 유효 |
| FailSafe | 정상 출력 없음·protection_required | 원래 고장 유지; caller가 독립 보호 경로에 연결 |

Stop intent는 별도 epoch/sequence/source/expiry와 curvature를 가진 trusted 입력이다.
Same identity mutation, sequence 역행/큰 jump, 원천 age50 ms·최대 lifetime80 ms 이탈은 거부한다.
이전 accepted intent가 만료된 뒤 새 intent를 받아 복구하지 않는다.
`StopIssuerSeed`는 기존 lifecycle/vehicle issuer의 다음 sequence를 trusted coordinator가 넘기는 계약이다.
이후 자식 root를 생성하며 각 plan에 원래 stop ancestor를 보존한다. CAN에서 seed/parent를 학습하지 않는다.
자식의 generation source는 현재 계산 시각이며 expiry는 원래 stop expiry/source-age bound를 넘지 않는다.
Allocator/VM/Zone는 계속 독립적으로 자식 root를 수용·대조하고 실제 입력에 따른 더 짧은 expiry를 적용한다.

VM의 Stopping/Stopped에서는 fresh **Shutdown만** 갱신할 수 있게 한다. 종료 phase budget은 재시작하지 않는다.
Enable/KeepOff 취소·자동 재출발은 기존 RestartRequired다. 만료된 stop root의 제한적 local Shutdown 동작도
유지한다. NormalStop/terminal lease가 만료되면 정상 종료 owner는 별도로 latch하므로 재인가의 근거가 되지 않는다.

## 첫 Host fixture의 정지 조건

| 값 | 결정 / 근거 |
| --- | --- |
| 제동 demand | 1 m/s² 감속 요청; 기존 1000 kg/0.3 m 배분 fixture에서 계산, 차량 제어 calibration 아님 |
| 정지 speed deadband | ≤0.01 rad/s; 현재 wheel-speed wire 한 step. 기존 hold 진입0.5 rad/s와 구분 |
| actual torque | 절댓값≤0.1 Nm; 기존 release tolerance/torque wire 한 step, local raw gate도 적용 |
| actual brake pressure | ≥100000 Pa; 기존 hold100 Nm / friction0.001 Nm/Pa |
| 확인 dwell | 60 ms; speed/torque/pressure의 가장 오래된 원래 취득 시각 진행으로 확인, cached read로 진행 금지 |
| Actual source / skew | 기존30 ms / 20 ms 유지; Front local sensor20 ms·Drive local30 ms도 유지 |
| Braking / PowerDown budget | 첫 fixture5 s / 기존 VM과 같은2 s; root 갱신으로 연장하지 않음 |

값들은 재현 가능한 SIL 설정이다. 실제 차량의 standstill/parking hold·노면/경사·센서 calibration,
제동 안전성 또는 정지 거리/FTTI를 확정하지 않는다. Speed script를 vehicle dynamics 검증으로 표시하지 않는다.

## Terminal lease와 로컬 선택

`ActuatorStopLease`는 원래 stop epoch/sequence/source/expiry를 갖는 same-host trusted sideband다.
Source는 새 INIT 경계 이후·age≤50 ms, lifetime≤80 ms이며 expiry는 exclusive다.
Duplicate는 lease를 연장할 수 없고, 기존 lease 만료를 새 갱신 전에 검사한다. 최초 sequence는 독립
stop stream 중간일 수 있지만 이후 진행량1…10·strictly increasing source를 요구한다.
HandoffPending token의 deadline은 고정이며 관계없는 새 intent로 늘리지 않는다.

`simulation::NormalStopControl`은 두 Zone normal gateway·Rear power gateway·allocator·세 Leaf를 연결한다.
동일 epoch/scope와 plan을 확인하고 Leaf 선택부터 수행한다. 중간 실패/만료는 전부 보호하며 ACK하지 않는다.
보호 callback은 gateway가 이미 관측한 더 나중 시각을 보존한다. 이 선택은 atomic transaction이 아니다.

- Steering은 Hold로 지연된 motion을 폐기하고 local tracking을 계속한다.
- Brake는 Hold로 pending release를 폐기하고 압력을 보존한다. Response monitor의 지연 목표도 폐기하되 sensor identity/fault는 reset하지 않는다. Floor 상실은 로컬 fault다.
- Drive는 실제 local speed/torque를 다시 확인하고 Zero를 선택한다. Quiescent 상태에서 Inhibit/HV-off는 정상 과정이지만, limits/permission·HV/speed/torque 센서·고장 감시는 유지한다.
- Normal gateway는 backlog를 비우고 정상 ingress/dispatch를 닫는다. Allocator는 Quiesced로 normal output을 종료한다. 재출발은 새 trusted INIT가 필요하다.
- Rear power gateway도 기존 큐를 비우고 Enable/AllowNormal 재인가를 거부한다. Shutdown/limits/status와 기존 current→open→discharge 순서를 계속 전달한다.

Actual의 sensor 취득·publication sequence와 원래 command causal history는 계속된다. Normal command
receiver만 terminal handoff 뒤 중지하며, terminal lease 감시는 계속한다. 유효 0·unknown·FAIL_SAFE를 섞지 않는다.
ACK는 출력 선택이며 실제 torque0·압력 유지·접점 open 성공 ACK가 아니다. 후속 fresh actual로 계속 검증한다.
Complete 후에도 LV ECU/센서·lease가 살아 있는 fixture다. 이 단계는 ECU 전원 차단이나 parking brake 구현이 아니다.

## 검증과 남은 범위

기존 startup 시험을 유지하고 별도3.2 s 논리 시간 시험에서 VM/allocator·Front/Rear gateway·세 Leaf,
angle/pressure/torque plant·PowerController/RC/접점·독립 Actual receiver를 연결한다.
외부 speed20→0 script, Zone health·BMS limits/safety·pack400 V/load0 A는 명시적 fixture다.
단일 host binding/issuer handoff가 실제 DDS coordinator·원격 Leaf lease 구현을 대신하지 않는다.
Stop root·동작 판정/부분 handoff·local pressure/speed/lease 상실·제한적 Shutdown 갱신을 시험한다.
정적 분석·회귀·개발 실패 이력은 [학습 기록](../learning/m4_normal_stop.md)과 [품질 기록](../quality_policy.md)에 둔다.

전체 ingress/status/rejoin·remote32-byte CAN composite lease/stop 신호, DDS·전체 workload timing·Target,
실제 vehicle deceleration/hold·Battery energy/SOC를 포함한 정상 종료 loop는 후속이다. M4 전체 완료가 아니다.
