# M7 독립 wall guard와 terminal barrier 검증

2026-10-28. **전체 M7 NOT CLOSED.** 이번 변경은 독립 monitor와 기존 native 보호 선택을
연결한 opt-in 진단이다. CARLA를 기다리는 owner 실행 자체를 분리하거나 연속 wall 정상 주행을
수용한 결과가 아니다. M6 코드/계약/판정·서버3개 module hash·V1 계수는 변경하지 않았다.

## 실행 결과

| 실행 | 결과 |
| --- | --- |
| suite-a/wall-gap | 실제199 receipt/199 EV 정산 후 다음 native 입력 보류. 독립9-owner 미완료 검출→local 보호 선택255/credit0→다음 stage/tick 없음·pause 확인. native2, 서버130 |
| suite-a/camera-a | 대화 중단으로 runner/client 종료, 원본 trace 일부만 존재. **미완료/판정 없음.** 남은 전용 서버에 SIGINT 후30.087s에도 종료되지 않아 강제 종료. 부모가 사라져 wait exit code는 취득 불가 |
| suite-a/protection | 중단 당시 **NOT RUN** |
| suite-b/camera-a | 새 서버900 receipt/900정산, RGB180/GT180, 독립 wire/work/시나리오 감사. native0, 서버130 |
| suite-b/protection | 새 서버400 receipt/400정산, 보호200구간·마지막100구간 wheel exact0. advance 전 명시적 safety 요청 인과 검증. native0, 서버130 |

suite-a의 `suite.json`은 중단 당시 RUNNING 원본이다. 이후 성공한 suite-b로 덮어쓰지 않았다.
정상 종료3회와 camera 중단 후 강제 종료1회를 구분한다. 후자의 원인 확정/수정은 미완료이며,
과거 로딩 중 RPC 취소 수정의 FIXED_LIMITED를 client-loss/동기 대기 종료까지 확장하지 않는다.

wall-gap은 첫 release를100ms 뒤로 선언한 **별도 진단 창**이다. 이전 INIT/정상 구간이나
이미 완료된 pause를 감시했다고 주장하지 않는다. 원래 M4 schedule의2ms/4ms·누락 slot·latch를
그대로 사용한다. 실제8-role poll/physical step만 owner 완료로 기록하고 stdin poll/monitor는
owner를 대신하지 않는다. `native-wall.csv`의 이 창에는 owner0..8의 완료가 없으며 monitor9만
실행했다. 별도 component 시험에서는 실제 owner 호출 완료와 late completion 불복구도 확인했다.

[독립 감사](suite-a/wall-gap-audit.json): 최대 검출 지연0.074ms,
검출→local 선택0.961ms, 검출→adapter pause 확인4.722ms. **1회 관측치이며 보장 상한 아님.**
local 선택은 원래 Central/Zone/leaf 보호 함수를 호출한 상태 readback이다. 원격 ACK나 새 Actual이
아니며, wall 시각을 simulation acquisition으로 변환/소급하지 않았다. 원래 barrier 시각에서 terminal
처리하고 모델/물리 시간을 더 진행하지 않았다. 시험 입력에 PROTECT/압력/torque를 넣지 않았다.
audit는 owner 누락·가짜 heartbeat 완료·deadline 완화·선택 누락·barrier 시각 변경5종을 거부했다.
in-flight RPC fault, 실제 보호 제동, source clock mapping, 연속 owner scheduling은 **미수용**이다.

## Native 검사와 회귀

- Normal M7 **76/76**, ASan/UBSan **76/76**. 기존73개와 새3개 wall/terminal 검사를 실행했다.
- TSan 최초 configure에 M7 opt-in flag가 빠져 target이 없었다. flag를 켠 빌드 후 첫 실행은
  `unexpected memory mapping`으로 test 시작 전 실패했다. 원본 로그를 보존했다.
- `setarch x86_64 -R`로 해당 process의 ASLR만 해제한 별도 TSan 실행은 **3/3**, 경고 없음.
  system-wide 설정/기존 M6 판정을 변경하지 않았다. 전체 UE/SDK sanitizer 수용이 아니다.
- [물리 비교](physics-comparison.json): 이전 정상900·보호400·wall 시험 이전199개 구간의
  모든 physics 필드가 generation을 제외하고 정확히 같다. 기존 Actual/work 물리 결과를 바꾸지 않았다.
- 보호 시험의 마지막 body 속도는−0.000005432376638054848m/s이며 완전 정지 수용은 하지 않았다.

## 재현과 보존

`suite-a/suite.json`, `suite-b/suite.json`에 전체 runner argv와 실행 source hash가 있다.
같은 engine/source/python/fixture/native 경로에 새 runtime/output을 지정한다:

```sh
python3 tests/integration/carla/m7_integrated_run.py --engine <UE4.26> --source <CARLA0.9.16> \
  --python <m7-venv/bin/python> --fixture <m7-1m-fixture> --native <m7_wheel_shadow> \
  --runtime <new-runtime> --output <new-output> --cases wall-gap camera-a protection
```

검사 명령은 `cmake --build build/m7-functional -j8`,
`ctest --test-dir build/m7-functional -R '^M7' --output-on-failure`이며 ASan build도 동일하다.
TSan은 `-DSTRATADRIVE_TSAN=ON -DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON`으로 구성 후
`setarch x86_64 -R build/m7-wall-tsan/tests/integration/carla/m7_1g/m7_wheel_test --gtest_filter='M7WallWatch.*'`.

`source-and-validation.json`에 native 원본/실행 binary hash와 M6·서버 module 불변 검사가 있다.
`archive-manifest.json`은37개 gzip의 원본/압축 SHA·해제 readback 검증이다. 압축은 무손실이며
중단 trace·실패 로그도 포함한다. 실행 binary 자체는 커밋하지 않는다. `SHA256SUMS`는 자신을
제외한 이 디렉터리의 Git staged blob을 검증한다.
현재 남은 구현은 [통합 종료 검토](../../../archive/carla-history.md#m7-review-wall-guard-후속-결과)를 따른다.
