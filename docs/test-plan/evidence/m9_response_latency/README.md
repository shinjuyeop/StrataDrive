# M9 SOME/IP 응답 대기와 지연 계측 후속

2026-11-04, base `2dcdc6cc8e4ede8599312c90fed90f4ad330b117`.
**송수신 대기 경로를 개선했지만 전체 응답 지연과 M9 수용은 OPEN이다.**
최종 binary의 고정30개는 Normal6/6·ASan5/6·TSan6/18, 전체17/30이다.
앞선24/30·23/30과 최종 실패를 모두 보존한다. 성공한 표본만 모아 통과로 판단하지 않는다.
[사전 protocol과 후보별 결정](../../service-response-protocol.md)을 따른다.

## 반영한 변경

- Sender의200us empty polling을 enqueue 알림으로 바꿨다. Functional owner는 RX 알림과
  monotonic1ms idle timeout을 사용한다. 실제 wake 지연은 scheduler에 의존한다.
  원래18ms support/20ms result/30ms Actual,8개 mailbox, lane 순서와 drain budget은 유지한다.
  Native-watch의 requested wake grid도 유지한다.
- SDK trace는131072행 고정 용량 메모리에 모으고 SDK join 뒤 저장한다. 초과/IO 실패는
  fixture 실패다. tx-queued/send-begin/send-return/rx-enter/rx-queued의 원본 CRC를 TCP bytes·
  owner token/epoch/source/deadline과 대조한다. CRC를 권한·인증으로 사용하지 않는다.
  SIGKILL된 Central1의 미저장 trace는 복구된 증거로 세지 않는다.
- GCC11 TSan의 `pthread_cond_clockwait` 미계측을 독립1000회 handshake로 재현했다.
  경고를 억제하지 않고 CLOCK_MONOTONIC 조건변수와 `pthread_cond_timedwait`를 사용한다.
  Spurious wake는 원래 absolute timeout을 연장하지 않는다.
- Capacity fixture는 정상 명령을 원래 기한 안에 마치고 consumer pause request/ack를
  확인한 뒤8개 invalid token과 정확한9번째 probe를 보낸다. 실제 수신 overflow가 먼저
  보호하며 Central은 그 뒤 관측된 Front 보호로 닫힌다. 정상 서비스 경로와 구분된 시험
  주입 순서다. 초기 회귀에서 정상 명령이9번째가 된 실패2개도 보존한다.

