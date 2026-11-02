# M8 SimpleVehicle 속도 폐루프

2026-10-29, 기준 commit `f9cef7d98ef733de9f09da437c6b9c290572c4da` 위의
SpeedPI component 변경을 이어서 작업했다. **기존 owner 경로의 논리 시간 속도 폐루프 PASS**다.
[사전 프로토콜](../../speed-loop-protocol.md), [ADR-0068](../../../archive/design-decisions.md#adr-0068),
[현재 상태](../../../project-status.md)를 따른다. 이전 component evidence는 수정하지 않았다.

## 연결한 경로

8 participant INIT/ACK/release → Central `SpeedRequest`/SpeedPI → VehicleCoordinator
allocation → Zone/CAN P05 → Leaf → 실제 torque/pressure → 단일 VehicleEvModel →
Drive Actual receiver → SpeedPI다. 제어는 physical truth를 직접 읽지 않는다.

20ms 제어와 Host10ms allocation을 분리하고 기존 permission·보호·NormalStop을 사용한다.
검증된 wheel acquisition timestamp를 요청 source/expiry에 묶어 캐시를 새 입력으로
바꾸지 않는다. PI 상수·Python 모델·runtime30ms age와 성능 기준은 변경하지 않았다.
첫 제어는 정상 arm 후 allocation release+1ms, 물리1ms, owner poll0.2ms다.

## 결과

최종 Normal과 ASan/UBSan에서 정상·Actual 손실·명령 중단 **각3/3**을 통과했다.
[정상 결과](normal/result.json), [sanitizer 결과](sanitized/result.json),
[전체 요약](results-summary.json)에 정확한 분모와 값을 보존한다.

| 실제 차량 속도 판정 | 결과 | 기준 |
| --- | --- | --- |
| 30km/h plateau [25,35)s | 최대 오차 0.049677km/h, 1,000표본 | ≤1km/h |
| 20km/h plateau [48,58)s | 최대 오차 0.047984km/h, 1,000표본 | ≤1km/h |
| 0km/h plateau [77,87)s | 최대 오차 0km/h, 1,000표본 | ≤1km/h |
| 양수 목표 대비 최대 overspeed | 1.290820% | ≤10% |
| 제어/물리 trace | 4,350회 / 9,200행, 정상 중 fault0 | 고정 87초 profile + 종료 tail |
| NormalStop | Complete, 실제 speed0·torque0·hold pressure·contacts open·HV≤30V | 기존 정지 인계 |

Central이 받은 양자화된 feedback도 독립 판정했다. Plateau 최대 오차는
0.0516/0.0448/0km/h, 각500표본이며 overspeed는1.295197%다.
제어와 physical의 표본 시각·값은 서로 바꾸거나 보간하지 않았다.

25초에 실제 주행 중 Drive Actual 전송 손실/명령 생산 중단을 각각 주입했다.
검출은21.2/11.2ms, 전체 보호 선택은21.4/11.4ms다(기준100ms).
보호 선택+230ms 이후 실제 |torque|≤1Nm·pressure≥1MPa·normal gate 닫힘을
각274/275표본에서 확인했다. 이230ms는 actuator 응답이며 차량 정지 시간의 보장이 아니다.

| 검증 | 결과 |
| --- | --- |
| Normal 전체 기본/논리 회귀 | 1,033/1,033. 새 폐루프와 기존 SpeedPI 동등성 포함 |
| 최종 permission 검사 보강 후 통합 | Normal 3/3, ASan/UBSan 3/3 별도 재실행 |
| SpeedRequest 계약 시험 | Normal·ASan/UBSan 각7/7 |
| Python 회귀 | 219/219. 새 oracle 손상 시험8개 포함 |
| 기존 wall 회귀 | **8/9**, 실패한 physical guard 단독 재확인1/1. 최초 FAIL 유지 |
| clang-tidy | 변경 영향8개 TU 진단0, 최종2개 TU 재검사 진단0 |
| cppcheck | 초기 style6개. 새 main const 진단 수정, 기존 header5개 검토 예외 후 진단0 |
| Production library | BUILD_TESTING=OFF Release `speed_request` 빌드 PASS |

전체 기본/논리 회귀 뒤 변경은 speed loop의 현재 AllowNormal grant 명시 검사와
runner의 const 매개변수다. 해당 통합을 두 configuration에서 재검사했다.
Sanitizer 전체 저장소 시험으로 확대하지 않는다. 새 thread/concurrency 계약이 없어 TSan은 실행하지 않았다.

## 실패와 수정 이력

- `development/nominal-01`: 제어와 Drive publish의 같은 위상에서10ms 전 wheel을
  읽었다. source+30ms 만료 전에 다음 명령이 도착하지 않아801.2ms에 보호됐다.
  위상을+1ms로 수정했으며 age/expiry와 PI·성능 기준은 그대로다.
- 최초 빌드2회는 조건식 괄호 warning을 error로 처리해 실패했다. 새 target을
  configure 전에 호출한 build2회도 별도 실패 로그를 보존했다.
- Adapter 시험 첫 실행6/7: slew saturation 중 integral이 갱신된다는 잘못된 기대를
  고쳤다. Anti-windup production 코드는 바꾸지 않았다.
- cppcheck의 기존 `useStlAlgorithm`3개는 관련 없는 loop 스타일 제안이다.
  `unusedPrivateFunction`2개는 실제 member initializer에서 호출하는
  `PhysicalOwner::battery_fixture/circuit_fixture`다. 파일별 예외와 원본 진단을
  `validation/cppcheck*.json/.txt`에 남겼으며 일반 warning을 전역 숨기지 않았다.
- 기존 wall physical guard는 예정된 주입보다 앞선 초기137.467348ms에 보호돼 실패했다.
  단독 재확인은 통과했지만 최초 FAIL을 성공으로 바꾸지 않는다. 최초 실패의
  event trace는 수집하지 않아 정확한 timing 원인은 미확정이며 wall 안정성은 OPEN이다.

개발 중 실행은 최종 분모에 합치지 않았다. 초기 실행은 config/raw/log만 있고 당시
binary 및 완전한 source snapshot은 남아 있지 않다. 최종 두 cohort는 실행 manifest의
source/binary hash와 최종 `source.tar.gz`를 대조했다.

## 재현과 원본

```sh
cmake -S . -B build/m8-loop -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_LONGITUDINAL_EQUIVALENCE=ON
cmake --build build/m8-loop --target speed_loop_run speed_request_test --parallel 2
ctest --test-dir build/m8-loop -R '^SpeedRequest\.|^speed_loop_integration$' --output-on-failure
```

`check_speed_loop.py`는 unique output directory를 만들고 nominal/feedback-loss/command-loss를
실행한다. 각 `config.json`은 실행 전, 원본 CSV와 runtime 판정은 실행 후 기록한다.
`--check DIRECTORY`로 저장된 plain CSV를 다시 판정할 수 있다.

[빌드 manifest](build-manifest.json)는 tool version·binary·source hash를,
[archive map](archive-map.json)은 원본 위치·압축 여부·원본 SHA256을 담는다.
CSV는 gzip으로 보존한다. 다시 검사할 때 별도 작업 디렉터리에 복사·해제해 사용한다.
`source.tar.gz`는 해당 기준 commit 위에 적용할 production/test/CMake 입력 snapshot이다.
[감사 결과](audit.json)와 `SHA256SUMS`로 자료 무결성을 확인한다.

이 시험은 in-process owner/mailbox·논리 시간 기능 검증이다. 실제 SOME/IP/vCAN·
RunLease 전송, CARLA의 느린 센서/clock mapping, wall scheduling, OEM tuning·실차 안전·
M8 전체 또는 개인 이해 수용을 뜻하지 않는다. 다음 단계는 CARLA simulation-time 연결이다.
