# BMS·Power 입력 손실의 차량 SIL 연결

2026-11-03. **BMS electrical/Power current 두 입력 손실 PASS; 전체 M9 OPEN**.
[계약](../../../interfaces/diagnostics.md#bmspower-입력-손실-차량-연결),
[recipe](../../diagnostics-protocol.md#bmspower-자체-입력-손실-차량-sil-fixture),
[ADR-0083](../../../archive/design-decisions.md#adr-0083), C-M9-VEH-01–06을 따른다.

## 실행한 경계

Physical model7은 계속 실행한다. BMS runnable은 electrical 그룹, Power runnable은 current
scalar를 **입력 사본에서만** 누락한다. 공유 sensor channel·다른 ECU 입력·CAN/source/
identity·control period·native threshold/dwell/보호 기준은 유지한다. Window 설정과 실제
affected body를 구분한다. `native-input-unavailable/restored`는 body 시각과 원래 acquisition/
dependency다. Logical Host10ms 전용이며 다른 fault recipe와 혼합하지 않는다.

Run/clock5001·registry2·Central7/Front30/Rear31/BMS32/Power33이다. Elapsed10s 주입,
10.2s 복원,20s 기존 joined link 교체와 실제8-role INIT2,24s 종료다. 실제 body의 최초 누락은
absolute11.001s·복원11.201s이며 각각 configuration 경계 다음1ms다. 원래 local controller는
다음 body에서 검출했고 추가 diagnostic debounce를 넣지 않았다.

| 실제 결과 | BMS electrical 누락 | Power current 누락 |
| --- | --- | --- |
|첫 native 원인|InputsInvalid/Unavailable·SD-3101 한 건|InputsUnavailable·SD-3201 한 건 |
|검출·local 선택|11.001s|11.001s |
|첫 torque≤1Nm/brake≥1MPa physical 표본|11.211s·검출 후210ms|11.211s·검출 후210ms |
|실제 contactors open·bus≤30V 표본|11.591s|11.771s |
|실제 speed≤0.01m/s 표본|12.221s|12.221s |
|복원 뒤·INIT 전|native latch/gate·Failed 유지|native latch/gate·Failed 유지 |
|INIT2 enable|21.0202s|21.0202s |
|정상 재시험 source proof|21.1402s BMS release dwell/Active|21.7602s actual HV Ready |
|DTC 최종 이력|Passed·count1/generation1·미삭제|Passed·count1/generation1·미삭제 |
|journal / physical|15 events /2400 samples|13 events /2400 samples |

표는 absolute simulation이다. 검출은 configuration 주입 후1ms이며 이것을 wall latency로
표현하지 않는다. BMS Passed는 local monitor 복구이고 차량 전체의 normal readiness/arm과
다르다. Power Passed는 실제 새 Ready를 요구한다. INIT 자체는 두 DTC를 Passed로 바꾸지 않는다.
원래 native selection은 journal과 owner log에서 대조한다. 두 Zone ACK는 원본 owner log의
epoch/시간에서 별도로 검증하며 새 causal ACK를 만들어 붙이지 않는다. 실제 torque/brake,
차량 stationary, contactor/HV-off와 metadata proof를 각각 판정한다.

복구 없는 시험에서 입력을 복원해도 같은 epoch의 Failed/latch/gate는 유지했다. 영구 누락
시험도 별도 실행했다. 특히 Power current가 계속 없으면 WaitCurrent/shutdown_blocked이며
차량은 정지해도 contacts3·bus>300V를 유지한다. Current를0으로 채우거나 contactors open/
HV-off/Passed를 꾸미지 않는다. BMS 영구 누락은 다른 valid Power current로 controlled
shutdown이 가능하므로 두 고장의 HV 결과를 같다고 강제하지 않는다.

## 검사와 독립 감사

| 검사 | 결과 |
| --- | --- |
|일반 unit + integration.logical|1137/1137·failure/skip0 |
|영향 ASan/UBSan|59/59·failure/skip0; native/owner/control recovery·M4 관련 경계 |
|Normal/ASan export|각11/11; 새8개·기존3개 시험 |
|기존 wall owner 회귀|2/2; 새 fault/diagnostic wall 수용 아님 |
|변경 production 정적 검사|4 TU clang-tidy/cppcheck warning/performance/portability exit0 |
|기타|source fingerprint2/2·Release BUILD_TESTING=OFF runtime 빌드 PASS·이전 M9 다섯 묶음 SHA 유지 |

두 새 case의 독립 감사는 registry/CRC/commit·정확한 최초 DTC/선택·원본 누락/복원 body·
native sample identity와 누락 scalar·새 session/proof reference·BMS release dwell endpoint/
Power Ready·원래 모델의 연속성/에너지/실제 응답·stationary/HV-off를 대조한다. 각 Normal/
ASan에서10개 손상을 거부한다. Registry·false root·누락 소거·missing→zero·proof 바꿔치기·
INIT-as-pass·이력 삭제·자동 회복·physical reset·가짜 HV-off다. 기존 Gateway/정상 fixture도
양쪽 export에서 재감사했다. 새 Reader의 부가 model/state/unknown 필드는 encoding을 바꾸지
않으며 이전 control/clear/owner 다섯 cohort의 감사도 다시 통과했다.

On/off는 같은 공개 runtime recipe에서 전체 physical 표본의 epoch/gate·model identity/
sequence·토크/압력·bus/contacts·speed/distance·energy/SOC/balance와 native fault/보호 시각이
동일했다. 두 mode의 원본 입력·물리·권한 경로는 동일하다. 정상92s/4350 controls의 root DTC0도
유지한다. 새 process/thread/backend를 추가하지 않았고 이번에 새 TSan cohort를 실행하지 않았다.

`native.csv`는 Fault/Passed 시 원본 source snapshot, `native-samples.csv`는 해당 bounded
sample slots/optional scalars다. `native-bodies.csv`는 실제 BMS/Power body별 대상 raw identity/
누락 여부·native 판정과 raw Power current/bus/contacts를 기록한다. 이 raw source는 실제
누락 사본과 구분하며 native Fault의 missing group/scalar는 sample CSV에서 확인한다.
모든 scalar/config가 journal schema에 영속화됐다는 뜻은 아니다.

## 교정 이력과 재현

최초 차량6개 시험과 추가 영구 손실2개 시험은 통과했다. 최초 Power 독립 감사는 Passed의
state_after를 Fault detail과 같다고 기대해 실패했다. 기존 계약은 Fault의 native detail과
proof의 metadata(writes)를 구분한다. Oracle만 교정했으며 budget/제어/기록을 바꾸지 않았다.
`audit-probe-power.err.gz`와 당시 auditor source, 최초 recipe/source hash·binary hash를
보존한다. Normal/ASan 최종 실행은 이 교정 후의 source에 따른다. 최종 분모에 중간 실행을
더하지 않는다.

Manifest의 base commit에 `sources/` overlay를 적용한다. Final source/binary/tool hash와
정확한 commands를 보존한다. 압축 CSV를 새 위치에 풀면 standalone Python 감사가 된다.
`normal/`·`asan/`은 새 두 case와 기존 Gateway/정상 재실행이다. 기존 evidence를 덮어쓰지 않았다.

```sh
cmake --build build/m1-angle --parallel 3
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --parallel 3 --output-on-failure
STRATADRIVE_M9_NATIVE_EVIDENCE=/tmp/new-native-vehicle build/m1-angle/native_diagnostics_sil_test
python3 -B tests/integration/diagnostics/audit_native_vehicle.py /tmp/new-native-vehicle/bms-input-loss --mutations
python3 -B tests/integration/diagnostics/audit_native_vehicle.py /tmp/new-native-vehicle/power-input-loss --mutations
```

이 디렉터리에서 `sha256sum -c SHA256SUMS`로 무결성을 확인한다. Source snapshot의 metadata
proof와 physical actual을 구분한다. Release 전 startup 수집·remote wire/spool·source restart/
Clock 복구·전체 scalar 영속 schema·다른 BMS trip/Power contactor 등 전체 fault matrix·
CARLA30km/h·wall/Target·학습자 수용과 TBD-08은 OPEN이다.
