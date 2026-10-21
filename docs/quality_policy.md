# Software quality policy

Status: **M1 통신·M2 모델·M3 Host 실행·M4 Central/Zone component에 적용**. Compiler warnings, GoogleTest,
clang-tidy/cppcheck와 ASan/UBSan을 사용했다. 현재 상태·최신 검증 분모의 기준은 [project_status.md](project_status.md)다.
현재 `97afb35` normal·ASan/UBSan 각각 **C++973/973 PASS**다(unit800/logical164/wall9).
[Settlement 후속 근거](test-plan/evidence/m4_settlement/README.md)와 [M4 종료 검토](m4_exit_review.md)를 따른다.
TSan 경계108/108·native wall9/9 PASS, full trace normal20+TSan20회40/40 PASS다.
기존 native8/9 실패는 미재현·원인 미확정으로 OPEN이며 새 성공에 합치지 않는다.
마지막 전체 Python 회귀 기록은 **137/137 PASS**다(이전120+middleware JSON schema/process-exit14+diagnostic bookkeeping3).
`658562e` 후속 [관련29개 회귀](test-plan/evidence/m5_dds_shutdown_followup/README.md)는
build/ 없는 checkout에서27 PASS/2개 시험 FAIL(하위 조건 포함3건)을 재현하고 잠금 준비를
수정한 뒤 fresh·작업 트리 각각29/29 PASS다. SDK mock bookkeeping과 실제 child cleanup을
검증했으며 새 DDS/성능/sanitizer 실행은0회다. 기존64경고의32 stack 조합과 SDK bitfield
공유 바이트 근거를 보존했지만 모든 경고 FAIL·full-RHC 종료 OPEN·제어 gate CLOSED 유지다.
`9136c1f` focused22개는 수정 전10 PASS/8 FAIL/4 ERROR→22 PASS. 원본 잘못된 JSON을 보존하고 남은 시험을 계속한다.
`1677f85`의 신규8개는 수정 전2 PASS/5 FAIL/1 ERROR→8 PASS다. [실제 DDS 수명 근거](test-plan/evidence/m4_dds_lifetime/README.md)는
Writer normal3·ASan3 PASS, TSan3 FAIL/각2경고, 고의 ASan UAF3 검출을 별도 기록한다.
초기 harness12 setup 실패, wrapper ASan2 PASS/TSan2 FAIL도 보존한다. 제품 코드·SDK 버전/알고리즘은 변경하지 않았다.
[Host 한정 수용 B안](m4_host_acceptance_review.md)은 사용자 승인으로 적용했다. M4 전체 종료는 아니며 DDS 정규 제어 gate는 CLOSED다.
[M5 gate-closed DDS 진단](test-plan/evidence/m5_dds_qualification/README.md)은42회23 PASS/19 FAIL이다.
초기5 build/setup runtime NOT RUN·GDB1회·의도한 timeout 미재현/post-check FAIL1회는 별도 보존한다.
Normal/ASan 수명 관측 PASS를 TSan 전체 안전성이나 정규 제어 허용으로 확대하지 않는다.
원래20ms normal 전달 실패·full-RHC close timeout·미확정 경고 때문에 control gate는 CLOSED다.
새 product973 전체·native40·timing48은 NOT RUN이며 기존 근거를 새 실행으로 세지 않는다.

`d3e7f6d` 별도 고정 수집213425는11쌍 VALID·OTHER2 FAIL(191/186 miss)·FIFO20 PASS다.
FIFO 주입 전 miss0, 원래 deadline 후3.170–5.059µs 검출·이후1.008–3.484µs 보호를 관측했다.
실제 user20/20·FIFO 설정·marker/정리·유실0을 확인했지만 과거 FIFO 원인은 미확정이다.
기존 `cfeda34`212418 유실/INVALID·FIFO20 NOT RUN과 원본 실패는 유지한다.
[새 진단 분모·근거](test-plan/evidence/m4_kernel_campaign/completed_213425/README.md)를 따른다.
`05e088b` native full-trace Normal20+TSan20도40/40 PASS, 경고0이다.
[고정 수집 준비](test-plan/evidence/m4_kernel_campaign/README.md)와
[SDK 후속](test-plan/evidence/m4_sdk_followup/README.md)은 별도 분모다. DDS 공식 옵션 재빌드4/4 FAIL,
Zenoh matched partial4 FAIL/full4 PASS를 보존하며 M4 종료는 보류한다.
이번 C++ 전체·48회 timing 재실행은 없으며 위973/973은 기존 커밋의 결과다. 아래 과거 수치는 당시 범위로 보존한다.
Actuator 6개 + EV 6개 DBC/독립 CRC와 C++ payload 36개의 교차 검사가 PASS다.
[Drive 실행 기록](learning/m1_drive_codec.md)과 [BMS 실행 기록](learning/m1_bms_codec.md)에
도구 버전, 검사 범위와 재현 명령을 보존한다. M1 89개와 M2 첫 Steering 2개·Brake 3개·Drive 3개,
총 local vCAN **97개 case**를 검사한다.
Battery/BMS/Power/Drive gate·에너지/회로 단계는 로컬 component 검사이며 CAN wire나 transport 변경은 없다.
97개 vCAN은 앞선 Drive 응답 단계의 증거다. 직전 gate 단계에는 normal·sanitizer 각각 기존 Drive model vCAN 3개를 재검사해 통과했다.

2026-10-20 첫 VALID kernel 관측: compact-v2 사용자 실행3쌍/6 workload 모두 FAIL, 두 쌍은
종료 marker EBADF이고185513쌍은729726 event·유실0·11951 chain으로 VALID다. 최초 조향 사례는
callback hard-expiry 초과3.714µs, wake→CPU2.856ms, body1.125µs다. 기존 최신-slot 정책에서
2ms 기회가 누락되어4ms deadline 뒤65.184µs 검출·4.895µs 뒤 physical override를 확인했다.
전체 운전 arm 전 사례이며 과거 FIFO/Target 원인 확인으로 확대하지 않는다. `eecc1d7`은
marker 실패에도 raw/stat을 저장·실패 반환하고 collector CPU ring을2MiB로 보완했다. 전체97/97 PASS,
새 실제 tracefs 재실행은 NOT RUN이다. EBADF의 buffer reserve 경로/포화 후보와 확정 사실을
[근거](test-plan/evidence/m4_kernel_valid/README.md)에 구분한다. 이전 실패 수치는 유지한다.

2026-10-20 kernel 첫 실제 관측 후속: `a26a206`은 실제 syscall pretty-printer를 파싱하고
필수 event를 유지하며 optional 중복 수집량/CPU1 buffer를 조정했다. `984d5ac`은 Linux의
relative CLOCK_REALTIME→MONOTONIC base 규칙을 적용하되 ABS realtime/미확인 clock을 거부한다.
실제 trace 발췌 회귀를 포함해95/95 PASS다. 원래183050 capture는 OFF176/ON311 miss·CPU1 event256668 유실,
parser145058줄 실패다. 재분석은762977 event 전부 파싱했지만 원본 유실로9076 chain 전부 UNTRUSTED,
exit2/INVALID를 유지한다. 앞선183033의 EBADF·271/301 miss도 별도 보존했다. 두 실행의
instance 제거/global 불변은 실제 확인했지만 새 compact-v2 수집/cleanup은 NOT RUN이다.
C++ workload·deadline·48회 분모는 바뀌지 않는다. [후속 근거](test-plan/evidence/m4_kernel_capture_followup/README.md).

2026-10-20 kernel 관측 준비: [수집 프로토콜](test-plan/m4_kernel_capture.md)은 OTHER loaded
OFF1회→ON1회와 별도 FIFO Monitor-overrun 진단을 정의한다. 실제 owner TID·원래 실행 CSV를
trace_clock=mono·clock sandwich와 대조하며 timer soft/hard expiry·wakeup·CPU 배정·body 선점/IRQ를 구분한다.
`d20156b` collector/analyzer 위에 `cb0ad7c`가 sleeping→wakeup→runnable 구간 분할을 보완했다.
이 분할 시험은 이전 analyzer에서 FAIL, 수정 후 PASS이며 전체 Python90/90다. 신규19개는 synthetic/임시
filesystem/프로세스 권한 경계 시험이다. 실제 kernel instance cleanup이나 kernel 원인 확인을 뜻하지 않는다.
`d20156b` 비관리자 Normal/OTHER loaded smoke1회는 기존 binary SHA와 동일, UID1000/capability0,
설정·부하·grid·buffer control PASS이나 timing FAIL(266 miss/skip)이다. 원래48회 분모와 별도로 보존했다.
현재 자동 세션의 sudo probe는 exit1/password-required, 사용자 터미널 sudo 성공은 사용자 확인 근거다.
Privileged inventory·OFF/ON pair·실제 cleanup·원인 판정은 NOT RUN이다. 새 C++ full/TSan/48회 실행은
없으며 기존 source별 실패와 M4 보류를 유지한다. [준비 근거](test-plan/evidence/m4_kernel_capture/README.md)를 따른다.

2026-10-20 `29b8221` 후속: `398a1de`는 pending 상태를 다음 배분 실패와 분리했다.
대기 중 allocation tick은 완료 처리하지 않으며 request/support expiry·30ms gap·원래20ms TX envelope와
실제 적용 명령 expiry는 그대로 감시한다. 전송 결과 후 fresh 입력으로 기존 release grid를 따른다.
수정 전4개 focused는2 PASS/2 FAIL, 수정 후 최종 focused55/55 PASS다. 최초 persistent 지연을 정상으로
기대한 시험의 FAIL도 보존했고, 일시 지연 정상/지속 지연 권한 만료 보호로 입력 조건·oracle을 구분했다.
기존19.8ms 재현은 기한 전 pending 충돌에서 exact deadline 보호로 기대 결과를 변경한 유일한 기존 시험이다.
`97afb35`는 진단 runner가 전체 결과 저장 후 FAIL/timeout/누락/TSan 경고에 exit1을 반환하도록 했다.
실제 child process 검증8개는 수정 전1 PASS/5 FAIL/2 ERROR, 수정 후8 PASS; 전체 Python71 PASS다.
최종973개 C++는 원본948+이전 검토18+이번7이며 이름은 모두 보존했다. 전체 normal/ASan·UBSan 각각973 PASS,
TSan 변경 경계108·wall9 PASS, static production4개 PASS다. 같은 source/fingerprint의 고정40회는40 PASS/exit0다.
별도 변경 없는48회 timing은42 PASS/6 FAIL, FIFO24/24, 설정·부하·grid·사전 할당 control48/48이다.
실패6개는 OTHER loaded normal이며 독립 보호 성공과 timing 수용 실패를 구분한다. 통과 fault24회의
원래 deadline→검출0.003282–0.084379ms, 검출→실제 override0.000936–0.986748ms를 기록했다.
원래41/7·42/6·42/6·41/7 실패 기록, native/SDK TSan OPEN, tracefs/perf 제약·Target NOT RUN과
M4 종료 보류는 유지한다. 이번 FIFO 성공이 과거 누락의 원인 규명이나 전체 수용을 뜻하지 않는다.

2026-10-20 `4a399af` 외부 검토 후: 원본948개를 보존하고 old-Epoch reply identity(`7396b2d`),
최초 sent/원래 expiry의20ms envelope(`9e96182`), issuer/Epoch/token 보호 ACK 보관(`57457e6`)을 수정했다.
수정 전 신규 시험은 각각0/3·0/3·1/5 PASS였고 수정 후 각 대상 시험이 통과했다.
첫 전체 실행은 `57457e6` **962/963 PASS**로 기존 command-expiry 관측 assertion이 실패했고 ASan/UBSan은 미실행이었다.
Accepted-input 관측을 내부 명령 expiry로 바로잡은 `c4195a6`는 normal/ASan·UBSan963/963·경계 TSan64/64였다.
제어 시한과 기존 assertion은 변경하지 않았다. 전달 trace 등가성1개와 지연 인과 경계2개를 더한 `1989477`는
전체966/966 두 빌드·경계 TSan67/67·wall9/9, fault artifact33개씩 및 durable CLI 재가입 양 빌드 PASS다.
과거948개와 신규18개의 실제 결과를 별도 열로 남겼고, production4개 clang-analyzer/cppcheck도 통과했다.
이번 vCAN·Release BUILD_TESTING=OFF·전체966개 TSan·새 SDK 실행·Rust 전체 계측은 NOT RUN이다.

같은 후속에서 `f895dc6` native 고정20+20회(1.8s/OTHER/no load/guards off/full trace)는40/40 PASS였으나
원래 TSan CommandDelivery 실패는 미확정이다. 실제 owner 논리 지연 두 조건으로 이전 command expiry와
다음 allocation의 pending 충돌을 구분했고, 틀린 최초 가설/시험 draft 실패도 별도 보존했다.
`1989477`의 새48회는 **41 PASS/7 FAIL/0 BLOCKED**, control48/48이며 **FIFO23/24**다.
OTHER loaded6건 외에 FIFO Monitor-overrun 조건이 주입 전 Front/Rear662ms slot 누락으로 실패했다.
666.004077ms 검출·666.009677ms 물리 override를 확인했으나 정상 timing 성공은 아니다.
기존41/7·42/6·42/6과 같은 분모/시한을 유지하고 source별로 구분한다. Tracefs/perf 접근 제약으로 kernel 원인은 OPEN이다.
DDS11.0.1 GC source에서 vendor atomic helper의 TSan 계측 제외를 확인했으나 실제 lifetime 안전성/false positive는
확정하지 않았다. Zenoh binary와 Rust 동기화 인식도 미확정이다. 기존 wrapper4 FAIL·SDK 재계측2 FAIL은 OPEN,
M4 NOT CLOSED·M5 미착수·학습자 REVIEW PENDING·전체 system NOT RUN을 유지한다.

2026-10-20 M4 후속은 원본12fc4a5의908/908·41 PASS/7 FAIL을 보존했다. 원본7 FAIL의 명령/설정/slot을 감사하고 공통 release origin과 사전 할당/requested-wake 기록을 수정했다(`603fe24`). 이후 책임·데이터 계약/로컬 transport·reset predicate·disjoint CTest label을 별도 분리했다(`77d411c`). 각 시점 normal/ASan·UBSan912/912, 별도48회는각42 PASS/6 FAIL이다. 원본 FIFO wake 원인 미확정/OTHER 부하6 FAIL은 OPEN이다. 원본→수정35개, 수정→분리36개 logical physical CSV가 byte 동일하다.

후속 owner-wire/global credit/remote Leaf endpoint36개를 더한`d7115ff`는 normal/ASan·UBSan948/948, 분리 전후36개 trace 동일이다. 기존 CAN/P05 payload와 source/parent/expiry를 유지한다. 새36개 TSan PASS, native9개 중8 PASS/1 FAIL(CommandDelivery 보호), 경합 경고0이며 추가1회 trace 진단 PASS는 원본 실패를 대체하지 않는다. Middleware v1 36회는30 PASS/6 FAIL(DDS late reply/reader rejection 관측 누락)을 보존하고, 관측 보완은`5eb1b3b`의 별도 결과로 기록한다. V2 별도36/36 PASS이고, wrapper ASan4/4 PASS·wrapper TSan4 FAIL·완전 DDS SDK 계측 추가2 FAIL을 보존한다. SDK 경고는 OPEN-M4-MWTSAN-01이며 억제/false-positive 확정 없이 보류한다. 두 후보의 실제 process/netns/CLI/조건/원본·공유 CSV는 후속 evidence에 있다. Probe는 echo이고 M5 제어/Actual 배포·복구가 아니다. Release BUILD_TESTING=OFF와 production4개 analyzer/cppcheck를 검사했고 analyzer 오류0이다. 명시적 enum range registry의 동일 반환식5개 branch-clone 경고는 근거와 함께 보존했다.

2026-10-13 문서 정리 시 normal·ASan/UBSan build/unit/vCAN과 DBC 검사를 다시 통과했다.
Local observed timeout은 normal 80.019–81.072 ms, sanitizer 80.053–81.065 ms였다.
차량 timing 보장이나 sanitizer의 대표 성능으로 확대하지 않는다. M1 최종 acceptance/학습자
review는 PENDING이었다. 당시 EV C++ 통신과 두 Zone/runtime/차량 TC는 PLANNED / NOT RUN이었다.
문서 52개의 상대 링크/앵커 459개, 요구사항 32개/TC 29개의 정의·추적성,
YAML 3개의 중복 key/책임 배치와 Python syntax를 검사했다. 활성 경로의 낡은 참조를 정리하고
과거 ADR/부분 시험 이력과 목적이 다른 검증 계층은 보존했다.

2026-10-14 [BMS wire 초안](icd/bms_frame_draft.md)의 DBC·6개 goldens/uint64/CRC/canonical
검사를 추가했다. Normal·ASan/UBSan unit 99개, 기존 C++ demo 14개 교차 검증을 통과했다.
48-byte P05 case는 전체 384개 single-bit corruption/잘못된 DataID를 검사한다.
변경 C++ test에 clang-tidy 14 analyzer/bugprone을 적용해 user-source 진단은 없었다.
이 결과는 EV codec/receiver/Drive gate/모델/transport와 전체 TC-EV의 PASS가 아니다.
문서 54개/상대 링크·앵커 478개, 32개 요구와 29개 TC의 추적성, YAML 3개 및
EV rate/age/100 ms monitor budget의 설계 일관성도 검사했다. Python syntax/whitespace 검사를 통과했다.

같은 날 후속 구현에서 BMS value/frame codec·항목별 receiver를 추가했다. Normal·ASan/UBSan
각각 129개 unit이 PASS다. BMS 28개와 기존 Drive/SocketCAN 파일에 추가한 age/adapter case를
포함한다. 전체 12개 DBC/C++ payload 36개를 교차 검증했다.
변경 C++ source/test 10개에 clang-tidy 14의 analyzer/bugprone을 적용해 user-source 진단 없이
통과했다(third-party/header 진단은 제외). Cppcheck 2.7의 warning/performance/portability는
BMS 3개·공통 수신 상태·Drive receiver·SocketCAN adapter·demo의 source 7개에 적용해 통과했다.
EV의 native 48/64-byte 변환과 수동 clock timeout/parent expiry는 Host 단위 범위다.
이 codec 구현 시점에는 EV TX/RX/wall-time budget, Drive의 torque·limits·permission·로컬 HV
통합 gate, BMS/power 모델과 두 Zone/runtime/전체 TC-EV는 NOT RUN이었다.
공통 수신 상태 변경 후 기존 actuator vCAN은 normal·ASan/UBSan 각각 27 case를 재통과했다.
Local timeout은 normal 80.007–81.081 ms, sanitizer 80.029–81.219 ms였다.
이는 기존 6개 actuator frame 회귀이며 새 EV transport의 검증 결과가 아니다.
Fresh `BUILD_TESTING=OFF` build에서 BMS 포함 라이브러리/demo만 생성하고 receiver 예제를 실행했다.
문서 57개/상대 링크·앵커 508개, 요구사항 32개/TC 29개, YAML 3개 및 Python 3개의 syntax와
whitespace도 검사했다. System TC의 Runtime Result는 모두 NOT RUN을 유지한다.

후속 EV SocketCAN 작업은 기존 TX/RX/support/runner를 확장했다. 6종류 각각의 normal/faults/
silent/flood와 partial limits, cached dependency/physical input, 비critical 관측, parent expiry/
identity·explicit INIT/rejoin, 3-process 원천 보존 relay의 **EV 36개**를 추가했다.
Harness는 승인된 parent 목록을 stdin으로 공급하며 CAN에서 context를 자동 생성하지 않는다.
RX는 cycle당 8개 dispatch 후 poll하며 overflow 관측 시 실패한다. Kernel overflow 주입과
application queue/실제 coordinator·DDS는 남아 있다. Normal·ASan/UBSan 각각 전체 63개
(기존 actuator 27 + EV 36)를 검사하고 전체 unit 129개와 DBC 교차 검증도 재통과했다.
Clang-tidy 14 analyzer/bugprone은 변경 TX/RX 2개와 support header에 적용해 user-source
진단 없이 통과했고 cppcheck 2.7 warning/performance/portability도 통과했다.
EV critical timeout은 normal **80.021–81.045 ms**, sanitizer **80.052–81.036 ms**,
관측 envelope timeout은 normal **300.282–300.984 ms**, sanitizer **300.275–301.069 ms**였다.
Forward relay도 따로 80..100 ms budget을 판정했다. Actuator 회귀는 normal
80.008–81.034 ms, sanitizer 80.001–81.050 ms였다. 고정된 local fixture의 관측값이며
Target/차량 timing 보장이나 sanitizer의 대표 성능으로 확대하지 않는다.
실제 BMS limit/power 모델·Drive actuation gate와 두 Zone/차량 TC는 NOT RUN이다.

2026-10-14 [M1 session/queue 마무리](learning/m1_session_queue.md)는 영속 Epoch 발급과
fixed-capacity FIFO/continuity latch를 구현했다. 기존 unit 129 + session/queue 14 = 143개,
기존 vCAN 63 + application/kernel overflow 24 + durable restart 2 = 89개를 검사한다.
Unit의 동시 8개 process 발급·손상/상실/busy/I/O/소진과 12개 receiver 복구를 확인했다.
VCan kernel case는 실제 SO_RXQ_OVFL >0을 요구한다. 이전 Epoch의 counter 200이 새 세션의
P05 state를 오염시키지 않는지 unit/독립 process 양쪽에서 검사했다.
M1 기술 구현·자동 검사는 수용 항목별 기록하고 학습자 review/wire 채택은 PENDING으로 남긴다.
Actual Front session/DDS 및 물리 response/system TC 결과는 후속이다.
Normal·ASan/UBSan 각각 143개 unit/89개 vCAN이 PASS다. App overflow report의 최초 usable
RX 대비 시간은 normal 23.601–25.059 ms, sanitizer 23.698–25.513 ms였다.
Kernel drop report는 normal 48.986–51.073 ms, sanitizer 49.257–50.936 ms였고 12종류 모두
실제 nonzero drop을 기록했다. Report latency는 물리 loss onset latency가 아니다.
Critical timeout은 normal 80.013–81.071 ms, sanitizer 80.002–81.184 ms,
관측 timeout은 normal 300.030–301.045 ms, sanitizer 300.422–300.788 ms였다.
Clang-tidy 14 analyzer/bugprone은 변경 source/test 11개와 receiver/queue/support header에
적용해 user-source 진단 없이 통과했다. Cppcheck 2.7은 production/fixture source 10개에 적용했다.
59개 Markdown의 상대 링크·앵커 528개, 32개 요구/29개 TC, YAML 3개와 Python 3개의
정합성·syntax/whitespace를 검사했다. 실제 차량/Target 성능이나 전체 TC PASS로 확대하지 않는다.

2026-10-14 [M2 첫 Steering 모델](learning/m2_steering_model.md)은 unit 13개를 추가했다.
Normal·ASan/UBSan 각각 전체 156개 unit을 통과했다. 기존 M1 89개 vCAN 회귀를 모두 통과했고,
model-normal/model-loss 2개를 별도로 실행해 각각 통과했다. 첫 model verifier에서 expiry의
reference를 RX time에서 Command source time으로 수정하고 두 model case를 다시 통과했다.
유효 Command → delay/rate/saturation → 독립 Actual RX, source-expiry hold/latch/late command
거부를 확인했다. Actual validity와 FAIL_SAFE를 분리하며 full vehicle TC는 NOT RUN이다.
Clang-tidy의 변경 source/test 5개와 cppcheck production/fixture 4개를 최종 user-source 진단 없이
통과했다. BUILD_TESTING=OFF의 model library/demo build와 결정론적 demo도 통과했다.
61개 Markdown의 상대 링크/앵커, 요구사항 32개/TC 29개와 YAML/Python 정합성을 확인했다.
모델 설정은 SIL fixture이며 Target timing/실차 calibration은 별도다.

2026-10-14 [M2 첫 Brake 압력 모델](learning/m2_brake_model.md)은 unit 16개와 model vCAN 3개를
추가했다. Normal·ASan/UBSan 각각 전체 **172개 unit / 94개 vCAN**을 통과했다.
가압/감압·delay/saturation·valid-zero release, expiry/continuity/deadline의 protective floor ramp,
이미 높은 압력의 retain·late release 거부·clock/restart를 검사한다.
Maximum delay/300개 목표 변경도 fixed history에 유지되는지 unit에서 확인했다.
Generic model loop/runner를 Steering과 공유하고 Actual source/sequence/causal/state/pressure가
독립 RX에 보존되는지 검사했다. Clang-tidy 14 변경 source/test 5개와 cppcheck 2.7 source 4개는
user-source 진단 없이 통과했다. BUILD_TESTING=OFF library/demo build와 brake-model 실행도 통과했다.
63개 Markdown의 상대 링크/앵커, 32개 요구/29개 TC와 YAML/Python 정합성도 확인했다.
Pressure→wheel torque/차량 감속/ABS/회생 배분과 Target scheduling/full TC는 후속이다.

2026-10-14 [ADR-0021](adr/ADR-0021-central-coordination-and-parallel-zones.md)은 Central의 별도
VCU/allocation/session/feedback bridge와 대등한 두 Zone의 문서·profile 배치를 개정했다.
요구 4개를 v0.5로 기록하고 기존 32개 요구/29개 TC의 owner/interface/fault variant를 갱신했다.
Epoch library를 central/session으로 이동해 normal·ASan/UBSan build와 각 172개 unit을 통과했다.
CPP 발급 동작은 이전 source와 동일함을 확인했다. BUILD_TESTING=OFF build와 독립 production
issuer process의 1→2 발급, 64개 Markdown/상대 링크·앵커/추적성/YAML/Python 검사를 통과했다.
앞선 94개 vCAN 결과는 기존 component/wire 부분 증거다. 실제 새 Central–Zone DDS topology와
vehicle/system TC 결과는 NOT RUN이며 M4/M5 이후 검증한다.

