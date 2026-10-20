# M4 정상 경로: owner마다 실행하고 결과를 기다리기

Status: **Native Host component 구현·시험 / 전체 M4 수용 후속**.
현재 상태는 [project_status](../project_status.md), 설계는 [ADR-0055](../adr/ADR-0055-asynchronous-normal-owner-integration.md)를 따른다.

명령 결과 대기와 다음 배분 주기의 경계는
[ADR-0059](../adr/ADR-0059-pending-command-allocation-settlement.md)로 보완했다.
진행 중인 batch가 있으면 다음 배분 한 건을 보류하고, 성공 후 최신 입력으로 계산한다.
대기 자체를 전달 실패로 취급하지 않지만, 원래 응답 deadline과 이미 적용한 명령의 expiry는
각각 계속 검사한다. 대기 중 allocator poll도 완료된 tick으로 기록하지 않는다.
Rear19.8ms와 양쪽12ms 지연의 서로 다른 보호 경로, 실제 출력 발행 관측과 재현 결과는
[후속 근거](../test-plan/evidence/m4_settlement/README.md)에 있다.

이번 경로는 `요청 → Central 판단 → Zone 검증/전송 → Leaf 제어 → 실제 sensor → Zone → Central`을 실행한다.
`VehicleCoordinatorPort`가 다른 객체를 곧바로 호출하던 연결을 방향별 mailbox로 바꿨다.
이전 EV 예제는 개별 모델 fixture로 유지하고, 새 `m4-async` 명령은 실제 VM·allocator·BMS·Power 판단을 사용한다.

## 먼저 읽을 코드

| 순서 | 코드 | 확인할 부분 |
| --- | --- | --- |
| 1 | [owner_transport.hpp](../../interfaces/zone/owner_transport.hpp) | enqueue/result와 protection 분리, global gate, scope·token·원래 deadline |
| 2 | [async_coordinator_port.cpp](../../central/coordinator/async_coordinator_port.cpp) | 실제 grant 수신/parent 조회, Front 성공 뒤 Rear dispatch, missing result deadline |
| 3 | [vehicle_coordinator.cpp](../../central/coordinator/vehicle_coordinator.cpp) | pending arm·allocation 재개·terminal ACK 뒤 Shutdown |
| 4 | [async_zone_owner.cpp](../../zone/gateway/async_zone_owner.cpp) | 각 Zone의 독립 gateway/RX/health와 Leaf ACK 집계 |
| 5 | [async_leaf_owner.cpp](../../simulation/runtime/async_leaf_owner.cpp) | 자기 controller만 수정, queue 대기 뒤에도 원래 expiry 검사 |
| 6 | [m4_async_runtime.cpp](../../simulation/runtime/m4_async_runtime.cpp) |9개 owner·절대 release·sensor/물리 출력·고장 주입·논리/실제 실행 |

**발급과 수신은 다르다.** 새 permission을 queue에 넣었다고 Drive나 Central RX가 받은 것은 아니다.
실제 수신된 frame에 대응하는 원래 parent를 찾아야 한다. 이전 grant를 새 grant의 parent와 섞으면 안 된다.

**Run gate는 세션당 한 번 연다.** 모든 INIT/Release ACK 뒤 열고 보호 시 닫는다.
Zone·Leaf의 로컬 보호도 즉시 atomic gate를 닫는다. 같은 Epoch의 일반 polling이 gate를 다시 열지 않으며 Central이 새 세션의 준비를 다시 완료해야 한다.

**주기와 최소 호출 간격도 다르다.** 10 ms task가 OS 지터로9.9 ms 간격에 호출될 수 있다.
외부 release가 주기를 소유하고 함수는1 ms의 중복 호출 guard를 사용한다. Actual/source timestamp는 실제 취득 시각이며 release 시각으로 바꾸지 않는다.
기존30 ms gap·source/dependency age·expiry는 유지한다. IO만200 μs로 service하고 제어 주기를200 μs로 바꾸지 않는다.

