"""Fixed model-free panels; rendering does not change any annotation/input."""

from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json, local_path
from physical_ai.perception.domain_data_v1 import write_json_new
from physical_ai.perception.contract import sha256_file, CLASSES


def review(data, output, prefix):
    data, output = Path(data), Path(output)
    manifest = read_json(data / "data.json")
    support = read_json(data / "support.json")["frames"]
    selected = []
    if manifest["split"] == "preflight":
        selected = [
            n
            for n, r in enumerate(support)
            if (r["stratum"] == "preflight-near" and r["orientation_degrees"] == 90)
            or (r["stratum"] == "preflight-far" and r["orientation_degrees"] == 0)
        ]
    else:
        selected = [
            n
            for n, r in enumerate(support)
            if r["stratum"] in ("near", "far")
            and r["orientation_degrees"]
            == {"ClearNoon": 0, "WetCloudyNoon": 90, "CloudySunset": 180}[r["weather"]]
        ]
        selected += [
            n
            for n, r in enumerate(support)
            if r["stratum"] == "occluded" and r["weather"] == "ClearNoon"
        ]
    if len(support) == 12 and all(r["weather"] == "WetCloudyNoon" for r in support):
        selected = list(range(12))
    panels = []
    for index in selected:
        row = manifest["frames"][index]
        meta = support[index]
        rgb = np.frombuffer(
            local_path(data, row["rgb_path"]).read_bytes(), np.uint8
        ).reshape(384, 640, 3)
        panel = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        for obj in row["objects"]:
            a, b, c, d = obj["box"]
            color = (255, 255, 0) if obj["quality_eligible"] else (140, 140, 140)
            if 13 in obj["semantic_tags"]:
                color = (255, 80, 255)
            cv2.rectangle(panel, (a, b), (c, d), color, 1)
            cv2.putText(
                panel,
                f"{CLASSES[obj['class_id']]} {obj['visible_pixels']}px",
                (max(0, a), max(12, b - 3)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.3,
                color,
                1,
                cv2.LINE_AA,
            )
        panel = cv2.resize(panel, (400, 240), interpolation=cv2.INTER_NEAREST)
        header = np.zeros((42, 400, 3), np.uint8)
        for n, text in enumerate(
            [
                row["scene"],
                f"{meta['weather']} {meta['stratum']} yaw{meta['orientation_degrees']}",
            ]
        ):
            cv2.putText(
                header,
                text,
                (3, 16 + n * 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.33,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        panels.append(np.concatenate((header, panel)))
    images = []
    for page in range(0, len(panels), 12):
        group = panels[page : page + 12]
        while len(group) < 12:
            group.append(np.zeros_like(panels[0]))
        canvas = np.concatenate(
            [np.concatenate(group[n : n + 4], axis=1) for n in (0, 4, 8)]
        )
        name = f"{prefix}-{page // 12:02d}.png"
        assert cv2.imwrite(str(output / name), canvas)
        images.append(name)
    report = dict(
        schema="m10-domain-review-v1",
        data_sha256=sha256_file(data / "data.json"),
        fixed_selected_frames=len(selected),
        all_raw_frames=len(manifest["frames"]),
        selected_scenes=[manifest["frames"][n]["scene"] for n in selected],
        panels=images,
        scope="Fixed weather/view/near/far and occlusion GT panels, not detector predictions; display resize never changes input RGB",
    )
    write_json_new(output / f"{prefix}-panels.json", report)
    return report
