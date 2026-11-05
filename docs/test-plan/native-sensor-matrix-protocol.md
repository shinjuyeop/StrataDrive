# BMS·Power 센서 고장 차량 SIL

2026-11-05. M9의 개별 부품 검증을 실제8-role 논리 차량 경로로 확장한다.
센서 고장 주입이며 배터리/접촉기 물리 모델 자체의 고장 주입과 구분한다.
원래 acquisition identity/source/dependency와 actuator·단일 EV 모델은 유지한다.

## 실행 전 고정 조건

- `native_sensor_matrix_test`: BMS mask1/2/4/8/16/32/64/128/170의9조건,
  Power charger-connected/contactor-mismatch/bus-low의3조건,
  BMS170과 각 Power 고장의 동시3조건. 총15조건이다.
- 각 조건에서 복원 후 INIT 없음14s, 명시적 새 INIT/Release 포함24s를 각각 실행한다.
  총30개 실행이며 모든 성공/실패와 실제 journal을 보존한다.
- Logical Host10ms,20ms BMS, native input fault10s–10.2s, 새 INIT20s.
  원래40ms BMS trip dwell/100ms release dwell·Power 조건·timeout은 유지한다.
- BMS 소비 사본에만 해당 threshold 초과 값을 넣는다. Power 소비 사본에만
  charger-connected=true / precharge contact=true / bus=200V를 넣는다.
  이 값들은 새 센서 취득이 아니라 명시적 고장 입력이다. 정상 ECU/plant 사본은 보존한다.

## 판정

9.9s 정상 주행·DTC0을 먼저 확인한다. 실제 native fault reason/mask와 원래 검출 시각을
SD-3101/SD-3201 및 durable journal에 대조한다. 동시 고장에서는 보호 전달 뒤의 자체
BMS trip도 별도 root로 남겨야 한다. BMS는 주입 후60ms 이내·원래40ms dwell,
Power는10ms 이내 검출한다. 보호는 기존100ms, 실제 torque≤1Nm·brake≥1MPa는
검출 후230ms 이내를 유지한다.13s부터 재기동 전까지 실제 정지·HV-off를 확인한다.

입력 복원만으로 Failed가 바뀌지 않는다. 새 전역 Release 이후 실제 BMS Active/release
dwell 및 Power HV Ready를 거친 경우만 Passed가 가능하다. Count/generation1과 이력을
유지하며 자동 clear하지 않는다. 모델 epoch7·연속 sequence·에너지 정산도 검사한다.

별도 Python 감사가 canonical journal, native snapshot, owner/protection 및 물리 trace를
대조한다. 원인/시각·물리 반응·새 세션·Passed를 손상한 자료를 거절해야 한다.
Debug/ASan·UBSan/TSan은 논리·메모리·동시성 검사이며 wall 성능의 분모가 아니다.

## 최초 실행 후 원인별 기대값 교정

최초15조건 중13조건 통과·2조건 실패(구성 검사 별도1개 통과)의 원본을 보존한다.
시험이 모든 Power 고장을 Ready의10ms 검사로 가정한 오류였다. 실제 구현/상태를 확인한
후 다음 실행 전에 기대 원인을 아래처럼 고정했다. 제품 기준·고장 입력은 바꾸지 않는다.

- BMS170+접점 불일치: BMS pending trip의 inhibition이 먼저 Power를 WaitCurrent로 보낸다.
  이후 OpenContactors의 원래100ms deadline에서 SD-3201을 기록한다. 이 phase 기점과
  deadline을 정확히 검사하며 즉시 Ready 고장으로 바꾸지 않는다.
- BMS170+bus-low: 같은 선행 inhibition 때문에 Ready 전압 감시를 실행하지 않는다.
  200ms 주입은 원래1s discharge timeout 전에 복원된다. Power BmsInhibit는 Observation,
  자체 Power DTC는0, BMS SD-3101은1이어야 한다. 없는 자체 고장을 합성하지 않는다.

Power precharge/request-loss/shutdown-current/startup-energized/discharge의 통합 경계,
CARLA 물리·native SOME/IP wall 고장 조합은 이 시험의 수용 범위가 아니다.
