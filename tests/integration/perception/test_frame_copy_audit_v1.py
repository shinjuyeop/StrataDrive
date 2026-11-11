from copy import deepcopy
import unittest

from audit_carla_frame_copy_v1 import audit_details


def report():
    stages = dict(
        begin=100,
        gray=110,
        health=120,
        resize=130,
        tensor=140,
        inference=150,
        decode=160,
        end=170,
    )
    identity = dict(frame=5)
    stages.update(identity=identity, owner_thread_id=17)
    pool = dict(
        capacity=120,
        reserved=0,
        completed=0,
        allocated_bytes=120 * 3840 * 2304 * 4,
        allocation_ns=8,
    )
    return dict(
        schema="m10-carla-frame-copy-v1",
        condition="copy-prefault-01",
        copy_errors=[],
        enabled_wall_ns=50,
        copy_preparation=dict(
            mode="prefault", begin_wall_ns=10, end_wall_ns=20, pool=pool
        ),
        copy_final=dict(pool, reserved=1, completed=1),
        traces=dict(
            camera=[
                dict(
                    begin_wall_ns=60,
                    view_ready_wall_ns=61,
                    copy_end_wall_ns=62,
                    offer_entry_wall_ns=63,
                    offer_end_wall_ns=64,
                    end_wall_ns=65,
                )
            ]
        ),
        backend_stages=[stages],
        preparation_calls=[],
        model_calls=[
            dict(
                identity=identity,
                owner_thread_id=17,
                begin_wall_ns=90,
                end_wall_ns=180,
                result=dict(
                    convert_ns=0, preprocess_ns=40, inference_ns=10, postprocess_ns=10
                ),
            )
        ],
    )


class FrameCopyAuditTests(unittest.TestCase):
    def test_baseline_and_prefault_accounting(self):
        r = report()
        self.assertEqual(audit_details(r)["sensor_stages"], 1)
        r.update(condition="copy-baseline-01", copy_final=None)
        r["copy_preparation"].update(mode="baseline", pool=None)
        self.assertEqual(audit_details(r)["sensor_stages"], 1)

    def test_rejects_missing_or_renewed_provenance(self):
        for case in range(9):
            r = deepcopy(report())
            if case == 0:
                r["copy_final"]["completed"] = 0
            elif case == 1:
                r["copy_final"]["reserved"] = 2
            elif case == 2:
                r["copy_preparation"]["end_wall_ns"] = 60
            elif case == 3:
                r["copy_preparation"]["pool"]["allocated_bytes"] = 1
            elif case == 4:
                r["traces"]["camera"][0]["copy_end_wall_ns"] = 59
            elif case == 5:
                r["backend_stages"][0]["owner_thread_id"] = 18
            elif case == 6:
                r["backend_stages"][0]["inference"] = 145
            elif case == 7:
                r["backend_stages"] = []
            elif case == 8:
                r["copy_errors"] = ["overflow"]
            with self.subTest(case=case), self.assertRaises(ValueError):
                audit_details(r)


if __name__ == "__main__":
    unittest.main()
