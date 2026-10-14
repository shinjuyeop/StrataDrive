# ADR-0016: BMS 상태·Power·Drive constraint의 M1 wire 초안

현재 배치: [ADR-0021](ADR-0021-central-coordination-and-parallel-zones.md). Producer/vehicle management·배분과 상위 routing 배치는 2026-10-14 ADR-0021로 개정한다. CAN wire/scaling/typed parent/expiry 초안과 당시 시험 결과는 유지한다.

Date: 2026-10-14. Status: **범위 EV-01 / wire·timing PROPOSED / Host DBC·P05 부분 검사 / 학습자 review PENDING**.
Owner: 학습자(project owner). 기존 EV-01/ZON-01과 BMS 규격부터 재개하는 작업 순서를 따른다.
DBC parser/vector 검사와 실제 C++ EV receiver/runtime 채택을 구분한다.

## 문제

배터리 관측·제어 한계·power request/actual/permission을 한 validity/주기로 표현하면
cached SOC와 critical 한계의 freshness가 섞인다. BMS 정보의 Front/Rear 중계가
원천 시각을 연장할 수 있으며 기존 Drive의 30 ms 보조 입력 정책과 새 budget도 다르다.

## 제안

- BmsPowerRequest, BmsPowerStatus, BmsPowerLimits, BmsBatteryState,
  DriveBatteryLimits, DrivePermission의 6개 frame을 하나의 BMS DBC에 정의한다.
- Critical request/limits는 50 Hz, power status/permission은 100 Hz, 관측 state는 10 Hz로
  구분한다. BMS local battery/model sampling·한계 계산은 첫 SIL에서 50 Hz를 계획한다.
- EV family schema 1을 기존 actuator schema 2와 분리한다. 48/64-byte CAN FD payload와
  독립 P05 Data ID를 쓰고 CRC 29..30/counter 31 및 전체 extension 보호를 유지한다.
- SOC fraction, V/A/°C, pack DC power W를 사용한다. 유효 0과 unknown, sensor group별
  validity/source time, power actual과 주행 permission을 구분한다.
- Front 차량 전체 조정과 Rear routing을 유지한다. DriveBatteryLimits는 BMS 원천
  Sequence/Epoch/Source/Input/causal identity를 보존하며 counter/DataID만 transport별로 바뀐다.
- Request/permission에 parent-bounded expiry를 두고 INIT Enable을 normal-driving grant와
  구분한다. 로컬 보호 command의 origin도 정상 request와 다르게 처리한다.
- Critical source age 50 ms, oldest input age 70 ms, RX threshold 80 ms + monitor/margin
  20 ms를 시작값으로 정의한다. 관측 source/group age 150 ms와 RX unavailable 300 ms는
  비critical 경로다. 양쪽 한계/power의 필요한 source validity는 각각 감시한다.

수치/배치는 프로젝트 초안이며 OEM 표준·실측·물리 안전 budget이 아니다.
상세 표/byte/판정식은 [BMS wire ICD](../icd/bms_frame_draft.md)를 따른다.

## 대안과 영향

단일 큰 status는 publication을 줄일 수 있지만 slow observation과 critical gate가 묶인다.
모든 정보를 100 Hz로 보내는 대신 역할/주기를 나누고 CAN 관측과 local sensor cadence도 분리한다.
Drive가 BMS 센서 raw 값으로 한계를 중복 계산하거나 상위 timestamp만 보고 fresh로 수용하지 않는다.

기존 actuator wire/receiver 설정은 변경하지 않는다. EV 연결 전에 Drive auxiliary의 source와
dependency age 설정을 분리하고 20 Hz vehicle state와 speed source 관계를 검증해야 한다.
Power Enable의 INIT/multi-field canonical/deadline 정책은 기존 actuator command 검사를 그대로
재사용할 수 없다. Shared Target clock 시험도 Host–Target 동기화 증거로 확대하지 않는다.

TBD-14의 frame inventory/scaling/flags/DataID와 local timing 시작값을 이 초안으로 구체화한다.
Wire 수용/교차 codec/receiver/vCAN, trusted Epoch/bootstrap/parent correlation, 각 hop clock/budget,
queue/overflow와 학습자 review는 남는다. TBD-12의 sequence/reaction과 TBD-13 모델은 별도다.
기존 요구사항 revision을 변경하지 않고 TC-EV-001/002/004의 M1 부분 증거에 연결한다.

## 검증과 다음 단계

기존 DBC 도구를 12개 frame 검사로 확장하며 EV fixed goldens, canonical/uint64/CRC와
원천 보존을 검사한다. 기존 P05 unit test에 48-byte golden/bit corruption을 추가한다.
전체 TC-EV는 NOT RUN이다. 다음은 BMS 물리/프레임 codec → stateful receiver
→ Drive dependency policy 개정 → 기존 vCAN fixture 확장이다. 모델/permission runtime은 이후다.

후속 구현(2026-10-14): [ADR-0017](ADR-0017-bms-codec-receiver.md)에서 C++ codec/항목별 receiver,
Drive age config 분리와 SocketCAN 변환 unit, 후속 local vCAN 36개 case를 시험했다.
실제 모델/Zone runtime과 wire 최종 수용은 남는다.
