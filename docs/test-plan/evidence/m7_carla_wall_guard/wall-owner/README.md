# 새 wall INIT·owner/수신 분리 실행 근거

2026-10-28. **Native runtime component 한정, 전체 M7 NOT CLOSED.**
새 CARLA 실행·서버 설치·빌드는 하지 않았다. 합성 stationary wheel/zero-work 생산자와 실제
Host CLOCK_MONOTONIC timer를 사용했다. native Controller/Zone/vECU/Actual은 원래 구현을 쓰지만,
이 시험의 Actual이 CARLA 또는 합성 work 생산자에 적용되는 주행 폐루프는 아니다.

## 구현과 경계

`WallRig`는 새 `M7MONO01` domain에서 INIT한다. 단일 mutation owner가 원래8-role service와
actuator/단일 EV를 실행하고, IO thread는 고정8개 SPSC mailbox로 receipt만 넘긴다.
각 실제 invocation에 owner를 한 번 호출하며 과거 ECU job을 재생하지 않는다. 응답 모델만
실제 elapsed를1ms 이하 내부 구간으로 적분한다. overflow는 latch하고 미정산 receipt를 덮지 않는다.
정상 권한이 닫혀도 이미 완료된 유효 work를 정산하며, 보호 이후 정상 credit을 다시 열지 않는다.

일반 model/원래 Controller20ms·Zone/leaf10ms·BMS20ms·Drive30ms·expiry는 유지한다.
새 wall INIT만 첫 work 정산 이후 취득에서2ms 이상 지난 위상을 사용한다. Initialize 전달을
원래 안전 근거가 생길 때까지 보류할 수 있으나 source/enable/ACK·message age/commit window를
변경하지 않는다. 준비가 끝나지 않으면 원래 deadline에서 실패하며 거부된 INIT를 재시도하지 않는다.
functional 모드의 기존8ms INIT offset·14ms Controller phase는 바꾸지 않았다.

`WallReceipt`는 wheel/work가 **같은 monotonic domain**이어야 한다. SolverWork의 기존10ms
duration·값·dependency 검사를 그대로 사용한다. CARLA sim timestamp를 wall로 재표기하지 않으며,
잘못된 domain·future·duplicate·frame을 거부한다. held wheel/EV/HV를 새 취득처럼 발행하지 않는다.
전기 이력128개가 넘으면 기존 deferred 규칙대로 전기 validity를 닫고 actuator 보호는 계속한다.
새 보호 요청은 현재 service 시각부터 적용하며 이미 지난 물리 응답 구간에 소급하지 않는다.

