"""Freeze a visible-support detector and evaluate it on the reserved independent road."""

import argparse
from pathlib import Path

import m10_small_car_quality as tiles
from m10_multiview_quality import (
    parent,
    capture_scenes,
    PYTHON,
    TESTS,
    ROOT,
    sha,
    read,
    baseline,
)
from small_car_plan import plans, validate_retained
from visible_car import EVIDENCE, WORK, evaluate

MARK = EVIDENCE / "nomination.json"
RUN = WORK / "native/runs/evaluation-holdout-01"
PREP = tiles.BASE / "runs/preparation-holdout-01/visibility.json"
HISTORICAL = {
    "previous101": ROOT
    / "docs/test-plan/evidence/m10_fresh_quality_2k_v1/runs/evaluation-holdout-01",
    "previous307": ROOT
    / "build/m10-person-support-v1/holdout/runs/evaluation-holdout-01",
    "previous492": ROOT / "build/m10-bus-recall-v1/holdout/runs/evaluation-holdout-01",
    **{
        n: ROOT / ("build/m10-" + folder + "-v1/native/runs/evaluation-holdout-01")
        for n, folder in {
            "previous1576": "multiview",
            "previous43": "cycle-transfer",
            "previous17": "vehicle-conflict",
            "previous57": "vehicle-class",
            "previous58": "car-recovery",
            "previous55": "car-support",
        }.items()
    },
}


def nomination():
    if not read(EVIDENCE / "selection.json")["passed"] or tiles.nomination() != read(
        tiles.MARK
    ):
        raise ValueError("parent or development qualification changed")
    if read(PREP)["status"] != "PASS" or read(PREP)["plan_sha256"] != sha(
        tiles.PLAN / "preparation.json"
    ):
        raise ValueError("preparation identity")
    validate_retained(tiles.PLAN)
    files = [
        tiles.MARK,
        tiles.PLAN / "evaluation.json",
        tiles.PLAN / "sites.json",
        PREP,
        EVIDENCE / "selection.json",
        EVIDENCE / "protocol.json",
        TESTS / "visible_car.py",
        Path(__file__).resolve(),
    ]
    return dict(
        sites=plans()["sites"], files={str(p.relative_to(ROOT)): sha(p) for p in files}
    )


def fresh():
    if RUN.exists() or (tiles.BASE / "runs/evaluation-holdout-01").exists():
        raise ValueError("road 60 already consumed")
    if not all(read(EVIDENCE / (n + ".json"))["passed"] for n in HISTORICAL):
        raise ValueError("historical qualification")
    base = WORK / "native"
    plan = base / "plan"
    plan.mkdir(parents=True, exist_ok=True)
    for k, v in plans().items():
        parent.record(plan / (k + ".json"), v)
    parent.boot_cache(RUN, False)
    try:
        capture_scenes(
            RUN,
            plans()["sites"]["map"],
            [
                PYTHON,
                ROOT / "tools/m10_small_car_quality.py",
                "client",
                "--plan",
                plan / "evaluation.json",
                "--output",
                RUN / "dataset",
                "--partition",
                "holdout",
            ],
            acquisition=dict(
                phase="evaluation",
                partition="holdout",
                plan_sha256=sha(plan / "evaluation.json"),
                selection_sha256=sha(MARK),
            ),
            timeout=1200,
        )
    finally:
        if (RUN / "server.json").exists():
            parent.boot_cache(RUN, True)
    previous = tiles.previous.reviewer.previous_images
    roots = [
        tiles.BASE,
        tiles.support.BASE,
        tiles.previous.BASE,
        tiles.conflict.BASE,
        tiles.typed.BASE,
        tiles.recovery.BASE,
        tiles.PREVIOUS,
        tiles.bus.BASE,
    ]
    prior = set(
        read(tiles.support.EVIDENCE / "interrupted-exclusions.json")[
            "previous_interrupted_rgb"
        ]
    )
    for root in roots:
        for path in (root / "runs").glob("*/images.json"):
            prior.update(f["rgb_sha256"] for f in read(path)["frames"])
    for run in HISTORICAL.values():
        prior.update(f["rgb_sha256"] for f in read(run / "images.json")["frames"])
    tiles.previous.reviewer.previous_images = lambda p: previous(p) | prior
    tiles.bus.BASE = base
    tiles.bus.validate_retained = validate_retained
    if tiles.bus.review(RUN)["status"] != "PASS" or read(RUN / "server.json")[
        "selection_sha256"
    ] != sha(MARK):
        raise ValueError("capture integrity")
    baseline(RUN)
    evaluate(RUN, "holdout", "visible-final", full=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("nominate", "history", "fresh"))
    p.add_argument("site", nargs="?", choices=tuple(HISTORICAL))
    a = p.parse_args()
    if a.action == "nominate":
        if (
            MARK.exists()
            or RUN.exists()
            or (tiles.BASE / "runs/evaluation-holdout-01").exists()
        ):
            raise ValueError("already nominated or acquired")
        parent.record(MARK, nomination())
    else:
        if nomination() != read(MARK):
            raise ValueError("detector seal")
        if a.action == "history":
            evaluate(HISTORICAL[a.site], a.site, a.site)
        else:
            fresh()
