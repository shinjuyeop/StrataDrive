# Terminal service finite soak

Host quiet/sanitizer 분리 계약을 유지하며 비계측 normal build에서 시험한다.
기존500ms 정상 관측을 유지하는 기준1회, 각 Epoch2/3 정상 armed 구간을60s 유지하는
quiet3회와 loaded3회를 고정한다. Loaded는 기존 runtime load-child를 owner CPU1/2/7에
SCHED_OTHER로 배치하며 실제 affinity/policy/priority/CPU time/window와 생존을 기록한다.
owner FIFO·SDK I/O2 CPU4/5/6·plant3·aux8은 기존 수용 배치를 유지한다.

확장하는 것은 정상 관측 길이와 전체 fixture supervisor/trace 사전 용량뿐이다. 제어20ms
envelope,10ms renewal/18ms support, INIT/RunLease/expiry/response/정지/clear의 기한을 바꾸지
않는다. 원본 native service·ordering·timing·physical response 독립 감사를 전부 적용한다.
최종 duration/정상 구간 release 수·load-control과 종료를 추가 감사한다. 실패를 제거하거나
cohort를 통과할 때까지 재실행하지 않는다. 실패 후 수정한 후보는 새 cohort로 구분한다.

빌드·sanitizer·큰 raw 분석과 wall 실행을 겹치지 않는다. 약130s/run의 유한 Host 관측이며
24시간/무제한 운영, Target timing, 무제한 journal 보존 수용으로 확대하지 않는다.

첫 cohort는 기존 고정+.2m/s² 입력을60s 유지하여 정지 budget을 초과했고131072-row SDK
trace가 넘쳤다. 긴 캡처에서 실제 CRC32C 충돌도 검출했다. 원본 분모7개를 유지한다.
수정 후보는 긴 profile에만 실제 validated wheel로0.5m/s 목표·P0.5/s·±.2m/s² demand를
공급한다(모델 wheel radius .3m). 기존0.5s profile과 실제 정지 기한은 유지한다.
SDK 로그도 사전 할당하고 원본 epoch/token/sender/receiver+CRC로 연결한다. 원본 identity가
없는 과거 로그의 모호한 CRC는 계속 거절한다. 같은7개 조건을 새 후보로 다시 고정한다.

수정 후보2의 기준 실행은 통과했다. 첫60s quiet에서 실제 ECU/물리/서비스는 통과했으나
Leaf input trace 기본12000건이 가득 차 갱신 증거가 불완전했다. 해당 raw를 보존하고 후속
5조건을 실행하지 않았다(완료7/7로 세지 않음). 후보3은 Leaf trace도 관측 길이에 맞춰 사전
할당하고 capacity 소진을 runtime verdict에 명시한다. 제어/통신 queue 용량은 바꾸지 않는다.

후보3의 실제 runtime/정상 구간은 통과했으나 quiet1/2에서 TCP capture에 각각 누락 구간이
있었다. 원본 검사는 sequence wrap으로 설명되지 않는 실제 byte gap을 확인했다. 실행 중이던
quiet3은 정상 종료시키고 loaded3조건은 시작하지 않았다. 후보4는 CPU0의 비 RT capture에서
최대256MiB/2000000 packets를 메모리에 보관한 후 종료 시 파일로 쓴다. SO_RCVBUF 요청/실제값,
PACKET_STATISTICS drop, 실제 affinity와 overflow를 기록하고 누락이면 수용하지 않는다.
별도 control/diagnostic queue나 expiry는 변경하지 않는다. 전체 TCP/CRC 감사도 유지한다.
