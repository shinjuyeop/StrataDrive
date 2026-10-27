# M7 NoDrive 최소 서버 포트

CARLA0.9.16 commit `294096eb1c38eabf246e4f3a9cdab704e33a7f4c`와 프로젝트의
UE4.26.2 Linux 도구체인을 대상으로 하는 **opt-in 0 effort 진단 포트**다.
정상 주행 backend가 아니다. 실행 판정은 [M7-1k evidence](../../../docs/test-plan/evidence/m7_carla_1k/README.md)를 따른다.

`install.py --carla <source-root> --manifest <external-path.json>`은 고정 revision과 원본
integration 파일을 검사하고 프로젝트 소스를 외부 CARLA fork에 설치한다. 다운로드·빌드·실행은
하지 않는다. 재실행은 manifest의 원본을 기준으로 패치를 재생성하며 알 수 없는 변경을 거부한다.
manifest는 실제 설치 소스 hash와 기존 RPC130개의 허용/차단 결정을 보존한다.
원래 빌드 호환 패치와 SimReady 설정을 변경하지 않는다.

`UM7NoDriveMovement`는 기존4W component의 wheel/animation 연결을 유지하고 명시적으로
바인딩된 차량만 `PxVehicleNoDrive`로 전환한다. 그 차량에서는 stock engine/gear/control
처리를 실행하지 않는다. 다른 차량은 기존4W 동작을 사용한다. M6 원본 receiver·codec12개는
byte 그대로 복사해 별도 `M7Native` UE 모듈에서 C++17/clang10/libc++로 컴파일한다.
Linux visibility 설정으로 필요한 원본 심볼을 내보내며 외부 PhysX SDK 바이너리를 링크하지 않는다.
엔진 소스/PhysX solver는 수정하지 않는다. 다른 플랫폼/UE 버전은 미지원이다.

서버는 `-StrataM7ZeroProbe`와 최소32문자의 `STRATADRIVE_M7_OWNER_KEY`가 모두 있어야
bind를 허용한다. owner key는 실행 환경에서 만들고 서버/시험 client에만 전달한다. 저장소,
로그, RPC evidence에 키를 넣지 않는다. 전용 서버·무허가 client 배제는 계속 환경 gate다.
stock CARLA 전체를 인증·암호화하는 기능으로 주장하지 않는다.

RPC는 `client.m7_nodrive(JSON-string)` 하나이며 schema는 `m7-nodrive-zero-probe-v1`이다.
uint64 값은 정확한 decimal 문자열로 보존한다. `describe` 외 변경/receipt 요청은 owner key,
서버가 발급한 run UUID/session을 요구한다. wire/owner-wire v1 개정이 아니다.

| 요청 | 동작 |
| --- | --- |
| describe | 진단 한계·현재 frame·readback 조회. 정상 driving/work capability는 false |
| geometry | owner/run/session과 동일 physics generation을 검사한 읽기 전용 reference/rest geometry. actor/body/COM pose·reference bone·offset을 SI로 반환하며 tick/actuation 없음 |
| bind(actor) | sync10ms·4wheel 확인, 새 session/application epoch 발급, NoDrive 생성. 실패는 latch |
| stage(frame, steering/brake/drive) | 원래 CAN ID/FD flags/전체 payload hex와 oldest/expiry 검사. 각 native Actual receiver/P05/epoch/sequence/source 검사. 세 값 모두 정확히0일 때만 원자적 수용 |
| advance(ticket) | 한 번만 tick cue를 큐에 넣음. 응답은 queued이며 physics receipt가 아님 |
| receipt | physics 후 실제 frame/시각·원래 Actual·setter readback·raw signed ω 조회. 반복 조회는 재적용 없음 |
| pause | pending 폐기·setter 제거·latch. 자동 재무장 없음 |
| reset | pending 폐기·실제 physics state 재생성·latch. epoch 재사용으로 주행을 재개하지 않음 |
| close | setter 제거·바인딩한 ego 종료·독점 gate 해제. 다음 actor는 새 INIT/session 필요 |

바인딩 중 기존 제어·force/velocity/pose·physics·설정/reload·batch·일반 tick RPC는 서버에서
거부하고 route별 거부 횟수를 조회할 수 있다. `FCarlaServer::Tick` 내부 cue도 통과시키지 않는다.
읽기 RPC는 명시 allowlist다.
pre-physics에서 staged/queued/frame·10ms·동일 physics generation을 검사하고 한 번 소비한다.
post-physics 검증 실패는 ambiguous latch로 남기며 다음 tick을 막는다. 수신/advance timeout은
조회로 대조하며 advance를 맹목적으로 재시도하지 않는다.

clock은 `m7-zero-probe-logical-frame`이며 bind 원점1s + frame차×10ms다. 원래 Actual
payload source time을 바꾸지 않고 전체 구간 age30ms/skew10ms·exclusive expiry를 검사한다.
서버 simulation begin/end는 별도로 기록한다. 이 진단 clock/합성 epoch는 실제8-role authority,
native wall deadline 또는 kernel clock mapping 증명이 아니다. 과거 sample을 재취득했다고
표시하지 않는다.

[M7-1l geometry 검증](../../../docs/test-plan/evidence/m7_carla_1l/README.md)은5개 INIT 자세에서
reference bone→body→COM→world→actor를 교차 검증했다. wheel resting center와 contact patch,
공개 `center_of_mass`(RPC에서 이미 m로 변환된 COMNudge)와 실제 PhysX COM pose를 구분한다.
식별한 기준점은 body에 고정된 nominal rear-axle **rest** 중심이며 suspension에 따라 움직이는
wheel center 측정이 아니다. nonzero 조향 부호·브레이크 보정·주행은 계속 미검증이다.

캘리브레이션 없는 nonzero rad/Nm/Pa를 모두 거부한다. wheel geometry/max brake readback은
보정 완료가 아니다. `set_*`는 적용 demand readback이며 새 actuator Actual이 아니다.
raw ω를 clamp/abs/epsilon으로 보정하지 않는다. `interval_work_valid=false`이며 endpoint
Tωdt, SOC/회생 수용이나 full Actual 주행을 주장하지 않는다. RGB/GT·AI·Jetson은 이 포트 시험
범위 밖이며 기존 영상50ms와 ECU 주기/freshness 계약은 그대로다.

빌드는 기존 환경에서 `BuildCarlaUE4.sh --build --no-simready`,
`make PythonAPI ARGS=--python-version=3.10`을 사용한다. 기존 Client와 바이너리를 백업하고
별도 venv에 새 wheel을 설치한다. 서버가 살아 있는 동안 module을 다시 링크하지 않는다.

합성 fixture는 저장소 root에서 다음처럼 빌드한다. 실제 vECU/Zone 반환을 대체하는 정상
입력 생성기가 아니다.

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Werror \
  -Iinterfaces/common -Iinterfaces/steering -Iinterfaces/brake -Iinterfaces/drive \
  tests/integration/carla/m7_1k_fixture.cpp \
  interfaces/{common,steering,brake,drive}/*.cpp -o <external-fixture>
<extension-venv>/bin/python tests/integration/carla/m7_1k_server_probe.py \
  --fixture <external-fixture> --output <new-evidence-dir> \
  --expected-version 294096e-dirty
python3 tests/integration/carla/audit_m7_1k_server_probe.py \
  <new-evidence-dir>/result.json --output <new-audit.json>
```
