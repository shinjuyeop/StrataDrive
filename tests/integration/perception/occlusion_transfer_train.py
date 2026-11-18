"""Adapt D-FINE's decoder to independent CARLA imagery and evaluate the selected checkpoint."""

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import random
import sys
import zlib

import numpy as np
from PIL import Image
import torch
from torchvision.ops import (
    box_convert,
    box_iou,
    generalized_box_iou,
    sigmoid_focal_loss,
)

from export_resolution_v1 import configure, model_from_checkpoint
from fresh_quality_2k_review import (
    BASE,
    ROOT,
    EXCLUSIONS,
    digest,
    read,
    rgb_bytes,
    write,
)
from camera_resolution_v1_common import annotate
from physical_ai.perception.camera_resolution_v1 import unpack
from physical_ai.perception.resolution_car_v1 import decode, VECTOR
from physical_ai.perception.class_calibration_v1 import validate_vector
from quality_benchmark_v3 import measure
from run_resolution_v2 import quality

# Use distribution-provided SciPy when the repository training venv has no private copy.
sys.path.append("/usr/lib/python3/dist-packages")
from scipy.optimize import linear_sum_assignment

WEIGHTS = ROOT / "build/m10-model-screen-v2/upstream/dfine-m.pth"
SEED = 83627
EPOCHS = 8
BATCH = 3


def tensor(image):
    resized = image.resize((960, 960), Image.Resampling.BILINEAR)
    return torch.from_numpy(np.array(resized)).permute(2, 0, 1)


def network():
    model, _ = model_from_checkpoint("dfine-m", WEIGHTS)
    configure(model, 960)
    return model.eval().cuda()


def inputs(dataset, seen, parked=False):
    rows = read(dataset / "labels.json")
    plan = read(dataset / "plan.json")
    if (
        read(dataset.parent / "server.json")["status"] != "PASS"
        or (len(rows) not in (60, 120, 180, 240) if parked else len(rows) != 192)
        or len(plan["scenes"]) != len(rows)
    ):
        raise ValueError("incomplete training acquisition")
    for path in EXCLUSIONS:
        seen.update(read(path)["rgb_sha256"])
    for path in (BASE / "runs").glob("*/images.json"):
        seen.update(row["rgb_sha256"] for row in read(path)["frames"])
    samples = {"train": [], "validation": []}
    roads = {"train": set(), "validation": set()}
    for row, scene in zip(rows, plan["scenes"]):
        if row["id"] != scene["id"] or row["split"] != scene["split"]:
            raise ValueError("plan linkage")
        rgb = Image.open(dataset / (row["id"] + ".png")).convert("RGB")
        pixel_hash = hashlib.sha256(rgb.tobytes()).hexdigest()
        if (
            rgb.size != (1280, 768)
            or pixel_hash != row["rgb_sha256"]
            or pixel_hash in seen
        ):
            raise ValueError("duplicate or altered RGB")
        seen.add(pixel_hash)
        mask = zlib.decompress((dataset / (row["id"] + ".mask.z")).read_bytes())
        if hashlib.sha256(mask).hexdigest() != row["mask_sha256"] or annotate(
            mask, 1280, 768
        ) != (row["objects"], row["excluded"]):
            raise ValueError("training mask or annotations changed")
        samples[row["split"]].append((tensor(rgb), row))
        roads[row["split"]].update(scene["roads"])
    expected_map = "Town05_Opt" if parked else "Town04_Opt"
    if plan["map"].split("/")[-1] != expected_map:
        raise ValueError("split map mismatch")
    if roads["train"] & roads["validation"] or (
        not parked
        and (roads["train"] | roads["validation"]) & {6, 35, 41, 43, 45, 47, 29, 36}
    ):
        raise ValueError("split road overlap")
    return samples


def add_archived(samples, images):
    """Replay only the original Town03 training project splits with pinned COCO labels."""
    export = ROOT / "build/m10-domain-data-v1/export"
    metadata = read(export / "dataset.json")
    seen = {r["rgb_sha256"] for batch in samples.values() for _, r in batch}
    for path in (BASE / "runs").glob("*/images.json"):
        seen.update(row["rgb_sha256"] for row in read(path)["frames"])
    for split, expected in (
        ("train", "8132e8126995f8cb2da4d3b388bcb0a486612a127fa93c3815e0b5ba3674dede"),
        (
            "validation",
            "ad4789d7ce6ae9ca5b0830ca3828a120b3fdb6874b22f6a53a74ce780ab482a6",
        ),
    ):
        path = export / metadata["splits"][split]["annotation_path"]
        if digest(path) != expected:
            raise ValueError("original training archive annotation digest")
        coco = read(path)
        annotations = {r["id"]: {"objects": [], "excluded": []} for r in coco["images"]}
        for ann in coco["annotations"]:
            x, y, w, h = ann["bbox"]
            key = "objects" if ann["m10_quality_eligible"] else "excluded"
            annotations[ann["image_id"]][key].append(
                dict(class_id=ann["category_id"] - 1, box=[x, y, x + w, y + h])
            )
        for row in coco["images"]:
            image_path = images / row["file_name"]
            if (
                image_path.parent != images / split
                or digest(image_path) != row["png_sha256"]
            ):
                raise ValueError("archived PNG digest or split")
            rgb = Image.open(image_path).convert("RGB")
            h = hashlib.sha256(rgb.tobytes()).hexdigest()
            if (
                h in seen
                or h != row["rgb_sha256"]
                or row["site"]
                not in ({"train": {14, 31, 74}, "validation": {104}}[split])
            ):
                raise ValueError("archived RGB or site split")
            seen.add(h)
            samples[split].append(
                (tensor(rgb), dict(**annotations[row["id"]], rgb_sha256=h))
            )


