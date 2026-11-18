"""One bounded fit of D-FINE's car classifier row on verified training splits."""

import argparse
import random
from pathlib import Path

import torch
from torchvision.ops import box_convert, box_iou

from occlusion_transfer_train import (
    BATCH,
    SEED,
    add_archived,
    digest,
    inputs,
    linear_sum_assignment,
    network,
    read,
    validation,
    write,
)


@torch.no_grad()
def examples(model, head, samples):
    features = []
    encoded = []
    hook = head.register_forward_pre_hook(
        lambda module, args: features.append(args[0].detach())
    )
    try:
        for start in range(0, len(samples), BATCH):
            batch = samples[start : start + BATCH]
            images = torch.stack([img for img, _ in batch]).cuda().float() / 255
            output = model.detector(images)
            state = features.pop()
            boxes = box_convert(output["pred_boxes"], "cxcywh", "xyxy").clamp(0, 1)
            boxes *= boxes.new_tensor([640, 384, 640, 384])
            logits = output["pred_logits"][:, :, 2]
            for i, (_, row) in enumerate(batch):
                objects = [o["box"] for o in row["objects"] if o["class_id"] == 2]
                targets = torch.zeros_like(logits[i])
                if objects:
                    overlap = box_iou(boxes[i], boxes.new_tensor(objects))
                    # The first term maximizes the number of distinct usable matches.
                    # Prefer a confident query among equivalent assignments.
                    cost = (
                        100 * (overlap >= 0.5).float()
                        + logits[i].sigmoid()[:, None]
                        + 0.2 * overlap
                    )
                    queries, labels = linear_sum_assignment(-cost.cpu().numpy())
                    targets[queries] = (overlap[queries, labels] >= 0.5).float()
                encoded.append((state[i].cpu(), logits[i].cpu(), targets.cpu()))
    finally:
        hook.remove()
    return encoded


def fit(main_dataset, parked, archived, parent, out):
    out.mkdir(parents=True, exist_ok=False)
    chosen = read(parent / "selection.json")
    if digest(parent / "decoder.pt") != chosen["decoder_sha256"]:
        raise ValueError("parent checkpoint")
    seen = set()
    samples = inputs(main_dataset, seen)
    extra = inputs(parked, seen, parked=True)
    for name, rows in extra.items():
        samples[name].extend(rows)
    add_archived(samples, archived)
    model = network()
    model.detector.decoder.load_state_dict(
        torch.load(parent / "decoder.pt", weights_only=True)
    )
    model.requires_grad_(False)
    head = model.detector.decoder.dec_score_head[-1]
    original_w = head.weight[2].detach().clone()
    original_b = head.bias[2].detach().clone()
    changes = torch.nn.Parameter(torch.zeros(original_w.numel() + 1, device="cuda"))
    optimizer = torch.optim.AdamW([changes], lr=0.001)
    torch.manual_seed(SEED)
    rand = random.Random(SEED)
    recipe = dict(
        parent_sha256=chosen["decoder_sha256"],
        epochs=8,
        seed=SEED,
        lr=0.001,
        batch=16,
        train=len(samples["train"]),
        validation=len(samples["validation"]),
        adjustable_parameters=len(changes),
        class_id=2,
        box_iou=0.5,
        match_scope="one-to-one car assignments",
        selection="Highest validation recall among epochs with precision >= 85% and F1 >= parent, ties highest F1 then earliest. Retain parent if none improves.",
    )
    write(out / "protocol.json", recipe)
    cached = examples(model, head, samples["train"])
    baseline = validation(model, samples["validation"])
    best = (baseline["tp"], baseline["f1"])
    history = [dict(epoch=0, **baseline)]
    selected = 0
    torch.save(model.detector.decoder.state_dict(), out / "decoder.pt")
    for epoch in range(1, 9):
        rand.shuffle(cached)
        for start in range(0, len(cached), 16):
            x, base, labels = (
                torch.stack(v).cuda() for v in zip(*cached[start : start + 16])
            )
            scores = x @ changes[:-1] + changes[-1] + base
            # Sample hard backgrounds for each image; keep every assigned positive.
            negative = scores.masked_fill(labels.bool(), -torch.inf).topk(16).values
            positive = scores[labels.bool()]
            loss = torch.nn.functional.softplus(negative).mean()
            if positive.numel():
                loss = loss + torch.nn.functional.softplus(-positive).mean()
            loss = loss + 0.1 * changes.square().sum()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([changes], 2, error_if_nonfinite=True)
            optimizer.step()
        with torch.no_grad():
            head.weight[2].copy_(original_w + changes[:-1])
            head.bias[2].copy_(original_b + changes[-1])
        card = validation(model, samples["validation"])
        history.append(dict(epoch=epoch, **card))
        print(history[-1], flush=True)
        rank = card["tp"], card["f1"]
        if (
            card["tp"] >= 0.85 * (card["tp"] + card["fp"])
            and card["f1"] >= baseline["f1"]
            and rank > best
        ):
            selected = epoch
            best = rank
            torch.save(model.detector.decoder.state_dict(), out / "decoder.pt")
    write(
        out / "selection.json",
        dict(
            epoch=selected, history=history, decoder_sha256=digest(out / "decoder.pt")
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("dataset", "parked", "archived", "parent", "output"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    torch.set_num_threads(4)
    fit(a.dataset, a.parked, a.archived, a.parent, a.output)
