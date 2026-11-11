"""Adversarial checks for the async trace auditor, independent of GPU/threads."""

from copy import deepcopy
from dataclasses import asdict
import unittest

from audit_async_native_v1 import audit
from physical_ai.perception.async_native_v1 import NativeResult
from physical_ai.perception.contract import FrameIdentity


def fixture():
    start = 1_000_000_000
    results = [
        asdict(NativeResult(FrameIdentity(1, 77, n, n * 10_000_000))) for n in (2, 3)
    ]
    state = [
        dict(
            index=i,
            frame=i + 2,
            source_ns=(i + 2) * 10_000_000,
            begin_wall_ns=start + 10 + 100 * i,
            end_wall_ns=start + 11 + 100 * i,
        )
        for i in range(2)
    ]
    camera = [
        dict(
            index=i,
            frame=i + 2,
            source_ns=(i + 2) * 10_000_000,
            original_bgra_sha256="a" * 64,
            accepted=True,
            begin_wall_ns=start + 12 + 200 * i,
            end_wall_ns=start + 14 + 200 * i,
        )
        for i in range(2)
    ]
    calls = [
        dict(
            identity=r["identity"],
            result=r,
            received_wall_ns=start + receipt,
            begin_wall_ns=start + before,
            end_wall_ns=start + after,
        )
        for r, receipt, before, after in zip(results, (13, 213), (15, 220), (200, 230))
    ]
    control = [
        dict(
            index=0, begin_wall_ns=start + 150, end_wall_ns=start + 152, perception=None
        ),
        dict(
            index=1,
            begin_wall_ns=start + 240,
            end_wall_ns=start + 242,
            snapshot_read_wall_ns=start + 241,
            snapshot_read_source_ns=30_000_000,
            perception=results[1],
        ),
    ]
    counters = dict(
        offered=2,
        accepted=2,
        rejected=0,
        overwritten=0,
        cancelled=0,
        expired_pending=0,
        started=2,
        completed=2,
        published=2,
        late=0,
        errors=0,
        obsolete=0,
    )
    return dict(
        status="PASS",
        closed=True,
        fault="none",
        actual_vehicle_control=False,
        live_camera=False,
        runtime_promotion=False,
        quality_acceptance=False,
        live20Hz_acceptance=False,
        cold_calls_excluded=0,
        thread_errors=[],
        traces=dict(state=state, camera=camera, control=control),
        model_calls=calls,
        worker=dict(counters=counters, clock_fault=False),
        fresh_output_observed=True,
        media=dict(originals=[dict(bgra_sha256="a" * 64)]),
        overlap_jobs_during_backend=dict(state=1, control=1),
        unique_consumed_frames=1,
    )


class AsyncAuditTests(unittest.TestCase):
    def test_valid_observational_trace_replays(self):
        self.assertEqual(audit(fixture())["status"], "PASS")

    def test_changed_denominator_identity_deadline_scope_or_overlap_fails(self):
        mutations = (
            lambda r: r["worker"]["counters"].update(overwritten=1),
            lambda r: r["traces"]["control"][1].update(
                snapshot_read_source_ns=130_000_000
            ),
            lambda r: r["traces"]["control"][1].update(
                snapshot_read_wall_ns=1_100_000_213
            ),
            lambda r: r.update(runtime_promotion=True),
            lambda r: r["overlap_jobs_during_backend"].update(control=0),
            lambda r: r["model_calls"][0]["identity"].update(source_ns=21_000_000),
            lambda r: r["model_calls"][0]["result"].update(model_sha256="0" * 64),
            lambda r: r.update(fresh_output_observed=False),
        )
        for mutate in mutations:
            report = deepcopy(fixture())
            mutate(report)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit(report)


if __name__ == "__main__":
    unittest.main()
