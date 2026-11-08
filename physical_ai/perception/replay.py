"""Lossless numeric conversion to the opt-in typed C++ replay executable."""

import json
import subprocess
from .contract import PerceptionResult


def frame_line(result: PerceptionResult, now_ns):
    result.validate()
    i = result.identity
    fields = [
        "F",
        now_ns,
        1,
        i.epoch,
        i.clock_instance,
        i.frame,
        i.source_ns,
        result.expires_ns,
        i.camera_id,
        i.calibration_revision,
        640,
        384,
        1,
        result.model_sha256,
        len(result.detections),
    ]
    for d in result.detections:
        fields.extend((d.class_id, d.score, *d.box))
    return " ".join(map(str, fields))


def run_boundary(binary, lines):
    result = subprocess.run(
        [str(binary)],
        input="\n".join(lines) + "\n",
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    records = [json.loads(row) for row in result.stdout.splitlines()]
    if len(records) != len(lines):
        raise ValueError("C++ result denominator mismatch")
    return records
