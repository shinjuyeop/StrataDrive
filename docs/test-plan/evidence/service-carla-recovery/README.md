# Epoch 서비스와 CARLA 복구 주행 마감

2026-11-06, baseline `e6c76d5f8fdc22789a67ed378edd631dbfc1445b` 이후의 두 후속 항목이다.
기존 M9 Host·simulation10ms 기능 범위를 유지하며 이번에 약속한 서비스 family 연결과
실제 CARLA 새 INIT·복구 주행을 완료한다. 전체 wall/Target/ODD나 학습 모델 수용으로 확대하지 않는다.

## 실제 CARLA 복구

같은 차량·physics generation·actuator/EV owner·diagnostic observer를 유지한60초 실행이다.
가용력 입력을15초에 생략하고17초에 복원한다. 복원만으로는 보호가 풀리지 않는다.25초에
현재 정차 wheel/torque·HV off·개방 접촉기를 확인한 뒤 실제 application42→43 INIT를 수행한다.
원래8-role Release/RunLease와 새 명령을 검증한 뒤 재출발하고 마지막에 다시 정지한다.

- 관측6001개, 물리 구간·단일 EV 정산6000개, 정상 구간4840개, 초기화 공백7개.
- 복구 뒤 최대 body 속도2.7992373657226564m/s, 최종0m/s·모든 wheel0rad/s.
- 원본 진단24개, Supervisor fault1개와 같은 occurrence의 qualified Passed1개. 자동 clear는 없다.
- 독립 solver/CAN/NoDrive 감사가 원본 권한·age·expiry·P05·setter·work와 연속 EV 원장을 확인한다.
  에너지 잔차 최대2.2213498596102e-08J로 기존0.00072J 기준을 유지했다.
- 원래 입력으로6001관측의 native 결과를 정확히 재생했다. 기존 nominal/input-loss도 최종 binary로 각각4001관측을 재생했다.

[통과 실행](carla/recovery/result.json), [서버 종료](carla/recovery/server.json),
`carla/recovery/trace.jsonl.gz`·`diagnostic-store`와 [감사 요약](audits.json)을 함께 본다.
학습 모델 대신 기존 classical fallback과 고정0:200N 저항 범위를 사용한다.

첫 실제 시도는 새 INIT 후 `native_release_ack`에서 거절됐다. 부동소수 CARLA elapsed를 반올림한
barrier와 처음부터 쓰던0.2ms native 작업 grid의 차이를 admission이 고려하지 않았기 때문이다.
동일한 원래 grid에서 다음 시작 기회를 계산하도록 수정했으며 deadline/age는 늘리지 않았다.
[실패 원문](carla/failed-grid-phase/result.json)과 trace·서버 종료를 그대로 보존했다.

그 전에 native 시험에서 Drive의 NonDriving 새 INIT가 이전 receiver의 accepted 명령을 Actual
origin/causal sequence로 가져오는 결함을 찾았다. 새 command monitoring이 열리기 전에는 그 참조를
사용하지 않도록 고쳤고 원본 Actual로 재검사했다. 정수 시간뿐 아니라1ns 어긋난 frame도 검사한다.

## Epoch family terminal service

Central SIGKILL 뒤 살아 있는 Front/Rear와 실제 epoch2 재가입, 정상 정지, operator의 epoch3 INIT,
다시 정상 정지와 보호를 거친다. Source9개를 먼저 정지/drain하고 collector를 닫은 뒤 별도 UNIX
peer 서비스가 원본/복제본의 모든 누적 ordinal·실제 ACK·원래 Actual을 검사한다.

전송용 원문은 바꾸지 않고 별도 `service-case` family에 Proof→Review→Passed→Clear4개를 기록한다.
Unknown 유실 가능성은 원문에 남는다. 미해결 continuity가 있는 merged/service segment는 회전하지
않으며 나머지 source/context는 실제 새 epoch에서 회전한다. 서비스 producer는 과거 segment에도
재사용할 수 없다. 잘못된 peer/capability/epoch/revision, 중복/충돌 요청도 원래 정책으로 처리한다.

최초 서비스 실행은 원본57개·실제 credit27개·source cut9개·물리 sample5개·요청9개를 감사했고,
17개 변조를 거절했다. 최종 재실행도 같은57개 원본·27개 credit와17개 변조 거절을 확인했다.
추가 epoch 감사16개 변조, ACK/Actual 유실 감사 각각5개 변조, finite 회귀17개 변조를 거절했다.
최종 재실행·ACK 유실·Actual 유실의 원래 runtime 판정과 독립 감사는
[acceptance.json](acceptance.json)과 [audits.json](audits.json), `someip.tar.gz`에 보존한다.
주입된 실패를 성공한 서비스로 바꾸지 않는다. 기존 finite 경로도 회귀 검사한다.

## 검증과 보존

전체 Debug1560개(`runtime.wall` 제외), 영향 범위 ASan/UBSan90개, Python280개를 통과했다.
변경 C++9개 unit의 clang-tidy 검사에서 사용자 코드 진단은 없었다. Clang14가 GCC13의 C++20
chrono를 해석하지 못한1건은 GCC12 표준 헤더로 분석을 다시 수행했다. 실제 native 실행은 원래
GCC13 build이며 CARLA server는 원래 UE toolchain으로 다시 빌드했다.

초기 native 복구의 Abort 처리·과거 Drive 명령 참조·CARLA grid 판정 실패, 테스트 macro braces
빌드 실패와 force-loss를 speed-loss reason으로 검사한 감사 오류를 `validation.tar.gz`에 보존한다.
첫 CARLA 실행은 보존된 실행 binary·probe snapshot·입력으로 최종 실행과 구분한다.
Server 출력은 완전한 첫 JSON 객체와 뒤에 남은 fragment를 분리해 `server.json`으로 제공하며,
원문 전체도 각 실행의 `server-output.raw`로 보존한다. 검증 결과를 수정한 것은 아니다.
기존 과거 evidence는 수정하지 않았다.

[소스 목록](sources.json)·`sources.tar.gz`, [문서 점검](docs-check.json), [SHA256SUMS](SHA256SUMS)를
따른다. 상세 명령·빌드 설정·원문 검사는 `validation.tar.gz`에 있다. 큰 trace는 Git LFS다.

```sh
python3 tests/integration/someip/front_run.py build/new-epoch-service --three --diagnostics --diagnostic-epochs --diagnostic-service --simple-vehicle --isolated-ecus --cases central-rejoin
python3 tests/integration/diagnostics/audit_native_service.py build/new-epoch-service/central-rejoin-1 --mutations
python3 tests/integration/carla/audit_supervised_speed.py docs/test-plan/evidence/service-carla-recovery/carla/recovery --output /tmp/recovery.json --mutations --replay build/m1-angle/tests/integration/carla/m7_1g/m7_wheel_shadow
python3 tests/integration/carla/audit_m7_1r_work.py docs/test-plan/evidence/service-carla-recovery/carla/recovery --output /tmp/recovery-work.json
```
