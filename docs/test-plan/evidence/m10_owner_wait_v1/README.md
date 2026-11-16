# M10 owner wait V1 — 대기 사유 계측 준비

[Host clock V2](../m10_host_clock_v2/README.md)의 최초 HV 만료를 구체화하는 별도
진단 후보다. 원래 HV30ms·제어 판단·수치 적분·sleep 요청은 유지한다.
물리 단계별 thread CPU/문맥 전환/페이지 fault와 pump 대기 사유, 명시적 sleep,
루프 바깥 시간을 고정 크기로 기록한다. 파일 출력은 원래 사후 trace 조회에서만 한다.

별도 CARLA 모듈 빌드 완료. Python504·동결88검사 PASS이며 변경 없는 native의
기존207검사·30/300 allocation 검사를 재사용했다.10,000회 비용 측정에서 stamp
p95는361ns, 최대16,709ns였다. OwnerPath1688바이트로5분60000구간 약96.6MiB다.
조용한 비용 측정은 live 최대 지연을 보장하지 않는다.

[프로토콜](../../perception-owner-wait-v1-protocol.md), [준비 결과](prepared.json),
[계측 비용](stamp-cost.json), [공유 파일 복원](post-freeze-restoration.json)을 따른다.
기존 동일70% 제한을 사용하려면 새 owner PID에 대한 수동 helper 실행이 필요하다.
실행 전 상태는 NOT STARTED이며,30초→30초→300초에서 첫 실패에 중단한다.
원래 실패·모든 영상은 보존하며 장기 안정성·인지 수용·M10 종료는 OPEN이다.
