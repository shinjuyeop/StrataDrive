"""RGB-only evaluation input. Ground-truth manifests are a different schema."""

import hashlib
import json
from pathlib import Path
from .contract import CameraFrame, FrameIdentity, HEIGHT, WIDTH


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite JSON: {value}")

    return json.loads(
        Path(path).read_text(), object_pairs_hook=unique, parse_constant=invalid
    )


def local_path(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("relative dataset path required")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("dataset path escapes root")
    return result


class RgbDataset:
    def __init__(self, path):
        self.path = Path(path)
        self.manifest = read_json(path)
        m = self.manifest
        if (
            set(m)
            != {
                "schema",
                "split",
                "capture_sha256",
                "camera",
                "epoch",
                "clock_instance",
                "frames",
            }
            or m["schema"] != "m10-rgb-dataset-v1"
            or m["split"] != "evaluation"
            or m["camera"]
            != {
                "width": WIDTH,
                "height": HEIGHT,
                "camera_id": 1,
                "calibration_revision": 1,
                "format": "RGB8",
            }
            or not isinstance(m["frames"], list)
            or not 1 <= len(m["frames"]) <= 10000
        ):
            raise ValueError("RGB-only manifest schema")
        seen = set()
        last_frame = last_source = None
        for row in m["frames"]:
            if (
                set(row) != {"scene", "frame", "source_ns", "rgb_path", "rgb_sha256"}
                or not isinstance(row["scene"], str)
                or not row["scene"]
                or not isinstance(row["rgb_sha256"], str)
                or len(row["rgb_sha256"]) != 64
            ):
                raise ValueError("RGB row schema")
            identity = FrameIdentity(
                m["epoch"], m["clock_instance"], row["frame"], row["source_ns"]
            )
            identity.validate()
            if last_frame is not None and (
                identity.frame <= last_frame or identity.source_ns <= last_source
            ):
                raise ValueError("RGB source ordering")
            last_frame, last_source = identity.frame, identity.source_ns
            image = local_path(self.path.parent, row["rgb_path"])
            if image in seen:
                raise ValueError("RGB file reused under new identity")
            seen.add(image)

    def frames(self):
        for row in self.manifest["frames"]:
            raw = local_path(self.path.parent, row["rgb_path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["rgb_sha256"]:
                raise ValueError("RGB hash mismatch")
            camera = CameraFrame(
                FrameIdentity(
                    self.manifest["epoch"],
                    self.manifest["clock_instance"],
                    row["frame"],
                    row["source_ns"],
                ),
                raw,
            )
            camera.validate()
            yield row, camera
