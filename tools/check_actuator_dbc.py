#!/usr/bin/env python3
"""M1 actuator/EV twelve-frame DBC·golden·C++ demo 교차 검증."""

import argparse
import binascii
from pathlib import Path
import re
import subprocess
import sys

try:
    import cantools
except ImportError:
    raise SystemExit("cantools가 필요합니다. docs/learning/communication-guide.md를 참고하세요.")


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
DATA_IDS = {0x180: 0x1001, 0x280: 0x1002, 0x181: 0x1101, 0x281: 0x1102,
            0x182: 0x1201, 0x282: 0x1202,
            0x183: 0x1301, 0x283: 0x1302, 0x284: 0x1303, 0x285: 0x1304,
            0x193: 0x1203, 0x194: 0x1204}
DRIVE_EXTENSION = {
    "WheelSpeed": (256, 16), "WheelSpeedValid": (272, 8), "RegenLimitReason": (280, 8),
    "RegenTorqueLimit": (288, 16), "RegenCapabilityValid": (304, 8), "FeedbackReserved": (312, 8),
    "WheelSpeedSourceTimeNs": (320, 64), "CapabilitySourceTimeNs": (384, 64),
    "CapabilityInputTimeNs": (448, 64),
}
DRIVE_RANGES = {
    "Torque": (-3276.7, 3276.7), "WheelSpeed": (0, 655.34),
    "RegenTorqueLimit": (0, 3276.7), "WheelSpeedValid": (0, 1), "RegenCapabilityValid": (0, 1),
    "RegenLimitReason": (0, 4), "FeedbackReserved": (None, None),
    **{name: (0, 2**64 - 1) for name in DRIVE_EXTENSION if name.endswith("TimeNs")},
}
DRIVE_CHOICES = {
    "WheelSpeedValid": CHOICES["Validity"], "RegenCapabilityValid": CHOICES["Validity"],
    "RegenLimitReason": {0: "Nominal", 1: "MotorOrSpeedLimited", 2: "ChargeAcceptanceLimited",
                         3: "Disabled", 4: "InputsInvalid"},
}
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


def signals(raw_angle, sequence, timestamp, cause, crc=0, counter=0, value_name="Angle"):
    return {
        value_name: raw_angle, "SchemaVersion": 2, "Validity": 1,
        "Sequence": sequence, "Epoch": 1, "SourceTimeNs": timestamp,
        "CausalSequence": cause, "LocalState": 1, "Origin": 1,
        "Reserved": 0, "E2ECrc": crc, "E2ECounter": counter,
    }


def payload_crc(can_id, payload):
    covered = payload[:29] + payload[31:] + DATA_IDS[can_id].to_bytes(2, "little")
    return binascii.crc_hqx(covered, 0xFFFF)


