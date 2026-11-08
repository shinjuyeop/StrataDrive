#!/usr/bin/env python3
"""RGB-only offline candidate execution. Does not read labels or scene metadata."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import MODEL_SHA256, sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.quality_candidates_v2 import QualityCandidateV2, CANDIDATES
from physical_ai.perception.run import distribution
from physical_ai.perception.provenance import runtime_identity
from quality_v2_common import check_freeze, write_new, require


def run(
    dataset_path, model_path, output, candidate, phase, freeze_path, selection_path=None
):
    frozen = check_freeze(freeze_path)
    seal_path = dataset_path.parent / "benchmark-seal.json"
    seal = read_json(seal_path)
    require(
        seal["schema"] == "m10-quality-data-seal-v2"
        and seal["partition"] == phase
        and seal["plan_sha256"] == frozen["plan_sha256"]
        and seal["rgb_manifest_sha256"] == sha256_file(dataset_path),
        "sealed dataset identity",
    )
    if phase == "holdout":
        require(selection_path is not None, "holdout requires sealed nomination")
        selection = read_json(selection_path)
        require(
            selection["schema"] == "m10-quality-selection-v2"
            and selection["freeze_sha256"] == sha256_file(freeze_path),
            "selection identity",
        )
        require(
            candidate in ("baseline", selection["selected"]),
            "unselected holdout candidate",
        )
        require(
            seal["selection_sha256"] == sha256_file(selection_path),
            "selection was not sealed before acquisition",
        )
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="m10-quality-run-v2",
        status="FAIL",
        candidate=candidate,
        phase=phase,
        started_utc=datetime.now(timezone.utc).isoformat(),
        dataset_sha256=sha256_file(dataset_path),
        dataset_seal_sha256=sha256_file(seal_path),
        freeze_sha256=sha256_file(freeze_path),
        protocol_sha256=frozen["protocol_sha256"],
        model_sha256=MODEL_SHA256,
        selection_sha256=sha256_file(selection_path) if selection_path else None,
        expected=0,
        attempted=0,
        model_valid=0,
        admitted=0,
        errors=0,
        rows=[],
        runtime=runtime_identity(),
        authority="offline experiment only; not v1 runtime profile; no C++/vehicle publication",
        cold_calls_excluded=0,
    )
    try:
        dataset = RgbDataset(dataset_path)
        report["expected"] = len(dataset.manifest["frames"])
        begin = time.monotonic_ns()
        backend = QualityCandidateV2(model_path, candidate)
        report["model_initialization_wall_ns"] = time.monotonic_ns() - begin
        report["providers"] = backend.detector.session.get_providers()
        report["provider_options"] = backend.detector.session.get_provider_options()
        report["cpu_node_fallback_disabled"] = True
        for source, camera in dataset.frames():
            row = {k: source[k] for k in ("scene", "frame", "source_ns", "rgb_sha256")}
            row.update(model_valid=False, admitted=False, detections=None)
            report["attempted"] += 1
            before = time.monotonic_ns()
            try:
                result = backend.infer(camera)
                result.validate()
                require(
                    result.identity == camera.identity,
                    "candidate changed source identity",
                )
                elapsed = time.monotonic_ns() - before
                row.update(
                    model_valid=True,
                    admitted=elapsed < 100_000_000,
                    detections=[asdict(d) for d in result.detections],
                    expires_ns=result.expires_ns,
                    elapsed_wall_ns=elapsed,
                    preprocess_ns=result.preprocess_ns,
                    inference_ns=result.inference_ns,
                    postprocess_ns=result.postprocess_ns,
                )
                report["model_valid"] += 1
                report["admitted"] += int(row["admitted"])
            except Exception as error:
                report["errors"] += 1
                row.update(
                    error=f"{type(error).__name__}: {error}",
                    elapsed_wall_ns=time.monotonic_ns() - before,
                )
            report["rows"].append(row)
        report["latency"] = distribution([r["elapsed_wall_ns"] for r in report["rows"]])
        report["status"] = "PASS" if not report["errors"] else "FAIL"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        write_new(output / "result.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--phase", choices=("development", "holdout"), required=True)
    p.add_argument("--candidate", choices=CANDIDATES, required=True)
    p.add_argument("--selection", type=Path)
    a = p.parse_args()
    r = run(a.dataset, a.model, a.output, a.candidate, a.phase, a.freeze, a.selection)
    print(
        {
            k: r.get(k)
            for k in (
                "status",
                "candidate",
                "attempted",
                "model_valid",
                "admitted",
                "errors",
                "error",
                "latency",
            )
        }
    )
    sys.exit(0 if r["status"] == "PASS" else 1)
