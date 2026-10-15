"""Native module32 list geometry, with real guarded Speed record/text wrappers."""
import os,struct,subprocess,tempfile,unittest
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
import test_player_speed_menu_arm as menu
ROOT=menu.ROOT
class SettingsLayoutTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  menu.PlayerSpeedMenuTests.setUpClass();cls.patches=[]
  env=dict(os.environ);env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
  with tempfile.TemporaryDirectory(prefix='settings-layout-') as d:
   for source in sorted((ROOT/'playback/hooks').glob('settings_row_*.S')):
    out=Path(d)/(source.stem+'.patch');subprocess.run(['tools/asm2patch.sh',str(source),str(out)],cwd=ROOT,env=env,check=True,capture_output=True)
    cls.patches.append(menu.read_patch(out))
 def setUp(self):
  self.f=menu.PlayerSpeedMenuTests();self.f.setUp();self.cpu=self.f.cpu
  self.baseline=bytes(self.cpu.mem_read(0x030797ec,0x3900))
  for module,address,data in self.patches:self.assertEqual(module,32);self.cpu.mem_write(address,data)
  self.draws=[];self.texts=[];self.full=False;self.update=False
  self.cpu.hook_add(UC_HOOK_CODE,self.hook)
 def hook(self,cpu,a,size,user):
  r0=cpu.reg_read(UC_ARM_REG_R0);result=None
  if a==0x030521d4:
   self.draws.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)))
   for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3):cpu.reg_write(r,0xdeadbeef)
   result=0
  elif a==0x03052b08:self.texts.append(struct.unpack('<4H',cpu.mem_read(r0,8)));result=0
  elif a==0x0306b05c:result=int((r0==203 and self.full) or (r0==206 and self.update) or r0==339)
  elif a==0x03067e4e:cpu.mem_write(cpu.reg_read(UC_ARM_REG_R1),struct.pack('<8H',4,4 if r0==9 else 32,0,0,0,0,0,0));result=0
  elif a in (0x03051540,0x03051524,0x03051574,0x03067904,0x030678e0,0x0306b0a0,0x0306b040,0x0306b082,0x030579a8,0x03052dfc):result=0
  if result is not None:cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 def draw(self,id=237,full=True,header=b'ENP2'):
  self.cpu.mem_write(0x03092400,header);record=self.f.record(id)
  self.cpu.mem_write(0x0300e924,struct.pack('<I',1))
  self.cpu.mem_write(0x03006248,struct.pack('<10H',2,0,0,1,0,0,255,236 if id==237 else 237,0,0)+struct.pack('<I',menu.OUT))
  self.full=full;self.update=not full;self.f.call(0x030795ce)
  return record
 def check(self,full,speed=False):
  self.assertNotIn(129,[d[0] for d in self.draws]);self.assertNotIn(130,[d[0] for d in self.draws])
  expected=[(17,0,0),(17,32,0)]+([] if full else [(127,0,16),(127,32,16)])
  self.assertEqual([d for d in self.draws if d[0] in (17,127)],expected)
  self.assertEqual(self.texts,[(3,2,110 if speed else 123,13),(3,18,110 if speed and full else 123,29)])
  self.assertEqual([d for d in self.draws if d[0] in (8,9)],[(8,124,0),(9,124,0)])
 def test_full_native_music_settings_without_payload(self):
  self.assertEqual(self.draw(header=b'CFW!')[7],6);self.check(True)
 def test_update_native_music_settings_without_payload(self):
  self.assertEqual(self.draw(full=False,header=b'CFW!')[7],6);self.check(False)
 def test_full_and_update_with_speed_menu(self):
  for full in (True,False):
   with self.subTest(full=full):
    self.setUp();self.assertEqual(self.draw(menu.MENU,full)[7],5);self.check(full,True)
 def test_seventh_speed_row_is_preserved(self):
  record=self.draw();self.assertEqual(record[7],7);self.assertEqual(record[14],menu.MENU);self.check(True)
 def test_second_logo_variant_is_removed(self):
  self.cpu.mem_write(0x030041da,b'\x01');self.draw();self.check(True)
 def test_resources_and_leaf_screen_bytes_are_unchanged(self):
  image=self.f.image;b=image.sections[-1]['offset']
  for resource in (17,127):self.assertEqual(struct.unpack_from('<2H',image.d,b+32+resource*16),(92,16))
  self.assertTrue(self.patches)
  for module,address,data in self.patches:self.assertGreaterEqual(address,0x03079738);self.assertLessEqual(address+len(data),0x030798ae)
  # All subsequent native action, slider and value-screen instructions remain
  # exactly the same as the already-tested Speed menu baseline.
  for start,end in ((0x030798ae,0x03079aac),(0x0307b800,0x0307cc00)):
   self.assertEqual(bytes(self.cpu.mem_read(start,end-start)),self.baseline[start-0x030797ec:end-0x030797ec])
 def test_combined_image_contains_settings_geometry(self):
  image=menu.Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
  for module,address,data in self.patches:
   off,_=image.region(module,address);self.assertEqual(bytes(image.d[off:off+len(data)]),data,hex(address))
