from pathlib import Path
import json
import sys
import hashlib
import numpy as np
from PIL import Image, ImageDraw

root = Path.cwd()
sys.path.insert(0, str(root))
from physical_ai.perception.dataset import RgbDataset  # noqa: E402

base = root / "build/m10-model-screen-v2"
f = json.loads((base / "freeze.json").read_text())
selected = json.loads((base / "selection.json").read_text())
candidates = list(selected["candidates"])
panels = []
# Fixed semantic scene indices, selected without viewing any candidate prediction.
for group, key, index in [
    ("calibration", "v4", 6),
    ("calibration", "v6", 14),
    ("check", "v8", 3),
]:
    spec = f["datasets"][group][key]
    data = root / spec["path"]
    sources = list(RgbDataset(data / "rgb.json").frames())
    source, frame = sources[index]
    truth = json.loads((data / "evaluation-only-gt.json").read_text())["frames"][index]
    canvas = Image.new("RGB", (1280, 432 * 3), (18, 22, 28))
    for n, candidate in enumerate(candidates):
        run = json.loads((base / "runs" / candidate / group / "run.json").read_text())
        row = next(
            r
            for r in run["rows"]
            if r["dataset"] == key and r["scene"] == source["scene"]
        )
        threshold = selected["candidates"][candidate]["threshold"]
        prediction = row["predictions"][str(threshold)]
        assert prediction["valid"] and row["rgb_sha256"] == source["rgb_sha256"]
        im = Image.fromarray(np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3))
        draw = ImageDraw.Draw(im)
        for obj in truth["objects"]:
            box = tuple(obj["box"])
            draw.rectangle(box, outline=(60, 255, 90), width=2)
            draw.text(
                (box[0], max(0, box[1] - 11)),
                f"GT {obj['class_id']}",
                fill=(60, 255, 90),
                stroke_width=1,
                stroke_fill=(0, 0, 0),
            )
        for obj in prediction["detections"]:
            box = tuple(obj["box"])
            draw.rectangle(box, outline=(255, 70, 70), width=1)
            draw.text(
                (box[0], min(370, box[3])),
                f"{obj['class_id']} {obj['score']:.2f}",
                fill=(255, 100, 100),
                stroke_width=1,
                stroke_fill=(0, 0, 0),
            )
        x, y = (n % 2) * 640, (n // 2) * 432
        canvas.paste(im, (x, y + 48))
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (x + 10, y + 5),
            f"{candidate} threshold={threshold} | {key} scene={index}",
            fill="white",
        )
        draw.text(
            (x + 10, y + 23),
            "GREEN=all positive GT | RED=prediction | 0person 1bicycle 2car 3moto 5bus 7truck",
            fill=(190, 200, 210),
        )
    path = base / f"{key}-scene-{index:02d}.png"
    canvas.save(path)
    panels.append(
        dict(
            file=path.name,
            rgb_sha256=source["rgb_sha256"],
            dataset=key,
            scene=source["scene"],
            thresholds={k: v["threshold"] for k, v in selected["candidates"].items()},
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    )
(base / "visual-panels.json").write_text(
    json.dumps(
        dict(
            status="PASS",
            selection_sha256=hashlib.sha256(
                (base / "selection.json").read_bytes()
            ).hexdigest(),
            panels=panels,
            holdout_access=False,
        ),
        indent=2,
    )
    + "\n"
)
