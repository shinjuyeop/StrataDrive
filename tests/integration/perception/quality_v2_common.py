"""V2 frozen experiment identity, shared by RGB runner and offline evaluator."""

from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import MODEL_SHA256, sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.quality_candidates_v2 import CANDIDATES
from quality_benchmark import require, write_new

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-quality-plan-v2.json"
PROTOCOL = ROOT / "profiles/perception-quality-protocol-v2.json"
EXCLUSION = ROOT / "profiles/perception-quality-v1-exclusion.json"


def validate_descriptors():
    p, plan = read_json(PROTOCOL), read_json(PLAN)
    require(
        p["schema"] == "m10-quality-protocol-v2"
        and p["candidate_ids"] == list(CANDIDATES[1:])
        and p["score_threshold"] == 0.35
        and p["minimum_visible_pixels"] == 25
        and p["minimum_box_side"] == 4
        and p["center_refine"]
        == dict(
            crop_xywh=[160, 96, 320, 192],
            scale=2,
            crop_edge_margin_pixels=2,
            same_class_nms_iou=0.5,
            cross_class_nms=False,
        )
        and p["vru_refine"]
        == dict(
            classes=[0, 1, 3],
            baseline_priority=True,
            duplicate_iou=0.5,
            base_boxes_unchanged=True,
        )
        and p["annotation"]["person_tags"] == [12, 13]
        and p["annotation"]["primary_ignore"] is False,
        "v2 descriptor/executable mismatch",
    )
    require(
        plan["schema"] == "m10-quality-plan-v2"
        and all(len(part["cases"]) == 81 for part in plan["partitions"].values())
        and p["coverage"]["cases_per_partition"] == 81
        and p["coverage"]["minimum_visible_cases_per_class_stratum"] == 2
        and p["coverage"]["minimum_rider_instances"] == 12,
        "v2 coverage descriptor",
    )
    # Thresholds and selection policy cannot be loosened by a profile-only edit.
    legacy = read_json(ROOT / "profiles/perception-quality-protocol-v1.json")
    require(
        all(
            p[k] == legacy[k]
            for k in ("absolute_quality", "relative_promotion", "selection_order")
        ),
        "v2 must retain v1 numeric quality gates",
    )


def freeze(path):
    validate_descriptors()
    files = set((ROOT / "physical_ai/perception").glob("*.py"))
    files.update((ROOT / "tests/integration/perception").glob("*quality*.py"))
    files.update(
        ROOT / "tests/integration/perception" / name
        for name in ("evaluate.py", "prepare_dataset.py", "run_capture.py")
    )
    files.update(
        (
            PLAN,
            PROTOCOL,
            EXCLUSION,
            ROOT / "profiles/perception-quality-protocol-v1.json",
        )
    )
    result = dict(
        schema="m10-quality-freeze-v2",
        created_utc=datetime.now(timezone.utc).isoformat(),
        model_sha256=MODEL_SHA256,
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        exclusion_sha256=sha256_file(EXCLUSION),
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(files)},
    )
    write_new(path, result)
    return result


def check_freeze(path):
    f = read_json(path)
    require(
        f["schema"] == "m10-quality-freeze-v2"
        and f["model_sha256"] == MODEL_SHA256
        and f["plan_sha256"] == sha256_file(PLAN)
        and f["protocol_sha256"] == sha256_file(PROTOCOL)
        and f["exclusion_sha256"] == sha256_file(EXCLUSION),
        "v2 freeze identity",
    )
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, f"v2 frozen source changed: {name}")
    return f