**부분 성공은 존재한다.** Steering frame enqueue 후 Brake가 실패하면 해당 Rear batch를 보내지 않는다.
정상 FIFO가 가득 차도 priority protection은 전달한다. Selection ACK와 물리적 pressure/torque 응답은 따로 관측한다.

**물리 값이 알려졌다고 모든 capability가 알려진 것은 아니다.** fresh torque/speed는 유지돼도 regen capability가 unavailable일 수 있다.
이 경우 새 regen 대신 기존 friction fallback을 사용한다. 오래된 capability의 dependency를 현재 시각으로 바꾸지 않는다.

## 직접 실행

```sh
cmake -S . -B build/m4-readiness -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m4-readiness -j 4
mkdir -p build/m4-manual
build/m4-readiness/actuator_demo epoch init build/m4-manual/epochs
build/m4-readiness/actuator_demo m4-async logical normal build/m4-manual/epochs build/m4-manual/normal
build/m4-readiness/actuator_demo m4-async wall feedback-loss build/m4-manual/epochs build/m4-manual/loss
build/m4-readiness/actuator_demo m4-async logical rejoin build/m4-manual/epochs build/m4-manual/rejoin
```

Epoch store bootstrap는 최초1회만 명시적으로 한다. 출력 directory는 매번 새 경로를 쓴다.
재가입용 두 grant는 thread 시작 전에 durable하게 발급하고, 정해진 시점에 두 번째 grant로 새 준비를 시작한다.
CSV의 `source_ns`는 physical acquisition, `*_source_ns`는 별도 Central current feedback/issued command의 원래 시각이다.
0인 feedback source는 unknown이며 현재 시각으로 대체하지 않는다. `startup.json`은 application grant와 continuing model Epoch를 기록한다.

전체 자동 검증과 근거 생성은 다음 하나로 묶었다. 새 raw directory를 지정해야 하며 실패 결과도 남는다.

```sh
python3 tests/integration/runtime/check_m4_async.py \
  --raw-dir build/m4-async-verification-new --output build/m4-async-evidence-new
```

Normal/sanitizer 전체 CTest와 durable CLI 재가입을 순서대로 실행한다. Target commit·source fingerprint·환경을 기록하고
추적표의 실제 test/function 참조를 확인한 뒤 작은 CSV·JSON·SVG를 만든다.
코드 fingerprint가 같으면 `--reuse`로 이미 실행한 XML/CSV를 사용한다. 당시 tested commit을 유지하며 변경된 코드에는 재사용하지 않는다.
저장소에 남긴 결과와 수치·판정은 [대표 근거 안내](../test-plan/evidence/m4_async/README.md)에 있다.

## 검증 범위 구분

Logical 시험은 동일 port/owner를200 μs 논리 step으로 실행한다. Wall 시험은 start gate 뒤9개 thread가 독립 실행하며 cycle barrier가 없다.
후자의 elapsed time·body mean/P95/P99/max·gap과 protection response를 실제 monotonic clock으로 측정한다.
일반 scheduler의 이번 Host 관측이며 WCET·임의 부하·Target/RTOS timing 보장이 아니다.

Normal·normal-stop·partial Front·feedback loss·vehicle-root loss·partial arm·explicit rejoin·old Epoch를 검사한다.
제어 대상 speed는0 fixture이고 angle/pressure/torque·RC/Battery 반응은 실제 기존 모델이다. SOC/energy는 단일 EvPowerModel owner가 갱신한다.
차량의 운동·회생 energy 검증은 기존 M2 component 증거와 M6–M8 계획을 구분한다.
후속 공통 고장 주입·독립 감시·CPU/FIFO 반복 측정은 아래와 [ADR-0056](../adr/ADR-0056-m4-faults-and-independent-execution-watch.md)을 따른다. Remote Leaf lifetime/arm/lease/protection 계약은 아래 component 시험까지 진행했다. 실제 transport·독립 process·M5 DDS/Host bridge 통합은 다음 경계다.


## 정상 경로에 고장을 넣고 복구하기

