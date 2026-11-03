# M9 실제 native Central/Front/Rear 진단 배선

2026-11-03, base `9dcaadf` + [source overlay](sources/). 기존 실제8-participant native graph에
원본 observer→SPSC/snapshot→별도 writer→SOME/IP TCP→replica/merged journal을 연결했다.
**기능 연결 범위이며 M9/TBD-08·native4ms wall/Target·학습자 수용은 OPEN**이다.

Central Startup7이 실제 full8-role ACK 뒤 만든 Session을 Front/Rear에 전달한다. Local Ready나
수신 시각으로 Session을 만들지 않는다. 실제 endpoint의 accepted RunLease를 자기 owner에서
복사해 ContextualOutbox에 대조한다. Coordinator/Stop8은 중복 Session을 발행하지 않는다.
Zone/Leaf20–24와 native Gateway/BMS/Power30–33의 실제 최초 snapshot을 연결했다.
새 logical Network나 archived event를 source로 사용하지 않는다.

Context2개와 source9개, **논리 stream11개**를 원래 control TCP와 별도 service/endpoint에
bind한다. 각 source/replica는 독립 journal이고 Central merged는 동일 원본 EventId/bytes를
중복 제거한다. Remote ACK는 replica와 merged 양쪽의 durable commit 뒤에만 발행한다.
Source history는 ACK로 삭제하지 않는다. Registry3/Event schema1/원래 clock·발생 ID는 유지한다.
원격 Clear와 source 재시작 adoption은 구현 완료로 세지 않는다.

Callback FIFO8·source pending32·retry100ms·종료 drain2s다. Writer는 실제 CPU15/
SCHED_OTHER0이며 original actor는 새 진단 파일 IO를 수행하지 않는다. 물리 로그의 정상 선행
표본은 plant가 atomic timestamp로 넘기고 별도 non-RT observer가 prerequisite 파일을 쓴다.
진단은 원래 제어 gate를 열지 않는다. Recovery는 실제 native predicate와 writer의 context
commit이 모두 필요하다. 지연 context는 과거 고장 기록이며 현재 readiness/Passed가 아니다.

Control TCP/wire512·queue8192·lane8을 유지했다. Diagnostic TCP31610–12만2048,
SDK 요구에 따라 새 opt-in profile의 shared local envelope는1024→2048이다. Data는602 bytes다.
Store는 명시적 새 `/var/tmp` ext4 directory이며 원본도 보존한다. Private tmp/shm으로 진단을
운반하지 않는다. 종료/join 후 복사한 모든 파일을 원본과 대조했다. 이 결과는 저장 용량/부하
수용이나 Target filesystem 수용이 아니다.

## 최종 판정과 분모

| 검사 | 결과 / 범위 |
| --- | --- |
| 실제 native 기능 Normal | 5/5: 정상·Front loss·Rear loss·진단 ACK 유실·context1500ms 지연 |
| 실제 native ASan/UBSan | 같은5/5 |
| 실제 native SDK-instrumented TSan | 정상·ACK 유실2/2; process-local fixed layout |
| 독립 PCAP/journal/원본 감사 | 최종12 dataset 통과; 정상 각5개·손실 각8개 변조 거부 |
| 진단 off 기존3-ECU | 정상·Front loss·Rear loss3/3 |
| 일반 unit/logical | 1188/1188 |
| 영향 ASan/UBSan | 279/279 |
| 기존 M4AsyncWall | 2/2; 아래 native guarded4ms와 별도 |
| source fingerprint / Release | 검사2개; BUILD_TESTING=OFF Release transport/context library 통과 |
| 정적 분석 | clang-tidy warnings-as-errors3 TU·변경 header; cppcheck4 TU 통과 |
| native guarded4ms | 0/6; 별도 시도6개 모두 미통과, 실패 원본·분모 보존 |

최종 functional 묶음은 `native-normal/asan/tsan.tar.gz`다. 집중 queue policy2개는 기본/ASan
분모에도 포함되며 합산하지 않는다. Clang은 새 composition library의 실제 C++17 compilation
database로 shared SDK header까지 검사했다. 기존 front adapter는 C++20을 유지하고 cppcheck와
실제 compiler/sanitizer로 검사했다. Standalone logical SOME/IP auditor의 기본 동작도 기존
normal/loss dataset과8/10개 변조로 회귀했다.

