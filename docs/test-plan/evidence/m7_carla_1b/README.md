# M7-1b — 비주행 RGB / Semantic GT / Vehicle State 수집

2026-10-23 (Asia/Seoul). `7a2b0fa` + 미커밋 M7-1a와 이 M7-1b 변경에서 실행했다.
[M7 계획](../../m7_carla_preflight.md), [Plant Adapter 초안](../../../icd/carla_plant_adapter.md)을 따른다.
**수집·센서 lifecycle·50ms tick·제한된 fault/pause/reset 범위 완료**다. 정상 주행·M6 runtime·
AI inference/학습·Jetson·source build는 실행하지 않았다. 실제 ECU30ms freshness 해결 증거가 아니다.

## 재현 조건과 코드

- [수집 harness](../../../../tests/integration/carla/m7_1b_capture.py),
  [독립 trace 검사기](../../../../tests/integration/carla/analyze_m7_1b.py).
- [환경/Client wheel](environment.json), 서버 archive는 [M7-1a manifest](../m7_carla_1a/package.json).
  최종 실행은 서버 패키지 포함 cp310 wheel SHA
  `cd3f70a6c01793654ad4905813d03fcd20ad55a0343095d89eee3ccf78835d84`를 설치한
  `/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled`다. 기존 PyPI venv와 M7-1a 근거는 보존했다.
- CARLA Server/Client0.9.16, Town10HD_Opt, mkz_2020, 첫 spawn, physics/autopilot off.
  ego actuation API 호출0. ClearNoon·traffic0. 카메라 두 개는 ego actor 기준 `(1.5,0,1.7)m`,
  roll/pitch/yaw0°,Rigid attachment다. 800×600/FOV90°/sensor_tick0.05, lens_k/kcube0.
  이는 smoke fixture 배치이며 차량 rear-axle/OEM calibration이 아니다.
- synchronous0.05s, substep0.01s/max10, rendering on, Vulkan offscreen Low.
  [GPU 사용](nvidia-smi-live.txt). source clock은 CARLA sim seconds/round(ns), arrival/delivery는
  Host monotonic이다. 둘을 직접 빼지 않는다. 카메라 source time은 콜백 도착/재배달 시각으로 바꾸지 않는다.
- 센서별 callback inbox64, overflow는 newest drop+사유 기록. 콜백은 원본 image와 arrival만
  enqueue하며 tick을 호출하지 않는다. owner thread 하나가 tick/상태 snapshot/큐 소비를 맡는다.
  이미지 검증·hash·PNG sample export는 수집기 비용에 포함된다. callback 오류나 예외에도
  모든 센서 stop→queue close/clear→각 actor destroy를 시도하며 설정을 복원한다.
- GT raw BGRA의 red channel class ID와 label histogram을 사용한다. palette 변환은 없다.
  `online/records.jsonl`은 RGB/state, `training_evaluation/records.jsonl`은 GT만 담는다.
  `packets.jsonl`은 모든 stream의 검증용 audit다. 실제 AI runtime은 없으며 접근 제어/전송 ACL을
  검증한 것은 아니다. full image dataset은 저장하지 않고 전체 frame metadata/digest와 sample PNG만 보존한다.

서버는 [실제 명령/환경](server-02-process.json)대로 별도 terminal에서 실행한다.
M7-1a의 cold-start timeout 이력이 있으므로 world 준비 전 실패를 기록하고 새 시도로 재실행한다.

```sh
python3 -m venv /d/shin/stratadrive-tools/carla-0.9.16/venv-bundled
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -m pip install --no-index --no-deps /d/shin/stratadrive-tools/carla-0.9.16/server/PythonAPI/carla/dist/carla-0.9.16-cp310-cp310-manylinux_2_31_x86_64.whl
```

서버 디렉터리에서:

```sh
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json ./CarlaUE4.sh -RenderOffScreen -quality-level=Low -nosound -carla-rpc-port=2000 -vulkan -stdout -FullStdOutLogOutput -log
```

저장소 root에서 output을 매번 새 경로로 지정한다. 기존 output 덮어쓰기는 거부한다.

```sh
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -I tests/integration/carla/m7_1b_capture.py --output /d/shin/stratadrive-tools/carla-0.9.16/m7-1b/new-attempt
python3 tests/integration/carla/analyze_m7_1b.py /d/shin/stratadrive-tools/carla-0.9.16/m7-1b/new-attempt
```

## 실제 시험과 결과

최종 [attempt04 summary](attempt-04/summary.json), [독립 재계산](attempt-04/offline-verification.json).
수집 전에 profile을 result manifest에 고정했다. nominal은 startup20/main200/drain20,
callback fault/after-reset은 각각20/40/20, exception case는22tick에서 의도적으로 중단한다.
각 case의 추가1tick은 cleanup 확인이며240tick 수집 분모에 포함하지 않는다. setup/settings/
reload 단계의 서버 frame 진행도240tick 검사 범위 밖이며, reset 후 frame 번호가0으로 돌아온다고
가정하지 않는다. run/plant epoch/episode로 분리한다.

