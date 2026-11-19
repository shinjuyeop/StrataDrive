"""Verify original native frames and compare both historical regressions with their sealed scores."""

import argparse
from pathlib import Path

from cycle_transfer import WORK, EVIDENCE, ROOT, evaluate, read
from multiview_audit import audit


def verify(name, run):
    prior = ROOT / "docs/test-plan/evidence/m10_multiview_v1"
    source = {"previous492": "site492", "previous1576": "holdout"}
    selection = read(EVIDENCE / "selection.json")
    if name in source:
        if not (EVIDENCE / "nomination.json").is_file():
            raise ValueError("candidate registration required")
        evaluate(run, name, selection)
    result = audit(run, WORK, EVIDENCE, name)
    if (
        name in source
        and result["parent"]["per_class"]
        != read(prior / (source[name] + ".json"))["candidate"]["card"]["per_class"]
    ):
        raise ValueError("same-image parent score changed")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("name", choices=("previous492", "previous1576", "holdout"))
    p.add_argument("run", type=Path)
    a = p.parse_args()
    verify(a.name, a.run)
