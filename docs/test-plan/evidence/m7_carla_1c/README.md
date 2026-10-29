# M7-1c — Actual-only / single writer / Drive freshness 논리 경계

2026-10-23 (Asia/Seoul), 기준 `7a2b0fa` + 미커밋 M7-1a/b와 이 변경.
**M7-1c fake-backend 논리 범위 완료**다. [M7 계획](../../../carla-guide.md),
[Plant Adapter 초안](../../../interfaces/carla-plant-adapter.md)의07~09를 아래 한정 범위로 검사했다.
기존 M6 source/계약·CAN/P05 bytes·수치·수용을 변경하지 않았다. 새 코드는 test-only이며
CARLA SDK link/서버 실행·actuation·source build, 실제8-role 전송 연결은 없다.

## 구현 경계

[actual_boundary.hpp](../../../../tests/integration/carla/m7_1c/actual_boundary.hpp)는
Simulator 독립 의미 계약을 검토하는 **시험 전용 prototype**이다. 정규 Plant Adapter나
새 wire ABI가 아니다. [contract_test.cpp](../../../../tests/integration/carla/m7_1c/contract_test.cpp)의
fake backend와 기존 receiver/vECU 코드를 연결한다.

- ingress는 optional Steering/Brake/Drive **원래 frame**을 받는다. 값3개를 받는 raw demand
  API가 없다. Actual-configured 기존 receiver가 CAN ID/P05/epoch/source/sequence/validity/
  mode/range를 검사한다. command frame, CRC 오류·invalid·부분 입력은 apply로 갈 수 없다.
- trusted launch context가 run/clock-domain/plant epoch와 역할별 port binding을 고정한다.
  payload가 이 값을 학습/갱신하지 않는다. 역할·run/clock/plant 불일치는 거부한다.
  이것은 fixture의 trusted 입력 검사다. CRC는 인증이 아니며 올바른 route를 사칭한 공격자의
  CRC-valid Actual을 물리 측정인지 판별하거나 실제 peer를 인증한 증거가 아니다.
- `Support.oldest/exclusive_expiry`는 **fixture가 원천에 선언한 measurement support**다.
  기존 CAN에 필드를 추가하지 않았고 command/RunLease expiry와 같은 의미로 바꾸지 않았다.
  원천 command의 완전한 parent·권한 transport는 후속이다. support를 receipt 시각에서
  갱신/생성하지 않는다. 원래 source·causal sequence·CAN bytes·수신 시각을 backend까지 보존한다.
- source/oldest age30ms, input skew10ms와 범위는 M6 fixture 기반의 prototype admission이다.
  유효 Actual과 sender health를 구분하며 Zero target을 실제 torque0으로 대체하지 않는다.
  정상·보호 actual 모두 기존 native 수신 의미를 따른다.
- prepare는 수용 snapshot을 내부에 복사해 ticket과 예상 frame/interval에 묶는다. 이후 caller
  frame/support 변경은 반영되지 않는다. 미래 interval 끝의 age/expiry는 순수 산술로 검사하고
  native receiver clock을 미래로 poll하지 않는다. interval은 `[begin,end)`로 support expiry를
  넘지 않아야 하며 age30ms는 inclusive다. commit이 begin보다 늦으면 소급 적용하지 않는다.
- backend 한 개는 수명 동안 adapter 한 개만 bind할 수 있다(atomic claim). writer handle은
  외부 생성/복사 불가이며 원래 owner thread에서만 쓴다. 중복 claim·다른 adapter handle·다른
  thread·재진입으로 두 번째 적용 권한을 얻을 수 없다. pending 중 입력 교체/INIT도 제한한다.
- ticket은 backend 호출 전에 소비한다. apply 성공 뒤에만 같은 frame의 tick을 한 번 허용한다.
  중복 commit/tick·잘못된 ticket/frame·apply reject/ambiguous·throwing apply/tick은 추가 tick을
  만들지 않는다. 첫 fault는 latch하며 late fresh 입력으로 해소하지 않는다. 새 trusted INIT만
  reset할 수 있고 ticket serial은 reset하지 않아 옛 ticket 재사용을 막는다.
- fixture는 한 owner thread에서 apply와 tick 요청 단계를 직렬화해 검사한다. 실제
  Plant Adapter/orchestrator의 별도 port·process 배치나 외부 CARLA client 차단은 미구현이다.
  CARLA 서버가 writer/tick 권한을 인증해 준다고 가정하지 않는다.
- 유일한 positive mode는 명시적 `FakeProbe`다. NonDriving/CarlaDriving은 항상 Disabled다.
  normalizing coefficient·가짜 calibration·속도/command fallback이 없다. 실제 CARLA backend를
  추가하거나 boolean 하나로 driving을 켜는 기능은 구현하지 않았다.

