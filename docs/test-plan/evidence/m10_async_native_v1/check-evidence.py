#!/usr/bin/env python3
"""Verify bytes and replay frozen-source async traces; no GPU/model execution."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("unsafe evidence path")
    return root / path


def check(evidence):
    checked = set()
    for line in (evidence / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if name in checked or sha(local(evidence, name)) != digest:
            raise ValueError("evidence hash/duplicate: " + name)
        checked.add(name)
    freeze = json.loads((evidence / "fault-v2-freeze.json").read_text())
    v1 = json.loads((evidence / "freeze.json").read_text())
    if len(v1["files"]) != 500 or len(freeze["files"]) != 503:
        raise ValueError("source denominators")
    if any(freeze["files"].get(k) != v for k, v in v1["files"].items()):
        raise ValueError("original500 source bytes changed")
    names = ("none-01", "slow-01", "blocked-01", "exception-delayed-01")
    reports = [evidence / name / "result.json" for name in names]
    for name, path in zip(names, reports):
        data = json.loads(path.read_text())
        expected = (
            "fault-v2-freeze.json" if name == "exception-delayed-01" else "freeze.json"
        )
        if data["source_freeze_sha256"] != sha(evidence / expected):
            raise ValueError("run source freeze identity")
        profile = (
            "profiles/perception-async-native-fault-v2.json"
            if name == "exception-delayed-01"
            else "profiles/perception-async-native-v1.json"
        )
        if data["profile_sha256"] != freeze["files"][profile]:
            raise ValueError("run profile identity")
    normal = json.loads(reports[0].read_text())
    if (
        sha(evidence / "reference/rgb-manifest.json")
        != normal["media"]["manifest_sha256"]
    ):
        raise ValueError("original RGB-only media manifest identity")
    numeric_reference = json.loads((evidence / "reference/numeric-6.json").read_text())
    for index, original in enumerate(normal["media"]["originals"]):
        row = numeric_reference["rows"][index]
        if row["rgb_sha256"] != original["rgb_sha256"] or not any(
            r["file"] == f"numeric-6-raw/{index}-cuda.npz"
            and r["sha256"] == sha(evidence / f"reference/{index}-cuda.npz")
            for r in row["raw_files"]
        ):
            raise ValueError("prior numeric reference/image identity")
    failed = json.loads((evidence / "exception-01/result.json").read_text())
    if (
        failed["status"] != "FAIL"
        or not failed["error"].endswith(
            "ValueError: no independent state/control work during inference\n"
        )
        or failed["worker"]["counters"]["errors"] != 120
        or failed["worker"]["counters"]["published"] != 0
        or [len(failed["traces"][k]) for k in ("state", "camera", "control")]
        != [600, 120, 300]
    ):
        raise ValueError("original immediate-exception fixture failure not preserved")
    with tempfile.TemporaryDirectory(prefix="stratadrive-async-source-") as directory:
        root = Path(directory)
        extracted = set()
        with tarfile.open(evidence / "sources.tar.gz", "r:gz") as archive:
            for member in archive:
                if not member.isfile() or member.name in extracted:
                    raise ValueError("only unique regular source files allowed")
                target = local(root, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                if sha(target) != freeze["files"].get(member.name):
                    raise ValueError("archived source hash: " + member.name)
                extracted.add(member.name)
        if extracted != set(freeze["files"]):
            raise ValueError("complete503 source snapshot required")
        environment = dict(
            os.environ,
            PYTHONPATH=str(root)
            + os.pathsep
            + str(root / "tests/integration/perception"),
        )
        audit_out = root / "audit.json"
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tests/integration/perception/audit_async_native_v1.py"),
                *(str(p) for p in reports),
                "--output",
                str(audit_out),
            ],
            env=environment,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        # All64 real ONNX calls used the same three original development images.
        # Compare saved final detections to their prior frozen CUDA outputs. This
        # checks adapter equivalence, not a new full300 numeric or quality test.
        numeric_code = """
import json, sys
from pathlib import Path
import numpy as np
from physical_ai.perception.camera_resolution_v1 import decode
evidence=Path(sys.argv[1])
normal=json.loads((evidence/'none-01/result.json').read_text())
reference={}
for i,row in enumerate(normal['media']['originals']):
    with np.load(evidence/'reference'/f'{i}-cuda.npz') as arrays:
        detections=decode(dict(arrays),6)
    reference[row['bgra_sha256']]=[(d.class_id,d.score,[v*6 for v in d.box]) for d in detections]
count=0
for name in ('none-01','slow-01','blocked-01'):
    report=json.loads((evidence/name/'result.json').read_text())
    offered={r['frame']:r['original_bgra_sha256'] for r in report['traces']['camera']}
    for call in report['model_calls']:
        expected=reference[offered[call['identity']['frame']]]
        actual=call['result']['detections']
        assert len(actual)==len(expected)
        for d,e in zip(actual,expected):
            assert d['class_id']==e[0]
            np.testing.assert_allclose(d['score'],e[1],rtol=0,atol=1e-4)
            np.testing.assert_allclose(d['box'],e[2],rtol=0,atol=.6)
        count+=1
assert count==64
print(json.dumps({'status':'PASS','real_model_calls':count,'reference_images':3}))
"""
        numeric = subprocess.run(
            [sys.executable, "-c", numeric_code, str(evidence)],
            env=environment,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if numeric.returncode:
            raise RuntimeError(numeric.stdout + numeric.stderr)
        trace_audit = json.loads(audit_out.read_text())
    return dict(
        status="PASS",
        validated_files=len(checked),
        frozen_sources=len(extracted),
        original500_sources_unchanged=True,
        original_exception_failure_preserved=True,
        trace_audit=trace_audit,
        adapter_detection_recheck=json.loads(numeric.stdout),
        mode="fresh archived sources; trace and cached detection replay only",
        model_inference=False,
        simulator=False,
        fresh_quality=False,
    )


def main():
    evidence, output = (Path(v).resolve() for v in sys.argv[1:])
    result = check(evidence)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                status=result["status"], frozen_sources=result["frozen_sources"], runs=4
            )
        )
    )


if __name__ == "__main__":
    main()
