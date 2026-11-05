# 관리 주기 사이의 원본 정지 요청 만료 검증

2026-11-05, allocation-release의27/30 및 SMT의25/30 원본을 보존한 후속 후보다.
SMT는 채택하지 않았으며 조건부60건은 NOT RUN이다. 최종 실행 배치는 원래
SDK I/O2·단일 논리 CPU4/5/6, owner FIFO1/2/7, auxiliary8로 되돌린다.

`release-slot/tsan-stop-request-loss-r3`는 원래 StopRequest source+50ms+1에서
파생 Lifecycle/command 권한이 끝났다. Central은 그 시각 뒤 generic local protection을
선택했지만 다음 VM tick 전이어서 NormalStop 자체의 RequestLost 관측은 없었다.
두 Gateway의 동일 expiry 고장 이력은 있으며 이것을 가짜 Central 원인으로 바꾸지 않는다.

NormalStop의 기존 clock/request/job/handoff 만료 검사를 별도 `poll`로 공개하고
Coordinator의 실제 관측 advance에서 호출한다. 제어 runnable, grant/child 발행,
last_tick 및 원본 요청의 source/expiry는 갱신하지 않는다. 기존50ms inclusive age와
exclusive expiry 그대로다. ControlDeadline 이후의 우선순위도 유지한다.
회귀 시험은 source+50ms에서는 유효,1ns 뒤에는 실제 RequestLost/보호 선택/SD-1105
원본 기록을 요구한다. 지속 poll만으로30ms control deadline이 연장되지 않아야 한다.

기존 구현의 회귀 실패와 새 구현의 통과를 보존한다. Debug·ASan/UBSan 전체,
관련 TSan, 변경 TU 정적 분석과 CARLA6개 target 전체를 검증한다. 이후 소스·binary를
고정해 기능12건, 서비스 Normal6/ASan6/TSan18의30건을 실행한다. 모든 native runtime
후 감사하며 실패 분모를 유지한다. 기존 별개 SDK 갱신 지연을 해결했다고 미리 판단하지 않는다.
