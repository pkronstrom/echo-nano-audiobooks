"""Book directional events must not reach native chapter restart/skip dispatch."""
from pathlib import Path
import os, struct, subprocess, tempfile, unittest, sys
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from playback_layout import read_patch,player_controls_space
from rknano_fw import Image
STOP=0x030ff000; SEEK=0x030ff100; ACTIVE=0x030f0100
class PlayerControlsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  env=dict(os.environ);env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   def run(args):return subprocess.check_output(args,cwd=ROOT,env=env)
   run(['arm-none-eabi-gcc','-mthumb','-mcpu=cortex-m3','-Os','-ffreestanding','-Iplayback','-Isrc','-c','playback/player_controls.c','-o',str(p/'key.o')])
   run(['arm-none-eabi-ld','-Ttext=0x03098000','-e','playback_player_key',str(p/'key.o'),'-o',str(p/'key.elf'),'--defsym=playback_active='+hex(ACTIVE),'--defsym=playback_seek_request='+hex(SEEK|1),'--defsym=playback_rate_cancel='+hex((SEEK+16)|1)])
   run(['arm-none-eabi-objcopy','-O','binary',str(p/'key.elf'),str(p/'key.bin')]);cls.code=(p/'key.bin').read_bytes()
   cls.uninit=next(int(line.split()[0],16) for line in run(['arm-none-eabi-nm',str(p/'key.elf')]).decode().splitlines() if line.endswith(' playback_player_uninit'))
   (p/'playback_syms.inc').write_text('.equ playback_player_key, 0x03098000\n.equ playback_player_uninit, '+hex(cls.uninit)+'\n')
   cls.patches=[]
   for name in ('player_controls_guard','player_controls_key','player_controls_uninit_guard','player_controls_uninit_pointer'):
    run(['tools/asm2patch.sh','playback/hooks/'+name+'.S',str(p/(name+'.patch')),str(p)])
    cls.patches.append(read_patch(p/(name+'.patch')))
   cls.guard=read_patch(ROOT/'out/playback/speed_guard.patch')
 def run_key(self,event,active=1,guarded=False,valid=True,uninit=False):
  c=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);c.mem_map(0x03000000,0x100000);c.mem_write(0x03098000,self.code);c.mem_write(ACTIVE,struct.pack('<I',active));calls=[]
  if guarded:
   for _,address,data in self.patches+[self.guard]:c.mem_write(address,data)
   c.mem_write(0x03092400,b'ENP2' if valid else b'BAD!')
  def hook(cpu,address,size,user):
   if address==0x03063242:
    calls.append(('native',cpu.reg_read(UC_ARM_REG_R0)));cpu.reg_write(UC_ARM_REG_R0,event)
   elif address in (SEEK+16,0x03079512):
    calls.append(('cancel',) if address==SEEK+16 else ('uninit',));cpu.reg_write(UC_ARM_REG_R0,0)
   elif address==SEEK:
    value=cpu.reg_read(UC_ARM_REG_R0);calls.append(('seek',value if value<0x80000000 else value-0x100000000));cpu.reg_write(UC_ARM_REG_R0,0xffffffff)
   else:return
   cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  c.hook_add(UC_HOOK_CODE,hook);c.reg_write(UC_ARM_REG_R0,123);c.reg_write(UC_ARM_REG_SP,0x030fe000);c.reg_write(UC_ARM_REG_LR,STOP|1)
  entry=((0x0307a271 if guarded else self.uninit|1) if uninit else (0x0307a3d5 if guarded else 0x03098001))
  c.emu_start(entry,STOP,count=2000);self.assertEqual(c.reg_read(UC_ARM_REG_PC),STOP);self.assertEqual(c.reg_read(UC_ARM_REG_SP),0x030fe000)
  return c.reg_read(UC_ARM_REG_R0),calls
 def test_book_directional_phases_are_consumed_even_on_seek_refusal(self):
  for key,direction in ((4,1),(8,-1)):
   for phase in range(1,6):
    result,calls=self.run_key((phase<<28)|key)
    self.assertEqual(result,0)
    self.assertEqual(calls,[('native',123)]+([('seek',direction)] if phase in (2,3,4) else []))
 def test_music_and_sorted_folder_events_are_unchanged(self):
  for active in (0,2):
   for event in (0x40000004,0x40000008,0x30000004,0x50000008):
    result,calls=self.run_key(event,active);self.assertEqual(result,event);self.assertEqual(calls,[('native',123)])
 def test_bookmark_double_and_other_controls_retain_native_precedence(self):
  for event in (0,0x60000008,0x60000004,0x40000040,0x20000040,0x40001000):
   result,calls=self.run_key(event);self.assertEqual(result,event);self.assertEqual(calls,[('native',123)])

 def test_guard_falls_back_to_native_without_loaded_payload(self):
  for valid in (False,True):
   result,calls=self.run_key(0x40000008,guarded=True,valid=valid)
   self.assertEqual(result,0 if valid else 0x40000008)
   self.assertEqual(calls,[('native',123)]+([('seek',-1)] if valid else []))
 def test_layout_rejects_changed_diagnostic_and_references(self):
  data=(ROOT/'NANOV170.IMG').read_bytes()
  image=Image(data);player_controls_space(image)
  off,_=image.region(27,0x0307a260);self.assertEqual(image.d[off:off+4],bytes.fromhex('00bf00bf'))
  image=Image(data);image.patch(27,0x0307a3d4,b'BAD!')
  with self.assertRaisesRegex(ValueError,'diagnostic'):player_controls_space(image)
  image=Image(data);image.patch(27,0x0307a3d4-4,struct.pack('<I',0x0307a3d4))
  with self.assertRaisesRegex(ValueError,'referenced'):player_controls_space(image)

 def test_uninit_guard_cancels_pending_work_and_preserves_native_cleanup(self):
  for valid in (False,True):
   result,calls=self.run_key(0,guarded=True,valid=valid,uninit=True)
   self.assertEqual(calls,([('cancel',)] if valid else [])+[('uninit',)])
