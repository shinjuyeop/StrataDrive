"""CRC32C acceleration preserves the original independent wire check."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration/diagnostics'))
from audit_service_response import crc32c


class ResponseCrc(unittest.TestCase):
    def test_known_vectors(self):
        self.assertEqual(crc32c(b''),0)
        self.assertEqual(crc32c(b'123456789'),0xe3069283)

    def test_matches_bitwise_reference_for_bounded_packet_sizes(self):
        generator=random.Random(9701)
        for size in (1,3,4,24,25,57,58,62,64,128,255,256,512,1024):
            raw=bytes(generator.randrange(256) for _ in range(size));reference=0xffffffff
            for byte in raw:
                reference^=byte
                for _ in range(8):reference=(reference>>1)^(0x82f63b78 if reference&1 else 0)
            self.assertEqual(crc32c(raw),reference^0xffffffff)


if __name__=='__main__':unittest.main()