def predictions(model, images):
    with torch.no_grad():
        labels, boxes, scores = model(
            images, torch.tensor([[640, 384]], device="cuda").expand(images.shape[0], 2)
        )
    arrays = {
        key: val.cpu().numpy()
        for key, val in (("labels", labels), ("boxes", boxes), ("scores", scores))
    }
    return [
        [
            dict(class_id=d.class_id, score=d.score, box=list(d.box))
            for d in decode({k: v[i : i + 1] for k, v in arrays.items()})
        ]
        for i in range(len(images))
    ]


def validation(model, samples):
    counts = np.zeros(3, np.int64)
    for start in range(0, len(samples), BATCH):
        batch = samples[start : start + BATCH]
        imgs = torch.stack([s[0] for s in batch]).cuda().float() / 255
        for pred, (_, row) in zip(predictions(model, imgs), batch):
            values = measure(pred, row["objects"], row["excluded"])[0]
            counts += [sum(v[k] for v in values.values()) for k in ("tp", "fp", "fn")]
    tp, fp, fn = map(int, counts)
    return dict(tp=tp, fp=fp, fn=fn, f1=2 * tp / max(1, 2 * tp + fp + fn))


def assignment_loss(outputs, targets):
    total = 0
    denominator = 0
    for logits, boxes, (truth, labels) in zip(
        outputs["pred_logits"], outputs["pred_boxes"], targets
    ):
        presence = torch.zeros_like(logits)
        xyxy = box_convert(boxes, "cxcywh", "xyxy")
        if len(labels):
            truth_center = box_convert(truth, "xyxy", "cxcywh")
            giou = generalized_box_iou(xyxy, truth)
            cost = (
                5 * torch.cdist(boxes, truth_center, p=1)
                - 2 * giou
                - 2 * logits.sigmoid()[:, labels]
            )
            i, j = linear_sum_assignment(cost.detach().cpu().numpy())
            presence[i, labels[j]] = 1
            total = (
                total
                + 5 * (boxes[i] - truth_center[j]).abs().sum()
                + 2 * (1 - giou[i, j]).sum()
            )
        total = total + sigmoid_focal_loss(
            logits, presence, alpha=0.25, gamma=2, reduction="sum"
        )
        denominator += len(labels)
    return total / max(denominator, 1)


def train(dataset, out, parked=None, archived=None):
    out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(SEED)
    rand = random.Random(SEED)
    seen = set()
    samples = inputs(dataset, seen)
    if parked:
        extra = inputs(parked, seen, parked=True)
        for split, rows in extra.items():
            samples[split].extend(rows)
    if archived:
        add_archived(samples, archived)
    model = network()
    model.detector.backbone.requires_grad_(False)
    model.detector.encoder.requires_grad_(False)
    params = [p for p in model.detector.decoder.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=2e-5, weight_decay=1e-4)
    best = -1
    history = []
    write(
        out / "protocol.json",
        dict(
            epochs=EPOCHS,
            batch=BATCH,
            seed=SEED,
            lr=2e-5,
            plan_sha256=digest(dataset / "plan.json"),
            labels_sha256=digest(dataset / "labels.json"),
            weights_sha256=digest(WEIGHTS),
            archived_town03_splits=bool(archived),
            parked_labels_sha256=digest(parked / "labels.json") if parked else None,
            parked_plan_sha256=digest(parked / "plan.json") if parked else None,
            selection="Highest validation micro F1, earliest tie, including epoch zero",
            train_size=len(samples["train"]),
            validation_size=len(samples["validation"]),
        ),
    )
    for epoch in range(EPOCHS + 1):
        losses = []
        if epoch:
            order = list(samples["train"])
            rand.shuffle(order)
            for start in range(0, len(order), BATCH):
                imgs, targets = [], []
                for im, row in order[start : start + BATCH]:
                    objects = row["objects"]
                    boxes = torch.tensor(
                        [o["box"] for o in objects], dtype=torch.float32, device="cuda"
                    ).reshape(-1, 4) / torch.tensor([640, 384, 640, 384], device="cuda")
                    if rand.random() < 0.5:
                        im = im.flip(-1)
                        boxes[:, [0, 2]] = 1 - boxes[:, [2, 0]]
                    imgs.append(im)
                    targets.append(
                        (
                            boxes,
                            torch.tensor(
                                [o["class_id"] for o in objects],
                                device="cuda",
                                dtype=torch.long,
                            ),
                        )
                    )
                opt.zero_grad(set_to_none=True)
                output = model.detector(torch.stack(imgs).cuda().float() / 255)
                loss = assignment_loss(output, targets)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(params, 1, error_if_nonfinite=True)
                opt.step()
                losses.append(loss.item())
        card = validation(model, samples["validation"])
        history.append(
            dict(epoch=epoch, loss=np.mean(losses).item() if losses else None, **card)
        )
        print(history[-1], flush=True)
        if card["f1"] > best:
            selected = epoch
            best = card["f1"]
            torch.save(model.detector.decoder.state_dict(), out / "decoder.pt")
    write(
        out / "selection.json",
        dict(
            epoch=selected, history=history, decoder_sha256=digest(out / "decoder.pt")
        ),
    )


