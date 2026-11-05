# SDK의 두 물리 코어 실행 기회 검증

2026-11-05, egress 후보 이후 별도 고정30건. 선행 기능12/12·서비스27/30의
실패와 소스/바이너리를 보존한다. 이 후보는 C++/SDK binary를 변경하지 않는다.
SDK는 기존2개 IO thread를 갖지만 한 logical CPU4/5/6에 묶여 있었다. 새로운
opt-in `--sdk-owner-core`는 각 SDK의 전용 CPU와 해당 FIFO owner의 CPU도 허용한다:
Central[1,4], Front[2,5], Rear[6,7]. 두 CPU가 서로 다른 physical core인지 검증한다.
이전 SMT pair 실험과 다르며 성능 개선을 미리 확정하지 않는다.

Owner는 기존 CPU1/2/7 및 FIFO11/18/18 그대로다. SDK는 SCHED_OTHER/priority0으로
owner보다 우선하지 않는다. Plant3·보조 IO8은 그대로다. 시스템 governor/thermal/
커널 정책은 바꾸지 않는다. 원래20ms result·18ms support·10ms allocation·source/
expiry·queue 용량·SDK 오류 판정도 유지한다.

SDK IO thread 수·실제 affinity/policy, main owner TID/affinity/priority, 독립 process
snapshot topology를 검사하고 요청만으로 성공 처리하지 않는다. Legacy profile에서
새 affinity를 허용하지 않는다. 설정 누락/다른 CPU/SMT/잘못된 policy 변조는 거절한다.
Python 단위와 기존 원본의 배치 감사 동등성을 먼저 검사한다. C++ source와 binary
hash가 egress 후보와 같은지 검증한다. Native30건은 Normal6/ASan6/TSan18의 동일
고정 scenario로 한 번 실행하며 runtime 종료 뒤 전체 감사를 수행한다. 실패도 모두
보존한다. 기본 profile의 기능12건과 전체 Debug/ASan은 이번 재실행으로 표시하지 않는다.
강제 종료 첫 TCP reset은 질문 중인 별도 기준 결정이며 임의 면제하지 않는다.
전체 M9, 메모리 기반 TSan wall 실패, native4ms/Target 수용은 별도다.
