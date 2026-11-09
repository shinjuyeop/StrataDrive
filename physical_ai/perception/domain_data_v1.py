"""Lossless six-class visible-mask development data; no model/training dependency."""

from pathlib import Path
import hashlib
import json
import math
import cv2
import numpy as np
from .contract import CLASSES, sha256_file
from .dataset import read_json, local_path

CATEGORIES = [
    dict(id=c + 1, name=name, supercategory="person" if c == 0 else "vehicle")
    for c, name in CLASSES.items()
]
CATEGORY_TO_NATIVE = {c + 1: c for c in CLASSES}
POLICY = dict(
    width=640,
    height=384,
    quality_min_visible_pixels=25,
    quality_min_box_side=4,
    training_labels="all nonempty visible instances, including small fragments",
    iscrowd=0,
    segmentation="uncompressed COCO RLE, column-major",
    image_format="lossless RGB PNG",
    category_to_native={str(k): v for k, v in CATEGORY_TO_NATIVE.items()},
)


def write_json_new(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def encode_rle(mask):
    if mask.dtype != np.bool_ or mask.shape != (384, 640):
        raise ValueError("mask layout")
    flat = mask.reshape(-1, order="F").astype(np.uint8)
    edges = np.flatnonzero(np.diff(flat)) + 1
    counts = np.diff(np.r_[0, edges, len(flat)]).tolist()
    if flat[0]:
        counts.insert(0, 0)
    return dict(size=[384, 640], counts=counts)


def decode_rle(rle):
    if set(rle) != {"size", "counts"} or rle["size"] != [384, 640]:
        raise ValueError("mask schema")
    counts = rle["counts"]
    if (
        not isinstance(counts, list)
        or not counts
        or any(type(n) is not int or n < 0 for n in counts)
        or sum(counts) != 640 * 384
    ):
        raise ValueError("mask counts")
    return (
        np.repeat(np.arange(len(counts)) % 2, counts)
        .astype(bool)
        .reshape((384, 640), order="F")
    )


def visible_objects(raw):
    """Preserve every positive fragment; quality support stays a separate flag."""
    if len(raw) != 640 * 384 * 4:
        raise ValueError("instance layout")
    p = np.frombuffer(raw, np.uint8).reshape(384, 640, 4)
    tags = p[:, :, 2]
    ids = p[:, :, 1].astype(np.uint16) + (p[:, :, 0].astype(np.uint16) << 8)
    result = []
    for cls, semantics in (
        (0, (12, 13)),
        (1, (19,)),
        (2, (14,)),
        (3, (18,)),
        (5, (16,)),
        (7, (15,)),
    ):
        selected = np.isin(tags, semantics)
        for ident in np.unique(ids[selected]):
            mask = selected & (ids == ident)
            y, x = np.where(mask)
            box = [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]
            area = int(len(x))
            result.append(
                dict(
                    class_id=cls,
                    instance_id=int(ident),
                    box=box,
                    visible_pixels=area,
                    semantic_tags=[int(t) for t in np.unique(tags[mask])],
                    quality_eligible=area >= 25
                    and box[2] - box[0] >= 4
                    and box[3] - box[1] >= 4,
                    segmentation=encode_rle(mask),
                )
            )
    return result


def export(prepared, output, collection_freeze_sha256, plan_sha256):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "annotations").mkdir()
    report = dict(
        schema="m10-domain-dataset-v1",
        policy=POLICY,
        collection_freeze_sha256=collection_freeze_sha256,
        plan_sha256=plan_sha256,
        splits={},
    )
    for split, roots in prepared.items():
        (output / "images" / split).mkdir(parents=True)
        coco = dict(
            info=dict(
                description="Synthetic M10 development data; not quality holdout",
                version="1",
            ),
            licenses=[],
            images=[],
            annotations=[],
            categories=CATEGORIES,
        )
        for root in roots:
            root = Path(root)
            manifest = read_json(root / "data.json")
            if manifest["split"] != split:
                raise ValueError("split binding")
            for row in manifest["frames"]:
                rgb = local_path(root, row["rgb_path"]).read_bytes()
                if (
                    hashlib.sha256(rgb).hexdigest() != row["rgb_sha256"]
                    or len(rgb) != 640 * 384 * 3
                ):
                    raise ValueError("RGB identity")
                name = f"{split}/{row['scene']}.png"
                path = local_path(output / "images", name)
                image = np.frombuffer(rgb, np.uint8).reshape(384, 640, 3)
                ok, png = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                assert ok
                with path.open("xb") as f:
                    f.write(png.tobytes())
                if not np.array_equal(
                    cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB), image
                ):
                    raise ValueError("lossless PNG")
                ident = len(coco["images"]) + 1
                coco["images"].append(
                    dict(
                        id=ident,
                        file_name=name,
                        width=640,
                        height=384,
                        rgb_sha256=row["rgb_sha256"],
                        png_sha256=sha256_file(path),
                        scene=row["scene"],
                        variant_group=row["variant_group"],
                        site=manifest["site"],
                        road_id=manifest["road_id"],
                        capture_sha256=manifest["capture_sha256"],
                    )
                )
                for obj in row["objects"]:
                    x1, y1, x2, y2 = obj["box"]
                    coco["annotations"].append(
                        dict(
                            id=len(coco["annotations"]) + 1,
                            image_id=ident,
                            category_id=obj["class_id"] + 1,
                            bbox=[x1, y1, x2 - x1, y2 - y1],
                            area=obj["visible_pixels"],
                            iscrowd=0,
                            segmentation=obj["segmentation"],
                            m10_quality_eligible=obj["quality_eligible"],
                            m10_semantic_tags=obj["semantic_tags"],
                            m10_instance_id=obj["instance_id"],
                        )
                    )
        path = output / "annotations" / f"instances_{split}.json"
        write_json_new(path, coco)
        report["splits"][split] = dict(
            annotation_path=str(path.relative_to(output)),
            annotation_sha256=sha256_file(path),
            images=len(coco["images"]),
            objects=len(coco["annotations"]),
            small_fragments=sum(
                not a["m10_quality_eligible"] for a in coco["annotations"]
            ),
        )
    write_json_new(output / "dataset.json", report)
    DomainDataset(output, "train").validate_split(DomainDataset(output, "validation"))
    return report


