# SDK의 owner 코어 공유 실험 — 미채택

2026-11-05, [사전 protocol](../../sdk-owner-core-protocol.md)의 고정30건은
**23/30**(Normal6/6·ASan5/6·TSan12/18)이다. 이 설정은 채택하지 않았다.
[복원 기록](restoration.json)대로 launcher/배치 감사/시험을 egress 후보로 되돌렸고,
[활성 source2453개 동일성](restored-source-check.json)을 확인했다. 현재 기본 SDK는
CPU4/5/6 각 한 개, SCHED_OTHER/priority0, IO2 thread다.
실험을 재현할 source/launcher는 이 폴더의 `runtime-sources.tar.gz`에 있다.

C++/SDK binary는 egress 후보와 같았다. SDK affinity만 Central[1,4], Front[2,5],
Rear[6,7]로 확대했다. Owner CPU와 FIFO11/18/18, Plant3, 보조 IO8, 모든 원래
source/expiry/20ms result/18ms support를 유지했다. 실제 topology·thread affinity/
policy 감사와 mutation을 실행했다. 이전 SMT 실험과 다르지만 개선을 입증하지 못했다.

ASan ack-loss의 Rear reset104 외에 TSan6건이 시나리오 전제/정지 detector 검사에서
실패했다. 특히 actual-loss-r2와 stop-ack-loss-r2는 초기 실행이 실패해 이후 증거가
없으므로 ordering/timing/response도 실패다. 누락을 면제하지 않았다.
[원본 결과](results.json)를 따르며 정상 prefix나 일부 latency 통과를 전체 성공으로 세지 않는다.

Python39개와 이전 배치 mutation8개가 통과했고, 복원 뒤 Python38개와 기존 배치
감사를 다시 통과했다. C++ 전체/기능12건을 이번 재실행으로 표시하지 않는다.
[SDK 원문과 시각](sdk-cause.json), [trace 관측](egress-audit.json)을 보존한다.
Trace 관측의 `coverage_complete=false`는 초기 실패로 ACK coverage가 없는 case이며
시험 성공을 뜻하지 않는다. [포장 시 동일성](identity-checks.json)은 실험 source 시점이다.

현재 활성 후보의 실패는 [egress 근거](../m9_egress/README.md), 전체 완료 조건은
[프로젝트 상태](../../../project-status.md)를 따른다. 이 실험의 실패도 원래 분모에 남는다.

보관본17개의 원본 파일35,637개를 [바이트 대조](archive-verification.json)했다.
[압축 해제 후 감사 재현](archive-recheck.json)에서 정상 성공, 기존 SDK 오류 실패,
미채택 배치의 원래 timing 감사 결과가 각각 유지됐다.
