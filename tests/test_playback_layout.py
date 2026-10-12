"""Image boundaries and stale payload/loader pair rejection."""
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from playback_layout import stage,FLASH_START,FLASH_END,DEBUG_TEXT,LOADER_ADDRESS

class PlaybackLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock=(ROOT/'NANOV170.IMG').read_bytes();cls.input=(ROOT/'out/NANOV170.IMG').read_bytes()
        cls.payload=(ROOT/'out/playback/playback.bin').read_bytes()
        line=next(l for l in (ROOT/'out/playback/loader.patch').read_text().splitlines() if not l.startswith('#'))
        cls.loader=bytes.fromhex(line.split(':')[2])
    def test_staging_preserves_layout_and_resource_bytes(self):
        result=Image(stage(self.stock,self.input,self.payload,self.loader));before=Image(self.input)
        self.assertEqual(result.modules,before.modules);self.assertEqual(result.sections,before.sections)
        self.assertEqual(result.date,before.date);self.assertTrue(result.header_copy_ok())
        self.assertEqual(result.crc_stored(),result.crc_calc())
        for section in result.sections:
            a=section['offset'];b=a+section['length'];self.assertEqual(result.d[a:b],before.d[a:b])
        self.assertEqual(result.d[FLASH_START:FLASH_START+len(self.payload)],self.payload)
        self.assertEqual(result.d[FLASH_END:],before.d[FLASH_END:-4]+result.d[-4:])
    def test_occupied_padding_and_stale_code_pairs_are_rejected(self):
        changed=Image(self.input);changed.d[FLASH_START]=1;changed.finalize()
        with self.assertRaisesRegex(ValueError,'padding'):stage(self.stock,changed.d,self.payload,self.loader)
        payload=self.payload+bytes(4)
        with self.assertRaises(ValueError):stage(self.stock,self.input,payload,self.loader)
        changed=bytearray(self.payload);struct.pack_into('<I',changed,4,0x03050001)
        with self.assertRaisesRegex(ValueError,'entry'):stage(self.stock,self.input,changed,self.loader)
    def test_reclaimed_message_has_only_the_audited_literal_reference(self):
        image=Image(self.stock);needle=struct.pack('<I',LOADER_ADDRESS);hits=[]
        for module in image.modules:
            for kind in ('code','data'):
                offset=image.l2f(module[kind+'_load']);data=image.d[offset:offset+module[kind+'_len']]
                for i in range(len(data)):
                    if data.startswith(needle,i):hits.append((module['index'],kind,module[kind+'_exec']+i))
        self.assertEqual(hits,[(21,'code',0x03079dfc)])
        offset,_=image.region(0,LOADER_ADDRESS)
        self.assertEqual(image.d[offset:offset+84],DEBUG_TEXT)

if __name__=='__main__':unittest.main()
