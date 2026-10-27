# M7-1l — rest geometry 검증과 brake 모델안

2026-10-27 KST. 선행 [M7-1k](../m7_carla_1k/README.md)는 `3e6bc9c`로 커밋·푸시했다.
이번 범위는 **읽기 전용 geometry 검증과 검토 가능한 brake 모델안**이다.
정상 주행·nonzero effort·pressure calibration 수용은 아니다. M6 코드·계약·기존 수치는 유지한다.

## 실제 구현·빌드·실패

[서버 구현/계약](../../../../tools/carla/m7_nodrive/README.md)의 기존 generic RPC에 `geometry`를
추가했다. owner/run/session과 physics generation을 검사해 reference bone·offset,
actor/mesh/body/COM pose와4wheel rest 중심을 SI로 반환한다. tick/actuation setter는 호출하지 않는다.
physics generation 변경 후 새 INIT 없이 이 geometry를 유효하게 재사용할 수 없다.

CARLA `294096eb1c38eabf246e4f3a9cdab704e33a7f4c`, UE4.26.2
`e9d9e60c85f643e10eeb03f42f61554d18dcb30f`를 유지했다. Client/Server 관측 identity는
`294096e-dirty`다. Client wheel/API는 바꾸지 않았으며 서버 확장만 다시 빌드했다.
[기존 binary 백업](baseline-backup.json), [최종 설치 소스 hash](source.json),
[실행 artifact·원본 보존 검사](artifacts.json)를 남긴다.

[빌드 시도](builds.json): build01은 exit2 FAIL이었다. `BodySetup`의 weak pointer를 bool로
사용한 오류와 `MakeShared`의 shared-ref에 불필요한 `ToSharedRef`를 호출한 오류였다.
해당 타입 사용을 수정한 build02는 exit0이다. engine·M6 소스/solver 변경은 없다.
원본 compiler 로그는 외부 위치/hash로 보존했고 성공 뒤 과거 FAIL을 바꾸지 않았다.

## 실제 실행과 독립 감사

[geometry01](geometry01/result.json)은 전용2200/Town03_Opt/mkz_2020, traffic/TM 없음,
시작 DisableRendering·Episode no_rendering 설정이다. actor는 spawn point보다3m 높게
생성했고 physics enabled, bind 중 tick0·actuation0으로 유지했다. 이는 contact/hold 시험이 아니다.
INIT 자세는 yaw0/90/−90/180과 yaw37/pitch7/roll−4의5개다. actor를 teleport해 주행하지 않았다.
각 ego는 lifecycle close로 종료했고 설정 복원·차량 잔존0을 확인했다.

최초 [audit FAIL](audit01-public-com-unit-fail.json)은 공개 `center_of_mass`를 cm로 가정해
한 번 더100으로 나눈 데서 발생했다. 정확한 source chain은 다음과 같았다.

1. 서버 `GetVehiclePhysicsControl`은 실제 COM 대신 `BodyInstance.COMNudge`를 넘긴다.
2. RPC의 `center_of_mass`는 `geom::Location`이고 그 FVector 변환은 이미 cm→m를 수행한다.
3. API 관측`[0.3,0,-0.2] m`와 extension의 nudge가 일치한다. 실제 COM은 다른 값이다.

[수정 후 audit](audit02.json)은 동일 원본 geometry를 사용해5자세를 통과했다. runtime 데이터를
바꾸거나 오차 한계를 완화하지 않았다. [감사 도구](../../../../tests/integration/carla/audit_m7_1l_geometry.py)는
CARLA math를 import하지 않고 quaternion/matrix 계산으로 다음 경로를 대조한다.

- reference bone/mesh scale/root-body reference pose + class/setup offset → body rest center.
- 실제 COM pose × PhysX COM-relative center → body center, UE resting position과 비교.
- body→world→actor 및 INIT 자세 사이 actor 기준 geometry 불변성.
- radius cm→m, steer deg→rad, max brake Nm의 공개 API readback.
- 프로젝트 y-left 반사`S=diag(1,-1,1)`, quaternion`[-qx,qy,-qz,qw]`, nominal rear rest 중심의 world 변환.

사전 계산 비교 예산은`64·2^-23·max(1,좌표 크기)`이며 world→local에는 원래 world 좌표 크기도
포함한다. float32 변환 연산의 보수적인 비교 예산일 뿐 센서 epsilon/실차 오차 수용이 아니다.
최대 대조 차이는 약`6.59e-6 m`였다. 초기 audit02는 unit100배·휠 순서·COMNudge/실제 COM 혼동·
Y부호·rear 기준점0·NaN의 손상6종을 거부했다. 별도 새 서버의 [최종 geometry02](geometry02/result.json)/
[audit03](audit03.json)은 같은5자세를 검증하고, 같은 frame의 다른 actor geometry까지 **손상7종을 거부**했다.
run/session/actor를 함께 검증하며 frame만으로 join하지 않는다. 실제 physics reset 뒤 generation이
변한 geometry 조회도 `geometry_generation`으로 거부되고 frame은 진행되지 않았다.

| 해당 asset의 zero-yaw 관측 | 값/의미 |
| --- | --- |
| wheel order | FL/FR/RL/RR, index0/1/2/3. 실제 bone 이름과 local 축으로 대조 |
| 실제 COM/body | 약`[0.212369,0.000294,0.549693] m` |
| API COMNudge | `[0.3,0,-0.2] m`, 실제 COM을 대체하지 않음 |
| nominal rear rest/actor | 약`[-1.388633,0,0.359541] m` |
| wheelbase/front track | 약2.86047m / 1.59292m |
| radius/max brake | 각0.355m / 800Nm |
| chassis mass | 1696kg. 기존 M6의1000kg와 다르며 motion/응답 수용을 승계하지 않음 |

