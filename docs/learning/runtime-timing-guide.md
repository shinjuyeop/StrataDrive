# 주기 실행과 독립 감시

## 주기와 원천 시각

Release는 실행 예정 시각, jitter는 예정→실제 시작, body elapsed는 시작→끝,
response는 release→끝, deadline은 완료 시한이다. CPU 시간은 thread가 실제 CPU에서
계산한 시간이며 sleep/실행 대기·선점과 구분한다. 실행하지 못한 예정 slot도 분모에 남긴다.

늦은 일을 몰아서 재생하거나 다음 release를 현재 시각으로 옮기지 않는다.
새 CAN publication·cached snapshot 읽기로 원래 acquisition/sequence를 바꾸지 않는다.
유효 RX 감시와 job completion 감시는 별도이며 어느 하나의 heartbeat로 다른 loss를 메우지 않는다.

| 코드 | 읽을 내용 |
| --- | --- |
| `vecu/common/periodic_task.*` | absolute release·완료 기록·독립 deadline latch |
| `vecu/common/latest_snapshot.hpp` | bounded SPSC 최신 snapshot의 소유권 교환 |
| `simulation/runtime/steering_runtime.cpp` | ECU·monitor·plant 실행과 실제 output 적용 |
| `simulation/runtime/`의 multirate/owner 연결 | ECU/RX·monitor·plant 분리, 실제 토크 CAN 반환 |
| `tests/integration/runtime/` | jobs/plant/monitor CSV·miss/skip·환경·판정·hash |

## 작은 실행부터 확인

[core 빌드](../../README.md#시작하기) 후 새 출력 경로로 실행한다.

```sh
build/m1-angle/actuator_demo steering-runtime stall build/m1-angle/my-m3-stall
python3 tests/integration/runtime/check_timing.py --analyze build/m1-angle/my-m3-stall
```

`my-m3-stall`은 기존 경로를 재사용하지 않는다. Stall 주입은 정상 timing 실패와
독립 monitor의 보호 선택·실제 적용을 확인하는 예제다.
`jobs.csv`의 release/deadline/start/end·미완료와 `monitor.csv`, `plant.csv`를 같은 clock에서 대조한다.
`run.json`·`environment.json`의 실제 policy/priority/CPU/TID·계측·config·source/binary hash도 확인한다.

## CPU·FIFO와 결과 해석

같은 workload·부하·CPU 배치에서 OTHER/FIFO와 full/minimal trace를 비교한다.
Requested duty와 실제 CPU 시간을 구분하고 placement/load control부터 확인한다.
설정이 하나라도 실패하면 gate를 열지 않는다. 실제 RT 권한과 kernel 지원은 실행 환경마다 확인한다.
FIFO 허용, PREEMPT_RT, kernel trace 권한, Target 정시성은 각각 다른 조건이다.

Miss/skip·release→완료·wakeup/CPU 대기·body/CPU·보호 선택/적용을 따로 보고한다.
Control 실패는 제외 이유를 남기고, 유효한 timing FAIL은 분모에 포함한다.
Sanitizer 경고0은 timing 통과가 아니다. 실제 관측 tail은 WCET나 보장 상한이 아니다.

## Hosted OS·kernel 관측

Trampoline POSIX Steering은 OS Task/Event/Alarm의 별도 학습 파일럿이다.
설정·생성·native/ARM64 build와 실제 Jetson 실행을 구분한다. ECU와 plant는 별도 process이며
Host 자원을 공유하므로 물리 fault 독립성을 주장하지 않는다.
Kernel trace는 timer expiry → wakeup → runnable → CPU 배정 → body·선점/IRQ를 분리한다.
유실·clock 불명·marker/cleanup 실패가 있으면 원인 확정 자료로 사용하지 않는다.

이전 고정 cohort·권한/실패 분석은 [M3 검토](../archive/milestone-reviews.md#m3),
[M4 kernel 프로토콜](../archive/m4-test-protocols.md#m4_kernel_capture),
[실행 근거](../test-plan/evidence/m4_kernel_campaign/README.md)에서 확인한다.
실제 수집은 해당 프로토콜의 범위·권한·한도를 따르고 진단을 정상 timing 수용과 구분한다.
