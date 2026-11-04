# Native 서비스 응답 지연 후속 protocol

2026-11-04, base `2dcdc6c`. 이전 FIFO cohort의 TSan 정상/ACK loss/Actual loss/250ms
marker 지연4개 미통과를 조사한다. 기존 원본과 실패 판정을 변경하지 않는다.

이전 정상 TSan token313/Epoch2는 Central 접수789668875516528, Rear 수신789668884017426,
Rear 결과 source789668885257507, Central 수신789668892343042ns다. 원래 결과 기한
789668890070650ns를 넘었다. PCAP 사용자 공간 관측은 요청789668879422183, 응답
789668887810183ns다. Capture 수신 시각은 실제 NIC 송수신 시각이나 callback 시각이 아니다.

새 계측은 고정 용량 메모리에 tx-queued/send-begin/send-return/rx-enter/rx-queued를
원래 packet CRC와 함께 기록하고 SDK join 후 저장한다. CRC는 인증이나 권한이 아니며
원본 PCAP/owner token과 대조한다. 기록 초과·IO 실패는 시험 실패다. SDK sender의 기존
동기 파일 출력을 이 경로에서 제거한다. 기동 중 SIGKILL된 process의 미저장 메모리는
복구된 evidence로 세지 않는다. 나머지 source/journal/PCAP는 그대로 보존한다.

먼저 동일 계측 바이너리로 위4개를 기존 split-owner/FIFO 조건에서 각1회 실행한다.
다음4개는 별도 `--sdk-fifo` 조건에서 각1회 실행한다. 기존은 SDK CPU4/5/6에서
SCHED_OTHER이며 다음 조건은 SDK sender/IO/dispatcher FIFO8, owner Central1/FIFO11,
Front2/Rear7/FIFO18이다. Plant3·diagnostic/marker IO15는 SCHED_OTHER로 유지한다.
SDK 설정은 초기 handshake 이전에 적용·확인하며 실제 thread별 policy/priority/affinity를
검증한다. TSan background thread는 SCHED_OTHER로 유지한다.

Host10ms allocation, management10ms/+4ms,18ms support,20ms result,30ms Actual,
기존 stop/drain 기한과8개 mailbox 크기를 유지한다. Freshness 재기록·drop/coalescing·
재시도에 따른 기한 연장·미주입 실패의 통과 재분류를 허용하지 않는다.

수정 후보를 확정한 뒤 Normal/ASan 각6개, TSan6개씩 연속3세트의 고정30개를 검증한다.
각6개는 정상·ACK loss·Actual loss·StopRequest loss·Stop ACK loss·정상250ms marker 지연이다.
전체 결과와 기존 service/ordering/placement auditor의 mutation을 보존한다. Profile과
소스/바이너리를 실행 전에 고정하고30개 중 실패가 있으면 전체 수용으로 올리지 않는다.
이 결과는 이 Host 기능 profile의 반복 검증이며 Native4ms·Target·장기 부하 수용은 별도다.

## 실행 대기 개선 후보

초기 동일 계측4개는3/4, SDK FIFO4개는2/4, thread CPU 시각 추가4개는2/4였다.
고정4개의 추가 주파수 관측에서도 실패가 있었으며 관련 CPU1–7이 약4.1GHz에서800MHz로
내려간 구간과 result expiry가 겹쳤다. 우선순위만으로 해결된 것으로 판단하지 않는다.
온도와 thermal throttle counter도 후속 관측하며 시스템 governor·thermal 보호는 변경하지 않는다.

후속 후보는 sender의200us 주기 empty polling을 실제 enqueue 알림으로 교체한다.
Host 기능 owner는 RX 알림으로 깨어나며 입력이 없을 때1ms timeout을 요청한다.
실제 wake 지연은 scheduler에 의존하며1ms wall 상한을 보장하지 않는다.
Native-watch의 기존 requested wake grid는 그대로 유지한다. 모든 protocol deadline,
명령·Actual source/expiry, mailbox/drain 용량·FIFO·고장 주입 조건은 유지한다.
동일4개를 기존 SDK SCHED_OTHER 조건에서 먼저 검증한 뒤 최종30개를 실행한다.

최초 event 대기4개는 GCC11 TSan 경고와 startup 실패로0/4였다. 표준 `wait_for`가 호출하는
`pthread_cond_clockwait`를 해당 libtsan이 intercept하지 않는 현상을 독립1000회 handshake로
재현했다. 경고를 억제하지 않고 CLOCK_MONOTONIC 조건변수와 계측 가능한
`pthread_cond_timedwait`로 교체했다. 같은 최소 재현 및 동기화/timeout 단위3개가 통과했다.
교체 후 동일4개는4/4이며 sanitizer 경고가 없다. 원래0/4는 보존한다.

