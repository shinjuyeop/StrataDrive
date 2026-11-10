#!/usr/bin/env python3
"""Freeze and describe errors on consumed development only, with primary replay."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.model_diagnostics_v1 import (
    FP_BUCKETS,
    FN_BUCKETS,
    fp_evidence,
    fn_evidence,
    gt_attributes,
    maximum_matching,
    native_proposals,
    strict_matching,
)
from physical_ai.perception.model_screen_v2 import decode
from quality_benchmark import total
from quality_benchmark_v3 import measure, validate_truth
from run_model_screen_v1 import add, counts, require, validate_development, write_new
from run_model_screen_v2 import check_freeze as check_v2, validate_run

ROOT = Path(__file__).resolve().parents[3]
V2 = ROOT / "build/m10-model-screen-v2"
PROTOCOL = ROOT / "docs/test-plan/perception-model-diagnostics-v1-protocol.md"
MODELS = ("dfine-m", "rtv4-s")
NEW_SOURCES = (
    "physical_ai/perception/model_diagnostics_v1.py",
    "tests/integration/perception/analyze_model_diagnostics_v1.py",
    "tests/integration/perception/test_model_diagnostics_v1.py",
    "docs/test-plan/perception-model-diagnostics-v1-protocol.md",
)


def freeze(output):
    original = check_v2(V2 / "freeze.json")
    selection = read_json(V2 / "selection.json")
    inputs = {}
    unique = set()
    for group, paths in original["datasets"].items():
        for spec in paths.values():
            data = ROOT / spec["path"]
            rgb, _, _ = validate_development(data)
            hashes = [source["rgb_sha256"] for source, _ in rgb.frames()]
            require(
                hashes == spec["rgb_sha256"] and not unique.intersection(hashes),
                "development RGB identity",
            )
            unique.update(hashes)
            for filename in spec["files"]:
                path = data / filename
                inputs[str(path.relative_to(ROOT))] = sha256_file(path)
    for candidate in MODELS:
        require(
            selection["candidates"][candidate]["threshold"] == 0.5,
            "sealed V2 confidence",
        )
        for group in ("calibration", "check"):
            run_path = V2 / "runs" / candidate / group / "run.json"
            report = validate_run(original, V2 / "freeze.json", run_path, group)
            inputs[str(run_path.relative_to(ROOT))] = sha256_file(run_path)
            for row in report["rows"]:
                raw = run_path.parent / row["raw"]
                require(
                    raw.parent == run_path.parent / "raw"
                    and sha256_file(raw) == row["raw_sha256"],
                    "raw input identity",
                )
                inputs[str(raw.relative_to(ROOT))] = row["raw_sha256"]
    for filename in ("freeze.json", "selection.json", "check.json", "numeric-rgb.json"):
        path = V2 / filename
        inputs[str(path.relative_to(ROOT))] = sha256_file(path)
    sources = dict(original["sources"])
    sources.update({relative: sha256_file(ROOT / relative) for relative in NEW_SOURCES})
    result = dict(
        schema="m10-model-diagnostics-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        source_baseline="e57ccac",
        sources=sources,
        inputs=inputs,
        candidates=list(MODELS),
        confidence=0.5,
        unique_development_frames=len(unique),
        model_frames=810,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
        board_execution=False,
    )
    require(len(unique) == 405, "diagnostic development denominator")
    write_new(output, result)
    return result


def check_freeze(frozen):
    f = read_json(frozen)
    require(
        f["schema"] == "m10-model-diagnostics-freeze-v1"
        and f["candidates"] == list(MODELS)
        and f["confidence"] == 0.5
        and f["unique_development_frames"] == 405
        and f["model_frames"] == 810
        and f["holdout_access"] is False
        and f["fresh_acceptance"] is False
        and f["runtime_promotion"] is False
        and f["board_execution"] is False,
        "diagnostic scope/freeze",
    )
    for collection in ("sources", "inputs"):
        for name, digest in f[collection].items():
            path = ROOT / name
            require(
                path.resolve().is_relative_to(ROOT) and sha256_file(path) == digest,
                "diagnostic frozen file changed: " + name,
            )
    check_v2(V2 / "freeze.json")
    return f


def distribution(values):
    return dict(
        n=len(values),
        **{
            label: float(np.percentile(values, quantile)) if values else None
            for label, quantile in (
                ("min", 0),
                ("p25", 25),
                ("p50", 50),
                ("p75", 75),
                ("max", 100),
            )
        },
    )


def summarize(primary, fps, fns, gts, frames):
    gt_slices, fp_slices = {}, {}
    for axis in (
        "dataset",
        "class_id",
        "weather",
        "stratum",
        "box_size",
        "person_kind",
    ):
        values = defaultdict(
            lambda: dict(gt=0, tp=0, fn=0, optimistic_native_supported=0)
        )
        for row in gts:
            cell = values[str(row[axis])]
            cell["gt"] += 1
            cell["tp"] += int(row["primary_matched"])
            cell["fn"] += int(not row["primary_matched"])
            cell["optimistic_native_supported"] += int(row["optimistic_matched"])
        for cell in values.values():
            cell["recall"] = cell["tp"] / cell["gt"]
            cell["optimistic_native_recall_bound"] = (
                cell["optimistic_native_supported"] / cell["gt"]
            )
        gt_slices[axis] = dict(sorted(values.items()))
    for axis in (
        "dataset",
        "class_id",
        "weather",
        "stratum",
        "prediction_box_size",
        "rider_overlap",
    ):
        values = defaultdict(list)
        for row in fps:
            values[str(row[axis])].append(row)
        fp_slices[axis] = {
            key: dict(
                fp=len(rows),
                buckets=dict(Counter(r["bucket"] for r in rows)),
                confidence=distribution([r["prediction"]["score"] for r in rows]),
            )
            for key, rows in sorted(values.items())
        }
    relations = Counter()
    for row in fps:
        for relation in row["relationships"]:
            if relation["class_id"] != row["class_id"] and relation["iou"] >= 0.5:
                relations[f"{row['class_id']}->{relation['class_id']}"] += 1
    per_class = {}
    for class_id, values in primary.items():
        cell = dict(values)
        cell.update(
            gt=values["tp"] + values["fn"],
            recall=values["tp"] / (values["tp"] + values["fn"]),
            fp_buckets={
                bucket: sum(
                    row["class_id"] == int(class_id) and row["bucket"] == bucket
                    for row in fps
                )
                for bucket in FP_BUCKETS
            },
            fn_buckets={
                bucket: sum(
                    row["class_id"] == int(class_id) and row["bucket"] == bucket
                    for row in fns
                )
                for bucket in FN_BUCKETS
            },
        )
        per_class[class_id] = cell
    optimistic = sum(row["optimistic_matched"] for row in gts)
    require(
        sum(primary[c]["fp"] for c in primary) == len(fps)
        and sum(primary[c]["fn"] for c in primary) == len(fns),
        "all errors diagnosed",
    )
    return dict(
        frames=frames,
        positive_gt=len(gts),
        micro=total(primary),
        per_class=per_class,
        fp_buckets={
            bucket: sum(row["bucket"] == bucket for row in fps) for bucket in FP_BUCKETS
        },
        fn_buckets={
            bucket: sum(row["bucket"] == bucket for row in fns) for bucket in FN_BUCKETS
        },
        fp_confidence=distribution([row["prediction"]["score"] for row in fps]),
        recoverable_fn_support_score=distribution(
            [
                row["max_same_class_support_score"]
                for row in fns
                if row["max_same_class_support_score"] is not None
            ]
        ),
        fp_rider_overlap=sum(row["rider_overlap"] for row in fps),
        fp_same_actor_cross_class_gt_overlap=sum(
            row["same_actor_cross_class_gt_overlap"] for row in fps
        ),
        other_class_overlap_relationship_counts=dict(sorted(relations.items())),
        gt_slices=gt_slices,
        fp_slices=fp_slices,
        optimistic_native_matching=dict(
            matched=optimistic,
            total=len(gts),
            recall_bound=optimistic / len(gts),
            ignores_fp_capacity_and_greedy_order=True,
            limited_to_exported_top300=True,
        ),
    )


def analyze(frozen, output):
    check_freeze(frozen)
    original = read_json(V2 / "freeze.json")
    chosen = read_json(V2 / "selection.json")
    checked = read_json(V2 / "check.json")
    report = dict(
        schema="m10-model-diagnostics-report-v1",
        status="PASS",
        freeze_sha256=sha256_file(frozen),
        source_root=str(ROOT),
        candidates={},
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
        scope="Descriptive consumed development only; geometric overlap is not semantic cause",
    )
    for candidate in MODELS:
        candidate_rows = dict(groups={})
        for group, paths in original["datasets"].items():
            run_path = V2 / "runs" / candidate / group / "run.json"
            run = validate_run(original, V2 / "freeze.json", run_path, group)
            primary, fps, fns, gts, frame_records = counts(), [], [], [], []
            position = 0
            for key, spec in paths.items():
                rgb, metadata, truth = validate_development(ROOT / spec["path"])
                for source, scene, gt in zip(
                    rgb.manifest["frames"], metadata["scenes"], truth["frames"]
                ):
                    row = run["rows"][position]
                    position += 1
                    require(
                        row["dataset"] == key
                        and row["scene"]
                        == source["scene"]
                        == scene["scene"]
                        == gt["scene"]
                        and row["frame"] == source["frame"] == gt["frame"]
                        and row["source_ns"] == source["source_ns"]
                        and row["rgb_sha256"] == source["rgb_sha256"],
                        "diagnostic row lineage",
                    )
                    validate_truth(gt)
                    prediction = row["predictions"]["0.5"]
                    require(
                        prediction["valid"] is True, "all diagnostic predictions valid"
                    )
                    with np.load(
                        run_path.parent / row["raw"], allow_pickle=False
                    ) as data:
                        raw = dict(data)
                    proposals = native_proposals(raw)
                    decoded = decode(raw, "rtdetr", 0.5)
                    predictions = prediction["detections"]
                    require(
                        [(d.class_id, d.score, list(d.box)) for d in decoded]
                        == [(d["class_id"], d["score"], d["box"]) for d in predictions],
                        "native selected prediction replay",
                    )
                    values, assignment, matched = strict_matching(
                        predictions, gt["objects"]
                    )
                    expected, expected_matched, _, _, _ = measure(
                        predictions, gt["objects"], gt["excluded"]
                    )
                    require(
                        values == expected and matched == expected_matched,
                        "primary matching identity replay",
                    )
                    add(primary, values)
                    optimistic = set(
                        maximum_matching(gt["objects"], proposals)["matched_gt"]
                    )
                    metadata_row = dict(
                        dataset=key,
                        scene=source["scene"],
                        frame=source["frame"],
                        source_ns=source["source_ns"],
                        rgb_sha256=source["rgb_sha256"],
                        weather=scene["weather"],
                        stratum=scene["stratum"],
                        target_class=scene["target_class"],
                    )
                    for n, obj in enumerate(gt["objects"]):
                        details = gt_attributes(obj)
                        gts.append(
                            dict(
                                metadata_row,
                                gt_index=n,
                                class_id=obj["class_id"],
                                instance_id=obj["instance_id"],
                                semantic_tags=obj["semantic_tags"],
                                visible_pixels=obj["visible_pixels"],
                                primary_matched=n in matched,
                                optimistic_matched=n in optimistic,
                                **details,
                            )
                        )
                        if n not in matched:
                            fns.append(
                                dict(
                                    metadata_row,
                                    gt_index=n,
                                    class_id=obj["class_id"],
                                    **fn_evidence(obj, proposals, 0.5),
                                )
                            )
                    for n, d in enumerate(predictions):
                        if assignment[n] is None:
                            fps.append(
                                dict(
                                    metadata_row,
                                    prediction_index=n,
                                    class_id=d["class_id"],
                                    prediction_box_size=gt_attributes(
                                        dict(
                                            box=d["box"],
                                            class_id=d["class_id"],
                                            semantic_tags=[],
                                        )
                                    )["box_size"],
                                    **fp_evidence(
                                        d, gt["objects"], gt["excluded"], matched
                                    ),
                                )
                            )
                    frame_records.append(
                        dict(
                            metadata_row,
                            native_cutoff=float(raw["scores"].min()),
                            native_rows=300,
                            clipped_valid_rows=len(proposals),
                            primary=values,
                            optimistic_assignment=maximum_matching(
                                gt["objects"], proposals
                            ),
                        )
                    )
            expected = (
                chosen["candidates"][candidate]["selected"]
                if group == "calibration"
                else checked["candidates"][candidate]["selected"]
            )
            require(total(primary) == expected["micro"], "V2 primary score unchanged")
            summary = summarize(primary, fps, fns, gts, position)
            summary["native_top300_cutoff"] = distribution(
                [row["native_cutoff"] for row in frame_records]
            )
            summary["native_top300_cutoff_ge_0p1_frames"] = sum(
                row["native_cutoff"] >= 0.1 for row in frame_records
            )
            candidate_rows["groups"][group] = dict(
                summary=summary,
                false_positives=fps,
                false_negatives=fns,
                ground_truth=gts,
                frames=frame_records,
            )
        report["candidates"][candidate] = candidate_rows
    write_new(output, report)
    return report


def audit(frozen, report_path, output):
    import tempfile

    report = read_json(report_path)
    require(report["freeze_sha256"] == sha256_file(frozen), "diagnostic report binding")
    with tempfile.TemporaryDirectory() as directory:
        recomputed = analyze(frozen, Path(directory) / "recomputed.json")
    require(
        recomputed["candidates"] == report["candidates"]
        and report["status"] == "PASS"
        and report["holdout_access"] is False
        and report["fresh_acceptance"] is False
        and report["runtime_promotion"] is False,
        "diagnostic complete replay",
    )
    result = dict(
        status="PASS",
        source_root=str(ROOT),
        freeze_sha256=sha256_file(frozen),
        report_sha256=sha256_file(report_path),
        source_files=len(read_json(frozen)["sources"]),
        native_raw_outputs=810,
        primary_positive_observations=1290,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "analyze", "audit"))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze(args.output)
    elif args.action == "analyze":
        result = analyze(args.freeze, args.output)
    else:
        result = audit(args.freeze, args.report, args.output)
    print(result.get("status", "PASS"))
