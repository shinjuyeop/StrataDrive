#!/usr/bin/env python3
"""M1 환경 확인: 임시 vCAN에서 CAN FD frame 하나를 송수신한다."""

import socket
import struct
import subprocess
import sys


INTERFACE = "sd_m1_probe"
# 아래 ID/payload는 transport 확인용 fixture이며 차량 DBC 정의가 아니다.
PROBE_ID = 0x5A0
PAYLOAD = b"StrataDrive!"
# Linux canfd_frame ABI: native byte order, ID / length / flags / padding / data.
# length는 DLC code가 아닌 payload byte 수다. DBC signal endian과 별개다.
CAN_FD_FRAME = struct.Struct("=IBB2x64s")


def exchange():
    """별도 송신·수신 socket으로 ID, payload 길이와 내용을 확인한다."""
    with socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as receiver, \
            socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as sender:
        for endpoint in (receiver, sender):
            endpoint.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FD_FRAMES, 1)
            # 실행이 무한 대기하지 않게 하는 제한이며 차량 timeout requirement가 아니다.
            endpoint.settimeout(1.0)
            endpoint.bind((INTERFACE,))

        mask = socket.CAN_SFF_MASK | socket.CAN_EFF_FLAG | socket.CAN_RTR_FLAG
        receiver.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER,
                            struct.pack("=II", PROBE_ID, mask))
        sender.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, b"")
        frame = CAN_FD_FRAME.pack(PROBE_ID, len(PAYLOAD), 0, PAYLOAD)
        if sender.send(frame) != CAN_FD_FRAME.size:
            raise RuntimeError("CAN FD frame 전체를 송신하지 못했습니다.")
        print(f"TX CAN FD id=0x{PROBE_ID:03X} len={len(PAYLOAD)} data={PAYLOAD.hex()}")

        received = receiver.recv(CAN_FD_FRAME.size)
        if len(received) != CAN_FD_FRAME.size:
            raise RuntimeError("수신한 frame이 CAN FD socket frame이 아닙니다.")
        can_id, length, _flags, data = CAN_FD_FRAME.unpack(received)
        if (can_id, length, data[:length]) != (PROBE_ID, len(PAYLOAD), PAYLOAD):
            raise RuntimeError("수신 ID, 길이 또는 payload가 송신값과 다릅니다.")
        print(f"RX CAN FD id=0x{can_id:03X} len={length} data={data[:length].hex()}")


def main():
    created = False
    try:
        subprocess.run(["ip", "link", "add", "dev", INTERFACE, "type", "vcan"],
                       check=True)
        created = True
        subprocess.run(["ip", "link", "set", "dev", INTERFACE,
                        "mtu", str(CAN_FD_FRAME.size), "up"], check=True)
        exchange()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    finally:
        # 기존 interface에는 손대지 않고, 이번 실행에서 만든 것만 정리한다.
        if created:
            subprocess.run(["ip", "link", "delete", "dev", INTERFACE], check=True)
    print("PASS: vCAN transport smoke (차량 command/actual 검증 아님)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
