# M7 actuator 응답 / 관측 EV 정산 분리

2026-10-28. **모델 계층 분리 완료, 실제 wall runner 연결은 미완료.**
기존 M6와 서버 module, 기본 native coupled 실행 모드는 변경하지 않았다.
새 CARLA 실행·wall deadline 검증을 하지 않았으며 이전 CARLA PASS에 분모를 더하지 않는다.

## 변경과 경계

`DeferredObservedWork`는 한 mutation owner에서 두 진행 시점을 분리한다.
`advance_actuators()`는 work 수신 없이 원래 Steering/Brake/Drive response를 진행한다.
`settle_observed_frame()`은 과거에 실제 적용한 coil 이력으로 단일 EV만 정산한다.
원래 source/sequence/oldest를 유지하며 현재 coil을 과거 frame에 소급하지 않는다.
중복·잘못된 work, energy 계산 실패,128개 고정 이력 슬롯 초과는 전기 정산을 실패로 고정한다.
이미 진행한 actuator는 rollback하지 않고 보호를 계속한다. 정상 재개·coupled rollback 혼합은 거부한다.

보관된 전기 취득은 시간이 갱신되지 않는다. 전기 실패 시 HV/BMS/Power는 unavailable이 되고,
새 response 취득과 wheel 부재는 각각 별도로 표현한다. Power의 기존 source50ms/dependency70ms
경계를 적용해 만료한 low-current를 접촉기 opening dwell에 쓰지 않는다. Drive30ms는 변경하지 않았다.
모든 API는 단일 caller가 소유한다. 새 수신 thread/queue나 simulation↔wall clock mapping을 만든 것은 아니다.
후속 owner는 response 진행 성공을 정상 권한으로 취급하지 않고, electrical failure를 원래
LocalProtection 선택/정상 credit 차단에 연결해야 한다.

## 검증

최종 수용 근거는 파일명의 **reviewed** 실행이다. 초기/중간 실행도 보존하지만 합산하지 않는다.

| 검사 | 결과 |
| --- | --- |
| 전체 M7 Normal / ASan·UBSan | 각각83/83; 기존76개 + 새7개 component |
| work 수신 부재 | warmup 후250개1ms 구간 동안 response 지속. 모델 시각에서 보호 선택 후230ms 내 torque0·pressure1MPa 검사. EV 시간/장부 동결, fresh wheel 생성 없음 |
| 지연 work / 과거 coil | 180개10ms frame을30ms마다 정산. 양·음수 motor work 포함. 기존 coupled 방식과 response·SOC·motor/circuit/chemical 장부·전압·전류 정확히 일치 |
| fractional tail | frame 끝1ns 차이를 다음 coil 구간에 정확히 이월. 더 새 actuator 취득을 backdate/restamp하지 않음 |
| 정산 실패/중복 | EV whole-frame rollback, 진행한 actuator는 보존. electrical unavailable·보호 response 지속·재개 거부 |
| 오래된 전류 | 토크가 이미0인 상태에서 current 취득 만료. 오래된 low-current로 접촉기를 열지 않음 |
| wheel identity / 혼합 모드 | mutation/regression/future 및 coupled commit/abort/step 혼합 거부 |
| 정상 native 재생 | 기존900구간 기록의901개 native 출력(마지막 정산 포함) 전부 정확히 일치 |
| 보호 native 재생 | 기존400구간 기록의401개 native 출력 전부 정확히 일치, 원래 시점의 PROTECT1회 |

초기 새 테스트 빌드는 GTest assertion을 감싼 if의 braces 누락으로 `-Werror=dangling-else` 실패했다.
`m7-deferred-build-tests.log.gz`에 원본을 보존하고 수정 후 검사를 수행했다.
중간에는 Power freshness를30ms로 작성했으나 최종 검토에서 원래 PowerControllerConfig의50/70ms로
수정하고 다시 검증했다. 초기/중간 로그·재생은 최종 구현 수용 근거가 아니다.
새 동시 모델 mutation은 없으며 이번에 TSan/새 CARLA/실제8-role wall 제동을 실행하지 않았다.

## 재현·무결성

```sh
cmake --build build/m7-functional -j8
ctest --test-dir build/m7-functional -R '^M7' --output-on-failure
cmake --build build/m7-functional-asan -j8
ctest --test-dir build/m7-functional-asan -R '^M7' --output-on-failure
python3 tests/integration/carla/replay_m7_native.py \
  --native build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --scenario tests/integration/carla/scenarios/m7_integrated_v1.txt \
  --trace docs/test-plan/evidence/m7_carla_wall_guard/suite-b/camera-a/trace.jsonl.gz \
  --output <new-output>
```

보호 재생은 trace를 `suite-b/protection/trace.jsonl.gz`로 바꾼다. 각 result.json에 입력·실행 binary
hash와 argv가 있다. 재생용 executable은 런타임 폴더에 동결했으며 Git에는 넣지 않았다.
`source-and-validation.json`에 최종 source/binary hash, M6 source·서버 module 불변, 수용 파일 목록을
기록했다. `archive-manifest.json`의22개 gzip은 무손실 해제/SHA를 검증했다.
상위 evidence의 기존99개 checksum 대상은 변경하지 않았다. 이 후속 폴더는 별도 `SHA256SUMS`로
자신을 제외한 staged Git blob을 검증한다.

다음 작업은 [현재 종료 검토](../../../../m7_exit_review.md#actuator-응답과-관측-ev-정산-분리)의
native timer/수신 분리와 새 경로 배선이다. **전체 M7 NOT CLOSED**를 유지한다.
