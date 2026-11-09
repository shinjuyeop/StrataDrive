"""Actual support matrices for development data, independent of detector scores."""

from collections import Counter
from pathlib import Path
from physical_ai.perception.dataset import read_json
from domain_plan_v1 import WEATHER, ANGLES, DISTANCES


def assess(roots):
    views = Counter()
    distances = Counter()
    occlusions = Counter()
    blueprints = set()
    riders = Counter()
    negatives = Counter()
    missing = []
    rows = []
    for root in roots:
        frames = read_json(Path(root) / "support.json")["frames"]
        lookup = {r["id"]: r for r in frames}
        for row in frames:
            if row["stratum"] == "occluded_reference":
                original = lookup[row["reference_for"]]
                target = next(a for a in original["actors"] if a["role"] == "target")
                reference = next(a for a in row["actors"] if a["role"] == "target")
                a, b = target["object"], reference["object"]
                ratio = a["visible_pixels"] / b["visible_pixels"] if a and b else None
                passed = bool(
                    target["qualified"]
                    and reference["qualified"]
                    and ratio is not None
                    and 0 < ratio < 0.95
                )
                if passed:
                    occlusions[(row["target_class"], row["weather"])] += 1
                rows.append(
                    dict(
                        scene=original["id"],
                        reference=row["id"],
                        ratio=ratio,
                        qualified=passed,
                    )
                )
                continue
            if row["stratum"] == "negative":
                negatives[row["weather"]] += 1
                continue
            for a in row["actors"]:
                blueprints.add(a["blueprint"])
                if a["class_id"] in (1, 3):
                    riders[
                        "qualified" if a["rider_qualified"] else "small_or_invisible"
                    ] += 1
                if not a["qualified"]:
                    missing.append(
                        dict(scene=row["id"], blueprint=a["blueprint"], role=a["role"])
                    )
                if (
                    a["role"] == "target"
                    and a["qualified"]
                    and row["stratum"] in ("near", "medium", "far")
                ):
                    views[
                        (a["class_id"], row["weather"], row["orientation_degrees"])
                    ] += 1
                    distances[
                        (
                            a["class_id"],
                            row["weather"],
                            DISTANCES[("near", "medium", "far").index(row["stratum"])],
                        )
                    ] += 1
    required_views = [
        (c, w, y) for c in (0, 1, 2, 3, 5, 7) for w in WEATHER for y in ANGLES
    ]
    required_distances = [
        (c, w, d) for c in (0, 1, 2, 3, 5, 7) for w in WEATHER for d in DISTANCES
    ]
    required_occ = [(c, w) for c in (0, 1, 2, 3, 5, 7) for w in WEATHER]
    gates = dict(
        every_class_weather_view=all(views[k] >= 1 for k in required_views),
        every_class_weather_distance=all(distances[k] >= 1 for k in required_distances),
        every_class_weather_occlusion=all(occlusions[k] >= 1 for k in required_occ),
        all_weather_background_controls=all(negatives[w] >= 1 for w in WEATHER),
    )
    return dict(
        status="PASS" if all(gates.values()) else "FAIL",
        gates=gates,
        view_support=[
            dict(class_id=c, weather=w, orientation=y, qualified=views[(c, w, y)])
            for c, w, y in required_views
        ],
        distance_support=[
            dict(class_id=c, weather=w, distance_m=d, qualified=distances[(c, w, d)])
            for c, w, d in required_distances
        ],
        occlusion_support=[
            dict(class_id=c, weather=w, qualified=occlusions[(c, w)])
            for c, w in required_occ
        ],
        occlusion_records=rows,
        planned_unsupported=missing,
        riders=dict(riders),
        blueprints=sorted(blueprints),
        background_controls=dict(negatives),
        scope="Development data support, not model accuracy; all unsupported fragments retained as training positives",
    )
