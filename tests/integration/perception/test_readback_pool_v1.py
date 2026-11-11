import unittest
from unittest.mock import patch

from audit_carla_readback_pool_v1 import audit_readback, normalized


class ReadbackPoolTests(unittest.TestCase):
    def test_adapter_preserves_original_identity(self):
        r = dict(
            condition="pool-deferred-01", schema="m10-carla-readback-pool-v1", marker=17
        )
        a = normalized(r)
        self.assertEqual(a["condition"], "deferred-01")
        self.assertEqual(a["marker"], 17)
        self.assertEqual(r["condition"], "pool-deferred-01")

    def test_actual_console_values_required(self):
        r = dict(condition="pool-baseline-01", schema="m10-carla-readback-pool-v1")
        valid = 'r.SceneRenderTargetResizeMethod = "2"\nr.SceneRenderTargetResizeMethodForceOverride = "1"'
        for text in ("", valid.replace('"2"', '"0"'), valid.replace('"1"', '"0"')):
            with self.assertRaises(ValueError):
                audit_readback(r, text)
        with patch(
            "audit_carla_readback_pool_v1.original_readback", return_value={"ok": True}
        ) as mocked:
            self.assertEqual(audit_readback(r, valid), {"ok": True})
            self.assertEqual(mocked.call_args[0][0]["condition"], "baseline-01")


if __name__ == "__main__":
    unittest.main()
