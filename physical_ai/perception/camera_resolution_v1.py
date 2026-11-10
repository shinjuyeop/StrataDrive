"""Variable native camera frames for offline study; frozen runtime remains640x384."""

from dataclasses import dataclass
import hashlib
import zlib
import cv2
import numpy as np
from PIL import Image
from .contract import FrameIdentity
from .dataset import read_json, local_path
from .resolution_v2 import ResolutionDetector
from .resolution_car_v1 import decode as decode_fixed

SCALES = (1, 2, 3, 4, 6)


def scale_of(width, height):
    if (
        type(width) is not int
        or type(height) is not int
        or width % 640
        or width // 640 not in SCALES
        or height != 384 * (width // 640)
    ):
        raise ValueError("declared native camera dimensions required")
    return width // 640


def unpack(root, packet, width, height):
    scale_of(width, height)
    data = local_path(root, packet["path"]).read_bytes()
    expected = width * height * 4
    if (
        packet["compression"] != "zlib-1"
        or len(data) != packet["stored_bytes"]
        or hashlib.sha256(data).hexdigest() != packet["stored_sha256"]
        or packet["raw_bytes"] != expected
    ):
        raise ValueError("stored sensor packet integrity")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(data, expected + 1)
    if (
        len(raw) != expected
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
        or hashlib.sha256(raw).hexdigest() != packet["sha256"]
    ):
        raise ValueError("exact original sensor bytes required")
    return raw


@dataclass(frozen=True)
class NativeFrame:
    identity: FrameIdentity
    width: int
    height: int
    rgb: bytes

    def validate(self):
        self.identity.validate()
        scale_of(self.width, self.height)
        if type(self.rgb) is not bytes or len(self.rgb) != self.width * self.height * 3:
            raise ValueError("native RGB payload layout")


def health(frame):
    frame.validate()
    rgb = np.frombuffer(frame.rgb, np.uint8).reshape(frame.height, frame.width, 3)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    values = dict(
        luma_std=float(gray.std()),
        near_black_fraction=float(np.mean(gray <= 5)),
        near_white_fraction=float(np.mean(gray >= 250)),
    )
    if (
        values["luma_std"] < 2
        or values["near_black_fraction"] > 0.98
        or values["near_white_fraction"] > 0.98
    ):
        raise ValueError("image information unavailable")
    return values


class NativeDataset:
    def __init__(self, path):
        self.path = path
        self.manifest = read_json(path)
        m = self.manifest
        if (
            m["schema"] != "m10-highres-rgb-only-v1"
            or m["partition"] != "development"
            or len(m["frames"]) not in (3, 81)
        ):
            raise ValueError("development RGB-only camera study required")
        self.scale = scale_of(m["camera"]["width"], m["camera"]["height"])

    def frames(self):
        m = self.manifest
        seen = set()
        previous = None
        for row in m["frames"]:
            if set(row) != {"scene", "frame", "source_ns", "rgb_sha256", "rgb_raw"}:
                raise ValueError("RGB-only row fields")
            identity = FrameIdentity(
                m["epoch"], m["clock_instance"], row["frame"], row["source_ns"]
            )
            identity.validate()
            if previous is not None and (
                identity.frame <= previous.frame
                or identity.source_ns <= previous.source_ns
            ):
                raise ValueError("native source order")
            previous = identity
            packet = row["rgb_raw"]
            path = local_path(self.path.parent, packet["path"])
            if path in seen:
                raise ValueError("native raw file reused")
            seen.add(path)
            raw = unpack(
                self.path.parent, packet, m["camera"]["width"], m["camera"]["height"]
            )
            rgb = (
                np.frombuffer(raw, np.uint8)
                .reshape(m["camera"]["height"], m["camera"]["width"], 4)[:, :, 2::-1]
                .copy()
                .tobytes()
            )
            if hashlib.sha256(rgb).hexdigest() != row["rgb_sha256"]:
                raise ValueError("native RGB SHA")
            frame = NativeFrame(
                identity, m["camera"]["width"], m["camera"]["height"], rgb
            )
            frame.validate()
            yield row, frame


def prepare(frame):
    health(frame)
    rgb = np.frombuffer(frame.rgb, np.uint8).reshape(frame.height, frame.width, 3)
    image = Image.fromarray(rgb).resize((960, 960), Image.Resampling.BILINEAR)
    tensor = np.asarray(image, np.float32).transpose(2, 0, 1)[None] / 255.0
    return dict(
        images=np.ascontiguousarray(tensor),
        orig_target_sizes=np.array([[frame.width, frame.height]], np.int64),
    )


def canonical(raw, scale):
    if scale not in SCALES:
        raise ValueError("undeclared source scale")
    result = {k: v.copy() for k, v in raw.items()}
    result["boxes"] = result["boxes"] / np.float32(scale)
    return result


def decode(raw, scale):
    return decode_fixed(canonical(raw, scale))


class NativeDetector(ResolutionDetector):
    def prepare(self, frame):
        return prepare(frame)
