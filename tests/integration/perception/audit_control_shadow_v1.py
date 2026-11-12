"""Evidence integrity and live delivery are separate verdicts, including zero input."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "carla"))
from audit_m7_wall_carla import wire, frame
from physical_ai.perception.ipc_2k_v1 import HEADER, RESULT, MAX_BYTES


def require(condition, why):
    if not condition:
        raise ValueError(why)


def audit(directory, raw=True):
    capture = directory / "capture"
    server = json.loads((directory / "server.json").read_text())
    run = json.loads((capture / "result.json").read_text())
    perception = json.loads((capture / "sensors.json").read_text())
    meta = json.loads((capture / "native.json").read_text()) if (capture / "native.json").exists() else {}
    native = [json.loads(x) for x in (capture / "native-perception.jsonl").read_text().splitlines()] if (capture / "native-perception.jsonl").exists() else []
    calls = {c["identity"]["frame"]: c for c in perception["model_calls"]}
    packets, results = {}, {}
    previous = 0
    for row in perception["ipc"]:
        data = bytes.fromhex(row["packet_hex"])
        require(80 <= len(data) <= MAX_BYTES, "bounded wire")
        magic, version, kind, sequence, epoch, reserved, source_clock, wall_clock, sent, state_frame, source, receipt = HEADER.unpack_from(data)
        require(magic == b"S2KPIPC1" and version == 1 and reserved == 0 and kind in (0, 1, 2), "canonical header")
        require(sequence > previous and epoch == 42 and source_clock == perception["source_clock"] and wall_clock == perception["wall_clock"], "wire session/sequence")
        previous = sequence
        require(row["observation_wall_ns"] <= sent == row["sender_wall_ns"] <= row["end_wall_ns"], "original sender times")
        require(receipt <= sent and (state_frame or (kind == 0 and source == receipt == 0)), "actual state or explicit absence")
        if row["disposition"] == "sent":
            packets[sequence] = data
        if kind != 2:
            require(len(data) == 80, "poll/unavailable length")
            continue
        schema, candidate, image, acquired, expiry, received, wall_expiry, camera, calibration, width, height, valid, count, model = RESULT.unpack_from(data, 80)
        require((schema, candidate, camera, calibration, width, height, valid) == (1, 1, 1, 1, 2560, 1536, 1), "native2K schema")
        require(count <= 100 and len(data) == 184 + count * 48, "bounded detections")
        call = calls[image]
        require(call["received_wall_ns"] == received and call["identity"]["source_ns"] == acquired, "original model acquisition/receipt")
        require(call["end_wall_ns"] <= row["observation_wall_ns"], "no result before inference returned")
        require(expiry == acquired + 100_000_000 and wall_expiry == received + 100_000_000, "unchanged exclusive deadlines")
        require(call["result"]["model_sha256"] == model.hex() and len(call["result"]["detections"]) == count, "model identity/detections")
        for i, d in enumerate(call["result"]["detections"]):
            cls, zero, score, *box = struct.unpack_from("<II5d", data, 184 + 48*i)
            require(cls == d["class_id"] and zero == 0 and score == d["score"] and box == d["box"], "unchanged decoded detections")
        if row["disposition"] == "sent":
            results[image] = dict(frame=image, source_ns=acquired, expires_ns=expiry, received_wall_ns=received, wall_expires_ns=wall_expiry, count=count)
    fresh, actual = [], []
    prev_received = prev_accepted = prev_sequence = 0
    for row in native:
        v = row["perception"]
        require(row["ipc_service_ns"] >= 0 and row["native_observed_ns"] <= v["observed_wall_ns"], "native timing")
        require(v["received"] >= prev_received and v["accepted_results"] >= prev_accepted and v["sequence"] >= prev_sequence, "native counters monotone")
        prev_received, prev_accepted, prev_sequence = v["received"], v["accepted_results"], v["sequence"]
        if v["sequence"]:
            require(v["sequence"] in packets, "native references actual sent sequence")
        if v["available"]:
            r = results[v["frame"]]
            require(all(v[k] == value for k, value in r.items()), "native original result unchanged")
            require(v["initialized"] and not v["state_fault"] and not v["disconnected"] and not row["root_error"], "trusted native receiver")
            require(v["wall_enable_ns"] == row["native_enable_ns"] <= v["received_wall_ns"], "actual INIT binding")
            require(v["source_enable_ns"] <= v["source_ns"] <= v["state_source_ns"] < v["expires_ns"], "exclusive original source deadline")
            require(v["received_wall_ns"] <= v["observed_wall_ns"] < v["wall_expires_ns"], "exclusive original receipt deadline")
            require(0 <= v["observed_wall_ns"] - v["state_received_wall_ns"] < 100_000_000, "actual state liveness")
            fresh.append(v)
        for role, packet in enumerate(row["actual"]):
            if packet is not None:
                decoded = frame(wire(packet, 0 if role < 2 else 1, 7, 9), role, True, False)
                require(decoded["source"] <= row["native_observed_ns"], "Actual original native source")
                actual.append(decoded)
    hashes = []
    require(len(perception["raw"]) == len(perception["camera"]), "all received camera packets retained")
    for r in perception["raw"]:
        if raw:
            stored = (capture / r["path"]).read_bytes()
            require(len(stored) == r["stored_bytes"] and hashlib.sha256(stored).hexdigest() == r["stored_sha256"], "stored raw identity")
            bgra = zlib.decompress(stored)
            require(len(bgra) == r["raw_bytes"] == 2560*1536*4 and hashlib.sha256(bgra).hexdigest() == r["bgra_sha256"], "BGRA original")
            rgb = Image.frombytes("RGB", (2560,1536), bgra, "raw", "BGRX").tobytes()
            require(hashlib.sha256(rgb).hexdigest() == r["rgb_sha256"], "future exclusion RGB")
        hashes.append(r["rgb_sha256"])
    services = sorted(r["ipc_service_ns"] for r in native)
    failures = [run.get("error"), meta.get("first_fault"), run.get("cleanup_error"), run.get("camera_cleanup_error")]
    return dict(integrity="PASS", live_shadow_delivery="PASS" if fresh else "NOT_DEMONSTRATED",
        driving_acceptance=False, server_status=server["status"], run_status=run["status"],
        physical_intervals=run.get("completed_physics", 0), native_first_fault=meta.get("first_fault"),
        failures=[x for x in failures if x], model_calls=len(calls), camera_packets=len(perception["camera"]),
        raw_packets=len(hashes), native_reads=len(native), fresh_reads=len(fresh), unique_fresh_frames=len({v["frame"] for v in fresh}),
        original_actual_packets=len(actual), accepted_results=prev_accepted, sent_packets=len(packets),
        last_native_view=native[-1]["perception"] if native else None,
        ipc_service_ns=dict(max=max(services), median=services[len(services)//2]) if services else None,
        rgb_sha256=sorted(set(hashes)), source_and_receipt_lifetime_ns=100_000_000)


if __name__ == "__main__":
    p = argparse.ArgumentParser();p.add_argument("directory", type=Path);p.add_argument("--output", type=Path, required=True)
    a = p.parse_args();result = audit(a.directory)
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k != "rgb_sha256"}, indent=2))
