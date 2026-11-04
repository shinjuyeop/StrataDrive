# Native 서비스 시험 신호와 owner 실행 간격

2026-11-04, base `85eca94`. 기존 `m9_completion/verified-*` 15개 중 미통과4개를
후속 조사한다. 과거 결과를 덮어쓰거나 재시도 성공만 골라 분모를 만들지 않는다.

## 사전 판정 기준

- 동일3-ECU, SimpleVehicle, 실제 diagnostic journal과 명시적 service socket을 사용한다.
  Central/Front/Rear CPU1/2/7, plant3, diagnostic·시험 신호 IO15, SCHED_OTHER다.
- Host10ms allocation,18ms support,30ms Actual age,20ms result budget 및 기존
  session/stop/drain 기준을 유지한다. Native4ms timing 수용과 구분한다.
- Normal/ASan/TSan 각각 정상, durable ACK 손실, Brake Actual 손실, StopRequest 갱신 손실,
  실제 Stop ACK 손실의5개, 총15개를 정해진 순서로 한 번씩 실행한다.
- 추가로 각 profile의 정상 service에서 `armed` 파일 쓰기를250ms 지연한다. 지연은
  IO worker에만 적용한다. 제어시계·DTC·권한·물리 모델·Actual을 변경하지 않는다.
- 전체18개의 원본 exit/log/journal/PCAP를 보존한다. 정상은 실제서비스/독립감사 모두
  통과해야 한다. 주입 고장은 runtime FAIL을 유지하고 기존 독립 fault auditor가 실제 주입,
  최초 원인, 원본 기록, 무허위Complete/clear를 판정한다. 기존 mutation 검사도 실행한다.
- 쓰기 지연의 원본 source/request 시각과 write begin/end를 기록한다. 실제 writer CPU/policy,
  정상 service 완료와 owner poll gap을 함께 확인한다. 단일 빨라진 실행으로 이전 실패의
  유일 원인이나 모든 scheduler 부하의 수용을 주장하지 않는다.
- 시험 신호는 오케스트레이션 정보다. 읽기·쓰기 완료가 제어 authority, actual evidence,
  DTC durable receipt를 대신하지 않는다. IO 실패는 시험 실패로 남긴다.

## 원본에서 확인한 실패

첫3개는 Epoch2 release ACK255와 normal arm 뒤 각각98.674229/192.834067/43.648841ms의
owner gap 및 RX overflow다. 원본 코드는 arm 직후 `armed`를 owner에서 open/write/close했다.
기존 기록에는 syscall별 시간이 없어 디스크 지연을 유일 원인으로 확정하지 않는다.

TSan Stop ACK case는 이전 명령 만료783780184420358ns 뒤 새 명령의 Front 수신
783780184874095ns, 즉453737ns 늦음이다. Front CommandExpired가 먼저이며, Central은
실제 negative result를 SD-1002/0x20006으로 기록했다. ACK 유실은 아직 주입되지 않았다.
새 명령의 미래 만료로 이미 만료된 이전 authority를 복구하면 안 된다.

## 첫 후속 실행에서 추가로 발견한 순서 결함

시험 신호 IO를 분리한 첫18개 실행에서 Normal/ASan은 각5/5와250ms 지연을 통과했다.
TSan은3/5이며 지연 조건도 미통과다. 원본을 `campaign`으로 보존한다.
TSan ACK/Actual loss의 선행 실패2개는 새 VehicleRequest가 진행 중인 명령의 Rear 전달보다
앞서 도착했다. Actual loss 원본은 request234(부모 source788375146461113)가 먼저 수용된 뒤
command235(부모 source788375136247092)가 도착해 ParentMismatch로 거절됐다.
이는 timeout을 늘려 해결할 문제가 아니다.

AsyncCoordinatorPort에서 진행 중인 Front→Rear batch가 끝날 때까지 다음 VehicleRequest를
기존 owner budget 크기의 유한 FIFO에 보류한다. 원래 source/expiry와 접수 시점의20ms 결과
기한을 유지하고, 실제 enqueue 때만 token을 부여해 원격 token 순서를 유지한다. 만료·full은
실패로 닫으며 나중 ACK로 되살리지 않는다. 새 Epoch에서만 폐기한다. Gate/permission/정지
보호 처리는 계속 실행한다. 동일18개를 수정 후 별도 cohort로 다시 검사한다.

## SDK와 owner CPU를 나누는 후속 환경

순서 수정 후 `ordered-campaign`18개에서 독립 원본 ordering 감사는 모두 통과했다.
Normal/ASan은 각5/5 및 지연 조건을 통과했지만 TSan은2/5이며 지연 조건도 미통과다.
정상 TSan의 Epoch3에서 Rear 원래 명령 만료788925219504313ns보다 Central의 다음 Rear
enqueue788925220334480ns가 늦었다. 원래 보호/negative 결과를 유지한다.

기존은 SDK와 owner가 각 같은 CPU를 공유했다. 다음 `--split-owner-io` profile에서는
SDK thread의 시작 affinity를 Central4/Front5/Rear6으로 고정하고, 실제 main owner만 기존
CPU1/2/7로 이동한다. Plant3·writer15, SCHED_OTHER, 모든 원래 시간 기한은 유지한다.
요청 CPU뿐 아니라 owner/SDK thread 실제 affinity/policy를 보존한다. 변경 소스·바이너리
빌드가 모두 끝난 뒤 같은18개를 한 번씩 실행한다. 이전 profile의 미통과를 지우지 않으며
새 결과가 통과해도 임의 CPU 배치·SCHED_OTHER 전체의 timing 보장으로 올리지 않는다.

`split-campaign`에서 Normal/ASan은 각5/5, TSan은1/5이며250ms 지연은3/3이다.
원본 ordering은18/18 통과했고, TSan의 지원 기한 초과는 남았다. 별도 placement 감사의
첫 판본은 process 최초 Epoch2 `armed` marker를 최종 Epoch3 summary와 비교한 오류가 있었다.
원래 실패 로그를 유지하고 같은 원본 Epoch2 event/쓰기 시간·지연 중 command-enqueue로
재심사한다. 이는 runtime 재실행이나 실제 service 실패의 재분류가 아니다.

다음 `--owner-fifo` 조건은 동일 split 배치에서 기존 Host 우선순위 Central FIFO11,
Front/Rear FIFO18을 적용한다. SDK/plant/기록 worker는 SCHED_OTHER다. 실제 설정/읽기 검증이
실패하면 session을 열지 않는다. Native4ms execution-watch나 Target 수용은 주장하지 않는다.
고정18개 시나리오·원본20ms/18ms/30ms 기한과 모든 mutation 검사는 그대로 적용한다.
