# SDK SMT 후보의 조건부 고정 확인 시험

2026-11-05, 첫 SMT30건 중23건의 runtime 완료·감사 전 선언한다.
첫30건의 독립 서비스/ordering/timing/response 감사가 모두 통과할 때만 실행한다.
어느 하나 실패하면 동일 후보 재시도로 바꾸지 않고 원인 분석으로 돌아간다.

동일 세 binary·원본 SDK·SMT 배치·기한을 유지한다. TSan의 normal, ack-loss,
actual-loss, stop-request-loss, stop-ack-loss, normal+250ms signal delay의6개를
순서대로10round, 총60건 실행한다. 명시한60건은 중간 실패에도 끝까지 보존한다.
모든 native runtime 뒤 각 원본을 네 감사기와 mutation으로 검증한다. 최초 SMT30건과
이60건은 별도 분모이며 검증을 마친 뒤 그때의 소스/도구/결과를 보관한다.

이 시험은 드문 기존 TSan 갱신 실패에 대한 추가 확인이다. 현재 Host의 관측을
모든 OS 부하·하드웨어의 실시간 보장 또는 M9 전체 완료로 확대하지 않는다.
