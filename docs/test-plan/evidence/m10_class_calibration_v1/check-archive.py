#!/usr/bin/env python3
"""Replay archived error analysis, mask review and sealed class calibration."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main(evidence, output):
    if output.exists():
        raise FileExistsError(output)
    evidence = evidence.resolve()
    checksums = 0
    for directory in (evidence, evidence.parent / "m10_model_diagnostics_v1"):
        for line in (directory / "SHA256SUMS").read_text().splitlines():
            expected, name = line.split("  ", 1)
            path = (directory / name).resolve()
            if not path.is_relative_to(directory) or digest(path) != expected:
                raise ValueError("external checksum: " + name)
            checksums += 1
    with tempfile.TemporaryDirectory(
        prefix="m10-class-calibration-replay-"
    ) as directory:
        temporary = Path(directory)
        with tarfile.open(evidence / "experiment.tar.gz") as archive:
            seen = set()
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not member.isfile()
                    or member.name in seen
                ):
                    raise ValueError("unsafe or duplicate archive member")
                seen.add(member.name)
            archive.extractall(temporary)
        project = temporary / "project"
        manifest = json.loads((project / "archive-files.json").read_text())
        for relative, expected in manifest.items():
            path = (project / relative).resolve()
            if not path.is_relative_to(project) or digest(path) != expected:
                raise ValueError("archive member checksum: " + relative)
        env = dict(
            os.environ,
            PYTHONPATH=str(project)
            + os.pathsep
            + str(project / "tests/integration/perception"),
        )

        def run(script, *arguments):
            process = subprocess.run(
                [sys.executable, str(script), *map(str, arguments)],
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
            )
            if process.returncode:
                raise RuntimeError(process.stdout + process.stderr)

        diagnostic = project / "build/m10-model-diagnostics-v1"
        calibration = project / "build/m10-class-calibration-v1"
        diag_result = temporary / "diagnostic-audit.json"
        run(
            project / "tests/integration/perception/analyze_model_diagnostics_v1.py",
            "audit",
            "--freeze",
            diagnostic / "freeze.json",
            "--report",
            diagnostic / "analysis.json",
            "--output",
            diag_result,
        )
        run(diagnostic / "mask-annex/check-masks.py")
        class_result = temporary / "class-audit.json"
        run(
            project / "tests/integration/perception/audit_class_calibration_v1.py",
            "audit",
            "--annex",
            calibration / "audit-annex-freeze.json",
            "--freeze",
            calibration / "freeze.json",
            "--selection",
            calibration / "selection.json",
            "--numeric",
            calibration / "numeric.json",
            "--regression",
            calibration / "regression.json",
            "--output",
            class_result,
        )
        audits = [json.loads(path.read_text()) for path in (diag_result, class_result)]
        if any(
            r["status"] != "PASS" or Path(r["source_root"]) != project for r in audits
        ):
            raise ValueError("fresh-source subprocess identity")
        validation_script = """
from pathlib import Path
from itertools import islice
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.contract import sha256_file
root=Path.cwd();v2=root/'build/m10-model-screen-v2';cal=root/'build/m10-class-calibration-v1'
freeze=read_json(v2/'freeze.json');seen=set()
for paths in freeze['datasets'].values():
    for spec in paths.values():
        actual=[source['rgb_sha256'] for source,_ in RgbDataset(root/spec['path']/'rgb.json').frames()]
        assert actual==spec['rgb_sha256'] and not seen.intersection(actual)
        seen.update(actual)
assert len(seen)==405
profile=read_json(root/'profiles/perception-class-calibration-candidates-v1.json')
selection=read_json(cal/'selection.json');regression=read_json(cal/'regression.json');registry=read_json(root/'profiles/perception-model-screen-v2.json')
for key, filename in [('selection_sha256','selection.json'),('freeze_sha256','freeze.json'),('numeric_sha256','numeric.json'),('regression_sha256','regression.json')]:assert profile[key]==sha256_file(cal/filename)
assert profile['class_adapter_source_sha256']==sha256_file(root/'physical_ai/perception/class_calibration_v1.py')
assert profile['runtime_promotion'] is False and profile['fresh_acceptance'] is False and profile['training'] is False and profile['jetson_execution'] is False
qualified=[]
for candidate,value in profile['models'].items():
    name=value['native_model_id'];spec=registry['models'][name];vector=[value['class_thresholds'][str(c)] for c in profile['class_order']]
    assert vector==selection['candidates'][name]['search']['selected']['vector'] and min(vector)>=.35
    for key in ['onnx_sha256','onnx_bytes','checkpoint_sha256']:assert value[key]==spec['sha256' if key=='onnx_sha256' else 'bytes' if key=='onnx_bytes' else key]
    assert value['native_source_revision']==spec['revision']
    assert value['native_registry_sha256']==sha256_file(root/'profiles/perception-model-screen-v2.json')
    assert value['native_preprocess_source_sha256']==sha256_file(root/'physical_ai/perception/model_screen_v2.py')
    assert value['calibration_absolute']==selection['candidates'][name]['calibration']['metrics']['absolute_pass']
    assert value['calibration_relative']==selection['candidates'][name]['calibration']['metrics']['relative_pass']
    assert value['consumed_town04_absolute']==regression['candidates'][name]['metrics']['absolute_pass']
    assert value['consumed_town04_relative']==regression['candidates'][name]['metrics']['relative_pass']
    assert value['runtime_promotion'] is False
    if value['calibration_absolute'] and value['consumed_town04_absolute']:qualified.append(candidate)
assert qualified==[profile['next_fresh_quality_candidate']]==['dfine-m-class-v1']
print('PASS405')
"""
        validation = subprocess.run(
            [sys.executable, "-c", validation_script],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
        )
        if validation.returncode or validation.stdout.strip() != "PASS405":
            raise RuntimeError(validation.stdout + validation.stderr)
        result = dict(
            status="PASS",
            archive_sha256=digest(evidence / "experiment.tar.gz"),
            archive_bytes=(evidence / "experiment.tar.gz").stat().st_size,
            checksums_checked=checksums,
            archive_members_checked=len(manifest),
            fresh_source_subprocess=True,
            diagnostic_audit=audits[0],
            class_calibration_audit=audits[1],
            unique_development_rgb=405,
            mask_cases=3,
            derived_candidate_profile="PASS",
            holdout_access=False,
            fresh_acceptance=False,
            runtime_promotion=False,
        )
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS", result["archive_members_checked"], result["unique_development_rgb"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.evidence, args.output)
