# M7-1n — V1 차량 내부20분할 대조 / native gate FAIL 유지

2026-10-27 KST. V1 nonzero 격리 결과를 `9b7b925`로 커밋·푸시한 뒤 이어서 진단했다.
**20분할로 음수 문제가 크게 줄었지만 해결되지 않았다. 정상 주행 gate는 계속 FAIL이다.**
V1 law/geometry·Actual-only·single writer·10ms world·30ms freshness·M6 계약은 유지한다.

## 변경과 실제 빌드

기존 V1 flag에 **별도 서버 옵션** `-StrataM7V1Substeps20`을 함께 지정한 경우만
NoDrive wheel sim data의 low/high 내부 step count를 모두20으로 설정한다.
V1 flag 없이 이 옵션만 지정하면 extension 요청을 거부한다. 기본값은 asset 설정3/1 그대로다.
client가 count를 요청해 설정하는 API는 없고 native/정상 실행의 기본을20으로 바꾸지 않았다.
`physics.numerical_profile`, low/high count·5m/s threshold를 실제 live PhysX readback으로
binding/모든 receipt에 남긴다.20분할 profile은 pre/post-physics에서20/20을 검사한다.
reset 뒤 동일 진단 설정을 재생성하더라도 generation/latch 때문에 새 INIT 없이 tick하지 못한다.

[소스 경로/hash와 수치 계약](numerical-contract.json)을 기록했다. 정확한 UE fork의
`PxVehicleWheels.h` setter/getter, `PxVehicleUpdate.cpp`의 NoDrive→computeNumberOfSubsteps,
UE movement의 기본3/1·threshold5m/s를 확인했다. low/high 모두20이므로 임계 속도를 넘어도
해당 내부 분할 수가 같다. 외부10ms world/timestamp·CAN sampling 주기를20배로 바꾸거나
추가 sensor sample을 만든 것은 아니다. tire law/solver/engine source·actuator delay/ramp는 바꾸지 않았다.

[기존 module 백업](baseline-backup.json), [build01 exit0/44.10s](builds.json)을 보존한다.
CARLA/UE commit과 client/server `294096e-dirty`는1m과 같고 client build는0회다.
[설치 source](source.json)55개/원본 M6 receiver·codec24개의 hash와 [binary](artifacts.json)를 남긴다.
별도 runtime 준비01은 이미 존재하는 backup 디렉터리와 이름이 겹쳐 `FileExistsError`로
실패했다. 덮어쓰거나 서버를 띄우지 않았고, 준비02에서 runtime 이름을 분리했다([기록](setup.json)).
compiler/build FAIL은 이번 단계에 없었다.

## 같은 입력의 실제 대조

전용2200/Town03_Opt/mkz_2020/spawn0, no traffic/TM/camera, startup DisableRendering와 Episode
no_rendering, physics-on이다. 새 서버3개를 사용해 각각1,621receipt/42검사를 실행했다.
시험은1m과 같은 settle/200kPa/300Nm step launch/−200Nm motor/마찰 정지/hold/release/좌우 turn이다.
보호 Brake Actual은 실제 native codec의 `FailSafe/LocalProtection` metadata를 사용한 합성 fixture다.
실제8-role 보호 authority/정상 주행을 연결한 것은 아니다.

| 실행 | 실제 vehicle count | 전체 raw wheel 음수 sample | rear 음수 frame/native unavailable | 판정 |
| --- | --- | --- | --- | --- |
| [baseline](baseline/result.json) |3/1 |671 |487/1,621 | native forward FAIL 재현 |
| [20a](substeps20a/result.json) |20/20 |6 |3/1,621 | native forward FAIL |
| [20b](substeps20b/result.json), 새 서버 반복 |20/20 |6 |3/1,621 | native forward FAIL 재현 |

각 [baseline audit](audit-baseline.json)/[20a audit](audit20a.json)/[20b audit](audit20b.json)는 원래
CAN/P05·mode/epoch/source/expiry·SI/float32·geometry/mapping·원래 interval/clear·수치 profile을
독립 검사하고 손상10종을 거부했다. 그 외 외부 writer 차단, pending nonzero pause/reset 폐기,
single-use ticket, generation·ego/설정 정리 검사를 유지했다.

[대조 도구](../../../../tests/integration/carla/m7_1n_compare.py)/[대조 결과](comparison.json)는
CARLA를 import하지 않고 저장된 원래 입력과 관측을 비교한다.
세 실행은 요청값뿐 아니라 **원래 CAN/P05 전체 payload·source/oldest/expiry·logical interval까지
동일**하다. fixed tick/render/substep 세계 설정과 모델 hash도 같다.
새 binary의 기본 설정1,621개 physics 관측은 이전1m effort02와 전부 정확히 같았다.
20a/20b의1,621개 wheel/body 관측도 정확히 같았다. client에서 출력값을 clamp한 효과가 아니다.
이 입력/차량/위치 범위에서 내부 subdivision이 결과에 영향을 준다는 대조 근거이며,
원래 모든 음수의 유일한 근본 원인이나 전체 ODD 안정성을 증명하지 않는다.

## 남은 실패와 다음 작업

[음수 원본 관측](negative-observations.json)과 각 raw JSONL을 보존했다.
20a/20b 각각 **직진·좌·우 launch 첫 frame**에서 rear2wheel이 음수다.
범위는 약−0.25525..−0.25674rad/s이며 body forward는 약+0.006m/s였다.
나머지 관측 phase에서 음수가 없었다고 이3frame을 warmup/무효 기간으로 제외하지 않는다.
Drive30ms freshness·native forward 검증도 완화하지 않는다.
`candidate_no_negative_in_sampled_cases=false`이고20분할을 정상 profile로 채택하지 않았다.

hold100/100frame exact4wheel0·출발/감속·좌우 부호라는 한정 criteria는 통과했다.
`PASS_RECEIPT_RUN`/`PASS_MAPPING_AUDIT_ONLY`/`PASS_CONTROLLED_COMPARISON_ONLY`는 각각 해당
적용·감사·대조 범위를 뜻하며 **native forward gate PASS가 아니다**.
native sensor/8-role loop는 이 diagnostic에 연결하지 않았다. 정상 경로라면 이 frame에서
unavailable/latch·추가 tick 차단을 유지해야 한다.

다음 작은 작업은 동일 step Actual 스트레스에 대한40분할 후보·수렴 대조 또는 실제 기존
actuator owner가 생성한 원래 Actual trajectory의 분리 시험이다. 후자는 adapter에 ramp를
추가한다는 뜻이 아니며, 스트레스 FAIL을 삭제하거나 정상 trajectory 수용으로 전체 ODD를
확대하지 않는다. 아직40분할은 이 CARLA 서버에서 NOT RUN이다.
그 후에도 실제8-role full Actual dependency/권한/interval, solver 구간 work/단일 EV,
native wall2/4ms가 남는다. 현재 interval work/회생/SOC는 unavailable다.
AI/Jetson·새 RGB/GT·renderer 원인·전체 M6/sanitizer/wall 시험은 NOT RUN이다.

같은 새 binary의 [zero-only 회귀](regression1k/result.json)는156개 검사/13receipt를 통과했고
[독립 감사](audit-regression1k.json)는 손상8종을 거부했다. 기본 flag-off lifecycle은 이 단계에서 재실행하지 않았다.
소유 서버4개는 actor/설정 정리 뒤 각각 SIGINT130으로 종료했다. 원래 crash/content/Vulkan 경고와 과거 모든 FAIL은 그대로 보존한다.

[검증 범위](validation.json): 기존 frozen 항목1022개를 다시 hash 검사했고 변경하지 않았다.