기존 `m4-async` 실행에 여러 `fault=` 옵션을 넣을 수 있다. 새 Epoch store는 명시적으로 최초 bootstrap하고 각 output은 새 directory를 사용한다.

```sh
build/m4-readiness/actuator_demo epoch init build/m4-fault-manual-epochs
build/m4-readiness/actuator_demo m4-async logical fault build/m4-fault-manual-epochs build/m4-fault-manual-owner fault=owner:pause:drive:1200:200:0
build/m4-readiness/actuator_demo m4-async wall fault build/m4-fault-manual-epochs build/m4-fault-manual-rejoin fault=zone-central:overflow:rear:1200:200:0 duration-ms=4200 recover-ms=2300 replace-links
build/m4-readiness/actuator_demo m4-async wall fault build/m4-fault-manual-epochs build/m4-fault-manual-guard guards cpus=0,1 fifo duration-ms=2540 fault=owner:overrun:monitor:1200:6:0
```

Recipe는 `path:kind:target:start_ms:duration_ms:delay_ms[:phase]`다. 시각 단위는 정수 ms, 기준은 run 시작이다. Duration0은 지속이다.

| Path | Kind / target | 쓰는 곳 |
| --- | --- | --- |
| owner | pause/overrun; central/front/rear/steering/brake/drive/bms/power/physical/monitor | 세션·RX·제어·자체 감시 전체 정지; monitor는 guards 필요 |
| central-zone / zone-central | drop/delay/overflow; front/rear | request와 TX result/status/Actual 방향 |
| zone-leaf / leaf-zone | drop/delay/overflow; steering/brake/drive/bms/power | command/operation과 Leaf result/Actual 방향 |
| session-control / session-ack | drop/delay/overflow; front/rear/steering/brake/drive/bms/power/central | Prepare/INIT/Release 경계; 선택 phase로 prepare/init/release 지정 |

Phase `arm`/`stop`은 해당 operation/result만 대상으로 한다. Delay는 delay_ms를 사용하며 원래 source/deadline은 유지한다.
Overflow는 실제 pop을 막아 FIFO를 채운다. 고장이 끝나도 failed latch는 남으며 owner join 뒤 교체해야 한다.
`recover-ms`는 명시적 복구 요청이며 단순 pause 해제와 다르다. 더 큰 durable Epoch·전체 session·fresh 물리 준비·readiness/arm이 필요하다.
Physical 모델은 계속 존재하고 SOC/energy/angle/pressure/torque/전원과 model identity를 초기화하지 않는다.

## Event와 실제 실행 감시 읽기

`*-events.csv`는 실제 주입, valid input/feedback, controller fault, gate 관측, Leaf 선택/Zone ACK, physical watchdog/override, 복구/normal-authorized를 구분한다.
`source_ns`는 원천, `deadline_ns`는 원래 기한, `reference_ns`는 사건별 기준이다. 유효 Leaf 입력의 reference는 실제 receiver에 넘긴 RX 시각이다.
설정 주입 시각·첫 실제 차단·마지막 유효 수신·원래 command expiry를 서로 대체하지 않는다.
Owner 번호는 Front0/Rear1/Steering2/Brake3/Drive4/BMS5/Power6/Central7/Physical8/Monitor9다.
멈춘 owner의 missing ACK와 살아 있는 경로의 선택 mask를 함께 읽는다. Physical watchdog(owner8)은 멈춘 ECU의 ACK가 아니다.

`guards`는 열 번째 독립 Monitor를 추가한다. 기존 M3 monitor가2 ms service 기회의4 ms deadline을 검사하고 Physical이 Monitor를 감시한다.
`*-execution.csv`의 slot/release/deadline/start/end/CPU/detected 시각으로 누락·늦은 완료·독립 검출을 구분한다.
기존 IO body>4 ms 통계가0이어도 실행 기회가 누락될 수 있다. 실제 제어10/20 ms 주기·5/8 ms 자체 admission 검사도 별도 event다.
`cpus=A,B`와 `fifo`는 실제 적용된 thread 정보를 JSON에 남기며 권한 실패 시 정상 실행으로 대체하지 않는다.

