# 30km/h NormalStop의 감속·시간 제한 검토

2026-11-02. 아래 계산·C++ 시험은 물리 실행 이전의 계약 검토다. 별도10s profile의
후속 실제 CARLA 결과는 문서 끝에 연결한다.
현재 `NormalStopConfig`는 감속1m/s², 제동5s, 정지 확인60ms, shutdown2s다.
제동 예산에는 실제 감속뿐 아니라 standing-hold 압력 안정과 원천 표본 확인도 들어간다.
shutdown 예산은 정확한 원본 handoff ACK를 받은 뒤 별도로 시작한다.

| 출발 속도 / 감속 | 이상적 정지 시간 v/a | 이상적 정지 거리 v²/(2a) | 확인60ms까지 최소 시간 | 현재5s 대비 |
| --- | --- | --- | --- | --- |
| 10km/h / 1m/s² | 2.7778s | 3.8580m | 2.8378s | 약2.1622s 여유 |
| 30km/h / 1m/s² | 8.3333s | 34.7222m | 8.3933s | 약3.3933s 부족 |
| 30km/h / 2m/s² | 4.1667s | 17.3611m | 4.2267s | 약0.7733s 여유 |

위 계산에는 통신/제어 지연, actuator 응답, 회생→마찰 전환, 경사·저항·타이어 특성,
압력 안정 시간이 없다. 예산 적합성의 필요조건이며 안전 거리나 물리 성능 보장이 아니다.
5s와 확인60ms만으로 계산한1m/s² 속도 상한17.784km/h도 실제 운용 상한이 아니다.

`NormalStopTest.DefaultBudgetAcceptsIdealTenKmhButTimesOutIdealThirtyKmh`는 현재
실제 config/controller에10ms마다 갱신된 입력을 넣는다. 무지연1m/s² 감속·wheel0에서
즉시 hold 압력이라는 낙관적 조건이다.10km/h는 handoff에 도달하고30km/h는 정확히
제동5s에 BrakingTimeout/보호 요구로 latch한다. 그때 잔여 속도는3.3333m/s(12km/h)다.
새로운 정지 표본으로 실패를 회복할 수 없는 것도 확인한다. 이를 CARLA 결과로 세지 않는다.

다음 물리 시험의 권장 후보는 **별도30km/h fixture에1m/s²·제동10s·shutdown2s**다.
기존10km/h/default5s는 유지한다.10s는 최소8.3933s 이후 약1.6067s의 가설적 여유이며
실측으로 검증해야 한다. 실제 물리 시험 전에 독립 profile/config ID와 고정 평가 기준을
만들고, native/서버/감사에 사용한 설정과 hash를 기록해야 한다.

2m/s²·5s 대안은 별도 제동력/전력·승차감 계약 검토가 필요하고 남은0.7733s가 작다.
현재 시험 통과를 위해 감속을 자동으로 높이거나 timeout을 뒤늦게 늘리지 않는다.
가속은 기존30km/h에서 검증한20s ramp를 사용하고, 충분히 긴 Town06 직선 fixture에서
plateau 이후 사건 시점을 고정하는 것이 다음 단계다. 곡선/Planner/localization은 별도다.

수용 기준에는 원본 wheel/body 정지·압력 dwell·StopLease/세 ECU ACK·PowerStatus Off,
전체 solver/단일 EV 정산, 동일 reference의 timeout/입력 손실 고장 결과를 함께 둔다.
이 사전 검토 시점에는 권장10s를 적용하거나 실제30km/h 정지를 수행하지 않았다.
[정지 인계 보호 시험](carla-stop-fault-protocol.md)과 [실행 근거](evidence/m8_stop_fault/README.md)를 따른다.


후속으로 `normal-stop30-a1-t10-v1`을 별도로 구현했다. 기존 default5s는 유지하며
35s 고정 사건의 실제 Town06 실행에서29.952690km/h→정지8.477999s,
Complete/HV-off9.277999s를 검증했다. 이는 위 이상적 계산과 별도의 물리 근거다.
[사전 기준](carla-stop30-protocol.md), [결과·감사 실패 이력](evidence/m8_stop30/README.md)을 따른다.
같은 참조의 timeout·입력 손실·ACK/전체 통신 손실 fault matrix는 후속이다.
