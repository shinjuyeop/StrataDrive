# Trusted Clock recovery protocol

SD-4001은 입력 복원/INIT만으로 Passed가 되지 않는다. 같은 clock instance의 신뢰된
로컬 관리 경로가 명시적인 재검증 revision과 다음 application epoch를 제공해야 한다.
동일 domain/instance, zero offset/uncertainty의 established agreement만 수용한다.
새 실제 8-role Release 뒤 해당 owner의 정상 gate/현재 native health와 원본 source가
100ms 연속 전진하고 source age/gap≤30ms일 때 원래 occurrence에 Control proof/Passed를
연결한다. 100ms는 진단 복구 관측창이며 제어 검출/보호/command expiry를 늘리지 않는다.

시계 역행/다른 instance는 재검증을 무효화한다. 불완전 release, source 정지/역행,
stale/future source, native failure, 다른 session/plan은 연속창을 충족하지 않는다.
후속 고장은 새 revision을 요구한다. DTC history/발생 횟수/명시적 clear 계약은 유지한다.

단위 경계와 실제8-role logical SIL을 각각 실행한다. 차량 시험은 정상10s에 BMS owner의
로컬 clock만2ms 되돌려 실제 SessionParticipant Clock fault를 발생시키고 즉시 복원한다.
물리 clock/모델은 바꾸지 않는다.20s 새 INIT 전19s 명시적 재검증을 하는 경로와 재검증
없이 새 INIT만 하는 대조 경로를24s까지 비교한다. 실제 PowerReady/BMSActive와 완전한
Release를 관측한다. Debug/ASan·UBSan/TSan은 기능 판정이며 wall timing을 주장하지 않는다.
각 executable watchdog600s, 원본 실패·binary/source·canonical journal·물리/관측 행을 보존한다.

API는 신뢰된 같은 owner composition용이며 받은 패킷의 timestamp는 재검증 권한이 아니다.
다른 host/reboot clock mapping, 원격 재검증 service와 Target clock hardware 수용은 별도다.
