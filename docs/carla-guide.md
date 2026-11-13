# CARLA 실행과 결과 확인

이 저장소의 CARLA는 고정 source build와 NoDrive 확장을 사용하는 시험 환경이다.
현재 검증된 기능과 wall 실행의 한계는 [프로젝트 상태](project-status.md),
단일 writer·clock·work 계약은 [CARLA ICD](interfaces/carla-plant-adapter.md)를 따른다.

## 준비된 Host 경로

| 항목 | 경로 |
| --- | --- |
| UE4.26.2 | `/d/shin/stratadrive-tools/UnrealEngine_4.26` |
| CARLA 0.9.16 source | `/d/shin/stratadrive-tools/m7-source/carla-0.9.16` |
| 확장 client Python | `/d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python` |
| NoDrive fixture | `/d/shin/stratadrive-tools/m7-source/m7-1m-fixture` |
| Native functional 실행 파일 | `build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow` |

위 경로는 현재 Host 기준이며 다른 PC에 자동 설치되지 않는다.
CARLA commit `294096eb1c38eabf246e4f3a9cdab704e33a7f4c`,
UE commit `e9d9e60c85f643e10eeb03f42f61554d18dcb30f`와 프로젝트 patch를 사용한다.
Stock pip client만으로 프로젝트 RPC를 실행할 수 없다.
설치·모듈 재빌드는 [NoDrive 확장 안내](../tools/carla/m7_nodrive/README.md),
이전 환경/빌드 문제는 [보관 이력](archive/carla-history.md#preflight)을 따른다.

## 한 개의 기능·영상 시험 재실행

저장소 루트의 Linux 터미널에서 실행한다. Native binary가 없거나 source를 변경했다면 먼저 빌드한다.

```sh
cmake -S . -B build/m7-functional -DCMAKE_BUILD_TYPE=Release -DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON
cmake --build build/m7-functional --target m7_wheel_shadow --parallel 2
```

다음은 기존 통합 suite에서 `camera-a` 하나만 실행하는 명령이다.
GPU/엔진 로딩·shader 준비에 시간이 걸릴 수 있다. RPC 포트2200/2201/2202가 비어 있어야 한다.
Runner는 각 case마다 전용 서버를 만들고 종료한다. Runtime·output은 새 경로여야 한다.

```sh
run_dir="$PWD/build/carla-manual-$(date +%Y%m%d-%H%M%S)"
python3 tests/integration/carla/m7_integrated_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --native "$PWD/build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow" \
  --runtime "$run_dir/runtime" \
  --output "$run_dir/evidence" \
  --cases camera-a
```

옵션은 `python3 tests/integration/carla/m7_integrated_run.py --help`로 확인한다.
전체 기본 suite에는 고장·중단 case가 포함된다. 위 명령은 기능 clock의 고정 시나리오이며
정상 wall 주행이나 Reference 30km/h 폐루프 시험이 아니다. 동작 중인 외부 서버를 별도로 시작할 필요는 없다.

시뮬레이션 시간의 연속 주행·영상·보호·고장 7개 시험은 위 명령의 `--cases camera-a`를
`--simulation-time --held-steer-sleep`으로 바꿔 실행한다. 연속 case는 각각 시뮬레이션60초이며
실제 실행 시간은 더 길다. 원본 work trace 저장 공간이 필요하다.
실행 분모·한계와 저장 증거 복원은 [연속 실행 증거](test-plan/evidence/m7_carla_integrated/simulation-time/README.md)를 따른다.

## 비영상 wall5ms 실험 재실행

`wall5-hv50-v1`의 단기 정상/보호4회는 통과했으며 전체 실시간 수용은 OPEN이다. 기본10ms 기능 실행과 구분한다.
원본 시각·source30ms·owner2ms/4ms를 유지하고 카메라는 사용할 수 없다.
아래는 `wall5-hv50-v1` 명령이다. 파생 HV의 oldest dependency만50ms이며,
`--wall-hv-dependency-ms 50` 옵션 생략 시 기존30ms다.
[적용 범위와 근거](interfaces/carla-plant-adapter.md#carla-파생-hv-입력-예산-재조정)를 따른다.
[개정 후 실제 결과·빌드 식별](test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/README.md)과
[이전 성공·실패](test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/README.md)를 구분한다.

```sh
cmake --build build/m7-functional --target m7_carla_wall_owner --parallel 2
run_dir="$PWD/build/carla-wall5-$(date +%Y%m%d-%H%M%S)"
python3 tests/integration/carla/m7_1o_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --native-actual "$PWD/build/m7-functional/tests/integration/carla/m7_1g/m7_carla_wall_owner" \
  --runtime "$run_dir/runtime" --output "$run_dir/result" \
  --scenario tests/integration/carla/scenarios/m7_integrated_v1.txt \
  --vehicle-substeps 320 --solver-work --compact-work --held-steer-sleep \
  --wall-native --wall-step-ms 5 --wall-hv-dependency-ms 50 \
  --wall-nullrhi --wall-inline-render --ticks 900
python3 tests/integration/carla/audit_m7_wall_carla.py \
  "$run_dir/result" --output "$run_dir/audit.json"
```

공유 ABI3와 같은5ms 서버 모듈이 필요하다. Native만 빌드하고 이전 서버 모듈과 혼용하지 않는다.
`--native-fault wall-gap`은 physics만100ms 보류하고, `--native-fault protection`은 명시적
보호 요청이다. 두 시험 모두 정상50구간 이후 요청해야 하며, 그 전에 자연 보호가 발생하면
의도한 fault 시험을 통과한 것이 아니다. Raw 감사와 별도로 runner의 server exit도 확인한다.

## 주행 영상 보기

실행 중 차량을 보려면 준비된 Linux Host의 데스크톱 터미널에서 다음 명령을 실행한다.

```sh
bash tools/carla/view_stop30.sh
```

맵 로딩이 끝나면 `StrataDrive CARLA LIVE — STOP30` 창에960×540 차량 뒤쪽 카메라와
현재 속도가 표시된다. 가속→30km/h 유지→제동→정지/HV-off까지 실행 후 창이 닫힌다.
시뮬레이션60초의 계산은 실제로 더 오래 걸릴 수 있다. 창의 닫기 버튼은 표시만 끄고,
터미널의 `Ctrl+C`는 실행을 중단한다. 창을 열려면 SDK Python의 tkinter와 사용 가능한
`DISPLAY`가 필요하다. 도구 설치 위치가 다르면 `STRATADRIVE_TOOLS`로 지정한다.

이는 실행 중 생성되는 RGB를 표시하는 창이다. 최신 프레임 하나만 보관하며 GUI가
CARLA tick이나 제어 명령을 보내지 않는다. 결과는 매번 `build/carla-live-*`에 저장된다.
아래 runner를 직접 쓸 때는 `--cameras --live-view`를 추가하면 된다.
`bash tools/carla/view_stop30.sh --record-video`로 표시와 원본 녹화를 함께 사용할 수도 있다.

시험 runner는 `-RenderOffScreen`으로 실행한다. `--cameras`만 사용하면 기존320×240
전방 RGB/GT 첫 프레임과 전체 metadata/hash를 저장한다. **`--cameras --record-video`**는
고정 STOP30 profile의 RGB를960×540·20Hz 차량 뒤쪽 시점으로 녹화한다. 제어기·단일 tick/writer 경로는 유지한다.
화면용 녹화이며 M8의 기존 수용 증거를 덮어쓰지 않는다. 녹화 옵션만으로는 화면 창이 뜨지 않는다.

30km/h 가속→정지/HV-off를60초 MP4로 만드는 명령이다. 준비된 Host 경로와 FFmpeg가 필요하다.
실제 실행에는 로딩·rendering·원본 기록 시간이 들며 영상 재생보다 오래 걸릴 수 있다.

```sh
run_dir="$PWD/build/carla-video-$(date +%Y%m%d-%H%M%S)"
python3 tests/integration/carla/m7_1o_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --native-actual "$PWD/build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow" \
  --runtime "$run_dir/runtime" --output "$run_dir/run" \
  --vehicle-substeps 320 --solver-work --held-steer-sleep --simulation-continuous \
  --route-profile tests/integration/carla/scenarios/m8_stop30_v1.json \
  --route-startup-seconds 600 --ticks 6000 --cameras --record-video
python3 tools/carla/encode_video.py "$run_dir/run" --output "$run_dir/drive-stop.mp4"
```

`drive-stop.mp4`를 영상 플레이어로 연다. 카메라의 원본 frame/hash/time을 검사한 뒤
20fps로 인코딩하며, 속도·가속/제동/정지/HV-off 표시는 같은 frame의 물리/native 로그에서
가져온다. `camera-original.mp4`에는 자막 없는 카메라 영상, `video.json`에는 프레임 수와
길이·인코딩 검사가 남는다. 60초의 raw BGRA 저장에 약2.5GB가 필요하다.

기존 결과의 첫 정지 화면은 [전방 카메라 PNG](test-plan/evidence/m7_carla_1j_render_followup/native02-camera/first-rgb.png)에서
볼 수 있다. 녹화 옵션 도입 이전의 M8 실행에는 전체 카메라 동영상이 없다.

## 결과를 읽는 순서

| 파일 | 확인할 내용 |
| --- | --- |
| `evidence/suite.json` | case·runner·독립 audit의 exit와 최종 판정 |
| `evidence/camera-a/result.json` | 실제 receipt/정산·권한·fault·정리 결과 |
| `evidence/camera-a/sensors.json` | RGB/GT frame/time·identity·수·gap·payload hash |
| `evidence/camera-a-audit_m7_integrated.json` | 시나리오·영상·metadata·시간 결과의 독립 검사 |
| `runtime/camera-a/server.log`, `client.log`, `readiness.log` | 엔진·client·준비 실패 원인 |

Trace는 실행에 따라 원본 JSONL 또는 무손실 gzip이다. 정상·기능 fault 차단·timing·종료를
각각 확인한다. 기대한 fault가 검출돼도 물리적 보호 제동/정지까지 검증한 것으로 해석하지 않는다.
새 실패를 숨기거나 기존 evidence를 덮어쓰지 않는다.

## 저장된 검증 결과 찾기

현재 사용하는 Unreal의 `Engine/DerivedDataCache`와 CARLA 프로젝트의 `DerivedDataCache`는
오래된 시험 빌드와 구분해 보존한다. 삭제 후 첫 실행에는 mesh·거리장·셰이더 재생성이 필요하며,
[M10 동시 실행 준비](test-plan/evidence/m10_paired_v2/README.md)에서는 시작 지연과 첫 렌더
프레임 충돌이 발생했다. 캐시 재생성은 별도 준비로 기록하고, 원래 실행 설정으로 다시 확인한
뒤 주행·영상 성능을 측정한다. 캐시 준비 시간은 실제 물리 주행 지연 수치에 합치지 않는다.

[검증 안내](test-plan/README.md)에 M6·M7 대표 실행을 모았다.
CARLA 최초 package·source build·geometry·V1·solver 조사 등 단계별 원본은
`test-plan/evidence/m7_carla_1*/`에 남아 있다. 과거 계획을 현재 실행 순서로 따라가지 않는다.
