"""Execute the native clock conversion and replacement painter at hour boundaries."""
import os,struct,subprocess,tempfile,unittest
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *
import test_playback_runtime_arm as runtime
from playback_layout import read_patch
ROOT=runtime.ROOT
FONT=((31,17,31),(18,31,16),(29,21,23),(21,21,31),(7,4,31),(23,21,29),(31,21,29),(1,1,31),(31,21,31),(23,21,31))
class PlayerTimeHoursTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  env=dict(os.environ);env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'clock.patch'
   subprocess.check_output(['tools/asm2patch.sh','playback/hooks/player_time_hours.S',str(p)],cwd=ROOT,env=env)
   cls.patch=read_patch(p)
 def test_full_millisecond_range_clock_pixels_and_isolation(self):
  for ms in (0,3599000,3600000,3610000,7199000,36000000,360000000,0xffffffff):
   with self.subTest(ms=ms):
    image=runtime.Image((ROOT/'NANOV170.IMG').read_bytes());c=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);c.mem_map(0x03000000,0x100000)
    for index in (0,27):
     m=image.modules[index];off=image.l2f(m['code_load']);c.mem_write(m['code_exec'],bytes(image.d[off:off+m['code_len']]))
    c.mem_write(self.patch[1],self.patch[2]);before=bytes([0xa5])*640;c.mem_write(0x03007d88,before)
    def hook(cpu,address,size,user):
     if address==0x03051524:cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    c.hook_add(UC_HOOK_CODE,hook)
    def call(address,args):
     for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):c.reg_write(r,v)
     c.reg_write(UC_ARM_REG_SP,0x030fe000);c.reg_write(UC_ARM_REG_LR,0x030ff001)
     c.emu_start(address|1,0x030ff000,count=10000)
     self.assertEqual(c.reg_read(UC_ARM_REG_PC),0x030ff000);self.assertEqual(c.reg_read(UC_ARM_REG_SP),0x030fe000)
    call(0x030594b0,(ms//1000,0x030f0000,0x030f0004,0x030f0008))
    hours=struct.unpack('<H',c.mem_read(0x030f0000,2))[0];minutes=c.mem_read(0x030f0004,1)[0];seconds=c.mem_read(0x030f0008,1)[0]
    call(0x0307ab7e,(hours,minutes,seconds,0))
    text=(str(hours)+':' if hours else '')+f'{minutes:02}:{seconds:02}'
    pixels=[]
    for ch in text:pixels.extend((0x28,0) if ch==':' else tuple(n<<1 for n in FONT[int(ch)])+(0,))
    self.assertLessEqual(len(pixels),38)
    expected=bytearray(before)
    for x in range(10,48):expected[x*5+3]=0
    for x,n in enumerate(pixels,10):expected[x*5+3]=n
    self.assertEqual(bytes(c.mem_read(0x03007d88,640)),bytes(expected))
