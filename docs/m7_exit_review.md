# M7 통합 검증 및 종료 검토

2026-10-27. **전체 M7 NOT CLOSED.** 고정 시나리오의 native Actual→CARLA→solver work→단일 EV
기능 연결은 검증했다. 실시간 실행 기회와 fault 이후 실제 보호 제동의 수용은 완료되지 않았다.
하위 단계를 계속 늘리는 대신 이 문서의 남은 gate를 기준으로 관리한다.
M6 Host quiet SIL/Python MIL의 구현·계약·결과·종료 판정은 변경하지 않는다.

## 이번 통합 범위

[실행 원본·실패·집계](test-plan/evidence/m7_carla_integrated/README.md),
[재현 runner](../tests/integration/carla/m7_integrated_run.py),
[ICD](icd/carla_plant_adapter.md)를 함께 따른다.
Controller20ms·Zone/vECU10ms·world/state10ms·영상50ms·Drive source-age30ms 및
원래 exclusive expiry를 유지했다. V1 가상 EV 계수·320 내부 분할·원래 solver wheel source도 유지한다.

입력은 시험용 **상위 VehicleRequest** 일정이다. 실제 Central 배분→Zone→vECU 응답→
CAN/P05 Actual 반환과 서버의 권한 검사를 모두 거친다. Actual이나 CARLA effort를 시험 일정으로
직접 대체하지 않는다. 원래 native root request의 source time으로 단계별 입력을 독립 검증한다.
M8 route-following Controller나 AI 주행을 구현한 것은 아니다.

| 검토 gate | 현재 판정 / 근거 |
| --- | --- |
| 고정 환경·모델·단일 writer | CARLA0.9.16 source/Client `294096e-dirty`, UE4.26.2 pin, Town03_Opt/mkz_2020, V1 모델 hash 고정. 외부 writer/tick·synthetic stage 거부 유지 |
| 정상 주행·제동·에너지 | 9s/900구간에서 좌조향 가속→signed 회생→마찰 제동/휠 정지→우조향 재출발 관측. 독립 raw-wire·solver 방정식·work/EV 장부 감사. Reference 전체 속도/ODD 수용 아님 |
| 영상·state·lifecycle | 통합 evidence의 실제 실행별 판정 적용. RGB/학습·평가 GT 분리, frame/source timestamp 검증, 누락 차단·pause/reset/새 INIT 확인 |
| 실시간2ms/4ms·clock | **NOT ACCEPTED.** 현재 native runner는 CARLA 응답 대기 중 owner를 실행하지 않는다. monotonic 계측에서2ms를 넘는 실행 공백 관측. 개별 job4ms deadline·simulation↔wall uncertainty 수용은 미완료 |
| fault 이후 실제 보호 제동 | **OPEN.** 누락/잘못된 권한/정산은 다음 physics tick 차단·latch. 정상 연결의 native admission은 arm 후 비정상 mode를 거부한다. fault 중 실제 보호 Actual을 계속 적용해 감속/정지하는 경로는 아직 없음 |
| 시작·종료 안정성 | 준비 후 종료 경합 수정은 M7-1s FIXED_LIMITED 유지. 새 빌드 최초180s 준비 timeout과 SIGINT30s 초과/강제−9 재현. cold-loading abort 정상 종료 보장은 OPEN |
| Reference 경로 | 54m 직선 후보 좌표/곡률·맵 hash 고정. M8의30km/h 적합성·추종/정지 시험은 NOT RUN |

## 이번에 해결한 문제

1. spawn 직후 첫 physics tick 전 ActorSnapshot에는 새 ego가 아직 없을 수 있다.
   index0은 `valid=false`로 남기고, 이후 누락은 실패 처리한다. 초기 좌표/속도를 조작해 채우지 않는다.
2. 기본 UE float `sensor_tick=0.05`에서 첫 영상 간격60ms를 재현했다.
   M7 전용 flag와 정확한 camera role/종류/주기를 모두 만족하는 센서만 actor tick을 매 frame 실행하고,
   원래 CARLA frame counter의5배수에서 실제 취득한다. capture나 timestamp를 사후 보정하지 않는다.
   기본 CARLA 센서 동작은 이 opt-in 조건 밖에서 유지된다. 내부 센서 스케줄을 조정했으며
   native/M6 계약·차량 운동·에너지 코드는 변경하지 않았다.

## 남은 문제를 닫는 작업

**다음 작업은 wall 실행 구조와 보호 Actual 경로를 함께 해결하는 한 묶음이다.**
현재 Python/RPC/전체 solver JSON 진단 loop의 지연을 단순 timeout 증가로 해결할 수 없다.

- native owner/감시의 wall 실행을 CARLA 응답 대기와 분리한다. 실제2ms 실행 기회·4ms 완료를
  monotonic 기준으로 계측하고, 지연 시 normal 권한을 닫는 경로를 검증한다. trace는 비동기 수집하되
  frame별 work 정산 증거를 잃지 않아야 한다. 최적화 전후 동일 시나리오의 물리/work 비교를 유지한다.
- normal 권한이 닫힌 뒤 LocalProtection Actual의 원래 origin/epoch/source/sequence·authority를
  검증하는 별도 보호 적용 계약과 실행 경로를 구현한다. stale normal을 재사용하거나 명령값으로
  brake를 만드는 것은 금지한다. world freeze를 실제 감속/정지로 수용하지 않는다.
- cold loading 중 cancellation이30s 안에 끝나지 않는 engine 작업을 식별한다. 현재 강제 종료는
  실패 containment일 뿐 정상 shutdown PASS가 아니다. 기존180s/30s 한도를 조용히 늘리지 않는다.

원래 renderer Distance Field crash 원인은 여전히 미확정이다. 이번 짧은 영상 시험이 성공해도
모든 content/장시간 안정성을 주장하지 않는다. 정지 시 휠 회전0과 차체의 작은 잔류 속도는
구분해 기록했다. 새 stationary 허용 오차를 임의로 만들거나 음수를0으로 바꾸지 않았다.

M8 Controller/30km/h 경로 적합성, M9 diagnostics, AI 학습·Jetson 배포는 각 후속 milestone의
범위이며 M7 검증을 진행할 때마다 새 선행 작업으로 추가하지 않는다.
