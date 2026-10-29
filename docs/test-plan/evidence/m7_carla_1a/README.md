# M7-1a — 공식 package / Python 환경 / 비주행 lifecycle

2026-10-23 (Asia/Seoul). 실행 기준 `7a2b0fa` + 이 변경의
[m7_1a_smoke.py](../../../../tests/integration/carla/m7_1a_smoke.py).
[M7 사전 계획](../../../carla-guide.md)의 M7-1a 범위다.
서버 패키지와 venv는 저장소 밖 `/d/shin/stratadrive-tools/carla-0.9.16/`에 둔다.
source build/ScenarioRunner/정상 주행/실제 M6 runtime 연결은 수행하지 않는다.

## 재현과 환경

[Host snapshot](host.json), [wheel 원천·SHA256](wheel.json), [pip 다운로드](pip-download.txt),
[설치](pip-install.txt), [freeze](pip-freeze.txt)를 보존한다. Client import는 `python -I`로
PYTHONPATH/user site 영향을 배제하며 system Python에 패키지를 설치하지 않는다.
서버는 non-root 사용자로 off-screen/Low quality·sound off 실행한다.
no-rendering/null RHI 모드는 사용하지 않는다. camera 품질/센서 수집 검증은 M7-1b다.

공식 [release0.9.16](https://github.com/carla-simulator/carla/releases/tag/0.9.16)에 연결된
[Ubuntu package](https://downloads.carlasim.com/Linux/CARLA_0.9.16.tar.gz)와
[공식 PyPI0.9.16](https://pypi.org/project/carla/0.9.16/)의 cp310 wheel을 사용한다.
wheel SHA는 PyPI metadata와 대조한다. server package SHA는 로컬 파일 식별용이며
공식 독립 checksum 검증과 구분한다.

```sh
mkdir -p /d/shin/stratadrive-tools/carla-0.9.16/downloads
curl --fail --location --retry 3 --continue-at - --output /d/shin/stratadrive-tools/carla-0.9.16/downloads/CARLA_0.9.16.tar.gz https://downloads.carlasim.com/Linux/CARLA_0.9.16.tar.gz
python3 -m venv /d/shin/stratadrive-tools/carla-0.9.16/venv
/d/shin/stratadrive-tools/carla-0.9.16/venv/bin/python -m pip download --only-binary=:all: --no-deps --dest /d/shin/stratadrive-tools/carla-0.9.16/downloads carla==0.9.16
/d/shin/stratadrive-tools/carla-0.9.16/venv/bin/python -m pip install --no-index --no-deps /d/shin/stratadrive-tools/carla-0.9.16/downloads/carla-0.9.16-cp310-cp310-manylinux_2_31_x86_64.whl
mkdir -p /d/shin/stratadrive-tools/carla-0.9.16/server
tar -xzf /d/shin/stratadrive-tools/carla-0.9.16/downloads/CARLA_0.9.16.tar.gz -C /d/shin/stratadrive-tools/carla-0.9.16/server
```

기존 설치가 있으면 덮어쓰지 않고 manifest hash를 대조해 재사용한다.
시험 output 디렉터리는 시도마다 새로 사용한다(동일 경로는 거부한다).

서버 실행(별도 terminal, 작업 디렉터리는 위 `server`):

```sh
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json ./CarlaUE4.sh -RenderOffScreen -quality-level=Low -nosound -carla-rpc-port=2000 -vulkan -stdout -FullStdOutLogOutput -log
```

저장소 root에서 준비된 서버를 대상으로 실행한다. 각 RPC timeout은10s다. 서버 첫 로딩은
그보다 오래 걸렸으므로 port listening/버전 응답만으로 world 준비 완료를 판단하지 않는다.
실패 시 새 output 경로로 시도하고 기존 결과를 덮어쓰지 않는다.

```sh
/d/shin/stratadrive-tools/carla-0.9.16/venv/bin/python -I tests/integration/carla/m7_1a_smoke.py --output /d/shin/stratadrive-tools/carla-0.9.16/evidence/new-attempt
```

## 실제 실행 결과와 실패 원본

**M7-1a 한정 완료:** Client/Server0.9.16 일치·연결/world 조회, NON_DRIVING ego 생성,
일반/의도적 예외 종료·잔존0·world 설정 복원을 최종 시도에서 확인했다.
원본6시도는 **1PASS/5FAIL**이며 실패를 성공으로 바꾸지 않는다. 01은 서버 미실행을
확인한 사전 negative 시도다. 06 안의 예외 주입은 기대 동작이며 정상 cleanup을 검증했다.

| 시도 / 원본 | 관측 | 원본 판정 |
| --- | --- | --- |
| [01 prelaunch](attempt-01-prelaunch.json) | 서버 실행 전 server-version RPC10s timeout | FAIL (의도된 연결 불가 관측) |
| [02 live](attempt-02-live.json) | 첫 서버의 양쪽 버전0.9.16, `get_world`10s timeout | FAIL |
| [03 NVIDIA](attempt-03-nvidia.json) | NVIDIA ICD 지정 재실행, 양쪽 버전0.9.16, world 준비 전10s timeout | FAIL |
| [04 loaded](attempt-04-loaded.json) | world/ego24 생성·destroy=true, `get_actor(id)` 캐시를 잔존으로 오판 | FAIL, 판정기 문제 |
| [05 cleanup observation](attempt-05-cleanup-observation.json) | ego25,10tick 모두 snapshot에서는 부재지만 get_actor 캐시는 존재 | FAIL, 시간 대기만으로 해결되지 않음 |
| [06 current episode](attempt-06-current-episode.json) | ego26 정상·ego27 예외 종료 모두 destroy=true, 다음 snapshot/current actor list 부재, vehicle0·설정 복원 | PASS |

04/05는 CARLA actor 누수를 입증한 결과가 아니다. 공식
[Episode.cpp0.9.16](https://github.com/carla-simulator/carla/blob/0.9.16/LibCarla/source/carla/client/detail/Episode.cpp)의
`GetActorById`는 description cache를 먼저 반환하고, `GetActors`는 현재 episode의 actor IDs를
사용한다. 관측기 수정은 current `world.get_actors().find(id)`와 snapshot 부재를 함께 요구한다.
최종 실행은 두 경우 모두 cleanup 관측1tick으로 완료했다. 이전 시도의 원본·source hash와
최종 source에서 이전 판정기를 복원할 [patch](historical-harness.patch), [revision hash](harness-revisions.json)를 보존한다.
판정기 수정이 M6나 freshness 요구를 변경한 것은 아니다.

서버1은 RTX 사용 미확인·world timeout 상태에서 SIGTERM을 보냈으나 binary가 남았다.
10s 추가 grace 후 시험 소유 process group만 SIGKILL했다
([종료](server-01-exit.json), [강제 종료](server-01-forced-stop.json)). 정확한 renderer/정지 원인은
미확정이다. 서버2는 NVIDIA ICD를 명시했고 [GPU snapshot](nvidia-smi-live.txt)에 CARLA C+G
프로세스가 RTX3090에서 확인됐다. 재실행에서 로딩 대기 시간도 달라졌으므로 ICD만으로
모든 timeout 원인이 해결됐다고 단정하지 않는다. renderer pixel/camera 품질·FPS는 미검증이다.
[서버1 명령](server-01-process.json), [서버2 명령/환경](server-02-process.json),
[서버1 출력](server-01-stdout.txt), [서버2 출력](server-02-stdout.txt)을 보존한다.

최종 [별도 client probe](final-probe.json)도 vehicle0/sensor0·원래 async/no-rendering=false를
확인했다. 이후 서버2를 SIGTERM으로 종료했고 binary 부재·TCP2000/2001/2002 listener0을
확인했다([종료 상태](shutdown.json), [launcher exit](server-02-exit.json)). launcher의-15는
시험 종료 시 보낸 SIGTERM 결과이며 실행 crash 판정과 구분한다. 설치/venv는 재사용하도록 남겼다.

## 고정 artifact와 범위

[package manifest](package.json)의 archive는8,346,095,504bytes,
SHA256 `09e3ebb28df17962f0c997e66f4b914ad5ea6f1d6a6dbbf13c9f87eb38346d57`이다.
압축 해제 exit0, 약19GiB. 패키지 VERSION·실제 RPC 모두0.9.16이다.
PyPI cp310 wheel SHA는 `52b1f2fafb0655e25954f9f6d1e97c211a4da404217fd1d0094b4b7350737c95`로
공식 PyPI metadata와 일치했다. 패키지 포함 cp310 wheel은 SHA가 다르므로 manifest에 별도로
남겼으며 혼용하지 않았다. 실제 실행은 기록된 PyPI wheel이다. 같은 version string을 binary
동일성으로 간주하지 않는다. 향후 다른 wheel을 쓰면 별도 실행 근거가 필요하다.

map은 `Carla/Maps/Town10HD_Opt`, ego는 `vehicle.lincoln.mkz_2020`, spawn은 최종 JSON의
첫 spawn point다. 비주행 초기화에서 physics/autopilot을 끄고 control API를 호출하지 않았다.
50ms sync 설정은 lifecycle 관측에만 사용했고 원래 설정으로 복원했다.
M7-1-01은 PASS, M7-1-02는 **ego 정상/예외 lifecycle 부분 PASS**다. RGB/GT 생성·callback
정리까지 포함한02 전체,240tick/센서/clock·pause/reset/actual-only single writer·Drive 연결은
NOT RUN이다. 다음은 M7-1b 센서 수집이다. 정상 주행 gate는 계속 BLOCKED다.
M6 구현·계약·수치/수용, 기존 evidence를 변경하지 않았다. 소스 빌드·AI 학습·Jetson 배포는 없다.

정적 검증: 변경 문서 로컬 링크120개 깨짐0, Python 문법 검사·`git diff --check` 오류0.
원본 JSON에서6시도1PASS/5FAIL·최종 두 lifecycle PASS·설정 복원·잔존0을 대조했다.
증거 파일 hash는 [SHA256SUMS](SHA256SUMS)에 있다. 기존 M6 회귀 시험은 재실행하지 않았다.