2026-10-15 [첫 Drive torque 응답](learning/m2_drive_model.md)은 ECU adapter와 CAN 독립 물리
모델을 별도 모듈로 구현했다. Unit 20개와 signed normal/positive-loss/negative-loss vCAN 3개를 추가해
normal·ASan/UBSan 각각 전체 **192개 unit / 97개 vCAN**을 통과했다.
Normal delay/rate/양·음 saturation/0 command, source-expiry·continuity·deadline의 zero-target ramp,
late frame/clock/restart, 시간 순서·FIFO/uint64 경계를 검사했다. Actual source/sequence/causal/state와
torque, speed/capability unavailable을 독립 RX에서 확인했다.
Local actuator timeout은 normal 80.002–81.032 ms, sanitizer 80.013–81.052 ms였다.
기존 CAN/P05 계약은 유지하며 BMS/permission/local HV gate, capability/energy와 full vehicle TC는 NOT RUN이다.
실행 로그는 각 build의 `drive-model-unit.txt`, `drive-model-vcan-all.txt`,
`socketcan-results/drive-model-*.log`에 보존한다.
Clang-tidy 14 analyzer/bugprone을 변경 source/test 6개와 관련 header에 적용했다.
단위시험 helper의 혼동 가능한 인자를 구조체로 수정했고 최종 test/물리 모델 재검사에서
user-source 진단이 없었다. Cppcheck 2.7은 production/fixture source 5개를 통과했다.
시간 skip에서 pending goal을 취소하도록 보강한 뒤 양 build의 unit 192개와 model vCAN 8개를
다시 통과했다. BUILD_TESTING=OFF library/demo build와 결정론적 `drive-model` 예제도 통과했다.
67개 Markdown/상대 링크·앵커 631개, 요구사항 32개/TC 29개, YAML 3개/Python 3개의
정합성·syntax/whitespace를 검사했다. 기존 100 ms 검출 상한이나 full TC의 NOT RUN 상태는 유지한다.

2026-10-15 [첫 Battery 물리·관측](learning/m2_battery_model.md)은 unit 30개를 추가했다.
Normal·ASan/UBSan 각각 전체 **222개 unit**을 통과했다. 실제 DC/auxiliary power→chemical energy,
zero/unknown·full/empty·실수 회로해/thermal 해석해, 독립 sensor pair·cache source/batch·explicit reset을 검사했다.
100,000개 교대 power interval에서도 0.00018 J balance tolerance를 만족했다.
Battery fault는 미관측 에너지를 추측하지 않고 current 관측을 unavailable로 만든다.
CAN frame/vCAN case는 추가하지 않았고 앞선 Drive의 97개 증거와 full TC NOT RUN을 유지한다.
실행 로그는 각 build의 `battery-model-unit.txt`, `battery-model-demo.txt`에 보존한다.
Clang-tidy 14 analyzer/bugprone은 model/test/demo 3개와 model header에 적용해 최종 user-source
진단 없이 통과했다. Cppcheck 2.7은 production/demo 2개를 통과했다.
Full에서 한 ULP보다 작은 추가 charge도 capacity 위반으로 보고하는 경계를 보강한 뒤
normal·sanitizer unit 222개를 다시 통과했다. BUILD_TESTING=OFF build와 `battery-model` demo도 통과했다.
69개 Markdown/상대 링크·앵커 654개, 요구사항 32개/TC 29개, YAML 3개/Python 3개의
정합성·syntax/whitespace를 검사했다. 기존 차량 수용 조건과 full TC의 NOT RUN 상태는 유지한다.

2026-10-15 [첫 BMS 한계·보호 판단](learning/m2_bms_controller.md)은 unit 33개를 추가했다.
Normal·ASan/UBSan 각각 전체 **255개 unit**과 기존 CLI의 `bms-control`을 통과했다.
Platform-neutral sensor port를 추출하고 ECU와 plant 의존성을 분리했다. 방향별 SOC/온도/전압
derating·10 W floor, cell 극값/pack mean, hard fault 후보의 즉시 inhibit·개별 acquisition dwell,
release hysteresis·명시적 새 app Epoch/INIT·physical model/SOC 유지, sensor unknown/cache/skew/
age/identity/clock/deadline과 기존 P05/receiver의 valid zero/usable-RX를 검사했다.
Demo는 20 ms 수동 시계로 plant→sensor port→controller→codec→receiver를 실행한다.
새 socket transport/vCAN case는 추가하지 않았고 이전 97개 증거 및 full TC NOT RUN은 유지한다.
실행 로그는 각 build의 `bms-control-unit.txt`, `bms-control-demo.txt`에 보존한다.
Clang-tidy 14 analyzer/bugprone은 controller/model/test 2개/demo의 source 5개와 관련 header에
적용해 최종 user-source 진단 없이 통과했다. Cppcheck 2.7 production/demo 3개도 통과했다.
BUILD_TESTING=OFF build/demo와 문서 71개/상대 링크·앵커 676개, 요구사항 32개/TC 29개,
YAML 3개/Python 3개의 정합성·syntax/whitespace를 검사했다.
실차 calibration·hardware protection·Power lifecycle/Drive gate·SOC estimator의 검증 결과가 아니다.

2026-10-15 [첫 Power lifecycle](learning/m2_power_lifecycle.md)은 Power 37개와 BMS local gate 1개를
추가했다. Normal·ASan/UBSan 각각 전체 **293개 unit**과 기존 CLI의 네 `power-model` scenario를 통과했다.
RC 해석해·지연 event 전후 적분·실제 부하/반환 전류, negative/precharge/positive 실제 sequence,
fresh acquisition dwell·BMS source-age/cache/unknown, current wait/open actual/discharge voltage,
LV·weld/stuck/부분 센서·canonical unknown·trusted parent/expiry/identity/deadline/restart를 검사한다.
초기 테스트의 late Enable 수용 기대를 receiver timeout latch의 원래 계약에 맞춰 수정했다.
종료한 physical OFF와 센서 health FAIL_SAFE도 독립적으로 유지한다.
LocalState와 PowerState를 구분하고 request source/causal과 physical batch/dependency를 보존한다.
`power-unit.txt`, `power-demo-normal.txt`, `power-demo-bms-trip.txt`, `power-demo-weld.txt`,
`power-demo-blocked.txt`는 각 build에 보존한다. Demo의 actual current/contactor/RC 응답은
PowerModel에서 오고 SOC/온도/400 V는 명시적 fixture다. Battery SOC 에너지 통합은 미검증이다.
Clang-tidy 14 analyzer/bugprone을 production 3개/test 2개/demo source 6개와 관련 header에 적용해
최종 user-source 진단 없이 통과했다. Cppcheck 2.7 production/demo 4개도 통과했다.
BUILD_TESTING=OFF build/네 demo와 문서 73개/상대 링크·앵커 700개, 요구사항 32개/TC 29개,
YAML 3개/Python 3개의 정합성·syntax/whitespace를 검사했다.
새 wire/transport/vCAN case는 없고 이전 97개 증거 및 full vehicle TC NOT RUN을 유지한다.
실차 calibration/부품 정격/hardware 차단 안전성·Drive 실제 gate·독립 OS task 결과가 아니다.

2026-10-15 [Drive local gate/capability](learning/m2_drive_gate.md)는 gate 37개와 공통 TorqueResponse
추가 4개를 더했다. Normal·ASan/UBSan 각각 전체 **334개 unit PASS**다. 원천 limits의 명시적 relay,
trusted parent/permission·local HV/speed·known zero/unknown·startup 순서·directional power/low-speed
envelope·pending 목표 축소/회복·finite actual residual·loss/clock/deadline/새 Epoch를 검사했다.
구동은 정지 copper loss와 shared fixed reserve를 포함한 power upper estimate, 회생은 반환 power의
보수적 mechanical upper bound를 사용한다. 실제 효율 map/전류 제어/배터리 충전 적분은 시험하지 않았다.
기존 CLI의 `drive-gated` 여섯 scenario를 normal·sanitizer·BUILD_TESTING=OFF build에서 실행했다.
각 build의 `drive-gate-unit.txt`, `drive-gated-*.txt`와 production `drive-gate-build.txt`에 결과를 보존한다.
Clang-tidy 14 analyzer/bugprone은 controller/physics/test 2개/demo source 5개와 관련 header에 적용하고,
최종 변경 controller를 다시 검사했다. Cppcheck 2.7 production/demo 3개도 user-source 진단 없이 통과했다.
Signed zero 정규화의 redundant-assignment 진단은 중복 조건 대입을 없애 해결했다.
문서 75개/상대 링크·앵커 727개, 요구사항 32개/TC 29개와 NOT RUN 추적성, YAML 3개/Python 3개의
정합성·syntax/whitespace도 검사했다.
기존 isolated Drive model vCAN 3개는 normal·sanitizer 각각 재실행해 PASS했다. 처음 host namespace의
`ip link add`는 권한 오류였으나 기존 문서의 `unshare --user --map-root-user --net`로 해결했다.
`drive-gate-vcan-regression.txt`와 각 build의 `socketcan-results`에 결과를 보존한다.
새 EV gate transport case는 없으며 이전 vCAN 97개 전체를 재사용한 새 PASS로 표시하지 않는다.
Actual DC/Battery SOC coupling, 공유 부하/충전 headroom·잔여 회생 budget, 실제 Central/Zone runtime,
차량 motion/마찰 보충·실차 calibration·Target OS timing과 전체 TC-REG/EV/ZON은 미검증이다.

2026-10-15 [첫 Drive/Battery energy 연결](learning/m2_drive_energy.md)은 새 28개 시험으로 normal·ASan/UBSan
각각 전체 **362개 unit PASS**다. 기계적 power→motor conversion/copper/idle→실제 DC→auxiliary·Battery
chemical energy/저항 heat를 구분한다. Analytic 구동/회생·작은 회생의 순방전·standstill, actual delay,
원천 identity/cache/age/skew·missing/역행/gap, full/empty capacity fault·no clipping과 20,000 interval 장부를 검사했다.
초기 시험의 skew 기대는 실제 sequence rollback과 분리하고, BMS input이 매 10 ms 새 값이라는 기대는
원래 20 ms multirate 계약에 맞춰 수정했다. Timestamp를 정규화해 통과시키지 않았다.
Fixture의 gate upper power estimate/공유 reserve·SOC guard band/finite reaction budget을 교차 확인했고,
20→10 ms ZOH refinement와 실제 Battery 관측→BMS→명시적 relay/독립 trusted grant→Drive→P05 receiver loop도 검사했다.
`drive-energy-unit.txt`, `drive-energy-{normal,charge-zero,near-full,auxiliary}.txt`에 결과를 보존한다.
Normal·sanitizer·BUILD_TESTING=OFF에서 네 demo와 SOC 증감·잔여 actual 반환·charge-zero·auxiliary·장부를 확인했다.
Clang-tidy 14 analyzer/bugprone을 model/test/demo source 3개와 관련 header에 적용했다.
Cppcheck 2.7 model/demo 2개도 검사했으며 최종 user-source 진단은 없다.
에너지 모델의 validation loop는 std::find_if로 정리했다. Compiler warnings-as-errors·production build와
문서 77개/상대 링크·앵커 754개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace를 검사했다.
Wire/transport/기존 torque physics 변경이 없어 새 vCAN 실행은 없고 이전 97개 이력·gate 단계의 3개 재검사를 유지한다.
현재 coupling은 이상적 energized HV와 외부 fixed-speed의 component다. Dynamic RC/접점·capacitor/path
에너지·shutdown 부하, vehicle motion·마찰 보충·실차 calibration/정확도·Target timing과 full TC는 미검증이다.

2026-10-16 [RC/접점·Battery energy 연결](learning/m2_ev_power_circuit.md)은 새 29개(circuit 24개·Battery
integrated-flow 5개)를 추가해 normal·ASan/UBSan 각각 전체 **391개 unit PASS**다.
Actual motor DC·Rint/source·main/precharge/bleed·capacitor를 연결하고 구간 current/current-square 적분으로
단일 Battery chemical energy를 갱신했다. RC analytic/event/end-point·50→25 µs refinement,
isolated capacitor regen/discharge·10,000 alternating interval 장부·power/capacity domain과 atomic commit,
identity/source/dependency/cache/unknown·epoch/clock·mean-square heat와 mode 변경 거부를 검사했다.
기존 CLI `ev-power`의 normal/weld/current-unknown/aux-blocked 네 loop를 normal·sanitizer·production에서 실행했다.
PowerStatus·DriveActual/P05 receiver, 실제 READY·구동/회생 SOC 증감·정상 OFF와 고장 blocked·접점·residual·energy를
독립 로그 assertion으로 확인했다. 각 build의 `ev-circuit-unit.txt`, `ev-circuit-{scenario}.txt`에 결과를 보존한다.
기존 Power 4개·Drive energy 4개·Drive gate 6개 demo도 세 build에서 회귀 실행했다.
로그는 `ev-circuit-regression-{family}-{scenario}.txt`이며 production은 BUILD_TESTING=OFF다.
Clang-tidy 14 analyzer/bugprone을 production 4개/test 2개/demo source 7개와 관련 header에 적용하고
변경 뒤 해당 source를 재검사했다. Cppcheck 2.7 production/demo 5개도 최종 user-source 진단 없이 통과했다.
Earliest contact event 선택은 std::accumulate로 정리했고 기존 362개 회귀도 통과했다.
Combined fixture의 opening current 0.5 A·reserve 500 W와 standalone default 5 A·200 W를 구분한다.
OFF 후 auxiliary 소비와 Drive PermissionInhibit latch는 별도다. Thermal은 interval 평균 heat 근사이며
50 µs solver step을 ECU task/RTOS 보장으로 해석하지 않는다.
문서 79개/상대 링크·앵커 781개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace를 검사했다.
새 wire/transport/vCAN case는 없으며 기존 vCAN 97개 이력과 gate 단계의 3개 재검사를 유지한다.
Vehicle motion/마찰 배분·실제 Central/Zone·LV sleep·정밀 부품 calibration·Target timing과 full TC는 미검증이다.

2026-10-16 [M2 수용 검토](m2_acceptance_review.md)는 기존 working tree의 주기·입출력·감시,
fixture parameter, fault/session과 요구사항의 component 증거를 대조했다.
Normal·ASan/UBSan 각각 전체 unit **391개**, model vCAN **8개**(Steering 2/Brake 3/isolated Drive 3)를 재실행해 통과했다.
기존 actuator/Battery/BMS demo 5개와 combined EV scenario 4개도 각 build에서 실행했다.
Combined 종료 phase/fault/접점·current unknown·actual zero·energy 잔차를 독립 assertion으로 확인했다.
각 build의 `m2-review/`에 build/unit/JUnit/inventory·demo·vCAN 로그를 보존하고,
normal build의 `m2-review/evidence.json`에 base commit과 미커밋 runtime source/DBC/profile hash를 기록했다.
Runtime 코드·시험 모듈·의존성은 추가하지 않았다. 기존 vCAN all 97개 이력은 유지하며 이번 재실행 범위는 8개다.
문서 80개/상대 링크·앵커 817개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace를 검사했다.
수용 검토에서 Steering jam/tracking·Brake stuck/slow-response detector를 **M2 미완료 OPEN-M2-01/02**로 기록했다.
Tick gap guard는 멈춘 task의 독립 검출이 아니며 scheduler/watchdog·trace·deadline 측정은 M3에 남긴다.
M2는 IN PROGRESS, M1 wire/학습자 설명·직접 재현은 PENDING, system Result는 NOT RUN을 유지한다.

2026-10-16 [Steering response monitor](learning/m2_steering_fault_monitor.md)는 물리 9개·monitor 21개·기존 adapter 9개,
새 39개를 더해 normal·ASan/UBSan 각각 전체 **430개 unit PASS**다.
물리 delay/rate/jam과 angle acquisition을 별도 모듈로 분리하고 local monitor가 issued bounded target 이력과
독립 sensor만으로 정상 rate band·residual/dwell을 검사하도록 했다. 기존 Steering 13개도 회귀 통과했다.
양방향 stall, 정상 rate band 양끝·지연/방향 전환/포화, transient pending 해제, fresh-source confirmation,
unknown/cache/identity/clock·bounded history, valid Actual과 sensor fallback 금지·새 epoch를 시험했다.
기존 CLI `steering-model`의 normal/jam/slow/sensor-hold/sensor-invalid/transient 6개와
Brake/isolated Drive/combined EV normal 회귀 3개를 normal·sanitizer·production에서 실행했다.
로그 assertion으로 jam 130→190 ms, slow 140→200 ms의 pending→검출, sensor unavailable와 transient 회복을 확인했다.
Production BUILD_TESTING=OFF build도 통과했다. 각 build의 `steering-monitor-build.txt`, `steering-monitor-<scenario>.txt`,
`steering-monitor-regression-*.txt`에 결과를 보존하며 unit 로그는 normal/sanitizer의 `steering-monitor-unit.txt`다.
기존 model vCAN 8개도 normal·sanitizer에서 각각 재실행해 통과했고 로그는 `steering-monitor-vcan.txt`다.
Jam을 넣은 새 SocketCAN case는 없으며 기존 all 97개 이력과 이번 8개 회귀를 구분한다.
Clang-tidy 14 analyzer/bugprone을 production 3개·test 3개·demo 1개와 관련 header에 적용하고,
cppcheck 2.7 production/demo 4개도 user-source 진단 없이 통과했다.
문서 82개/상대 링크·앵커 846개·요구 32개/TC 29개 NOT RUN·YAML 3개/Python 3개·whitespace도 검사했다.
Threshold/rate/dwell은 fixture이며 기계 jam의 고유 원인 진단, 실차 조향 안전성이나 100 ms tracking 검출 보장이 아니다.
M2 OPEN-M2-01의 component 증거를 추가했고 Brake OPEN-M2-02·학습자 수용, M3 task/watchdog/trace는 남긴다.

2026-10-16 [Brake pressure response monitor](learning/m2_brake_fault_monitor.md)는 plant 10개·monitor 16개·기존 adapter 14개,
새 40개를 더해 normal·ASan/UBSan 각각 전체 **470개 unit PASS**다. 기존 Brake adapter 16개도 유지했다.
독립 pressure sensor/물리 응답 경계와 별도 rise/fall 정상 band·residual/source-time dwell을 구현했다.
가압/감압 stuck·slow, 정상 rate 양끝·지연/포화/방향 전환, transient pending 해제, unknown/cache·identity/time,
bounded history, 새 epoch·persistent stuck과 plausible sensor freeze를 시험했다.
보호 floor 요청 뒤에도 물리 stuck을 적용하고 요청/fresh 관측/실제 제동 성공을 구분한다.
관측 gap은 fault를 latch하지만 개별 유효한 새 압력은 FAIL_SAFE 상태와 함께 보고할 수 있다.

기존 CLI `brake-model`의 normal/stuck-rise/slow-rise/stuck-release/slow-release/sensor-hold/sensor-invalid/transient 8개와
Steering normal/jam·isolated Drive·combined EV normal 회귀 4개를 normal·sanitizer·production에서 실행했다.
별도 로그 assertion으로 rise stuck 120→180 ms, slow rise 130→190 ms, release stuck/slow 370→430 ms의 pending→검출,
보호 중 stuck 잔존·floor unknown·transient 해제를 확인했다. Production BUILD_TESTING=OFF build도 통과했다.
각 build의 `brake-monitor-build.txt`, `brake-monitor-<scenario>.txt`, `brake-monitor-regression-*.txt`에 보존하며,
normal/sanitizer의 `brake-monitor-unit.txt`, `brake-monitor-unit.xml`에 전체 unit 결과를 둔다.
기존 model vCAN 8개도 normal·sanitizer에서 각각 재실행했고 `brake-monitor-vcan.txt`와 `socketcan-results`에 결과를 둔다.
이는 새 pressure fault network case가 아닌 기존 정상/통신 상실 회귀다. All 97개는 앞선 전체 실행 이력이다.
Clang-tidy 14 analyzer/bugprone은 production 3개·test 3개·demo 1개, cppcheck 2.7은 production/demo 4개에 적용했다.
문서·추적성/YAML·Python/whitespace 검사와 실행 source/DBC/profile SHA-256은
`build/m1-angle/brake-monitor-doc-check.txt`, `brake-monitor-evidence.json`에 보존한다.
M2 OPEN-M2-01/02의 component 구현 공백은 해소했고 직접 재현·학습자 수용은 PENDING이다.
실차 calibration/고유 기계 원인 진단·vehicle stop·독립 task/watchdog는 검증한 결과가 아니다.
32개 요구/29개 system TC 전체 Result는 NOT RUN이며 M3 task/trace·측정 설계가 다음 구현이다.

2026-10-16 예제 구조 정리에서 단일 `actuator_demo` 실행 파일을 유지하고 명령 분기/도움말과
`tools/demo/`의 Steering·Brake·Drive·EV 구현을 분리했다. Normal·ASan/UBSan·BUILD_TESTING=OFF build에서
각각 **90개 CLI 입력의 stdout/stderr/exit code가 이전 binary와 동일**했다. Clang-tidy analyzer/bugprone을
변경된 source 5개에 적용해 통과했다. 기존 runtime library/시험 case는 이 단계에서 변경하지 않았다.
비교 binary·명령 목록/스크립트·build/static 로그는 `build/m1-angle/structure-review/`와 각 build의
`structure-demo-build.txt`에 둔다. 문서 링크/추적성/YAML/Python/whitespace 검사도 통과했다.

2026-10-16 후속 [ECU/SIL 실행 경계](learning/m2_execution_boundaries.md) 정리에서 네 actuator/Drive core의
physical response 소유/호출을 제거했다. Core `prepare/complete`와 typed actuation/sensor port,
`simulation/`의 명시적 SIL runner로 분리했다. Model injection/truth는 simulation에만 남긴다.
신뢰된 app/model epoch·enable boundary는 ActuatorSession으로 묶고 wire에서 자동 학습하지 않는다.

새 **21개** = core-only 경계 18개 + 기존 actuator 파일의 독립 물리 진행 3개다.
Normal·ASan/UBSan 각각 전체 **491개 unit PASS**, production BUILD_TESTING=OFF build를 통과했다.
Core 경계 executable의 compile include/link 목록에 simulation 경로·plant library가 없음을 확인했다.
ECU 미호출 중 외부 물리 진행·복귀 시 무소급 보호, sensor unknown/identity/source·Actual fallback 금지,
job phase/clock·중복 완료와 gated Drive의 실제 torque port를 확인했다.
Drive torque의 유효 scalar는 같은 job end의 새 acquisition만 보고하며 cached/delayed는 unavailable,
missing/잘못된 identity·time·range/30 ms 초과 age는 TorqueFeedbackUnavailable로 latch한다.
Steering/Brake의 지연된 새 acquisition은 원래 source time을 보존한다.

Normal·sanitizer·production 각각 **90개 CLI 입력**의 stdout/stderr/exit code를 구조 변경 전 binary와 비교해 일치했다.
기존 model vCAN **8개**(Steering 2/Brake 3/isolated Drive 3)도 normal·sanitizer에서 각각 회귀 검사했다.
이는 새 port fault의 network case나 독립 task 정지 감시 시험이 아니다. 기존 all 97개 이력을 유지한다.
Clang-tidy 14 analyzer/bugprone은 변경 C++ source 20개, cppcheck 2.7은 production/demo 13개에 적용했다.
Normal 상세 로그·CLI 비교 목록/스크립트·core-only compile/link는 `build/m1-angle/structure-review/`에 둔다.
최종 build/unit/XML은 normal·sanitizer의 `structure-final-*`, production의 `structure-final-build.txt`,
vCAN은 각 build의 `structure-final-vcan.txt`와 `socketcan-results`에 둔다.
실행 source/DBC/profile·문서 SHA-256과 로그 목록은 `build/m1-angle/structure-review/evidence.json`에 묶는다.
문서 링크/앵커·32개 요구/29개 TC NOT RUN·YAML/Python/whitespace도 검사했다.
M1/M2 학습자 수용은 PENDING이다. 실행 경계를 분리했으며 실제 thread/task/watchdog·RT 계측은 M3에 남는다.

같은 날 후속 문서 대조에서 M2 학습 흐름·수용 검토 표를 현재 ECU phase/SIL API에 맞추고,
Classic ADR의 과거 대응표와 M1 수동 검사 명령을 당시 이력으로 구분했다.
현재 demo 파일 배치·검사 진입점과 Brake 보호 요청/물리 응답의 책임도 정리했다.
문서 87개/상대 링크·앵커 953개, 요구 32개/TC 29개 NOT RUN, YAML 3개/Python 3개와 whitespace 검사는 PASS다.
이 후속은 문서만 변경했으며 C++ 시험을 다시 실행한 기록은 아니다.

2026-10-16 [M3 첫 Steering 주기 실행](learning/m3_steering_timing.md)은 absolute schedule·독립 completion monitor와
SPSC latest snapshot을 구현하고 ECU/monitor/plant owner를 분리했다. 새 unit **14개**를 더해
normal·ASan/UBSan 각각 전체 **505개 PASS**, Python 통계/분모·unavailable 시각 검사 **5개 PASS**다.
Normal/최소 계측/15 ms busy overrun/120 ms stall을 normal·sanitizer에서 각각 3회(**12 runs씩**),
BUILD_TESTING=OFF build에서 1회(**4 runs**) 실행했다. 모든 run의 예정 job은 120개이고 warm-up 제외는 0이다.
이번 최종 계측 실행은 세 build를 순서대로 수행했다. Host의 다른 부하·DVFS·cooling은 통제하지 않았다.

