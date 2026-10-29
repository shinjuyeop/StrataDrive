# Terminal native wall response — 2026-10-28

**PASS_NATIVE_TERMINAL_RESPONSE_ONLY; 전체 M7 NOT CLOSED.** 정상 CARLA 주행의 wall scheduling,
clock agreement/uncertainty, wall fault 이후 CARLA 연속 물리 제동 수용은 아니다.
base `a33c2b25802eb6fe866bd8ebf2da4783851eed28`. 원래 M6 코드·계약·기존 수용은 변경하지 않았다.

## 변경과 실행

완료된 정상 solver-work barrier의 동일 native session/EV/response 객체를 terminal 분기로 넘긴다.
원래 Central/Zone/leaf 보호를 선택하고, single mutation owner가 wall timer로 ECU service와 response를
계속 호출한다. stdin/WORK를 기다리지 않는다. response 내부 분할을 owner job으로 세지 않는다.
FrameClock은 영구 차단하며 정상 lease/request를 재발급하지 않는다. 새 Actual은 원래 vECU→CAN/P05→
Zone→Central 경로에서 가져온다. 마지막 EV 정산과 wheel source는 그대로 유지한다.

`LOCAL_TERMINAL_RESPONSE_NOT_CARLA`는 `barrier + monotonic handoff 이후 경과`인 **별도 local branch**다.
CARLA clock 변환이 아니며, 여기서 나온 raw Actual은 진단으로만 보관하고 CARLA에 적용하지 않는다.
시험이300ms 뒤 exit2로 끝나는 것은 bounded probe이며 배포용 지속 실행 정책이 아니다.

| 실행 | 실제 결과 |
| --- | --- |
| `probe-first` | 기존 정상 입력200개 정확히 재생 후 stdin을 열린 채 보류. PROTECT 주입 없이 native fault→보호.300개 응답, 각 Actual source30개, 첫 torque0·pressure≥1MPa209.065ms |
| `carla` | fresh CARLA199 physics·199 EV 정산 후 같은 보류 시험.300개 응답/각30개 새 Actual. 첫 torque0·pressure≥1MPa209.053ms. 각각 original FailSafe/LocalProtection 및 wire/P05 확인 |
| fresh wall CSV | terminal 구간 owner0..9 각각150개 완료. 완전한 deadline 구간 누락/late0. 단일300ms 관측이며 정상 실시간 수용/보장 상한 아님 |
| containment | 검출→선택 readback2.210ms, 선택 readback→adapter pause 확인1.339ms. pause는 terminal 관측 완료를 기다리지 않음. 다음 CARLA stage/advance 없음 |
| physics 비교 | fresh199개 구간의 모든 physics 필드가 기존 camera-a와 generation을 제외하고 정확히 동일 |
| 정상/ASan | 각86/86(신규3 포함), 실패0. 신규 검사는 정수/fractional handoff, 실제 native Actual 지속, clock/thread/모드 거부 |
| TSan | process-local `setarch x86_64 -R`,6/6. terminal process warmup200개도 정확히 일치, race 경고0. 실제243개 service/각30개 Actual을 관측했으나 owner0..3 완료 누락6/7/2/1개는 보존. **timing PASS가 아님** |
| 기존 native 회귀 | 정상901개·보호401개 전체 JSON 출력 정확히 일치. 기존 기록 replay이며 새 CARLA 실행 분모에 더하지 않음 |
| 독립 감사 | `audit_m7_terminal.py`가 wire/P05·epoch/source·held wheel·EV 동결·clock·wall jobs와8종 손상 거부 확인. 압축 archive에서도 같은 결과 |
| 서버 종료 | 이번 정상 cleanup 후 SIGINT 약2.920s, exit130. client-loss 실패 재현/수정 시험이 아니므로 해당 OPEN 유지 |

`normal`, `asan`, `tsan` build/test 로그를 각각 보존했다. 첫/두 번째 신규 테스트 실행은 fractional
barrier의 이전 substep에 새 보호 output을 넣어 `M7 output time`으로 거부됐다. 보호 선택을 handoff
anchor로 옮겨 source 이후에만 적용하도록 수정했다. 세 번째 실행과 이후 전체 검사만 최종 통과 근거다.
첫 로그의 빈 exception 설명도 보존하며 오류 문자열은 동작 후 읽도록 수정했다.

## 재현

기존 configure된 build에서 `cmake --build build/m7-functional -j6` 및
`ctest --test-dir build/m7-functional -R '^M7' --output-on-failure`. ASan build도 동일하다.
TSan은 `setarch x86_64 -R <m7_wheel_test> --gtest_filter='M7WallWatch.*:M7TerminalResponse.*'`.
`probe_m7_terminal.py --native <binary> --scenario tests/integration/carla/scenarios/m7_integrated_v1.txt
--trace docs/test-plan/evidence/m7_carla_wall_guard/suite-b/camera-a/trace.jsonl.gz --output <new-dir>`로
실제 wall 보류 probe를 재현한다. TSan process는 동일 명령의 Python도 `setarch x86_64 -R`로 시작한다.

fresh CARLA 전체 argv·binary/module/source hash는 `carla-runner.log.gz`, 실제 입력/응답은
`carla/trace.jsonl.gz`, terminal raw Actual은 `carla/terminal.jsonl.gz`, wall jobs는
`carla/native-wall.csv.gz`에 있다. runner 옵션은 기존 source/engine/python/fixture/native 인자에
`--solver-work --native-fault wall-gap --terminal-response --vehicle-substeps 320`을 추가한다.

```sh
python3 tests/integration/carla/audit_m7_terminal.py \
  docs/test-plan/evidence/m7_carla_wall_guard/terminal-response/carla --output /tmp/m7-terminal-audit.json
```

`archive-manifest.json`은 원본/압축 SHA와 무손실 readback, `source-and-validation.json`은 최종
source/binary·검사 범위를 기록한다. binary·credentials는 보관하지 않는다. 부모 evidence와 이전
실패는 수정하지 않았다. 현 남은 작업은 [통합 종료 검토](../../../../project-status.md#m7-종료-조건)를 따른다.