실제 CARLA simulation dt/EV work와 wall acquisition의 연결은 아직 없다. 이 API에 CARLA
receipt의 시각만 교체해 넣을 수 없고, `next_frame=0`이며 기존 server admission domain과 다르다.
queued/in-flight RPC containment 및 wall-origin Actual의 실제 CARLA 제동 수용도 남아 있다.
[ICD draft-v24](../../../../archive/carla-history.md#icd-새-wall-owner의-구현-범위-draft-v24)를 따른다.

## 최종 실행 결과

| 실행 | 결과 | 한계/원본 |
| --- | --- | --- |
| FIFO18 정상2회 | 각 PASS_CASE_ONLY | 각1.5s·149개 합성 receipt 정산. 판정 가능한7,480 slot의 누락/late0. `fifo/1-normal`, `fifo/4-normal` |
| FIFO18 IO 단절2회 | 각 PASS_CASE_ONLY | 1.1s 이후 생산자만 대기. 각7,480 slot 누락/late0, wheel/EV 시각 동결·보호 Actual 지속. `fifo/2-gap`, `fifo/5-gap` |
| FIFO18 owner10ms 정지1회 | PASS_CASE_ONLY | 36개 미완료 slot을 그대로 보존, deadline fault→보호 선택. 미완료를 정상 timing PASS로 세지 않음. `fifo/3-owner-stall` |
| 일반 / ASan·UBSan | 각각103/103 | `tests-normal-reviewed.log.gz`, `tests-asan-reviewed.log.gz` |
| TSan 관련 경계 | 16/16, race 경고0 | `tests-tsan-reviewed.log.gz`; wall watch/terminal/새 owner/mailbox |
| TSan 실제 probe | race 경고0, **timing 미수용** | `tsan-gap.*`: 실행1,332회, 정상 armed0, missed8. sanitizer 비용 중 deadline 보호 선택 |
| 기존 native 입력 재생 | 정상901/보호401 출력 모두 정확히 동일 | `replay-*-reviewed/result.json`; 새 CARLA 시험 아님 |
| 독립 감사 손상 | 6/6 거부 | future wheel, work 누락, job backfill, owner 누락, deadline 변경, 보호 후 rearm. `audit-negative.json` |

FIFO 시험은 이미 허용된 RLIMIT_RTPRIO20 안에서 `chrt -f 18`을 사용했다. 프로세스와 그 thread가
상속한 FIFO18이며 기존 M6의 개별 role priority 배치나 M6 수용을 바꾼 것이 아니다. 원래
M4 monitor의2ms release/4ms deadline과10개 owner 계측을 사용했다. owner/IO TID·policy·priority·
affinity는 각 JSON, 실제 호출은 CSV에 있다. 짧은 무CARLA component 결과를 보장 상한으로 확대하지 않는다.

IO 단절2회는 기점 이후 각각22.019/22.005ms에 최초 보호 fault, 그 뒤0.998/0.999ms에 실제
전체 selection mask255를 관측했다. 새 Actual torque0·pressure1MPa는 선택 후 각각211.001/
210.999ms였다. 기존100ms loss/230ms 응답 경계로 감사했다. native actuator 모델 결과이며
CARLA 차체 감속·물리 정지 결과가 아니다. 정지 주입은 감시 fault 후 보호 Actual까지202.977ms였다.

## 실패·수정 이력

1. 첫 `ctest -L m7`는 **No tests were found**였다. 실제 선택은 `-R '^M7'`로 바로잡았으며
   빈 실행을 PASS에 합산하지 않는다. 초기7/8개 등 component 분모도 최종103과 합산하지 않는다.
2. 초기 `gap-01`, `gap-02`는 fault 주입 전에 native gate가 닫혔다. 완료 EV work를 ECU
   service 뒤에 commit해 센서 의존 시각을 한 주기 더 지연시키던 순서를 수정했다. 최종은 response
   history 확보→work commit→sensor publish→ECU service 순서다. phase/jitter component 검사를 추가했다.
3. `final/gap`는 INIT의20ms reset-evidence 경계에서 실패했다. 최초 Initialize 보류만 추가한
   `tests-init-fix.log.gz`도 1개 실패했다. wall INIT의 시작 위상을 첫 완료 관측 이후로 옮기고
   원래 commit window 안에서 안전한 근거로 Initialize를 전달한다. `tests-init-phase.log.gz` 및
   최종 회귀가 후속 근거다. 기존 M6/functional 세션 코드는 바꾸지 않았다.
4. 최초 감사는 fault 선택과 동시에 mask255를 요구했다. 실제 native에서는 최초252 이후 다음
   실제 service에서255가 된다. 즉시 ACK를 만들지 않고 기존100ms 안의 전체 선택 완료와 이후
   latch를 검사하도록 감사기를 수정했다. `final-phase/*-audit.json`을 덮지 않고 원본에 대한
   수정 감사는 `*-audit-reviewed.json`에 보존했다.
5. OTHER0 `final-phase`의6개 실행은 수정 감사에서5개 통과/1개 실패다. `6-gap`의 monitor(owner9)
   slot2개 누락은 실제 실패로 유지한다. 별도 FIFO5개 실행을 이 실패의 소거·무조건적인 Host
   timing 보장으로 해석하지 않는다. 현재 probe mode/결과는 각 manifest와 원시 로그가 우선한다.

초기 시도는 당시 완전한 source snapshot을 보존하지 못했다. 해당 로그/원시 trace와 수정 순서는
유지하되 `sources/`의 최종 코드가 모든 초기 실행에 사용됐다고 주장하지 않는다. 최종 FIFO의
binary hash는 이후 검증한 최종 binary와 같다. 모델·안전 요구를 완화해 실패를 없애지 않았다.

## 재현·보존

저장소 root에서 기존 `build/m7-functional`, `build/m7-functional-asan`, `build/m7-wall-tsan`
설정을 사용한다. `cmake --build build/m7-functional --target m7_wall_owner_probe m7_wheel_test`
후 다음처럼 **새 output prefix**로 실행한다. output directory는 먼저 준비한다.

```bash
chrt -f 18 build/m7-functional/tests/integration/carla/m7_1g/m7_wall_owner_probe /tmp/m7-wall-gap gap
python3 tests/integration/carla/audit_m7_wall_owner.py /tmp/m7-wall-gap --output /tmp/m7-wall-gap-audit.json
ctest --test-dir build/m7-functional -R '^M7' --output-on-failure
setarch x86_64 -R build/m7-wall-tsan/tests/integration/carla/m7_1g/m7_wheel_test --gtest_filter='M7WallOwner.*:M7WallMailbox.*:M7WallWatch.*:M7TerminalResponse.*'
```

`normal`, `gap`, `owner-stall`은 고정 probe 사례다. process exit0은 실행 완료만 뜻하며 별도
감사 판정이 필요하다. FIFO 권한이 없으면 그 사실을 실패로 기록하며 권한·한도를 자동 변경하지 않는다.
빌드/검사 도중의 진단 시도와 최종 순차 timing 실행을 구분한다. 최종 FIFO 중에는 별도 build,
CTest, CARLA를 실행하지 않았다.

`archive-manifest.json`은 원본/저장 hash, 최종 project-owned source hash와 기존 M6 경로의
diff 없음, `fifo/manifest.json`은 실제 argv와 binary hash를 기록한다. 컴파일 binary는 저장소에
넣지 않았다. 최종 source는 `sources/`, 실패 포함 원시 trace/로그는 gzip으로 보존했고
`SHA256SUMS`는 저장 파일 전체를 검사한다.
