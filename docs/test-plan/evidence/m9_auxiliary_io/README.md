# M9 보조 IO 물리 코어 분리와 역할별 파일 관측

2026-11-04, base `bbcb86a478944734d032df2725d856f3a555c2de`.
**두 개선을 구현했지만 전체 응답 지연과 M9 수용은 OPEN이다.** 최종 서비스 고정30개는
Normal6/6·ASan6/6·TSan15/18, 전체27/30이다. 별도 기능 회귀는11/12이며 실패도 보존한다.
[사전 protocol](../../auxiliary-io-protocol.md), [ADR-0098](../../../archive/design-decisions.md#adr-0098),
[실행 계약](../../../interfaces/someip-rear-adapter.md)을 따른다.

## 변경과 효과의 범위

- 기존 Rear CPU7과 보조 IO CPU15는 같은 물리 코어다. Split functional profile의
  `--separate-aux-io`는 실제 package/core topology와 허용 CPU를 읽고 owner1/2/7,
  plant3, SDK4/5/6과 물리 코어가 다른 CPU를 고른다. 이 Host에서는 CPU8이다.
  적합한 코어가 없거나 topology를 읽지 못하면 시작을 거절한다.
- Marker·diagnostic·Epoch·physical prerequisite·terminal service writer를 모두 선택된
  CPU의 SCHED_OTHER/priority0으로 배치한다. 기존 native-watch/일반 진단 profile은15다.
  선언과 별개로 process snapshot의 실제 affinity/policy/topology, 각 writer 배치를 감사한다.
  OS의 다른 작업까지 격리한 전용 코어를 뜻하지 않는다. Host observer는 CPU0에서 실행되어
  CPU8과 물리 코어를 공유한다. 두 비교 조건 모두 같은 observer를 사용했다.
- Marker worker의1ms 전체34개 파일 조회를 시작 전 역할별 등록으로 줄였다.
  Plant4, Central8, Front/Rear 각5개를 확인한다. 초기 snapshot·create/remove/rename,
  원래 쓰기 요청 시각·실제 쓰기 지연/실패 처리는 유지한다. 구독하지 않은 읽기는 오류다.
  모든 기존 등록 marker 쓰기는 계속 지원한다. Inotify나 시스템 watch 한도를 바꾸지 않는다.

단독2초 Normal worker probe의 `newfstatat`은47,067→13,285회(약72% 감소)였다.
Strace 없는 별도 표본의 worker CPU 시간은69.876→41.763ms였다. 각 조건 한 번의 idle
측정이며 strace overhead가 있는 실행과 없는 실행을 섞지 않는다. Native 전체 CPU 사용률이나
최악 응답 개선의 증거로 일반화하지 않는다. [측정 원본](probe-results.json)을 보존한다.

## 고정 실행 결과

| 실행 | 결과 | 조건 |
| --- | ---: | --- |
| 배치 비교 A: 기존 IO15 | 6/8 | TSan 정상·ACK loss·Actual loss·250ms marker 지연 |
| 배치 비교 B: 분리 IO8 | 7/8 | 같은 binary/source, 각 scenario별 A/B/B/A |
| 역할별 관측 + 분리: Normal | 6/6 | 정상·4종 service fault·250ms marker 지연 |
| 역할별 관측 + 분리: ASan/UBSan | 6/6 | 같은6개 |
| 역할별 관측 + 분리: TSan | 15/18 | 같은6개×3세트 |
| 역할별 관측 기능 회귀 | 11/12 | Normal/ASan별 정상·command loss·Front restart·delay·overflow·close-full |

총58개 native runtime attempt의 실행 명령·개별 exit·감사 결과는 [results.json](results.json)에 있다.
배치 비교16개와 두 변경을 합친30개를 같은 비교 분모로 합치지 않는다. 원래 고장 주입의
runtime exit1은 독립 감사가 실제 고장 위치/거절/DTC를 확인해야 통과다. 성공 prefix나
배치/순서 검사만의 성공으로 전체 서비스 실패를 바꾸지 않는다.
각 묶음의 runtime을 모두 끝낸 뒤 CPU 집약적인 독립 감사를 수행했다. 온도에 따른 대기나
성공할 때까지 재시도는 하지 않았다. 외부 부하/냉각은 통제하지 않았으므로 배치 비교의
작은 통과율 차이나 이전17/30과의 차이를 통계적으로 입증된 개선으로 보지 않는다.

## 남은 실패

최종30개의 미통과는 `tsan-normal`, `tsan-normal-slow-signals-r2`,
`tsan-stop-request-loss-r3`다. 모두 service 감사가 실패하며 순서·배치·accepted-response 감사의
통과로 이를 대체하지 않는다. [원본 시각 분석](analysis.json)에 최초 fault, 갱신 도착과 직전
명령 expiry, SDK 구간 및 전후25ms host 표본을 연결했다.

`tsan-normal`의 Epoch3 Front token147은 다음과 같다.

- Central 접수:801317991973181ns, Front 수신:801317992564814ns(0.591633ms).
- 직전 정상 token140의 명령 expiry:801317992463420ns. 새 명령 도착은0.101394ms 늦었다.
- Front가 gateway protection을 선택하고 negative result를 기록했다. 마지막 요청의
  왕복만 줄여서는 앞선 permission/command 갱신 연쇄의 여유 부족을 설명할 수 없다.
  이 한 사례를 모든 실패의 단일 원인으로 확대하지 않는다.

같은 실패 전후25ms의 가장 긴 완전 SDK 전달 구간은3.925ms였다. Sender queue와 SDK call,
callback 구간을 원본 CRC로 나눠 기록했다. CPU 시간 차는 동일 send call 또는 동일 callback
내에서만 계산했다. 서로 다른 스레드 CPU 시계를 빼지 않는다. Wall stamp와 trace 내부 CPU
읽기의 위치가 다르므로 이 차이를 정밀한 scheduler 대기 시간으로 주장하지 않는다.
SDK 내부 대기와 runnable 상태의 실행 대기를 완전히 구분한 결과는 아니다.

Host는 배치 비교와 최종30개에서 각각 최대100°C, runtime thermal counter 증가367/757을
보였다. 그러나 최종 실패3개 전후25ms에는 CPU1–7이 모두810MHz 이하인 표본이 없었다.
해당 구간 최대 온도는84/97/88°C, thermal count 증가는0/0/2다. 관측은 순차 sysfs 읽기의
begin/end이며 요청 간격10ms다. 온도나 낮은 주파수만으로 개별 실패 원인을 확정하지 않는다.
Governor·EPP·thermal 보호·perf 보안·watch 한도는 변경하지 않았다.

기능 회귀의 `normal-close-full`은 Central/Front의 두 세대 process가 모두exit0이고 원래
보호/큐 처리/재시작을 마쳤지만 Central1 SDK가 `Connection reset by peer(104)`를 기록했다.
Front stop begin801779790397041ns 뒤에 Central의 추가 시험 token1000000008–15가 enqueue되어
종료 중인 상대와 경합했다. 원문은 service5344/method0020, remote10.88.0.2:30501,
222bytes다. 기존 injected-crash 예외에 맞지 않으므로 **11/12 판정을 그대로 유지**한다.
이 종료 경합은 별도 미해결이며 실제 전송 오류를 숨기는 분류를 추가하지 않았다.

## 검증과 재현

- FixtureSignals 단위5개씩 Normal/ASan·UBSan/TSan 통과: blocked write, 최초 source 유지,
  외부 create/remove/rename, 쓰기 실패, 구독하지 않은 경로 미조회/읽기 거절과 startup snapshot.
- Python29개 통과: SMT·package·허용 CPU·별도 코어 부재·누락 topology와 기존 bookkeeping.
- 실제 adapter/diagnostic/service TU의 compiler warning, cppcheck warning/performance/portability,
  clang-tidy 통과. Third-party suppressed warning 원문도 저장한다.
- 최종3개 binary와 소스는 실제30개 실행과 일치하고 Normal/ASan 기능 회귀에도 같은 binary를
  사용했다. 세 source snapshot의 원래 SHA를 각각 확인했다. [확인 결과](identity-checks.json).
- 보관 archive를 다시 풀어 정상 service/배치/response 통과와 지연 service 실패를 재현했다.
  Close-full의 원래 SDK 오류도 같은 분류로 재현했다. [재감사 결과](archive-reaudit.json).
- 이전1256개 기본 검사를 이번에 다시 실행했다고 세지 않는다. Native4ms/Target·장기 부하·
  실제 CARLA 재실행과 M9 나머지 완료 항목은 [현재 상태](../../../project-status.md)를 따른다.

```sh
python3 tests/integration/someip/service_timing_campaign.py \
  --split-owner-io --owner-fifo --separate-aux-io --tsan-repeats 3 \
  --response-audit --defer-audits build/m9-aux-reproduction
```

기존SDK/RT 권한을 갖춘 Host에서 실행하며 이미 있는 output 폴더를 덮어쓰지 않는다.
Archive는 cohort별 원본 PCAP/CSV/journal/stdout/stderr/manifest와 당시 source snapshot을
포함한다. `validation-and-tools.tar.gz`에는 실행·분석·probe script, 빌드/검사 로그와 host 관측을
넣었다. `source-final.tar.gz`와 manifest는 최종 측정 소스다. `SHA256SUMS`로 보관 무결성을 확인한다.
