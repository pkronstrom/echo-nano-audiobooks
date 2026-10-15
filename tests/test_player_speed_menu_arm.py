"""Isolated Speed menu wrappers and resident guards; no combined image build."""
from pathlib import Path
import os,struct,subprocess,sys,tempfile,unittest
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from playback_layout import read_patch
STOP=0x030ff000;OUT=0x030f0000;MENU=0xff00
class PlayerSpeedMenuTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  env=dict(os.environ);env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
  with tempfile.TemporaryDirectory(prefix='speed-menu-') as d:
   p=Path(d);obj=p/'menu.o';elf=p/'menu.elf';binary=p/'menu.bin'
   def run(args):return subprocess.check_output(args,cwd=ROOT,env=env)
   run(['arm-none-eabi-gcc','-mthumb','-mcpu=cortex-m3','-Os','-ffreestanding','-fno-common','-fno-strict-aliasing','-Isrc','-Iplayback','-c','playback/player_speed_menu.c','-o',str(obj)])
   cls.apis={'playback_speed_supported':0x030ff100,'playback_rate_request':0x030ff110,'playback_rate_poll':0x030ff120,'playback_rate_cancel':0x030ff130,'playback_speed_label_text':0x030ff140}
   run(['arm-none-eabi-ld','-Ttext=0x03098000','-e','player_speed_menu_record',str(obj),'-o',str(elf)]+['--defsym='+k+'='+hex(v|1) for k,v in cls.apis.items()])
   run(['arm-none-eabi-objcopy','-O','binary',str(elf),str(binary)]);cls.code=binary.read_bytes()
   cls.symbols={line.split()[2]:int(line.split()[0],16) for line in run(['arm-none-eabi-nm',str(elf)]).decode().splitlines() if len(line.split())==3}
   (p/'playback_syms.inc').write_text('\n'.join('.equ '+k+', '+hex(v) for k,v in cls.symbols.items()))
   cls.patches=[]
   for source in sorted((ROOT/'playback/hooks').glob('player_speed_menu*.S')):
    destination=p/(source.stem+'.patch');run(['tools/asm2patch.sh',str(source),str(destination),str(p)])
    cls.patches.append(read_patch(destination))
 def setUp(self):
  self.image=Image((ROOT/'NANOV170.IMG').read_bytes());self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);self.cpu.mem_map(0x03000000,0x100000)
  for index in (0,32):
   m=self.image.modules[index]
   for kind in ('code','data'):
    o=self.image.l2f(m[kind+'_load']);self.cpu.mem_write(m[kind+'_exec'],bytes(self.image.d[o:o+m[kind+'_len']]))
  _,address,data=read_patch(ROOT/'out/playback/speed_guard.patch');self.cpu.mem_write(address,data)
  # Explicit shared ABI: entry pushes r4/r5, tests ENP2, restores args and BX target.
  self.assertEqual(bytes(self.cpu.mem_read(0x03072f62,22)).hex(),'30b4084c2468084dac4218bf0846844630bc03bc6047')
  for module,address,data in self.patches:self.assertEqual(module,32);self.cpu.mem_write(address,data)
  self.cpu.mem_write(0x03098000,self.code);self.cpu.mem_write(0x03092400,b'ENP2')
  self.exit_service=False;self.native=False;self.stop_at=None;self.supported=1;self.request=1;self.poll=0;self.transition=0;self.calls=[];self.cpu.hook_add(UC_HOOK_CODE,self.hook)
 def hook(self,cpu,address,size,user):
  if address==self.stop_at:cpu.reg_write(UC_ARM_REG_PC,STOP);return
  r0=cpu.reg_read(UC_ARM_REG_R0);r1=cpu.reg_read(UC_ARM_REG_R1);r2=cpu.reg_read(UC_ARM_REG_R2);result=None
  if address==0x030ff140:
   label=('1x','1.25x','1.5x','1.75x','2x')[r0-4]
   cpu.mem_write(0x030f1000,label.encode()+b'\0');result=0x030f1000
  elif address in self.apis.values():
   self.calls.append((address,r0));result={0x030ff100:self.supported,0x030ff110:self.request,0x030ff120:self.poll,0x030ff130:0}[address]
  elif address==0x03067988:
   self.assertLess(r0,431);offset=self.image.lang_text(2,r0)-58;cpu.mem_write(r1,bytes(self.image.d[offset:offset+58]));self.calls.append(('record',r0));result=0
  elif address==0x03067860:
   self.assertLess(r0,431);offset=self.image.lang_text(2,r0);cpu.mem_write(r1,bytes(self.image.d[offset:offset+r2]));self.calls.append(('text',r0));result=0
  elif address==0x03079fbc:
   self.calls.append(('native-action',r0))
   if not self.native:result=0
  elif address==0x03079a74:
   self.calls.append(('native-service',))
   if not self.native:result=self.transition
  elif self.native and address==0x03051540:result=int(self.exit_service and r0==21)
  elif self.native and address in (0x0306b040,0x0306b082,0x0306b05c,0x0306b0a0,0x03051540,0x03051574,0x0305159a):result=0
  elif address==0x0306b26a:self.calls.append(('window',r0,r1));result=0
  if result is not None:cpu.reg_write(UC_ARM_REG_R0,result&0xffffffff);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 def call(self,address,*args):
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):self.cpu.reg_write(reg,value)
  self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000);self.cpu.reg_write(UC_ARM_REG_LR,STOP|1)
  self.cpu.emu_start(address|1,STOP,count=20000);self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),STOP)
  self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),0x030fe000-(40 if self.stop_at==0x0307bd40 else 0))
  return self.cpu.reg_read(UC_ARM_REG_R0)
 def record(self,id):
  self.call(0x03079aac,id,OUT);return struct.unpack('<29H',self.cpu.mem_read(OUT,58))
 def test_music_record_preserves_six_controls_and_only_appends_when_supported(self):
  self.supported=0;before=self.record(237);self.assertEqual(before[7],6)
  self.supported=1;after=self.record(237);self.assertEqual(after[:7],before[:7]);self.assertEqual(after[8:14],before[8:14]);self.assertEqual(after[7],7);self.assertEqual(after[14],MENU)
 def test_native_seventh_row_index_dispatches_speed(self):
  self.record(237)
  state=0x030f2000
  self.cpu.mem_write(state+10,struct.pack('<H',6))
  self.cpu.mem_write(state+20,struct.pack('<I',OUT))
  self.cpu.reg_write(UC_ARM_REG_R4,state)
  self.stop_at=0x0307a7f8
  self.call(0x0307a7e8)
  self.assertIn(('native-action',MENU),self.calls)
 def test_synthetic_records_and_bounded_labels(self):
  rec=self.record(MENU);self.assertEqual(rec[1],237);self.assertEqual(rec[7:13],(5,MENU+1,MENU+2,MENU+3,MENU+4,MENU+5))
  for index,label in enumerate(('Speed','1x','1.25x','1.5x','1.75x','2x')):
   self.cpu.mem_write(OUT,b'Z'*20);self.call(0x03079ed0,MENU+index,OUT,12)
   self.assertEqual(bytes(self.cpu.mem_read(OUT,12)).decode('utf-16le').split('\0')[0],label)
   self.assertEqual(bytes(self.cpu.mem_read(OUT+12,2)),b'ZZ')
   if index:self.assertEqual(self.record(MENU+index)[7],0)
 def test_action_preserves_native_and_does_not_relaunch_twice(self):
  for id in (238,247,256,262,263,264,MENU):self.call(0x0307a79c,id);self.assertIn(('native-action',id),self.calls)
  for result,expected in ((-1,0),(1,0),(2,1),(3,1)):
   self.calls=[];self.request=result;self.assertEqual(self.call(0x0307a79c,MENU+2),expected)
   self.assertIn((0x030ff110,5),self.calls)
   self.assertEqual([x for x in self.calls if x[0]=='window'],[('window',3,0)] if result==3 else [])
 def test_service_polls_and_cancels_on_native_transition(self):
  self.poll=2;self.assertEqual(self.call(0x0307b2b4),1);self.assertNotIn(('native-service',),self.calls)
  self.calls=[];self.poll=1;self.transition=1;self.assertEqual(self.call(0x0307b2b4),1);self.assertTrue(any(x[0]==0x030ff130 for x in self.calls))
 def setup_native_menu(self,index):
  self.record(237)
  self.native=True
  self.cpu.mem_write(0x0300e914+16,struct.pack('<I',1))
  state=0x03006230+24
  self.cpu.mem_write(state,struct.pack('<10H',2,0,0,0,0,index,255,236,0,0)+struct.pack('<I',OUT))
  return state
 def read16(self,address):return struct.unpack('<H',self.cpu.mem_read(address,2))[0]
 def read32(self,address):return struct.unpack('<I',self.cpu.mem_read(address,4))[0]
 def test_native_enter_and_back_restore_music_settings_record(self):
  parent=self.setup_native_menu(6)
  self.assertEqual(self.call(0x0307a79c,MENU),0)
  child=parent+24
  self.assertEqual(self.read32(0x0300e924),2)
  record=self.read32(child+20)
  self.assertEqual(self.read16(record),MENU)
  self.assertEqual(self.read16(record+14),5)
  self.assertEqual(self.read16(child+14),237)
  self.assertEqual(self.read16(child),2)
  # Native Back computes parent/depth and reloads the record through patched a66c.
  self.cpu.reg_write(UC_ARM_REG_R4,child)
  self.cpu.reg_write(UC_ARM_REG_R8,0x0300e914)
  self.stop_at=0x0307a670
  self.call(0x0307a636)
  self.assertEqual(self.read32(0x0300e924),1)
  restored=self.read32(parent+20)
  self.assertEqual(self.read16(restored),237)
  self.assertEqual(self.read16(restored+14),7)
  self.assertEqual(self.read16(restored+28),MENU)
  self.assertEqual(self.read16(parent+10),6)
 def test_native_existing_sound_submenus_are_unchanged(self):
  for index,id in ((0,238),(1,247),(2,256),(5,264)):
   with self.subTest(id=id):
    self.setUp();parent=self.setup_native_menu(index)
    self.call(0x0307a79c,id)
    child=self.read32(parent+24+20)
    self.assertEqual(self.read16(child),id)
    expected_offset=self.image.lang_text(2,id)-58
    self.assertEqual(bytes(self.cpu.mem_read(child,58)),bytes(self.image.d[expected_offset:expected_offset+58]))
 def test_native_balance_and_volume_leaf_dispatch_unchanged(self):
  for index,id in ((3,262),(4,263)):
   with self.subTest(id=id):
    self.setUp();self.setup_native_menu(index)
    self.stop_at=0x0307bd40
    self.assertEqual(self.call(0x0307a79c,id),id)
    self.assertIn(('native-action',id),self.calls)
 def test_native_service_exit_cancels_pending_request(self):
  self.native=True;self.poll=1;self.exit_service=True
  self.assertEqual(self.call(0x0307b2b4),1)
  self.assertIn(('native-service',),self.calls)
  self.assertTrue(any(x[0]=='window' and x[1]==0 for x in self.calls))
  self.assertTrue(any(x[0]==0x030ff130 for x in self.calls))
 def test_native_pending_service_returns_before_stale_continuation(self):
  self.native=True;self.poll=2
  self.assertEqual(self.call(0x0307b2b4),1)
  self.assertNotIn(('native-service',),self.calls)
  # Still-draining service really enters stock SetMenuService, then returns normally.
  self.poll=1;self.calls=[]
  self.assertEqual(self.call(0x0307b2b4),0)
  self.assertIn(('native-service',),self.calls)
 def test_invalid_payload_never_forwards_synthetic_ids(self):
  self.cpu.mem_write(0x03092400,b'BAD!');self.assertEqual(self.record(MENU),(0,)*29)
  self.cpu.mem_write(OUT,b'ZZ');self.call(0x03079ed0,MENU,OUT,2);self.assertEqual(bytes(self.cpu.mem_read(OUT,2)),bytes(2))
  self.assertEqual(self.call(0x0307a79c,MENU+1),0);self.assertEqual(self.calls,[])
  self.assertEqual(self.record(237)[7],6)
  self.call(0x0307a79c,238);self.assertIn(('native-action',238),self.calls)
if __name__=='__main__':unittest.main()
