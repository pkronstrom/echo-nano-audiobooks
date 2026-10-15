"""Native module23 full/update draws, with module-local width hooks only."""
from pathlib import Path
import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from playback_layout import STOCK_SHA256, read_patch
STATE=0x0300ea3c
EXPECTED={
 'width':(0x0307a316,'4d20'),
 'text_full_left':(0x0307a428,'2c20'),
 'text_full_right':(0x0307a43c,'2c30'),
 'text_update_left':(0x0307a56a,'4ff02c08'),
 'text_update_right':(0x0307a58c,'2c30'),
 'icon':(0x0307a408,'d7f7e4fe'),
 'full_x':(0x0307a424,'1f27'),
 'update_x':(0x0307a568,'1f27'),
 'full_old':(0x0307a45a,'d7f7bbfe'),
 'full_new':(0x0307a46e,'d7f7b1fe'),
 'update_old':(0x0307a5ae,'d7f711fe'),
 'update_new':(0x0307a5c2,'d7f707fe'),
 'glyph_full':(0x0307a4b6,'d7f78dfe'),
 'glyph_update':(0x0307a60a,'d7f7e3fd'),
 'helpers':(0x03079e40,'04f10c00fff795fca08904f10c0128b332e02781b8f8000064680025401c08bfbde8f087701981b204f10c00fff781fc')
}
class MediaLayoutTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.patches={};cls.basepatches=[]
  env=dict(os.environ)
  env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
  with tempfile.TemporaryDirectory(prefix='echo-media-layout-') as directory:
   sources=[ROOT/'playback/hooks'/('media_row_'+n+'.S') for n in EXPECTED]
   sources += [ROOT/'patches'/(n+'.S') for n in ('recent_albums_50_mod23_setup','shuffle_20_mod23_key','track_artists_50_mod23_setup')]
   for source in sources:
    output=Path(directory)/(source.stem+'.patch')
    subprocess.run([str(ROOT/'tools/asm2patch.sh'),str(source),str(output)],cwd=ROOT,env=env,check=True,capture_output=True)
    patch=read_patch(output)
    if source.stem.startswith('media_row_'):cls.patches[source.stem.removeprefix('media_row_')]=patch
    else:cls.basepatches.append(patch)
 def test_combined_image_contains_media_hooks(self):
  image=Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
  for name,(module,address,data) in self.patches.items():
   off,_=image.region(module,address)
   with self.subTest(hook=name):self.assertEqual(bytes(image.d[off:off+len(data)]),data)
 def setUp(self):
  source=(ROOT/'NANOV170.IMG').read_bytes()
  self.assertEqual(hashlib.sha256(source).hexdigest(),STOCK_SHA256)
  self.image=Image(source);m=self.image.modules[23]
  self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);self.cpu.mem_map(0x03000000,0x100000)
  for kind in ('code','data'):
   offset=self.image.l2f(m[kind+'_load'])
   self.cpu.mem_write(m[kind+'_exec'],bytes(self.image.d[offset:offset+m[kind+'_len']]))
  for name,(address,original) in EXPECTED.items():
   self.assertEqual(bytes(self.cpu.mem_read(address,len(bytes.fromhex(original)))),bytes.fromhex(original))
  for module,address,data in self.basepatches:
   self.assertEqual(module,23);self.assertLessEqual(address+len(data),0x03079e40)
   self.cpu.mem_write(address,data)
  for module,address,data in self.patches.values():
   self.assertEqual(module,23);self.cpu.mem_write(address,data)
  self.put16(STATE,10);self.put16(STATE+22,1);self.put16(STATE+24,0);self.put16(STATE+26,2)
  self.cpu.mem_write(STATE+28,struct.pack('<I',0x030f0000))
  self.cpu.mem_write(0x030f0004,struct.pack('<I',0x030f0040))
  self.draws=[];self.texts=[];self.full=False;self.update=False
  self.cpu.hook_add(UC_HOOK_CODE,self.hook)
 def put16(self,address,value):self.cpu.mem_write(address,struct.pack('<H',value))
 def hook(self,cpu,address,size,user):
  result=None
  if address==0x030521d4:
   self.draws.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)))
   for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3):cpu.reg_write(r,0xdeadbeef)
   result=0
  elif address==0x03052b08:
   self.texts.append(struct.unpack('<4H',cpu.mem_read(cpu.reg_read(UC_ARM_REG_R0),8)));result=0
  elif address==0x0306b05c:
   event=cpu.reg_read(UC_ARM_REG_R0)
   result=int((event==371 and self.full) or (event==372 and self.update) or event==397)
  elif address==0x03067e4e:
   resource=cpu.reg_read(UC_ARM_REG_R0);p=cpu.reg_read(UC_ARM_REG_R1)
   cpu.mem_write(p,struct.pack('<8H',4,4 if resource==9 else 32,0,0,0,0,0,0));result=0
  elif address in (0x03051540,0x03051524,0x03051574,0x03067904,0x030678e0,0x0306b0a0,
                    0x0306b040,0x0306b082,0x030579a8,0x03052dfc):result=0
  if result is not None:
   cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 def draw(self,full=False,update=False):
  self.full=full;self.update=update
  self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000);self.cpu.reg_write(UC_ARM_REG_LR,0x030ff001)
  self.cpu.emu_start(0x0307a311,0x030ff000,count=10000)
  self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),0x030ff000)
  self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),0x030fe000)
 def check_rows(self):
  self.assertEqual(self.texts,[(13,2,123,13),(13,18,123,29)])
  self.assertNotIn(126,[d[0] for d in self.draws])
  self.assertEqual([d for d in self.draws if d[0] in (17,127)],[(127,0,0),(127,32,0),(17,0,16),(17,32,16)])
  self.assertEqual([d for d in self.draws if d[0] in (8,9)],[(8,124,0),(9,124,0)])
 def test_full_draw_preserves_glyphs_with_wide_rows(self):
  self.draw(full=True);self.check_rows()
  self.assertEqual([d for d in self.draws if d[0] in (10,11,131,132)],[(11,0,2),(131,0,18)])
 def test_update_draw_preserves_glyphs_with_wide_rows(self):
  self.draw(update=True);self.check_rows()
  self.assertEqual([d for d in self.draws if d[0] in (10,11,131,132)],[(11,0,2),(131,0,18)])
 def test_folder_glyph_selection_unchanged(self):
  self.put16(0x0300d482,5);self.put16(STATE+10,0)
  self.draw(full=True);self.check_rows()
  self.assertEqual([d for d in self.draws if d[0] in (10,11,131,132)],[(10,0,2),(132,0,18)])
 def test_helpers_fit_owned_cave_and_keep_stack_without_payload(self):
  _,address,data=self.patches['helpers']
  self.assertEqual((address,len(data)),(0x03079e40,48));self.assertLessEqual(address+len(data),0x03079ef6)
  self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000);self.cpu.reg_write(UC_ARM_REG_LR,0x030ff001)
  for r,v in ((UC_ARM_REG_R0,127),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,16)):self.cpu.reg_write(r,v)
  self.cpu.emu_start(address|1,0x030ff000,count=1000)
  self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),0x030fe000)
  self.assertEqual(self.draws,[(127,0,16),(127,32,16)])
  self.assertEqual(bytes(self.cpu.mem_read(0x03092400,4)),bytes(4))
 def test_native_resource_widths_keep_glyph_text_scrollbar_separate(self):
  base=next(s['offset'] for s in self.image.sections if s['name']=='images')
  for resource in (10,11,131,132):self.assertEqual(struct.unpack_from('<HH',self.image.d,base+32+16*resource),(10,12))
  for resource in (17,127):self.assertEqual(struct.unpack_from('<HH',self.image.d,base+32+16*resource),(92,16))
if __name__=='__main__':unittest.main()
