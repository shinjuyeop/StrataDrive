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

## 화면 확인

현재 시험 runner는 `-RenderOffScreen`으로 실행해 CARLA 게임 창을 띄우지 않는다.
카메라 payload는 RGB/GT 첫 BGRA 프레임만 저장하고 나머지는 metadata/hash를 기록한다.
기존 결과는 전체 동영상이나 실시간 뷰어가 아니다.

- 바로 열 수 있는 [기존 전방 카메라 PNG](test-plan/evidence/m7_carla_1j_render_followup/native02-camera/first-rgb.png)는 과거 비주행 준비 시험의 정지 화면이다.
- 새 실행의 `camera-a/rgb-first.bgra.gz`는 첫 RGB 원본이다. 크기·format은 `camera-a/sensors.json`에 있다.
- 차량 움직임을 실시간으로 보려면 기존 단일 tick/writer를 유지하면서 camera/spectator 출력 경로를 연결해야 한다.
  `-RenderOffScreen`만 제거한다고 시험 차량을 추적하는 뷰어가 완성되지는 않는다.

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

[검증 안내](test-plan/README.md)에 M6·M7 대표 실행을 모았다.
CARLA 최초 package·source build·geometry·V1·solver 조사 등 단계별 원본은
`test-plan/evidence/m7_carla_1*/`에 남아 있다. 과거 계획을 현재 실행 순서로 따라가지 않는다.
