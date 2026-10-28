# M7-0 환경 조사와 M7-1 CARLA 최소 실행 계획

조사일 **2026-10-23 (Asia/Seoul)**, 저장소 기준 `765ed8f`, 작업 전 tracked 변경 없음.
**M7-0 조사·설계 문서 작성 완료, CARLA runtime NOT RUN**.
[M6 종료 판정](../m6_exit_review.md)·기존 검증 수치/통신/안전 계약은 유지한다.
CARLA package/client/ScenarioRunner 다운로드·설치·빌드·서버 실행은 하지 않았다.
온라인 문서/릴리스 metadata 조회와 Host read-only 점검만 수행했다.

## 2026-10-23 후속 — M7-1a 실행

사용자의 다운로드·설치 허용으로 공식0.9.16 package/별도 Python3.10 환경을 준비하고
[실행 원본·실패/재현](evidence/m7_carla_1a/README.md)을 기록했다. 양쪽 버전0.9.16·world 연결,
비주행 ego 정상/예외 생성·종료·잔존0·설정 복원을 최종 시도에서 확인했다. 원본6시도1PASS/5FAIL
(서버 미실행 negative1, world timeout2, 관측기 cache 오판2)을 모두 보존했다.
**M7-1-01 PASS, M7-1-02 ego 부분 PASS; 센서 포함02 전체와03~09 NOT RUN**이다.
아래의 M7-0 미설치/NOT RUN 문구·Host 표는 당시 조사 기록이다. 현재 실행 상태는 이 후속과
연결한 evidence를 따른다. 정상 주행·source build·M6 변경은 수행하지 않았다.

## 2026-10-23 후속 — M7-1b 실행

[실행/실패/재현](evidence/m7_carla_1b/README.md):50ms 단일 tick owner의240tick과
RGB/GT/state main 각200/200, raw frame/time·format/pose·GT 분리, 정상/예외 센서 cleanup을
확인했다. 초기 camera1frame 누락은 startup 분모에 보존했다. 실제 drop·카메라 delay/reorder/
duplicate, 실제 pause/reset·새 epoch 및 metadata replay를 검사했다.
**02~04는 해당 비주행 profile PASS,05/06은 부분 PASS**,07~09는 NOT RUN이다.
전체4시도1PASS/3FAIL·native incomplete와 server crash를 보존했다. 같은 sensor-session
client reload의 native crash는 두 wheel에서 재현됐고, 최종 한정 경로는 client retire→
fresh client→reload다. 초기1a와 다른 최종 client artifact는 서버 포함 wheel의 별도 venv로
고정했다. live overflow/10s 초과 delay·ECU timeout/old Actual은 미검증이다. 다음은 M7-1c다.

## 2026-10-23 후속 — M7-1c 논리 실행

[test-only Actual/fake backend·원래 Drive 검증](evidence/m7_carla_1c/README.md)을 완료했다.
Normal/ASan 각39/39, 관련 기존120/120 PASS. compile 경고로 실패한 첫 build와 중간 cohort는
보존했다. **07/08은 명시된 논리 범위 PASS,09는 fake/CLI 부분 PASS**이며 실제 CARLA
actuation/외부 writer·peer 인증/권한 전송·RPC 오류는 NOT RUN이다.
원래 source0/10/20/30ms 수용,30ms+1ns 거부,40ms Drive 보호 선택·fresh 입력 후 latch 유지로
50ms state/30ms conflict를 확인했다. 실제 수신 시각 restamp나 요구 완화는 하지 않았다.
후속은 인과적 substep 관측·ECU exchange·actuation/clock 설계 타당성 검토다.

## 2026-10-23 후속 — M7-1d 시간 계약 개정·실행

사용자가 world/state10ms·영상50ms 방향의 다음 작업을 승인했다. [ICD](../icd/carla_plant_adapter.md)
및 [시간 계약](../requirements/timing_requirements.md)을 개정하고 [실행 근거](evidence/m7_carla_1d/README.md)를 남겼다.
M7-0/1b의50ms world 조건은 과거 baseline으로 보존하며 현재 M7 world는10ms다.
Controller20ms·Zone/vECU10ms·Drive30ms·native guard/기존 M6 수용은 유지한다.

