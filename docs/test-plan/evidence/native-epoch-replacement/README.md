# Live ECU 교체의 세션별 원본 기록

2026-11-06. [계약](../../../interfaces/epoch-retention.md)과
[ADR-0111](../../../archive/design-decisions.md#adr-0111)을 따른다. 선택형 native 3-ECU 경로에서
Front/Rear 프로세스를 실제 SIGKILL하고 새 INIT로 재가입할 때 역할별 고정 stream의 원본을
보존한다. 기존 M9 마감 범위와 wall/Target 수용 판정은 바꾸지 않는다.

## 구현과 판정

- 역할9개와 Central spool1개의 membership을 고정한다. 새 프로세스는 같은 family를 독점
  개방하고 이전 committed prefix를 ordinal1부터 재전송한다. 원본 producer ID는 새 generation이다.
  신뢰된 로컬 lineage와 실제 새 RunLease 없이 이전 Session을 새 프로세스에 적용하지 않는다.
- Central startup/control observer queue는 실제 이전 owner가 종료된 후 publish한 cut을
  acquire하고 비운다. 이전 tail을 먼저 기록한 뒤 새 Attempt/Session을 commit한다.
  Context 배포는 merged ACK와 독립적이다. 원격 endpoint evidence도 queue drain 전에 acquire한다.
- 강제 종료 전 memory/queue 유실 가능성은 source별 continuity fault로 보존한다. 유실 event 수를
  추측하거나 재전송으로 DTC를 해제하지 않는다. Pending/incomplete family는 자동 수리하지 않는다.
- ACK 없는 진단 전송은100→200→400→800→1000ms로 backoff한다. SDK queue8, 원래 제어 기한,
  overflow·deadline·정상 운행 오류의 실패 규칙은 그대로다.

실제 SOME/IP 시험은 서로 다른 network namespace의 Central/Front/Rear와 별도 plant를 사용한다.
기능 프로파일은 owner CPU1/2/7, plant3, 비실시간 diagnostic writer15다. Native4ms 보증 시험이 아니다.
새 profile의 threshold1은 새 epoch에서 실제 segment 회전을 반드시 검사하기 위한 설정이다.

| 실행 | 검사 |
| --- | --- |
| `front-initial` | Front SIGKILL → 보호 → 새 프로세스 → 실제 epoch2 INIT → 정상 종료; merged34개·continuity4개 |
| `rear-drop-ack` | Rear 교체와 Fault ACK1개 유실; merged33개·continuity5개·중복 재전송 |
| `normal` | 교체 없는 정상 운행·정상 정지; merged19개·continuity0개 |
| `command-loss` | 기존 명령 유실과 원래 물리 보호 판정 |
| `finite-normal` | 기존 finite 저장 경로의 정상 운행 회귀 |

실행별 최종 판정은 [acceptance.json](acceptance.json)에 기록한다. 강제 종료는 실제 정상 제어와
initial prefix의 durable receipt 이후에 주입한다. 이전 프로세스의 family는 재기동 전에 별도 copy로
보존한다. 이 시험을 임의 파일 write/fsync 도중 중단의 자동 복구 수용으로 확대하지 않는다.

독립 감사는 family metadata/CRC·segment·checkpoint 경계, source/replica/merged canonical bytes,
전체 TCP Data/ACK, 후속 SDK client의 ordinal1 재전송, 두 실제 INIT의 Release8개, endpoint별
원본 accepted RunLease를 검사한다. Front/Rear의 prefix·membership·producer·credit·ACK·receipt·
queue loss·continuity·물리 보호 등 변조13개씩, 정상/명령 유실 변조6개씩,
기존 finite 경로 변조5개를 거절한다.

## 검증·보관

- Debug 전체 회귀 **1,548/1,548**, `runtime.wall` 제외.
- 변경 경로 ASan/UBSan **109/109**: delivery49·context39·epoch16·process5.
- Python **280/280**, 변경 C++4개 clang-tidy 진단0.
- 새 단위시험10개: producer lineage/actual epoch/불완전 family3개와 Central spool의
  지연 old tail·cut 이전 보류·잘못된 source·queue 유실·미처리 pending7개.

`someip.tar.gz`에는 모든 실행의 원본 config·stdout/stderr·pcap·물리/제어 CSV·source/replica/merged
family·교체 전 copy가 있다. `validation.tar.gz`는 빌드/회귀/sanitizer/정적 검사·독립 감사 log와
빌드 설정이다. `sources.tar.gz`/`sources.json`은 변경 소스 snapshot과 hash다.
[SHA256SUMS](SHA256SUMS)로 증거를 확인한다. 실패가 있으면 실행을 덮어쓰지 않고 그대로 보관한다.

```sh
cmake --build build/m1-angle --target diagnostics_delivery_test remote_diagnostics_context_test
cmake --build build/m5-someip-normal/project --target someip_front_adapter
python3 tests/integration/someip/front_run.py build/new-native-epochs --three --diagnostics --diagnostic-epochs --isolated-ecus --cases restart-live --fault-zone front
python3 tests/integration/diagnostics/audit_native_epochs.py build/new-native-epochs/restart-live-1 --mutations
```

이 경로는 선택형이며 기본 finite 저장 경로를 자동 이관하지 않는다. Central 프로세스 교체와
terminal service의 family 적용, 실제 역할 증감, 단일 epoch 무중단 회전·디스크 보존 정책,
CARLA 감독 제어의 새 INIT/복구 주행, 전체 ODD·wall·Target과 학습 모델은 후속이다.
