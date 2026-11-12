"""Real private Python/C++ process transport, explicitly logical fixture time."""
import argparse
from dataclasses import replace
import json
import select
import subprocess

from physical_ai.perception.async_native_2k_v1 import NativeDetection, NativeResult
from physical_ai.perception.boundary_2k_v1 import BoundaryObservation, Publication
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.ipc_2k_v1 import Publisher, socket_pair


def check(binary):
    tx, rx = socket_pair()
    child = subprocess.Popen([str(binary), str(rx.fileno())], pass_fds=(rx.fileno(),),
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    rx.close()
    rows = []
    def ask(command):
        child.stdin.write(command + "\n");child.stdin.flush()
        if not select.select([child.stdout], [], [], 2)[0]:
            raise TimeoutError("bounded native fixture")
        line = child.stdout.readline()
        row = json.loads(line);rows.append(row)
        return row
    try:
        pub = Publisher(tx, 42, 77, 88)
        assert ask("INIT 1000000000") == 1
        # An actual-state analogue initializes source domain before the image.
        obs = BoundaryObservation(None, 40_000_000, 1_001_000_000, 1_001_000_000)
        pub.send(obs, 4, 1_001_000_000)
        assert ask("POLL 1002000000")["initialized"]
        result = NativeResult(FrameIdentity(42, 77, 5, 50_000_000),
                              (NativeDetection(2, .8, (0, 0, 2560, 1536)),))
        obs = BoundaryObservation(Publication(result, 88, 1_010_000_000, 1_110_000_000),
                                  60_000_000, 1_020_000_000, 1_020_000_000)
        pub.send(obs, 6, 1_020_000_000)
        row = ask("POLL 1021000000")
        assert all(row[k] == v for k,v in dict(available=1, frame=5, source=50_000_000,
                   receipt=1_010_000_000, expiry=150_000_000, wall_expiry=1_110_000_000, accepted=1, tracks=1).items())
        pub.send(obs, 6, 1_030_000_000)
        row = ask("POLL 1031000000")
        assert row["available"] and row["accepted"] == 1 and row["receipt"] == 1_010_000_000
        # Exact exclusive receipt expiry; unchanged actual state receipt remains fresh.
        assert not ask("POLL 1110000000")["available"]
        pub.send(obs, 6, 1_111_000_000)
        assert not ask("POLL 1112000000")["available"]
        tx.send(b"malformed")
        assert ask("POLL 1113000000")["rejected"] == 1
        tx.close()
        assert ask("POLL 1114000000")["disconnected"]
    finally:
        tx.close();child.stdin.close()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill();child.wait();raise
    assert child.returncode == 0, child.stderr.read()
    return dict(status="PASS", scope="actual process/socket transport, logical times, no vehicle", observations=rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser();p.add_argument("binary");a = p.parse_args()
    print(json.dumps(check(a.binary), indent=2))
