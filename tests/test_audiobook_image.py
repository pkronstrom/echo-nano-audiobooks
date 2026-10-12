import hashlib
from pathlib import Path
import struct
import unittest
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from playback_layout import HOOKS,read_patch,FLASH_START,AUDIO_REFS

class AudiobookImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock=Image((ROOT/'NANOV170.IMG').read_bytes())
        cls.base=Image((ROOT/'out/NANOV170.IMG').read_bytes())
        cls.book=Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
    def test_complete_hooks_payload_and_crc(self):
        self.assertEqual(self.book.crc_stored(),self.book.crc_calc());self.assertTrue(self.book.header_copy_ok())
        self.assertEqual(self.book.modules,self.stock.modules)
        self.assertEqual(self.book.sections,self.stock.sections)
        for name,(mod,addr,length,callee) in HOOKS.items():
            off,_=self.book.region(mod,addr)
            self.assertEqual(self.book.d[off:off+length],read_patch(ROOT/f'out/playback/{name}.patch')[2])
        payload=(ROOT/'out/playback/playback.bin').read_bytes()
        self.assertEqual(self.book.d[FLASH_START:FLASH_START+len(payload)],payload)
        off,_=self.book.region(32,0x0307cf14);self.assertEqual(self.book.d[off:off+8],'P3a\0'.encode('utf-16le'))
    def test_music_exclusion_and_resources_are_preserved(self):
        # Refresh patch regions are byte-identical to the already tested P1b image.
        for name in ('cfw_blob','cfw_hooks'):
            for line in (ROOT/f'out/gen/{name}.patch').read_text().splitlines():
                line=line.split('#',1)[0].strip()
                if not line:continue
                mod,address,data=line.split(':');expected=bytes.fromhex(data)
                offset,_=self.book.region(int(mod),int(address,16))
                self.assertEqual(self.book.d[offset:offset+len(expected)],self.base.d[offset:offset+len(expected)])
        for section in self.book.sections:
            a=section['offset'];b=a+section['length'];self.assertEqual(self.book.d[a:b],self.base.d[a:b])
    def test_recovery_is_later_dated_stock_code(self):
        recovery=Image((ROOT/'out/audiobook/recovery/NANOV170.IMG').read_bytes())
        expected=Image(bytes(self.stock.d));expected.set_date(recovery.date);expected.finalize()
        self.assertEqual(recovery.d,expected.d);self.assertGreater(recovery.date,self.book.date)
    def test_audio_pointer_audit_and_audio_only_whitelist(self):
        hits=[];needle=struct.pack('<I',0x03005a89)
        for m in self.stock.modules:
            for kind in ('code','data'):
                off=self.stock.l2f(m[kind+'_load']);data=self.stock.d[off:off+m[kind+'_len']]
                hits.extend((m['index'],m[kind+'_exec']+i) for i in range(len(data)) if data.startswith(needle,i))
        self.assertEqual(sorted(hits),sorted(AUDIO_REFS))
        for mod,addr in AUDIO_REFS:
            off,_=self.book.region(mod,addr);self.assertEqual(self.book.d[off:off+4],struct.pack('<I',0x03005ab4))
        off,_=self.book.region(0,0x03005ab4)
        self.assertEqual(self.book.d[off:off+43],self.stock.d[off:off+43])

if __name__=='__main__':unittest.main()
