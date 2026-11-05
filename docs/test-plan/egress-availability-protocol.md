# 연결 종료 이후 egress와 처리 응답 우선 연결 검증

2026-11-05, base `ddac8ec` + plant-field-io 후보. 선행 기능12/12·서비스28/30의
분모와 원본을 유지한다. 새 후보의 결과를 이전 실패와 합치지 않는다.

선행 ASan slow-signals에서 SDK는 Central1 TCP 단절을 알렸지만 어댑터가
Actual을 계속 enqueue하여 외부8192-byte 큐를 넘었다. 새 후보는 SDK availability
소실 뒤 enqueue를 거절하고 sender도 SDK 호출 전에 다시 확인한다. 미전송 원본은
CRC/시각의 `tx-unavailable`과 count로 기록한다. 거절은 성공이나 ACK가 아니며
owner 보호/원래 pending deadline을 유지한다. 용량을 늘리거나 SDK 오류를 면제하지 않는다. 이미 SDK에 넘긴 bytes와
availability 확인 직후의 단절 race까지 취소한다고 주장하지 않는다.

선행 TSan normal-r3의 Rear 정지 token674는 원래20ms 기한을 넘겨
25.304616ms에 Central에 도착했다. TxResult0x0080을 기존 우선 TCP 연결
Front0x5347:30504/Rear0x534b:30508로 옮긴다. 권한/feedback 의미와 wire payload는
그대로다. TxResult는 권한이 아니다. 구 binding은 거절하고 세 ECU를 함께 빌드한다.
기존 telemetry0x0070은 data 연결에 남는다. 기한·주기·FIFO 용량을 바꾸지 않는다.

변경 pure transport contract/PlantIO 회귀를 Debug·ASan/UBSan·TSan으로 실행하고,
변경 header 포함 cppcheck/clang-tidy, Python 및 adapter build를 검사한다.
선행 전체 Debug/ASan1277과 TSan115/116의 결과는 이번 전체 재실행으로 세지 않는다.
그 TSan wall 실패는 새 IPC/SDK 경로를 사용하지 않으며 여전히 OPEN이다.

검사 뒤 source/binary 고정 후 동일 기능12건과 서비스30건(Normal6/ASan6/TSan18)을
한 번 실행한다. 모든 runtime 종료 뒤 감사한다. Native 중 build/무거운 분석/다른
runtime은 금지한다. 실패 원본·분모를 보존한다. 강제 종료 중 OS의 첫 reset/broken
pipe와 정상 운행의 deadline 위반은 그대로 원본 기준으로 판정한다. 추가 반복 cohort는 없다.
전체 M9/CARLA subinterval/Clock/bootstrap/전체 fault·보존/Target 완료를 뜻하지 않는다.