Normal은 모두 120개 완료/miss 0이었다. Overrun은 실행 119개·skip 1개·miss 2개,
stall은 실행 109개·skip 11개·miss 12개였으며 누락 job을 분모에서 빼지 않았다.
Normal build의 첫 검출은 deadline 뒤 **1.073–1.242 ms**, 독립 Hold 적용은 검출 뒤 **1.999–2.006 ms**였다.
둘 모두 ECU의 injected sleep/busy work 종료 전이었다. Late injected feedback은 발행하지 않았고
새 sensor acquisition·Command/Actual causal identity와 output issued/applied time을 확인했다.
복귀 뒤 timely FAIL_SAFE 진단 발행은 유지했다. Sensor-gap latch의 unavailable은 측정으로 집계하지 않으며
진단 생성 시각과 유효 각도의 acquisition source를 구분하는 회귀 검사를 더했다.
이 값은 default SCHED_OTHER의 local 관측이며 100 ms CAN loss·차량 반응/Target 보장으로 확대하지 않는다.

Normal/full의 360개 job elapsed는 Mean **0.015845 ms**, P95 **0.015552 ms**, P99 **0.067195 ms**, Max **0.072855 ms**였다.
Minimal 계측과의 평균 차이는 **+0.000231 ms**였다. 별도 실행의 scheduler/cache 잡음도 포함하므로
이 차이를 계측 비용의 상한으로 보거나 deadline에서 빼지 않는다. ECU phase와 외부 physics 비용은 별도 지표다.
Sanitizer 수치는 기능/메모리 검사이며 대표 성능 증거로 사용하지 않는다.

변경 C++ source/test 4개에 clang-tidy 14 analyzer/bugprone, production/demo 3개에 cppcheck 2.7을 적용했다.
최종 trace field 변경 뒤 해당 runtime source를 다시 검사했다. User-source 진단 없이 통과했으며 기존 header/NOLINT filter는 유지했다.
TSan은 PIE/non-PIE 두 시작 시도 모두 Host의 `unexpected memory mapping`으로 실행되지 않았다. Race 검사는 NOT RUN이다.
세 slot의 동시 payload 무결성 stress test와 ASan/UBSan 결과를 TSan PASS로 대신하지 않는다.

각 build의 `m3-result/`에 CSV/run 환경·설정·source/profile/binary hash·summary/artifact manifest를 보존한다.
Normal·sanitizer의 `m3-final-unit.txt/xml`, Python `m3-final-python.txt`, 각 build의 `m3-result.txt`와
`m3-final-*` build/static 로그, normal의 `m3-static-clang.txt`·`m3-final-clang.txt`·`m3-final-cppcheck.txt`에 적용 범위를 남긴다.
최종 소스·문서·로그 연결은 `build/m1-angle/m3-evidence.json`에 묶는다. 이번에 CAN wire/receiver/DBC는 변경하지 않았고
vCAN 재실행은 하지 않았다. 기존 M2 model 8개·전체 97개는 앞선 실행 이력이다.
이 첫 실행 시점 다른 ECU/통신 감시는 후속이었으며 아래 확장에서 검사했다. M3는 IN PROGRESS이고 32개 요구/29개 전체 system TC는 NOT RUN이다.

2026-10-16 후속 [M3 다중 주기·실제 CAN 감시](learning/m3_multirate_runtime.md)는 Brake/Drive/Power 10 ms·BMS 20 ms와
SocketCAN RX 2 ms를 별도 thread로 실행했다. 유효 RX monitor 7개·trusted issuer history 4개 unit을 추가해
normal·ASan/UBSan 각각 전체 **516개 PASS**, 리포터의 원천 참조/80..100 ms 경계·clock 검사 3개를 더해 Python **8개 PASS**다.
BUILD_TESTING=OFF build도 통과했다. 기존 Core·wire/receiver·DBC 계약은 변경하지 않았다.

정상/full·정상/minimal, Brake/Drive/BMS/Power/RX 각각의 120 ms stall과 지속 CRC 손상의 8조건을 실행했다.
최종 소스에서 normal·sanitizer 각각 2회(**16 runs씩**), production 1회(**8 runs**)로 총 **40 runs PASS**다.
공통 Linux helper 추출과 snapshot/보호 flag 취득→clock read 순서 수정 뒤 기존 Steering 4조건도
normal·sanitizer 각각 1회(**8 runs 합계**) 회귀했다. 빌드/정적 분석을 끝낸 뒤 계측을 세 build에서 순서대로 실행했으며
warm-up 제외는 0이다. Host 다른 부하·DVFS/cooling은 통제하지 않았다.

Normal의 task miss/skip은 모두 0이었다. 아래는 normal build의 full 계측 2회 job elapsed(ms)이며,
ECU prepare/complete 또는 tick 비용과 외부 물리 계산은 별도 trace 지표다. 서로 다른 주기의 sample을 합치지 않는다.

| Task | Samples | Mean | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| Brake | 480 | 0.029995 | 0.091016 | 0.096215 | 0.101209 |
| Drive | 480 | 0.071357 | 0.184090 | 0.198146 | 0.201208 |
| BMS | 240 | 0.010297 | 0.023323 | 0.025128 | 0.038002 |
| Power | 480 | 0.061046 | 0.100879 | 0.108182 | 0.114536 |
| RX | 2400 | 0.053212 | 0.148148 | 0.154004 | 0.171159 |

Full/minimal 평균 차이는 task에 따라 음수도 나왔다. 별도 실행의 scheduling/cache 잡음을 포함하므로 계측 비용의 상한으로
해석하거나 deadline에서 빼지 않는다. 자세한 역할별 비교는 `summary.json`의 `trace_overhead_comparison.by_task`에 둔다.
Sanitizer 수치는 기능/메모리 검증에만 사용한다.

Normal build의 stall에서 Brake/Drive/Power는 각각 miss 12·skip 11, BMS miss 6·skip 5, RX miss 60·skip 59였다.
누락 job을 분모에 남겼고 다른 task는 miss 0이었다. 최초 검출은 해당 deadline 뒤 **1.055–1.294 ms**,
독립 보호 적용은 검출 뒤 **1.820–2.022 ms**였으며 모두 stalled job 복귀 전이었다.
초기 개발 검사에서 보호가 검출보다 수백 ns 먼저 적용된 것으로 찍힌 run은 FAIL로 보존했다.
새 snapshot/flag를 취득한 뒤 적용 clock을 읽도록 수정해 소급 적용을 막았으며 최종 suite는 그 순서를 검사한다.

마지막 valid application RX→loss 검출은 normal **80.002–81.996 ms**, sanitizer **80.005–82.019 ms**,
production **80.010–81.993 ms**였다. CRC 손상 packet이 계속 들어와도 valid age는 갱신하지 않았다.
유한 torque 잔여 응답·Brake increase-only floor와 Power 정지 중 접점 유지/복귀 후 measured-current 종료를 검사했다.
정상 precharge/READY·BMS fresh release dwell→gated Drive와 실제 SOC 감소/회로 energy 잔차도 확인했다.
이는 5개 입력 stream의 local Host/vCAN 증거이며 실제 CAN arbitration·Zone/Central·Target/차량 안전 정지 증거가 아니다.
비동기 Drive torque는 원천 acquisition을 보존해 현 wire에서 unavailable이다. 실제 torque는 physical trace에 있고
Actual CAN TX→독립 feedback RX는 sampling/timestamp 계약 검토 뒤 별도로 검사해야 한다.

Clang-tidy 14 analyzer/bugprone은 변경 runtime·demo·test C++ 5개, cppcheck 2.7은 production/demo 3개에 적용해 통과했다.
기존 user-source/header/NOLINT filter 범위를 유지했다. TSan은 앞서 기록한 Host 시작 오류 때문에 여전히 **NOT RUN**이다.
각 build의 `m3-multi-recorded/`에 최종 40 runs의 CSV·run/environment·source/profile/binary hash·summary/artifact manifest를 보존한다.
보고서 환경 설명의 모델/deadline을 family별로 수정해 재기록했으며 앞선 `m3-multi-final/` 40 runs도 보존한다.
Steering 회귀는 normal·sanitizer의 `m3-steering-recorded/`, unit은 `m3-multi-unit.txt/xml`, Python은 normal의
`m3-multi-python.txt`, build는 각 build의 `m3-multi-final-build.txt`에 기록했다.
정적 분석은 normal의 `m3-multi-final-clang.txt`·`m3-multi-cppcheck.txt`, 최종 증거 연결은
`build/m1-angle/m3-multirate-evidence.json`이다. 이전 실패/검토 로그는 별도 directory에 유지한다.
Markdown 91개·상대 링크/앵커 1015개, 요구 32개/TC 29개, YAML 3개·Python 5개 syntax/정합성을 검사했다.
기존 M1/M2 97개 vCAN은 이 40 runs와 별도 이력이다.
이 단계에서 후속이던 고정 부하·CPU 배치 비교는 아래에 기록한다. Owner별 우선순위·Drive 관측 계약·M3 수용과 Target/E2E는 후속이다.
전체 32개 요구/29개 system TC는 NOT RUN이며 M1/M2 학습자 수용 기록은 PENDING이다.

2026-10-16 [고정 부하·CPU 배치 비교](learning/m3_cpu_placement.md)는 기존 timing runner와 runtime의 owner별 affinity 기록을 확장했다.
CPU 선택/조건 순서·all-owner mask·busy CPU 경계·run 사이 interval·실패 통계 보존의 Python 8개를 추가해 **16개 PASS**다.
Normal·ASan/UBSan 각각 기존 C++ **516개 PASS**, production BUILD_TESTING=OFF build도 PASS다.
Clang-tidy 14 analyzer/bugprone은 runtime C++ 2개와 `simulation/runtime` header filter에 적용했고,
cppcheck 2.7 warning/performance/portability는 기존 production/demo 3개 compile entry에 적용해 user-source 진단 없이 통과했다.
TSan은 앞선 Host 시작 오류 때문에 여전히 NOT RUN이다.

모든 runtime owner를 CPU 0에 고정하고 부하 없음/busy worker CPU 0/busy worker CPU 1을 비교했다.
현재 allowed 0–15와 topology(package 0/core 0 및 1, sibling 0·8 및 1·9)를 기록했다. 별도 physical core가 보이지만 resource reservation은 아니다.
부하는 10 ms마다 7 ms wall busy window를 요청하고 실제 busy thread CPU와 worker loop process CPU를 별도 측정한다.
SCHED_OTHER·상속 nice를 유지했다. Layout 순서를 회전하고 full/minimal 순서도 바꿔 normal·production 각각 3회(**18 runs씩**),
sanitizer 1회(**6 runs**)로 최종 **42 runs**를 순서대로 실행했다. Warm-up 제외는 0이며 빌드/정적 분석은 계측 전에 끝냈다.

배치·부하 수명/CPU 측정은 **42/42 PASS**였고 worker 강제 종료·누락 cycle은 없었다.
기존 ECU normal 계약은 **28 PASS / 14 FAIL**이다. Baseline·separate는 모두 통과했고 shared는 모두 실패했다.
Normal·production shared RX는 각각 **48개 miss/skip**, sanitizer는 **18개 miss/skip**이었다. 다른 runnable의 miss는 0이었다.
독립 monitor가 RX miss를 latch해 Drive가 처음 활성화되기 전에 zero 보호로 들어갔다.
따라서 이 shared 배치의 정상 구동·timing 계약은 충족하지 못했다. 실행 성공/데이터 수집을 ECU 계약 PASS로 대신하지 않았다.

아래는 normal build의 layout/trace별 RX individual sample 통계다. 각 조건의 예정 job은 3600개이며 miss는 모두 skip이었다.
Response time은 실제 실행한 job의 release→end이며 skipped job에 가짜 duration을 부여하지 않는다.

| Layout / trace | Executed / eligible | Miss / skip | Response P99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- |
| baseline / full | 3600 / 3600 | 0 / 0 | 0.337464 | 0.404273 |
| baseline / minimal | 3600 / 3600 | 0 / 0 | 0.319541 | 0.373310 |
| shared / full | 3577 / 3600 | 23 / 23 | 0.760680 | 1.535098 |
| shared / minimal | 3575 / 3600 | 25 / 25 | 0.881875 | 1.889200 |
| separate / full | 3600 / 3600 | 0 / 0 | 0.339223 | 0.372659 |
| separate / minimal | 3600 / 3600 | 0 / 0 | 0.189907 | 0.521037 |

P99/Max가 deadline 3 ms보다 작아도 skip이 있는 조건은 실패다. 이 표의 Max는 WCET bound가 아니다.
Normal build의 measurement busy CPU 하한/상한 관측 범위는 **66.51–69.46%**, bookkeeping을 포함한 worker loop CPU 비율은
**67.47–69.40%**였다. 요청 70%를 실측 CPU 사용률로 대체하지 않는다. Runtime window 경계의 partial cycle CPU는 비례 추정하지 않았다.
실패 run도 schedule/interval이 유효해 모든 job을 통계에 남겼고 통계에서 제외한 run은 0이었다.
Full/minimal 차이는 layout별로만 비교하며 fault 뒤 코드 경로·scheduler/cache 잡음도 포함해 계측 비용 상한으로 쓰지 않는다.
Sanitizer 수치는 기능/수명 검증이며 대표 성능 비교에 쓰지 않는다. Host 다른 process·interrupt·DVFS/cooling은 통제하지 않았다.

기존 fault matrix 회귀는 normal·sanitizer 각각 multirate 8 + Steering 4 = **12 runs씩 PASS**다.
최종 CPU campaign은 각 build의 `m3-placement-result/`에 CSV·run/environment·worker cycle·summary/artifact SHA를 남긴다.
예비 `build/m1-angle/m3-placement-probe/`는 6 runs 중 shared/minimal 1건 FAIL을 포함해 별도로 보존한다.
회귀는 normal·sanitizer의 `m3-placement-multi-regression/`·`m3-placement-steering-regression/`이다.
Unit은 `m3-placement-unit.txt/xml`, build는 `m3-placement-build.txt`, Python은 normal의 `m3-placement-python.txt`,
정적 분석은 normal의 `m3-placement-clang.txt`·`m3-placement-cppcheck.txt`에 기록한다.
Source/profile/binary/artifact와 최종 문서·검사 로그 연결은 `build/m1-angle/m3-placement-evidence.json`에 둔다.
Drive 비동기 torque CAN 보고 계약과 RX/monitor/plant budget·owner별 배치/우선순위를 검토해야 한다.
기존 deadline을 완화하지 않았으며 M3는 IN PROGRESS다. 전체 32개 요구/29개 system TC는 NOT RUN이다.

2026-10-18 [비동기 Drive Actual CAN 연결](learning/m3_drive_feedback.md)은 기존 header SourceTimeNs의 torque 취득 의미를 사용했다.
Sender는 새 유효 sample의 원래 취득 시각을 보존하고 cached torque는 unavailable 진단으로 보고한다.
Receiver의 보조 source를 torque 시각과 묶던 조건을 session/now·각 age/cursor로 개정했다.
CAN schema 2/ID·length/P05 DataID·CRC coverage와 golden payload는 유지하고 DBC 설명/ICD·ADR을 함께 갱신했다.
기존 receiver는 더 늦은 보조 시각을 Invalid로 제거할 수 있으므로 양쪽 정책 검토가 필요하다.

Core/receiver의 지연된 새 torque·cache 미갱신·독립 보조/torque age·같은 sample 재발행/future/regression 5개를 더해
normal·ASan/UBSan 각각 C++ **521개 PASS**다. Trace의 원래 bytes/source·generation·uint64 parse·replay count 검사 5개를 더해
Python **21개 PASS**다. 새 valid TorqueMeasurement를 값/시각과 함께 반환하며 초기화는 기존 typed ActuatorSession을 사용한다.
BUILD_TESTING=OFF build도 통과했다. Clang-tidy 14 analyzer/bugprone은 변경 C++ 7개와 runtime/Drive header filter에,
cppcheck 2.7 warning/performance/portability는 production/demo 5개 compile entry에 적용해 통과했다.
확대한 header filter에서 초기화 인자 순서 진단을 확인해 typed Session으로 정리했다. 최초 진단 로그도 보존한다.
TSan은 앞서 기록한 Host 시작 오류 때문에 여전히 NOT RUN이다.

Actual을 실제 socket으로 송신하고 기존 RX worker의 0x282 socket/별도 DriveReceiver로 검증했다.
독립 monitor에 여섯 번째 valid RX를 추가했으며 Actual replay에서도 다른 5개 입력은 계속 정상 수용된다.
RX budget 8·ECU period/deadline은 유지하고 마지막 response를 수신하는 20 ms drain tail(1210 RX jobs)을 명시했다.
Trace schema 3과 CAN schema 2는 별개다. Minimal trace도 동일 송수신·receiver 경로와 count를 실행한다.

최종 9조건(normal full/minimal·worker stall 5·CRC 손상·Actual replay)을 normal·sanitizer 각각 2회(**18 runs씩**),
production 1회(**9 runs**)로 실행해 **45 runs PASS**다. 기존 Steering 4조건도 normal·sanitizer 각각 1회(**8 runs 합계**) 회귀했다.
빌드/정적 분석 뒤 세 build의 계측을 순서대로 실행했으며 warm-up 제외는 0이다. Host 다른 부하·DVFS/cooling은 통제하지 않았다.
정상 run마다 **240 TX = 240 RX = 240 Accepted**, expired Actual 0이었다. Full trace는 모든 Accepted의 64-byte payload·torque/source를
원래 TX와 producing job의 sensor에 연결한다. Torque 양자화 차이 <=0.05 N·m와 원래 정수 ns를 검사한다.

아래는 각 build의 normal/full individual sample을 합친 **토크 source→소프트웨어 RX(ms)**다.
ECU job 비용·논리 job/report 시각→TX·socket TX→RX와 물리 settling time은 서로 구분한다.
Trace generation_ns는 phase_ns이며 실제 직렬화 완료 시각을 뜻하지 않는다.

| Build | Samples | Mean | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| normal | 480 | 4.484734 | 6.045365 | 6.052930 | 6.060372 |
| ASan/UBSan | 480 | 5.914341 | 6.046427 | 6.057854 | 6.075002 |
| production BUILD_TESTING=OFF | 240 | 2.197888 | 4.019047 | 4.042298 | 6.006025 |

Sanitizer는 기능/메모리 검사이고 위 차이를 대표 성능 개선/악화로 해석하지 않는다. Local single-clock·vCAN 경계이며 Target/차량 E2E가 아니다.
Replay run의 raw TX/RX는 240개였으나 Accepted는 110개에서 멈췄다. Actual loss 검출은 normal **81.988–82.062 ms**,
sanitizer **81.850–81.857 ms**, production **81.863 ms**였다. Raw CRC-valid replay가 계속되어도 valid age는 갱신하지 않았다.
6개 stream 전체의 fault별 valid RX loss 범위는 normal **80.009–82.062 ms**, sanitizer **80.002–81.981 ms**,
production **81.786–81.982 ms**였다. Source 30 ms 만료/current_sample unavailable과 RX 80 ms timeout latch는 별개다.
Late feedback 자동 복구를 허용하지 않았고 독립 zero 요청 뒤 실제 torque는 유한하게 감소했다.

새 workload의 CPU placement smoke는 normal·sanitizer 각각 1회(**12 runs 합계**) 실행했다.
배치·부하 적용은 **12/12 PASS**, ECU 계약은 **6 PASS / 6 FAIL**이다. Normal은 baseline/separate 통과·shared 2건 실패(RX miss/skip 7/8),
sanitizer는 baseline 2건 통과·shared 2건 실패(RX miss/skip 15/9)·separate 2건 실패(RX miss/skip 1/2)였다.
일부 critical stream의 최초 valid reference를 취득하지 못한 경우도 FAIL로 남겼다. 실패 run의 유효 job 관측은 모두 통계에 보존했다.
이는 새 RX 작업량/계측에서의 1회 smoke이며 10월 16일 3회 성능 비교와 구분한다. 기존 deadline을 완화하거나 실패 조건을 제외하지 않았다.

기존 M1 actuator 40 + EV 49 + M2 model 8 = **97 cases**를 normal·sanitizer 각각 모두 재실행해 통과했다.
Cantools 40.7.1의 기존 `build/m1-dbc-venv/bin/python`으로 12개 DBC·독립 CRC·C++ 36개 payload를 양 build와 교차 검증해 통과했다.
시스템 Python에는 cantools가 없었고 기존 전용 환경을 사용했다. 설치나 버전 변경은 하지 않았다.
Unit/build/Python/static/DBC는 각 build의 `m3-feedback-unit.txt/xml`·`m3-feedback-final-build.txt`, normal의 `m3-feedback-python.txt`·
`m3-feedback-final-clang.txt`·`m3-feedback-final-cppcheck.txt`, 양 build의 `m3-feedback-dbc.txt`에 남긴다.
각 build의 `m3-feedback-result/`에 45 runs의 trace/environment/source/profile/binary/artifact hash, 양 build의 `m3-feedback-steering/`·
`m3-feedback-placement/`에 회귀/부하 실패를 보존했다. VCan stdout은 `m3-feedback-vcan.txt`, 원래 trace 사본은 `m3-feedback-vcan-artifacts/`다.
최종 코드/문서/검사 로그 연결은 `build/m1-angle/m3-feedback-evidence.json`에 둔다. 예비 9 runs와 최초 static 진단도 별도 보존한다.
Markdown 95개·상대 링크/앵커 1069개, 요구 32개/TC 29개, YAML 3개와 Python 5개의 syntax/정합성을 검사했다.
전체 32개 요구/29개 system TC의 Result는 NOT RUN이다. Actual consumer를 차량에 반영하는 Central/Zone/Host bridge와
owner별 실행 budget/배치·우선순위·Target 검증 및 M3 수용은 후속이다. M1/M2 학습자 수용 기록도 PENDING이다.

2026-10-18 후속 [owner별 CPU 배치 비교](adr/ADR-0037-runtime-owner-cpu-placement.md)는
7개 owner의 선택적 CPU map·실제 affinity/policy 확인을 추가했다. 기존 상속 동작과 세 layout의 CPU 실험은 유지한다.
원래 RX source·CAN wire·8-frame budget·2 ms period/3 ms deadline과 ECU 설정·보호 기준을 변경하지 않았다.
실행된 RX body가 짧아도 다음 release까지 CPU를 얻지 못해 이전 job을 생략할 수 있다.
배치별 정상 계약을 확인하며 시한/skip 기준을 완화하거나 실패 조건을 골라 제외하지 않았다.

Normal·BUILD_TESTING=OFF production 각 3회(**24 runs씩**), ASan/UBSan 1회(**8 runs**)를 순서대로 실행했다.
CPU A=0·B=1이며 노출된 topology는 서로 다른 physical core다. Loaded 세 layout 모두 B에 같은 7/10 ms 요청 부하를 둔다.
IO baseline은 같은 IO map의 무부하 대조군이다. 부모는 고정하지 않고 runtime thread가 자기 mask를 설정한다.
Warm-up 제외는 0이고 layout/trace 순서를 회전했다. Host/VM의 다른 부하·IRQ·DVFS/cooling은 통제하지 않았다.
배치·부하 control은 **56/56 PASS**, 정상 ECU 계약은 **31 PASS / 25 FAIL**이다.
측정 window의 실제 busy CPU 하한 최소~상한 최대는 normal **67.08–69.08%**, production **66.92–68.76%**,
sanitizer **64.92–67.73%**였다. 요청 duty 70%를 실현된 일정 CPU 사용률로 간주하지 않는다.
아래는 full/minimal 합산 **계약 PASS/runs; RX skipped jobs**이며 normal·production의 layout당 예정 RX jobs는 7260개,
sanitizer는 2420개다. 이번 RX miss 수는 모두 skip 수와 같았고 실행하지 않은 duration을 만들지 않았다.

| Layout | Normal | Production | ASan/UBSan |
| --- | --- | --- | --- |
| colocated | 0/6; 47 | 0/6; 51 | 0/2; 50 |
| rx-isolated | 1/6; 1 | 2/6; 0 | 2/2; 0 |
| io-isolated | 6/6; 0 | 4/6; 3 | 2/2; 0 |
| io-baseline | 6/6; 0 | 6/6; 0 | 2/2; 0 |

RX만 이동해도 normal/production의 실제 output expiry가 각각 10/20개, Actual TX expiry가 17/17개 남았다.
Normal의 rx-isolated에는 Power miss도 1개 있었다. RX 자체의 miss 0만으로 전체 계약을 PASS로 바꾸지 않는다.
함께 이동한 IO 조건의 expiry는 모두 0이며, PASS 정상 run마다 **240 TX=240 RX=240 Accepted**였다.
Production IO의 잔여 RX skip 3개는 실패로 보존한다. Full run의 한 skip 근처에서는 monitor와 physical capture도
각각 약 4.27/4.31 ms 간격을 보였다. 공통 실행 지연의 관측이며 kernel/VM 원인을 식별한 scheduler trace는 아니다.

IO-isolated의 RX **실행된 job response(release→종료, ms)**는 아래와 같다. 실패 run의 유효 job도 포함했다.
같은 layout 안에서만 trace mode를 나누며 skip을 percentile에서 가짜 duration으로 대체하지 않는다.

