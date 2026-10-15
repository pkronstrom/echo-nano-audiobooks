"""Playback/refresh overlay ownership and preserved upper memory boundary."""
from pathlib import Path
import sys
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from playback_layout import RAM_START,RAM_END

class PlaybackMemoryTests(unittest.TestCase):
    def test_playback_has_room_for_book_ui_without_crossing_other_modules(self):
        image=Image((ROOT/'NANOV170.IMG').read_bytes())
        self.assertEqual(RAM_END,0x0309fff0)
        self.assertGreaterEqual(RAM_END-RAM_START,48*1024)
        overlaps=[]
        for m in image.modules:
            for kind in ('code','data','bss'):
                start=m[kind+'_exec'];end=start+m[kind+'_len']
                if m[kind+'_len'] and start<RAM_END and end>RAM_START:
                    overlaps.append((m['index'],kind))
        self.assertEqual(overlaps,[(40,'code')])

    def test_refresh_load_invalidates_playback_after_replacing_hook_sites(self):
        image=Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        module=image.modules[40]
        start=module['code_exec'];end=start+module['code_len']
        self.assertLessEqual(start,RAM_START)
        self.assertGreater(end,RAM_START+16)
        offset=image.l2f(module['code_load'])
        data=image.d[offset:offset+module['code_len']]
        self.assertNotEqual(struct.unpack_from('<I',data,RAM_START-start)[0],0x32504e45)
        # These overlay-local branches must be replaced before a forward module
        # copy reaches the playback header. Resident save wrappers check magic.
        for address in (0x03079b1e,0x0307b31a,0x030817be,0x030822ac,0x030825c4,0x030828ec):
            self.assertLess(address+4,RAM_START)
            owner=31 if address==0x0307b31a else 21 if address==0x03079b1e else 33
            old,_=image.region(owner,address)
            self.assertNotEqual(image.d[old:old+4],data[address-start:address-start+4])
