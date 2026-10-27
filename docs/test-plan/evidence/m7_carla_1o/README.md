# M7-1o — 출발 음수 회전 원인 분리와 직접 solver 관측

2026-10-27 KST. M6 코드·계약·수용 수치, V1 가상 EV의 물리 계수,
10ms world/state·50ms 영상·30ms Drive freshness를 유지한다.
전용 Town03_Opt/spawn0/mkz_2020의 합성 Actual 진단이며 실제8-role 정상 주행은 연결하지 않는다.

## 원인 분리

- **정착:** 기존100tick hold 뒤에는 wheel0이어도 차체 수직속도 약0.0176m/s가 남았다.
  20분할에서 실제 sleep/차체 선속도·각속도·4wheel exact0까지 기다린134tick 조건도
  출발3frame 음수를 재현했다. 단순 정착 부족으로 설명되지 않는다. 최대1000tick의 진단
  대기이며 sleep을 정상 주행의 새 필수 조건으로 정하지 않았다. 대기 관측도 모두 보존한다.
- **입력:** 기존 response 모델을 그대로 컴파일한 [fixture](../../../../tests/integration/carla/m7_1o_actuator_fixture.cpp)는
  지연50ms·Drive1000Nm/s·Steering1rad/s·Brake 상승5MPa/s/하강10MPa/s와 기존 초기값을 쓴다.
  1ms 물리 advance 뒤10ms 시각에 실제 capture하고 그 후 새 target을 반영한다.
  codec 양자화 전 측정·원래 source·target을 저장하며 Adapter에 ramp를 추가하지 않는다.
  보호 pressure 해제는 기존 begin으로 물리 압력을 보존한다. **전체 actuator/electrical owner나
  vECU authority를 실행한 것은 아니다.** energy 계산도 없다.20분할에서는 이 입력도
  brake0 시점에 rear 음수3frame을 재현했다(직진140Nm/좌우150Nm).
- **적분:** 동일 원래 CAN/P05·source/expiry·구간을 유지한40분할은 rear 음수35frame,
  80분할은14frame으로 실패했다. 작은 분할 증가가 단조롭게 개선된다는 가정은 기각했다.

## 확인한 계산 경로와 수정

