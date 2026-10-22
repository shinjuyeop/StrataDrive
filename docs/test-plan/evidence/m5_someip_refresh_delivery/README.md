# Host FIFO command renewal delivered to the actual Leaf

2026-10-22. **Host FIFO Central↔Front 제한 범위 수용 / Rear 연결 진행 가능**.
구현·최종 시험 소스 `6b2b5a3`. 시작 HEAD와 fetch 후 origin/main은 모두
`b624243eaf6720f6ce455f6e0464c096e489c87c`, 작업 트리는 깨끗했고 이후 변경은 없었다.
사용자가 승인한 profile 변경과 필수 시험 범위를 적용했다. Rear 구현은 이번에 하지 않았다.

[사전 고정 protocol](protocol.md), [기계 판독 결과](results-summary.json),
[전체 결과표](results.csv), [실제 수신 여유 CSV](renewal-margins.csv),
[보호·세션 시간축](timeline.csv), [논리 재현 시간축](replay-timeline.csv).
원본은 [raw-evidence.tar.gz](raw-evidence.tar.gz), 파일별 SHA256은
[raw-manifest.json](raw-manifest.json), archive 식별자는 [archives.json](archives.json).
기존 [fifo-refresh](../m5_someip_fifo_refresh/README.md)의 실패·분모·원본은 변경하지 않았다.

## 원인과 수정 전 재현

확인된 결함은 오래된 입력으로 제한된 허가와 배분/갱신 위상의 조합이다.
`permission_expiry()`는 입력의 **원래 시각+허용 age**와 원래 lifecycle/acknowledged
PowerRequest expiry의 최솟값이다. 이를 단순히 management 생성 시각+수명으로 볼 수 없다.
`permission-limit`은 그 최솟값을 만든 원래 source, exclusive expiry, 입력 종류를
bounded trace에 기록한다. 동률이면 기존 평가 순서의 첫 항목을 기록한다.
CAN/owner-wire payload와 expiry 계산 결과는 바꾸지 않았다.

- 기존 사건: `release+20ms`에 **69,603ns 부족**하여 배분을 보류했다. 다음 management는
  이전 명령 expiry 이후였다. 이 분기와 최초 Leaf expiry는 이전 원본으로 확정됐다.
- 당시 각 입력별 전체 관측이 없어 **과거 사건의 정확한 최솟값 입력 및 네트워크 지연은
  여전히 특정할 수 없다**. 새 관측에서 SteeringActual 제한이 주로 나타났고 DriveActual,
  acknowledged PowerRequest 제한도 있었다. 이것을 과거 입력의 확정 증거로 소급하지 않는다.
- 결정적 재현: 실제 모델을 500µs 간격(offset430,396ns), 실제 owner를200µs 간격으로 실행하고,
  1s부터 Front feedback의 전달을6ms로 고정했다. 새 값을 취득하는 원래 모델/센서/Leaf/codec/
  receiver를 모두 사용했다. 필드 시각을 고치지 않았다. 역사적 실제6ms 지연을 주장하는 시험이
  아니라, **정상 허용 입력 age/전송 범위 안에서 같은 보류→갱신 단절을 만드는 충분조건**이다.
- 이 재현의 부족분은 **169,603ns**(역사적 값보다100µs 큼). 기존 exact69,603ns 계약 시험도
  유지한다. 초기에 정상 갱신을 요구한 assertion은 exit1/FAIL이었다. 최종 소스의 legacy20
  비교 사례도 underlying normal result=FAIL을 기대하며, 이를 정상 운전 PASS로 세지 않는다.

