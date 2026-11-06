# 이전 milestone 소프트웨어 후속 검증

2026-11-06. 기존 실패 원본·수용 수치·전체 milestone 범위는 유지한다.
이번 범위는 M8 제동 측 조건부 적분과 M9 journal 쓰기 의도의 crash consistency다.
실제 전원 차단, 전체 도로/차량 모델, Target, 과거 kernel/renderer 원인 규명은 포함하지 않는다.

## M8 방향별 배분 피드백 v3

동결된 model.py/v2는 보존하고 model_v3.py에 `braking_saturated && error<0`의
적분 보류를 추가한다. 반대 방향 error는 기존 amplitude/slew 조건 아래 적분한다.
가속도 출력은 이전 integral을 사용한다. 계수·20ms 주기·원래 참조는 그대로다.
두 flag가 false이면 v1, braking=false이면 v2와 전체 상태/출력이 일치해야 한다.

성공한 배분만 기존 PropulsionSelection에 요청/선택 braking Nm와 braking_limited를
추가한다. 이름은 기존 호출과 진단 reason 호환성을 유지한다. 선택 값은 CAN 양자화 전
회생+마찰 배분이며 Actual·달성 감속도·permission을 뜻하지 않는다. 잔류 Actual 회생으로
마찰 명령을 늦춘 경우도 보수적으로 적분을 보류할 수 있다. 기존 BrakingCapacity/Deficit/
Excess 보호와 임계값을 유지하며 큰 용량 부족을 정상 포화로 바꾸지 않는다.

SpeedRequest의 기존 opt-in은 양쪽 피드백을 검증한다. 첫 release는 양쪽 적분을 보류한다.
같은 epoch/직전 request/원래 시각·age·단조성, 유한한 0<=선택<=요청, flag 일관성,
음수 가속도에 양수 제동 요청이 필요하다. 누락·변조는 기존 진단 reason7로 latch한다.
source/expiry를 갱신하지 않는다. CARLA trace/result는 allocation_feedback_schema=3을
명시하고 oracle는 기존 schema2 기록도 해당 v2 규칙으로 읽는다.

검증 분모와 기준:
- 정상·제동 포화·해제·반대 방향 적분·양방향/변동 제한·fault/새 INIT의 독립 Python/C++
  전체 state/출력 비교. 기존 abs+relative1e-12와 v1/v2 동등성 검사를 유지한다.
- 합성 plant: 초기속도3m/s, 목표2m/s, 외란+.08m/s², 제동한계 첫15초 .12m/s²/
  이후1.5m/s², 20ms Euler·50초. v3가 제한 미반영보다 음수 integral 누적과 속도
  undershoot가 작으며 최종오차<.01m/s. 같은 획득 입력으로 C++도 비교한다.
- 실제 allocator→SpeedRequest 연결, 변조 거부·INIT/authority 보존, 용량 부족 보호 유지.
- 저장된 S03 원본 획득 입력의 native 재생과 독립 PI/명령 ancestry 감사 및 손상 거부.
  이것은 offline replay이며 새 CARLA 물리 실행·ODD 수용이 아니다.

## M9 저장 실패와 프로세스 중단

pending checkpoint를 만들고 fsync(file, directory)한 뒤 journal을 append/fsync한다.
그 후 pending→commit rename/fsync(directory)를 수행한다. pending은 미확정 의도이며
commit이 아니다. 재시작 시 pending이 있으면 suffix가0이어도 read-only/incomplete다.
기존 pending·원본 suffix를 자동 삭제하지 않는다. 기존 archive/restore는 그대로 보존한다.

Linux test 전용 linker syscall interception으로7개 경계(write pending, sync pending,
sync directory, write journal, sync journal, rename, sync directory)를 검사한다.
write는 ENOSPC, sync/rename은 EIO를 주입하고, 각 syscall 직후 자식 프로세스 종료도
별도로 검사한다. write/sync EINTR 재시도6개와 short write2개, no-tail pending도 검사한다.
원본 committed prefix가 동일해야 하며 실패한 append는 성공을 반환할 수 없다.
rename 전은 원래 watermark만 replay한다. rename 후 실패/응답 유실은 재시작 후 유효한
새 commit이 보일 수 있다. 이 경우 동일 transaction의 Duplicate receipt는 허용하지만
incomplete 상태에서 새 clear는 거절해야 한다. duplicate와 새 clear를 구별한다.

Archive fsync2개, restore fsync9개 실패 경계를 검사한다. 원본은 불변이어야 하고,
복원 lock이 보이면 그 이전 모든 content가 기록/동기화돼 있어야 한다. 중단 목적지를
자동 재사용하지 않는다. 이는 OS 오류/프로세스 crash 검사이며 캐시 소실·매체 고장·실제
전원 차단 증명이 아니다. 의도 파일 생성조차 실패하고 gap marker도 기록할 수 없는
매체에서는 영속적 실패 기록을 보장할 수 없다.

관련 Debug 회귀·ASan/UBSan·정적 검사를 수행한 뒤 heavy 작업이 끝난 상태에서 기존
native 서비스 정상/ACK-loss/Stop-ACK-loss3개를 고정 재실행한다. 정상 exit0,
주입 거부 exit1, 각 원본 서비스/순서/시간/응답 audit와 mutation 통과가 필요하다.
이전 장시간/loaded cohort를 대체하지 않는다. 실행·실패·source/binary identity를 새
[evidence](evidence/milestone-followup/README.md)에 보존한다.

## 추가 실제 CARLA 실행 분모

Offline S03에서 음수 적분 보류가 실제로 발생하여, 새 v3의 물리 추종을 별도로 검사한다.
실행 전에 분모를 정상 S03 v2 경로1회·8000×10ms로 고정한다. 기존 Town06 경로·seed·
1696kg/.355m·기존 모든 route/speed/work 기준·320 substeps를 유지하고 새 native binary와
현행 설치 서버를 사용한다. CLI는 기존 `--propulsion-aware`이며 schema3를 요구한다.
정상 trace의 route+mutation, 방향별 selection/PI+mutation, raw native/work/EV audit,
원래 terminal wheel stop과 orderly server exit130을 모두 요구한다. 정상 정지/HV-off나
전체 ODD 수용으로 확대하지 않는다. 실패하면 원본을 보존하고 자동 재시도로 분모를 바꾸지 않는다.
