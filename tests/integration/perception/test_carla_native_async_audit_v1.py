"""Live trace audit rejects missing acquisitions and renewed/expired snapshots."""

from copy import deepcopy
from dataclasses import asdict
import unittest

from audit_carla_native_async_v1 import audit
from physical_ai.perception.async_native_v1 import NativeResult
from physical_ai.perception.contract import FrameIdentity


def fixture():
    start = 1_000_000_000
    ticks = [
        dict(
            frame=f,
            source_ns=f * 10_000_000,
            begin_wall_ns=start + (f - 5) * 30_000_000,
            end_wall_ns=start + (f - 5) * 30_000_000 + 1_000_000,
        )
        for f in range(5, 305)
    ]
    camera, calls = [], []
    for tick in ticks:
        f, wall = tick["frame"], tick["begin_wall_ns"]
        if f % 5:
            continue
        camera.append(
            dict(
                frame=f,
                source_ns=f * 10_000_000,
                width=3840,
                height=2304,
                begin_wall_ns=wall + 1_000_000,
                offer_entry_wall_ns=wall + 2_000_000,
                end_wall_ns=wall + 3_000_000,
                accepted=True,
            )
        )
        result = asdict(NativeResult(FrameIdentity(1, 77, f, f * 10_000_000)))
        calls.append(
            dict(
                identity=deepcopy(result["identity"]),
                result=result,
                received_wall_ns=wall + 2_500_000,
                begin_wall_ns=wall + 4_000_000,
                end_wall_ns=wall + 34_000_000,
            )
        )
    stopped = ticks[-1]["end_wall_ns"] + 20_000_000
    consumers = [
        dict(
            begin_wall_ns=start + 15_000_000,
            end_wall_ns=start + 16_000_000,
            snapshot_read_wall_ns=start + 15_000_000,
            snapshot_read_source_ns=50_000_000,
            perception=None,
        ),
        dict(
            begin_wall_ns=start + 35_000_000,
            end_wall_ns=start + 36_000_000,
            snapshot_read_wall_ns=start + 35_000_000,
            snapshot_read_source_ns=60_000_000,
            perception=deepcopy(calls[0]["result"]),
        ),
    ]
    for i in range(6):
        w = stopped + 110_000_000 + i * 20_000_000
        consumers.append(
            dict(
                begin_wall_ns=w,
                end_wall_ns=w + 1,
                snapshot_read_wall_ns=w,
                snapshot_read_source_ns=3_040_000_000,
                perception=None,
            )
        )
    return dict(
        status="PASS",
        closed=True,
        live_camera=True,
        actual_vehicle_control=False,
        runtime_promotion=False,
        quality_acceptance=False,
        live20Hz_acceptance=False,
        cold_calls_excluded=0,
        errors=[],
        cleanup_errors=[],
        recorder_overflow=[],
        recorder_capacity=64,
        clock_instance=77,
        initial_frame=4,
        initial_source_ns=40_000_000,
        last_planned_frame=304,
        traces=dict(state=ticks, camera=camera, consumer=consumers),
        model_calls=calls,
        raw=[dict(frame=x["frame"]) for x in camera],
        worker=dict(
            clock_fault=False,
            busy=False,
            pending=False,
            counters=dict(
                offered=60,
                accepted=60,
                rejected=0,
                started=60,
                completed=60,
                published=60,
                overwritten=0,
                cancelled=0,
                expired_pending=0,
                late=0,
                errors=0,
                obsolete=0,
            ),
        ),
        fresh_output_observed=True,
        unique_consumed_frames=1,
        sensor_stopped_wall_ns=stopped,
    )


class CarlaNativeAuditTests(unittest.TestCase):
    def test_complete_actual_clock_fixture_and_stopped_clock_expiry(self):
        self.assertEqual(audit(fixture())["status"], "PASS")

    def test_missing_raw_changed_source_deadline_or_scope_is_rejected(self):
        mutations = (
            lambda r: r["raw"].pop(),
            lambda r: r["traces"]["camera"].pop(0),
            lambda r: r["traces"]["state"][10].update(source_ns=0),
            lambda r: r["worker"]["counters"].update(overwritten=1),
            lambda r: r["traces"]["consumer"][1].update(
                snapshot_read_source_ns=150_000_000
            ),
            lambda r: r["traces"]["consumer"][1].update(
                snapshot_read_wall_ns=1_102_500_000
            ),
            lambda r: r["traces"]["consumer"][-1].update(
                snapshot_read_source_ns=3_050_000_000
            ),
            lambda r: r["model_calls"][0]["result"].update(model_sha256="0" * 64),
            lambda r: r.update(cold_calls_excluded=1),
            lambda r: r.update(actual_vehicle_control=True),
        )
        for mutate in mutations:
            r = fixture()
            mutate(r)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit(r)


if __name__ == "__main__":
    unittest.main()