| 재현 시간(ns) | 실제 흐름 / legacy20와 host10 비교 |
| --- | --- |
| 1,990,430,396 | 실제 Steering 센서 취득; Actual 원래 source |
| 1,990,800,000 | Central validator의 해당 Actual 수용(`valid-feedback`, owner7/code0) |
| 2,000,600,000 | 배분 nominal release; 과거 허가는 source<release이므로 기다림 |
| 2,004,600,000 | management 새 허가 생성. SteeringActual+30,000,001 = **2,020,430,397**이 최소 |
| 2,004,800,000 | host10은 실제 CAN grant ingress 일치 확인 후 allocation, Front token240 발행 |
| 2,005,000,000 | Front owner→Steering/Brake 실제 수신·수용; Front 결과 뒤 Rear token241 발행 |
| 2,005,200,000 | Rear→Drive 실제 수신·수용; 원래 payload/expiry 보존 |
| 2,010,430,397 | legacy20의 마지막 명령 원래 expiry. legacy는 위 대체 명령을 발행하지 못함 |
| 2,010,600,000 | legacy 세 Leaf expiry 감지, Central 최초 fault; 전부 보호2,010,800,000 |
| 2,014,600,000 | 다음 management. legacy 마지막 명령에는 이미 늦음; host10은 계속 새 갱신 |

host10은 중간10ms release에서도 실제 새 허가·VehicleRequest·명령을 발행한다. 비교 시점의
host10 직전 명령은 legacy의 마지막 명령과 별개의 새 명령이다. 기존 명령의 expiry를
연장한 것이 아니다. 전체 재현에서 legacy 각 Leaf11개 뒤 단절, host10 각102개 수용,
**모든 연속 갱신 최소5,230,397ns 여유**. 추가 command-loss 재현에서는 원래 expiry/보호가
계속 동작한다. 최초 보류/만료를 보호 후 발생한 후속 expiry와 구분했다.

## 명시적인 새 Host profile: host10-v1

| 항목 | 기존 legacy20 | host10-v1 실제 코드 적용 |
| --- | --- | --- |
| Central allocation / 실제 VehicleRequest 생성 | 20ms | **10ms** |
| management | 10ms, enable+4ms phase | 동일 |
| grant 준비 조건 | source≥release, 살아 있는 실제 수신 grant, expiry>release+20ms | 위 source/수신 검사를 유지하고 expiry>release+**18ms** |
| 인계 여유 | 다음 nominal release까지만 검사 | 다음10ms release 뒤 **8ms**(management phase4ms + 비동기 인계4ms) 예약 |
| 실제 센서 취득 / Leaf body | 기존 모델500µs, Leaf10ms/BMS20ms | 동일 |
| 명령·허가 source/expiry, input age | 원래 값/기존 validator | 동일 |
| native 기회/deadline, 전송 envelope | 2ms/4ms, 20ms | 동일 |
| 큐 / pending batch / SDK | RX/TX8, 한 command batch, 기존 SDK | 동일 |

`central/coordinator/command_renewal.hpp`가 두 profile을 구분한다. 기본 component/network는
legacy20이며, SOME/IP `Owners`는 port와 coordinator에 **Host10ms를 명시**한다.
`host-renewal-period` 런타임 기록(12개 보존)과 runner plan의10,000,000/18,000,000ns가 일치한다.
reference.yaml이 이를 설정한다고 가정하지 않는다. 실제 source 간격/Leaf 수신 CSV도 보존했다.

단순히 source≥release를 없애는 이전 철회안을 재도입하지 않았다. management phase만 뒤로
옮기면 이미 짧아진 이전 명령의 남은 시간을 더 소비한다. 기존10ms management와 같은 갱신
기회를 사용하여 원격 인계 전에 새 명령을 만들고, 다음 nominal release를 간신히 넘는 허가는
받지 않는다. 이는 **모든20ms 전송 지연을 정상 운전으로 허용하는 보장**이 아니다.20ms는
최대 전송 거부 envelope이고, 늦은/중단된 갱신은 원래 expiry에 따라 보호한다.
제어 명령/VehicleRequest 트래픽은 대략2배, VM/센서/Leaf 주기는 그대로다.

## 최종 동일 소스 시험