| 최종 case | 관측 | 판정 |
| --- | --- | --- |
| [nominal](attempt-04/nominal/result.json) | 240tick의 frame+1/50ms·sim time 단조, main RGB/GT/state 각200/200. startup 카메라 각1누락, state20/20; drain 전부20/20 | PASS (main 수용 기준), startup 누락 보존 |
| [callback_faults](attempt-04/callback_faults/result.json) | frame8314의 RGB/GT/state를 pipeline에서 각각 drop, 모두 원래 frame의 missing으로 남음. RGB/GT frame8319를32번째 전달 뒤로 보류·재배달하여 reordered2건, frame8320의 duplicate3건 거부 | 기대 fault 검출 PASS, 정상 무누락 PASS가 아님 |
| [exception_cleanup](attempt-04/exception_cleanup/result.json) | 22tick 뒤 의도적 InterruptedError, 두 sensor stop/콜백 quiet·queue clear, sensor/ego 모두 destroy=true, owned 잔존0 | PASS |
| [after_reset](attempt-04/after_reset/result.json), [reset](attempt-04/reset.json) | fresh client로 실제 world reload, episode/run ID 변경·epoch1→2. main RGB/GT/state 각40/40, old state metadata 거부. boundary replay는3stream old epoch를 각각 거부 | 수집 reset 범위 PASS |

RGB/GT마다 width/height/stride/raw byte 길이, 원래 sim timestamp와 frame을 확인했다.
같은 frame의 RGB/GT pose 일치와 actor→camera rigid extrinsic(오차<0.1mm)을 확인했다.
Vehicle State는 WorldSnapshot의 ActorSnapshot에서 pose/velocity/acceleration/angular velocity를
읽었으며 actor origin 기준이라고 명시했다. 프로젝트 반사 좌표·각속도 axial 부호/단위를
기록하고 별도 비영 벡터 reflection 왕복/yaw 부호를 검사했다. rear-axle transform은 미확정이다.

[RGB sample](attempt-04/nominal/online/rgb.png)은 실제 영상을 열어 도로/건물/하늘이 보임을
확인했다. [GT raw ID PNG](attempt-04/nominal/training_evaluation/semantic_ids.png)는 시각화 palette가
아닌 원래 class ID다. 관측 label IDs는1,2,3,6,7,8,9,11,14,18,20,21,22,24,25이며 모든 frame의
histogram 합은480000pixel이다. 모든 frame의 full pixels를 보존하지 않았으므로 추후 pixel
품질 검토는 retained sample 범위다. GT를 학습된 perception 결과로 해석하지 않는다.

[pause](attempt-04/nominal/result.json)는 wall250.290497ms 동안 frame8167과 sim6.600764627568424s가
불변이었고 다음 tick이 연속 진행했다. callback fault/after-reset에서도 같은 동작을 확인했다.
wall monitor/ECU를 연결하지 않았으므로100ms timeout/latch·재가입은 NOT RUN이다.
최종 nominal의 tick span은11.961472986wall s,12logical s로 RTF1.003220926이다.
이는 tick1 시작→tick240 완료 구간(콜백 처리·PNG export·pause 포함)이며 이후 최대10s
누락 대기, cleanup/reload를 제외한다. 다른 case의 span/RTF는 각 result에 있다.
이를 Host 실시간20Hz 보장이나 M6 quiet 부하 수용 확대로 주장하지 않는다.

[boundary replay](attempt-04/boundary-replay.json)는 다음을 **분리된 synthetic/metadata 시험**으로 확인했다.
3stream old epoch와 이미 missing 확정된 frame의 뒤늦은 packet 거부,64개 큐에65번째 입력 시
newest overflow1건·capacity64 유지·close시 clear, coordinate 부호/왕복이다.
실제 sensor callback 큐의 high-water는nominal2/fault3이므로 live overload/overflow 검증은 아니다.
인위 delay는 원래 acquisition을 유지한 채 되돌아온 frame으로 join했고 nearest-frame 대체는 없다.
late-after-deadline은 metadata replay이며 별도 live10s 초과 지연 시험은 수행하지 않았다.

## 실패와 원본 보존

전체 suite **4시도1PASS/3FAIL 또는 native incomplete**다. 작은 진단 probe는 별도 분모다.
실패 당시 source hash와 최종 코드에서 이전 source를 복원할 patch를
[harness revisions](harness-revisions.json), [patch](historical-harness.patch)에 남겼다.

