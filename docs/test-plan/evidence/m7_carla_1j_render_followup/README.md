# M7-1j 후속 — 자원 수명 추적과 asset 준비

2026-10-26 KST. 이전 [렌더링 조사](../m7_carla_1j_render_diagnosis/README.md)의 후속이다.
기존 source binary/별도 Client 환경을 사용하며 engine·M6 소스/계약 변경은 없다.
이전 FAIL과 evidence는 수정하지 않는다. 정상 actuation/주행·native wall 수용은 범위 밖이다.

## 수명 추적

Trace01은 volume 초기화/소멸, static mesh proxy cache/소멸을 모두 기록했다.
53,255개 event를 얻었으나 계측 부하가 커져 identity 조회 뒤 world RPC20s timeout으로
lifecycle이 FAIL했다. ego/camera는 NOT RUN이다. LoadMap 로그만으로 조회 준비를 판정한
한계도 남긴다. SIGINT 후 engine shutdown 로그가 진행됐지만 debugger 종료가 지연돼
GDB에 SIGTERM을 보냈다. debugger exit0을 서버 정상 종료로 판정하지 않는다.

[주소 대조](trace01-analysis.json)의13개 volume/proxy 주소 일치는 모두 SIGINT 종료 요청
뒤의 관측이다. destructor 진입과 실제 free는 다르며, 이후 해당 주소의 읽기를 관측하지 않았다.
이 결과는 실행 중 use-after-free의 증거나 해당 메시의 결함 판정이 아니다.
Initialize의 최적화된 인자 읽기 실패1,958개도 기록에 보존한다.

Trace02는 proxy 전체 추적을 제거하고 volume event를 종류별10,000개로 제한했다.
셰이더 처리 시점에10s 간격으로 shader outstanding/external/queue/finalize/maps와
Distance Field referenced task 수를 읽었다. inferior 함수를 호출하거나 설정을 바꾸지 않았다.
Engine 초기화 완료 로그 뒤 ego 정상/주입 예외2/2·102tick와 RGB/GT30쌍·150tick 수신,
actor 정리/설정 복원을 한정 확인했다. GDB 정지 신호는 없었고 SIGINT 후 inferior exit130이다.
기존 crash root cause는 미확정이다.

초기 한 시점의 queue0 뒤 맵 로딩에서 작업이 다시 생겼다. camera 수집 무렵에도
Distance Field 약60개와 shader 약3천 개가 남았다. 따라서 이 성공을 준비 완료로 분류하지 않는다.
GDB는 timing을 바꾸며 queue sampling은 모든 순간의0이나 wall deadline을 증명하지 않는다.

## 오프라인 준비

고정한 UE의 DerivedDataCache commandlet은 마지막에 shader compilation 완료,
Distance Field BlockUntilAllBuildsComplete, texture cache 완료와 DDC quiescence를 기다린다.
Town03_Opt와 하위9맵을 명시했고 NullRHI로 오프라인 준비했다. runtime 렌더링 검증과 구분한다.
캐시 삭제, distance field 비활성화, driver 변경은 하지 않았다.

DDC01은 `/Game/...` map 이름을 전달해 대상 맵0개로 종료했다. process exit0과 엔진의
Success 문구에도 불구하고 **맵 준비 FAIL**이다. 초기 editor 자원 일부는 이 과정에서도
캐시됐으므로 이후는 동일 cold 조건 비교가 아니다. [검사](audit-ddc01.json)가 이를 거부한다.
DDC02는 실제 파일 경로10개를 사전 확인·hash한 뒤 재실행했다.10개 대상 enumeration과
실제 Loading을 확인했으나 공통 soft reference 해석과 cooked platform data 생성이
보행자 skeletal mesh까지 확대됐다. 최소 runtime 준비와 구분해 **INCOMPLETE/수동 중단**으로
남겼다. SIGINT 뒤에도 blocking commandlet이 진행돼 해당 프로세스/자식에 SIGKILL을 보냈다.
tool completion은1이며 underlying wait status는 노출되지 않았다. OOM이나 준비 PASS로
해석하지 않는다. [검사](audit-ddc02.json)도 완료로 인정하지 않는다.
캐시 일부는 이미 생성됐으며 기존 캐시를 삭제하지 않았다. 맵10개를 모두 처리했다고 주장하지 않는다.

commandlet 검사는 process 종료와 대상 enumeration/처리·마지막 blocking drain·오류 요약을
함께 확인한다. 이미 dependency로 처리한 package를 다시 LoadPackage하지 않으므로 명시적
Loading 줄 수만으로 처리 개수를 판단하지 않는다. 범위가 커진 오프라인 준비의 대안으로
아래 실제 장면의 준비 상태를 직접 관측한다.

## 실제 runtime 준비 조건

Trace03과 별도 준비 harness에서 physics-disabled ego와 RGB/평가용 GT320×240을 유지한다.
world10ms·camera50ms를 사용하고 실제 world tick을 진행한다. 같은 Host의 debugger가 읽은
작업 수는 simulation timestamp와 별도인 진단 값이다. scene 생성 전/이전 맵의 관측은 제외한다.
shader outstanding/external/compile queue와 finalize/map의 실제 원소 수, Distance Field task가
모두0인 새 관측을10s 간격으로 두 번 요구한다. 양 센서의 callback 수신도 최소10개 확인한다.
이 조건은 timestamp restamp나 native freshness/deadline 완화가 아니다. 원래 snapshot 시각을
보존하며 별도1200s 한도는 이 준비 실행의 관찰 budget이다.