def check_database(db, family="Steering"):
    brake = family == "Brake"
    drive = family == "Drive"
    value_name = "Torque" if drive else "Pressure" if brake else "Angle"
    layout = {value_name if key == "Angle" else key: value for key, value in LAYOUT.items()}
    ranges = dict(RANGES)
    if brake:
        ranges["Pressure"] = (0, 65534000)
    if drive:
        ranges.update(DRIVE_RANGES)
    require(cantools.__version__ == "40.7.1", "cantools 40.7.1로 재현해야 합니다.")
    require({item.name for item in db.messages} == {family + "Command", family + "Actual"},
            f"{family} 두 frame의 정의가 필요합니다.")
    base_id = {"Steering": 0x180, "Brake": 0x181, "Drive": 0x182}[family]
    for name, can_id, sender, receiver in [
            (family + "Command", base_id, "Zone", family + "Vecu"),
            (family + "Actual", base_id + 0x100, family + "Vecu", "Zone")]:
        message = db.get_message_by_name(name)
        extended = drive and name == "DriveActual"
        length = 64 if extended else 32
        expected_layout = {**layout, **(DRIVE_EXTENSION if extended else {})}
        require(message.frame_id == can_id and message.is_fd and not message.is_extended_frame,
                f"{name}: CAN ID/FD/standard format 불일치")
        require(message.length == length and message.cycle_time == 10 and message.senders == [sender],
                f"{name}: length/period/sender 불일치")
        require({item.name: (item.start, item.length) for item in message.signals} == expected_layout,
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
            require(signal.is_signed == (signal.name in ("Angle", "Torque")),
                    f"{name}.{signal.name}: signed 형식 불일치")
            scale = {"Angle": 0.0001, "Pressure": 1000, "Torque": 0.1,
                     "WheelSpeed": 0.01, "RegenTorqueLimit": 0.1}.get(signal.name, 1)
            require(signal.offset == 0 and signal.scale == scale,
                    f"{name}.{signal.name}: factor/offset 불일치")
            require((signal.minimum, signal.maximum) == ranges[signal.name],
                    f"{name}.{signal.name}: wire range 불일치")
            unit = ("ns" if signal.name.endswith("TimeNs") else
                    {"Angle": "rad", "Pressure": "Pa", "Torque": "Nm",
                     "WheelSpeed": "rad/s", "RegenTorqueLimit": "Nm"}.get(signal.name))
            require(signal.unit == unit, f"{name}.{signal.name}: unit 불일치")
            choices = {value: str(label) for value, label in (signal.choices or {}).items()}
            require(choices == {**CHOICES, **DRIVE_CHOICES}.get(signal.name, {}),
                    f"{name}.{signal.name}: enum 정의 불일치")
        print(f"PASS: {name} id=0x{can_id:03X}, CAN FD, {length} bytes, {len(expected_layout)} signals, E2E P05")


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



def check_brake_vectors(db):
    vectors = [
        ("BrakeCommand", 2000, 1000000000, 7, 1, 0x36CA,
         "D0 07 02 01 00 00 00 00 01 00 00 00 00 CA 9A 3B "
         "00 00 00 00 07 00 00 00 01 01 00 00 00 CA 36 00"),
        ("BrakeActual", 1500, 1010000000, 0, 1, 0x3D73,
         "DC 05 02 01 00 00 00 00 01 00 00 00 80 60 33 3C "
         "00 00 00 00 00 00 00 00 01 01 00 00 00 73 3D 00"),
        ("BrakeCommand", 0, 1000000000, 7, 1, 0x0D2A,
         "00 00 02 01 00 00 00 00 01 00 00 00 00 CA 9A 3B "
         "00 00 00 00 07 00 00 00 01 01 00 00 00 2A 0D 00"),
        ("BrakeActual", 65535, 1010000000, 0, 0, 0x6BB3,
         "FF FF 02 00 00 00 00 00 01 00 00 00 80 60 33 3C "
         "00 00 00 00 00 00 00 00 00 00 00 00 00 B3 6B 00"),
    ]
    for name, raw, timestamp, cause, valid, crc, text in vectors:
        message = db.get_message_by_name(name)
        expected = signals(raw, 0, timestamp, cause, crc, value_name="Pressure")
        if not valid:
            expected.update(Validity=0, LocalState=0, Origin=0)
        payload = bytes.fromhex(text)
        require(message.encode(expected, scaling=False, strict=bool(valid)) == payload,
                f"{name}/{raw}: DBC golden encode 불일치")
        require(message.decode(payload, decode_choices=False, scaling=False) == expected,
                f"{name}/{raw}: DBC golden decode 불일치")
        require(payload_crc(message.frame_id, payload) == crc, f"{name}/{raw}: 독립 CRC 불일치")
        print(f"PASS: {name}/{raw} golden bytes, CRC=0x{crc:04X}")
    message = db.get_message_by_name("BrakeActual")
    for timestamp in [2**53 + 1, 2**64 - 1]:
        values = signals(0, 0, timestamp, 0, value_name="Pressure")
        payload = message.encode(values, scaling=False, strict=True)
        require(message.decode(payload, decode_choices=False, scaling=False)["SourceTimeNs"] == timestamp,
                "Brake SourceTimeNs 정수 정밀도 손실")

def drive_extension(valid=True):
    return {
        "WheelSpeed": 1234 if valid else 65535, "WheelSpeedValid": int(valid),
        "RegenLimitReason": 2 if valid else 4, "RegenTorqueLimit": 2000 if valid else 65535,
        "RegenCapabilityValid": int(valid), "FeedbackReserved": 0,
        "WheelSpeedSourceTimeNs": 1010000000 if valid else 0,
        "CapabilitySourceTimeNs": 1010000000 if valid else 0,
        "CapabilityInputTimeNs": 1005000000 if valid else 0,
    }


def check_drive_vectors(db):
    vectors = [
        ("DriveCommand", -2000, 1000000000, 7, 0x47A1,
         "30 F8 02 01 00 00 00 00 01 00 00 00 00 CA 9A 3B "
         "00 00 00 00 07 00 00 00 01 01 00 00 00 A1 47 00"),
        ("DriveActual", -1500, 1010000000, 0, 0xE62F,
         "24 FA 02 01 00 00 00 00 01 00 00 00 80 60 33 3C "
         "00 00 00 00 00 00 00 00 01 01 00 00 00 2F E6 00 "
         "D2 04 01 02 D0 07 01 00 80 60 33 3C 00 00 00 00 "
         "80 60 33 3C 00 00 00 00 40 15 E7 3B 00 00 00 00"),
    ]
    for name, raw, timestamp, cause, crc, text in vectors:
        message = db.get_message_by_name(name)
        expected = signals(raw, 0, timestamp, cause, crc, value_name="Torque")
        if name == "DriveActual":
            expected.update(drive_extension())
        payload = bytes.fromhex(text)
        require(message.encode(expected, scaling=False, strict=True) == payload, f"{name}: golden encode")
        require(message.decode(payload, decode_choices=False, scaling=False) == expected, f"{name}: golden decode")
        require(payload_crc(message.frame_id, payload) == crc, f"{name}: independent CRC")
        print(f"PASS: {name} signed torque/feedback golden bytes, CRC=0x{crc:04X}")
    message = db.get_message_by_name("DriveActual")
    for timestamp in [2**53 + 1, 2**64 - 1]:
        values = signals(0, 0, timestamp, 0, value_name="Torque")
        values.update(drive_extension())
        for name in ("WheelSpeedSourceTimeNs", "CapabilitySourceTimeNs", "CapabilityInputTimeNs"):
            values[name] = timestamp
        payload = message.encode(values, scaling=False, strict=True)
        decoded = message.decode(payload, decode_choices=False, scaling=False)
        require(all(decoded[name] == timestamp for name in values if name.endswith("TimeNs")),
                "Drive uint64 source/input precision lost")
    print("PASS: Drive exact uint64 torque/wheel/capability/input timestamps")


def check_demo(db, demo, family="Steering"):
    brake = family == "Brake"
    drive = family == "Drive"
    cases = [("command", "2000000", 2000), ("actual", "1500000", 1500),
             ("command", "0", 0), ("actual", "invalid", 65535),
             ("command", "2000500", 2001)] if brake else [
             ("command", "0.2", 2000), ("actual", "0.15", 1500),
             ("command", "-0.2", -2000), ("actual", "invalid", -32768)]
    if drive:
        cases = [("command", "-200", -2000), ("actual", "-150", -1500),
                 ("command", "200", 2000), ("command", "0", 0), ("actual", "invalid", -32768)]
    for kind, input_value, raw in cases:
        name = family + ("Command" if kind == "command" else "Actual")
        message = db.get_message_by_name(name)
        result = subprocess.run([str(demo), "drive-frame" if drive else "brake-frame" if brake else "frame", kind, input_value], capture_output=True,
                                text=True, check=True, timeout=5)
        payload_line = re.search(r"^Payload: ([0-9A-F ]+)$", result.stdout, re.M)
        id_line = re.search(r"^ID: 0x([0-9A-F]+)$", result.stdout, re.M)
        require(payload_line and id_line, "C++ demo 출력 형식 불일치")
        payload = bytes.fromhex(payload_line[1])
        require(len(payload) == message.length and int(id_line[1], 16) == message.frame_id,
                "C++ demo ID/length 불일치")
        expected = signals(raw, 0, 1000000000 if kind == "command" else 1010000000,
                           7 if kind == "command" else 0, value_name="Torque" if drive else "Pressure" if brake else "Angle")
        if drive and kind == "actual":
            expected.update(drive_extension(input_value != "invalid"))
        if input_value == "invalid":
            expected.update(Validity=0, LocalState=0, Origin=0)
        # Invalid sentinel은 physical min/max 밖이다. 시험용으로 raw encode한다.
        draft_payload = message.encode(expected, scaling=False, strict=input_value != "invalid")
        expected["E2ECrc"] = payload_crc(message.frame_id, draft_payload)
        require(message.encode(expected, scaling=False, strict=input_value != "invalid") == payload,
                f"C++ {family} {kind} {input_value}: DBC encode 불일치")
        require(message.decode(payload, decode_choices=False, scaling=False) == expected,
                f"C++ {family} {kind} {input_value}: DBC decode 불일치")
        print(f"PASS: C++ {kind} {input_value} payload matches DBC + independent CRC")


# EV schema 1 is independent from the actuator schema 2 above.
EV_FRAMES = {
    'BmsPowerRequest': (0x183, 0x1301, 48, 20, 'RearZone', 'BmsVecu', 'RequestAction'),
    'BmsPowerStatus': (0x283, 0x1302, 64, 10, 'BmsVecu', 'RearZone', 'PowerState'),
    'BmsPowerLimits': (0x284, 0x1303, 48, 20, 'BmsVecu', 'RearZone', 'ChargePowerLimit'),
    'BmsBatteryState': (0x285, 0x1304, 64, 100, 'BmsVecu', 'RearZone', 'Soc'),
    'DriveBatteryLimits': (0x193, 0x1203, 48, 20, 'RearZone', 'DriveVecu', 'ChargePowerLimit'),
    'DrivePermission': (0x194, 0x1204, 64, 10, 'RearZone', 'DriveVecu', 'Permission'),
}
EV_GOLDENS = {
    'BmsPowerRequest': '01 00 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 9D C1 00 00 7E 5F 40 00 00 00 00 80 33 02 3B 00 00 00 00',
    'BmsPowerStatus': '03 00 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 3C 3F 00 01 01 00 07 1F 00 00 00 3C 0F 01 00 C0 7E 4E 3B 00 00 00 00 80 33 02 3B 00 00 00 00 0C 00 00 00',
    'BmsPowerLimits': 'E0 2E 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 00 9C 00 20 4E 01 00 00 00 00 00 80 33 02 3B 00 00 00 00',
    'BmsBatteryState': '70 17 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 33 2B 00 A0 0F 50 FB FA 00 01 01 80 33 02 3B 00 00 00 00 80 33 02 3B 00 00 00 00 80 33 02 3B 00 00 00 00',
    'DriveBatteryLimits': 'E0 2E 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 21 8C 00 20 4E 01 00 00 00 00 00 80 33 02 3B 00 00 00 00',
    'DrivePermission': '01 00 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 CB 73 00 0C 00 00 00 C0 7E 4E 3B 00 00 00 00 80 33 02 3B 00 00 00 00 80 E7 C6 3F 00 00 00 00 00 00 00 00',
}

EV_LIMIT_LAYOUT = {'DischargePowerLimit': (256, 16), 'DischargeLimitValid': (272, 8),
                   'ChargeLimitReason': (280, 8), 'DischargeLimitReason': (288, 8),
                   'LimitReserved': (296, 24), 'InputTimeNs': (320, 64)}
EV_EXTENSION = {
    'BmsPowerRequest': {'ExpiresAtNs': (256, 64), 'ParentSourceTimeNs': (320, 64)},
    'BmsPowerLimits': EV_LIMIT_LAYOUT,
    'DriveBatteryLimits': EV_LIMIT_LAYOUT,
    'BmsBatteryState': {'Voltage': (256, 16), 'Current': (272, 16), 'Temperature': (288, 16),
                        'ElectricalValid': (304, 8), 'TemperatureValid': (312, 8),
                        'SocSourceTimeNs': (320, 64), 'ElectricalSourceTimeNs': (384, 64),
                        'TemperatureSourceTimeNs': (448, 64)},
    'BmsPowerStatus': {'PositiveContactor': (256, 8), 'NegativeContactor': (264, 8),
                       'PrechargeContactor': (272, 8), 'ConditionBits': (280, 8),
                       'ConditionValidity': (288, 8), 'PowerReserved': (296, 24),
                       'HvBusVoltage': (320, 16), 'HvBusVoltageValid': (336, 8),
                       'BusReserved': (344, 8), 'InputTimeNs': (352, 64),
                       'AcceptedRequestSourceTimeNs': (416, 64), 'InputSequence': (480, 32)},
    'DrivePermission': {'PowerStatusSequence': (256, 32), 'PowerStatusSourceTimeNs': (288, 64),
                        'InputTimeNs': (352, 64), 'ExpiresAtNs': (416, 64),
                        'PermissionReserved': (480, 32)},
}
EV_ENUMS = {
    **CHOICES, 'RequestAction': {0: 'KeepOff', 1: 'Enable', 2: 'Shutdown'},
    'PowerState': {0: 'OFF', 1: 'CHECKS', 2: 'PRECHARGE', 3: 'HV_READY', 4: 'SHUTDOWN'},
    'Permission': {0: 'Inhibit', 1: 'AllowNormal'},
    **{key: CHOICES['Validity'] for key in ('DischargeLimitValid', 'ElectricalValid',
                                           'TemperatureValid', 'HvBusVoltageValid')},
    **{key: {0: 'Open', 1: 'Closed'} for key in ('PositiveContactor', 'NegativeContactor',
                                              'PrechargeContactor')},
    **{key: {0: 'Nominal', 1: 'SocLimited', 2: 'TemperatureLimited', 3: 'ElectricalLimited',
              4: 'Disabled', 5: 'InputsInvalid'} for key in ('ChargeLimitReason', 'DischargeLimitReason')},
}


def check_ev_database(db):
    require({item.name for item in db.messages} == set(EV_FRAMES), 'EV six-message inventory mismatch')
    for name, (can_id, data_id, length, period, sender, receiver, primary) in EV_FRAMES.items():
        message = db.get_message_by_name(name)
        layout = {primary if key == 'Angle' else key: value for key, value in LAYOUT.items()}
        layout.update(EV_EXTENSION[name])
        require(message.frame_id == can_id and message.is_fd and not message.is_extended_frame,
                f'{name}: CAN envelope mismatch')
        require((message.length, message.cycle_time, message.senders) == (length, period, [sender]),
                f'{name}: payload/period/producer mismatch')
        require({s.name: (s.start, s.length) for s in message.signals} == layout,
                f'{name}: wire layout mismatch')
        for key, expected in {'E2EProfile': 5, 'E2EDataID': data_id,
                              'E2EOffsetBits': 232, 'E2EMaxDeltaCounter': 10}.items():
            require(key in message.dbc.attributes and message.dbc.attributes[key].value == expected,
                    f'{name}: {key} mismatch')
        for field in message.signals:
            key = field.name
            scale, unit, bounds = 1, None, RANGES.get(key, (0, 1))
            if key == 'SchemaVersion': bounds = (1, 1)
            if key.endswith('Reserved'): bounds = (None, None)
            if key.endswith('TimeNs') or key.endswith('AtNs'):
                unit, bounds = 'ns', (0, 2**64-1)
            if key.endswith('Sequence'): bounds = (0, 2**32-1)
            if key in ('ChargePowerLimit', 'DischargePowerLimit'): scale, unit, bounds = 10, 'W', (0, 655340)
            if key in ('Voltage', 'HvBusVoltage'): scale, unit, bounds = 0.1, 'V', (0, 6553.4)
            if key in ('Current', 'Temperature'):
                scale, unit, bounds = 0.1, 'A' if key == 'Current' else 'degC', (-3276.7, 3276.7)
            if key == 'Soc': scale, unit, bounds = 0.0001, 'fraction', (0, 1)
            if key in ('RequestAction', 'PowerState'): bounds = (0, 2 if key == 'RequestAction' else 4)
            if key in ('ChargeLimitReason', 'DischargeLimitReason'): bounds = (0, 5)
            if key in ('ConditionBits', 'ConditionValidity'): bounds = (0, 31)
            require(field.byte_order == 'little_endian' and field.receivers == [receiver],
                    f'{name}.{key}: endian/consumer mismatch')
            require(field.is_signed == (key in ('Current', 'Temperature')) and field.offset == 0,
                    f'{name}.{key}: signed/offset mismatch')
            require((field.scale, field.unit, field.minimum, field.maximum) == (scale, unit, *bounds),
                    f'{name}.{key}: scaling/unit/range mismatch')
            choices = {value: str(label) for value, label in (field.choices or {}).items()}
            require(choices == EV_ENUMS.get(key, {}), f'{name}.{key}: enum mismatch')
        print(f'PASS: {name} id=0x{can_id:03X}, EV schema 1, {length} bytes/{period} ms, P05')


def ev_fixture(name):
    _, _, _, _, _, _, primary = EV_FRAMES[name]
    values = {primary: 0, 'SchemaVersion': 1, 'Validity': 1, 'Sequence': 0, 'Epoch': 1,
              'SourceTimeNs': 1000000000, 'CausalSequence': 7, 'LocalState': 1, 'Origin': 1,
              'Reserved': 0, 'E2ECrc': 0, 'E2ECounter': 0}
    values.update({key: 0 for key in EV_EXTENSION[name]})
    if primary == 'ChargePowerLimit':
        values.update(ChargePowerLimit=12000, DischargePowerLimit=20000,
                      DischargeLimitValid=1, InputTimeNs=990000000)
    elif name == 'BmsPowerRequest':
        values.update(RequestAction=1, ExpiresAtNs=1080000000, ParentSourceTimeNs=990000000)
    elif name == 'BmsBatteryState':
        values.update(Soc=6000, Voltage=4000, Current=-1200, Temperature=250,
                      ElectricalValid=1, TemperatureValid=1, SocSourceTimeNs=990000000,
                      ElectricalSourceTimeNs=990000000, TemperatureSourceTimeNs=990000000)
    elif name == 'BmsPowerStatus':
        values.update(PowerState=3, PositiveContactor=1, NegativeContactor=1, PrechargeContactor=0,
                      ConditionBits=7, ConditionValidity=31, HvBusVoltage=3900,
                      HvBusVoltageValid=1, InputTimeNs=995000000,
                      AcceptedRequestSourceTimeNs=990000000, InputSequence=12)
    else:
        values.update(Permission=1, PowerStatusSequence=12, PowerStatusSourceTimeNs=995000000,
                      InputTimeNs=990000000, ExpiresAtNs=1070000000)
    return values


def validate_ev_raw(name, values):
    # Offline canonical vectors only. This is not the future stateful receiver/gate.
    require(values['SchemaVersion'] == 1 and values['Epoch'] != 0, 'schema/epoch invalid')
    for key, value in values.items():
        if key.endswith('Reserved'): require(value == 0, f'{key} must be zero')
    for key in ('Validity', 'LocalState', 'Origin', 'DischargeLimitValid', 'ElectricalValid',
                'TemperatureValid', 'HvBusVoltageValid', 'ChargeLimitReason', 'DischargeLimitReason'):
        if key in values: require(values[key] in EV_ENUMS[key], f'{key} enum invalid')
    source = values['SourceTimeNs']

    def sample(flag, fields, timestamp):
        valid = values[flag]
        for key, sentinel, maximum, minimum in fields:
            value = values[key]
            require((minimum <= value <= maximum) if valid else value == sentinel,
                    f'{key}: valid range/invalid sentinel mismatch')
        require(0 <= values[timestamp] <= source if valid else values[timestamp] == 0,
                f'{timestamp}: source order/invalid timestamp mismatch')

    if name == 'BmsBatteryState':
        sample('Validity', [('Soc', 65535, 10000, 0)], 'SocSourceTimeNs')
        sample('ElectricalValid', [('Voltage', 65535, 65534, 0), ('Current', -32768, 32767, -32767)],
               'ElectricalSourceTimeNs')
        sample('TemperatureValid', [('Temperature', -32768, 32767, -32767)], 'TemperatureSourceTimeNs')
    elif name in ('BmsPowerLimits', 'DriveBatteryLimits'):
        for field, flag, reason in [('ChargePowerLimit', 'Validity', 'ChargeLimitReason'),
                                    ('DischargePowerLimit', 'DischargeLimitValid', 'DischargeLimitReason')]:
            if values[flag]:
                require(0 <= values[field] <= 65534 and values[reason] != 5, 'valid limit invalid')
                require(values[reason] != 4 or values[field] == 0, 'Disabled limit must be zero')
            else:
                require(values[field] == 65535 and values[reason] == 5, 'invalid limit must be canonical')
        require(0 <= values['InputTimeNs'] <= source if values['Validity'] or values['DischargeLimitValid']
                else values['InputTimeNs'] == 0, 'limit input timestamp invalid')
    elif name in ('BmsPowerRequest', 'DrivePermission'):
        primary = EV_FRAMES[name][-1]
        require(values[primary] in EV_ENUMS[primary] if values['Validity'] else values[primary] == 65535,
                'primary enum/sentinel invalid')
        if values['Validity']:
            require(source < values['ExpiresAtNs'] <= min(2**64-1, source+80000000), 'expiry invalid')
            if name == 'BmsPowerRequest':
                require(values['ParentSourceTimeNs'] <= source, 'parent time invalid')
                if values['Origin'] == 0:
                    require(values['RequestAction'] == 0 and values['CausalSequence'] == 0 and
                            values['ParentSourceTimeNs'] == 0, 'NoAcceptedInput only allows KeepOff')
                if values['Origin'] == 2: require(values['RequestAction'] != 1, 'protection cannot Enable')
            else:
                require(0 <= values['InputTimeNs'] <= values['PowerStatusSourceTimeNs'] <= source,
                        'permission input/source order invalid')
                if values['Permission'] == 1:
                    require(values['Origin'] == 1 and values['LocalState'] in (1, 2),
                            'normal permission mode invalid')
        else:
            require(all(value == 0 for key, value in values.items() if key in EV_EXTENSION[name]),
                    'invalid request/permission extension must be zero')
    else:
        require(values['PowerState'] in EV_ENUMS['PowerState'] if values['Validity'] else
                values['PowerState'] == 65535, 'power state invalid')
        contacts = ('PositiveContactor', 'NegativeContactor', 'PrechargeContactor')
        require(all(values[key] in (0, 1, 255) for key in contacts), 'contactor enum invalid')
        bits, valid = values['ConditionBits'], values['ConditionValidity']
        require(0 <= bits <= 31 and 0 <= valid <= 31 and bits & ~valid == 0, 'condition mask invalid')
        require(0 <= values['HvBusVoltage'] <= 65534 if values['HvBusVoltageValid'] else
                values['HvBusVoltage'] == 65535, 'bus voltage invalid')
        any_actual = values['Validity'] or valid or values['HvBusVoltageValid'] or any(values[k] != 255 for k in contacts)
        require(0 <= values['InputTimeNs'] <= source if any_actual else values['InputTimeNs'] == 0,
                'power input time invalid')
        if not any_actual: require(values['InputSequence'] == 0, 'unknown power input identity must be zero')
        require(values['AcceptedRequestSourceTimeNs'] <= source, 'accepted request time invalid')
        if values['Origin'] == 0:
            require(values['CausalSequence'] == 0 and values['AcceptedRequestSourceTimeNs'] == 0,
                    'NoAcceptedInput correlation must be zero')


def ev_encode(message, values):
    validate_ev_raw(message.name, values)
    values = dict(values)
    values['E2ECrc'] = 0
    payload = message.encode(values, scaling=False, strict=False)
    values['E2ECrc'] = payload_crc(message.frame_id, payload)
    return message.encode(values, scaling=False, strict=False)


def check_ev_vectors(db):
    for name in EV_FRAMES:
        message = db.get_message_by_name(name)
        values = ev_fixture(name)
        payload = ev_encode(message, values)
        decoded = message.decode(payload, decode_choices=False, scaling=False)
        validate_ev_raw(name, decoded)
        require({k: v for k, v in decoded.items() if k != 'E2ECrc'} ==
                {k: v for k, v in values.items() if k != 'E2ECrc'}, f'{name}: raw roundtrip mismatch')
        require(payload == bytes.fromhex(EV_GOLDENS[name]), f'{name}: golden bytes mismatch')
        for timestamp in (2**53+1, 2**64-1):
            precise = dict(values)
            for key in precise:
                if key.endswith('TimeNs') or key.endswith('AtNs'): precise[key] = timestamp
            if name in ('BmsPowerRequest', 'DrivePermission'):
                precise['SourceTimeNs'] = timestamp-1
                for key in precise:
                    if key.endswith('TimeNs') and key != 'SourceTimeNs': precise[key] = timestamp-1
            raw = ev_encode(message, precise)
            result = message.decode(raw, decode_choices=False, scaling=False)
            require(all(result[k] == precise[k] for k in precise if k.endswith('Ns')),
                    f'{name}: uint64 precision lost')
        for byte in range(message.length):
            corrupt = bytearray(payload)
            corrupt[byte] ^= 1
            stored = int.from_bytes(corrupt[29:31], 'little')
            require(payload_crc(message.frame_id, corrupt) != stored, f'{name}: unprotected byte {byte}')
        print(f'PASS: {name} golden/raw roundtrip, uint64 precision and all-byte CRC corruption')

    original = db.get_message_by_name('BmsPowerLimits')
    forwarded = db.get_message_by_name('DriveBatteryLimits')
    values = ev_fixture('BmsPowerLimits')
    upstream, downstream = ev_encode(original, values), ev_encode(forwarded, values)
    require(upstream[:29]+upstream[32:] == downstream[:29]+downstream[32:], 'forwarding rewrites source')
    require(upstream[29:31] != downstream[29:31], 'different DataID must change CRC')
    independent_counter = ev_encode(forwarded, {**values, 'E2ECounter': 17})
    require(independent_counter[31] == 17 and upstream[31] == 0, 'transport counters not independent')
    require(upstream[:29]+upstream[32:] == independent_counter[:29]+independent_counter[32:],
            'independent transport counter rewrites source identity')

    mutations = []
    for name in EV_FRAMES:
        mutations.extend((name, patch) for patch in ({'SchemaVersion': 2}, {'Epoch': 0},
                                                    {'Reserved': 1}, {'Validity': 2}, {'Origin': 3}))
    mutations.extend([
        ('BmsBatteryState', {'Soc': 10001}), ('BmsBatteryState', {'ElectricalValid': 0}),
        ('BmsBatteryState', {'TemperatureSourceTimeNs': 1000000001}),
        ('BmsPowerLimits', {'Validity': 0}), ('BmsPowerLimits', {'ChargeLimitReason': 4}),
        ('BmsPowerLimits', {'InputTimeNs': 1000000001}),
        ('DriveBatteryLimits', {'DischargePowerLimit': 65535}),
        ('BmsPowerRequest', {'RequestAction': 3}), ('BmsPowerRequest', {'ExpiresAtNs': 1000000000}),
        ('BmsPowerRequest', {'ExpiresAtNs': 1080000001}),
        ('BmsPowerRequest', {'ParentSourceTimeNs': 1000000001}),
        ('BmsPowerRequest', {'Origin': 2}),
        ('DrivePermission', {'Permission': 2}), ('DrivePermission', {'LocalState': 0}),
        ('DrivePermission', {'PowerStatusSourceTimeNs': 1000000001}),
        ('BmsPowerStatus', {'PowerState': 5}), ('BmsPowerStatus', {'PositiveContactor': 2}),
        ('BmsPowerStatus', {'ConditionBits': 32}), ('BmsPowerStatus', {'ConditionValidity': 0}),
        ('BmsPowerStatus', {'InputTimeNs': 1000000001}),
        ('BmsPowerStatus', {'PowerState': 65535, 'Validity': 0, 'PositiveContactor': 255,
                            'NegativeContactor': 255, 'PrechargeContactor': 255,
                            'ConditionBits': 0, 'ConditionValidity': 0, 'HvBusVoltage': 65535,
                            'HvBusVoltageValid': 0, 'InputTimeNs': 0}),
    ])
    for name, patch in mutations:
        values = {**ev_fixture(name), **patch}
        try:
            validate_ev_raw(name, values)
        except ValueError:
            continue
        raise ValueError(f'{name}: accepted malformed canonical vector {patch}')

    # Valid zero and unknown are different wire values, independently for each limit.
    for name in ('BmsPowerLimits', 'DriveBatteryLimits'):
        values = ev_fixture(name)
        for update in ({'ChargePowerLimit': 0, 'ChargeLimitReason': 4},
                       {'ChargePowerLimit': 65535, 'Validity': 0, 'ChargeLimitReason': 5},
                       {'DischargePowerLimit': 65535, 'DischargeLimitValid': 0, 'DischargeLimitReason': 5},
                       {'ChargePowerLimit': 65535, 'Validity': 0, 'ChargeLimitReason': 5,
                        'DischargePowerLimit': 65535, 'DischargeLimitValid': 0,
                        'DischargeLimitReason': 5, 'InputTimeNs': 0}):
            raw = ev_encode(db.get_message_by_name(name), {**values, **update})
            validate_ev_raw(name, db.get_message_by_name(name).decode(raw, decode_choices=False, scaling=False))
    accepted_vectors = [
        ('BmsBatteryState', {'Soc': 0}),
        ('BmsBatteryState', {'Soc': 65535, 'Validity': 0, 'SocSourceTimeNs': 0}),
        ('BmsBatteryState', {'Voltage': 65535, 'Current': -32768, 'ElectricalValid': 0,
                             'ElectricalSourceTimeNs': 0}),
        ('BmsBatteryState', {'Temperature': -32768, 'TemperatureValid': 0,
                             'TemperatureSourceTimeNs': 0}),
        ('BmsPowerStatus', {'PowerState': 65535, 'Validity': 0, 'PositiveContactor': 255,
                            'NegativeContactor': 255, 'PrechargeContactor': 255, 'ConditionBits': 0,
                            'ConditionValidity': 0, 'HvBusVoltage': 65535, 'HvBusVoltageValid': 0,
                            'InputTimeNs': 0, 'InputSequence': 0, 'AcceptedRequestSourceTimeNs': 0,
                            'Origin': 0, 'LocalState': 0, 'CausalSequence': 0}),
        ('BmsPowerRequest', {'RequestAction': 0, 'Origin': 0, 'LocalState': 0,
                             'CausalSequence': 0, 'ParentSourceTimeNs': 0}),
        ('BmsPowerRequest', {'RequestAction': 65535, 'Validity': 0,
                             'ExpiresAtNs': 0, 'ParentSourceTimeNs': 0}),
        ('DrivePermission', {'Permission': 0, 'Origin': 2, 'LocalState': 0,
                             'PowerStatusSequence': 0, 'PowerStatusSourceTimeNs': 0, 'InputTimeNs': 0}),
        ('DrivePermission', {'Permission': 65535, 'Validity': 0, 'PowerStatusSequence': 0,
                             'PowerStatusSourceTimeNs': 0, 'InputTimeNs': 0, 'ExpiresAtNs': 0}),
    ]
    for name, patch in accepted_vectors:
        message = db.get_message_by_name(name)
        raw = ev_encode(message, {**ev_fixture(name), **patch})
        validate_ev_raw(name, message.decode(raw, decode_choices=False, scaling=False))
    print(f'PASS: EV source-preserving forwarding, valid-zero/unknown and {len(mutations)} canonical rejection vectors')



def check_ev_demo(db, demo):
    commands = {'BmsPowerRequest': 'request', 'BmsPowerStatus': 'power-status',
                'BmsPowerLimits': 'limits', 'BmsBatteryState': 'battery',
                'DriveBatteryLimits': 'drive-limits', 'DrivePermission': 'permission'}
    for name, command in commands.items():
        variants = ['nominal', 'zero', 'invalid']
        if name in ('BmsPowerLimits', 'DriveBatteryLimits', 'BmsBatteryState', 'BmsPowerStatus'):
            variants.append('partial')
        for variant in variants:
            message = db.get_message_by_name(name)
            values = ev_fixture(name)
            if variant == 'invalid':
                primary = EV_FRAMES[name][-1]
                values.update({key: 0 for key in EV_EXTENSION[name]})
                values.update({primary: 65535, 'Validity': 0, 'LocalState': 0, 'Origin': 0, 'CausalSequence': 0})
                if name in ('BmsPowerLimits', 'DriveBatteryLimits'):
                    values.update(DischargePowerLimit=65535, ChargeLimitReason=5, DischargeLimitReason=5)
                elif name == 'BmsBatteryState':
                    values.update(Voltage=65535, Current=-32768, Temperature=-32768)
                elif name == 'BmsPowerStatus':
                    values.update(PositiveContactor=255, NegativeContactor=255, PrechargeContactor=255, HvBusVoltage=65535)
            elif variant == 'zero':
                if name in ('BmsPowerLimits', 'DriveBatteryLimits'):
                    values.update(ChargePowerLimit=0, DischargePowerLimit=0, ChargeLimitReason=4, DischargeLimitReason=4)
                elif name == 'BmsBatteryState': values.update(Soc=0, Voltage=0, Current=0, Temperature=0)
                elif name == 'BmsPowerStatus': values.update(PowerState=0, PositiveContactor=0, NegativeContactor=0, HvBusVoltage=0)
                elif name == 'BmsPowerRequest': values['RequestAction'] = 0
                else: values['Permission'] = 0
            elif variant == 'partial':
                if name in ('BmsPowerLimits', 'DriveBatteryLimits'):
                    values.update(ChargePowerLimit=65535, Validity=0, ChargeLimitReason=5)
                elif name == 'BmsBatteryState':
                    values.update(Temperature=-32768, TemperatureValid=0, TemperatureSourceTimeNs=0)
                else: values['ConditionValidity'] = 15
            result = subprocess.run([str(demo), 'bms-frame', command, variant], capture_output=True,
                                    text=True, check=True, timeout=5)
            payload_line = re.search(r'^Payload: ([0-9A-F ]+)$', result.stdout, re.M)
            id_line = re.search(r'^ID: 0x([0-9A-F]+)$', result.stdout, re.M)
            require(payload_line and id_line, 'C++ EV fixture output mismatch')
            payload = bytes.fromhex(payload_line[1])
            require(int(id_line[1], 16) == message.frame_id and payload == ev_encode(message, values),
                    f'C++ {name}/{variant}: DBC/raw/canonical/independent CRC mismatch')
            print(f'PASS: C++ {name}/{variant} matches DBC + independent CRC')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbc", type=Path, default=ROOT / "interfaces/dbc/steering_m1_draft.dbc")
    parser.add_argument("--brake-dbc", type=Path, default=ROOT / "interfaces/dbc/brake_m1_draft.dbc")
    parser.add_argument("--drive-dbc", type=Path, default=ROOT / "interfaces/dbc/drive_m1_draft.dbc")
    parser.add_argument("--demo", type=Path, help="C++ actuator_demo 경로; actuator/EV frame 명령으로 검사 (선택)")
    parser.add_argument("--ev-dbc", type=Path, default=ROOT / "interfaces/dbc/bms_m1_draft.dbc")
    args = parser.parse_args()
    try:
        db = cantools.database.load_file(args.dbc, strict=True)
        check_database(db)
        check_vectors(db)
        brake_db = cantools.database.load_file(args.brake_dbc, strict=True)
        check_database(brake_db, "Brake")
        check_brake_vectors(brake_db)
        drive_db = cantools.database.load_file(args.drive_dbc, strict=True)
        check_database(drive_db, "Drive")
        check_drive_vectors(drive_db)
        ev_db = cantools.database.load_file(args.ev_dbc, strict=True)
        check_ev_database(ev_db)
        check_ev_vectors(ev_db)
        messages = db.messages + brake_db.messages + drive_db.messages + ev_db.messages
        require(len({m.frame_id for m in messages}) == len(messages), "CAN ID collision")
        require(len({m.name for m in messages}) == len(messages), "message name collision")
        require(len({m.dbc.attributes['E2EDataID'].value for m in messages}) == len(messages),
                "P05 DataID collision")
        if args.demo:
            check_demo(db, args.demo.resolve())
            check_demo(brake_db, args.demo.resolve(), "Brake")
            check_demo(drive_db, args.demo.resolve(), "Drive")
            check_ev_demo(ev_db, args.demo.resolve())
    except (OSError, ValueError, cantools.errors.Error, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: 12-frame Host DBC/codec checks (stateful receiver/transport/vehicle evidence is separate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