이 rear 기준점은 **body에 고정된 nominal rest 중심**이다. suspension 변위에 따른 동적 wheel
center/contact patch로 보고하지 않는다. nonzero steering 부호, 동적 rear 기준점 속도
`v_rear=v_COM+ω×r`, 조향/차량 운동은 별도 시험이다. raw 관측값을 임의로0/반올림해 입력하지 않았다.

같은 새 binary에서 기존 [M7-1k 회귀](regression1k/result.json)는 **156개 검사(반복 포함)·
13개10ms receipt/2session**을 통과했다. [독립 감사](audit-regression1k.json)의 손상8종도 모두
거부했다. geometry만 읽었을 때 single writer/tick·Actual-only0 gate가 바뀌지 않았음을 확인한다.
[서버01](server.json)/[02](server02.json)는 자기 actor/설정 정리 후 소유 PID에 SIGINT를 보내
각각 tool exit130으로 종료했다.
전용 포트 잔존0이다. 기존 Vulkan handled ensure/content 경고는 남으며 renderer 원인은 OPEN이다.
새 RGB/GT·전체 M6 회귀·sanitizer·native wall/8-role 주행은 실행하지 않았다.

## 브레이크 모델 선택안 — 아직 미채택

[구체 모델안/known·unknown 파라미터](brake-model-proposal.json)은 `DRAFT_NOT_APPROVED`이며
`runtime_enabled=false`다. 서버의0 Actual 제한을 유지한다. 실제 MKZ 유압 자료는 확보하지 못했다.

| 안 | 제안 내용/근거 | 남은 결정 |
| --- | --- | --- |
| V1 가상 EV | 기존 [M6 정의](../../../../simulation/vehicle/simple_vehicle.hpp)의 합산0.001Nm/Pa를 reference law로 사용하고4륜에 균등 배분하는 제안. 각0.00025Nm/Pa,200kPa에서각50Nm·1.5MPa에서각375Nm | 균등 배분은 새 가상 모델 선택이며 명시적 수용이 필요. M6 gain을 MKZ calibration으로 부르지 않음. 아직 미적용 |
| H1 유압 식별 | 정의된 pressure 관측 위치/회로, 피스톤 면적·유효 반경·효율·마찰·onset으로 wheel별 capacity를 식별 | 모든 해당 파라미터/자료 미확정. wheel radius 또는800Nm만으로 식별 불가 |

V1은 실제 차량을 복원하는 대신 기존 SIL의 **합산 torque law**를 명시적으로 이어가는 모델안이다.
M6의 mass·radius·motion/energy 모델을 CARLA와 함께 적분하지 않는다. 기존 수용 수치와 같은
감속/hold/230ms 응답을 보장하지 않는다. 입력은 취득된 Pressure Actual이므로 추가 lag/filter를
붙이지 않는다. 제안 범위의 각375Nm가 asset800Nm보다 작다는 것은 산술 비교이며 실제 제동 PASS가 아니다.

H1의 검토식은`P_w=α_w·P_actual`,
`T_capacity,w=2 μ_eff,w A_one_side,w r_eff,w η_w max(P_w−P_threshold,w,0)`다.
두 패드 힘이 같은 이상적인 구조라는 **모델 가정**이며 `A_one_side`는 한쪽 피스톤 면적 합이다.
모든 피스톤을 합한 뒤 다시2를 곱하지 않는다. onset 이후의 capacity law와 기존 압력 actuator
동특성을 구분하고, actual pressure가 어느 위치에서 취득됐는지도 먼저 바인딩한다.
[MathWorks Disc Brake](https://www.mathworks.com/help/sdl/ref/discbrake.html)는 pressure·피스톤·
마찰·반경의 관계와 정지/회전 상태를 구분한다. 문서 default 수치를 차량 값으로 채택하지 않았다.
[Brembo 설명](https://www.brembo.com/en/news-archive/5-factors-that-make-a-brembo-braking-system-unbeatable)은
clamp force·friction·effective radius의 의존성을 뒷받침하며 MKZ parameter 자료가 아니다.

NoDrive에는 nonnegative brake capacity를 전달하고 정지 반력을 adapter가`−sign(ω)`로
만들지 않는다. 하나의 PhysX 입력이 별도 static/kinetic 마찰 curve의 식별을 증명하지 않는다.
정확한 UE fork의 setter를 조사했으며 index/음수 검사 후 저장하고800Nm 상한을 자동 적용하지 않았다.
후속 adapter가 승인된 상한/범위를 검사해 초과를 **거부**해야 하며 silent clamp를 하지 않는다.
[조사 source 경로/hash·웹 근거/제외한 자료](research.json)를 남긴다. upstream
[PhysX3.4 header](https://github.com/NVIDIAGameWorks/PhysX-3.4/blob/master/PhysX_3.4/Include/vehicle/PxVehicleNoDrive.h)는
API 근거이며 PhysX5.4 자료를 현재 binary의 증거로 사용하지 않았다.

다음은 V1의 명시적 수용 또는 H1 자료 확보 → 그 모델의 isolated nonzero/hold/release·raw wheel →
실제8-role full Actual interval → solver work/단일 EV·외부 응답 budget/wall timing이다.
현재 geometry 식별은 한정 완료했으며 brake calibration/정상 주행 gate는 계속 **BLOCKED**다.
