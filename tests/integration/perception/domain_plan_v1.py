"""Deterministic model-free training/validation collection; no quality holdout."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from quality_geometry_v4 import road_pose, camera_projection, route_eligible
from quality_benchmark import require

ROOT = Path(__file__).resolve().parents[3]
SURVEY = ROOT / "docs/test-plan/evidence/m10_road_preparation_v4/survey-selected.json"
EXCLUSION = (
    ROOT / "docs/test-plan/evidence/m10_quality_v6/future-evaluation-exclusion.json"
)
ASSETS = {
    "train": {
        0: [
            "walker.pedestrian.0004",
            "walker.pedestrian.0010",
            "walker.pedestrian.0015",
        ],
        1: ["vehicle.bh.crossbike", "vehicle.diamondback.century"],
        2: [
            "vehicle.dodge.charger_2020",
            "vehicle.audi.tt",
            "vehicle.ford.mustang",
            "vehicle.audi.etron",
        ],
        3: ["vehicle.yamaha.yzf", "vehicle.vespa.zx125"],
        5: ["vehicle.mitsubishi.fusorosa"],
        7: ["vehicle.carlamotors.carlacola", "vehicle.carlamotors.firetruck"],
    },
    "validation": {
        0: [
            "walker.pedestrian.0001",
            "walker.pedestrian.0007",
            "walker.pedestrian.0018",
        ],
        1: ["vehicle.gazelle.omafiets"],
        2: ["vehicle.tesla.model3", "vehicle.jeep.wrangler_rubicon"],
        3: ["vehicle.kawasaki.ninja", "vehicle.harley-davidson.low_rider"],
        5: ["vehicle.mitsubishi.fusorosa"],
        7: ["vehicle.carlamotors.carlacola", "vehicle.carlamotors.firetruck"],
    },
}
WEATHER = ("ClearNoon", "WetCloudyNoon", "CloudySunset")
SITES = {"train-14": 14, "train-31": 31, "train-74": 74, "validation-104": 104}
ANGLES = (0, 90, 180, 270)
DISTANCES = (8, 16, 24)


def actor(site, blueprint, cls, distance, right, yaw, role="target", color=None):
    node = site["nodes"][str(distance)]
    clearance = site["base_clearance_m"] + 0.5
    return dict(
        class_id=cls,
        blueprint=blueprint,
        role=role,
        route_distance_m=distance,
        road_node=deepcopy(node),
        right_m=right,
        clearance_m=clearance,
        yaw_offset_degrees=yaw,
        pose=road_pose(node, right, clearance, yaw),
        color=color,
    )


def build(preflight=False):
    survey = read_json(SURVEY)
    sites = {s["spawn_point_index"]: s for s in survey["sites"]}
    plan = dict(
        schema="m10-domain-data-plan-v1",
        phase="asset-preflight" if preflight else "development-data",
        map="Town03_Opt",
        server_quality="Epic",
        rgb_postprocess=True,
        world_step_ns=10_000_000,
        sensor_tick_seconds=0,
        settle_ticks=40,
        capture_ticks=10,
        selected_capture_tick=5,
        seed=0,
        survey_sha256=sha256_file(SURVEY),
        xodr_sha256=survey["xodr_sha256"],
        previous_rgb_exclusion_sha256=sha256_file(EXCLUSION),
        reserved_future_holdout_site=127,
        quality_holdout_collected=False,
        assets={
            split: {str(k): v for k, v in group.items()}
            for split, group in ASSETS.items()
        },
        asset_overlap_exceptions={
            "5": "Only one compatible bus blueprint available",
            "7": "Two compatible truck blueprints shared to measure novel-view/road transfer; not independent asset generalization",
        },
        partitions={},
    )
    runs = {"preflight": 104} if preflight else SITES
    for run, index in runs.items():
        site = sites[index]
        require(route_eligible(site), "whole-route site eligibility")
        split = "preflight" if preflight else run.split("-")[0]
        settings = dict(
            spawn_point_index=index,
            split=split,
            road_id=site["nodes"]["0"]["road_id"],
            camera_pose=deepcopy(site["camera_pose"]),
            cases=[],
        )
        cases = settings["cases"]

        def add(
            cls,
            bp,
            distance,
            angle,
            weather,
            stratum,
            right=0.4,
            view=0,
            ref=None,
            others=(),
        ):
            camera = deepcopy(settings["camera_pose"])
            camera["rotation"]["yaw"] += view
            if stratum in ("near", "medium", "far"):
                camera["location"]["z"] += 0.15 if (angle // 90) % 2 else 0
                camera["rotation"]["pitch"] += 2 if weather == "CloudySunset" else 0
            color = ("35,35,35", "190,190,190", "180,35,35")[WEATHER.index(weather)]
            items = (
                []
                if bp is None
                else [actor(site, bp, cls, distance, right, angle, color=color)]
            )
            items += list(others)
            ident = f"domain-v1-{run}-{len(cases):04d}"
            case = dict(
                id=ident,
                weather=weather,
                stratum=stratum,
                target_class=cls,
                camera_pose=camera,
                orientation_degrees=angle,
                variant_group=ref or ident,
                actors=items,
            )
            if ref:
                case["reference_for"] = ref
            for a in items:
                a["camera_projection"] = camera_projection(camera, a["pose"])
                require(a["camera_projection"]["in_frame"], "actor origin frustum")
            cases.append(case)
            return case

        if preflight:
            all_assets = sorted(
                {
                    (cls, bp)
                    for group in ASSETS.values()
                    for cls, bps in group.items()
                    for bp in bps
                }
            )
            for cls, bp in all_assets:
                for angle in ANGLES:
                    for distance in (8, 24):
                        add(
                            cls,
                            bp,
                            distance,
                            angle,
                            "ClearNoon",
                            "preflight-near" if distance == 8 else "preflight-far",
                        )
        else:
            group = ASSETS[split]
            for cls, bps in group.items():
                for w, weather in enumerate(WEATHER):
                    for y, angle in enumerate(ANGLES):
                        for d, distance in enumerate(DISTANCES):
                            bp = bps[(w + y + d + list(SITES).index(run)) % len(bps)]
                            add(
                                cls,
                                bp,
                                distance,
                                angle,
                                weather,
                                ("near", "medium", "far")[d],
                                right=(-0.8, 0.4, 0.8)[(w + y) % 3],
                                view=(-7, 0, 7)[(d + w) % 3],
                            )
            for cls, bps in group.items():
                for w, weather in enumerate(WEATHER):
                    bp = bps[w % len(bps)]
                    blocker = actor(
                        site,
                        group[2][w % len(group[2])],
                        2,
                        10,
                        -0.6,
                        15,
                        role="occluder",
                        color="70,70,70",
                    )
                    target = add(
                        cls,
                        bp,
                        16,
                        80 if cls in (1, 3) else 15,
                        weather,
                        "occluded",
                        right=1.2,
                        others=(blocker,),
                    )
                    add(
                        cls,
                        bp,
                        16,
                        80 if cls in (1, 3) else 15,
                        weather,
                        "occluded_reference",
                        right=1.2,
                        ref=target["id"],
                    )
            for weather in WEATHER:
                add(None, None, 0, 0, weather, "negative")
        plan["partitions"][run] = settings
    if not preflight:
        plan["collection_revision"] = (
            "post-asset-preflight: side-view occlusion for two-wheelers; original unused draft retained"
        )
    validate_plan(plan)
    return plan


def validate_plan(plan):
    require(
        plan["schema"] == "m10-domain-data-plan-v1"
        and plan["phase"] in ("asset-preflight", "development-data"),
        "domain schema",
    )
    require(
        plan["reserved_future_holdout_site"] == 127
        and not plan["quality_holdout_collected"],
        "no quality holdout",
    )
    seen = set()
    for run, p in plan["partitions"].items():
        require(
            p["spawn_point_index"] != 127 and p["cases"],
            "reserved road and nonempty runs",
        )
        for c in p["cases"]:
            require(c["id"] not in seen, "duplicate case")
            seen.add(c["id"])
            require(c["weather"] in WEATHER, "weather")
            for a in c["actors"]:
                require(
                    a["blueprint"] != "vehicle.carlamotors.european_hgv",
                    "incompatible asset denied",
                )
                require(
                    a["pose"]
                    == road_pose(
                        a["road_node"],
                        a["right_m"],
                        a["clearance_m"],
                        a["yaw_offset_degrees"],
                    ),
                    "road pose",
                )
                require(
                    a["camera_projection"]
                    == camera_projection(c["camera_pose"], a["pose"])
                    and a["camera_projection"]["in_frame"],
                    "camera projection",
                )
    if plan["phase"] == "development-data":
        require(
            set(plan["partitions"]) == set(SITES)
            and all(len(p["cases"]) == 255 for p in plan["partitions"].values()),
            "frozen four-run denominator",
        )
        train = set(SITES[k] for k in SITES if k.startswith("train"))
        valid = {104}
        require(not train & valid, "site split")
        for cls in (0, 1, 2, 3):
            require(
                not set(plan["assets"]["train"][str(cls)])
                & set(plan["assets"]["validation"][str(cls)]),
                "disjoint asset classes",
            )
    return plan
