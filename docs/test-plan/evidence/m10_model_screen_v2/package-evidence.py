"""Package immutable v2 artifacts; split dense raw outputs by model."""

from pathlib import Path
import hashlib
import json
import tarfile
import shutil

ROOT = Path.cwd()
BASE = ROOT / "build/m10-model-screen-v2"
OUT = ROOT / "docs/test-plan/evidence/m10_model_screen_v2"


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


f = json.loads((BASE / "freeze.json").read_text())
assert json.loads((BASE / "audit.json").read_text())["status"] == "PASS"
entries = {}


def add(p):
    if p.is_symlink() or not p.is_file():
        raise ValueError(p)
    entries[str(p.relative_to(ROOT))] = p


for relative, h in f["sources"].items():
    p = ROOT / relative
    assert digest(p) == h
    add(p)
add(OUT / "check-archive.py")
excluded = {
    "package.log",
    "archive-recheck.json",
    "archive-recheck.log",
    "archive-files.json",
    "docs-check.json",
    "final-integrity.json",
}
for p in BASE.iterdir():
    if (
        p.is_file()
        and p.suffix in (".json", ".log", ".txt", ".py", ".png")
        and p.name not in excluded
    ):
        add(p)
for directory in ["runs", "reference", "reference-v2", "reference-v3", "reference-rgb"]:
    p = BASE / directory
    if p.exists():
        for q in p.rglob("*"):
            if q.is_file() and "__pycache__" not in q.parts:
                add(q)
for p in (BASE / "upstream").iterdir():
    if p.is_file() and not p.name.endswith("-reexport.onnx"):
        add(p)
for paths in f["datasets"].values():
    for spec in paths.values():
        for p in (ROOT / spec["path"]).rglob("*"):
            if p.is_file():
                add(p)
for path in json.loads((BASE / "models.json").read_text()).values():
    add(ROOT / path)
# Small legacy development-only score records support the common0.35 regression.
for key in ["yolox-s", "yolox-l", "rtdetrv2-r18"]:
    add(ROOT / "build/m10-model-screen-v1" / (key + "-score.json"))
manifest = {name: digest(p) for name, p in sorted(entries.items())}
manifest_path = BASE / "archive-files.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
groups = {
    name: []
    for name in [
        "experiment.tar.gz",
        "raw-yolox-s.tar.gz",
        "raw-yolox-l.tar.gz",
        "raw-damo-s.tar.gz",
        "raw-detr.tar.gz",
    ]
}
for name, p in sorted(entries.items()):
    group = "experiment.tar.gz"
    if "/runs/" in name and "/raw/" in name and p.suffix == ".npz":
        candidate = Path(name).parts[3]
        group = (
            "raw-" + candidate + ".tar.gz"
            if candidate in ["yolox-s", "yolox-l", "damo-s"]
            else "raw-detr.tar.gz"
        )
    groups[group].append((name, p))
archives = []
for name, files in groups.items():
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    with tarfile.open(path, "w:gz", compresslevel=1) as archive:
        if name == "experiment.tar.gz":
            archive.add(
                manifest_path, arcname="project/archive-files.json", recursive=False
            )
        for relative, p in files:
            archive.add(p, arcname="project/" + relative, recursive=False)
    archives.append(
        dict(
            file=name,
            bytes=path.stat().st_size,
            sha256=digest(path),
            members=len(files) + (name == "experiment.tar.gz"),
        )
    )
    print(name, path.stat().st_size, flush=True)
(OUT / "archives.json").write_text(json.dumps(archives, indent=2) + "\n")
with tarfile.open(OUT / "sources.tar.gz", "w:gz") as archive:
    for relative in sorted(f["sources"]):
        archive.add(ROOT / relative, arcname=relative, recursive=False)
for p in BASE.iterdir():
    if (
        p.is_file()
        and p.suffix in (".json", ".log", ".txt", ".py", ".png")
        and p.name not in excluded
    ):
        shutil.copyfile(p, OUT / p.name)
# Preserve native construction/export records and provenance without duplicating weights.
for p in (BASE / "upstream").iterdir():
    if p.is_file() and (p.suffix == ".json" or p.name.endswith(".export.json")):
        dest = OUT / "intake" / p.name
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(p, dest)
print("members", len(entries), "source files", len(f["sources"]), flush=True)
