# SDK SMT 배치 후보 — 미채택

2026-11-05, [사전 protocol](../../sdk-smt-protocol.md)의 고정30건 결과는
**25/30**(Normal6/6·ASan6/6·TSan13/18)이다. 개선 근거가 없어 활성 runner에서 후보
선택지를 제거하고 기존 SDK I/O2·단일 논리 CPU 배치를 유지한다.

동일 바이너리를 사용해 SDK4/5/6의 affinity만4/12·5/13·6/14로 늘렸다. 각 쌍은 같은
물리 코어의 SMT sibling이며 owner/plant/auxiliary 물리 코어와 구분했다. 실제 thread
수·affinity·policy와 topology를 독립 감사했다. 기한이나 SDK 오류 whitelist는 바꾸지 않았다.

실패는 `tsan-normal`의 실제 Broken pipe SDK 종료 오류, `tsan-stop-request-loss`의
만료 경계 Central 원인 관측 누락, `tsan-normal-slow-signals-r2`의 갱신 거절,
`tsan-ack-loss-r3`·`tsan-actual-loss-r3`의 정지/transport 선행 실패5건이다.
[원본 오류/최초 fault·token](failed-cases.json), [개별 결과·명령·해시](results.json)를 보존한다.

Python bookkeeping32개·SDK 관측/배치9개 및 기존 single-CPU timing 재감사/변조 거절이
통과했다. [바이너리 동일성](binary-identity.json)은 직전 release-slot 후보와 같다.
후보 소스와 launcher/감사기·도구는 `runtime-sources.tar.gz`, `validation-tools.tar.gz`에
있다. 현재 활성 runner의 기능으로 오해하지 않는다.

30건 실행 중 미리 선언한 [조건부 TSan60건](confirmation-protocol.md)은 첫30건 감사가
실패했으므로 **NOT RUN**이다. 성공까지 재시도하지 않았으며 분모에 넣지 않는다.
[최종 처리](final-disposition.json) 후 별도 Stop deadline poll 수정이 이어진다.
