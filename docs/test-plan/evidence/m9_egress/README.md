# 연결 불가 egress와 처리 응답 우선 연결

2026-11-05, [사전 protocol](../../egress-availability-protocol.md)의 기능 **12/12**,
서비스 **27/30**(Normal6/6·ASan5/6·TSan16/18)이다. 전체 수용은 OPEN이다.
[선행 IO 후보](../m9_plant_field_io/README.md)의28/30과 합치지 않는다.

## 변경과 확인

SDK availability가 사라진 뒤에는 새 owner packet을 enqueue하지 않고, sender도
SDK 호출 전에 다시 검사한다. 미전송은 원래 CRC/시각의 `tx-unavailable`과 count로
기록한다. 성공/ACK로 처리하거나 replacement peer에 재생하지 않는다. 이미 SDK에
넘긴 bytes나 availability 확인 직후의 단절 race를 취소한다고 주장하지 않는다.
처리 결과0x0080은 Front0x5347:30504/Rear0x534b:30508의 우선 연결을 사용한다.
TxResult는 권한이 아니며 원래 payload/20ms 기한을 유지한다.

[30건 trace 대조](egress-audit.json)에서 연결 불가 거절2908건과 우선 연결 result52331건을
확인했고, SDK/어댑터 큐 포화는0건이다. 단절1000회 후 재연결에 이전 payload가 남지
않는 회귀, full queue·원본 credit·legacy/새 binding을 포함한 transport36개와
PlantIO4개가 Debug/ASan·UBSan/TSan 각각 통과했다. 변경 header 포함 정적 검사와
Python38개도 통과했다. 선행 전체 Debug/ASan1277·CARLA 논리162는 이번 전체
재실행으로 세지 않는다. 선행 메모리 M4 TSan wall 실패도 계속 OPEN이다.

## 원래 판정으로 남긴 세 실패

- ASan stop-ack-loss: Central1 SIGKILL9.593246ms 뒤 Front TCP reset104.
  새 Central boot 전이고 surviving PID는 같지만, 기존 SDK 기준상 실패다.
  [시각·원문 대조](sdk-cause.json)는 판정을 변경하지 않는다.
- TSan actual-loss-r2: Epoch2의 원래 command expiry873044391962245를 넘긴
  뒤 Front/Rear SD-2001이 발생해 Epoch3 시작 전에 종료했다. 의도한 fault 시험을
  완료하지 못했다. 정상 prefix만 성공으로 세지 않는다.
- TSan stop-request-loss-r3: Epoch3의 원래 command expiry873105117274448을
  넘긴 뒤 Zone SD-2001이 발생했다. 요구한 원래 Stop detector DTC를 확인하지
  못했으므로 실패다.

[원본 결과](results.json), [포장 시 source/binary 동일성](identity-checks.json), 각 profile/round의
원본 archive를 보존한다. 강제 종료 SDK 판정 변경은 사용자에게 질문한 상태이며 적용하지
않았다. 큐 포화·기한 초과는 그 질문과 별개다. 전체 완료 조건은 [프로젝트 상태](../../../project-status.md)를 따른다.
