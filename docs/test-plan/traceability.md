# Requirement → component → interface → test → result

Status: M0 draft. **모든 runtime test는 NOT_RUN**이다. Result ID는 실행 후에만 부여한다.
아래는 coverage 후보이며 시험 완료의 증거가 아니다.

| Requirement | Architecture component | Interface | Test case | Result ID / evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| SYS-ARCH-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | IF-DDS-VEHICLE-CMD, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE | TC-ARCH-001 | — | NOT_RUN |
| SYS-COM-001 | ARCH-ZONE, ARCH-VECU | IF-CAN-STEERING, IF-FAULT-EVENT | TC-COM-001 | — | NOT_RUN |
| SYS-COM-002 | ARCH-ZONE, ARCH-VECU | IF-DDS-VEHICLE-CMD, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE | TC-COM-002 | — | NOT_RUN |
| SYS-CTRL-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-DDS-VEHICLE-CMD, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR | TC-CTRL-001 | — | NOT_RUN |
| SYS-AI-001 | ARCH-CENTRAL, ARCH-SAFETY | IF-CENTRAL-TRAJECTORY, IF-FAULT-EVENT | TC-AI-001 | — | NOT_RUN |
| SYS-SAFE-001 | ARCH-SAFETY, ARCH-ZONE, ARCH-VECU | IF-DDS-ZONE-STATUS, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-FAULT-EVENT | TC-SAFE-001 | — | NOT_RUN |
| SYS-DIAG-001 | ARCH-DIAG | IF-FAULT-EVENT | TC-DIAG-001 | — | NOT_RUN |
| SYS-PERF-001 | ARCH-CENTRAL, ARCH-ORCH, ARCH-ADAPTER | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-DDS-VEHICLE-CMD, IF-HOST-ACTUATOR | TC-PERF-001 | — | NOT_RUN |

정의: [requirements](../requirements/system_requirements.md),
[components](../architecture/system_architecture.md),
[interfaces](../icd/interface_overview.md), [test cases/results](verification_strategy.md).

변경 workflow: requirement 변경 이유와 version 기록 → component/interface 영향 확인
→ test/oracle 갱신 → 실행 시 Result ID와 artifact 연결 → verdict/reviewer 기록.
같은 test의 여러 board/run 결과는 별도 행 또는 linked summary로 유지한다.
TBD parameter나 미구현 component를 빈칸으로 남겨두고 verified로 표시하지 않는다.
