"""Execute stock glyph/rasterizer with a synthetic flash-font bitmap."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from playback_layout import STOCK_SHA256
BASE=0x0300d6c0
OUTPUT=0x030e0000
STOP=0x030ff000
class NativeTextModeTests(unittest.TestCase):
 def setUp(self):
  source=(ROOT/'NANOV170.IMG').read_bytes()
  self.assertEqual(hashlib.sha256(source).hexdigest(),STOCK_SHA256)
  image=Image(source);module=image.modules[0]
  self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);self.cpu.mem_map(0x03000000,0x100000)
  for kind in ('code','data'):
   offset=image.l2f(module[kind+'_load'])
   self.cpu.mem_write(module[kind+'_exec'],bytes(image.d[offset:offset+module[kind+'_len']]))
  self.cpu.mem_write(BASE,bytes(40))
  self.half(36,1) # native 12px font
  self.reads=0
  self.cpu.hook_add(UC_HOOK_CODE,self.hook)
 def half(self,offset,value):self.cpu.mem_write(BASE+offset,struct.pack('<H',value))
 def word16(self,offset):return struct.unpack('<H',self.cpu.mem_read(BASE+offset,2))[0]
 def hook(self,cpu,address,size,context):
  if address==0x030689c6:
   self.assertEqual(cpu.reg_read(UC_ARM_REG_R2),26)
   # Twelve rows of 100000b, followed by native halfwidth classification0x10.
   bitmap=struct.pack('<12H',*([0x8000]*12))+b'\x00\x10'
   cpu.mem_write(cpu.reg_read(UC_ARM_REG_R1),bitmap);self.reads+=1
   cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 def call(self,address):
  self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000);self.cpu.reg_write(UC_ARM_REG_LR,STOP|1)
  self.cpu.emu_start(address|1,STOP,count=20000)
  self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),STOP)
 def glyph(self,logical):
  self.cpu.reg_write(UC_ARM_REG_R0,logical);self.call(0x03067904)
  self.cpu.mem_write(OUTPUT,bytes(1530));self.half(20,0);self.half(22,0)
  self.cpu.reg_write(UC_ARM_REG_R0,OUTPUT);self.cpu.reg_write(UC_ARM_REG_R1,ord('A'))
  self.call(0x03064814)
  return bytes(self.cpu.mem_read(OUTPUT,12))
 def test_mode_one_erases_ink_on_cleared_scratch(self):
  self.assertEqual(self.glyph(1),bytes(12))
  self.assertEqual(self.reads,1)
 def test_mode_zero_sets_ink_and_clears_background(self):
  self.assertEqual(self.glyph(0),b'\xff\x0f'+bytes(10))
  self.assertEqual(self.reads,1)
 def test_raw_mode_restore_is_exact_and_setter_is_asymmetric(self):
  for raw in (0,1,2,4):
   with self.subTest(raw=raw):
    self.half(32,raw)
    before=bytes(self.cpu.mem_read(BASE,40))
    self.cpu.reg_write(UC_ARM_REG_R0,0);self.call(0x03067904)
    self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0),raw)
    self.assertEqual(self.word16(32),2)
    self.half(32,raw)
    self.assertEqual(bytes(self.cpu.mem_read(BASE,40)),before)
if __name__=='__main__':unittest.main()
