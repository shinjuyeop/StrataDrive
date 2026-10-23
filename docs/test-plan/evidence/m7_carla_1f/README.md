# M7-1f — 별도 functional clock와 native8-role CARLA shadow

2026-10-23, HEAD7a2b0fa + 기존 미커밋 M7 작업. 사용자의 후속 해결 요청으로 구현했다.
**판정: 느린 CARLA wall 실행과 ECU logical freshness를 분리한 기능 검증 경로 구현·한정 PASS.**
**CARLA 정상 주행·wheel sensor 입력·calibrated actuation은 NOT RUN / 연결 BLOCKED.**
M6 코드·profile·종료 수치/수용과 source30ms·global credit60ms·20ms 전달 envelope를 변경하지 않았다.
CARLA source build/추가 설치, AI 학습, Jetson 실행은 하지 않았다.

## 구현한 경로

[FrameClock](../../../../tests/integration/carla/m7_1f/frame_clock.hpp),
[native rig](../../../../tests/integration/carla/m7_1f/functional_rig.cpp),
[CLI](../../../../tests/integration/carla/m7_1f/shadow_main.cpp),
[CARLA owner](../../../../tests/integration/carla/m7_1f_shadow.py).
정규 backend가 아닌 opt-in 시험 코드이며 `STRATADRIVE_M7_FUNCTIONAL_TESTS`는 default OFF다.

1. Python 단일 owner가 snapshot의 원래 frame/elapsed/delta와 run/application/plant scope,
   별도 clock domain을 native process에 보낸다. GT/RGB/body speed/wheel은 이 입력에 없다.
2. native 시간은 원래 elapsed seconds를 ns로 반올림한다. CPU/도착 시각을 원천으로 바꾸지 않는다.
   기존 native owner들을 동일 논리 시각에 실행한다. ingress0.2ms·fixture1ms의 내부 job grid와
   Controller root20ms·Host10ms child allocation·leaf10ms/BMS20ms를 유지한다.
3. 실제8역할 actor의 Prepare/INIT/Release ACK, 원래 SessionCoordinator/RunLeaseIssuer,
   각 역할의 개별 RunLeaseGate를 사용한다. Release ACK8개 전 credit0. 정상 명령은
   Central→Front/Rear Zone→vECU→physical fixture→Actual→Zone→Central 경로를 거친다.
   제어/ACK/외부 역할 lease는 기존 v1 codec 왕복, 정상 경로는 in-process typed queues다.
   Central self-credit은 local binding이다. SOME/IP/실제 분산 프로세스 검증은 아니다.
4. 모든 역할이 해당 진행 구간에서 처리된 후 NON_DRIVING next-frame permit을 발급한다.
   `service_mask`는 처리 barrier, `release_mask`는 실제 Release ACK, `credit_mask`는 실제 lease
   수용으로 구분한다. armed fixture의3Actual 원래 source가 다음10ms 끝까지30ms 이내인지 검사한다.
   누락/오래된 source, clock/frame/scope 오류는 latch하고 추가 tick을 막는다.
5. Python은 permit 이후 world tick1회와 반환 frame을 확인한다. 늦은 wall 응답은 logical time을
   바꾸지 않는다. pause 중 native STEP/lease 갱신도 없다. RPC/IPC 실패 뒤 retry해서 진행하지 않는다.

**중요한 범위:** `PhysicalOwner(simple_vehicle=false)`를 stationary actuator/electrical fixture로
재사용한다. wheel=0은 이 fixture 값이며 CARLA 관측이 아니다. CARLA ego는 physics off,
actuation API 호출0이다. native 실제 actor/Actual 경로 검증과 CARLA 실제 차량 주행은 별개다.
source-only interval 검사는1c의 oldest dependency/exclusive support expiry/full apply admission을
대체하지 않는다. actuator-only backend/energy 결합·새 wheel 원천은 아직 연결하지 않았다.
기존 wall2ms/4ms guard를 logical 시간으로 바꾼 것이 아니며 해당 wall 검증은 NOT RUN이다.

## Native 검사

[시험](../../../../tests/integration/carla/m7_1f/functional_test.cpp):
Normal [14/14](native-normal-final.xml), ASan/UBSan [14/14](native-asan-final.xml).
final 빌드는 `-Wall -Wextra -Werror`, ASan은 `detect_leaks=1`을 사용했다.

- 원래 simulation ns 보존,8역할 barrier, 중복 receipt/permit, pending 덮어쓰기, 다른 thread,
  frame duplicate/skip/rollback/overflow, 잘못된 domain/run/application/plant·50ms delta 거부.
- 실제 native8-role INIT/Release/credit/arm·Actual 반환, Controller20ms·leaf10ms/BMS20ms 확인.
- 80ms wall pause 이후 logical10ms만 진행. lease 갱신 중단 시 원래30ms source-age에서 차단·
  같은 instance로 복구 불가. 역할/Actual 누락도 tick permit 차단.
- 새 scope instance는 다시 INIT/Release가 필요하며 old scope를 거부한다. 실제 CARLA reload/reset이나
  영속 EpochStore 연결 시험은 아니다. trusted test scope1/42/7을 production grant로 쓰지 않는다.

[관련 회귀](regression.json): 기존 remote contract30 + remote leaf/Zone24 + session24 +
Drive44 + M4 async22 = **144/144**, 기존 M7-1c **39/39**.
M6 전체1018/전체 SDK/wall qualification은 재실행하지 않았으며 역사적 결과에 합산하지 않는다.