독립 Python auditor가 control/진단 TCP를 재조립한다.11개 stream의 모든 Data/ACK와 원본
ordinal/CRC, 전역 Session의 실제8개 Release ACK, 원격9개 accepted credit와 실제 control
RunLease, 원본 native detector/deadline/command identity·Zone ACK를 대조한다. 정상 DTC0,
Front loss는2개/Rear loss는3개의 실제 서로 다른 monitor key이며 각각 count1/generation1이다.
보호 전달을 임의 root로 바꾸지 않는다. 기존 Central의 CodeNone/Unmapped 관측도 원본대로
남긴다. 전체 root 연결과 clear 수용은 후속이다.

실제 physical trace의 정상 torque/brake 표본 뒤에 고장을 주입하고 기존100ms torque/brake
criterion과 정상 정지/HV-off를 적용했다. Wall 실행의 on/off 물리 표본을 byte 동일하다고
주장하지 않으며 각 실행에 동일한 기존 oracle를 적용했다. 이 fixture는30km/h CARLA
Reference나 전체 BMS/Power native 고장 matrix가 아니다.

[results.json](results.json)은 최종/중간/guard 분모·감사, [manifest.json](manifest.json)은
source overlay/fingerprint·binary/SDK/config/tool hash를 묶는다. 전체 raw cohort는 tar.gz로,
build/static/unit log와 실패 당시 source는 `logs/`·`candidate-sources.tar.gz`로 보존한다.
이전 M9 evidence10묶음의 SHA43/153/135/203/183/186/217/306/654/130개도 유지했다.

## 실패와 수정

1. 첫 실제2개 실행은 SDK local envelope 설정 오류와 느린 `/d` ext4 fsync의 재전송 적체/
   callback overflow·drain timeout으로 실패했다. 오류 원본은 `probe-normal.tar.gz`다.
   Local size를 명시하고 새 local ext4 store profile을 지정했다. Queue/deadline/drain 한도는 유지했다.
2. 첫 auditor가 기존 Central의 원인 미지 Observation을 잘못 거부했다. 해당 source의 CodeNone/
   Unmapped flag를 그대로 보존하도록 바로잡았으며 모르는 원인을 remote root로 만들지 않았다.
3. Rear 시험은 CAN 정상 확인 직후 주입돼10ms physical trace에 정상 표본이 남지 않은 경우를
   거부했다. 기존 정상 선행 조건에 맞게 실제 trace 표본도 기다리도록 했다. 새 marker IO는
   plant runnable 밖의 observer로 옮겼다. 임계값·튜닝을 완화하지 않았다.
4. 보호 전환에서4-role credit와 Abort4/보호 요청이 겹쳐 TX/RX authority 큐가 포화된 실행을
   보존했다. 같은 peer·plan/epoch·clock의 미사용 credit만 유효 Abort/보호 요청이 대체하도록
   했다. Control/command/ACK·다른 세션·actor의 accepted evidence는 지우지 않는다. 실제 codec의
   결정적 burst/음성 검사2개와 최종 전 cohort를 재검증했다. 취소/overflow 방향을 별도 계수한다.
   종료 후 진단 drain 동안의 late control ingress도 별도 retire하며 runnable 완료로 세지 않는다.
5. Guarded4ms 시도는 missed/late native slot·정상 관측 분모 미달로 미통과다. 최종 기능 통과나
   기존 M4 wall2개로 덮지 않는다. 원래4ms·owner CPU/정책·반복 분모는 유지하며 안정화는 OPEN이다.

중간 cohort의 성공·실패를 최종12개에 합산하지 않는다. `attempts`에는 모든 native 실행을
남긴다. Archived binary 자체 대신 각 실행의 source/binary hash·SDK commit/build 설정을 보존한다.

## 재현

Base에 `sources/` overlay를 적용한다. Pinned vSomeIP3.7.6/Boost와 기존 build.py profile을 쓴다.
최종 output은 새 경로여야 하며 parallel native campaign은 기존 exclusive lock으로 막는다.

```sh
cmake -S . -B build/m5-someip-normal/project
cmake --build build/m5-someip-normal/project --target someip_front_adapter --parallel 3
python3 -B tests/integration/someip/native_diagnostics_run.py build/native-normal --profile normal
python3 -B tests/integration/someip/native_diagnostics_run.py build/native-asan --profile asan
python3 -B tests/integration/someip/native_diagnostics_run.py build/native-tsan --profile tsan --fixed-layout --cases normal drop-ack
python3 -B docs/test-plan/evidence/m9_native_routing/verify-packaged.py
```

SDK ASan/TSan target도 먼저 해당 profile로 빌드한다. Native4ms guard를 재현하려면 기존
`front_run.py --three --native-watch --diagnostics --cases normal command-loss`를 사용한다.
Clock/Target·source/collector 재시작 adoption·기동 전 로컬 실패·전체 원인 연결/복구·부하/보존
용량·CARLA matrix·학습자 수용은 남아 있다.