| Build / trace | Executed / scheduled | Mean | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| normal full | 3630/3630 | 0.113605 | 0.193476 | 0.228865 | 0.992502 |
| normal minimal | 3630/3630 | 0.118963 | 0.200799 | 0.243726 | 0.714671 |
| production full | 3629/3630 | 0.108668 | 0.151443 | 0.233031 | 1.700965 |
| production minimal | 3628/3630 | 0.080966 | 0.124059 | 0.205948 | 0.287464 |

Production minimal의 작은 Max도 생략된 2개 job을 지우지 않는다. 고장 뒤 실행 경로 차이·scheduler/cache 간섭이 있으므로
layout 사이 body 비용 차이를 최적화 성능으로 해석하지 않는다. Sanitizer 1회는 기능/수명 확인이며 대표 성능 비교가 아니다.
Affinity는 CPU 예약/하드웨어 watchdog 격리가 아니며 IO 분리가 잔여 miss를 모두 해결했다고 선언하지 않는다.

고정 IO map `1,1,1,1,0,0,0`에서 기존 normal full/minimal·worker stall 5·CRC 손상·Actual replay를
normal·sanitizer 각각 1회(**18 runs 합계**) 실행해 모두 통과했다. 이 회귀에는 추가 CPU 부하가 없다.
기존 상속 동작의 normal fault matrix도 1회(**9 runs**) 통과했다. 기존 3-layout CPU 실험은 normal 1회(**6 runs**)로
control 6/6 PASS, 계약 4 PASS/2 FAIL(shared RX skip·Drive 미활성화)을 기록했다. 모두 별도 directory로 남긴다.

Normal·sanitizer C++ **각각 521개 PASS**, 배치 map/실제 thread 대응/순서/입력 검사 4개를 더한 Python **25개 PASS**다.
CLI malformed/duplicate/outside-mask 거부 **24조건**에서 socket/output directory 생성 전에 거부한 것을 확인했다.
3개 build와 변경 C++ 2개(runtime/dispatcher)의 clang-tidy 14 analyzer/bugprone·runtime header filter,
cppcheck 2.7 warning/performance/portability를 통과했다. 직전 M1/vCAN 97조건·DBC 검사는 위 이력을 따르며 이번에는 재실행하지 않았다.
RT policy probe는 즉시 종료하는 별도 child에 FIFO priority 1을 요청했고 **EPERM**, RLIMIT_RTPRIO=(0,0)이었다.
부모는 SCHED_OTHER/nice 0을 유지했다. RT priority 실제 실행 검증과 기존 Host 오류의 TSan은 **NOT RUN**이다.

세 build의 `m3-owner-results/`에 최종 56 runs의 trace/environment/source/profile/binary/artifact hash,
normal·sanitizer의 `m3-owner-faults/`에 고정 배치 18 runs, normal의 `m3-owner-inherited-faults/`·`m3-owner-legacy-placement/`에
상속 fault 9/기존 CPU 실험 6 runs를 보존했다. 예비 8 runs는 normal의 `m3-owner-probe/`이며 최종 수치에 포함하지 않는다.
Unit stdout은 각 build의 `m3-owner-ctest-console.txt`, Python/CLI/static/RT probe는 normal의
`m3-owner-{python,cli,clang,cppcheck,rt-probe}.txt`다. 최종 무결성·코드/문서 연결은 `build/m1-angle/m3-owner-evidence.json`에 둔다.
Monitor/plant의 physics 일부만이 아닌 전체 cycle budget, RT 적용 가능한 환경/Target timing과 M3 수용 검토는 남는다.
전체 32개 requirement/29개 system TC의 Result는 NOT RUN이며 M1/M2 학습자 수용도 PENDING이다.
이번 문서 검사는 Markdown 96개·상대 링크/앵커 1086개, YAML 3개·Python 5개의 syntax/정합성을 통과했다.

2026-10-18 후속 [전체 owner cycle 계측](adr/ADR-0038-whole-owner-cycle-observation.md)은
monitor의 입력 읽기→검사/보호/trace, plant/fixture의 입력 읽기→physics/센서→CAN TX/trace를 포함한다.
Periodic sleep과 end 뒤 bookkeeping은 body 밖이다. 원래 snapshot 취득 후 application/acquisition 시각을 읽는 순서는 유지한다.
Trace schema **4**에 owner마다 enable~2440 ms의 2 ms grid **1221개 기회**와 실제 sleep target/call/start·phase/end를 남긴다.
양 trace mode에서 essential rows를 쓰고 full에만 CLOCK_THREAD_CPUTIME_ID delta를 추가했다.
CPU 절대 시각은 thread 사이에서 비교하지 않고 계측 비용을 시한에서 빼지 않았다.

Skipped release는 이전 body 안/다음 요청 wake 이전/요청 wake 이후로 분류한다. 이 합을 전체 skip 수와 맞추고,
모든 RX miss를 같은 owner slot·앞/뒤 phase와 대조한다. 이는 관측 위치/동시 지연이며 kernel/IRQ/VM 원인 식별이 아니다.
Failed run도 schedule/interval이 유효하면 보존한다. 잘못된 owner trace는 이유와 label을 남겨 제외하며 유효한 job 통계는 유지한다.
Owner deadline은 null(TBD-04)로 두고 새 budget/skip 0 기준이나 자동 보호 latch를 도입하지 않았다.

기존 9조건에 monitor/plant 각각 6 ms overrun의 full/minimal 4조건을 추가했다. 각 owner의 첫 phase>=1100 ms에서
본문 끝에 sleep을 한 번 넣어 전체 body·기회 생략을 확인한다. Plant 주입 중 기다린 출력/Actual은 만료될 수 있다.
해당 fault에서는 expiry가 첫 후속 cycle에만 있는지와 delta 합계, Actual sent+expired=240·sent=received=accepted,
실제로 보낸 Actual의 기존 TX admission 시한을 검사한다. Normal/다른 fault의 expiry 0·기존 ECU deadline은 유지했다.
이를 단위 시험으로도 고정했다. 주입의 PASS는 지연/폐기 관측의 성공이며 정상 timing 수용이 아니다.

3개 build 각각 상속 map의 13조건, normal·sanitizer 각각 고정 IO map의 13조건을 1회씩 순서대로 실행해 **65 runs PASS**다.
추가 CPU 부하 없는 기능/지연 주입 회귀다. Normal full의 monitor 주입 cycle은 body **6.071524 ms / CPU 0.019561 ms**,
plant는 **6.221538 ms / CPU 0.132012 ms**였고 해당 owner는 각각 3개 기회를 생략했다.
Plant 주입에서는 첫 후속 cycle에 출력 2개·Actual 1개가 만료돼 TX/RX/Accepted는 239개였다.
같은 normal RX 120 ms stall은 RX miss 60개 동안 두 owner의 skip은 0이었다. RX 단독 정지와 전체 owner 지연의 관측을 구분했다.

새 workload의 owner 배치 비교는 normal·BUILD_TESTING=OFF production 각각 3회(24 runs씩), ASan/UBSan 1회(8 runs)로
**56 runs**를 실행했다. Control **56/56 PASS**, 기존 정상 계약 **33 PASS / 23 FAIL**이다. CPU A=0·B=1,
loaded 조건의 부하는 모두 B의 7/10 ms 요청 window다. Warm-up 제외는 0, 순서는 회전하고 Host/VM 다른 부하·IRQ·DVFS/cooling은 통제하지 않았다.
아래 수는 full/minimal 합산이며 owner마다 normal/production의 layout당 기회 7326개, sanitizer는 2442개다.
RX 예정 jobs는 각각 7260/2420개다. Owner skip과 ECU/RX deadline miss는 서로 다른 관측이다.

| Build | Layout | 기존 계약 PASS/runs | RX miss | Monitor skip | Plant skip | RX miss 중 두 owner도 같은 slot 생략 |
| --- | --- | --- | --- | --- | --- | --- |
| normal | colocated | 0/6 | 55 | 42 | 76 | 32 |
| normal | rx-isolated | 1/6 | 7 | 55 | 128 | 0 |
| normal | io-isolated | 6/6 | 0 | 0 | 0 | 0 |
| normal | io-baseline | 6/6 | 0 | 0 | 0 | 0 |
| production | colocated | 0/6 | 51 | 42 | 90 | 31 |
| production | rx-isolated | 3/6 | 0 | 41 | 93 | 0 |
| production | io-isolated | 6/6 | 0 | 0 | 0 | 0 |
| production | io-baseline | 5/6 | 1 | 1 | 1 | 1 |
| sanitizer | colocated | 0/2 | 16 | 15 | 19 | 14 |
| sanitizer | rx-isolated | 2/2 | 0 | 244 | 244 | 0 |
| sanitizer | io-isolated | 2/2 | 0 | 0 | 0 | 0 |
| sanitizer | io-baseline | 2/2 | 0 | 0 | 0 | 0 |

Sanitizer RX 단독 분리는 기존 계약 PASS여도 두 owner 각각 244개 기회가 생략됐다. 기존 verdict를 새 owner budget PASS로 바꾸지 않는다.
Normal colocated에서는 owner skip 중 monitor 42개 모두·plant 76개 중 74개가 요청 wake 이후에 위치했다.
Production colocated도 monitor 42개·plant 90개 모두 같은 분류였다. Body 밖 지연과 body 안 지연을 구분할 자료이며 원인 단정은 하지 않는다.

Production의 **무부하 io-baseline-full-3**에도 RX job 470과 두 owner의 slot 471이 함께 생략됐다.
Monitor/plant phase gap은 **4.398211/4.394398 ms**, 후속 cycle의 요청 wake→시작은 **2.488532/2.492042 ms**였다.
Sleep 호출 자체는 target보다 늦지 않았고 body는 **0.002229/0.018754 ms**(CPU **0.001855/0.018434 ms**)였다.
최신 release만 실행하는 RX 정책은 2 ms period를 넘긴 이전 job을 생략하므로 이를 단순히 3 ms body 초과로 해석하지 않는다.
이번 loaded IO 분리 14/14 PASS를 Host/Target 보장이나 이전 schema의 실패 해결로 확대하지 않는다.

아래는 IO-isolated full의 owner별 individual sample을 같은 build에서 합친 수치다. 각 owner **3663 executed/3663 scheduled**다.
CPU 계측을 포함하는 새 workload이며 이전 schema와 합치지 않는다. 서로 다른 owner/build/mode의 percentile도 섞지 않는다.

| Build / owner | Body P99 / Max ms | CPU P99 / Max ms | 요청 wake→시작 P99 / Max ms |
| --- | --- | --- | --- |
| normal monitor | 0.025179 / 0.045029 | 0.021274 / 0.042886 | 0.198079 / 0.782139 |
| normal plant | 0.082582 / 0.118503 | 0.079904 / 0.117346 | 0.164478 / 1.849179 |
| production monitor | 0.028146 / 0.081114 | 0.023138 / 0.064059 | 0.254787 / 0.298139 |
| production plant | 0.100725 / 0.140094 | 0.096532 / 0.136229 | 0.195394 / 0.298796 |

Sanitizer 1회는 기능/진단 범위이고 대표 성능 비교가 아니다. CPU delta와 wall 차이에는 대기·선점·I/O·계측 경계가 섞인다.
기존 3-layout CPU 비교도 normal 1회(6 runs)로 control 6/6 PASS·기존 계약 4 PASS/2 FAIL(shared)을 기록했다.
전체 새 wall-time 실행은 **127 runs = 102 PASS / 25 FAIL**, owner/기존 CPU 비교 control 62개와 고정 map control 26개는 모두 PASS다.

Normal·sanitizer C++ **각각 521개**, whole-cycle/CPU/skip·pooling·RX 대응/불완전 trace 보존·정상/fault expiry 정책의
Python 12개를 더한 **37개**가 PASS다. 3 build 및 변경 C++ 2개(runtime/dispatcher)의 clang-tidy 14 analyzer/bugprone·runtime header filter,
cppcheck 2.7 warning/performance/portability도 통과했다. 이전 trace schema 2/3의 normal/full 각 1개를 현재 reader로 재분석해 PASS였다.
M1/vCAN 97조건·DBC/CRC와 CLI 거부 검사는 이전 이력이며 이번에 재실행하지 않았다. RT/TSan은 기존 환경 제한으로 여전히 NOT RUN이다.

각 build의 `m3-cycle-faults/`에 기본 39 runs, normal·sanitizer `m3-cycle-fixed-faults/`에 26 runs,
3 build의 `m3-cycle-placement/`에 56 runs, normal `m3-cycle-legacy-placement/`에 6 runs를 보존했다.
각 directory는 environment/source/profile/binary/artifact hash와 원래 CSV·실패 판정을 포함한다.
초기 `m3-cycle-probe/` 13 runs(plant expiry의 정상 기준 적용으로 2 FAIL)는 최종 series에 포함하지 않았다.
이후 explicit plant fault의 expiry delta·첫 후속 cycle/송수신 count 검사를 추가했고 정상 만료 0 기준은 유지했다.
Build/unit은 각 build의 `m3-cycle-build.txt`·`m3-cycle-unit.txt`, Python/static/history/doc은 normal의
`m3-cycle-{python,clang,cppcheck}.txt`·`m3-cycle-history.json`·`m3-cycle-doc-check.txt`다.
`build/m1-angle/m3-cycle-evidence.json`은 최종 source/binary/artifact hash와 모든 127 runs의 cycle/expiry·원래 phase·physics/Actual TX 포함 범위를 대조한다.
관측을 근거로 owner budget·최대 감시/취득 공백·RT 환경/Target 및 M3 수용을 검토한다. 전체 32개 요구/29개 system TC는 NOT RUN이며 학습자 수용도 PENDING이다.
문서 검사도 Markdown 98개·상대 링크/앵커 1104개, YAML 3개·Python 5개의 syntax/정합성을 통과했다.

| 영역 | 향후 정책 | 적용 시점 / 증거 |
| --- | --- | --- |
| Compiler | 직접 관리하는 GCC/Clang target에 `-Wall -Wextra -Werror` 적용 | 첫 C++ target부터 적용; 검토된 최소 범위의 예외는 문서화하고 third-party에 global flag 적용 지양 |
| Static analysis | clang-tidy와 cppcheck | 처음 적용할 코드와 함께 규칙을 검토하고 도구 버전 고정 |
| Dynamic analysis | ASan과 UBSan | Host의 계측된 test job에서 사용; Target 지원은 별도 검증 |
| Unit tests | C++는 GoogleTest, Python은 pytest | 구현과 함께 동작/계약 시험 작성 |
| System tests | Integration Test, SIL Regression, Fault Regression, Performance Regression | Milestone별로 추적 가능한 case와 검토된 threshold 사용 |
| CI | 초기에 필요하면 configure/문서 검사만 수행 | M0에는 CI workflow 없음; 실제로 수행하지 않은 차량 시험을 PASS로 표시하거나 의존성이 많은 골격을 만들지 않음 |

Sanitizer를 사용한 timing은 대표 성능 증거로 볼 수 없다. 결과에는 build type,
compiler/option, 활성화된 계측을 기록한다. Real-time priority, affinity, kernel 선택,
최적화에는 변경 전후 증거가 필요하며 효과를 미리 보장하지 않는다.
Linux 측정만으로 hard real-time 인증을 주장하지 않는다.

코드를 수용하기 전에 학습자가 변경을 설명하고 diff를 검토하며 관련 검사를 직접
실행한다. Edge/fault 동작도 확인하고 결과를 요구사항에 연결한다. 미실행 test를
PASS로 표시하지 않는다. 의존성을 추가하기 전에 버전과 license를 검토하며,
M0에서는 대형 의존성을 설치하지 않는다.

