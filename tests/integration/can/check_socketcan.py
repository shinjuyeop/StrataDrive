#!/usr/bin/env python3
"""독립 C++ TX/RX process를 임시 vCAN에 연결하는 유한 시간 integration fixture."""

import argparse
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time


INTERFACE = "sd_m1_app"
EV_STREAMS = {
    "bms-request": (0x183, 48, 20), "bms-power": (0x283, 64, 10),
    "bms-limits": (0x284, 48, 20), "bms-battery": (0x285, 64, 100),
    "drive-limits": (0x193, 48, 20), "drive-permission": (0x194, 64, 10),
}
EV_EXTRA = [
    ("bms-limits", "partial"), ("drive-limits", "partial"),
    ("bms-limits", "cached"), ("drive-limits", "cached"), ("bms-power", "cached"),
    ("bms-battery", "observation"), ("bms-request", "expiry"), ("drive-permission", "expiry"),
    ("bms-request", "parent"), ("drive-permission", "parent"),
    ("drive-permission", "rejoin"), ("drive-limits", "forward"),
]
FAULT_DECISIONS = [
    "ACCEPTED", "E2E_REJECTED", "E2E_REJECTED", "SOURCE_STALE", "ACCEPTED",
    "MALFORMED_ENVELOPE", "MALFORMED_ENVELOPE", "MALFORMED_ENVELOPE",
    "MALFORMED_ENVELOPE", "MALFORMED_ENVELOPE", "SEQUENCE_REJECTED", "TIMEOUT",
]
BRAKE_FAULT_DECISIONS = (
    FAULT_DECISIONS[:5] + ["ACCEPTED"] + FAULT_DECISIONS[5:-1]
    + ["PRESSURE_OUT_OF_RANGE", "UNAVAILABLE", "MODE_REJECTED", "EPOCH_MISMATCH", "TIMEOUT"]
)
DRIVE_FAULT_DECISIONS = [
    "TORQUE_OUT_OF_RANGE" if item == "PRESSURE_OUT_OF_RANGE" else item
    for item in BRAKE_FAULT_DECISIONS
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def ready(process, expected):
    """stdio handshake만 기다린다. 수신 payload에서 Epoch/start time을 학습하지 않는다."""
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        require(selector.select(5), f"handshake timeout: {expected}")
        line = process.stdout.readline().decode().strip()
        require(line.startswith(expected), f"expected {expected}, received {line!r}")
        return line


def start(process):
    process.stdin.write(b"start\n")
    process.stdin.close()


def collect(processes, output):
    """TX/RX stdout와 stderr를 함께 비워 로그 pipe 때문에 RX가 막히지 않게 한다."""
    with selectors.DefaultSelector() as selector:
        for name, process in processes.items():
            selector.register(process.stdout, selectors.EVENT_READ, name)
            selector.register(process.stderr, selectors.EVENT_READ, name + "_err")
        deadline = time.monotonic() + 5
        while selector.get_map():
            require(time.monotonic() < deadline, "application process deadline exceeded")
            for key, _ in selector.select(0.05):
                chunk = os.read(key.fd, 65536)
                if chunk:
                    output[key.data].extend(chunk)
                    require(len(output[key.data]) < 2_000_000, "fixture output exceeded limit")
                else:
                    selector.unregister(key.fileobj)
        for name, process in processes.items():
            code = process.wait(timeout=1)
            require(code == 0, f"{name} exit {code}: {output[name + '_err'].decode()}")


def fields(line):
    return dict(part.split("=", 1) for part in line.split()[1:])


def verify_brake(kind, session, output):
    lines = output["rx"].splitlines()
    events = [fields(line) for line in lines if line.startswith("BRAKE ")]
    expected = ["WIRE_VALID", "E2E_REJECTED", "E2E_REJECTED", "WIRE_VALID",
                "WIRE_UNAVAILABLE", "WIRE_REJECTED", "WIRE_VALID", "WIRE_REJECTED"]
    require([item["decision"] for item in events] == expected, "Brake wire decisions mismatch")
    require([int(item["e2e"]) for item in events] == [0, 8, 7, 32, 0, -1, 0, -1],
            "Brake E2E status mismatch")
    actual = kind == "brake-actual"
    pressure = 1500000 if actual else 2000000
    require(all(int(item["id"]) == (0x281 if actual else 0x181) for item in events),
            "Brake CAN ID changed during transport")
    wire_events = [events[index] for index in (0, 3, 4, 6)]
    require([float(item["pressure_pa"]) for item in wire_events] == [pressure, 0, 0, pressure],
            "Brake pressure transport mismatch")
    require([item["valid"] for item in wire_events] == ["1", "1", "0", "1"],
            "Brake zero and unavailable were confused")
    require([int(item["seq"]) for item in wire_events] == [0, 2, 3, 4], "Brake sequence mismatch")
    require(all(item["epoch"] == fields(session)["epoch"] for item in wire_events), "Brake Epoch transport mismatch")
    timestamps = [int(item["source_ns"]) for item in wire_events]
    require(timestamps == sorted(set(timestamps)) and timestamps[0] >= int(fields(session)["enable_ns"]),
            "Brake source timestamp transport mismatch")
    require(lines[-1].startswith("END ") and fields(lines[-1]) == {"decoded": "4", "rejected": "4"},
            "Brake wire result count mismatch")
    require("TX wire_frames=8" in output["tx"], "Brake TX did not finish sending")


def verify(kind, scenario, session, output):
    if scenario in ("app-overflow", "kernel-overflow"):
        return verify_overflow(kind, scenario, session, output)
    if scenario == "restart":
        return verify_restart(kind, session, output)
    if kind in EV_STREAMS:
        return verify_ev(kind, scenario, session, output)
    if scenario == "wire":
        verify_brake(kind, session, output)
        return None
    lines = output["rx"].splitlines()
    events = [fields(line) for line in lines if line.startswith("RX ")]
    timeout = [fields(line) for line in lines if line.startswith("TIMEOUT ")]
    require(len(timeout) == 1, "timeout must be reported once")
    elapsed = int(timeout[0]["elapsed_ns"])
    require(80_000_000 <= elapsed <= 100_000_000, f"observed timeout outside 80..100 ms: {elapsed}")
    require(timeout[0]["usable"] == "0", "sample remained usable after timeout")
    end = fields(lines[-1])
    require(lines[-1].startswith("END ") and end["timeout"] == "1" and end["usable"] == "0",
            "receiver did not finish with latched timeout and no current sample")
    decisions = [event["decision"] for event in events]
    if scenario == "normal":
        require(decisions == ["ACCEPTED"] * 5, f"normal RX: {decisions}")
    elif scenario == "faults":
        expected = (DRIVE_FAULT_DECISIONS if kind.startswith("drive-") else
                    BRAKE_FAULT_DECISIONS if kind.startswith("brake-") else FAULT_DECISIONS)
        require(decisions == expected, f"fault RX: {decisions}")
        require(events[1]["e2e"] == "8" and events[2]["e2e"] == "7", "repeat/CRC status mismatch")
        require(events[3]["e2e"] in ("0", "32"), "stale fixture did not pass E2E")
        cached = next(event for event in events if event["decision"] == "SEQUENCE_REJECTED")
        require(cached["e2e"] in ("0", "32"), "cached sequence did not pass E2E")
        require(events[-1]["e2e"] == "-1", "late RX ran E2E after timeout latch")
    elif scenario == "feedback":
        require(kind == "drive-actual", "feedback fixture must use Drive Actual")
        require(decisions == ["ACCEPTED"] * 6 + ["UNAVAILABLE"], f"Drive feedback RX: {decisions}")
        require([item["regen_valid"] for item in events[:6]] == ["1", "1", "0", "0", "0", "1"],
                "cached/invalid capability became usable or valid zero was lost")
        require([float(item["regen_limit_nm"]) for item in (events[0], events[1], events[5])] == [200, 0, 200],
                "Drive capability value transport mismatch")
        require(all(item["speed_valid"] == "1" for item in events[:6]), "fresh speed feedback lost")
        require(all(int(item["payload_length"]) == 64 for item in events), "Drive Actual was truncated")
        require(all(int(item["at_ns"]) - int(item["cap_input_ns"]) <= 30_000_000
                    for item in events[:6] if item["regen_valid"] == "1"), "stale dependency remained usable")
    elif scenario == "flood":
        require(len(events) == 769 and decisions[0] == "ACCEPTED", "flood frame count mismatch")
        require(all(decision in ("E2E_REJECTED", "TIMEOUT") for decision in decisions[1:]),
                "flood renewed validity")
        require("TIMEOUT" in decisions, "no frames arrived after timeout during flood")
    else:
        require(not events, "silent source produced frames")
        require(int(timeout[0]["reference_ns"]) == int(fields(session)["enable_ns"]),
                "first-frame timeout did not start at trusted enable time")

    history = None
    pressure = kind.startswith("brake-")
    drive = kind.startswith("drive-")
    value_field = "history_torque_nm" if drive else "history_pressure_pa" if pressure else "history_angle_rad"
    expected_value = ((-200 if kind == "drive-cmd" else -150) if drive else
                      (2000000 if kind == "brake-cmd" else 1500000) if pressure else
                      (0.2 if kind == "cmd" else 0.15))
    for event in events:
        current = tuple(event[key] for key in ("last_valid_ns", "last_source_ns", "last_seq", value_field))
        if event["decision"] == "ACCEPTED":
            require(event["at_ns"] == event["last_valid_ns"], "accepted RX time mismatch")
            age = int(event["at_ns"]) - int(event["last_source_ns"])
            require(0 <= age <= 30_000_000, "accepted an old/future sample")
            wanted = 0 if (pressure or drive) and scenario == "faults" and event["last_seq"] == "2" else expected_value
            require(math.isclose(float(event[value_field]), wanted), "decoded actuator value mismatch")
            history = current
        else:
            require(current == history, "rejected frame changed accepted history")
    require(int(end["accepted"]) == decisions.count("ACCEPTED"), "accepted count mismatch")
    require(int(end["rejected"]) == len(events) - decisions.count("ACCEPTED"), "rejected count mismatch")
    if history:
        require(int(timeout[0]["reference_ns"]) == int(history[0]), "timeout used raw RX time")
        expired = [fields(line) for line in lines if line.startswith("SOURCE_EXPIRED ")]
        require(expired, "current_sample age expiry was not observed")
        require(all(int(event["at_ns"]) - int(event["source_ns"]) > 30_000_000 for event in expired),
                "sample expired before source-age boundary")
    return elapsed / 1_000_000


def ev_start_plan(kind, scenario, epoch):
    """Trusted fixture inputs come from the harness, never from CAN RX."""
    anchor = time.monotonic_ns() + 20_000_000
    rejoin = anchor + 180_000_000 if scenario == "rejoin" else 0
    parents = []
    if kind in ("bms-request", "drive-permission"):
        if scenario == "normal":
            period = EV_STREAMS[kind][2]
            parents = [(1, 7+i, i*period, i*period+60) for i in range(5)]
        elif scenario == "faults":
            parents = [(1, 7, 0, 60), (1, 8, 65, 125), (1, 9, 220, 280)]
        elif scenario == "expiry":
            parents = [(1, 7, 0, 35), (1, 9, 130, 190)]
        elif scenario == "parent":
            parents = [(1, 7, 0, 60), (1, 8, 30, 90), (1, 9, 200, 260)]
        elif scenario == "rejoin":
            parents = [(1, 7, 0, 60), (1, 8, 100, 160), (2, 7, 200, 260), (2, 8, 220, 280)]
        elif scenario == "restart":
            parents = [(1, 7, 0, 60), (1, 8, 50, 110), (1, 9, 190, 250)]
        elif scenario in ("app-overflow", "kernel-overflow"):
            parents = [(1, 7, 0, 60), (1, 8, 50, 110), (1, 9, 70, 130)]
        else:
            parents = [(1, 7, 0, 60)]
    items = ["start", str(anchor), str(rejoin), str(len(parents))]
    for parent_epoch, sequence, source_ms, expiry_ms in parents:
        items += [str(epoch + parent_epoch - 1), str(sequence), str(anchor + source_ms*1_000_000), str(anchor + expiry_ms*1_000_000)]
    return (" ".join(items) + "\n").encode()


def verify_ev(kind, scenario, session, output):
    lines = output["rx"].splitlines()
    events = [fields(line) for line in lines if line.startswith("EV_RX ")]
    views = [fields(line) for line in lines if line.startswith("EV_VIEW ")]
    timeout = [fields(line) for line in lines if line.startswith("EV_TIMEOUT ")]
    tx = [fields(line) for line in output["tx"].splitlines() if line.startswith("EV_TX ")]
    anchor = int(fields(session)["enable_ns"])
    epoch = int(fields(session)["epoch"])
    observation = kind == "bms-battery"
    lower = 300_000_000 if observation else 80_000_000
    require(len(timeout) == (2 if scenario == "rejoin" else 1), "EV timeout/latch count mismatch")
    for item in timeout:
        elapsed = int(item["elapsed_ns"])
        require(lower <= elapsed <= lower + 20_000_000, f"EV timeout outside monitor budget: {elapsed}")
        require(item["usable"] == "0", "EV remained usable after timeout")
    require(lines[-1].startswith("EV_END ") and fields(lines[-1])["timeout"] == "1", "EV timeout not latched at end")
    decisions = [item["decision"] for item in events]
    if scenario in ("normal", "forward"):
        require(decisions == ["ACCEPTED"]*5, f"EV normal RX: {decisions}")
        require(all(item["rx_q0"] == "USABLE" for item in events), "EV normal primary unusable")
        if kind in ("bms-power", "bms-limits", "drive-limits", "bms-battery"):
            require(all(item["rx_q1"] == "USABLE" for item in events), "EV normal dependency unusable")
        if observation:
            require(all(item["rx_q2"] == "USABLE" for item in events), "EV temperature unusable")
            require(all(float(item["soc"]) == 0.75 and float(item["voltage_v"]) == 400 and
                        float(item["current_a"]) == -12.3 and float(item["temperature_c"]) == 25
                        for item in events), "EV physical observations changed in transport")
        if kind == "bms-power": require(all(item["ready"] == "1" for item in events), "EV physical readiness lost")
        if kind in ("bms-request", "drive-permission"):
            require(all(item["allow"] == "1" for item in events), "fresh independently authorized request/grant unusable")
        if kind == "bms-request":
            require(all(item["local_state"] == "0" for item in events), "non-driving power Enable could not use INIT")
    elif scenario == "faults":
        expected = (["ACCEPTED", "E2E_REJECTED", "E2E_REJECTED"] + ["MALFORMED_ENVELOPE"]*5
                    + ["EPOCH_MISMATCH", "SOURCE_STALE", "ACCEPTED", "SEQUENCE_REJECTED",
                       "MALFORMED_PAYLOAD", "ACCEPTED", "TIMEOUT"])
        require(decisions == expected, f"EV fault RX: {decisions}")
        require(events[1]["e2e"] == "8" and events[2]["e2e"] == "7", "EV repeat/extension CRC not rejected")
        require(events[-2]["rx_q0"] == "UNAVAILABLE", "EV unknown interpreted as valid zero")
        require(events[-1]["e2e"] == "-1", "late EV frame ran E2E after latch")
    elif scenario == "silent":
        require(not events and int(timeout[0]["reference_ns"]) == anchor, "EV startup timeout origin changed")
    elif scenario == "flood":
        count = 2177 if observation else 769
        require(len(events) == count and decisions[0] == "ACCEPTED", "EV flood count mismatch")
        require(all(item in ("E2E_REJECTED", "TIMEOUT") for item in decisions[1:]), "EV flood renewed health")
        require("TIMEOUT" in decisions, "EV flood did not reach latched timeout")
    elif scenario == "partial":
        require(decisions == ["ACCEPTED"]*5 + ["TIMEOUT"], f"EV partial RX: {decisions}")
        require(events[1]["q0"] == "USABLE" and events[1]["charge_w"] == "0", "EV valid zero lost")
        require(all(item["q0"] == "UNAVAILABLE" and item["q1"] == "USABLE" for item in events[2:5]),
                "partial charge loss normalized or fresh discharge lost")
        require(int(timeout[0]["reference_ns"]) == int(events[1]["at_ns"]), "other limit refreshed missing charge age")
    elif scenario == "cached":
        expected = ["ACCEPTED"]*4 + ["TIMEOUT"]*2 if kind == "bms-power" else ["ACCEPTED"]*6
        require(decisions == expected, f"EV cached input RX: {decisions}")
        if kind == "bms-power":
            require(int(timeout[0]["reference_ns"]) == int(events[0]["at_ns"]), "cached power input refreshed physical RX")
        else:
            require(all(item["rx_q0"] == "STALE" and item["rx_q1"] == "STALE" for item in events[4:]),
                    "new calculation concealed old dependency")
            require(int(timeout[0]["reference_ns"]) == int(events[3]["at_ns"]), "stale dependency refreshed valid RX")
    elif scenario == "observation":
        require(decisions == ["ACCEPTED"]*6, f"EV observation RX: {decisions}")
        require(all(item["q1"] == "USABLE" and item["q2"] == "UNAVAILABLE" for item in events[1:]),
                "missing temperature stopped electrical observation")
        require(events[1]["q0"] == "USABLE" and int(events[1]["soc_ns"]) == anchor, "cached SOC acquisition changed")
        require(all(item["q0"] == "STALE" for item in events[2:]), "cached SOC became fresh from envelope")
        require(int(timeout[0]["reference_ns"]) == int(events[-1]["at_ns"]), "observation envelope timeout origin changed")
    elif scenario == "expiry":
        require(decisions == ["ACCEPTED", "UNAVAILABLE", "UNAVAILABLE", "TIMEOUT"], f"EV expiry RX: {decisions}")
        require([item["issue"] for item in events] == ["NONE", "EXPIRED", "PARENT_MISMATCH", "NONE"],
                "EV parent expiry/renewal bypassed")
        expiry = int(events[0]["expiry_ns"])
        closed = [item for item in views if item["q0"] == "STALE" and item["allow"] == "0"]
        require(closed and expiry <= int(closed[0]["at_ns"]) <= expiry + 20_000_000,
                "EV expiry use gate did not close before RX timeout")
    elif scenario == "parent":
        require(decisions == ["ACCEPTED", "UNAVAILABLE", "UNAVAILABLE", "ACCEPTED", "UNAVAILABLE",
                              "UNAVAILABLE", "ACCEPTED", "TIMEOUT"], f"EV parent RX: {decisions}")
        require([item["issue"] for item in events] == ["NONE", "PARENT_MISSING", "PARENT_MISMATCH", "NONE",
                    "PARENT_ROLLBACK", "PARENT_MISMATCH", "NONE", "NONE"], "EV parent identity/deadline checks bypassed")
        require(events[6]["allow"] == "0" and events[6]["q0"] == "USABLE", "explicit non-driving action was not usable")
    elif scenario == "rejoin":
        require(decisions == ["ACCEPTED", "TIMEOUT", "TIMEOUT", "ACCEPTED", "EPOCH_MISMATCH", "ACCEPTED"],
                f"EV rejoin RX: {decisions}")
        resets = [fields(line) for line in lines if line.startswith("REINIT ")]
        require(len(resets) == 1 and resets[0]["epoch"] == str(epoch + 1), "EV trusted explicit INIT missing")
        require(events[3]["seq"] == "0" and events[3]["epoch"] == str(epoch + 1) and events[3]["counter"] == "0",
                "EV new Epoch failed to reset stream state")
        require([item["epoch"] for item in timeout] == [str(epoch), str(epoch + 1)], "EV silently rejoined before trusted INIT")

    history = None
    for item in events:
        current = tuple(item[key] for key in ("history_rx_ns", "source_ns", "seq", "epoch"))
        if item["decision"] == "ACCEPTED":
            require(item["history_rx_ns"] == item["at_ns"], "EV accepted RX timestamp mismatch")
            age = int(item["at_ns"]) - int(item["source_ns"])
            require(0 <= age <= (150_000_000 if observation else 50_000_000), "EV accepted old/future envelope")
            history = current
        else:
            require(current == history, "EV rejected frame changed accepted history")
        if item["decision"] == "ACCEPTED":
            require((int(item["id"]), int(item["length"])) == EV_STREAMS[kind][:2], "EV envelope transport changed")
    if scenario in ("normal", "forward"):
        sources = [item["source_ns"] for item in events]
        require(sources == [item["source_ns"] for item in tx], "EV original source timestamp changed in transport")
        require([item["seq"] for item in events] == [item["seq"] for item in tx] and
                all(item["epoch"] == str(epoch) for item in events), "EV source sequence/Epoch changed in transport")
        require([int(item["counter"]) for item in events] == list(range(5, 10) if scenario == "forward" else range(5)),
                "EV transport counter did not remain independent")
    if scenario == "forward":
        forwarded = [fields(line) for line in output["relay"].splitlines() if line.startswith("FORWARD ")]
        require(len(forwarded) == 5 and [item["source_ns"] for item in forwarded] == [item["source_ns"] for item in tx],
                "EV relay lost original source lineage")
        require(all(item["charge_w"] == "120000" and item["discharge_w"] == "200000" for item in events),
                "EV relay changed physical limits")
        require([item["input_ns"] for item in events] == [item["input_ns"] for item in tx] and
                [item["causal_seq"] for item in events] == [item["causal_seq"] for item in tx],
                "EV relay changed dependency time or model identity")
        require(all(int(item["input_ns"]) < int(item["source_ns"]) for item in events),
                "EV relay replaced old dependency with forwarding timestamp")
        relay_timeout = [fields(line) for line in output["relay"].splitlines() if line.startswith("EV_TIMEOUT ")]
        require(len(relay_timeout) == 1 and relay_timeout[0]["usable"] == "0" and
                80_000_000 <= int(relay_timeout[0]["elapsed_ns"]) <= 100_000_000,
                "EV relay receiver timeout bypassed monitor budget")
    return int(timeout[-1]["elapsed_ns"])/1_000_000


def issue_epoch(build, store):
    completed = subprocess.run([str(build / "actuator_demo"), "epoch", "next", str(store)],
                               check=True, capture_output=True, text=True)
    value = int(fields(completed.stdout.strip())["value"])
    require(0 < value <= 0xFFFFFFFF, "invalid durable Epoch grant")
    return value


def verify_overflow(kind, scenario, session, output):
    lines = output["rx"].splitlines()
    events = [fields(line) for line in lines if line.startswith(("RX ", "EV_RX "))]
    faults = [fields(line) for line in lines if line.startswith("QUEUE_FAULT ")]
    discarded = [fields(line) for line in lines if line.startswith("QUEUE_DISCARD ")]
    require(events and events[0]["decision"] == "ACCEPTED", "overflow fixture lacked initial usable sample")
    require(len(faults) == 1 and faults[0]["usable"] == "0", "queue continuity did not close use gate")
    fault = faults[0]
    require(fault["kind"] == ("kernel" if scenario == "kernel-overflow" else "application"), "wrong overflow layer")
    require((int(fault["drops"]) > 0) == (scenario == "kernel-overflow"), "real SO_RXQ_OVFL evidence missing")
    require(0 <= int(fault["at_ns"]) - int(events[0]["at_ns"]) <= 100_000_000, "continuity detection exceeded local budget")
    require(all(event["decision"] != "ACCEPTED" for event in events[1:]), "backlog/new packet repaired continuity")
    require(discarded and int(discarded[-1]["at_ns"]) >= int(fault["at_ns"]), "latched queue did not discard later traffic")
    end = fields(lines[-1])
    require(end["continuity"] == "1" and end["usable"] == "0", "overflow was automatically recovered")
    require("fresh_after_overflow" in output["tx"] and "late_after_overflow" in output["tx"], "fresh late frames not transmitted")
    return None


def verify_restart(kind, session, output):
    lines = output["rx"].splitlines()
    events = [fields(line) for line in lines if line.startswith(("RX ", "EV_RX "))]
    require([item["decision"] for item in events] == ["EPOCH_MISMATCH", "ACCEPTED", "EPOCH_MISMATCH", "ACCEPTED", "TIMEOUT"],
            "old Epoch poisoned newly initialized transport or healed timeout")
    source_key = "source_ns" if kind in EV_STREAMS else "last_source_ns"
    rx_key = "history_rx_ns" if kind in EV_STREAMS else "last_valid_ns"
    require(events[0][rx_key] == "0", "old Epoch learned before current producer")
    require(events[2][rx_key] == events[1][rx_key] and events[2][source_key] == events[1][source_key],
            "old counter/epoch changed accepted sample")
    require(events[-1][rx_key] == events[3][rx_key] and events[-1]["e2e"] == "-1", "late frame bypassed timeout")
    timers = [fields(line) for line in lines if line.startswith(("TIMEOUT ", "EV_TIMEOUT "))]
    require(len(timers) == 1 and 80_000_000 <= int(timers[0]["elapsed_ns"]) <= 100_000_000, "restart timeout budget failed")
    if kind in EV_STREAMS:
        require(events[1]["allow"] == events[3]["allow"] == "1", "new independent parent grant unusable")
    return int(timers[0]["elapsed_ns"])/1_000_000


def run_case(build, log_dir, kind, scenario, repetition, epoch_store):
    processes = {}
    output = {name: bytearray() for name in ("tx", "rx", "tx_err", "rx_err")}
    session = ""
    epoch = issue_epoch(build, epoch_store)
    if scenario == "rejoin":
        require(issue_epoch(build, epoch_store) == epoch + 1, "trusted rejoin Epoch reservation failed")
    try:
        ev = kind in EV_STREAMS
        duration = (950 if scenario == "observation" else 800) if kind == "bms-battery" else 400
        roles = [("rx", "rx", kind, str(duration) if ev else "230"),
                 ("tx", "tx", "bms-limits" if scenario == "forward" else kind, scenario)]
        if scenario == "forward":
            roles.append(("relay", "rx", "bms-limits", "400"))
            output.update({"relay": bytearray(), "relay_err": bytearray()})
        for role, executable, stream, argument in roles:
            command = [str(build / f"actuator_socketcan_{executable}"), INTERFACE, stream, str(epoch), argument]
            if role == "rx" and scenario == "wire":
                command.append("wire")
            if role == "relay":
                command.append("forward")
            if role == "rx" and scenario in ("app-overflow", "kernel-overflow"):
                command.append(scenario)
            processes[role] = subprocess.Popen(
                command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        rx_ready = ready(processes["rx"], "RX_READY")
        output["rx"].extend((rx_ready + "\n").encode())
        tx_ready = ready(processes["tx"], "TX_READY")
        output["tx"].extend((tx_ready + "\n").encode())
        if ev:
            if "relay" in processes:
                output["relay"].extend((ready(processes["relay"], "RX_READY") + "\n").encode())
            plan = ev_start_plan(kind, scenario, epoch)
            for process in processes.values():
                process.stdin.write(plan)
                process.stdin.close()
        else:
            start(processes["rx"])
        session = ready(processes["rx"], "SESSION ")
        output["rx"].extend((session + "\n").encode())
        if "relay" in processes:
            output["relay"].extend((ready(processes["relay"], "SESSION ") + "\n").encode())
        if not ev:
            start(processes["tx"])
        collect(processes, output)
        return verify(kind, scenario, session, {name: data.decode() for name, data in output.items()})
    finally:
        for name, process in processes.items():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
            # Collector가 실패해도 종료 후 pipe에 남은 trace/stderr를 보존한다.
            for stream, key in ((process.stdout, name), (process.stderr, name + "_err")):
                if stream and not stream.closed:
                    output[key].extend(stream.read(2_000_000))
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe and not pipe.closed:
                    pipe.close()
        # 성공/실패 모두 수집된 trace를 artifact로 남긴다.
        path = log_dir / f"{kind}-{scenario}-{repetition}.log"
        path.write_text("\n".join(name + ":\n" + data.decode(errors="replace") for name, data in output.items()))


def run_model_case(build, log_dir, scenario, epoch_store, repetition, domain="steering"):
    brake = domain == "brake"
    value_key = "pressure_pa" if brake else "angle_rad"
    history_key = "history_pressure_pa" if brake else "history_angle_rad"
    maximum = 1500000 if brake else 0.3
    quantum = 1000 if brake else 0.0001
    rise_rate = 5000000 if brake else 1
    fall_rate = 10000000 if brake else 1
    epoch = issue_epoch(build, epoch_store)
    processes = {}
    output = {key: bytearray() for key in ("rx", "rx_err", "tx", "tx_err", "model", "model_err")}
    try:
        commands = {
            "rx": [str(build / "actuator_socketcan_rx"), INTERFACE, "brake-actual" if brake else "actual", str(epoch), "1100" if brake else "850"],
            "model": [str(build / "actuator_socketcan_rx"), INTERFACE, "brake-cmd" if brake else "cmd", str(epoch), "1000" if brake else "750", "model"],
            "tx": [str(build / "actuator_socketcan_tx"), INTERFACE, "brake-cmd" if brake else "cmd", str(epoch), scenario],
        }
        for role, command in commands.items():
            processes[role] = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE, bufsize=0)
            prefix = "TX_READY" if role == "tx" else "RX_READY"
            output[role].extend((ready(processes[role], prefix) + "\n").encode())
        for role in ("rx", "model"):
            start(processes[role])
            output[role].extend((ready(processes[role], "SESSION ") + "\n").encode())
        start(processes["tx"])
        collect(processes, output)
        traces = {key: data.decode() for key, data in output.items()}
        ticks = [fields(line) for line in traces["model"].splitlines() if line.startswith("MODEL ")]
        commands = [fields(line) for line in traces["tx"].splitlines() if line.startswith("MODEL_TX ")]
        inputs = [fields(line) for line in traces["model"].splitlines() if line.startswith("MODEL_RX ")]
        feedback = [fields(line) for line in traces["rx"].splitlines() if line.startswith("RX ")]
        require(len(ticks) >= 50 and commands and inputs and feedback, "model flow incomplete")
        require(all(item["valid"] == "1" for item in ticks), "modeled Actual unexpectedly unavailable")
        require(all(item["decision"] == "ACCEPTED" for item in feedback), "Actual rejected across vCAN")
        require(len(feedback) == len(ticks), "published Actual lost")
        require([int(item["seq"]) for item in ticks] == list(range(len(ticks))), "Actual sequence gap")
        for tick, received in zip(ticks, feedback):
            require(received["last_source_ns"] == tick["at_ns"] and received["last_seq"] == tick["seq"],
                    "Actual source identity changed across vCAN")
            require(all(received[key] == tick[key] for key in ("state", "origin", "causal")),
                    "Actual protection/causal metadata changed")
            require(abs(float(received[history_key]) - float(tick[value_key])) <= quantum/100,
                    "Actual is a command echo or changed on transport")
        moving = [item for item in ticks if abs(float(item[value_key])) > quantum/2]
        require(moving and int(moving[0]["at_ns"]) - int(inputs[0]["at_ns"]) >= 50_000_000,
                "physical delay skipped")
        for previous, current in zip(ticks, ticks[1:]):
            elapsed = (int(current["at_ns"]) - int(previous["at_ns"]))/1e9
            require(elapsed > 0 and abs(float(current[value_key])) <= maximum + quantum/2, "clock/physical limit failed")
            difference = float(current[value_key]) - float(previous[value_key])
            rate = rise_rate if difference >= 0 else fall_rate
            require(abs(difference) <= rate*elapsed + quantum*1.01,
                    "rate limit exceeded")
        normal = [item for item in ticks if item["state"] == "1"]
        protected = [item for item in ticks if item["state"] == "3"]
        require(normal and protected and all(item["origin"] == "2" for item in protected), "loss protection missing")
        if brake:
            target = max(float(protected[0][value_key]), 1000000)
            require(abs(float(protected[-1][value_key]) - target) <= quantum/2, "protective pressure floor not reached")
            require(all(float(item[value_key]) <= target + quantum/2 for item in protected), "protective pressure overshot")
            require(all(float(current[value_key]) >= float(previous[value_key]) for previous, current in zip(protected, protected[1:])),
                    "loss protection released pressure")
        else:
            require(all(item[value_key] == protected[0][value_key] for item in protected), "held angle changed")
        first_protection = ticks.index(protected[0])
        require(all(item["state"] == "3" for item in ticks[first_protection:]), "late traffic healed model fault")
        require(all(item["fault"] == "1" for item in protected), "unexpected scheduling/continuity fault")
        accepted = [item for item in inputs if item["decision"] == "ACCEPTED"]
        causal_source = next((int(item["at_ns"]) for item in commands if item["seq"] == protected[0]["causal"]), None)
        require(accepted and causal_source is not None and
                30_000_000 < int(protected[0]["at_ns"]) - causal_source <= 50_000_000,
                "source-expiry control response missed its fixture budget")
        if scenario == "model-normal":
            require(abs(max(float(item[value_key]) for item in normal) - maximum) <= quantum/2, "physical saturation not reached")
            if brake:
                require(float(normal[-1][value_key]) == 0 and float(protected[0][value_key]) == 0,
                        "valid zero did not release pressure before communication loss")
            require(len(accepted) == len(commands), "normal command rejected")
        else:
            require(inputs[-1]["decision"] == "MODE_REJECTED", "late command bypassed latched protection")
            if scenario == "model-high-loss":
                require(brake and float(protected[0][value_key]) == maximum, "high pressure was reduced on loss")
            else:
                require(0 < float(protected[0][value_key]) < maximum, "loss did not interrupt movement")
            expected_causal = "45" if scenario == "model-high-loss" else "15"
            require(protected[0]["causal"] == protected[-1]["causal"] == expected_causal, "last accepted command lost")
    finally:
        for role, process in processes.items():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
            for stream, key in ((process.stdout, role), (process.stderr, role + "_err")):
                if stream and not stream.closed:
                    output[key].extend(stream.read(2_000_000))
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe and not pipe.closed:
                    pipe.close()
        (log_dir / f"{domain}-{scenario}-{repetition}.log").write_text(
            "\n".join(role + ":\n" + data.decode(errors="replace") for role, data in output.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build/m1-angle"))
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--family", choices=("all", "actuator", "ev", "model"), default="all")
    parser.add_argument("--model", choices=("all", "steering", "brake"), default="all")
    args = parser.parse_args()
    has_actuator = args.family in ("all", "actuator")
    has_ev = args.family in ("all", "ev")
    has_model = args.family in ("all", "model")
    model_cases = []
    if has_model:
        for domain in ("steering", "brake"):
            if args.model in ("all", domain):
                scenarios = ("model-normal", "model-loss", "model-high-loss") if domain == "brake" else ("model-normal", "model-loss")
                model_cases += [(domain, scenario) for scenario in scenarios]
    build = args.build_dir.resolve()
    require(1 <= args.repetitions <= 20, "repetitions must be 1..20")
    for role in ("tx", "rx"):
        require((build / f"actuator_socketcan_{role}").is_file(), "build SocketCAN test executables first")
    log_dir = build / "socketcan-results"
    log_dir.mkdir(exist_ok=True)
    # Fresh explicit bootstrap is valid only on this isolated test bus. A real
    # deployment configures one persistent store and never auto-resets it.
    owned = Path(tempfile.mkdtemp(prefix="epoch-run-", dir=log_dir))
    epoch_store = owned / "store"
    subprocess.run([str(build / "actuator_demo"), "epoch", "init", str(epoch_store)], check=True, capture_output=True)
    created = False
    observed = []
    try:
        subprocess.run(["ip", "link", "add", "dev", INTERFACE, "type", "vcan"], check=True)
        created = True
        subprocess.run(["ip", "link", "set", "dev", INTERFACE, "mtu", "72", "up"], check=True)
        for repetition in range(1, args.repetitions + 1):
            for kind in (("cmd", "actual", "brake-cmd", "brake-actual", "drive-cmd", "drive-actual") if has_actuator else ()):
                for scenario in ("normal", "faults", "silent", "flood"):
                    elapsed = run_case(build, log_dir, kind, scenario, repetition, epoch_store)
                    observed.append(elapsed)
                    print(f"PASS {kind}/{scenario} #{repetition}: timeout={elapsed:.3f} ms", flush=True)
            if has_actuator:
                elapsed = run_case(build, log_dir, "drive-actual", "feedback", repetition, epoch_store)
                observed.append(elapsed)
                print(f"PASS drive-actual/feedback #{repetition}: timeout={elapsed:.3f} ms", flush=True)
            for kind in (("brake-cmd", "brake-actual") if has_actuator else ()):
                run_case(build, log_dir, kind, "wire", repetition, epoch_store)
                print(f"PASS {kind}/wire #{repetition}: 8 frames; wire/E2E only", flush=True)
            if has_ev:
                ev_cases = [(kind, scenario) for kind in EV_STREAMS for scenario in ("normal", "faults", "silent", "flood")] + EV_EXTRA
                for kind, scenario in ev_cases:
                    elapsed = run_case(build, log_dir, kind, scenario, repetition, epoch_store)
                    print(f"PASS {kind}/{scenario} #{repetition}: timeout={elapsed:.3f} ms", flush=True)
            streams = (("cmd", "actual", "brake-cmd", "brake-actual", "drive-cmd", "drive-actual") if has_actuator else ())
            streams += tuple(EV_STREAMS) if has_ev else ()
            for kind in streams:
                for scenario in ("app-overflow", "kernel-overflow"):
                    run_case(build, log_dir, kind, scenario, repetition, epoch_store)
                    print(f"PASS {kind}/{scenario} #{repetition}: continuity latched", flush=True)
            restart_streams = (("cmd",) if has_actuator else ()) + (("drive-permission",) if has_ev else ())
            for kind in restart_streams:
                run_case(build, log_dir, kind, "restart", repetition, epoch_store)
                print(f"PASS {kind}/restart #{repetition}: durable Epoch, old counter 200 rejected", flush=True)
            for domain, scenario in model_cases:
                run_model_case(build, log_dir, scenario, epoch_store, repetition, domain)
                print(f"PASS {domain}/{scenario} #{repetition}: command -> dynamics -> Actual", flush=True)
    finally:
        if created:
            subprocess.run(["ip", "link", "delete", "dev", INTERFACE], check=True)
    ev_count = len(EV_STREAMS)*4 + len(EV_EXTRA)
    count = ((40 if has_actuator else 0) + (49 if has_ev else 0) + len(model_cases))*args.repetitions
    print(f"PASS {count} cases (M1 actuator 40 / EV {ev_count + 13} / M2 steering 2 + brake 3 per full repetition)")
    if observed:
        print(f"Actuator application timeout {min(observed):.3f}..{max(observed):.3f} ms")
    print(f"Epoch store: {epoch_store}; each grant persisted by an independent issuer process")
    print(f"Trace: {log_dir}; local vCAN fixture only (actuator/vehicle TC 아님)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
