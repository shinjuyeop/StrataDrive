# 비영상 CARLA wall5ms 조사·개선과 반복 실패

2026-10-29, 기준 commit `1215bd6`. **짧은 정상 주행과 실제 보호 정지를 확인했지만 반복 안정화는 OPEN**이다.
M6 코드·계약·수용 수치와 M7 simulation-time 기능 종료 판정은 변경하지 않았다.
현재 상태는 [프로젝트 상태](../../../../../project-status.md), 계약은
[CARLA ICD](../../../../../interfaces/carla-plant-adapter.md#비영상-wall5ms-profile)에 둔다.

## 확인한 원인과 변경

- 기존10ms wall 연결은 renderer 지연만의 문제가 아니었다. run02는 최대 pump 공백3.184ms에서도
  정상0구간으로 끝났다. 첫 정상 Actual의 command 잔여 유효 구간은12.484ms인데 admission은
  다음10ms와 preview4ms를 요구했다. 새 physics를 승인하지 못하면 새 wheel도 오지 않는 대기가 생겼다.
  분리된 native component에 매번 새 receipt를 넣던 시험은 이 결합을 드러내지 못했다.
- 승인된 physics 뒤에만 receipt를 공급하는 결합 시험을 추가했다. 별도 비영상5ms plant와 절대
  release grid에서는 원래30ms·4ms preview·Controller20ms·Zone/vECU10ms를 유지하며 진행했다.
  기본 world10ms와 기능 실행은 그대로다. 원본 model step/solver dt/EV interval을 함께5ms로
  명시하고 공유 ABI3에서 혼합 연결을 거부한다. Phase 변경이나 ECU catch-up은 적용하지 않았다.
- run03은 저속 `Physics()` 취득 JSON에 중복1280 tire callback 객체를 넣는 데15.877ms가 걸려
  적용된 물리1구간의 권한이 만료됐다. Wall snapshot에서 이 중복 표현만 제외했다. 모든320×4
  solver force/omega/dt 원본과 work/EV 정산 증거는 기존 bounded journal에 유지한다.
- run05는100ms physics 보류 중 실제 도착한 Actual을 receiver에 넣지 않아 재개 시 CAN counter/
  timeout을 거부했다. 원본 수신 검증을 physics 승인과 분리했다. 수신 자체는 actuation 권한이 아니다.
  미수신 counter나 sensor timestamp를 만들지 않으며 session을 초기화해 실패를 숨기지 않는다.
- run06–09의 수신 JSON 비용을 줄이기 위해 최대4096개의 원본 packet/timestamp를 사전 할당한
  구조체에 보관하고 종료 후 문자열로 변환한다. 적용 proof의 hex 변환도 동일 byte를 직접 기록한다.
  run10은 정상 주행4.5model s를4.503wall s에 완료했으나 최종 반복run11/13은 보호로 전환됐다.
  따라서 이 최적화를 반복 안정성 해결로 판정하지 않는다.

## 조건과 전체 시도

기존 Host Ubuntu22.04/i7-11700/RTX3090, UE4.26.2 commit
`e9d9e60c85f643e10eeb03f42f61554d18dcb30f`, CARLA0.9.16 source
`294096eb1c38eabf246e4f3a9cdab704e33a7f4c`에 프로젝트 확장을 사용했다.
Server/client는 `294096e-dirty`로 일치했다. Town03_Opt/첫 spawn/mkz_2020/V1,
vehicle320 substep, compact solver journal, 단일 native FIFO18 owner·1ms wake다.
각 case는 새 서버/INIT/actor이며 traffic·camera0, 고정 VehicleRequest 시나리오다.
run02 이후 비영상은 NullRHI/inline render를 사용했다. 실행 중 다른 process를 강제 정리하지 않았다.

| 실행 | 구성·의도 | physics / normal / protection | model / wall 초 | 최종 해석 |
| --- | --- | --- | --- | --- |
| run01 | 기존 wall10ms | 60 /0 /0 | 미완료 | INIT 이후 정상 진입 실패 |
| run02 | wall10ms·비영상 renderer 옵션 | 80 /0 /0 | 미완료 | 짧은 pump 공백에서도 admission 대기; server 종료−11 |
| run03 | wall5ms·기존 중복 callback JSON | 900 /22 /712 | 4.5 /4.501198 | 물리 권한 만료1; 정상 FAIL |
| run04 | wall5ms·중복 JSON 제외 | 900 /734 /0 | 4.5 /4.502120 | 당시 raw 감사 통과. 능동 writer/전체 ingress 추가 전 탐색 근거 |
| run05 | wall5ms·100ms physics 보류 | 221 /정상50 이상 /0 | 미완료 | native_actual_receiver 거부 |
| run06 | 수신/physics 분리·100ms 보류 | 900 /50 /684 | 4.5 /4.501133 | 해당 보호 case PASS |
| run07 | 같은 빌드·정상 | 900 /734 /0 | 4.5 /4.893047 | 원본 권한/감사 PASS, 진행 비율0.920 |
| run08 | 같은 빌드·명시적 보호 | 900 /50 /684 | 4.5 /4.501065 | 해당 보호 case PASS |
| run09 | 같은 빌드·정상 반복 | 900 /730 /0 | 4.5 /4.783296 | 원본 권한/감사 PASS, 진행 비율0.941 |
| run10 | POD ingress/hex 개선·정상 | 900 /734 /0 | 4.5 /4.503257 | 짧은 정상 case PASS, 진행 비율0.9993 |
| run11 | 최종 빌드·정상 반복 | 900 /181 /553 | 4.5 /4.501375 | 예상치 못한 보호; 정상 FAIL, server 종료−11 |
| run12 | 최종 빌드·100ms 보류 | 900 /52 /682 | 4.5 /4.500867 | 물리 감사 PASS지만 server 종료−11, 전체 case FAIL |
| run13 | 최종 빌드·명시적 보호 예정 | 900 /24 /710 | 4.5 /4.501306 | 정상50구간 전 자연 보호. 의도한 fault 미실행, FAIL |

숫자0은 raw trace에서 확인한 값이다. 미완료 case를 전체 실행 PASS로 바꾸지 않는다.
정상 외 구간에는 원래 bounded empty INIT와 non-driving INIT Actual이 있다.
4.5초는 INIT를 포함한 model 구간이고, wall 시간은 native initial부터 마지막 취득 종료까지다.
로딩·종료·journal 회수 시간은 별도 supervisor metadata에 있다. `PASS_CASE_ONLY` raw 감사는
원본 입력·권한·job·work 범위이며 별도 real-time factor 보장이나 server lifecycle PASS가 아니다.
전체 판정은 [summary.json](summary.json)의 runner exit·raw audit를 함께 확인한다.

최종 빌드의 정상 의도 실행은run10/11의 **1/2 통과**다. Fault 의도run12/13도 전체 case PASS가
아니다. 성공한 이전 빌드run06–09를 최종 빌드의 반복 수용 분모에 섞지 않는다.

## 원본 timing·실제 보호 반응

run06–13은 각각900 physics와900 단일 EV 정산을 보존했다. 실제 적용 구간의30ms age·expiry,
원래10owner의2ms release/4ms deadline, 원본 CAN/P05·부모 command 인과·Release/credit,
실제 solver work·energy·pause/reset/actor 종료를 독립 검사했다. 모두 측정 owner slot 누락/지연0,
적용 구간 권한 만료0이었다. 이것은 적용되지 않은 대기 중 Drive 로컬 입력까지 계속 fresh했다는
뜻이 아니다. run11/13은 그 입력 보호 때문에 정상 주행 시험에 실패했다.

run10의22540 eligible owner slot 중 miss0, 최대 전 구간 원천 age22.006ms,
최소 command 여유3.939ms, receipt→native EV commit 최대1.731ms,
최대 energy balance 오차9.55e-9J였다. 최대 전방 속도1.2483m/s인 짧은 고정 요청 시험이다.

| 실행 | 최초 보호 physics | 최초 brake ≥1MPa | 최초 body/wheel 자연 정지 | 마지막100 pose |
| --- | ---: | ---: | ---: | --- |
| run06 ·100ms physics 보류 | 135.811ms | 205.792ms | 358.189ms | 동일 |
| run08 ·명시적 보호 | 68.681ms | 212.521ms | 433.413ms | 동일 |
| run12 ·100ms 보류·종료 FAIL | 85.581ms | 210.268ms | 393.079ms | 동일 |

기점은 원본 native **보호 선택 시각**이다. 두 case의 최고 속도는run06 약0.0283m/s,
run08 약0.0100m/s로 매우 낮다. 고속 정지거리·차량 FTTI·M6의230ms 물리 응답 수용으로
전용하지 않는다. `wall-gap`은 physics만 보류하며 game thread/실제 CAN 수신은 계속한다.
엔진 thread 자체 SIGSTOP 중 보호 actuation을 실행했다고 주장하지 않는다.
외부 throttle batch·일반 world.tick·인증된 외부 stage_native의 거부도 정상 주행 중 확인했다.

## 남은 실패를 특정한 근거

run11의 마지막 정상 physics 이후 native 보호 선택은 initial+1737.004975ms였다.
원본 호출 시각과 CARLA receipt를 같은 native 로직에 재생하자 **동일 시각·동일 fault**가 재현됐다.
진단용 DriveController 복사본의 관측 로그는 그보다 앞선 initial+1734.004555ms에 다음을 보였다.

- 이전 HV source는 initial+1721.473244ms지만, 실제 입력 의존성은 initial+1703.994177ms다.
- 로컬 검사의 그 입력 age는 **30.010378ms**, 원래 허용값은30ms다.
- `observe_local`은 새 입력을 받기 전에 기존 입력의 만료를 검사한다. 새 receipt의 도착으로 이미
  검출된 만료를 취소할 수 없다. Wheel 재발행이나 HV source만 새 시각으로 바꾸는 해결은 부적합하다.

[진단](runs/run11-diagnosis.json)과 재생 source/input/log를 보존했다. 진단 복사본은 저장소의
M6 controller나 실제 서버에 설치하지 않았다. 이 사례는 **EV 관측의 가장 오래된 입력부터 다음
유효 수신까지의 전체 여유**가 부족함을 보여 준다. 이후 개선은 command/Actual 유효 구간과
physics 완료→EV 수신을 함께 고려한 일정·전달 예산을 대상으로 한다. 이번 단계에서는 미해결이다.

run02/11/12의 server 종료 코드는−11이었다. run12 stack은 `FSafeRecyclableEvent::Trigger` →
`FQueuedThreadPoolBase::Destroy` → `FEngineLoop::AppPreExit`다. Actor 정리 뒤 엔진 종료 중
발생했으며 수정 전run02에도 있었다. 정확한 thread/event 수명 원인은 미확정이다.
원본 server log와 정상 SIGINT 종료130을 모두 남겼다. SIGSEGV를 정상 종료로 처리하지 않는다.

## 회귀·손상 검사와 범위

Native Normal/ASan·UBSan은 각각118/118 통과했다. 새 결합 admission·5ms/10ms identity 혼합
거부·EV 정산 주기·physics 보류 중 원본 수신 시험을 포함한다. 최초 native-build05의
`-Werror=dangling-else` 실패도 보존하며 braces 수정 후 재빌드했다. 새 TSan/전체 M6 suite는
실행하지 않았다. M6 source 변경은 없다.

최종 서버의 기존10ms `camera-a`900구간/RGB·GT 각180개와 `protected-sleep`400구간은
runner·work·통합/보호·closeout 감사 모두 통과했다. 독립 감사 손상12/12를 거부했다.
[summary.json](summary.json)에 분모와 판정을 둔다. 손상 검사는 원본을 수정하지 않고
메모리 복사에만 CRC·시각·수신 이력·step·writer·exit·job deadline·
Actual·solver dt·acquisition 변조를 주입한다. Fault 요청 증거 누락도 수용하지 않는다.

장시간 wall·영상 wall·전체 thread 정지 후 실제 제동·work/sensor 누락의 최종5ms runtime suite·
Reference30km/h·경로/AI·Target/HIL은 이번에 검증하지 않았다. 5ms와10ms 물리 궤적의 완전 동등성도
주장하지 않는다. M7 simulation-time60s CLOSED 근거와 새4.5s wall 실험은 서로 다른 실행이다.

## 재현과 보관

[실행 안내](../../../../../carla-guide.md#비영상-wall5ms-실험-재실행)의 명령을 따른다.
실행 당시 인수·module/native SHA·서버 상태는 `runs/server-runNN.json`과 각 runner log에 있다.
`runs/preopt-sources/`는run06–09 전 소스, `sources/`는 최종 저장소 M7 source snapshot이다.
초기run01–05의 설치 이력은 module hash·빌드 로그·실행별 Python snapshot으로 식별하며,
모든 중간 C++ 편집 상태를 별도 snapshot으로 보존한 것은 아니다.

`runs/phase*`와`five_ms_probe*`는 별도 합성 진단이다. Controller phase/INIT phase sweep 및
preview0 반사실 시험은 실제 CARLA에 설치하지 않았다. preview0은 채택하지 않았고 실제4ms
여유는 유지했다. 합성 결과를 물리 주행 PASS로 세지 않는다.

`artifact-manifest.json`은 원본/저장본 SHA256·압축 방식·제외 이유를 기록한다. Log/CSV/JSONL·텍스트와
큰 JSON은 무손실 gzip, 실행 ELF는 SHA로 식별하며 private UE source/installer 원본은 vendoring하지 않는다.
독립 auditor는 gzip trace/ingress/CSV를 읽는다. 예:

```sh
python3 tests/integration/carla/audit_m7_wall_carla.py \
  docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/runs/run10
```

`SHA256SUMS`는 manifest·README·summary·source·원본 보관물 전체의 무결성을 확인한다.
실패run11/13의 auditor 비영 종료는 기대되는 실패 보존이며 새 PASS로 수정하지 않는다.
