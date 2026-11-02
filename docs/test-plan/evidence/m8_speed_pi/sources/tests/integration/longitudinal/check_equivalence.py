#!/usr/bin/env python3
"""Replay one persisted input file through independent Python and C++ SpeedPI.

Every run keeps its input, both outputs, plan, process exit/stderr and verdict.
This is controller component equivalence, not vehicle closed-loop performance.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "models/longitudinal"))
from model import Sample, SpeedPI
from mil import judge, reference, simulate
from speed_pi_vectors import generate, SEED

ABS_TOL = REL_TOL = 1e-12
MODEL_SHA256 = "181297fb101d0f7dc69222489956a3bdcc701924556fa2210e4ff5705975e858"
MIL_SHA256 = "d34ad472c240f91aa41809f8a54f0e2e062b091a66c7cba0ee5d84fed69fc3f3"
REASONS = {"normal", "uninitialized", "latched", "sample-time", "permission", "target",
           "invalid-speed", "epoch", "source-age", "identity"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def unsigned(text, bits):
    if not re.fullmatch(r"[0-9]+", text) or int(text) >= 2**bits:
        raise ValueError("invalid unsigned integer")
    return int(text)


def boolean(text):
    if text not in ("0", "1"):
        raise ValueError("invalid boolean")
    return text == "1"


def python_replay(text):
    controller = None
    name = None
    records = []
    for index, line in enumerate(text.splitlines()):
        if len(line) > 1024 or index >= 100000:
            raise ValueError("input bound exceeded")
        fields = line.split()
        if not fields:
            raise ValueError("empty event")
        op = fields[0]
        accepted = output = None
        if op == "new" and len(fields) == 2:
            name = fields[1]
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
                raise ValueError("invalid case name")
            controller = SpeedPI()
        elif controller is None:
            raise ValueError("new case required")
        elif op == "init" and len(fields) == 2:
            accepted = controller.initialize(unsigned(fields[1], 32))
        elif op == "step" and len(fields) in (5, 9):
            now, target = unsigned(fields[1], 64), float(fields[2])
            permission, present = boolean(fields[3]), boolean(fields[4])
            if len(fields) != (9 if present else 5):
                raise ValueError("sample field count")
            speed = Sample(unsigned(fields[5], 32), unsigned(fields[6], 64),
                           unsigned(fields[7], 64), float(fields[8])) if present else None
            output = asdict(controller.step(now, target, speed, permission))
        else:
            raise ValueError("unknown or malformed event")
        state = dict(epoch=controller.epoch, integral=controller.integral, previous=controller.previous,
                     last_ns=controller.last_ns, sample=asdict(controller.sample) if controller.sample else None,
                     fault=controller.fault, target=controller.target)
        records.append(dict(index=index, case=name, op=op, accepted=accepted, output=output, state=state))
    if not records:
        raise ValueError("empty input")
    return records


def compare_records(expected, actual):
    if not expected or len(expected) != len(actual):
        raise ValueError(f"event count: expected {len(expected)}, actual {len(actual)}")
    maximum_errors = {}
    cases = {}
    reasons = Counter()

    def compare(want, got, path, stats):
        if isinstance(want, dict):
            if not isinstance(got, dict) or want.keys() != got.keys():
                raise ValueError(f"{path}: object fields differ")
            for key in want:
                compare(want[key], got[key], f"{path}.{key}" if path else key, stats)
        elif isinstance(want, float):
            if (type(got) not in (int, float) or abs(got) > sys.float_info.max
                    or not math.isfinite(want) or not math.isfinite(got)):
                raise ValueError(f"{path}: nonfinite or nonnumeric output")
            error = abs(want - got)
            maximum_errors[path] = max(maximum_errors.get(path, 0.), error)
            stats["max_absolute_error"] = max(stats["max_absolute_error"], error)
            if error > ABS_TOL + REL_TOL * max(abs(want), abs(got)):
                raise ValueError(f"{path}: expected {want!r}, actual {got!r}, absolute error {error!r}")
        elif type(want) is not type(got) or want != got:
            raise ValueError(f"{path}: expected {want!r}, actual {got!r}")

    for index, (want, got) in enumerate(zip(expected, actual)):
        stats = cases.setdefault(want["case"], dict(events=0, steps=0, max_absolute_error=0.))
        stats["events"] += 1
        stats["steps"] += want["op"] == "step"
        if want["output"]:
            reasons[want["output"]["reason"]] += 1
        try:
            compare(want, got, "", stats)
        except ValueError as error:
            raise ValueError(f"event {index}, case {want['case']}: {error}") from error
    return dict(pass_=True, events=len(expected), cases=cases, reasons=dict(reasons),
                max_absolute_errors=maximum_errors)


def read_records(text):
    def reject_constant(value):
        raise ValueError(f"nonfinite JSON constant {value}")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result

    return [json.loads(line, parse_constant=reject_constant, object_pairs_hook=unique_keys)
            for line in text.splitlines()]


MALFORMED = {
    "empty": "", "no_case": "init 1\n", "blank": "new a\n\n", "unknown": "new a\nfoo\n",
    "case_name": 'new a"b\n', "extra_init": "new a\ninit 1 extra\n",
    "negative_epoch": "new a\ninit -1\n", "epoch_overflow": "new a\ninit 4294967296\n",
    "negative_time": "new a\ninit 1\nstep -1 0 1 0\n",
    "time_overflow": "new a\ninit 1\nstep 18446744073709551616 0 1 0\n",
    "bad_double": "new a\ninit 1\nstep 0 nope 1 0\n",
    "bad_bool": "new a\ninit 1\nstep 0 0 2 0\n",
    "missing_sample": "new a\ninit 1\nstep 0 0 1 1\n",
    "extra_sample": "new a\ninit 1\nstep 0 0 1 0 1 0 0 0\n",
    "sequence_overflow": "new a\ninit 1\nstep 0 0 1 1 1 18446744073709551616 0 0\n",
    "trailing_field": "new a\ninit 1\nstep 0 0 1 1 1 0 0 0 trailing\n",
}


def malformed_checks(binary):
    results = []
    for name, text in MALFORMED.items():
        try:
            python_replay(text)
        except ValueError:
            python_rejected = True
        else:
            python_rejected = False
        run = subprocess.run([str(binary)], input=text, text=True, capture_output=True, timeout=5)
        results.append(dict(case=name, input=text, python_rejected=python_rejected,
                            returncode=run.returncode, stdout=run.stdout, stderr=run.stderr,
                            passed=python_rejected and run.returncode == 2))
    return results


def plan(binary):
    sources = ["models/longitudinal/model.py", "models/longitudinal/mil.py",
               "central/longitudinal/speed_pi.hpp", "central/longitudinal/speed_pi.cpp",
               "tests/unit/speed_pi_test.cpp", "tests/unit/longitudinal_equivalence_test.py",
               "tests/integration/longitudinal/speed_pi_vectors.py",
               "tests/integration/longitudinal/speed_pi_replay.cpp",
               "tests/integration/longitudinal/check_equivalence.py", "CMakeLists.txt",
               "cmake/CoreTargets.cmake", "cmake/CoreTests.cmake",
               "docs/test-plan/longitudinal-equivalence-protocol.md"]
    metadata = dict(protocol="speed-pi-equivalence-v1", model="m6-pi-v1", seed=SEED,
                    abs_tolerance=ABS_TOL, rel_tolerance=REL_TOL,
                    python=sys.version, platform=platform.platform(),
                    binary=str(binary), binary_sha256=sha(binary),
                    sources={name: sha(ROOT / name) for name in sources}, argv=sys.argv)
    database = binary.parent / "compile_commands.json"
    if database.exists():
        metadata["compile_commands"] = [entry for entry in json.loads(database.read_text())
                                         if Path(entry["file"]).name in ("speed_pi.cpp", "speed_pi_replay.cpp")]
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", required=True, type=Path)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--output", type=Path)
    output.add_argument("--output-root", type=Path)
    parser.add_argument("--vectors", type=Path, help="Replay a previously saved common input file")
    args = parser.parse_args()
    if args.output_root:
        args.output_root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="run-", dir=args.output_root))
    else:
        folder = args.output
        folder.mkdir(parents=True, exist_ok=False)
    result = {"pass": False, "errors": []}
    try:
        binary = args.replay.resolve(strict=True)
        metadata = plan(binary)
        save(folder / "plan.json", metadata)
        if sha(ROOT / "models/longitudinal/model.py") != MODEL_SHA256 or sha(ROOT / "models/longitudinal/mil.py") != MIL_SHA256:
            raise ValueError("reference model revision differs from the pre-run protocol")
        if args.vectors:
            text = args.vectors.read_text()
        else:
            rows = simulate()
            mil_result = judge(rows)
            save(folder / "mil-result.json", mil_result)
            if not mil_result["pass"]:
                raise ValueError("reference MIL failed before vector generation")
            text = generate(rows, reference)
        inputs = folder / "inputs.txt"
        inputs.write_text(text)
        metadata["input_sha256"] = sha(inputs)
        save(folder / "plan.json", metadata)
        expected = python_replay(inputs.read_text())
        (folder / "python.jsonl").write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in expected))
        with inputs.open() as source, (folder / "cpp.jsonl").open("w") as stdout, (folder / "cpp.stderr").open("w") as stderr:
            run = subprocess.run([str(binary)], stdin=source, stdout=stdout, stderr=stderr, timeout=20)
        save(folder / "process.json", dict(argv=[str(binary)], returncode=run.returncode))
        if run.returncode != 0:
            raise ValueError(f"C++ replay exited {run.returncode}; see cpp.stderr")
        comparison = compare_records(expected, read_records((folder / "cpp.jsonl").read_text()))
        comparison.pop("pass_")
        result.update(comparison)
        if not args.vectors and set(comparison["reasons"]) != REASONS:
            raise ValueError("corpus does not exercise every output reason")
        malformed = malformed_checks(binary)
        save(folder / "malformed-inputs.json", malformed)
        result["malformed_rejected"] = sum(row["passed"] for row in malformed)
        result["malformed_total"] = len(malformed)
        if not all(row["passed"] for row in malformed):
            raise ValueError("malformed-input rejection failed")
        result["pass"] = True
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result["errors"].append(str(error))
    save(folder / "result.json", result)
    print(json.dumps(dict(output=str(folder), **{key: result.get(key) for key in ("pass", "events", "errors")})))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
