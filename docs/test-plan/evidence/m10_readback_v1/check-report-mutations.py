from pathlib import Path
from copy import deepcopy
import json
import runpy
from audit_carla_readback_v1 import audit_readback as rb
from audit_carla_readback_pool_v1 import audit_readback as pool


def mutate(r, case):
    if case == "mode":
        r["active_settings"]["synchronous_mode"] = True
    elif case == "delta":
        r["traces"]["state"][1]["delta_ns"] = 20_000_000
    elif case == "episode":
        r["traces"]["state"][1]["world_id"] += 1
    elif case == "receipt":
        r["model_calls"][0]["received_wall_ns"] += 1_000_000_000
    elif case == "raw":
        r["raw"].pop()
    elif case == "available":
        r["availability"]["active_ticks"]["available_samples"] += 1
    elif case == "rate":
        r["metrics"]["primary_camera_hz"] += 1
    elif case == "tick":
        r["traces"]["tick_requests"].append(dict(frame=1))
    elif case == "disk":
        r["recorder"]["disk_frames_during_measurement"] = 1
    elif case == "busy":
        r["worker"]["busy"] = True
    elif case == "decision":
        r["decisions"]["rows"][0]["receipt_expired"] = not r["decisions"]["rows"][0][
            "receipt_expired"
        ]
    elif case == "false_promotion":
        r["runtime_promotion"] = True


for ver, readback in [("readback", rb), ("readback_pool", pool)]:
    e = Path("docs/test-plan/evidence/m10_" + ver + "_v1")
    runs = json.loads((e / "runs.json").read_text())
    outcome = runpy.run_path(str(e / "audit-outcome.py"))["outcome"]
    results = {}
    for name in runs["conditions"]:
        r = json.loads((e / name / "capture/result.json").read_text())
        expected = runs["failed_conditions"].get(name)
        outcome(r, expected)
        rejected = []
        for case in (
            "mode",
            "delta",
            "episode",
            "receipt",
            "raw",
            "available",
            "rate",
            "tick",
            "disk",
            "busy",
            "decision",
            "false_promotion",
        ):
            x = deepcopy(r)
            mutate(x, case)
            try:
                outcome(x, expected)
            except (ValueError, AssertionError, KeyError):
                rejected.append(case)
            else:
                raise AssertionError((name, "accepted mutation", case))
        s = (e / name / "server.log").read_text()
        lines = s.splitlines()
        idx = next(
            i
            for i, value in enumerate(lines)
            if value.startswith("STRATA_READBACK_V1 ")
        )
        line = lines[idx]
        row = json.loads(line.split(" ", 1)[1])
        for field, value in [
            ("timestamp", row["timestamp"] + 1),
            ("deferred", not row["deferred"]),
            ("error", "bounded_capacity"),
            ("inflight", 4),
        ]:
            changed = dict(row)
            changed[field] = value
            new = s.replace(line, "STRATA_READBACK_V1 " + json.dumps(changed), 1)
            try:
                readback(r, new)
            except (ValueError, AssertionError, KeyError):
                rejected.append("gpu_" + field)
            else:
                raise AssertionError((name, "accepted trace mutation", field))
        results[name] = rejected
    (e / "report-mutation-check.json").write_text(
        json.dumps(
            dict(
                status="PASS", rejected=sum(map(len, results.values())), cases=results
            ),
            indent=2,
        )
        + "\n"
    )
    print(ver, sum(map(len, results.values())))
