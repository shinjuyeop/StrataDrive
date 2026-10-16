# ADR-0019: 첫 조향 응답 component 모델

현재 배치: [ADR-0021](ADR-0021-central-coordination-and-parallel-zones.md). 후속 vehicle management/allocation/session/feedback owner와 Zone routing은 2026-10-14 ADR-0021을 따른다. 이 component 모델의 동작과 시험 설정은 유지한다.

Date: 2026-10-14. Status: **Host functional SIL 부분 구현 / 학습자 review PENDING**.
Owner: project owner. TBD-02/03/04, IF-CAN-STEERING, STEERING_COMMAND_LOSS에 연결한다.

후속 구조 변경: [ADR-0032](ADR-0032-ecu-and-sil-execution-boundaries.md)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

## 결정

`vecu/steering/SteeringActuator`가 기존 Command receiver를 소유하고, 외부 monotonic clock으로
control tick을 실행한다. 수신 codec/receiver는 `interfaces/steering/`에 유지한다.
동일 thread에서 command 검증 → command snapshot → dynamics → Actual/P05를 수행한다.
OS task 분할/독립 watchdog/Target scheduling은 M3 이후 검토한다.

첫 모델은 control tick에서 포착한 목표의 고정 지연, 방향 대칭 rate limit, 물리 각도 saturation을
결합한다. 목표 변경을 bounded delay FIFO에 보관하고, 같은 목표의 반복 수신은 freshness만
갱신한다. Delay 경계가 두 tick 사이에 있으면 경계 뒤 시간에 대해서만 새 목표로 움직인다.
Tick의 최소 간격과 delay 상한을 제한해 128-entry FIFO에 최대 101개 목표 변경이 들어온다.
동적 할당은 control 경로에서 사용하지 않는다. 실제 RTOS 실행 보장은 아니다.

수신 허용 범위와 물리 모델 한계는 별개다. 허용 범위 밖 command는 기존 receiver가 거부한다.
허용된 목표가 물리 한계보다 크면 모델 target만 saturation한다. Normal/Degraded 입력 상태를
Actual에 전달하고 Actual 값은 dynamics의 결과다. CausalSequence는 기존 wire 계약대로
마지막 수용 Command 번호이며 현재 움직임을 만든 delayed target의 번호라는 뜻은 아니다.

## 시험용 parameter와 보호 정책

Fixture는 Command ±0.5 rad, model ±0.3 rad, 초기 0 rad, 최대 1 rad/s, 지연 50 ms,
control/publication 최소 간격 10 ms, 허용 tick gap 30 ms를 사용한다.
Source age 30 ms와 valid-RX timeout 80 ms는 기존 Steering receiver 후보값이다.
이 값은 OEM calibration이나 차량의 보호 응답 수치로 채택하지 않는다.
교육 그래프의 deg 예제와 이 SIL fixture의 rad 설정은 서로 다른 예제다.

Command source expiry, receiver timeout, queue continuity loss 또는 control deadline 위반 시
pending target을 취소하고 현재 modeled angle을 hold한다. Tick에서 source freshness를 먼저
검사하므로 interval 끝에서 stale이면 그 interval의 이동 전체를 생략하는 보수적 sampled 정책이다.
수신 함수도 이전 snapshot의 expiry를 새 command 전에 확인한다. 늦은 fresh command가
관측 사이의 expiry를 숨기거나 latched local FAIL_SAFE를 해제하지 못한다.
새 trusted Epoch와 비감소 clock으로만 session을 재시작하며 physical angle은 보존한다.
실차에서 hold가 안전한지, 차량 감속/전원 정책과 어떻게 결합할지는 TBD-03/06 후속 검토다.

Actual은 새 control sample 시각/독립 sequence/P05를 갖는다. 수용 Command가 있으면
hold angle도 유효 Actual이지만 FAIL_SAFE + LocalProtection으로 표시한다.
수용 Command가 없는 startup timeout의 Actual은 unavailable이며 causal=0은 진단용이다.
Clock 역행 후에는 신뢰할 새 source time이 없으므로 publication을 중단한다.
Missed deadline을 여러 tick으로 backfill하지 않는다. Actual sequence 소진 시 wrap하지 않는다.

## 증거와 후속

[M2 조향 실행 안내](../learning/m2_steering_model.md)에 단위 시험과 독립 세 process
Command TX → model → Actual RX vCAN 기록을 둔다. 기존 통신 runner/executable과
`actuator_demo steering-model`을 확장하며 feature별 executable을 추가하지 않는다.

이 모델은 inertia/friction/acceleration/noise/센서 고장/actuator jam 검출, vehicle closed-loop,
Front/Rear coordinator 및 DDS를 구현하지 않는다. Tracking fault threshold/dwell과 실제 local
보호 gate는 별도다. 기존 system TC를 PASS로 바꾸지 않는다.
