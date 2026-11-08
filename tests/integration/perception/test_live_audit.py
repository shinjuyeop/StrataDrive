from copy import deepcopy
import unittest
from audit_live import audit


def fixture():
    """Small independent symbolic trace: two camera frames, ten observed ticks."""

    def identity(frame, source, clock=7):
        return dict(
            epoch=1,
            clock_instance=clock,
            frame=frame,
            source_ns=source,
            camera_id=1,
            calibration_revision=1,
        )

    prep = dict(
        state="READY",
        started_wall_ns=1,
        finished_wall_ns=10,
        calls=[
            dict(number=n, started_wall_ns=n * 3 - 2, elapsed_wall_ns=2)
            for n in (1, 2, 3)
        ],
    )
    ticks = [
        dict(
            frame=10 + n,
            source_ns=100_000_000 + n * 10_000_000,
            scheduled_wall_ns=1_000_000_000 + n * 10_000_000,
            begin_wall_ns=1_000_000_000 + n * 10_000_000,
            end_wall_ns=1_001_000_000 + n * 10_000_000,
        )
        for n in range(1, 11)
    ]
    callbacks, submissions, calls, consumer = [], [], [], []
    for n in (1, 2):
        source = 100_000_000 + n * 50_000_000
        wall = 1_001_000_000 + n * 50_000_000
        number = 10 + n * 5
        ident = identity(number, source)
        callbacks.append(
            dict(
                frame=number, source_ns=source, callback_wall_ns=wall, outcome="offered"
            )
        )
        submissions.append(
            dict(
                identity=ident,
                received_wall_ns=wall + 1,
                pump_wall_ns=wall + 2,
                accepted=True,
            )
        )
        calls.append(
            dict(
                phase="sensor",
                identity=ident,
                start_wall_ns=wall + 3,
                complete_wall_ns=wall + 4,
                detections=[],
            )
        )
        consumer.append(
            dict(
                frame=number,
                source_ns=source,
                source_now_ns=source,
                expires_ns=source + 100_000_000,
                wall_ns=wall + 5,
                detections=[],
            )
        )
    consumer.append(dict(frame=None, wall_ns=1_600_000_000))
    calls = [
        dict(
            phase="startup",
            identity=identity(n, 0, 1),
            start_wall_ns=n * 3 - 2,
            complete_wall_ns=n * 3,
        )
        for n in (1, 2, 3)
    ] + calls
    worker = dict(
        submitted=2,
        overwritten=0,
        started=2,
        completed=2,
        published=2,
        rejected=0,
        errors=0,
        late=0,
        obsolete=0,
        cancelled=0,
        invalidated=0,
    )
    ingress = dict(
        received=2,
        accepted=2,
        overwritten=0,
        malformed=0,
        submitted=2,
        rejected=0,
        cancelled=0,
        after_close=0,
    )
    return dict(
        status="PASS",
        closed=True,
        cleanup_errors=[],
        preparation=prep,
        stream_started_wall_ns=1_000_000_000,
        stream_finished_wall_ns=1_120_000_000,
        final_worker=dict(stopped=True, busy=False),
        requested_camera_frames=2,
        clock_instance=7,
        enable_frame=10,
        enable_source_ns=100_000_000,
        ticks=ticks,
        callbacks=callbacks,
        submissions=submissions,
        model_calls=calls,
        consumer=consumer,
        worker=dict(counters=worker, pending=False),
        ingress=dict(counters=ingress, pending=False),
        unique_consumed=2,
        fault="none",
    )


class LiveAuditTests(unittest.TestCase):
    def test_independent_good_trace(self):
        self.assertEqual(audit(fixture())["unique_consumed"], 2)

    def test_mutations_cannot_turn_missing_or_stale_work_into_acceptance(self):
        original = fixture()
        mutations = (
            lambda r: r["preparation"].update(state="FAILED"),
            lambda r: r["preparation"]["calls"].pop(0),
            lambda r: r["preparation"]["calls"][2].update(elapsed_wall_ns=100_000_000),
            lambda r: r["model_calls"][0].update(start_wall_ns=0),
            lambda r: r["model_calls"][-1]["identity"].update(clock_instance=9),
            lambda r: r["model_calls"][-1].update(error="failed"),
            lambda r: r["callbacks"][1].update(frame=15),
            lambda r: r["callbacks"][0].update(source_ns=149_000_000),
            lambda r: r["submissions"][0].update(received_wall_ns=1_052_000_000),
            lambda r: r["consumer"][0].update(wall_ns=1_151_000_001),
            lambda r: r["consumer"][0].update(source_now_ns=250_000_000),
            lambda r: r["consumer"][0].update(expires_ns=250_000_001),
            lambda r: r["consumer"][0].update(detections=[{}]),
            lambda r: r["worker"]["counters"].update(overwritten=1),
            lambda r: r["worker"]["counters"].update(errors=True),
            lambda r: r["ingress"].update(pending=True),
            lambda r: r["consumer"].pop(),
            lambda r: r.update(fault="blackout"),
            lambda r: r.update(fault="slow"),
            lambda r: r.update(fault="silence"),
            lambda r: r["final_worker"].update(busy=True),
        )
        for index, mutate in enumerate(mutations):
            report = deepcopy(original)
            mutate(report)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                audit(report)


if __name__ == "__main__":
    unittest.main()
