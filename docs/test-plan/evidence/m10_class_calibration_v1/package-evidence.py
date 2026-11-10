"""Archive both diagnostics and calibration with their exact frozen dependencies."""

from pathlib import Path
import hashlib
import json
import tarfile
import shutil

ROOT = Path.cwd()
BASE = ROOT / "build/m10-class-calibration-v1"
DIAG = ROOT / "build/m10-model-diagnostics-v1"
OUT = ROOT / "docs/test-plan/evidence/m10_class_calibration_v1"
DOUT = ROOT / "docs/test-plan/evidence/m10_model_diagnostics_v1"


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


f = json.loads((BASE / "audit-annex-freeze.json").read_text())
assert json.loads((BASE / "audit-annex.json").read_text())["status"] == "PASS"
assert json.loads((DIAG / "audit.json").read_text())["status"] == "PASS"
entries = {}


def add(p):
    if not p.is_file() or p.is_symlink():
        raise ValueError(p)
    entries[str(p.relative_to(ROOT))] = p


for name, h in {**f["sources"], **f["inputs"]}.items():
    p = ROOT / name
    assert digest(p) == h
    add(p)
for p in [
    BASE / "audit-annex-freeze.json",
    DIAG / "mask-annex/freeze.json",
    OUT / "check-archive.py",
    OUT / "README.md",
    DOUT / "README.md",
    ROOT / "profiles/perception-class-calibration-candidates-v1.json",
]:
    add(p)
mask = json.loads((DIAG / "mask-annex/freeze.json").read_text())
for name, h in mask["inputs"].items():
    p = ROOT / name
    assert digest(p) == h
    add(p)
for spec in json.loads((ROOT / "build/m10-model-screen-v2/freeze.json").read_text())[
    "datasets"
].values():
    for data in spec.values():
        for p in (ROOT / data["path"]).rglob("*"):
            if p.is_file():
                add(p)
# Include the whole small preparation RGB manifest to keep optional numeric replay usable.
probes = ROOT / "build/m10-quality-v7/preparation-development-data/rgb.json"
add(probes)
for row in json.loads(probes.read_text())["frames"]:
    add(probes.parent / row["rgb_path"])
models = json.loads((ROOT / "build/m10-model-screen-v2/models.json").read_text())
for key in ["dfine-m", "rtv4-s"]:
    add(ROOT / models[key])
excluded = {
    "archive-files.json",
    "archive-recheck.json",
    "archive-recheck.log",
    "docs-check.json",
    "package.log",
    "staged-integrity.json",
    "commit.log",
    "push.log",
}
for base in [BASE, DIAG]:
    for p in base.rglob("*"):
        if (
            p.is_file()
            and "__pycache__" not in p.parts
            and p.name not in excluded
            and p.suffix in [".py", ".json", ".log", ".png", ".h"]
        ):
            add(p)
manifest = {name: digest(p) for name, p in sorted(entries.items())}
mp = BASE / "archive-files.json"
mp.write_text(json.dumps(manifest, indent=2) + "\n")
archive = OUT / "experiment.tar.gz"
assert not archive.exists()
with tarfile.open(archive, "w:gz", compresslevel=1) as tar:
    tar.add(mp, arcname="project/archive-files.json", recursive=False)
    for name, p in sorted(entries.items()):
        tar.add(p, arcname="project/" + name, recursive=False)
with tarfile.open(OUT / "sources.tar.gz", "w:gz") as tar:
    for name in sorted(f["sources"]):
        tar.add(ROOT / name, arcname=name, recursive=False)
for p in BASE.iterdir():
    if p.is_file() and p.name not in excluded and p.suffix in [".py", ".json", ".log"]:
        shutil.copyfile(p, OUT / p.name)
for p in DIAG.iterdir():
    if (
        p.is_file()
        and p.name not in excluded
        and p.suffix in [".py", ".json", ".log", ".png"]
    ):
        shutil.copyfile(p, DOUT / p.name)
for name, target in [
    ("freeze.json", "mask-freeze.json"),
    ("review.json", "mask-review.json"),
    ("review.log", "mask-review.log"),
    ("check-masks.py", "check-masks.py"),
    ("ObjectLabel.h", "ObjectLabel.h"),
]:
    shutil.copyfile(DIAG / "mask-annex" / name, DOUT / target)
summary = dict(
    status="PASS",
    archive_bytes=archive.stat().st_size,
    archive_sha256=digest(archive),
    members=len(entries),
    frozen_sources=len(f["sources"]),
    diagnostic_raw=810,
    class_scorecards=31250,
    mask_cases=3,
    unique_quality_rgb=405,
    holdout_access=False,
    runtime_promotion=False,
)
(OUT / "package-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
