"""Reproduce small-car decisions, unmodified mask truth, and paired YOLOX reference scores."""

import argparse
from pathlib import Path

import car_support as parent
from multiview_audit import audit
from small_car import add, evaluate, records, read, dump
from small_car_plan import WORK, EVIDENCE, ROOT

OLD = ROOT / "docs/test-plan/evidence/m10_car_support_v1"


def verify(name, run):
    if not (EVIDENCE / "nomination.json").is_file():
        raise ValueError("missing nomination")
    choice = read(EVIDENCE / "selection.json")
    previous = "holdout" if name == "previous55" else name
    if name not in ("holdout", "previous307"):
        evaluate(run, name, choice, parent.WORK / (previous + "-verified.jsonl.gz"))
    if name == "previous307":
        evaluate(run, name, choice)
    extra = []
    for r in records(WORK / (name + "-verified.jsonl.gz")):
        ds = add(r["original_parent"], r["candidates"], choice["cutoff"])
        if ds != r["detections"] or ds != r["base"]:
            raise ValueError("small-car replay")
        extra.append(dict(rgb=r["rgb"], added=ds[len(r["original_parent"]) :]))
    result = audit(run, WORK, EVIDENCE, name)
    if (
        name not in ("holdout", "previous307")
        and result["parent"]["per_class"]
        != read(OLD / (previous + ".json"))["candidate"]["card"]["per_class"]
    ):
        raise ValueError("frozen parent reproduction")
    dump(EVIDENCE / (name + "-additions.json"), extra)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "name",
        choices=(
            "holdout",
            "previous307",
            "previous492",
            "previous1576",
            "previous43",
            "previous17",
            "previous57",
            "previous58",
            "previous55",
        ),
    )
    p.add_argument("run", type=Path)
    a = p.parse_args()
    verify(a.name, a.run)
