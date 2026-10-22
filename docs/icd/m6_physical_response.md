# M6 SIL physical-response-v1

Status: **현재 Host quiet 모델 한정 채택**,2026-10-22.
SYS-COM-003의 마지막 유효 RX→검출100ms와 SYS-SAFE-004의 zero-target 선택은 유지한다.
[사전 산식/실행 근거](../test-plan/evidence/m6_physical_response/README.md),
[단일 실행 설정](../../profiles/m6_sil_response_v1.json),
[에너지 경계](vehicle_energy.md)를 함께 적용한다.

| 시간/조건 | 적용값 | 실제 근거 |
| --- | --- | --- |
| 마지막 유효 수신→상실 검출 | <=100ms | matching Leaf valid-input/command-expired, 원래 source/expiry |
| 로컬 검출 회차→보호 선택 ACK | <=4ms | owner service 진입~fault 관측 구간/실제 선택 ACK |
| 최초 로컬 목표 선택→양쪽 출력 적용 | <=4ms | 실제 Actuation.issued_time/applied-source/physical step 전후 |
| 최초 로컬 목표 선택→실제 완료 관측 | <=230ms | abs(T)<=1Nm 및 실제 압력>=1MPa 동시 만족 |
| 모델 실행 간격 | <=4ms | 기존 native2ms opportunity/4ms guard와 bounded model samples |

Drive 모델의 −200..+300Nm/zero rate2000Nm/s는 tolerance1Nm까지 각각99.5/149.5ms다.
Brake physical max1.5MPa/초기0.2MPa, 최저0Pa, 보호floor1MPa/rise5MPa/s는200ms 최악이다.
정상50ms 지연은 보호가 pending normal과 함께 취소하며 보호 지연은0이다.
병렬 물리200 + 양쪽 인계4 + 모델4 + 기존 CSV관측10 + 명시 여유12 =230ms.
초기0.2MPa만 고려하면160ms지만 정상 해제 후0Pa도 포함해 산정했다.
보호는 더 높은 압력을 낮추지 않는다. 동작 범위 밖 OEM/Target calibration 보장은 아니다.

Runner/oracle는 JSON을 읽고 plan/result/per-case contract에 저장한다. C++ fixture는
JSON에서 전달받은 완료 threshold만 사용하며 물리 모델/ECU target을 바꾸지 않는다.
compiled model 설정 readback과 JSON이 다르면 FAIL이다. reference.yaml은 loader가 아니다.
활성화는 M6 energy normal/command-loss에 한정하며 M5/다른 profile의 판정을 바꾸지 않는다.

Bounded1024개의 약500us step 기록은 torque/pressure·Epoch·원래 output/issued/applied source를
보존한다. 완료 모델 sample과 연속 crossing 시각을 같게 쓰지 않고 직전 미완료~최초 완료로
bracket한다. 실제 적용은 성공한 physical step의 전후 구간이며 요청 시각으로 소급하지 않는다.
기존10ms CSV의 첫 완료 관측은 따로 보고한다. 누락/비유한/미응답/시한 초과는 FAIL이다.
기존 command/permission expiry·source age·20ms envelope·2ms/4ms watch·queue·CAN/P05·
실제8참여자 Release ACK/RunLease/arm·독립 보호는 변경하지 않는다.
