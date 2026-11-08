"""Render sealed v3 masks before inference; never reads predictions."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json

root = Path(sys.argv[1])
part = sys.argv[2]
data = root / f"{part}-data"
manifest = read_json(data / "rgb.json")
gt = read_json(data / "evaluation-only-gt.json")
meta = read_json(data / "benchmark.json")
colors = {
    0: (255, 255, 0),
    1: (0, 255, 255),
    2: (255, 150, 80),
    3: (100, 255, 100),
    5: (255, 160, 255),
    7: (80, 150, 255),
}
names = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def draw(index):
    source, truth = manifest["frames"][index], gt["frames"][index]
    image = np.frombuffer((data / source["rgb_path"]).read_bytes(), np.uint8).reshape(
        384, 640, 3
    )
    # Fixed centre viewport for inspection only. Stored/model RGB remains unchanged.
    x, y, w, h = 230, 100, 200, 150
    panel = cv2.resize(
        cv2.cvtColor(image[y : y + h, x : x + w], cv2.COLOR_RGB2BGR),
        (400, 300),
        interpolation=cv2.INTER_NEAREST,
    )
    for field in ("objects", "excluded"):
        for obj in truth[field]:
            a, b, c, d = [int(v) for v in obj["box"]]
            a, c = (a - x) * 2, (c - x) * 2
            b, d = (b - y) * 2, (d - y) * 2
            color = (
                (160, 160, 160)
                if field == "excluded"
                else (
                    (255, 80, 255)
                    if 13 in obj["semantic_tags"]
                    else colors[obj["class_id"]]
                )
            )
            cv2.rectangle(panel, (a, b), (c, d), color, 1)
            text = (
                names[obj["class_id"]]
                + (" rider" if 13 in obj["semantic_tags"] else "")
                + f" {obj['visible_pixels']}px"
            )
            cv2.putText(
                panel,
                text,
                (max(1, a), max(12, min(295, b - 5))),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.33,
                color,
                1,
                cv2.LINE_AA,
            )
    header = np.zeros((38, 400, 3), np.uint8)
    cv2.putText(
        header,
        source["scene"] + " " + meta["scenes"][index]["stratum"],
        (4, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return np.concatenate([header, panel])


for label, offsets in (("near-occluded", (0, 3)), ("medium-far", (1, 2))):
    panels = [draw(c * 4 + offset) for c in range(6) for offset in offsets]
    canvas = np.concatenate(
        [np.concatenate(panels[n : n + 4], axis=1) for n in range(0, 12, 4)]
    )
    cv2.imwrite(str(root / f"{part}-annotation-{label}.png"), canvas)
coverage = {
    str(c): {s: 0 for s in ("near", "medium", "far", "occluded")} for c in names
}
missing = []
for scene in meta["scenes"]:
    for actor in scene["actors"]:
        if (
            actor["role"] == "target"
            and scene["target_class"] == actor["class_id"]
            and scene["stratum"] in coverage[str(actor["class_id"])]
        ):
            coverage[str(actor["class_id"])][scene["stratum"]] += int(actor["included"])
            if not actor["included"]:
                missing.append(dict(scene=scene["scene"], actor=actor))
report = dict(
    schema="m10-v3-pre-inference-annotation-review",
    created_utc=datetime.now(timezone.utc).isoformat(),
    partition=part,
    data_seal_sha256=sha256_file(data / "benchmark-seal.json"),
    scope="RGB and GT only; no model predictions read; visual crop is inspection only",
    objects=sum(len(g["objects"]) for g in gt["frames"]),
    excluded=sum(len(g["excluded"]) for g in gt["frames"]),
    rider_objects=sum(
        13 in o["semantic_tags"] for g in gt["frames"] for o in g["objects"]
    ),
    primary_coverage=coverage,
    missing_primary=missing,
)
with (root / f"{part}-annotation-review.json").open("x") as f:
    json.dump(report, f, indent=2)
    f.write("\n")
print(json.dumps(report))
