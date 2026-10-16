"""Stock reset trampoline must invalidate retained playback before application entry.
No factory dump is required: execute the app's two vector stages and real byte
reader; only sector I/O/locks are mocked by the shared loader fixture.
"""
from pathlib import Path
import os, struct, subprocess, tempfile, unittest
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
import test_payload_flash_read_arm as reader
from playback_layout import RAM_START, FLASH_START, LOADER_ADDRESS, read_patch, startup_invalidation_space
ROOT=Path(__file__).resolve().parents[1]

class StartupInvalidationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.patches=[]
  env=dict(os.environ);env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
  with tempfile.TemporaryDirectory() as d:
   for name in ('startup_invalidate','startup_invalidate_entry'):
    source=ROOT/'playback/hooks'/f'{name}.S'
    target=Path(d)/(name+'.patch')
    subprocess.check_output(['tools/asm2patch.sh',str(source),str(target)],cwd=ROOT,env=env)
    cls.patches.append(read_patch(target))
 def setup(self,patched=True,second=False):
  f=reader.PayloadFlashReadTests();f.setup_cpu((ROOT/'out/audiobook/NANOV170.IMG').read_bytes(),second,True)
  c=f.cpu;c.mem_map(0xe000e000,0x2000)
  # Restore stock entry even when the generated image includes the correction.
  c.mem_write(0x030660ca,bytes.fromhex('2de9f043'))
  if patched:
   for module,address,data in self.patches:
    self.assertEqual(module,0);c.mem_write(address,data)
  self.f=f;self.c=c;self.writes=[]
  c.hook_add(UC_HOOK_MEM_WRITE,self.observe_write)
  return f,c
 def observe_write(self,c,access,address,size,value,user):
  if RAM_START<=address<0x030a0000:self.writes.append((address,size,value))
 def startup(self):
  self.c.reg_write(UC_ARM_REG_SP,0x03004000)
  self.c.emu_start(0x03058865,0x030660ce,count=300000)
  self.assertEqual(self.c.reg_read(UC_ARM_REG_PC),0x030660ce)
 def test_stock_trampoline_retains_old_magic_but_patched_startup_clears_it(self):
  for patched in (False,True):
   self.setup(patched);self.c.mem_write(RAM_START,b'ENP2'+b'old state')
   marker=b'NanoCRebootFlag\0';self.c.mem_write(0x0309fff0,marker)
   self.startup()
   self.assertEqual(bytes(self.c.mem_read(RAM_START,4)),bytes(4) if patched else b'ENP2')
   self.assertEqual(bytes(self.c.mem_read(RAM_START+4,9)),b'old state')
   self.assertEqual(bytes(self.c.mem_read(0x0309fff0,16)),marker)
   self.assertEqual(self.writes,[(RAM_START,4,0)] if patched else [])
   self.assertEqual(self.c.reg_read(UC_ARM_REG_SP),0x03004000-28)
   self.assertEqual(struct.unpack('<7I',self.c.mem_read(0x03004000-28,28)),(0,0,0,0,0,0,0x030660cb))
 def test_startup_forces_real_reader_to_replace_retained_payload_in_both_slots(self):
  for second in (False,True):
   f,c=self.setup(second=second)
   payload=(ROOT/'out/playback/playback.bin').read_bytes();old=bytearray(payload)
   old[4:8]=struct.pack('<I',0x03092555);old[32:36]=b'OLD!';c.mem_write(RAM_START,bytes(old))
   # Demonstrate existing loader's ENP2-only fast path accepts stale bytes.
   c.reg_write(UC_ARM_REG_SP,0x03003f00);c.reg_write(UC_ARM_REG_LR,0x03010001)
   c.emu_start(LOADER_ADDRESS|1,0,count=200000)
   self.assertEqual(f.reads,[]);self.assertFalse(f.init_seen)
   self.startup()
   # Native initialization normally restores these flash-selection globals.
   c.mem_write(0x0300d454,struct.pack('<I',512));c.mem_write(0x0300e238,bytes([int(second)]));c.mem_write(0x0300e224,struct.pack('<I',26624))
   start,end=struct.unpack_from('<II',f.image.d,FLASH_START+8);c.mem_write(start,b'\xa5'*(end-start))
   f.returned=False;f.load()
   self.assertTrue(f.reads);self.assertEqual(bytes(c.mem_read(RAM_START,len(payload))),payload)
   self.assertEqual(bytes(c.mem_read(start,end-start)),bytes(end-start))
 def test_entry_preserves_original_register_frame_and_cold_start(self):
  for magic in (bytes(4),b'ENP2'):
   self.setup();c=self.c;c.mem_write(RAM_START,magic)
   regs=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12)
   for i,r in enumerate(regs):c.reg_write(r,0x12340000+i)
   c.reg_write(UC_ARM_REG_SP,0x03003f00);c.reg_write(UC_ARM_REG_LR,0x03010001)
   c.emu_start(0x030660cb,0x030660ce,count=1000)
   self.assertEqual(bytes(c.mem_read(RAM_START,4)),bytes(4))
   self.assertEqual(c.reg_read(UC_ARM_REG_SP),0x03003f00-28)
   self.assertEqual(tuple(c.reg_read(r) for r in regs),tuple(0x12340000+i for i in range(13)))
   self.assertEqual(struct.unpack('<7I',c.mem_read(0x03003f00-28,28)),tuple(0x12340000+i for i in range(4,10))+(0x03010001,))

 def test_pinned_diagnostic_and_reference_checks_before_suppression(self):
  original=(ROOT/'NANOV170.IMG').read_bytes()
  image=reader.Image(original);startup_invalidation_space(image)
  off,_=image.region(1,0x0307a240)
  self.assertEqual(image.d[off:off+4],bytes.fromhex('00bf00bf'))
  for module,address,replacement in ((0,0x030733e0,b'BAD!'),(0,0x030660ca,bytes(4)),(1,0x0307a444,bytes(4))):
   image=reader.Image(original);image.patch(module,address,replacement)
   with self.assertRaisesRegex(ValueError,'base changed'):startup_invalidation_space(image)
  image=reader.Image(original);image.patch(9,0x0307c154,struct.pack('<I',0x030733e1))
  with self.assertRaisesRegex(ValueError,'cave referenced'):startup_invalidation_space(image)
