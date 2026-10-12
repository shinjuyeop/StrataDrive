#!/usr/bin/env python3
"""M1 DBC parser/golden vectors 검사. 선택 시 C++ demo payload와 교차 검증한다."""

import argparse
import binascii
from pathlib import Path
import re
import subprocess
import sys

try:
    import cantools
except ImportError:
    raise SystemExit("cantools가 필요합니다. docs/learning/m1_steering_frame_codec.md를 참고하세요.")


ROOT = Path(__file__).resolve().parent.parent
LAYOUT = {
    "Angle": (0, 16), "SchemaVersion": (16, 8), "Validity": (24, 8),
    "Sequence": (32, 32), "Epoch": (64, 32), "SourceTimeNs": (96, 64),
    "CausalSequence": (160, 32), "LocalState": (192, 8), "Origin": (200, 8),
    "Reserved": (208, 24), "E2ECrc": (232, 16), "E2ECounter": (248, 8),
}
RANGES = {
    "Angle": (-3.2767, 3.2767), "SchemaVersion": (2, 2), "Validity": (0, 1),
    "Sequence": (0, 2**32 - 1), "Epoch": (1, 2**32 - 1),
    "SourceTimeNs": (0, 2**64 - 1), "CausalSequence": (0, 2**32 - 1),
    # cantools는 DBC의 [0|0]을 min/max 미지정으로 읽는다. Reserved=0은 C++에서 검사한다.
    "LocalState": (0, 3), "Origin": (0, 2), "Reserved": (None, None),
    "E2ECrc": (0, 65535), "E2ECounter": (0, 255),
}
CHOICES = {
    "Validity": {0: "InvalidOrUnavailable", 1: "Valid"},
    "LocalState": {0: "INIT", 1: "NORMAL", 2: "DEGRADED", 3: "FAIL_SAFE"},
    "Origin": {0: "NoAcceptedInput", 1: "NormalPath", 2: "LocalProtection"},
}
DATA_IDS = {0x180: 0x1001, 0x280: 0x1002}
GOLDEN = [
    ("CMD-POS", "SteeringCommand", 2000, 0, 1000000000, 7, 0, 0x26EB,
     "D0 07 02 01 00 00 00 00 01 00 00 00 00 CA 9A 3B "
     "00 00 00 00 07 00 00 00 01 01 00 00 00 EB 26 00"),
    ("ACT-POS", "SteeringActual", 1500, 0, 1010000000, 0, 0, 0x2D52,
     "DC 05 02 01 00 00 00 00 01 00 00 00 80 60 33 3C "
     "00 00 00 00 00 00 00 00 01 01 00 00 00 52 2D 00"),
    ("CMD-NEG", "SteeringCommand", -2000, 1, 1020000000, 8, 1, 0xBA82,
     "30 F8 02 01 01 00 00 00 01 00 00 00 00 F7 CB 3C "
     "00 00 00 00 08 00 00 00 01 01 00 00 00 82 BA 01"),
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def signals(raw_angle, sequence, timestamp, cause, crc=0, counter=0):
    return {
        "Angle": raw_angle, "SchemaVersion": 2, "Validity": 1,
        "Sequence": sequence, "Epoch": 1, "SourceTimeNs": timestamp,
        "CausalSequence": cause, "LocalState": 1, "Origin": 1,
        "Reserved": 0, "E2ECrc": crc, "E2ECounter": counter,
    }


def payload_crc(can_id, payload):
    covered = payload[:29] + payload[31:] + DATA_IDS[can_id].to_bytes(2, "little")
    return binascii.crc_hqx(covered, 0xFFFF)


def check_database(db):
    require(cantools.__version__ == "40.7.1", "cantools 40.7.1로 재현해야 합니다.")
    require({item.name for item in db.messages} == {"SteeringCommand", "SteeringActual"},
            "Steering 두 frame의 정의가 필요합니다.")
    for name, can_id, sender, receiver in [
            ("SteeringCommand", 0x180, "Zone", "SteeringVecu"),
            ("SteeringActual", 0x280, "SteeringVecu", "Zone")]:
        message = db.get_message_by_name(name)
        require(message.frame_id == can_id and message.is_fd and not message.is_extended_frame,
                f"{name}: CAN ID/FD/standard format 불일치")
        require(message.length == 32 and message.cycle_time == 10 and message.senders == [sender],
                f"{name}: length/period/sender 불일치")
        require({item.name: (item.start, item.length) for item in message.signals} == LAYOUT,
                f"{name}: signal 배치 불일치")
        attributes = message.dbc.attributes
        expected_attributes = {"E2EProfile": 5, "E2EDataID": DATA_IDS[can_id],
                               "E2EOffsetBits": 232, "E2EMaxDeltaCounter": 10}
        for key, value in expected_attributes.items():
            require(key in attributes and attributes[key].value == value,
                    f"{name}: {key} 설정 불일치")
        for signal in message.signals:
            require(signal.byte_order == "little_endian" and signal.receivers == [receiver],
                    f"{name}.{signal.name}: endian/receiver 불일치")
            require(signal.is_signed == (signal.name == "Angle"),
                    f"{name}.{signal.name}: signed 형식 불일치")
            require(signal.offset == 0 and signal.scale == (0.0001 if signal.name == "Angle" else 1),
                    f"{name}.{signal.name}: factor/offset 불일치")
            require((signal.minimum, signal.maximum) == RANGES[signal.name],
                    f"{name}.{signal.name}: wire range 불일치")
            unit = "rad" if signal.name == "Angle" else "ns" if signal.name == "SourceTimeNs" else None
            require(signal.unit == unit, f"{name}.{signal.name}: unit 불일치")
            choices = {value: str(label) for value, label in (signal.choices or {}).items()}
            require(choices == CHOICES.get(signal.name, {}),
                    f"{name}.{signal.name}: enum 정의 불일치")
        print(f"PASS: {name} id=0x{can_id:03X}, CAN FD, 32 bytes, 12 signals, E2E P05")


def check_vectors(db):
    require(binascii.crc_hqx(b"123456789", 0xFFFF) == 0x29B1, "CRC check 값 불일치")
    # AUTOSAR R25-11 PRS 6.8.5의 공식 예제와 Python C CRC를 대조한다.
    require(binascii.crc_hqx(bytes(6) + bytes.fromhex("34 12"), 0xFFFF) == 0xCA1C,
            "공식 P05 offset=0 예제 CRC 불일치")
    require(binascii.crc_hqx(bytes(14) + bytes.fromhex("34 12"), 0xFFFF) == 0x9128,
            "공식 P05 offset=64 예제 CRC 불일치")
    print("PASS: official AUTOSAR R25-11 P05 CRC examples (offset 0 and 64 bits)")
    for label, name, raw, seq, timestamp, cause, counter, crc, text in GOLDEN:
        message = db.get_message_by_name(name)
        expected = signals(raw, seq, timestamp, cause, crc, counter)
        payload = bytes.fromhex(text)
        require(message.encode(expected, scaling=False, strict=True) == payload,
                f"{label}: DBC encode와 golden bytes 불일치")
        require(message.decode(payload, decode_choices=False, scaling=False) == expected,
                f"{label}: DBC raw decode 불일치")
        require(payload_crc(message.frame_id, payload) == crc, f"{label}: 독립 CRC 불일치")
        print(f"PASS: {label} DBC encode/decode, golden bytes, CRC=0x{crc:04X}")
    # 시각을 정수 그대로 encode/decode해 float64의 정밀도 제약을 피한다.
    message = db.get_message_by_name("SteeringActual")
    for timestamp in [2**53 + 1, 2**64 - 1]:
        values = signals(0, 0, timestamp, 0)
        payload = message.encode(values, scaling=False, strict=True)
        require(message.decode(payload, decode_choices=False, scaling=False)["SourceTimeNs"] == timestamp,
                "SourceTimeNs의 정수 정밀도가 손실됐습니다.")
    print("PASS: exact uint64 SourceTimeNs above 2^53 and at UINT64_MAX")


def check_demo(db, demo):
    for kind, input_value, raw in [("command", "0.2", 2000), ("actual", "0.15", 1500),
                                   ("command", "-0.2", -2000), ("actual", "invalid", -32768)]:
        name = "SteeringCommand" if kind == "command" else "SteeringActual"
        message = db.get_message_by_name(name)
        result = subprocess.run([str(demo), kind, input_value], capture_output=True,
                                text=True, check=True, timeout=5)
        payload_line = re.search(r"^Payload: ([0-9A-F ]+)$", result.stdout, re.M)
        id_line = re.search(r"^ID: 0x([0-9A-F]+)$", result.stdout, re.M)
        require(payload_line and id_line, "C++ demo 출력 형식 불일치")
        payload = bytes.fromhex(payload_line[1])
        require(len(payload) == 32 and int(id_line[1], 16) == message.frame_id,
                "C++ demo ID/length 불일치")
        expected = signals(raw, 0, 1000000000 if kind == "command" else 1010000000,
                           7 if kind == "command" else 0)
        if input_value == "invalid":
            expected.update(Validity=0, LocalState=0, Origin=0)
        # Invalid sentinel은 physical min/max 밖이다. 시험용으로 raw encode한다.
        draft_payload = message.encode(expected, scaling=False, strict=input_value != "invalid")
        expected["E2ECrc"] = payload_crc(message.frame_id, draft_payload)
        require(message.encode(expected, scaling=False, strict=input_value != "invalid") == payload,
                f"C++ {kind} {input_value}: DBC encode 불일치")
        require(message.decode(payload, decode_choices=False, scaling=False) == expected,
                f"C++ {kind} {input_value}: DBC decode 불일치")
        print(f"PASS: C++ {kind} {input_value} payload matches DBC + independent CRC")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbc", type=Path, default=ROOT / "interfaces/dbc/steering_m1_draft.dbc")
    parser.add_argument("--demo", type=Path, help="C++ steering_frame_demo 경로 (선택)")
    args = parser.parse_args()
    try:
        db = cantools.database.load_file(args.dbc, strict=True)
        check_database(db)
        check_vectors(db)
        if args.demo:
            check_demo(db, args.demo.resolve())
    except (OSError, ValueError, cantools.errors.Error, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: Host DBC/codec checks (receiver/transport/vehicle 검증 아님)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
