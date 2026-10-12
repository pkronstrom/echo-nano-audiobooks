"""Binary integration checks. Build stock, custom and recovery images first."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("firmware", ROOT / "tools/rknano_fw.py")
firmware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firmware)


class BaselineChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock_bytes = (ROOT / "NANOV170.IMG").read_bytes()
        cls.stock = firmware.Image(cls.stock_bytes)
        cls.custom = firmware.Image((ROOT / "out/NANOV170.IMG").read_bytes())
        cls.recovery = firmware.Image((ROOT / "out/recovery/NANOV170.IMG").read_bytes())

    def test_exact_stock_image(self):
        self.assertIn(hashlib.sha256(self.stock_bytes).hexdigest(), firmware.STOCK)

    def test_all_images_have_valid_crc_and_matching_headers(self):
        for img in (self.stock, self.custom, self.recovery):
            with self.subTest(date=img.date):
                self.assertEqual(img.crc_calc(), img.crc_stored())
                self.assertTrue(img.header_copy_ok())

    def test_default_baseline_retains_stock_power_settings(self):
        count = 0
        for name in ("power_idle.patch", "power_clocks.patch"):
            for line in (ROOT / "patches" / name).read_text().splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                mod, addr, value = line.split(":", 2)
                offset, _ = self.stock.region(int(mod), int(addr, 16))
                length = len(bytes.fromhex(value))
                self.assertEqual(self.custom.d[offset:offset + length],
                                 self.stock.d[offset:offset + length], line)
                count += 1
        self.assertGreater(count, 0)

    def test_library_shuffle_scope_patches_are_present(self):
        for line in (ROOT / "patches/shuffle_scope.patch").read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            mod, addr, value = line.split(":", 2)
            if int(addr, 16) in (0x03083026, 0x03083042, 0x03083060):
                continue  # P1b replaces raw File Browser settings with folder containment
            offset, _ = self.custom.region(int(mod), int(addr, 16))
            value = bytes.fromhex(value)
            self.assertEqual(self.custom.d[offset:offset + len(value)], value, line)

    def test_raw_scope_patch_stays_within_reclaimed_code(self):
        line = (ROOT / "out/gen/music_scope_10_raw_settings.patch").read_text().splitlines()[-1]
        mod, addr, data = line.split(":")
        self.assertEqual((int(mod), int(addr, 16), len(bytes.fromhex(data))),
                         (33, 0x0308301e, 0x030830dc - 0x0308301e))
        offset, _ = self.custom.region(33, 0x030830dc)
        self.assertEqual(self.custom.d[offset:offset+8], self.stock.d[offset:offset+8])

    def test_recovery_changes_only_dates_and_crc(self):
        self.assertGreater(self.recovery.date, self.custom.date)
        self.assertEqual(len(self.recovery.d), len(self.stock.d))
        expected = firmware.Image(self.stock_bytes)
        expected.set_date(self.recovery.date)
        expected.finalize()
        self.assertEqual(self.recovery.d, expected.d)

    def test_modified_stock_is_rejected(self):
        changed = bytearray(self.stock_bytes)
        changed[0x1000] ^= 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrong.IMG"
            path.write_bytes(changed)
            for args in (("check", str(path)),
                         ("patch", str(path), str(Path(tmp) / "output.IMG"))):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools/rknano_fw.py"), *args],
                    capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(tmp) / "output.IMG").exists())


if __name__ == "__main__":
    unittest.main()