## 실행과 결과

[결과 요약·최종 source hash](results-summary.json), [최종 Normal XML](final-39.xml),
[ASan/UBSan XML](asan-39.xml), [최종 process exit](final-39-process.json).

| 실행 | 결과 / 범위 |
| --- | --- |
| 최종 Normal | **39/39 PASS**, 네 suite: Contract/M7Ingress/M7Freshness/M7Writer |
| 최종 ASan/UBSan | **39/39 PASS**, detect_leaks·halt_on_error 활성화, sanitizer 진단0. [설정/실행](asan-process.json), [계측 compile 명령](asan-compile-boundary.json) |
| 최종 CTest `m7.contract` | **39/39 PASS**; [원본](ctest-final-39.txt). binary 직접 실행과 같은 시험이므로78개 독립 시험으로 합산하지 않음 |
| 기존 native 영향 검사 | Steering receiver19/19, Brake receiver16/16, Drive codec/receiver21/21, DriveController44/44, ECU boundary20/20 = **120/120 PASS**; 개별 XML/로그와 [process](normal-final-process.json) |
| 기본 configuration | [default-off](default-off.json): 새 option OFF·기본 build에 M7 target 없음. 기존 default M6 test 분모를 변경하지 않음 |
| 실제 M7-1b CLI negative | [원본](collection-cli-driving-rejected.txt), [exit](collection-cli-driving-rejected.json): unsupported `--driving`을 exit2로 거부, output 미생성·Client 생성 전 종료. CARLA 서버에서 driving 권한을 거부한 시험은 아님 |

각 GTest는 독립 assertion 묶음이며 loop의 입력 변형을 별도 test 수로 부풀리지 않는다.
범위는 logical clock/CPU component다. wall100ms 검출·차량 물리 응답·실시간 deadline PASS가
아니다. TSan·SDK·기존 M6 전체1018개 회귀·기존32req/29system TC는 이번에 실행/승격하지 않았다.

### Actual와 writer 검증

원래 Leaf Steering/Brake/isolated Drive 소프트웨어에 command를 수용시킨 뒤 서로 다른 센서
값을 주입해 `complete()`가 만든 Actual CAN을 그대로 사용한 positive case가 있다.
command는 `.05rad/200kPa/25Nm`, 센서/Actual은 `.02rad/100kPa/5Nm`이며 fake backend가 후자를
관측했다. 이는 실제 전송·물리 동특성·전체 Drive EV gate를 우회 연결한 runtime이 아니라
명시적 sensor-port ECU fixture다. Actual-only 판단을 단순 command echo로 증명하지 않았다.

negative는 각 command CAN family, role/run/clock/plant·application epoch 불일치, missing3종,
CRC·invalid·범위, stale/future/oldest dependency/skew, cached source·value 변경을 포함한다.
NaN/Inf는 fixed-integer CAN wire로 정상 인코딩할 수 없으므로 **원래 producer codec 거부**를
시험했다. NaN frame을 수신했다고 주장하지 않는다. 유효 source/sequence·bytes의 불변성과
prepared snapshot 불변성은 적용 시 backend 관측값으로 assertion했다.

writer 검사는 두 adapter의 동일 backend bind 경합, foreign handle/thread, 중복 apply/tick,
wrong frame/ticket, pending 교체, backend 재진입·exception, old ticket/새 INIT까지 포함한다.
올바른 positive는 apply1/tick1이며 reject는 무단 추가 호출0이다. ambiguous apply는 이미
호출1회일 수 있으므로 rollback 성공이 아니라 추가 apply/tick 금지와 fault latch를 검사한다.

### 기존 Drive30ms와20Hz 충돌의 실제 코드 검사

`M7Freshness`는 원래 DriveReceiver/DriveController를 **직접 호출**한다. 새 Python age 검사를
만들어 기존 코드를 대신하지 않았다. fixture의 시각0은 실제 정수원점1.010s이며 source는
그대로 두고 logical now만 증가시켰다. 새 wheel acquisition은50ms 뒤에만 가능하다는 전제다.

| sample age | 기존 receiver/local validator | 기존 full DriveController gate |
| --- | --- | --- |
| 0/10/20/30ms | usable/Accepted; 원래 source 보존 | fresh command/BMS/permission + 같은 원래 wheel/HV sensor로 active |
| 30ms+1ns | `current_sample` 없음 | 별도 receiver 경계 시험이며 Controller가1ns task로 실행됐다는 뜻은 아님 |
| 40ms | stale/Time, cached source 재발행으로 갱신 불가 | **LocalInputsUnavailable·Zero target**, 물리 torque0 도달을 주장하지 않음; sensor port는5Nm 사용 |
| 50ms의 새 acquisition | 새 sample 수용은 가능 | 이전 fault가 **계속 latch**하며 normal 자동 복귀 없음 |

