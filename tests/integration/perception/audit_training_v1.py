"""Replay every validation score/selection and inspect retained learned tensors."""

import argparse
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.domain_data_v1 import DomainDataset, write_json_new
from physical_ai.perception.training_v1 import ROOT, check_freeze, model, state_digest
from train_domain_v1 import score_records


def read(path):
    return json.loads(Path(path).read_text())


def audit(root, data, inspect_weights=True):
    root, data = Path(root), Path(data)
    run = root / "run-01"
    freeze = check_freeze(run / "freeze.json")
    for name, digest in freeze["sources"].items():
        if sha256_file(run / "source" / name) != digest:
            raise ValueError("training snapshot bytes")
    p = freeze["profile"]
    if p != read(root / "run-01/profile.json") or p != read(
        ROOT / "profiles/perception-training-v1.json"
    ):
        raise ValueError("training profile lineage")
    if sha256_file(data / "dataset.json") != p["dataset_manifest_sha256"]:
        raise ValueError("training corpus identity")
    train, val = DomainDataset(data, "train"), DomainDataset(data, "validation")
    train.validate_split(val)
    if len(train.images) != 813 or len(val.images) != 267:
        raise ValueError("corpus denominator")
    baseline = score_records(val, read(run / "baseline80-predictions.json"))
    if baseline != read(run / "baseline80-score.json"):
        raise ValueError("80-class baseline score")
    best = None
    epochs = []
    for epoch in range(25):
        metrics = score_records(val, read(run / f"epoch-{epoch:02d}-predictions.json"))
        if metrics != read(run / f"epoch-{epoch:02d}-score.json"):
            raise ValueError("independent all-positive score replay")
        if best is None or metrics["macro_f1"] > best["score"]:
            best = dict(epoch=epoch, score=metrics["macro_f1"])
        if epoch:
            row = read(run / f"epoch-{epoch:02d}.json")
            batches = row["batches"]
            if (
                row["metrics"] != metrics
                or row["epoch"] != epoch
                or row["frames_seen"] != 813
                or len(batches) != 204
                or [b["images"] for b in batches] != [4] * 203 + [1]
                or row["best_epoch"] != best["epoch"]
                or not all(
                    np.isfinite([b["loss"], b["gradient_norm"]]).all() for b in batches
                )
                or row["loss_mean"]
                != sum(b["loss"] * b["images"] for b in batches) / 813
            ):
                raise ValueError("epoch loss/order/batch accounting")
        epochs.append(
            dict(
                epoch=epoch, macro_f1=metrics["macro_f1"], micro_f1=metrics["micro_f1"]
            )
        )
    result = read(run / "result.json")
    if (
        result["status"] != "COMPLETE"
        or result["epochs"] != 24
        or result["optimizer_steps"] != 4896
        or result["best"]["epoch"] != best["epoch"]
        or result["best"]["score"] != best["score"]
        or result["quality_holdout_read"] is not False
        or result["runtime_promotion"] is not False
        or result["train_images"] != 813
        or result["validation_images"] != 267
        or result["trained_candidate_selected"] != (best["epoch"] > 0)
        or not result["weights_changed"]
    ):
        raise ValueError("training completion/selection")
    for name in ("best", "last"):
        if sha256_file(run / f"{name}.pth") != result[f"{name}_checkpoint_sha256"]:
            raise ValueError("checkpoint retained bytes")
    manifest = read(root / "export/manifest.json")
    if (
        manifest["checkpoint_sha256"] != result["best_checkpoint_sha256"]
        or manifest["training_freeze_sha256"] != sha256_file(run / "freeze.json")
        or manifest["model_sha256"] != sha256_file(root / "export/model.onnx")
        or manifest["state_sha256"] != result["best"]["state_sha256"]
        or manifest["selected_epoch"] != best["epoch"]
    ):
        raise ValueError("export identity chain")
    selected = read(run / f"epoch-{best['epoch']:02d}-score.json")
    for execution in ("cpu", "cuda"):
        report = read(root / f"numeric-{execution}.json")
        records = read(root / f"numeric-{execution}.predictions.json")
        if (
            report["status"] != "PASS"
            or report["validation_score"] != selected
            or score_records(val, records) != selected
            or report["model_sha256"] != manifest["model_sha256"]
            or len(report["probes"]) != 16
        ):
            raise ValueError("all validation numeric replay")
    weight_report = None
    if inspect_weights:
        import torch

        net = model(root / "upstream/yolox_l.pth")
        initial = {n: t.detach().clone() for n, t in net.state_dict().items()}
        if state_digest(net) != result["initial_state_sha256"]:
            raise ValueError("official tensor transplant replay")
        changed = {}
        for name in ("best", "last"):
            checkpoint = torch.load(
                run / f"{name}.pth", map_location="cpu", weights_only=True
            )
            if checkpoint["freeze_sha256"] != sha256_file(run / "freeze.json"):
                raise ValueError("checkpoint freeze binding")
            if checkpoint["epoch"] != (best["epoch"] if name == "best" else 24):
                raise ValueError("checkpoint epoch binding")
            net.load_state_dict(checkpoint["model"], strict=True)
            expected = (
                result["best"]["state_sha256"]
                if name == "best"
                else result["last_state_sha256"]
            )
            if state_digest(net) != expected:
                raise ValueError("learned tensor identity")
            for n, value in net.state_dict().items():
                if not torch.isfinite(value).all():
                    raise ValueError("finite learned tensors")
                if ("running_" in n or "num_batches_tracked" in n) and not torch.equal(
                    value, initial[n]
                ):
                    raise ValueError("BatchNorm statistics changed")
            changed[name] = sum(
                not torch.equal(value, initial[n])
                for n, value in net.named_parameters()
            )
            if name == "last" and not changed[name]:
                raise ValueError("no actual learned parameter")
        weight_report = dict(
            status="PASS",
            changed_parameter_tensors=changed,
            batchnorm_buffers_unchanged=True,
            initial_state_sha256=result["initial_state_sha256"],
            best_state_sha256=result["best"]["state_sha256"],
        )
    return dict(
        schema="m10-training-audit-v1",
        status="PASS",
        train_images=813,
        validation_images=267,
        epochs=24,
        optimizer_steps=4896,
        frozen_sources=len(freeze["sources"]),
        baseline80=baseline,
        initialized6=read(run / "epoch-00-score.json"),
        selected=selected,
        selected_epoch=best["epoch"],
        history=epochs,
        learned_tensors=weight_report,
        all_scores_and_selection_replayed=True,
        numeric_all_validation_counts_equal=True,
        quality_holdout_read=False,
        runtime_promotion=False,
        scope="Frozen fixture-domain training, all validation predictions/selection and retained tensor audit; no retraining replay or independent quality holdout acceptance",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("data", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    report = audit(a.root, a.data)
    write_json_new(a.output, report)
    print(json.dumps(report), flush=True)
