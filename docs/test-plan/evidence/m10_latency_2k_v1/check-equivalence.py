"""Replay all81 prior development inputs; no inference or new quality selection."""

from pathlib import Path
import hashlib
import json
import subprocess
import tarfile
import zlib
import cv2
import numpy as np
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.async_native_2k_v1 import BgraPacket
from physical_ai.perception.native_kernel_2k_v1 import NativeResize
from physical_ai.perception.staged_kernel_2k_v1 import prepare_staged
from physical_ai.perception.tensor_2k_v1 import TensorWorkspace
from physical_ai.perception.run import distribution
from evidence_payload_v1 import payload
from source_compare_v1_common import verify_sources


def check(workspace, base):
    verify_sources(base / "freeze.json")
    prior = Path("docs/test-plan/evidence/m10_source_compare_v2")
    pv = json.loads((prior / "quality-2k-01/packet-validation.json").read_text())
    expected = {x["frame"]: x for x in pv["exact_inputs"]}
    manifest = json.loads((prior / "raw-archives.json").read_text())
    media = Path(
        next(
            x.split("=", 1)[1]
            for x in subprocess.check_output(
                ["git", "lfs", "env"], text=True
            ).splitlines()
            if x.startswith("LocalMediaDir=")
        )
    )
    profile = json.loads(Path("profiles/perception-latency-2k-v1.json").read_text())
    binding = profile["native_libraries"]["4"]
    resize = NativeResize(Path(binding["path"]).resolve(), binding["sha256"])
    new = TensorWorkspace()
    cv2.setNumThreads(4)
    rows = []
    before = []
    after = []
    for item in manifest:
        if not item["file"].startswith("raw-quality-2k-01-"):
            continue
        archive = payload(
            workspace / prior / item["file"], item["sha256"], item["bytes"], media
        )
        with tarfile.open(archive, "r|") as a:
            for member in a:
                if "/rgb/" not in member.name:
                    continue
                data = a.extractfile(member).read()
                raw = zlib.decompress(data)
                frame = int(Path(member.name).name.split(".")[0])
                assert frame in expected and len(raw) == 2560 * 1536 * 4
                packet = BgraPacket(
                    FrameIdentity(1, 1, frame, frame * 10_000_000), raw, 1
                )
                old_clock = {}
                new_clock = {}
                if len(rows) % 2:
                    got = new.prepare(resize, packet, new_clock)[0]
                    want = prepare_staged(resize, packet, old_clock)[0]
                else:
                    want = prepare_staged(resize, packet, old_clock)[0]
                    got = new.prepare(resize, packet, new_clock)[0]
                for k in want:
                    np.testing.assert_array_equal(want[k], got[k])
                h = hashlib.sha256(got["images"].tobytes()).hexdigest()
                assert h == expected[frame]["tensor_sha256"]
                rows.append(dict(frame=frame, tensor_sha256=h))
                before.append(old_clock["tensor"] - old_clock["begin"])
                after.append(new_clock["tensor"] - new_clock["begin"])
    assert len(rows) == len(expected) == 81 and {r["frame"] for r in rows} == set(
        expected
    )
    return dict(
        status="PASS",
        frames=81,
        rows=rows,
        model_unchanged=True,
        quality_scope="Exact prior development model inputs; no new inference or independent quality qualification",
        offline_preprocess=dict(
            baseline=distribution(before), tensor=distribution(after)
        ),
    )


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    result = check(Path.cwd(), base)
    (base / "prior-input-equivalence.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))
