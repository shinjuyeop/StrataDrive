# CARLA 계약·환경 조사·검토 이력

이 문서는 당시 결정과 검토를 보존한 기록이다. 현재 상태는 [프로젝트 상태](../project-status.md), 현재 계약은 [문서 안내](../README.md)를 따른다. 과거의 “다음 작업/미구현”은 현재 지시가 아니다.

- [M7-0 환경 조사와 M7-1 CARLA 최소 실행 계획](#preflight)
- [CARLA Plant Adapter / Vehicle Plant Interface 초안](#icd)
- [M7 통합 검증 및 종료 검토](#m7-review)

<a id="preflight"></a>

## M7-0 환경 조사와 M7-1 CARLA 최소 실행 계획

조사일 **2026-10-23 (Asia/Seoul)**, 저장소 기준 `765ed8f`, 작업 전 tracked 변경 없음.
**M7-0 조사·설계 문서 작성 완료, CARLA runtime NOT RUN**.
[M6 종료 판정](milestone-reviews.md#m6)·기존 검증 수치/통신/안전 계약은 유지한다.
CARLA package/client/ScenarioRunner 다운로드·설치·빌드·서버 실행은 하지 않았다.
온라인 문서/릴리스 metadata 조회와 Host read-only 점검만 수행했다.

<a id="preflight-2026-10-23-후속--m7-1a-실행"></a>

### 2026-10-23 후속 — M7-1a 실행

사용자의 다운로드·설치 허용으로 공식0.9.16 package/별도 Python3.10 환경을 준비하고
[실행 원본·실패/재현](../test-plan/evidence/m7_carla_1a/README.md)을 기록했다. 양쪽 버전0.9.16·world 연결,
비주행 ego 정상/예외 생성·종료·잔존0·설정 복원을 최종 시도에서 확인했다. 원본6시도1PASS/5FAIL
(서버 미실행 negative1, world timeout2, 관측기 cache 오판2)을 모두 보존했다.
**M7-1-01 PASS, M7-1-02 ego 부분 PASS; 센서 포함02 전체와03~09 NOT RUN**이다.
아래의 M7-0 미설치/NOT RUN 문구·Host 표는 당시 조사 기록이다. 현재 실행 상태는 이 후속과
연결한 evidence를 따른다. 정상 주행·source build·M6 변경은 수행하지 않았다.

<a id="preflight-2026-10-23-후속--m7-1b-실행"></a>

### 2026-10-23 후속 — M7-1b 실행

[실행/실패/재현](../test-plan/evidence/m7_carla_1b/README.md):50ms 단일 tick owner의240tick과
RGB/GT/state main 각200/200, raw frame/time·format/pose·GT 분리, 정상/예외 센서 cleanup을
확인했다. 초기 camera1frame 누락은 startup 분모에 보존했다. 실제 drop·카메라 delay/reorder/
duplicate, 실제 pause/reset·새 epoch 및 metadata replay를 검사했다.
**02~04는 해당 비주행 profile PASS,05/06은 부분 PASS**,07~09는 NOT RUN이다.
전체4시도1PASS/3FAIL·native incomplete와 server crash를 보존했다. 같은 sensor-session
client reload의 native crash는 두 wheel에서 재현됐고, 최종 한정 경로는 client retire→
fresh client→reload다. 초기1a와 다른 최종 client artifact는 서버 포함 wheel의 별도 venv로
고정했다. live overflow/10s 초과 delay·ECU timeout/old Actual은 미검증이다. 다음은 M7-1c다.

<a id="preflight-2026-10-23-후속--m7-1c-논리-실행"></a>

### 2026-10-23 후속 — M7-1c 논리 실행

[test-only Actual/fake backend·원래 Drive 검증](../test-plan/evidence/m7_carla_1c/README.md)을 완료했다.
Normal/ASan 각39/39, 관련 기존120/120 PASS. compile 경고로 실패한 첫 build와 중간 cohort는
보존했다. **07/08은 명시된 논리 범위 PASS,09는 fake/CLI 부분 PASS**이며 실제 CARLA
actuation/외부 writer·peer 인증/권한 전송·RPC 오류는 NOT RUN이다.
원래 source0/10/20/30ms 수용,30ms+1ns 거부,40ms Drive 보호 선택·fresh 입력 후 latch 유지로
50ms state/30ms conflict를 확인했다. 실제 수신 시각 restamp나 요구 완화는 하지 않았다.
후속은 인과적 substep 관측·ECU exchange·actuation/clock 설계 타당성 검토다.

<a id="preflight-2026-10-23-후속--m7-1d-시간-계약-개정실행"></a>

### 2026-10-23 후속 — M7-1d 시간 계약 개정·실행

사용자가 world/state10ms·영상50ms 방향의 다음 작업을 승인했다. [ICD](../interfaces/carla-plant-adapter.md)
및 [시간 계약](../requirements/timing-requirements.md)을 개정하고 [실행 근거](../test-plan/evidence/m7_carla_1d/README.md)를 남겼다.
M7-0/1b의50ms world 조건은 과거 baseline으로 보존하며 현재 M7 world는10ms다.
Controller20ms·Zone/vECU10ms·Drive30ms·native guard/기존 M6 수용은 유지한다.

비주행 main state600/600·RGB/GT 각120/120과 누락·pause/reset을 확인했다.
첫 camera 간격60ms, 최초 oracle FAIL·startup 위상 수정·확인 실행을 구분해 기록했다.
논리 sampling 충돌은 해소했지만 wall100Hz는 충족하지 못했다. 실제 ECU30ms freshness는 NOT RUN이다.
최종 actor0·설정 복원 뒤 서버 SIGTERM 중SIGSEGV/139는 **OPEN-M7-1D-01**로 남겼다.
다음은 wheel telemetry·clock mapping·wall timing 비용/native guard·종료 crash의 제한된 조사다.
아래 M7-0/1b 시험표의50ms 조건/분모는 역사적 조건이며 새 실행 수치로 덮어쓰지 않는다.

<a id="preflight-2026-10-23-후속--m7-1e-진단대안"></a>

### 2026-10-23 후속 — M7-1e 진단·대안

[진단 근거](../test-plan/evidence/m7_carla_1e/README.md): physics-on wheel 회전각 RPC 확인, 정적4조건×2회
render/camera/audit 비용 분리, platform/Host clock bracket 검사, 새3서버 종료 재현을 수행했다.
metadata 수집만으로 RTF1.014~1.033이나 실제 Drive source-age는 NOT RUN이다.
고정 offset mapping은 전체 관측에 맞지 않았고, 빈 서버TERM/INT도139로 종료했다.
다음은 별도 functional clock·8-role barrier 설계와 wheel 구간 각속도 의미 검증 계획이다.
새 source build/정상 주행 연결·기존 M6 계약 변경은 하지 않았다.

<a id="preflight-2026-10-23-후속--m7-1f-functional-clockshadow"></a>

### 2026-10-23 후속 — M7-1f functional clock/shadow

[functional clock/shadow 실행](../test-plan/evidence/m7_carla_1f/README.md)을 추가했다. 별도 opt-in C++
harness가 실제8-role native actor의 세션·RunLease·arm·Actual 경로를 stationary SIL fixture로
실행하고, Python 단일 tick owner는 각 snapshot의 원래 elapsed time을 전달한 뒤8역할 처리
barrier를 기다린다. Normal/ASan 각14/14, 관련 기존144/144와1c39/39를 확인했다.
CARLA는 physics-off ego/RGB/GT 비주행이며 vehicle/wheel을 ECU 입력으로 전달하지 않는다.
100ms 지연·250ms pause의 논리 기능 검증은 wall freshness·native deadline 검증이 아니다.
새 run의 INIT와 old scope 거부는 native 시험, 이번 live world reload/reset은 NOT RUN이다.
다음 작은 작업은 [ICD의 wheel 계획](#icd-m7-1g-wheel-검증-계획)이다.

<a id="preflight-2026-10-23-후속--m7-1g-실제-wheelnative-연결"></a>

### 2026-10-23 후속 — M7-1g 실제 wheel/native 연결

[실행/실패 근거](../test-plan/evidence/m7_carla_1g/README.md):0.9.16의 직접 PhysX omega를 발견해
pitch 차분 대신 사용했다. physics-on 무동력 내리막400tick에서 실제 wheel→Drive vECU→
DriveActual CAN/P05→Rear→Central 반환396개, armed fixture322frame, 최대 source age10ms를 확인했다.
첫 native 연결은 fractional timestamp에서 pending sample을 덮어쓰는 버그로 실패했고 수정했다.
평지 native 연결은 미세 음수 wheel 때문에 여전히 FAIL이다. 임의 clamp/abs/요구 완화는 없다.
Normal/ASan 각22/22(1f14+1g8), 기존 관련144/144와1c39/39, raw oracle 변조7/7 거부.
6live 시도 중3개 수집 완료/3개 실패이며 모두 서버 종료139. M6 수용·과거 원본은 유지한다.
정상 제어 주행·actuation·energy fidelity는 미완료다. 다음은 정지 잡음의 sensor 의미,
actuator/전기 port 분리와 rad/Nm/Pa actuation 방식 결정이다. source build는 하지 않았다.

<a id="preflight-2026-10-23-후속--m7-1h-actuatorelectrical-분리"></a>

### 2026-10-23 후속 — M7-1h actuator/electrical 분리

[구현·실행·실패](../test-plan/evidence/m7_carla_1h/README.md): 별도 opt-in M7 owner가 actuator 응답과
EvPowerModel을 소유하며 실제 wheel 취득 이력에서 각1ms 구간 begin 이전 sample을 선택한다.
차량 운동은 적분하지 않는다. 계산 결과는 CARLA에 적용하지 않은 ZOH 모델 예측으로 표시한다.
Normal/ASan 각32/32(기존22+신규10), 기존 관련144/144·1c39/39와 실제 내리막400tick을 확인했다.
평지의 미세 음수는 SubResolutionNegative 진단 후 거부한다. 0.01rad/s wire resolution을
noise 보정 허용으로 해석하지 않았다. 평지 연결 FAIL·서버 종료139·정상 actuation 미연결은 유지한다.
다음은 actuation 방식·중복 dynamics·정지 sensor 오차 근거, applied Actual/interval work 계약이다.

<a id="preflight-2026-10-23-후속--m7-1i-actuation-방식-검토"></a>

### 2026-10-23 후속 — M7-1i actuation 방식 검토

[조사·오프라인 구현/검증](../test-plan/evidence/m7_carla_1i/README.md): 기본 throttle 역변환은 미채택하고,
PhysX NoDrive의4wheel effort를 노출하는 서버 확장안을 우선 후보로 결정했다. 설치0.9.16 binding과
공식 소스를 대조했으며 exact upstream commit/해시를 남겼다. 새 CARLA 실행·source build는 없다.
직접 rad/Nm/Pa mapping의 수학/Actual 경계 prototype Normal·ASan 각16/16, 기존 M7 각71/71.
처음 ASan1c binary 미빌드로 회귀 실행이 중단된 기록과 빌드 후 결과를 구분한다.
Brake pressure table 수치는 미확정이고 음수 측정 보정도 미채택이다. 과거 평지 무제어 접지
실패를 정상 brake-hold의 센서 오차로 해석하지 않는다. 다음은 별도 source build 범위 결정 →
직접 effort 포트·calibration artifact → 실제 보호 brake 적용/원래 wheel 검증이다.
frame receipt/interval work·서버139·wall 수용은 OPEN으로 유지한다.

<a id="preflight-2026-10-23-후속--m7-1j-source-build독립-sdk-포트"></a>

### 2026-10-23 후속 — M7-1j source build/독립 SDK 포트

[실제 빌드·실행·실패](../test-plan/evidence/m7_carla_1j/README.md): source build 범위로 후속 착수했다.
공개 CARLA0.9.16 source 확보, 공개 PhysX3.4 CHECKED SDK 빌드·합성 Actual→NoDrive 포트
Normal/ASan 각15/15를 확인했다. 외부 SDK 자체는 sanitizer 미계측이며 vptr 검사는 제외다.
기본 적분 음수45/850 FAIL을 보존했고 world10ms 안의 차량 적분20분할 후보에서는0/850이다.
시각/배분/정지/invalid work 독립 CSV oracle와 손상8/8 거부를 확인했다. CARLA 차량 calibration은 아니다.

UE fork 접근은 Git/GitHub CLI404이며 사용자가 Epic–GitHub 연결을 설정한 적 없다고 응답했다.
공식 CARLA build 명령은 UE4_ROOT 누락으로 실패했고 UE compilation은 시작되지 않았다.
계정 연결·EpicGames 초대 수락 후 UE toolchain/fork pin → CARLA 서버 포트 → 실제 brake
calibration/보호 제동·wheel → 구간 work 순서로 계속한다. 기존 package/venv·M6는 유지한다.
원래 M7-0/1a–1i의 source build 제외 기록은 당시 범위이며1j부터 변경됐다.

<a id="preflight-2026-10-23-후속--ue4262-빌드-완료"></a>

### 2026-10-23 후속 — UE4.26.2 빌드 완료

[빌드 근거](../test-plan/evidence/m7_carla_1j_ue_build/README.md): Epic 연결 후 fork 접근 성공,
`carla` branch commit e9d9e60c85f643e10eeb03f42f61554d18dcb30f 고정.
Setup/프로젝트 파일 생성 exit0, 중단했던 make를 재개하여 전체 exit0을 확인했다.
UE4Editor 및 도구 생성, ldd missing0이며 engine tracked source 변경 없음.
editor runtime/CARLA build·정상 actuation은 NOT RUN이다. 다음은 g++-12 등 CARLA 빌드
의존성·별도 Client 환경·버전에 맞는 asset 준비와 기본 서버/client build다.
이전 fork404·UE4_ROOT 누락·중단 기록은 당시 근거로 보존한다.

<a id="preflight-2026-10-23-후속--carla-client서버-모듈-빌드"></a>

### 2026-10-23 후속 — CARLA Client/서버 모듈 빌드

[의존성·실제 build 근거](../test-plan/evidence/m7_carla_1j_carla_build/README.md): g++-12 등 시스템
패키지 설치 확인 후 별도 Python3.10 venv에서 Client wheel과 서버 모듈을 빌드했다.
Client01 URL404/02 PROJ include/03 PROJ C PIC 실패를 보존하고 최소 build patch 후
Client04 exit0/import 성공, server01 exit0/ldd missing0을 확인했다. SimReady는 제외했다.
0.9.16 content ID는20250912_2171890이다. source Client identity는294096e-dirty이며
서버 handshake/ego/runtime·NoDrive 직접 포트는 NOT RUN이다. 다음은 source 서버 smoke다.

<a id="preflight-2026-10-26-후속--source-서버-실행"></a>

### 2026-10-26 후속 — source 서버 실행

[실행·실패·범위](../test-plan/evidence/m7_carla_1j_source_smoke/README.md): Town10HD_Opt는 최초
1800s 준비 한도를 넘겼고 추가 관찰 뒤 SIGINT에 응답하지 않아 강제 정리했다. 반복 준비
조회가 backlog를 누적시킨 관측도 보존하고, 이후 LoadMap 완료 후 조회하는 방식으로 바꿨다.
Town03_Opt 렌더링 시작에서는 distance field/GPUScene 경로 SIGSEGV를 관측했다.
시작 DisableRendering INI로 재실행하고 초기 INI/Episode 읽기값을 혼동한 harness 실패를
수정한 뒤, 비렌더링 identity/ego 정상·예외2/2 및10ms 본 관측102샘플을 검증했다.
Episode 설정 복원 후 SIGINT130과 포트/소유 프로세스 정리를 확인했다. exit0 수용이 아니다.
raw timestamp와 실패를 보존했으며 비렌더링 결과를 RGB/GT·렌더링 crash 해결로 확대하지 않는다.
기존 M6/age30ms·native guard는 유지하고 해당 wall 수용 시험은 수행하지 않았다.
후속 [렌더링 조사](../test-plan/evidence/m7_carla_1j_render_diagnosis/README.md)에서는 같은 바이너리의
camera 경로 SIGSEGV와 유효하지 않은 Distance Field 내부 참조를 GDB로 관측했다.
다음 GDB1회·native 같은 서버2회는 각각150tick/RGB·GT30쌍 수신·정리/설정 복원에 성공했다.
간헐 재현이며 원인은 미확정이다. shader 준비 중 체크무늬 재질·첫60ms 영상 간격도 보존한다.
완전 센서 delivery/렌더러 안정성·정상 actuation 수용은 아니다. engine patch는 적용하지 않았다.
다음은 실패 시 자원 수명 추적과 asset 준비 완료 조건의 새 native 서버 반복 검증이다.

[후속 준비/반복 검증](../test-plan/evidence/m7_carla_1j_render_followup/README.md): 넓은 proxy 추적은
world20s timeout으로 FAIL했고, 줄인 추적의 ego/camera는 한정 통과했다. DDC01은 exit0에도
대상 맵0개로 FAIL, 파일 경로를 고친 DDC02는10개 대상을 인식했으나 광범위 cooked 데이터
생성으로 확대돼 SIGINT 후 수동 강제 중단했다. 모두 보존하고 실제 장면 준비 관측으로 전환했다.
ego/RGB/GT 유지23,620tick·1169.091s에서 shader/Distance Field zero를10s 간격2회 확인했다.
준비 후 GDB1회·서로 다른 새 native2서버 각150tick/30쌍·정리/복원·SIGINT130을 확인했다.
샘플 RGB의 대체 체크무늬가 벽면 재질로 바뀐 것을 확인했지만 전체 content 적합성은 OPEN이다.
첫60ms 영상 간격·원래 timestamp를 보존했다. root cause 미확정이며 engine/M6 변경은 없다.
다음 작은 작업은 이 제한된 baseline의 NoDrive single-writer/frame stage·receipt 최소 서버 포트다.

<a id="preflight-실제-host-관측"></a>

### 실제 Host 관측

아래는 공식 권장값이 아니라 이 작업 terminal에서 얻은 snapshot이다. 메모리/공간은 변동한다.
`systemd-detect-virt`는 `none`을 반환했다. Target/원격 서버 사양을 추정한 것이 아니다.

| 항목 | 관측값 | 확인 방법 / 한계 |
| --- | --- | --- |
| OS/kernel | Ubuntu22.04.5 LTS x86_64,6.8.0-138-generic PREEMPT_DYNAMIC | `/etc/os-release`, `uname -a` |
| CPU | Intel Core i7-11700 @2.50GHz,8core/16thread, max4.9GHz | `lscpu`; CARLA 부하/실시간 성능 미측정 |
| GPU/VRAM | NVIDIA GeForce RTX3090,24576MiB, free24110MiB | `nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv` |
| NVIDIA driver | 580.178.04 | GPU 조회 성공; Vulkan/UE 렌더링 미검증, `vulkaninfo` 명령 경로 없음 |
| Python/ABI/pip | Python3.10.12, glibc2.35, pip22.0.2 | `python3 --version`, `getconf GNU_LIBC_VERSION`, `python3 -m pip --version` |
| RAM/swap | 총31GiB(약32GB), 가용24GiB / swap975MiB | `free -h`; benchmark 아님 |
| 저장소 | `/d` ext4 총916G/가용305G; `/` ext4 총220G/가용72G | `df -hT . /tmp`; 서버·dataset 위치는 `/d` 후보, I/O 성능 미측정 |
| NIC | enp0s31f6 UP,1000Mb/s full duplex, default IPv4 route 존재 | `ip -brief address`, `ip route`, sysfs speed/duplex; 실제 처리량/지터 아님 |
| 외부 네트워크 | carla.org/github.com/pypi.org DNS 및 HTTPS200 | Python socket/urllib로 endpoint 조회. 대형 asset/CDN 다운로드 경로 미검증 |
| 로컬 port | TCP2000/2001/2002 listening 없음 | `ss -ltn '( sport = :2000 or sport = :2001 or sport = :2002 )'`; 향후 bind·방화벽/원격 연결 성공 보장 아님 |
| CARLA Python 모듈 | 현재 Python의 `find_spec('carla') is None` | 다른 env/디스크 전체에 CARLA가 없다는 뜻은 아님 |

네트워크 주소 자체는 실행 manifest에 필요할 때 기록한다. M7-1은 같은 Host의 loopback
server/client를 우선 사용한다. 기존 SOME/IP netns/veth는 변경하지 않는다. 실제 Jetson NIC,
Host–Target latency/clock sync·방화벽은 NOT RUN이다. 일반 HTTPS 성공과 CARLA RPC 성공은 별개다.
Host에서 ReadTheDocs 직접 urllib 조회는403이었으며 공식 문서 내용은 web 조회로 확인했다.

<a id="preflight-공식-근거와-호환성-판단"></a>

### 공식 근거와 호환성 판단

아래 링크는 조사일 열람했다. 공식 문서의 권장값과 실제 실행 성공을 구분한다.

| 근거 | 확인한 사실 | 이 프로젝트 판단 |
| --- | --- | --- |
| [0.9.16 공식 release](https://github.com/carla-simulator/carla/releases/tag/0.9.16), [발표](https://carla.org/2025/09/16/release-0.9.16/) | Ubuntu용 `CARLA_0.9.16.tar.gz` 및 별도 AdditionalMaps 제공 | **0.9.16 패키지 우선 후보 유지**, nightly/source build 미채택. 다운로드 checksum·실제 server version은 M7-1 |
| [0.9.16 quickstart](https://carla.readthedocs.io/en/0.9.16/start_quickstart/) | Ubuntu20.04/22.04, RTX2070급 이상·VRAM8GB 이상 권장, 약20GB 공간, TCP2000/2001, pip>=20.3 | OS/GPU/공간/Python 도구의 사전 조건 부합. 이 페이지의 latest0.9.15 문구는 오래된 부분이므로 exact release는 위 tag로 판단 |
| [공식 client PyPI carla0.9.16](https://pypi.org/project/carla/0.9.16/) | Linux cp310/cp311/cp312 manylinux_2_31_x86_64 wheel 존재 | Host3.10/glibc2.35에 맞는 `carla-0.9.16-cp310-cp310-manylinux_2_31_x86_64.whl` 후보. ABI 적합성 판단이며 import/RPC NOT RUN |
| [ScenarioRunner v0.9.16 README](https://github.com/carla-simulator/scenario_runner/blob/v0.9.16/README.md), [requirements](https://github.com/carla-simulator/scenario_runner/blob/v0.9.16/requirements.txt) | CARLA0.9.16 대응 명시; py-trees0.8.3, numpy1.24.4, networkx3.4.2 등 dependency 지정 | 같은 tag를 pin하고 Python3.10 별도 venv 후보. dependency 해결/import/scenario 실행은 NOT RUN; master 혼용 금지 |
| [UE5 quickstart](https://carla-ue5.readthedocs.io/en/latest/start_quickstart/) | Ubuntu>=22.04, RTX3000급/VRAM>=16GB 권장, Linux driver>=550, 공간130GB | RTX3090/driver는 제시 조건에 부합, `/d` 여유는 충분하나 `/`72G는130GB 미달. 실행 성능 미확인 |
| [0.10.0 UE5.5 release](https://carla.org/2024/12/19/release-0.10.0/) | Lumen/Nanite·camera fidelity 개선. 해당 release 당시 map/weather/API·cosimulation 제약 명시 | 영상 학습 fidelity는 미래 이점. 이번 RGB/GT/state·계약 검증의 필수 이점은 아님. 0.10.x 전체가 같은 제약이라고 단정하지 않음 |

선정안은 **Ubuntu22.04.5 / CARLA server0.9.16 / Client0.9.16 CPython3.10 /
ScenarioRunner v0.9.16(후속 연동)**이다. 패키지 포함 wheel 또는 공식 PyPI의 exact wheel 중
실제 artifact를 hash로 고정하고 import 경로 중복을 차단한다. quickstart의 넓은 Python
지원 표보다 실제 wheel tag를 우선한다. 제3자 유사 이름 패키지는 후보가 아니다.
0.9.16 quickstart에 수치로 명시되지 않은 CPU/RAM/NVIDIA 최소 driver를 임의로 만들지 않는다.
현재 Host의 충분한 자원은 실행 가능성 근거이며20Hz 보장이나 M6 quiet 부하 수용 확대가 아니다.

**UE5 전환은 보류**한다. 공식0.10.0의 시각적 개선은 유용하지만 이번 목적의 runtime 경계,
30ms freshness, Nm/Pa mapping을 자동으로 해결하지 않는다. UE5 exact build/client/
ScenarioRunner 호환은 별도 미검증이다. AI 영상 품질 평가가 필요해질 때 해당0.10.x tag,
map/weather 기능·GPU 부하·ScenarioRunner 지원을 다시 비교한다(TBD-07/09).

<a id="preflight-m7-0-당시-코드-대조와-설계-결과"></a>

### M7-0 당시 코드 대조와 설계 결과

[Plant Adapter ICD](../interfaces/carla-plant-adapter.md)가 의미 계약의 기준이다. 아래 실제 구현을
대조했으며 문서의 설계 위치를 이미 구현된 CARLA 모듈로 오인하지 않는다.

| 구현/계약 근거 | 조사 결과 |
| --- | --- |
| [PhysicalOwner](../../simulation/runtime/m4_owner_network.cpp), [VehicleEvModel](../../simulation/vehicle/vehicle_ev_model.cpp) | 실제 actuator·vehicle/EV가 함께 step된다. CARLA motion과 병행하면 중복되므로 후속 backend 분리가 필요 |
| [SimpleVehicleConfig](../../simulation/vehicle/simple_vehicle.hpp) | mass/geometry/pressure 계수는 M6 fixture. age30ms/skew10ms/max step20ms도50ms CARLA와 직접 치환 불가 |
| [DriveController](../../vecu/drive/drive_controller.cpp), [DriveReceiver](../../interfaces/drive/drive_receiver.cpp) | wheel source/oldest dependency30ms 검사. 20Hz state의40ms task에서 stale 발생; 재발행/EV70ms option으로 해소 불가 |
| [AsyncCoordinatorPort](../../central/coordinator/async_coordinator_port.cpp), [owner-wire](../interfaces/owner-wire-v1.md), [ADR-0062](design-decisions.md#adr-0062) | 원래 source/expiry·20ms 전달 envelope·8참여자 경계 보존 필요 |
| [P05](../../interfaces/common/e2e_profile5.cpp), [ADR-0036](design-decisions.md#adr-0036) | CRC/counter와 Actual acquisition 의미 보존. 새 bridge의 도착 시각으로 재인코딩 금지 |
| [ADR-0063](design-decisions.md#adr-0063), [ADR-0064](design-decisions.md#adr-0064) | 독립 Python MIL과 M6 차량/전기 구간 work의 수용 경계를 CARLA로 승계할 수 없음 |

M7-0 당시 결정한 것은 actual-only/single writer,50ms tick owner,20/10ms 기존 주기, GT 격리,
원천 identity/time/validity와 pause/reset 의미다. calibration·true substep 양방향 연동·clock
mapping·energy fidelity는 OPEN이다. **기본 패키지50ms world state로 정상 Drive 연결 불가**라는
판정을 숨기지 않으며 M7-1은 비주행 connectivity/sensor/거부 검증부터 진행한다.

<a id="preflight-m7-1-시험-준비와-공통-증거"></a>

### M7-1 시험 준비와 공통 증거

아래 시험표는 M7-0 당시 **PLANNED / NOT RUN** 계획이다. 현재 M7-1a/b/c/d 부분 실행은 위 후속을 따른다. 이번 Host 정보 조회를 CARLA 시험 PASS로 세지 않는다.
M7-1 실행 단계에서만 package/client를 준비하고 source build/ScenarioRunner 자동 실행은 하지 않는다.
단일 ego, traffic0, clear daytime, front RGB+동일 pose GT, state20Hz를 초기 scope로 한다.
실행 전 사용 가능한 map/vehicle blueprint/spawn point를 조회해 exact ID·pose·seed·physics
readback을 manifest에 고정한다. 경로/차종 calibration 수용은 별도다.

최소 수집 profile 제안은 camera800×600/FOV90°/sensor_tick0.05, render enabled
(off-screen 가능, no-rendering 금지), synchronous0.05s, substep0.01s/max10이다.
이는 M7-1 smoke workload이며 M10 Reference AI 해상도 확정이 아니다. 카메라 extrinsic은
차종 선정 후 수치/단위·시야를 검토해 첫 실행 전에 manifest에 고정한다.
초기 join queue는 sensor당64frame, RPC/누락 관측 wall timeout10s 후보로 고정한다.
이10s는 시험 harness hang 종료용이며 Drive30ms/critical loss100ms의 대체값이 아니다.

정상 수집은 startup20tick, 본 관측200tick(10 logical s), drain20tick을 **따로** 집계한다.
world frame은 startup/drain에도 기록하며 camera별 expected/received/late/missing/duplicate/
overflow를 모두 남긴다. 늦게 온 frame은 원래 capture key로 join하고 timeout 후 누락을 성공으로
덮지 않는다. 본 관측 RGB/GT/state200세트의 누락0이 수집 case 기준이며 초기 실패도 보존한다.
clock/버전/manifest·raw trace·oracle 결과·시도별 실패를 향후 `evidence/`에 저장한다.
10ms/20ms schedule 논리 시험과 실제 runtime wall 검증은 서로 다른 결과로 보고한다.

<a id="preflight-m7-1-시험표"></a>

### M7-1 시험표

| ID / 현재 상태 | 절차 | 판정과 남길 증거 |
| --- | --- | --- |
| M7-1-01 / PASS (M7-1a) | 별도 env의 client로 localhost server 연결, `get_client_version/get_server_version`, import 경로·package hash 기록 | 둘 다0.9.16, RPC 정상. 불일치는 fail/중단; wheel tag만으로 PASS 금지 |
| M7-1-02 / PASS (비주행 정상/예외 fixture) | INIT/NON_DRIVING에서 ego·RGB·GT 생성, parent/actor 목록 확인, 정상/예외 종료 | 자기 actor만 destroy, sensor callback 종료·queue 폐기, actor 잔존0. 기존 world settings 복원 결과 기록 |
| M7-1-03 / PASS (240tick profile) | 설정 readback 후 단일 owner로240tick, tick request/return/snapshot frame·elapsed/delta·Host monotonic 기록 | 연속 frame+1, delta0.05s(수치 tolerance1µs), timestamp 단조. 중복 tick/설정 변경 거부. wall duration·RTF 보고, wall20Hz PASS로 확대 금지 |
| M7-1-04 / PASS (정적 smoke 수집) | RGB/GT/state join, BGRA 길이·class ID·intrinsic/extrinsic·frame/time 검사 | 본 관측200세트 완전, pose/frame 일치. raw GT red-channel label과 palette 구분, GT 온라인 구독0. 위치/축 변환 왕복·좌우 부호 vector 검사 |
| M7-1-05 / 부분 PASS; live overflow/deadline NOT RUN | 각각 RGB/GT/state callback drop·delay/reorder/duplicate·queue overflow를 명시 주입 | 의도한 missing/late reason과 exact frame 기록, cached restamp0. 필수 온라인 관측 누락은 driving gate 닫힘; GT 누락은 dataset invalid, 값0 채움 금지 |
| M7-1-06 / 부분 PASS; ECU timeout/old Actual NOT RUN | tick pause 후 resume, world reload/reset, old callback/old Actual 늦게 전달 | pause 중 sim time 정지·wall 증가. attached monitor는 기존 timeout/latch 유지. 새 run/epoch와 INIT 전 normal 금지, old frame/actor/Actual 거부, ECU rejoin만으로 world reset 금지 |
| M7-1-07 / 논리 PASS; 실제 전송/writer NOT RUN | Actual admission harness에 유효 Actual positive vector와 command 타입/출처 위조·stale·old epoch·NaN·부분 bundle·변조 cached Actual 주입, 두 번째 writer/tick 요청 시도 | fake backend에서 유효 vector당 commit1회·중복0, raw command→apply0, 원래 metadata 불변, reject 이유·apply audit·writer owner 기록. API spy/fixture 검증은 실제 Central→Zone→vECU 연결 PASS와 구분 |
| M7-1-08 / native logical PASS | logical0/10/20/30/40/50ms에 원래0ms wheel sample을 기존 Drive 검증기로 평가, CARLA frame period와 비교 | 40ms에서 stale이며30ms 초과 거부가 기대 결과. 보호/차단 확인은 negative case 성공일 뿐 정상 주행 가능 판정 아님. future50ms sample 소급 금지 |
| M7-1-09 / fake/CLI 부분 PASS | mock backend에서 interval coverage·미확정 calibration·apply RPC ambiguous·중간 expiry 검사, live 수집 모드에서 정상 driving 요청 차단 확인 | 근거 없는 normalized apply0, 추가 driving tick0, 최초 failure 유지. 실제 moving ego mapping/EV·응답 시험은 후속 gate BLOCKED |

M7-1-02/03/04의 sensor-only world 진행은 ECU 주행 허가를 발급하지 않는 별도
NON_DRIVING 시험이다. 필요하면 INIT에서 ego physics 비활성화한 정적 fixture임을 명시한다.
이를 실제 actuator feedback이나 정상 closed-loop로 보고하지 않는다. 동적 ego actuation의
positive case는 실제 vECU Actual 경로와 calibration/시간 gate가 준비된 후만 실행한다.
pause 중 실제 기존 monitor를 연결하지 않았다면 timeout 항목은 NOT RUN으로 남긴다.
single writer의 unit spy 결과만으로 외부 client 차단이나 전체 실제 경로를 PASS로 쓰지 않는다.

<a id="preflight-다음-작업-단위와-착수-판정"></a>

### 다음 작업 단위와 착수 판정

1. **M7-1a 환경 재현:** 정확한 package/wheel hash·별도 env·GPU renderer 확인, 연결/버전,
   actor lifecycle. 예상 산출물은 manifest와 M7-1-01/02 증거다.
2. **M7-1b 수집 전용 harness:** tick owner·RGB/GT/state queue·timestamp/GT 분리·cleanup,
   M7-1-03~06. M6 runtime과 주행 연결하지 않는다.
3. **M7-1c 경계 시험:** simulator 독립 typed Actual/metadata validator와 fake backend,
   기존 Drive 검증을 이용한 negative case, M7-1-07~09. 새 wire/기존 threshold 변경 없음.
4. **M7-1d 주기 분리:** world/state10ms·영상50ms 비주행 cadence/누락·pause/reset 검증 완료.
   다음은 wheel 원천·clock mapping·wall timing 비용·native guard·Actual interval 적합성 검토다.
   기존50ms world 내부 substep 양방향 연동 후보는 이번 요구 개정으로 우선순위에서 제외했다.
5. **주행 gate 이후:** 차종 geometry/torque·pressure·steer mapping calibration, actuator
   중복 제거, 실제8-role 경로 연결, energy interval port와 보호 응답 검증을 각각 작은 변경으로 수행한다.

**현재:** M7-1a/b/c/d의 명시한 한정 실행 완료, [1d 결과](../test-plan/evidence/m7_carla_1d/README.md)의
startup/wall timing 제한·종료 crash와 기존 OPEN 유지. 다음 조사에는 착수 가능하다.
**착수 불가:** 실제 clock·wheel/Actual 경로·native guard·calibration을 입증하지 않은 정상 주행,
M6 동등 energy/안전 수용 주장. 기존 M4/SDK/DDS OPEN 전체를 M7 비주행 선행 조건으로 추가하지 않는다.
Jetson 배포/학습은 범위 밖이며 TBD-09는 Host 조사만 반영한다.

<a id="preflight-2026-10-26-후속--m7-1k-최소-서버-포트"></a>

### 2026-10-26 후속 — M7-1k 최소 서버 포트

[실행·실패 기록](../test-plan/evidence/m7_carla_1k/README.md)의 opt-in 포트는 실제 UE NoDrive에
합성 CAN/P05 Actual0만 수용한다. 최종156개 검사(반복 포함)·13개10ms receipt와
원본 보존/손상8종 거부, 별도 client의 직접 writer·일반 tick 차단, pause/실제 physics reset,
새 session/INIT를 확인했다. flag-off 별도 서버는 기존 비주행 lifecycle2/2·102샘플을 통과했다.
서버4회 모두 설정/actor 정리 후 SIGINT130이다. 초기 build2회와 harness1회의 FAIL을 보존한다.

이는 위 M7-1-06/07/09의 **서버 진단 일부**에 대한 후속 근거이며 과거 전체 판정을
PASS로 고치지 않는다. 실제8-role 정상 연결·nonzero rad/Nm/Pa·brake calibration·구간 work,
native wall/transport timeout 실주입·평지 보호 brake 및 렌더링 안정성은 미수용이다.
다음 작업은 wheel/COM geometry의 좌표·차량 기준점 검증과 근거 있는 brake 모델 선정이다.
기존 M6 수용·ECU 주기·freshness·영상/GT 계약은 유지한다.

<a id="preflight-2026-10-27-후속--m7-1l-rest-geometrybrake-모델안"></a>

### 2026-10-27 후속 — M7-1l rest geometry/brake 모델안

[실행·실패·모델안](../test-plan/evidence/m7_carla_1l/README.md):5개 INIT 자세의 frozen-frame geometry와
reference/body/실제 COM/world/actor/프로젝트 반사 변환을 교차 검증했다. 독립 손상7종 거부·실제 reset 뒤 geometry 무효화와
새 source binary의1k156개 검사/13receipt 회귀를 확인했다. build1FAIL과 API COM 단위 가정
audit1FAIL을 보존했고 서버는 정리 후 SIGINT130으로 종료했다. sensor/actuation 시험이 아니다.

V1(M6 합산 torque law·4륜 균등 가상 EV)과 H1(실측 유압 식별)의 구체 모델안을 제시했다.
실차 보정 자료나 가상 모델의 명시적 수용 전에는 계수를 확정하지 않는다. 서버0 effort gate와
M6 계약은 유지하며 실제 조향 부호·보호 brake/raw wheel·full Actual/work/wall은 후속이다.

<a id="preflight-m7-0-변경의-검증-범위"></a>

### M7-0 변경의 검증 범위

변경은 Markdown7개(새 문서2개·기존 연결/상태5개)다. 변경 문서의 로컬 링크/앵커121개를
정적으로 대조해 깨짐0, code fence 짝 누락0을 확인했다. `git diff --check`와 새 파일의
공백 검사에 오류가 없다. M6 종료 문서·requirements·profiles·구현·시험/evidence 파일의
변경0을 확인했다. C++/SDK/MIL 회귀와 CARLA runtime 시험은 새로 실행하지 않았다.

<a id="preflight-2026-10-27-후속--m7-1m-승인-v1-nonzero-격리-진단"></a>

### 2026-10-27 후속 — M7-1m 승인 V1 nonzero 격리 진단

[실행·실패](../test-plan/evidence/m7_carla_1m/README.md): 사용자가 V1 가상 EV law를 수용했다.
별도 서버 opt-in·model hash/geometry 검사로 합성 Actual의 nonzero effort와 보호 Brake Actual을 적용했다.
새2서버 각1,621receipt/38검사·독립 손상9/9 거부, hold100/100 exact wheel0을 확인했다.
각487frame의 raw rear 음수는 native 전진 입력 unavailable이며 정상 gate FAIL이다. clamp/restamp 없음.
full Actual/work/EV/wall·전체 renderer 안정성은 미수용이다. 다음은 내부 적분 분할 후보의 명시적 비교다.

<a id="preflight-2026-10-27-후속--m7-1n-내부-적분-대조"></a>

### 2026-10-27 후속 — M7-1n 내부 적분 대조

[같은 입력의 실제 대조](../test-plan/evidence/m7_carla_1n/README.md): 기본3/1·내부20/20을 별도 서버 옵션으로 구분했다.
같은 새 binary의 기본 rear 음수487frame 재현,20분할 새2서버 각3frame/1,621receipt였다.
출발 첫 tick에 약−.256rad/s가 남아 native forward gate FAIL/20분할 정상 미채택이다.
원래 Actual/시각/요구사항을 보존하며 다음40분할 또는 기존 actuator Actual trajectory의 분리 시험이 남는다.

<a id="preflight-2026-10-27-후속--m7-1o-출발-적분-안정화와-wheel-원천-정정"></a>

### 2026-10-27 후속 — M7-1o 출발 적분 안정화와 wheel 원천 정정

[실행 원본](../test-plan/evidence/m7_carla_1o/README.md):20분할은 실제 정착과 기존 response 모델 입력에서도
출발 음수를 재현했고40/80분할도 실패했다. 읽기 전용 tire callback으로 저속 반력의 적분 진동을
확인하고320분할을 후속 격리 후보로 정했다. 최종 직접 solver source의 새2서버 stress 및
response 입력은 각1,621frame/4wheel 음수0이다. 중간 앞바퀴 미세 음수는 보존한다.
기존 공개 getter는 무구동 저속 보정값일 수 있어 `mWheelSpeeds` 직접 읽기를 별도로 추가했다.
UE commit/header hash를 고정하며 engine/M6 source·물리 계수·주기/freshness는 바꾸지 않았다.
정상 주행은 직접 원천의 native 반환·full Actual/authority·solver work/단일 EV·wall 검증 뒤 판단한다.

<a id="preflight-2026-10-27-후속--m7-1p-직접-solvernative-반환"></a>

### 2026-10-27 후속 — M7-1p 직접 solver/native 반환

[실행·실패 기록](../test-plan/evidence/m7_carla_1p/README.md):320분할 step/response 새2서버의 각각1,621개
직접 solver 관측을 기존 native8-role fixture에 공급해1,609개 Actual 반환을 확인했다.
원래 acquisition을 유지해 다음 구간 끝 age 최대20ms이며 기존30ms 요구를 변경하지 않았다.
20분할의 실제 음수와200번째 snapshot 전달 누락 주입은 native barrier 없이 다음 tick을 차단했다.
Normal/ASan 각60/60, frozen replay 각1,621개와 손상29종 거부·독립 live audit 손상8종 거부를 확인했다.
최초 receipt보다 snapshot stream이 늦은 FAIL 및 당시 cleanup latch 검사 FAIL은 보존한다.
동일 frame 도착까지 조회만 기다리고 모든 실패 경로를 latch하도록 고쳤다. 수정 후 누락 주입은
cached receipt로 회복하지 못했으며6개 소유 서버 모두 설정/actor 정리 후 SIGINT130이었다.
native sensor 반환만 연결했고 CARLA actuation은 합성 Actual이다. 다음은 full Actual/authority 적용
gate → solver work/단일 EV → wall 검증이며 renderer·AI/Jetson·M6 전체 회귀는 이번에 실행하지 않았다.

<a id="preflight-2026-10-27-후속--m7-1q-실제-native-actual의-서버-적용"></a>

### 2026-10-27 후속 — M7-1q 실제 native Actual의 서버 적용

[실행·실패·제한](../test-plan/evidence/m7_carla_1q/README.md): 원본 Actual/CAN/P05, 실제8-role Release ACK·
Run credit, 인과 명령과 permission의 전체 다음10ms 유효성을 검사하는 별도 서버 모드를 구현했다.
새2서버 각400tick/319정상 권한 구간, 최종 약0.291m/s 전진을 확인했다. 값·source 재발급이나
명령 우회 없이 native→CARLA 기능 경로를 연결했다. M7 전용 INIT offset8ms로 기존20/10ms 위상을
맞췄고 Drive30ms/기존 expiry는 유지한다. 초기 즉시 INIT의 구간 coverage FAIL을 보존했다.
Normal/ASan 각64/64, 원본 wire/physics 독립 검사와 권한·명령·snapshot 누락 시 다음 tick 차단을 기록한다.
최소 command expiry 여유1ns는 고정 simulation clock 경계이며 wall2/4ms 수용이 아니다.
다음 M7-1r은 solver 구간 work의 완전성/누락 검출 → 단일 EV 정산 → 원자적 실패 처리다.
모델 전기는 ZOH 예측으로만 표기하고 `interval_work_valid=false`를 유지한다. M6/engine 원본·V1 계수는
변경하지 않았으며 일반 주행 시나리오/renderer·AI 학습·Jetson·M6 전체 회귀는 이번에 실행하지 않았다.

<a id="preflight-2026-10-27-후속--m7-1r-완전한-solver-work단일-ev-정산"></a>

### 2026-10-27 후속 — M7-1r 완전한 solver work·단일 EV 정산

[실행·실패·제한](../test-plan/evidence/m7_carla_1r/README.md): NoDrive 적분 전후320개 구간을 원래 dt/토크와
함께 관측하고 누락/중복·sleep return을 구분하는 opt-in observer를 구현했다. UE source/static
archive는 변경하지 않고 외부 생성본으로 PhysXVehicles module을 빌드했으며 원본 binary를 보존했다.
최종 새2서버 각400receipt/400정산·319정상 구간에서 signed discrete motor work를 기존 단일
EV owner에 연결했다. work의 보수적 시간 배분과 끝 잔여 정산은 원래 wheel/CAN timestamp를
갱신하지 않는다. 새 모드는 ZOH 전기 예측을 함께 실행하지 않는다. Normal/ASan 각69/69,
raw wire/solver/work/SOC/손실 독립 검사, 실제 work 누락·중복 및 ACK 누락·중복·불일치 차단을 기록한다.
M6 계약/구현·V1 계수·Drive30ms/기존 expiry·world10ms/영상50ms는 유지한다. 초기 native build
실패와 ACK 중복 시험의 집계 오류를 원본 그대로 보존하고 수정 후 확인했다.

기존 native 회귀의 서버 종료−11도1회 관측했다. multi-GPU Listener/Asio accept 스택이며 원인/수정은
OPEN-M7-1R-EXIT-01이다. 재실행130을 실패 해소로 간주하지 않는다. 비정상 서버 종료를 성공으로
집계하던 runner를 수정했고 원본 실패를 보존했다.

다음 M7-1s: 종료−11의 최소 재현/원인 분리·수정 검증을 먼저 진행한다. 그 뒤 같은 native Actual
경로의 가속→감속→정지·재출발, 보호 제동, signed 회생을 각각
작은 시험으로 분리한다. 각 시험에서 work 누락/음수 범위/정산 오류 시 즉시 중단하고 다음 tick을
막는지 확인한 뒤 wall2/4ms·계측 비용을 검증한다. 일반 ODD/renderer·AI/Jetson·M6 전체 회귀는 NOT RUN.

<a id="preflight-2026-10-27-후속--m7-1s-종료-경합-수정"></a>

### 2026-10-27 후속 — M7-1s 종료 경합 수정

[원인·실행·실패](../test-plan/evidence/m7_carla_1s/README.md): 실제 pinned CARLA Listener/Router의
accept/close data race를 독립 TSan으로 재현했다. pool stop/join 후 소켓·세션을 닫고,
취소 재등록/context reset·중복 Stop·자기 참조를 수정했다. 실제 source component는
Normal/ASan·UBSan/TSan 각각6/6(종료1,000회·연결 종료100회 포함), 기존 native Normal/ASan 각69/69다.
UE 전체 sanitizer 수용이 아니다. LibCarla와 UE Carla module을 다시 빌드했고 M6 원본40파일,
M7Native/PhysX observer module·V1/기존 시간 계약은 보존했다.

최초 실행은 cold map 준비 중 get_world10초 timeout 뒤 SIGINT30초 한도 초과/강제−9로 실패했다.
실패를 보존하고 기존180초 startup 한도 안에서 read-only world snapshot 준비를 기다리도록
runner를 보완했다. cold-load 중단 자체의30초 종료 수용은 남는다. 후속 새 서버의 개별 종료/독립
work audit는 위 evidence에 기록한다. M7-1r−11은 accept/close 경합 수정 범위로 한정해 판단하며
옛 package SIGTERM/renderer crash까지 해소한 것으로 확대하지 않는다.

다음 M7-1t는 같은 native Actual/단일 EV 경로의 가속→감속→정지·재출발을 확인한다.
V1 가상 EV 브레이크를 유지하며 보호 제동·signed 회생은 별도 scenario다.
cold-load 중단·wall2/4ms/clock uncertainty·장시간/전체 ODD는 별도 gate로 남는다.


<a id="preflight-m7-통합-검증--2026-10-27-현재-판정"></a>

### M7 통합 검증 — 2026-10-27 현재 판정

후속 작업을 개별 승인 단계로 계속 나누지 않고 주행·회생/마찰 제동·정지/재출발·영상/state·
누락·pause/reset·종료·wall 계측과 독립 audit를 묶어 실행했다.
[통합 실행 원본/실패](../test-plan/evidence/m7_carla_integrated/README.md), [종료 검토](../project-status.md#m7-종료-조건),
[재현 runner](../../tests/integration/carla/m7_integrated_run.py)를 사용한다.

정상 새 서버5회(비렌더3/영상2)가 각각900receipt/900EV 정산·819정상 권한 구간을 완료했다.
영상2회는 각각RGB180/GT180이며 원래 image/state timestamp가 일치한다. native Normal/ASan
각70/70, raw-wire/work/EV 독립 감사와 영상/상위 요청 metadata 손상7종 거부를 확인했다.
실행별 분모를 기존 M6나 과거 M7 PASS에 합산하지 않는다.

새 시험 코드의 초기 ActorSnapshot 미존재 실패와 기본 camera의 첫60ms 간격 실패를 보존했다.
전자는 초기 unavailable 처리, 후자는 M7 전용 frame5 실제 취득 스케줄로 수정했다.
M6 코드·40개 native 복사 원본·UE tracked source·V1 계수·freshness/expiry는 유지했다.

최종 기능 성공은 전체 M7 종료가 아니다. native owner 대기 공백>2ms, 실제 보호 Actual 적용 경로
미구현, cold-loading의 준비180s/종료30s 실패가 남는다. 원래 renderer crash 원인도 미확정이다.
계측 비용과 clock domain·동일 scope·성공/실패를 분리한 현재 판정은 통합 종료 검토를 따른다.


<a id="preflight-종료보호-연결-후속-검증-2026-10-28"></a>

### 종료/보호 연결 후속 검증 (2026-10-28)

[원본·실패·실행 명령](../test-plan/evidence/m7_carla_recovery/README.md)을 따른다.
동기 RPC가 아직 game thread에 dispatch되지 않은 상태에서 Stop을 호출하는 component 재현과,
실제 fresh CARLA 로딩 중 SIGINT→30s 내 종료를 검사한다. 기존 네트워크 경합 수정과 구분한다.
`m7_integrated_run.py --cases protection camera-a work-missing loading-abort`로 정상/보호/영상/누락/종료
회귀를 재현할 수 있다. 보호 case는 원래 native 안전 선택 후200개 physics 구간과 단일 EV 정산을
이어간다. 원래 Actual/P05/freshness/출처를 독립 감사하고 보호 proof 손상·정상 재개를 거부한다.
원래 M6 판정, 과거 실패, wall2/4ms 미수용·차체 완전 정지 미수용은 유지한다.

<a id="preflight-독립-wall-guard-검증-2026-10-28"></a>

### 독립 wall guard 검증 (2026-10-28)

`m7_integrated_run.py --cases wall-gap camera-a protection`으로 실행한다.
wall-gap은199 physics 구간과 모든 EV 정산을 완료한 뒤 다음 입력을 보류한다.
native가 선언한 첫 release 이후 실제 owner0..8의 미완료를 독립 monitor가 검출해야 한다.
원래2ms/4ms·latched fault를 유지하고, late finish/heartbeat/동일 slot 중복으로 누락을 숨기지 않는다.
명시적 PROTECT/압력 주입 없이 native local 보호 선택·credit0·다음 frame 없음·동일 barrier time과
adapter pause 이후 frame 불변을 확인한다. `audit_m7_wall.py`가 CSV/원본 trace 및5종 손상을 검사한다.
물리 제동 PASS가 아니며, in-flight RPC fault·연속 owner scheduling/clock mapping은 후속 시험이다.
기존 normal900/영상·functional 보호400 회귀와 원본 비교도 함께 수행한다.
실행 중단/강제 종료, TSan 초기 실행 실패와 process-local ASLR 해제 후 결과는
[해당 실행 근거](../test-plan/evidence/m7_carla_wall_guard/README.md)에 분리 기록한다.

<a id="preflight-actuatorev-독립-진행-선결-검사-2026-10-28"></a>

### Actuator/EV 독립 진행 선결 검사 (2026-10-28)

`M7DeferredWork.*`는 work 부재 중 response 지속·원래 취득 시각 유지, 과거 coil 기반 지연 정산과
signed EV 장부 동등성, fractional tail, 정산 실패/중복의 actuator rollback 금지, stale current의
opening dwell 금지, wheel identity 변조와 coupled/deferred 혼합 거부를 검사한다.
원래 M7 전체 CTest와 ASan/UBSan 검사를 실행하고 `replay_m7_native.py`로 기존 정상/보호
trace의 WORK/WHEEL/PROTECT 입력을 재생해 모든 native 출력을 비교한다. replay는 새 CARLA
실행이 아니며 원래 physics/센서/종료 PASS 분모에 합산하지 않는다.
[실행·오류·제한](../test-plan/evidence/m7_carla_wall_guard/deferred-response/README.md)을 따른다.

<a id="preflight-terminal-native-service-후속-검사-2026-10-28"></a>

### Terminal native service 후속 검사 (2026-10-28)

`M7TerminalResponse.*`는 동일 native8-role 상태의 보호 Actual 지속·EV/wheel 원시 시각 동결,
fractional barrier handoff, 정상 재진입/다른 thread/역행 시간 거부를 검사한다.
`probe_m7_terminal.py`는 기존 raw 입력200개를 정확히 재생한 뒤 stdin을 열린 채 보류하여
독립 wall fault를 유발한다. 새 CARLA 실행은 `m7_1o_run.py --solver-work --native-fault wall-gap
--terminal-response --vehicle-substeps 320`과 기존 source/engine/python/fixture/native 인자로 수행한다.
`audit_m7_terminal.py`는 원본 wire/P05·Actual provenance·clock/EV 불변·실제 wall CSV 및8종 손상을
검사한다. 순수 idle 전용 `audit_m7_wall.py`와 구분하며, terminal service의 누락/late도 그대로 보고한다.
정상/ASan 회귀·TSan과 기존901/401개 출력 replay를 별도 기록하고 CARLA physics 분모에 합산하지 않는다.
[실행·실패·재현](../test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md)을 따른다.


<a id="preflight-종료보호-정지clock-일괄-후속-검사-2026-10-28"></a>

### 종료·보호 정지·clock 일괄 후속 검사 (2026-10-28)

[원본/실패/판정](../test-plan/evidence/m7_carla_recovery/batch-closeout/README.md)의 단일 suite를 사용한다.
`m7_integrated_run.py --held-steer-sleep --cases client-loss protected-sleep camera-a
client-loss-cameras loading-abort wall-gap zero disabled`에 기존 engine/source/python/fixture/native
및 새 runtime/output 경로를 전달한다. 컴파일된 서버/observer ABI2를 함께 사용한다.

- client-loss: 정상199receipt/정산 후 실제 process exit73, cleanup 없음. SIGINT30s 내 종료 및
  원래 frame 유지, physics 등록 차단 로그를 검사한다. 영상 유/무 모두 실행한다.
- protected-sleep: 기존400구간/보호200구간의 Actual/wire/완전 solver/EV 감사를 유지한다.
  자연 sleep 이후 body/wheel exact0 지속, 마지막100구간 pose/quaternion 동일을 검사한다.
  hold의 직전 완료 구간/동일 effort/원래 보호 Actual을 확인하고5종 변조를 거부한다.
  pause/reset/close 후 새 INIT의 보호 hold 이력 부재와 이전 stage 재사용 차단을 확인한다.
- clock: 실제 post-physics 취득 bracket과 다음 native 처리의 같은 Host monotonic 순서만
  검사한다. index150의 의도적250ms pause 포함/제외 통계를 분리하며 기존 CAN 시각은 불변이다.
  offset 교집합·지연 관측은 정상 wall 수용 증거가 아니다.

일반/ASan M7 회귀와 기존 정상900구간의 physics/solver 대조를 함께 기록한다. 초기 실패는
최종 성공으로 덮지 않는다. M8/AI/Jetson이나 M6 재수용을 이 묶음에 추가하지 않는다.


<a id="preflight-solver-기록-경로-분리-검증"></a>

### Solver 기록 경로 분리 검증

기존 suite에 `--compact-work`를 추가하고 normal-a/camera-a/protected-sleep/wall-gap/work-missing/
snapshot-stop을 실행한다. journal 원시 steps·compact mean·원래 frame/ticket/scope를 교차 검사한다.
완전 trace 회수 후 기존 Actual/wire/P05·solver 방정식·EV 장부 감사와 body 정지 검사를 유지한다.
추가5종의 journal ticket/frame/session/generation/mean 변조를 거부한다. capacity/원본 복사/중복·
skipped frame/ABI 오류는 CTest에서 검사한다. default-off와 compact 영상을 동일 바이너리로
연속 실행하고 physics/solver/work의 정확한 동등성 및 원래 monotonic 통계를 비교한다.

`m7_phase_probe`의42개 synthetic 조합은 원래 admission/expiry 규칙을 유지한 시작 위상 조사다.
실패 조합을 PASS로 합산하지 않는다. 일반/ASan 회귀와 기존 native901/401개 출력 replay를
함께 수행한다. [실행 결과](../test-plan/evidence/m7_carla_wall_guard/pipeline/README.md)의 정상 wall gate는 계속 OPEN이다.

<a id="icd"></a>

## CARLA Plant Adapter / Vehicle Plant Interface 초안

2026-10-28, `m7-plant-draft-v25`. **복합 주행/회생·센서 기능 통합 검증 / 전체 M7 NOT CLOSED**.
[시간 계약](../requirements/timing-requirements.md)의 M7 world/state 주기는 M7-1d 사용자 승인에 따라
50→10ms로 개정했다. M7-1f는 별도 opt-in functional clock 검증이며 wall 계약 개정이 아니다.
기존 [공통 ICD](../interfaces/README.md), [owner-wire](../interfaces/owner-wire-v1.md),
[M6 종료 범위](milestone-reviews.md#m6)의 통신·안전·물리 수용 계약은 유지한다.
환경 근거와 실행 gate는 [M7 사전 점검·시험 계획](../carla-guide.md)에 둔다.

<a id="icd-1-경계와-단일-소유권"></a>

### 1. 경계와 단일 소유권

정상 경로는 Central → Front/Rear Zone → vECU → Actual CAN/P05 → 담당 Zone →
Central feedback bridge → Plant Adapter → CARLA다. 물리 actuator 모델은 ECU 밖에서
응답을 생성하고 vECU가 이를 센서로 취득·검증해 Actual로 보고한다. 기존 physical bus의
값을 CARLA로 바로 보내 이 반환 경로를 생략하지 않는다. Command, target, permission,
capability, `get_control()`의 마지막 설정값은 실제 actuator feedback이 아니다.

Plant Adapter만 ego actuation API에 접근한다. Controller/AI/Zone/ScenarioRunner/
Traffic Manager/manual_control/ROS ego control은 writer가 될 수 없다. Autopilot은 끈다.
spawn/destroy/INIT pose 설정은 orchestration lifecycle이며 정상 주행 제어가 아니다.
fault injection도 명령/센서/actuator 모델에 적용하며 독립 ego writer를 만들지 않는다.
single writer는 CARLA 서버가 인증해 주는 기능으로 가정하지 않는다. 전용 서버·클라이언트
구성, adapter 내부 owner token, API 호출 감사로 통제하고 외부 무허가 client 배제는 실행
환경 gate다. 별도 client가 직접 API를 부르는 것을 Python wrapper만으로 막았다고 주장하지 않는다.

| 상태/계산 | M7 책임 | 중복 금지 / 미결정 경계 |
| --- | --- | --- |
| 세션·배분·보호 | 기존 Central/Zone/vECU | 실제8-role INIT/ACK/RunLease/arm·expiry·CAN/P05 보존 |
| actuator delay/rate/saturation/fault·actual 센서 | 기존 SIL actuator physical owner + vECU 보고 | CARLA adapter에서 같은 delay/ramp를 다시 적용하지 않음 |
| 차량 질량·관성·타이어/노면·pose/속도 | CARLA만 | CARLA run에서 SimpleVehicle 및 VehicleEvModel의 motion step을 함께 돌리지 않음 |
| CARLA engine/gear/clutch/steering filter | backend 적합성 검토 대상 | 기존 wheel actual에 engine response를 중복하지 않는 설정/저수준 API 입증 전 정상 apply 차단 |
| battery/SOC·HV/접점·전기 손실 | 하나의 EV physical owner | CARLA와 별도 SOC 적분 금지; vECU가 physics를 소유하지 않음 |
| motor/friction work | 검증된 CARLA interval telemetry → 단일 energy bridge | torque·wheel rotation의 같은 구간 work만 전달; 회생과 마찰을 별도 장부로 보존 |

현재 [PhysicalOwner](../../simulation/runtime/m4_owner_network.cpp)는 actuator/차량/EV를
한 경로로 실행한다. 위 분리는 후속 opt-in backend 작업이며 M6 코드를 이번에 바꾸지 않는다.
`VehicleEvModel::step`을 CARLA와 병행하거나, CARLA 속도로 M6 pose를 다시 적분하지 않는다.
50ms end speed를 10ms/2ms 센서나 과거 speed로 소급할 수 없다. [M6 energy port](../interfaces/vehicle-energy.md)의
구간·dependency·원자적 commit 전제는 CARLA에서 아직 충족되지 않는다. 외부 서버 tick은
로컬 candidate처럼 rollback할 수 없으므로 실패 interval을 invalid로 남기고 다음 tick을
막는다. M6의 에너지 오차 예산/230ms 응답 수용을 CARLA에 승계하지 않는다.
wheel work를 신뢰성 있게 얻기 전 CARLA EV energy는 **unavailable**, SOC/회생 수용은 NOT RUN이다.

<a id="icd-2-simulator-독립-vehicle-plant-interface"></a>

### 2. Simulator 독립 Vehicle Plant Interface

아래는 의미 schema이며 C++ ABI, Python class, 새 wire layout 확정이 아니다.
기존 IF-HOST-ACTUATOR/IF-HOST-SENSOR/IF-HOST-EV-STATUS를 구현할 port로 검토한다.
CAN/P05나 owner-wire v1을 수정하지 않는다. CARLA handle/type은 backend 안에만 둔다.

| Port | 입력/출력 | 계약 |
| --- | --- | --- |
| describe/configure | backend version, geometry/calibration ID+hash, capabilities | INIT 전 읽기/고정. `supports_signed_wheel_torque`, true substep observation, energy fidelity 등 미지원은 명시 |
| accept_actual | `ActualBundle`: steering rad, signed drive Nm, friction Pa의 독립 sample | typed actual만 수용. 값이 같아도 command 타입/원천은 거부 |
| prepare_step | run/plant epoch, expected frame, begin/end, ActualBundle | age/clock/identity/coverage/calibration 검사 → prepared 또는 이유 있는 reject; actuation하지 않음 |
| commit_step | prepared token + tick-owner 허가 | adapter만 apply, orchestrator만 tick. 동일 token/frame 중복 apply 금지. tick RPC timeout은 무조건 재시도하지 않고 실제 snapshot과 대조 |
| observe | `VehicleState`, `SensorPacket[]`, `PlantHealth`, 선택 `IntervalWork` | 관측/추정/GT 구분, 원래 acquisition 보존; incomplete는 zero가 아닌 unavailable |
| pause/reset/close | lifecycle 요청 | pause containment; reset은 새 run/plant epoch·명시적 INIT, close는 sensor stop→자신의 actor destroy·설정 복원 |

각 sample은 `schema_version, run_id, plant_epoch, source_id, source_epoch, sequence,
clock_domain, acquisition_time, oldest_dependency_time, validity, reason, frame_id`를 갖는다.
actuator에는 기존 application Epoch/role/CAN identity/원래 source·parent·origin·expiry 및
수신 검증 provenance를 함께 보존한다. `source_id`는 trusted configuration의 role/plant/sensor
인스턴스에 바인딩하며 payload의 자기 선언만 신뢰하지 않는다. CARLA actor ID는 episode 안의
식별자일 뿐, ECU authority가 아니다. bundle 번호·bridge receive/publish 시각은 별도 필드다.

- `validity`: valid / unavailable / stale / invalid; reason은 missing, wrong-source, old-epoch,
  replay, future, clock, nonfinite, out-of-range, skew, expired, calibration, coverage, overflow 등.
- 새 source sequence·취득 시각은 단조 증가. 동일 sample 재사용은 원래 값·시각·dependency가
  모두 불변이어야 하며 valid-RX나 acquisition cursor를 갱신하지 않는다. wire counter wrap은
  기존 수신부 규칙을 따르고 adapter 자체 sequence 소진은 새 epoch를 요구한다.
- 각 actuator의 age/state/quality를 따로 검사한다. 부분 bundle을 0으로 채우지 않는다.
  missing/NaN/무효/출처 불명은 apply와 다음 driving tick을 막는다. command fallback 없음.
- M6 입력 age30ms/skew10ms는 [SimpleVehicleConfig](../../simulation/vehicle/simple_vehicle.hpp)의
  모델 한계다. M7 draft의 보수적 admission 상한으로 유지하며 기존 stream의 더 짧은
  expiry/지원 조건이 우선한다. CARLA 50ms interval 전체를 허용한다는 뜻은 아니다.

<a id="icd-3-물리량-변환과-calibration-gate"></a>

### 3. 물리량 변환과 calibration gate

[CARLA 0.9.16 API](https://carla.readthedocs.io/en/0.9.16/python_api/)의 VehicleControl은
steer[-1,1], throttle/brake[0,1]이며 Nm/Pa 직접 입력이 아니다. wheel max steer는 deg,
radius는 cm, max brake torque는 Nm다. engine torque curve는 wheel aggregate torque가 아니다.
Ackermann speed/acceleration 제어는 별도 제어기를 추가하므로 actual-only 대체 경로로 채택하지 않는다.

| 원천 actual | 기본 package에서 검토한 mapping (미채택) | 아직 필요한 근거 |
| --- | --- | --- |
| Steering δ(rad), 좌회전+ | `steer = inverse_steering(-δ, speed, geometry, calibration)` | 좌우 road-wheel→equivalent angle, 속도별 steering curve, tire/geometry와 포화 범위. 단순 δ/상수 확정 금지 |
| Drive T(Nm), 전진 구동+ | `throttle = inverse_drivetrain(T, wheel_speed, gear, calibration)` | engine/gear/differential 손실·inertia·zero-throttle drag를 포함한 wheel 기준 역변환. T/300 같은 M6 fixture 재사용 금지 |
| Drive T<0, 전진 회생 | signed wheel torque backend 우선 검토; 기본 API는 `brake_regen_equivalent` 후보 | reverse=true로 음수 torque를 구현하지 않음. 제동 등가 근사만으로 회생 에너지 검증했다고 주장하지 않음 |
| Brake P(Pa), 마찰만 | `Tfriction = calibrated_pressure_to_wheel_torque(P)`, inverse brake mapping | aggregate 계수·차륜 배분·max brake torque readback·정적 hold/저속 특성. M6 0.001Nm/Pa는 CARLA calibration 아님 |

기본 brake API를 사용하는 제한적 motion 근사 후보는 음수 motor torque의 등가 제동과
friction torque를 **한 번만 합산**한다. 각 원천 기여는 장부에서 분리하고 saturation/residual을
보고한다. 양수 drive와 마찰이 동시에 있을 때 API가 요청한 양쪽 실제 힘을 재현하는지도 gate다.
포화로 입력을 몰래 잘라 정상처럼 보고하지 않으며 backend capability 부족은 reject한다.
회생을 CARLA friction loss로 적용하면서 배터리에도 같은 에너지를 회수한 것으로 세지 않는다.
기본 API가 필요한 충실도를 못 내면 저수준 wheel-force/torque 연동을 후속 검토한다.
`set_target_velocity`, 반복 teleport, 두 번째 physics plant로 우회하지 않는다.

calibration artifact는 vehicle blueprint/map·CARLA build, physics readback, 단위/부호,
geometry, 곡선/유효 범위, 데이터·식별 방법, 검증 잔차/허용 오차, revision/hash를 포함한다.
계수·허용 오차는 **TBD-02/03/07**. M7-1에서 geometry를 읽는 것은 calibration 완료가 아니다.

<a id="icd-m7-1i--직접-wheel-effort-확장안"></a>

#### M7-1i — 직접 wheel effort 확장안

[공식 소스·설치 API 조사 및 오프라인 시험](../test-plan/evidence/m7_carla_1i/README.md)에 따라
기본 `VehicleControl`의 throttle 역변환을 정상 연결의 구현 방향으로 채택하지 않는다.
선행 Actual은 wheel torque인데 기본 backend는 engine/clutch/gear 상태를 추가한다.
현재 공개 관측만으로 이를 정확히 역변환하거나 중복 응답을 없앴다는 근거가 없다.
**우선 구현 후보는 PhysX `PxVehicleNoDrive`를 노출하는 별도 CARLA 서버 확장**이다.
이는 엔진 없는 suspension/wheel/tire plant를 제공하지만 설치된0.9.16 Python API에는
직접 effort setter가 없다.1j에서 source build 작업은 승인 범위가 되었지만 실제 서버 구현·빌드·차량 수용은 미완료다.

| 입력 | 확장 backend에 전달할 SI 값 / 설계 법칙 | 미결정 또는 필요한 검증 |
| --- | --- | --- |
| equivalent Steering Actual δ, 좌+ rad | 이상 Ackermann: `δL=atan2(L tanδ,L−W tanδ/2)`, `δR=atan2(L tanδ,L+W tanδ/2)`; CARLA 우+ 기준은 `−δL,−δR`, rear0 | 실제 local wheelbase L/front track W, 휠 순서·축 부호·최대각 readback과 실제 회전 검증. 스케일·속도 필터·추가 지연 없음 |
| aggregate Drive Actual T, signed Nm | 제안 EV 모델은 이상적 open differential: rear 각각 `T/2`, front0. 양·음수 모두 motor 입력에 유지 | stock mkz drivetrain 재현이 아닌 명시적 모델 법칙. 원래 rear 평균 ω와 `ΣTiωi=T(ωRL+ωRR)/2`가 일치. torque vectoring은 별도 work port 개정 필요 |
| Brake Actual P, Pa | 근거 있는 `P→[TFL,TFR,TRL,TRR]` 단조 table의 구간 선형 보간; 전부 nonnegative friction Nm | 실제 유압·패드·디스크 데이터 또는 명시적으로 수용한 가상 brake 모델 필요. max brake800Nm readback만으로 P→Nm 식별 불가. 기본 계수 없음 |

`tests/integration/carla/m7_1i`는 위 수학만 구현한 **test-only prototype**이다.
합성 geometry/table은 오프라인 test vector이며 차량 calibration artifact가 아니다.
table 누락/비정상·입력/휠 한계 초과·불가능한 조향 기하는 거부하고 clamp/외삽하지 않는다.
원래1c Actual/P05 boundary 뒤 fake backend로만 검사하며 `CarlaDriving`은 계속 Disabled다.
순수 함수의 double 인자 자체는 Actual provenance 증명이 아니므로 runtime 입구로 노출하지 않는다.

CARLA plugin 경계까지 SI를 보존한다. UE kg/cm/s 내부에서만 torque를 `Nm×100²`로 바꾼다.
이는 단위 변환이지 임의 normalization gain이 아니다. 각도는 rad, scene 길이는 cm→m로 구분한다.
upstream PhysX3.4 소스는 확장 설계 근거이며 bundled UE의 exact build identity를 증명하지 않는다.
빌드 시 실제 fork/commit·scale·좌표 기준을 별도로 고정하고 검증해야 한다.

확장 시 native actuator는 delay/rate/fault, CARLA는 wheel inertia/damping·tire/suspension·chassis만
소유한다. stock movement controller·engine·clutch·gear·steering smoothing은 함께 실행하지 않는다.
기존 M6 response/vehicle model을 변경하거나 두 번째 motion step을 추가하지 않는다.

<a id="icd-서버-apply-receipt와-interval-work-요구"></a>

##### 서버 apply receipt와 interval work 요구

구현 전의 의미 계약이며 새 RPC/wire ABI는 아직 없다. 단일 writer와 tick owner는 유지한다.

1. INIT에서 build/model/calibration hash, wheel order, 단위, run/plant/actor/owner를 바인딩한다.
   client가 임의로 보낸 capability=true는 권한 또는 calibration 수용 근거가 아니다.
2. `prepare`는 원래 CAN/P05 Actual·application·sequence·source/oldest/expiry를 그대로 보존한다.
   geometry/table 범위와 전체10ms interval coverage를 검사한다. endpoint 관측으로 소급하지 않는다.
3. 하나의 `(run,plant,actor,frame,token)`에4wheel steer/motor/friction을 원자적으로 stage한다.
   pre-physics ACK는 **staged**이고 work 증명이 아니다. 같은 token 재호출은 조회만 가능하며
   재적용·중복 tick을 하지 않는다. timeout은 receipt/snapshot 대조 전까지 ambiguous로 latch한다.
4. physics 구간 종료 receipt는 실제 begin/end·frame·적용 effort·solver substep coverage·원래
   Actual 참조를 포함한다. `Σ Tmotor_i Δθdynamic_i`와 friction loss를 별도로 기록한다.
   animation pitch 또는 endpoint `T×ω×dt`를 실제 구간 work로 승격하지 않는다. brake lock,
   damping·tire loss·수치 잔차를 분리하고 선택한 solver work 정의/허용 오차를 검증해야 한다.
5. receipt가 검증된 뒤에만 단일 EV owner의 IntegratedMotorWork에 전달한다. 같은 구간을
   기존 ZOH 예측과 함께 적분하지 않는다. 외부 tick은 rollback 불가하므로 불완전 receipt는
   energy unavailable·latch이며 다음 tick 금지다. M6 energy budget 수용을 승계하지 않는다.

NoDrive setter는 다음 setter까지 지속되는 API다. 따라서 RPC 추가만으로 expiry를 만족하지 않는다.
확장 서버가 frame별 single-use latch와 pre-tick coverage를 검사하고 old effort 재사용을 막아야 한다.
pause는 tick 정지·pending token 폐기, reset은 새 epoch/INIT·잔존 effort 제거이며 자동 재무장하지 않는다.
wheel·brake 초기 보호 Actual도 같은 반환 경로를 거쳐야 하고 초기화 명목의 직접 brake 쓰기는 금지한다.

<a id="icd-m7-1j--독립-public-sdk-포트와-남은-서버-경계"></a>

#### M7-1j — 독립 public SDK 포트와 남은 서버 경계

[실행 근거](../test-plan/evidence/m7_carla_1j/README.md)의 포트는 위 계약 중
단일 wrapper owner·Actual/P05 admission·frame별 stage/tick·잔존 setter 제거·모호한 결과 latch를
공개 PhysX3.4 CHECKED SDK에서 구현했다. 입력은 합성 Actual fixture이며1c `FakeProbe`
경계 뒤에서만 실행한다. 실제 native8-role 반환·CARLA RPC에 연결한 것은 아니다.
post-step 관측에는 원래 Actual/provenance·interval·float applied effort·raw signed omega·
PhysX sleep을 보존한다. setter readback을 새 Actual로 생성하지 않는다.
`interval_work_valid=false`이며 위 서버 work receipt 계약을 충족했다고 주장하지 않는다.

SDK snippet은 upY/forwardZ, wheel order RL/RR/FL/FR이므로 프로젝트 FL/FR/RL/RR과
`{2,3,0,1}`로 바인딩했다. SI1500kg/radius0.5m fixture와 합성 pressure table은
mkz_2020 또는 실제 brake calibration이 아니다. 실제 UE에서는 fork·좌표·단위·wheel geometry를
다시 검증해야 한다. 외부 SDK writer는 wrapper만으로 완전히 봉쇄되지 않는다.

world10ms 안에서 차량 내부 `setSubStepCount`를3/10/20/40으로 비교했다.
3에서는 출발 중 rear 음수45/850 FAIL,10/20/40은0/850이었다. 독립 probe 설정은20이며
별도 fail-stop 시험에서 coarse 첫 음수 후 다음 tick 차단을 확인했다. 신호 보정/threshold 완화가
아니며 차량 질량·타이어·gain은 바꾸지 않았다. 이 설정을 CARLA `max_substeps`와 혼동하거나
stock 바이너리의 평지 실패 해결로 수용하지 않는다. 정확도 허용 오차·전체 ODD는 OPEN이다.

1j 초기 UE fork404 이후 Epic 연결과 [UE4.26.2 전체 빌드](../test-plan/evidence/m7_carla_1j_ue_build/README.md)를 완료했다.
후속 [CARLA 기본 빌드](../test-plan/evidence/m7_carla_1j_carla_build/README.md)는 Client/서버 module exit0이다.
[source 실행](../test-plan/evidence/m7_carla_1j_source_smoke/README.md)은 Town03 비렌더링
identity/ego 정상·예외2/2·102샘플10ms를 한정 검증했고 Episode 설정 복원·SIGINT130/자원 정리를 확인했다.
Town10 준비 한도 초과와 Town03 렌더링 SIGSEGV는 미해결이다.
후속 [렌더링 조사](../test-plan/evidence/m7_carla_1j_render_diagnosis/README.md)에서 잘못된
Distance Field 내부 참조를 관측했다. 같은 바이너리에서 source RGB/GT320×240 수신은
GDB1회·native 같은 서버2회 각30쌍으로 한정 확인했지만 crash 원인/재질 준비/완전 delivery는 OPEN이다.
직접 effort 포트·정상 actuation은 NOT RUN이며 기존 센서/시간 계약을 완화하지 않는다.
후속 [준비/반복 검증](../test-plan/evidence/m7_carla_1j_render_followup/README.md)은 ego·RGB/GT가
살아 있는 상태의 shader/Distance Field zero 관측2회와 준비 후 새 native2서버의150tick/30쌍·
정리/복원·SIGINT130을 한정 확인했다. 원래 crash 원인·전체 content/동적 asset 안정성은 OPEN이다.
이 baseline은 NoDrive 최소 포트의 후속 시험 조건이며 정상 actuation/주행 수용이 아니다.
동일 의미를 실제 서버 lifecycle·scene tick
안에 구현·검증하고 brake calibration과 구간 work를 해결해야 정상 주행 gate를 열 수 있다.

<a id="icd-m7-1k--서버-nodrive-0-effort-진단-포트"></a>

#### M7-1k — 서버 NoDrive 0 effort 진단 포트

[설치·구체 RPC 계약](../../tools/carla/m7_nodrive/README.md)과
[실행 evidence](../test-plan/evidence/m7_carla_1k/README.md)에 별도 opt-in 서버 포트를 둔다.
고정 CARLA/UE Linux fork에서 기존4W component를 상속하고, 명시적으로 bind한 ego만
실제 `PxVehicleNoDrive`로 전환한다. stock engine/gear/control 처리는 그 ego에서 제외하며
타이어·suspension·차량 운동은 기존 UE PhysX 한 곳이 소유한다. M6 구현·wire는 변경하지 않는다.

현재 admission은 **합성 CAN/P05 fixture 전용이며 세 Actual이 모두0인 경우만 허용**한다.
원본 receiver·codec을 UE clang10/libc++의 별도 모듈에서 그대로 컴파일해 Actual CAN identity,
CRC·epoch·sequence·source를 검사한다. oldest/source의 전체10ms age30ms·skew10ms 및
exclusive expiry도 별도로 검사한다. nonzero rad/Nm/Pa는 calibration unavailable로 거부한다.
합성 지원 provenance는 실제 Central–Zone–vECU authority가 아니며 이 진단 경로를 정상
8-role 반환으로 수용하지 않는다. command/마지막 control을 새 Actual로 발행하지 않는다.

서버 INIT는 owner key와 명시적 실행 flag를 요구하고 run UUID/session/actor를 바인딩한다.
바인딩 중 legacy 제어·force/velocity/pose·physics·설정/reload·batch·일반 tick RPC를 막는다.
이는 전용 실행 환경의 추가 서버 guard이며 전체 CARLA 인증/격리 수용을 뜻하지 않는다.
`stage` ACK는 미적용, `advance` ACK는 큐 삽입, `receipt`만 physics 종료 관측이다.
frame/ticket은 single-use이며 원래 CAN bytes와 실제 frame·simulation begin/end를 receipt에
보존한다. persistent setter readback은 적용 demand이지 실제 actuator feedback이 아니다.
raw signed wheel ω를 보존하며 `interval_work_valid=false`, substep work observation도 false다.
energy owner를 연결하지 않은 이0 effort 진단만 다음 관측 tick을 허용하며, 정상 energy
receipt가 불완전하면 latch해야 한다는 위 주행 계약을 완화하지 않는다.

진단 clock은 bind 원점1s + frame차×10ms이고 원래 payload source는 불변이다.
실제 simulation 시각을 별도 기록하며 native wall/kernel clock 수용으로 승격하지 않는다.
pause는 pending 폐기·latch, reset은 실제 physics state 재생성·generation 변경·latch다.
physics generation 변경 또는 모호한 post-tick 결과는 다음 tick을 막는다. close로 해당 ego를
종료하고 새 session/INIT를 받아야 다시 진행한다. advance timeout의 자동 재시도는 금지한다.

다음 gate는 readback geometry의 좌표·휠 순서 검증과 근거 있는 brake 모델, nonzero effort,
보호 Brake Actual/raw wheel, 실제8-role interval 연결, solver work/단일 EV 및 wall timing이다.
짧은0 effort 실행은 평지 brake-hold·기존 미세 음수 문제·렌더러 crash 해결의 근거가 아니다.

<a id="icd-m7-1l--rest-geometry와-brake-모델-선택-경계"></a>

#### M7-1l — rest geometry와 brake 모델 선택 경계

[실행·독립 감사](../test-plan/evidence/m7_carla_1l/README.md)에서 yaw0/±90/180 및
yaw37/pitch7/roll−4의5개 INIT 자세를 사용했다. physics enabled·tick 정지 상태에서
reference bone/offset→body→실제 COM→world→actor 및 프로젝트 반사 변환을 대조했다.
FL/FR/RL/RR 순서와 nominal rear-axle rest 중심의 actor 기준 위치 약
`[-1.388633,0,0.359541] m`, wheelbase 약2.86047m·front track 약1.59292m를 확인했다.
이는 **reference/rest geometry**이며 contact patch나 suspension 변위에 따른 실제 wheel center가 아니다.
body에 고정된 nominal rear frame의 초기 근거로 사용하며 동적 기준점/속도 변환은 별도 검증한다.

공개 `VehiclePhysicsControl.center_of_mass`는 `COMNudge`이고 RPC에서 이미 cm→m 변환된다.
관측값 `[0.3,0,-0.2] m`를 실제 COM 위치로 사용하지 않는다. 실제 body local COM은
약`[0.212369,0.000294,0.549693] m`였다. 변환 검사는 float32 계산 오차 예산을 사전 고정했고
센서 validity/freshness epsilon을 추가하지 않았다. nonzero 조향 방향은 NOT RUN이다.

[brake 모델안](../test-plan/evidence/m7_carla_1l/brake-model-proposal.json)은 **미채택**이다.
V1은 기존 M6의 합산0.001Nm/Pa를 명시적인 가상 EV에서4륜 균등 배분하는 제안이며
각0.00025Nm/Pa,200kPa에서각50Nm·1.5MPa에서각375Nm다. 합산 law의 근거는 기존 SIL
정의이고 균등 배분은 새 가상 모델 선택이다. MKZ/OEM 보정이나 M6 응답 수용 승계가 아니다.
이 가상 모델의 명시적 수용 전에는 runtime에 설치하지 않는다.
H1은 유압 pressure 위치/회로 배분·피스톤 면적·마찰·유효 반경·효율·onset의 식별 자료를
요구하는 대안이며 수치는 미확정이다. wheel radius와 max brake800Nm로 이를 대신하지 않는다.
현재 서버는0 Actual만 수용하며 pressure→torque law를 실행하지 않는다.

<a id="icd-4-좌표계와-센서-계약"></a>

### 4. 좌표계와 센서 계약

프로젝트는 x forward/y left/z up, yaw 좌회전+, rear-axle center 기준이다.
CARLA/UE는 x forward/y right/z up이며 센서 frame/time 의미는
[공식 센서 문서](https://carla.readthedocs.io/en/0.9.16/ref_sensors/)를 따른다.
CARLA world를 프로젝트 map으로 반사하는 기준은 `S=diag(1,-1,1)`:
`p_project=S*p_carla`, `R_project=S*R_carla*S`, yaw는 planar 경우 `-deg*pi/180`이다.
속도/가속도는 S, 각속도 같은 axial vector는 `det(S)*S`를 적용하고 deg/s→rad/s 변환한다.
원점·map ID를 manifest에 고정한다. rear axle 위치는 actor origin/COM과 같다고 가정하지 않고
검증된 `T_actor_rear_axle`로 변환한다. sensor extrinsic도 동일 기준으로 합성한다.
body 속도는 회전행렬 역변환으로 얻으며 `speed/radius`는 no-slip 추정이지 실제 wheel 센서가 아니다.

| Stream | 초기 계약 | 확장/금지 사항 |
| --- | --- | --- |
| RGB front | camera ID, frame, simulation timestamp, arrival monotonic, width/height/stride/encoding, intrinsics/extrinsics revision | CARLA BGRA8 원본과 AI용 RGB8 변환을 구분; 원본 timestamp 유지 |
| Semantic Segmentation GT front | RGB와 같은 pose/FOV/resolution·frame key, raw class ID 및 label-map version | 별도 training/evaluation channel/storage; palette image를 class ID로 쓰지 않음 |
| Vehicle State | 해당 WorldSnapshot/ActorSnapshot의 pose, velocity, acceleration, angular velocity·frame/time | 실제 wheel torque/pressure/angle을 차량 속도·마지막 control로 합성하지 않음 |
| 향후 multi-camera/object/BEV/temporal | sensor ID 배열, frame별 completeness mask, source frame 목록, 모델·calibration ID, uncertainty | array index를 camera identity로 사용하지 않음. derived timestamp와 oldest dependency 분리 |

GT topic/파일/포트는 inference runtime 구독 목록에서 제외한다. 객체 GT·semantic GT를
online perception output으로 대체하지 않는다. AI가 받는 관측 RGB/state와 학습 label은
별도 schema/접근 경계이며 실제 분리 검증은 M7-1/M10이다. Temporal history는 run/epoch와
frame gap을 검사하고 reset 시 비운다. 보간/추정 결과는 `estimated` provenance로 별도 전달하며
현재 Drive의 measured input으로 승격할 수 없다.

RGB/GT는 `(run_id, plant_epoch, frame, sensor_id)`로 join한다. callback 도착 순서가 capture
순서라는 가정은 금지한다. GPU camera의 frame 지연은 공식 [synchrony 문서](https://carla.readthedocs.io/en/0.9.16/adv_synchrony_timestep/)에도 명시돼 있다.
bounded queue·대기 시한·누락 mask를 사용하고 가장 가까운 frame으로 대체하지 않는다.
M7-1은 수집 전용 bounded window로 지연 frame을 join한다. startup/drain frame도 누락 통계에
남기며 별도 분모로 보고한다. 주행 모드에서 필수 input 만료/미완성이면 다음 driving tick을
보류한다. GT-only 누락은 dataset sample을 invalid로 만들며 online 주행 입력이 되지는 않는다.

<a id="icd-5-clock과-m7-multirate-개정-m7-1d"></a>

### 5. Clock과 M7 multirate 개정 (M7-1d)

**결정:** 사용자가 world/state10ms + 영상50ms 방향의 다음 작업을 승인했다.
M7-0의50ms world baseline을 아래와 같이 명시적으로 supersede한다. M7-1b의50ms
시험과 M7-1c의40ms stale 거부는 당시 조건의 유효한 과거 증거로 보존한다.
M6 코드/실행 profile/수용 수치와 Drive30ms 한계는 변경하지 않는다.

| 단계 | M7 개정 주기 / 의미 |
| --- | --- |
| CARLA world / Vehicle State | synchronous=true, fixed_delta_seconds=0.01; 매 frame의 새 WorldSnapshot/ActorSnapshot 취득 |
| RGB / Semantic GT | sensor_tick=0.05; world5frame마다 촬영, 원래 frame/time 유지 |
| Planner / Controller | 기존50/20ms; Controller 위상은 영상 frame마다 재시작하지 않음 |
| Zone / Steering·Brake·Drive vECU | 기존10ms; 실제 task/runtime 연동은 후속 |
| Source freshness / native owner guard | 기존30ms 및2ms opportunity/4ms 완료 계약 유지; CARLA tick으로 대체하지 않음 |

단일 Host orchestrator만 tick한다. `apply_batch_sync(..., do_tick=True)`의 숨은 tick,
Traffic Manager/ScenarioRunner의 별도 tick은 금지한다. ScenarioRunner는 기본 시험에서 제외한다.
physics substepping은 max delta0.01s/max steps10으로 설정·readback한다. 이 설정은
서버 내부 적분의 상한이며 클라이언트 substep 관측/API 제공의 증거는 아니다.

향후 functional scheduler의 각10ms 단계 순서는 새 관측 수용→due Controller/기존 Central
배분→Front/Rear 전달·Leaf 작업→외부 actuator 응답/Actual 반환→adapter 검증/apply ACK→
단일 world tick→다음 관측이다. Controller는0,20,40,60ms의 연속 위상을 유지한다.
관측 frame n을 사용한 출력은 다음 interval에만 적용한다. 원천30ms·skew·expiry·interval
coverage와 기존 peer/parent/ACK/RunLease를 모두 검사한다. camera 지연 때문에 같은
snapshot을 새 것으로 재발행하거나 미래 상태를 과거 ECU release에 배치하지 않는다.
이 순서는 **설계**이며 M7-1d에는 ECU scheduler·Actual apply가 연결되지 않는다.

<a id="icd-50ms30ms-충돌의-해소-범위와-남은-gate"></a>

#### 50ms/30ms 충돌의 해소 범위와 남은 gate

기존 [DriveController](../../vecu/drive/drive_controller.cpp)와
[DriveReceiver](../../interfaces/drive/drive_receiver.cpp)는 원천/oldest dependency30ms를
요구한다. 50ms 측정 사이10ms task의 age0/10/20/30/**40**ms는 필연적으로 stale이었다.
EV capability70ms나 M6 MIL speed60ms는 이 계약을 바꾸지 않는다.

이제 state를10ms마다 **실제 새 snapshot**으로 취득하여 이 샘플링 주기 불일치를 제거한다.
state까지50ms로 export/decimate하면 충돌이 남으므로 critical feedback 후보 경로는100Hz를
유지한다. 영상만20Hz다. 100Hz 재발행·sequence 증가·도착 시각 restamp·보간으로 대체하지 않는다.

| 대안 / 상태 | 판단 |
| --- | --- |
| world/state10ms + 영상50ms | **채택**, M7-1d 비주행 수집으로 논리 cadence 검증. 실시간 Drive 적합은 별도 |
| 50ms world 내부의 실제 substep 양방향 연동 | 기존 조건 보존 후보였으나 이번 주기 개정으로 우선순위에서 제외. 패키지에서 구현/입증되지 않음 |
| predictor/독립 wheel model | measured input 대체 불가, 중복 dynamics 금지 |
| freshness30→60ms / 캐시 restamp | 계속 금지 |

10ms 논리 tick도 wall10ms를 보장하지 않는다. sampling 간격+전송/queue/consumer 지연+
clock uncertainty가30ms 안인지 실제 경로에서 측정해야 한다. actor velocity와 `speed/radius`는
실제 wheel angular-speed 센서가 아니므로 Drive 연결에 필요한 wheel 원천은 여전히 미확정이다.
또한10ms interval 안의 새 보호 반영·비가역 CARLA RPC 지연은 native2ms/4ms guard와 별개다.
더 빠른 world 설정만으로 기존 완료 시한이나20ms transport envelope 충족을 주장하지 않는다.
Actual interval support·중복 dynamics/energy·calibration gate도 남는다.

**정상 주행 연결 BLOCKED**를 유지한다. M7-1d 수집기는 static NON_DRIVING fixture이며
논리 cadence·센서 누락·pause/reset 결과와 wall 측정치를 따로 보고한다.

<a id="icd-시간-영역pausereset"></a>

#### 시간 영역·pause/reset

CARLA `frame/timestamp.elapsed_seconds`는 simulation clock이다. 원래 double seconds와
명시적 반올림한 ns를 함께 보존한다. M7-1 tick 검증 tolerance1µs는 부동소수 비교용이며
source-age 여유가 아니다. callback arrival/receive/apply/RPC 시작·끝은 Host CLOCK_MONOTONIC.
UTC는 run label에만 사용한다. 두 clock을 직접 빼거나 nominal10ms를 wall10ms라고 주장하지 않는다.

기존 owner-wire Host는 공통 kernel monotonic·zero offset/uncertainty다. CARLA sim timestamp를
그 domain으로 단순 라벨 교체하지 않는다. functional replay는 별도 simulation clock 모드로
고정하고 wall-time100ms 검증으로 세지 않는다. wall 연결용 acquisition mapping/불확실성
예산과 Target sync는 미확정이며, bridge 도착 시각을 acquisition으로 쓰지 않는다.

pause 시 tick만 멈추고 wall monitor/통신 timeout은 계속한다. 기존 latch/age는 보존한다.
simulation-clock replay의 logical age 정지는 모드로 명시한다. resume은 stale sample으로
NORMAL 복귀하지 않고 해당 기존 재가입/INIT를 요구한다. reset은 새 run/plant epoch,
센서 queue·pending apply·temporal history 폐기, actor handle 재바인딩, ECU의 새 trusted
application Epoch/전체 INIT/arm으로 연결한다. ECU 단독 재가입은 CARLA world를 reset하지 않는다.
snapshot 확인이 불가능한 RPC timeout·부분 apply는 ambiguous로 기록하고 추가 tick을 막는다.
containment는 시뮬레이션 진행 중단이며 물리 차량 정지/안전 성능의 증거가 아니다.

<a id="icd-m7-1b-실행-연결"></a>

### M7-1b 실행 연결

2026-10-23 [수집 근거](../test-plan/evidence/m7_carla_1b/README.md)에서 정적 ego의
RGB/GT/state·50ms tick/원천 metadata·채널 분리·제한된 fault/pause/reset을 검사했다.
서버 포함0.9.16 wheel/별도 venv·fresh client reset 경로를 한정 사용한다. 같은 client native
reload/server crash OPEN은 보존한다. Vehicle State는 actor origin이고 rear-axle calibration은
미확정이다. 이 실행은 외부 Actual bridge·clock mapping/Drive30ms·actuation/energy 수용이 아니다.

<a id="icd-m7-1c-논리-검증-연결"></a>

### M7-1c 논리 검증 연결

2026-10-23 [test-only Actual/fake backend](../test-plan/evidence/m7_carla_1c/README.md)에서
원래 receiver/P05·DriveController를 재사용해 metadata/interval·writer·single-use ticket·
ambiguous apply/tick·중복/재진입 거부와 source-age 경계를 검사했다. Normal/ASan 각39/39.
이 prototype은 정규 runtime/새 wire ABI가 아니다. measurement support metadata는 fixture의
원천 선언이며 기존 CAN command/RunLease expiry와 같은 것으로 바꾸지 않았다. 실제
peer/parent/authority transport·CARLA 접근 제어·주행 calibration은 미구현이다.
이1c 당시50ms 조건에서는 원래 Drive가40ms-old local sample로 보호를 선택해 충돌이 남았다.
현재 M7 주기는 아래1d 개정을 따르며1c의 과거 조건/결과는 보존한다.

<a id="icd-m7-1d-실행-연결"></a>

### M7-1d 실행 연결

[10ms world/state·50ms 영상 비주행 근거](../test-plan/evidence/m7_carla_1d/README.md)에서
main state600/600·영상각120/120, live pipeline drop·실제 pause/fresh-client reset을 확인했다.
첫 camera 간격60ms는 startup 변동으로 남겼다. 마지막50startup tick에서 안정 위상을 확인하고
main 위상을 고정했다. 주행 센서 readiness는 첫 callback 수신만으로 성립하지 않는다.
최종 nominal RTF0.764923, pause 제외 snapshot 완료 간격>30ms12/798로 wall100Hz는 미충족이다.
실제 ECU clock/Drive 연결은 NOT RUN이며 논리 source-age replay로 대체하지 않는다.
정리 후 SIGTERM 중 native SIGSEGV/139는 OPEN-M7-1D-01이다. 기존 native crash OPEN도 유지한다.

<a id="icd-m7-1e-원천clock비용-진단-연결"></a>

### M7-1e 원천·clock·비용 진단 연결

[진단과 대안](../test-plan/evidence/m7_carla_1e/README.md)에서 공식0.9.16 source와 설치된
wheel RPC를 대조했다. `get_wheel_pitch_angle`은 physics on이면 물리 wheel 회전각,
off이면 animation pitch다. frame/time 없는 float RPC이며4wheel 개별 호출이다.
새 snapshot 사이 tick을 보류한 unpowered probe에서 유한 값을 얻었지만, 유효 회전 자극·
wrap/slip·구간 각속도의 기존 Drive sensor 적합성은 NOT RUN이다. v/r 대체는 계속 금지한다.

`platform_timestamp`는 WorldObserver 직렬화 시작의 FPlatformTime이며 개별 물리 취득
시각과 동일하다고 가정하지 않는다. Host monotonic과 약2.4s 차이가 있었고, 전체 진단
구간에서 하나의 상수 offset은 관측 bracket과 불일치했다. arrival restamp/zero offset은 금지다.
render/audit 분리 결과 metadata만 수집하면 RTF1.014~1.033이었으나 max gap26.654ms이며
실제 ECU/통신·source-age 수용은 미검증이다. 빈 서버도 종료139가 재현돼 OPEN을 유지한다.

다음 우선 후보는 명시적 **functional simulation clock 모드 설계**다. 기존 wall runtime에
sim timestamp를 넣거나 기존2ms/4ms guard의 clock을 몰래 바꾸지 않는다. 전체 ECU/권한/
lease/expiry·Actual 경로와 논리 barrier를 별도 opt-in으로 설계하고,30ms 값·원천 dependency를
보존해야 한다. 해당 결과는 wall deadline/100ms 검출 수용을 대신하지 않는다.
CARLA를 영상/환경용으로만 쓰고 기존 SIL이 motion을 소유하는 대안은 현재 소유권 변경을
요구하므로 미채택이다.1e 당시 정상 주행·새 backend·clock mode 구현은 NOT RUN이었다.

<a id="icd-m7-1f-functional-clockshadow-계약과-구현"></a>

### M7-1f functional clock/shadow 계약과 구현

[구현/시험](../test-plan/evidence/m7_carla_1f/README.md)은 `STRATADRIVE_M7_FUNCTIONAL_TESTS=ON`
및 native CLI `--functional-shadow`로만 실행한다. default는 OFF이며 production wire ABI,
M6 실행 profile, 세션·lease 상수, 기존 wall watch를 변경하지 않는다.

| 경계 | 이번 구현 / 제한 |
| --- | --- |
| 시계 | run/application/plant scope와 별도 domain `0x4d3746554e435449`; native 시간은 CARLA snapshot의 원래 elapsed seconds를 ns로 반올림. nominal grid나 도착 시각으로 치환하지 않음. 원래 seconds·platform·Host monotonic도 raw trace에 별도 저장 |
| tick 순서 | snapshot → frame/scope/time 검사 → 해당 시각까지 native jobs →8역할 처리 barrier → NON_DRIVING next-frame permit → Python tick1회 → 원래 snapshot 확인. 중복/skip/rollback/domain 오류는 해당 instance를 latch하고 재시도 금지 |
| native 실행 | 같은 프로세스/단일 thread의 실제 Central·Front/Rear Zone·Steering/Brake/Drive/BMS/Power. 기존0.2ms ingress·1ms physical fixture job grid, Controller root20ms, Host10ms child allocation, leaf10ms/BMS20ms를 유지. 이 grid는 Host 실행 기회/4ms deadline 판정이 아님 |
| 세션/권한 | 실제8역할 ParticipantPort의 Prepare/INIT/Release ACK를 원래 SessionCoordinator가 수용한 뒤 원래 RunLeaseIssuer가 발급. 각 역할에 개별 RunLeaseGate, global60ms·source30ms·원래 expiry 유지. Central self-credit만 local binding; 다른 역할의 제어/ACK/lease는 v1 codec 왕복, normal 경로는 native typed queues. SOME/IP/프로세스 분리 시험 아님 |
| Actual | native physical fixture→vECU→Zone→Central 실제 반환 경로. armed 구간에3Actual의 원래 source age+다음10ms<=30ms/skew<=10ms 검사. 이것은 **source-only fixture coverage**이며1c의 source/oldest/expiry provenance·full apply admission을 대체하지 않음 |
| plant 책임 | 기존 PhysicalOwner를 `simple_vehicle=false`인 stationary actuator/electrical 시험 fixture로만 재사용. fixture wheel=0; CARLA 측정으로 위장하지 않음. CARLA는 별도 physics-off ego, apply0. 실제 backend 분리/물리량/energy 결합은 아직 구현하지 않음 |
| pause/실패 | Python이 tick을 멈춘 동안 native process에도 STEP을 보내지 않아 logical time·lease를 갱신하지 않음. 별도10s IPC wall timeout은 시험 hang containment용. lease 갱신 상실·Actual/역할 누락은 native 검증 또는 barrier에서 차단. wall 실행에서는 기존 monitor가 계속 동작한다는 계약 유지 |
| reset | fault latch를 같은 instance에서 해제하지 않음. trusted caller가 새 scope·새 process/object를 발급하고 INIT부터 재시작. native 새scope/oldscope 거부를 검증했으나 live world reset·영속 epoch store 연결은 NOT RUN |

**해결 범위:** CARLA의 wall 처리 지연과30ms source-age를 혼용하던 문제에 대해, 요구값을
보존하는 별도 기능 검증 경로를 구현했다. 원래 native ECU/권한 API에 동일 logical time을
공급할 수 있음을 실제 actor 경로에서 확인했다. CARLA의 vehicle/wheel sensor나 Actual actuation이
이 경로에 연결된 것은 아니다. 실제 wheel 원천·source/oldest dependency·actuator 분리·calibration이
준비되기 전 정상 driving permit은 구현하지 않는다. wall mapping과2ms/4ms 검증은 별도 gate다.

<a id="icd-m7-1g-wheel-검증-계획"></a>

### M7-1g wheel 검증 계획

**계획을 실행한 결과:** [M7-1g 원본/실패/근거](../test-plan/evidence/m7_carla_1g/README.md).
0.9.16의 `get_telemetry_data().wheels[].omega`가 직접 PhysX rad/s를 제공함을 확인했다.
이 입력에는 pitch 차분·unwrap 후보를 사용하지 않는다. 기존1e/1f의 당시 조사 결과는 보존한다.

| 항목 | 이번 결정과 한계 |
| --- | --- |
| 원천 | physics-on,4wheel을 한 RPC/scene read lock으로 읽음. RPC payload에는 timestamp/frame 없음. 전용 single tick owner가 snapshot 전후 동일 frame/time을 확인하고 source=oldest=원래 elapsed ns로 결부 |
| identity | trusted run/application/plant/actor·functional clock 고정. 원래 frame을 sequence로 사용,32bit 범위 밖 거부. 네트워크 인증이나 서버 timestamp 확장을 구현한 것은 아님 |
| ECU 입력 | 뒤쪽 index2/3 산술평균 → 기존 LocalSensors → DriveActual CAN/P05 → Rear → Central. 실제 비영 wheel 입력/원래 source/CAN0.01rad/s 양자화를 확인. rear drivetrain calibration을 의미하지 않음 |
| multirate | native subjob 시각보다 미래인 sample은 최대2개 queue에서 보존. 소비 시각으로 restamp하지 않음. ns grid 오차 때문에 pending을 덮어쓰던 첫 live 실패를 수정·회귀 검증 |
| 유효성 | 결측·scope/actor/frame/source 불일치·NaN·range·rear 음수 거부. 평지 접지 중 미세 음수로 native 연결 실패가 남음. abs/epsilon/clamp로 원래 전진 전용 계약을 완화하지 않음 |
| 실제 검증 | 내리막400tick 중396개 wheel Actual 반환·322개 armed fixture frame, 최대 wheel source age10ms. pause250ms와 duplicate 후 tick 차단. 무동력 중력 이동이며 정상 control actuation 아님 |
| ownership | CARLA는 motion만 관측, native torque/steer/pressure·전기는 여전히 시험 fixture. 에너지 입력 wheel0을 실제 CARLA energy로 사용하지 않음. CARLA apply0이며 정상 driving CLI 없음 |

`telemetry.torque`는 DebugWheelTorque이며 실측상 `-long_force×radius`와 일치한다.
모터축 Drive Actual로 사용하지 않는다. 직접 omega는 구간 각도 차분의 aliasing 문제를 피하지만,
이 결과가 역회전/정지 잡음/슬립/전체 운행 범위 calibration을 모두 해결하지는 않는다.

1g 이후 signed wheel validity와 actuator/전기 포트 분리는 아래1h를 따른다.
full Actual provenance→apply ACK→tick 및 원래
interval expiry 검증이 끝나기 전 정상 driving permit은 없다. 패키지 직접 torque 포트가 확인되지
않았으므로 검증 가능한 역변환과 서버 확장안을 비교한다. source build는 별도 범위다.

<a id="icd-m7-1h-signed-validity와-actuatorelectrical-포트"></a>

### M7-1h signed validity와 actuator/electrical 포트

[구현·실행 근거](../test-plan/evidence/m7_carla_1h/README.md).
`--external-wheel-plant`는 M7 전용 ActuatorElectrical을 선택하며 기존 PhysicalOwner를 병행하지 않는다.
Steering/Brake/Drive 응답과 EvPowerModel을 소유하고 SimpleVehicle/VehicleEvModel을 사용하지 않는다.
파라미터는 기존 functional fixture의 명시적 재사용이며 CARLA 차종 calibration이 아니다.

| 포트 | 계약 / 현재 상태 |
| --- | --- |
| signed wheel 평가 | 기존 accepted 값은 유지. rear 음수 중 abs<0.005rad/s인 zero-bin은 SubResolutionNegative 진단으로만 분류하고 forward 값은 unavailable. 기존0.01rad/s wire resolution을 noise 허용값으로 사용하지 않음. 평지 일반 연결은 FAIL 유지 |
| ECU wheel | 원래 sample·rear 평균·source/frame/model identity, 기존 source-age 유지. 값이나 시각을 소비 시각에 맞춰 고치지 않음 |
| electrical wheel | 원래 acquisition 최대5개 history에서 각1ms 구간 begin 이전 최신 값 선택. ZOH 입력이며 미래 endpoint 사용 금지. 기존30ms age/10ms skew 유지 |
| actuator output | leaf/type·application·source 검증 후 기존 물리 응답 모델에만 적용. fresh old/new application mismatch·잘못된 시각/값 거부. no-actuation publication은 watchdog을 갱신하지 않음 |
| commit/fault | actuator·전기·Battery·출력 cursor를 후보 상태로 계산, 전체 성공 후 commit. 실패 시 센서 unavailable·latch·추가 tick 거부. 모델 상태 일부만 전진시키지 않음 |
| energy audit | 각 구간 Tactual×ω(begin)×dt 및 source/oldest/누적을 출력. `MODEL_ZOH_UNAPPLIED`, `carla_work_valid=false` 고정. CARLA apply/receipt가 없으므로 실제 차량 work/회생/에너지 수용으로 사용 금지 |

1h는 실제 wheel을 전기 **예측 모델**에 공급하는 포트 분리까지 구현했다. CARLA 실제 물리 work를
받는 IntegratedMotorWork 연결은 아직 없다. 모델 파라미터/응답 budget의 CARLA 동등성도 미검증이다.
1i의 직접 wheel effort 확장안은 위3절을 따른다. full Actual provenance/apply ACK/interval work
연결은 후속이며 M6 계약은 변경하지 않는다.

<a id="icd-m7-1i-정지-부근-validity-판단"></a>

#### M7-1i 정지 부근 validity 판단

**숫자 epsilon은 채택하지 않는다.** 기존 평지 trace는 자유 낙하·접지 중이고 Brake Actual이
CARLA에 적용되지 않았다. 음수74/400개의 관측 상한은 센서 오차 bound가 아니며, 현재 RPC는
PhysX sleep/접지 제약 상태도 제공하지 않는다. actor `is_active/is_dormant`로 대체할 수 없다.
upstream PhysX에는 brake로 회전 부호가 바뀔 때 wheel을 물리적으로 lock하는 처리와 sleeping
차량의 내부 속도를0으로 만드는 처리가 있다. 이는 **물리 solver 동작**이지 client의 음수→0 보정
허용이 아니다. 현재 바이너리의 미세 음수 원인이나 brake 적용 후 정상성을 증명한 것도 아니다.

후속 순서는 실제 보호 Brake Actual 적용 → 원래 wheel·contact/sleep·frame·receipt 관측 →
정지/출발/정지 반복 시험이다. 음수이면 계속 unavailable/latch하고 tick을 정지한다.
exact0 또는 원래 전진 범위의 측정만 수용하며 warmup을 명목으로 음수 구간을 숨기지 않는다.
이 경로로도 실패하면 forward ODD와 측정 불확도를 포함한 별도 requirement revision이 필요하다.
이번 단계에서 M6 ODD·codec·source-age·reset 증거 조건을 바꾸지 않았다.

<a id="icd-m7-1m--수용된-v1-가상-ev--격리-nonzero-진단"></a>

### M7-1m — 수용된 V1 가상 EV / 격리 nonzero 진단

[승인 모델](../../tools/carla/m7_nodrive/virtual_ev_v1.json)과 [실행 근거](../test-plan/evidence/m7_carla_1m/README.md).
사용자가 V1을 수용했다. 이는 **가상 모델 선택**이며 실제 MKZ 유압 식별이 아니다.
기존1l의 DRAFT artifact는 당시 상태로 보존한다. 별도 `-StrataM7V1Probe`가 있어야 하며
zero-only flag와 동시 지정은 거부한다. owner/run/session 외 bind에 정확한 모델 SHA256이 필요하다.
모델 값은 서버가 설치 시 생성한 상수이며 client가 승인/계수를 선언해 교체할 수 없다.

| 입력·범위 | 승인된 V1 법칙 |
| --- | --- |
| equivalent angle ±0.3rad, 프로젝트 좌+ |1l 실측 front track/wheelbase로 이상 Ackermann, UE 우+는 음수, rear0 |
| aggregate signed motor −200..300Nm | front0, rear각T/2. 별도 gear/lag/filter 없음 |
| Pressure Actual0..1.5MPa | 합산0.001Nm/Pa,4륜 각25%의 nonnegative brake capacity.200kPa→각50Nm,1.5MPa→각375Nm |
| geometry/상한 | 실측 mass1696kg·wheel bone/COM x,y offset·radius.355m·front steer/각800Nm brake와 정확히 일치해야 함. 변경 asset은 거부 |

검사된 원래 CAN/P05 Actual에서만 mapping한다. 원래 native receiver의 mode/source/age/expiry를
통과해야 하며 pressure/drive/steer 초과를 clamp하지 않는다. LocalProtection Brake Actual은 센서 보고의
원래 mode를 보존한다. 합성 test fixture이며 실제8-role 보호 authority를 증명한 것은 아니다.
Nm는 UE kg·cm²/s²로10000배, rad는 그대로 float32 setter에 전달한다. pre-physics에서12개 setter를
한 번 적용하고 post-physics에서 같은 float32 demand를 검증·receipt에 남긴 뒤 모두0으로 지운다.
후속 describe의0은 setter 제거 증거이며 solver에 실제 적용된 brake 반력의 측정값이 아니다.
pause/reset은 nonzero pending도 폐기·latch한다. 다음 tick이나 자동 재무장으로 이어지지 않는다.
clock schema 이름은 기존 `m7-zero-probe-logical-frame`을 유지하며 wall authority를 뜻하지 않는다.

실제 두 새 서버에서 각1,621receipt·nonzero1,601개와 출발/감속/정지/hold/release/좌우 조향을
관측했다. hold100/100frame exact wheel0이지만, 출발/주행의 rear 음수로 각487frame은 native forward
unavailable이다. 음수는 최대 약−7.4rad/s로 작은 센서 epsilon으로 처리할 근거도 없다.
이 diagnostic에서는 native sensor 입력/8-role loop를 연결하지 않고 원래 음수까지 관측했다.
정상 native 경로라면 unavailable/latch·다음 tick 차단 계약이 유지된다. **forward gate FAIL**이다.
내부 적분 분할 후보 비교는 후속이며 world/ECU rate·30ms freshness를 바꾸는 해결안이 아니다.
solver 구간 work는 미관측, `interval_work_valid=false`; 전기/SOC/회생 수용과 정상 주행 permit은 없다.

<a id="icd-m7-1n--별도-내부20분할-수치-진단"></a>

### M7-1n — 별도 내부20분할 수치 진단

[동일 입력 대조·원본 실패](../test-plan/evidence/m7_carla_1n/README.md).
`-StrataM7V1Substeps20`은 V1 flag와 함께 지정하는 별도 서버 진단 옵션이다.
client가 count를 전달하는 actuation API를 만들지 않는다. 기본 asset low/high3/1·threshold5m/s는
유지하고, 후보에서만 low/high20/20을 NoDrive wheel sim data에 설정한다.
threshold 양쪽에서20이므로 원래10ms world step 내부 분할이다. wheel/frame/source를 추가 생성하거나
Controller20ms/Zone10ms·Drive30ms freshness·Actual expiry를 바꾸지 않는다.
receipt의 numerical profile·실제 live low/high/threshold를 보존하고,20/20 일치 여부도 pre/post에 검사한다.

동일 원래 CAN/P05/Actual·V1 law·world 설정에서 기본487frame rear 음수가 재현됐고,
20분할 새2서버는 각각3frame으로 감소했다. launch 첫 tick의 약−.256rad/s는 여전히 unavailable이다.
입력과 원래 음수를 보정하지 않았으며 이3frame을 startup 면제로 처리하지 않는다.
**20분할 정상 profile은 미채택, native gate FAIL**이다.40분할이나 기존 actuator owner의 원래
Actual trajectory 분리 시험은 후속이다. adapter에서 응답 ramp/filter를 추가하지 않는다.
전체 ODD/실제8-role/work/전기/wall 수용을 이 대조 결과로 대체하지 않는다.

<a id="icd-6-결정과-미결정"></a>

### 6. 결정과 미결정

**M7-1o 후속:** [원인·검증](../test-plan/evidence/m7_carla_1o/README.md)에서 기존20분할의
출발 음수는 저속 tire 반력과 명시적 wheel 적분의 진동으로 확인했다. 정착/기존 response 모델
입력/40·80분할도 FAIL이며, 물리 계수 변경 없이320분할을 후속 격리 통합 후보로 사용한다.
world10ms와30ms freshness는 그대로다.160/320/640 비교는 측정된 민감도이며 전역 정확도 수용이 아니다.

원천 정정: 기존 `getWheelRotationSpeed()`/`omega_rad_s`는 이 fork의 `mCorrectedWheelSpeeds`다.
무구동·무제동 저속에서는 rolling speed 혼합이 가능하므로 항상 내부 solver ω라는 해석은 정정한다.
과거 원본/FAIL은 보존한다. 새 `solver_omega_rad_s`/`PhysX3.4.mWheelSpeeds.direct.v1`는
pinned UE header의 serialization accessor로 `mWheelSpeeds`를 직접 읽은 동일 post-physics
frame 관측이다. engine 수정·v/r 재구성·clamp·timestamp 재발급이 아니다. 향후 native bridge는
이 source를 명시적으로 요구하고 source 부재·비유한·rear 음수에는 unavailable/latch를 유지한다.
공개 보정값으로 fallback하지 않는다. 기존 M6 CAN/P05 wire나 native 요구사항은 바꾸지 않는다.

최종320분할의 새2서버 stress와 response 입력은 각각1,621frame/4wheel 직접 solver 음수0이다.
내부 앞바퀴 callback의 미세 음수는 보존하며 모든 substep의 무음수/전체 ODD를 주장하지 않는다.
callback은 생략될 수 있어 `interval_work_valid=false`와 solver work/단일 EV gate는 유지한다.
native8-role full Actual/authority·wall2/4ms는 미연결·미수용이다.

**M7-1p 센서 반환 경계:** [실행 근거](../test-plan/evidence/m7_carla_1p/README.md).
별도 opt-in local bridge는 bind의 run UUID/session/actor/physics generation/model/profile을 고정하고,
post-physics receipt의4wheel 직접 source·순서·frame·ticket·구간 연속성을 검사한다. 공개
`omega_rad_s` fallback은 없다. CARLA world snapshot은 같은 frame/원래 simulation-end time으로
교차 확인한다. receipt RPC보다 episode stream이 늦을 수 있어 최대10s wall 동안 **조회만** 기다린다.
timeout/skip이면 latch한다. 이 timeout은 functional harness의 수신 한도이며30ms source age나
native wall deadline 변경이 아니다. 기다리는 동안 tick/advance 재시도·restamp는 없다.

센서 acquisition은 원래 simulation-end seconds의 ns 반올림이며 frame은 원래 acquisition sequence다.
기존 M7 native fixture의 scope `(1,42,7)`/clock domain은 fresh process마다 새 INIT로 시작한다.
CARLA run/session/generation은 그 외부의 신뢰된 local binding으로 보존한다. synthetic Actual의
`m7-zero-probe-logical-frame` 시각이나 session을 native authority로 간주/변환하지 않는다.
기존 native rear 평균·CAN0.01rad/s 양자화·vECU→Rear→Central 반환을 사용하고, pending sample은
자기 시각 이후 job에만 공급된다. Controller20ms/Zone·vECU10ms/Drive30ms를 유지한다.

실제320분할 step/response 새2서버는 각각1,621관측/1,609반환·다음 구간 끝 age 최대20ms였다.
native 반환은 **sensor-only shadow**다. actuator/전기는 stationary native fixture이고
차량 motion 적분은 비활성이다. 이 fixture의 torque/SOC를 CARLA effort/work로 주장하지 않는다.
native barrier 성공만 다음 진단 tick 진행을 허용한다. 부재/비유한/범위 초과/원천 불일치/후륜 음수는
다음 tick을 막고 backend pause·persistent setter clear·latch로 이어진다. 아주 작은 음수도 native가
거부한다. pause/reset/close는 bridge를 폐기하며 cached receipt로 재무장하지 않는다.
실제20분할 음수와 snapshot 누락 주입에서 containment를 검증했다. 실제8-role full Actual의
authority/interval→NoDrive 적용, solver work/EV, wall 성능은 별도 후속 gate다.

**M7-1q native Actual 적용 경계:** [구현·실행·실패](../test-plan/evidence/m7_carla_1q/README.md).
별도 `-StrataM7NativeProbe -StrataM7V1Substeps320`로만 활성화한다. 기존 zero/V1 합성 진단과
상호 배타적이며 일반 `stage`는 거부·latch한다. `stage_native`는 반환된 원본 CAN/P05와
native authority를 검사한 뒤 single-use ticket을 발급한다. `advance` 한 번에 한 구간만 적용하고
post-physics receipt/clear 후 다음 관측으로 진행한다. 일반 CARLA writer/tick RPC는 계속 차단한다.

- 원본 native mailbox의 **수신 완료 hook**에서 Zone→Central Actual과 Zone→vECU 명령/permission을
  읽기만 한다. 메시지를 pop/대체/재발급하거나 ACK를 대신 만들지 않는다. current receiver 표본의
  epoch/sequence/source 및 Actual.causal_sequence에 맞는 원본 command를 선택한다.
- 실제 coordinator가 수용한8개 Release ACK,7개 remote RunLease 및 Central local credit을 포함한
 8-role service/credit mask를 전달한다. server는 original owner-wire route/domain/CRC32C와
  session plan/ACK·동일 credit/60ms expiry를 검사한다. CRC는 인증이 아니다. owner key와 fresh local
  process의 신뢰 경계 안에서만 사용하며 Host IPC/SOME-IP 또는 Target authority로 전용하지 않는다.
- CARLA run UUID/session/actor/physics generation/model/profile은 외부 binding으로 고정한다.
  native application42/fixture scope(1,42,7)는 fresh process의 실제 INIT로 시작한다. native 시각은
  동일 snapshot의 원래 simulation elapsed seconds를 ns 반올림한 `m7-native-simulation-elapsed`다.
  기존 합성 profile의 logical-origin 시각은 사용하지 않는다. 이전 binding의 packet 재사용은 금지한다.
- 새 모드만 최초 관측+8ms에 INIT을 요청한다. 현재 native owner 순서에서 enable은+29ms,
  Controller/management 첫 위상은 enable+14ms다. 주기20/10ms·IO200µs·physical1ms 및 모든
  freshness/expiry는 그대로다. 기존 immediate INIT은 Actual 반환 후 부모 명령의 여유가5ms인
  구간에서 다음10ms를 덮지 못했다. offset은 실제 job의 실행 시점을 바꾸며 source를 재발급하지 않는다.
- Actual3개는 원본 receiver로 decode/P05/cursor 검사하고 source·Drive wheel의 **구간 끝 age≤30ms**,
  skew≤10ms를 요구한다. Normal/Degraded NormalPath만 정상 적용하며 causal command/root age30ms,
  dependency70ms, 원래 context expiry를 **전체 다음10ms**에 검사한다. 원래 BMS permission의
  source50ms/dependency70ms·parent와 grant expiry·Drive capability quality도 검사한다.
  동일 held packet은 새 표본으로 수신 처리하지 않고 기존 receiver의 current_sample로 검증한다.
- 최초4tick은 native Actual이 아직 없는 명시적 INIT 무입력 관측이다(최대80ms, 정상 권한 없음).
  이후 실제 Init/NoAcceptedInput Actual만 torque0 조건으로 적용하며 angle/brake를0으로 만들지 않는다.
  최초 정상 진입 후 INIT/empty로 돌아가거나 누락을 cache로 채우는 것은 거부·latch한다.
- native external owner가 기존 actuator 응답과 전기 ZOH **예측**만 소유하고 차량 운동은 CARLA만 적분한다.
  모델 전기는 적용 receipt/solver 적분 work를 정산한 값이 아니다. `MODEL_ZOH_PREDICTION_NOT_CARLA_WORK`,
  `interval_work_valid=false`이며 일반 정상 주행/에너지 수용 flag는 열지 않는다.

최종 새 서버400tick/319정상 권한 구간 및 독립 wire/physics 검사에서 원래 source의 구간 끝 age는
최대20ms다. 최소 명령 expiry 여유1ns는 기존 exclusive expiry 경계이며 wall jitter나 불확실성의
여유가 아니다. pause/reset/오류는 setter clear·latch 후 fresh process/새 INIT를 요구한다.
현재 시험은 고정 VehicleRequest(0.2m/s², curvature0.02/m)의 제한된 출발이며 일반 시나리오·센서
영상/AI·전체 ODD·wall deadline은 포함하지 않는다. 다음은 solver work/단일 EV·원자적 실패 처리다.

<a id="icd-m7-1r-완전한-solver-work와-단일-ev-정산"></a>

#### M7-1r: 완전한 solver work와 단일 EV 정산

[실행 근거](../test-plan/evidence/m7_carla_1r/README.md). `-StrataM7SolverWork`를 native/320분할
프로필에 추가한 경우만 아래 계약을 사용한다. 기존1q 모드는 ZOH 예측/`interval_work_valid=false`를
유지한다. M6 코드·EV 계수·에너지 오차 수용 기준은 변경하지 않는다.

- **관측점:** pinned PhysX3.4 `updateNoDrive` 진입/정상 종료 및 sleeping-return, 각320개
  `integrateNoDriveWheelSpeeds` 호출 전후의 raw `mWheelSpeeds`, 실제 drive/brake/tire/damping,
  원래 float solver dt를 기록한다. ABI1·단일 호출·4wheel·순서/개수·overflow·전후 연속성·setter·
  최종 direct getter를 검사한다. tire callback 생략을 work 누락으로 추정 보완하지 않는다.
  sleeping은 실제 해당 return의 witness와 torque/steer/최종 wheel0이 함께 있어야0 work다.
- **정의:** wheel별 `W = Σ τ_drive,Nm × ω_solver,after,rad/s × dt_solver,s`인 signed discrete
  motor work다. NoDrive의 구동 wheel 회전각 적분에 쓰이는 post-solver ω를 사용한다. torque0의
  렌더링용 회전 보정은 motor work0을 바꾸지 않는다. UE torque의cm²→m² 변환은10000으로 나눈다.
  프레임 끝 속도의 ZOH나 임의 변환 계수를 사용하지 않는다. 이 정의는 chassis/tire/brake까지
  포함한 전체 기계 에너지 보존·연속시간 적분 정확도·OEM 효율의 검증을 뜻하지 않는다.
- **범위:** V1 rear50:50의 모터 축 속도는 후륜 평균이다. 관측된 구동 substep마다 그 평균이
  원래 전진 모델의0..100rad/s 범위를 벗어나면 EV 연결을 거부한다. 음수 절댓값/epsilon/clamp는 없다.
  마찰 brake work는 DC/회생 work에 합치지 않는다. 실제 회생/일반 제동 scenario는 후속 검증이다.
- **원천/시각:** receipt의 UUID/session/actor/generation/frame/ticket 및 원본 Actual proof를
  유지한다. `solver_work.source=PhysX3.4.NoDrive.integrator.postOmega.v1`; 정산 끝은 원래 CARLA
  elapsed seconds를 ns 반올림한 `work_end_ns`다. 기존 `logical_end_ns=begin+10ms`는 명목 끝이며
  float clock으로1ns 차이 날 수 있다. 어느 경우에도 wheel/CAN 취득 시각을 고쳐 쓰지 않는다.
- **정산:** native `--native-solver-work`는 완전한 receipt를 검증한 후 기존 EV owner 하나의
  `step_integrated_motion`만 호출한다. 같은 owner의 ZOH `step`은 호출하지 않고 SimpleVehicle도
  만들지 않는다. scalar wheel은 구간 시작의 원래 취득 표본이다. torque는 서버가 실제 setter에
  적용한 Nm witness이며 source는 그 apply의 원래 frame begin, oldest는 원본 Actual/wheel 의존성이다.
  원본 CAN의 source/sequence는 proof에 그대로 남으며 apply witness가 새 CAN Actual을 만들지 않는다.
  최초 empty INIT의0 setter도 명시적 무입력 관측이며 정상 권한/가짜 Actual이 아니다.
- **다중 주기:** 원래320개 discrete work를 원래 frame begin/end의 동일 ordinal bin에 배분하고,
  native1ms 경계와 겹치는 비율만 각 전기 구간에 보수적으로 배정한다. 원래 solver dt와 frame 전체
  work 합은 보존하며 이 배분값을 새 wheel 취득으로 사용하지 않는다. 끝의1ms 미만 잔여도 그 프레임
  안에서 정산한다. actuator 응답 job·Controller20ms·Zone/vECU10ms·30ms age/10ms skew는 유지한다.
- **commit/중단:** 모델 상태와 cursor는 frame checkpoint를 두며 중간 실패 시 해당 frame의
  actuator/EV 모델 상태·장부를 복원하고 sensor를 무효화한다. 이미 진행된 CARLA physics나 내부
  native 메시지를 되돌릴 수 있다는 뜻은 아니다. 실패한 rig는 폐기하고 fresh process/새 INIT가 필요하다.
  서버는 유효 work receipt 뒤 `settle_work` 전까지 다음 stage를 차단한다. 인증된 단일 local adapter가
  frame/ticket/원래 끝 시각·누적 motor J·에너지 balance를 제출하며 누락/중복/불일치는 clear·latch다.
  누적 J 비교 허용치는 binary64 합산 오차 범위이고 EV의 기존0.00072J balance 기준은 유지한다.
  ACK는 신뢰된 local owner의 결과 보고이며 독립 원격 증명/암호 인증 protocol로 전용하지 않는다.

이 opt-in receipt만 `interval_work_valid=true`다. `normal_driving_enabled=false`는 유지한다.
UE 원본 source/static archive는 보존하고, hash로 고정한 외부 copy에 읽기 전용 observer를 삽입하여
PhysXVehicles module만 별도 빌드한다. 원본 module backup/restore와 실행 binary hash를 기록한다.
Wall2/4ms·계측 비용·renderer·다중 ODD·실차 calibration·signed 회생/일반 정지는 미수용이다.

<a id="icd-m7-1s-서버-lifecycle-종료-경계"></a>

#### M7-1s: 서버 lifecycle 종료 경계

[종료 조사/검증](../test-plan/evidence/m7_carla_1s/README.md)의 pinned source patch는
secondary-server I/O pool stop/join 뒤 acceptor/session을 해제한다. 취소/실패 accept를 재등록하지
않고 context reset을 제거한다. 반복 Stop/소멸과 Router 자기 참조를 처리한다. 외부 생산자를
먼저 정지한 lifecycle owner가 호출하며, worker 내부 Stop·동시 lifecycle 호출·같은 Router의
재시작은 지원하지 않는다. 새 서버/Router로 다시 시작한다. M7 frame/pause/reset·Actual/EV 계약은 그대로다.

시험 runner는 포트 개방뿐 아니라 read-only client의 첫 유효 world snapshot까지 확인한다.
기존180초 startup deadline 안의 준비 절차이며 tick/actuation을 수행하거나 sensor timestamp를
재작성하지 않는다. 실제 probe RPC10초·SIGINT 종료30초, Drive30ms·expiry 기준은 유지한다.
probe 성공이어도 서버−11/강제 종료는 FAIL이다. cold-load 중단의 종료 한도는 별도 미수용이다.

**결정:** actual-only 경로·단일 actuation writer,10ms world/state·50ms 영상·단일 tick owner,
20/10ms 기존 rate·freshness/권한 보존, 중복 motion/actuator/energy 금지, metadata/좌표 의미,
GT 격리, pause/reset containment, M7-1 비제어 관측 범위. 별도 opt-in functional clock/8-role
barrier는1f, 직접 omega→native Actual 반환은1g, actuator/electrical 분리·원래 wheel 기반 ZOH는1h에서
한정 검증했다.1i는 직접 wheel effort 확장안을 우선 후보로 결정하고 수학/거부 경계를 오프라인
검증했다.1j는 공개 NoDrive SDK에서 합성 Actual의 물리 적용·single-use/pause 경계를 한정 검증했다.
정지 sensor의 임의 오차 보정은 미채택이다. 정상 CARLA driving 수용은 아니다.

**미결정:** smoke 외 server/client 조합의 안정성, V1 외 vehicle geometry/실차 역변환 calibration,
wheel 정지 잡음/전체 ODD validity·wall clock mapping·일반 시나리오의 Actual interval·native wall guard 연동, 일반 주행/회생의 energy telemetry,
Host–Target transport/배치, M10 AI shape/history. 소유자·gate는 기존 TBD-02/03/04/07/09
(energy는 기존 TBD-13)이며 [로드맵](../roadmap.md)에 연결한다. 이번 문서는 주행 통합 승인이나
interface binary freeze가 아니다.


<a id="icd-m7-통합-검증-현재-적용-계약"></a>

#### M7 통합 검증: 현재 적용 계약

앞선 단계별 “미연결/미수용” 서술은 당시 기록이다. 현재 판정은
[통합 종료 검토](../project-status.md#m7-종료-조건)와 [원본](../test-plan/evidence/m7_carla_integrated/README.md)을 따른다.

- `m7_integrated_v1.txt`는 INIT 전에 고정하는 상위 VehicleRequest 일정이다.20ms Controller
  release에서 상대 simulation 시각으로 선택하고, 원래 source/sequence/expiry를 부여한다.
  마지막 단계 이후 요청을 무한 유지하지 않는다. 기존 M6 allocation의 질량/radius를 V1 값으로
  바꾸지 않았으므로 이 입력의 가속도는 CARLA 실제 가속도와 동일하다는 의미가 아니다.
- native 정상 Actual·원래 권한 전체 구간·직접 solver wheel·완전 work·단일 EV ACK를 유지한다.
  각900구간에서 가속·음수 motor work/충전 구간·마찰 제동·휠 정지·재출발을 관측했다.
  휠0과 차체0은 구분하며, 작은 signed 차체 잔류 속도를 삭제하지 않는다.
- `-StrataM7SensorFrame5` **및** native probe flag, `role_name=m7_frame5`, RGB/semantic
  camera 종류, `sensor_tick=0.05`를 모두 만족하는 센서만 매 frame의 actor tick에서
  `FCarlaEngine::GetFrameCounter()%5==0`일 때 실제 capture한다. float interval의 첫60ms
  지연을 피하는 전용 취득 스케줄이다.10ms world guard는 유지하며 image frame/timestamp는
  기존 CARLA 원본이다. 다른 센서/flag-off 실행에는 적용하지 않는다.
- 영상은320×240/FOV90,ego 기준x1.6m/z1.7m/pitch−8deg,원본BGRA8이다. GT는 red channel의
  semantic tag와 `TRAIN_EVAL_ONLY` 용도로 분리한다. 어떤 영상도 이번 고정 요청 생성에 쓰지 않는다.
  sensor/ego identity·frame·취득 timestamp·arrival monotonic·validity·payload hash를 기록하며
  run/session/generation은 같은 실행의 binding envelope에 속한다. 새 run으로 캐시를 넘기지 않는다.
- 초기 ego snapshot 미존재는 index0에만 unavailable로 남긴다. 후속 state 누락은 실패다.
  RGB delivery drop은 원래 frame의 누락으로 기록하고 다음 이미지에서 gap을 확인하면 다음 tick을
  차단한다. pause/reset은 기존 latch/새 INIT 조건을 유지한다. 이 gap 검출을 미래 AI deadline 수용으로
  확대하지 않는다. bounded callback buffer overflow도 실패다.
- 실행 환경은 Town03_Opt/mkz_2020/ClearNoon/traffic 없음. 최종 재현 runner는 `-FixedSeed`로
  UE의 `RandInit(0)/SRandInit(0)`을 선택하며 fixed timestep은 CARLA 설정만 소유한다.
  `-Deterministic`의 별도 timestep 옵션을 사용하지 않는다.54m 직선 경로 후보는 좌표/곡률/map hash를
  evidence에 고정했고30km/h 적합성은 M8에서 확인한다. 이번4.77m 주행은 route tracking 시험이 아니다.
- wall 계측은 같은 Host monotonic끼리만 차감한다. native stdin 대기 구간의 실행 공백이2ms를
  넘는 것을 확인했으며 개별4ms deadline 수용은 아직 없다. functional clock을 wall로 이름만
  바꾸거나 RPC10s timeout을 freshness 요구에 대입하지 않는다.

현재 `native_admission.hpp`는 arm 뒤 비정상 origin/state와 닫힌 authority를 거부한다.
따라서 현재 fault 정책은 다음 physics tick 차단이며 **실제 native LocalProtection Actual을
계속 적용하는 안전 정지 경로가 아니다**. 그 경로와 wall guard 연동, cold-loading 중30초 종료,
원래 renderer crash 원인/장시간 안정성이 남은 gate다. M6 계약·V1 계수는 변경하지 않았다.


<a id="icd-보호-actual-연속-적용과-rpc-종료-수정-2026-10-28"></a>

### 보호 Actual 연속 적용과 RPC 종료 수정 (2026-10-28)

[수정·실행 근거](../test-plan/evidence/m7_carla_recovery/README.md). M6 코드·상수·수용은 변경하지 않는다.
정상 admission 검사는 유지하고, 이미 정상 운전한 같은 native 세션에 terminal protection 경로를 추가한다.

- trusted local `PROTECT`는 안전 선택 요청일 뿐 pressure/torque/angle 값을 전달하지 않는다.
  기존 Central/Zone/leaf의 보호 선택, 모델의 유한 응답, CAN/P05 Actual 반환을 거친다.
  선택 뒤 새 VehicleRequest/normal credit 발급을 멈추고 기존 owner/feedback service는 계속한다.
  시험 요청은 현재 native/CARLA frame이 같은 상태에서 다음 physics advance **전에** 전송한다.
  완료된 physics 구간 뒤에 요청해 native subjob에 소급 적용하는 fixture는 인과 검증 근거에서 제외한다.
  [보완 실행](../test-plan/evidence/m7_carla_recovery/causal-followup/README.md)은 원래 request source/frame과
  wall 전송→advance→receipt 순서, request source 이후 protection selection을 검사한다.
- M7 전용 proof의 `protection_since_ns`는 native owner가 보호를 요청한 원래 simulation 시각이다.
  `protection_selected_mask=255`는 두 Zone·다섯 leaf의 원래 protection acknowledgement와
  Central fault/closed gate의 **현재 관측**이다. 이 mask를 M6 원격 ProtectionAck 또는 실제 선택 시각으로 꾸미지 않는다.
  기존 인증된 local owner 경계 안의 증거이며 공개 네트워크 인증을 대체하지 않는다.
- 첫 보호 시각은 마지막 정상 admission보다 뒤여야 하며 이후 고정된다. 원래8개 Release ACK와
  enable/epoch를 유지하고 normal=false, credit mask=0, 전체 service/selection mask=255를 요구한다.
  같은 세션의 정상 재개는 금지한다. 새 INIT는 기존 reset/session 절차를 따른다.
- 세 Actual 모두 `FailSafe/LocalProtection`, 원래 sequence/P05/route/source와30ms whole-interval
  age·10ms skew·Drive wheel provenance를 검사한다. 보호 선택 전 Actual, stale/future/replay,
  다른 Zone·epoch, 누락은 거부하며 receiver를 reset하지 않는다. 명령에서 Actual을 만들지 않는다.
- 보호에서는 종료된 정상 command/permission/RunLease를 권한으로 사용하지 않는다.
  `exclusive_expiry_ns`는 원래 Actual·wheel source 중 최솟값+30ms+1ns인 **측정 freshness의
  exclusive 끝**이며 normal RunLease 연장이 아니다. 실제 적용 effort는 항상 raw Actual에서만 읽는다.
- solver work→단일 EV 정산·ACK 후 다음 stage, single writer, pause/reset latch는 유지한다.
  Actual/work 자체가 없거나 admission이 이미 실패한 경우에는 여전히 다음 tick을 차단한다.
  그런 누락에서 감속을 보장하거나 값을 합성해 보호 진행을 강제하지 않는다.

RPC shutdown은 game-thread owner에서 terminal Stop을 호출한다. sync callback을 기다리는 worker에
종료를 알린 **뒤** worker join을 수행한다. queued mutation을 실행해서 join을 풀지 않으며,
종료 후 새/queued sync 호출도 거부한다. 정상 dispatch는 game thread에서 그대로 수행한다.
Restart/concurrent Stop/worker-thread Stop은 지원 범위 밖이다. 준비180s·종료30s 한도는 유지한다.

이 변경은 functional clock의 보호 경로를 연결한 것이다. wall 실행 기회2ms·job4ms와
simulation↔wall mapping은 미수용이며, native stdin 대기의 wall 공백을 heartbeat로 숨기지 않는다.

<a id="icd-독립-wall-감시와-terminal-barrier-선택-draft-v19"></a>

#### 독립 wall 감시와 terminal barrier 선택 (draft-v19)

M7 fixture의 opt-in `--wall-watch <csv>`와 `WALL_ARM`은 **진단 모드**다.
정상 입증·완료된 solver work barrier에서만 arm할 수 있으며, 첫 wall release를100ms 뒤로 명시한다.
앞선 INIT/정상 경로는 이 감시의 검증 범위가 아니다. 기존 `M4ExecutionWatch`의2ms release/4ms
deadline·누락 slot·late completion latch를 유지하며 최대2s 진단 창 만료도 fail closed다.
원래8-role participant poll과 physical step의 실제 monotonic 시작/완료를 계측한다.
별도 monitor(9)는0..8을, physical(8)은 monitor를 관찰한다. stdin polling은 job이 아니다.

deadline 위반은 별도 monitor의 latch로 전달된다. native 입력 대기는 bounded poll로 끊고,
마지막 완료 barrier에서 원래 Central·Zone·leaf 보호 함수를 호출한다. 모델 시간을 진행하거나
취득/Actual을 만들지 않으며 이후 observe/frame 허가를 영구 차단하고 native exit2로 끝낸다.
`WALL_GUARD_STOP`의 `logical_barrier_ns`와 `wall_selected_ns`는 각각 별도 domain이며 서로 빼지 않는다.
`selected_mask`는 local 선택 상태 readback이며 remote ACK/새 P05 Actual을 대체하지 않는다.
adapter는 해당 terminal 결과를 받으면 다음 stage/advance 없이 기존 서버 pause로 입력을 지운다.
새 INIT/별도 process 없이는 정상 복귀할 수 없다.

검증된 범위는199 physics 구간·EV 정산 뒤 **in-flight 요청이 없는 경계에서의 input gap**이다.
RPC 진행 중 fault, 연속 wall 정상 실행, clock agreement, 지연 뒤 물리 제동은 미수용이다.
현재 actuator/EV가 관측 solver work 수신에 함께 종속되므로 이 진단은 독립 감시를 연결한 것이며
독립 actuator 실행을 구현한 것이 아니다. 원래 pressure/torque Actual 없이 brake를 직접 적용하지 않는다.
[현재 결과/남은 구조](#m7-review-wall-guard-후속-결과)를 따른다.

<a id="icd-독립-response--deferred-observed-work-draft-v20"></a>

#### 독립 response / deferred observed work (draft-v20)

`PlantExecution::DeferredObservedWork`는 M7 모델 계층의 별도 선택이다. 기존 bool 생성자와
ZOH/coupled solver 경로의 동작·실행 결과는 유지한다. 실제 native runner의 기본 모드를 변경하지 않는다.
두 API는 한 mutation owner에서 호출하며, 수신 thread가 모델을 동시에 변경할 수 없다.
현재 API의 시간은 caller가 선언한 한 model clock이다. simulation→wall 변환/불확실성 수용을 포함하지 않는다.

| 동작 | 계약 |
| --- | --- |
| `advance_actuators(now, wheel, outputs, released, protect)` | work 없이 원래 응답 모델을(0,1ms]만큼 진행하고 새 angle/pressure/torque 취득. 원래 output source/epoch·30ms watchdog 유지. wheel 부재는 null이며 새0/abs/clamp로 채우지 않음 |
| electrical/HV/BMS 취득 | 마지막 실제 정산 시각/oldest 유지. envelope source가 새 actuator 취득 시각이어도 개별 electrical 취득을 restamp하지 않음. 초기 power 부재는 그대로 unavailable |
| coil history | 해당 response 구간 시작에 적용된 coil을128개 고정 슬롯에 보관. 과거 work에 현재 coil을 소급하지 않음. 부분 frame tail은 같은 원래 구간을 잘라 다음 work에 한 번만 사용 |
| `settle_observed_frame(work)` | 기존 검증된 receipt에서 유래한 완전한 work, frame/wheel sequence, 연속 energy 시간, 이미 진행한 response 범위, 원래 dt/oldest를 검사. 원래 signed work 적분만 단일 EV로 반영하고 whole-frame commit |
| 정산 실패/중복/이력 초과 | EV/장부는 마지막 성공 시점 유지, electrical 센서는 unavailable. actuator 상태는 rollback하지 않음. 이후 response는 보호를 계속하고 새 정상 output·정산 재개를 허용하지 않음 |
| 보호 선택 | terminal latch. 원래 response 모델이 torque0/pressure floor를 생성하며 CARLA 직접 적용은 하지 않음. 원래 ECU 취득→CAN/P05 Actual 경로는 별도 runtime 연결 필요 |
| Power watchdog | 기존 PowerControllerConfig의 source50ms/dependency70ms·current dwell을 재사용. 현재 전류가 만료되면 보관된 low-current로 접촉기 opening dwell을 채우지 않음. Drive freshness30ms와 구분 |

`begin_work_frame/step/finish/commit/abort` coupled API와 독립 API의 혼합은 거부한다.
새 모드의 실패 시 actuator는 이미 진행했으므로 coupled checkpoint로 과거 상태를 복원할 수 없다.
`advance_actuators()` 성공은 response 진행 성공일 뿐 normal 권한이 아니다. 후속 native owner는
`electrical_ok()==false`를 원래 LocalProtection 선택에 전달하고, 정상 credit/Actual 권한을 열지 않아야 한다.
Native 정상 권한·CARLA stage/advance·scope/Actual/work ACK 계약은 개정하지 않았다.
component 결과는 [현재 검토](#m7-review-actuator-응답과-관측-ev-정산-분리)를 따른다.

<a id="icd-terminal-wall-response-연결-draft-v21"></a>

#### Terminal wall response 연결 (draft-v21)

`--wall-watch <csv> --wall-response <jsonl>`는 solver-work 모드의 별도 terminal 진단이다.
`WALL_ARM` 이후 원래 monitor가 fault를 검출하면, 완료된 정상 barrier의 동일 native/EV/응답
객체를 `begin_terminal_response()`로 일방향 전환한다. 미정산 checkpoint·ZOH·미초기화·중복 전환은 거부한다.
원래 Central/Zone/leaf 보호 선택 시각은 handoff anchor다. 그 뒤 service에서 생성되는 output을
이전 응답 substep에 적용하지 않는다. 기존 coupled 기본 경로와 M6 코드는 유지한다.

- 한 mutation thread가 실제 monotonic wake마다 owner cycle을 한 번 호출한다.1ms wake는
  검사용 service 기회이며 원래 ECU20/10/20ms·감시2ms/4ms 설정을 바꾸지 않는다.
  지연 시 release를 건너뛰며 과거 owner poll로 slot을 채우지 않는다. 응답 모델의 내부1ms 이하
  분할은 별도 owner job이 아니다. 독립 monitor는 계속 실행한다.
- local time은 `barrier + (monotonic - handoff_anchor)`이며 **CARLA 시각 변환/동기 계약이 아니다**.
  raw CAN/P05는 해당 terminal branch의 진단이며 외부 stage/advance로 전송하지 않는다.
  기존 FrameClock은 전환 즉시 영구 차단한다. 정상 credit/Controller request/lease 재발급은 없다.
- wheel과 electrical acquisition의 기존 시각을 유지한다. work 정산/정상 복귀는 금지한다.
 128개 이력 슬롯 소진 시 electrical unavailable로 고정되지만 response·원래 ECU service는 계속한다.
  슬롯 수는 freshness 여유가 아니다. 새 Actual은 원래 vECU→Zone→Central 경로에서만 얻는다.
- 최초 보호 선택 readback 후 `WALL_GUARD_STOP`을 즉시 전달해 adapter가 기존 pause로 차단한다.
  trace는 메모리에 유한 보관한 뒤 기록한다. 시험은300ms 관측 후 exit2이며 API의1s 상한도
  시험 자원 상한일 뿐 source-age/보호 시간 요구를 완화하는 값이 아니다. 지속 배포 runtime이 아니다.

[실행 판정](#m7-review-terminal-wall-service와-보호-actual-지속)은 native terminal
응답 한정이다. 정상 wall owner/수신 분리·clock uncertainty·in-flight RPC 차단과 CARLA 물리 제동을
수용하려면 별도 연결이 필요하다. 이 경로의 Actual로 freshness/clock 검사를 우회하지 않는다.

<a id="icd-보호-hold종료취득-clock-증거-draft-v22"></a>

#### 보호 hold·종료·취득 clock 증거 (draft-v22)

`-StrataM7HeldSteerSleep`는 native+solver-work 진단 프로필에 한정한다. 직전 완료 구간과 현재
구간이 모두 원래 보호 Actual(torque0, pressure≥1MPa)이고 네 바퀴의 적용 steer/friction이 정확히
같으며 friction>0·drive0일 때만 NoDrive의 비영 steer wake 조건을 생략한다. 자연 sleep 진입을
강제하지 않으며 drive/외부 접촉의 wake, 실제 effort, pose/속도, 타이어 법칙은 유지한다.
다른 차량·일반 프로필에는 적용하지 않는다. 이전 구간 증거는 pause/reset/새 bind 상태를 넘지 않는다.

observer ABI2의 `protected_steer_hold`와 receipt의 `protected_held_steer_sleep`는 같아야 한다.
독립 감사는 이전 frame/run/session/actor/generation, 두 원래 Actual과 모든 wheel effort도 확인한다.
sleeping zero-work는 실제 actor sleep·직접 solver wheel0·drive0 및 steer0 또는 검증된 hold를
요구한다. 단순 flag만으로 임의 steer/sleep/work0을 수용하지 않는다. ABI1 과거 자료는 기존
steer0 규칙을 유지하며 새 서버에서 ABI1 observer는 fail-closed한다. V1 모델 계수는 불변이고
이 옵션은 별도의 수치 정책으로 실행 argv/observer module hash와 함께 보존한다.

`physics_acquisition_begin_ns/end_ns`는 새 Physics 취득을 감싼 같은 Host의 CLOCK_MONOTONIC
원시 bracket(string uint64)이며 `physics_acquisition_clock`에 진단 출처를 기록한다. cached receipt
조회 시 갱신하지 않는다. 기존 simulation/frame/CAN timestamp와 별개이며 wall mapping/새 CAN
source로 쓰지 않는다. uncertainty·clock agreement 수용 전에는 정상 wall 권한을 만들 수 없다.

engine exit가 요청된 경우에만 game-thread synchronous wait를 취소한다. adapter를 latch하고
입력을 지운 뒤 world physics 등록을 막으며 post-tick receipt/snapshot을 발행하지 않는다.
그 뒤 서버를 종료한다. client-loss 자체의 자동 안전 제동 계약은 아니며, SIGINT 종료 응답과
원래 frame 유지 시험이다. 상세 판정은 [일괄 검증](../test-plan/evidence/m7_carla_recovery/batch-closeout/README.md)을 따른다.


<a id="icd-solver-증거-전달-비용-분리-draft-v23"></a>

#### Solver 증거 전달 비용 분리 (draft-v23)

`--compact-work`/`-StrataM7CompactWork`는 별도 opt-in native solver-work 진단 프로필이다.
물리/단일 EV/원래 source·Actual·authority 검사는 유지한다. AfterTick에서 모든320개 원시
solver 값의 finite·연속성·applied torque·최종 wheel·work 합 검사를 그대로 수행하되, 세부 JSON
직렬화는 실행 경로에서 분리한다. 정산에 필요한 원래 rear mean320개와 동일한 signed work만
즉시 전달한다. 새 wheel 취득이나 work 예측을 만드는 것이 아니다.

bind 시 game-thread 단독 소유의1024-entry journal을 미리 할당한다. 각 entry는 ABI2 원시
POD trace·원래 frame/ticket의 독립 복사다. 다음 solver invocation이 원본을 재사용해도 변하지
않으며 overwrite/eviction이 없다. 용량이 차면 다음 physics 전에 latch한다. 실제 indefinite
운영용 logger/백그라운드 IO 구현은 아니며 유한 시험 구간의 직렬화 지연이다.

인증된 같은 run/session/actor에서 `solver_trace(ticket)`로 원본 steps를 읽는다. 반환의
trace_frame/physics_generation도 원래 receipt와 같아야 한다. 조회는 tick/Actual/취득 시각을
갱신하지 않는다. 시험기는950tick 이내로 제한하고 close/reset 전에 모든 원본을 회수한다.
raw steps→compact mean의 정확한 일치, 기존 solver 방정식·EV·wire 감사 후에만 시험을 통과시킨다.
누락·scope 불일치·overflow·회수 실패는 FAIL이다. raw trace를 얻지 못한 abrupt client-loss를
이 모드의 PASS로 처리하지 않으며 runner는 그 조합을 거부한다. RAM journal은 crash-durable
로그가 아니고, 비정상 process 손실 때 완전 증거 수용을 보장하지 않는다.

[실행·동등성·시간 결과](../test-plan/evidence/m7_carla_wall_guard/pipeline/README.md)를 따른다.
현재 `FunctionalRig.observe()`의 simulation-time barrier를 wall owner로 바꾼 것은 아니다.
별도 component phase probe는 Controller/management의 enable 후 시작 위상만0..20ms로 조사한다.
기존20ms/10ms 주기와 expiry 검사를 유지하며, 정상 native 실행의 기본14ms 위상은 불변이다.
수용 가능한 조합도 최소 expiry 여유1ns이므로 위상 변경을 실시간 해결안으로 채택하지 않았다.

<a id="icd-다음-wall-runtime의-구현-경계"></a>

#### 다음 wall runtime의 구현 경계

정상 wall 연결은 새 INIT부터 같은 Host CLOCK_MONOTONIC을 쓰는 native mutation owner와,
CARLA tick/RPC/증거 기록을 담당하는 IO owner를 분리해야 한다. 과거 logical subjob을 뒤늦게
재생하거나 같은 simulation time으로 반복 poll한 것을 실제 실행 기회로 세면 안 된다.
새 post-physics의 원시 monotonic 취득 bracket과 원래 frame/simulation elapsed는 각각 보존한다.
상수 offset으로 기존 functional CAN을 wall CAN처럼 재표기하지 않는다.

actuator response의 실제 elapsed, CARLA의10ms model dt, 관측 solver work의 단일 EV 정산 및
각 sensor의 취득/dependency 시각을 별도로 정의하고 검증해야 한다. 현재 `SolverWork`의
10ms 단일-domain 입력에 wall jitter를 그대로 넣거나 duration 범위를 넓히는 변경은 미채택이다.
queued/in-flight fault 시 정상 권한을 닫고 이미 실행한 구간은 원본 work로 정산해야 하며,
그 이후 새 LocalProtection Actual만 적용해야 한다. 기존 terminal local branch를 그대로
서버 stage에 전달하는 것은 여전히 금지한다. 이 절은 **설계 경계이며 구현/실행 완료가 아니다**.

<a id="icd-새-wall-owner의-구현-범위-draft-v24"></a>

#### 새 wall owner의 구현 범위 (draft-v24)

`WallRig`는 새 `M7MONO01` domain/INIT에서 같은 native Controller·Zone·leaf·CAN/P05와
deferred actuator/EV owner를 실행한다. `service(now)`는 실제 monotonic 시각에서 한 번만
각 owner를 호출한다. Controller20ms/management10ms/Zone·leaf10ms/BMS20ms를 유지하고,
과거 runnable/owner completion을 재생하지 않는다. 응답 모델의1ms 이하 내부 적분은 ECU job이 아니다.

입력 parser/IO는 단일 생산자, native mutation은 단일 소비자다. 고정8개 receipt mailbox는
덮어쓰지 않으며 overflow를 latch한다. normal 권한이 닫혀도 이미 완료된 유효 work는 한 번 정산한다.
새 model response 이후, **ECU가 sensor를 읽기 전**에 완료 work를 commit한다. local fault 뒤에도
owner service·보호 Actual을 계속한다. held wheel/EV 시각은 보존하고, 이후 전기 이력 용량 초과는
기존 deferred 규칙대로 전기 validity를 닫으며 actuator 보호는 지속한다.

wall INIT은 첫 work가 정산되고 원래 취득에서2ms 이상 지난 위상에서 Prepare를 시작한다.
Initialize 전달은 기존20ms reset-evidence 검사에 적합한 시점까지 기다릴 수 있으나 원래
Control source/enable·30ms message age·20ms commit window를 변경하지 않는다. 거부된 INIT는
재시도하지 않는다. 준비되지 않으면 기존 deadline에서 실패한다. functional 모드의8ms offset과
14ms Controller phase는 그대로다. 보호 선택도 현재 invocation 시각부터이며 과거 응답 적분에 소급하지 않는다.

현재 `WallReceipt`는 **wheel과 완전한 SolverWork가 모두 같은 monotonic domain**인 경우만
받는다. 원래 SolverWork10ms 범위·freshness·identity 검사를 그대로 사용한다. 시뮬레이션 시각,
다른 domain, duplicate/future/잘못된 frame을 도착 시각으로 고쳐 받지 않는다. 출력의 next-frame
권한은 항상0이며 기존 CARLA admission domain과 다르다.

[현재 근거](../test-plan/evidence/m7_carla_wall_guard/wall-owner/README.md)는 합성 stationary
wheel/work 생산자와 실제 Host timer/IO thread를 연결한 **native runtime component**다.
CARLA가 새 wall-domain work를 생산하거나 wall Actual을 적용한 시험은 아니다. 실제 CARLA
simulation dt·EV work와 wall acquisition의 명시적 연결, queued/in-flight RPC 차단 및
wall-origin 보호 Actual의 연속 CARLA 적용은 여전히 미구현·미수용이다.


<a id="icd-실제-carla와-wall-owner-연결-draft-v25"></a>

#### 실제 CARLA와 wall owner 연결 (draft-v25)

**구현된 실험 경계이며 정상 주행 수용 아님.** [실행·실패](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/README.md).
기존 functional 프로필과 별개로 `--wall-native`/`-StrataM7WallNative`를 명시한다.
같은 Linux kernel CLOCK_MONOTONIC의 새 INIT와 `M7MONO01` owner-wire domain만 허용한다.
다른 Host clock agreement를 제공하지 않으며, CARLA simulation elapsed를 wall로 환산하지 않는다.

- `CarlaWork`는 원래 frame/model begin/end/320-bin solver work와 **별도의** applied/acquired begin/end,
  oldest dependency, 적용 당시 Power coil bits/source를 운반한다. EV는 원래 model10ms 안에서
  1ms 정산하고 actuator response/ECU는 실제 wall timer에서 진행한다. 정산 자체의 늦은 도착을
  새 센서 시각으로 쓰지 않는다. 전기 관측은 완료된 physics 취득 identity로 한 번 생성한다.
- model-domain `SolverWork.oldest=begin`은 해당 solver 구간의 적용 witness다. 원래 wall dependency는
  별도 `CarlaWork.oldest/coil_source`에 보존하고 전기/Drive sensor oldest에 전파한다. 누락 work를
  예측/0으로 채우거나 EV를 이중 진행하지 않는다. 대기 중 EV 모델 시각/관측은 동결한다.
- 공유 ABI2는 같은 빌드/Host·0600 소유 파일의 magic/size/run/session/actor/physics generation/
  application/model origin을 확인한다. 실패 실험의 ABI1은 최종 연결에서 거부한다.
  방향마다3개 exclusive slot, 단일 reader/writer이며 payload ownership은 acquire/release exchange로
  이전한다. 원본 CAN/P05·owner-wire를 그대로 전달한다. 외부 네트워크/보안 채널 계약이 아니다.
- native FIFO18 owner는 실제1ms wake마다 한 번 service한다. 과거 job catch-up은 없다.
  원래2ms opportunity/4ms deadline을10owner에 독립 계측한다. IO는 GET/STOP/보호 요청만 처리한다.
  새 CARLA 모드에서만 생성한 Drive owner가 센서 ingress를 control body보다 먼저 수행한다.
  원래 Drive monitor·10ms 제어·freshness·CAN source는 바꾸지 않고 M6 원본은 그대로 컴파일한다.
- game thread의 `PumpWall`만 물리를 발급한다. external advance/stage/EV ACK와 legacy writer는
  잠금 중 거부한다. 다음 실제10ms를 덮는 원래 Actual/Command/permission/credit만 선택한다.
  선택 preview에는 추가4ms 여유를 요구하며 기존 expiry를 늘리지 않는다. 물리 직전 다시 확인한다.
  완료된 원본 work는 fault 후에도 한 번 정산하고 ACK 전 다음 물리를 금지한다.
- 정상 승인 후의 terminal protection은 세션/Release 불변·선택 mask255·credit0·새 LocalProtection
  Actual 전체를 요구한다. torque는 정확히0만 허용한다. 이0 torque의 적용에는 stale wheel을
  유효한 값으로 승격하지 않는다. 정상/nonzero/regen에는 원래 wheel30ms gate가 그대로 필요하다.
  초기화 실패의 unavailable Actual에는 적용 권한이 없다. M6의 명령 없는 진단 Actual 계약 유지.
- pause/reset/close는 기존 latch·input clear·새 INIT 경계를 유지한다. receipt cache/공유 슬롯을 읽어도
  원래 acquisition/source가 변하지 않는다. RGB/GT50ms·TRAIN_EVAL_ONLY 계약은 그대로다.

native executable의 유한 horizon은19s(원래 schedule10000 slot 이내), server receipt 한도는950,
raw solver journal은1024다. 시험 request의 마지막 phase만 wall 유한 horizon까지 hold하며
그 값을 새 Actual로 만들지 않는다. 이는 Reference AI/정상 wall 수용 또는 freshness 예외가 아니다.
완료 기준은 같은 실제 runtime의 정상/영상 및 고장·보호 정지·에너지·writer/lifecycle suite다.
현재 실제 wall 시도는 INIT 이후 Drive 원천 만료로 실패했으며 다음 stage 차단까지만 관측했다.

<a id="m7-review"></a>

## M7 통합 검증 및 종료 검토

2026-10-28. **전체 M7 NOT CLOSED.** 고정 시나리오의 native Actual→CARLA→solver work→단일 EV
기능 연결에 보호 Actual의 연속 적용·고정 시나리오의 자연 완전 정지와
로딩/클라이언트 단절 시 종료 교착 수정을 추가 검증했다.
실시간 실행 기회와 wall fault→보호 전환 수용은 완료되지 않았다.
하위 단계를 계속 늘리는 대신 이 문서의 남은 gate를 기준으로 관리한다.
M6 Host quiet SIL/Python MIL의 구현·계약·결과·종료 판정은 변경하지 않는다.

<a id="m7-review-이번-통합-범위"></a>

### 이번 통합 범위

[실행 원본·실패·집계](../test-plan/evidence/m7_carla_integrated/README.md),
[재현 runner](../../tests/integration/carla/m7_integrated_run.py),
[ICD](../interfaces/carla-plant-adapter.md)를 함께 따른다.
Controller20ms·Zone/vECU10ms·world/state10ms·영상50ms·Drive source-age30ms 및
원래 exclusive expiry를 유지했다. V1 가상 EV 계수·320 내부 분할·원래 solver wheel source도 유지한다.

입력은 시험용 **상위 VehicleRequest** 일정이다. 실제 Central 배분→Zone→vECU 응답→
CAN/P05 Actual 반환과 서버의 권한 검사를 모두 거친다. Actual이나 CARLA effort를 시험 일정으로
직접 대체하지 않는다. 원래 native root request의 source time으로 단계별 입력을 독립 검증한다.
M8 route-following Controller나 AI 주행을 구현한 것은 아니다.

| 검토 gate | 현재 판정 / 근거 |
| --- | --- |
| 고정 환경·모델·단일 writer | CARLA0.9.16 source/Client `294096e-dirty`, UE4.26.2 pin, Town03_Opt/mkz_2020, V1 모델 hash 고정. 외부 writer/tick·synthetic stage 거부 유지 |
| 정상 주행·제동·에너지 | 9s/900구간에서 좌조향 가속→signed 회생→마찰 제동/휠 정지→우조향 재출발 관측. 독립 raw-wire·solver 방정식·work/EV 장부 감사. Reference 전체 속도/ODD 수용 아님 |
| 영상·state·lifecycle | 통합 evidence의 실제 실행별 판정 적용. RGB/학습·평가 GT 분리, frame/source timestamp 검증, 누락 차단·pause/reset/새 INIT 확인 |
| 실시간2ms/4ms·clock | **NOT ACCEPTED.** 실제 owner 호출별 계측과 독립 monitor, deadline 위반→보호 선택→다음 tick 차단을 검증했다. 새 wall-domain INIT·독립 owner/수신은 아래 합성 원천 component에서 검증했다. 실제 CARLA 두 시간축/work 공유 전달은 구현했으나 엔진 프레임 공백으로 정상 wall 주행 전에 차단됨; 연속 정상 wall 실행은 미수용 |
| 보호 Actual 제동 | **기능 경로 검증 완료.** trusted safety 요청 후 원래 LocalProtection Actual로200개 physics 구간·EV 정산을 계속하며 감속·휠 정지 관측. 정상 재개·누락·stale/future/다른 출처 거부. 명시적 opt-in 보호 hold에서 차체 자연 완전 정지까지 한정 검증. wall fault 자동 연동은 OPEN |
| 시작·종료 안정성 | 준비 후 네트워크 경합 수정은 M7-1s FIXED_LIMITED 유지. 별도 sync RPC/game-thread 종료 교착을 재현·수정하고 로딩 중 SIGINT30s 내 종료 확인: **FIXED_LIMITED**. client-loss 동기 tick 대기도 수정 후 영상 유/무 종료 확인. 원래180s 준비 timeout/강제−9와 renderer 별도 원인은 보존 |
| Reference 경로 | 54m 직선 후보 좌표/곡률·맵 hash 고정. M8의30km/h 적합성·추종/정지 시험은 NOT RUN |

<a id="m7-review-이번에-해결한-문제"></a>

### 이번에 해결한 문제

1. spawn 직후 첫 physics tick 전 ActorSnapshot에는 새 ego가 아직 없을 수 있다.
   index0은 `valid=false`로 남기고, 이후 누락은 실패 처리한다. 초기 좌표/속도를 조작해 채우지 않는다.
2. 기본 UE float `sensor_tick=0.05`에서 첫 영상 간격60ms를 재현했다.
   M7 전용 flag와 정확한 camera role/종류/주기를 모두 만족하는 센서만 actor tick을 매 frame 실행하고,
   원래 CARLA frame counter의5배수에서 실제 취득한다. capture나 timestamp를 사후 보정하지 않는다.
   기본 CARLA 센서 동작은 이 opt-in 조건 밖에서 유지된다. 내부 센서 스케줄을 조정했으며
   native/M6 계약·차량 운동·에너지 코드는 변경하지 않았다.

<a id="m7-review-종료-교착보호-actual-후속-수정"></a>

### 종료 교착·보호 Actual 후속 수정

[실행·실패·독립 감사](../test-plan/evidence/m7_carla_recovery/README.md).
보호 요청의 인과 검증은 [순서 보완 후 실행](../test-plan/evidence/m7_carla_recovery/causal-followup/README.md)이
최신 근거다. 이전3회는 요청을 physics 완료 후 주입했으므로 요청 인과 검증 근거에서 제외하고
물리 응답 관측 자료로 보존한다. 보완 후에는 advance 전에 요청하고 이후 native 선택/Actual을 검증했다.
RPC worker가 game thread의 sync callback을 기다리는 중에 game thread가 worker join을 기다리던
교착을 수정했다. 종료 신호로 대기를 먼저 취소하며, 대기 중인 mutation을 실행하지 않는다.
실제 pinned header component 원본 TIMEOUT/수정5개 통과와 fresh CARLA 로딩 중단을 대조했다.

M7 native fixture는 보호를 선택한 뒤에도 기존 owner/Actual service를 계속한다.
Plant Adapter는 정상 credit을 다시 열지 않고 같은 Release/epoch의 LocalProtection Actual만
별도 검사·적용한다. 이전 normal proof, 합성 명령, 갱신한 sensor timestamp로 대체하지 않는다.
원래 wire/P05·source age·solver/단일 EV 장부와 single writer 경계를 독립 감사했다.
정상900구간·RGB/GT 각180개 회귀도 확인했다. M6는 변경하지 않았다.

<a id="m7-review-남은-문제를-닫는-작업"></a>

### 남은 문제를 닫는 작업

**남은 주 작업은 정상 wall owner/수신 실행과 clock agreement를 연결하고, wall fault 이후 CARLA에 보호 Actual을 연속 적용하는 것이다.**
terminal native 응답은 아래 후속 실행에서 연결했다.
현재 Python/RPC/전체 solver JSON 진단 loop의 지연을 단순 timeout 증가로 해결할 수 없다.

- native owner/감시의 wall 실행을 CARLA 응답 대기와 분리한다. 실제2ms 실행 기회·4ms 완료를
  monotonic 기준으로 계측하고, 지연 시 normal 권한을 닫는 경로를 검증한다. trace는 비동기 수집하되
  frame별 work 정산 증거를 잃지 않아야 한다. 최적화 전후 동일 시나리오의 물리/work 비교를 유지한다.
- 독립 wall 지연 검출→native 보호 선택→다음 tick 차단은 아래 한정 시험으로 연결했다.
  actuator/전기 분리와 terminal native timer/service 연결은 아래 후속 결과를 따른다. 정상 수신 경로 연결은 남는다.
  Actual/work 자체가 없을 때는 다음 tick 차단을 유지하며 그 차단을 물리 안전 정지로 수용하지 않는다.

현 loop의 native 요청 응답 시간은 짧아도, RPC/trace 대기 중 owner를 호출하지 않는 구조는 남는다.
단순 heartbeat만 추가하거나 멈춘 simulation clock으로 wall freshness를 갱신해서는 해결되지 않는다.
새 wall runtime은 원래 clock agreement·source provenance와 실제 job 실행 증거가 필요하다.

<a id="m7-review-wall-guard-후속-결과"></a>

### Wall guard 후속 결과

[실행 원본·중단·sanitizer 제한](../test-plan/evidence/m7_carla_wall_guard/README.md).
별도 opt-in `WALL_ARM` 진단에서 기존 M4 schedule/deadline monitor를 그대로 사용했다.
원래8-role poll 및 physical step의 실제 CLOCK_MONOTONIC 시작/완료만 기록하고,
stdin polling/monitor heartbeat/과거 logical subjob을 실행 기회로 채우지 않는다.
선언한 첫 release 전100ms는 진단 준비 구간이며 이전 INIT/정상 실행을 감시했다고 주장하지 않는다.

실제 CARLA199구간·199정산 후 다음 입력을 보류하자 독립 monitor가9개 owner의 미완료를 검출했다.
검출→local 보호 선택0.961ms, 검출→adapter pause 확인4.722ms를 관측했다.
이는1회 관측치이며 보장 상한이 아니다. native가 자체적으로 기존 Central/Zone/leaf 보호를 선택하고
credit0·local selection mask255를 읽었다. 이 mask는 원격 ProtectionAck나 새 Actual이 아니다.
마지막 완료 barrier의 logical time은 유지하고 다음 frame 권한을 영구 차단했다.
시험 입력에 `PROTECT`/압력값을 넣지 않았으며, 별도 wall→simulation 시각 변환도 만들지 않았다.

**기존 정상 runner의 owner 실행은 아직 CARLA 대기에 묶여 있다.** 아래 terminal 후속 모드만 독립 진행한다.
기존 coupled `ActuatorElectrical::step()`은 work가 있어야 actuator도 진행한다.
아래 새 경로는 실제 response 모델을 독립 진행하므로 work 없이도 새로운 actuator 취득을 만들 수 있다.
이전 Actual을 restamp하거나 관측 work 없이 전기 정산을 진행하는 것은 허용하지 않는다.
다음은 원래 ECU service/timer에 새 경로를 연결하고 clock mapping/불확실성·in-flight fault를
검증하는 작업이다. 위 wall 진단은 완료 barrier에서만 수행했으며 RPC 진행 중 차단/연속 제동 수용은 아니다.

<a id="m7-review-actuator-응답과-관측-ev-정산-분리"></a>

### Actuator 응답과 관측 EV 정산 분리

[구현·검사·기존 출력 재생](../test-plan/evidence/m7_carla_wall_guard/deferred-response/README.md).
M7 모델 계층에 `DeferredObservedWork`를 추가했다. `advance_actuators()`는 work 수신을 기다리지
않고 원래 Steering/Brake/Drive response를1ms 이하 구간으로 진행한다. `settle_observed_frame()`은
완료된 work와 해당 과거 구간의 실제 coil 이력으로 단일 EV만 정산한다. 전체 frame의 EV commit은
원자적이며 실패해도 이미 진행한 actuator를 되돌리지 않는다. 두 API의 mutation owner는 하나다.

work가 없는250개1ms 구간에서도 보호 response를 계속하며 모델 시각의230ms 안에 torque0·pressure1MPa를
검사했다. EV/HV/BMS 값과 시각은 동결하고 wheel 부재를0으로 채우지 않았다.128개 이력 슬롯이
넘치면 전기 정산은 실패로 고정하지만 actuator 보호는 계속한다.128은 저장 공간 상한이며
freshness 완화가 아니다. Power의 기존50/70ms source/dependency 경계 밖 전류는 opening dwell에
쓰지 않는다. 잘못된/중복 work·혼합 모드·sensor identity 변조 및 재개도 거부한다.

30ms 단위 지연 정산 component 대조에서 원래 방식과 SOC·signed motor work·손실·전압·전류가
정확히 일치했다. 원래 native 실행 모드는 유지했으며 기록된 정상900구간과 보호400구간의 입력을
재생한 모든 native 출력(terminal 포함901/401개)도 정확히 일치했다.
이 당시 결과는 **모델 계층 분리 완료**이며 아래 terminal wall 후속 실행과 구분한다.
새 CARLA 실행·2ms/4ms 수용·wall fault 이후 CARLA 물리 제동 완료를 주장하지 않는다.

<a id="m7-review-terminal-wall-service와-보호-actual-지속"></a>

### Terminal wall service와 보호 Actual 지속

[실행·실패·독립 감사](../test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md).
`--wall-response` opt-in은 기존 wall fault 이후 **같은 native 세션/모델**을 terminal 분기로 넘긴다.
원래 Central/Zone/leaf 보호를 먼저 선택하고 single mutation owner가 monotonic timer로
8-role service와 response를 실행한다. 입력 read/WORK 수신을 기다리지 않는다. 응답 적분의1ms 이하
내부 분할을 ECU job으로 세지 않으며 지연 뒤 과거 owner poll을 재생하지 않는다.
원래 Controller20ms/Zone·leaf10ms/BMS20ms 설정과 CAN/P05 source·epoch를 유지한다.

fresh CARLA199구간/199정산 후 입력 보류→독립 deadline 검출→native 보호 선택→adapter pause를
실행했다. 이후300ms 동안 steering/brake/drive의 새 LocalProtection Actual을 각각30회 관측했다.
토크0·압력1MPa 첫 동시 관측은209.053ms였다. 이는 native 응답 모델 관측이며 CARLA 차체 제동이 아니다.
EV time/장부와 마지막 wheel 시각은 유지하고, 만료한 wheel을 새 취득으로 발행하지 않았다.
해당 terminal 구간에서 owner0..9 각각150개 완료, 완전한 구간의 누락/late0을 관측했다.
단일 짧은 구간이며 정상 전체 실행의 실시간 수용이나 보장 상한으로 확대하지 않는다.

일반/ASan 각86/86, TSan6/6 및 실제 terminal process 검사에서 race 경고는 없었다.
TSan process에서는 owner0..3의 완료 누락을 각각6/7/2/1개 관측·보존했다. sanitizer 통과와 timing
통과를 구분하며 그 누락을 뒤늦은 poll로 채우지 않았다. 기존 정상/보호 입력 재생901/401개 출력은
정확히 같았다. 최초 fractional clock 시험에서 새 보호 output을 이전 substep에 넣어 거부된 오류를
수정했다. handoff anchor에서 먼저 보호를 선택해 source 이후에만 적용하며 실패 로그도 보존했다.

**Clock/적용 경계:** terminal local time은 마지막 barrier + handoff 이후 실제 monotonic 경과다.
`LOCAL_TERMINAL_RESPONSE_NOT_CARLA`로 분리 기록하며 simulation clock과 동기됐다고 주장하지 않는다.
기존 FrameClock은 terminal latch로 닫고, 이 Actual을 서버 stage/advance에 전달하지 않는다.
따라서 정상 wall loop/clock uncertainty, in-flight RPC fault, CARLA 연속 보호 제동은 OPEN이다.
이번 서버는 정상 cleanup 후 SIGINT 약2.920s에 종료했다. 이 당시 결과는 client-loss 종료 문제의 해결 근거가 아니며 아래 일괄 검증과 구분한다.

대화 중단으로 camera 실행기가 사라진 실행은 미완료로 보존했다. 남은 전용 서버에 SIGINT를
보냈지만30초 안에 종료하지 않아 강제 종료했다. 기존 로딩 중 RPC 교착 수정은 이 별도
client-loss/동기 대기 종료 문제의 해결 근거가 아니었다. 아래에서 별도 재현·수정했다.

원래 renderer Distance Field crash 원인은 여전히 미확정이다. 이번 짧은 영상 시험이 성공해도
모든 content/장시간 안정성을 주장하지 않는다. 정지 시 휠 회전0과 차체의 작은 잔류 속도는
구분해 기록했다. 새 stationary 허용 오차를 임의로 만들거나 음수를0으로 바꾸지 않았다.

M8 Controller/30km/h 경로 적합성, M9 diagnostics, AI 학습·Jetson 배포는 각 후속 milestone의
범위이며 M7 검증을 진행할 때마다 새 선행 작업으로 추가하지 않는다.

<a id="m7-review-종료정지clock-일괄-검증-2026-10-28"></a>

### 종료·정지·clock 일괄 검증 (2026-10-28)

[수정 전 실패·중간 실패·최종 실행 및 재현](../test-plan/evidence/m7_carla_recovery/batch-closeout/README.md).

- **client-loss 종료 FIXED_LIMITED:** 정상199구간/정산 후 probe를 cleanup 없이 exit73으로
  종료했다. 수정 전에는 SIGINT30s 후 강제−9가 필요했다. game thread의 synchronous tick 대기가
  engine exit를 확인하도록 수정하고 종료 시에만 world physics 등록과 post-tick 발행을 차단했다.
  없는 client의 tick을 조작해 만들지 않는다. 수정 후 영상 유/무 모두 원래 frame을 유지하며 종료했다.
- **보호 정지 FIXED_LIMITED:** PhysX NoDrive는 같은 비영 조향각도 매번 wake 입력으로 취급했다.
  `--held-steer-sleep`에서 연속한 두 구간 모두 원래 보호 Actual이며 drive0·동일 steer·동일 양의
  friction brake인 경우에만 그 wake 조건을 생략한다. 힘/속도/pose/타이어식은 바꾸지 않는다.
  자연 수면 후 기존 steer 유지가 재기동시키던 문제를 고정 Town03/V1 시나리오에서 해결했다.
  400receipt/400정산, 첫 sleep index278부터122구간 body/wheel exact0, 마지막100구간 pose 동일.
  이는 PhysX sleep 모델의 정지이며 연속체의 엄밀 정지/OEM·전체 ODD 수용은 아니다.
- **work 증거:** 최초 수정은 sleeping zero-work 검증기의 기존 steer0 조건에 걸려 index279에서
  fail-closed했다. observer ABI2에 보호 hold witness를 추가하고 server/solver 및 이전 구간의
  원래 Actual/동일 effort를 독립 검사했다. ABI1 과거 evidence는 원래 규칙으로 검사한다.
  미세 잔류 속도·pose 변조·hold 누락·이전 effort/보호 변조5종을 거부했다.
- **clock은 미수용:** 새 post-physics 취득을 Host CLOCK_MONOTONIC begin/end로 감쌌다.
  cached receipt도 최초 bracket을 유지하며 simulation/CAN 시각을 바꾸지 않았다. 이 bracket은
  clock mapping 후보 관측일 뿐이다. 고정 offset의 교집합은 없고, 의도적 pause를 제외해도
  현재 RPC/전체 trace 경로의 취득→다음 native 처리와 owner 호출 공백이 원래 budget을 초과한다.
  단순 offset·heartbeat·timeout 증가로 정상 wall 연결을 승인할 수 없다.

남은 필수 작업은 하나의 통합 작업으로 수행한다: **정상 wall owner/수신 분리 + 원천별 clock
agreement/uncertainty + in-flight fault 차단 + CARLA 보호 Actual 연속 적용**. 이를 연결한 다음
동일 suite의 정상/영상·고장·정지·에너지 회귀와 원래2ms/4ms·30ms를 함께 판정한다.
현재 functional 시간의 native 입력을 wall로 재표기하거나 terminal local Actual을 서버에 넘기는
단축 경로는 구현하지 않았다. M7 전체는 계속 NOT CLOSED이며 별도 새 milestone을 추가하지 않는다.


<a id="m7-review-solver-전달-경로-분리와-wall-전환-가능성-조사"></a>

### Solver 전달 경로 분리와 wall 전환 가능성 조사

[현재 실행·보존 원본](../test-plan/evidence/m7_carla_wall_guard/pipeline/README.md).
기존 전체 solver trace의 즉시 JSON 생성/전송/감사를 유한 raw journal 회수로 분리했다.
원래320개 solver 값과 signed work는 모두 보존하며, 실제 physics 전 capacity guard 및
회수 후 raw/compact·wire·EV 교차 검증을 수행한다. cached source/Actual/expiry는 바꾸지 않는다.

새 CARLA suite6/6(정상·영상·보호 정지·wall-gap·work 누락·snapshot 누락), 최종 동일 바이너리의
기존/compact 영상 대조 각1/1, 일반/ASan 각93/93을 확인했다. 정상4실행의900구간과 보호400구간의
physics(generation 제외)·solver steps·motor work·Actual 값이 기존 reference와 정확히 같았다.
기본 native 경로의 기존 입력 replay도901/401개 출력이 정확히 같았다. 실패 build/phase 후보는 보존한다.

동일 바이너리의 연속 영상 대조에서 pause를 제외한 취득→다음 native 처리 평균은38.215→15.845ms,
P95는67.893→41.179ms였다. 최대값은103.017→166.566ms로 개선되지 않았고, compact에서도
266/898구간이30ms를 넘었다. 이는 진단 loop 관측으로 개별 ECU job latency/CAN source-age나
실시간 보장 상한이 아니다. 현재 정상 wall 수용은 계속 NOT ACCEPTED다.

Controller/management 시작 위상0..20ms × 정수/분수 clock42개 component 조합 중32개는
functional admission을 유지하고10개는 원래 검사에서 거부됐다. 유지된 조합도 최소 expiry
여유가 모두1ns였다. 따라서 기본14ms 위상을 유지하며 expiry/source-age를 늘리지 않는다.
같은 simulation barrier를 wall로 이름만 바꾸는 경로는 사용할 수 없다.

**실제로 남은 구현:** 새 wall-domain INIT·native owner/수신 분리, actuator/model dt와 EV work의
시간 관계, in-flight fault containment, wall-origin 보호 Actual의 CARLA 연속 적용이다.
이번 변경은 그 선행 IO 병목을 줄였으며 해당 runtime 자체를 구현했다고 표시하지 않는다.
구체 경계는 [ICD draft-v23](#icd-다음-wall-runtime의-구현-경계)을 따른다.

<a id="m7-review-새-wall-ownerio-분리-구현"></a>

### 새 wall owner/IO 분리 구현

[실행·실패 원본](../test-plan/evidence/m7_carla_wall_guard/wall-owner/README.md),
[ICD draft-v24](#icd-새-wall-owner의-구현-범위-draft-v24).
새 monotonic INIT의8-role owner와8개 고정 receipt mailbox를 구현했다. owner는 입력을 기다리지
않고 실제 timer에서 한 번씩 실행하며, 지연 후 과거 job을 재생하지 않는다. 입력 단절 후에도
원래 모델의 새 LocalProtection Actual이 계속 생성된다. 완료 work는 보호 선택 뒤에도 한 번 정산한다.

실제 timer 시험에서 정산을 ECU 처리 뒤에 반영하던 순서와 INIT/source 경계 위상 문제를 찾았다.
정산을 sensor 소비 전에 옮기고 새 wall INIT만 첫 완료 관측 이후로 배치했다. 기존 reset20ms,
Drive30ms·message age·commit deadline은 그대로다. 지연으로 안전한 INIT 근거가 없으면
원래 window 안에서 실패한다. 실패 로그/초기 verifier의 즉시 전체 ACK 가정 오류도 보존했다.

합성 stationary wheel/work를 쓰는 FIFO18의 정상2회·수신 단절2회·owner 정지1회는5/5
case 검사 통과다. 정상/수신 단절은 각7,480개의 판정 가능한 원래2ms/4ms slot에서 누락/late0,
owner 정지 주입은36개 미완료 slot을 보존하고 보호를 선택했다. 단절 검출 약22ms,
새 보호 Actual의 torque0·pressure1MPa는 선택 후 약211ms를 관측했다. 일반/ASan 각103/103,
TSan 관련16/16을 확인했다. 짧은 native component이며 실시간 보장 상한·CARLA 주행 수용은 아니다.
OTHER0 대조 중 monitor slot2개가 누락된 실행은 실패로 유지한다.

**M7은 계속 NOT CLOSED다.** 새 WallRig는 같은 monotonic domain의 wheel/10ms work만 받는다.
실제 CARLA simulation dt·EV work와 wall acquisition을 연결하지 않았으며 이 출력으로 CARLA
tick을 발급하지 않는다. 남은 구현은 그 clock/work 경계와 queued/in-flight RPC 차단,
wall-origin 보호 Actual의 연속 CARLA 적용이다. 새 CARLA 시험을 실행한 것으로 기록하지 않는다.


<a id="m7-review-실제-carla-두-시간축공유-전달-연결-결과"></a>

### 실제 CARLA 두 시간축·공유 전달 연결 결과

[이번 실행·실패 원본](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/README.md),
[ICD draft-v25](#icd-실제-carla와-wall-owner-연결-draft-v25).
새 opt-in 경로에서 원래 CARLA frame/10ms model dt·320-bin signed work를 단일 EV에 정산하고,
물리 취득의 원래 CLOCK_MONOTONIC bracket을 native 센서 원천으로 사용했다. 두 시간을
상수 offset으로 바꾸지 않는다. cached 관측의 timestamp/sequence와 원래 dependency를 유지한다.

Python/RPC가 native owner를 멈추지 않도록 같은 Host의 유한 공유 mailbox를 연결했다.
서버 game thread만 원본8-role 권한/CAN/P05 Actual을 검사하고 다음 물리를 발급한다.
완료 work 정산 ACK 전 다음 tick은 금지하고, 물리 직전/직후의 expiry·terminal latch를 확인한다.
M7 전용 Drive owner는 새 센서를 ingress에서 원래 monitor에 먼저 전달한다. 제어20/10ms와
원래4ms owner deadline·30ms source-age를 그대로 유지하며 M6 원본 owner는 수정하지 않았다.

**결과는 정상 wall 주행 FAIL이다.** 실제 취득→native 정산 지연은 분리했지만 엔진 프레임
사이 공백이 남았다. 새 입력이 없으면 원래 Drive monitor가 보호를 선택한다. render fence 대기
위치를 진단에서 관측했지만 FIFO/예열/null-RHI/inline-render 대조는 원인 제거를 증명하지 못했다.
일반/ASan 각113/113, TSan 경계26/26, 기존 정상901/보호401개 출력의 정확 재생은 component와
회귀 근거다. CARLA의 정상 wall/보호 주행 수용으로 대체하지 않는다.

초기화 중 명령을 한 번도 받지 못한 Steering/Brake는 기존 계약상 유효한 보호 측정값을
내보내지 않는다. 이를 허용하려던 후보는 폐기했고, NULL/진단 Actual을 실제 브레이크 값으로
대체하지 않았다. 따라서 이번 실제 wall 실패를 **보호 제동 성공**으로 기록할 수 없다.

**남은 필수 gate는 두 개다:** (1) 엔진 프레임 공백을 해결하고 원래 freshness/expiry 안에서
정상·영상 wall 실행을 유지하는 것, (2) 정상 세션의 wall fault→원래 LocalProtection Actual→실제
CARLA 제동/정지 및 in-flight work·sensor/writer/pause/reset 통합 검증. 별도 새 milestone을
늘리지 않는다. M7은 NOT CLOSED, M6 종료 판정과 기존 functional 검증은 그대로다.
