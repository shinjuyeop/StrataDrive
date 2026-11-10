"""New pre-quality freeze for the validated640/960 subset; V1 remains immutable."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path
from physical_ai.perception.resolution_v2 import (
    SIZES,
    VECTOR,
    ORIGINAL_ONNX_SHA,
    CHECKPOINT_SHA,
)
from resolution_v1_common import (
    ROOT,
    PROBES,
    GROUPS,
    development,
    safe_input,
    require,
    write_new,
)
from resolution_v1_common import check_freeze as check_v1
from investigate_resolution_numeric_v1 import check_annex

PARENT = ROOT / "build/m10-resolution-v1"


def freeze(base):
    old = check_v1(PARENT / "freeze.json")
    annex = check_annex(PARENT)
    numeric = read_json(PARENT / "numeric-second-profile.json")
    require(
        numeric["profile"] == "ORT_ENABLE_BASIC"
        and numeric["status"] == "FAIL"
        and len(numeric["rows"]) == 9,
        "original failed investigation retained",
    )
    require(
        all(r["passed"] for r in numeric["rows"] if r["size"] in SIZES)
        and {(r["size"], r["probe"]) for r in numeric["rows"] if r["size"] in SIZES}
        == {(s, n) for s in SIZES for n in range(3)}
        and any(not r["passed"] for r in numeric["rows"] if r["size"] == 1280),
        "numerically selected subset only",
    )
    f = dict(old)
    f.update(
        schema="m10-resolution-freeze-v2",
        created_utc=datetime.now(timezone.utc).isoformat(),
        sizes=list(SIZES),
        graph_optimization="ORT_ENABLE_BASIC",
        sources=dict(old["sources"]),
        inputs=dict(old["inputs"]),
        parent_freeze_sha256=sha256_file(PARENT / "freeze.json"),
    )
    files = [
        ROOT / "profiles/perception-resolution-study-v2.json",
        ROOT / "docs/test-plan/perception-resolution-v2-protocol.md",
    ]
    files += list((ROOT / "physical_ai/perception").glob("*resolution_v2.py"))
    files += list((ROOT / "tests/integration/perception").glob("*resolution_v2*.py"))
    f["sources"].update(annex["sources"])
    f["sources"].update({str(p.relative_to(ROOT)): sha256_file(p) for p in files})
    extra = [
        PARENT / n
        for n in [
            "freeze.json",
            "models.json",
            "numeric.json",
            "numeric-diagnostic.json",
            "numeric-annex-freeze.json",
            "cached640-reference.json",
            "numeric-second-profile.json",
            "numeric-continuation-before-run.json",
            "continue-numeric.py",
        ]
    ]
    for spec in read_json(PARENT / "models.json")["models"].values():
        extra.append(local_path(PARENT, spec["path"]))
    extra += list((PARENT / "reference").glob("*.npz")) + list(
        (PARENT / "cached640-reference").glob("*.npz")
    )
    extra += [ROOT / n for n in annex["inputs"]]
    f["inputs"].update({str(p.relative_to(ROOT)): sha256_file(p) for p in extra})
    write_new(base / "freeze.json", f)
    shutil.copy2(PARENT / "baseline-index.json", base / "baseline-index.json")
    return f


def check_freeze(path):
    f = read_json(path)
    require(
        f["schema"] == "m10-resolution-freeze-v2"
        and f["groups"] == GROUPS
        and f["sizes"] == list(SIZES)
        and f["vector"] == list(VECTOR)
        and f["graph_optimization"] == "ORT_ENABLE_BASIC"
        and all(
            f[k] is False
            for k in (
                "holdout_access",
                "fresh_acceptance",
                "runtime_promotion",
                "training",
                "new_rgb",
            )
        ),
        "validated subset freeze/scope",
    )
    for n, h in f["sources"].items():
        require(sha256_file(ROOT / n) == h, "V2 frozen source drift: " + n)
    for n, h in f["inputs"].items():
        require(
            sha256_file(safe_input(ROOT / n)) == h,
            "V2 frozen development input drift: " + n,
        )
    require(
        sha256_file(path.parent / "baseline-index.json")
        == f["inputs"]["build/m10-resolution-v1/baseline-index.json"],
        "baseline copy identity",
    )
    return f


def intake(base):
    check_freeze(base / "freeze.json")
    old = read_json(PARENT / "models.json")
    control = read_json(PARENT / "cached640-reference.json")
    (base / "models").mkdir(exist_ok=False)
    (base / "reference").mkdir(exist_ok=False)
    m = dict(old)
    m.update(
        schema="m10-resolution-models-v2",
        freeze_sha256=sha256_file(base / "freeze.json"),
        started_utc=datetime.now(timezone.utc).isoformat(),
        models={},
        references=[],
        graph_optimization="ORT_ENABLE_BASIC",
    )
    for size in SIZES:
        spec = dict(old["models"][str(size)])
        shutil.copy2(PARENT / spec["path"], base / spec["path"])
        if size == 640:
            spec["geometry"] = dict(
                size=640,
                reference_mode="native checkpoint cache",
                nongeometric_state_sha256=control["nongeometric_state_sha256"],
                cached_anchor_sha256=control["cached_anchor_sha256"],
                cached_anchor_shape=control["cached_anchor_shape"],
            )
        m["models"][str(size)] = spec
        for n in range(3):
            row = dict(
                next(
                    r for r in old["references"] if (r["size"], r["probe"]) == (size, n)
                )
            )
            source = (
                PARENT
                / ("cached640-reference" if size == 640 else "reference")
                / f"{size}-{n}.npz"
            )
            shutil.copy2(source, base / "reference" / f"{size}-{n}.npz")
            row.update(file=f"reference/{size}-{n}.npz", sha256=sha256_file(source))
            if size == 640:
                row.pop("static_dynamic")
                row["cached640_old_v9_delta"] = control["rows"][n]["old_v9_delta"]
            m["references"].append(row)
    m["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(base / "models.json", m)
    return m


def models(base):
    f = check_freeze(base / "freeze.json")
    m = read_json(base / "models.json")
    require(
        m["schema"] == "m10-resolution-models-v2"
        and m["freeze_sha256"] == sha256_file(base / "freeze.json")
        and m["strict_state_load"] is True
        and m["checkpoint_sha256"] == CHECKPOINT_SHA
        and set(m["models"]) == set(map(str, SIZES))
        and m["graph_optimization"] == "ORT_ENABLE_BASIC",
        "V2 model manifest",
    )
    require(m["models"]["640"]["sha256"] == ORIGINAL_ONNX_SHA, "original640 retained")
    require(
        len(m["references"]) == 6
        and {(r["size"], r["probe"]) for r in m["references"]}
        == {(s, n) for s in SIZES for n in range(3)},
        "six native references",
    )
    for size, spec in m["models"].items():
        p = local_path(base, spec["path"])
        require(
            sha256_file(p) == spec["sha256"]
            and p.stat().st_size == spec["bytes"]
            and spec["size"] == int(size)
            and spec["geometry"]["nongeometric_state_sha256"]
            == m["nongeometric_state_sha256"],
            "V2 model identity/state",
        )
    for r in m["references"]:
        require(
            sha256_file(local_path(base, r["file"])) == r["sha256"], "V2 reference SHA"
        )
    return f, m


def check_numeric(base):
    _, m = models(base)
    report = read_json(base / "numeric.json")
    require(
        report["schema"] == "m10-resolution-numeric-v2"
        and report["status"] == "PASS"
        and not report["failures"]
        and report["model_manifest_sha256"] == sha256_file(base / "models.json")
        and report["box_atol"] == 0.1
        and report["score_atol"] == 0.0001
        and report["cold_calls_excluded"] == 0
        and len(report["rows"]) == 6
        and {(r["size"], r["probe"]) for r in report["rows"]}
        == {(s, n) for s in SIZES for n in range(3)},
        "six native numeric pairs",
    )
    for row in report["rows"]:
        ref = next(
            r
            for r in m["references"]
            if (r["size"], r["probe"]) == (row["size"], row["probe"])
        )
        require(
            row["passed"]
            and row["rgb_sha256"] == ref["rgb_sha256"]
            and row["providers"][0] == "CUDAExecutionProvider",
            "numeric RGB/CUDA identity",
        )
    return report
