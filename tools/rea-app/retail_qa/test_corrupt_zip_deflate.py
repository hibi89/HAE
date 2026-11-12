"""A malformed DEFLATE stream must be a controlled HOLD, not an uncaught crash."""
from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from test_customer_delivery import owner, package, reports

ROOT = Path(__file__).resolve().parents[1] / "retail"


class BrokenDeflateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bundle = self.root / "original-reports"
        self.bundle.mkdir()
        for name, payload in reports().items():
            (self.bundle / name).write_bytes(owner._encode(payload))
        self.delivery = self.root / "review"
        self.archive = self.root / "review.zip"
        owner.build(self.bundle, self.delivery)
        package.pack(self.bundle, self.delivery, self.archive)
        self.source_sha = {p.name: owner._hash(p.read_bytes()) for p in self.bundle.iterdir()}
        with zipfile.ZipFile(self.archive) as z:
            info = z.getinfo("review.json")
        raw = bytearray(self.archive.read_bytes())
        name_len, extra_len = struct.unpack_from("<HH", raw, info.header_offset + 26)
        start = info.header_offset + 30 + name_len + extra_len
        self.assertGreater(info.compress_size, 10)
        raw[start] = 0xFF  # Invalid first DEFLATE block, CRC/central directory unchanged.
        self.archive.write_bytes(raw)

    def test_corrupt_deflate_stream_returns_delivery_hold(self):
        with self.assertRaisesRegex(owner.DeliveryError, "invalid ZIP data"):
            package.verify_zip(self.archive, self.bundle)
        self.assertEqual(self.source_sha, {p.name: owner._hash(p.read_bytes()) for p in self.bundle.iterdir()})

    def test_cli_corrupt_deflate_returns_code_two_without_traceback(self):
        cmd = [sys.executable, str(ROOT / "package_delivery.py"), "verify-zip",
               "--bundle", str(self.bundle), "--archive", str(self.archive)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("HOLD:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.source_sha, {p.name: owner._hash(p.read_bytes()) for p in self.bundle.iterdir()})


if __name__ == "__main__":
    unittest.main()
