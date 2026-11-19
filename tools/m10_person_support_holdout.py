"""Acquire a disjoint, model-free preparation, then one nominated six-class holdout."""

import argparse
import hashlib
from pathlib import Path
import os
import shutil
import stat
import subprocess

from m10_capture_fresh_quality import BASE as OLD, PYTHON, ROOT, TESTS
from m10_collect_occlusion_transfer import capture_scenes
from m10_verify_parking_candidate import sha, verify
from fresh_quality_2k_review import read, write
from person_support_plan import plans, validate_retained

WORK = ROOT / "build/m10-person-support-v1"
BASE = WORK / "holdout"
ADDITIVE = ROOT / "build/m10-person-additive-v2"
SERIES = ROOT / "docs/test-plan/evidence/m10_person_additive_v2"
PLAN = BASE / "plan"


def materialize():
    PLAN.mkdir(parents=True, exist_ok=True)
    for name, value in plans().items():
        path = PLAN / (name + ".json")
        if not path.exists():
            write(path, value)
    validate_retained(PLAN)


def record(path, value):
    if path.exists():
        if value != read(path):
            raise ValueError(f"retained result changed: {path}")
    else:
        write(path, value)


def nomination():
    from person_support_replay import BUNDLE

    verify(BUNDLE)
    for key, expected in read(OLD / "freeze.json")["files"].items():
        if sha(ROOT / key) != expected:
            raise ValueError(f"original dependency changed: {key}")
    selected = ADDITIVE / "additive-selection.json"
    if read(selected) != read(SERIES / selected.name) or not all(
        r["passed"] for r in read(selected)["scores"].values()
    ):
        raise ValueError("registered multi-road selection")
    cards = [
        ADDITIVE / n
        for n in (
            "archive.json",
            "replication.json",
            "evaluation-development-01-score.json",
        )
    ]
    if not all(read(p)["passed"] for p in cards):
        raise ValueError("development or replication gates")
    prep = [
        p
        for p in sorted((BASE / "runs").glob("preparation-*/visibility.json"))
        if read(p)["status"] == "PASS"
        and read(p)["plan_sha256"] == sha(PLAN / "preparation.json")
    ]
    if not prep:
        raise ValueError("model-free preparation")
    paths = [
        *cards,
        prep[-1],
        selected,
        SERIES / "protocol.json",
        OLD / "freeze.json",
        BUNDLE / "manifest.json",
        PLAN / "evaluation.json",
        Path(__file__).resolve(),
        ROOT / "tools/m10_collect_occlusion_transfer.py",
        *(
            TESTS / name
            for name in (
                "person_additive.py",
                "person_additive_transfer.py",
                "person_support_plan.py",
                "person_support_replay.py",
                "person_zoom_validation.py",
                "parking_onnx_replay.py",
                "person_pair_candidate.py",
            )
        ),
    ]
    return dict(
        site=plans()["sites"]["selected"][-1],
        frames=81,
        files={str(p.relative_to(ROOT)): sha(p) for p in paths},
    )


def review_run(run):
    from PIL import Image
    import fresh_quality_2k_review as reviewer
    from person_support_replay import CACHE

    prior = reviewer.previous_images(run)
    for name in (
        "pairs-train",
        "pairs-validation",
        "archive-train",
        "archive-validation",
    ):
        prior.update(x["rgb"] for x in read(CACHE / name / "index.json"))
    for ds in (*WORK.glob("*/dataset"), *ADDITIVE.glob("*/dataset")):
        if (ds / "labels.json").exists():
            prior.update(x["rgb_sha256"] for x in read(ds / "labels.json"))
        else:
            for path in ds.glob("*.png"):
                with Image.open(path) as im:
                    prior.add(hashlib.sha256(im.convert("RGB").tobytes()).hexdigest())
    # This isolated CLI binds the original reviewed capture routine to the new plan.
    previous = reviewer.previous_images
    reviewer.BASE = BASE
    reviewer.validate_retained = validate_retained
    reviewer.previous_images = lambda current: prior | previous(current)
    try:
        return reviewer.review(run)
    finally:
        reviewer.BASE = OLD
        reviewer.previous_images = previous
        from fresh_quality_2k_plan import validate_retained as original

        reviewer.validate_retained = original


