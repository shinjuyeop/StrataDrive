"""Reconstruct fresh and historical scores after vehicle-type verification."""

import argparse
from pathlib import Path

from multiview_audit import audit
from multiview_detector import records
from vehicle_conflict import PARENT, evaluate, filter_detections
from vehicle_conflict_plan import WORK, EVIDENCE, ROOT, read

OLD = ROOT / "docs/test-plan/evidence/m10_cycle_transfer_v1"


def verify(run, name):
    previous = {
        "previous492": "previous492",
        "previous1576": "previous1576",
        "previous43": "holdout",
    }
    selection = read(EVIDENCE / "selection.json")
    if name in previous:
        if not (EVIDENCE / "nomination.json").is_file():
            raise ValueError("nomination")
        parent = previous[name]
        evaluate(run, name, selection, PARENT / (parent + "-verified.jsonl.gz"))
    decisions = []
    for r in records(WORK / (name + "-verified.jsonl.gz")):
        pred = filter_detections(
            r["original_parent"], r["checks"], selection["threshold"]
        )
        if pred != r["detections"] or pred != r["base"]:
            raise ValueError("decision replay")
        if r["checks"]:
            decisions.append(dict(rgb=r["rgb"], vehicles=r["checks"]))
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
        "name", choices=("holdout", "previous43", "previous492", "previous1576")
    )
    p.add_argument("run", type=Path)
    a = p.parse_args()
    verify(a.run, a.name)