## 실제 결과와 한계

| 실행 | 실제 관측/한정 판정 |
| --- | --- |
| Trace03 runtime 준비 | [결과](trace03-warm-scene/result.json): **PASS**,23,620tick, RGB/GT callback 각각4,724개,1169.091s. 새 zero 관측 seq614/615의 간격10.015s. actor3개 제거·Episode 설정 복원 |
| 준비 관측 재검사 | [raw debugger join](audit-trace03-warm-scene.json):10개 조건 일치. cold 준비/완전 센서 delivery/독립 runtime TC10개 수용이 아님 |
| Trace03 준비 후 camera | [결과](trace03-camera/result.json):150tick/RGB·GT30쌍·정리/복원 PASS. 이후에도 queue0 관측. SIGINT 후 inferior exit130, GDB exit0 |
| Native01 새 프로세스 | [결과](native01-camera/result.json):150tick/RGB·GT30쌍·정리/복원 PASS, SIGINT tool exit130. debugger 미사용 |
| Native02 새 프로세스 | [결과](native02-camera/result.json):150tick/RGB·GT30쌍·정리/복원 PASS, SIGINT tool exit130. Native01과 별도 부팅, debugger 미사용 |
| 저장 metadata 검사 | camera별16조건 일치. [Trace03](audit-trace03-camera.json), [Native01](audit-native01-camera.json), [Native02](audit-native02-camera.json). 독립 runtime TC 수나 전체 M7 PASS로 합산하지 않음 |

준비 helper의 callback 수는 원래 frame/timestamp별 완전 delivery 검사가 아니다. 준비 후
별도 camera probe에서 원래 frame과 snapshot timestamp를 join했다. 첫 영상 간격6frame/60ms와
이후5frame/50ms를 그대로 보존한다. 이것은 최소 수신 시험이며 startup/정규20Hz 요구를
완화하거나 Drive freshness30ms·native2/4ms guard를 수용한 결과가 아니다.

[Native01 RGB](native01-camera/first-rgb.png)를 직접 확인했다. 이전 샘플의 큰 체크무늬
대체 재질 대신 벽면 재질이 보인다. 이 한 시점의 시야를 전체 맵/재질/GT taxonomy·학습
dataset 적합성으로 확대하지 않는다. GT는 진단 전용이며 AI 입력에 연결하지 않았다.

Native01/02 로그에는 새 material shader map miss, shader worker compile, Distance Field build,
static mesh build가 관측되지 않았다. native에서 내부 queue를 직접 읽은 것은 아니므로 로그
부재를 계측값0과 동일시하지 않는다. 초기화 로그22.38/22.17s는 공유 캐시가 준비된 조건의
관측값이며 cold 시작 시간/성능 수용이 아니다. 기존 handled Vulkan vendor ensure와 누락
보행자 animation·spline mesh 경고는 남아 있다. 전체 content/ODD 적합성은 OPEN이다.

실행 후 [정리](cleanup.json)에서 서버/commandlet/ShaderCompileWorker/GDB와 포트2200/2201/2202가
남지 않았고 GPU 가용24104MiB를 확인했다. [manifest](manifest.json)에 원본 외부 log 경로/hash,
실행 명령·프로세스 상태·코드 identity를 남겼다. UE/CARLA/wheel hash는 이전 조사와 일치한다.
private engine source 본문은 복사하지 않고 자체 debugger 계측 script와 구조화 관측만 보존했다.

## 현재 판단과 다음 작업

**준비된 Town03_Opt/mkz_2020/320×240 비주행 장면의 제한된 반복 baseline은 확보했다.**
이번 추적에서는 SIGSEGV가 재현되지 않아 원래 잘못된 참조의 생성/해제 원인을 입증하지
못했다. 캐시 준비가 메모리 결함을 수정했다는 뜻은 아니다. engine patch는 적용하지 않았다.
새 맵/미준비 asset·동적 actor·다중 camera 조건과 원래 crash는 계속 OPEN이다.

다음은 이 baseline에서 **NoDrive 단일 writer/frame stage·receipt 최소 서버 포트**를
별도로 구현·검증하는 작은 작업이다. 실제 effort/Brake Pa calibration·정지 wheel validity·
full Actual dependency/interval work를 입증하기 전 정상 주행 gate는 열지 않는다.
렌더링 root cause는 별도 격리 DDC의 cold 재현과 실패 시 cached/live 주소·allocation/free
추적이 남는다. 기존 캐시를 삭제해 재현하지 않는다. pause/reset·wall deadline은 이번에 새로
시험하지 않았으며 M6 코드·계약·수치·수용은 유지한다.

준비 실행은 전용 server와 자체 debugger의 새 출력 경로를 만든 뒤 사용한다. debugger script의
OUT과 gdb source 경로는 새 디렉터리로 바꿔 이전 event를 덮어쓰지 않는다.

```bash
/d/shin/stratadrive-tools/m7-source/carla-build-venv/bin/python \
  tests/integration/carla/m7_1j_warm_scene.py \
  --debugger-dir /tmp/m7-new-debugger-run \
  --expected-version 294096e-dirty --output /tmp/m7-new-warm-scene
```

이후 기존 render probe와 저장 metadata oracle를 실행한다. 모든 output은 새 경로만 허용한다.
SHA256SUMS는 이 묶음의 무결성용이며 전체 시스템 수용 판정이 아니다.
