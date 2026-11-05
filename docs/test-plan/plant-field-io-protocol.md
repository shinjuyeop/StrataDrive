# Host SIL 센서·출력 전달 분리 검증

2026-11-05, base `ddac8ec`. 지연 grant 후보와 분리한 새 고정 cohort다.
원본 normal-actual-loss의 Brake Actual84는 source830400811785904,
NormalPath/Degraded, 유효 pressure952000Pa다. 이전83은 Normal/1000000Pa다.
누락이나 command 만료가 아니라 응답 monitor의 일시 위반이 먼저 발생했다.
Physical trace의 압력 하강과 최초 Leaf 출력 사이의 지연은 공유 파일 전달 경로를
조사할 근거이며, 원본에 없는 개별 syscall 시각을 확정하지 않는다.

기존 파일 전체 read/modify/write 잠금을 센서·Leaf별 출력·Release 필드별
nonblocking OFD lock으로 분리한다. 잠금 안에서 callback/모델 작업을 하지 않는다.
동일 필드 busy는 기존 값을 유지하며 원래 source/epoch로 재시도한다. 다른 필드의
busy가 Brake 출력/Release를 막지 않도록 한다. Leaf 실행 후 같은 turn에서 출력도
전달하여 다음 ingress 대기를 기다리지 않는다. 실제 물리 적용은 다음 plant step의
현재 시각이다. 예측 tolerance, detector, source/expiry, 주기는 바꾸지 않는다.

필드 경합·원본 재시도·잘린 IO 및 독립 writer 보존 회귀, 전체 Debug/ASan·UBSan,
관련 TSan과 변경 구현 정적 검사, 기존 Python 검사를 실행한다. 새 source와
Normal/ASan/TSan binary 고정 후 기존 기능12건과 서비스 Normal6/ASan6/TSan18건을
한 번씩 실행한다. Native 중 build/무거운 감사/다른 runtime은 실행하지 않는다.
모든 실패와 원본을 보존하고 모든 runtime 종료 뒤 감사한다. 조건부 추가 cohort는 없다.

SDK 판정은 그대로다. 강제 Central 종료와 TCP Broken pipe/reset의 원인 관계를
별도 분석하되 이 cohort의 실패를 통과로 바꾸지 않는다. 전체 M9, native4ms/Target,
CARLA subinterval, trusted Clock/부트 이전 incident, 전체 fault/보존 수용을 대신하지 않는다.

## Native 실행 전 검증 관측

전체 Debug/ASan 각1277개는 통과했다. 관련 TSan116개 중 기존
`M4AsyncWall.IndependentOwnersRunActualNormalPath`가 원래 transport 기한을
초과해 실패했다(115/116). 이 메모리 기반 M4 경로는 새 PlantIO를 사용하지 않으며
해당 runtime/test source는 base와 같다. 실패를 삭제하거나 재시도하지 않는다.
나머지 정적 검사·adapter build 뒤 위 고정42건은 변경한 실제 IPC 경로의 진단
근거로 실행한다. 통과하더라도 위 TSan wall 실패나 전체 수용을 대체하지 않는다.
