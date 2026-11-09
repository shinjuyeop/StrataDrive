#!/usr/bin/env python3
"""Prospective V6 scoring with Rider labels, strict gates and explicit diagnostics."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import Detection, sha256_file, uint
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.quality_candidates_v6 import (
    CANDIDATES,
    MODELS,
    INPUT_PROFILE,
)
from evaluate import rates
from quality_benchmark import CLASSES, relative, total
from quality_v6_common import (
    PLAN,
    PROTOCOL,
    EXCLUSION,
    check_freeze,
    freeze,
    require,
    write_new,
)


from quality_benchmark_v3 import measure, validate_truth
from prepare_quality_v6 import assess_visibility


def score(data, run_path, frozen_path):
    frozen = check_freeze(frozen_path)
    protocol, plan = read_json(PROTOCOL), read_json(PLAN)
    dataset = RgbDataset(data / "rgb.json")
    list(dataset.frames())
    meta, truth, seal, run = [
        read_json(p)
        for p in (
            data / "benchmark.json",
            data / "evaluation-only-gt.json",
            data / "benchmark-seal.json",
            run_path,
        )
    ]
    partition = meta["partition"]
    require(
        seal["schema"] == "m10-quality-data-seal-v6"
        and seal["partition"] == partition
        and meta["schema"] == "m10-quality-dataset-v6"
        and truth["schema"] == "m10-rider-visible-gt-v2"
        and truth["partition"] == partition
        and seal["metadata_sha256"] == sha256_file(data / "benchmark.json")
        and seal["truth_sha256"]
        == meta["truth_sha256"]
        == sha256_file(data / "evaluation-only-gt.json")
        and seal["rgb_manifest_sha256"]
        == meta["rgb_manifest_sha256"]
        == truth["rgb_manifest_sha256"]
        == sha256_file(data / "rgb.json")
        and seal["capture_sha256"]
        == meta["capture_sha256"]
        == truth["capture_sha256"]
        == dataset.manifest["capture_sha256"]
        and seal["plan_sha256"] == meta["plan_sha256"] == frozen["plan_sha256"]
        and seal["protocol_sha256"]
        == meta["protocol_sha256"]
        == frozen["protocol_sha256"]
        and seal["exclusion_sha256"]
        == meta["exclusion_sha256"]
        == frozen["exclusion_sha256"]
        and seal["visibility_sha256"] == sha256_file(data / "visibility.json"),
        "v6 dataset seal",
    )
    require(
        run["schema"] == "m10-quality-run-v6"
        and run["phase"] == partition
        and run["candidate"] in CANDIDATES
        and run["model_sha256"] == MODELS[run["candidate"]]
        and run["input_profile"] == INPUT_PROFILE
        and run["freeze_sha256"] == sha256_file(frozen_path)
        and run["protocol_sha256"] == frozen["protocol_sha256"]
        and run["dataset_sha256"] == sha256_file(data / "rgb.json")
        and run["dataset_seal_sha256"] == sha256_file(data / "benchmark-seal.json")
        and run["providers"][0] == "CUDAExecutionProvider"
        and run["cpu_node_fallback_disabled"] is True,
        "v6 run provenance",
    )
    require(
        run["selection_sha256"] == seal["selection_sha256"] == meta["selection_sha256"]
        and (
            (partition == "development" and run["selection_sha256"] is None)
            or (partition == "holdout" and run["selection_sha256"] is not None)
        ),
        "v6 selection binding",
    )
    cases = plan["partitions"][partition]["cases"]
    require(
        len(cases)
        == len(meta["scenes"])
        == len(truth["frames"])
        == len(dataset.manifest["frames"])
        == len(run["rows"])
        == run["expected"]
        == run["attempted"]
        == 81,
        "v6 denominator",
    )
    consumed = set(read_json(EXCLUSION)["rgb_sha256"])
    require(
        not consumed & {s["rgb_sha256"] for s in dataset.manifest["frames"]},
        "consumed v1 image",
    )
    totals = [{str(c): dict(tp=0, fp=0, fn=0) for c in CLASSES} for _ in range(3)]
    strata = defaultdict(
        lambda: dict(frames=0, tp=0, fp=0, fn=0, target_visible=0, target_detected=0)
    )
    weather = defaultdict(lambda: dict(frames=0, tp=0, fp=0, fn=0))
    coverage = {
        str(c): {s: 0 for s in ("near", "medium", "far", "occluded")} for c in CLASSES
    }
    riders = dict(visible=0, detected=0, excluded=0)
    near_person = dict(tp=0, fp=0, fn=0)
    valid = admitted = errors = ignored_count = 0
    records = []
    for case, metadata, source, gt, row in zip(
        cases, meta["scenes"], dataset.manifest["frames"], truth["frames"], run["rows"]
    ):
        require(
            case["id"]
            == metadata["scene"]
            == source["scene"]
            == gt["scene"]
            == row["scene"]
            and source["frame"] == gt["frame"] == row["frame"]
            and source["source_ns"] == row["source_ns"]
            and source["rgb_sha256"] == row["rgb_sha256"]
            and all(
                case[k] == metadata[k] for k in ("stratum", "weather", "target_class")
            )
            and len(case["actors"]) == len(metadata["actors"]),
            "v6 scene/source identity",
        )
        validate_truth(gt)
        require(
            type(row["model_valid"]) is bool
            and type(row["admitted"]) is bool
            and uint(row["elapsed_wall_ns"]),
            "v6 validity/timing type",
        )
        predictions = row["detections"] if row["model_valid"] else []
        if row["model_valid"]:
            require(
                isinstance(predictions, list)
                and len(predictions) <= 100
                and row["expires_ns"] == source["source_ns"] + 100_000_000,
                "v6 result count/expiry",
            )
            for d in predictions:
                require(set(d) == {"class_id", "score", "box"}, "v6 detection fields")
                Detection(d["class_id"], d["score"], tuple(d["box"])).validate()
            stages = [
                row[k] for k in ("preprocess_ns", "inference_ns", "postprocess_ns")
            ]
            require(
                all(uint(v) for v in stages)
                and sum(stages) <= row["elapsed_wall_ns"]
                and row["admitted"] == (row["elapsed_wall_ns"] < 100_000_000),
                "v6 stage/admission",
            )
            valid += 1
            admitted += row["admitted"]
        else:
            require(
                row["detections"] is None and row.get("error") and not row["admitted"],
                "error encoded as empty",
            )
            errors += 1
        raw, matched, diagnostic, ignored, covered = measure(
            predictions, gt["objects"], gt["excluded"]
        )
        available = measure(
            predictions if row["admitted"] else [], gt["objects"], gt["excluded"]
        )[0]
        for dest, observed in zip(totals, (raw, available, diagnostic)):
            for c in dest:
                for k in ("tp", "fp", "fn"):
                    dest[c][k] += observed[c][k]
        aggregate = total(raw)
        for group in (strata[case["stratum"]], weather[case["weather"]]):
            group["frames"] += 1
            for k in ("tp", "fp", "fn"):
                group[k] += aggregate[k]
        all_keys = {(o["class_id"], o["instance_id"]) for o in gt["objects"]}
        matched_keys = {
            (gt["objects"][n]["class_id"], gt["objects"][n]["instance_id"])
            for n in matched
        }
        for expected, actual in zip(case["actors"], metadata["actors"]):
            require(
                all(
                    expected[k] == actual[k] for k in ("class_id", "blueprint", "role")
                ),
                "planned actor lineage",
            )
            key = (actual["class_id"], actual["actor_id"] % 65536)
            require(
                actual["included"] == (key in all_keys), "primary visibility binding"
            )
            if (
                actual["role"] == "target"
                and case["target_class"] == actual["class_id"]
            ):
                coverage[str(actual["class_id"])][case["stratum"]] += int(
                    key in all_keys
                )
                strata[case["stratum"]]["target_visible"] += int(key in all_keys)
                strata[case["stratum"]]["target_detected"] += int(key in matched_keys)
        for n, obj in enumerate(gt["objects"]):
            if 13 in obj["semantic_tags"]:
                riders["visible"] += 1
                riders["detected"] += int(n in matched)
        riders["excluded"] += sum(13 in o["semantic_tags"] for o in gt["excluded"])
        if case["stratum"] == "near" and case["target_class"] == 0:
            for k in near_person:
                near_person[k] += raw["0"][k]
        ignored_count += len(ignored)
        records.append(
            dict(
                scene=case["id"],
                stratum=case["stratum"],
                weather=case["weather"],
                counts=raw,
                excluded=len(gt["excluded"]),
                small_predictions_ignored_diagnostic=len(ignored),
                covered_but_iou_missed=[
                    dict(gt["objects"][n]) for n in sorted(covered)
                ],
            )
        )
    require(
        (valid, admitted, errors)
        == (run["model_valid"], run["admitted"], run["errors"])
        and run["status"] == ("PASS" if not errors else "FAIL"),
        "v6 run summary",
    )
    micro, per_class = total(totals[0]), rates(totals[0])
    for s in strata.values():
        s["target_recall"] = (
            s["target_detected"] / s["target_visible"] if s["target_visible"] else None
        )
    near_person["recall"] = (
        near_person["tp"] / (near_person["tp"] + near_person["fn"])
        if near_person["tp"] + near_person["fn"]
        else None
    )
    visibility = assess_visibility(cases, meta["scenes"], truth["frames"])
    saved_visibility = read_json(data / "visibility.json")
    require(
        all(saved_visibility[k] == v for k, v in visibility.items()),
        "actual visibility seal",
    )
    absolute, cov = protocol["absolute_quality"], protocol["coverage"]
    gates = dict(
        coverage=all(
            sum(v.values()) >= cov["minimum_visible_target_cases_per_class"]
            and all(
                n >= cov["minimum_visible_cases_per_class_stratum"] for n in v.values()
            )
            for v in coverage.values()
        )
        and riders["visible"] >= cov["minimum_rider_instances"]
        and set(strata) == set(cov["all_strata_required"])
        and strata["negative"]["frames"] == cov["negative_cases"],
        all_planned_actors_visible=visibility["gates"]["all_planned_actors_visible"],
        all_two_wheeler_riders_visible=visibility["gates"][
            "all_two_wheeler_riders_visible"
        ],
        no_model_errors=errors == 0,
        precision=micro["precision"] is not None
        and micro["precision"] >= absolute["micro_precision_min"],
        recall=micro["recall"] is not None
        and micro["recall"] >= absolute["micro_recall_min"],
        per_class_recall=all(
            v["recall"] is not None and v["recall"] >= absolute["per_class_recall_min"]
            for v in per_class.values()
        ),
        near_person=near_person["recall"] is not None
        and near_person["recall"] >= absolute["near_person_recall_min"],
        negative_fp=strata["negative"]["fp"] / strata["negative"]["frames"]
        <= absolute["negative_fp_per_frame_max"],
    )
    return dict(
        schema="m10-quality-score-v6",
        audit="PASS",
        partition=partition,
        candidate=run["candidate"],
        absolute_quality="PASS" if all(gates.values()) else "FAIL",
        gates=gates,
        micro=micro,
        per_class=per_class,
        admitted_micro=total(totals[1]),
        small_ignore_diagnostic_micro=total(totals[2]),
        small_predictions_ignored_diagnostic=ignored_count,
        strata=dict(strata),
        weather=dict(weather),
        primary_coverage=coverage,
        visibility=visibility,
        riders=riders,
        near_person=near_person,
        records=records,
        run_sha256=sha256_file(run_path),
        metadata_sha256=sha256_file(data / "benchmark.json"),
        freeze_sha256=sha256_file(frozen_path),
    )


def nominate(paths, frozen_path, output):
    check_freeze(frozen_path)
    scores = [read_json(p) for p in paths]
    require(
        len(scores) == 3
        and {s["candidate"] for s in scores} == set(CANDIDATES)
        and all(
            s["schema"] == "m10-quality-score-v6"
            and s["partition"] == "development"
            and s["audit"] == "PASS"
            and s["freeze_sha256"] == sha256_file(frozen_path)
            for s in scores
        )
        and len({s["metadata_sha256"] for s in scores}) == 1,
        "v6 nomination provenance/dataset",
    )
    by_id = {s["candidate"]: s for s in scores}
    comparisons = {
        c: relative(by_id["baseline"], by_id[c], read_json(PROTOCOL))
        for c in CANDIDATES[1:]
    }

    def rank(c):
        m = by_id[c]["micro"]
        return (
            -(comparisons[c]["status"] == "PASS"),
            -(m["f1"] or 0),
            -(m["recall"] or 0),
            -(m["precision"] or 0),
            c,
        )

    result = dict(
        schema="m10-quality-selection-v6",
        created_utc=datetime.now(timezone.utc).isoformat(),
        freeze_sha256=sha256_file(frozen_path),
        metadata_sha256=scores[0]["metadata_sha256"],
        selected=sorted(CANDIDATES[1:], key=rank)[0],
        development_relative=comparisons,
        development_absolute={c: by_id[c]["absolute_quality"] for c in CANDIDATES},
        score_files={str(p): sha256_file(p) for p in paths},
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("output", type=Path)
    e = sub.add_parser("score")
    for name in ("data", "run", "freeze", "output"):
        e.add_argument(name, type=Path)
    n = sub.add_parser("select")
    for name in ("freeze", "output"):
        n.add_argument(name, type=Path)
    n.add_argument("scores", nargs="+", type=Path)
    a = parser.parse_args()
    if a.command == "freeze":
        r = freeze(a.output)
    elif a.command == "score":
        r = score(a.data, a.run, a.freeze)
        write_new(a.output, r)
    else:
        r = nominate(a.scores, a.freeze, a.output)
    print({k: r.get(k) for k in ("schema", "absolute_quality", "micro", "selected")})
