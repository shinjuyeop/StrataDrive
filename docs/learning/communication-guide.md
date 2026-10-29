# 통신과 수신 검증

## 전체 흐름

물리값·의미를 먼저 정하고 field encoding → frame codec/DBC → E2E P05 → receiver →
SocketCAN 순서로 읽는다. 각 계층의 검사는 서로를 대신하지 않는다.
조향은 equivalent front road-wheel angle(rad, 좌+), Drive는 signed torque(Nm), Brake는
aggregate friction pressure(Pa)다. 값0과 unavailable, Command와 독립 Actual을 구분한다.

| 읽을 코드·계약 | 확인할 것 |
| --- | --- |
| `interfaces/steering/`, `brake/`, `drive/`, `bms/` | 값·단위·범위·reserved, 독립 command/actual·capability |
| [CAN ICD](../interfaces/can.md) · [Steering](../interfaces/steering-frame.md) · [BMS](../interfaces/bms-frame.md) | schema·payload layout·Data ID·원천/부모·expiry |
| `interfaces/common/` | P05 Protect/Check, counter·CRC와 application 수신 상태의 구분 |
| `interfaces/session/` | 영속 Epoch·trusted INIT·queue/overflow·이전 세션 차단 |
| `interfaces/socketcan/` · `tests/integration/can/` | 실제 socket TX/RX·독립 process·silent/flood/중단 |

## 처음 실행하기

저장소 루트에서 [core 빌드](../../README.md#시작하기)를 먼저 한다.

```sh
build/m1-angle/actuator_demo frame command 0.2
build/m1-angle/actuator_demo frame actual 0.15
build/m1-angle/actuator_demo frame actual invalid
unshare --user --map-root-user --net python3 tools/vcan_smoke.py
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py
```

vCAN smoke는 interface 생성·TX/RX 일치·정리만 확인한다. 차량 command/Actual 검증은 아니다.
`check_socketcan.py --family ev`로 EV 경로만 선택할 수 있다. Kernel vCAN·user/network namespace
지원이 필요하며 권한 오류를 성공으로 해석하지 않는다. CLI의 값·시각은 fixture다.

## DBC 교차 확인

C++ runtime과 별개인 Python 환경에서 고정 dependency로 DBC를 읽어 C++ payload와 비교한다.
환경이 없다면 아래 명시적 설치를 한 번 수행한다.

```sh
uv venv --python /usr/bin/python3 build/m1-dbc-venv
uv pip install --python build/m1-dbc-venv/bin/python -r tools/requirements-dbc.txt
build/m1-dbc-venv/bin/python tools/check_actuator_dbc.py --demo build/m1-angle/actuator_demo
```

[고정 dependency](../../tools/requirements-dbc.txt)와 [DBC 원본](../../interfaces/dbc)을 사용한다.
CRC/counter golden vector가 맞아도 source/expiry·INIT·timeout까지 수용한 것은 아니다.

## 수신과 세션을 읽는 기준

- CRC/counter와 별도로 source age·clock·epoch·parent·expiry·mode·validity를 검사한다.
- Reject/duplicate/cached replay는 last-valid RX를 갱신하지 않는다. 지속 invalid도 timeout으로 이어진다.
- 새 envelope·새 P05 counter가 오래된 sensor나 BMS dependency를 fresh로 만들지 않는다.
- BMS limit의 부분 유효성을 항목별로 관리한다. 유효한0과 unknown은 다른 gate 결과다.
- Epoch는 trusted coordinator/영속 issuer가 발급한다. 수신 payload에서 자동 학습하지 않는다.
- Queue overflow는 continuity 상실이다. 오래된 queue를 버렸다는 이유로 자동 정상 복구하지 않는다.

[owner-wire v1](../interfaces/owner-wire-v1.md)은 원격 Host 경계의 encoding/권한,
[공통 interface](../interfaces/README.md)는 의미의 기준이다.
