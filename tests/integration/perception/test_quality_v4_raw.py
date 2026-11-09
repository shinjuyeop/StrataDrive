"""Independent raw-pair -> metadata -> strict-score regression, without a model."""

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from physical_ai.perception.contract import MODEL_SHA256, sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.quality_candidates_v3 import INPUT_PROFILE
from quality_annotation import SEMANTICS_BY_CLASS
from quality_benchmark import write_new
from quality_benchmark_v4 import score
from quality_v4_common import PLAN, PROTOCOL, freeze
from prepare_quality_v4 import prepare


class QualityV4RawTests(unittest.TestCase):
    def test_raw_capture_identity_survives_preparation_and_scoring(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("quality_v4_common.check_numeric"),
        ):
            root = Path(tmp)
            write_new(root / "model-check.json", {})
            frozen = root / "freeze.json"
            freeze(frozen)
            run_root = root / "capture"
            raw = run_root / "dataset"
            raw.mkdir(parents=True)
            plan = read_json(PLAN)
            cases = plan["partitions"]["development"]["cases"]
            rgb = raw / "source.bgra"
            rgb.write_bytes(bytes([31, 97, 181, 255]) * 640 * 384)
            cap = dict(
                schema="m10-road-evaluation-capture-v4",
                phase="evaluation",
                partition="development",
                status="PASS",
                cleanup_errors=[],
                overflow=[],
                plan_sha256=sha256_file(PLAN),
                survey_sha256=plan["survey_sha256"],
                xodr_sha256=plan["xodr_sha256"],
                epoch=1,
                clock_instance=7,
                camera_pose=plan["partitions"]["development"]["camera_pose"],
                frames=[],
                scenes=[],
            )
            for n, case in enumerate(cases, 1):
                actors = []
                pixels = np.zeros((384, 640, 4), np.uint8)
                slot = 0
                for index, wanted in enumerate(case["actors"], 1):
                    loc = wanted["pose"]["location"]
                    lane = dict(
                        x=loc["x"], y=loc["y"], z=loc["z"] - wanted["clearance_m"]
                    )
                    actors.append(
                        dict(
                            class_id=wanted["class_id"],
                            blueprint=wanted["blueprint"],
                            role=wanted["role"],
                            actor_id=index,
                            pose=wanted["pose"],
                            road_readback=dict(
                                nearest_lane_pose=dict(location=lane),
                                projection_m=0,
                                clearance_error_m=0,
                                road_id=wanted["road_node"]["road_id"],
                                lane_id=wanted["road_node"]["lane_id"],
                            ),
                        )
                    )
                    tags = [SEMANTICS_BY_CLASS[wanted["class_id"]][0]]
                    if wanted["class_id"] in (1, 3):
                        tags.append(13)
                    for tag in tags:
                        x = 10 + slot * 45
                        pixels[10:30, x : x + 20] = [0, index, tag, 255]
                        slot += 1
                instance = raw / f"{n}.instance"
                instance.write_bytes(pixels.tobytes())
                image = raw / f"{n}.bgra"
                os.link(rgb, image)
                cap["frames"].append(
                    dict(
                        scene=case["id"],
                        frame=n,
                        source_ns=n * 50_000_000,
                        rgb=dict(path=image.name, sha256=sha256_file(image)),
                        instance=dict(path=instance.name, sha256=sha256_file(instance)),
                    )
                )
                cap["scenes"].append(
                    dict(
                        id=case["id"],
                        frame=n,
                        weather=case["weather"],
                        stratum=case["stratum"],
                        target_class=case["target_class"],
                        actors=actors,
                    )
                )
            write_new(raw / "capture.json", cap)
            write_new(
                run_root / "server.json",
                dict(
                    schema="m10-quality-server-v4",
                    stage="evaluation",
                    status="PASS",
                    server_exit=130,
                    capture_exit=0,
                    plan_sha256=sha256_file(PLAN),
                    freeze_sha256=sha256_file(frozen),
                    protocol_sha256=sha256_file(PROTOCOL),
                    selection_sha256=None,
                ),
            )
            data = root / "data"
            self.assertEqual(
                prepare(raw / "capture.json", data, frozen)["status"], "PASS"
            )
            truth = read_json(data / "evaluation-only-gt.json")
            self.assertEqual(truth["capture_sha256"], sha256_file(raw / "capture.json"))
            run = dict(
                schema="m10-quality-run-v4",
                status="PASS",
                phase="development",
                candidate="baseline",
                model_sha256=MODEL_SHA256,
                input_profile=INPUT_PROFILE,
                providers=["CUDAExecutionProvider"],
                cpu_node_fallback_disabled=True,
                freeze_sha256=sha256_file(frozen),
                protocol_sha256=sha256_file(PROTOCOL),
                dataset_sha256=sha256_file(data / "rgb.json"),
                dataset_seal_sha256=sha256_file(data / "benchmark-seal.json"),
                selection_sha256=None,
                expected=81,
                attempted=81,
                model_valid=81,
                admitted=81,
                errors=0,
                rows=[],
            )
            for source, gt in zip(
                read_json(data / "rgb.json")["frames"], truth["frames"]
            ):
                run["rows"].append(
                    dict(
                        **{
                            k: source[k]
                            for k in ("scene", "frame", "source_ns", "rgb_sha256")
                        },
                        model_valid=True,
                        admitted=True,
                        expires_ns=source["source_ns"] + 100_000_000,
                        elapsed_wall_ns=10_000_000,
                        preprocess_ns=1_000_000,
                        inference_ns=1_000_000,
                        postprocess_ns=1_000_000,
                        detections=[
                            dict(class_id=o["class_id"], score=0.9, box=o["box"])
                            for o in gt["objects"]
                        ],
                    )
                )
            write_new(root / "run.json", run)
            self.assertEqual(
                score(data, root / "run.json", frozen)["absolute_quality"], "PASS"
            )
