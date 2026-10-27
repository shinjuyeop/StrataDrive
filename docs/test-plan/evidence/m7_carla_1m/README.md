# M7-1m — 사용자 수용 V1과 실제 NoDrive nonzero 격리 검증

2026-10-27 KST. 선행 M7-1l은 `dfae604`로 커밋·푸시했다. 사용자가 이전 V1 제안에
“그래 그렇게 가자”로 동의했으므로 **V1 가상 EV law를 수용**했다. 실제 MKZ/OEM hydraulic
calibration, M6 응답·에너지 수용 승계, 정상8-role 주행 연결 승인은 아니다.
기존1l의 `DRAFT_NOT_APPROVED` artifact와 모든 과거 FAIL은 수정하지 않는다.

## 결정과 구현

[승인 모델](../../../../tools/carla/m7_nodrive/virtual_ev_v1.json)은 기존 M6의 **합산**
0.001Nm/Pa를 참조하고, 새 가상 선택인4륜 균등25%를 사용한다.
각 wheel은200kPa에서50Nm,1.5MPa에서375Nm이며 실제 asset 상한800Nm를 넘지 않는다.
이는 pressure에 대한 brake **capacity demand**이고 정지 반력의 측정값이 아니다.
기존 actuator owner가 지연/고장을 맡으며 adapter는 lag/filter/차량 운동/전기를 중복 적분하지 않는다.
차량 mass1696kg/radius.355m는 M6의1000kg/.3m와 달라 과거 감속/230ms/에너지 수용을 승계하지 않는다.

[서버 포트](../../../../tools/carla/m7_nodrive/README.md)는 기존 zero-only와 별개인
`-StrataM7V1Probe`로만 켠다. 두 flag 동시 지정은 거부하며 기본은 disabled다.
owner key/run/session과 정확한 모델 SHA256을 요구한다. 모델 상수는 승인 JSON에서 설치 시
생성하고 서버에 컴파일하므로 client가 계수나 approval flag를 보내 해제할 수 없다.
실제 bone·COM x,y offset·radius·max steer/brake·mass가 고정 모델과 다르면 bind/stage/apply를 거부한다.

원래 native CAN/P05 Actual receiver12개를 수정 없이 UE clang10/libc++ C++17로 사용한다.
통과한 decoded Actual에서만 이상 Ackermann(프로젝트 좌+→UE 우+ 음수), rear motor50:50,
4륜 brake capacity를 계산한다. 초과를 clamp하지 않는다. Nm는 UE kg·cm²/s²로10000배,
rad는 그대로 float32 setter에 넣는다. pre-physics 한 번 적용 → post-physics 정확한 float32
demand 대조·원래 Actual/source/frame receipt →12개 persistent setter를 모두0으로 제거한다.
pause/reset은 nonzero pending도 폐기·latch하며, 실제 physics generation 변경 뒤 자동 재무장하지 않는다.

## 실제 빌드와 실행

CARLA `294096eb1c38eabf246e4f3a9cdab704e33a7f4c`, UE4.26.2
`e9d9e60c85f643e10eeb03f42f61554d18dcb30f`를 유지했다. 관측 Client/Server는
`294096e-dirty`이고 client를 새로 빌드하지 않았다. [기존 module 백업](baseline-backup.json),
[build01 exit0/131.68s](builds.json), 설치/원본24파일 hash와 binary를 별도 artifact에 기록한다.
이 단계의 compiler/build FAIL은 없었다. 기존 과거 compiler/renderer 실패가 해결됐다는 뜻이 아니다.

전용2200/Town03_Opt/mkz_2020, traffic/TM/카메라 없음, startup DisableRendering와 Episode
no_rendering을 사용했다. Ego는 기존 spawn point0에서 생성, physics enabled다.
world10ms, engine vehicle 기본 내부 subdivision, Controller/Zone/Drive freshness 변경 없음이다.
공개 SDK에서 검토했던20분할 후보를 이 실행에 적용하지 않았다. stock engine/gear/filter는 NoDrive에서 제외한다.

[effort01](effort01/result.json)은 NormalPath synthetic Actual을 사용했다.
[effort02](effort02/result.json)는 별도 새 서버에서 settle/마찰 정지/hold를
`FailSafe/LocalProtection` Brake Actual로 만들어 반복했다. 원래 M7 fixture를 해당 metadata
선택만 확장해 새 binary `m7-1m-fixture`로 빌드했으며 이전 fixture binary를 덮지 않았다.
이는 **합성 Actual의 mode 전달 시험**이며 실제 ECU의 보호 검출/authority 시험이 아니다.

