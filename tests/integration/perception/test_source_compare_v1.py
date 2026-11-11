"""Geometry/provenance failures must not cross the2K/4K result boundary."""

from dataclasses import asdict, replace
import unittest
from audit_carla_source_compare_v1 import validate_result
from physical_ai.perception import async_native_2k_v1 as two, async_native_v1 as four
from physical_ai.perception.contract import FrameIdentity


class SourceCompareTests(unittest.TestCase):
    def test_geometry_and_candidate_are_bound(self):
        identity = FrameIdentity(1, 77, 5, 50_000_000)
        for module in (two, four):
            row = asdict(module.NativeResult(identity))
            self.assertEqual(asdict(validate_result(row)), row)
            for changes in (
                dict(width=2560, height=2304),
                dict(candidate="dfine-m-960"),
                dict(schema="unknown"),
            ):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    validate_result(dict(row, **changes))
        with self.assertRaises(ValueError):
            validate_result(
                dict(asdict(two.NativeResult(identity)), width=3840, height=2304)
            )

    def test_native_2k_layout_and_detection_bounds(self):
        identity = FrameIdentity(1, 77, 5, 50_000_000)
        packet = two.BgraPacket(identity, bytes(2560 * 1536 * 4), 1)
        packet.validate()
        with self.assertRaises(ValueError):
            replace(packet, bgra=bytes(3840 * 2304 * 4)).validate()
        valid = two.NativeDetection(0, 0.9, (0, 0, 2560, 1536))
        two.NativeResult(identity, (valid,)).validate()
        with self.assertRaises(ValueError):
            replace(valid, box=(0, 0, 2561, 1536)).validate()


if __name__ == "__main__":
    unittest.main()
