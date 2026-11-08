#!/usr/bin/env python3
"""Freeze, independently score, and nominate one offline perception experiment."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import MODEL_SHA256, Detection, sha256_file, uint
from physical_ai.perception.dataset import RgbDataset, read_json
from evaluate import counts, overlap, rates, valid_box

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-quality-plan-v1.json"
PROTOCOL = ROOT / "profiles/perception-quality-protocol-v1.json"
CLASSES = (0, 1, 2, 3, 5, 7)


def write_new(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def check_freeze(path):
    frozen = read_json(path)
    require(
        frozen["schema"] == "m10-quality-freeze-v1"
        and frozen["model_sha256"] == MODEL_SHA256,
        "freeze identity",
    )
    require(
        frozen["plan_sha256"] == sha256_file(PLAN)
        and frozen["protocol_sha256"] == sha256_file(PROTOCOL),
        "plan/protocol changed",
    )
    for source, digest in frozen["sources"].items():
        require(
            sha256_file(ROOT / source) == digest,
            f"frozen implementation changed: {source}",
        )
    return frozen


def validate_protocol():
    p = read_json(PROTOCOL)
    require(
        p["schema"] == "m10-quality-protocol-v1"
        and p["score_threshold"] == 0.35
        and p["minimum_visible_pixels"] == 25
        and p["minimum_box_side"] == 4
        and p["candidate_ids"] == ["vehicle-nms-v1", "center-refine-v1"]
        and p["vehicle_nms"] == dict(classes=[2, 5, 7], iou_threshold=0.75)
        and p["center_refine"]
        == dict(
            crop_xywh=[160, 96, 320, 192],
            scale=2,
            crop_edge_margin_pixels=2,
            same_class_nms_iou=0.5,
        ),
        "candidate descriptor/executable drift",
    )
    require(
        p["coverage"]["cases_per_partition"] == 81
        and all(
            p["relative_promotion"][k] == 0
            for k in (
                "micro_recall_drop_max",
                "per_class_recall_drop_max",
                "far_and_occluded_recall_drop_max",
                "near_person_tp_drop_max",
                "negative_fp_increase_max",
            )
        ),
        "gate descriptor/executable drift",
    )


def freeze(output):
    validate_protocol()
    files = sorted((ROOT / "physical_ai/perception").glob("*.py"))
    files += sorted((ROOT / "tests/integration/perception").glob("*quality*.py"))
    files += [
        ROOT / "tests/integration/perception/evaluate.py",
        ROOT / "tests/integration/perception/prepare_dataset.py",
    ]
    value = dict(
        schema="m10-quality-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        model_sha256=MODEL_SHA256,
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in files},
    )
    write_new(output, value)
    return value


def total(metrics):
    t = {k: sum(v[k] for v in metrics.values()) for k in ("tp", "fp", "fn")}
    tp, fp, fn = t["tp"], t["fp"], t["fn"]
    t.update(
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
        f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    )
    return t


def matched_objects(detections, truth):
    used = set()
    for d in sorted(detections, key=lambda d: -d["score"]):
        candidates = [
            (overlap(d["box"], g["box"]), n)
            for n, g in enumerate(truth)
            if n not in used and d["class_id"] == g["class_id"]
        ]
        best = max(candidates, default=(0, -1), key=lambda x: (x[0], -x[1]))
        if best[0] >= 0.5:
            used.add(best[1])
    return {(truth[n]["class_id"], truth[n]["instance_id"]) for n in used}


def score(dataset_dir, run_path, freeze_path):
    frozen = check_freeze(freeze_path)
    protocol, plan = read_json(PROTOCOL), read_json(PLAN)
    meta = read_json(dataset_dir / "benchmark.json")
    seal = read_json(dataset_dir / "benchmark-seal.json")
    truth = read_json(dataset_dir / "evaluation-only-gt.json")
    dataset = RgbDataset(dataset_dir / "rgb.json")
    list(dataset.frames())
    run = read_json(run_path)
    partition = meta["partition"]
    require(
        seal["schema"] == "m10-quality-data-seal-v1"
        and seal["partition"] == partition
        and run["dataset_seal_sha256"]
        == sha256_file(dataset_dir / "benchmark-seal.json")
        and seal["metadata_sha256"] == sha256_file(dataset_dir / "benchmark.json")
        and seal["truth_sha256"] == sha256_file(dataset_dir / "evaluation-only-gt.json")
        and seal["rgb_manifest_sha256"] == sha256_file(dataset_dir / "rgb.json")
        and seal["plan_sha256"] == frozen["plan_sha256"],
        "dataset seal changed",
    )
    if partition == "holdout":
        require(
            run["selection_sha256"]
            == seal["selection_sha256"]
            == meta["selection_sha256"]
            and run["selection_sha256"] is not None,
            "holdout selection binding",
        )
    cases = plan["partitions"][partition]["cases"]
    require(
        meta["schema"] == "m10-quality-dataset-v1"
        and meta["plan_sha256"] == frozen["plan_sha256"],
        "dataset plan",
    )
    require(
        meta["rgb_manifest_sha256"]
        == sha256_file(dataset_dir / "rgb.json")
        == run["dataset_sha256"]
        == truth["rgb_manifest_sha256"],
        "RGB hash",
    )
    require(
        meta["truth_sha256"] == sha256_file(dataset_dir / "evaluation-only-gt.json")
        and truth["capture_sha256"]
        == meta["capture_sha256"]
        == dataset.manifest["capture_sha256"],
        "truth hash",
    )
    require(
        run["schema"] == "m10-quality-run-v1"
        and run["freeze_sha256"] == sha256_file(freeze_path)
        and run["protocol_sha256"] == frozen["protocol_sha256"]
        and run["model_sha256"] == MODEL_SHA256
        and run["phase"] == partition
        and run["candidate"] in ["baseline"] + protocol["candidate_ids"],
        "run provenance",
    )
    require(
        run["providers"][0] == "CUDAExecutionProvider"
        and run["cpu_node_fallback_disabled"] is True,
        "CUDA provenance",
    )
    require(
        len(cases)
        == len(meta["scenes"])
        == len(truth["frames"])
        == len(run["rows"])
        == len(dataset.manifest["frames"])
        == run["expected"]
        == run["attempted"]
        == 81,
        "quality denominator",
    )
    totals = {str(k): dict(tp=0, fp=0, fn=0) for k in CLASSES}
    admitted_totals = {str(k): dict(tp=0, fp=0, fn=0) for k in CLASSES}
    strata = defaultdict(
        lambda: dict(frames=0, tp=0, fp=0, fn=0, target_visible=0, target_detected=0)
    )
    weather = defaultdict(lambda: dict(frames=0, tp=0, fp=0, fn=0))
    visible_primary = {str(k): 0 for k in CLASSES}
    near_person = dict(tp=0, fp=0, fn=0)
    n_valid = n_admitted = n_errors = 0
    records = []
    for case, metadata, source, gt, row in zip(
        cases, meta["scenes"], dataset.manifest["frames"], truth["frames"], run["rows"]
    ):
        require(
            case["id"]
            == metadata["scene"]
            == source["scene"]
            == gt["scene"]
            == row["scene"],
            "scene identity/order",
        )
        require(
            metadata["stratum"] == case["stratum"]
            and metadata["weather"] == case["weather"]
            and metadata["target_class"] == case["target_class"],
            "scene strata",
        )
        require(
            len(metadata["actors"]) == len(case["actors"])
            and all(
                all(actual[k] == expected[k] for k in ("blueprint", "class_id", "role"))
                for actual, expected in zip(metadata["actors"], case["actors"])
            ),
            "planned actor lineage",
        )
        require(
            source["frame"] == gt["frame"] == row["frame"]
            and source["source_ns"] == row["source_ns"]
            and source["rgb_sha256"] == row["rgb_sha256"],
            "camera provenance",
        )
        seen = set()
        for obj in gt["objects"] + gt["excluded"]:
            require(
                obj["class_id"] in CLASSES
                and type(obj["class_id"]) is int
                and valid_box(obj["box"])
                and uint(obj["visible_pixels"], positive=True)
                and uint(obj["instance_id"]),
                "GT payload",
            )
        for obj in gt["objects"]:
            key = (obj["class_id"], obj["instance_id"])
            require(
                key not in seen
                and obj["visible_pixels"] >= 25
                and min(obj["box"][2] - obj["box"][0], obj["box"][3] - obj["box"][1])
                >= 4,
                "GT duplicate/support",
            )
            seen.add(key)
        require(
            type(row["model_valid"]) is bool
            and type(row["admitted"]) is bool
            and uint(row["elapsed_wall_ns"]),
            "result validity/timing type",
        )
        detected = row["detections"] if row["model_valid"] else []
        if row["model_valid"]:
            require(
                isinstance(detected, list)
                and len(detected) <= 100
                and row["expires_ns"] == source["source_ns"] + 100_000_000,
                "result count/expiry",
            )
            for d in detected:
                require(set(d) == {"class_id", "score", "box"}, "detection fields")
                Detection(d["class_id"], d["score"], tuple(d["box"])).validate()
            stages = [
                row[k] for k in ("preprocess_ns", "inference_ns", "postprocess_ns")
            ]
            require(
                all(uint(v) for v in stages) and sum(stages) <= row["elapsed_wall_ns"],
                "stage timing",
            )
            require(
                row["admitted"] == (row["elapsed_wall_ns"] < 100_000_000),
                "late result admitted",
            )
            n_valid += 1
            n_admitted += row["admitted"]
        else:
            require(
                row["detections"] is None and not row["admitted"] and row.get("error"),
                "error encoded as empty scene",
            )
            n_errors += 1
        raw = counts(detected, gt["objects"])
        available = counts(detected if row["admitted"] else [], gt["objects"])
        for c in totals:
            for k in ("tp", "fp", "fn"):
                totals[c][k] += raw[c][k]
                admitted_totals[c][k] += available[c][k]
        aggregate = total(raw)
        group = strata[case["stratum"]]
        lighting = weather[case["weather"]]
        group["frames"] += 1
        lighting["frames"] += 1
        for k in ("tp", "fp", "fn"):
            group[k] += aggregate[k]
            lighting[k] += aggregate[k]
        matched = matched_objects(detected, gt["objects"])
        for actor in metadata["actors"]:
            key = (actor["class_id"], actor["actor_id"] % 65536)
            require(actor["included"] == (key in seen), "visible actor binding")
            if (
                actor["role"] == "target"
                and case["target_class"] is not None
                and actor["class_id"] == case["target_class"]
            ):
                group["target_visible"] += int(key in seen)
                group["target_detected"] += int(key in matched)
                visible_primary[str(actor["class_id"])] += int(key in seen)
        if case["stratum"] == "near" and case["target_class"] == 0:
            for k in near_person:
                near_person[k] += raw["0"][k]
        records.append(
            dict(
                scene=case["id"],
                stratum=case["stratum"],
                weather=case["weather"],
                counts=raw,
                **{k: aggregate[k] for k in ("tp", "fp", "fn")},
            )
        )
    require(
        (n_valid, n_admitted, n_errors)
        == (run["model_valid"], run["admitted"], run["errors"]),
        "summary denominator",
    )
    require(run["status"] == ("PASS" if not n_errors else "FAIL"), "run status")
    for values in strata.values():
        values["target_recall"] = (
            values["target_detected"] / values["target_visible"]
            if values["target_visible"]
            else None
        )
    micro = total(totals)
    class_rates = rates(totals)
    near_rate = (
        near_person["tp"] / (near_person["tp"] + near_person["fn"])
        if near_person["tp"] + near_person["fn"]
        else None
    )
    coverage = protocol["coverage"]
    absolute = protocol["absolute_quality"]
    gates = dict(
        coverage=all(
            v >= coverage["minimum_visible_target_cases_per_class"]
            for v in visible_primary.values()
        )
        and set(coverage["all_strata_required"]) == set(strata)
        and strata["negative"]["frames"] == coverage["negative_cases"],
        no_model_errors=n_errors == 0,
        precision=micro["precision"] is not None
        and micro["precision"] >= absolute["micro_precision_min"],
        recall=micro["recall"] is not None
        and micro["recall"] >= absolute["micro_recall_min"],
        per_class_recall=all(
            x["recall"] is not None and x["recall"] >= absolute["per_class_recall_min"]
            for x in class_rates.values()
        ),
        near_person=near_rate is not None
        and near_rate >= absolute["near_person_recall_min"],
        negative_fp=strata["negative"]["fp"] / strata["negative"]["frames"]
        <= absolute["negative_fp_per_frame_max"],
    )
    return dict(
        schema="m10-quality-score-v1",
        audit="PASS",
        partition=partition,
        candidate=run["candidate"],
        absolute_quality="PASS" if all(gates.values()) else "FAIL",
        gates=gates,
        quality_scope=protocol["scope"],
        micro=micro,
        per_class=class_rates,
        admitted_micro=total(admitted_totals),
        strata=dict(strata),
        weather=dict(weather),
        near_person=dict(**near_person, recall=near_rate),
        visible_primary_cases=visible_primary,
        records=records,
        run_sha256=sha256_file(run_path),
        metadata_sha256=sha256_file(dataset_dir / "benchmark.json"),
        freeze_sha256=sha256_file(freeze_path),
    )


def relative(baseline, candidate, protocol):
    limits = protocol["relative_promotion"]

    def value(v):
        return v if v is not None else -1

    gates = dict(
        precision=value(candidate["micro"]["precision"])
        - value(baseline["micro"]["precision"])
        >= limits["precision_gain_min"],
        recall=value(candidate["micro"]["recall"])
        >= value(baseline["micro"]["recall"]),
        per_class=all(
            value(candidate["per_class"][str(k)]["recall"])
            >= value(baseline["per_class"][str(k)]["recall"])
            for k in CLASSES
        ),
        far_occluded=all(
            value(candidate["strata"][s]["target_recall"])
            >= value(baseline["strata"][s]["target_recall"])
            for s in ("far", "occluded")
        ),
        near_person=candidate["near_person"]["tp"] >= baseline["near_person"]["tp"],
        negatives=candidate["strata"]["negative"]["fp"]
        <= baseline["strata"]["negative"]["fp"],
    )
    return dict(status="PASS" if all(gates.values()) else "FAIL", gates=gates)


def nominate(score_paths, freeze_path, output):
    check_freeze(freeze_path)
    protocol = read_json(PROTOCOL)
    scores = {}
    for path in score_paths:
        r = read_json(path)
        require(
            r["partition"] == "development"
            and r["freeze_sha256"] == sha256_file(freeze_path)
            and r["audit"] == "PASS",
            "nomination uses development only",
        )
        require(r["candidate"] not in scores, "duplicate candidate score")
        scores[r["candidate"]] = r
    require(
        set(scores) == {"baseline", *protocol["candidate_ids"]}, "candidate denominator"
    )
    comparisons = {
        c: relative(scores["baseline"], scores[c], protocol)
        for c in protocol["candidate_ids"]
    }

    def key(c):
        m = scores[c]["micro"]
        return (
            -(comparisons[c]["status"] == "PASS"),
            -(m["f1"] or 0),
            -(m["recall"] or 0),
            -(m["precision"] or 0),
            c,
        )

    selected = sorted(protocol["candidate_ids"], key=key)[0]
    value = dict(
        schema="m10-quality-selection-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        freeze_sha256=sha256_file(freeze_path),
        selected=selected,
        development_relative=comparisons,
        development_absolute={c: scores[c]["absolute_quality"] for c in scores},
        score_files={str(p): sha256_file(p) for p in score_paths},
        runtime_promotion=False,
        note="One development-ranked nominee, including when gates fail. Holdout is diagnostic unless all gates pass; no retuning after selection.",
    )
    write_new(output, value)
    return value


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("output", type=Path)
    e = sub.add_parser("score")
    e.add_argument("dataset", type=Path)
    e.add_argument("run", type=Path)
    e.add_argument("freeze", type=Path)
    e.add_argument("output", type=Path)
    s = sub.add_parser("select")
    s.add_argument("freeze", type=Path)
    s.add_argument("output", type=Path)
    s.add_argument("scores", nargs="+", type=Path)
    a = p.parse_args()
    if a.command == "freeze":
        r = freeze(a.output)
    elif a.command == "score":
        r = score(a.dataset, a.run, a.freeze)
        write_new(a.output, r)
    else:
        r = nominate(a.scores, a.freeze, a.output)
    print(json.dumps(r, indent=2))
