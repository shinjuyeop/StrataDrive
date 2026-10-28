# M7 solver 기록 경로 분리와 wall 연결 가능성 조사

2026-10-28. **선행 IO 병목 개선 / 정상 wall runtime 미구현 / 전체 M7 NOT CLOSED**.
원래 solver/Actual/work를 유지하며 세부 JSON 직렬화·전송·감사를 실행 경로에서 분리했다.
controller 시작 위상만 바꾸는 방법도 조사했지만, 원래 expiry 여유 문제를 해결하지 못했다.
M6 구현·통신/안전 계약·수용 판정과 기존 M7 coefficient/tick/freshness는 유지했다.

## 실행 결과

| 실행 | 결과 | 근거 |
| --- | --- | --- |
| compact suite | 6/6 PASS_CASE_ONLY | normal-a, camera-a, protected-sleep, wall-gap, work-missing, snapshot-stop |
| 최종 legacy 영상 | 1/1 PASS_CASE_ONLY | 동일 server/observer/최종 native binary, compact 옵션 off |
| 최종 compact 영상 | 1/1 PASS_CASE_ONLY | 위 실행 후 같은 binary로 compact 옵션 on |
| 일반 / ASan·UBSan | 각각93/93 | journal3개·phase 변경 경계1개 포함, 기존 M7 전체 |
| 기존 native 입력 replay | 901/401개 출력 정확히 동일 | 정상 / 보호 각각. 새 CARLA 실행으로 합산하지 않음 |
| phase component probe | 42조합 중32 functional admission 유지 / 10 거부 | 유지된32개 모두 최소 expiry margin1ns; wall PASS 아님 |

각 suite의 argv·status·로그·원본 trace·independent audit를 그대로 보존한다. 최초 phase utility의
CMake 미재설정 target 오류와 이후 Werror 들여쓰기 오류도 보존했다. 둘을 수정한 실행은
`phase-scan.json`, 상세 causal example을 추가한 실행은 `phase-details.json`이다.
`tests-all-current-*.log`가 모든 FunctionalRig 의존 executable 재빌드 후 최종 CTest 근거다.
새 TSan이나 전체 UE sanitizer는 실행하지 않았다.

## 구현과 증거 보존

기본은 off다. `--compact-work`는 server의 `-StrataM7CompactWork`를 선택한다.
BeforeTick/AfterTick·Actual-only·native 권한/causal command·wheel/solver validity·단일 EV ACK는
그대로 유지한다. 모든320개 원시값의 finite/연속성/applied effort/final solver readout 검사를
서버에서 수행한다. observer ABI2와 PhysX module은 이번에 바꾸지 않았다.

bind 때1024entry의 raw solver journal을 선할당한다. game thread가 원래 trace/frame/ticket을
독립 복사하며 덮어쓰기·eviction이 없다. capacity 도달은 다음 physics 전에 latch한다.
즉시 응답에는 정산에 필요한320개 원래 rear mean·signed work 합을 담고, full steps의 JSON
생성은 `solver_trace(ticket)` 조회까지 미룬다. 실제 원본의 손실 압축/샘플링이 아니다.

시험기는950tick 이하의 유한 window를 쓰고 compact record도 메모리에 보관했다가 close/reset
전에 journal을 전부 회수한다. frame/ticket/run/session/actor/generation, 원래 raw steps에서
계산한 mean과 compact mean의 정확한 일치, 기존 raw-wire/P05·solver 방정식·EV 장부 검사를
통과해야 PASS다. 조회가 cached timestamp를 새로 만들거나 tick을 진행시키지 않는다.
추가 journal 손상5종(ticket/frame/session/generation/mean)을 거부했다. journal의 복사/용량/
중복·누락 frame/ABI 및 failure latch는 CTest에서 검증했다. 실 CARLA1024 overflow 주입은 NOT RUN.

이것은 무한 운영용 asynchronous logger가 아니다. process crash 후 복구 가능한 durable
로그도 아니며 원본 회수 실패는 FAIL이다. abrupt client-loss와 compact 조합은 runner에서 거부한다.
일반 client-loss 종료 수정의 기존 근거를 이 모드의 crash 증거 보존 보장으로 확대하지 않는다.

## 물리·work 동등성

[대조 원본](comparison.json)의 정상4실행 각각900구간과 보호400구간이 기존 reference와
physics(generation identity 제외), 전체 solver steps, signed motor work, 원래 Actual 값까지
정확히 같았다. observer 재사용 이후 raw copy가 바뀌지 않았음을 실제 회수 자료로 확인했다.
각 영상 실행 RGB/GT180개와 frame/source metadata·TRAIN_EVAL_ONLY 분리도 기존 감사로 검사했다.