비주행 main state600/600·RGB/GT 각120/120과 누락·pause/reset을 확인했다.
첫 camera 간격60ms, 최초 oracle FAIL·startup 위상 수정·확인 실행을 구분해 기록했다.
논리 sampling 충돌은 해소했지만 wall100Hz는 충족하지 못했다. 실제 ECU30ms freshness는 NOT RUN이다.
최종 actor0·설정 복원 뒤 서버 SIGTERM 중SIGSEGV/139는 **OPEN-M7-1D-01**로 남겼다.
다음은 wheel telemetry·clock mapping·wall timing 비용/native guard·종료 crash의 제한된 조사다.
아래 M7-0/1b 시험표의50ms 조건/분모는 역사적 조건이며 새 실행 수치로 덮어쓰지 않는다.

## 2026-10-23 후속 — M7-1e 진단·대안

[진단 근거](evidence/m7_carla_1e/README.md): physics-on wheel 회전각 RPC 확인, 정적4조건×2회
render/camera/audit 비용 분리, platform/Host clock bracket 검사, 새3서버 종료 재현을 수행했다.
metadata 수집만으로 RTF1.014~1.033이나 실제 Drive source-age는 NOT RUN이다.
고정 offset mapping은 전체 관측에 맞지 않았고, 빈 서버TERM/INT도139로 종료했다.
다음은 별도 functional clock·8-role barrier 설계와 wheel 구간 각속도 의미 검증 계획이다.
새 source build/정상 주행 연결·기존 M6 계약 변경은 하지 않았다.

## 2026-10-23 후속 — M7-1f functional clock/shadow

