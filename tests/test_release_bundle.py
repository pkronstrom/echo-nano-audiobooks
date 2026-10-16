import copy
import hashlib
import json
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import apply_release as ar
import build_release as br
from rknano_fw import Image


def fixture():
    data = bytearray(2048)
    data[0x10:0x18] = b'Rockchip'
    data[0x1f8:0x200] = b'RKnanoFW'
    struct.pack_into('<I', data, 0x1f4, 1024)
    im = Image(data)
    im.set_date('20260824')
    im.finalize()
    base = bytes(im.d)
    im.d[800] = 42
    im.set_date('20261012')
    im.finalize()
    target = bytes(im.d)
    man = dict(schema=1, base_sha256=ar.sha(base), target_sha256=ar.sha(target),
               size=len(base), default_date='20261012', source_commit='a' * 40,
               source_dirty=False, ranges=br.sparse_ranges(base, target))
    return base, target, man


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.base, self.target, self.man = fixture()
        self.allow = patch.dict(ar.STOCK, {ar.sha(self.base): 'synthetic test fixture'})
        self.allow.start()
        self.addCleanup(self.allow.stop)

    def test_reconstruct_exact_and_reject_wrong_stock_or_tamper(self):
        self.assertEqual(bytes(ar.reconstruct(self.base, self.man)[1].d), self.target)
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            ar.reconstruct(self.target, self.man)
        bad = copy.deepcopy(self.man)
        bad['ranges'][-1]['hex'] = '00'
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            ar.reconstruct(self.base, bad)

    def test_ranges_schema_bounds_overlap_and_encoding(self):
        for ranges in ([{'offset': -1, 'hex': 'ff'}], [{'offset': 2048, 'hex': 'ff'}],
                       [{'offset': 1, 'hex': 'ffff'}, {'offset': 2, 'hex': '00'}],
                       [{'offset': True, 'hex': '00'}], [{'offset': 1, 'hex': '0'}],
                       [{'offset': 1, 'hex': '00', 'extra': 1}], []):
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                ar.validate_manifest(dict(self.man, ranges=ranges))
        for change in ({'schema': 2}, {'schema': True}, {'extra': 1}, {'size': True},
                       {'base_sha256': '0' * 64}, {'source_dirty': 1}, {'source_commit': 'bad'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ar.validate_manifest(dict(self.man, **change))

    def test_invalid_dates(self):
        for date in ('20260230', '20261301', '2026101', 'abcd1012', '99991231', None):
            with self.subTest(date=date), self.assertRaises(ValueError):
                ar.date_value(date)

    def test_output_dates_recovery_input_preserved_and_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stock = root / 'stock.img'
            stock.write_bytes(self.base)
            manifest = root / 'patch.json'
            manifest.write_text(json.dumps(self.man))
            output = root / 'ready'
            with self.assertRaises(ValueError):
                ar.apply(stock, output, manifest, '20260824')
            self.assertFalse(output.exists())
            report = ar.apply(stock, output, manifest, '20261231')
            self.assertEqual(stock.read_bytes(), self.base)
            custom = ar.checked_image((output / 'custom/NANOV170.IMG').read_bytes())
            recovery = ar.checked_image((output / 'recovery/NANOV170.IMG').read_bytes())
            self.assertEqual(custom.date, '20261231')
            self.assertEqual(recovery.date, '20270101')
            recovery.set_date('20260824')
            recovery.finalize()
            self.assertEqual(bytes(recovery.d), self.base)
            self.assertEqual(report['files']['custom/NANOV170.IMG'], ar.sha(custom.d))
            with self.assertRaisesRegex(ValueError, 'already exists'):
                ar.apply(stock, output, manifest)

    def test_crc_header_and_protected_layout(self):
        damaged = bytearray(self.target)
        damaged[900] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC'):
            ar.checked_image(damaged)
        base, target = Image(self.base), Image(self.target)
        target.modules.append({})
        with self.assertRaisesRegex(ValueError, 'layout'):
            ar.compatible(base, target)

    def test_builder_rejects_dirty_and_protected_resources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'base').write_bytes(self.base)
            (root / 'target').write_bytes(self.target)
            with patch.object(br.subprocess, 'check_output', side_effect=['a' * 40, ' M dirty.py']):
                with self.assertRaisesRegex(ValueError, 'dirty'):
                    br.build(root / 'base', root / 'target', root / 'candidate.zip')
            self.assertFalse((root / 'candidate.zip').exists())
        base, target = Image(self.base), Image(self.target)
        base.sections = target.sections = [dict(name='images', offset=800, length=1)]
        with self.assertRaisesRegex(ValueError, 'protected resource'):
            ar.compatible(base, target)
        with self.assertRaisesRegex(ValueError, 'malformed'):
            ar.checked_image(b'x')

    def test_cli_help_and_clear_error(self):
        command = [sys.executable, str(ROOT / 'tools/apply_release.py')]
        result = subprocess.run(command + ['--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--date', result.stdout)
        result = subprocess.run(command + ['--input', '/nonexistent.img', '--output', '/nonexistent-output'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('error:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    @unittest.skipUnless((ROOT / 'NANOV170.IMG').exists() and (ROOT / 'out/audiobook/NANOV170.IMG').exists(), 'local stock and built target required')
    def test_browser_relocation_is_exact_and_bounded(self):
        base = Image((ROOT / 'NANOV170.IMG').read_bytes())
        target_bytes = (ROOT / 'out/audiobook/NANOV170.IMG').read_bytes()
        target = Image(target_bytes)
        self.assertNotEqual(base.modules[31], target.modules[31])
        ar.compatible(base, target)
        # Reject every other table change, including relocation of another module.
        for index, field, value in ((31, 'code_load', 0x0308e004),
                                    (31, 'code_exec', 0x0307941c),
                                    (31, 'code_len', 9308 + 14064),
                                    (31, 'code_len', 9308 + 17),
                                    (31, 'code_len', 9308 + 12),
                                    (31, 'data_load', 0x0308e080),
                                    (31, 'bss_len', 2154),
                                    (32, 'code_load', 0x0308e000)):
            with self.subTest(index=index, field=field, value=value):
                changed = Image(target_bytes)
                changed.modules[index][field] = value
                with self.assertRaisesRegex(ValueError, 'layout'):
                    ar.compatible(base, changed)
        header = 0x3c800 + 9308
        code_end = struct.unpack_from('<I', target.d, header + 8)[0]
        for offset, value in ((0, 0), (4, 0x0307b884), (4, 0x0307b875),
                              (4, code_end | 1), (8, code_end + 4),
                              (12, code_end - 4), (12, 0x03080474)):
            with self.subTest(header_offset=offset, value=value):
                changed = Image(target_bytes)
                struct.pack_into('<I', changed.d, header + offset, value)
                with self.assertRaisesRegex(ValueError, 'layout'):
                    ar.compatible(base, changed)
        changed = Image(target_bytes)
        protected = next(s for s in base.sections if s['name'] == 'images')
        changed.d[protected['offset']] ^= 1
        with self.assertRaisesRegex(ValueError, 'protected resource'):
            ar.compatible(base, changed)
        # The exception cannot be reused with a different purported stock image.
        base.d[0x3c800] = 1
        with self.assertRaisesRegex(ValueError, 'layout'):
            ar.compatible(base, target)

    @unittest.skipUnless((ROOT / 'NANOV170.IMG').exists() and (ROOT / 'out/audiobook/NANOV170.IMG').exists(), 'local stock and built target required')
    def test_real_bundle_deterministic_and_standalone_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / 'first.zip', root / 'second.zip'
            # Freeze bundle inputs while other contributors may edit the workspace.
            snapshot = root / 'source'
            for name in ('tools/apply_release.py', 'tools/rknano_fw.py', 'tools/prepare_book.py',
                         'LICENSE', 'docs/releases.md', 'docs/audiobooks.md', 'docs/automatic-book-preparation.md', 'docs/approved-icons.json',
                         'docs/icon-library-assets/tabler/LICENSE', 'docs/icon-library-assets/lucide/LICENSE',
                         'docs/icon-library-assets/bootstrap/LICENSE'):
                dest = snapshot / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            with patch.object(br, 'ROOT', snapshot), patch.object(br.subprocess, 'check_output', side_effect=['a' * 40, '', 'a' * 40, '']):
                br.build(ROOT / 'NANOV170.IMG', ROOT / 'out/audiobook/NANOV170.IMG', first)
                br.build(ROOT / 'NANOV170.IMG', ROOT / 'out/audiobook/NANOV170.IMG', second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertFalse(any(name.endswith('.IMG') for name in archive.namelist()))
                for library in ('tabler','lucide','bootstrap'):
                    self.assertTrue(archive.read(f'licenses/{library}.txt'))
                self.assertTrue(archive.read('approved-icons.json'))
                guide = archive.read('audiobooks.md').decode()
                self.assertIn('python3 prepare_book.py', guide)
                self.assertNotIn('builds/phase3a', guide)
                self.assertNotIn('tools/prepare_book.py', guide)
                automatic_guide=archive.read('automatic-book-preparation.md').decode()
                self.assertIn('BOOK.M3U',automatic_guide)
                self.assertNotIn('tools/prepare_book.py',automatic_guide)
                archive.extractall(root / 'bundle')
            run = subprocess.run([sys.executable, str(root / 'bundle/apply_release.py'), '--input', str(ROOT / 'NANOV170.IMG'), '--output', str(root / 'ready')], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual((root / 'ready/custom/NANOV170.IMG').read_bytes(), (ROOT / 'out/audiobook/NANOV170.IMG').read_bytes())
            report = json.loads(run.stdout)
            self.assertEqual(ar.checked_image((root / 'ready/recovery/NANOV170.IMG').read_bytes()).date, report['recovery_date'])


if __name__ == '__main__':
    unittest.main()
