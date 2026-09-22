# ADR-0004 — AI / control boundary

## Status

Accepted for **StrataDrive Reference Baseline v0.1** (2026-09-22).
설계 경계의 수용이며 runtime 구현/호환성/성능 검증은 **PLANNED / NOT RUN**이다.

## Context

Learned Temporal Planner는 늦거나 유효하지 않거나 실행 불가능한 출력을 만들 수 있다.
AI 도입 전에 fault 동작을 관측할 수 있어야 하며 classical baseline이 필요하다.
Interface 경계를 유지하면 이러한 영향을 살펴보기 쉽지만 안전성이 증명되지는 않는다.

## Decision

먼저 Zone Controller/vECU를 거치는 classical route/waypoint 주행을 구현한다.
Lateral control에는 Pure Pursuit 또는 Stanley, longitudinal control에는 Longitudinal PID를
사용한다. 그다음 pretrained perception을 추가한다. 이후 0.5–1초의 state/object history를
사용하는 GRU 또는 작은 Temporal Transformer를 평가한다.

AI는 Future Waypoints / Suggested Trajectory, Target Speed, Risk Score를 출력한다.
Actuator command를 직접 생성하지 않는다. 출력은 Safety Supervisor → Classical Controller
→ Vehicle Command 경로를 거친다. AI timeout이나 유효하지 않은 출력에 대비해
Classical Planner fallback을 유지한다. Fallback 입력도 사용할 수 없으면 유효한 fallback으로
간주하지 않고 정의된 degraded/fail-safe 정책을 따른다.

## Alternatives Considered

- End-to-end learned actuator control: 명시적인 경계는 줄지만 계약, timing, fault를
  구분해 살펴보기 어려워진다.
- Classical autonomy만 사용: 첫 단계에 적합하지만 이후 Physical AI 학습이 빠진다.
- Safety validator 없이 learned 출력 사용: 검증과 복구 경계가 부족하다.

## Consequences

검증, mode 전환, trajectory 연속성, fallback timing을 명시적으로 시험해야 한다.
Classical Controller나 deterministic 규칙만으로 hard real-time 보장이나 안전 인증이
성립하지 않는다. Risk 의미/calibration, 검증 한계값, training/evaluation 분리,
recovery threshold는 TBD다. [software architecture](../architecture/software_architecture.md)와
[안전 계약](../requirements/safety_requirements.md)을 참조한다.

Algorithm/tuning은 TBD-11(M8), AI model/feature는 TBD-09(M10), history/risk/fallback은
TBD-10(M10/M11)이다. v0.1 AI 계약 수용은 AI 구현/모델 선택의 완료를 뜻하지 않는다.

미결정 항목의 owner/rationale은 [TBD register](../roadmap.md#open-m0-decisions)를 따른다.
