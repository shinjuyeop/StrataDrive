# M6 simple vehicle / MIL pilot — 실행 전 protocol

2026-10-22. 시작 HEAD/origin/main ae3bb4fa7b7f943e1c97fe69bda255b5047c755b,
fetch 후 동일, 작업 트리 clean, 저장소/상위 AGENTS.md 없음.

## 구현 경계

- M6 첫 실행 범위: 실제 actuator 응답 → 단일 SimpleVehicle → 실제 wheel speed → 기존
  Drive/BMS/Power/Actual 경계. 선택형 `--simple-vehicle`; 기존 M5 fixed-zero fixture 유지.
- 평지/전진, 질량1000kg·반경0.3m·wheelbase2.7m·압력 환산0.001Nm/Pa는 기존
  allocator fixture와 일치. rolling100N, drag0.4N/(m/s)^2는 새 명시적 SIL 가정이다.
  단일 관성·무슬립 kinematic bicycle, 실제 차량 calibration/타이어/후진/경사 모델 아님.
- 이산 종방향 PI 모델은 Python 표준 라이브러리로 실행한다(TBD-16 첫 MIL 선택).
  M8 C++ controller/모델 동등성/실제 Central 속도 폐루프는 여기서 완료하지 않는다.
- 기존 세션/ACK/credit/arm/명령 원천 시각/expiry/host10-v1/감시/큐/SDK는 유지한다.
  물리 model epoch와 ECU session epoch를 구분하고 재가입으로 물리 상태를 초기화하지 않는다.

## 고정 시험

1. C++ analytic/계약: 추진·coast·정지 시 역행 없음·곡률·work/energy·invalid/stale/
   future/identity/timing 입력 거부 및 상태 보존·실제 actuator delay 반영·물리 재시작 경계.
   개발 중 이 변경 경계만 실행. 실패/수정별 로그 보존.
2. MIL: 2ms plant,20ms PI,50ms 실제 speed acquisition/ZOH,60ms 원천 age;
   0→30km/h 20s 선형 reference 뒤15s plateau,30→20km/h 8s 뒤15s plateau,
   20→0km/h 14s 뒤15s plateau. 처음5s settling, 다음10s 모든20Hz sample
   absolute error<=1km/h, positive reference overspeed<=10%; zero percentage N/A.
   acceleration [-5,2]m/s², slew2m/s³. 별도 saturation/recovery, stale/invalid,
   permission loss, explicit newer INIT reset 계약 시험. 각1회. 결과 뒤 기준 변경 금지.
3. 실제 3-process SDK + 선택 vehicle: Normal FIFO quiet normal1, Rear command-loss1,
   Rear restart-live1. 기존2540ms 정상 관측/2500ms shutdown tail/20s runner timeout.
   CPU·정책·부하는 M5 accepted profile 그대로, 새 부하/48회 없음.
   실제 양 IP·8 ACK·Leaf renewal·원래 보호·HV-off·stop/join 검사는 기존 oracle 유지.
   새 판정: finite vehicle states, 실제 이동>0, wheel speed>0, model identity 연속,
   normal stop 후 speed<=0.15m/s; 재가입 뒤 물리 model epoch/position reset 없음.
4. ASan/UBSan 실제 SDK normal1. TSan 새 model/변경 C++ 경계1회, 실제 SDK normal1
   (기존 fixed-layout). sanitizer wall-time 실패를 Normal 성능 PASS와 합치지 않음.
5. 공유 PhysicalOwner 변경에 따른 최종 전체 C++ Normal·ASan/UBSan 각1회.
   Python runner/oracle/MIL 계약과 build/ 없는 재현 준비 검사. 이전987 이름/assertion 보존.

모든 실행은 build/.m4-exclusive.lock. 측정 중 빌드/대규모 검색 금지.
실패·timeout·누락·예상 밖 SDK/sanitizer 오류 exit1, 원본 보존. 원인 없는 재시도 없음.
최종 소스/바이너리 hash·실행 명령·설정/분모·실패를 별도 결과에 기록한다.
M6 부분 구현/검증 결과로 전체 M6/M4/M7/M8·Jetson·차량 시스템을 수용하지 않는다.

## 개발 비교1 (최초 MIL 보존 후, 재실행 전)

MIL attempt1은 각 plateau200sample의 <=1km/h 조건을 충족했으나71.95s에
reference0.0198413 / actual0.0304410m/s, positive overspeed53.42% FAIL이다.
P/I만으로50ms actuator delay와 held speed를 추종하면서 정지 직전 오차 비율이 커졌다.
동일 reference/판정/87s를 유지하고2-DOF reference derivative feedforward와 감속 때만
50ms actuator+50ms sensor+20ms controller=120ms preview를 추가해1회 비교한다.
판정 reference나 실제 speed source를 바꾸지 않는다. M8 적용은 별도 동등성 검증 대상이다.
초기 C++ build는 새 target configure 누락, 이어 gtest macro dangling-else 경고로 미실행.
괄호 수정 후9case를 실행한다. 실패 로그는 보존한다.

## 개발 비교2 — 실제 이동 후 NormalStop 인계

`SDK sdk-dev-normal/normal-1` FAIL 원본을 보존한다. 정상205batches/세 Leaf 갱신,
native miss0 뒤 stop에서 Front 첫 Stop(token1261)은 수용,20ms 뒤 갱신1267의
Brake Leaf가 거부됐다. 실제 압력이 낮아지는 중 terminal Hold를 선택한 경계다.
새 논리 회귀 `FallingBrakePressureCannotStartTerminalHoldBeforeSettledDwell`은
기존 코드에서 FAIL(`stop-before.txt`)을 재현했다. 정상 정지의 원래60ms dwell에
brake 실제 압력이 한 wire step(1000Pa) anchor 안에 머무는 조건을 추가한다.
감속/명령/허가 시한·5s braking timeout·2s shutdown timeout은 늘리지 않는다.
Leaf monitor 조건을 완화하지 않는다. 관련 전체 NormalStop 계약과 실제 normal1 비교 후
동일 최종 코드로 원래 정한 command-loss/rejoin·sanitizer를 실행한다.

## 개발 비교3 — delayed hold target과 주입 전 실제 이동

`sdk-normal` normal FAIL/command-loss FAIL/rejoin PASS를 그대로 보존한다.
Normal의 안정 압력300kPa는 **기존 감속 목표**였고50ms 지연된100kPa hold 목표가
첫 인계 직전에 적용됐다. 단순 안정 dwell만으로는 pending target을 배제하지 못했다.
Braking 인계는 기존 standing-hold 목표100kPa(+한 wire step) 도달과 기존60ms dwell을
함께 요구하도록 좁힌다. 새 `StableOldBrakingTargetIsNotSettledStandingHold` 회귀를 추가한다.
기존 감소 압력 시험의 최종 stable 입력도 실제 hold 목표100kPa로 명시한다.

command-loss는 기존 정상 torque/Brake 조건 직후(아직 rolling force보다 작은 실제 torque)
주입하여 차량 이동 기준에 못 미쳤다. M6 선택 경로만 **실제 validator wheel speed>=0.1rad/s**를
주입 전 조건에 추가한다. 기존 M5 기준/시한을 변경하거나 zero-motion을 PASS로 세지 않는다.
동일 Normal3case를 변경된 두 경계 확인을 위해1회씩 실행한다. 더 이상의 조건 탐색은 하지 않는다.
앞선 include 누락 빌드와 그 뒤 stale binary의stop-after FAIL은 수용 근거에서 제외한다.
