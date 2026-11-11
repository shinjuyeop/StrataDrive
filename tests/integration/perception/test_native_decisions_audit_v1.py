"""Reject altered completion clocks, deadline causes, and missing trace rows."""

from copy import deepcopy
import unittest

from audit_native_decisions_v1 import audit_decisions
from test_async_native_audit_v1 import fixture as base_fixture


def fixture():
    report = base_fixture()
    rows = [
        dict(
            identity=deepcopy(c["identity"]),
            received_wall_ns=c["received_wall_ns"],
            started_wall_ns=c["received_wall_ns"] + 1,
            started_source_ns=c["identity"]["source_ns"],
            backend_return_monotonic_ns=c["end_wall_ns"],
            decision_source_ns=30_000_000,
            decision_wall_ns=c["end_wall_ns"] + 1,
            source_expired=False,
            receipt_expired=False,
            outcome="published",
        )
        for c in report["model_calls"]
    ]
    report["decisions"] = dict(rows=rows, capacity=512, overflow=0)
    return report


class NativeDecisionAuditTests(unittest.TestCase):
    def test_fresh_completion_clocks_reproduce_publication(self):
        self.assertEqual(audit_decisions(fixture())["outcomes"], {"published": 2})

    def test_changed_clock_cause_identity_or_missing_trace_fails(self):
        mutations = (
            lambda r: r["decisions"].update(overflow=1),
            lambda r: r["decisions"]["rows"].pop(),
            lambda r: r["decisions"]["rows"][0].update(source_expired=True),
            lambda r: r["decisions"]["rows"][0].update(decision_source_ns=120_000_000),
            lambda r: r["decisions"]["rows"][0].update(decision_wall_ns=1_100_000_013),
            lambda r: r["decisions"]["rows"][0].update(backend_return_monotonic_ns=0),
            lambda r: r["decisions"]["rows"][0].update(outcome="late"),
            lambda r: r["decisions"]["rows"][0]["identity"].update(frame=99),
        )
        for mutate in mutations:
            r = fixture()
            mutate(r)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit_decisions(r)


if __name__ == "__main__":
    unittest.main()