두 실행 각각 runtime38검사와1,621개의10ms receipt(물리 진행한3session, nonzero1,601개)를 얻었다.
그 외1session은 nonzero stage 후 pause로 tick 없이 폐기했다.
원래 CAN/P05 전체 bytes·source/oldest/exclusive expiry·원래 frame/시각·signed wheel을
[JSONL01](effort01/receipts.jsonl)/[JSONL02](effort02/receipts.jsonl)에 보존했다.
staged는 apply가 아니고 queued는 physics receipt가 아니다. timeout 재시도 advance는 없다.
양쪽 모두 owner/model identity, Command/CRC/range/expiry 거부, foreign 직접 control 거부,
single-use ticket, pause/reset pending 폐기·setter clear·새 INIT 및 actor/설정 정리를 확인했다.

| 관측 단계, 각 실행 | 관측 결과 / 범위 |
| --- | --- |
| settle100frame·1.5MPa |4wheel exact0 100/100. 초기 body는 낙하/접지 중이며 정적 hold의 독립 증거가 아님 |
| capacity200kPa1frame | 각50Nm setter readback. 실제 디스크 마찰계수 식별 아님 |
| launch300frame·300Nm | body forward 최종 약1.449m/s. 첫 frame은 약−0.00293m/s; raw 음수 숨기지 않음 |
| negative motor100frame·−200Nm | forward1.425→1.121m/s. 전진 중 signed motor effort 감속이며 회생/SOC 수용 아님 |
| friction stop200frame·1.5MPa |199frame exact4wheel0, 끝 body velocity0. braking reaction/work 미관측 |
| hold100frame·1.5MPa |100/100 exact4wheel0, body velocity0/pose 동일. 이 위치·기간 한정 |
| release20frame |12setter0, raw wheel0·sleeping 정지 유지. 모든 slope/roll-away 시험 아님 |
| left/right 각settle100+turn300 |δ±.2rad, yaw 적분 UE 약−.14821/+.14855rad. 좌우 부호 확인, 전체 경로 추종/ODD 아님 |

[독립 감사01](audit01.json)/[02](audit02.json)는 CARLA/서버 mapping을 import하지 않고
원래 CRC·metadata·session/generation·source/interval·SI/float32·Ackermann/후륜배분·clear와
동적 summary를 다시 계산했다. 각각 손상9종(model/actor/CRC/expiry/clear/Nm/energy/NaN/조향 부호)을
모두 거부했다. 조향 대조의2^-22rad 연산 예산은 libm→float32 비교용이며 sensor validity epsilon이 아니다.

## 남은 실제 실패 — 정상 gate 유지

**두 실행 모두 native forward gate FAIL.** 각1,621frame 중 rear 음수487frame,
전체 wheel 음수671sample이다. launch138frame/negative motor47/left154/right148에서
rear 값이 기존 전진 전용 입력 계약을 만족하지 않는다. 최소 wheel 값은 약−7.404rad/s다.
이것은 작은 정지 잡음이라고 축소하거나 abs/0/epsilon으로 보정할 결과가 아니다.
보호 brake로 hold가 되더라도 주행 sensor gate가 자동으로 해소되지 않는다.

이 diagnostic에서는 native8-role loop/sensor input을 **연결하지 않고** signed 물리 관측을
기록했다. 정상 native 경로에서는 unavailable/latch·추가 tick 차단이 유지된다.
`PASS_RECEIPT_RUN`/`PASS_MAPPING_AUDIT_ONLY`는 위 격리 적용·관측 범위만 뜻하며
raw wheel gate·정상 주행 PASS가 아니다. 원인에 solver 내부 적분이 관여하는지 아직 입증하지 않았다.

후속은 내부 적분 subdivision 후보를 **별도 명시 profile**로 비교하고 원래 signed raw 값을
재검증하는 것이다. world/ECU rate·30ms freshness/expiry를 바꾸지 않는다. 그 후에도 실제8-role
full Actual dependency/권한/interval → solver 구간 work/단일 EV → native wall2/4ms 검증이 남는다.
`interval_work_valid=false`, solver work 미관측이며 endpoint Tωdt로 에너지 PASS를 만들지 않는다.
AI·Jetson·새 camera/renderer 안정성·전체 M6/sanitizer 시험은 NOT RUN이다.

기존 [zero-only 회귀](regression1k/result.json)는156개 검사(반복 포함)/13receipt를 통과했고,
[독립 감사](audit-regression1k.json)는 손상8종을 거부했다. [기본 flag-off](default-off.json)는 disabled이며
[원래 client lifecycle](default-smoke/result.json) 정상/예외2/2·102tick과
[독립 감사](audit-default-smoke.json)를 확인했다.
소유 서버4개는 자기 actor/설정 정리 후 SIGINT로 종료했고 각각 tool exit130이다.
[설치/binary 무결성](artifacts.json)과 [검증 범위](validation.json)에 기존 전체 frozen 항목997개(M7만772개) 불변도 기록한다. 원래 Distance Field crash와
content/Vulkan 경고는 OPEN이다. M6 코드·계약·수치·판정은 변경하지 않았다.
