# Native 속도 감독 운영 연결 검증

2026-11-06, baseline `c9933ebc59069399c6a5cf374349a735db002ba5` 이후의 선택형 연결이다.
`--supervised-speed 0:200`은 receiver BMS 전력 제한·wheel 취득과 고정 SIL 저항 범위를 사용한다.
Supervisor의 classical fallback→가용력 governor→기존 PI/배분→보호→DTC를 실제 native 실행에 연결했다.
[계약](../../../interfaces/supervised-speed-proposal.md)과 [ADR-0108](../../../archive/design-decisions.md#adr-0108)을 따른다.

## 실제 CARLA

동일 실행 binary, fresh server 두 개, simulation10ms·solver320substeps·기존 whole-interval-v1 기준이다.
새 source/expiry를 만들거나 sampled-Actual 기준으로 전환하지 않았다.

| 조건 | 물리 구간 | 제어 release | DTC root | 최종 body 속도 |
| --- | ---: | ---: | ---: | ---: |
| nominal | 4000 | 1960 | 0 | 0m/s |
| speed input loss | 4000 | 750 | SD-1002/monitor4 1개 | 0m/s |

두 실행 모두 최대 body 속도2.798537292480469m/s를 관측했다. 입력 상실의 trigger와 검출은
16411718988ns로 같고 보호·ACK·원본 Actual과20개 event가 영속 journal에 연결된다.
정상 실행은 Session 관련2개 event이며 false DTC가 없다. 두 저장기와 native process는0으로,
서버는 소유 실행기의 SIGINT 정리 후130으로 종료됐다. 입력 복구만으로 정상 운행을 재개하지 않는다.

기존 solver-work/NoDrive 감사는 각4000구간의 실제 work·EV 정산·Actual·명령 만료를 독립 검사했다.
새 감사는 원천별 age/expiry, 고정 가용력 식,20ms 목표 변화, DTC 원문 일치를 검사하고 각3개
변조를 거절했다. 전체8002관측의 native 결과는 보존한 입력으로 정확히 재생됐다.

원문 [nominal](carla/nominal/result.json)·[input-loss](carla/input-loss/result.json), 각 디렉터리의
`trace.jsonl.gz`와 `diagnostic-store`, [정상 감사](carla/nominal/supervision.json)·
[고장 감사](carla/input-loss/supervision.json), `work.json`을 함께 본다. 큰 trace는 Git LFS다.

첫 실제 서버 시도는180초 내 world snapshot을 제공하지 못했고 SIGINT 종료도30초를 넘겨
소유 실행기가 SIGKILL했다. ego/주행 시험을 시작하지 못한 **실패**로 보존했다. 기존 route의
명시적인600초 로딩 예산을 speed simulation에도 선택할 수 있게 해 새 서버로 다시 실행했다.
주행 deadline·feedback age·shutdown budget은 바꾸지 않았다. 이 재실행 성공이 일반
renderer/GC/로딩 종료 원인을 해결했다는 뜻은 아니다.

## Host 검사와 개발 실패

- 전체 Debug1515개 중1514개 통과, 새 power provenance 시험1개의 fixture 순번 증가 오류를 수정했다.
  수정 후 영향 범위113개와 최종20개 supervisor/force 시험 및 native 연결을 통과했다.
- ASan/UBSan89개 통과. 마지막 보호 admission/증거 저장 추가 뒤 해당 native 시험도 다시 통과했다.
- Python280개, CLI 경계8개, clang-tidy9개 translation unit 통과. 마지막 변경3개를 재검사했다.
- Native stationary wheel/work fixture는 nominal/force-loss 각600관측에서 실제8-role 보호,
  server admission, ActuatorElectrical, original DTC 영속 기록/재열기와 복구 후 latch를 확인했다.
  이 fixture를 움직이는 CARLA 차량 정지 증거로 사용하지 않는다.

초기 빌드의 test macro braces·추가 optional 기본 초기화 누락, 단일30ms force 가정으로 정상
BMS를 차단한 실패, 낡은 Drive Actual의 expiry를 가용력 결과에 다시 씌워 whole-interval admission을
차단한 실패를 보존했다. 최종 구현은 기존 계약대로 현재 wheel30ms와 derived60ms,
BMS message50ms와 physical input70ms를 구분하고 모든 원래 dependency를 child 명령에 전달한다.
잘못 지정한 sanitizer target 이름의 실행 실패도 보존했다. 기존 실패 기록은 덮어쓰지 않았다.

## 남은 범위

학습 모델·온라인 경사/저항 추정·전체 Reference ODD·wall/Target 수용은 아니다.
새 SupervisedSpeed monitor의 qualified Passed/서비스 clear는 후속이며 기존 Speed clear로 지우지 않는다.
EpochRecorder의 SOME/IP stream/ACK 운영 연결·단일 epoch 회전·디스크 보관 정책도 별도다.

## 재현

```sh
cmake --build build/m1-angle -j4
ctest --test-dir build/m1-angle -R '^(AvailableForce|SpeedSupervisor|Supervised|ControlAllocation|M10NativeSpeed|M8Carla)' --output-on-failure
python3 tests/integration/carla/audit_supervised_speed.py docs/test-plan/evidence/runtime-speed-connection/carla/nominal --output /tmp/supervision.json --mutations --replay build/m1-angle/tests/integration/carla/m7_1g/m7_wheel_shadow
python3 tests/integration/carla/audit_m7_1r_work.py docs/test-plan/evidence/runtime-speed-connection/carla/input-loss --output /tmp/solver-work.json
```

[acceptance.json](acceptance.json), [sources.json](sources.json), [SHA256SUMS](SHA256SUMS)를 확인한다.
[sources.tar.gz](sources.tar.gz)는 변경 소스/문서, [validation.tar.gz](validation.tar.gz)는 최초 실패·최종 검사,
원본 native fixture journal, 서버 로그·실행 manifest·빌드 설정을 보존한다. 이전 milestone 원본은 수정하지 않았다.
