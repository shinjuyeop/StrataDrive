# M6 종료 검토 — Host quiet SIL / Python MIL

2026-10-22. 검토 기준 `6705388`(fetch 후 HEAD/origin/main 일치, clean).
**판정: M6 Host quiet SIL/MIL 범위 종료(CLOSED). 해당 범위의 필수 산출물 누락 없음.**
제어/모델/통신 수치나 실행 코드를 바꾸지 않고 기존 구현·원본 결과를 대조한 문서 검토다.
M4 전체 종료·Jetson·전체 시스템 수용, M7 CARLA/M8 C++ controller 완료를 뜻하지 않는다.
실제 SIL은 기존 문서의 Normal FIFO CPU/스레드 배치·quiet 부하·정상 사례8s 관측과 기존2.5s
shutdown tail 범위다. Python MIL의87logical s와 실제 SDK wall-time을 합치지 않는다.

## 종료 검토표

로드맵/개발 계획의 M6 산출물은 Simple Vehicle + EV plant의 actual/lifecycle/energy와
실행 가능한 종방향 제어 모델·MIL의 parameter/sample time/추종·제약 검증이다.
전체 차량 system TC나 M8 C++ 속도 폐루프를 M6 종료 조건으로 추가하지 않는다.

| M6 필수 산출물 / 관련 요구의 부분 범위 | 구현·기존 검증 근거 | 판정/한계 |
| --- | --- | --- |
| Simple Vehicle / SYS-CTRL-001·002, SYS-ARCH-002 | [모델 ICD](icd/simple_vehicle.md), `simulation/vehicle/simple_vehicle.*`; 실제 torque/pressure/angle→전진 운동·bicycle pose, finite/time/identity 검증·원래 step 보존 | 완료. 평지/전진/no-slip 근사, OEM calibration·S01 전체 차량 추종 아님 |
| actual actuator·센서·네트워크 / SYS-ARCH-003, SYS-COM-002·004 | [3-vECU 근거](test-plan/evidence/m5_someip_rear_adapter/README.md), [M6 첫 연결](test-plan/evidence/m6_simple_vehicle/README.md); Central·Front·Rear 별도 process, 실제8 ACK/RunLease/arm, CAN/P05, 실제 wheel sensor→Drive→Rear→SOME/IP→Central validator | 완료. 시나리오 입력과 단일 persistent SIL physical process는 fixture. 공유 감시/물리 채널이 명령·권한을 우회하지 않음 |
| EV 전원·Battery/BMS·실제 회생/마찰 / SYS-EV-001–005, SYS-CTRL-008·009 | [에너지 근거](test-plan/evidence/m6_vehicle_energy/README.md), `VehicleEvModel`/`EvPowerModel`; 정상 시동·stop/HV-off, 실제 charge-zero SOC0.96/BMS0W, owner-pause·Rear 새 Epoch 재가입 | 완료한 유한 Normal FIFO quiet 기능 범위. 전체 EV 고장 조합/차량 calibration 수용 아님 |
| 구간 에너지 수지 / SYS-CTRL-009, SYS-COM-004 | [에너지 ICD](icd/vehicle_energy.md), 동일 motor work·candidate 동시 commit, independent ledger. Normal received DC194.015J, friction776.297J, max residual1.630e-8J<0.001J | 완료. chemical/kinetic/마찰/회로 손실의 단일 소유권, 원천 dependency 유지. SOC 증가를 회생 필요조건으로 삼지 않음 |
| 물리 보호 응답 / SYS-SAFE-004, SYS-COM-003 | [최종 응답 근거](test-plan/evidence/m6_physical_response/README.md), [물리 계약](icd/vehicle_energy.md#physical-response-contract). RX→검출<=100ms/로컬 선택<=4ms/최초 선택→실제 토크·1MPa 완료<=230ms | 완료. 실제 command-loss: RX→검출24.195ms, 선택→완료200.925ms. 기존 rate·권한·expiry·2ms/4ms·20ms envelope 유지. 다른 fault profile의 과거 판정은 그대로 |
| 종방향 실행 모델/MIL / SYS-CTRL-004·007, SYS-COM-004·SYS-SAFE-002의 모델 부분 | `models/longitudinal/model.py`, `mil.py`, [고정 MIL protocol](test-plan/evidence/m6_simple_vehicle/protocol.md). Python binary64/PI20ms·plant2ms·speed50ms, 고정30/20/0km/h reference87s·1741sample | 완료. 각 plateau5s settling+10s/200sample; max error0.049180/0.046337/0.005251km/h, overspeed1.2233%. saturation/slew·stale/invalid/permission loss/새 INIT 계약 포함. 독립 Python 근사이며 실제 C++ 폐루프 아님 |
| 변경 경계/원본·재현성 | [최종 결과 JSON](test-plan/evidence/m6_physical_response/results-summary.json): Normal/ASan 각1018/1018, 실제 TSan 경계35/35, Python/무build export 각54/54 | 기존 결과 대조 완료. 비계측35회는 TSan 수용에서 제외. SDK 전체 sanitizer 기능은 아래 OPEN이며 component PASS로 대체하지 않음 |

각 행은 관련 요구의 **M6 부분 증거**다. 원래32 requirement/29 system TC의 전체 Result는
[추적성](test-plan/traceability.md)대로 NOT RUN이며, 이 종료 검토로 PASS로 바꾸지 않는다.
M6 물리 후속 실제 SDK3회는2PASS/1FAIL(관측기 수정 전 FAIL 보존), 수정 후 command-loss1/1과
영향 없는 nominal1/1이 수용 근거다. 에너지 단계5/9·개발 포함5/12와 첫 MIL FAIL도 유지한다.

## TBD의 M6 결정과 후속 경계

| ID / owner | M6에서 결정·검증한 부분 | M7 이후 결정할 부분 / 선행 gate |
| --- | --- | --- |
| TBD-02 / plant·interface | [SimpleVehicleConfig](../simulation/vehicle/simple_vehicle.hpp):1000kg/r0.3m/wheelbase2.7m, aggregate friction0.001Nm/Pa, rolling100N/drag0.4, actual/source/skew·wheel 기준. allocator와 일치 | M7 CARLA 좌표·geometry·steer 정규화/Drive·마찰 한 번씩 적용하는 mapping. 실제 차/OEM/tire/후진·경사 calibration은 범위 밖 |
| TBD-03 / vECU·plant | 현재 finite delay/rate/limit/초기값, normal stop standing-hold·60ms dwell. [M6 response JSON](../profiles/m6_sil_response_v1.json)의 양·음수 torque→0/실제 brake floor 병렬230ms 산정·실측 | M7 외부 vehicle response와의 중복 dynamics 방지·mapping 오차/물리 응답 재검증. 다른 모델/Target/OEM 반응 budget을230ms로 일괄 결정하지 않음 |
| TBD-07 / simulation | 단일 persistent Host physical process가 vehicle·actuator·EV/Battery model/energy를 소유, model epoch와 ECU Epoch 분리. clock/solver·계측 scope 명시 | M7 CARLA/Ubuntu/Python/client/server/ScenarioRunner 호환 버전·GPU·map/route/seed,50ms synchronous tick·single writer·clock/source-age 경계 확정 후 접속 |
| TBD-12 / vehicle management·safety | 실제8-role INIT/Release ACK·RunLease·arm, actual 기반 power sequence/정상 stop/HV-off·새 Epoch 재가입. READY/권한/물리 완료를 구분 | M7 Host–Target clock/transport·외부 plant/LV/charging/interlock·차량 특성에 따른 threshold/반응 범위. 현재 SIL 범위 밖 기능의 차량 수용은 별도 |
| TBD-13 / model | Battery50kWh/400V·SOC 초기0.63/0.96 등 명시 SIL 설정, RC/접점/auxiliary·손실/효율·BMS limits, 실제 회생/charge-zero와 coherent energy 오차 예산. [vehicle-energy 계약](icd/vehicle_energy.md) | M7 에너지/actuation mapping·정밀 battery/thermal/chemistry/OEM calibration. 모델 가정을 실차 특성으로 간주하지 않음 |
| TBD-16 / control·toolchain | [ADR-0063](adr/ADR-0063-simple-vehicle-and-longitudinal-mil.md): Python 표준 라이브러리/binary64·독립 plant, sample/solver/reference/초기 상태/제약 고정, MIL 추종·fault/state 판정 완료 | M8 모델↔C++의 공통 입력 vector·tick별 출력/내부 상태 tolerance·동등성, 생성 도구를 채택할 때 license/재생성/qualification. 미선정 자동 생성 도구는 M6 누락 아님 |

이는 각 TBD의 **M6 부분 결정**이며 ID 전체를 CLOSED로 덮어쓰지 않는다.
Canonical register는 [roadmap](roadmap.md#open-m0-decisions), 모델의 실행 계약은 위 ICD/설정이다.

## 제한과 OPEN

- `OPEN-M6-ENERGY-01`: 현재 SIL 모델/응답 시한 불일치 범위 해소. 옛100ms FAIL과
  옛 로그의1MPa 미완료는 보존한다. 후속 성공으로 과거 FAIL을 바꾸지 않는다.
- `OPEN-M6-ENERGY-02`: 실제 instrumented SDK의 wall/송수신/SDK 오류·기능 미완료는 OPEN.
  메모리/UB/경합 진단0이 전체 기능 PASS는 아니다. 이번 범위 종료의 일괄 선행 조건으로 추가하지 않는다.
- M4 전체 NOT CLOSED, 역사적 OTHER/FIFO/native/물리 pause/DDS OPEN과 DDS 제어 gate CLOSED 유지.
  OTHER 부하 timing은 진단이며, 이번 M6 quiet 수용은 M5 부하 범위를 확장하지 않는다.
- Jetson/실제 IO/Host–Target Ethernet·전체 차량32req/29TC·M7/M8은 미검증.
  학습자 직접 설명/수용 기록은 기술적 범위 종료와 별도다.

## 다음 한 단계 — M7 최초 접속 계약과 환경 확인

첫 작업은 **CARLA 접속 전 호환 환경과 actual-only/synchronous bridge 계약 확정**이다.
M7 구현은 이번 작업에서 시작하지 않았다. 다음 작업에서 확인할 선행 조건은 다음과 같다.

1. 사용할 Host GPU/OS·CARLA server/client·Python·ScenarioRunner 호환 버전과 실행 환경을
   실제 자원/공식 호환 근거로 고정한다(TBD-07). 설치/권한·Target 가용성은 확인 결과로 구분한다.
2. 기존50ms 동기 tick/orchestrator와 Plant Adapter 단일 ego writer를 적용하고,
   원래 actual/identity/source/expiry가 보존되는 인터페이스·역방향 state/sensor를 정의한다.
   특히 CARLA20Hz state와 기존 Drive30ms source-age의 차이를 명시적으로 해결해야 한다.
   cached state restamp/직접 raw command fallback으로 연결하지 않는다.
3. M6 모델과 CARLA 중 각 inertia/actuator/energy 상태를 누가 한 번만 계산하는지,
   torque/압력/steer·좌표 mapping·clock/pause/reset·invalid containment를 고정한다.
   실제 Host–Jetson 배포는 BSP/ABI·NIC/clock/권한 확인 후 별도 검증하며 M6 결과로 대체하지 않는다.

M4/DDS/SDK OPEN 전체 해소나 새로운 극단·복합고장을 이 첫 작업의 선행 조건으로 만들지 않는다.

## 저장소 정리·검증 기록

현재 상태는 [project_status](project_status.md), 단계/TBD는 [roadmap](roadmap.md),
이력/원본은 기존 evidence와 [품질 기록](quality_policy.md)로 역할을 나눴다.
중복 물리 응답 ICD를 vehicle-energy의 위 절로 통합하고 이전 링크를 갱신했다.
내용이 생긴14개 디렉터리의 불필요한 `.gitkeep`만 제거했다. 다른 빈 디렉터리 placeholder,
원본/실패/중복 cohort CSV·archive·재현 script·codec 초안·사용자 build/측정 자료는 보존했다.
실행 script/fixture는 빌드·시험·문서/재현 참조를 대조했으며 삭제 대상으로 입증된 것은 없었다.

문서 링크/앵커·요구사항/112개 component 추적성·M6 archive/재현 경로를 정적 검증한다.
실행 코드/모델 수치/전송 계약 변경이 없으므로 새 C++/SDK/48회 타이밍 시험은 수행하지 않는다.
최종 정적 검증(새 runtime 실행 아님):

- 마크다운199개(이전199개와 동일), 로컬 링크/앵커1888개: 깨짐0.
- component112개: 요구사항/구현/evidence 경로 누락0. 기존1018개 XML에105개 C++ 이름이 존재하고,
  나머지7개는 별도 DDS diagnostic/Python 연결로 분류했다.32개 requirement/29개 system TC와
  Result 표, component CSV·stable interface ID는 변경하지 않았다.
- M5 Rear 및 M6 model/energy/physical archive4개의 SHA 일치. 기존 최종 MIL1741sample/3plateau
  결과와 현재 model.py/mil.py source hash를 archive에서 대조했다. 기존 결과를 재실행 결과로 세지 않았다.
- 재현 명령8개 runner 옵션·CMake target·5개 Python 진입 경로를 정적으로 확인했다.
  실제 script/fixture·빌드·공통 로직 변경0, `.gitkeep` 제거 디렉터리14개 모두 다른 tracked 내용이
  존재하고 실행 경로에서 marker 참조0. YAML은 수용 상태 문자열2개만 변경, 실행 JSON/모델 수치 불변.
- `git diff --check` PASS. C++ 전체/SDK/MIL/48회 타이밍 신규 실행0회.

실패 원본·NOT RUN·OPEN을 삭제/승격하지 않았으며 무시된 build/사용자 측정 자료는 정리하지 않았다.