class DomainDataset:
    def __init__(self, root, split):
        self.root = Path(root)
        self.split = split
        manifest = read_json(self.root / "dataset.json")
        if (
            manifest["schema"] != "m10-domain-dataset-v1"
            or manifest["policy"] != POLICY
            or split not in manifest["splits"]
        ):
            raise ValueError("dataset policy/split")
        spec = manifest["splits"][split]
        path = local_path(self.root, spec["annotation_path"])
        if sha256_file(path) != spec["annotation_sha256"]:
            raise ValueError("annotation hash")
        self.coco = read_json(path)
        if self.coco["categories"] != CATEGORIES:
            raise ValueError("category mapping")
        self.images = {im["id"]: im for im in self.coco["images"]}
        self.targets = {n: [] for n in self.images}
        if not self.images or len(
            {im["rgb_sha256"] for im in self.images.values()}
        ) != len(self.images):
            raise ValueError("empty dataset or duplicate RGB within split")
        if (
            len(self.images) != len(self.coco["images"])
            or len(self.images) != spec["images"]
            or len(self.coco["annotations"]) != spec["objects"]
        ):
            raise ValueError("dataset denominator")
        seen = set()
        for ann in self.coco["annotations"]:
            if (
                type(ann["id"]) is not int
                or ann["id"] in seen
                or ann["image_id"] not in self.images
                or ann["category_id"] not in CATEGORY_TO_NATIVE
                or type(ann["iscrowd"]) is not int
                or ann["iscrowd"] != 0
            ):
                raise ValueError("annotation identity")
            seen.add(ann["id"])
            box = ann["bbox"]
            if len(box) != 4 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in box
            ):
                raise ValueError("finite box")
            mask = decode_rle(ann["segmentation"])
            y, x = np.where(mask)
            if (
                not len(x)
                or ann["area"] != len(x)
                or box
                != [
                    int(x.min()),
                    int(y.min()),
                    int(x.max() - x.min() + 1),
                    int(y.max() - y.min() + 1),
                ]
            ):
                raise ValueError("visible mask/area/box")
            qualified = len(x) >= 25 and box[2] >= 4 and box[3] >= 4
            if (
                type(ann["m10_quality_eligible"]) is not bool
                or ann["m10_quality_eligible"] != qualified
            ):
                raise ValueError("quality support flag")
            self.targets[ann["image_id"]].append(ann)
        for im in self.images.values():
            if (im["width"], im["height"]) != (640, 384) or not im[
                "file_name"
            ].startswith(split + "/"):
                raise ValueError("image split/layout")
            path = local_path(self.root / "images", im["file_name"])
            if sha256_file(path) != im["png_sha256"]:
                raise ValueError("PNG hash")
            bgr = cv2.imread(str(path))
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB) if bgr is not None else None
            if (
                rgb is None
                or rgb.shape != (384, 640, 3)
                or hashlib.sha256(rgb.tobytes()).hexdigest() != im["rgb_sha256"]
            ):
                raise ValueError("decoded RGB hash")
        self.manifest = manifest

    def validate_split(self, other):
        for field in (
            "rgb_sha256",
            "site",
            "road_id",
            "variant_group",
            "capture_sha256",
        ):
            if {im[field] for im in self.images.values()} & {
                im[field] for im in other.images.values()
            }:
                raise ValueError("split overlap: " + field)
        return True

    def samples(self):
        for ident, im in self.images.items():
            rgb = cv2.cvtColor(
                cv2.imread(str(local_path(self.root / "images", im["file_name"]))),
                cv2.COLOR_BGR2RGB,
            )
            yield (
                im,
                rgb,
                tuple(
                    dict(
                        native_class=CATEGORY_TO_NATIVE[a["category_id"]],
                        box=tuple(a["bbox"]),
                        quality_eligible=a["m10_quality_eligible"],
                    )
                    for a in self.targets[ident]
                ),
            )
