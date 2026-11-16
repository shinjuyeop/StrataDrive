# M10 owner wait V2 — 텐서 재사용·대기 계측 후보

[V1](../m10_owner_wait_v1/README.md)의 준비 지연 재발을 조사하는 별도 후보다.
매번 만드는 float32 임시 배열을 기존 값 일치 검증된 NCHW 재사용 버퍼로 바꾼다.
물리 쪽 모델 준비와 영상 추론에 명시적으로 적용하며 기본 설정은 유지한다.
실패해도 관측 스레드 CPU 복원 결과를 기록하도록 보완했다.

조용한 새 프로세스40회 비교에서는 양쪽20/20 모두 통과했다. CARLA 동시 실행 때의
119ms 텐서 지연은 재현하지 못했으므로 해결되었다고 판단하지 않는다.
Python505·동결93검사 PASS, 소스1490개 동결을 완료했다. 동일 owner 대기 계측 모듈을 재사용한다.
[준비 결과](prepared.json), [후보 적용 검사](workspace-audit-check.json), [공유 파일 복원](post-freeze-restoration.json).
[프로토콜](../../perception-owner-wait-v2-protocol.md)을 따른다.
추가 검사기의 종료 후 상태 판독을 실행 전에 수정하고 재동결했다.
[이전 준비본](preflight-01/disposition.json)은 보존하며 실제 실행에는 사용하지 않았다.

실행 순서는30초→30초→300초이며 첫 실패에서 중단한다. 원래 준비100ms·HV30ms·
source 시각과 검사 순서는 유지한다. 실제 실행 전 상태는 NOT STARTED다.
70% 조건을 적용하는 새 owner PID의 좁은 관리자 helper 단계만 필요하다.
장기 안정성·native 인지 수용·전체 장면·각 Jetson 배포·M10은 OPEN이다.
