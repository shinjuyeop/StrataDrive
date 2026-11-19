"""Capture disjoint development and sealed evaluation roads and run the fixed model."""

import argparse
from pathlib import Path

import m10_bus_recall_holdout as bus
from m10_bus_recall_holdout import parent, PYTHON, capture_scenes, sha, ROOT, TESTS
import fresh_quality_2k_review as reviewer
from fresh_quality_2k_review import read
from fresh_quality_2k_score import predict, score
from multiview_plan import WORK, EVIDENCE, plans, validate_retained

BASE = WORK / "native"
PLAN = BASE / "plan"
MARK = EVIDENCE / "nomination.json"


def nomination():
    sources = [
        EVIDENCE / n for n in ("protocol.json", "selection.json", "validation.json")
    ]
    if not read(sources[-1])["passed"]:
        raise ValueError("development gates")
    if (
        sha(WORK / "verifier.joblib")
        != read(EVIDENCE / "selection.json")["model_sha256"]
    ):
        raise ValueError("verifier identity changed")
    bus.verify(bus.BUNDLE)
    for name, expected in read(bus.MARK)["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("parent source changed")
    sources.extend(
        [
            bus.MARK,
            Path(__file__).resolve(),
            TESTS / "multiview_plan.py",
            TESTS / "multiview_detector.py",
            TESTS / "multiview_observations.py",
            TESTS / "multiview_select.py",
            WORK / "verifier.joblib",
            WORK / "training.json",
            ROOT / "profiles/perception-quality-protocol-v9.json",
            ROOT / "docs/test-plan/evidence/m10_bus_recall_v1/selection.json",
            ROOT
            / "docs/test-plan/evidence/m10_person_additive_v2/additive-selection.json",
            PLAN / "evaluation.json",
            PLAN / "sites.json",
        ]
    )
    for part in ("development", "holdout"):
        path = BASE / "runs" / f"preparation-{part}-01" / "visibility.json"
        if read(path)["status"] != "PASS" or read(path)["plan_sha256"] != sha(
            PLAN / "preparation.json"
        ):
            raise ValueError("preparation")
        sources.append(path)
    return dict(
        sites=plans()["sites"],
        frames=81,
        files={str(p.relative_to(ROOT)): sha(p) for p in sources},
    )


def review(run):
    # Include both earlier native holdouts plus all archived, paired and interrupted images.
    old = reviewer.previous_images
    extra = set()
    for root in (bus.BASE, BASE):
        for f in (root / "runs").glob("*/images.json"):
            if f.parent != run:
                extra.update(v["rgb_sha256"] for v in read(f)["frames"])
    reviewer.previous_images = lambda path: old(path) | extra
    bus.BASE = BASE
    bus.validate_retained = validate_retained
    return bus.review(run)


def capture(phase, part):
    PLAN.mkdir(parents=True, exist_ok=True)
    for key, val in plans().items():
        parent.record(PLAN / (key + ".json"), val)
    run = BASE / "runs" / f"{phase}-{part}-01"
    if run.exists():
        raise FileExistsError(run)
    sealed = phase == "evaluation" and part == "holdout"
    if phase == "evaluation":
        prep = read(BASE / "runs" / f"preparation-{part}-01" / "visibility.json")
        if prep["status"] != "PASS" or prep["plan_sha256"] != sha(
            PLAN / "preparation.json"
        ):
            raise ValueError("visibility preparation")
    if sealed and read(MARK) != nomination():
        raise ValueError("nomination")
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
                "--partition",
                part,
            ],
            acquisition=dict(
                phase=phase,
                partition=part,
                plan_sha256=sha(plan),
                selection_sha256=sha(MARK) if sealed else None,
            ),
            timeout=1200,
        )
    finally:
        if (run / "server.json").exists():
            parent.boot_cache(run, True)
    if review(run)["status"] != "PASS":
        raise ValueError(f"{run.name} visibility failed")


def baseline(run):
    if not (run / "baseline/predictions.json").exists():
        predict(run, "baseline")
    if not all(row["valid"] for row in read(run / "baseline/predictions.json")["rows"]):
        raise ValueError("baseline validity")
    parent.record(run / "baseline/score.json", score(run, "baseline"))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=(
            "client",
            "preparation",
            "evaluation",
            "baseline",
            "nominate",
            "score",
        ),
    )
    p.add_argument(
        "--partition", choices=("development", "holdout"), default="development"
    )
    p.add_argument("--plan", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    if a.action == "client":
        import fresh_quality_2k_capture as cli

        a.port = 2400
        cli.validate_retained = validate_retained
        raise SystemExit(cli.capture(a))
    elif a.action == "nominate":
        if (BASE / "runs/evaluation-holdout-01").exists():
            raise ValueError("already acquired")
        parent.record(MARK, nomination())
    elif a.action in ("baseline", "score"):
        run = BASE / "runs" / ("evaluation-" + a.partition + "-01")
        v = read(run / "visibility.json")
        if (
            v["status"] != "PASS"
            or v["server_sha256"] != sha(run / "server.json")
            or v["capture_sha256"] != sha(run / "dataset/capture.json")
        ):
            raise ValueError("capture association")
        if a.partition == "holdout" and (
            read(MARK) != nomination()
            or read(run / "server.json")["selection_sha256"] != sha(MARK)
        ):
            raise ValueError("nomination association")
        baseline(run)
        if a.action == "score":
            from multiview_detector import evaluate_run

            evaluate_run(run, WORK, read(EVIDENCE / "selection.json"))
    else:
        capture(a.action, a.partition)
