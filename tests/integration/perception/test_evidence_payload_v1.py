import tempfile
from pathlib import Path
import unittest

from evidence_payload_v1 import digest, payload


class PayloadTests(unittest.TestCase):
    def test_materialized_pointer_and_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            raw.write_bytes(b"evidence" * 100)
            sha, size = digest(raw), raw.stat().st_size
            self.assertEqual(payload(raw, sha, size), raw)
            cached = root / sha[:2] / sha[2:4] / sha
            cached.parent.mkdir(parents=True)
            cached.write_bytes(raw.read_bytes())
            pointer = root / "pointer"
            pointer.write_text(
                f"version https://git-lfs.github.com/spec/v1\noid sha256:{sha}\nsize {size}\n"
            )
            self.assertEqual(payload(pointer, sha, size, root), cached)
            for args in (
                (pointer, sha, size),
                (pointer, sha, size + 1, root),
                (pointer, "../bad", size, root),
            ):
                with self.assertRaises(ValueError):
                    payload(*args)
            cached.write_bytes(b"X" * size)
            with self.assertRaises(ValueError):
                payload(pointer, sha, size, root)

    def test_malformed_pointer_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pointer"
            path.write_text(
                "version https://git-lfs.github.com/spec/v1\noid sha256:../../x\nsize 4\n"
            )
            with self.assertRaises(ValueError):
                payload(path, "a" * 64, 4, directory)
