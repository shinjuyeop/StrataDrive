# SOME/IP 보조 IO 물리 코어 분리 비교

Base `bbcb86a`, 2026-11-04. 기존 owner Central1/Front2/Rear7, plant3,
SDK4/5/6 배치를 유지한다. 기존 보조 IO15는 이 Host에서 Rear7의 SMT sibling이다.
새 `--separate-aux-io`는 실행 가능한 CPU의 package/core topology를 읽고 위 일곱
CPU와 물리 코어를 공유하지 않는 CPU 중 가장 큰 번호를 선택한다(현재 CPU8).
별도 코어가 없거나 topology를 읽을 수 없으면 시작을 거절한다.

Marker worker, diagnostic journal writer, physical prerequisite writer,
durable Epoch worker, terminal service writer를 같은 보조 CPU로 옮긴다.
모두 SCHED_OTHER/priority0이다. 이전 native-watch와 일반 진단 profile은 CPU15를
유지한다. 요청 topology와 process별 실제 affinity/policy/topology를 원본으로 남긴다.

먼저 같은 새 binary/source로 TSan 정상·ACK loss·Actual loss·250ms marker write 지연을
각각 A/B/B/A 순서로 실행한다. A는 기존15, B는 분리8이다. 총16개(각 배치8개)를
실행 전에 고정한다. 모든 runtime 뒤 독립 service/ordering/placement/response 감사를
수행한다. 실행 중 빌드·감사 작업은 하지 않는다. 온도에 따른 대기/재시도/실패 제외는
하지 않는다. Host 주파수/온도 표본은 별도로 기록하며 외부 부하 통제를 주장하지 않는다.

지원18ms, 결과 최대20ms 및 원래 명령 expiry, Actual30ms, mailbox8, 기존 고장 주입과
DTC 판정은 유지한다. 최초 기한 초과는 원본으로 남긴다. Accepted prefix의 통계는 전체
실패를 대신하지 않으며, 배치만으로 완치·실시간 상한을 주장하지 않는다.

비교 후 분리 배치에서 동일 Normal6/ASan6/TSan18의 고정30개를 실행한다.
파일 조회 최적화는 배치 비교가 끝난 뒤 별도 소스/실행으로 분리한다.

## 역할별 파일 관측

배치 비교16개 runtime 후 별도 후보에서 marker 조회를 명시적 구독으로 줄인다.
Plant4개, Central8개, Front/Rear 각5개를 시작 전에 등록한다. 그 밖의 등록 marker 쓰기는
유지하되 구독하지 않은 이름을 읽으면 오류다. 초기 snapshot·create/remove/rename 관측,
원래 쓰기 요청 시각과 지연·실패 처리 및1ms worker 주기를 유지한다.
Inotify나 시스템 watch 한도 변경에 의존하지 않는다.

이 후보의 별도 idle probe에서 기존34개 전체 관측과 Central8개 관측의 system call 수와
worker CPU 시간을 비교한다. Strace 실행과 비계측 실행은 따로 기록하고 native runtime의
CPU 비율로 일반화하지 않는다. 단위 경계 검사 후 이 후보의 분리 배치로 고정30개와
기존 Normal/ASan 기능 회귀12개를 수행한다. CPU 배치만의 비교16개와 섞어 통과율을 내지 않는다.
