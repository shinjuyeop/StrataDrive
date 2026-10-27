# M7-1s — CARLA secondary-server 종료 경합 수정

2026-10-27. 기준 commit `e2c3ba4`. M7-1r의 `OPEN-M7-1R-EXIT-01`을 조사했다.
원본 CARLA Listener의 accept/close data race를 독립 TSan으로 재현하고 종료 순서를 수정했다.
M6 구현·계약·수용 수치, V1 가상 EV/브레이크 계수, world10ms·영상50ms,
Controller20ms·Zone/vECU10ms·Drive30ms·expiry, solver320/단일 EV 계산은 그대로다.

## 원인과 수정 범위

- [이전 UE 원본 스택](../m7_carla_1r/legacy-native-exit-Diagnostics.txt)은 `Listener::OpenSession`
  및 Asio accept completion을 가리킨다. 실제 pinned CARLA 네트워크 소스를 UE/물리 없이
  컴파일한 [원본 TSan](original-tsan-02/stress.log)에서 worker의 `async_accept`와 owner의
  `Listener::Stop → acceptor.close`가 같은 메모리에 접근하는 data race를 탐지했다.
  이전 UE crash의 정확한 메모리 상태를 재현한 것은 아니지만 같은 경로의 구체적인 결함을 확인했다.