최종 후보는 SDK SCHED_OTHER를 유지한다. 효과가 충분하지 않았던 SDK FIFO 선택지는
실험 source snapshot에만 보존하고 최종 runner에서는 제거한다. 기존 owner FIFO 배치와
최종30개 분모를 적용한다. 원본 token/PCAP CRC/SDK 다섯 구간/accepted deadline을 새 독립
reader로 대조하고, 바뀐 bytes/기한/수신 순서/누락 stage 변조4개를 거절한다. 응답 통계의
accepted prefix를 시나리오 전체 성공으로 대체하지 않는다. Temperature/frequency 관측은
사후 해석용이며 실패를 제외하거나 다음 시도를 기다리는 조건으로 사용하지 않는다.

## Offline 감사와 runtime의 실행 순서 분리

첫30개는24/30이었다. TSan 선행 실패5개와 ASan StopRequest loss의 SDK 오류1개를
원래 판정으로 보존한다. Temperature 최대100°C, package throttle counter 증가15710과
실패 부근의800MHz 관측을 남겼다. 매 runtime 사이에 CPU 집약적인 PCAP/변조 감사를
넣었던 영향을 분리하기 위해 다음 동일30개는 runtime을 모두 끝낸 뒤 감사를 실행한다.
시험별 대기/재시도나 온도에 따른 실행 선별은 하지 않는다. 첫/다음 cohort를 합쳐 PASS로
올리지 않으며 새로운 고정 cohort의 전부 통과만 별도 Host 기능 근거로 사용할 수 있다.

ASan의 오류는 실제 종료 시각 대조 결과 의도한 Central1 SIGKILL 뒤이며 Central2 issuer
boot 전의 보호된 Front Actual 전송이었다. 이후 일반 전송 실패를 허용하지 않는다.
정확한 PID 생존·실제 재가입·SIGKILL·보호 시각·후계 boot 시각·원래 socket/service/method/
bytes/SDK error가 일치할 때만 새 실행에서 expected injected fault로 기록한다. 기존 실패는
수정하지 않는다. 산출물에 오류 원문과 미전송 bytes를 유지하고 독립 서비스/DTC 판정은 계속한다.

## 큐 포화 회귀의 유한 주입 순서

두 번째30개는23/30(Normal6/6, ASan6/6, TSan11/18)이었다. TSan 실패7개 모두
최초 fault ±25ms 구간에 CPU1–7 동시 약800MHz 표본이 있으며, 전체 runtime 중
thermal counter가636 증가했다. 각 fault 순간의 counter 증가는0이므로 온도만을
개별 실패의 단일 원인으로 확정하지 않는다. 전체 서비스 timing은 OPEN이다.

별도 Normal/ASan의 정상·command loss·Front restart·delay·overflow·close-full12개
회귀는10/12였다. 두 overflow는 정상 요청이 시험용9번째보다 먼저 도착해 rx_rejected2와
다른 overflow token을 기록했다. 실제 보호/FIFO/새 Epoch 재시작은 있었지만 기존 정확한
9번째 판정을 완화하지 않는다. Capacity fixture만 정상 work 생성을 멈추고 원래 pending/
command batch를 완결한 뒤 pause request/ack로 consumer 정지를 확인한다. 이후 기존8개
invalid token과9번째 probe를 보낸다. 실수신 overflow가 먼저 보호하고 Central은 그 뒤
관측된 Front 보호에 닫힌다. 정상 제어/서비스 경로, 원래 요청 기한·8개 용량은 유지한다.
동일12개를 새 고정 cohort로 재검증하고 최종 binary의 동일30개 service도 보존한다.

## Idle 파일 관측 비용의 제거

Capacity fixture 수정 후12개 회귀는12/12였다. 최종 binary30개는17/30이었다.
이 실패도 원본으로 보존한다. Idle worker를2초 동안 strace로 관측했을 때 파일 상태가
변하지 않아도 newfstatat46761회, worker CPU0.17s를 기록했다. 계측 overhead가 포함된
이 표본을 실제 native CPU 사용률이나 지연의 단일 원인으로 해석하지 않는다.

후속 후보는 fixture directory에 초기 snapshot 전에 inotify watch를 설치하고 실제
create/delete/rename된 등록 이름만 갱신한다. Owner의 atomic marker API와1ms IO worker
주기·원래 request/write timestamp는 유지한다. Watch 유실·queue overflow/read 오류는
fixture 실패이며 주기적 전체 재조회나 성공으로의 fallback은 없다. 읽기는8×4096bytes/pass로
제한한다. 동일 idle probe, create/remove/rename와 watch-loss 단위 검사, 같은12개 회귀 및
동일30개 service를 각각 새 cohort로 실행한다. 온도에 따른 실행 선별이나 재시도는 없다.

Inotify 후보는 `inotify_add_watch: ENOSPC`로 초기화에 실패했다. 해당 Host의 watch 한도는
변경하지 않았다. 원래 단위 fixture4개(추가 watch-loss 포함)가 Normal/ASan/TSan 모두
초기화 실패였고 monotonic3개만 통과했다. after idle probe도 비정상 종료여서 성능 비교에
사용하지 않는다. 이 후보 source/로그는 별도 보관하고 최종 구현은 검증된 polling worker로
복원했다. 이 후보의12개/30개 native 실행은 NOT RUN이며 성공 분모에 넣지 않는다.
최종 binary가 기존 capacity cohort SHA와 같은지 확인한 뒤 기존 판정을 유지한다.
