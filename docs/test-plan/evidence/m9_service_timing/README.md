# M9 서비스 명령 순서와 시험 신호 IO 후속

2026-11-04, base `85eca942cec2fab2a325260c78d62381c0d2c5e3`.
**두 결함은 수정했지만 native 서비스 timing과 M9 전체 수용은 OPEN이다.**
[사전 protocol](../../service-timing-protocol.md)과 원래18ms support/20ms result/30ms Actual
기한을 유지했다. Native4ms/Target, 실제 CARLA 재실행, 임의 부하의 timing 보장은 이 범위가 아니다.

## 수정과 확인 범위

진행 중 Front→Rear 명령 사이에 다음 VehicleRequest가 끼어 Rear의 부모가 바뀌던 결함을
수정했다. `AsyncCoordinatorPort`는 원래 source/expiry와 접수 시점 결과 기한을 보존하는
유한8개 FIFO를 사용한다. 실제 enqueue 때만 token을 부여하며 full/expiry는 보호로 닫는다.
늦은 ACK는 실패를 복구하지 않고 새 Epoch만 대기 항목을 폐기한다.
[ADR-0096](../../../archive/design-decisions.md#adr-0096)과
[owner-wire 계약](../../../interfaces/owner-wire-v1.md)을 따른다.

시험 marker의 반복 exists/open/write를 control owner에서 별도 CPU15 worker로 옮겼다.
원래 요청 시각과 실제 write begin/end를 별도 기록한다. Marker는 제어 권한·DTC commit·
Actual의 증거가 아니다. Plant의 일회성 injection 시각 읽기 등 모든 파일 IO를 없앤 것은 아니다.
이전 owner gap에는 syscall별 기록이 없어 파일 IO를 유일 원인으로 확정하지 않는다.

## 고정 분모와 실패

각 cohort는 Normal/ASan/TSan별 정상·ACK 손실·Actual 손실·StopRequest 손실·Stop ACK 손실의
5개씩15개와 각 profile의250ms marker 쓰기 지연3개다. 고장 주입의 runtime FAIL은 정상적인
거절일 수 있으므로 기존 fault auditor가 실제 주입·최초 원인·기록·무허위 clear를 판정한다.
고장 주입 전 선행 실패는 통과로 세지 않는다. 전체 실행 명령과 개별 exit는 [results.json](results.json)에 있다.

| Cohort | Normal /5 | ASan /5 | TSan /5 | 지연 service /3 | 전체 /18 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `campaign`: marker IO 분리 | 5 | 5 | 3 | 2 | 15 |
| `ordered-campaign`: 부모 순서 수정 | 5 | 5 | 2 | 2 | 14 |
| `split-campaign`: owner/SDK CPU 분리 | 5 | 5 | 1 | 3 | 14 |
| `fifo-campaign`: 분리 + owner FIFO | 5 | 5 | 2 | 2 | 14 |

네 cohort72개와 첫 탐색 `signals-normal-stop-ack-loss`1개, 총73개 runtime attempt를 보존한다.
최종 cohort는 owner Central1/FIFO11, Front2·Rear7/FIFO18, SDK4/5/6·plant3·writer15/SCHED_OTHER다.
실제 thread affinity/policy와 marker 시각 감사18/18, 원본 부모 순서 감사18/18이 통과했다.
순서 수정 뒤 세 cohort의 ordering54/54는 전체 service 통과를 의미하지 않는다.

최종 TSan의 정상·Actual loss는 Epoch2, ACK loss·250ms 지연은 Epoch3 정상 정지 이전에
실패했다. 정상/Actual loss의 최초 transport ResultTimeout과 ACK loss/지연의 최초
Allocation SupportExpired 원본은 [failure-analysis.json](failure-analysis.json)과 archive CSV에 있다.
최종 네 실패의 Central 최대 owner 간격은1.75–2.42ms이며 RX overflow는 없다.
빠른 owner poll만으로 SDK 왕복·지원 기한을 충족한다고 볼 수 없다. 원래 protection과
미주입 상태를 유지하며 미래 authority로 이전 만료를 복구하거나 기한을 늘리지 않았다.

250ms 쓰기의 실제 duration은 Normal250.117ms, ASan250.157ms, TSan293.783ms였다.
세 경우 모두 쓰기 대기 중 원래 Epoch2 command-enqueue가 계속됐다. 전체 service 완료는
Normal/ASan만 통과했고 TSan은 이후 Epoch3 SupportExpired로 실패했다.

## 검증과 도구 오류의 구분

- 일반1253/1253: unit1028, logical211, transport5, wall9.
- 영향 ASan/UBSan22/22: async owner19와 signal worker3.
- TSan signal worker3/3, CARLA 논리135/135. 실제 CARLA runtime 재실행은 없다.
- 독립 순서 감사는 부모 교체·staging deadline 갱신 변조를 거절한다. 배치/시각 감사는
  CPU 위조·writer/marker 누락·지연 시간 삭제를 거절한다. 기존 service auditor의 변조 검사도 유지한다.
- 변경 production TU와 adapter clang-tidy 및 cppcheck warning/performance/portability를 확인했다.
  cppcheck style 전체 clean은 주장하지 않는다. 변경하지 않은 기존 style 경고도 원본에 남겼다.

첫 `campaign`의 manifest를 ASan 빌드 종료 전에 읽은 오류가 있었다. 초기 manifest를
수정하지 않고 `binary-build-completion.json`에 완료된 SHA를 추가했다. 실제18개 plan의
binary SHA가 해당 완료된 binary와 모두 일치한다. 이후 cohort는 빌드 완료 후 manifest를
고정하고 매 실행 전 SHA를 확인했다. 탐색1개는 최종 source/binary 수용의 분모가 아니다.

`split-campaign` 최초 placement 감사는 Epoch2 marker를 최종 Epoch3 summary arm과
비교한 오류로16/18 실패했다. 전18개 종료 후 reader를 수정해 같은 원본 Epoch2 event와
대조했고18/18 통과했다. 최초 로그와 `timing-reassessment.json`을 함께 보존한다.
Runtime/service 실패는 바꾸지 않았다. 마지막 FIFO cohort는 수정된 reader를 처음부터 사용했다.
초기 CMake target 미등록/no-tests 결과도 통과로 세지 않으며 실제 후속 검사와 구분한다.

## 원본과 재현

각 cohort의 `.tar.gz`에는 raw CSV/PCAP/journal, stdout, plan, runtime thread snapshot,
audit/mutation 결과, manifest 및 당시 선택 source snapshot이 있다. `sources.tar.gz`의
source 목록은 각 manifest를 따른다. 전체 기반은 위 base commit이다.
`source-final.tar.gz`와 manifest는 최종 변경 파일, `artifacts.json`은 native 실행파일 SHA/크기,
`build-configurations.tar.gz`는 세 profile의 CMakeCache/compile commands다.
`validation-logs.tar.gz`에는 build/unit/정적 검사와 초기 실패·재심사 기록·집계 script가 있다.
모든 이 디렉터리 파일의 SHA는 `SHA256SUMS`로 확인한다.

```sh
cd docs/test-plan/evidence/m9_service_timing
sha256sum -c SHA256SUMS
tar -xzf fifo-campaign.tar.gz -C /tmp
cd ../../../..
python3 tests/integration/diagnostics/audit_service_ordering.py /tmp/fifo-campaign/tsan-normal/central-rejoin-1 --mutations
python3 tests/integration/diagnostics/audit_service_timing.py /tmp/fifo-campaign/tsan-normal/central-rejoin-1 --mutations
# 기존 native build/SDK 환경과 CPU/FIFO 권한을 갖춘 경우 새 이름으로 전체 실행한다.
python3 tests/integration/someip/service_timing_campaign.py --split-owner-io --owner-fifo build/m9-service-timing-reproduction
```

이 README 위치에서 저장소 root는 `../../../..`다. 새 runtime에는 기존
[SOME/IP adapter 실행 조건](../../../interfaces/someip-rear-adapter.md)을 적용한다.
최종 service auditor는 기록된 실패4개에서 nonzero를 반환해야 한다.

남은 완료 조건은 native service timing, silent packet loss의 CARLA subinterval 물리 연결,
trusted Clock 재검증, proposal 이전 bootstrap incident, 전체8-role BMS/Power fault/recovery,
실제 부하·장기 보존이다. 학습자 이해 review는 별도다. 현재 우선순위는
[프로젝트 상태](../../../project-status.md)와 [로드맵](../../../roadmap.md)을 따른다.
