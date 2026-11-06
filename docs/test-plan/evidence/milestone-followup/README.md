# 이전 milestone 소프트웨어 후속

2026-11-06. 기준 commit `ce760dc`. **PASS — 방향별 배분 피드백의 고정 S03 기능 검증과 유한 journal 오류/중단 검증.**
[사전 기준](../../milestone-followup-protocol.md)을 유지하며 과거 실패 원본·수용 범위는 바꾸지 않는다.

## 해결한 소프트웨어 경로

M8의 선택형 배분 피드백을 제동 방향까지 연결했다. 성공한 allocator의 양자화 전
요청/선택 braking·flag를 같은 epoch/직전 request/원래 시각으로 검증하고 음수 error의
적분 누적을 보류한다. 반대 방향 적분·기존 BrakingCapacity/Deficit/Excess 보호는 유지한다.
첫 release는 양쪽 적분을 보류한다. CAN/owner-wire·DTC reason 번호는 변경하지 않는다.
`model_v3.py`와 trace/result schema3를 추가하고 기존 v1/v2 모델은 그대로 보존했다.

M9 journal은 data 쓰기 전에 pending 의도를 file/directory fsync한다. 실패·중단 후
suffix가0이어도 pending이 남으면 read-only/incomplete로 복원한다. 남은 pending이나
원본 suffix를 자동 삭제하지 않는다. Commit rename 뒤의 응답 유실은 새 commit이 보일
수 있으므로 이미 저장된 동일 transaction의 Duplicate와 새 clear를 구별한다.

## 검증

| 검사 | 결과 |
| --- | --- |
| Debug CTest | 1478/1478: unit1126·logical347·transport5 |
| ASan/UBSan | 137/137: unit134·transport3 |
| Python unit | 280/280; archive/restore11 포함 |
| 정적 검사 | 변경 production4 TU와 syscall test의 clang-tidy, googletest 설정을 사용한 cppcheck 통과 |
| v3 독립 모델/C++ | 주 행렬8428개·braking=false8428개·합성 plant각2502개; 전체 state/출력 오차0 |
| v1/v2 회귀 | 기존 모델 동등성 및 propulsion 합성 plant 검사 통과 |
| 저장 오류/중단 | 7경계 오류·7경계 프로세스 종료·EINTR6·short write2·no-tail pending1 =23개 |
| Archive/restore | sync 오류2/9경계·pending 원형 보존; 기존 원본 불변 |
| S03 원본 입력 재생 | native8001관측·PI3960회·배분7920회; 독립 감사·18손상 거부 |
| Native 서비스 | 정상/ACK-loss/Stop-ACK-loss3/3; 각각4감사와 mutation 통과 |
| 새 CARLA S03 | 새 서버1회·physics/EV각8000·schema3·route손상28/selection손상18 거부·서버130 종료 |

합성 plant에서 제한 미반영/방향별 피드백의 최저속도는0.512136/1.993178m/s,
최저 integral은−2.025269/−0.088909, 최종속도는1.999708/1.999996m/s다.
고정 합성 외란/한계 조건의 결과이며 실차 개선율이 아니다.

원본 S03 재생은 음수 적분 보류2회를 검증했다. 기존 v2와 달라진 speed 출력/적분이
7920 held 관측 중902개에 존재한다. 기존 물리 입력을 재생했으므로 새로운 궤적의
폐루프 결과로 해석하지 않는다. [독립 감사](saturation-audit-final.json)를 따른다.

Native는 빌드/정적/회귀/재생이 끝난 뒤 실행했다. 정상 runtime0, 두 fault runtime1은
각각 성공 서비스/의도한 거절이다. 감사4272개 요청의 최대 RTT1.603057ms,
최소 원래 만료 여유18.396943ms다. [세 실행별 값](native-response-summary.json)은
이번 유한 기능 smoke만 뜻하며 이전404821-request loaded cohort를 대체하지 않는다.

