"""One fresh, prospective bus quality evaluation after development qualification."""

import argparse
from pathlib import Path

import m10_person_support_holdout as parent
import fresh_quality_2k_review as reviewer
from bus_recall_plan import WORK, EVIDENCE, plans, validate_retained
from m10_collect_occlusion_transfer import capture_scenes
from m10_capture_fresh_quality import PYTHON, ROOT, TESTS
from m10_verify_parking_candidate import sha, verify
from fresh_quality_2k_review import read
from person_support_replay import BUNDLE, CACHE

BASE = WORK / "holdout"
PLAN = BASE / "plan"
MARK = EVIDENCE / "nomination.json"


def prepare():
    PLAN.mkdir(parents=True, exist_ok=True)
    for key, value in plans().items():
        parent.record(PLAN / (key + ".json"), value)
    validate_retained(PLAN)


def nomination():
    verify(BUNDLE)
    for k, h in read(parent.OLD / "freeze.json")["files"].items():
        if sha(ROOT / k) != h:
            raise ValueError(f"original source changed: {k}")
    prep = read(BASE / "runs/preparation-holdout-01/visibility.json")
    if prep["status"] != "PASS" or prep["plan_sha256"] != sha(
        PLAN / "preparation.json"
    ):
        raise ValueError("preparation")
    paths = [
        EVIDENCE / n
        for n in (
            "protocol.json",
            "selection.json",
            "validation.json",
            "evaluation-development-01-score.json",
        )
    ]
    if not all(read(path)["passed"] for path in paths[1:]):
        raise ValueError("development gates")
    paths += [
        PLAN / "sites.json",
        PLAN / "evaluation.json",
        BASE / "runs/preparation-holdout-01/visibility.json",
        BUNDLE / "manifest.json",
        parent.SERIES / "nomination.json",
        Path(__file__).resolve(),
        TESTS / "bus_recall.py",
        TESTS / "bus_recall_plan.py",
        TESTS / "bus_recall_fit.py",
        ROOT / "profiles/perception-quality-protocol-v9.json",
    ]
    for name, expected in read(parent.SERIES / "nomination.json")["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"parent candidate changed: {name}")
    return dict(
        site=plans()["sites"],
        frames=81,
        files={str(p.relative_to(ROOT)): sha(p) for p in paths},
    )


def review(run):
    prior = reviewer.previous_images(run)
    for r in parent.BASE.glob("runs/*/images.json"):
        prior.update(f["rgb_sha256"] for f in read(r)["frames"])
    for folder in (
        "archive-train",
        "archive-validation",
        "pairs-train",
        "pairs-validation",
    ):
        prior.update(f["rgb"] for f in read(CACHE / folder / "index.json"))
    for root in (parent.WORK, parent.ADDITIVE):
        for p in root.glob("*/dataset/labels.json"):
            prior.update(f["rgb_sha256"] for f in read(p))
    from PIL import Image
    import hashlib

    for p in (parent.WORK / "interrupted-Town05_Opt/dataset").glob("*.png"):
        with Image.open(p) as img:
            prior.add(hashlib.sha256(img.convert("RGB").tobytes()).hexdigest())
    original = reviewer.previous_images
    reviewer.BASE = BASE
    reviewer.validate_retained = validate_retained
    reviewer.previous_images = lambda current: prior | original(current)
    return reviewer.review(run)


def acquire(phase):
    prepare()
    run = BASE / "runs" / (phase + "-holdout-01")
    if phase == "evaluation":
        if read(MARK) != nomination() or any(
            (BASE / "runs").glob("evaluation-*/dataset/rgb/*.bgra.z")
        ):
            raise ValueError("nomination changed or evaluation already acquired")
    plan = PLAN / (phase + ".json")
    parent.boot_cache(run, False)
    try:
        capture_scenes(
            run,
            "Town04_Opt",
            [
                PYTHON,
                Path(__file__).resolve(),
                "client",
                "--plan",
                plan,
                "--output",
                run / "dataset",
            ],
            acquisition=dict(
                phase=phase,
                partition="holdout",
                plan_sha256=sha(plan),
                selection_sha256=sha(MARK) if phase == "evaluation" else None,
            ),
            timeout=1200,
        )
    finally:
        if (run / "server.json").exists():
            parent.boot_cache(run, True)
    if review(run)["status"] != "PASS":
        raise ValueError("visibility failed")


def score_holdout():
    from fresh_quality_2k_score import predict, score
    from person_support_replay import six_class
    from bus_recall_fit import infer

    run = BASE / "runs/evaluation-holdout-01"
    vis = read(run / "visibility.json")
    if (
        read(MARK) != nomination()
        or read(run / "server.json")["selection_sha256"] != sha(MARK)
        or vis["status"] != "PASS"
        or vis["server_sha256"] != sha(run / "server.json")
        or vis["capture_sha256"] != sha(run / "dataset/capture.json")
    ):
        raise ValueError("unqualified holdout")
    if not (run / "baseline/predictions.json").exists():
        predict(run, "baseline")
    if not all(row["valid"] for row in read(run / "baseline/predictions.json")["rows"]):
        raise ValueError("baseline errors")
    parent.record(run / "baseline/score.json", score(run, "baseline"))
    six_class(WORK, run, read(EVIDENCE / "selection.json")["policy"], detector=infer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("preparation", "client", "nominate", "evaluation", "score")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    if args.action == "client":
        import fresh_quality_2k_capture as client

        client.validate_retained = validate_retained
        args.partition = "holdout"
        args.port = 2400
        raise SystemExit(client.capture(args))
    elif args.action == "nominate":
        if (BASE / "runs/evaluation-holdout-01").exists():
            raise ValueError("nominate before acquisition")
        parent.record(MARK, nomination())
    elif args.action == "score":
        score_holdout()
    else:
        acquire(args.action)