- 원본은 worker가 실행 중인데 소켓을 cancel/close하고 context를 stop/reset한다. 취소된
  accept completion도 다음 accept를 무조건 등록한다. [단일 스레드 취소 시험](original-normal/cancel.log)은
  닫힌 descriptor에서 재등록이32completion까지 계속되는 것을 확인했다.
  [Boost1.84 acceptor](https://www.boost.org/doc/libs/1_84_0/doc/html/boost_asio/reference/basic_socket_acceptor.html)의
  shared-object 안전 조건과 [restart 조건](https://www.boost.org/doc/libs/1_84_0/doc/html/boost_asio/reference/io_context/restart.html)에 맞지 않는다.
- 수정은 **pool stop/join → listener cancel/close → session/promise 해제**다. 종료 중 context
  reset을 제거했고 실패한 accept는 재등록하지 않는다. Listen의 최초 지연 호출은 shared owner를
  캡처한다. 빈 Router/반복 Stop/소멸자가 안전하게 작동하고 commander의 Router 자기 참조를 끊는다.
- `Stop`은 외부 생산자가 정지한 뒤 lifecycle owner가 호출하는 terminal operation이다.
  I/O worker 안에서 Stop, 동시 lifecycle 호출, 같은 Router의 재시작은 지원하지 않는다.
  재시작은 새 Router/서버다. multi-GPU 운영/통신 오류 후 재연결 기능을 새로 승인하지 않는다.
- [설치 비교](installation-audit.json)에서 바뀐 CARLA integration 파일은
  `multigpu/{router.cpp,listener.cpp,listener.h}`뿐이다. 복사한 M6 원본40파일과 UE tracked source는 불변이다.
  [시험 source와 설치 source 해시](patch-install-match.json)가 일치한다. installer가 pin/기존 manifest를
  검사하고 원본에서 패치를 재생성한다. 기존 module 백업은 외부 `m7-1s/before-libUE4Editor-Carla.so`다.

## 독립 component 검증

실제 CARLA `294096eb…`의 Listener/Router/Primary/PrimaryCommands/Buffer와 Boost1.84 헤더를 사용한다.
Host clang14/libstdc++ 실행이며 UE clang10/libc++ 전체 sanitizer 시험을 대신하지 않는다.

| 실행 | 실제 결과 |
| --- | --- |
| [원본 Normal](original-normal/result.json) | 6case 모두 실패: 취소 재등록, 빈/반복 Stop, 병렬 종료/소멸 오류. 기대한 결함 재현이며 성공으로 집계하지 않음 |
| [원본 ASan/UBSan](original-asan-03/result.json) | 6case 실패, null Listener 호출/잘못된 descriptor 오류 포함 |
| [원본 TSan](original-tsan-02/result.json) | stress에서 accept/close data race, 빈/반복 Stop 오류. `halt_on_error=1` |
| [수정 Normal](patched-normal/result.json) | 6/6: 취소 completion1회로 종료, 빈/반복 Stop, idle 종료1,000회·실제 연결 종료100회·객체 해제10회 |
| [수정 ASan/UBSan](patched-asan-03/result.json) | 같은6/6, leak detection 켬. 반복마다 Router weak reference 만료 및 port 재bind 확인 |
| [수정 TSan](patched-tsan-02/result.json) | 같은6/6,1,000회 종료·100회 연결 종료, race 보고 없음 |
| [기존 native Normal](native-normal.log), [ASan](native-asan.log) | 각각69/69. 기존 executable·모델은 변경하지 않음 |

처음 두 component 빌드는 rpclib/moodycamel include 경로 누락으로 실패했다
([원본](original-asan/build.log), [수정본](patched-asan/build.log)). 경로를 고쳐 재빌드했다.
PIE ASan 실행 일부는 로그 없이−11이었다. [GDB5번째 재현](pie-gdb-05.log)은 `main` 전
`AsanInitInternal → allocator mmap`에서 SIGSEGV를 보여 주며 CARLA 종료 오류와 구분한다.
component를 non-PIE로 빌드한 후 위 ASan 시험을 통과했다. 최초 [TSan 주소 배치 실패](original-tsan/stress.log)는
FAIL로 보존하고 child에만 `setarch x86_64 -R`을 적용해 재실행했다. Host 전역 ASLR 설정은 바꾸지 않았다.

## 실제 서버 검증과 초기 실패

[LibCarla build](libcarla-build.log)/[dependency 설치](libcarla-install.log)/[UE module build](carla-build.log)는 exit0이다.
Carla module은 `10c4ed749156cd26cc67216717b0efc937e1f09455d19b338c803c1d2970d28d`이며
M7Native·PhysX observer module은 [전/후 해시](after-artifacts.json)상 기존과 같다.
Town03_Opt/mkz_2020/V1 비렌더링, 기존 source Client/Server `294096e-dirty`를 사용했다.

첫 [legacy-a](legacy-a/result.json)는 버전만 확인하고 `get_world`10초 timeout으로0receipt였다.
뒤이어 SIGINT30초 한도를 넘어−9 강제 종료됐으므로 [SERVER_EXIT_FAIL](server-legacy-a.json)이다.
이 실행에서 SIGSEGV는 관측되지 않았으며 actor/Actual/work 시험은 수행되지 않았다.
포트가 열린 시점에 episode 준비가 끝났다고 가정한 runner를 수정해, 같은180초 startup deadline 안에서
별도 read-only client로 첫 유효 snapshot을 기다린다. readiness client는 tick/actuation을 하지 않는다.
cached timestamp를 갱신하지 않으며 실제 주행의30ms source-age나10초 probe RPC/30초 shutdown 한도는 그대로다.
timeout된 read-only 조회만 재시도하고 tick은 재시도하지 않는다.
원래 cold map loading 중단이30초 안에 끝나는지는 이 보완만으로 수용하지 않는다.

서버 로그의 CrashReportClient 자동 업로드는 pinned UE가 지원하는 process-local ini override로 끈다.
server/client/readiness 로그는 로컬 원본 hash와 무손실 gzip으로 보존한다.

후속 새 서버 **12회 모두 SIGINT130, 강제 종료0회**다. 처음 실패까지 전체13회를 포함한
[종료/자원 점검](cleanup-audit.json)에서 UE/CrashReportClient 잔여 process0 및2200/2201/2202
port 해제를 확인했다. [실행 argv/집계](live-suite.json)는 첫 실패도 포함한다.

| 후속 실행 | 실제 결과 |
| --- | --- |
| [legacy A](legacy-a-ready/result.json), [B](legacy-b/result.json), [C](legacy-c/result.json) | 각각400receipt/319정상 권한 구간·4empty INIT, 기존 wire/Actual 독립 audit 통과 |
| [energy A](energy-a/result.json), [B](energy-b/result.json), [C](energy-c/result.json) | 각각400receipt/400EV 정산·319정상 구간. 세 실행 모두 work74.65267507976446J, 최종SOC0.6299940397683207 |
| [zero A](zero-a/result.json), [B](zero-b/result.json) | 각각156runtime 검사/13receipt와 기존 oracle8종 손상 거부, pause/reset/복원 확인 |
| [disabled A](disabled-a/result.json), [B](disabled-b/result.json) | 확장 비활성 describe 거부·unlocked, ego/actuation 없음 |
| [ACK 누락](ack-missing/result.json) | 200receipt, native정산200회/서버 ACK199회 뒤 stage 거부·다음 tick 없음 |
| [명령 오류](command/result.json) | 원래 명령 계약 위반 거부·다음 tick 차단, 기존 수용 기준 유지 |

정상6실행의 각400개 `receipt.physics`(run별 generation identity 제외)는 M7-1r의 frozen
energy-final-a와 **정확히 일치**한다. [비교](trajectory-comparison.json)는 허용 오차를 추가하지 않는다.
energy [A](energy-a-audit.json)/[B](energy-b-audit.json)/[C](energy-c-audit.json)는 각각400구간의
원본 wire/Actual·모든320개 solver block·1ms work 보존·단일 EV/SOC 장부와11개 solver/7개 energy
손상 거부를 독립 확인한다. 고장 실행도 별도 [ACK audit](ack-missing-audit.json)/[명령 audit](command-audit.json)를 통과했다.
관측 범위의 종료 경합은 **FIXED_LIMITED**, cold-load 중단은 **OPEN-M7-1S-COLD-01**이다.
renderer·일반 가감속/회생·wall 수용으로 확대하지 않는다.

기존 tracked evidence **2,258파일**은 [전부 불변](frozen-prior-audit.json)이다. [component provenance](component-provenance.json),
[실행 소스 snapshot](executed-sources.json), server report의 실제 binary hash를 보존했다.
원본 실패를 삭제하거나 PASS로 고치지 않았고 새 evidence는 [SHA256SUMS](SHA256SUMS)로 고정한다.

## 재현과 후속 경계

- component: `python3 tests/integration/carla/m7_1s_component.py --carla <pinned-source> --output <new-external-dir> --patched --sanitizer address`.
  TSan은 `--sanitizer thread --disable-aslr`; 원본 대조는 `--patched`를 생략한다.
- install은 기존 `tools/carla/m7_nodrive/install.py`를 사용한다. 이후 외부 CARLA에서
  `cmake --build Build/libcarla-server-build.release --target carla_server -j 8`,
  `cmake --install Build/libcarla-server-build.release`, 기존 `BuildCarlaUE4.sh --build --no-simready` 순서다.
  해당 build tree/UE4_ROOT는 앞선 pinned 환경이다. 서버가 정지한 상태에서 수행한다.
- 실제 실행은 기존 `m7_1o_run.py`와 [최초 suite](live-suite.py), [준비 확인 후 suite](live-suite-ready.py)를 사용했다. 재실행은 새 output/runtime 경로를 지정한다. 실행 binary/원래 probe
  snapshot hash는 각 server report에 있다. component 원본 source와 실행 파일은 외부에 두며 vendoring하지 않는다.
- 원래 M7-1r 실패 evidence는 수정하지 않는다. 패키지 SIGTERM/renderer crash, cold-load 중단,
  UE 전체 sanitizer/장시간 stress, wall2/4ms·전체 ODD의 종료 안정성은 별도 gate다.
  다음 M7-1t는 동일 Actual/단일 EV 경로에서 가속→감속→정지·재출발을 작은 시나리오로 검증한다.
  V1 가상 EV 브레이크를 유지하며 OEM calibration으로 해석하지 않는다. 회생/보호 제동은 별도 시험이다.
