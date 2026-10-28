# 실제 CARLA ↔ native wall owner 연결 시도

2026-10-28. **정상 wall 주행 NOT ACCEPTED, 전체 M7 NOT CLOSED.**
`4a3139b`의 합성 원천 WallRig에서 실제 CARLA model/work·wall 취득으로 확장했다.
기존 M6 코드·계약·수치·판정은 변경하지 않았다. 새 모드는 default-off 실험 경로다.

## 최종 결과

| 실제 범위 | 결과 | 근거 |
| --- | --- | --- |
| ABI2 정상 wall 시도 | **FAIL/NOT_ACCEPTED**, INIT 물리64구간/정산64, 정상0·보호 적용0 | `run24/result.json`, `run24/audit-final.json`, 원본 trace/events/native job CSV |
| ABI2 영상 wall 시도 | **FAIL/NOT_ACCEPTED**, bootstrap 물리2구간/정산2, RGB/GT0·정상0 | `run25/result.json`, `run25/audit-final.json`, `run25/sensors.json` |
| 실제 native owner 실행 기회 | run24:7,040 / run25:4,360 판정 가능 slot, 각 missing0·late0. **주행 수용 아님** | 실제2ms grid·4ms deadline의 `native-wall.csv.gz`; gap 후에도 owner 실행 유지 |
| 원본 취득→native 정산 | run24 최대1.355ms, run25 최대1.396ms | native CSV의 **최초** 해당 model-end commit. cached publish/늦은 server ACK 시각과 구분 |
| 서버 프레임 공백 | run24 최대30.804ms, run25 최대149.855ms | `wall_status`의 pump 간격. 같은 실행 RPC window 최대0.232/0.129ms. 원천 만료로 다음 물리 차단 |
| 마지막 서버 빌드의 기존 functional 회귀 | **2/2 case 한정 통과**: camera900구간·RGB/GT180쌍, protection400구간·자연 sleep122구간/마지막100구간 pose 동일 | `scope-functional-regression/suite.json`, 독립 wire/solver/energy/시나리오/stop 감사. wall 수용 아님 |
| 일반 / ASan | **각113/113** | `build-checks/m7-scope-*-tests.log.gz` |
| TSan | **26/26**, race 경고0 | 기존/clock 경계21 + 최종 admission/IPC5. 실제 CARLA/실시간 acceptance로 확대하지 않음 |
| 기존 출력 정확 재생 | **901/401** 출력 일치 | `replay-*-final/result.json`; CARLA 실행 아님 |
| 새 감사기 손상 거부 | **8/8**, baseline 자체는 NOT_ACCEPTED | `audit-corruptions.json`: CRC, 미래 취득, model dt, 무근거 effort, 음수 wheel, raw solver 변조, work 누락, 에너지 불일치 |

최종 두 wall 실행은 기준을 충족하지 못했다. 입력 만료·초기화 실패 후 원래 보호 선택/다음 stage
차단은 관측했지만 **실제 CARLA 보호 제동/정지 성공으로 기록하지 않는다**. reset이 속도를0으로
만든 결과도 보호 정지 근거가 아니다. 정상 wall 이후의 wall-gap/protection 주입은 선행 정상
구간에 도달하지 못해 NOT REACHED이며, 새 wall work-missing/snapshot fault runner는 미구현이다.
기존 functional fault suite의 결과를 새 wall suite에 전용하지 않는다.

## 연결과 원인 분리

- CARLA 원본10ms model dt/frame·320-bin solver work와 원래 monotonic applied/acquisition/
  dependency를 별도 좌표로 보존한다. 동일 kernel clock만 공유하며 simulation→wall offset을
  만들지 않는다. 완료된 frame을 단일 EV에 한 번 정산하고 cached 관측 시각은 유지한다.
- Python/RPC receipt를 기다리던 owner를 shared triple buffer로 분리했다. ABI2는 CARLA
  run/session/actor/generation과 native application/initial/model origin에 묶인다. 각 방향의
  single reader/writer와 원본 wire CRC/P05·세션/권한 검사를 유지한다. 실제 file mapping이
  원본 work를 운반하며 새 Actual을 Python에서 합성하지 않는다.
- M7 전용 생성 Drive owner는 원래 monitor의 센서 ingress를 제어 body보다 먼저 호출한다.
  첫 receipt 후 INIT 위상과 model/wall 좌표를 구분하며 원래 reset20ms, Controller20ms,
  Zone/leaf10ms, Drive30ms·owner2/4ms·expiry를 유지한다. 생성본/원본은 `generated/`에 보존한다.
- server game thread만 admission→effort→physics를 실행한다. 다음 model10ms의 원래 권한을
  확인하고 preview에4ms 추가 여유를 요구한다. 실제 적용 전/완료 후 expiry·terminal을 확인하고
  완료 work 정산 ACK 전 다음 tick을 금지한다. source age를 늘리는 여유가 아니다.
- native 정산이 약1.4ms 안에 끝나도 engine frame 처리 사이의 공백은 남았다. 조건부 renderer
  대기 위치를 샘플에서 관측했지만 원인 제거를 입증하지 못했다. FIFO10, TCP_NODELAY,
 150tick 예열, null-RHI, inline render 및 두 옵션 결합도 정상 wall 주행을 만들지 못했다.