새 CARLA의 body plateau 최대오차는30km/h에서0.077184km/h,20km/h에서0.027828km/h,
정지 window 오차0, 양수 목표 최대 overspeed3.483045%다. 경로1333표본·누락0,
횡오차P95 0.034105m·heading P95 0.534945°로 기존 기준을 통과했다.
8000개 solver-work와 단일 EV 정산·원본 native Actual/권한 감사 및 각각의 손상 거부를
통과했다. 이 실행의 실제 음수 적분 보류는2회다. [경로 감사](carla/audit_m8_route.json),
[PI/배분 감사](carla/audit_m8_saturation-mutations.json), [work/EV 감사](carla/audit_m7_1r_work.json)를
따른다. S03의 terminal wheel hold를 NormalStop/HV-off 수용으로 해석하지 않는다.
기존 renderer/cold-load 원인이 해결됐다고 주장하지 않는다.

## 보존한 개발 실패

초기 build의 미갱신 target cache와 GTest macro dangling-else 컴파일 오류를 수정했다.
첫 syscall 시험은 rename 후 재시작에서 동일 clear의 Duplicate도 거절돼야 한다고
잘못 기대했다. 원래 idempotent receipt 계약에 맞춰 새 clear 거절과 Duplicate를 분리했다.
기존 delivery fixture는 pending 생성 실패에도 먼저 data suffix가 생긴다고 기대했지만,
새 쓰기 순서에서는 원본 data가 불변이고 pending이 남는다. ACK 거절·incomplete는 그대로
검사하며 기대값과 이름을 갱신했다. 초기 full/ASan 실패와 수정 후 결과를 모두 보존한다.
Cppcheck의 TEST_P 파싱 실패는 googletest library 설정으로 해결했다. 검사를 숨기지 않았다.

## 남은 범위

- M3/M4 과거 timer/wakeup/IRQ와 SDK failure의 인과 자료는 새 PASS로 복원할 수 없다.
  미채택 DDS의 race/shutdown 문제는 현재 SOME/IP 경로와 별개다.
- M7 일반 renderer/GC·cold-load/기존 package 종료 원인, Native4ms/전체 wall·Target은 별도다.
- M8 동적 가용력/도로 부하 기반 참조·전체 ODD·Planner/localization은 남는다.
- M9 자동 journal rollover/상태 이관/용량 회수, 실제 전원 차단·캐시 소실·매체 열화는 남는다.
  intent 생성조차 실패하고 marker도 저장할 수 없는 매체의 영속 기록은 보장하지 않는다.
- 학습자 최종 검토와 M10–M13은 별도다. Component PASS를 전체 TC/Target PASS로 올리지 않는다.

## 원본과 재현

`sources.json`/`sources.tar.gz`는 기준 commit에 대한 변경 구현·시험 원본이다.
`validation.tar.gz`에는 초기 실패와 최종 build/test/static/model 입력·출력 및 offline 재생을,
`native.tar.gz`에는 세 native 실행의 원본 journal/trace/명령/감사를 보존한다.
`carla/S03/trace.jsonl.gz`는 Git LFS의 실제 새 physics 원본이며 result/events/route와
server report·독립 감사를 함께 보존했다. `carla-runtime.tar.gz`에는 실행된 native binary와
probe snapshot·server/client/readiness 로그가 있다. 원본 raw 파일과 archive member를
다시 비교했으며 [최종 판정](acceptance.json)과 [SHA256SUMS](SHA256SUMS)를 따른다.
`sources.json`은 모델 v3와 정확한 Git 추적 예외도 포함한다. 원래 runtime capture는
`runtime-sources.json`에 보존하고 모델 SHA를 실제 비교 verdict와 대조했다.
`documentation.json`/`documentation.tar.gz`는 최종 문서 snapshot이다.

```sh
ctest --test-dir build/m1-angle -L 'unit|integration.logical|integration.transport' --output-on-failure
python3 -m unittest discover -s tests/unit -p '*_test.py'
python3 tests/integration/longitudinal/check_braking_pi.py build/m7-functional/speed_pi_replay --output-root build/new-braking-equivalence
```

실제 native/CARLA 재현 명령과 artifact hash는 보존한 실행기 및 execution/protocol JSON을
따른다. 기존 결과 경로를 덮어쓰지 않고 새 output/runtime 경로를 사용한다.
