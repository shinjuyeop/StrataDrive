# ADR-0017: EV/BMS codec와 항목별 수신 유효성

Date: 2026-10-14. Status: **M1 Host 구현·unit/local vCAN 검사 / wire 채택·학습자 review PENDING**.
Owner: 학습자(project owner). [ADR-0016](ADR-0016-bms-power-wire.md)의 wire 초안을 구현한다.

## 문제와 결정

BMS 메시지는 여러 센서/한계의 validity를 가진다. Frame이 정상 수신됐다는 이유로 모든
항목의 age를 reset하면 끊긴 충전 한계나 오래된 power 센서가 계속 정상으로 보인다.
전원 요청은 INIT에서도 필요하지만 주행 허가는 원래 요청의 만료를 연장하면 안 된다.

- `interfaces/bms/`에 물리값 codec, 6개 frame의 typed content와 receiver를 둔다.
  기존 actuator schema 2는 유지하며 EV schema 1/48·64 bytes를 별도로 직렬화한다.
  공통 metadata/P05/수신 cursor와 Linux SocketCAN endpoint를 재사용한다.
- Optional field는 known zero와 unknown을 구분한다. Sentinel/validity/reserved/time 관계를
  canonical하게 검사하며 물리 허용 범위는 호출자가 명시한다. Wire 범위는 차량 calibration이 아니다.
- Envelope Sequence/Epoch/Source 검증과 항목별 quality/last-usable RX를 분리한다.
  Partial 메시지는 진단에 수용할 수 있지만 unusable 항목은 제어 view에서 제거한다.
  Observation acquisition/model batch의 진행도 검증한다. Critical timeout/clock rollback은
  latched이며 외부 trusted 새 Epoch/INIT로만 재시작한다.
- NormalPath power request와 AllowNormal permission은 수신 CAN과 독립적으로 검증한
  `BmsParentContext`가 필요하다. Parent identity/age/deadline을 대조하고 동일 원천의
  만료 연장을 금지한다. INIT Enable, 실제 HV readiness, normal-driving permission을 구분한다.
- Drive auxiliary의 source age와 capability input age 설정을 분리한다. 기본값 30 ms를
  유지하고 EV input age 70 ms는 명시적 opt-in으로 시험한다. Torque/source budget은 유지한다.
- 기존 `actuator_demo`/DBC checker에 EV를 확장한다. BMS 단위 시험은 한 domain 파일에
  모으며 SocketCAN adapter 시험도 기존 파일에 추가한다.

## 검증 범위와 남은 일

Normal·ASan/UBSan 각각 unit 129개, 전체 12개 DBC와 C++ payload 36개를 검사했다.
Unit의 항목별 timeout/expiry는 수동 clock 시험이며 SocketCAN 변환은 native frame 단위 시험이다.
후속 local vCAN에서는 독립 process의 wall-time timeout/expiry도 검사했다.
실행 명령과 범위는 [BMS 학습 기록](../learning/m1_bms_codec.md)에 둔다.
TC-EV-001/002/004의 부분 증거에 연결하며 전체 system Result는 NOT RUN이다.

후속 작업에서 기존 vCAN fixture의 EV TX/RX/session·parent·relay 36개 case를 시험했다.
Trusted allowlist를 harness stdin으로 제공하며 CAN causal key는 조회에만 쓴다.
Context를 전달하는 실제 coordinator/DDS protocol과 각 hop budget은 TBD-14/15다.
P05와 identity 대조는 인증 기능이 아니다.
BMS limit 산출, power response, local protection과 Drive의 torque/limits/permission/실제 HV
통합 gate는 M2 이후 구현한다. 셀 전압·온도 극값은 로컬 모델 계약에 포함하며 이번 wire를 늘리지 않는다.
TBD-12/13/14와 학습자의 review를 완료 처리하지 않는다.
