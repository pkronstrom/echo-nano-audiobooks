import hashlib
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from approved_icons import encode, decode, icon_bytes, load_manifest, apply_icons
from rknano_fw import Image

class ApprovedIconsTests(unittest.TestCase):
    def test_page_major_bit_order(self):
        rows = ['0' * 20 for _ in range(16)]
        for x, y in [(0,0), (19,7), (3,8), (4,15)]:
            rows[y] = rows[y][:x] + '1' + rows[y][x+1:]
        expected = bytearray(40)
        expected[0]=1; expected[19]=128; expected[23]=1; expected[24]=128
        self.assertEqual(encode(rows), expected)
        self.assertEqual(decode(expected), rows)
    def test_invalid_grid_rejected(self):
        for rows in [[], ['0'*20]*15, ['x'*20]*16, ['0'*19]*16]:
            with self.assertRaises(ValueError): encode(rows)
    def test_pinned_assets_and_renderings(self):
        manifest=load_manifest()
        self.assertEqual(len(manifest['icons']),8)
        for icon in manifest['icons']:
            data=icon_bytes(icon['id'])
            self.assertEqual(decode(data),icon['pixels'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),icon['bitmap_sha256'])
            if icon['source_file']:
                self.assertEqual(hashlib.sha256((ROOT/icon['source_file']).read_bytes()).hexdigest(),icon['source_sha256'])
        self.assertEqual(next(i for i in manifest['icons'] if i['id']=='play')['symbol'],'music')

@unittest.skipUnless((ROOT/'NANOV170.IMG').exists() and (ROOT/'out/NANOV170.IMG').exists(), 'local firmware fixtures required')
class ApprovedIconImageTests(unittest.TestCase):
    def test_only_six_bitmaps_changed(self):
        stock=Image((ROOT/'NANOV170.IMG').read_bytes()); image=Image((ROOT/'out/NANOV170.IMG').read_bytes())
        before=bytes(image.d); changes=apply_icons(image,stock)
        expected=bytearray(before)
        self.assertEqual(len(changes),6)
        for change in changes:
            offset,_=image.region(change['module'],change['address'])
            expected[offset:offset+40]=icon_bytes(change['id'])
        self.assertEqual(image.d,expected)
    def test_wrong_base_is_rejected_atomically(self):
        stock=Image((ROOT/'NANOV170.IMG').read_bytes()); image=Image((ROOT/'out/NANOV170.IMG').read_bytes())
        offset,_=image.region(21,0x0307951c); image.d[offset]^=1
        before=bytes(image.d)
        with self.assertRaises(ValueError): apply_icons(image,stock)
        self.assertEqual(bytes(image.d),before)
        stock.d[100]^=1
        with self.assertRaises(ValueError): apply_icons(image,stock)
