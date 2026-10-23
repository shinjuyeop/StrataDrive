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

## M7-0 변경의 검증 범위

변경은 Markdown7개(새 문서2개·기존 연결/상태5개)다. 변경 문서의 로컬 링크/앵커121개를
정적으로 대조해 깨짐0, code fence 짝 누락0을 확인했다. `git diff --check`와 새 파일의
공백 검사에 오류가 없다. M6 종료 문서·requirements·profiles·구현·시험/evidence 파일의
변경0을 확인했다. C++/SDK/MIL 회귀와 CARLA runtime 시험은 새로 실행하지 않았다.