[ADR-0097](../../../archive/design-decisions.md#adr-0097)과
[실행 계약](../../../interfaces/someip-rear-adapter.md)을 따른다.

## 모든 실행의 분모

각 탐색4개는 TSan 정상·ACK loss·Actual loss·정상250ms marker 지연이다.
고정30개는 Normal/ASan 각6개와 TSan6개씩3세트다. 각6개는 정상·ACK loss·Actual loss·
StopRequest loss·Stop ACK loss·정상250ms marker 지연이다. Runtime exit1은 의도한 고장
거절일 수 있으므로 실제 주입·최초 원인·DTC·무허위 clear를 독립 auditor가 판정한다.
주입 전 기한 초과와 sanitizer/SDK 오류는 전체 성공으로 세지 않는다.

| Cohort | 판정 | 변경/조건 |
| --- | ---: | --- |
| `observed-other` | 3/4 | SDK trace 메모리 버퍼, 기존 polling |
| `observed-fifo` | 2/4 | 같은 binary, SDK FIFO8 실험 |
| `cpu-observed-fifo` | 2/4 | thread CPU 시각 추가 |
| `frequency-observed-fifo` | 3/4 | CPU 주파수 관측 추가 |
| `event-other` | 0/4 | 알림 대기의 GCC11 TSan 경고/startup 실패 |
| `event-monotonic-other` | 4/4 | 계측 가능한 monotonic wait |
| `final-campaign` | 24/30 | Normal6/6, ASan5/6, TSan13/18; 감사 interleaved |
| `quiet-campaign` | 23/30 | Normal6/6, ASan6/6, TSan11/18; 모든 runtime 뒤 감사 |
| `capacity-campaign` | 17/30 | Normal6/6, ASan5/6, TSan6/18; 최종 코드/모든 runtime 뒤 감사 |
| `regressions` | 10/12 | Normal/ASan별 정상·command loss·Front restart·delay·overflow·close-full |
| `capacity-regressions` | 12/12 | 같은12개, 유한 포화 주입 순서 수정 |

총138개 native runtime attempt의 명령·개별 exit·판정 필드는 [results.json](results.json)에 있다.
`quiet`은 감사 실행 순서의 이름이며 외부 부하나 냉각이 통제됐다는 의미가 아니다.
SDK FIFO8 실험은 충분하지 않아 최종 선택지에서 제거했다. 최종 실제 배치는 owner
Central1/FIFO11, Front2·Rear7/FIFO18, SDK4/5/6·plant3·IO15/SCHED_OTHER다.
Inotify 후보의 native12개/30개는 초기화 실패 때문에 NOT RUN이며138개에 더하지 않는다.

## 남은 실패와 host 관측

[실패 분석](failure-analysis.json)에 최초 Central fault/epoch/ns와 전후25ms 주파수 표본을
연결했다. 두 번째30개의 TSan 실패7개 모두 CPU1–7 동시 약800MHz 표본과 겹쳤다.
최종30개의 TSan 실패12개 중11개에서도 같은 관측이 있었다. 최초 fault는 지원 만료,
결과 기한 초과/지연 및 연속성·상태 거절로 나뉘며 원본 이벤트 값을 유지한다.
최종 ASan StopRequest loss도 정상 정지 이전 실패와 Rear SDK reset이 있어 미통과다.
기존 Front old-generation 오류 분류로 이를 통과시키지 않는다.

각30개 runtime 구간에 최대100°C를 관측했다. 두 번째30개 runtime까지의 thermal counter
증가는636, 최종30개는549다. 각 fault 전후25ms counter 증가가0인 경우도 있어,
온도만으로 개별 실패를 설명하거나 낮은 주파수와의 상관을 단일 원인의 증명으로 삼지 않는다.
표본은 순차 sysfs 읽기의 begin/end를 기록하며 모든 CPU의 동시 하드웨어 측정이 아니다.
Governor, EPP, thermal 보호와 시스템 한도는 변경하지 않았다.
사후 감사/정적 검사 구간의 counter는 runtime-complete 시각으로 별도 구분한다.

정상 TSan의 accepted token 표본은 초기1481개/알림 후1486개였다. 요청 송신 queue 중앙값은
178162→72208ns, 결과 queue는146734→51707ns였다. 왕복 중앙값은1.766→1.489ms지만
p99는2.908→3.254ms였다. 이 두 표본은 통제된 전체 성능 비교가 아니며 tail 개선이나 전체
scenario 수용 근거가 아니다. 응답 reader가 통과한 prefix도 service 실패를 대체하지 않는다.

현재 완료 조건은 냉각/전원·실제 실행 조건을 확인한 환경에서 동일 고정 cohort의 전체 기한을
충족하는 것이다. Host 기능 검증과 Native4ms/Target·장기 부하 수용은 별도이며 이 실행에서
실제 CARLA를 재실행하지 않았다. M9 나머지 범위는 [프로젝트 상태](../../../project-status.md)를 따른다.

## 추가 후보와 도구 실패

첫30개 ASan StopRequest loss의 SDK 오류는 의도한 Central1 SIGKILL 뒤, Front 보호 뒤,
Central2 issuer boot 이전의 정확한 Front Actual socket/85bytes Broken pipe였다.
새 classifier는 원본 PID 생존·실제 재가입·SIGKILL/-9·보호/boot 시각·socket/service/method를
모두 확인한다. 다른 오류나 새로운 세대의 오류를 면제하지 않는다. 원래 실패 판정은
고치지 않았으며 [원본 시각 분석](original-sdk-error-analysis.json)을 별도로 보존했다.

Idle fixture worker2초 strace 표본은 newfstatat46761회/worker CPU0.17s였다. 측정 overhead를
포함하며 실제 native 사용률로 일반화하지 않는다. Inotify 후보는 이 Host의 watch 한도
소진(`inotify_add_watch: ENOSPC`)으로 unit fixture4개 모두 초기화에 실패했다.
Normal/ASan/TSan 로그와 `watch-prototype.tar.gz`를 보존했고 최종 코드는 이전 polling worker다.
실패한 after idle probe를 성능 향상으로 세지 않는다. 최종3-profile binary SHA가 실제
`capacity-campaign`/`capacity-regressions`와 같은 것은 `restored-identity.json`으로 확인한다.

추가 clang-tidy 실행은 설치된 GCC13 header 자동 선택으로 chrono compiler error가 났다.
해당 로그를 보존하고 실제 build의 GCC11 include로 검사했다. 초기 ASan target/no-tests
로그도 통과 근거가 아니다. TSan 최소 재현 경고·시도별 SDK 실패도 삭제하지 않는다.

## 검증과 재현

- 일반1256/1256: unit1031, logical211, transport5, wall9.
- Monotonic wait ASan/UBSan3/3·TSan3/3. 최종 marker/monotonic 경계6/6은 Normal과
  ASan/UBSan·TSan으로 확인했다. Inotify 후보 실패7개 시험 중3개 통과를 이에 섞지 않는다.
- Python bookkeeping25개 통과. 정확한 injected SDK 오류의 positive와 변경된 근거의 negative를 포함한다.
- 원본 TCP/owner/SDK 대조 reader는 bytes·deadline·수신 순서·누락 stage 변조4개를 거절한다.
  기존 service/ordering/placement reader와 mutation도 각 cohort 원본에 남긴다.
- 실제 adapter TU와 변경 header의 clang-tidy, cppcheck warning/performance/portability 확인.
  전체 third-party/style clean을 주장하지 않는다.

각 cohort archive는 raw CSV/PCAP/journal, stdout/stderr, plan, 실제 thread 배치,
source/binary manifest와 당시 source snapshot을 포함한다. `source-final.tar.gz`는 최종 변경
파일, `build-configurations.tar.gz`는 실제3개 profile의 project/SDK CMake 설정이다.
`host-observations.tar.gz`와 `validation-logs.tar.gz`에는 측정 원본·도구 버전·script·실패를 포함한다.
재현 script가 조사 중 바뀐 경우 당시 개별 명령과 cohort manifest가 기준이다.

```sh
cd docs/test-plan/evidence/m9_response_latency
sha256sum -c SHA256SUMS
# 새 임시 디렉터리에 풀고 원본 pass/fail을 그대로 감사한다.
tar -xzf capacity-campaign.tar.gz -C /tmp
cd ../../../..
python3 tests/integration/diagnostics/audit_service_response.py /tmp/capacity-campaign/normal-normal/central-rejoin-1 --mutations
python3 tests/integration/diagnostics/audit_native_service.py /tmp/capacity-campaign/tsan-normal-r3/central-rejoin-1 --mutations
# 두 번째 명령은 보관된 실패에서 nonzero여야 한다.
# 기존 SDK/CPU/FIFO 권한을 갖춘 환경에서 새 output 이름으로 실행한다.
python3 tests/integration/someip/service_timing_campaign.py --split-owner-io --owner-fifo --tsan-repeats 3 --response-audit --defer-audits build/m9-response-reproduction
```

Archive에서 추출한 정상·실패 재감사 결과는 `archive-reaudit.json`, 모든 파일의 무결성은
`SHA256SUMS`를 따른다. Re-audit가 과거 runtime verdict를 바꾸지는 않는다.
