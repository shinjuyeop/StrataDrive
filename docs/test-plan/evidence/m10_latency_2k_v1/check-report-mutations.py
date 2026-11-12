from pathlib import Path
from copy import deepcopy
import json
import runpy
from audit_carla_latency_2k_v1 import audit_readback


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
    elif case == "copy_order":
        r["traces"]["camera"][0]["copy_end_wall_ns"] = 1
    elif case == "copy_after_enable":
        r["copy_preparation"]["end_wall_ns"] = r["enabled_wall_ns"] + 1
    elif case == "copy_error":
        r["copy_errors"] = ["overflow"]
    elif case == "stage_owner":
        r["backend_stages"][0]["owner_thread_id"] += 1
    elif case == "stage_inference":
        r["backend_stages"][0]["inference"] += 1
    elif case == "stage_missing":
        r["backend_stages"].pop()
    elif case == "false_promotion":
        r["runtime_promotion"] = True


for ver in (1,):
    e = Path("docs/test-plan/evidence/m10_latency_2k_v1")
    runs = json.loads((e / "runs.json").read_text())
    outcome = runpy.run_path(str(e / "audit-outcome.py"))["outcome"]
    results = {}
    cases = [
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
        "copy_order",
        "copy_after_enable",
        "copy_error",
        "stage_owner",
        "stage_inference",
        "stage_missing",
        "source_scale",
        "sensor_geometry",
        "result_geometry",
        "candidate",
        "result_schema",
        "packet_bytes",
        "variant",
    ]
    for name in runs["live_runs"]:
        r = json.loads((e / name / "capture/result.json").read_text())
        expected = json.loads((e / name / "packet-validation.json").read_text())[
            "expected_failure"
        ]
        outcome(r, expected)
        rejected = []
        for case in cases:
            x = deepcopy(r)
            mutate(x, case)
            if case == "source_scale":
                x["source_scale"] = 5
            elif case == "sensor_geometry":
                x["sensor_attributes"]["image_size_x"] = "2048"
            elif case == "result_geometry":
                x["model_calls"][0]["result"]["width"] += 1
            elif case == "candidate":
                x["model_calls"][0]["result"]["candidate"] = "unsupported"
            elif case == "result_schema":
                x["model_calls"][0]["result"]["schema"] = "unsupported"
            elif case == "variant":
                x["variant"] = "unsupported"
            elif case == "packet_bytes":
                x["raw"][0]["raw_bytes"] += 1
            try:
                outcome(x, expected)
            except (ValueError, AssertionError, KeyError, TypeError):
                rejected.append(case)
            else:
                raise AssertionError((name, "accepted mutation", case))
        s = (e / name / "server.log").read_text()
        line = next(
            value for value in s.splitlines() if value.startswith("STRATA_READBACK_V1 ")
        )
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
                audit_readback(r, new)
            except (ValueError, AssertionError, KeyError):
                rejected.append("gpu_" + field)
            else:
                raise AssertionError((name, "accepted trace mutation", field))
        if r["variant"] == "balanced":
            changed = s.replace('t.MaxFPS = "100"', 't.MaxFPS = "0"')
            try:
                audit_readback(r, changed)
            except (ValueError, AssertionError, KeyError):
                rejected.append("engine_cap")
            else:
                raise AssertionError((name, "accepted engine cap mutation"))
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
