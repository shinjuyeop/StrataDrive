# 프로젝트 상태

정리 기준·최신 검증: **2026-11-06**.
이 문서가 현재 구현·수용 범위와 다음 작업의 기준이다. 실행 중인 미기록 변경은 완료로 세지 않는다.

## 단계별 현재 판정

| 단계 | 판정 | 근거 |
| --- | --- | --- |
| M0 | 요구·구조 baseline 확정 | [M0 검토](archive/milestone-reviews.md#m0) |
| M1–M2 | 통신·actuator/EV component 기술 검사 완료; 학습자 review 별도 | [M2 검토](archive/milestone-reviews.md#m2) |
| M3 | Host FIFO 기준 사용; 과거 timing 예외·전체 종료 OPEN | [M3 검토](archive/milestone-reviews.md#m3) |
| M4 | Host IO/FIFO component 한정 수용; 전체 NOT CLOSED | [Host 수용](archive/milestone-reviews.md#m4-host) · [종료 검토](archive/milestone-reviews.md#m4) |
| M5 | Central↔Front/Rear 3-process SOME/IP Host FIFO 기능 한정 수용 | [실행 근거](test-plan/evidence/m5_someip_rear_adapter/README.md) |
| M6 | **Host quiet SIL/Python MIL 범위 CLOSED** | [종료 검토](archive/milestone-reviews.md#m6) · [최종 물리 응답](test-plan/evidence/m6_physical_response/README.md) |
| M7 | **시뮬레이션 시간 기능 통합 CLOSED / 실제 wall 실시간 수용 별도 OPEN** | [7개 실제 실행·독립 감사](test-plan/evidence/m7_carla_integrated/simulation-time/README.md) · [ADR-0065](archive/design-decisions.md#adr-0065) |
| M8 | **제어기·고정 fixture 기능 SIL 범위 CLOSED / 전체 Reference·wall·Target 별도 OPEN** | [종료 검토](archive/milestone-reviews.md#m8) · [마감 무결성](test-plan/evidence/m8_closeout/README.md) |
| M9 | **선언한 유한 Host·simulation10ms 기능 범위 CLOSED / wall·Target·장기 운용 별도** | [진단 계약](interfaces/diagnostics.md) · [마감 검증·원본·제한](test-plan/evidence/m9_followup/README.md) |
| M10–M11 | 속도 제안·BMS 가용력·native 보호 연결; 인지/학습 모델·전체 통합 NOT RUN | [제안 계약](interfaces/supervised-speed-proposal.md) · [로드맵](roadmap.md) |
| M12–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

기술 검사와 학습자 설명·수용은 별도다. Component PASS를 전체 system/Target PASS로 올리지 않는다.

## M9 기능 범위 마감

[최종 근거](test-plan/evidence/m9_followup/README.md)는 남아 있던 부하 시 명령 갱신과
silent Front packet loss의 실제 CARLA 응답을 검증했다. 명시적 SDK FIFO1은 기존 전용
CPU4/5/6에만 적용한다. 고정 기준1·quiet3·loaded3은 **7/7**, 뒤이은 서비스6조건×3회는
**18/18**이다. 서비스 고장12건은 실제 거절/무승인 commit0을 검증한 것이며 원래 runtime
FAIL을 성공한 서비스로 바꾸지 않는다. Owner 우선순위·20ms envelope·10ms 갱신/18ms
support·Front-before-Rear 의존과 원래 만료는 유지했다. 감사 대상404821개 요청의 관측 최대
왕복2.295638ms·최소 만료 여유17.704362ms는 이 유한 실행의 값이다.

CARLA는 기본 정상1·새 판정 정상1·silent loss2의 새 서버 실행 **4/4**를 통과했다.
각6000개 실제 physics/에너지 정산·6001개 native JSON 관측 재현·원본 DTC byte journal·
실제 body/4-wheel 정지·서버 종료130을 확인했다. Silent loss는 실제 gateway/Leaf 감시기의
SD-2001과 fresh torque/pressure/wheel을 연결한다. 서로 다른 producer의 event는 전체
run/producer/sequence와 occurrence로 연결하며 가짜 Central DTC를 만들지 않는다.

사용자가 허용한 수용 기준 조정은 명시적 `sampled-actual-v1`의 **10ms 물리 sample/hold**다.
Normal Command의 원래 권한은 현재 barrier에서 검사하고 Actual·wheel·permission·RunLease는
전체 다음10ms를 덮어야 한다. 구간 안의 원래 command 만료를 그대로 기록하고 native 감시기
기한도 유지한다. 다음 barrier에는 실제 native 결과가 필요하다. 기본 whole-interval·wall
판정과 보호 선택/새 LocalProtection Actual 조건은 유지한다. Subinterval 연속 물리 응답으로
해석하지 않는다. [사전 계약](test-plan/carla-sampled-actual-protocol.md)을 따른다.

변경 CARLA component는 Release·Debug·ASan/UBSan·TSan 각각52개, 총208개를 통과했다.
Python54개와 잘못된 profile/실행 환경9조건 거절, 변경 C++ 정적 검사·UE 빌드도 확인했다.
실행기 가상환경 경로 오류의 준비 단계 실패·중단과 수정 전 component 실패도 분리 보존했다.
앞선 Clock/Power 복구·명시적 clear·비활성 journal archive/restore 근거와 합쳐 선언한 M9
기능 범위를 마감한다. Native4ms/wall·Target, 무제한 보존/자동 용량 회수, 다른 kernel의
Clock 운영과 학습자 review는 별도다. 과거 실패는 당시 분모와 함께 [보관 이력](archive/implementation-history.md)에 유지한다.

## 이전 milestone 소프트웨어 후속

제동 배분 피드백을 PI의 음수 적분 보류까지 연결하고, journal data 쓰기 전에 영속적인
pending 의도를 남기도록 보강했다. 제동 용량/응답 보호·source/expiry·DTC 코드·명시적
clear 조건은 유지한다. 독립 모델 동등성, 실제 allocator 연결, 저장 오류/프로세스 중단과
복원 실패 경계·새 CARLA S03 8000구간은 [후속 검증](test-plan/evidence/milestone-followup/README.md)에 기록한다.
저장된 S03의 native 재생과 새 서버 S03 실제 실행을 따로 기록했다. 실제 전원 차단/자동 용량 회수와
과거 timing·renderer 원인 규명을 완료한 것으로 올리지 않는다.

후속으로 [세션 경계 EpochRecorder](interfaces/epoch-retention.md)의 활성 기록 창 회수·DTC 상태
이관과 CLI, [가용력 목표·M10 Host 속도 제안](interfaces/supervised-speed-proposal.md)의
Supervisor→governor→기존 PI/배분 연결을 추가했다. [검증과 제한](test-plan/evidence/remaining-improvements/README.md)을
따른다. 이어서 선택형 native speed 실행에 receiver BMS 가용력·원래 dependency·coordinator 보호·DTC를
연결했다. [연결 검증](test-plan/evidence/runtime-speed-connection/README.md)을 별도로 보존한다.
기본 경로와 기존 milestone 증거는 유지하며 M7 전체 wall 연동은 사용자가 후순위로 두었다.

## 현재 구현과 수용 경계

| 영역 | 현재 범위 | 상세 근거 |
| --- | --- | --- |
| 통신·세션 | Central/Front/Rear 3-process SOME/IP, 8-role INIT/Release/RunLease, 원래 source/expiry와 새 Epoch 재가입 | [SOME/IP 계약](interfaces/someip-rear-adapter.md) |
| 모델·제어 | 독립 종방향 MIL, C++ 모델 동등성, 고정 속도·경로 fixture, 방향별 배분 포화 피드백과 정상 정지/HV-off | [M8 종료 검토](archive/milestone-reviews.md#m8) |
| CARLA | 원본 CAN/P05 Actual의 NoDrive 적용, solver work의 단일 EV 정산, simulation-time 기능 | [Plant 계약](interfaces/carla-plant-adapter.md) · [실행 안내](carla-guide.md) |
| 진단 | 원본 검출·인과 ID·보호·Actual·DTC, qualified 복구와 명시적 clear, 재기동/연속성 심사 | [진단 계약](interfaces/diagnostics.md) |
| 기록 보존 | 유한 journal, 비활성 store의 독점 잠금 archive/restore, byte 동일한 이력 복원 | [보존 계약](test-plan/diagnostic-retention-protocol.md) |

문서 이력과 공통 진단 발행기·감사 decoder를 정리한 뒤의 동등성·회귀 검증은
[M9 이후 구조 정리 근거](test-plan/evidence/post-m9-refactor/README.md)를 따른다.

## 남은 문제와 제한

- Native4ms와 전체 wall 실시간 수용, 실차/Target 적합성은 별도다. 짧은 비영상
  `wall5-hv50-v1` 실행을 장시간·영상·고속 보장으로 확대하지 않는다.
- UE renderer/GC·로딩 중 종료와 일부 과거 서버 종료 실패의 근본 원인은 남아 있다.
  완료된 M9 네 서버의 정상 종료와 구분한다.
- 전체 Reference ODD, Planner/localization과 온라인 경사/저항 추정은 후속이다.
  BMS limits/wheel 기반 가용력과 governor·Supervisor는 선택형 native speed 경로에 연결했다.
  저항은 명시적 SIL 보정값이며 학습 모델은 없다. 새 SupervisedSpeed monitor의 qualified Passed와
  안전 정차 후 명시적 clear를 논리 SIL에서 연결했다. 입력 복구·재기동으로 DTC를 지우지 않는다.
  제동 피드백 v3는 component/원본 입력 재생과 새 고정 S03 실행을 통과했다. 전체 ODD 수용은 별도다.
- 기본512-event 경계, 비활성 archive/restore는 유한 운용이다. 새 EpochRecorder는 새 세션에서
  DTC 상태와 원본 이력을 보존하며 활성 창을 회수한다. Outbox/Inbox 및 전용 SOME/IP의 세션 전환·
  수신기 강제 종료/재시작을 연결했다. 고정 membership의 세션 순서 장벽과 ContextualOutbox family,
  실제 SOME/IP 원본 세 stream의 재시작 병합도 [검증](test-plan/evidence/epoch-merge/README.md)했다.
  선택형 live 3-ECU 경로의 Front/Rear 교체와 Central spool도
  [검증](test-plan/evidence/native-epoch-replacement/README.md)했다. 역할별 stream을 고정하고
  실제 새 INIT에서 producer 세대를 전환한다. Central 프로세스 교체·service의 family 적용,
  단일 epoch 무중단 회전, 디스크 삭제/외부 보존 정책과
  전체 매체/전원 장애, 다른 kernel의 Clock 운영은 별도다. syscall 저장 오류와 프로세스
  중단 검증은 추가했지만 실제 전원 차단/캐시 소실 시험을 대신하지 않는다.
- 과거 M3/M4·SDK timing/sanitizer 실패와 미채택 후보는 당시 분모로 보존한다.
  최신 환경 probe에서도 FIFO는 가능하나 tracefs/perf 접근이 차단되고 비대화형 sudo 권한이 없다.
  따라서 과거 timer→wakeup→switch/IRQ 원인을 새로 규명한 것으로 올리지 않는다.
  기술 검사 통과로 학습자 설명·최종 수용을 대신하지 않는다.

## M7 종료 조건

시뮬레이션 시간 기능 범위는 CLOSED다. 연속 주행·회생/제동·영상·보호와 고장7조건의
[원본 및 독립 감사](test-plan/evidence/m7_carla_integrated/simulation-time/README.md)를 기준으로 한다.
Wall/Target과 전체 renderer 안정성은 별도이며 [당시 종료 검토](archive/implementation-history.md#m7-종료-조건)에 보존한다.

## M8 종료 조건

제어기·고정 fixture 기능 SIL 범위는 CLOSED다. 모델/C++ 동등성, 속도/경로 폐루프,
고정30km/h fixture·추진 포화·정상 정지를 [종료 검토](archive/milestone-reviews.md#m8)와
[마감 무결성](test-plan/evidence/m8_closeout/README.md)으로 확인했다. 전체 Reference·wall·Target은 별도다.

## 다음 작업

M10의 상태 기반 Host 속도 제안 입출력·history·risk·fallback 경계는 첫 프로파일로 고정했다.
[감독 DTC의 qualified 복구·해제와 EpochRecorder 송수신 연결](test-plan/evidence/supervised-recovery-delivery/README.md)을 추가했다.
고정 송신원 집합의 [세션 순서 장벽과 family 병합](test-plan/evidence/epoch-merge/README.md)을 추가했다.
이어서 [live Front/Rear 교체·Central spool·원본 prefix 재전송](test-plan/evidence/native-epoch-replacement/README.md)을
연결했다. 다음은 CARLA에서 새 감독 제어의 복구 주행 검증과 Central 프로세스 교체/service의
family 적용이다. CARLA는 현재 단일 application scope를 고정하므로 실제 새 INIT와 관측·NoDrive 권한의 epoch 전환을 먼저 연결해야 한다.
인지/학습 모델과 온라인 저항 추정은 공통 scenario/seed에서 별도 검증한다.
구체 산출물과 TBD 담당·결정 시점은 [로드맵](roadmap.md)에서 관리한다.
진행한 시도별 상세 경과와 과거 실행 목록은 [구현·검증 이력](archive/implementation-history.md)에서 찾는다.
