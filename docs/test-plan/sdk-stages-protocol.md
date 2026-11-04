# SDK 대기 구간 관측

2026-11-04, base `b740c5e`. 기존 service28/30의 TSan 선행 정상 구간 실패를
분석하기 위한 관측이다. 성능 개선·M9 수용 판정을 대신하지 않는다.

## 변경 범위

Pinned SDK `4187431d2815bd351845a09d01aa85b2a3163cab`를 별도 경로에 복제하고
`build_sdk_observation.py`로 명시적 patch와 compiler/library hash를 남긴다.
기본 SDK·제어 바이너리·source/expiry·18ms support·10ms/+4ms 주기·queue8은 유지한다.
`--sdk-observation` 실행에만 내부 계측과 세 ECU의 AF_PACKET 관측을 켠다.

`tcp-send`, `tcp-receive`(완전 메시지를 제공한 receive callback 진입 시각),
`tcp-message`(파싱 후 routing 전달), `app-message`, `handler-queued`,
`handler-enter/exit`를 원래 SOME/IP service/method/client/session/길이/CRC로 연결한다.
메시지 분할·묶음 전송은 TCP sequence로 재조립하며 CRC만으로 다른 패킷을 합치지 않는다.
Internal buffer262144행은 SDK 시작 전에 초기화하고 writer join 후 저장한다.
초과·시계 실패·누락은 관측 실패다. 의도한 SIGKILL의 미저장 구간은 완전 trace 분모에서
구분하고 실행 자체는 분모에서 제외하지 않는다.

수신측 커널 시각은 `SO_TIMESTAMPNS_NEW`의 CLOCK_REALTIME이다. 매 frame의
MONOTONIC→REALTIME→MONOTONIC bracket과 원래 ns를 sidecar에 보존한다.
PCAP에는 호환을 위해 us 값을 쓰며 정밀 계산은 sidecar를 사용한다. 시계 step/drift,
관측점 차이, 재전송/순서 뒤바뀜과 캡처 drop을 검사한다. 전체 관측 offset envelope가100µs를
넘으면 정밀 구간 분석은 실패한다. 이는 제어 기한이 아니라 시계 환산 품질의 사전 한계다.
Outgoing 관측은 물리 NIC TX가 아니다.
관측기3개는 CPU0/SCHED_OTHER, 기존 auxiliary8과 SMT core를 공유한다. 추가 계측 부하가
있으므로 이전 cohort와 통과율 차이를 성능 개선/악화로 해석하지 않는다.

Thread CPU와 voluntary/involuntary switch 누적값은 보조 근거다. 다른 thread 사이의
CPU 값을 빼지 않는다. Wall−CPU만으로 lock 대기와 runnable 대기를 확정하지 않는다.
OS perf/schedstats·전력·thermal 설정을 바꾸지 않는다.

## 사전 실행 분모와 판정

1. Kernel timestamp 누락/중복/잘림·clock bracket·TCP 재조립 및 SDK 기록의 변조 검사를 수행한다.
2. 계측 SDK TSan으로 `ack-loss`, `stop-ack-loss`를 각각3회, 교대로 고정6회 실행한다.
   모든 runtime을 마친 뒤 service/order/timing/response와 내부 구간 분석을 수행한다.
   통과할 때까지 재시도하거나 실패를 삭제하지 않는다.
3. 같은 조건에서 실패가 재현되지 않으면 고정 cohort의 관측 가능한 긴 지연만 보고하고
   과거 실패의 원인이 확정됐다고 쓰지 않는다. 재현되면 최초 fault의 원래 token/expiry와
   수신 경로를 연결한다. 측정 결과에 따라 수정 후보를 별도 사전 protocol로 정한다.
4. 실제 동작 수정 후에만 기존30건 서비스·관련 기능 회귀를 최종 후보로 재검증한다.
   계측만 추가한 실행을 응답 지연 해결이나 Native4ms/Target 수용으로 세지 않는다.

Kernel 시각의 의미는 [Linux timestamping 문서](https://docs.kernel.org/networking/timestamping.html)를 따른다.