읽기 전용 `GenerateTireForces` 관측은 원래 Super 계산을 그대로 실행하고 입력 ω·slip·load,
출력 tire torque/force만 기록한다.20분할 직진 첫 tick의 후륜150Nm 구동에서
ω 약+0.05950rad/s → tire torque 약−1533.22Nm → ω 약−0.48924rad/s로 뒤집힌다.
이후 같은10ms 구간 안에서 양/음 진동한다. 타이어 반력을 이전 ω로 계산하는 명시적 적분의
저속 불안정 경로이며, [공개 PhysX 구현](https://github.com/NVIDIAGameWorks/PhysX-3.4/blob/master/PhysX_3.4/Source/PhysXVehicle/src/PxVehicleUpdate.cpp)의
`computeTireSlips`/`integrateNoDriveWheelSpeeds`와 정확한 설치 fork의 [source hash](source-contract.json)를 대조했다.
원래 solver/타이어 law/마찰·관성/구동 gain은 바꾸지 않았다.

[국소 선형 추정](stability-estimate.json)은 관측 inertia1.26025kg·m²/radius0.355m,
작은 slip에서의 force 기울기 약29400N, denominator offset0.1m/s를 사용한다.
차체를 고정한 근사에서 안정 dt<약68µs, 비진동 dt≤약34µs이며 전역 안정성 증명은 아니다.
이 근거로160(62.5µs)·320(31.25µs)·640(15.625µs)을 비교했다.
world tick/센서 주기를 바꾸거나 새로운 sample을 만들어내는 변경이 아니다.

서버의 명시 옵션 `-StrataM7V1Substeps{20,40,80,160,320,640}`만 해당 low/high count를 설정한다.
V1 flag를 요구하고 여러 count의 동시 지정은 거부한다. 기본 asset3/1은 유지한다.
**320분할은 후속 격리 통합의 수치 후보**이며 전체 ODD/정상 주행 또는 wall budget 수용이 아니다.
160/320/640의 고정 stress는 모두10ms 공개 관측 음수0/1621이었다.
320↔640의 최대 차이는 wheel 약0.0038002rad/s, forward 약0.0013287m/s, 위치 약0.002012m다.
이는 저장된 결과의 민감도 비교이며 새 허용 오차나 엄밀한 수렴 차수 판정으로 채택하지 않는다.

## wheel 원천 정정

초기 recurrence audit는 마지막 무구동 앞바퀴에서 실패했다([원본](audit-attempt01.json)).
이 fork의 `getWheelRotationSpeed()`는 **`mCorrectedWheelSpeeds`**를 반환하며 무구동·무제동
저속 접지에서 rolling speed와 내부 ω를 혼합할 수 있다. 이전 문서의 raw는 프로젝트가
수정하지 않은 공개 API 값이라는 의미만 입증됐으며, 항상 순수 solver 상태라는 해석은 정정한다.
동력이 걸린 후륜의 원래 출발 음수 FAIL은 이 혼합과 무관하며 그대로 유효하다.

기존 `omega_rad_s`와 과거 evidence는 보존한다. 새 `solver_omega_rad_s`는 pinned UE/PhysX
serialization accessor `getWheel4DynData()`가 반환하는 `mWheelSpeeds`를 **직접 읽는다**.
source ID는 `PhysX3.4.mWheelSpeeds.direct.v1`이다. private layout cast·v/r 재구성·engine 변경은 없다.
install 시 정확한 UE commit과 두 header hash를 검사한다. header를 저장소에 복사하지 않고
해당 UE 설치의 include만 사용한다. 이 결합은 다른 엔진/플랫폼 호환성을 뜻하지 않는다.
향후 native wheel bridge는 새 직접 source를 명시적으로 사용해야 하며 공개 보정값으로 fallback하지 않는다.

내부 tire callback에는320분할 stress에서 앞바퀴 음수6개(최저 약−3.10e−9rad/s)가 남았다.
후륜 callback 음수는0이다. 이 값을 epsilon으로 제거하거나 전체 solver 음수0이라고 주장하지 않는다.
callback은 조건에 따라 생략되며 저속 비영 effort 구간만 상세 저장한다. 전체 substep work coverage가 아니다.
실제 energy 계산에는 앞바퀴를 포함한 signed 상태와 brake 반력이 필요하다.

## 검증과 남은 gate

최종 직접 solver 읽기 버전에서 다음을 실제 실행했다. 첫 tick을 포함해 모두 집계한다.

| 조건 | receipt | 직접 solver 음수 sample / rear 음수 frame | 판정 |
| --- | ---: | ---: | --- |
| [20분할 stress](substeps20-raw/result.json) |1,621 |6 / 3 | 기존 FAIL 재현 |
| [320분할 stress A](substeps320-rawa/result.json) |1,621 |0 / 0 | 해당 범위 해소 |
| [320분할 새 서버 B](substeps320-rawb/result.json) |1,621 |0 / 0 | 반복 검증 |
| [320분할 response 입력](substeps320-raw-response/result.json) |1,621 |0 / 0 | 해당 범위 해소 |

320 A/B의 body·공개 wheel·직접 solver 관측은 모두 정확히 일치했다. 추가 직접 읽기는
이전320분할 물리 관측도 바꾸지 않았다. 세320 실행에서 출발·음수 motor 감속·마찰 정지·
hold/release·좌우 yaw 부호를 확인했다. 기존 source/expiry/P05·single-use·foreign writer
거부·nonzero pending pause/reset 폐기·actor/설정 복원을 유지한다.

[독립 대조](comparison.json)는 원래 CAN/P05·metadata·단위·모델·프레임·구간·clear와
입력 stream 동일성,320 새 서버 반복, 원래 response 재실행, callback 사이 적분식을 검사한다.
계측 전후20분할의1,621개 물리 관측은 이전1n과 전부 같았다.
총15개 V1 실행/24,528receipt를 보존한다. 이 분모에는 음수 실패 조건도 포함되므로 전체를
주행 PASS로 합산하지 않는다. 최종 직접 source의 각 audit는 손상12종을 거부했고,
callback torque 손상 및 response source 손상도 각각 거부했다.
[최종 zero-only 회귀](regression1k-final/result.json)는156검사/13receipt,
[감사](audit-regression1k-final.json)는 손상8종 거부다. 중간 build04의 동일 회귀도 별도로 보존했다.
[중복 count](flag-ambiguous/result.json), [V1 없는 count](flag-requires-v1/result.json),
[기본 flag-off](flag-disabled/result.json)의 읽기 요청 거부를 새 서버에서 확인했다.
flag-off ego lifecycle은 이번 단계에서 재실행하지 않았다. 소유 서버20개는 모두SIGINT130으로
종료했다. exit0 또는 renderer 전체 안정성 판정이 아니다.
`PASS_RECEIPT_RUN`/`PASS_MAPPING_AUDIT_ONLY`/`PASS_CAUSE_AND_COMPARISON_AUDIT_ONLY`는
해당 한정 범위이며 full Actual/work/native wall PASS가 아니다.

정상 주행의 남은 순서는 직접 solver wheel→native 반환 검증 → 실제8-role full Actual dependency/
권한/interval admission → solver 구간 work와 단일 EV 계산 → wall2/4ms 측정이다.
기존20분할/40/80의 FAIL·원래 crash·미검증 ODD는 유지한다. pause/reset·single writer·single-use
ticket·expiry·음수 unavailable/latch 계약을 완화하지 않았다. AI/Jetson·새 RGB/GT·전체 M6/
sanitizer/wall 시험은 NOT RUN이다.

[빌드](builds.json)의02는 PhysX 벡터에 UE 메서드 `Size()`를 사용한 컴파일 오류로 실패했고,
03에서 `magnitude()`로 수정했다.01/03/04/05는 exit0이며 client 재빌드는 없다.
기존 frozen [1,051항목](prior-integrity.json)은 hash가 같았다.
raw JSONL은 [원본 hash와 크기](compression.json)를 기록한 무손실 gzip으로 보존한다.
관측을 버리거나 source time을 바꾸지 않았다.
[최종 검증 범위](validation.json)와 [무결성 목록](SHA256SUMS)을 따른다.
