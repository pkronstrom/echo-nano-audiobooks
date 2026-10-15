"""Checked browser-only geometry; shared bitmap resources remain unmodified."""
import struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
class BrowserLayoutTests(unittest.TestCase):
 def test_list_reclaims_panel_width_on_both_redraw_paths(self):
  im=Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
  expected={0x0307a442:'00bf00bf',0x0307a59a:'00bf00bf',
    0x0307a486:'4ff00d0b',0x0307a616:'0c20',
    0x0307a4e6:'4ff00001',0x0307a536:'4ff00001',
    0x0307a660:'4ff00001',0x0307a6e8:'4ff00001'}
  for addr,hexdata in expected.items():
   off,_=im.region(31,addr)
   with self.subTest(address=hex(addr)):self.assertEqual(im.d[off:off+len(bytes.fromhex(hexdata))],bytes.fromhex(hexdata))
 def test_highlight_tiles_cover_text_without_overdrawing_scrollbar(self):
  im=Image((ROOT/'NANOV170.IMG').read_bytes())
  base=next(s['offset'] for s in im.sections if s['name']=='images')
  for resource in (17,127):
   width,height=struct.unpack_from('<HH',im.d,base+32+16*resource)
   self.assertEqual((width,height),(92,16))
   self.assertEqual(32+width,124) # scrollbar starts x124
if __name__=='__main__':unittest.main()
