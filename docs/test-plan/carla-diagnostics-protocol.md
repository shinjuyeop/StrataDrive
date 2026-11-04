# M9 STOP30 진단 연결 사전 프로토콜

2026-11-04. [고정 정상 STOP30](carla-stop30-protocol.md)의 route, PI,
Pure Pursuit, 6000 ticks, 10ms PhysX/320 substeps, 단일 EV work 정산,
NormalStop 1m/s²·10s·60ms·2s를 그대로 사용한다. 진단 opt-in은 실행 전에
`--diagnostic-fault`로 고정하고 native 원본 event bytes를 각 barrier에 저장한다.
진단 observer는 원본 owner 호출이 끝난 뒤 읽으며 clock·제어·물리 입력을 갱신하지 않는다.
주입 시각은 첫 PI release+35s다. 정상 선행 구간의 목표·경로·모델을 바꾸지 않는다.

| Recipe | 실제 주입 위치 | 예상 최초 원인 / 판정 |
| --- | --- | --- |
| `none` | 주입 없음 | 정상 정지·HV off, confirmed DTC 0 |
| `input-loss` | SpeedRequest의 input 인자 공급 중단; 실제 센서/CAN/물리는 계속 실행 | SD-1001, 보호 선택, 원본 protection Actual, 실제 차량 정지 |
| `stop-ack-loss` | Front Zone→Central mailbox의 Stop TxResult 폐기 | SD-1102; Stop 모니터의 lease expiry 또는 실제 transport ResultTimeout 중 최초 검출 경로를 보존. 정상 Complete로 세지 않음 |
| `front-command-loss` | Central→Front Zone normal work mailbox 폐기 | Central transport SD-1002 및 owner의 command expiry. 실제 local 보호·물리 정지. 이 recipe는 명령 lane 손실 범위 |
| `front-link-failure` | Central→Front work mailbox의 실제 sticky close; feedback/priority protection은 유지 | SD-1002 transport Continuity, authority 폐쇄, 실제 local 보호·물리 정지 |
| `braking-timeout` | 요청 시점부터 각 physics frame에 인증된 `stage_native`와 명시적인 `-StrataM9ExternalLoad` 서버 설정으로 pre-physics의 원본 actor 진행 방향에 1800N 외력을 적용 | 정상 제동 능력을 넘는 지속 외력에서 SD-1101과 원래 10s deadline 검증. 압력·토크·wheel 측정은 원본. 이후 보호 제동의 실제 정지 여부를 별도 보고 |

외력은 환경 시험 입력이다. 네 wheel brake torque, 정상 제어 출력, 접촉기,
EV motor work나 DTC 값을 직접 수정하지 않는다. 외력 벡터와 호출 frame을 원본
JSONL에 남긴다. 외력이 수행한 일은 EV motor work로 합산하지 않는다.

수용은 다음을 모두 확인한다.

- 고정 profile hash와 실제 실행 binary/source/config hash, 실행·실패·cleanup 원본 보존.
- 주입 전 body 29–31km/h, plateau [25,35)s의 속도 오차≤0.5km/h.
- 실제 8-role Release가 먼저 완료된 Session과 동일 epoch의 DTC. 원본 검출 시각,
  request/lease/transport token 및 deadline, 보호 선택, actual acquisition을 구분.
- 선언한 주입 경계의 실제 omission count 또는 외력 벡터가 존재. 결과 event를
  덮어써 기대 code를 만들지 않으며 먼저 검출한 계층을 임의로 바꾸지 않음.
- 보호 후 원본 torque≤1Nm, pressure≥1MPa, wheel/body 응답을 대조.
  입력/ACK/명령 손실은 최종 body≤0.001m/s·네 wheel 0. 외력 case는
  timeout 시점의 미정지와 이후 실제 정지 여부를 분리하고, 정상 Complete를 요구하지 않음.
- 모든 6000 physics/6000 EV 정산 및 기존 native/work 독립 감사. 기존 observer가
  더 좁은 nominal 조건을 가정하면 그 실패를 보존하고 진단 전용 독립 판정과 구분.
- DTC code·발생 시각·주입·물리 응답을 변경한 evidence는 독립 감사에서 거부.

이 시험의 clock은 CARLA simulation time이며 native owners는 기존 단일 thread
functional rig다. SOME/IP 별도 3-ECU, native wall deadline, Target 수용은 해당
별도 실행 근거로 판단한다. 학습자 이해 review도 기술 시험과 별도다.

초기 functional admission 검사에서 silent `front-command-loss`는 native timeout
전에 다음 10ms 전체 구간의 command expiry를 만족하지 못해
`native_command_interval_or_causal`로 거부됐다. 초기 source와 실패를 보존한다.
이 경로는 실제 차량 정지 PASS로 올리지 않으며 구간 분할을 지원하는 물리 adapter가
필요하다. `front-link-failure`는 별도의 명시적 연결 고장 recipe다.

첫 timeout 실행은 legacy `actor.add_force`가 기존 독점 gate에서 거절되어 정상 정지했다. 해당 실패를 보존한다. 후속 주입은 전용 simulation/work 서버만 허용하며 기존 legacy RPC 차단을 유지한다. 고정 1800N을 동일 frame의 pre-physics에서 적용하고 서버 receipt에 실제 벡터를 기록한다. 클라이언트의 호출 성공만으로 적용을 주장하지 않는다.
