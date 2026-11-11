from pathlib import Path
import json


def compare(base):
    a = json.loads((base / "comparison-6-score.json").read_text())
    b = json.loads((base / "comparison-4-score.json").read_text())
    assert a["frames"] == b["frames"] == 81
    assert [r["scene"] for r in a["records"]] == [r["scene"] for r in b["records"]]
    changes = []
    for left, right in zip(a["records"], b["records"]):
        if left["counts"] != right["counts"]:
            changes.append(
                dict(scene=left["scene"], four_k=left["counts"], two_k=right["counts"])
            )
    metrics = {}

    def add(label, left, right):
        metrics[label] = dict(
            four_k=left, two_k=right, delta=right - left, regressed=right < left
        )

    for k in ["precision", "recall"]:
        add("micro_" + k, a["micro"][k], b["micro"][k])
    for k in a["per_class"]:
        add(
            "class_" + k + "_recall",
            a["per_class"][k]["recall"],
            b["per_class"][k]["recall"],
        )
    for k in a["strata"]:
        if a["strata"][k]["target_recall"] is not None:
            add(
                "stratum_" + k + "_target_recall",
                a["strata"][k]["target_recall"],
                b["strata"][k]["target_recall"],
            )
    for k in a["sizes"]:
        add(
            "size_or_person_" + k + "_recall",
            a["sizes"][k]["recall"],
            b["sizes"][k]["recall"],
        )
    add("near_person_recall", a["near_person"]["recall"], b["near_person"]["recall"])
    add(
        "rider_recall",
        a["riders"]["detected"] / a["riders"]["visible"],
        b["riders"]["detected"] / b["riders"]["visible"],
    )
    out = dict(
        schema="m10-source-development-comparison-v1",
        frames_per_arm=81,
        scope="Previously consumed development site38; not independent qualification; no threshold change",
        live_timing_included=False,
        runtime_promotion=False,
        absolute_quality={"4k": a["absolute_quality"], "2k": b["absolute_quality"]},
        metrics=metrics,
        regressions=[k for k, v in metrics.items() if v["regressed"]],
        changed_scenes=changes,
    )
    return out


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    out = compare(base)
    (base / "quality-comparison.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
