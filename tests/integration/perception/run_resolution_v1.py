#!/usr/bin/env python3
"""Run fixed resolutions, recompute strict development gates, then seal selection."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import resource
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import CLASSES, sha256_file
from physical_ai.perception.dataset import read_json, local_path
from physical_ai.perception.resolution_v1 import (
    SIZES,
    VECTOR,
    ResolutionDetector,
    decode,
)
from physical_ai.perception.yolox import postprocess as decode_original
from physical_ai.perception.model_screen_v2 import decode as decode_scalar
from physical_ai.perception.model_diagnostics_v1 import (
    gt_attributes,
    fn_evidence,
    native_proposals,
    strict_matching,
)
from physical_ai.perception.run import distribution
from quality_benchmark import total, relative
from quality_benchmark_v3 import measure, validate_truth
from evaluate import rates
from resolution_v1_common import (
    ROOT,
    GROUPS,
    check_freeze,
    check_numeric,
    development,
    require,
    write_new,
)


def json_detections(values):
    return [dict(class_id=d.class_id, score=d.score, box=list(d.box)) for d in values]


def run(base, size, group):
    check_numeric(base)
    if group == "regression":
        check_selection(base)
    manifest = read_json(base / "models.json")
    output = base / "runs" / str(size) / group
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    report = dict(
        schema="m10-resolution-run-v1",
        size=size,
        group=group,
        started_utc=datetime.now(timezone.utc).isoformat(),
        status="FAIL",
        freeze_sha256=sha256_file(base / "freeze.json"),
        models_sha256=sha256_file(base / "models.json"),
        numeric_sha256=sha256_file(base / "numeric.json"),
        selection_sha256=sha256_file(base / "selection.json")
        if group == "regression"
        else None,
        expected=81 * len(GROUPS[group]),
        attempted=0,
        model_valid=0,
        admitted=0,
        errors=0,
        cold_calls_excluded=0,
        rows=[],
    )
    try:
        start = time.monotonic_ns()
        backend = ResolutionDetector(
            size,
            local_path(base, manifest["models"][str(size)]["path"]),
            base / "models.json",
        )
        report["initialization_wall_ns"] = time.monotonic_ns() - start
        report["providers"] = backend.session.get_providers()
        report["provider_options"] = backend.session.get_provider_options()
        report["cpu_node_fallback_disabled"] = True
        for key, relative_path in GROUPS[group].items():
            dataset, _, _ = development(ROOT / relative_path)
            for source, frame in dataset.frames():
                row = dict(
                    dataset=key,
                    **{
                        k: source[k]
                        for k in ("scene", "frame", "source_ns", "rgb_sha256")
                    },
                    valid=False,
                    admitted=False,
                    detections=None,
                )
                report["attempted"] += 1
                before = time.monotonic_ns()
                try:
                    feed = backend.prepare(frame)
                    prepared = time.monotonic_ns()
                    raw = backend.raw(feed)
                    inferred = time.monotonic_ns()
                    detections = decode(raw)
                    complete = time.monotonic_ns()
                    cache = output / "raw" / f"{len(report['rows']):04d}.npz"
                    np.savez_compressed(cache, **raw)
                    row.update(
                        valid=True,
                        admitted=complete - before < 100_000_000,
                        detections=json_detections(detections),
                        elapsed_wall_ns=complete - before,
                        preprocess_ns=prepared - before,
                        inference_ns=inferred - prepared,
                        postprocess_ns=complete - inferred,
                        raw=str(cache.relative_to(output)),
                        raw_sha256=sha256_file(cache),
                    )
                    report["model_valid"] += 1
                    report["admitted"] += int(row["admitted"])
                except Exception:
                    row.update(
                        error=traceback.format_exc(),
                        elapsed_wall_ns=time.monotonic_ns() - before,
                    )
                    report["errors"] += 1
                report["rows"].append(row)
        report["status"] = (
            "PASS"
            if report["attempted"] == report["expected"] and not report["errors"]
            else "FAIL"
        )
    except Exception:
        report["error"] = traceback.format_exc()
    report.update(
        finished_utc=datetime.now(timezone.utc).isoformat(),
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        latency=distribution([r["elapsed_wall_ns"] for r in report["rows"]])
        if report["rows"]
        else None,
    )
    write_new(output / "run.json", report)
    return report


def blank_counts():
    return {str(c): dict(tp=0, fp=0, fn=0) for c in CLASSES}


def add(dest, source):
    for c in dest:
        for k in ("tp", "fp", "fn"):
            dest[c][k] += source[c][k]


def quality(rows):
    counts = blank_counts()
    admitted_counts = blank_counts()
    near = dict(tp=0, fp=0, fn=0)
    strata = defaultdict(
        lambda: dict(frames=0, tp=0, fp=0, fn=0, target_visible=0, target_detected=0)
    )
    coverage = {
        str(c): {s: 0 for s in ("near", "medium", "far", "occluded")} for c in CLASSES
    }
    riders = dict(visible=0, detected=0)
    sizes = defaultdict(lambda: dict(visible=0, detected=0))
    fn_buckets = defaultdict(int)
    records = []
    errors = missing = missing_riders = 0
    for scene, gt, predictions, valid, admitted, raw in rows:
        validate_truth(gt)
        result, matched, _, _, _ = measure(predictions, gt["objects"], gt["excluded"])
        check, _, used = strict_matching(predictions, gt["objects"])
        require(result == check and set(matched) == used, "primary matching identity")
        add(counts, result)
        add(
            admitted_counts,
            measure(predictions if admitted else [], gt["objects"], gt["excluded"])[0],
        )
        errors += int(not valid)
        aggregate = total(result)
        stat = strata[scene["stratum"]]
        stat["frames"] += 1
        for k in ("tp", "fp", "fn"):
            stat[k] += aggregate[k]
        visible = {(o["class_id"], o["instance_id"]) for o in gt["objects"]}
        matched_keys = {
            (gt["objects"][n]["class_id"], gt["objects"][n]["instance_id"])
            for n in matched
        }
        for actor in scene["actors"]:
            key = (actor["class_id"], actor["actor_id"] % 65536)
            missing += int(key not in visible)
            if actor["class_id"] in (1, 3):
                missing_riders += int((0, key[1]) not in visible)
            if actor["role"] == "target" and scene["target_class"] == actor["class_id"]:
                coverage[str(actor["class_id"])][scene["stratum"]] += int(
                    key in visible
                )
                stat["target_visible"] += int(key in visible)
                stat["target_detected"] += int(key in matched_keys)
        if scene["stratum"] == "near" and scene["target_class"] == 0:
            for k in near:
                near[k] += result["0"][k]
        proposals = (
            native_proposals(raw) if raw is not None and "labels" in raw else None
        )
        fn = []
        for n, obj in enumerate(gt["objects"]):
            attr = gt_attributes(obj)
            for label in (attr["box_size"], attr["person_kind"]):
                sizes[label]["visible"] += 1
                sizes[label]["detected"] += int(n in matched)
            if 13 in obj["semantic_tags"]:
                riders["visible"] += 1
                riders["detected"] += int(n in matched)
            if n not in matched and proposals is not None:
                evidence = fn_evidence(
                    obj, proposals, VECTOR[list(CLASSES).index(obj["class_id"])]
                )
                fn_buckets[evidence["bucket"]] += 1
                fn.append(dict(object=obj, attributes=attr, **evidence))
        records.append(dict(scene=scene["scene"], counts=result, false_negatives=fn))
    for s in strata.values():
        s["target_recall"] = (
            s["target_detected"] / s["target_visible"] if s["target_visible"] else None
        )
    for s in sizes.values():
        s["recall"] = s["detected"] / s["visible"]
    micro, per_class = total(counts), rates(counts)
    for v in per_class.values():
        v["f1"] = (
            2 * v["tp"] / (2 * v["tp"] + v["fp"] + v["fn"])
            if 2 * v["tp"] + v["fp"] + v["fn"]
            else 0
        )
    near["recall"] = near["tp"] / (near["tp"] + near["fn"])
    sites = len(rows) // 81
    gates = dict(
        no_model_errors=errors == 0,
        all_planned_actors_visible=missing == 0,
        all_riders_visible=missing_riders == 0,
        coverage=all(n == 3 * sites for c in coverage.values() for n in c.values())
        and riders["visible"] == 27 * sites
        and strata["negative"]["frames"] == 3 * sites,
        precision=micro["precision"] >= 0.85,
        recall=micro["recall"] >= 0.8,
        per_class_recall=all(v["recall"] >= 0.7 for v in per_class.values()),
        near_person=near["recall"] >= 0.9,
        negative_fp=strata["negative"]["fp"] / strata["negative"]["frames"] <= 1 / 3,
    )
    return dict(
        frames=len(rows),
        micro=micro,
        per_class=per_class,
        macro_f1=sum(v["f1"] for v in per_class.values()) / 6,
        minimum_class_recall=min(v["recall"] for v in per_class.values()),
        strata=dict(strata),
        near_person=near,
        riders=riders,
        gates=gates,
        absolute_quality="PASS" if all(gates.values()) else "FAIL",
        admitted_micro=total(admitted_counts),
        sizes=dict(sizes),
        fn_buckets=dict(fn_buckets),
        records=records,
    )


def score(base, size, group):
    check_freeze(base / "freeze.json")
    baseline = size == "baseline"
    report = (
        read_json(base / "baseline-index.json")[group]
        if baseline
        else read_json(base / "runs" / str(size) / group / "run.json")
    )
    if not baseline:
        require(
            report["size"] == size
            and report["group"] == group
            and report["freeze_sha256"] == sha256_file(base / "freeze.json")
            and report["models_sha256"] == sha256_file(base / "models.json")
            and report["numeric_sha256"] == sha256_file(base / "numeric.json")
            and report["providers"][0] == "CUDAExecutionProvider"
            and report["cpu_node_fallback_disabled"] is True
            and report["cold_calls_excluded"] == 0,
            "run provenance",
        )
    predictions = report if baseline else report["rows"]
    require(len(predictions) == 81 * len(GROUPS[group]), "complete score denominator")
    position = 0
    assembled, partitions = [], {}
    valid_count = admitted_count = 0
    for key, relative_path in GROUPS[group].items():
        dataset, meta, truth = development(ROOT / relative_path)
        subtotal = []
        for source, scene, gt in zip(
            dataset.manifest["frames"], meta["scenes"], truth["frames"]
        ):
            row = predictions[position]
            position += 1
            require(
                row["dataset"] == key
                and row["scene"] == source["scene"] == scene["scene"] == gt["scene"]
                and row["frame"] == source["frame"] == gt["frame"]
                and row["source_ns"] == source["source_ns"]
                and row["rgb_sha256"] == source["rgb_sha256"],
                "strict row lineage",
            )
            valid = True if baseline else row["valid"]
            admitted = row["admitted"]
            raw = None
            values = []
            if valid:
                path = (
                    ROOT / row["raw"]
                    if baseline
                    else local_path(base / "runs" / str(size) / group, row["raw"])
                )
                require(sha256_file(path) == row["raw_sha256"], "native raw cache SHA")
                with np.load(path, allow_pickle=False) as arrays:
                    raw = dict(arrays)
                values = json_detections(
                    (
                        decode_scalar(raw, "yolox", 0.35)
                        if row["decoder"] == "screen-v2"
                        else decode_original(raw["output"])
                    )
                    if baseline
                    else decode(raw)
                )
                require(
                    values == row["detections"], "raw decode/prediction exact equality"
                )
                valid_count += 1
                admitted_count += int(admitted)
                if not baseline:
                    require(
                        admitted == (row["elapsed_wall_ns"] < 100_000_000),
                        "deadline admission",
                    )
            else:
                require(
                    row["detections"] is None and row.get("error") and not admitted,
                    "error must not encode empty success",
                )
            subtotal.append((scene, gt, values, valid, admitted, raw))
        partitions[key] = quality(subtotal)
        assembled.extend(subtotal)
    if not baseline:
        require(
            (valid_count, admitted_count, len(predictions) - valid_count)
            == (report["model_valid"], report["admitted"], report["errors"])
            and report["attempted"] == report["expected"] == len(predictions)
            and report["status"]
            == ("PASS" if valid_count == len(predictions) else "FAIL"),
            "run summary denominator",
        )
    return dict(
        schema="m10-resolution-score-v1",
        group=group,
        size=size,
        freeze_sha256=sha256_file(base / "freeze.json"),
        run_sha256=sha256_file(
            base / "baseline-index.json"
            if baseline
            else base / "runs" / str(size) / group / "run.json"
        ),
        fresh_acceptance=False,
        runtime_promotion=False,
        partitions=partitions,
        **quality(assembled),
    )


def nonregression(control, candidate):
    gates = dict(
        precision=candidate["micro"]["precision"] >= control["micro"]["precision"],
        per_class=all(
            candidate["per_class"][str(c)]["recall"]
            >= control["per_class"][str(c)]["recall"]
            for c in CLASSES
        ),
        near_person=candidate["near_person"]["tp"] >= control["near_person"]["tp"],
        negatives=candidate["strata"]["negative"]["fp"]
        <= control["strata"]["negative"]["fp"],
    )
    return dict(status="PASS" if all(gates.values()) else "FAIL", gates=gates)


def rank(card):
    s = card["score"]
    return (
        card["eligible"],
        s["absolute_quality"] == "PASS",
        s["macro_f1"],
        s["minimum_class_recall"],
        s["micro"]["f1"],
        -card["size"],
    )


def selection_from_scores(base):
    scores = {
        s: read_json(base / f"selection-{s}-score.json") for s in ("baseline", *SIZES)
    }
    protocol = read_json(ROOT / "profiles/perception-quality-protocol-v4.json")
    cards = {}
    for size in (960, 1280):
        s = scores[size]
        rel = relative(scores["baseline"], s, protocol)
        non = nonregression(scores[640], s)
        sites = all(v["absolute_quality"] == "PASS" for v in s["partitions"].values())
        cards[size] = dict(
            size=size,
            score=s,
            relative=rel,
            nonregression640=non,
            all_sites_absolute=sites,
            eligible=s["absolute_quality"] == "PASS"
            and sites
            and rel["status"] == non["status"] == "PASS",
        )
    selected = max(cards.values(), key=rank)["size"]
    return dict(
        schema="m10-resolution-selection-v1",
        selected=selected,
        eligible_for_fresh_test=cards[selected]["eligible"],
        cards={
            str(k): {n: v for n, v in c.items() if n != "score"}
            for k, c in cards.items()
        },
        score_sha256={
            str(s): sha256_file(base / f"selection-{s}-score.json") for s in scores
        },
        freeze_sha256=sha256_file(base / "freeze.json"),
        runtime_promotion=False,
        holdout_access=False,
    )


def nominate(base):
    result = selection_from_scores(base)
    result["created_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(base / "selection.json", result)
    return result


def check_selection(base):
    selection = read_json(base / "selection.json")
    require(
        {k: v for k, v in selection.items() if k != "created_utc"}
        == selection_from_scores(base),
        "sealed nomination score replay",
    )
    return selection


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("run", "score", "nominate"))
    p.add_argument("base", type=Path)
    p.add_argument("--size", choices=("baseline", *map(str, SIZES)))
    p.add_argument("--group", choices=GROUPS)
    a = p.parse_args()
    size = int(a.size) if a.size and a.size != "baseline" else a.size
    if a.command == "run":
        r = run(a.base, size, a.group)
    elif a.command == "score":
        r = score(a.base, size, a.group)
        write_new(a.base / f"{a.group}-{size}-score.json", r)
    else:
        r = nominate(a.base)
    print(
        {
            k: r.get(k)
            for k in (
                "status",
                "size",
                "group",
                "absolute_quality",
                "micro",
                "selected",
                "eligible_for_fresh_test",
            )
        }
    )
    if a.command == "run" and r["status"] != "PASS":
        sys.exit(1)
