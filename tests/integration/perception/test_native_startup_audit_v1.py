"""Mutation checks for cold-call accounting and owner/publication separation."""

from copy import deepcopy
from dataclasses import asdict
import unittest
from physical_ai.perception.async_native_v1 import NativeResult
from physical_ai.perception.contract import FrameIdentity
from audit_native_startup_v1 import audit_preparation


def fixture():
    calls, rows = [], []
    for i in range(1, 4):
        identity = FrameIdentity(1, 1, i, 0)
        result = asdict(NativeResult(identity))
        calls.append(
            dict(
                identity=asdict(identity),
                received_wall_ns=i * 10,
                begin_wall_ns=i * 10 + 1,
                end_wall_ns=i * 10 + 2,
                owner_thread_id=7,
                result=result,
            )
        )
        rows.append(
            dict(
                number=i,
                synthetic=True,
                published=False,
                begin_wall_ns=i * 10,
                end_wall_ns=i * 10 + 3,
                elapsed_wall_ns=3,
                owner_thread_id=7,
                result=result,
            )
        )
    prep = dict(
        state="READY", error=None, started_wall_ns=1, finished_wall_ns=33, calls=rows
    )
    final = deepcopy(prep)
    final["state"] = "CANCELLED"
    return dict(
        preparation=prep,
        preparation_final=final,
        preparation_calls=calls,
        model_calls=[dict(begin_wall_ns=40, owner_thread_id=7)],
        live_camera=False,
        traces=dict(control=[dict(perception=None)]),
    )


class NativeStartupAuditTests(unittest.TestCase):
    def test_complete_separate_denominators(self):
        result = audit_preparation(fixture())
        self.assertEqual(result["total_backend_calls"], 4)
        self.assertEqual(result["startup_calls"], 3)

    def test_missing_cold_call_owner_switch_and_synthetic_publication_rejected(self):
        def remove(r):
            r["preparation_calls"].pop(0)

        def owner(r):
            r["model_calls"][0]["owner_thread_id"] = 8

        def early(r):
            r["model_calls"][0]["begin_wall_ns"] = 20

        def publish(r):
            r["traces"]["control"][0]["perception"] = r["preparation_calls"][0][
                "result"
            ]

        def omit_final(r):
            r["preparation_final"]["calls"].pop(0)

        for change in (remove, owner, early, publish, omit_final):
            with self.subTest(change=change.__name__):
                r = fixture()
                change(r)
                with self.assertRaises(ValueError):
                    audit_preparation(r)


if __name__ == "__main__":
    unittest.main()