def boot_cache(run, restore):
    manifest = read(
        ROOT / "docs/test-plan/evidence/m10_cuda_resize_v1/cache-manifest.json"
    )
    (entry,) = [
        e
        for e in manifest["entries"]
        if Path(e["path"]).name == "Boot.ddc"
        and e.get("original_inode")
        and Path(e["path"]).is_file()
        and Path(e["path"]).stat().st_ino == e["original_inode"]
    ]
    path, backup = Path(entry["path"]), Path(entry["target"])
    before = path.stat()
    if (
        path.is_symlink()
        or (before.st_ino, before.st_dev)
        != (entry["original_inode"], entry["original_device"])
        or sha(backup) != entry["sha256"]
    ):
        raise ValueError("boot cache identity")
    if restore:
        if any(
            subprocess.run(["pgrep", "-x", name], stdout=subprocess.DEVNULL).returncode
            == 0
            for name in ("UE4Editor", "UE4Editor-Cmd")
        ):
            raise RuntimeError("editor still active")
        if sha(path) != entry["sha256"]:
            with (run / "boot-after.ddc").open("xb") as save, path.open("rb") as src:
                shutil.copyfileobj(src, save)
            with backup.open("rb") as src, path.open("r+b") as dest:
                shutil.copyfileobj(src, dest)
                dest.truncate()
                dest.flush()
                os.fsync(dest.fileno())
        os.chmod(path, entry["mode"])
        os.utime(path, ns=(before.st_atime_ns, entry["mtime_ns"]))
    st = path.stat()
    if (st.st_size, st.st_mtime_ns, stat.S_IMODE(st.st_mode), sha(path)) != (
        entry["bytes"],
        entry["mtime_ns"],
        entry["mode"],
        entry["sha256"],
    ):
        raise ValueError("shared cache differs from original")
    if restore:
        write(
            run / "boot-restoration.json",
            dict(path=str(path), inode=st.st_ino, sha256=entry["sha256"]),
        )


def acquire(phase, attempt):
    materialize()
    run = BASE / "runs" / f"{phase}-holdout-{attempt:02d}"
    plan = PLAN / (phase + ".json")
    mark = SERIES / "nomination.json"
    if phase == "evaluation":
        if any((BASE / "runs").glob("evaluation-*/dataset/rgb/*.bgra.z")):
            raise ValueError("evaluation previously acquired")
        if read(mark) != nomination():
            raise ValueError("prospective nomination changed")
    if run.exists():
        raise FileExistsError(run)
    boot_cache(run, False)
    try:
        capture_scenes(
            run,
            "Town04_Opt",
            [
                PYTHON,
                Path(__file__).resolve(),
                "client",
                "--plan",
                plan,
                "--output",
                run / "dataset",
            ],
            acquisition=dict(
                phase=phase,
                partition="holdout",
                plan_sha256=sha(plan),
                selection_sha256=sha(mark) if phase == "evaluation" else None,
            ),
            timeout=1200,
        )
    finally:
        if (run / "server.json").exists():
            boot_cache(run, True)
    result = review_run(run)
    if result["status"] != "PASS":
        raise ValueError(f"visibility failed; see {run}/visibility.json")


def adjudicate():
    from fresh_quality_2k_score import predict, score
    from person_support_replay import six_class

    run = BASE / "runs/evaluation-holdout-01"
    mark = SERIES / "nomination.json"
    server, vis = read(run / "server.json"), read(run / "visibility.json")
    if (
        read(mark) != nomination()
        or server["selection_sha256"] != sha(mark)
        or vis["status"] != "PASS"
        or vis["server_sha256"] != sha(run / "server.json")
        or vis["capture_sha256"] != sha(run / "dataset/capture.json")
    ):
        raise ValueError("holdout evidence association")
    if not (run / "baseline/predictions.json").exists():
        predict(run, "baseline")
    if not all(r["valid"] for r in read(run / "baseline/predictions.json")["rows"]):
        raise ValueError("invalid baseline predictions")
    record(run / "baseline/score.json", score(run, "baseline"))
    from person_additive_transfer import infer_additive

    six_class(
        ADDITIVE,
        run,
        read(ADDITIVE / "additive-selection.json")["config"],
        detector=infer_additive,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=("client", "preparation", "evaluation", "score", "plan", "nominate"),
    )
    p.add_argument("--attempt", type=int, default=1)
    p.add_argument("--plan", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.action == "client":
        import fresh_quality_2k_capture as client

        client.validate_retained = validate_retained
        args.port, args.partition = 2400, "holdout"
        raise SystemExit(client.capture(args))
    elif args.action == "nominate":
        if any((BASE / "runs").glob("evaluation-*/dataset/rgb/*.bgra.z")):
            raise ValueError("holdout already consumed")
        record(SERIES / "nomination.json", nomination())
    elif args.action == "plan":
        materialize()
    elif args.action == "score":
        adjudicate()
    else:
        acquire(args.action, args.attempt)
