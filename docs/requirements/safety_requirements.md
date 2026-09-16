# Safety requirements and behavior contract

Status: **DRAFT / TBD**. SYS-SAFE-001과 SYS-AI-001의 학습용 SIL 설계다.
ISO 26262 준수, ASIL 할당, 인증, 실차 안전성이나 QNX/AUTOSAR 사용을 주장하지 않는다.

## Responsibility and boundary

Safety Supervisor는 trajectory의 freshness, finite values, range, feasibility와
health/state를 평가할 예정이다. Classical Controller는 bounded command를 생성하고,
Zone Controller는 age/integrity/mode/range와 actuator availability를 독립 검증한다. vECU는
local timeout/watchdog와 dynamics를 가진다. 한계값, 우선순위, 검출/반응 시간은 TBD다.

| Trigger | 계획된 정책 후보 | 미결정 acceptance |
| --- | --- | --- |
| AI timeout / invalid output | 유효한 Classical Planner로 fallback | 전환 deadline, trajectory continuity, fallback 입력 유효성 |
| Central Vehicle Compute command loss | Zone Controller의 local 보호 동작 | ramp/hold/stop 선택, 최대 지속 시간, 재연결 |
| Steering/Brake/Drive loss | 가용성에 따라 DEGRADED 또는 FAIL_SAFE | actuator별 가능한 동작, 속도/노면/ODD 조건 |
| Stale actual feedback at Host Plant Adapter | stale 검출과 명시적인 simulation safety policy | bounded hold/stop/pause 등의 선택, simulation/wall time 처리 |
| Task overrun / compute overload | optional workload 축소, 필요하면 안전 상태 전환 | 필수 task budget, threshold/dwell, hysteresis |
| Fault cleared | RECOVERY에서 health/sequence/state 재검증 | confirmation dwell, 수동/자동 승인, 초기 command |

FAIL_SAFE라는 상태 이름은 모든 고장에서 안전한 정지를 보장한다는 뜻이 아니다.
특히 brake loss에서 braking을 전제로 정지를 요구하지 않는다. Fault별 가용 actuator,
남은 제어 능력, 관측 가능한 예상 동작을 먼저 정의한다. Diagnostic 기록 완료를
기다리지 않고 local reaction을 수행할 수 있어야 한다. Physical plant response를
평가한 뒤에야 protective action의 검증 결과를 판단한다.

## Safety contract template

- Requirement / fault / scenario / ODD / 가정: TBD
- 검토할 위험 동작 (정식 hazard analysis는 완료되지 않음): TBD
- 가용 sensor/actuator와 가용성 증거: TBD
- 검출 조건 / debounce / clock / deadline: TBD
- 요구 상태 / 출력 한계 / actuator 동작 / 반응 deadline: TBD
- Actuator를 사용할 수 없을 때의 대안과 남은 한계: TBD
- 복구 조건 / 권한 / dwell / 재초기화: TBD
- Test Case / 관측 가능한 판정 기준 / Result: TBD / NOT_RUN

Startup에서는 valid state와 command를 확인하기 전 정상 운행 출력을 허용하지 않는
방향이다. 초기 state/output/handshake는 미결정이다. 상세 내용은
[fault architecture](../architecture/fault_diagnostics_architecture.md),
[timing](timing_requirements.md), [verification](../test-plan/verification_strategy.md)을 참조한다.
