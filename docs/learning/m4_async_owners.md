# M4 정상 경로: owner마다 실행하고 결과를 기다리기

Status: **Native Host component 구현·시험 / 전체 M4 수용 후속**.
현재 상태는 [project_status](../project_status.md), 설계는 [ADR-0055](../adr/ADR-0055-asynchronous-normal-owner-integration.md)를 따른다.

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
다음은 방향별 partition·owner 정지 시험 확대와 M3 선택 profile의 통합 workload 반복 측정이다. 이후 remote Leaf lifetime/arm/lease/protection 계약과 SocketCAN transport·독립 process·M5 DDS/Host bridge를 연결한다.
