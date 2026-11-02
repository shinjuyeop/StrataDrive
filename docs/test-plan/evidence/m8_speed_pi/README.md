# M8 종방향 SpeedPI C++ component 동등성

2026-10-29, 기준 commit `f9cef7d98ef733de9f09da437c6b9c290572c4da`의 clean tree에서 시작했다.
**C++17 SpeedPI 이식과 독립 Python/C++ 공통 입력 동등성을 검증했다.**
현재 단계 판정은 [프로젝트 상태](../../../project-status.md), 사전 기준은
[동등성 protocol](../../longitudinal-equivalence-protocol.md), 결정은
[ADR-0067](../../../archive/design-decisions.md#adr-0067)을 따른다.

## 구현 범위

`central/longitudinal/speed_pi.hpp/.cpp`는 고정 `m6-pi-v1`의 수작업 C++ 구현이다.
20ms PI·reference feedforward·감속 preview·amplitude/slew·conditional integration,
입력 검사 순서·fault latch·새 INIT와 원래 speed source를 유지한다. Invalid acceleration은
`std::nullopt`이며 정상0 출력으로 바꾸지 않는다. Production library는 Python/plant/SDK에 의존하지 않는다.

`tests/integration/longitudinal/`은 하나의 저장된 입력 파일을 Python과 컴파일된 C++에
각각 replay한다. 매 event의 출력과 epoch/integral/previous/last_ns/sample/fault/target을
비교한다. Float는 사전 고정한 abs1e-12+rel1e-12, 정수·validity·reason·optional은 exact다.
Python 모델과 MIL source는 변경하지 않았다. source snapshot과 실제 binary hash를 함께 보존한다.

## 검증 결과

| 검사 | 결과 |
| --- | --- |
| 최종 Debug/Release/ASan·UBSan 공통 vector | 각각 **97case / 14,523event / 14,302step PASS**. Init/new event 포함. 모든 finite 비교 필드의 최대 절대 오차0, categorical/identity 불일치0 |
| C++ 계약 시험 | 각 configuration **14/14**. 분석 가능한 출력·제약·fault/INIT·정수 경계 검사 |
| 잘못된 입력 문법 | 각 configuration에서 Python/C++ 모두 **16/16 거부**; C++ exit2 확인 |
| Comparator 손상 거부 | Python10개 시험에 행 누락/추가/순서·state/validity/reason/source·optional·integer/bool type·NaN/Inf·허용 오차 초과·중복 JSON key 포함 |
| Normal 기본 C++ 전체 회귀 | **1,034/1,034**. 기본·논리1,025 후 기존 wall9개를 exclusive lock 아래 직렬 실행 |
| Python 전체 회귀 | **211/211** |
| 정적 분석 | 현재 compile database의 새 production/replay2개 TU에 clang-tidy·cppcheck 진단0 |
| BUILD_TESTING=OFF | 별도 Release configure와 production `speed_pi` library 빌드 통과 |

최종 세 configuration의 공통 입력 SHA256은
`fb81d2333d29aa07627cf7605a30d15ed189da50d22b46788e4cfe9f917caf64`다.
10개 output reason을 모두 포함한다. 숫자 오차0은 이 Host/compiler/입력 집합의 관측 결과다.
문자열 byte 동등성이나 모든 입력·다른 Target에 대한 보장은 아니다.

실제 기본 C++ 회귀에는 M7 opt-in 시험·SDK·CARLA 실행이 포함되지 않는다. Sanitizer 결과도
이번 SpeedPI component 범위다. 새 component는 단일 owner이고 thread/IO를 추가하지 않아
TSan 대상이 없다. 차량의 속도 추종 성능·실시간 성능·system TC 수용은 여기서 판정하지 않는다.

## 개발 중 기록

첫 C++ build는 테스트의 `if (...) EXPECT_DOUBLE_EQ(...)` 두 곳에서
`-Werror=dangling-else`로 실패했다. 명시적 brace를 넣은 뒤 빌드·시험했다.
`validation/build-component-normal.txt`와 수정 후 로그를 함께 보존한다.

첫 Debug pilot도 같은 분모에서 동등성 PASS였지만, 경계 주변의 입력을 `6-error`/`1+error`로
만들면 adjacent binary64 차이가 상쇄될 수 있어 diff review에서 vector를 보강했다.
경계값 자체를 target 또는 speed로 전달하도록 수정했으며 판정 오차·모델·C++ production은 유지했다.
초기 입력/출력은 `normal-initial/`, 최종 것은 `normal/`, `release/`, `sanitized/`에 둔다.
최종 결과와 초기 결과를 합쳐 분모를 늘리지 않는다.

## 재현과 원본

저장소 루트에서 실행한다. Python3.10+와 기존 GTest1.11.0이 필요하다.
기본 build에는 C++ unit test를 추가했고, Python replay는 명시적 옵션으로 활성화한다.

```sh
cmake -S . -B build/m8-speed-pi/normal -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_LONGITUDINAL_EQUIVALENCE=ON
cmake --build build/m8-speed-pi/normal --parallel 2
ctest --test-dir build/m8-speed-pi/normal -LE runtime.wall --output-on-failure
flock -n build/.m4-exclusive.lock ctest --test-dir build/m8-speed-pi/normal -L runtime.wall --output-on-failure
python3 -m unittest discover -s tests/unit -p '*_test.py'
```

Release와 ASan/UBSan은 별도 directory에 각각 `-DCMAKE_BUILD_TYPE=Release`,
`-DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON`을 사용하고
`speed_pi_test speed_pi_replay` target 및 `-R 'SpeedPI\.|speed_pi_equivalence'` 시험을 실행한다.
CTest는 매번 새 run directory를 만들어 원본을 보존한다.
이미 보관한 입력을 다시 비교하려면 다음처럼 **새 output 경로**를 쓴다.

```sh
gzip -dc docs/test-plan/evidence/m8_speed_pi/normal/inputs.txt.gz > build/m8-speed-pi/archived-inputs.txt
python3 tests/integration/longitudinal/check_equivalence.py \
  --replay build/m8-speed-pi/normal/speed_pi_replay \
  --vectors build/m8-speed-pi/archived-inputs.txt \
  --output build/m8-speed-pi/replay-from-archive
```

- `results-summary.json`: 이번 실행만의 분모와 범위.
- `build-manifest.json`: 기준 commit·source/binary hash·compiler/tool·실제 build 설정.
- 각 실행의 `plan.json`, `inputs.txt.gz`, `python.jsonl.gz`, `cpp.jsonl.gz`, `cpp.stderr`,
  `process.json`, `result.json`, `malformed-inputs.json`: 입력·양쪽 출력·실패 처리·판정 원본.
- `validation/`: 최초 build 실패를 포함한 명령/exit code와 로그. 큰 텍스트는 gzip이다.
- `sources/`: 최종 검증 production·모델·harness·test·CMake·사전 protocol snapshot.
- `archive-map.json`: 원본 경로·압축 여부·압축 전 hash. `SHA256SUMS`: 보관 파일 무결성.

```sh
cd docs/test-plan/evidence/m8_speed_pi
sha256sum -c SHA256SUMS
```

다음 작업은 trusted INIT/permission, 실제 speed 원천 identity, 20ms PI와 runtime 명령 갱신,
VehicleRequest의 source/expiry 및 NormalStop 인계를 설계해 SimpleVehicle 속도 폐루프에 연결하는 것이다.
