# M1 첫 실행: SocketCAN / vCAN

Status: **M1 IN PROGRESS — 개발 환경의 transport smoke 실행 완료**.
학습자 코드 review와 직접 재현은 **PENDING**이다. Six-frame DBC/codec, CRC/sequence/
freshness 검증과 M1 acceptance는 아직 **PLANNED / NOT RUN**이다.

## 이번 작업의 끝

임시 vCAN에서 송신 socket이 보낸 CAN FD frame을 별도 수신 socket이 받아
ID, payload 길이와 내용이 일치하는지 확인한다. 이 작은 실행부터 프로젝트 구현을 시작한다.
조향 dynamics와 jam 판정의 상세 학습은 M2의 해당 구현에서 이어간다.

## 직접 실행

Repository root의 Linux terminal에서 실행한다.

```sh
unshare --user --map-root-user --net python3 tools/vcan_smoke.py
```

현재 Host에 있는 Python standard library, `ip`, `unshare`와 kernel vCAN을 사용한다.
추가 package 설치는 없다. `unshare`는 이번 process만의 user/network namespace를 만든다.
Script는 그 안에 `sd_m1_probe`를 생성하고 실행 후 삭제한다. Namespace도 process 종료 시
사라진다. 이 실험의 namespace 선택은 M4/M5 배포 방식(TBD-05)을 결정하지 않는다.

예상 출력:

```text
TX CAN FD id=0x5A0 len=12 data=537472617461447269766521
RX CAN FD id=0x5A0 len=12 data=537472617461447269766521
PASS: vCAN transport smoke (차량 command/actual 검증 아님)
```

권한 또는 vCAN 지원 오류가 나오면 해당 오류를 확인한다. 위 명령은 현재 Host에서
검증했으며 다른 Linux/Target에서도 실행된다고 가정하지 않는다.

## 코드에서 볼 것

[vcan_smoke.py](../../tools/vcan_smoke.py)의 `main()`은 interface 생성·정리를,
`exchange()`는 socket 설정·송수신·비교를 맡는다.

- 송신·수신 socket에서 `CAN_RAW_FD_FRAMES`를 활성화한다.
- 수신 filter는 fixture ID의 standard data frame을 선택한다.
- `struct canfd_frame`에 해당하는 72-byte socket buffer를 사용한다. Payload는 12 bytes다.
- `len`은 payload byte 수다. DBC의 bit layout이나 CAN FD의 DLC code와 구분한다.
- 수신 대기 1 s는 실행 중 무한 대기를 막는 값이다. 차량의 100 ms 검출 requirement가 아니다.

`0x5A0`와 `StrataDrive!`는 transport fixture다. Steering Command/Actual의 CAN ID나
signal 정의가 아니며 TBD-01/02를 해소하지 않는다. Linux socket ABI의 native endian은
향후 DBC signal endian 선택과 별개다. 이 도구의 Python 선택은 Host 개발 실험에 한정하며
C++ application의 표준/compiler/test toolchain(TBD-11)은 이후 첫 codec 구현 전에 검토한다.

Socket API와 vCAN 동작은 [Linux SocketCAN 문서](https://docs.kernel.org/networking/can.html),
Python binding은 [Python socket 문서](https://docs.python.org/3.10/library/socket.html)를 따른다.

## 실행 기록과 한계

2026-09-28, Codex가 현재 Host에서 실행했다.

| 항목 | 기록 |
| --- | --- |
| 환경 | Linux 6.8.0-138-generic, x86_64, Python 3.10.12 |
| 도구 | iproute2 5.15.0, util-linux (`unshare`) 2.37.2 |
| 확인한 동작 | CAN FD socket frame 송신/수신, ID/길이/payload 일치 |
| 결과 | 위 TX/RX 출력, exit code 0 |
| 추가 개발 점검 | 수신이 끊기면 exit 1 및 interface 정리; 같은 이름의 기존 interface는 삭제하지 않음 |
| Requirement / TC 판정 | 변경 없음. 기존 runtime TC는 NOT RUN |
| 학습자 review / 재현 | PENDING |

이는 Host의 개발 환경 확인이다. Target에 Zone/vECU를 배포한 결과, actuator actual
response, AI inference, CAN 전기적 특성·arbitration·실시간 timing 검증이 아니다.
Fixture 수신값을 차량 actual feedback으로 사용하지 않는다.

## 바로 다음 구현

1. 기존 [CAN ICD](../icd/can_icd.md)에 따라 six-frame wire 계약 초안을 작성한다.
   Steering Command/Actual부터 살펴보고 Brake/Drive와 공통 metadata를 함께 맞춘다.
2. CAN ID/layout/scaling, CRC/sequence/epoch/freshness와 receiver 정책의 근거를 검토한다.
3. Golden vectors를 만든 뒤 작은 codec과 정상·invalid-input 시험을 구현한다.
4. 확정한 application frame을 vCAN으로 주고받고 관련 TC에 결과를 연결한다.

각 작업에서 필요한 개념만 설명하고 실행으로 이어간다. AUTOSAR 전체나 안전 분석 전체를
먼저 공부해야 M1을 진행할 수 있는 것은 아니다. 관련 설계 결정에 필요한 검토는 유지한다.
