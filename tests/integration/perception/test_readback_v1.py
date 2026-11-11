"""Reject incomplete/mislabeled GPU evidence rather than publish invented timing."""

import copy
import json
import unittest

from audit_carla_readback_v1 import (
    PREFIX,
    STAGES,
    audit_capture,
    audit_readback,
    parse_trace,
)


def row(frame=5, serial=1, base=100, deferred=True):
    r = dict(
        frame=frame,
        serial=serial,
        timestamp=frame / 100,
        deferred=deferred,
        inflight=1,
        error="",
    )
    r.update({stage: base + i * 10 for i, stage in enumerate(STAGES)})
    if deferred:
        r["query"] = r["flush"]
    return r


def log(*rows):
    return "\n".join(PREFIX + json.dumps(r) for r in rows)


class ReadbackTests(unittest.TestCase):
    def test_baseline_and_deferred(self):
        for deferred in (True, False):
            r = row(deferred=deferred)
            self.assertEqual(parse_trace(log(r), deferred), [r])

    def test_completion_order_is_not_capture_order(self):
        a, b = row(), row(10, 2, 300)
        self.assertEqual(parse_trace(log(b, a), True), [a, b])

    def test_rejects_corrupt_trace_fields(self):
        for key, value in [
            ("frame", 6),
            ("frame", True),
            ("serial", 2),
            ("inflight", 4),
            ("deferred", False),
            ("error", "bounded_capacity"),
            ("timestamp", float("nan")),
            ("timestamp", -1),
            ("render", 99),
            ("query", 131),
            ("ready", 1),
            ("extra", 1),
        ]:
            with self.subTest(key=key, value=value):
                r = row()
                r[key] = value
                with self.assertRaises(ValueError):
                    parse_trace(log(r), True)

    def test_rejects_missing_duplicate_and_ambiguous_lines(self):
        for text in ("", log(row(), row()), "prefix" + log(row()), PREFIX + "{"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_trace(text, True)

    def test_rejects_hidden_queue_growth(self):
        rows = [row(5 * (i + 1), i + 1, 100 + i) for i in range(4)]
        with self.assertRaises(ValueError):
            parse_trace(log(*rows), True)

    def test_callback_join_requires_original_frame_and_timestamp(self):
        r = row()
        report = dict(
            condition="deferred-01",
            traces=dict(
                camera=[dict(frame=5, source_ns=50_000_000, begin_wall_ns=200)]
            ),
        )
        result = audit_readback(report, log(r))
        self.assertEqual(result["received"], 1)
        self.assertEqual(result["captured_without_callback"], [])
        self.assertEqual(result["metrics"]["blocking_query"]["mean_ms"], 0)
        for key, value in [
            ("frame", 10),
            ("source_ns", 51_000_000),
            ("begin_wall_ns", 169),
        ]:
            damaged = copy.deepcopy(report)
            damaged["traces"]["camera"][0][key] = value
            with self.assertRaises(ValueError):
                audit_readback(damaged, log(r))

    def test_undelivered_capture_is_counted(self):
        report = dict(condition="baseline-01", traces=dict(camera=[]))
        result = audit_readback(report, log(row(deferred=False)))
        self.assertEqual(result["captured_without_callback"], [5])

    def test_unrecognized_capture_identity_rejected(self):
        with self.assertRaises(ValueError):
            audit_capture(dict(condition="new", schema="m10-carla-readback-v1"))
        with self.assertRaises(ValueError):
            audit_capture(dict(condition="baseline-01", schema="wrong"))


if __name__ == "__main__":
    unittest.main()