[functional clock/shadow 실행](evidence/m7_carla_1f/README.md)을 추가했다. 별도 opt-in C++
harness가 실제8-role native actor의 세션·RunLease·arm·Actual 경로를 stationary SIL fixture로
실행하고, Python 단일 tick owner는 각 snapshot의 원래 elapsed time을 전달한 뒤8역할 처리
barrier를 기다린다. Normal/ASan 각14/14, 관련 기존144/144와1c39/39를 확인했다.
CARLA는 physics-off ego/RGB/GT 비주행이며 vehicle/wheel을 ECU 입력으로 전달하지 않는다.
100ms 지연·250ms pause의 논리 기능 검증은 wall freshness·native deadline 검증이 아니다.
새 run의 INIT와 old scope 거부는 native 시험, 이번 live world reload/reset은 NOT RUN이다.
다음 작은 작업은 [ICD의 wheel 계획](../icd/carla_plant_adapter.md#m7-1g-wheel-검증-계획)이다.

## 2026-10-23 후속 — M7-1g 실제 wheel/native 연결

[실행/실패 근거](evidence/m7_carla_1g/README.md):0.9.16의 직접 PhysX omega를 발견해
pitch 차분 대신 사용했다. physics-on 무동력 내리막400tick에서 실제 wheel→Drive vECU→
DriveActual CAN/P05→Rear→Central 반환396개, armed fixture322frame, 최대 source age10ms를 확인했다.
첫 native 연결은 fractional timestamp에서 pending sample을 덮어쓰는 버그로 실패했고 수정했다.
평지 native 연결은 미세 음수 wheel 때문에 여전히 FAIL이다. 임의 clamp/abs/요구 완화는 없다.
Normal/ASan 각22/22(1f14+1g8), 기존 관련144/144와1c39/39, raw oracle 변조7/7 거부.
6live 시도 중3개 수집 완료/3개 실패이며 모두 서버 종료139. M6 수용·과거 원본은 유지한다.
정상 제어 주행·actuation·energy fidelity는 미완료다. 다음은 정지 잡음의 sensor 의미,
actuator/전기 port 분리와 rad/Nm/Pa actuation 방식 결정이다. source build는 하지 않았다.

## 2026-10-23 후속 — M7-1h actuator/electrical 분리

[구현·실행·실패](evidence/m7_carla_1h/README.md): 별도 opt-in M7 owner가 actuator 응답과
EvPowerModel을 소유하며 실제 wheel 취득 이력에서 각1ms 구간 begin 이전 sample을 선택한다.
차량 운동은 적분하지 않는다. 계산 결과는 CARLA에 적용하지 않은 ZOH 모델 예측으로 표시한다.
Normal/ASan 각32/32(기존22+신규10), 기존 관련144/144·1c39/39와 실제 내리막400tick을 확인했다.
평지의 미세 음수는 SubResolutionNegative 진단 후 거부한다. 0.01rad/s wire resolution을
noise 보정 허용으로 해석하지 않았다. 평지 연결 FAIL·서버 종료139·정상 actuation 미연결은 유지한다.
다음은 actuation 방식·중복 dynamics·정지 sensor 오차 근거, applied Actual/interval work 계약이다.

## 2026-10-23 후속 — M7-1i actuation 방식 검토

[조사·오프라인 구현/검증](evidence/m7_carla_1i/README.md): 기본 throttle 역변환은 미채택하고,
PhysX NoDrive의4wheel effort를 노출하는 서버 확장안을 우선 후보로 결정했다. 설치0.9.16 binding과
공식 소스를 대조했으며 exact upstream commit/해시를 남겼다. 새 CARLA 실행·source build는 없다.
직접 rad/Nm/Pa mapping의 수학/Actual 경계 prototype Normal·ASan 각16/16, 기존 M7 각71/71.
처음 ASan1c binary 미빌드로 회귀 실행이 중단된 기록과 빌드 후 결과를 구분한다.
Brake pressure table 수치는 미확정이고 음수 측정 보정도 미채택이다. 과거 평지 무제어 접지
실패를 정상 brake-hold의 센서 오차로 해석하지 않는다. 다음은 별도 source build 범위 결정 →
직접 effort 포트·calibration artifact → 실제 보호 brake 적용/원래 wheel 검증이다.
frame receipt/interval work·서버139·wall 수용은 OPEN으로 유지한다.

## 2026-10-23 후속 — M7-1j source build/독립 SDK 포트

[실제 빌드·실행·실패](evidence/m7_carla_1j/README.md): source build 범위로 후속 착수했다.
공개 CARLA0.9.16 source 확보, 공개 PhysX3.4 CHECKED SDK 빌드·합성 Actual→NoDrive 포트
Normal/ASan 각15/15를 확인했다. 외부 SDK 자체는 sanitizer 미계측이며 vptr 검사는 제외다.
기본 적분 음수45/850 FAIL을 보존했고 world10ms 안의 차량 적분20분할 후보에서는0/850이다.
시각/배분/정지/invalid work 독립 CSV oracle와 손상8/8 거부를 확인했다. CARLA 차량 calibration은 아니다.

UE fork 접근은 Git/GitHub CLI404이며 사용자가 Epic–GitHub 연결을 설정한 적 없다고 응답했다.
공식 CARLA build 명령은 UE4_ROOT 누락으로 실패했고 UE compilation은 시작되지 않았다.
계정 연결·EpicGames 초대 수락 후 UE toolchain/fork pin → CARLA 서버 포트 → 실제 brake
calibration/보호 제동·wheel → 구간 work 순서로 계속한다. 기존 package/venv·M6는 유지한다.
원래 M7-0/1a–1i의 source build 제외 기록은 당시 범위이며1j부터 변경됐다.

## 2026-10-23 후속 — UE4.26.2 빌드 완료

[빌드 근거](evidence/m7_carla_1j_ue_build/README.md): Epic 연결 후 fork 접근 성공,
`carla` branch commit e9d9e60c85f643e10eeb03f42f61554d18dcb30f 고정.
Setup/프로젝트 파일 생성 exit0, 중단했던 make를 재개하여 전체 exit0을 확인했다.
UE4Editor 및 도구 생성, ldd missing0이며 engine tracked source 변경 없음.
editor runtime/CARLA build·정상 actuation은 NOT RUN이다. 다음은 g++-12 등 CARLA 빌드
의존성·별도 Client 환경·버전에 맞는 asset 준비와 기본 서버/client build다.
이전 fork404·UE4_ROOT 누락·중단 기록은 당시 근거로 보존한다.

## 2026-10-23 후속 — CARLA Client/서버 모듈 빌드

[의존성·실제 build 근거](evidence/m7_carla_1j_carla_build/README.md): g++-12 등 시스템
패키지 설치 확인 후 별도 Python3.10 venv에서 Client wheel과 서버 모듈을 빌드했다.
Client01 URL404/02 PROJ include/03 PROJ C PIC 실패를 보존하고 최소 build patch 후
Client04 exit0/import 성공, server01 exit0/ldd missing0을 확인했다. SimReady는 제외했다.
0.9.16 content ID는20250912_2171890이다. source Client identity는294096e-dirty이며
서버 handshake/ego/runtime·NoDrive 직접 포트는 NOT RUN이다. 다음은 source 서버 smoke다.

## 2026-10-26 후속 — source 서버 실행

[실행·실패·범위](evidence/m7_carla_1j_source_smoke/README.md): Town10HD_Opt는 최초
1800s 준비 한도를 넘겼고 추가 관찰 뒤 SIGINT에 응답하지 않아 강제 정리했다. 반복 준비
조회가 backlog를 누적시킨 관측도 보존하고, 이후 LoadMap 완료 후 조회하는 방식으로 바꿨다.
Town03_Opt 렌더링 시작에서는 distance field/GPUScene 경로 SIGSEGV를 관측했다.
시작 DisableRendering INI로 재실행하고 초기 INI/Episode 읽기값을 혼동한 harness 실패를
수정한 뒤, 비렌더링 identity/ego 정상·예외2/2 및10ms 본 관측102샘플을 검증했다.
Episode 설정 복원 후 SIGINT130과 포트/소유 프로세스 정리를 확인했다. exit0 수용이 아니다.
raw timestamp와 실패를 보존했으며 비렌더링 결과를 RGB/GT·렌더링 crash 해결로 확대하지 않는다.
기존 M6/age30ms·native guard는 유지하고 해당 wall 수용 시험은 수행하지 않았다.
후속 [렌더링 조사](evidence/m7_carla_1j_render_diagnosis/README.md)에서는 같은 바이너리의
camera 경로 SIGSEGV와 유효하지 않은 Distance Field 내부 참조를 GDB로 관측했다.
다음 GDB1회·native 같은 서버2회는 각각150tick/RGB·GT30쌍 수신·정리/설정 복원에 성공했다.
간헐 재현이며 원인은 미확정이다. shader 준비 중 체크무늬 재질·첫60ms 영상 간격도 보존한다.
완전 센서 delivery/렌더러 안정성·정상 actuation 수용은 아니다. engine patch는 적용하지 않았다.
다음은 실패 시 자원 수명 추적과 asset 준비 완료 조건의 새 native 서버 반복 검증이다.

[후속 준비/반복 검증](evidence/m7_carla_1j_render_followup/README.md): 넓은 proxy 추적은
world20s timeout으로 FAIL했고, 줄인 추적의 ego/camera는 한정 통과했다. DDC01은 exit0에도
대상 맵0개로 FAIL, 파일 경로를 고친 DDC02는10개 대상을 인식했으나 광범위 cooked 데이터
생성으로 확대돼 SIGINT 후 수동 강제 중단했다. 모두 보존하고 실제 장면 준비 관측으로 전환했다.
ego/RGB/GT 유지23,620tick·1169.091s에서 shader/Distance Field zero를10s 간격2회 확인했다.
준비 후 GDB1회·서로 다른 새 native2서버 각150tick/30쌍·정리/복원·SIGINT130을 확인했다.
샘플 RGB의 대체 체크무늬가 벽면 재질로 바뀐 것을 확인했지만 전체 content 적합성은 OPEN이다.
첫60ms 영상 간격·원래 timestamp를 보존했다. root cause 미확정이며 engine/M6 변경은 없다.
다음 작은 작업은 이 제한된 baseline의 NoDrive single-writer/frame stage·receipt 최소 서버 포트다.

## 실제 Host 관측

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

## 공식 근거와 호환성 판단

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

## M7-0 당시 코드 대조와 설계 결과

[Plant Adapter ICD](../icd/carla_plant_adapter.md)가 의미 계약의 기준이다. 아래 실제 구현을
대조했으며 문서의 설계 위치를 이미 구현된 CARLA 모듈로 오인하지 않는다.

| 구현/계약 근거 | 조사 결과 |
| --- | --- |
| [PhysicalOwner](../../simulation/runtime/m4_owner_network.cpp), [VehicleEvModel](../../simulation/vehicle/vehicle_ev_model.cpp) | 실제 actuator·vehicle/EV가 함께 step된다. CARLA motion과 병행하면 중복되므로 후속 backend 분리가 필요 |
| [SimpleVehicleConfig](../../simulation/vehicle/simple_vehicle.hpp) | mass/geometry/pressure 계수는 M6 fixture. age30ms/skew10ms/max step20ms도50ms CARLA와 직접 치환 불가 |
| [DriveController](../../vecu/drive/drive_controller.cpp), [DriveReceiver](../../interfaces/drive/drive_receiver.cpp) | wheel source/oldest dependency30ms 검사. 20Hz state의40ms task에서 stale 발생; 재발행/EV70ms option으로 해소 불가 |
| [AsyncCoordinatorPort](../../central/coordinator/async_coordinator_port.cpp), [owner-wire](../icd/owner_wire_v1.md), [ADR-0062](../adr/ADR-0062-someip-rear-host-adapter.md) | 원래 source/expiry·20ms 전달 envelope·8참여자 경계 보존 필요 |
| [P05](../../interfaces/common/e2e_profile5.cpp), [ADR-0036](../adr/ADR-0036-asynchronous-drive-actual-feedback.md) | CRC/counter와 Actual acquisition 의미 보존. 새 bridge의 도착 시각으로 재인코딩 금지 |
| [ADR-0063](../adr/ADR-0063-simple-vehicle-and-longitudinal-mil.md), [ADR-0064](../adr/ADR-0064-vehicle-ev-interval-energy.md) | 독립 Python MIL과 M6 차량/전기 구간 work의 수용 경계를 CARLA로 승계할 수 없음 |

M7-0 당시 결정한 것은 actual-only/single writer,50ms tick owner,20/10ms 기존 주기, GT 격리,
원천 identity/time/validity와 pause/reset 의미다. calibration·true substep 양방향 연동·clock
mapping·energy fidelity는 OPEN이다. **기본 패키지50ms world state로 정상 Drive 연결 불가**라는
판정을 숨기지 않으며 M7-1은 비주행 connectivity/sensor/거부 검증부터 진행한다.

## M7-1 시험 준비와 공통 증거

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

## M7-1 시험표

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

## 다음 작업 단위와 착수 판정

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

**현재:** M7-1a/b/c/d의 명시한 한정 실행 완료, [1d 결과](evidence/m7_carla_1d/README.md)의
startup/wall timing 제한·종료 crash와 기존 OPEN 유지. 다음 조사에는 착수 가능하다.
**착수 불가:** 실제 clock·wheel/Actual 경로·native guard·calibration을 입증하지 않은 정상 주행,
M6 동등 energy/안전 수용 주장. 기존 M4/SDK/DDS OPEN 전체를 M7 비주행 선행 조건으로 추가하지 않는다.
Jetson 배포/학습은 범위 밖이며 TBD-09는 Host 조사만 반영한다.

## 2026-10-26 후속 — M7-1k 최소 서버 포트

[실행·실패 기록](evidence/m7_carla_1k/README.md)의 opt-in 포트는 실제 UE NoDrive에
합성 CAN/P05 Actual0만 수용한다. 최종156개 검사(반복 포함)·13개10ms receipt와
원본 보존/손상8종 거부, 별도 client의 직접 writer·일반 tick 차단, pause/실제 physics reset,
새 session/INIT를 확인했다. flag-off 별도 서버는 기존 비주행 lifecycle2/2·102샘플을 통과했다.
서버4회 모두 설정/actor 정리 후 SIGINT130이다. 초기 build2회와 harness1회의 FAIL을 보존한다.

이는 위 M7-1-06/07/09의 **서버 진단 일부**에 대한 후속 근거이며 과거 전체 판정을
PASS로 고치지 않는다. 실제8-role 정상 연결·nonzero rad/Nm/Pa·brake calibration·구간 work,
native wall/transport timeout 실주입·평지 보호 brake 및 렌더링 안정성은 미수용이다.
다음 작업은 wheel/COM geometry의 좌표·차량 기준점 검증과 근거 있는 brake 모델 선정이다.
기존 M6 수용·ECU 주기·freshness·영상/GT 계약은 유지한다.

## 2026-10-27 후속 — M7-1l rest geometry/brake 모델안

[실행·실패·모델안](evidence/m7_carla_1l/README.md):5개 INIT 자세의 frozen-frame geometry와
reference/body/실제 COM/world/actor/프로젝트 반사 변환을 교차 검증했다. 독립 손상7종 거부·실제 reset 뒤 geometry 무효화와
새 source binary의1k156개 검사/13receipt 회귀를 확인했다. build1FAIL과 API COM 단위 가정
audit1FAIL을 보존했고 서버는 정리 후 SIGINT130으로 종료했다. sensor/actuation 시험이 아니다.

V1(M6 합산 torque law·4륜 균등 가상 EV)과 H1(실측 유압 식별)의 구체 모델안을 제시했다.
실차 보정 자료나 가상 모델의 명시적 수용 전에는 계수를 확정하지 않는다. 서버0 effort gate와
M6 계약은 유지하며 실제 조향 부호·보호 brake/raw wheel·full Actual/work/wall은 후속이다.

## M7-0 변경의 검증 범위

변경은 Markdown7개(새 문서2개·기존 연결/상태5개)다. 변경 문서의 로컬 링크/앵커121개를
정적으로 대조해 깨짐0, code fence 짝 누락0을 확인했다. `git diff --check`와 새 파일의
공백 검사에 오류가 없다. M6 종료 문서·requirements·profiles·구현·시험/evidence 파일의
변경0을 확인했다. C++/SDK/MIL 회귀와 CARLA runtime 시험은 새로 실행하지 않았다.

## 2026-10-27 후속 — M7-1m 승인 V1 nonzero 격리 진단

[실행·실패](evidence/m7_carla_1m/README.md): 사용자가 V1 가상 EV law를 수용했다.
별도 서버 opt-in·model hash/geometry 검사로 합성 Actual의 nonzero effort와 보호 Brake Actual을 적용했다.
새2서버 각1,621receipt/38검사·독립 손상9/9 거부, hold100/100 exact wheel0을 확인했다.
각487frame의 raw rear 음수는 native 전진 입력 unavailable이며 정상 gate FAIL이다. clamp/restamp 없음.
full Actual/work/EV/wall·전체 renderer 안정성은 미수용이다. 다음은 내부 적분 분할 후보의 명시적 비교다.

## 2026-10-27 후속 — M7-1n 내부 적분 대조

[같은 입력의 실제 대조](evidence/m7_carla_1n/README.md): 기본3/1·내부20/20을 별도 서버 옵션으로 구분했다.
같은 새 binary의 기본 rear 음수487frame 재현,20분할 새2서버 각3frame/1,621receipt였다.
출발 첫 tick에 약−.256rad/s가 남아 native forward gate FAIL/20분할 정상 미채택이다.
원래 Actual/시각/요구사항을 보존하며 다음40분할 또는 기존 actuator Actual trajectory의 분리 시험이 남는다.

## 2026-10-27 후속 — M7-1o 출발 적분 안정화와 wheel 원천 정정

[실행 원본](evidence/m7_carla_1o/README.md):20분할은 실제 정착과 기존 response 모델 입력에서도
출발 음수를 재현했고40/80분할도 실패했다. 읽기 전용 tire callback으로 저속 반력의 적분 진동을
확인하고320분할을 후속 격리 후보로 정했다. 최종 직접 solver source의 새2서버 stress 및
response 입력은 각1,621frame/4wheel 음수0이다. 중간 앞바퀴 미세 음수는 보존한다.
기존 공개 getter는 무구동 저속 보정값일 수 있어 `mWheelSpeeds` 직접 읽기를 별도로 추가했다.
UE commit/header hash를 고정하며 engine/M6 source·물리 계수·주기/freshness는 바꾸지 않았다.
정상 주행은 직접 원천의 native 반환·full Actual/authority·solver work/단일 EV·wall 검증 뒤 판단한다.

## 2026-10-27 후속 — M7-1p 직접 solver/native 반환

[실행·실패 기록](evidence/m7_carla_1p/README.md):320분할 step/response 새2서버의 각각1,621개
직접 solver 관측을 기존 native8-role fixture에 공급해1,609개 Actual 반환을 확인했다.
원래 acquisition을 유지해 다음 구간 끝 age 최대20ms이며 기존30ms 요구를 변경하지 않았다.
20분할의 실제 음수와200번째 snapshot 전달 누락 주입은 native barrier 없이 다음 tick을 차단했다.
Normal/ASan 각60/60, frozen replay 각1,621개와 손상29종 거부·독립 live audit 손상8종 거부를 확인했다.
최초 receipt보다 snapshot stream이 늦은 FAIL 및 당시 cleanup latch 검사 FAIL은 보존한다.
동일 frame 도착까지 조회만 기다리고 모든 실패 경로를 latch하도록 고쳤다. 수정 후 누락 주입은
cached receipt로 회복하지 못했으며6개 소유 서버 모두 설정/actor 정리 후 SIGINT130이었다.
native sensor 반환만 연결했고 CARLA actuation은 합성 Actual이다. 다음은 full Actual/authority 적용
gate → solver work/단일 EV → wall 검증이며 renderer·AI/Jetson·M6 전체 회귀는 이번에 실행하지 않았다.

## 2026-10-27 후속 — M7-1q 실제 native Actual의 서버 적용

[실행·실패·제한](evidence/m7_carla_1q/README.md): 원본 Actual/CAN/P05, 실제8-role Release ACK·
Run credit, 인과 명령과 permission의 전체 다음10ms 유효성을 검사하는 별도 서버 모드를 구현했다.
새2서버 각400tick/319정상 권한 구간, 최종 약0.291m/s 전진을 확인했다. 값·source 재발급이나
명령 우회 없이 native→CARLA 기능 경로를 연결했다. M7 전용 INIT offset8ms로 기존20/10ms 위상을
맞췄고 Drive30ms/기존 expiry는 유지한다. 초기 즉시 INIT의 구간 coverage FAIL을 보존했다.
Normal/ASan 각64/64, 원본 wire/physics 독립 검사와 권한·명령·snapshot 누락 시 다음 tick 차단을 기록한다.
최소 command expiry 여유1ns는 고정 simulation clock 경계이며 wall2/4ms 수용이 아니다.
다음 M7-1r은 solver 구간 work의 완전성/누락 검출 → 단일 EV 정산 → 원자적 실패 처리다.
모델 전기는 ZOH 예측으로만 표기하고 `interval_work_valid=false`를 유지한다. M6/engine 원본·V1 계수는
변경하지 않았으며 일반 주행 시나리오/renderer·AI 학습·Jetson·M6 전체 회귀는 이번에 실행하지 않았다.

## 2026-10-27 후속 — M7-1r 완전한 solver work·단일 EV 정산

[실행·실패·제한](evidence/m7_carla_1r/README.md): NoDrive 적분 전후320개 구간을 원래 dt/토크와
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

## 2026-10-27 후속 — M7-1s 종료 경합 수정

[원인·실행·실패](evidence/m7_carla_1s/README.md): 실제 pinned CARLA Listener/Router의
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


## M7 통합 검증 — 2026-10-27 현재 판정

후속 작업을 개별 승인 단계로 계속 나누지 않고 주행·회생/마찰 제동·정지/재출발·영상/state·
누락·pause/reset·종료·wall 계측과 독립 audit를 묶어 실행했다.
[통합 실행 원본/실패](evidence/m7_carla_integrated/README.md), [종료 검토](../m7_exit_review.md),
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


## 종료/보호 연결 후속 검증 (2026-10-28)

[원본·실패·실행 명령](evidence/m7_carla_recovery/README.md)을 따른다.
동기 RPC가 아직 game thread에 dispatch되지 않은 상태에서 Stop을 호출하는 component 재현과,
실제 fresh CARLA 로딩 중 SIGINT→30s 내 종료를 검사한다. 기존 네트워크 경합 수정과 구분한다.
`m7_integrated_run.py --cases protection camera-a work-missing loading-abort`로 정상/보호/영상/누락/종료
회귀를 재현할 수 있다. 보호 case는 원래 native 안전 선택 후200개 physics 구간과 단일 EV 정산을
이어간다. 원래 Actual/P05/freshness/출처를 독립 감사하고 보호 proof 손상·정상 재개를 거부한다.
원래 M6 판정, 과거 실패, wall2/4ms 미수용·차체 완전 정지 미수용은 유지한다.

## 독립 wall guard 검증 (2026-10-28)

`m7_integrated_run.py --cases wall-gap camera-a protection`으로 실행한다.
wall-gap은199 physics 구간과 모든 EV 정산을 완료한 뒤 다음 입력을 보류한다.
native가 선언한 첫 release 이후 실제 owner0..8의 미완료를 독립 monitor가 검출해야 한다.
원래2ms/4ms·latched fault를 유지하고, late finish/heartbeat/동일 slot 중복으로 누락을 숨기지 않는다.
명시적 PROTECT/압력 주입 없이 native local 보호 선택·credit0·다음 frame 없음·동일 barrier time과
adapter pause 이후 frame 불변을 확인한다. `audit_m7_wall.py`가 CSV/원본 trace 및5종 손상을 검사한다.
물리 제동 PASS가 아니며, in-flight RPC fault·연속 owner scheduling/clock mapping은 후속 시험이다.
기존 normal900/영상·functional 보호400 회귀와 원본 비교도 함께 수행한다.
실행 중단/강제 종료, TSan 초기 실행 실패와 process-local ASLR 해제 후 결과는
[해당 실행 근거](evidence/m7_carla_wall_guard/README.md)에 분리 기록한다.

## Actuator/EV 독립 진행 선결 검사 (2026-10-28)

`M7DeferredWork.*`는 work 부재 중 response 지속·원래 취득 시각 유지, 과거 coil 기반 지연 정산과
signed EV 장부 동등성, fractional tail, 정산 실패/중복의 actuator rollback 금지, stale current의
opening dwell 금지, wheel identity 변조와 coupled/deferred 혼합 거부를 검사한다.
원래 M7 전체 CTest와 ASan/UBSan 검사를 실행하고 `replay_m7_native.py`로 기존 정상/보호
trace의 WORK/WHEEL/PROTECT 입력을 재생해 모든 native 출력을 비교한다. replay는 새 CARLA
실행이 아니며 원래 physics/센서/종료 PASS 분모에 합산하지 않는다.
[실행·오류·제한](evidence/m7_carla_wall_guard/deferred-response/README.md)을 따른다.

## Terminal native service 후속 검사 (2026-10-28)

`M7TerminalResponse.*`는 동일 native8-role 상태의 보호 Actual 지속·EV/wheel 원시 시각 동결,
fractional barrier handoff, 정상 재진입/다른 thread/역행 시간 거부를 검사한다.
`probe_m7_terminal.py`는 기존 raw 입력200개를 정확히 재생한 뒤 stdin을 열린 채 보류하여
독립 wall fault를 유발한다. 새 CARLA 실행은 `m7_1o_run.py --solver-work --native-fault wall-gap
--terminal-response --vehicle-substeps 320`과 기존 source/engine/python/fixture/native 인자로 수행한다.
`audit_m7_terminal.py`는 원본 wire/P05·Actual provenance·clock/EV 불변·실제 wall CSV 및8종 손상을
검사한다. 순수 idle 전용 `audit_m7_wall.py`와 구분하며, terminal service의 누락/late도 그대로 보고한다.
정상/ASan 회귀·TSan과 기존901/401개 출력 replay를 별도 기록하고 CARLA physics 분모에 합산하지 않는다.
[실행·실패·재현](evidence/m7_carla_wall_guard/terminal-response/README.md)을 따른다.


## 종료·보호 정지·clock 일괄 후속 검사 (2026-10-28)

[원본/실패/판정](evidence/m7_carla_recovery/batch-closeout/README.md)의 단일 suite를 사용한다.
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


## Solver 기록 경로 분리 검증

기존 suite에 `--compact-work`를 추가하고 normal-a/camera-a/protected-sleep/wall-gap/work-missing/
snapshot-stop을 실행한다. journal 원시 steps·compact mean·원래 frame/ticket/scope를 교차 검사한다.
완전 trace 회수 후 기존 Actual/wire/P05·solver 방정식·EV 장부 감사와 body 정지 검사를 유지한다.
추가5종의 journal ticket/frame/session/generation/mean 변조를 거부한다. capacity/원본 복사/중복·
skipped frame/ABI 오류는 CTest에서 검사한다. default-off와 compact 영상을 동일 바이너리로
연속 실행하고 physics/solver/work의 정확한 동등성 및 원래 monotonic 통계를 비교한다.

`m7_phase_probe`의42개 synthetic 조합은 원래 admission/expiry 규칙을 유지한 시작 위상 조사다.
실패 조합을 PASS로 합산하지 않는다. 일반/ASan 회귀와 기존 native901/401개 출력 replay를
함께 수행한다. [실행 결과](evidence/m7_carla_wall_guard/pipeline/README.md)의 정상 wall gate는 계속 OPEN이다.