**첫 빌드 실패 보존:** [build-normal-01.log](build-normal-01.log)의 test 소스
`-Wmisleading-indentation`과 mixed float/double initializer-list 오류2건을 수정했다.
그 뒤 build02/Normal01·ASan01은 통과했다. frame uint64 overflow 거부와10ms leaf assertion을
추가한 final 빌드/시험도 통과했다. 최초 실패를 삭제하거나 처음부터 PASS였다고 기록하지 않는다.

## CARLA 실행 결과

기존 공식0.9.16/bundled Python3.10 venv, RTX3090/driver580.178.04, Town10HD_Opt,
mkz_2020, offscreen Vulkan Low, traffic0. RGB/GT800×600/FOV90/sensor_tick50ms,
rigid pose(1.5,0,1.7)m. camera는 metadata를 수집했고 native 입력에는 사용하지 않았다.
[현재 환경/최종 binary hash](environment.json), [최종 source hash](sources-harness.json).

| 관측 | run-01 | run-02 (최종 구현 확인) |
| --- | --- | --- |
| world10ms tick/8-role 처리 barrier | 320/320 | 320/320 |
| native fixture armed frame | 242, 첫 index78 | 242, 첫 index78 |
| Actual source 최대 age / 다음 interval 끝 age | 8.999983 / 18.999983ms | 8.999982 / 18.999982ms |
| native IPC+barrier wall Mean / Max | 1.199 / 5.997ms | 1.132 / 2.424ms |
| 지연 주입 | 100ms slow-host +250ms pause | 동일 |
| 마지막 중복 observation | 거부·native exit1·추가 tick0 | 동일 |
| cleanup | owned actor0·설정 복원·listener0 | 동일 |
| 서버 SIGTERM 종료 | **139 / FAIL** | **139 / FAIL** |

원본: [run01 summary](run-01/capture/summary.json), [run02 summary](run-02/capture/summary.json),
[run02 raw trace](run-02/capture/frames.jsonl.gz), [run02 분석](run-02/analysis.json).
run01은 초기 구현 관측이고, frame overflow guard·source/binary hash 기록을 추가한 뒤 run02를
확인했다. 서로 다른 실행의 분모를 합쳐 wall timing 수용으로 주장하지 않는다.
run02 source/hash는 실제 실행 직전에 기록되어 저장소 최종 코드와 대조 가능하다.

source-age 최대값은 **native stationary fixture의 Actual** 값이다. CARLA wheel acquisition
age가 아니다. 의도적 pause를 포함한 run02 최대 wall tick 간격252.042349ms는 숨기지 않았다.
logical 계약을 지키는 별도 functional 모드임을 보여주며 wall100Hz/Drive30ms 또는 기존
100ms loss 검출/230ms 물리 응답 PASS 근거로 사용하지 않는다. native barrier 시간도 여러
논리 sub-job/IPC를 포함하므로 M6 단일 native owner4ms completion과 비교 판정하지 않는다.

각 새 서버의 cold readiness timeout1건과 종료139를 [run01](run-01/process.json),
[run02](run-02/process.json)에 보존했다. 기존 **OPEN-M7-1D-01 유지**. child core limit0,
SIGKILL 없음. M7-1B native reload/server crash OPEN도 이 시험으로 해결되지 않았다.

## 재현·독립 판정

```sh
cmake -S . -B build/m7-functional -DBUILD_TESTING=ON -DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON -DSTRATADRIVE_M7_CONTRACT_TESTS=ON
cmake --build build/m7-functional --target m7_functional_test m7_functional_shadow -j 6
build/m7-functional/tests/integration/carla/m7_1f/m7_functional_test
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -I tests/integration/carla/m7_1f_shadow.py --server /d/shin/stratadrive-tools/carla-0.9.16/server --native build/m7-functional/tests/integration/carla/m7_1f/m7_functional_shadow --output /d/shin/stratadrive-tools/carla-0.9.16/m7-1f/new-run
python3 tests/integration/carla/analyze_m7_1f.py /d/shin/stratadrive-tools/carla-0.9.16/m7-1f/new-run
python3 tests/integration/carla/check_m7_1f_oracle.py /d/shin/stratadrive-tools/carla-0.9.16/m7-1f/new-run
```

server 포트가 사용 중이면 기존 프로세스에 손대지 않고 중단한다. output은 새 경로여야 한다.
runner exit0는 capture 완료이며 server139를 PASS로 바꾸지 않는다. duplicate injection 후
native exit1은 기대한 거부다. 초반 startup에는 NON_DRIVING tick만 허용하고 lease/arm0을 기록한다.
저장소 gzip raw를 임시 복사본에 풀면 같은 독립 oracle로 재계산할 수 있다.
[6개 oracle 변조 거부](oracle-negative.json), [검증 기록](validation.json), [SHA256SUMS](SHA256SUMS).

## 해결 범위와 다음 작업

Host가 느려도 source timestamp를 바꾸거나30ms를 늘리지 않고 원래 ECU/권한 기능을 검증할
실행 경로를 확보했다. **실제 차량 정상 주행까지 해결한 상태는 아니다.**
다음은 [ICD의 M7-1g wheel 계획](../../../icd/carla_plant_adapter.md#m7-1g-wheel-검증-계획)에 따라
무동력 회전 관측·단위/부호/wrap·구간 평균 각속도와 oldest dependency 의미를 확인한다.
이후 actuator-only port 분리 → 차종별 rad/Nm/Pa calibration → full Actual admission/apply ACK/tick
연결을 각 작은 작업으로 수행한다. 패키지 telemetry로 불가능하면 서버 확장 또는 SIL motion
소유 대안을 비교한다. 현재 backend 소유권 변경·source build·임의 normalization은 채택하지 않았다.
