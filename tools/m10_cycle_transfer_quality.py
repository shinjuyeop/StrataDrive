"""Capture the fixed quality protocol on a separate Town07 road and verify its frozen detector."""

import argparse
from pathlib import Path

import m10_multiview_quality as previous
from m10_multiview_quality import (
    bus,
    parent,
    PYTHON,
    capture_scenes,
    sha,
    ROOT,
    TESTS,
    read,
    baseline,
)
from cycle_transfer_plan import WORK, EVIDENCE, PREVIOUS, plans, validate_retained

BASE = WORK / "native"
PLAN = BASE / "plan"
MARK = EVIDENCE / "nomination.json"
OLD = ROOT / "docs/test-plan/evidence/m10_multiview_v1"


def nomination():
    if (
        not read(EVIDENCE / "selection.json")["passed"]
        or not read(OLD / "holdout.json")["passed"]
    ):
        raise ValueError("development qualification")
    if previous.nomination() != read(previous.MARK):
        raise ValueError("parent nomination changed")
    sources = [
        EVIDENCE / "protocol.json",
        EVIDENCE / "selection.json",
        OLD / "nomination.json",
        Path(__file__).resolve(),
        TESTS / "cycle_transfer_plan.py",
        TESTS / "cycle_transfer.py",
        PLAN / "evaluation.json",
        PLAN / "sites.json",
    ]
    for part in ("development", "holdout"):
        path = BASE / "runs" / f"preparation-{part}-01" / "visibility.json"
        if read(path)["status"] != "PASS" or read(path)["plan_sha256"] != sha(
            PLAN / "preparation.json"
        ):
            raise ValueError("model-free preparation")
        sources.append(path)
    return dict(
        sites=plans()["sites"],
        files={str(p.relative_to(ROOT)): sha(p) for p in sources},
    )


def capture(phase, part):
    PLAN.mkdir(parents=True, exist_ok=True)
    for k, v in plans().items():
        parent.record(PLAN / (k + ".json"), v)
    run = BASE / "runs" / f"{phase}-{part}-01"
    if run.exists():
        raise FileExistsError(run)
    if (
        phase == "evaluation"
        and read(BASE / "runs" / f"preparation-{part}-01" / "visibility.json")["status"]
        != "PASS"
    ):
        raise ValueError("unprepared site")
    sealed = (phase, part) == ("evaluation", "holdout")
    if sealed and nomination() != read(MARK):
        raise ValueError("seal")
    plan = PLAN / (phase + ".json")
    parent.boot_cache(run, False)
    try:
        capture_scenes(
            run,
            plans()["sites"]["map"],
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
    extra = {
        v["rgb_sha256"]
        for root in (PREVIOUS, BASE, bus.BASE)
        for image in (root / "runs").glob("*/images.json")
        if image.parent != run
        for v in read(image)["frames"]
    }
    reviewer = previous.reviewer
    orig = reviewer.previous_images
    reviewer.previous_images = lambda path: orig(path) | extra
    bus.BASE = BASE
    bus.validate_retained = validate_retained
    if bus.review(run)["status"] != "PASS":
        raise ValueError("visibility")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
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
    parser.add_argument(
        "--partition", choices=("development", "holdout"), default="development"
    )
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--output", type=Path)
    a = parser.parse_args()
    if a.action == "client":
        import fresh_quality_2k_capture as cli

        cli.validate_retained = validate_retained
        a.port = 2400
        raise SystemExit(cli.capture(a))
    if a.action == "nominate":
        if (BASE / "runs/evaluation-holdout-01").exists():
            raise ValueError("already captured")
        parent.record(MARK, nomination())
    elif a.action in ("baseline", "score"):
        run = BASE / "runs" / f"evaluation-{a.partition}-01"
        vis = read(run / "visibility.json")
        if (
            vis["status"] != "PASS"
            or vis["server_sha256"] != sha(run / "server.json")
            or vis["capture_sha256"] != sha(run / "dataset/capture.json")
        ):
            raise ValueError("capture association")
        if a.partition == "holdout" and (
            nomination() != read(MARK)
            or read(run / "server.json")["selection_sha256"] != sha(MARK)
        ):
            raise ValueError("seal")
        baseline(run)
        if a.action == "score":
            from cycle_transfer import evaluate

            evaluate(run, "holdout", read(EVIDENCE / "selection.json"))
    else:
        capture(a.action, a.partition)
