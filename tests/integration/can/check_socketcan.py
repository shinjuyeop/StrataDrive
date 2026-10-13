#!/usr/bin/env python3
"""독립 C++ TX/RX process를 임시 vCAN에 연결하는 유한 시간 integration fixture."""

import argparse
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time


INTERFACE = "sd_m1_app"
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
    require(all(item["epoch"] == "1" for item in wire_events), "Brake Epoch transport mismatch")
    timestamps = [int(item["source_ns"]) for item in wire_events]
    require(timestamps == sorted(set(timestamps)) and timestamps[0] >= int(fields(session)["enable_ns"]),
            "Brake source timestamp transport mismatch")
    require(lines[-1].startswith("END ") and fields(lines[-1]) == {"decoded": "4", "rejected": "4"},
            "Brake wire result count mismatch")
    require("TX wire_frames=8" in output["tx"], "Brake TX did not finish sending")


def verify(kind, scenario, session, output):
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


def run_case(build, log_dir, kind, scenario, repetition):
    processes = {}
    output = {name: bytearray() for name in ("tx", "rx", "tx_err", "rx_err")}
    session = ""
    try:
        for role, argument in (("rx", "230"), ("tx", scenario)):
            command = [str(build / f"actuator_socketcan_{role}"), INTERFACE, kind, "1", argument]
            if role == "rx" and scenario == "wire":
                command.append("wire")
            processes[role] = subprocess.Popen(
                command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        rx_ready = ready(processes["rx"], "RX_READY")
        output["rx"].extend((rx_ready + "\n").encode())
        tx_ready = ready(processes["tx"], "TX_READY")
        output["tx"].extend((tx_ready + "\n").encode())
        start(processes["rx"])
        session = ready(processes["rx"], "SESSION ")
        output["rx"].extend((session + "\n").encode())
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build/m1-angle"))
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    build = args.build_dir.resolve()
    require(1 <= args.repetitions <= 20, "repetitions must be 1..20")
    for role in ("tx", "rx"):
        require((build / f"actuator_socketcan_{role}").is_file(), "build SocketCAN test executables first")
    log_dir = build / "socketcan-results"
    log_dir.mkdir(exist_ok=True)
    created = False
    observed = []
    try:
        subprocess.run(["ip", "link", "add", "dev", INTERFACE, "type", "vcan"], check=True)
        created = True
        subprocess.run(["ip", "link", "set", "dev", INTERFACE, "mtu", "72", "up"], check=True)
        for repetition in range(1, args.repetitions + 1):
            for kind in ("cmd", "actual", "brake-cmd", "brake-actual", "drive-cmd", "drive-actual"):
                for scenario in ("normal", "faults", "silent", "flood"):
                    elapsed = run_case(build, log_dir, kind, scenario, repetition)
                    observed.append(elapsed)
                    print(f"PASS {kind}/{scenario} #{repetition}: timeout={elapsed:.3f} ms", flush=True)
            elapsed = run_case(build, log_dir, "drive-actual", "feedback", repetition)
            observed.append(elapsed)
            print(f"PASS drive-actual/feedback #{repetition}: timeout={elapsed:.3f} ms", flush=True)
            for kind in ("brake-cmd", "brake-actual"):
                run_case(build, log_dir, kind, "wire", repetition)
                print(f"PASS {kind}/wire #{repetition}: 8 frames; wire/E2E only", flush=True)
    finally:
        if created:
            subprocess.run(["ip", "link", "delete", "dev", INTERFACE], check=True)
    print(f"PASS {27 * args.repetitions} cases (Steering 8 + Brake application 8 + Brake wire 2 + Drive 9 per repetition); "
          f"application timeout {min(observed):.3f}..{max(observed):.3f} ms")
    print(f"Trace: {log_dir}; local vCAN fixture only (actuator/vehicle TC 아님)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