전체 회귀·prospective48회 cohort·최소 근거 생성은 다음 명령이다. 측정 중 다른 build/시험을 병행하지 않는다.

```sh
python3 tests/integration/runtime/check_m4_faults.py \
  --raw-dir build/m4-fault-new --output build/m4-fault-evidence-new \
  --timing-dir build/m4-timing-new --run-timing
```

재현 조건·PASS/FAIL 분모·원본 경로·대표 CSV/그래프는 [공유 근거](../test-plan/evidence/m4_faults/README.md),
사전 시한·부하·반복 조건은 [프로토콜](../test-plan/m4_fault_timing_protocol.md)에 있다. 저장소의 대표 결과와 학습자의 직접 실행·이해 확인은 별개이며 학습자 검토는 PENDING이다.
공유 atomic gate/protection이 통신 차단을 우회하는 같은 프로세스 시험이다. 원격 process/네트워크 단절·하드웨어 watchdog·Target timing 검증은 후속이다.


## 후속 모듈·시험 선택과 원격 경계

현재 실행 entry는 `m4_async_runtime.cpp`, private owner 상태/연결·시나리오/물리는 `m4_owner_network.*`, logical/native launch·join은 `m4_owner_execution.cpp`, join 뒤 판정/저장은 `m4_result.cpp`다. Canonical 메시지는 `interfaces/zone/owner_messages.hpp`, 같은 process SPSC/atomic만 `local_owner_transport.hpp`에 있다. 동기/비동기 INIT은 공통 `session_reset_safe`를 사용한다.

기존 GTest/CTest 이름은 보존했고 label은 서로 겹치지 않는다. 현재948개는 unit798/logical141/wall9다.

```bash
ctest --test-dir build/m4-readiness -L unit --output-on-failure
ctest --test-dir build/m4-readiness -L integration.logical --output-on-failure
STRATADRIVE_M4_RESULTS="$PWD/build/my-m4-wall" ctest --test-dir build/m4-readiness -L runtime.wall --output-on-failure
```

[원격 ICD](../icd/owner_wire_v1.md)는 local Release만으로 global 준비를 추정하지 않도록 별도 run credit를 요구한다. 실제 Leaf endpoint component는 wire→INIT/credit→arm→command/Actual→보호/재가입을 시험했다. 같은 process global atomic 효과를 원격 보장으로 옮기지 않는다. [후속 evidence](../test-plan/evidence/m4_followup/README.md)와 [M4 종료 검토](../m4_exit_review.md)에서 새 timing/TSan FAIL과 candidate echo의 범위를 확인한다. 전체 M4·M5 제어 배포·학습자 review 완료가 아니다.

외부 검토 후 [계약3개와 전달 trace](../test-plan/evidence/m4_contract_review/README.md)를 보완했다.
전송 envelope는 최초 `sent_ns`부터 최대20ms이며, 내부 command/parent/stop lease의 유효기간과 별개다.
이전 Epoch의 거절 응답도 원래 identity를 유지하고, 같은 보호 token의 ACK는 최초 선택 시각을 유지한다.
실제 Zone 출력→codec→다섯 Leaf→Actual/정상 Stop을 논리 통합으로 확인했다.

CLI의 `trace-transport` 또는 GTest의 `STRATADRIVE_M4_TRANSPORT_TRACE=1`을 켜면
`*-transport.csv`에 원래 source/expiry·enqueue·Zone RX/dispatch·Leaf handling 완료·결과 수신이 남는다.
각 owner의 사전 할당 로그를 join 뒤 수집하므로 실행 중 공용 logger를 공유하지 않는다.
Leaf handling 완료는 실제 압력/토크 도달이 아니며 물리 CSV를 함께 읽어야 한다.
고정40회 진단은 과거 TSan 실패를 재현하지 못했고, 새48회 timing은 FIFO 추가 실패를 포함해41/7이다.
학습자의 직접 재현·이해 확인은 아직 REVIEW PENDING이며 M4 종료·M5 adapter 착수는 보류한다.
