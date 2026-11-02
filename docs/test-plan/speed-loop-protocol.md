# SimpleVehicle 속도 폐루프 프로토콜

실행 전 고정한 M8 논리 시간 통합 범위. C++ `m6-pi-v1` 상수와 Python 모델은
변경하지 않는다. 실제 네트워크·wall time·CARLA 수용과 구분한다.

- 기존 8 participant INIT/ACK/release, VehicleCoordinator, Zone, CAN P05,
  Leaf controller와 단일 PhysicalOwner를 그대로 실행한다. 물리는 1ms,
  owner poll은 0.2ms, SpeedPI는 정확히 20ms, allocation은 Host10ms다.
- 첫 정상 arm 후 allocation release+1ms에 첫 제어 계산을 시작하고 이를 profile 원점으로 한다.
  1ms 위상은 기존 0.2ms owner poll의 Leaf→Zone→Central 전달 뒤 acquisition을 읽기 위한 값이다. M6와 같은 87초
  0→30→20→0 km/h profile. 이후 NormalStop에 인계하고 총 실행은 92초다.
- 제어 입력은 Central receiver의 current Drive Actual wheel speed × 0.3m.
  wire에 physical epoch/sequence는 없으므로 application epoch와 원래 wheel
  acquisition timestamp를 cursor로 쓴다. 물리 epoch 7을 application epoch로
  다시 찍는 방식은 사용하지 않는다. Ground truth는 사후 비교에만 사용한다.
- 매 제어 step은 새 wheel acquisition을 요구한다. 30ms source age와 session
  enable을 검사하며 같은 source의 envelope 갱신은 새 입력이 아니다.
  VehicleRequest source를 wheel source로, expiry를 source+30ms+1ns로 제한한다.
  10ms allocation은 같은 root를 재사용하며 제어 계산/원천 시각/expiry를 갱신하지 않는다.
- 20ms 제어 표본 4,350개(0 ≤ t < 87초)를 모두 저장한다. 정상 구간
  [25,35), [48,58), [77,87) 각각 500개에서 속도 오차 ≤1km/h.
  양수 목표에 대한 동시각 overspeed ≤10%, 목표 0의 비율은 N/A.
  physical 10ms trace도 같은 구간/동시각 기준을 독립 검사한다.
- 제어 출력 유한값 및 [-5,2]m/s², slew ≤2m/s³, 원천 시각/epoch/sequence,
  정상 중 fault 0, 물리 ledger 보존, NormalStop Complete·HV off를 검사한다.
  SOC/energy는 회생 중 증가할 수 있으므로 단조 감소를 요구하지 않는다.
- 결함: 새 envelope의 고정 wheel source, permission 상실, 제어 release 누락,
  이전 epoch/enable 이전 source는 단위 경계에서 reject/latch. 전체 경로에서는
  Drive Actual 손실과 명령 생산 중단을 주행 중 주입하고 100ms 이내 보호 선택,
  이후 정상 재개 없음 및 실제 torque zero/brake pressure 응답을 검사한다.
- 이전 evidence는 변경하지 않는다. 각 실행의 입력 설정·source/binary hash·
  버전·원본 표본·실패·결과를 별도 디렉터리에 보존한다. 기준을 결과에 맞춰 완화하지 않는다.

설계 수정 기록: initial nominal-01은 release와 같은 시각에 계산하여 10ms 전 wheel을
읽었고, source+30ms 만료 전에 다음 명령이 도착하지 않아 801.2ms에 보호되었다.
nominal-02부터 시작 위상을 +1ms로 수정했다. age/expiry와 성능 기준은 동일하다.