Toolchain/compiler/CI/test 버전은 TBD-11(M1), board 지원/측정 환경은 TBD-09(M5/M12)로
관리한다. Owner와 rationale은 [TBD register](roadmap.md#open-m0-decisions)를 따른다.

## 2026-10-18 — 완료 guard·수신 이중 감시와 배치 비교

[ADR-0039](adr/ADR-0039-owner-completion-guards.md)의 구현 commit은 **4a22815**다. Trace schema 5이며
CAN wire schema 2는 유지한다. Monitor/plant 주기 2 ms, 완료 시한 4 ms를 Host fixture 계약으로 채택했다.
각 owner의 guard는 enable–2420 ms의 1211 slots를 포함한다. 2424 ms의 마지막 deadline을 기존 2440 ms tail에서
관측한다. 정상은 guard 대상 miss/skip 0이며 기존 ECU 5/8 ms·RX 3 ms·8-frame budget과
유효 수신 threshold 80 ms·검출 <=100 ms를 유지했다. Schema 4의 PASS와 새 수용 기준을 합치지 않는다.

기존 DeadlineMonitor로 peer 완료를 감시한다. 늦은 완료·이전 slot 누락을 fault로 latch하고 floor/zero를 요청한다.
두 owner가 각자 별도 ReceiveWatch 상태를 가져 monitor 정지 중에도 plant가 accepted stream 상실을 검출한다.
Effective loss는 먼저 실제 검출한 observer의 last-valid/detected pair이며 늦은 observer 진단도 원래 시각으로 남긴다.
상세 trace의 owner/stream fault mask, guard first-fault와 peer body 경계, tail 및 누락 분모를 검증했다.

Normal·ASan/UBSan **C++ 각각 521개**, Python **43개**가 PASS다. 기존 Python 파일에 guard 분모·late publication·
peer/tail·배치·수신 이중 감시의 6개 case를 추가했다. 세 build(normal/sanitizer/BUILD_TESTING=OFF production)가 PASS다.
Clang-tidy 14 analyzer/bugprone은 변경 C++ 2개와 runtime/공통 guard header 범위에서 user-source 진단이 없었다.
Cppcheck 2.7 warning/performance/portability도 변경 C++ 2개가 PASS다. 확대된 config의 pass-by-value 진단은 const-reference로 수정했다.
기존 trace schema 2의 2개·3의 2개·4의 3개 기록은 당시 의미로 재분석해 7개 PASS다.
기존 전체 vCAN 97개/DBC 12 frame·36 payload는 이번에 재실행하지 않았다. Wire/codec 변경은 없다.

최종 workload는 **3 build의 고정 IO map 17조건씩 51 runs**, normal 상속 배치 17 runs,
배치 비교 normal/production 각각 3회×4 layouts×2 modes=24 runs와 sanitizer 1회×4×2=8 runs다.
고장 회귀 68/68 PASS와 배치 51 PASS/5 FAIL을 합쳐 **124 runs: 119 PASS / 5 FAIL**이다.
고정 map 51개+배치 56개에서 요청/실제 affinity·SCHED_OTHER·부하 생존/CPU 소비 control **107/107 PASS**다.
각 campaign은 순차로 실행했고 build/static과 겹치지 않았다. Warm-up 제외·best-run 선택은 없다.

| Build / layout | 정상 계약 PASS / runs | RX miss / eligible jobs | Monitor miss / guarded slots | Plant miss / guarded slots |
| --- | --- | --- | --- | --- |
| Normal / io-control | 6/6 | 0/7260 | 0/7266 | 0/7266 |
| Normal / rx-separated | 5/6 | 2/7260 | 0/7266 | 0/7266 |
| Normal / guard-separated | 6/6 | 0/7260 | 0/7266 | 0/7266 |
| Normal / guard-baseline | 5/6 | 0/7260 | 2/7266 | 0/7266 |
| Production / io-control | 6/6 | 0/7260 | 0/7266 | 0/7266 |
| Production / rx-separated | 4/6 | 2/7260 | 0/7266 | 0/7266 |
| Production / guard-separated | 5/6 | 0/7260 | 1/7266 | 0/7266 |
| Production / guard-baseline | 6/6 | 0/7260 | 0/7266 | 0/7266 |
| Sanitizer / io-control | 2/2 | 0/2420 | 0/2422 | 0/2422 |
| Sanitizer / rx-separated | 2/2 | 0/2420 | 0/2422 | 0/2422 |
| Sanitizer / guard-separated | 2/2 | 0/2420 | 0/2422 | 0/2422 |
| Sanitizer / guard-baseline | 2/2 | 0/2420 | 0/2422 | 0/2422 |

CPU A=0/B=1/C=2로 고정했다. IO control은 RX/monitor/plant=A, ECU4=B이고 부하는 B다.
RX-separated는 RX만 C, guard-separated는 monitor만 C로 옮긴다. Guard-baseline은 마지막 map에 부하가 없다.
각 guard 분모는 1211이며 전체 관측 기회 1221과 다르다. Full/minimal별 percentile은 summary에서 구분한다.
누락으로 보호해도 정상 timing은 FAIL이며 failed run의 유효 job/owner 관측을 통계에 포함했다.
다섯 실패는 RX 누락 3 runs와 monitor 누락 2 runs다. 총 RX miss 4개·monitor guard miss 3개이며
plant guard miss는 없었다. 원인이 특정 kernel/VM이라고 단정하지 않는다.
이번 Host의 다음 기준 배치는 **io-control 14/14 PASS**로 유지한다. Monitor 별도 코어 13/14 PASS이며
무부하 조건에서도 누락이 있어 코어 추가나 무부하만으로 정상 시한을 보장할 수 없다.

세 build의 owner 주입 24 runs에서 첫 owner fault 30개의 deadline→검출은 **0.038–4.260 ms**,
첫 검출→zero 적용 24개는 **0.001–4.103 ms**였다. 모두 선택한 margin 10 ms 이내다.
Monitor 120 ms 정지 full/minimal 6 runs의 backup loss 검출은 last-valid 기준 **80.002–82.047 ms**였다.
주입 중 peer 검출/보호·복귀 후 latch, finite torque ramp·brake floor·Actual source/bytes/Accepted와 보고 수를 검사했다.
Plant 정지 때는 monitor가 먼저 요청하더라도 실제 physics 적용은 복귀 후다. 두 owner의 6 ms 동시 지연은
복귀 후 late completion 검출을 확인하며 공백 중 실제 출력 변경을 주장하지 않는다.
Process/OS 전체 정지·hardware watchdog·RT/Target·전체 E2E는 미검증이다. RT probe는 앞서 EPERM/RLIMIT_RTPRIO=0이었고
이번 RT 실행/TSan은 NOT RUN이다. **32개 requirement/29개 system TC의 전체 Result도 NOT RUN**이다.

증거는 각 build의 `m3-guard-faults/`(17), `m3-guard-placement/`(24/8)와 normal `m3-guard-inherited/`(17)에 둔다.
각 폴더의 environment/summary/artifact-sha256는 commit·source/profile·binary/build/CPU·모든 실행을 보존한다.
각 build의 `m3-guard-{build,unit}.txt`(production은 unit 없음), normal의
`m3-guard-{python,clang,cppcheck,doc-check}.txt`·`m3-guard-history.json`이 검사 로그다.
`build/m1-angle/m3-guard-evidence.py`/`.json`은 124 runs의 source/profile/binary/artifact hash,
job/guard 분모·peer 관측·원래 phase/physics/Actual TX 포함·보호 latch·재판정을 교차 검증했다.
개발 중 `m3-guard-probe/`와 `m3-guard-probe2/` 각 17 runs는 최종 계약/소스와 구분해 집계에서 제외했다.
첫 probe에서 monitor 정지 중 수신 진단이 늦는 문제가 드러나 별도 plant ReceiveWatch를 추가한 뒤 최종 source를 고정했다.

## 2026-10-18 — Steering hosted RTOS와 실행 대기 진단

[ADR-0040](adr/ADR-0040-steering-rtos-pilot-and-delay-observation.md)의 구현은 **fea2de6**, 진단 부하 worker의
spawn import 수정은 **75b0cb2**다. Trampoline revision `ff287023252bf73273067f00d2dbc8bbc9a20401`을 고정하고
GOIL **3.1.16 / GALGAS 3.7.0**·ViPer를 소스에서 빌드했다. Upstream license와 tool/binary/archive/input hash는
`build/m3-rtos-pilot/build.json`에 있다. 일반 CMake build는 다운로드하지 않고 옵션 bridge와 외부 생성 빌드를 구분한다.

OIL 2.5로 ReleaseDispatch/Watch/Receive/Control Task·Alarm·Event·Resource를 실제 kernel에 생성했다.
기존 C++ Steering ECU·P05 CAN wire와 다른 process의 물리·센서·Actual receiver를 연결했다.
이것은 hosted OSEK OS 기능 시험이다. Upstream의 AUTOSAR OS 4.2 API alignment와 프로젝트 R25-11 wire 사용을
전체 Classic R25-11 stack 적합성으로 합치지 않는다. ARXML/RTE/BSW·ARM64 Jetson·실제 MCU/Target은 NOT RUN이다.

Normal·ASan/UBSan **C++ 각각 521개**, Python **48개 PASS**다. 기존 Python 파일에 source/late/skipped·
coverage·spawn 검사 5개를 추가했다. 세 build(native normal/sanitizer, 별도 BUILD_TESTING=OFF RTOS host)가 PASS다.
변경 C++ 5개(bridge, plant fixture, 기존 두 runtime, dispatcher)에 clang-tidy 14 analyzer/bugprone과 cppcheck 2.7
warning/performance/portability를 적용해 user-source 진단 없이 PASS다. Runtime support header도 clang-tidy 범위에 포함한다.
직접 작성한 hosted C는 생성 build의 Wall/Wextra로 검사했다. Upstream POSIX port의 기존 write return-value 경고는 별도로 남았다.
Hosted OS의 alternate-stack sanitizer/fiber 연동은 미검증이다. Native core의 ASan/UBSan 결과를 OS binary에 확대하지 않는다.

| 실행 범위 | 조건 / 반복 | 결과 |
| --- | --- | --- |
| Hosted RTOS Steering | normal/command-loss/corrupt/control-stall ×3회 | **12/12 PASS** |
| Native multirate | 기존 17조건 × normal/sanitizer | **34/34 PASS** |
| Native Steering | normal full/minimal·overrun·stall × normal/sanitizer | **8/8 PASS** |
| 추가 부하 없는 진단 | monitor CPU 2, observer CPU 3, 3회 | Capture/control 3/3 PASS, 원래 정상 timing **2 PASS/1 FAIL** |
| Monitor CPU 부하 진단 | 같은 map + CPU 2의 7/10 ms wall busy window, 3회 | Capture/control 3/3 PASS, 원래 정상 timing **0 PASS/3 FAIL** |

따라서 기능 회귀 **54/54 PASS**와 진단 **6 runs**를 구분한다. Build/static과 측정은 순차로 실행했다.
기능 회귀의 source cohort는 fea2de6이고 최종 진단은 75b0cb2다. 두 commit 사이 실행 코드 변경은
진단 Python import이며 C++/OIL/RTOS binary는 유지했다. Source hash는 당시 commit의 blob까지 대조한다.
동일 측정을 다시 선택해 좋은 결과만 집계하지 않았다. 기존 전체 vCAN 97개/DBC 12 frame·36 payload는 이번 재실행하지 않았다.

### RTOS 기능과 가상 tick

Control-stall은 실제 OS의 WaitEvent와 12-tick Resume Alarm을 사용한다. 감시·수신 Task와 별도 plant가
그동안 실행되는지, Watch가 복귀 전에 hold를 요청/적용하는지 검사했다. Late Actual 폐기·source 보존·CRC·
잘못된 명령이 accepted time을 갱신하지 않는지·hold latch도 확인했다. 종료 JSON·OS 오류·모든 물리/Actual trace를 대조한다.
Console shim exit 0만으로 OS 실행 성공을 판정하지 않는다. 각 RTOS PID의 POSIX IPC 이름 정리도 교차 확인했다.

고정한 upstream ViPer는 10 ms relative usleep 기반이다. 이번 12 runs의 첫 release 기준 누적 drift는
**23.846–30.521 ms**(1.6 s fixture)였다. 정상 3 runs의 ReleaseDispatch 게시→Control 완료 최대는 **0.131148 ms**다.
5 ms 완료 budget은 ReleaseDispatch가 실제로 게시한 시각부터이며 그 앞의 alarm/timer/Host 지연은 포함하지 않는다.
기능 PASS를 원래 M3의 2 ms/4 ms guard·RX 3 ms 시한이나 차량 E2E 완료로 대체하지 않는다.
두 실행자의 원천 취득·generation·적용 시각도 합치지 않는다. Linux scheduling은 SCHED_OTHER로 유지했다.

### 누락과 runqueue 대기

진단 대상은 RTOS 내부 Task가 아니라 기존 **native multirate Linux thread**다. ECU4=CPU1, RX/plant=CPU0,
monitor=CPU2, observer=CPU3다. Native 회귀의 기존 IO 동반 map과 다른 진단 조건이며 별도 비교군이다.
`/proc/PID/task/TID/schedstat`와 context-switch 누적값을 sample begin/end와 함께 기록했다.
CONFIG_SCHED_INFO=y를 확인했고 perf probe는 exit 255/paranoid=4, tracefs 접근은 EACCES였다. 커널 trace는 NOT RUN이다.

| 진단 | Monitor skip | 완전 coverage | Queue 증가 관측 | 해당 구간의 queue delta |
| --- | --- | --- | --- | --- |
| 추가 부하 없음, 3 runs | 1 | 1/1 | 1/1 | 3.510370 ms |
| Monitor CPU 부하, 3 runs | 485 | 485/485 | 485/485 | 2.071215–4.376561 ms |

모든 486개 사건은 실행하지 않은 monitor slot이다. RX/plant miss 사건은 없었다. 각 run의 miss 수는 무부하 **1/0/0**,
부하 **1/242/242**였으며 변동도 그대로 남겼다. 부하 process의 측정 중 실제 CPU 사용 경계는 약 **0.686–0.692**였다.
모든 run의 요청/실제 affinity·policy와 부하 생존/소비 control을 검증했다.

무부하 한 사건의 요청 wake 지연은 **3.564592 ms**, 이를 덮는 두 sample의 queue 증가는 **3.510370 ms**다.
그러나 sample 구간은 **6.058660 ms**, 사건 앞뒤 여유는 **2.494068 ms**다. Queue 증가를 해당 wakeup 하나에
전부 할당할 수는 없다. CPU 배정 대기가 관측된 근거이며 경쟁 process/IRQ/VM 또는 timer 지연의 완전한 분해는 아니다.
앞선 배치 실험의 5개 실패에는 이 counter가 없으므로 원인을 소급 확정하지 않는다. Observer 자체의 추가 비용도
포함한 진단 workload이며 원래 성능 표본과 합치지 않는다. 표본/카운터가 불완전하면 unknown으로 남긴다.

### 로그와 남은 검증

RTOS는 `build/m3-rtos-results/`에 environment·12 runs·summary·artifact hash를 보존했다.
Native는 normal/sanitizer의 `m3-rtos-native/`(각17)·`m3-rtos-steering/`(각4)이며 같은 이름의 .txt 로그가 있다.
진단은 normal build의 `m3-rtos-diagnostic-quiet/`·`m3-rtos-diagnostic-loaded/`에 각3 runs의 counter CSV와 대응 사건을 둔다.
`build/m3-rtos-evidence.py`/`.json`은 54회 기능 재판정·6회 counter 재대조, source/commit·binary·upstream·artifact hash,
OS API/원래 source·물리/보호·진단 coverage를 확인한다. Build/static은 `build/m3-rtos-{build,clang,cppcheck}.txt`,
unit/Python은 각 native build의 `m3-rtos-unit.txt` 및 normal의 `m3-rtos-python.txt`, 문서는 `build/m3-rtos-doc-check.txt`다.

개발 probe 1–4의 16 runs는 최종 series와 구분한다. POSIX stack 전환의 fortified longjmp 충돌, 허용되지 않은
Alarm callback의 SetEvent, port stack-size overflow를 수정하고 실제 Task context와 적합한 크기로 고정했다.
마지막 개발 probe의 4조건이 PASS한 뒤 최종 반복을 수행했다. 추가 호환 probe에서 유효한 49152-byte stack을 유지하고
fortify 예외만 제거했을 때 `__longjmp_chk`와 같은 abort를 재현했다. `build/m3-rtos-fortify-result/`·
`build/m3-rtos-fortify-check.txt`에 보존하며 예상 실패 1회는 기능 회귀의 분모에 넣지 않는다.
최초 진단 quiet 3 runs와 실패한 loaded 실행기 로그
(`m3-schedstat-quiet/`, `m3-schedstat-loaded.txt`)도 보존한다. Loaded는 runtime 실행 전 spawn import에서 실패했으며
수정 뒤 새 directory에서 quiet/loaded를 함께 3회씩 실행했다. Runtime timing FAIL과 실행기 오류를 혼동하지 않는다.

다음은 Steering OS/driver·Task mapping 검토, RT 설정이 가능한 native 환경과 timer→wakeup→switch 추적,
Target/virtual target 호환성과 RTE/BSW 검토다. 현재 Linux kernel/권한을 바꾸지 않았다. 다른 Leaf의 OS 전환,
Target·차량 전체 E2E, 32개 requirement/29개 system TC의 전체 Result는 **NOT RUN**, 학습자 수용은 PENDING이다.

## 2026-10-18 — ARM64 빌드 경계와 RT 사전 점검

구현은 **a9dfb54**, 결정은 [ADR-0041](adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)이다.
기존 builder·진단 도구·Python 시험 파일을 확장했다. 일반 CMake build나 Target OS를 변경하지 않았다.

| 확인 | 결과 / 범위 |
| --- | --- |
| Native POSIX RTOS build | 분리한 CMake·OS·ViPer directory에서 PASS |
| ARM64 Linux 교차 빌드 | GCC/G++ 11.4.0으로 RTOS·ViPer·외부 plant 세 ELF 생성, readelf machine·hash 대조 PASS |
| Native OS 기능 회귀 | 정상/명령 상실/CRC 손상/Control WaitEvent 정지 ×3회, **12/12 PASS** |
| Python | 기존 파일에 compiler/ELF/architecture·preemption/FIFO 검사 6개 추가, **54개 PASS** |
| CLI 차단 | 다른 CPU 실행·output architecture 혼용·CMake compiler 혼용·stale source·잘못된 FIFO priority **5개 예상 거부 확인** |
| Host RT 사전 점검 | 보고서 수집 PASS, FIFO priority 1은 **BLOCKED / EPERM**, 원래 scheduler 복원 확인 |
| 미실행 | 실제 ARM64/Jetson runtime·보드 stack/driver·RT workload·kernel trace·전체 system TC **NOT RUN** |

신규 native 기능 series의 nominal wall drift는 **24.261–28.727 ms / 1.6 s**, 정상 3 runs의 실제
ReleaseDispatch 게시→Control 완료 최대는 **0.141084 ms**였다. 앞선 12 runs와 별도 series이며 timing 개선 비교가 아니다.
가상 tick의 앞단 timer/Host 지연은 기존대로 별도다. Original source·late report 폐기·hold 적용·OS 오류 및 PID별 IPC 정리를 재검사했다.
기존 native multirate/Steering 42 runs와 normal/sanitizer C++ 521개씩의 이력은 유지한다. C++ 기능 변경이 없어 이번에 재실행하지 않았다.
Wire/DBC·부하 scheduling observer series도 이번에 새로 실행하지 않았다.

ARM64 산출물은 `/lib/ld-linux-aarch64.so.1`을 요구한다. RTOS/ViPer에는 `GLIBC_2.34`, plant에는
`GLIBCXX_3.4.29`를 포함한 symbol 요구가 있다. 전체 목록은 각 `build.json`의 `elf_artifacts.runtime_requirements`에 있다.
이는 현재 교차 toolchain의 ABI이며 선택한 JetPack/BSP와 호환된다는 근거가 아니다. GOIL은 Host 도구로 유지하고
ViPer를 target별 output 안에서 빌드했다. 고정 upstream은 수정하지 않았고 일반 다운로드/라이선스 정책도 유지한다.

Host는 `6.8.0-138-generic`, `CONFIG_PREEMPT_DYNAMIC=y`, `CONFIG_PREEMPT_RT` 비활성이다.
RLIMIT_RTPRIO는 0/0, runtime/period throttling은 950000/1000000 µs다. Tracefs는 EACCES,
perf paranoid=4/exit 255였다. 부모의 SCHED_OTHER/priority 0은 유지했다. Syscall 권한 검사와 PREEMPT_RT 여부를
구분하며, 권한 거부를 workload FAIL이나 RT timing PASS로 바꾸지 않는다. Owner별 RT 실행 경로와 지연 비교는 후속이다.

Native는 `build/m3-platform-native-host/`·`m3-platform-native-pilot/`, ARM64는
`build/m3-rtos-aarch64-host/`·`m3-rtos-aarch64-pilot/`에 두며 `m3-platform-{native,cross}-build.txt`가 build 로그다.
기능 회귀는 `build/m3-platform-rtos-results/`와 같은 이름의 .txt, 사전 점검은
`build/m3-platform-capabilities-final/`, Python은 `build/m3-platform-python.txt`다.
`build/m3-platform-evidence.py`·`.json`·`.txt`는 입력/도구/archive/ELF·ABI hash, 12회 기능 재판정·IPC 정리,
5개 CLI 거부와 사전 점검 상태를 대조한다. 일부 build/run metadata의 HEAD는 직전 3dc2b26이며 작업 중 source hash를
보존했다. 이를 구현 commit a9dfb54와 재대조했다. 사전 점검 최종 기록은 clean a9dfb54다.
문서·링크·추적성/YAML·Python syntax는 `build/m3-platform-doc-check.txt`에 보존한다.

다음은 선택한 ARM64 보드의 OS/BSP·ABI/stack/IPC 확인과 RT 권한이 있는 환경의 native policy/priority 적용·실측이다.
다른 Leaf 확대와 M3 수용은 해당 증거 검토 뒤 진행한다.

## 2026-10-18 — 개발 계정 RT 권한 적용 확인

사용자가 준비된 설정을 `/etc/security/limits.d/90-stratadrive.conf`에 설치했다. Root:root/0644와
`alswoghd soft/hard rtprio 20` 두 항목을 확인했다. 기존 IDE/Codex의 0/0 한도에서는 FIFO priority 1이 여전히 EPERM이었다.

`sudo -n -u alswoghd`로 같은 사용자에게 새 PAM 실행 세션을 만들면 한도는 **20/20**이었다.
UID 1000/CapEff=0에서 기존 진단 도구로 FIFO **1·20 AVAILABLE**, 상한 밖 **21 BLOCKED/EPERM**을 확인했다.
각 probe의 원래 scheduler 복원도 확인했다. 부모 IDE와 새 세션의 실행 정책은 SCHED_OTHER/priority 0을 유지했다.
시스템 sudo/sshd PAM 설정에 `pam_limits.so`가 있고, 이 실행 경로에서는 추가 비밀번호 입력이 필요하지 않았다.

첫 기존 세션 기록은 `build/rt-permission-check-20261018T142149.202896Z/`, 새 세션 priority 1은
`build/rt-permission-active-20261018T142329.848901Z/`, priority 20/21은 각각
`build/rt-permission-bound-{20,21}-20261018T142439.618421Z/`에 capabilities·source/commit·artifact hash를 보존했다.
이 기록의 source commit은 47c23fe다. 이번에는 문서만 변경해 build/unit/기능 회귀를 재실행하지 않았다.

RT workload와 일반/RT timing 비교는 **NOT RUN**이다. PREEMPT_DYNAMIC kernel과 trace/perf 접근 제한도 유지한다.
다음은 owner별 RT 설정·적용 실패 처리·실제 policy/priority 기록을 연결하고 같은 M3 시한에서 비교하는 것이다.
새 로그인/IDE 재시작 또는 위 같은 사용자 실행 경로로 계정 한도를 적용할 수 있다.

## 2026-10-19 — Native owner별 FIFO 실행과 동일 부하 비교

구현은 **7843a7e**, 결정은 [ADR-0042](adr/ADR-0042-native-owner-fifo-scheduling.md)다.
기존 multirate 실행기에 일곱 owner의 `owner-fifo=` 요청과 실제 policy/priority 확인, 모든 owner 준비 후 startup release,
실패 시 전체 취소와 호출 thread 복원을 연결했다. C++ parser 검사 2개와 기존 Python 파일의 scheduling/control 검사 5개를 추가했다.

### 확인한 범위

Normal·ASan/UBSan build와 C++ **각각 523개**, Python **59개**는 PASS다.
변경 C++ 3개(multirate runtime, demo 진입점, runtime unit)의 clang-tidy analyzer/bugprone·cppcheck warning/performance/portability도 PASS다.
Cppcheck는 GTest macro를 읽기 위해 `--library=googletest`를 사용했다. 초기 macro 구문 오류 로그도 별도 보존했다.
BUILD_TESTING=OFF의 hosted OS build와 ARM64 Linux RTOS·ViPer·plant build도 PASS이며 ARM64 runtime은 NOT RUN이다.

최종 실행은 clean 구현 commit에서 순차 진행했다. Native workload는 기존 IO 동반 map(ECU4=CPU1, RX/monitor/plant=CPU0)을 유지했다.
새 PAM 계정 세션의 rtprio는 20/20이며, 일반 조건은 SCHED_OTHER/0, FIFO는 10/10/9/10/18/20/19다.
각 owner의 준비/실제 적용값과 startup·호출 thread 복원, native **92회**의 배치·설정·부하 control은 모두 PASS다.

| Series | 조건 / 수 | 계약 결과 |
| --- | --- | --- |
| Native 비교 | OTHER/FIFO × quiet/loaded × full/minimal ×3 | **24/24 PASS** |
| Normal OTHER 고장 회귀 | 기존 17조건, 같은 CPU map | **17/17 PASS** |
| Normal FIFO 고장 회귀 | 같은 17조건과 주입 | **17/17 PASS** |
| ASan/UBSan OTHER 고장 회귀 | 같은 17조건과 주입 | **15/17 PASS**, 2 FAIL 보존 |
| ASan/UBSan FIFO 고장 회귀 | 같은 17조건과 주입 | **17/17 PASS** |
| Hosted OS Steering 회귀 | 기존 정상/명령 상실/CRC/WaitEvent 정지 | **4/4 PASS** |

총 **94/96 PASS**다. 추가 CLI 3개(권한 없음·BMS만 priority 21인 부분 실패·중복 옵션)는 예상 거부를 확인했으며 위 분모에 넣지 않는다.
설정이 거부된 두 경우 모두 startup release=0, 모든 job/cycle 미실행, CAN/physical 행 없음과 호출 thread 복원을 확인했다.
일반 policy로 fallback하거나 일부 작업만 실행하지 않았다. 미검증 priority map을 양산 설정으로 취급하지 않는다.

### 같은 부하에서 관측한 지연

다음은 normal build의 **Drive release→완료**이며 단위는 ms다. 각 행은 독립 3 runs의 job 관측을 합쳤고 run 간 gap은 만들지 않는다.
Drive 시한은 두 정책 모두 기존 5 ms다. Full/minimal·sanitizer 및 앞선 배치/observer 실험과 섞지 않는다.

| 부하 / trace | OTHER p99 | FIFO p99 | OTHER max | FIFO max |
| --- | --- | --- | --- | --- |
| ECU CPU 부하 / full | 1.946878 | 0.065454 | 2.638265 | 0.099024 |
| ECU CPU 부하 / minimal | 2.449738 | 0.073157 | 2.493961 | 0.090526 |

부하는 같은 SCHED_OTHER 7/10 ms wall busy window이며 CPU 소비도 검증했다. Partial boundary를 포함한 실제 CPU 비율 경계는
전체 loaded runs에서 약 0.664–0.688이었다. 주어진 경합 조건에서 ECU 응답 tail이 줄었지만 모든 작업의 지연이 개선된 것은 아니다.
예를 들어 quiet/minimal RX max는 OTHER **0.342025 ms**, FIFO **1.065564 ms**였다. 둘 다 RX 3 ms 시한 안이다.
Clock/power/background를 고정한 WCET 실험이 아니며 이 수치로 다른 Host/Target 또는 모든 timing tail을 보장하지 않는다.

### 보존한 sanitizer OTHER 실패

`power-stall-full-1`은 plant slot 1035(release 2070 ms)를 생략했다. 다음 실제 실행의 요청 wake 지연은 **2.053252 ms**였다.
Monitor가 **2074.100001 ms**에 검출했고 실제 brake floor는 **2076.057343 ms**에 적용됐다. Plant body max는 **0.238077 ms**였다.
이 실패는 주입된 Power 정지와 별도로 발생한 owner miss이므로 정상 수용으로 바꾸지 않았다.

`rx-stall-full-1`은 plant slots 210/721와 monitor slot 721을 생략했다. 요청 wake 지연은 각각 **2.073495/2.054862/2.111280 ms**다.
첫 plant miss의 검출은 **424.154572 ms**, 실제 floor/zero 적용은 **426.067791 ms**로 계획된 RX 정지(1100 ms) 전이었다.
Drive가 활성화되지 않아 oracle은 `Drive gate never enabled before fault`로 실패했다. Plant body max는 **0.205986 ms**였다.
이는 긴 body가 아니라 요청 wake 뒤의 지연과 slot 누락을 관측한 기록이다. Timer/IRQ/CPU 배정 원인은 이 trace만으로 특정하지 않는다.

두 run의 설정·배치 control은 PASS고 runtime abort/trace drop도 없다. 첫 실패는 plant 1개, 두 번째는 plant 2개·monitor 1개로
총 **4개 guarded slot**이 누락됐다. 기존 최신 release 실행 정책과 4 ms guard를 유지했고 보호가 실제 적용된 시각도 보존했다.
실패를 재실행 PASS로 대체하거나 비교 24회/앞선 observer 표본에 합치지 않았다. Sanitizer FIFO는 17/17이지만 hard real-time 증명은 아니다.

### 로그와 남은 작업

`build/m3-fifo-comparison/`(24), `m3-fifo-{other-faults,fifo-faults,asan-other-faults,asan-fifo-faults}/`(각17),
`m3-fifo-rtos-regression/`(4)에 environment/source/binary·모든 CSV·summary/artifact hash를 둔다. 같은 이름의 .txt가 실행 로그다.
`build/m3-fifo-campaign.{txt,json}`은 전체 실행 순서·exit/계약 결과를 보존한다.
`build/m3-fifo-cli-checks/`는 3개 예상 거부, `m3-fifo-{unit,sanitized-unit,python,clang,cppcheck}.txt`는 검사 로그다.
Native/sanitizer build는 `m3-fifo-{build,sanitized-build}.txt`, 문서 검사는 `m3-fifo-doc-check.txt`다.
선택형 OS는 `build/m3-fifo-rtos-{host,pilot}/`, ARM64는 `m3-fifo-aarch64-{host,pilot}/`과 각 build 로그·manifest에 둔다.
일부 build/CLI metadata는 직전 commit+작업 중 hash이며 구현 commit의 blob과 재대조했다. 최종 96 runs의 source commit은 clean 7843a7e다.

`build/m3-fifo-evidence.py`·`.json`·`.txt`는 source/commit·binary/build/archive/도구·ELF/ABI hash,
94 PASS/2 FAIL 재판정·실제 scheduler/CPU/startup/복원·부하 control·기존 OS IPC 정리를 대조한다.
개발용 `build/m3-fifo-probe/`의 8 runs는 최종 24회 비교에서 제외한다.
초기 `build/m3-fifo-python-probe.txt`의 54개 검사도 최신 59개 결과와 구분한다.

다음은 선택할 실행 profile·M3 수용 검토와 kernel timer→wakeup→switch 관측이다. PREEMPT_DYNAMIC kernel·RT throttling은 유지했고
PREEMPT_RT/kernel trace·실제 ARM64 실행·RTE/BSW·전체 32개 requirement/29개 TC는 **NOT RUN**이다.

## 2026-10-19 — M3 수용 검토 중 guarded 주기 집계 수정

`owner_cycle_metrics`의 `guarded_deadlines.observed_start_interval_ms`가 여러 run의 행을 먼저 합쳐
독립 실행 사이의 대기 시간을 task 실행 간격으로 포함했다. 바깥 owner 통계와 ECU/RX의 pooled 통계는
이미 run 경계를 보존했으며, 오류는 이 nested guarded 통계에 있었다. 기존 `pooled_job_metrics`를 재사용해 수정했다.
두 run의 guarded slot·관측 tail·skip을 포함한 회귀 검사가 수정 전 실패하고 수정 후 통과했다.
현재 Python 리포터 **60개 PASS**다. C++·runtime binary·주기·시한은 이번 변경 대상이 아니다.

수정 전 `build/m3-fifo-evidence.py` 감사는 원래 96 runs의 source/binary/artifact와 **94 PASS/2 FAIL**을
재확인했다. 그 감사 script/JSON/로그는 `build/m3-acceptance-review/m3-fifo-evidence.*`에 보존했다.
수정 후 같은 원본 96 runs를 재분석했고 개별 run의 판정·owner 통계와 Drive/RX 지연·분모·miss/skip·trace 비교는 동일했다.
24회 비교의 8조건×2 owner에서 pooled guarded interval 표본 수를 3632→3630으로 교정하고 해당 16개 분포를 다시 계산했다.
원본 CSV/summary/hash는 덮어쓰지 않았다. 실행 재시험은 **0회**이며 두 sanitizer OTHER 실패도 그대로다.
재분석 script/JSON/로그는 `build/m3-acceptance-review/reanalyze.py`, `reanalysis.json`, `reanalysis.txt`에 둔다.
앞선 59개 Python·523개씩 C++·build/static 결과는 당시 검사 이력으로 유지한다.

## 2026-10-19 — M3 Host 수용 검토와 통합 기준 선택

[M3-REV-20261019](m3_acceptance_review.md)에서 release/완료·누락 분모·원천 clock/Actual·유효 RX·교차 guard와
보호 요청/plant 적용/물리 관측을 대조했다. IO 동반 CPU 배치와 FIFO 10/10/9/10/18/20/19를 다음 Host 통합 기준으로 선택했다.
기본 CLI 정책·YAML 값·native runtime/시한은 바꾸지 않았다. 타이밍 예외 OPEN-M3-01/02·학습자 수용을 남기며 M3는 IN PROGRESS다.
RX 실패의 floor 목표 적용 426.067791 ms 때 압력은 0.3 MPa, 1 MPa 이상 첫 관측은 566.313704 ms였다.
Power 실패의 torque zero 목표는 1104.230218 ms, 실제 zero 관측은 1200.234945 ms였다.
보호 목표 적용을 즉시 물리 목표 도달로 해석하지 않는다.

README·상태·로드맵·timing 계약·ADR·학습/개발 계획·profile 안내·traceability를 갱신했다.
M4 coordinator 계약·기능 준비와 M3 예외 해소를 병행할 수 있으나 새 통합 workload는 별도 검증한다.
Target timing은 실제 배포 단계, Central/Zone DDS는 M5, 차량 E2E는 M7에 연결한다.
기존 system requirement 32개/TC 29개의 전체 NOT RUN과 M1/M2 학습자 review는 유지한다.
문서 105개/상대 링크·앵커 1186개, requirement 32개/TC 29개 추적성, YAML 3개/Python 8개 syntax와
whitespace를 검사해 통과했다. 결과는 `build/m3-acceptance-review/docs-check.txt`에 둔다.

## 2026-10-19 — Hosted timer drift 수정과 Host scheduling 회귀

[ADR-0043](adr/ADR-0043-hosted-monotonic-timer-and-placement.md)의 구현은 `625b487`,
기능 PASS 뒤 추가 timing 실패도 전체 FAIL/exit 1로 남기는 후속은 `554e91c`다.
후자의 clean source에서 계측 relative/absolute × OTHER/FIFO × 4 scenarios × 3회를 실행했다.
동일 IO CPU 0/RTOS CPU 1·추가 부하 없음·warm-up 제외 0이며 profile 순서를 repetition마다 회전했다.
코드·설정은 측정 중 바꾸지 않았고 아래 native/observer와 시간상 겹치지 않게 순차 실행했다.

| 실행 | 결과 / 범위 |
| --- | --- |
| Hosted timer 비교 48회 | 기능/배치 control 48/48 PASS, 추가 timing은 absolute 24/24 PASS / relative 0/24 PASS. 상대 대조군 24 FAIL/exit 1 보존 |
| Native FIFO normal/sanitizer | 기존 17조건×3회, 각각 51/51 PASS. 원래 96회 cohort의 OTHER 실패 2건과 별도 |
| Native observer 진단 | Control 12/12 PASS. Quiet 두 policy 각각 3/3, IO 부하 OTHER 0/3·FIFO 3/3 timing PASS |
| ViPer 정지 주입 | 실제 35.133071 ms 정지, 누락 expirations 3개와 normal FAIL/exit 1 확인; 나머지 3조건 PASS |
| Upstream backend 호환 | 원본 timer 선택·동일 CPU map의 OTHER 기능 4/4 PASS; 새 timing 수용으로 해석하지 않음 |
| Unit·build/static | C++ normal/sanitizer 각각 523개, Python 63개 PASS. Native/hosted OS/ARM64 build, C++ 2개 clang-tidy·C/C++ 3개 cppcheck PASS |

선택한 absolute/FIFO의 normal 세 runs에서 nominal drift는 −0.000772/−0.000368/−0.000862 ms,
원래 timer phase→Control 완료 max는 0.276923 ms였다. Relative/FIFO는 15.016595–17.319982 ms drift와
phase→완료 max 25.781443 ms였다. Absolute/OTHER도 Host 추가 timing 12/12 PASS이고 normal max는 0.284828 ms다.
각 normal 원천 job의 관측이며 fault의 의도적 Control 정지나 run 사이 gap을 성능 표본에 합치지 않는다.
실제 release 뒤 짧은 계산 시간만으로 timer 앞단 지연이 사라졌다고 판단하지 않는다.

Timerfd는 놓친 기간을 기록하고 signal 하나만 보내며 mmap trace를 시작 전에 준비한다.
원본 checkout은 수정하지 않고 GPL 표기·source/compile command/hash를 가진 timer object만 교체했다.
기본 opt-in build는 absolute이며 `relative`는 동일 계측 대조군, `upstream`은 고정 원본이다.
개발 probe 첫 4회 중 Control-stall은 12 ticks가 최소 wall 120 ms를 못 채워 FAIL이었다.
13 ticks로 수정하고 >=120 ms oracle을 유지했다. 이 개발 8회와 정지/호환 8회는 48회 비교에서 제외했다.
초기 cppcheck의 compound-literal ternary AST 오류는 동등한 initializer 표현으로 바꾼 뒤 검사했다.

Observer IO 부하의 187개 miss event 모두를 덮는 sample에서 runqueue 대기 증가를 확인했다.
Sample 경계 여유는 최대 2.891313 ms이며 intrusive 관측이다. 원래 sanitizer 두 실패의 개별 kernel 원인으로 소급하지 않는다.
PREEMPT_DYNAMIC·governor powersave·RT throttling은 유지했다. 전력/clock/cooling/background는 고정하지 않았고
tracefs/perf 접근도 여전히 제한돼 있다. PREEMPT_RT·실제 ARM64/Jetson·WCET·full AUTOSAR/전체 M3 수용은 후속이다.

`build/m3-latency-campaign/`에 48회·native 102회·observer 12회의 모든 trace/CSV·source/binary/environment·manifest와
`campaign.json`/각 `.txt`를 보존한다. `build/m3-latency-audit.{py,json,txt}`는 원본 hash·source blob·actual policy/CPU,
독립 재판정·timer expiration/phase·observer counter/load·ELF/ABI·archive를 재대조한다.
Build는 `build/m3-latency-{host,relative,absolute,aarch64-host,aarch64,upstream-host,upstream}/`과 같은 이름의 build 로그다.
주입은 `build/m3-latency-timer-stop*`, 원본 호환은 `m3-latency-upstream-results/`, unit/static은 `m3-latency-{unit,sanitized-unit,python,clang,cppcheck-*}.txt`다.
Profile YAML의 새 `m3_hosted_timer_fixture`는 측정 후 기록이며 당시 실제 설정은 ADR/source/CLI로 추적한다. Loader는 없다.
32개 requirement/29개 system TC 전체 NOT RUN과 기존 wire/M1·M2 수용 상태를 유지한다.
문서 106개/상대 링크·앵커 1203개, YAML 3개/Python 8개 syntax·추적성·whitespace도 검사했다.
결과는 `build/m3-latency-doc-check.txt`에 보존한다.

## 2026-10-19 M4 Central 준비 판정 첫 component

[정상 주행 준비 조건](learning/m4_normal_drive_readiness.md)을 `central/vehicle_management`의
순수 library로 추가했다. 두 Zone의 health와 각각의 Steering/Brake/Drive Actual·BMS status/limits를
확인하고 모든 차단 이유 및 oldest input을 반환한다. 실제 허가 발행/상태 owner·Zone ingress/runtime는 후속이다.
새 CLI·wire 변경은 없으며 기존 request/grant fixture도 아직 유지한다.

GCC 11.4.0, GoogleTest 1.11.0으로 새 unit 16개를 더해 normal·ASan/UBSan 각각 **539/539 PASS**다.
각각의 source 상실·다른 Epoch·age 경계/미래·fault/DEGRADED, INIT actual/known zero,
원래 dependency와 BMS quality·충전/접점 조건을 검사했다. 새 일반 Debug build와 기존 sanitizer build를 사용했다.
`BUILD_TESTING=OFF` fresh build도 PASS다. Python 코드는 변경하지 않아 직전 63개 PASS 이력을 유지한다.

Clang-tidy 14의 analyzer/bugprone 검사는 변경 production/test 2개에서 PASS다.
Cppcheck 2.7은 현재 compilation database에서 production entry를 추출해 1개를 검사했다.
GoogleTest 시험 source의 cppcheck 실행은 기존 macro 파싱 제약으로 syntaxError가 발생해 완료되지 않았다.
Production 검사는 PASS이며 이를 test source 정적 분석 PASS로 확대하지 않는다.
Test source는 compiler·clang-tidy·normal/sanitizer 실행으로 검사했다.

로그는 `build/m4-readiness-{build,test,full-build,full-test,sanitized-configure,sanitized-build,sanitized-test}.txt`,
`build/m4-readiness-{clang,cppcheck,cppcheck-production,production-configure,production-build}.txt`다.
문서 링크/앵커·추적성·YAML/Python syntax는 `build/m4-readiness-doc-check.txt`에 기록한다.
이번 vCAN·wall-time 통합 workload 실행은 없으며 M3 원본 실패·32개 requirement/29개 system TC NOT RUN을 유지한다.

## 2026-10-19 M4 Central 전원·허가 상태 owner

[ADR-0044](adr/ADR-0044-central-vehicle-management-lifecycle.md)와
[학습 안내](learning/m4_vehicle_management.md)로 INIT/actual OFF·Enable/ACK·NORMAL·종료·FAIL_SAFE latch를 정의했다.
원래 요청 identity/action/time/expiry의 변경·rollback을 거부하고 active parent/grant 만료를 새 입력보다 먼저 검사한다.
허가는 현재 root·확인한 Enable child와 모든 source/dependency의 deadline 안에서만 산출한다.
Shared readiness의 input-health 경로는 초기 BMS known zero/INIT·실제 OFF/Precharge를 인정하며 HV_READY로 바꾸지 않는다.

새 모듈 시험 31개를 추가했다. 기존 준비 판정 16개를 포함해 M4 관련 47개, 전체 normal·ASan/UBSan 각각
**570/570 PASS**다. 7개 source 각각의 상실·복구 latch, root/ACK/expiry·clock/gap과 startup/shutdown timeout을 검사했다.
PowerModel + PowerController + 기존 CAN codec/독립 BmsReceiver를 연결해 10 ms씩 2.2 s **논리 시간** 동안
precharge 중 허가 차단, actual READY 후 허가, Shutdown 응답·실제 open/low bus를 통한 종료를 확인했다.
Front/Rear health·비Power Actual/limits·로컬 BMS gate는 명시적 fixture다. 신규 demo를 추가하지 않았으며
기존 EV demo/runtime의 request/grant fixture는 유지한다. 이번 SocketCAN/vCAN·wall-time workload 실행은 없다.

일반·sanitizer·BUILD_TESTING=OFF 빌드 PASS다. GCC 11.4.0/GoogleTest 1.11.0,
clang-tidy 14 analyzer/bugprone으로 변경 production/test 3개 PASS, cppcheck 2.7로 현재 compilation database의
production 2개 PASS다. GoogleTest macro의 기존 cppcheck 파싱 제약은 유지하므로 test cppcheck PASS를 주장하지 않는다.
Python 변경·unit 재실행은 없으며 직전 63개 PASS 이력을 유지한다.
개발 중 root 재전송 시험에서 11 ms 뒤에 10 ms를 전달해 clock latch가 동작한 시험 오류 1건을 수정했다.
그 43-case 개발 실행은 `build/m4-management-test-development.txt`에 보존하며 최종 47개 결과와 구분한다.
Clang-tidy가 지적한 동일 ACK 실패 분기는 공통 조건으로 정리했다. 기존 시한·고장 latch를 완화하지 않았다.
최종 검토에서 OFF 관측을 전체 peer health와 분리했다. 별도 시험으로 sender fault/다른 Zone 상실 중에도
유효 physical OFF는 보존하고 FAIL_SAFE를 유지하며, bus unknown일 때는 확인하지 않는 것을 검사했다.

빌드/시험은 `build/m4-management-{configure,build,test,full-build,full-test,sanitized-configure,sanitized-build,sanitized-test}.txt`,
production build는 `build/m4-management-production-{configure,build}.txt`, 정적 분석은
`build/m4-management-{clang,cppcheck}.txt`에 기록한다. 문서 검사는 `build/m4-management-doc-check.txt`다.
M3 기존 실패·전체 수용 대기와 32개 requirement/29개 system TC NOT RUN을 유지한다.

## 2026-10-19 M4 첫 normal-path control allocation

[ADR-0045](adr/ADR-0045-first-central-control-allocation.md)와 [학습 안내](learning/m4_control_allocation.md)에
공통 wheel Nm/Pa 변환·서비스 제동 우선·현재 BMS/capability와 원래 권한·actual 잔여 회생 보정을 기록했다.
첫 저속 hysteresis/explicit hold·observed release, 제동 구간 내 회생 목표 비증가와 response budget은
`profiles/reference.yaml:m4_allocation_fixture`의 설계 데이터이며 loader/최종 차량 calibration이 아니다.
이전 interface 문서에 남아 있던 Zone의 차량 전체 배분 책임 문구도 채택한 Central owner로 정리했다.

새 unit **36개**, 전체 normal·ASan/UBSan 각각 **606/606 PASS**다.
실제 VehicleManagement의 허가를 기존 BmsReceiver로 받아 분리된 lifecycle/vehicle root를 확인한다.
별도 motor/pressure 모델의 sensor actual→CAN encode→독립 receiver→배분→command codec/receiver→plant 적용도 시험했다.
정상 3.6 s 논리 시간(20 ms cycle)은 cap 상실/회복·coast/release/출발·재제동을 포함한다.
별도 slow-pressure/held-pressure case는 관측 오차가 budget을 넘으면 보호를 요청하며 실제 sensor 값을 0으로 바꾸지 않는다.
이 세 case는 신규 unit에 포함하며 독립 wall-time 실험 횟수로 더하지 않는다.

Component 시험의 Zone health·Steering actual·BMS power/limits/permission·speed는 명시적 fixture다.
Full Leaf response monitor, 차량 관성/타이어/경사·Battery energy loop와 실제 BMS sender DEGRADED의 허가 정책은 후속이다.
기존 EV demo/runtime fixture도 유지하며 이번 SocketCAN/vCAN·DDS·RTOS/Target/timing workload 실행은 없다.
Normal output 없음은 brake release가 아니며 `protection_required`의 실제 coordinator/Zone handoff는 다음 통합 범위다.
기존 CAN command에 없는 parent/expiry sideband를 검사한 것을 Zone end-to-end 검증으로 표시하지 않는다.

GCC 11.4.0/GoogleTest 1.11.0, native normal/sanitizer·BUILD_TESTING=OFF build PASS다.
Clang-tidy 14 analyzer/bugprone은 production/test 2개, cppcheck 2.7은 compilation database의 production 1개 PASS다.
Cppcheck가 지적한 큰 config 복사는 const reference 생성자 인자로 정리했다. Test cppcheck의 기존 GoogleTest macro 제약은 유지한다.
Python 코드는 변경·unit 재실행하지 않았으며 직전 63개 PASS 이력을 유지한다.

첫 31-case 개발 실행의 **29 PASS/2 FAIL**은 `build/m4-allocation-test-development.txt`에 보존했다.
한 case는 input>source인 malformed capability를 stale로 예상한 시험 분류 오류, 다른 하나는 CAN 압력 해상도 1000 Pa
양자화를 거친 관측과 unquantized plant truth를 직접 같다고 비교한 시험 오류였다. 수신 actual 기준으로 수정하고
0.1 Nm/1000 Pa의 quantization 차이도 따로 검사했다. Response tolerance·dwell을 그 실패에 맞춰 완화하지 않았다.
700 ms dwell은 첫 case 실행 전에 signed motor reversal/pressure delay를 고려해 정했으며 critical loss 100 ms와 별개다.
최종 검토에서는 optional capability의 만료를 critical support의 만료와 분리했다.
다음 nominal cycle까지 유효하지 않은 회생 한계는 미리 억제하고, 허용 owner gap에서 optional 한계만 만료돼도
회생 복구 없이 마찰 경로를 유지한다. 필수 source/permission expiry는 계속 latch하며 각 경로를 별도 시험했다.

로그는 `build/m4-allocation-{configure,build,test,full-build,full-test,sanitized-configure,sanitized-build,sanitized-test}.txt`,
production build는 `build/m4-allocation-production-{configure,build}.txt`, 정적 분석은
`build/m4-allocation-{clang,cppcheck}.txt`, 문서 정합성은 `build/m4-allocation-doc-check.txt`다.
M3 원래 실패와 32개 requirement/29개 system TC NOT RUN·M1/M2 learner review 상태는 유지한다.

## 2026-10-19 M4 Front/Rear scoped command admission

[ADR-0046](adr/ADR-0046-scoped-zone-command-admission.md)와
[학습 안내](learning/m4_zone_command_admission.md)의 독립 normal 명령 수용 경계를 구현했다.
Shared VehicleRequest/CommandContext/FrontCommands/RearCommands를 `interfaces/central`로 분리해
Zone이 배분 알고리즘에 의존하지 않도록 했다. Root 승인과 명령 수용은 독립 callback/cursor이며,
trusted INIT/명시적 arm·scope/atomic pair·mode/range/age/expiry와 continuity/clock latch를 검사한다.
재전송/잘못된 packet/다른 Zone 수신/새 root만으로 accepted command의 lease를 갱신하지 않는다.

새 **59개 case**, 전체 normal·ASan/UBSan 각각 **665/665 PASS**다.
실제 allocator 출력을 20 ms cycle/200 ms 논리 시간 동안 Front/Rear 수용부에 전달했다.
별도 scoped fixture로 각 source/expiry 경계·identity 변조·invalid flood·원래 만료 우선 검사,
독립 loss/reinit·더 좁은 local 설정·CAN wire 반올림 뒤 한계 초과 거부·uint64 끝의 포화 계산을 확인했다.
초기 전원 준비 동안 Idle이 유지되고 packet으로 arm/INIT할 수 없는 것도 검사했다.
정상 command lifetime 이후 보호 요청은 반환하지만 실제 보호 출력이나 물리 응답은 이 시험에서 실행하지 않는다.

일반/sanitizer·`BUILD_TESTING=OFF` build PASS, clang-tidy 14 analyzer/bugprone은 변경 production/test
4개와 새 계약/수용 header에 적용해 user-source 진단 없이 PASS다. Cppcheck 2.7은 현재 compilation
database의 production 2개 PASS다. GoogleTest macro 파싱 제약에 따른 test cppcheck 범위 제한은 유지한다.
첫 54-case 개발 실행의 52 PASS/2 FAIL은 `build/m4-admission-test-development.txt`에 보존한다.
Mutation 시험이 root lifetime 60 ms도 함께 넘겨 InvalidContext를 먼저 받은 oracle 오류였다.
Lifetime 안의 expiry 변경으로 해당 시험을 수정했으며 수용 정책/시한을 완화하지 않았다.
정적 분석 실행 중 header 주석을 편집한 중간 snapshot의 파싱 실패는
`build/m4-admission-clang-development.txt`에 보존했다. 파일을 고정한 뒤 4개 source/header 분석을 다시 통과했다.

로그는 `build/m4-admission-{configure,build,full-test,sanitized-configure,sanitized-build,sanitized-test}.txt`,
`build/m4-admission-production-{configure,build}.txt`, `build/m4-admission-{clang,cppcheck,doc-check}.txt`다.
Markdown 113개/상대 링크·앵커 1276개, YAML 3개·Python 8개 syntax/추적성/whitespace를 검사했다.
Python unit 변경·재실행은 없고 직전 63개 PASS 이력을 유지한다.
이번 SocketCAN/vCAN·DDS·wall-time workload/Target/차량 실행은 없다. 기존 EV demo의 request/grant도 fixture다.
Gateway queue/CAN egress의 원래 expiry guard·Rear lifecycle/constraint 전달·local safety handoff·실제 ingress/rejoin은 후속이다.
M3 원본 실패와 전체 수용 대기, 32개 requirement/29개 system TC NOT RUN을 유지한다.

## 2026-10-19 M4 Zone CAN gateway·local protection 연결

[ADR-0047](adr/ADR-0047-zone-can-egress-and-local-protection.md)과
[학습 안내](learning/m4_zone_gateway.md)에 bounded FIFO/최신 명령 선택·원래 sideband와 각 write 전후
expiry guard·Front partial write·독립 local safety handoff를 기록했다.
기존 Endpoint의 `send` 직렬화는 유지하고 deadline이 있는 nonblocking `send_before`를 추가했다.
별도 same-host SIL port가 실제 SteeringActuator/BrakeActuator/mandatory DriveController의
기존 Hold/Protect/Zero 출력을 선택한다. ACK는 물리 actual 도달과 구분한다.

새 component **32개**, normal·ASan/UBSan 각각 전체 **697/697 PASS**다.
독립 Front/Rear queue/clock/overflow/lease·송신 실패/지연·일부 Front frame 전송·새 INIT와
Pending 보호 재시도를 검사했다. 분리된 Leaf/물리 모델은 지연 motion/release 취소,
높은 brake pressure 유지·stuck pressure/floor 미도달, EV gate를 통한 signed torque 목표와
lease 상실 후 남은 actual/zero ramp를 확인한다. BMS/허가/HV/speed는 해당 시험의 명시적 fixture다.

두 독립 `vcan_front`/`vcan_rear` interface에서 새 native integration **각각 3/3 PASS**다.
기존 CAN receiver의 P05/원래 metadata 수용·만료 write 없음·interface 독립성을 검사한다.
해당 vCAN의 보호 ACK는 fixture이며 실제 Leaf/물리 보호 시험은 별도 component에 있다.
공통 Endpoint 변경 회귀는 기존 runner의 **97/97개 case**를 normal/sanitizer 각각 재통과했다.
Actuator observed timeout은 normal 80.013–81.209 ms, sanitizer 80.049–81.200 ms다.
이 값은 기존 local transport fixture의 관측이며 새 gateway/차량 wall-time 보장으로 확대하지 않는다.
기존 evidence를 덮지 않도록 `build/m4-gateway-can-{normal,sanitized}`에 현재 build 실행 파일의
symlink와 새 `socketcan-results`를 분리했다. 원래 M3 workload/타이밍 실패 이력은 변경하지 않는다.

일반/sanitizer·`BUILD_TESTING=OFF` build PASS다. Clang-tidy 14 analyzer/bugprone으로 변경 production/test
10개와 관련 header를 검사했다. Test port의 vector/recipient 호출에서 exception escape 가능성 1건을
수정하고 해당 source를 재검사해 user-source 진단 없이 PASS다. 최초 결과와 재검사는 각각
`build/m4-gateway-clang.txt`/`build/m4-gateway-clang-test.txt`에 보존한다.
Cppcheck 2.7은 현재 compilation database의 production 8개 PASS다. 기존 GoogleTest macro 파싱 제약에
따른 test cppcheck 범위 제한은 유지하며, test는 compiler/clang-tidy/normal·sanitizer 실행으로 검사했다.

첫 30-case 개발 실행의 29 PASS/1 FAIL은 `build/m4-gateway-test-development.txt`에 보존한다.
TorqueResponse가 INIT부터 이미 진행한 zero ramp를 oracle이 빠뜨렸다. 원래 actual을 확인한 뒤
그 residual에서 감소하는지 검사하도록 고쳤다. 후속 전체 697-case 중 696 PASS/1 FAIL은
`build/m4-gateway-integration-development.txt`다. 새 EV fixture가 BMS input time만 진행시키고
원래 causal identity를 그대로 둬 quality가 Invalid가 된 것이며, fixture identity와 Usable assertion을
고쳤다. 기존 receiver의 freshness/quality·고장 latch와 시한을 완화하지 않았다.

로그는 `build/m4-gateway-{configure,build,full-test,sanitized-configure,sanitized-build,sanitized-test}.txt`,
`build/m4-gateway-production-{configure,build}.txt`, `build/m4-gateway-{vcan,sanitized-vcan,cppcheck,doc-check}.txt`,
`build/m4-gateway-can-{regression,sanitized-regression}.txt`에 둔다.
Markdown 115개/상대 링크·앵커 1301개, YAML 3개·Python 8개 syntax/추적성/whitespace를 검사했다.
Python unit 변경·재실행은 없고 이전 63개 PASS 이력을 유지한다.
Remote CAN composite lease/protection 표현·Rear lifecycle/constraint/startup·실제 ingress/status 감시와
full runtime/timing/Target/system TC는 후속이다. M3 원래 실패·전체 수용 대기와 32개 requirement/29개 TC NOT RUN을 유지한다.

### 2026-10-19 — Rear 전원/허가/limits와 non-driving startup

[ADR-0048](adr/ADR-0048-rear-power-routing-and-nondriving-startup.md)과
[학습 기록](learning/m4_rear_power_startup.md)에 경계·시동 순서·reviewed DEGRADED envelope를 기록했다.
독립 lifecycle root 승인→RearPowerGateway→기존 Power/Drive receiver, source/parent/expiry 보존,
실제 송신 Enable ACK 뒤 explicit arm/AllowNormal을 연결했다. 기존 EV wire/시한·기본 Drive Immediate는 유지한다.
NonDriving은 normal torque receiver만 arm까지 대기하며 limits/permission/local HV/speed 감시는 계속한다.
정차 중 known regen Disabled와 정상 BMS derating만 제한적으로 허용하고 고장/unknown/stale은 계속 차단한다.

Startup7·readiness3·Rear19개를 추가해 normal·ASan/UBSan **각각 C++ 726/726 PASS**다.
1.6 s 논리 시간 연결에서 실제 VehicleManagement/PowerController/RC·접점/DriveController/torque plant와
allocator·정상 gateway를 사용했다. >80 ms precharge 동안 normal torque packet 0개·actual motor0,
actual Ready/ACK 뒤 명시적 arm·첫 normal Sequence0·실제 구동을 확인했다. 마지막 Rear 상실은
실제 Drive Zero/Power inhibit를 선택하고 actual torque 잔류·닫힌 접점을 유지한다. 다음 tick은 WaitCurrent다.
Front actual·Zone health·BMS limits/safety·pack400 V/load0 A·speed0은 fixture이며 full BMS/SOC/차량 loop가 아니다.
정상 종료→전원 종료의 전체 coordinated stop을 검증한 것은 아니다.

분리 vCAN은 normal·sanitizer **각각 4/4 PASS**다. 기존 Front/Rear3개와 새 Rear BMS3-stream
(PowerRequest/DriveBatteryLimits/DrivePermission)의 기존 Leaf 수신·별도 trusted 발급 context 대조를 확인했다.
발급 history16개는 trusted TX에서만 생성하며 exact envelope에서 optional FDF0x04 표시만 제외한다.
BRS/ESI·payload/ID/length 불일치와 만료·새 INIT은 context를 회수하지 못한다. DDS 인증/remote protocol은 아니다.
기존 transport도 격리 netns에서 **각각 97/97 PASS**다. Fresh symlink build 경로
`build/m4-rear-can-{normal,sanitized}`에 로그를 분리해 과거 evidence를 보존했다.
Observed actuator timeout은 normal **80.002–81.109 ms**, sanitizer **80.052–81.112 ms**다.
이는 기존 local transport 관측이며 이번 gateway/전체 차량 wall-time 보장으로 확대하지 않는다.

Normal·ASan/UBSan·BUILD_TESTING=OFF production build를 통과했다. 현재 compilation database로
변경 production7개에 cppcheck2.7 warning/performance/portability를 적용해 진단 없이 통과했다.
Production7개+test4개에 clang-tidy14 analyzer/bugprone을 적용했다. 확장 header filter에서 기존
`DriveSilPlant::begin(model_epoch, now_ns)`의 easily-swappable-parameters 경고 1종(3 TU에서 반복)을 기록했다.
새 test helper의 같은 경고는 named stamp 인자로 수정·재검사했고 새 source/test 진단은 없다.
Third-party suppressed 진단과 기존 GoogleTest/cppcheck macro 제약을 전체 repo PASS로 바꾸지 않는다.

첫 개발 cohort **723개 중 722 PASS/1 FAIL**은 `build/m4-rear-test-development.txt`에 보존한다.
기존 blanket DEGRADED 거부 시험의 BMS Disabled0이 새 reviewed envelope에 들어간 경우였다.
해당 fixture를 양 방향 Nominal인 미검토 DEGRADED로 바꿨고 fault/unknown 차단 검사는 유지했다.
첫 vCAN **3 PASS/1 FAIL**은 `build/m4-rear-vcan-development.txt`다. Linux RX의 optional FDF4와
TX0 표현 차이 때문에 발급 frame을 찾지 못했다. FDF만 정규화하고 BRS/ESI·payload mismatch 시험을 추가했다.
실패를 삭제하거나 안전 시한/입력 validity를 완화해 통과시키지 않았다.

로그는 `build/m4-rear-{build,build-final,full-test,sanitized-configure,sanitized-build,sanitized-build-final,sanitized-test}.txt`,
`build/m4-rear-production-{configure,build}.txt`, `build/m4-rear-{vcan,sanitized-vcan,clang-tidy,clang-tidy-final,cppcheck,doc-check}.txt`,
`build/m4-rear-can-{regression,sanitized-regression}.txt`와 각 socketcan-results에 둔다.
Markdown117개/상대 링크·앵커1334개·추적성, YAML3개·Python8개 syntax와 whitespace를 검사했다. Python unit은 변경/재실행하지 않았다.
M4는 component 구현 중이며 Front startup·정상 종료·remote normal Leaf lease/보호·독립 ingress/status/rejoin·
전체 runtime/timing/DDS/Target은 후속이다. M3 원래 실패·학습자 수용 대기와 requirement32/TC29 NOT RUN도 유지한다.

### 2026-10-19 — Front NonDriving·pair arm과 양 Zone 시동 연결

[ADR-0049](adr/ADR-0049-front-nondriving-startup-and-paired-arm.md)와
[학습 기록](learning/m4_front_startup.md)에 Front 초기 대기/arm·센서/clock 감시와 정상 종료의 후속 경계를 기록했다.
Shared ActuatorCommandStartup을 사용하고 DriveCommandStartup 이름은 alias로 유지한다.
기본 Immediate 회귀는 유지하며 NonDriving은 normal receiver만 늦게 시작한다. 두 Front Leaf는
센서/period/clock 감시·INIT Actual을 계속하고, trusted FrontStartupControl이 두 Leaf/gateway를 preflight/arm한다.
Wrong scope/Epoch나 준비 미완료는 거부, fault·commit 실패는 gateway latch와 두 Leaf Hold/Protect다.

Steering startup9·Brake startup9·Front binding6개를 더해 normal·ASan/UBSan **각각 C++750/750 PASS**다.
기존726개 첫 회귀도 PASS였다. 새23개 첫 실행과 실제 양 Zone 확장 후 실행도 각각749/749 PASS다.
초기1 s 대기/센서·period/clock 감시, pre-arm packet·arm 이전 source 거부, 첫 normal Sequence0,
캐시/만료/누락 센서·새 INIT의 old causal 억제/physics 보존, arm 기준80 ms·gateway commit 실패를 검사했다.
Actual publication sequence와 물리 model/sensor는 arm에서 reset하지 않는다.

기존1.6 s 논리 시간 Rear 시험의 Front actual fixture를 실제 Steering/Brake controller·별도 angle/pressure
plant·독립 CAN Actual receiver로 교체했다. 프리차지 중 angle0.1 rad/pressure0.2 MPa를 유지하고
normal command는0개다. 두 Zone arm 뒤 세 normal command Sequence0·angle 변화/pressure release·실제 구동을 확인했다.
Zone health/BMS limits/safety·pack400 V/load0 A·외부 speed0은 fixture다. Full vehicle/BMS energy/SOC·
독립 ingress/status·상실 이후 전체 coordinator/Front 반응은 후속이다. 기존 Rear 보호/WaitCurrent 검사는 유지했다.

분리 vCAN은 normal·sanitizer **각각5/5 PASS**다. 새 Front case는 실제 CAN의 pre-arm Sequence9 거부 후
trusted arm/첫 정상 Sequence0 pair의 실제 Leaf 수신을 검사한다. 센서는 acquisition fixture이며 물리 반응은 component 범위다.
기존 local transport도 **각각97/97 PASS**다. `build/m4-front-can-{normal,sanitized}`의 fresh symlink 경로로
이전 결과를 보존했다. Observed actuator timeout은 normal **80.033–81.183 ms**, sanitizer **80.013–81.226 ms**다.
이는 local transport 관측이며 새 startup/full workload timing 보장으로 확대하지 않는다.

Normal·ASan/UBSan·BUILD_TESTING=OFF production build를 통과했다. 변경 production5개·test5개에
clang-tidy14 analyzer/bugprone을 적용했다. 새 Front arm의 epoch/time 인자 교환 경고는
FrontArmContext로 묶어 수정·재검사했고 새 source/test 진단은 없다. 확장 header filter에서 기존
DriveSilPlant::begin의 easily-swappable-parameters 경고1종이 두 test TU에서 반복된 기록은 유지한다.
Cppcheck2.7 warning/performance/portability는 production5개를 현재 compilation database로 검사·재검사해 진단 없이 통과했다.
GoogleTest macro/third-party 도구 범위와 이전 RTOS/ARM64 build 이력은 그대로 구분한다.

개발 중 다른 optional frame 타입을 한 auto 선언에 묶은 오류와 void Endpoint::send를 bool로 검사한
새 test compile 오류를 수정했다. 이 시점 실행된749-case cohort는 모두 PASS였다. 각각
`build/m4-front-integration-build.txt`/`build/m4-front-build-final.txt`에 compile 진단을 보존했다.
추가 review에서 advancing gateway clock 뒤의 두 번째 보호 callback이 과거 context 시각을 사용해
SensorUnavailable을 ClockError로 덮는 문제를 발견했다. 새1-case 회귀의 **0 PASS/1 FAIL**은
`build/m4-front-handoff-development.txt`에 보존했다. Leaf preflight를 gateway poll보다 먼저 하고,
명시적 보호에 max(context time, gateway observed time)을 사용한 뒤 gateway 보호를 요청하도록 수정했다.
고정 clock으로 문제를 숨기지 않았으며 final750개는 두 build 모두 PASS다. 변경 binding/회귀는
`build/m4-front-handoff-clang-tidy.txt`에 재검사하고 production5개 cppcheck도 재통과했다.
로그는 추가로 `build/m4-front-handoff-build{,-final}.txt`, `build/m4-front-sanitized-build-verified.txt`,
`build/m4-front-production-build-verified.txt`에 보존한다.
정상 종료는 현재 VM의 Inhibit/Shutdown과 active Drive fault의 구분이 필요해 후속 계약으로 남겼다.
안전 시한·unknown 거부를 완화하거나 정상 종료를 위해 고장 latch를 지우지 않았다.

로그는 `build/m4-front-{configure,build,baseline-test,build-tests,unit-development,integration-build-final,integration-development}.txt`,
`build/m4-front-{build-vcan-final,build-verified,full-test,sanitized-configure,sanitized-build,sanitized-build-final,sanitized-test}.txt`,
`build/m4-front-production-{configure,build,build-final}.txt`, `build/m4-front-{vcan,sanitized-vcan,clang-tidy,clang-tidy-final,cppcheck,cppcheck-final,doc-check}.txt`,
`build/m4-front-can-{regression,sanitized-regression}.txt`와 socketcan-results에 둔다.
Markdown119개/상대 링크·앵커1364개·추적성·YAML3개·Python8개 syntax·whitespace를 검사했다. Python unit 변경/재실행은 없다.
M4 전체 완료·M3 타이밍 예외 해소·Target/system PASS로 확대하지 않는다. Requirement32/TC29는 NOT RUN이다.

### 2026-10-19 — NormalStop·terminal lease와 정상 HV 종료

[ADR-0050](adr/ADR-0050-controlled-stop-and-terminal-handoff.md)와 [학습 기록](learning/m4_normal_stop.md)에
stop intent/issuer 계보·actual dwell·terminal handoff/lease→Inhibit/Shutdown→actual OFF/ACK를 기록했다.
NormalStop은 기존 issuer의 trusted 다음 sequence를 인계받고 자식 root의 expiry를 원래 stop authority 안에 둔다.
HandoffPending의 ancestor/token/deadline은 고정이며 새 intent나 중복 lease로 연장하지 않는다.
Scope/epoch/원래 ancestor를 대조한 same-host binding은 세 Leaf·allocator/양 Zone를 넘기며 부분 실패는 모두 보호한다.
Monitor와 plant의 지연된 정상 목표를 취소하고 physical state/sensor identity·fault를 보존한다.
VM은 Stopping/Stopped에서 fresh Shutdown만 갱신하며 Enable 취소와 phase timer 재시작을 허용하지 않는다.

Stop/lease16개·VM 갱신1개·Rear terminal1개·통합5개를 더해 normal·ASan/UBSan **각 C++773/773 PASS**다.
기존750개 첫 회귀와 초기 Stop unit 포함761개도 각각 PASS다. 별도3.2 s 논리 시간/10 ms·배분20 ms에서
실제 controller·세 actuator plant/독립 Actual receiver·양 Zone/VM/allocator·PowerController/RC/접점을 연결했다.
1200 ms stop intent→새 actual 확인60 ms→Hold/Zero 선택→정상 frame TX 중단→Inhibit/current/open/discharge→
VM Stopped·actual OFF/ACK를 fault reset 없이 확인했다. 이후 positive torque/release CAN·arm은 거부한다.
Complete 뒤에도 LV 센서와 terminal lease를 유지하는 fixture이며 ECU 전원 차단/parking brake는 아니다.

Root/lease/source/sequence/epoch·immutable duplicate/late renewal·cached dwell·누락 actual·fake OFF ACK·
제동/전원 종료 timeout·pending token 만료·issuer exhaustion과 local pressure/speed·lease 상실/부분 인계를 검사했다.
정지 speed는 allocation의 hold entry0.5와 구분해 wheel-speed 한 step인 **0.01 rad/s**로 정했다.
Torque0.1 Nm·hold0.1 MPa는 기존 release/hold fixture를 따른다. 제동1 m/s²·확인60 ms·braking5 s는
첫 SIL 설정이며 차량 calibration/정지 거리 검증이 아니다. Speed20→0 script·Zone health·BMS limits/safety·
pack400 V/load0 A는 명시적 fixture다. 차량 운동/BMS energy/SOC·분산 coordinator/전체 workload timing은 후속이다.

분리 vCAN은 normal·sanitizer **각5/5 PASS**다. 기존 Front case에 terminal 선택 후 실제 CAN의 다음
normal command 거부와 accepted sequence 보존을 더했다. Wire/CRC/schema는 바꾸지 않았다.
기존 local transport도 **각97/97 PASS**다. Fresh `build/m4-stop-can-{normal,sanitized}` symlink 경로로
이전 evidence를 보존했다. Observed timeout은 normal **80.056–81.189 ms**, sanitizer **80.005–81.033 ms**다.
이는 기존 local transport 관측이며 stop/차량 wall-time 보장으로 확대하지 않는다.

Normal·ASan/UBSan·BUILD_TESTING=OFF production build를 통과했다. 변경 production13개·test4개에
clang-tidy14 analyzer/bugprone을 적용했다. 새 unit helper의 adjacent double 경고는 named readings로 묶고,
cppcheck의 aggregate-copy 지적은 const reference로 수정·재검사했다. 새 source/test 진단은 없다.
확장 header의 기존 DriveSilPlant::begin easily-swappable-parameters 경고1종(test1 TU)은 보존한다.
Cppcheck2.7 warning/performance/portability는 현재 compilation database의 production13개를 재검사해 진단 없이 통과했다.
Pending ancestor/lease 관계 보강 후 변경3 TU clang-tidy와 production13개 cppcheck도 재통과했다.
Third-party suppressed 진단/GoogleTest macro 제약과 기존 RTOS/ARM64 build 이력은 따로 구분한다.

첫 통합 실행 **763개 중761 PASS/2 FAIL**은 `build/m4-stop-integration-development.txt`에 보존한다.
VM이 Stopping 이후 같은 Shutdown root 갱신도 RestartRequired로 거부해 정상 완료 전에 요청을 유지할 수 없었다.
Shutdown만 갱신하도록 수정하고 Enable 거부/timeout 비연장·만료 root의 local restrictive shutdown을 유지했다.
후속763/763 이후 경계/terminal 회귀를 더했다. Test if/GoogleTest brace와 grouped stamp 인자 compile
오류는 각각 `build/m4-stop-test-build.txt`/`build/m4-stop-boundary-build.txt`에 보존했다.
Normal CAN/BMS source budget·unknown 거부를 완화하거나 INIT로 fault를 지워 통과시키지 않았다.

로그는 `build/m4-stop-{core-build,baseline-test,component-build,component-baseline,test-build-fixed,test-development}.txt`,
`build/m4-stop-{integration-build,renew-build,renew-development,boundary-build-fixed,boundary-test,build-verified,guard-build,final-build,ancestry-build,full-test}.txt`,
`build/m4-stop-{sanitized-configure,sanitized-build,sanitized-build-final,sanitized-build-verified,sanitized-test}.txt`,
`build/m4-stop-production-{configure,build,build-final,build-verified}.txt`,
`build/m4-stop-{vcan,sanitized-vcan,clang-tidy,clang-tidy-final,ancestry-clang-tidy,cppcheck,cppcheck-final,cppcheck-verified,doc-check}.txt`,
`build/m4-stop-can-{regression,sanitized-regression}.txt`와 socketcan-results에 둔다.
Markdown121개/상대 링크·앵커1397개·추적성·YAML3개·Python8개 syntax·whitespace를 검사했다. Python unit 변경/재실행은 없다.
전체 ingress/status/rejoin·remote Leaf composite lease/stop transport·DDS·통합 timing/Target은 남아 있다.
M4 전체 완료/실차 정지 성능·M3 원래 실패 해소로 확대하지 않는다. Requirement32/system TC29는 NOT RUN을 유지한다.

### 2026-10-19 — 실제 Zone feedback health·독립 status ingress

[ADR-0051](adr/ADR-0051-zone-feedback-health-and-status-ingress.md)과 [학습 기록](learning/m4_zone_feedback_health.md)에
실제 gateway/담당 원천→Zone phase/health→독립 Front/Rear status receiver→Central 연결을 기록했다.
공통 Leaf health 정책은 interfaces/zone으로 옮겨 Zone/Central이 같은 INIT/제한 DEGRADED·source/dependency/quality
기준을 사용한다. 기존 readiness/VM/allocator·Stop 단위 fixture는 실제 phase/scope를 명시하도록 갱신했다.
실제 controller/모델/CAN receiver 연결 시험의 항상 정상인 Zone health fixture는 제거했다.
Ready/Active는 정상 준비 입력이며 실제 permission은 아니다. Terminal은 종료 input health에만 사용할 수 있다.

각 원천은 첫 대기80 ms·유효 입력 상실 시 latch, 명시적 보호는 즉시 선택한다. Status는 관찰 완료 시각을 갖지만
자식의 원래 시각을 바꾸지 않는다. 독립 ingress는 old source30 ms 초과를 late replacement 전에 latch하며
scope/phase/metadata·Epoch·sequence·strict source를 검사한다. 중복/거부는 liveness를 갱신하지 않는다.
통신 재개나 같은 Epoch의 정상 보고로 FailSafe/Terminal을 되돌리지 못한다. 복구는 각 참여자의 더 큰 trusted INIT다.
Gateway callback 중 정상적인 clock 진행을 허용하고 완료 시각에서 입력 age를 다시 검사한다.

Normal·ASan/UBSan **각 C++795/795 PASS**, BUILD_TESTING=OFF production build도 PASS다.
기존773개 + monitor/status15개·Central Terminal1개·기존 실제 모델 연결 loss/partition6개다.
시동/정상 종료3.2 s 논리 시간 연결의 status를 실제 monitor/receiver로 교체했다. Actual 전송 누락·한쪽 status
partition·명시적 continuity를 주입하고 Central FAIL_SAFE/Inhibit·양 Zone Hold/Protect/Zero 선택을 확인했다.
독립 component에서 첫 대기·원천 age 경계/재발행·각 stream 첫 유효 뒤 상실·clock/period·INIT/rejoin·old Epoch·
Terminal/FailSafe 역행·잘못된 scope/phase·callback 중 clock 진행/입력 만료를 검사했다.

Clang-tidy14 analyzer/bugprone을 production4개·test6개에 적용했다. 새 source/test 진단은 없다.
기존 DriveSilPlant::begin의 인자 순서 경고1종이 연결 시험/allocator 시험2 TU에서 보이며 그대로 보존한다.
Clock 보완 뒤 변경2 TU를 재검사해 새 진단 없이 통과했다. Cppcheck2.7 warning/performance/portability는
현재 compilation database의 production4개를 검사하고 clock 수정 뒤 재통과했다.
Third-party suppressed 진단과 GoogleTest cppcheck macro 제약은 기존 정책을 따른다.

기존 분리 vCAN은 normal·sanitizer **각5/5 PASS**, legacy local CAN도 **각97/97 PASS**다.
Status의 wire 검증은 아니며 codec/P05/CAN schema는 바꾸지 않았다. 새 symlink 디렉터리
`build/m4-zone-feedback-can-{normal,sanitized}`와 별도 socketcan-results로 이전 evidence를 보존했다.
Local application timeout은 normal **80.122–81.048 ms**, sanitizer **80.025–81.060 ms**다.
이는 local transport 관측이며 전체 차량/Zone wall-time 보장으로 확대하지 않는다.

첫 개발 build의 SteeringMessage metadata base cast 오류는 `build/m4-zone-feedback-build.log`에 보존하고
명시적 필드 복사로 수정했다. 첫791개 실행은 **787 PASS/4 FAIL**이며
`build/m4-zone-feedback-ctest-development.log`에 남겼다. 기존 permission/command expiry 또는 allocator skew가
새 시험의 다음 정상 ingress/배분 기대보다 먼저 보호할 수 있었다. 정상 조건을 완화하는 대신 전송 누락을
명시적1010 ms부터 주입하고,1040 ms 원천 만료 경계에서는 보호 상태 관찰을 정상 CAN 재전송보다 먼저 수행한다.
후속791/793 및 clock 보강795개 회귀를 통과했다. 실제 multithread coordinator의 순서/지연을 검증한 것은 아니다.

최종 build/unit 로그는 `build/m4-zone-feedback-{configure,build-final,ctest-normal,sanitized-configure,sanitized-build,ctest-sanitized,production-configure,production-build}.log`,
`build/m4-zone-feedback-clock-{build-normal,build-sanitized,build-production,ctest-normal,ctest-sanitized}.log`다.
정적 분석은 `build/m4-zone-feedback-{tidy-summary,tidy-*,cppcheck,clock-tidy,clock-cppcheck}.log`,
vCAN은 `build/m4-zone-feedback-{vcan-normal,vcan-sanitized,can-normal,can-sanitized}.log`에 둔다.
Markdown123개/상대 링크·앵커1419개·추적성·YAML3개·Python8개 syntax·whitespace를 검사했다.
문서 검사 최종 로그는 `build/m4-zone-feedback-doc-check.log`다. Python unit 변경/재실행은 없다.
전체 coordinator/runtime·실제 rejoin transaction·remote Leaf composite lease/stop/protection·DDS/clock mapping·
차량 운동/BMS energy 연결·전체 workload timing/Target은 후속이다. M4 전체 완료나 M3 예외 해소로 확대하지 않는다.
Requirement32/system TC29는 NOT RUN을 유지한다.

### 2026-10-19 — MBD 개발 경로 계획 추가

[ADR-0052](adr/ADR-0052-model-based-design-development-path.md)로 MBD 방법을 채택하고
[개발 계획](engineering_plan.md#model-based-design-path)·로드맵·검증 계층·현재 상태/학습 안내를 갱신했다.
첫 대상은 Central 종방향 속도 제어다. M6 모델/plant·MIL→M8 수작업 C++와 동등성·차량 SIL로 배치했다.
모델/코드의 공통 vector·초기 state·numeric/solver/sample time·수치/상태 비교와 차량 성능 판정을 구분한다.
모델이 구현 함수를 공유해 자기 자신과 비교하는 것을 독립 설계 검증으로 표시하지 않는다.
도구/허용 오차·선택적 code generator 결정은 owner/gate가 있는 TBD-16으로 등록했다.
Simulink 구매/설치·자동 생성 도입은 미확정이며 MBD 구현/실행은 PLANNED / NOT RUN이다.

문서 변경만 수행했다. C++/Python 실행 코드·CMake·YAML·wire와 requirement32/system TC29 정의·Result는 바꾸지 않았다.
기존 C++795개·CAN97개/분리 vCAN5개의 normal/sanitizer PASS는 직전 단계 이력이며 이번에 재실행하지 않았다.
Markdown124개/상대 링크·anchor1436개·fence·추적성·YAML3개 설계 budget·Python8개 syntax·whitespace 검사를 통과했다.
검사 로그는 `build/mbd-plan-doc-check.log`다. 새 모델/MIL/동등성 검증의 PASS로 기존 이력을 전용하지 않는다.

### 2026-10-19 — 단일 Central coordinator·실제 same-host 연결

[ADR-0053](adr/ADR-0053-central-coordinator-and-same-host-binding.md)과 [학습 기록](learning/m4_vehicle_coordinator.md)에
VehicleManagement/ControlAllocation/NormalStop의 private 소유·10/20 ms 순서·root/issuer 인계·부분 실패 보호를 기록했다.
Same-host port는 실제 Front/Rear/Rear-power gateway·Steering/Brake/Drive/Power·permission RX를 연결한다.
기존 실제 시동/정상 종료·Zone health/Actual 상실 시험에서 수동 Central 호출을 coordinator API로 교체했다.
물리 모델이나 remote reset을 coordinator가 소유하지 않는다. Existing NormalStopControl의 직접 allocator binding은 유지하고
coordinator가 자체 allocator를 quiesce한 뒤 Leaf/gateway만 선택하는 binding도 지원한다.

Normal·ASan/UBSan **각 C++820/820 PASS**다. 기존795개 + coordinator20개·실제 연결5개다.
미초기화/참여자 preflight·중복/mutation·초기 missing input·scope/Epoch/source 상실·root 전달/arm/power/command 실패·
callback gap/clock rollback·stop issuer/우선권·부분 handoff/옛 stop 권한 만료와 보호 재시도 상한을 검사했다.
실제 연결5개는 partial arm·Power TX·Front partial TX·Central permission RX 상실·한 gateway만의 새 Epoch다.
기존 RC/접점·angle/pressure/torque·실제 controller/CAN receiver·Zone monitor의 정상 종료3.2 s 논리 시간과
lease/압력/속도·Actual/독립 status loss 시험도 새 coordinator에서 통과했다. BMS limits/safety·pack/load·speed는 fixture다.

실제 permission ingress를 새 발급 grant로 대체하지 않는다. Early VM tick에서는 이전 출력을 다시 보내지 않고,
변경 없는 issued parent context만 보관해 실제 current permission을 대조하며 독립 allocation runnable을 계속 감시한다.
Clock jitter로 VM이 early가 되는 case와 기존 allocation 지원 만료를 새 root 수용에서 즉시 전달하는 경계를 추가했다.
Active Shutdown 우회·stop 뒤 정상 ingress·same-Epoch/부분 새 Epoch 복구를 차단한다. 보호 선택 ACK는 물리 완료가 아니다.

Normal·sanitizer·BUILD_TESTING=OFF production build를 통과했다. Clang-tidy14 analyzer/bugprone으로
production3개·test2개를 검사해 새 source/test 진단은 없다. 기존 DriveSilPlant::begin 인자 순서 경고1종은 연결 시험 TU에서 보존한다.
Cppcheck2.7 warning/performance/portability는 compilation database의 변경 production3개를 진단 없이 통과했다.
Third-party suppressed 진단/GoogleTest cppcheck macro 제약과 기존 RTOS/ARM64 build 이력은 구분한다.

분리 vCAN은 normal·sanitizer **각5/5 PASS**, legacy local CAN도 **각97/97 PASS**다.
Wire/CRC/schema 변경은 없다. 새 `build/m4-coordinator-can-{normal,sanitized}` symlink/socketcan-results에 기록했다.
Local application timeout은 normal **80.038–81.119 ms**, sanitizer **80.012–80.992 ms**다.
이는 기존 local transport 관측이며 coordinator·차량 workload wall-time 보장이 아니다.

첫813개 회귀는 **808 PASS/5 FAIL**로 `build/m4-coordinator-ctest-development.log`에 보존했다.
새 단위 fixture가 정상 vehicle root를 갱신하지 않아 기존 지원 만료를 넘어서 새 root/stop을 기대했다.
정상 fixture에서30 ms root를 제공한 뒤40 ms에 배분하도록 수정했고 source/지원 만료 기준은 유지했다.
후속818개 통과 뒤 early tick/즉시 만료 전파 경계를 더해820개를 재통과했다. 만료 뒤에는 새 root로 복구하지 않는 test도 유지한다.

로그는 `build/m4-coordinator-{configure,build-development,ctest-development,integration-build,integration-ctest,build-verified,ctest-normal}.log`,
`build/m4-coordinator-{sanitized-configure,sanitized-build,ctest-sanitized,production-configure,production-build}.log`,
`build/m4-coordinator-{tidy-summary,tidy-*,cppcheck,vcan-normal,vcan-sanitized,can-normal,can-sanitized,doc-check}.log`다.
Markdown126개/상대 링크·anchor1459개·fence·추적성·YAML3개 설계 budget·Python8개 syntax·whitespace를 검사했다. Python unit 변경/재실행은 없다.
새 coordinator를 기존 EV demo/runtime에 배포하거나 독립 thread/process·DDS/Host feedback bridge를 실행한 것은 아니다.
전체 remote INIT/ACK/rejoin·영속 Epoch 연결·remote composite lease/stop/protection·새 workload timing/Target은 후속이다.
M4 전체 완료·M3 예외 해소나 requirement32/system TC29 PASS로 확대하지 않는다. MBD는 계획대로 M6–M8 후속이다.

### 2026-10-19 — 세션 owner loop·8-role INIT/rejoin·물리 reset 경계

[ADR-0054](adr/ADR-0054-trusted-session-owner-loops.md)와 [학습 기록](learning/m4_session_bootstrap.md)에
Prepare→future enable/INIT→Central commit→Release ACK/global gate를 기록했다.
Front/Rear Zone·Steering/Brake/Drive/BMS/Power·Central ingress의8개 role을 같은 plan으로 준비한다.
영속 Epoch 발급은 explicit startup에서 수행하며 runnable·CAN/ACK가 새 grant를 만들지 않는다.
원래 deadline·immutable ACK·bounded capacity8 SPSC와 role별 처리 budget을 유지한다.
부분 INIT rollback/같은 Epoch 재시도는 허용하지 않고 보호 뒤 더 큰 durable grant를 요구한다.
Overflow 링크는 즉시 run gate를 닫으며 join/transport 교체 없이 새 Epoch로 복구하지 않는다.

Normal·ASan/UBSan **각 C++846/846 PASS**다. 이전820 + session23·실제 actor 연결2·durable grant 연결1개다.
모든 단계 ACK·wrong scope/plan/phase/source·duplicate/mutation·원래 timeout·owner gap/clock rollback·uint64 경계,
negative ACK·부분 send/commit 실패·callback overrun·준비 Pending 중 보호 service·유실 Prepare/Release/Abort,
부분 INIT·new Epoch 복구·queue wrap/overflow/잘못된 role 링크와 다음 step 전 gate 폐쇄를 검사했다.
8개 독립 owner thread는 typed mailbox와 자기 port 접근을 검사한다. 논리 clock/barrier이며 wall-time 실시간 판정은 없다.
Callback 뒤 clock을 다시 읽으므로 앞 owner가 시간을 사용한 뒤 다음 메시지를 이전 시각으로 검사하지 않는다.

실제 binding은 controller/gateway/monitor·Actual/permission/Zone status RX를 role별 INIT한다.
정지·토크·접점 open/잔류 bus·same model identity와 source/dependency freshness를 준비·실제 enable에서 각각 확인한다.
실제 actor 시험은 continuing physical acquisition·application1→실패2→명시적3 재가입을 수행한다.
Angle/pressure/torque·RC contacts/bus·Battery SOC와 model Epoch7이 초기화되지 않음을 확인했다.
다른 case는 Prepared 뒤 bus sensor 변화가 실제 INIT를 거부하고 Central commit이 일어나지 않음을 검사한다.
이 startup fixture는 정상 producer가 없고 BMS 부하/에너지 loop를 실행하지 않는다. 기존 drive fixture의 speed/BMS limits 제약은 유지한다.

Native normal/sanitizer·**Release BUILD_TESTING=OFF** build를 통과했다.
Release 첫 build에서 기존 Zone feedback의 optional ternary에 GCC `-Wmaybe-uninitialized`가 발생했다.
Power poll 결과를 존재 조건 안에서 바로 bool로 평가하도록 동등하게 정리해 경고 비활성화 없이 재통과했다.
첫 실패 로그 `build/m4-session-production-build.log`는 보존하며 수정 후 결과는 `build/m4-session-production-build-verified.log`다.
첫842개·추가845개 검사도 각각 normal/sanitizer 통과했고, 마지막 link-failure gate case를 더해846개를 검증했다.
Clang-tidy14 analyzer/bugprone은 변경 production4개·test3개와 포함 header를 검사했다.
새 user-source 진단은 없으며 기존 DriveSilPlant::begin 인자 순서 경고1종은 실제 actor test TU에 보존한다.
Cppcheck2.7 warning/performance/portability는 현재 compilation database의 production4개를 진단 없이 통과했다.

분리 gateway vCAN은 normal/sanitizer **각5/5 PASS**, 기존 local CAN은 **각97/97 PASS**다.
Local application timeout은 normal **80.008–80.888 ms**, sanitizer **80.006–81.050 ms**다.
Wire/CRC/schema를 바꾸지 않았다. 이 회귀는 session protocol을 network로 전송한 결과나 새 정상 workload timing 보장이 아니다.
추적 로그는 `build/m4-session-can-{normal,sanitized}/socketcan-results`에 둔다.

빌드·unit 로그는 `build/m4-session-{configure,build,ctest-normal,sanitized-configure,sanitized-build,ctest-sanitized}.log`,
`build/m4-session-{build-final,ctest-final-normal,sanitized-build-final,ctest-final-sanitized}.log`,
`build/m4-session-{build-verified,ctest-verified-normal,sanitized-build-verified,ctest-verified-sanitized,production-configure,production-build-verified}.log`다.
정적/transport/문서 로그는 `build/m4-session-{tidy-summary,tidy-*,cppcheck,vcan-normal,vcan-sanitized,can-normal,can-sanitized,doc-check}.log`다.
Markdown128개/상대 링크·anchor1483개·fence·요구32/TC29 추적성·YAML3개 budget·Python8개 syntax/whitespace도 통과했다. Python unit 변경/재실행은 없다.

현재 실제 actor 연결은 직렬 same-host다. 기존 synchronous normal/protection port를 여러 thread에서 호출하지 않는다.
정상 요청/arm/TX 결과·status/Actual/보호의 owner별 비동기 port·global gate 연결과 기존 EV runtime fixture 교체가 다음이다.
전체 runtime의 독립 정지/partition·timing·remote INIT/Leaf lease wire·DDS/Host feedback bridge는 후속이다.
M4 전체 완료·M3 예외 해소·requirement32/system TC29 PASS로 확대하지 않는다. MBD는 M6–M8 계획을 유지한다.

## 2026-10-19 M4 정상 owner 비동기 통합과 재현 근거

[ADR-0055](adr/ADR-0055-asynchronous-normal-owner-integration.md)에서 앞선 session owner 위에
Central/Front/Rear/다섯 Leaf/Physical의9개 owner를 연결했다. 방향별 정상 FIFO·정확한 TX result/arm/terminal ACK,
별도 priority protection·global epoch gate·원래 root/parent/expiry를 사용한다. 실제 BMS 판단/RC·접점/센서→Actual을 연결했다.
동기 port를 여러 thread에서 공유하지 않는다. CLI는 기존 actuator_demo의 m4-async이며 durable grant는 thread 시작 전에 발급한다.

첫 port 단위 commit `439f5fa`는846+11=857개 normal PASS였다. 최종 코드 **`117ebc002e2927d0886b8e6407497de716772adb`**는
846+async port13+runtime11+INIT wake1+optional capability1=**872개**, normal·ASan/UBSan **각각872/872 PASS**다.
8개 논리 scenario·고정 grant17의 부분 실패, native 정상/Actual 상실2개, durable CLI 재가입 각각1개를 포함한다.
같은 CTest/JUnit을 재사용해 [대표20개 함수·시험·판정·실제 결과](test-plan/evidence/m4_async/component_results.csv)를 연결했다.
[최소 공유 근거](test-plan/evidence/m4_async/README.md)에 대상 commit/source SHA256·환경·명령·입력·수치/CSV·그래프를 보존했다.

Native wall은 Linux6.8/GCC11.4 Debug, SCHED_OTHER·CPU0–15 허용·별도 부하 없음·각1.8s/조건1회다.
Actual 상실 주입→전체 보호 선택 ACK는 normal11.848ms/sanitizer12.976ms, 두 wall 조건의 owner body 최대는
normal184.272μs/sanitizer1203.494μs며4ms 초과 관측은0회다. 논리 fault/보호22ms 내·물리 압력 도달은 다른 clock/endpoint다.
이는 M3 선택 FIFO/CPU map·독립 감시·부하/장기 반복 결과나 기존 timing 예외의 해소 근거가 아니다.

Normal·sanitizer 기존 vCAN97개씩·gateway/startup5개씩도 재통과했다. Actuator timeout은
normal80.019–81.029ms, sanitizer80.107–81.213ms였다. 기존12 frame/36 payload 계약은 변경하지 않았다.
Production Release BUILD_TESTING=OFF 빌드와 변경 C++18개 clang-tidy14 analyzer/bugprone·production14개 cppcheck2.7을 확인했다.
새 진단은 정리했고 기존 DriveSilPlant::begin의 인접 인자 경고1종은 보존했다. 예외가 noexcept send/service를 빠져나가지 않게
기존 실패/보호 경로에 연결했다. 그래프3개는 같은 CSV에서 렌더해 확인했다.

개발 중 상대 phase/수신 grant와 최신 issued parent 불일치·root release 불일치가 원래 expiry를 넘는 실패를 관측했다.
원래 기한을 연장하지 않고 절대 release·실제 수신 grant 대기/원래 parent history·200μs ingress service로 수정했다.
정상 종료의 terminal ACK 전 VM 실행도 보류해 half-handoff status를 새 Enable 근거로 쓰지 않는다.
실제 optional capability unknown과 critical torque/speed loss를 분리해 기존 friction fallback을 유지했다.
최종 검토에서 normal poll마다 gate를 다시 여는 호출도 세션 최초 Release 한 번으로 제한했다.
모든 scenario trace에 protected_all이면 gate가 닫혀야 한다는 oracle을 추가했다.
추가 oracle의 첫 native Actual 상실은 local Zone 보호→Central 인지 사이 열린 gate를 잡아 **871/872 PASS·1 FAIL**이었다
(commit6677a46, `build/m4-async-verification-release/normal/`; 그 attempt의 sanitizer는 NOT RUN).
Zone/Leaf 보호 진입에서도 atomic gate를 즉시 닫고 controller 자체 fault도 같은 경로로 보내 수정했다.
수정 후 최종 전체872개와 CLI 재가입은 두 빌드 모두 PASS다. [짧은 전후 trace](test-plan/evidence/m4_async/gate-regression.csv)를 보존한다.
앞선 회귀 assertion의 brace 경고는 수정했으며 실패 빌드 원본은 `build/m4-async-verification-gate/normal/build.txt`에 보존한다.
수정 전 통합 commit617c200의872개 PASS는 `build/m4-async-verification/`에 보존하고 최종 결과와 합치지 않는다.
초기871개 실행은868 PASS/3 FAIL(늦은 INIT wake 처리에서 negative ACK 누락)이었고 negative ACK 전달을 수정해 전체 회귀했다.
개발 실패 원본 `build/m4-async-ctest-development.log`, `build/m4-async-logical-development.log`와
`build/m4-async-runtime-{recovery,wall-service,absolute,capability,optional,root-phase}.log`는 보존한다.

재현 runner는 `tests/integration/runtime/check_m4_async.py`다. 최종 원본은
`build/m4-async-verification-safety/{metadata.json,normal/,sanitized/}`(configure/build/ctest/JUnit/CLI/원본 scenario),
Gate 후속 정적 분석은 `build/m4-async-gate{,-test}-tidy.log`와 변경4개 `tidy-*` 로그를 함께 따른다.
정적·production·transport는 `build/m4-async-{tidy-summary-reviewed,tidy-*,cppcheck-final,production-final,vcan-normal,vcan-sanitized,can-normal,can-sanitized}.log`다.
Markdown131개/상대 링크·anchor1548개·fence, 요구32/TC29·YAML3개 budget·Python9개 syntax/whitespace도 통과했다.
새 Python runner의 실제 실행과 기존63개 Python unit 재실행을 구분한다.
Remote wire/process partition·M3 profile 통합 timing·TSan/Target/차량/MBD는 NOT RUN, learner review는 PENDING이다.
과거846/820개 등 당시 수치와 M3 실패를 지우거나 전체 system TC PASS로 올리지 않는다.

## 코드·예제·시험 배치

- 재사용 기능은 `interfaces/`와 해당 runtime component에 둔다.
- 학습/확인 예제는 `actuator_demo` 실행 파일 하나로 묶는다.
  [진입점](../tools/actuator_demo.cpp)은 명령 분기·도움말을,
  `tools/demo/{steering,brake,drive,ev}_demo.cpp`는 각 도메인의 명령 구현을, `m4_demo.cpp`는 독립 owner 경로의 실행·grant 준비를 맡는다.
  ECU 판단은 `vecu/`, 물리 모델과 SIL 연결은 `simulation/`에 둔다.
  기존 기능의 작은 변경마다 별도 demo를 추가하지 않는다.
- 단위 시험 파일은 모듈별로 유지한다. 기존 모듈의 조건/경계/fault 추가는 같은 파일의 case로 추가하고,
  새로운 독립 모듈이 생기면 시험 파일을 만든다.
- 통합 시험의 participant/helper/runner는 같은 영역 아래 모은다.
  세 actuator SocketCAN은 `tests/integration/can/`이며 새 fault는 기존 runner의 case로 확장한다.
- DBC 검사와 환경 확인은 `tools/`에 둔다. 목적과 확인 범위가 완전히 겹치는 임시 코드만 정리한다.
  표현/수용/transport의 서로 다른 검증 계층은 유지한다.

CMake의 `BUILD_TESTING=OFF`는 단위 시험과 통합 시험용 TX/RX build를 제외한다.
Fresh build에서 라이브러리와 `actuator_demo`만 생성되는 것을 확인했다.
아래는 2026-10-12 최초 예제 통합의 이력이다. 최신 구조 정리의 491개 unit·90개 CLI 비교 범위는 위 2026-10-16 기록을 따른다.
당시 기존 예제 4개의 정상/거부 출력 17개를 통합 프로그램과 비교했고 명령 오류 7개/도움말도 확인했다.
단위 시험 파일은 이 정리로 추가하거나 합치지 않았다.
정리 후 normal/ASan·UBSan 각각 unit 48개와 vCAN 8개 case를 통과했고,
통합 demo/TX/RX source 3개의 static analysis와 DBC 교차 검증도 통과했다.
수신 로그의 cycle flush와 실패 trace 보존을 보완한 범위는 [실행 기록](learning/m1_steering_socketcan.md#예제시험-정리와-재검증)에 남겼다.

## 현재 코드에서 검사하기

Repository root에서 실행한다. CMake는 `compile_commands.json`을 생성하므로 정적 분석에도
현재 target의 include 경로·define을 사용한다. M1 학습 문서의 수동 `-I` 명령은 당시 검사 이력이며,
현재의 도메인별 demo·ECU/SIL 파일 전체를 포함하지 않는다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized -j 4
ctest --test-dir build/m1-angle-sanitized --output-on-failure
```

예제의 명령 구현을 검사할 때는 dispatcher만 검사하지 않고 도메인·M4 source를 포함한다.
다음은 현재 demo6개 source에 한정한 clang-tidy 명령이다. ECU/plant 변경 시에는 해당 구현·시험 source도
대상에 추가하고 검사 목록·도구 버전·결과를 기록한다.

```sh
clang-tidy -p build/m1-angle '-checks=-*,clang-analyzer-*,bugprone-*' '-warnings-as-errors=*' tools/actuator_demo.cpp tools/demo/*_demo.cpp
```

Cppcheck도 현재 compilation database의 include/define과 변경 production/demo 범위를 사용한다.
GoogleTest macro의 기존 도구 제약은 위 기록처럼 따로 관리하며, 일부 source의 PASS를 전체 repository 결과로 확대하지 않는다.
SIL 실행 API와 core-only 경계 시험의 읽는 순서는 [실행 경계 안내](learning/m2_execution_boundaries.md)에 있다.
M3의 wall-time 실행과 report 재현은 [첫 Steering timing 안내](learning/m3_steering_timing.md)를 따른다.

## Design and evidence review

[개발·학습 계획](engineering_plan.md)의 표준 참고 활동에도 기존 review와 변경 관리를
적용한다. Automotive SPICE의 추적성과 일관성 관점을 참고하며 평가 등급을 주장하지 않는다.
안전 분석의 가정·Goal 후보와 기존 requirement의 검토 연결은
[concept study](safety/concept_study.md)에 남긴다. 분석 초안을 승인된 safety concept이나
기존 requirement의 도출 근거로 소급해서 표시하지 않는다.

AUTOSAR pilot은 입력 ARXML/설정, schema/release, generator/compiler 버전, 실행 명령과
결과를 기록한다. 직접 작성한 코드와 생성·third-party 코드를 구분하고 재생성 가능성을
검토한다. 도구 채택 전에 license와 지원 환경을 확인한다. 정적 분석이나 단위 시험의
성공만으로 AUTOSAR 적합성, ISO 26262 준수, 실차 안전성 검증을 선언하지 않는다.

분석 또는 실험에서 baseline 변경이 필요하면 이유, 영향 requirement/ICD/profile/test,
재검증 범위를 기록한다. ASIL, FTTI, safe state와 같은 미결정 값을 임의로 확정하지 않는다.
학습자의 review와 자동 문서 검사는 별도 기록이며 한쪽 결과가 다른 쪽을 대신하지 않는다.


## 2026-10-20 — M4 공통 고장·복구와 M3 독립 감시 연결

현재 기준은 [project_status](project_status.md), 공유 근거/명령은 [M4 fault evidence](test-plan/evidence/m4_faults/README.md),
사전 측정 계획은 [프로토콜](test-plan/m4_fault_timing_protocol.md), 설계는 [ADR-0056](adr/ADR-0056-m4-faults-and-independent-execution-watch.md)다.
외부 검토 `b65ec25`에서 시작해 `c83004f`(공통 고장) normal/sanitizer902개씩 PASS,
`83a3f00`(독립 guard)908개씩 PASS, atomic launch 수정 `12fc4a5`에서908개씩 다시 PASS했다. 이전 결과/실패 로그를 교체하지 않았다.
추적표56개를 실제 두 JUnit과 대조했다. 기존 normal/partial Front/normal stop/old Epoch/rejoin도 전체 회귀에 포함된다.
기존 durable CLI 재가입 두 빌드1회씩, 새 overflow/join CLI는 두 빌드×logical/wall4/4 PASS다. 격리 vCAN gateway/startup 각각5개, Release BUILD_TESTING=OFF 빌드도 PASS다.

공통 fault runtime32개 artifact씩은 정상 운전 중 Central/Zone/Leaf 전체 실행 정지와 방향별 drop/delay/실제 FIFO overflow,
Prepare/INIT/Release·arm/stop ACK 경계를 구분한다. 재개만으로 gate가 열리지 않으며 join 뒤 link 교체·새 grant/full readiness·arm을 확인한다.
물리 state/energy/model sequence를 보존한다. 사후 물리 감사56개 active fault 표본의 hold/floor/zero·접점 open PASS,
never-active8개 N/A이며 짧은 run의 bus가30V 미만인지 별도 기록했다. 새로운 물리 응답 timing 기준을 사후 채택하지 않았다.

Native cohort는 run2.54s·guard lead100ms·2ms/4ms·각 owner1211기회·20ms tail,
normal/sanitizer × OTHER/FIFO × quiet/loaded normal3회와 Drive pause/Monitor overrun3회다.
CPU0=두 Zone/Physical/Monitor, CPU1=Central/다섯 Leaf이며 FIFO9–20을 실제 thread에서 확인했다.
Load는 별도 OTHER CPU1 process의7ms/10ms busy와 실제 CPU≥100ms를 대조했다.
전체48회 설정/부하 control PASS. **41 PASS/7 FAIL/0 BLOCKED**이며 실패를 조용히 재실행하지 않았다.
OTHER loaded normal6개는 모두 실행 기회 누락으로 FAIL, 나머지 normal18개 PASS다.
Fault23/24 PASS, 나머지 normal-build FIFO Drive-stop은736.513ms에 Monitor 누락을 먼저 검출해 정상 arm 전에 보호했다.
1200ms 주입 전의 다른 실패를 지정 고장의 검증 성공으로 세지 않았다.
통과 fault의 원래 deadline→독립 검출0.479–1.721ms, 검출→물리 override0.001–0.997ms다.
완료된 body만의 짧은 실행 시간과 skipped/missing slot을 구분한다. 통계는 run 내부에서 계산하며 논리/normal/sanitizer를 섞지 않았다.

**OPEN-M4-TIM-01**: OTHER 부하의6개 누락과 FIFO의1개 조기 Monitor 누락. 감시/보호는 동작했으나 정상4ms 완료 계약 실패다.
전체 OS 정지·동시 Monitor/Physical 정지는 하드웨어 watchdog 검증이 아니다. 새 PASS로 기존 OPEN-M3-01/02를 닫지 않는다.
Preflight는 FIFO20 AVAILABLE·rlimit20/20, PREEMPT_DYNAMIC/not RT, perf paranoid4·tracefs EACCES를 다시 확인했다.
추가 권한이 필요한 kernel timer/wakeup/switch 원인 분석은 미실행/미해결이며 시스템 설정은 바꾸지 않았다.

TSan 기본 실행은 test body 전에 unexpected memory mapping(exit66)으로 실패했다.
Process-local `setarch x86_64 -R`에서는 초기5개 기능 assertion이 통과해도 timed-CV 관련 경고5개로 exit66이었다.
올바른 잠금 최소 예제에서도 같은 경고가 재현됐다. 시작 장벽을 release/acquire atomic으로 바꾼 뒤 native 신규5개+기존2개 **7/7 PASS·경합 경고0**다.
이 범위를 전체 TSan·Target·FIFO timing 결과로 확대하지 않는다.
Clang-tidy14 변경10개·cppcheck2.7 production8개 검사; cppcheck 새 진단0, clang analyzer 오류0.
Variant `std::get`의 noexcept escape 경고(leaf/actor 고정 invariant), guard/test 인자 순서 경고와 기존 DriveSilPlant 인자 경고를 남겼다.
Runtime atomic 수정 후 재검사는 기존 Drive 경고만 남았다. Compiler Debug/Release 새 경고0이다.

기능/소스/환경 원본은 `build/m4-fault-atomic`, timing48개는 `build/m4-timing-final`, TSan/정적 분석/Release/preflight 로그는 공유 안내에 명시했다.
물리/통신은 같은 프로세스의 typed mailbox·atomic bypass 범위다. 원격 분리/DDS·remote lease/clock·MBD/AUTOSAR 실행,
기존 timing 원인 분석과 학습자 직접 재현/수용은 후속이다.32개 requirement/29개 system TC **NOT RUN**을 유지한다.

### 2026-10-21 — DDS Host 운용 후보·진단 결함 후속

`c10688d`/origin 동기·clean tree에서 시작했다. [사전 조건·대조·원본](test-plan/evidence/m5_dds_operating_profile/README.md)에
설계/코드/적용값을 구분했다. CPU1 공용5ms full0/3, minimal2/3, CPU1/2 minimal5ms·20ms 각각3/3.
첫 DATA가 heartbeat 이전이라 거부되고100ms 재전송으로 초기17개가 만료되는 경로를 확인했다.
선택형 양방향 transport readiness 후 같은 full/CPU1/5ms3/3 PASS, 준비 미송신은 원래 setup cap
내 FAIL·go 없음·실제 cleanup 확인. 정규 session/arm/control gate와 별개다.

진단의 writer-only 삭제가 reader take를 중단하던 결함 수정: 전1회 received20/rejected104,
후 세 build 삭제 뒤40건 추가 수신/rejected0. QoS public readback·reader rejected/lost·thread 실제
정책/affinity·write duration을 보완하고 최소 observer는 고정 event buffer를 사용한다.
새 runtime45 attempts=수정 전1+비교/종료38+readiness6. 이전42회23/19는 그대로다.
Normal/ASan 후보 close/restart·지속 송신/포화 close 기능 통과는 과거 close 해결을 뜻하지 않는다.
TSan 경고64 occurrences는 FAIL/OPEN; 의도된 peer SIGKILL은 sanitizer INCOMPLETE로 별도 표시한다.

관련 Python29/29, ASan/TSan 원래 expiry·실제 actor 보호 component 각각11/11 PASS.
새 강제 timeout 회귀는 실제 자식 둘의 kill/wait/저장을 검사한다. 모든 새 명령/결과의 원래
20ms/inner expiry 검사는 유지했다. 제품 코드·SDK pin/알고리즘 변경 없음;973/native40/timing48
재실행 없음. Host 한정 수용·M4 NOT CLOSED·DDS control gate CLOSED·과거 OPEN/Target NOT RUN 유지.
이전 Daybreak 중단을 인계했으며 새 인증 안내는 없었다. 실패한 API URL 조회는 중단·기록했다.