| 시험 | 횟수 / 결과 | 의미 |
| --- | --- | --- |
| Normal FIFO 정상 무부하 | **2/2 PASS** | 각2540ms 기존 전체 관측 구간 |
| Normal FIFO 기존 부하 | **2/2 PASS** | CPU1/2 OTHER 7ms busy/10ms, 실제 부하 control PASS |
| command-loss / owner-pause / central-stop / restart-live | **각1/1, 총4/4 PASS** | 실제 정상 전제조건 뒤 주입; 보호/정리/재가입 |
| ASan/UBSan 실제 SDK normal + command-loss | **2/2 PASS** | 메모리/UB 오류0, 해당 기능 실행 완료 |
| TSan 실제 SDK normal + command-loss | **2/2 PASS** | 경합 경고0, fixed-layout; SDK 전체 안전성 증명 아님 |
| 최종 전체 CTest Normal / ASan+UBSan | **각983/983 PASS** | 공통 coordinator/VM 변경 경계 전체 회귀 각1회 |
| 개발 focused logical / 관련 계약 | **19/19, 85/85 PASS** | 전체 회귀를 개발 때 반복하지 않음 |
| Python bookkeeping | 최종 **20/20 PASS** | SDK 실행과 별개. 초기19/20(import 결함) 원본 보존 |

최종 실제 SDK 총**12/12**. timeout/누락/강제 cleanup/예상 밖 SDK 오류/sanitizer 진단 모두0.
Normal 네 정상 사례에서 **각 Leaf 총698개, 전체2,094개** 명령을 실제 수신했고, 전송 요청과
source/Epoch/original expiry가 일치했다. 최소 갱신 여유: 무부하14.097/14.458ms,
부하13.555/14.499ms. 정상 운전의 unsolicited protection/native miss는0이다.
SDK IP 데이터 패킷 normal각350개 이상 및 실제10.88.0.1↔.2 TCP socket/route/maps를 보존했다.

- command-loss: 마지막 명령 expiry600786965789663ns. Drive expiry검출+23,250ns,
  Front Steering+183,734ns/Brake+185,405ns, Front 보호 선택+189,046ns. 기한을 연장하지 않았다.
- owner-pause: 의도된 Front98개 miss. 원래 deadline600788700261423ns,
  독립 monitor검출+2,414ns, 물리 override는 검출 뒤456,983ns. 정지 owner가 ACK를 만들지 않았다.
  **normal_timing_ok=false / fault_protection_ok=true**로 분리한다.
- Central crash: 의도된 kill(-9)은 정상 종료로 세지 않는다. 살아 있는 물리 감시와 Front가
  보호하며 Front SDK stop/join은 반환했다. Front 선택600790375779735ns.
- restart-live: Front1 의도된 kill(-9), Central 생존. 신뢰된 durable Epoch2 발급→실제8 ACK
  mask255→RunLease/arm→정상 제어 복구; old-Epoch diagnostic1개 거부. 살아 있는 두 SDK의
  stop/join 반환. 이전 generation의 guard 파일 alias 한계는 기존 oracle/원본과 동일하다.

Normal 성능과 sanitizer wall time은 별개 판정이다. 위 sanitizer 두 사례만 새 SDK 기능 근거이며
다른 고장 조합을 이번에 계측 완료했다고 하지 않는다. 추가 overflow/close-full 경계는 수정하지
않아 재실행하지 않았고 기존 근거를 보존한다. 전체48회/모든SDK조합/OTHER부하 재수용/극단·복합
고장/61ms 미재현 사건 조사/Rear 네트워크/Jetson/실제 IO/전체 시스템은 **NOT RUN**.

## 환경·계측·재현

기존 Ubuntu22.04.5 / Linux6.8.0-138 PREEMPT_DYNAMIC / i7-11700(8 physical,16 SMT),
uid1000, 허용CPU0..15, 실제 RT limit20/20. Central1 FIFO11, Front2 FIFO18,
physical3 FIFO19, 독립 monitors0 FIFO20. SDK/sender4/5 OTHER0, plant auxiliary6 OTHER0.
명령·guard 주기와 실제 thread readback은 원본 runtime/watch JSON에 있다. 권한/OS 변경 없음.
모든 빌드/시험은 동일 `build/.m4-exclusive.lock`; 부하 측정 중 빌드/대규모 검색 없음.

