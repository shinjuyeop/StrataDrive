"""Freeze and execute the single location-101 evaluation of the development-qualified bundle."""

import argparse
from pathlib import Path

from m10_capture_fresh_quality import (
    BASE,
    PROBE,
    PYTHON,
    ROOT,
    TESTS,
    prepared_for_current_plan,
)
from m10_collect_occlusion_transfer import capture_scenes
from m10_verify_parking_candidate import EVIDENCE, verify, sha
from fresh_quality_2k_plan import validate_retained
from fresh_quality_2k_review import read, review, write
from fresh_quality_2k_score import PROTOCOL, predict, score
from parking_holdout_score import predict_candidate, replay_candidate
from quality_benchmark import relative
from quality_benchmark_v3 import measure

SERIES = ROOT / "docs/test-plan/evidence/m10_parking_holdout_v1"
BUNDLE = ROOT / read(EVIDENCE / "development-freeze.json")["local_bundle"]
RUN = BASE / "runs/evaluation-holdout-01"
DEV = BASE / "runs/evaluation-development-01"
SMOKE = ROOT / "build/m10-parking-holdout-v1/development-replay"


def declaration():
    model = verify(BUNDLE)
    parent = read(BASE / "freeze.json")
    for name, expected in parent["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"original capture or baseline dependency changed: {name}")
    plan = validate_retained(BASE / "plan")
    if plan["selected"]["holdout"]["spawn_index"] != 101:
        raise ValueError("wrong evaluation site")
    prep = {}
    for part in ("development", "holdout"):
        accepted = [
            p
            for p in sorted(
                (BASE / "runs").glob(f"preparation-{part}-*/visibility.json")
            )
            if prepared_for_current_plan(p, part)
        ]
        if not accepted:
            raise ValueError(f"missing passing preparation: {part}")
        prep[part] = sha(accepted[-1])
    dev_score = replay_candidate(DEV, BUNDLE, SMOKE)
    if (
        dev_score != read(EVIDENCE / "selected/score.json")
        or dev_score["absolute_quality"] != "PASS"
    ):
        raise ValueError("development score reproduction failed")
    preds = read(SMOKE / "predictions.json")["rows"]
    selected = read(EVIDENCE / "selected/predictions.json")
    truth = read(DEV / "evaluation-only-gt.json")["frames"]
    max_coordinate = max_score = 0.0
    for a, b, g in zip(preds, selected, truth, strict=True):
        actual, expected = a["detections"], b["detections"]
        if (
            not a["valid"]
            or a["rgb_sha256"] != b["rgb_sha256"]
            or not a["scene"] == b["scene"] == g["scene"]
            or [v["class_id"] for v in actual] != [v["class_id"] for v in expected]
            or measure(actual, g["objects"], g["excluded"])[:2]
            != measure(expected, g["objects"], g["excluded"])[:2]
        ):
            raise ValueError(
                "development frame detections or matched instances changed"
            )
        for det, ref in zip(actual, expected, strict=True):
            max_coordinate = max(
                max_coordinate,
                *(abs(x - y) for x, y in zip(det["box"], ref["box"], strict=True)),
            )
            max_score = max(max_score, abs(det["score"] - ref["score"]))
    rel = relative(score(DEV, "baseline"), dev_score, read(PROTOCOL))
    if (
        rel != read(EVIDENCE / "selected/result.json")["relative"]
        or rel["status"] != "PASS"
    ):
        raise ValueError("development relative comparison changed")
    return dict(
        site=101,
        partition="holdout",
        planned_frames=81,
        model_sha256=model,
        manifest_sha256=sha(BUNDLE / "manifest.json"),
        development_freeze_sha256=sha(EVIDENCE / "development-freeze.json"),
        capture_freeze_sha256=sha(BASE / "freeze.json"),
        plan_sha256=sha(BASE / "plan/evaluation.json"),
        preparation=prep,
        development_numeric_difference=dict(
            max_box_coordinate=max_coordinate, max_score=max_score
        ),
        development_replay_sha256=sha(SMOKE / "predictions.json"),
        files={
            str(p.relative_to(ROOT)): sha(p)
            for p in (
                Path(__file__).resolve(),
                ROOT / "tools/m10_collect_occlusion_transfer.py",
                TESTS / "parking_holdout_score.py",
            )
        },
        decision="All original absolute and paired YOLOX-S relative gates on the full denominator. Single acquisition. No retuning on this partition.",
    )


def capture():
    if declaration() != read(SERIES / "nomination.json"):
        raise ValueError("prospective nomination changed")
    if any((BASE / "runs").glob("evaluation-holdout-*/dataset/rgb/*.bgra.z")):
        raise ValueError("holdout already acquired")
    plan = BASE / "plan/evaluation.json"
    capture_scenes(
        RUN,
        "Town04_Opt",
        [
            PYTHON,
            PROBE,
            "--port",
            "2400",
            "--plan",
            plan,
            "--output",
            RUN / "dataset",
            "--partition",
            "holdout",
        ],
        acquisition=dict(
            case=RUN.name,
            phase="evaluation",
            partition="holdout",
            plan_sha256=sha(plan),
            freeze_sha256=sha(BASE / "freeze.json"),
            selection_sha256=sha(SERIES / "nomination.json"),
        ),
        timeout=900,
    )
    if review(RUN)["status"] != "PASS":
        raise ValueError("holdout capture visibility failed")


def adjudicate():
    if declaration() != read(SERIES / "nomination.json"):
        raise ValueError("prospective nomination changed")
    server = read(RUN / "server.json")
    cap = read(RUN / "dataset/capture.json")
    vis = read(RUN / "visibility.json")
    if (
        cap["site"] != 101
        or cap["partition"] != "holdout"
        or cap["phase"] != "evaluation"
        or server["status"] != "PASS_CAPTURE"
        or vis["status"] != "PASS"
        or sha(RUN / "server.json") != vis["server_sha256"]
        or sha(RUN / "dataset/capture.json") != vis["capture_sha256"]
        or server["selection_sha256"] != sha(SERIES / "nomination.json")
    ):
        raise ValueError("unqualified or unlinked holdout attempt")
    out = RUN / "parking-candidate"
    if not (out / "predictions.json").exists():
        predict_candidate(RUN, BUNDLE, out)
    if not (RUN / "baseline/predictions.json").exists():
        predict(RUN, "baseline")
    candidate = replay_candidate(RUN, BUNDLE, out)
    baseline = score(RUN, "baseline")
    comparison = relative(baseline, candidate, read(PROTOCOL))
    valid = all(
        r["valid"]
        for d in (out, RUN / "baseline")
        for r in read(d / "predictions.json")["rows"]
    )
    result = dict(
        status="PASS"
        if valid
        and candidate["absolute_quality"] == "PASS"
        and comparison["status"] == "PASS"
        else "FAIL",
        all_predictions_valid=valid,
        frames=81,
        site=101,
        absolute=candidate["gates"],
        relative=comparison,
        micro=candidate["micro"],
        baseline_micro=baseline["micro"],
        candidate_sha256=sha(out / "predictions.json"),
        baseline_sha256=sha(RUN / "baseline/predictions.json"),
        nomination_sha256=sha(SERIES / "nomination.json"),
        visibility_sha256=sha(RUN / "visibility.json"),
        labels_sha256=sha(RUN / "evaluation-only-gt.json"),
    )
    for p, v in (
        (out / "score.json", candidate),
        (RUN / "baseline/score.json", baseline),
        (SERIES / "result.json", result),
    ):
        if p.exists():
            if read(p) != v:
                raise ValueError(f"stored result changed: {p}")
        else:
            write(p, v)
    print(result, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("nominate", "capture", "score"))
    action = p.parse_args().action
    if action == "nominate":
        if RUN.exists():
            raise ValueError("nomination must precede holdout acquisition")
        if not (SMOKE / "predictions.json").exists():
            predict_candidate(DEV, BUNDLE, SMOKE)
        SERIES.mkdir(exist_ok=True)
        write(SERIES / "nomination.json", declaration())
    elif action == "capture":
        capture()
    else:
        adjudicate()