- 초기화 실패의 Steering/Brake는 accepted command가 없는 진단 Actual만 생성한다.
  valid 측정/원래 causal 계약이 없는 보호 Actual을 허용하려던 후보는 폐기했다. 해당 음성
  검사는 `InitFaultCannotInventMissingProtectiveActual`이다. 정상 승인 후0 torque 보호의
  wheel 독립성은 component에서만 검증됐으며 실제 wall 제동으로 수용하지 않는다.

## 실패·진단 이력

전체 실행별 count/error는 [attempt-summary.json](attempt-summary.json)에 있다. 실패 파일은
수정 후 PASS로 덮어쓰지 않았다. build/test 실패도 `build-checks/`, `server-build*.log.gz`에 보존한다.

| 시도 | 의미와 결과 |
| --- | --- |
| 01 | watch30s가 원래 schedule 용량을 넘어 생성 실패 후 joinable thread abort. 실행19s로 제한·정리 경로 수정. 정상 물리0 |
| 02–04 | RPC work 전달, 정상0. TCP_NODELAY도 도착 지연 제거 실패 |
| 05–08 | shared 경로, 새 Drive ingress·선택 여유·game thread FIFO 대조. 완료 전달을 분리했지만 INIT 원천 만료 지속 |
| 09–11 | stock VehicleControl zero 가정 실패, 예열 후에도 실패, null-RHI도 실패. NoDrive의 stock control getter 값은 유효한 제어/측정 근거가 아니며 최종 runner는 읽지 않음 |
| 12 | compact status 계측. RPC 최대0.078ms 대 pump gap26.148ms. INIT 보호 허용 후보도 유효한 Steering/Brake Actual 부재로 실패; 후보 폐기 |
| 13 | strace 진단. 관측 부하가 있으므로 timing 수용 불가 |
| 14–19 | sampler 진단. 초기 signal 예약 충돌/무효 수집·16 중단·17 port 점유 거부를 보존.19의 코드 주소 후보만 별도 요약. 성능 수용 근거 아님 |
| 20–21 | inline render, inline+null-RHI 대조도 정상0. 각각75/80 완료 physics 후 실패 |
| 22–23 | ABI1 영상/비영상 대조, 정상0. frame/work 전달과 한계 확인 |
| 24–25 | 최종 ABI2 scope 검증 후 비영상/영상 실행. 위 최종 표의 실패이며 정상/보호 제동 gate 미해결 |

`diagnostic-wait.json`은 실행 중 수집한 instruction pointer와 executable mapping 안의
return-address **후보**다. 완전하게 unwind한 call chain/원인 확정이 아니다. UE ELF의
p_vaddr-p_offset 보정 전 `run19-filtered-stack-symbols.json`의 symbol 분석은 무효다.
원래 샘플 stack words·실행 바이너리·UE 원본 소스·인증 값은 저장소에 포함하지 않았다.
일부 초기 failed candidate의 정확한 C++ 중간 소스는 보존하지 못했으며, 그 실행 hash/log와
RPC prototype·최종 소스만 있다. 최종 구현의 근거는 ABI2 실행·최종 소스/빌드로 한정한다.

## 보존과 재현

[artifact-manifest.json](artifact-manifest.json)은 원본/저장본 SHA256과 경로를 묶는다.
`.gz`는 원본 bytes의 gzip(mtime0)이며 큰 JSON/CSV/trace도 생략하지 않았다. `sources/`는
project-owned 최종 구현, `runtimeNN/probe/`는 당시 Python 입력, `installed-identity.json`은
서버 설치 identity다. 외부 작업 디렉터리는 `/d/shin/stratadrive-tools/m7-source/m7-wall-carla`다.

기존 pin/venv와 설치한 서버를 사용한다. source build/install은 기존 `install.py`·UE Build.sh
절차를 따르며 `server-build09.log.gz`가 최종 서버 빌드다. launch argv는 `run24-args.json`,
영상은 `run25-args.json`, functional 회귀는 suite의 argv에 보존한다. 기존 디렉터리를
덮어쓰지 않도록 output/runtime 경로를 새 경로로 바꾼다. FIFO18 가능 여부는 기존 Host
설정에 의존하며 runner가 전역 scheduler/권한을 바꾸지 않는다. final timing 중 build/CTest를
겹치지 않았다. 일반·ASan·TSan 검사는 실제 timing 측정과 구분한다.

```sh
cmake --build build/m7-functional -j 8
ctest --test-dir build/m7-functional -R '^M7' --output-on-failure
python3 tests/integration/carla/audit_m7_wall_carla.py \
  docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/run24 \
  --output /tmp/m7-wall-recheck.json
```

마지막 감사의 예상 exit는1/NOT_ACCEPTED다. 유효한 work/owner 실행 일부를 검증한 실패 기록을
전체 PASS로 해석하지 않는다. 다음 수정은 실제30ms 근거를 끊는 engine frame 공백을 제거하는
데 집중하고, 필요하면 물리/렌더 실행 분리를 검토한다. 그 뒤 같은 실제 runtime의 정상/영상·
wall fault/보호 정지·in-flight work·Actual-only/single writer·pause/reset을 일괄 검증해야 한다.
