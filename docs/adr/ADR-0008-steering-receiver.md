# ADR-0008: Steering의 로컬 application 수신부

Status: **2026-10-12 Host 구현·제어 가능한 시계 시험 완료 / 학습자 review PENDING**.
관련: [frame 초안](../icd/steering_frame_draft.md), [P05 결정](ADR-0007-autosar-e2e-profile5.md),
SYS-COM-001/002/003/004, SYS-SAFE-003/004. Reference v0.1의 requirement를 변경하지 않는다.

## 문제

Frame 복원과 P05 CRC/Counter 검사는 실행했지만 오래된 sample, 다른 Epoch, 새 Counter로
재포장한 cached sample을 application 입력으로 수용할지 결정하는 코드는 없었다.
P05의 raw counter 재동기화를 마지막 유효 수신으로 취급하면 invalid traffic이 timeout을
연장할 수 있다. Timeout 시 도착한 늦은 frame으로 자동 복구하는 것도 recovery 계약과 다르다.

## 결정

Socket/clock/coordinator와 독립인 C++17 [SteeringReceiver](../../interfaces/steering/steering_receiver.hpp)를
Command/Actual stream마다 단일 thread에서 소유한다. Runtime 동적 할당이나 unbounded drain은 없다.
신뢰된 호출자의 `start_session(epoch, monitoring_enable_ns)`가 INIT 설정을 전달한다.
첫 Epoch는 nonzero, 재초기화는 이전보다 큰 Epoch와 비감소 시각을 요구한다.
동일 인스턴스의 Epoch reuse/overflow를 거부하며 frame에서 새 Epoch를 자동 학습하지 않는다.

수신 순서는 clock/timeout → envelope → P05 → payload 표현 → Epoch/source age/trace Sequence
→ validity/mode/range다. P05 raw counter는 기존 규격대로 갱신한다. Application의
Sequence/source cursor/snapshot/last-valid RX는 모든 조건이 통과한 경우만 함께 갱신한다.
반환값은 reject 이유와 이번 호출의 E2E status를 구분하며, envelope/API 오류 때 이전 OK를 재사용하지 않는다.

| 정책 | 로컬 실험 설정 / 의미 |
| --- | --- |
| Clock | caller가 전달하는 uint64 ns; source와 now가 같은 monotonic domain이라는 설정 전제 |
| Trace Sequence | 첫 번호 0..9, 이후 +1..+10; 같은 Epoch의 uint32 wrap 거부 |
| Source time | session 시작 이상, now 이하, 수용한 이전 source보다 엄격히 증가 |
| Source freshness | 기본 age <=30 ms; cached 재송신은 source/Sequence를 바꾸지 않음 |
| RX/acquisition timeout | 기본 age >=80 ms; 첫 유효 수신 전에는 monitoring enable이 기점 |
| Timeout 설정 상한 | <=80 ms로 제한해 기존 100 ms budget의 polling/dispatch/jitter 20 ms를 남김 |
| 조향 한계 | finite min < max를 caller가 명시; wire 범위 안, fixture는 +/-0.5 rad |
| Numeric boundary | raw→double의 1 ULP 오차만 허용; 다음 0.0001-rad wire step은 거부 |

Config는 `0 < max_source_age_ns < timeout_ns <=80 ms`를 요구한다. 이 후보값과 fixture 한계는
양산차 calibration이 아니며 TBD-01/02/04를 CLOSED로 바꾸지 않는다.
Command는 NORMAL/DEGRADED + normal path만 수용한다. INIT와 보호 FAIL_SAFE command는
물리 정책이 정의되지 않아 거부한다. Actual은 sender 상태를 보존하며 origin=0은 INIT에서만
허용한다. Fault/protection 중 유효 Actual sample을 정상 주행 가능 판정으로 바꾸지 않는다.

`receive`와 `current_sample`은 timeout을 먼저 검사하고, 입력 없는 cycle은 caller가 `poll`한다.
Timeout/clock 감소는 fault로 유지하며 새 Epoch의 explicit INIT만 초기화한다.
`current_sample(now)`는 source age도 검사한다. 80 ms RX timeout 전이어도 30 ms source age가
끝나면 값이 없다. `last_accepted()`는 fault 후에도 남는 진단 이력이며 제어 입력 조회 API가 아니다.

## 대안과 결과

Socket 내부에서 바로 수용하거나 수신 frame으로 Epoch를 학습하면 clock/epoch/timeout 경계 시험이
transport에 결합된다. 명시적 local API로 분리해 수동 시각으로 경계와 fault를 먼저 검증한다.
항목별 reject는 반환값으로 전달하고 외부 logger가 호출 시각과 함께 기록한다.

실제 CLOCK_MONOTONIC adapter, startup coordinator/영속 Epoch, stream당 bounded queue,
socket overflow 관측, 10 ms monitor dispatch 및 wall-time 검출 지연 측정은 후속 작업이다.
이 수신부는 AUTOSAR profile-independent E2E State Machine이나 vehicle safety state machine이 아니다.
Actual invalid에 대한 Host apply/tick gate와 actuator availability, 보호 출력, dynamics는
Zone/Plant Adapter/vECU 통합에서 별도로 구현한다.

## 증거

[실행 기록](../learning/m1_steering_receiver.md): 새 receiver 19개 + 기존 25개 = normal/ASan·UBSan
각각 44개 PASS. Demo, 변경 source의 compiler/static analysis와 README의 light/dark Mermaid 렌더링을
확인했다. System TC, 실제 검출 지연, M1 acceptance와 학습자 review는 완료로 처리하지 않는다.

후속 [ADR-0009](ADR-0009-steering-socketcan.md)에서 실제 CLOCK_MONOTONIC/SocketCAN adapter와
독립 process 시험을 연결했다. 영속 Epoch coordinator와 차량 task/physical response는 남아 있다.

2026-10-13 [ADR-0012](ADR-0012-brake-receiver.md)에서 이 clock/Epoch/Sequence/timeout 상태를
공통 `ActuatorReceiverState`로 추출해 Brake와 공유했다. 기존 Steering API와 정책은 유지했고
기존 시험을 포함한 normal/sanitizer unit·vCAN을 다시 실행했다.