vSomeIP **3.7.6 / 4187431d2815bd351845a09d01aa85b2a3163cab**, SDK tree clean,
Boost1.85.0, GCC11.4, adapter C++20. compile commands 실제 최종-O2, debug/frame pointer;
프로젝트와 SDK core/cfg/sd/e2e 및 Boost filesystem/atomic의 ASan+UBSan 또는 TSan symbol,
동적 link와 실행 maps를 보존했다. SDK의 기존 compiler `-Wno-tsan`은 compile warning
옵션이며 runtime TSan suppression 파일/annotation을 추가하지 않았다. 시스템libc/libstdc++는
계측하지 않았다. TSan은 기존 `setarch x86_64 -R` process-local fixed-layout 조건;
프로세스 간 mmap SIL IPC 및 실행하지 않은 SDK 경로까지 race-free로 인증하지 않는다.

원본 안의 `environment.json`, `identity.json`, `final-builds.json`, `final-ctest.json`,
`sdk-campaign.json`, 각 cohort `plan.json`은 정확한 source/binary/library SHA와 명령/exit를 가진다.
깨끗한 checkout에서는 먼저 pinned SDK 빌드(시스템 설치 없음):

```bash
python3 tests/integration/someip/build.py normal
python3 tests/integration/someip/build.py asan
python3 tests/integration/someip/build.py tsan
python3 tests/integration/someip/front_run.py build/renewal-quiet --native-watch --fifo --profile normal --cases normal --normal-repeats 2
python3 tests/integration/someip/front_run.py build/renewal-loaded --native-watch --fifo --profile normal --loaded --cases normal --normal-repeats 2
python3 tests/integration/someip/front_run.py build/renewal-faults --native-watch --fifo --profile normal --timing --cases command-loss owner-pause central-stop restart-live
python3 tests/integration/someip/front_run.py build/renewal-asan --native-watch --fifo --profile asan --cases normal command-loss
python3 tests/integration/someip/front_run.py build/renewal-tsan --native-watch --fifo --profile tsan --fixed-layout --cases normal command-loss
python3 tests/unit/someip_pilot_test.py
```

실행 output은 새 경로여야 한다. 현재 사용자 RT 권한과 unprivileged namespaces가 필요하며
명령은 sudoers/커널 설정을 변경하지 않는다. 논리 재현은 CMake 기존 unit build의
`m4_async_runtime_test --gtest_filter=M4RefreshDelivery.*`; 환경
`STRATADRIVE_M4_RESULTS=<새경로>`로 actual trace/FAIL legacy result까지 저장한다.
최종 full CTest 로그는 최초 pre-fix FAIL을 대체하지 않는다.

## 판정과 남은 범위

승인된 필수 조건을 만족하여 **host10-v1 / 위 CPU·FIFO·기존 부하 / 2540ms 관측의
Central↔Front Host functional SIL**을 한정 수용한다. 실제8참여자와 원래 보호·재가입을
사용하며, 다음 작업에서 **Rear 연결 진행 가능**이다. Rear/Drive/BMS/Power는 현재 Central
프로세스 내부이고 물리/센서 및 trusted demand는 기존 SIL fixture다.

역사적69,603ns 사건의 숨은 입력/전달 위치,61ms 모델 사건, 기타 native/OTHER 및 DDS
FAIL/OPEN은 원본과 함께 남는다. 이번 갱신 경로의 재현·수정을 했다는 판단과 모든 과거
사건의 인과관계 해결은 다르다. 이들 전체를 닫는 것을 한정 진행의 새 gate로 추가하지 않는다.
DDS 제어 gate CLOSED, M4 전체 NOT CLOSED, Jetson/전체 시스템 NOT RUN은 그대로다.
외부 문의·게시·메시지는 전송하지 않았다. Daybreak/콘텐츠 제한 재발은 없었다.
