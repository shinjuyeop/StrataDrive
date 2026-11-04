# 단일 SDK I/O 스레드 후보 비교

2026-11-04, base `b740c5e` 및 SDK stage 관측 위의 후보.
첫 관측6건의 service fault 검증은6/6이며 과거의 갱신 실패는 재현되지 않았다.
ACK-loss-r1 정상 armed 구간의 Central→Rear request(service0x5348, session3613,
CRC4089537658)는 send→handler3.000398ms, 수신 kernel→SDK callback 약2.344–2.422ms,
handler17.862µs였다. SDK thread2개가 동일 CPU를 공유하고 TCP→app 처리 thread 이동도
실제 기록됐다. 이것만으로 과거 실패 원인이나 OS runnable 대기 전부를 확정하지 않는다.

## 후보와 고정 비교

`front_run.py --sdk-io-threads 1`은 각 ECU의 기존 SDK CPU4/5/6 위에서
vsomeip `applications[].threads`만2→1로 바꾼다. Default2는 유지한다.
Owner/SDK priority·auxiliary8·sender·dispatcher·주기·source/expiry·queue·SDK 버전은 유지한다.
실제 process thread 이름/개수·CPU/policy와 생성된 설정을 독립 감사한다.

같은 계측 SDK/세 커널 캡처로 A(2),B(1),B(1),A(2)의4 block을 실행한다.
각 block에 ACK-loss, Stop-ACK-loss를1회씩, 총8회이며 실패 제외/재시도는 없다.
Runtime8개를 마친 후 모두 독립 감사한다. 추가 계측이 scheduler에 영향을 줄 수 있으며
외부 부하/온도를 통제하지 않았으므로 작은 표본의 통과율/최댓값은 통계적 개선 입증이 아니다.
Kernel clock100µs 한계를 통과하지 못한 실행은 정밀 kernel 지연 비교에서 실패로 남긴다.
정상 armed→정상 stop 완료 또는 실제 고장 주입/최초 fault까지의 구간을 별도로 보고한다.
재접속·bootstrap 중200ms buffered packet을 정상 제어 지연으로 오인하지 않는다.

후보B에 sanitizer·SDK 오류나 새로운 기능 실패가 없으면 비계측 기존 pinned SDK에서
Normal6/ASan6/TSan18의30개와 Normal/ASan overflow/close-full4개를 별도 실행한다.
이 결과가 미달하면 기본 설정을 바꾸지 않으며 원래 미해결을 닫지 않는다.
30개를 통과하더라도 해당 고정 Host cohort만의 결과이며 Native4ms/Target·M9 전체 수용을
대신하지 않는다. 이전28/30과 관측 cohort를 합친 통과율을 만들지 않는다.
