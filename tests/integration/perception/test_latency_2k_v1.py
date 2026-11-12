import unittest
from unittest.mock import patch
from audit_carla_latency_2k_v1 import check_variant, audit_readback


class LatencyVariantTests(unittest.TestCase):
    def report(self, condition, variant):
        return dict(
            schema="m10-carla-latency-2k-v1", condition=condition, variant=variant
        )

    def test_declared_variant_cannot_be_silently_changed(self):
        for condition, variant in [
            ("baseline-01", "baseline"),
            ("tensor-01", "tensor"),
            ("balanced-01", "balanced"),
            ("confirm-01", "tensor"),
            ("confirm-01", "balanced"),
        ]:
            check_variant(self.report(condition, variant))
        for condition, variant in [
            ("baseline-01", "tensor"),
            ("tensor-01", "balanced"),
            ("balanced-01", "baseline"),
            ("confirm-01", "baseline"),
        ]:
            with self.assertRaises(ValueError):
                check_variant(self.report(condition, variant))

    def test_deferred_requires_observed_engine_cap(self):
        r = self.report("balanced-01", "balanced")
        with patch(
            "audit_carla_latency_2k_v1.original_readback", return_value={"ok": True}
        ) as prior:
            with self.assertRaises(ValueError):
                audit_readback(r, 't.MaxFPS = "0"')
            prior.assert_not_called()
            self.assertEqual(audit_readback(r, 't.MaxFPS = "100"'), {"ok": True})
            self.assertEqual(prior.call_args.args[0]["condition"], "pool-deferred-01")


class SelectionTests(unittest.TestCase):
    def row(self, variant="baseline", mean=100, p95=120, hz=17, fresh=0.45, rtf=0.85):
        return dict(
            variant=variant,
            status="PASS",
            raw_verified=True,
            end_to_end=dict(capture_to_backend_return=dict(mean_ms=mean, p95_ms=p95)),
            camera_hz=hz,
            fresh_fraction=fresh,
            realtime_factor=rtf,
        )

    def test_latency_improvement_can_pass_below20Hz(self):
        from latency_2k_selection_v1 import select

        b = self.row()
        t = self.row("tensor", 95)
        d = self.row("balanced", 94, hz=18, rtf=0.9)
        self.assertEqual(select(b, [t, d])["selected_variant"], "tensor")
        d["end_to_end"]["capture_to_backend_return"]["mean_ms"] = 90
        self.assertEqual(select(b, [t, d])["selected_variant"], "balanced")

    def test_bad_tails_availability_or_overrun_are_not_selected(self):
        from latency_2k_selection_v1 import eligibility, select

        b = self.row()
        for row in [
            self.row("tensor", 99),
            self.row("tensor", 90, p95=127),
            self.row("tensor", 90, hz=15),
            self.row("tensor", 90, fresh=0.39),
            self.row("balanced", 90, rtf=1.06),
        ]:
            self.assertFalse(eligibility(b, row)["eligible"])
        self.assertIsNone(
            select(b, [self.row("tensor", 99), self.row("balanced", 90, rtf=2)])[
                "selected_variant"
            ]
        )


if __name__ == "__main__":
    unittest.main()