full gate는10ms job을 유지하고 CAN command/limits/permission을 원래 codec·parent context로
계속 갱신했다. wheel/HV만 같은 취득 sample로 유지해40ms에서 보호 선택을 확인했다.
다른 sensor의 skew가 원인으로 먼저 작동하지 않도록 둘의 source를 같은 시각으로 고정했다.
새 sequence·source를 달아 cached sensor를 restamp하면 원래 identity 검사가 거부한다.
source만 fresh여도 oldest dependency가 오래되면 Time이며 future/model epoch/NaN도 거부한다.

fresh torque/capability를 계속 수신하고 기존 opt-in EV dependency70ms를 써도,40ms-old wheel은
Stale로 제거됐다. capability가 wheel을 대신하지 않는다. raw replay/P05나 새 report sequence가
valid-RX를 갱신하지 못하고 마지막 accepted RX+80ms에서 원래 receiver timeout이 latch한다.
이80ms는 logical polling 검사이며 wall100ms 보장은 아니다.

따라서 **50ms stock state를 기존 Drive30ms에 그대로 붙일 수 없음**을 확인했다. FakeProbe도
fresh sample을50ms interval 동안 hold하려 하면 Coverage로 거부했다. 이 결과는 conflict의
해결이 아니며 요구 완화·캐시 restamp의 근거가 아니다.

## 실패/개발 이력

[첫 build 실패](build-01-failed.txt)는 `if(current) EXPECT_EQ(...)`의 GTest 매크로가
`-Wdangling-else -Werror`에 걸린 compile failure다. 명시적 중괄호로 수정했으며 원본을 보존했다.
해당 build에서 runtime 시험이 실행됐다고 세지 않는다. 이후 build02/03은 성공했다.
중간 Normal34/34·Normal38/38·ASan38/38은 당시 cohort XML을 보존하며 최종39와 합치지 않는다.
backend bind/재진입·예외·frame guard를 검토하며 추가 assertion을 넣었다. 실행한 runtime
assertion FAIL은 없다. 이전 코드는 [최종→이전 source patch](historical-sources.patch)로 보존한다.

## 재현

현재 Host의 GCC11.4/GTest1.11.0/CMake를 사용한다. CARLA 다운로드/실행이 필요 없는 시험이다.
새 target은 명시적 option ON에서만 만들어진다. 기존 runtime loader·ECU library는 그대로다.

```sh
cmake -S . -B build/m7-contract -DSTRATADRIVE_M7_CONTRACT_TESTS=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m7-contract --target m7_plant_contract_test --parallel 2
ctest --test-dir build/m7-contract -L m7.contract --output-on-failure
cmake -S . -B build/m7-contract-asan -DSTRATADRIVE_M7_CONTRACT_TESTS=ON -DSTRATADRIVE_SANITIZERS=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m7-contract-asan --target m7_plant_contract_test --parallel 2
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 build/m7-contract-asan/tests/integration/carla/m7_1c/m7_plant_contract_test
```

## 판정과 다음 gate

M7-1-07/08은 **위 fake/backend·native logical 범위 PASS**,09는 interval/disabled/ambiguous·CLI
부분 PASS다. 실제 peer/parent/permission 전송·CARLA single writer·외부 client 차단·실제 RPC
오류 및 actuator dynamics·energy 연결은 NOT RUN이다. M7-1b의05/06 부분 검증과
OPEN-M7-1B-01/02(native reload/server crash)도 유지한다. M7 전체 종료가 아니다.

다음 한 단위는 **50ms world tick 안 실제 substep 관측·10ms ECU exchange·Actual actuation을
인과적으로 연결할 수 있는지 설계/타당성 검토**다. 원천 timestamp/30ms·20ms envelope·
local protection을 유지하고 clock domain·interval coverage·owner를 먼저 결정한다.
후속 backend prototype/저수준 확장·CARLA source build 여부는 그 검토 뒤 별도 범위다.
현재 정상 CARLA 주행은 계속 BLOCKED이며 calibration/중복 dynamics/energy gate도 미해결이다.


정적 검증: 변경 Markdown 로컬 링크/앵커 깨짐0, `git diff --check` 오류0,
원래 interfaces/vecu/central/zone/simulation·requirements/profiles·M6 종료 review 변경0.
CMake에는 기본OFF opt-in test block만 추가했다. 기존 M7-1a/b 증거와 source도 보존했다.
이번 작업에서 CARLA2000/2001/2002 listener는 없었다([확인](ports-after.txt)).
증거 SHA256은 [SHA256SUMS](SHA256SUMS)에 있다.
