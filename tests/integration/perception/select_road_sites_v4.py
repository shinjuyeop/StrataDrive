#!/usr/bin/env python3
"""Replay stricter site selection from the saved complete map query, not images."""

import argparse
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from quality_benchmark import write_new, require
from quality_geometry_v4 import route_eligible, select_sites


def derive(raw, raw_sha):
    require(
        raw["schema"] == "m10-road-survey-v4" and raw["status"] == "PASS",
        "complete raw map survey",
    )
    result = deepcopy(raw)
    for site in result["sites"]:
        site["eligible"] = route_eligible(site)
        site["reason"] = (
            None
            if site["eligible"]
            else "unused complete nonjunction42m route/width/turn/frustum screen rejected"
        )
    result.update(
        selected_sites=[s["spawn_point_index"] for s in select_sites(result["sites"])],
        raw_survey_sha256=raw_sha,
        selection_revision="v4b",
        selection="First eligible unused sites on different roads separated>=50m; entire42m route nonjunction; map-only replay after initial site rejection",
    )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("survey", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    r = derive(read_json(a.survey), sha256_file(a.survey))
    write_new(a.output, r)
    print(
        dict(selected=r["selected_sites"], selection_revision=r["selection_revision"])
    )
