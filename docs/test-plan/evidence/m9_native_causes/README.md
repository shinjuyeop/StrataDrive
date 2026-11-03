# M9 Gateway·BMS·Power native 원인과 qualified 복구

2026-11-03. **Gateway 논리 차량 SIL / BMS·Power component PASS; 전체 M9 OPEN**.
[계약](../../../interfaces/diagnostics.md#gatewaybmspower-native-원인-수집),
[recipe](../../diagnostics-protocol.md#gatewaybmspower-native-fixture),
[ADR-0082](../../../archive/design-decisions.md#adr-0082), C-M9-NAT-01–06을 따른다.

## 구현과 범위

실제 CommandGateway/RearPowerGateway/BmsController/PowerController가 bounded native snapshot을
만들고 같은 owner의 publisher가 유한 queue에 발행한다. Producer30 Front/31 Rear/32 BMS/
33 Power·monitor6–9이며 global Session은 Central7만 발행한다. 기존 제어 기준/보호와
권한은 원래 controller에 있다. 진단 파일 I/O는 owner 밖 writer 구간에서만 수행한다.

Gateway의 최초 admission/send reason·부분 전송 수·원래 parent/child expiry/dependency,
Rear의 네 stream/실패 mask, BMS의 실제 scalar/trip·release band/dwell, Power의 실제 phase/
부분 sensor/BMS gate와 threshold/timeout을 typed snapshot에 보존한다. Journal schema1에는
reason/detail/state·source identity/시각과 sample identity를 기록한다. 전체 scalar/config의
영속 직렬화까지 구현한 것으로 해석하지 않는다. BMS·Power는 외부 보호 전달과 이후 실제
자체 fault를 별도 slot에 보존하며 전달 자체를 root DTC로 만들지 않는다.

SD-2101 Gateway delivery / SD-3101 BMS local / SD-3201 Power local은 registry2다.
명시적 새 store bootstrap만 지원하며 기존 default registry1을 자동 변경하지 않는다.
구 registry에 새 code를 append하면 durable=false/incomplete이고 이전 manifest/watermark는
유지한다. Registry2 재시작은 새 code 이력/count를 보존하고 현재 condition은 Unknown이다.
지원하지 않는 registry는 store를 만들지 않는다. 기존 registry1 journal/clear 회귀도 통과했다.

| 실행한 검증 | 결과 |
| --- | --- |
|정상92s 차량 SIL|4350 controls·정상 Stop/HV-off·9200 physical samples·root DTC0 |
|Central만10s부터200ms 정지|두 live Gateway가 실제 context 만료를 검출. SD-2001 두 건·원본 ACK·차량 토크/제동 응답을 기록 |
|입력/owner 재개|13s에도 epoch1 gate/latch·Failed 유지; traffic만으로 복구 없음 |
|20s 실패 link 교체·실제8-role INIT2|같은 physical/battery model7·position/sequence 연속 |
|새 실제 dispatch|Front2 frames/Rear1 frame의 완전 전송·현재 health/gate/age/expiry로 Input proof; 두 기존 occurrence Passed·count1/generation1·미삭제 |
|Gateway component|실제 Front 두 번째 write 실패 SD-2101·부분 전송 수1; 새 INIT만/닫힌 gate/stale 등10개 음성 증거 거부 |
|Rear component|네 stream별 실제 누락 mask/최초 source/expiry, 실제 armed dispatch evidence·외부 continuity 전달 보존 |
|BMS component|실제 native controller에4.3V 입력·trip4.25V/40ms dwell:120→160ms 검출; 복원/recovery_ready만으로 latch 유지·새 INIT/100ms release dwell 뒤 Passed |
|BMS propagation component|외부 Protection110ms는 DTC0, 이후 실제 자체 trip160ms는 별도 원인; 시각을 덮지 않음 |
|Power component|실제 RC plant Ready 뒤 current scalar 누락 SD-3201; 부분 입력을0으로 채우지 않음. 복원/Off/INIT만으로 Passed 아님; plant reset 없이 실제 HV Ready 재도달 |

표의 시간은 elapsed이며 차량 simulation absolute에는1s를 더한다. 차량 최초 command expiry는
11.011000001s·검출11.0112s(199999ns 뒤), 첫 torque≤1Nm/brake≥1MPa 원본 physical 표본은
11.221s(검출 후209.8ms)다. 이를 차량 정지 완료로 세지 않는다. INIT2 enable은21.0202s,
실제 Front/Rear 완전 dispatch proof는21.7846/21.7848s다. 차량 고장 case는13 events·
DTC2건·2400 physical samples다. BMS/Power 자체 고장을 이 차량 recipe에 주입한 것은 아니다.

복구 대기는64 fixed slots이며 새 key가 이전 key를 몰래 지우지 않는다. Passed는 metadata
Observation proof를 참조하며 clear/제어 권한/plant reset을 만들지 않는다. BMS/Power의 실제
성공 snapshot에도 각각8개 음성 변형을 적용해 gate/health·epoch/enable·누락/old dependency·
stale body·미qualified를 거부했다. 원래 유효 증거만 Passed다. Source scalar/config 전체는
component assertions로 검증하며 독립 journal 감사가 이를 재계산한 것으로 주장하지 않는다.

## 검사와 원본

| 검사 | 결과 |
| --- | --- |
|최종 일반 unit + integration.logical|1129/1129·failure/skip0 (`normal-verified.xml`) |
|최종 영향 ASan/UBSan|206/206·failure/skip0 (`asan-complete.xml`) |
|Normal/ASan 최종 export|각3/3·주요 산출물16개 byte-identical |
|기존 wall owner 회귀|2/2; 새 diagnostics wall collector 수용 아님 |
|독립 canonical journal/native/ACK/physical 감사|Normal/ASan 정상·고장 PASS·고장 손상8개씩 거부 |
|정적 분석|변경 production11 TU clang-tidy exit0·cppcheck warning/performance/portability exit0 |
|정적 style 추가 관측|8 bounded-loop STL 제안·member initializer에서 쓰이는 helper의 unused 오탐2. `cppcheck.log.gz`/`static-result.json`에 보존; style0으로 보고하지 않음 |
|기타|source fingerprint2/2·Release BUILD_TESTING=OFF 빌드 PASS·이전 M9 evidence 네 묶음 SHA 유지 |

Independent 감사는 manifest registry2·CRC/commit·producer sequence·원래 native context/
expiry·검출/ACK·new epoch actual dispatch proof/occurrence·Passed 이력과 물리 연속성/응답을
대조한다. Registry·expiry·propagation root 오표기·proof reference·early pass·partial send·
history erase·physical reset의8개 손상을 거부했다. Hook on/off의 원래 fault/보호 시각과
전 physical 표본의 권한/sequence·토크/압력·거리/에너지/SOC가 같다. Wall 성능 주장은 없다.
기존 SPSC TSan 근거는 이전 component 묶음이며 이번에 새 TSan cohort를 실행하지 않았다.

## 실패와 교정

최초 compile은 GTest macro 중괄호·BmsTxState의 const 멤버 재대입, 다음 compile은 E2E
초기화 함수의 reference 인자 오류로 실패했다. `build-tests*.log.gz`에 보존한다.
첫 runtime은 Recorder의 ledger Accepted/durable=false 분리 계약을 시험이 잘못 기대했고,
Power fixture는 request origin을 누락해 encode가 실패했다. 기존 codec 계약에 맞게 고쳤다.
원래 protection/age/dwell/물리 budget을 바꾸지 않았다.

Power helper의 fatal assertion 뒤 외부 while이 계속 돌던 최초 실행은 SIGTERM으로 종료했고,
원인 확인을 위해 실행한 두 번째 probe도 종료했다. `initial.log.gz`/`initial.xml.gz`와
`power-probe.log.gz`에 원본 반복 출력을 보존한다. Helper 호출에 fatal failure 전파를 추가했다.
최초20개 중2개 실패를 최종 통과 분모에 더하지 않는다. 최종 source/binary hash를 보존하지만
실패 iteration별 전체 source/binary snapshot은 별도로 저장하지 않았다.

마지막 source review에서 PowerRequest의 원래 parent source와 Rear normal grant의 원래
input dependency를 diagnostic metadata에도 복사하도록 교정했다. 최종 일반/ASan과
export/독립 감사는 이 교정 이후 다시 실행했다. 초기/중간 export를 최종 것으로 대체하지 않았다.

## 재현과 남은 범위

`manifest.json`의 base commit에 `sources/` overlay를 적용한다. Source/binary/tool hash·빌드
설정과 명령은 manifest/commands를 따른다. `normal/`·`asan/`의 CSV는 gzip이며 새 위치에
풀어서 아래 감사 명령을 실행한다. Store binary는 원형이다. `sha256sum -c SHA256SUMS`로
이 묶음을 검사한다. 이미 있는 export 경로를 덮어쓰지 않는다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 3
ctest --test-dir build/m1-angle -L '^(unit|integration.logical)$' --parallel 3 --output-on-failure
STRATADRIVE_M9_NATIVE_EVIDENCE=/tmp/new-native-output build/m1-angle/native_diagnostics_sil_test
python3 tests/integration/diagnostics/audit_native_diagnostics.py /tmp/new-native-output/central-pause --mutations
python3 tests/integration/diagnostics/audit_native_diagnostics.py /tmp/new-native-output/normal
```

현재 collector는 global release 이후 source 수집이다. Release 전 startup·remote wire/spool·
production background writer·전체 scalar/config 영속 schema·owner clear service·source restart
adoption·Clock recovery·BMS/Power 자체 고장의 전체 차량 matrix·CARLA30km/h·wall/Target·
학습자 수용과 TBD-08 최종 판단은 OPEN이다.
