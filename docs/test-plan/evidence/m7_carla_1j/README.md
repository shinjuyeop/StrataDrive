# M7-1j — source build 준비와 독립 NoDrive SDK 검증

2026-10-23. **부분 완료 / CARLA 서버 확장은 BLOCKED**.
사용자의 후속 진행 지시에 따라 source build를 포함해 착수했다. 공개 CARLA 소스와
PhysX SDK를 내려받고 독립 SDK 포트를 구현·실행했다. Unreal Engine 접근 권한이 없어
CARLA/UE 빌드는 시작되지 않았다. 이전1a–1i 실패·M6 수용·구현·계약은 유지한다.

## 실제 Host와 공식 요구의 구분

| 구분 | 확인 결과 |
| --- | --- |
| 공식 CARLA0.9.16 [Linux build](https://carla.readthedocs.io/en/0.9.16/build_linux/) | 수정 UE4.26 `CarlaUnreal/UnrealEngine`의 `carla` branch 필요. Epic–GitHub 연결 필요. 문서상 저장 공간130GB, Ubuntu22.04 의존성에 g++-12 포함 |
| 실제 Host [preflight](host-build-preflight.json) | `/d` 가용297,449,078,784 bytes, `/`76,091,924,480 bytes. UE4_ROOT 미설정. g++-12/default clang 없음, clang++-14 존재. 새 소스는 `/d/shin/stratadrive-tools/m7-source`에 격리 |
| UE 접근 | Git `ls-remote` exit128, [GitHub CLI](ue-gh-access.json) HTTP404. 사용자가 Epic 계정 연결을 설정한 적 없다고 응답. 권한 확보 전 UE 호환 build 판정 불가 |
| 실제 CARLA build 시도 | [명령/exit2](build-carla-attempt01.json), [원본](build-carla-attempt01.log): 공식 BuildCarlaUE4.sh가 UE4_ROOT 누락으로 종료. **UE compilation NOT STARTED**, 서버 PASS 아님 |
| 공개 CARLA source | 0.9.16 commit `294096eb1c38eabf246e4f3a9cdab704e33a7f4c` clone 완료. 기존 실행 package/venv를 교체하지 않음 |
| 공개 PhysX source | `NVIDIAGameWorks/PhysX-3.4` commit `5e42a5f112351a223c19c17bb331e6c55037b8eb`. clang14 CHECKED SDK 독립 빌드 완료. **UE에 포함된 fork 또는 ABI와 동일하다는 증거 아님** |

다음 사용자 작업은 [Epic 공식 안내](https://www.unrealengine.com/ue-on-github?lang=en-US)의
Epic 계정 → Apps & Accounts → Accounts → GitHub Connect → 계정 연결/OAuth 승인 →
이메일의 EpicGames 조직 초대 수락이다(초대 유효7일). 계정·약관 절차는 사용자가 진행한다.
완료 후 현재 GitHub 인증 계정으로 private fork 접근을 다시 확인한다. 토큰을 문서/대화에
기록하지 않는다. 별도 소스 빌드 승인을 다시 받을 필요는 없으며 현재 blocker는 계정 접근이다.

CARLA Setup.sh는 UE 제공 clang10/libc++ 경로를 사용한다. 여기서 만든 clang14 SDK를
UE에 그대로 링크하지 않는다. 실제 UE source 확보 후 fork pin·toolchain·의존성·디스크를
재확인하고 그 build 안에서 확장을 검증해야 한다.

## 구현 범위와 실행 경계

[소스](../../../../tests/integration/carla/m7_1j)는 기본 OFF인
`STRATADRIVE_M7_PHYSX_PROBES`로만 빌드한다. 설치된 CARLA 서버·native8-role actor는
이번 시험에서 실행하지 않았다. 입력은 **합성 Actual CAN/P05 fixture**다. 기존1c receiver가
Actual 타입/epoch/source/oldest/expiry/30ms coverage를 검사한 뒤1i 변환을 수행한다.
Command를 actual로 바꾸거나 native 반환 경로를 연결했다고 주장하지 않는다.

- `nodrive_port.hpp`: 검증된 원본 Actual·provenance를 보관하고 한 frame의4wheel effort를
  stage한다. commit ACK는 물리 적용 증명이 아니다. tick에서만 SDK setter→물리 계산→
  원래 signed wheel 관측을 수행하고 persistent setter를 모두 제거한다. 같은 tick 재사용,
  두 번째 wrapper owner, 외부 setter 변경, pause/exception/ambiguous 결과는 거부한다.
- `sdk_scene.hpp`: 공식 snippet의1500kg·radius0.5m 차량/평면을 사용하는 SI fixture.
  up=Y/forward=Z, 원래 SDK wheel order는 RL/RR/FL/FR이므로 프로젝트 순서와 `{2,3,0,1}`로
  바인딩하고 geometry를 확인한다. **CARLA mkz_2020 geometry/좌표의 검증은 아니다**.
- 조향은 geometry readback 기반 Ackermann, motor는 rear 각T/2, friction은 독립 입력이다.
  `100000Pa→각1000Nm` table은 명시적 **합성 시험 데이터**다. 차량 calibration/default로
  승인하지 않는다. 질량·타이어·pressure gain을 음수 제거 목적으로 조정하지 않았다.
- 관측은 원래 Actual 참조·interval·float 적용 effort·signed omega·PhysX sleep을 보존한다.
  setter readback은 새 ActuatorActual이 아니다. contact raycast 여부를 별도로 CSV에 남긴다.
  `interval_work_valid=false`: substep work 계측과 EV energy 연결은 없다.
- 원래1c `FakeProbe` 모드로만 실행한다. wrapper registry는 raw SDK 접근을 완전히 차단하는
  인증 장치가 아니다. CARLA RPC/actor binding·서버 tick owner·외부 writer 배제는 미구현이다.

## 실제 시험 결과와 실패

원본 build/log/XML/CSV를 삭제하거나 성공으로 덮어쓰지 않았다.

| 실행 | 실제 결과 / 후속 |
| --- | --- |
| SDK build01/02 | FAIL. 현대 clang의 float 변환/unused typedef 경고가 upstream `-Werror`에 걸림. 각 [01](build-physx-attempt01.log), [02](build-physx-attempt02.log) 보존 |
| SDK build03 | [FAIL](physx-build-attempt03/result.json). 외부 SDK 경고를 남기고 -Werror 승격만 제외한 뒤 기존 const-reference 반환 오류 확인 |
| SDK build04 | [exit0](physx-build-attempt04/result.json). [한 줄 const 호환 patch](physx-build-attempt04/compatibility.patch) 적용. 물리 식/상수 변경 없음. SDK 경고는 [원본](physx-build-attempt04/build.log)에 남음 |
| port compile01 | [FAIL](build-probe-attempt01.log). namespace와 own-code warning 수정 후 build02 성공 |
| runtime01 | [0/11](tests-normal-attempt01.xml). Foundation/Physics version 상수 혼동으로 초기화 실패. `PX_FOUNDATION_VERSION`으로 수정 |
| runtime02 | [10/11](tests-normal-attempt02.xml). upstream 기본3low/1high에서 출발 직후 rear 음수45/850. [CSV](physics-normal-attempt02.csv) 보존 |
| sanitizer compile01 | [FAIL](build-probe-asan-attempt01.log). upstream SDK의 `-fno-rtti`와 UBSan vptr typeinfo 링크 충돌 |
| 최종 Normal | [15/15](tests-normal-verified.xml), [로그](tests-normal-verified.log), [CSV850행](physics-normal-verified.csv) |
| 최종 ASan/UBSan | [15/15](tests-asan-verified.xml), [로그](tests-asan-verified.log), [CSV850행](physics-asan-verified.csv). leak 검사 활성, UBSan vptr만 이 target에서 제외. **외부 SDK·snippet helper 자체는 미계측** |
| 독립 CSV oracle | [결과](audit.json): 시각/순서/배분/부호/정지/work unavailable 확인. 손상 입력8/8 거부. coarse FAIL을 그대로 분류 |
| 실제 UE/CARLA 포트/정상 주행/에너지 | **NOT RUN**. 독립 SDK 결과를 승계하지 않음 |

15개 시험은 staged-only, single-use/잔존 입력 제거, 중복 writer, 누락·지연·pause,
외부 SDK writer, Command 거부, wheel binding, raw signed reverse, coarse 음수 후 다음 tick
차단, 좌우 조향 궤적, 정지→가속→음수 motor 감속→마찰 정지, 모호한 step/예외를 포함한다.
기존 M7 각87개(1c39/1f14/1g8/1h10/1i16)의 직전 실행 근거는1i에 있으며 이번 새 분모와
합치거나 재실행했다고 표시하지 않는다. M6 전체 regression을 새로 수행한 것도 아니다.

## 수치 적분 조사: epsilon 대신 관측 가능한 비교

[공식 PhysX guide](https://github.com/NVIDIAGameWorks/PhysX-3.4/blob/5e42a5f112351a223c19c17bb331e6c55037b8eb/PhysX_3.4/Documentation/PhysXGuide/_sources/Manual/Vehicles.txt)의
저속 불안정 진단에 따라 `setSubStepCount`만 비교했다. 모든 world tick은10ms이며
low/high count를 같은 값으로 설정했다. **차량 update 내부 적분**이며 CARLA world
`max_substeps` 설정과 동일하지 않다. 원래 ECU20/10ms·Drive30ms 계약은 변경하지 않았다.

| 차량 내부 subdivision | rear 음수/850 | 가속 끝 m/s | 음수 motor 끝 m/s | 최종 z(m) | 엄격 판정 |
| --- | ---: | ---: | ---: | ---: | --- |
| 3 | 45 | 1.551509 | 1.251987 | 5.333652 | FAIL |
| 10 | 0 | 1.551802 | 1.255095 | 5.364815 | PASS (fixture 한정) |
| 20 | 0 | 1.551778 | 1.255083 | 5.369065 | PASS (fixture 한정) |
| 40 | 0 | 1.551729 | 1.255010 | 5.369010 | PASS (fixture 한정) |

[시도 목록](solver-attempts.json)과 `solver-{3,10,20,40}.{log,xml,csv}`가 근거다.
3의 첫 음수는frame101, 최소−1.44869256rad/s였다. 전850tick의 실패 trace는 진단 목적으로
계속 수집한 것이며 native 센서/정상 주행에 전달하지 않았다. 별도의 fault test는 첫 음수에서
기존1h validity로 unavailable 처리·pause하며 **다음 physics tick이 없음을** 검사했다.

20과40의 최종 이동 차이는약0.00005484m다. 이는 한 조건의 해상도 비교이며 전체 ODD의
수렴/정확도 tolerance를 확정한 것이 아니다. 독립 probe의 명시적 시험 설정으로20을 사용한다.
기본 환경변수 미설정 시 upstream3/1이 유지되어 nominal test는 실패할 수 있다.
CTest에는20을 명시했다([discovery](ctest-discovery.json)). 센서 부호를 바꾸거나0으로 clamp하지 않았다.

nominal 단계는1–100 보호 제동,101–500 합산+300Nm,501–650 합산−150Nm,
651–850 마찰 제동이다. rear wheel은1–100 및750–850에서 정확히0, 끝 body speed0이었다.
접지 중 body가 완전히 고정된다는 주장이나 stop deadline 수용은 아니다. 음수 motor에 의한
감속은 확인했지만 **배터리 회생/구간 일 검증은 없다**. stock CARLA의 기존 평지 FAIL 원인이
이 실험으로 규명되거나 해결된 것도 아니다.

## 재현과 다음 작업

공개 SDK를 위 commit으로 checkout한 뒤(실행 package와 별도 경로):

```bash
python3 tests/integration/carla/m7_1j/build_physx.py \
  --source /d/shin/stratadrive-tools/m7-source/physx-3.4 \
  --output /tmp/m7-physx-new-attempt
cmake -S . -B build/m7-physx -DBUILD_TESTING=ON \
  -DSTRATADRIVE_M7_PHYSX_PROBES=ON \
  -DSTRATADRIVE_M7_PHYSX_SOURCE=/d/shin/stratadrive-tools/m7-source/physx-3.4
cmake --build build/m7-physx --target m7_nodrive_test -j 4
M7_NODRIVE_SUBSTEPS=20 M7_NODRIVE_TRACE=/tmp/m7-nodrive-new.csv \
  build/m7-physx/tests/integration/carla/m7_1j/m7_nodrive_test
python3 tests/integration/carla/m7_1j/audit.py docs/test-plan/evidence/m7_carla_1j
```

ASan build는 별도 directory와 `-DSTRATADRIVE_SANITIZERS=ON`, 실행 시
`ASAN_OPTIONS=detect_leaks=1:halt_on_error=1`, `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`.
원본 evidence에 다시 출력하지 않는다. SDK build04 당시 script 사본을 보존했고 현재 script는
staged 변경까지 검사하도록 `git diff HEAD`를 사용한다. source/library/binary hash는
[manifest](manifest.json), 실행 분모는 [test-attempts](test-attempts.json), 모든 evidence hash는
[SHA256SUMS](SHA256SUMS)에 둔다.

1. 사용자 Epic–GitHub 연결/초대 수락 후 private UE4.26 fork 접근·commit·build prerequisite 확인.
2. UE/CARLA를 별도 위치에 빌드하고 기본 서버/client smoke부터 확인. 이 SDK binary를 이식하지 않음.
3. 실제 UE vehicle scene 안에 NoDrive lifecycle·wheel binding·frame 단일 owner/RPC 구현,
   stock drivetrain 동시 실행 배제. 시험 없는 RPC 구현을 완료 처리하지 않음.
4. mkz geometry와 근거 있는 brake 모델/calibration을 고정한 뒤 native Actual 보호 제동→
   출발→정지·누락·pause/reset을 실제 CARLA에서 검증. raw 음수는 계속 unavailable/latch.
5. solver 구간 motor/friction work·receipt·단일 EV owner 원자적 연결은 별도 구현/시험.

정상 CARLA 주행 착수 gate는 여전히 닫혀 있다. M6 코드·통신·freshness·수용 수치는 유지한다.
