"""Reconstruct fresh and historical scores after vehicle-type verification."""

import argparse
from pathlib import Path

from multiview_audit import audit
from multiview_detector import records
import car_recovery as prior
from car_support import evaluate, add
from car_support_plan import WORK, EVIDENCE, ROOT, read

OLD = ROOT / "docs/test-plan/evidence/m10_car_recovery_v1"


def verify(run, name):
    previous = {
        "previous492": "previous492",
        "previous1576": "previous1576",
        "previous43": "previous43",
        "previous17": "previous17",
        "previous57": "previous57",
        "previous58": "holdout",
    }
    selection = read(EVIDENCE / "selection.json")
    if name in previous:
        if not (EVIDENCE / "nomination.json").is_file():
            raise ValueError("nomination")
        parent = previous[name]
        evaluate(run, name, selection, prior.WORK / (parent + "-verified.jsonl.gz"))
    decisions = []
    for r in records(WORK / (name + "-verified.jsonl.gz")):
        pred = add(r["original_parent"], r["candidates"], selection["policy"])
        if pred != r["detections"] or pred != r["base"]:
            raise ValueError("decision replay")
        if r["candidates"]:
            decisions.append(dict(rgb=r["rgb"], vehicles=r["candidates"]))
    result = audit(run, WORK, EVIDENCE, name)
    if (
        name in previous
        and result["parent"]["per_class"]
        != read(OLD / (previous[name] + ".json"))["candidate"]["card"]["per_class"]
    ):
        raise ValueError("previous parent did not reproduce")
    from person_pair_candidate import dump

    dump(EVIDENCE / (name + "-checks.json"), decisions)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "name",
        choices=(
            "holdout",
            "previous43",
            "previous17",
            "previous57",
            "previous58",
            "previous492",
            "previous1576",
        ),
    )
    p.add_argument("run", type=Path)
    a = p.parse_args()
    verify(a.run, a.name)
