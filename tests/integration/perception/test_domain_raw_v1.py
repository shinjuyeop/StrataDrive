from pathlib import Path
from copy import deepcopy
import json
import shutil
import tempfile
import unittest
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.domain_data_v1 import write_json_new
from domain_plan_v1 import build
from prepare_domain_v1 import prepare
from quality_staging_v5 import staging_pose


class DomainRawTests(unittest.TestCase):
    def test_actual_raw_lineage_rgb_and_pose_rejection(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            run = root / "run"
            raw = run / "dataset"
            raw.mkdir(parents=True)
            plan = build(True)
            plan["partitions"]["preflight"]["cases"] = plan["partitions"]["preflight"][
                "cases"
            ][:4]
            profile = root / "test-plan.json"
            write_json_new(profile, plan)
            files = {}
            for name in (
                "carla_domain_capture_v1.py",
                "quality_geometry_v4.py",
                "quality_staging_v5.py",
            ):
                source = Path("tests/integration/perception") / name
                key = str(source)
                files[key] = sha256_file(source)
                dest = root / "snapshot" / key
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                shutil.copy2(
                    source,
                    run / ("capture-probe.py" if name.startswith("carla_") else name),
                )
            key = "profiles/" + profile.name
            dest = root / "snapshot" / key
            dest.parent.mkdir(parents=True)
            shutil.copy2(profile, dest)
            files[key] = sha256_file(profile)
            freeze = root / "freeze.json"
            write_json_new(
                freeze,
                dict(
                    schema="m10-domain-capture-freeze-v1",
                    created_utc="2026-01-01T00:00:00+00:00",
                    snapshot_directory="snapshot",
                    sources=files,
                ),
            )
            server = dict(
                schema="m10-domain-server-v1",
                status="PASS",
                capture_exit=0,
                server_exit=130,
                started_utc="2026-02-01T00:00:00+00:00",
                plan_sha256=sha256_file(profile),
                startup_budget_seconds=180,
                capture_budget_seconds=900,
                shutdown_budget_seconds=30,
                probe_sha256=files[
                    "tests/integration/perception/carla_domain_capture_v1.py"
                ],
                helper_sha256=files[
                    "tests/integration/perception/quality_geometry_v4.py"
                ],
                staging_sha256=files[
                    "tests/integration/perception/quality_staging_v5.py"
                ],
            )
            write_json_new(run / "server.json", server)
            cap = dict(
                schema="m10-domain-capture-v1",
                status="PASS",
                partition="preflight",
                phase="asset-preflight",
                epoch=1,
                clock_instance=7,
                client_version="294096e-dirty",
                server_version="294096e-dirty",
                plan_sha256=sha256_file(profile),
                survey_sha256=plan["survey_sha256"],
                xodr_sha256=plan["xodr_sha256"],
                cleanup_errors=[],
                overflow=[],
                frames=[],
                scenes=[],
            )
            for n, case in enumerate(plan["partitions"]["preflight"]["cases"], 1):
                pixels = np.zeros((384, 640, 4), np.uint8)
                pixels[:, :, :3] = np.indices((384, 640)).sum(0)[:, :, None] % 255
                pixels[:, :, 3] = 255
                pixels[0, 0, 0] = n
                (raw / f"{n}.rgb").write_bytes(pixels.tobytes())
                instance = np.zeros((384, 640, 4), np.uint8)
                instance[10:15, 10:15] = [0, 9, 12, 255]
                (raw / f"{n}.instance").write_bytes(instance.tobytes())
                cap["frames"].append(
                    dict(
                        scene=case["id"],
                        frame=n,
                        source_ns=n * 50000000,
                        rgb=dict(path=f"{n}.rgb", sha256=sha256_file(raw / f"{n}.rgb")),
                        instance=dict(
                            path=f"{n}.instance",
                            sha256=sha256_file(raw / f"{n}.instance"),
                        ),
                    )
                )
                a = case["actors"][0]
                cap["scenes"].append(
                    dict(
                        id=case["id"],
                        frame=n,
                        camera_pose=case["camera_pose"],
                        actors=[
                            dict(
                                actor_id=9,
                                class_id=a["class_id"],
                                blueprint=a["blueprint"],
                                role=a["role"],
                                pose=deepcopy(a["pose"]),
                                staging_requested_pose=staging_pose(a["pose"], 0),
                                requested_attributes={},
                                actor_attributes={},
                                road_readback=dict(
                                    projection_m=0,
                                    clearance_error_m=0,
                                    road_id=a["road_node"]["road_id"],
                                    lane_id=a["road_node"]["lane_id"],
                                ),
                            )
                        ],
                    )
                )
            path = raw / "capture.json"
            write_json_new(path, cap)
            exclusion = root / "exclusion.json"
            write_json_new(exclusion, dict(rgb_sha256=[]))
            result = prepare(path, profile, freeze, exclusion, root / "prepared")
            self.assertEqual(result["frames"], 4)
            self.assertEqual(
                json.loads((root / "prepared/data.json").read_text())["frames"][0][
                    "objects"
                ][0]["visible_pixels"],
                25,
            )
            cap["scenes"][0]["actors"][0]["pose"]["location"]["x"] += 0.03
            path.write_text(json.dumps(cap))
            with self.assertRaisesRegex(ValueError, "settled pose"):
                prepare(path, profile, freeze, exclusion, root / "bad-pose")
            cap["scenes"][0]["actors"][0]["pose"]["location"]["x"] -= 0.03
            path.write_text(json.dumps(cap))
            old = json.loads((root / "prepared/data.json").read_text())["frames"][0][
                "rgb_sha256"
            ]
            exclusion.write_text(json.dumps(dict(rgb_sha256=[old])))
            with self.assertRaisesRegex(ValueError, "consumed"):
                prepare(path, profile, freeze, exclusion, root / "bad-reuse")
