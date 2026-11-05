# M9 BMS·Power 센서 고장의8-role 차량 연결

2026-11-05. Base `835717c67d2bfd125c7e5e530ecea30b277332d3`.
[사전 protocol와 기대값 교정](../../native-sensor-matrix-protocol.md),
[검증 집계](acceptance.json), [최종 source](sources.json), [무결성](SHA256SUMS)을 따른다.
M9 전체 완료 판정은 아니다.

## 범위와 결과

실제 Central/Front/Rear/Steering/Brake/Drive/BMS/Power의 기존 논리 owner와 단일 EV·
SimpleVehicle를 함께 실행했다. BMS trip9조건, Power 센서3조건, BMS170과 Power의 동시
3조건을 고정했다. 각각 입력만 복원하는14s와 새 전역 Release로 복구하는24s를 실행했다.
최종 Debug·ASan/UBSan·TSan 각각30개 시나리오의 원본을 별도 archive에 보존한다.

검출·원본 native reason/시각·보호·실제 torque/brake·정지/HV-off·durable DTC를 연결했다.
복원 후에는 Failed를 유지하고 새 세션에서 BMS release dwell/Active 또는 Power HV Ready를
확인해야 Passed가 된다. Count/generation1·이력을 유지하고 자동 clear하지 않는다.
원래 source/dependency/model epoch·20ms BMS/10ms Power·40ms trip dwell·100ms 보호·
230ms torque/brake 응답 기준은 바꾸지 않았다.

센서 값은 해당 ECU가 소비하는 사본에만 주입했다. 물리 모델에 배터리 과전압이나 접촉기
기계 고장을 일으켰다는 의미는 아니다. 다른 ECU의 센서와 모델 identity·연속 에너지 정산은
유지한다. 기존 electrical component 시험은 별도 근거다.

독립 Python 감사는 CRC/commit을 포함한 canonical journal, 원본 native snapshot/sample,
owner event, 물리 trace를 대조한다. Fault 시각/source·원인·DTC 이력·물리 응답·HV-off·
model sequence·새 Session/Passed proof를 손상하는8종/복구 시11종 mutation을 거절한다.

## 동시 고장의 실제 인과

- BMS170+charger-connected는 자체 고장2개를 기록한다.
- BMS170+접점 불일치는 BMS pending trip inhibition이 Power 정지를 먼저 시작한다.
  Power의 자체 ContactorResponse는 OpenContactors의 원래100ms deadline에서 검출된다.
- BMS170+bus-low는 inhibition 뒤 Ready 검사를 실행하지 않는다. 주입은200ms 뒤 복원되어
  기존1s discharge timeout에도 도달하지 않는다. BMS DTC1개와 Power의 BmsInhibit 전달
  Observation을 보존하며, 없는 Power 자체 고장이나 Passed를 만들지 않는다.

최초 Debug는 이를 모두 Power Ready의10ms 자체 고장으로 가정해15조건 중2조건이 실패했다.
테스트16개 중14개 통과/2개 실패이며 로그와 생성된28개 case 자료를 `initial-debug.tar.gz`에
남긴다. 마지막 동시 bus-low 조건은 첫13s 검사에서 중단되어 해당 case의 전체 trace가 없다.
초기 실행 binary hash는 별도로 수집하지 않았으므로 최종 binary의 증거로 사용하지 않는다.
동작/기한 변경 없이 phase·원인에 맞게 기대값을 교정하고, 원본 source/sample export를 보강한
고정30개 최종 cohort를 다시 실행했다.

전체 회귀에서 발견한 기존 SOME/IP Rear binding 테스트의 TxResult 기대 service도 수정했다.
선행 egress 구현은 이미 결과를 우선 lane5347/534b로 보냈는데 테스트만5346/534a를 기대했다.
현재 우선 경로 수용·이전 경로 및 잘못된 발행자 거절을 검사한다. Production binding은 바꾸지
않았다. 최초 회귀 실패와 수정 후24개 관련 재검사를 함께 보존한다.

## 재현과 artifact

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --target native_sensor_matrix_test --parallel 2
STRATADRIVE_M9_MATRIX_EVIDENCE="$PWD/build/matrix-fresh" \
  build/m1-angle/native_sensor_matrix_test
python3 tests/integration/diagnostics/audit_native_sensor_matrix.py \
  build/matrix-fresh/bms170_power2_recover --mutations
```

Evidence 출력은 새 디렉터리를 사용한다. ASan/UBSan와 TSan은 기존 instrumented build에서
같은 target을 실행하며 TSan은 기존 Host의 `setarch x86_64 -R` 설정을 사용한다.
`validation.tar.gz`에 실제 명령·binary hash·XML·sanitizer 로그·정적 분석·독립 감사 결과와
초기 compile 실패/중단된 회귀 로그를 보존한다. Wall 검사는 sanitizer/빌드와 분리한다.

이 묶음은 SOME/IP 서비스 timing/CARLA 서버 재실행이 아니다. 기존 Host quiet 서비스 분리
판정과 합산하지 않는다. Power precharge/request-loss/shutdown-current/startup-energized/
discharge의8-role 통합, CARLA silent-loss subinterval, Clock 재검증, proposal 이전 bootstrap,
부하·장기 보존은 계속 남아 있다. 현재 목록은 [프로젝트 상태](../../../project-status.md)를 따른다.