def evaluate(out, reference=False):
    model = network()
    if reference:
        out.mkdir(parents=True, exist_ok=False)
    else:
        selected = read(out / "selection.json")
        if digest(out / "decoder.pt") != selected["decoder_sha256"]:
            raise ValueError("selected decoder digest")
        model.detector.decoder.load_state_dict(
            torch.load(out / "decoder.pt", weights_only=True)
        )
    run = BASE / "runs/evaluation-development-01"
    frames = read(run / "images.json")["frames"]
    scenes = read(run / "benchmark.json")["scenes"]
    truth = read(run / "evaluation-only-gt.json")["frames"]
    if not len(frames) == len(scenes) == len(truth) == 81:
        raise ValueError("development denominator")
    results = []
    diagnostics = []
    observations = []
    raw_dir = out / "queries"
    raw_dir.mkdir(exist_ok=False)
    thresholds = validate_vector(VECTOR)
    for f, s, g in zip(frames, scenes, truth):
        rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if (
            hashlib.sha256(rgb).hexdigest() != f["rgb_sha256"]
            or not f["scene"] == s["scene"] == g["scene"]
        ):
            raise ValueError("development pairing")
        image = (
            tensor(Image.frombytes("RGB", (2560, 1536), rgb))[None].cuda().float() / 255
        )
        with torch.no_grad():
            queries = model.detector(image)
            scale = torch.tensor([[640, 384]], device="cuda")
            numeric = model.post(queries, scale)
            raw = {
                k: v.cpu().numpy()
                for k, v in zip(("labels", "boxes", "scores"), numeric)
            }
            pred = [
                dict(class_id=d.class_id, score=d.score, box=list(d.box))
                for d in decode(raw)
            ]
            coordinates = (
                box_convert(queries["pred_boxes"][0], "cxcywh", "xyxy").clamp(0, 1)
                * scale.repeat(1, 2)
            ).cpu()
            confidence = queries["pred_logits"][0].sigmoid().cpu()
        path = raw_dir / f"{len(results):03d}.npz"
        np.savez_compressed(
            path, coordinates=coordinates.numpy(), confidence=confidence.numpy(), **raw
        )
        matched = measure(pred, g["objects"], g["excluded"])[1]
        for index, obj in enumerate(g["objects"]):
            if index in matched:
                continue
            iou = box_iou(coordinates, torch.tensor([obj["box"]]))[:, 0]
            candidates = confidence[iou >= 0.5, obj["class_id"]]
            best = float(candidates.max()) if len(candidates) else None
            reason = (
                "no_matching_box"
                if best is None
                else "below_class_threshold"
                if best < thresholds[obj["class_id"]]
                else "postprocessing_or_competing_match"
            )
            diagnostics.append(
                dict(
                    scene=f["scene"],
                    instance=obj["instance_id"],
                    class_id=obj["class_id"],
                    reason=reason,
                    best_iou=float(iou.max()),
                    best_matching_score=best,
                )
            )
        results.append(
            dict(
                scene=f["scene"],
                rgb_sha256=f["rgb_sha256"],
                detections=pred,
                queries_sha256=digest(path),
            )
        )
        observations.append((s, g, pred, True, False, None))
    write(out / "development-predictions.json", results)
    card = quality(observations)
    if len(diagnostics) != card["micro"]["fn"]:
        raise ValueError("unmatched object accounting")
    write(
        out / "development-misses.json",
        dict(reasons=dict(Counter(r["reason"] for r in diagnostics)), rows=diagnostics),
    )
    write(
        out / "development-score.json",
        {k: v for k, v in card.items() if k != "records"},
    )
    print(card["micro"], card["gates"], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("dataset", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--reference", action="store_true")
    p.add_argument("--archived", type=Path)
    p.add_argument("--parked", type=Path)
    p.add_argument("--evaluate", action="store_true")
    a = p.parse_args()
    torch.set_num_threads(4)
    if a.evaluate or a.reference:
        evaluate(a.output, a.reference)
    else:
        train(a.dataset, a.output, a.parked, a.archived)
