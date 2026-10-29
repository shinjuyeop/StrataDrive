# M1 BMS / Power / Drive constraint wire 초안

Date: 2026-10-14. Status: **wire·timing 초안 / Host codec·receiver·DBC/local vCAN 검사 / 학습자 review PENDING**.
[ADR-0016](../archive/design-decisions.md#adr-0016), [EV-01](ev-power-bms.md),
[ZON-01](../architecture/README.md)을 따른다. [ADR-0017](../archive/design-decisions.md#adr-0017)의
C++ codec/항목별 receiver와 SocketCAN 변환을 Host에서 구현·단위 시험했다.
EV 독립 TX/RX와 source-preserving relay도 local vCAN에서 시험했다.
BMS/power model, vehicle management와 두 Zone runtime은 **PLANNED / NOT RUN**이다.
이 파일의 수치와 상태 이름은 프로젝트 선택이며 OEM/자동차 공통 규격이 아니다.

## 메시지를 나누는 이유

배터리 관측, 제어 한계, 전원 실제 상태와 요청/허가를 분리한다. 느린 SOC 표시의 수신
중단과 주행에 필요한 critical 한계 상실을 같은 timeout으로 처리하지 않는다.
전원 요청이나 Central vehicle management의 주행 허가는 actual 컨택터/HV 상태를 대신하지 않는다.

| Frame / Interface | CAN ID / P05 Data ID | Producer → Consumer | Bytes / DLC | 논리 주기 |
| --- | --- | --- | --- | --- |
| BmsPowerRequest / IF-CAN-BMS | 0x183 / 0x1301 | Central 결정 → Rear → BMS | 48 / 14 | 20 ms / 50 Hz |
| BmsPowerStatus / IF-CAN-BMS | 0x283 / 0x1302 | BMS → Rear → Central | 64 / 15 | 10 ms / 100 Hz |
| BmsPowerLimits / IF-CAN-BMS | 0x284 / 0x1303 | BMS → Rear → Central | 48 / 14 | 20 ms / 50 Hz |
| BmsBatteryState / IF-CAN-BMS | 0x285 / 0x1304 | BMS → Rear → Central | 64 / 15 | 100 ms / 10 Hz |
| DriveBatteryLimits / IF-CAN-DRIVE-CONSTRAINT | 0x193 / 0x1203 | BMS 원천 → Central 판단 → Rear → Drive | 48 / 14 | 20 ms / 50 Hz |
| DrivePermission / IF-CAN-DRIVE-CONSTRAINT | 0x194 / 0x1204 | Central 결정 → Rear → Drive | 64 / 15 | 10 ms / 100 Hz |

Standard 11-bit CAN FD, BRS=0/ESI=0이다. SocketCAN length는 48/64이고 DLC code는 14/15다
([Linux 길이 변환 표](https://github.com/torvalds/linux/blob/master/drivers/net/can/dev/length.c),
[SocketCAN 문서](https://docs.kernel.org/networking/can.html#can-fd-flexible-data-rate-driver-support)).
Application frame은 실제 ID/FD flags/length를 검증하며 classic/extended/RTR/error를
정상 입력으로 정규화하지 않는다. 임시 단일 vCAN은 후속 local 시험용이며 물리 arbitration,
전기적 오류, 위 주기/latency의 충족 증거는 아니다.

## EV schema 1 prefix: bytes 0..31

기존 actuator schema 2와 다른 **EV family schema 1**이다. CAN ID와 version으로 분리한다.
Metadata 위치/P05를 재사용하지만 기존 `encode_actuator_payload`의 schema 2 encoding을
그대로 호출하는 계약은 아니다. 48-byte domain payload도 별도로 표현해야 한다.

| Byte | 필드 / 의미 |
| --- | --- |
| 0..1 | frame별 primary uint16 LE: RequestAction / PowerState / ChargePowerLimit / Soc / Permission |
| 2 / 3 | SchemaVersion=1 / primary Validity=0 또는 1; 다른 field의 validity를 대표하지 않음 |
| 4..7 / 8..11 | uint32 원천 Sequence / trusted nonzero Epoch |
| 12..19 | uint64 SourceTimeNs: 해당 논리 sample/결정의 생성 시각 |
| 20..23 | uint32 CausalSequence: 아래 frame별 원천 관계 |
| 24 / 25 | LocalState: INIT/NORMAL/DEGRADED/FAIL_SAFE / Origin: NoAcceptedInput/NormalPath/LocalProtection |
| 26..28 | Reserved=0 |
| 29..30 / 31 | P05 CRC16 LE / uint8 transport Counter |

P05 offset=232 bits, length=384 또는 512 bits, max delta=10이다. CRC bytes 29..30을
제외한 **전체** payload + implicit Data ID low/high를 보호한다. Counter는 frame별 독립,
첫 값 0/modulo 256이며 application Sequence와 다르다. Prefix/extension reserved는 0이다.
Source/dependency time은 float64로 변환하지 않는다. 초기 Sequence 0..9, 이후 +1..+10,
same-Epoch uint32 wrap 금지와 trusted INIT 정책을 receiver에 적용했다.

## Primary와 물리량

| 필드 | 표현 / 유효 raw | Invalid / 의미 |
| --- | --- | --- |
| RequestAction | uint16: 0 KeepOff, 1 Enable, 2 Shutdown | FFFF; 요청≠actual, Shutdown은 즉시 컨택터 open 명령 아님 |
| PowerState | uint16: 0 OFF, 1 CHECKS, 2 PRECHARGE, 3 HV_READY, 4 SHUTDOWN | FFFF; lifecycle≠system severity≠drive permission |
| Soc | uint16 ×0.0001 fraction, raw 0..10000 | FFFF; 10001..65534 금지, valid 0/1은 실제 empty/full 표현 |
| Charge/DischargePowerLimit | uint16 ×10 W, raw 0..65534 | FFFF; valid 0은 허용 없음, unknown과 구분 |
| Voltage / HvBusVoltage | uint16 ×0.1 V, raw 0..65534 | FFFF; 0은 알려진 0 V |
| Current | int16 ×0.1 A, raw -32767..32767 | -32768; 방전 양수/충전 음수 |
| Temperature | int16 ×0.1 °C, raw -32767..32767 | -32768; physical envelope/derating은 TBD-13 |
| Permission | uint16: 0 Inhibit, 1 AllowNormal | FFFF; invalid도 주행 금지 |

Power limit의 기준은 **pack terminal DC power**다. Wheel torque N·m와 직접 비교하지 않는다.
Motor/inverter 효율, auxiliary load의 몫과 zero-speed 변환은 TBD-13이다. 위 wire 범위를
차량의 허용 power/current/temperature로 사용하거나 초과 값을 clamp하지 않는다.
물리 codec은 finite/range 확인 뒤 half-away-from-zero rounding을 적용한다.

## Extension 배치

### BmsPowerRequest: bytes 32..47

32..39 `ExpiresAtNs`, 40..47 `ParentSourceTimeNs`다. Source/Sequence는 **Central vehicle management 결정**의
시각/identity, CausalSequence는 upstream Central lifecycle request다. Rear는 이 정보를 보존한다.
Normal Enable은 원래 parent의 유효 기간 안에서만 생성/사용한다. `source < expiry <=
source+80 ms`를 만족하되 parent deadline보다 늦게 만들지 않는다. Central 재계산/새 CAN
counter가 parent를 연장하지 못한다. Enable은 INIT에서 power checks를 시작할 수 있지만
normal torque 허가는 아니다. NoAcceptedInput은 KeepOff만, LocalProtection은 KeepOff/
Shutdown만 허용한다. Invalid primary는 FFFF, expiry/parent time은 0이다.

### BmsPowerLimits / DriveBatteryLimits: bytes 32..47

| Byte | 내용 |
| --- | --- |
| 32..33 / 34 | DischargePowerLimit / DischargeLimitValid |
| 35 / 36 | ChargeLimitReason / DischargeLimitReason |
| 37..39 / 40..47 | LimitReserved=0 / InputTimeNs |

Reason은 0 Nominal, 1 SocLimited, 2 TemperatureLimited, 3 ElectricalLimited,
4 Disabled, 5 InputsInvalid다. Disabled는 valid 0만 허용한다. Invalid limit는 FFFF/
flag 0/InputsInvalid다. Charge/Discharge validity는 독립이며 하나를 다른 값으로 대체하지 않는다.
둘 다 invalid일 때 InputTimeNs=0, 유효 한계가 있으면 `input <= source`다.

BMS CausalSequence는 **로컬 모델 입력 batch**이며 느린 BmsBatteryState CAN sequence가
아니다. InputTimeNs는 계산에 실제 사용한 모든 dependency의 가장 오래된 원천 시각이다.
관측 frame 10 Hz와 별개로 첫 SIL의 battery/model sampling·한계 산출을 50 Hz로 계획한다.
새 계산 시각으로 old sensor input을 fresh하게 만들지 않는다.

DriveBatteryLimits는 원래 BmsPowerLimits의 의미 field, Sequence/Epoch/Source/Input time과
origin/state/causal identity를 그대로 전달한다. CAN ID/Data ID/CRC와 독립 transport counter만
바뀐다. Central allocation은 이 한계를 사용해 배분하고 Rear는 검증·전달한다. 별도 BMS→Drive 직접
application 경로를 만들지 않는다. 더 느린 실제 sensor를 적용하면 dependency age/rate를
근거와 함께 개정해야 한다.

### BmsBatteryState: bytes 32..63

| Byte | 내용 |
| --- | --- |
| 32..33 / 34..35 / 36..37 | Voltage / Current / Temperature |
| 38 / 39 | ElectricalValid / TemperatureValid |
| 40..47 / 48..55 / 56..63 | SocSourceTimeNs / ElectricalSourceTimeNs / TemperatureSourceTimeNs |

SOC, electrical pair, temperature는 별도 group이다. Voltage/current는 같은 acquisition의
atomic pair로 다룬다. Invalid group은 각 sentinel/flag 0/source time 0이며 다른 group은
독립 관측 가능하다. 각 valid group time은 envelope source 이하이며 재발행 시 보존한다.
이 frame은 **비critical 관측용**이다. Drive는 그 frame의 cached SOC/온도로 직접 한계를
다시 계산하지 않고 BMS가 독립 산출한 fresh critical limit를 받는다.

### BmsPowerStatus: bytes 32..63

| Byte | 내용 |
| --- | --- |
| 32 / 33 / 34 | Positive/Negative/PrechargeContactor: 0 Open, 1 Closed, FF Unknown |
| 35 / 36 | ConditionBits / ConditionValidity: 각각 bit0..4, 나머지 0 |
| 37..39 / 40..41 / 42 / 43 | PowerReserved=0 / HvBusVoltage / HvBusVoltageValid / BusReserved=0 |
| 44..51 / 52..59 / 60..63 | InputTimeNs / AcceptedRequestSourceTimeNs / InputSequence |

Condition bits는 bit0 LV available, bit1 HV interlock closed, bit2 isolation OK,
bit3 charger connected, bit4 power fault다. Validity mask가 0인 bit의 값도 0이다.
Unknown을 false/정상으로 해석하지 않는다. Bus voltage invalid는 FFFF/flag 0이다.
InputTime은 알려진 physical model observations 중 가장 오래된 입력, InputSequence는 그
model batch다. 모든 actual 항목이 unknown이면 input time/sequence=0이다.
CausalSequence와 AcceptedRequestSourceTime은 원래 수용한 Central vehicle management 요청을 가리키며
NoAcceptedInput이면 둘 다 0이다. 초기 non-driving actual은 normal driving 전에 발행한다.

실제 HV가 준비돼도 contactor/condition/bus 값이 unknown/stale이거나 fault/charging 조건이면
정상 주행을 허용하지 않는다. HV_READY/fault를 동시에 관측할 수 있으며 actual을 임의로
정상화하지 않는다. Power fault별 torque 해소/차단 sequence는 TBD-12다.

### DrivePermission: bytes 32..63

32..35 PowerStatusSequence, 36..43 PowerStatusSourceTimeNs, 44..51 InputTimeNs,
52..59 ExpiresAtNs, 60..63 PermissionReserved=0이다. Central vehicle management 결정의 Source/Sequence와
upstream power request CausalSequence를 보존한다. InputTime은 power/limit/필수 health 등
결정에 사용한 critical 원천의 가장 오래된 시각이다. `input <= power source <= source <
expiry`와 parent-bounded deadline을 적용한다. Unknown이면 Inhibit/invalid로 처리한다.
AllowNormal은 NormalPath + NORMAL 또는 검증된 DEGRADED envelope에서만 허용한다.
Drive는 이 frame 하나만으로 torque를 적용하지 않으며 fresh torque/양쪽 한계/실제 power/
session·local health를 함께 검증한다. 실제 Drive HV bus 입력은 **IF-MODEL-DRIVE-POWER**의
로컬 물리 sensor 경계다. Central permission이나 참조한 PowerStatus identity를 local bus 측정으로
대체하지 않는다. BMS→Drive application 직접 우회도 만들지 않는다. 센서 schema/physical
threshold는 TBD-12/13/14이며 wire 검사 범위 밖이다. Invalid permission의 extension은 모두 0이다.

## First SIL timing / 수신 정책 초안

| 항목 | 시작값 / 의미 |
| --- | --- |
| Critical frame | PowerRequest / PowerStatus / PowerLimits / DriveBatteryLimits / DrivePermission |
| Critical source age | <=50 ms; frame 생성/결정 시각을 보존 |
| Critical dependency age | <=70 ms; oldest model/input/permission dependency, 별도 검사 |
| Critical RX/startup threshold | 80 ms, monitor 10 ms + dispatch/jitter margin 10 ms; 검출 상한 <=100 ms |
| Request/permission lifetime | <=80 ms이며 parent deadline 안; 만료된 허가는 사용 금지 |
| Battery 관측 source/group age | <=150 ms; 이를 넘으면 해당 group unknown |
| Battery 관측 RX unavailable | 300 ms; 비critical 관측 상실이며 정상 critical stream을 대신하지 않음 |

50/70 ms는 20 ms model/limit cadence와 담당 Zone/Central 경유 budget을 구분하기 위한 **후속 측정
대상 시작값**이다. Age와 local RX timeout을 함께 검사하며 threshold만으로 current sample을
보장하지 않는다. Invalid/stale/duplicate는 해당 valid age를 갱신하지 않는다. Partial limit/
power 상태는 진단에 보존하되 필요한 input unavailable은 즉시 normal-use gate를 닫는다.
Source별 monitor를 Zone heartbeat 또는 다른 유효 flag로 reset하지 않는다.

Drive auxiliary receiver는 source age와 oldest capability input age의 config를 분리·시험했다.
기본값은 양쪽 모두 30 ms이며 EV 연결에서 `max_capability_input_age_ns=70 ms`를 명시할 수 있다.
Wheel/capability source와 torque actual의 30 ms 정책은 유지한다. 이는 전체 Drive/BMS 통합이 아니다.
20 Hz vehicle-state speed 입력과 local wheel 입력의
관계도 TBD-04/14 및 M3/M6에서 별도 검토한다. BMS model sampling 50 Hz를 느린 CAN
관측 발행으로 대체하지 않는다.

Local 시험은 trusted Epoch의 같은 Target CLOCK_MONOTONIC domain을 사용한다. Cross-node
sync/uncertainty, 각 hop의 budget과 coordinator의 parent/model identity 전달은 TBD-04/05/14/15다.
Clock rollback/critical timeout은 latched, recovery는 explicit trusted INIT다. Startup/rejoin
이 wire 초안 이후 Host Central–Zone 세션/vehicle·Drive gate와 M6 actual response를 연결했다.
현재 수용은 [현재 상태](../project-status.md)를 따르며 다른 kernel/Target timing은 후속이다.
[Local Epoch/queue](../learning/communication-guide.md)는 영속 발급·trusted fixture 연결과 실제 overflow를 검사했다.

`BmsReceiver::start_session`에는 외부 trusted Epoch/monitor-enable 시각을 제공한다.
NormalPath power request(초기 INIT Enable 포함)와 AllowNormal permission은 별도로 검증한
Central 요청의 `BmsParentContext{epoch, sequence, source_time_ns, expires_at_ns}`가 필요하다.
수신 CAN 값만으로 context를 만들지 않는다. Parent와 wire의 Epoch/causal/source/deadline을
대조하며 같은 parent sequence의 원천 시각 변경·만료 연장과 parent rollback을 거부한다.
Explicit KeepOff/LocalProtection Shutdown/주행 Inhibit는 non-driving 경로로 구분한다.

Envelope의 Accepted와 항목의 Usable은 다르다. SOC/electrical pair/temperature,
charge/discharge limit, power lifecycle/physical-input group을 각각 검사한다.
Unknown/invalid/stale 항목은 usable view에서 제거하며 이전 정상 값으로 대체하지 않는다.
다른 정상 항목이나 새 envelope가 끊긴 항목의 last-usable RX를 갱신하지 못한다.
관측 group의 cached acquisition과 power physical-input의 cached model batch는 재발행으로
healthy RX가 갱신되지 않는다. Critical group timeout은 80 ms에서 latched다.
관측은 group별 unavailable을 표시하고 envelope 자체의 300 ms timeout은 새 trusted Epoch로 재시작한다.
`last_accepted()`는 raw 진단 기록이며 제어 소비자는 시각을 넣어 `current_sample(now_ns)`를 조회한다.
`bms_power_is_ready`는 physical readiness 판단 보조이고 normal torque 허가는 아니다.

## 검사와 다음 구현

기존 [DBC 검사기](../../tools/check_actuator_dbc.py)에 EV를 추가했다. Cantools 40.7.1의
strict layout/ID/DataID/enum/unit 검사, 6개 fixed golden, uint64 precision, 336개 byte 변조,
valid-zero/unknown·부분 sensor와 51개 canonical rejection vector를 검사한다.
C++ demo 교차 검증도 EV 6개를 포함한다. EV nominal/zero/invalid/partial payload 22개와
actuator 14개를 비교한다. Normal·ASan/UBSan 각각 unit 129개 중 BMS domain 28개가
전체 물리 raw 왕복, 6개 golden, payload 전체 single-bit 변조, envelope/canonical,
원천 전달/독립 counter, partial validity/timeout, parent·expiry·모델 identity를 검사한다.
SocketCAN 48/64-byte 변환의 unit과 EV vCAN 36개 case도 검사했다. 독립 TX/RX/relay에서
partial timeout·source/dependency·parent expiry·explicit rejoin을 확인했다.
이는 물리 BMS/power 모델·차량 검증이 아니다.
TC-EV 전체 결과는 NOT RUN이다. 명령/예상 출력은 [실행 안내](../learning/communication-guide.md)에 있다.

```sh
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py --demo build/m1-angle/actuator_demo
ctest --test-dir build/m1-angle --output-on-failure
```

기존 CAN fixture에 EV 독립 TX/RX와 trusted session/parent fixture를 연결했다.
Critical 80..100 ms/관측 300..320 ms timeout과 RX timeout 이전의 expiry gate를 검사한다.
다음은 M1 wire/학습자 review와 함께 M2의 실제 battery/power 모델과 BMS 한계
산출, Drive torque·limits·permission·로컬 HV 통합 gate다.
TBD-12/13/14 전체를 CLOSED로 바꾸지 않으며 학습자의 규격 review는 별도로 남긴다.

설계 참고: [Bosch BMS 역할](https://www.bosch-mobility.com/en/solutions/powertrain/fuel-cell-electric/battery-management-system/),
[Orion charge/discharge limits](https://www.orionbms.com/manuals/utility_o2/profile_limits_basic_settings.html).
측정/컨택터 제어와 충전·방전 가용량의 역할을 참고했으며 wire/rate/power 단위 선택의 출처는 아니다.