fresh server의 simulation 시작 시각은 서로 다르므로 마지막 EV binary64 값의 bit 일치를
주장하지 않는다. work 합 및 원래0.00072J 장부 기준을 독립 검사한다. 반면 같은 원래 입력을
재생한 native901/401개 출력은 완전히 같았다. M7 phase 조사 API 추가로 최종 native binary의
hash는 첫 compact suite 때와 달라졌으며 각 server/replay manifest의 실제 hash를 따른다.
기본 정상 실행 phase14ms는 바꾸지 않았다.

## 실제 시간: 개선과 남은 실패

최종 legacy/compact 영상은 새 서버에서 같은 binary·seed·모델·시나리오·RGB/GT 설정으로
순차 실행했다. 아래는 의도적 pause 뒤 index150 구간과 receipt가 없는 terminal row를 제외한
**898개**의 post-physics 취득 bracket 시작→다음 native 처리 완료다.

| 관측 | legacy | compact |
| --- | ---: | ---: |
| 평균 | 38.215ms | 15.845ms |
| 중앙값 | 32.289ms | 5.289ms |
| P95 | 67.893ms | 41.179ms |
| 최대 | 103.017ms | 166.566ms |
| 30ms 초과 | 678/898 | 266/898 |
| 진단 model/wall 진행 비율 | 0.248 | 0.558 |

평균은 약58.5% 줄었지만 최대값은 개선되지 않았다. 카메라 없는 compact normal-a는 평균6.943ms,
P95 28.168ms, 최대41.032ms, 30ms 초과8/898이었다. 평균 처리율을 deadline 보장으로 해석하지
않는다. 첫 compact suite 중에는 별도 phase utility build/조사가 겹쳤으며, 최종 순차 대조에는
동시 CARLA/CTest/build를 실행하지 않았다. 전용 실시간 benchmark 환경/보장 상한은 아니다.

이 통계는 동일 Host monotonic 쌍의 진단 loop 관측이다. 개별 ECU job4ms latency나 실제 CAN
source-age를 대신하지 않는다. 기본 closeout 감사의899개 통계는 terminal native 처리를 추가로
포함하므로 이 표와 분모가 다르다. fixed-offset 교집합은 없었고, native owner 호출도 여전히
RPC/physics 완료에 묶여 있다. **정상2ms/4ms·clock agreement·wall fault 이후 연속 물리 제동 미수용**이다.

## 위상 조사와 다음 구현의 경계

`m7_phase_probe`는 stationary synthetic wheel로400구간을 실행한다. Controller/management의
INIT enable 후 지연만0..20ms(1ms 간격)로 바꾸고 정수/분수 simulation 시각을 각각 적용한다.
원래 Controller20ms·management10ms·leaf/Zone10ms·source age·expiry를 그대로 검사한다.
0/1/10/11/20ms 조합은 원래 causal/credit 검사에서 거부됐다. 나머지32개는 admission을 유지해도
최소 command expiry margin1ns였다. 다른 위상을 실시간 해결책으로 채택하지 않았다.

native functional barrier는 새 관측 이후의 IO/timer job을 그 관측 시각 이후로 실행할 수 없다.
wall runtime에는 새 domain의 INIT와 실제 monotonic owner service, bounded 수신 경로가 필요하다.
CARLA frame/model10ms와 actuator response elapsed/EV work·취득 provenance의 관계도 명시해야 한다.
기존 SolverWork duration 범위 완화, cached source restamp, 일반 heartbeat를 owner job으로 세는
방법, 기존 terminal-local Actual을 그대로 서버에 적용하는 방법은 채택하지 않았다.
[ICD 설계 경계](../../../../icd/carla_plant_adapter.md#다음-wall-runtime의-구현-경계)와
[종료 검토](../../../../m7_exit_review.md)에 **미구현 상태**를 명시했다.

## 재현

[도구 명령](../../../../../tools/carla/m7_nodrive/README.md)에 따라 기존 pin/source/venv를 사용하고
CARLA module만 재설치·빌드한다. observer 재빌드는 불필요하다. 실행 중인 UE4Editor에는 설치하지 않는다.
기존 suite 인자에 `--compact-work --held-steer-sleep --cases normal-a camera-a protected-sleep
wall-gap work-missing snapshot-stop`을 추가한다. actual argv는 `compact/suite.json`을 따른다.
위상 조사는 `cmake --build build/m7-functional --target m7_phase_probe` 후 생성 executable을 실행한다.
새 디렉터리를 쓰며 과거 실패 자료를 덮지 않는다.

`archive-manifest.json`은 raw/저장 hash와 크기, `installed-source.json`은 설치 provenance,
`server-sources`와 각 suite/runtime source는 project-owned 재현 자료다. 원본 UE/PhysX source,
빌드 binary, owner key는 커밋하지 않는다. `SHA256SUMS`는 저장된 전체 파일을 검증한다.
