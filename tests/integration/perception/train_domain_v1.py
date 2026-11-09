"""Pinned, full-parameter FP32 fine-tuning on the frozen development corpus."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.domain_data_v1 import DomainDataset, write_json_new
from physical_ai.perception.training_v1 import (
    HEAD_TO_NATIVE,
    ROOT,
    check_freeze,
    decode_six,
    model,
    pack_sample,
    state_digest,
)
from evaluate import counts, valid_box

PROFILE = ROOT / "profiles/perception-training-v1.json"


def score_records(dataset, records):
    if len(records) != len(dataset.images) or {r["image_id"] for r in records} != set(
        dataset.images
    ):
        raise ValueError("validation denominator")
    totals = {str(c): dict(tp=0, fp=0, fn=0) for c in HEAD_TO_NATIVE}
    for r in records:
        im = dataset.images[r["image_id"]]
        if r["rgb_sha256"] != im["rgb_sha256"]:
            raise ValueError("validation RGB identity")
        for p in r["detections"]:
            if (
                p["class_id"] not in HEAD_TO_NATIVE
                or not valid_box(p["box"])
                or not 0.35 <= p["score"] <= 1
            ):
                raise ValueError("prediction contract")
        truth = []
        for a in dataset.targets[im["id"]]:
            x, y, w, h = a["bbox"]
            truth.append(dict(class_id=a["category_id"] - 1, box=[x, y, x + w, y + h]))
        for c, values in counts(r["detections"], truth).items():
            for key, val in values.items():
                totals[c][key] += val
    for v in totals.values():
        tp, fp, fn = (v[k] for k in ("tp", "fp", "fn"))
        v.update(
            precision=tp / (tp + fp) if tp + fp else 0.0,
            recall=tp / (tp + fn) if tp + fn else 0.0,
            f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        )
    tp, fp, fn = (sum(v[k] for v in totals.values()) for k in ("tp", "fp", "fn"))
    return dict(
        frames=len(records),
        objects=sum(len(a) for a in dataset.targets.values()),
        per_class=totals,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=tp / (tp + fp) if tp + fp else 0.0,
        recall=tp / (tp + fn) if tp + fn else 0.0,
        micro_f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        macro_f1=sum(v["f1"] for v in totals.values()) / 6,
    )


def rgb_samples(dataset):
    return list(dataset.samples())


def evaluate(net, samples, dataset, output, six=True):
    import torch
    from physical_ai.perception.yolox import postprocess

    net.eval()
    records = []
    with torch.inference_mode():
        for im, rgb, labels in samples:
            image, _ = pack_sample(rgb, labels)
            raw = net(torch.from_numpy(image[None]).cuda()).cpu().numpy()
            detected = decode_six(raw) if six else postprocess(raw)
            records.append(
                dict(
                    image_id=im["id"],
                    rgb_sha256=im["rgb_sha256"],
                    detections=[
                        dict(class_id=d.class_id, score=d.score, box=list(d.box))
                        for d in detected
                    ],
                )
            )
    write_json_new(output, records)
    return score_records(dataset, records)


def train(args):
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    import numpy as np
    import torch

    p = json.loads(PROFILE.read_text())
    if p["schema"] != "m10-domain-training-v1" or p["head_to_native"] != list(
        HEAD_TO_NATIVE
    ):
        raise ValueError("training profile contract")
    if sha256_file(args.data / "dataset.json") != p["dataset_manifest_sha256"]:
        raise ValueError("fixed dataset identity")
    if torch.__version__ != "2.5.1+cu124" or not torch.cuda.is_available():
        raise ValueError("pinned CUDA training required")
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    torch.set_num_threads(4)
    torch.manual_seed(p["seed"])
    torch.cuda.manual_seed_all(p["seed"])
    random.seed(p["seed"])
    np.random.seed(p["seed"])
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    files = [
        PROFILE,
        ROOT / "docs/test-plan/perception-training-v1-protocol.md",
        ROOT / "physical_ai/requirements-training-v1.txt",
    ]
    files += sorted((ROOT / "physical_ai/perception").glob("*.py"))
    files += sorted((ROOT / "tests/integration/perception").glob("*train*v1.py"))
    files += [ROOT / "tests/integration/perception/evaluate.py"]
    files += [
        f
        for f in sorted((ROOT / "third_party/megvii-yolox-training-v1").rglob("*"))
        if f.is_file() and "__pycache__" not in f.parts
    ]
    frozen = dict(
        schema="m10-training-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        baseline=os.popen("git rev-parse HEAD").read().strip(),
        sources={str(f.relative_to(ROOT)): sha256_file(f) for f in files},
        dataset_sha256=sha256_file(args.data / "dataset.json"),
        pretrained_sha256=sha256_file(args.pretrained),
        profile=p,
        environment=dict(
            python=sys.version,
            torch=torch.__version__,
            gpu=torch.cuda.get_device_name(),
            cuda=torch.version.cuda,
            cudnn=torch.backends.cudnn.version(),
        ),
        quality_holdout_read=False,
        runtime_promotion=False,
    )
    write_json_new(out / "freeze.json", frozen)
    shutil.copy2(PROFILE, out / "profile.json")
    snapshot = out / "source"
    for name in frozen["sources"]:
        dest = snapshot / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    train_data, val_data = (
        DomainDataset(args.data, "train"),
        DomainDataset(args.data, "validation"),
    )
    train_data.validate_split(val_data)
    if {"train": len(train_data.images), "validation": len(val_data.images)} != p[
        "dataset_counts"
    ]:
        raise ValueError("dataset counts")
    training, validation = rgb_samples(train_data), rgb_samples(val_data)
    net80 = model(args.pretrained, six=False).cuda()
    baseline = evaluate(
        net80, validation, val_data, out / "baseline80-predictions.json", six=False
    )
    write_json_new(out / "baseline80-score.json", baseline)
    del net80
    torch.cuda.empty_cache()
    net = model(args.pretrained).cuda()
    initial_bn = {
        n: b.clone()
        for n, b in net.named_buffers()
        if "running_" in n or "num_batches_tracked" in n
    }
    initial = evaluate(net, validation, val_data, out / "epoch-00-predictions.json")
    write_json_new(out / "epoch-00-score.json", initial)
    torch.save(
        dict(
            model=net.state_dict(),
            epoch=0,
            freeze_sha256=sha256_file(out / "freeze.json"),
        ),
        out / "best.pth",
    )
    best = dict(epoch=0, score=initial["macro_f1"], state_sha256=state_digest(net))
    optimizer = torch.optim.AdamW(
        net.parameters(), lr=p["learning_rate"], weight_decay=p["weight_decay"]
    )
    steps = math.ceil(len(training) / p["batch_size"])
    total_steps = p["epochs"] * steps
    generator = np.random.default_rng(p["seed"])
    history = [dict(epoch=0, metrics=initial, state_sha256=best["state_sha256"])]
    print(
        json.dumps(
            dict(stage="initialized", baseline80=baseline, initialized6=initial)
        ),
        flush=True,
    )
    for epoch in range(1, p["epochs"] + 1):
        check_freeze(out / "freeze.json")
        net.train()
        for module in net.modules():
            if isinstance(module, torch.nn.BatchNorm2d):
                module.eval()
        order = generator.permutation(len(training))
        losses = []
        seen = []
        begin = time.monotonic()
        for batch, start in enumerate(range(0, len(order), p["batch_size"])):
            if time.monotonic() - started > p["wall_budget_seconds"]:
                raise TimeoutError("fixed training wall budget")
            indices = order[start : start + p["batch_size"]]
            packed = [
                pack_sample(
                    training[i][1],
                    training[i][2],
                    generator.random() < p["horizontal_flip_probability"],
                )
                for i in indices
            ]
            images = torch.from_numpy(np.stack([a for a, _ in packed])).cuda()
            targets = torch.from_numpy(np.stack([b for _, b in packed])).cuda()
            step = (epoch - 1) * steps + batch
            warm = p["warmup_epochs"] * steps
            fraction = (
                (0.1 + 0.9 * (step + 1) / warm)
                if step < warm
                else (
                    p["cosine_min_fraction"]
                    + (1 - p["cosine_min_fraction"])
                    * 0.5
                    * (1 + math.cos(math.pi * (step - warm) / (total_steps - warm)))
                )
            )
            for group in optimizer.param_groups:
                group["lr"] = p["learning_rate"] * fraction
            optimizer.zero_grad(set_to_none=True)
            result = net(images, targets)
            loss = result["total_loss"]
            if not torch.isfinite(loss):
                raise ValueError("nonfinite training loss")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(
                net.parameters(), p["gradient_clip_norm"], error_if_nonfinite=True
            )
            optimizer.step()
            losses.append(
                dict(
                    loss=float(loss.detach()),
                    gradient_norm=float(norm),
                    images=len(indices),
                )
            )
            seen.extend(int(i) for i in indices)
        if sorted(seen) != list(range(len(training))):
            raise ValueError("all training frames exactly once per epoch")
        for name, before in initial_bn.items():
            if not torch.equal(dict(net.named_buffers())[name], before):
                raise ValueError("frozen batchnorm buffer changed")
        metrics = evaluate(
            net, validation, val_data, out / f"epoch-{epoch:02d}-predictions.json"
        )
        write_json_new(out / f"epoch-{epoch:02d}-score.json", metrics)
        digest = state_digest(net)
        torch.save(
            dict(
                model=net.state_dict(),
                epoch=epoch,
                freeze_sha256=sha256_file(out / "freeze.json"),
            ),
            out / "last.pth",
        )
        if metrics["macro_f1"] > best["score"]:
            best = dict(epoch=epoch, score=metrics["macro_f1"], state_sha256=digest)
            shutil.copy2(out / "last.pth", out / "best.pth")
        row = dict(
            epoch=epoch,
            metrics=metrics,
            state_sha256=digest,
            loss_mean=sum(r["loss"] * r["images"] for r in losses) / len(training),
            batches=losses,
            frames_seen=len(seen),
            learning_rate=optimizer.param_groups[0]["lr"],
            elapsed_wall_seconds=time.monotonic() - begin,
            best_epoch=best["epoch"],
        )
        write_json_new(out / f"epoch-{epoch:02d}.json", row)
        history.append(row)
        print(
            json.dumps(
                {
                    k: row[k]
                    for k in (
                        "epoch",
                        "metrics",
                        "loss_mean",
                        "elapsed_wall_seconds",
                        "best_epoch",
                    )
                }
            ),
            flush=True,
        )
    check_freeze(out / "freeze.json")
    final = dict(
        schema="m10-training-result-v1",
        status="COMPLETE",
        epochs=p["epochs"],
        optimizer_steps=steps * p["epochs"],
        train_images=813,
        validation_images=267,
        best=best,
        best_checkpoint_sha256=sha256_file(out / "best.pth"),
        last_checkpoint_sha256=sha256_file(out / "last.pth"),
        initial_state_sha256=history[0]["state_sha256"],
        last_state_sha256=history[-1]["state_sha256"],
        weights_changed=history[0]["state_sha256"] != history[-1]["state_sha256"],
        trained_candidate_selected=best["epoch"] > 0,
        peak_cuda_memory_bytes=torch.cuda.max_memory_allocated(),
        elapsed_wall_seconds=time.monotonic() - started,
        quality_holdout_read=False,
        model_accuracy_acceptance="NOT EVALUATED ON NEW QUALITY HOLDOUT",
        runtime_promotion=False,
    )
    write_json_new(out / "result.json", final)
    print(json.dumps(final), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--pretrained", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    train(p.parse_args())
