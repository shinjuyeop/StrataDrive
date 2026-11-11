import unittest
from unittest.mock import patch
from audit_carla_viewport_v1 import audit_readback, normalized


class ViewportTests(unittest.TestCase):
    def test_identity_adapter_does_not_edit_report(self):
        r = dict(condition="viewport-small-02", schema="m10-carla-viewport-v1")
        self.assertEqual(normalized(r)["condition"], "copy-prefault-01")
        self.assertEqual(r["condition"], "viewport-small-02")
        with self.assertRaises(ValueError):
            normalized(dict(r, condition="unknown"))

    def test_initial_viewport_must_be_observed_before_capture(self):
        r = dict(condition="viewport-small-01", schema="m10-carla-viewport-v1")
        line = "Reallocating scene render targets to support 128x128 Format 10"
        for log in (
            "",
            line.replace("128x128", "856x640"),
            "STRATA_READBACK_V1 " + line,
        ):
            with self.assertRaises(ValueError):
                audit_readback(r, log)
        with patch(
            "audit_carla_viewport_v1.parent_readback", return_value={"ok": True}
        ):
            self.assertEqual(audit_readback(r, line), {"ok": True})


if __name__ == "__main__":
    unittest.main()