| 시도 | 실제 결과 / 처리 |
| --- | --- |
| [01](attempt-01/summary.json), [process](attempt-01-process.json) | nominal main200세트 수집 뒤 `is_listening` 메서드를 속성처럼 읽어 항상 truthy로 오판. cleanup을 중간에 중단해 actor가 남음. 이후 [server1](server-exit.json)이SIGSEGV/139 종료. [server stdout](server-stdout.txt) 보존, crash 원인 미확정 |
| [02 process](attempt-02-process.json) | 메서드 호출 및 끝까지 cleanup 시도로 수정 후 nominal/fault/예외3case PASS. 같은 client의 native `reload_world(False)`에서SIGSEGV, process139·최종 summary 미작성. 부분 result/trace 보존 |
| [03 summary](attempt-03/summary.json), [process](attempt-03-process.json), [stderr](attempt-03-stdout.txt) | 서버 포함 wheel의 새 venv에서도3case PASS, 같은 reload 호출에서native SIGSEGV/-11. faulthandler stack과 before_reload checkpoint 보존. [부분 offline 검사](attempt-03/partial-offline-verification.json)는3case만 PASS이며 suite 완료가 아님 |
| [04 summary](attempt-04/summary.json), [process](attempt-04-process.json) | 센서 client를 retire하고 fresh client로 world reload, 네 case와 최종 설정 복원/잔존0 모두 PASS |

[listener probe](listener-probe-pypi-fixed.json)는 before=false→listen=true→stop=false→wait=false,
삭제true를 확인했다. [probe 추가 실패 기록](probe-errors.json)은 server1 crash 후 recovery
연결 timeout과 최초 probe에서 method 객체의 JSON 직렬화 TypeError를 명시한다.
[fresh reset probe](fresh-reset-probe.json), [exit](fresh-reset-probe-exit.json)와
[재현 script](fresh_reset_probe.py)는 센서 이력이 없는 client에서 실제 reload 성공을 확인했다.

**OPEN-M7-1B-01:** 같은 sensor-session client의 reload native crash는 두 wheel에서 재현됐다.
최종 한정 운영 경로는 stop/destroy·client retire→fresh client→reload→새 run/epoch/actor/센서다.
root cause나 일반 SDK reset 안정성은 해결됐다고 주장하지 않는다. callback/actor 객체를 새
run에 재사용하지 않는다. 반복 reset/장기 soak와 SDK 원인 조사는 후속이다.
**OPEN-M7-1B-02:** 최초 cleanup 실패 뒤 server1 crash 원인은 미확정이다. 뒤 시도에서 없었다는
이유로 옛 crash를 해소/면제하지 않는다. `is_listening()` 호출 수정은 판정기 오류 수정이며
이것만으로 server crash 원인을 확정하지 않는다.

## 시험 ID 적용 범위와 다음 단계

- M7-1-02: sensor parent/stop·queue/actor cleanup까지 정상/예외 경로 한정 PASS.
- M7-1-03/04: 이번 비주행240tick·frame/time·RGB/GT/state 수집/format/pose·채널 분리 범위 PASS.
  tick owner는 thread identity와 expected next frame으로 duplicate/다른 thread 요청을 RPC 전에
  거부했다. CARLA 외부 client의 tick 권한 차단/actuation writer 검증은 M7-1c다.
- M7-1-05: 실제3stream drop, 카메라 delay/reorder·duplicate 검증과 metadata/synthetic 경계 시험
  **부분 PASS**. live overload·10s 초과 지연과 실제 driving containment는 NOT RUN.
- M7-1-06: 실제 pause/reload·fresh run/epoch·old metadata 거부 **부분 PASS**.
  기존 ECU wall monitor/old Actual·INIT/arm 재가입은 NOT RUN.
- M7-1-07~09: 실제 actuator 경계/Drive30ms·주행 허가 시험은 M7-1c이며 NOT RUN.

다음 작업은 M7-1c actual-only typed ingress·single writer와 기존 Drive 검증을 활용한
freshness negative 시험이다.50ms world tick/30ms freshness·calibration·구간 actuation/energy
문제는 그대로이며 정상 주행 연결은 BLOCKED다. 원래 M6 코드·계약·수치·판정은 변경하지 않았다.

증거의 큰 pixel 데이터·native core는 저장소 밖에 두고, repository에는 JSON·gzip metadata와
nominal sample만 보존했다. gzip trace는 원본 JSONL의 byte 내용을 바꾸지 않고 압축했다.
원래 raw trace로 oracle를 실행하며 저장소 보관본은 압축을 풀어 동일 경로에서 재검사할 수 있다.

최종 [독립 client probe](final-probe.json)에서 vehicle/sensor0, async·fixed_delta=None·rendering on을
확인했다. 이후 서버2에SIGTERM을 보내 종료했고 [종료/포트 확인](shutdown.json)에서 시험 서버
프로세스와2000/2001/2002 listener가 없었다. [launcher exit](server-02-exit.json)의-15는 명시적
SIGTERM 정리 결과다. 설치와 두 venv는 보존했다.

정적/독립 검증: Python 문법·`git diff --check` 오류0, 변경 문서의 로컬 링크 깨짐0,
M6 종료 review/requirements/profiles/기존 구현 변경0. 저장소의 gzip를 풀어 원래 JSONL과
byte 일치를 확인했고, 실행 source hash가 최종 attempt04 manifest와 일치했다.
[offline negative 검사](oracle-negative-checks.json)는 원본을 바꾸지 않은 임시 복사본에서
source ns 변조, cross-stream timestamp 불일치, online GT 혼입을 각각 거부했다.
증거 파일 hash는 [SHA256SUMS](SHA256SUMS)에 있다. 기존 M6/SDK 회귀는 재실행하지 않았다.
