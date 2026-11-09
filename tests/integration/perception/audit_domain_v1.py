"""Replay retained domain base+extension captures, masks and lossless training export."""

from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.domain_data_v1 import export, DomainDataset
from prepare_domain_v1 import prepare, preflight_gate
from prepare_domain_extension_v1 import prepare as prepare_extra
from domain_coverage_v1 import assess
from domain_plan_v1 import build, EXCLUSION
from domain_extension_v1 import build_extension


def audit(root):
    root = Path(root)
    freeze = root / "collection-freeze.json"
    extra_freeze = root / "extension-freeze.json"
    f = read_json(freeze)
    ef = read_json(extra_freeze)
    has_support = (root / "support-runs.json").exists()
    identities = [f, ef] + (
        [read_json(root / "support-freeze.json")] if has_support else []
    )
    for identity in identities:
        for name, digest in identity["sources"].items():
            current = (
                root / Path(name).relative_to("build/m10-domain-data-v1")
                if name.startswith("build/m10-domain-data-v1/")
                else Path(__file__).resolve().parents[3] / name
            )
            if sha256_file(current) != digest:
                raise ValueError("current capture source drift: " + name)
    plan = root / "collection-source/profiles/perception-domain-collection-v1.json"
    extra_plan = root / "extension-source/profiles/perception-domain-extension-v1.json"
    exclusion = root / "collection-source/profiles/perception-domain-exclusion-v1.json"
    if read_json(plan) != build() or read_json(extra_plan) != build_extension():
        raise ValueError("deterministic plan replay")
    previous = set(read_json(EXCLUSION)["rgb_sha256"])
    consumed = set(read_json(exclusion)["rgb_sha256"])
    if len(previous) != 2717 or not previous <= consumed or len(consumed) != 2893:
        raise ValueError("all prior and preflight excluded")
    runs = read_json(root / "collection-runs.json")
    extra_runs = read_json(root / "extension-runs.json")
    summaries = {}
    bundle = read_json(root / "data-bundle.json")
    if bundle["captures"] != {
        name: sha256_file(root / name)
        for name in (
            ("collection-freeze.json", "extension-freeze.json", "support-freeze.json")
            if has_support
            else ("collection-freeze.json", "extension-freeze.json")
        )
    }:
        raise ValueError("bundle capture freezes")
    expected_plans = {sha256_file(plan), sha256_file(extra_plan)}
    if has_support:
        expected_plans.add(
            sha256_file(
                root / "support-source/profiles/perception-domain-support-v1.json"
            )
        )
    if (
        bundle["plans"] != read_json(root / "plans.json")
        or set(bundle["plans"].values()) != expected_plans
    ):
        raise ValueError("bundle plan identities")
    expected_inputs = {
        f"{prefix}{p}-data"
        for prefix in ("", "extension-")
        for p in ("train-14", "train-31", "train-74", "validation-104")
    }
    if has_support:
        expected_inputs.add("support-train-31-data")
    if set(bundle["inputs"]) != expected_inputs:
        raise ValueError("bundle input set")
    for name, digest in bundle["inputs"].items():
        if sha256_file(root / name / "data.json") != digest:
            raise ValueError("bundle prepared identity")
    with tempfile.TemporaryDirectory(prefix="domain-rebuild-", dir="build") as temp:
        temporary = Path(temp)
        pp = root / "preflight-source/profiles/perception-domain-preflight-v1.json"
        p = prepare(
            root / "preflight-01/dataset/capture.json",
            pp,
            root / "preflight-freeze.json",
            EXCLUSION,
            temporary / "preflight",
        )
        for name in ("data.json", "support.json", "reconstruction.json"):
            if sha256_file(temporary / "preflight" / name) != sha256_file(
                root / "preflight-data" / name
            ):
                raise ValueError("preflight raw reconstruction")
        if preflight_gate(temporary / "preflight") != read_json(
            root / "preflight-acceptance.json"
        ):
            raise ValueError("preflight support replay")
        if consumed != previous | set(p["rgb_sha256"]):
            raise ValueError("exact exclusion union")
        seen = set(consumed)
        groups = {"train": [], "validation": []}
        for part in ("validation-104", "train-14", "train-31", "train-74"):
            rebuilt = []
            for is_extra in (False, True):
                prefix = "extension-" if is_extra else ""
                name = f"{prefix}{part}"
                run = root / (extra_runs if is_extra else runs)[part]
                dest = temporary / name
                r = (prepare_extra if is_extra else prepare)(
                    run / "dataset/capture.json",
                    extra_plan if is_extra else plan,
                    extra_freeze if is_extra else freeze,
                    exclusion,
                    dest,
                )
                for file in ("data.json", "support.json", "reconstruction.json"):
                    if sha256_file(dest / file) != sha256_file(
                        root / f"{name}-data" / file
                    ):
                        raise ValueError("raw-to-label replay")
                hashes = set(r["rgb_sha256"])
                if seen & hashes or len(hashes) != (12 if is_extra else 255):
                    raise ValueError("cross-run RGB overlap")
                seen.update(hashes)
                rebuilt.append(dest)
                groups[part.split("-")[0]].append(dest)
                summaries[name] = {
                    k: r[k]
                    for k in (
                        "frames",
                        "quality_supported_objects",
                        "small_fragments",
                        "minimum_luma_std",
                    )
                }
            original = assess([rebuilt[0]])
            if original != read_json(root / f"{part}-coverage.json"):
                raise ValueError("original support preserved")
            c = assess(rebuilt)
            if c != read_json(root / f"{part}-combined-coverage.json"):
                raise ValueError("combined support matrices")
        if has_support:
            support_run = root / read_json(root / "support-runs.json")["train-31"]
            support_plan = (
                root / "support-source/profiles/perception-domain-support-v1.json"
            )
            support_dest = temporary / "support-train-31"
            r = prepare_extra(
                support_run / "dataset/capture.json",
                support_plan,
                root / "support-freeze.json",
                exclusion,
                support_dest,
            )
            for file in ("data.json", "support.json", "reconstruction.json"):
                if sha256_file(support_dest / file) != sha256_file(
                    root / "support-train-31-data" / file
                ):
                    raise ValueError("support sweep raw replay")
            hashes = set(r["rgb_sha256"])
            if len(hashes) != 12 or hashes & seen:
                raise ValueError("support sweep RGB separation")
            for split, roots in groups.items():
                original = assess(roots)
                if (
                    root / f"{split}-split-coverage.json"
                ).exists() and original != read_json(
                    root / f"{split}-split-coverage.json"
                ):
                    raise ValueError("original split coverage preserved")
            groups["train"].append(support_dest)
            summaries["support-train-31"] = {
                k: r[k]
                for k in (
                    "frames",
                    "quality_supported_objects",
                    "small_fragments",
                    "minimum_luma_std",
                )
            }
            for split, roots in groups.items():
                coverage = assess(roots)
                if (
                    coverage != read_json(root / "final-split-coverage.json")[split]
                    or coverage["status"] != "PASS"
                ):
                    raise ValueError(
                        "final split coverage after appended support sweep"
                    )
        else:
            for split, roots in groups.items():
                coverage = assess(roots)
                if (
                    coverage != read_json(root / f"{split}-split-coverage.json")
                    or coverage["status"] != "PASS"
                ):
                    raise ValueError("predeclared aggregate split coverage")
        report = export(
            groups,
            temporary / "export",
            sha256_file(root / "data-bundle.json"),
            sha256_file(root / "plans.json"),
        )
        if report != read_json(root / "export/dataset.json") or report != read_json(
            root / "export-summary.json"
        ):
            raise ValueError("export summary replay")
        for spec in report["splits"].values():
            if sha256_file(
                temporary / "export" / spec["annotation_path"]
            ) != sha256_file(root / "export" / spec["annotation_path"]):
                raise ValueError("COCO replay")
        a, b = (
            DomainDataset(root / "export", "train"),
            DomainDataset(root / "export", "validation"),
        )
        a.validate_split(b)
        for dataset in (a, b):
            for im in dataset.images.values():
                if (
                    sha256_file(temporary / "export/images" / im["file_name"])
                    != im["png_sha256"]
                ):
                    raise ValueError("PNG replay")
        rejected = read_json(root / "validation-104-01/server.json")
        if (
            rejected["status"] != "FAIL"
            or rejected["server_exit"] != -9
            or not rejected["forced_stop"]
            or (root / "validation-104-01/dataset/capture.json").exists()
        ):
            raise ValueError("startup failure history")
        original = read_json(root / "validation-104-coverage.json")
        if (
            original["status"] != "FAIL"
            or original["gates"]["every_class_weather_occlusion"]
        ):
            raise ValueError("original coverage failure history")
        return dict(
            schema="m10-domain-data-audit-v1",
            status="PASS",
            preflight_frames=176,
            base_frames=1020,
            extension_frames=48,
            collection_frames=1080 if has_support else 1068,
            train_frames=813 if has_support else 801,
            validation_frames=267,
            prior_rgb_excluded=2717,
            collection_rgb_excluded=2893,
            cross_run_rgb_overlap=0,
            training_validation_leakage=0,
            reserved_holdout_site=127,
            quality_holdout_collected=False,
            startup_failure_preserved=True,
            original_coverage_failure_preserved=True,
            capture_sources=len(f["sources"]),
            extension_sources=len(ef["sources"]),
            summary=summaries,
            split_summary=report["splits"],
            model_training=False,
            model_inference=False,
            runtime_promotion=False,
            scope="Model-free development data only; no model accuracy/live20Hz/vehicle or bus/truck asset independence claim",
        )


if __name__ == "__main__":
    import argparse
    from physical_ai.perception.domain_data_v1 import write_json_new

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    r = audit(a.root)
    write_json_new(a.output, r)
    print(r)
