# CARLA 파생 HV 예산 재조정 검증

2026-10-29, 기준 commit `10f7d97`. **`wall5-hv50-v1`의 단기 비영상 정상2회·보호2회,
실제4/4 case 통과**다. 전체 wall 실시간/고속·영상·장시간 수용을 뜻하지 않는다.
현재 판정은 [프로젝트 상태](../../../../../project-status.md), 개정 계약은
[CARLA ICD](../../../../../interfaces/carla-plant-adapter.md#carla-파생-hv-입력-예산-재조정),
결정은 [ADR-0066](../../../../../archive/design-decisions.md#adr-0066)에 둔다.

## 변경 근거와 경계

사용자가 프로젝트 진행을 막는 과도한 timing 조건의 재조정을 요청했다.
이전 run11은 **HV 취득 age12.531311ms, oldest dependency30.010378ms**에서 이전 sample이
만료됐다. 새 취득과 파생 계산의 입력 나이를 동일30ms로 제한한 사례다.
[이전 원본·실패](../nonvideo-wall5/README.md)를 보존하며 재채점하지 않는다.

새 실행 전에 HV source30ms/dependency50ms를 고정했다. 추가20ms는 한 Controller 주기의
계산·전달 예산이며 실차/OEM 안전 한계가 아니다. Wheel/Actual/명령30ms·부모 expiry·
RunLease·owner2ms/4ms·Controller20ms·Zone/vECU10ms는 유지한다. 원본 시각을 고쳐 쓰거나
새 값으로 직전 만료를 숨기지 않는다. 기본값은30ms이고50ms는 비영상 wall5ms에만 opt-in이다.
`validation/pre-run-manifest.json`과 `pre-run.patch`는 실제 실행 전 고정한 계획/소스다.

M6 원본은 바꾸지 않았다. 기존 M7 owner 생성 방식에 HV dependency 검사만 분리한
controller를 추가했고, 생성 anchor가 달라지면 구성 실패한다. 공유 알고리즘을 손으로
복제해 관리하지 않는다. 새 native/probe metadata에 예산을 기록하고 raw HV source/dependency를
원본 CARLA work·coil 시각과 독립 대조한다. 서버/PhysX/NoDrive 구현과 binary는 이전과 같다.

## 실제 실행

기존 Host Ubuntu22.04/i7-11700/RTX3090, CARLA0.9.16/UE4.26.2 source,
Town03_Opt/첫 spawn/mkz_2020/V1, 고정 `m7_integrated_v1.txt`, camera/traffic0이다.
320 vehicle substep,5ms model step,NullRHI/inline render,compact work,
native FIFO18/1ms wake이며 각 case는 새 서버·actor·INIT다. 빌드 최적화 옵션은 바꾸지 않았다.
시작/종료·실제 scheduling·실행 argv·binary hash는 각 `server-runNN.json`/`native.json`에 있다.
성능 측정 중 빌드·sanitizer·압축 작업은 실행하지 않았다.

| 실행 | 의도 | physics / normal / protection | model / wall 초 | 판정 |
| --- | --- | --- | --- | --- |
| run01 | 정상 | 900 /730 /0 | 4.5 /4.501412 | 원본 감사·서버 종료 PASS |
| run02 | 정상 반복 | 900 /734 /0 | 4.5 /4.502357 | 원본 감사·서버 종료 PASS |
| run03 | 정상50구간 후100ms physics 보류 | 900 /50 /684 | 4.5 /4.500879 | 보호 제동·자연 정지·서버 종료 PASS |
| run04 | 정상50구간 후 명시적 보호 요청 | 900 /50 /684 | 4.5 /4.500796 | 보호 제동·자연 정지·서버 종료 PASS |

정상 외에는 기존 bounded empty/non-driving INIT가 포함된다. 정상 주행 자체가4.5초인 것은
아니다. Wall 시간은 native initial→마지막 물리 취득 종료이며 로딩·증거 회수·종료는 별도다.
각900건의 완료 work를900회 EV 정산했다. Owner missing/late·물리 적용 중 권한 만료는 모두0,
Actual-only/능동 single writer·pause/reset/close·CAN/P05·에너지 검사가 통과했다.
서버는 네 번 모두 소유 process group에 SIGINT 후 exit130이며 강제 종료가 없었다.

정상 두 회의 HV source age 최대는13.399/13.595ms, dependency는31.641/31.661ms다.
이는 현재 값과 **교체 직전 cached 값**을 현재 호출 시각에서 검사한 최대치다.
50ms 예산이 실제 관측된31ms대를 허용하면서 source30ms는 충족했다.
단순히 새 sample을 먼저 넣어서 이전 만료를 지운 결과가 아니다.

run03/04는 보호 선택→실제 brake>=1MPa 적용213.295/209.201ms,
body/wheel exact0의 자연 정지379.406/405.157ms를 관측했다. 마지막100구간 pose가 동일했다.
정상 시작 속도는 낮은 fixture 범위이며 고속 정지 성능은 검증하지 않았다.
100ms physics 보류는 game thread 전체 정지가 아니고 원본 Actual 수신은 계속된다.

## 자동 검사와 한계

- 변경 후 관련 binary를 재빌드한 Normal123/123·ASan/UBSan123/123 통과.
  새5개 case는30/50ms 및+1ns, wheel/source30ms, cached identity 불변, 이전 만료 latch,
  잘못된/범위 밖 profile 거부를 검사했다. 초기 새 test 컴파일에서 `auto`의 정수형 추론이
  달라 실패했으며 명시적 `uint64_t`로 수정 후 재빌드했다. 실제 CARLA 실행 실패는0/4다.
- 독립 감사 손상6/6 거부: 미정의40ms·서로 다른 예산·숨긴 profile·source restamp·dependency
  restamp·현재 정상 trace를30ms로 판정한 반사실 대조. 마지막 검사는 새 물리 실행이 아니며
  이전 실패를 PASS로 바꾸는 용도가 아니다. `validation/audit-mutations.json`에 원인을 보존했다.
- 잘못된 CLI 조합은 서버/출력 디렉터리 생성 전에 exit2로 거부했다.
- M6 전체 시험·새 TSan·카메라 실제 회귀는 이번에 실행하지 않았다. 기본 기능 profile의
  M7 native 회귀는 포함한다. M6/기존 수용 결과를 이번 실행으로 다시 PASS 표시하지 않는다.
- 과거 UE 종료 SIGSEGV는 코드 수정 없이 이번4회 재현되지 않았다. 원인 해결로 판정하지 않는다.
  장시간·고속·영상·다른 Host/Target은 후속이며 M8 simulation-time 기능 개발을 막지 않는다.

## 원본과 재현

[summary.json](summary.json)은 runner/server와 raw 감사의 종합 판정이다.
[build-manifest.json](build-manifest.json)은 실행 native·서버 hash와 코드 변경 경계를 기록한다.
`runs/runNN/`에는 원본 trace/ingress/events/native CSV·결과·서버 로그·명령이 있다.
큰 파일은 원본 bytes를 gzip으로 보관했고 감사기는 `.gz`를 직접 읽는다. 공유 mmap 임시파일과
설치 manifest/비공개 engine 소스·binary는 보관하지 않았다. `sources/`에 변경 M7 소스와
실제 생성 controller/owner를 보존한다. 나머지 의존성은 기준 commit에 있다.

```sh
python3 tests/integration/carla/audit_m7_wall_carla.py \
  docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/runs/run01 \
  --output /tmp/strata-hv50-recheck.json
cd docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1
sha256sum -c SHA256SUMS
```

새 실제 실행은 [실행 안내](../../../../../carla-guide.md#비영상-wall5ms-실험-재실행)의 새 출력
디렉터리를 사용한다. 기존 evidence에 덮어쓰지 않는다. 이 profile의 한정 통과와 M7 기능
종료/전체 wall 수용은 별개다.
