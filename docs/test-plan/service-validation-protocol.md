# 서비스 기능·동시성·실행 시간의 분리 판정

2026-11-05, base `ef5d648`. 사용자가 과도한 시험 조건의 조정을 승인했다.
이 protocol은 실행 전에 고정한다. 기존30건의27/30과 M4 TSan wall 실패를
삭제하거나 새 기준의 성공으로 덮어쓰지 않는다.

## 판정 축

- `split-v1` native 서비스: 비계측 RelWithDebInfo normal binary로 정상,
  durable ACK 손실, Actual 손실, StopRequest 손실, Stop ACK 손실,
  signal writer250ms 지연의6조건을3회, 총18건 순차 실행한다.
  기존 물리·DTC·재가입·서비스·ordering·placement·response 감사 및 mutation을
  모두 통과해야 한다. CPU/priority·SDK2 threads·원래20ms envelope·10ms 갱신/
  18ms support·source/expiry·보호/물리 응답 제한은 그대로다.
- ASan/UBSan와 TSan: `service_sanitizer_suite.py`가 고정한 owner/transport,
  diagnostic journal/replication/service, 논리 SIL 및 실제 동시성 시험을 실행한다.
  각 시험 성공과 sanitizer 오류0을 요구한다. 논리 시각의 deadline 경계는 그대로
  검사한다. 실행이 느려져도 가짜 시각이나 만료 연장은 넣지 않는다.
  전체 시험 executable의 운영 watchdog은600초이며 제품의 control deadline과
  별개다. ASan 첫 실행은180초 watchdog으로 시작했으며 그 runner/hash도 보존한다.
  TSan 시작 전 논리 시나리오11개 묶음의 계측 실행 시간을 고려해 운영 상한을 정했다.
- `M4AsyncWall.*` 두 시험은 sanitizer의 정상 완료 조건에서 제외하고 비계측
  실행으로 별도 검증한다. 일반 CTest 목록은 바꾸지 않는다. 계측 native 시험이
  목적 fault 전까지 도달하지 못한 과거 기록은 미완료로 남으며, 정상/native18건과
  논리 fault 시험이 그 기능을 별도로 확인한다. 경고0만으로 미실행 경로를 세지 않는다.
- 이번 수용은 Host quiet 서비스 범위다. 부하/장시간·WCET·native4ms/Target,
  CARLA silent loss subinterval·Clock·bootstrap·전체8-role matrix는 별도다.

## 의도한 연결 종료

새 규칙 `retired-central-feedback-v2`는 실제 Central1 SIGKILL 뒤, Central2 원래
boot 이전의 Front/Rear1 feedback 연결에서 발생한 reset104/broken-pipe32만 분리한다.
정확한 로그 출처·IP/port/service/method/client·payload 상한을 확인한다.
두 surviving PID가 그대로이고 실제 정상 종료했으며, 원래100ms 내 로컬/물리 보호,
unclean successor와 실제 새 Epoch/8-role Release 재가입이 있어야 한다.
연결 오류가 보호 선택보다 먼저 발생할 수 있다. 모든 원문은 보존한다.
이 분류 자체는 서비스 성공이나 고장 검출/DTC의 증명이 아니다. 독립 시나리오 감사가
그 후의 동작을 검사한다. 새로운 세션 오류, 큐 포화, 다른 SDK 오류와 sanitizer 경고는
여전히 실패다. 로그의 wall→monotonic 매핑은 기존 단일 표본이며 독립 Clock 검증이 아니다.

## 검증·보존

오류 시각/연결/세대/보호/물리 응답/재가입 누락의 거절 회귀와 campaign/sanitizer
분모 검사를 먼저 실행한다. 기존 활성30건은 원본 파일을 바꾸지 않고 새 SDK 분류만
메모리에서 재감사해 별도 보고한다. 결과가 달라지면 원래와 새 결과를 모두 기록한다.
Sanitizer build/test가 끝난 뒤 native18건을 한 번 실행한다. Native 중에는 build나
무거운 분석을 겹치지 않는다. 모든 runtime 종료 후 감사하며 성공을 위한 재추첨은 없다.
소스·binary·명령·모든 종료값·실패·원본 archive와 SHA256을 보존한다.
