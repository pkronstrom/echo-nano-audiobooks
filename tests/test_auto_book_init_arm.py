"""Cold book init, local-symbol binding and native event-frame preservation."""
from pathlib import Path
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import hashlib
import json
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from hooks import encode_t32_branch

class ResidentBindingTests(unittest.TestCase):
 def binding(self):
  source=(ROOT/'tools/build_browser_sort.sh').read_text().split("<<'BIND'\n",1)[1].split('\nBIND',1)[0]
  self.assertIn('def resident_bindings(',source,'checked local ELF binding is missing')
  namespace={'__name__':'binding_test'}
  exec(compile(source,'<browser binding>','exec'),namespace)
  self.assertIn('resident_bindings',namespace,'checked local ELF binding is missing')
  return namespace['resident_bindings']
 def fixture(self):
  payload=struct.pack('<4I',0x32504e45,0x03092411,0x03092600,0x03092a00)+bytes(496)
  functions=['playback_folder_launch','navigation_browser_init','navigation_event','playback_browser_directory','playback_lookup','journal_try_write','journal_end_write','book_crc','playback_open','playback_read','playback_close']
  rows=[f'{0x03092410+i*8:08x} 00000008 T {name}' for i,name in enumerate(functions)]
  rows += ['03092600 00000160 b roots','03092760 00000001 b root_count','03092761 00000001 b chooser','03092762 00000001 b active','03092763 00000001 b returning','03092770 00000004 b active']
  return payload,rows
 def test_selects_unique_sized_local_and_public_symbols(self):
  payload,rows=self.fixture();bound=self.binding()('\n'.join(rows),payload)
  self.assertEqual(bound['BOOK_MENU_ACTIVE_ADDR'],0x03092762)
  self.assertEqual(bound['BOOK_ROOTS_ADDR'],0x03092600)
  self.assertEqual(bound['BOOK_NAV_EVENT_ADDR'],0x03092420)
 def test_rejects_ambiguous_wrong_type_and_out_of_bounds_bindings(self):
  payload,rows=self.fixture();bind=self.binding()
  for changed in [rows+[rows[-3]], [r.replace(' b roots',' B roots') for r in rows], [r.replace('03092600 00000160 b roots','03092900 00000160 b roots') for r in rows], [r.replace('03092420 00000008 T navigation_event','030925fc 00000008 T navigation_event') for r in rows]]:
   with self.subTest(rows=changed),self.assertRaises(ValueError):bind('\n'.join(changed),payload)


 def test_generated_header_and_binding_use_the_checked_payload_digest(self):
  payload,rows=self.fixture()
  source=(ROOT/'tools/build_browser_sort.sh').read_text().split("<<'BIND'\n",1)[1].split('\nBIND',1)[0]
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);out=root/'browser_sort';play=root/'playback';out.mkdir();play.mkdir();(play/'playback.bin').write_bytes(payload)
   with mock.patch.object(sys,'argv',['binding',str(out)]), mock.patch('subprocess.run',side_effect=lambda args,check:Path(args[-1]).write_bytes(payload)), mock.patch('subprocess.check_output',return_value='\n'.join(rows)):
    exec(compile(source,'<browser binding>','exec'),{'__name__':'__main__'})
   digest=hashlib.sha256(payload).hexdigest()
   self.assertEqual(json.loads((out/'playback.bind').read_text()),{'bytes':len(payload),'sha256':digest})
   self.assertIn(digest,(out/'browser_playback.h').read_text())
   self.assertIn('#define BOOK_MENU_ACTIVE_ADDR 0x3092762',(out/'browser_playback.h').read_text())
   with mock.patch.object(sys,'argv',['binding',str(out)]), mock.patch('subprocess.run',side_effect=lambda args,check:Path(args[-1]).write_bytes(payload+b'stale')):
    with self.assertRaisesRegex(ValueError,'ELF and payload disagree'):
     exec(compile(source,'<browser binding>','exec'),{'__name__':'__main__'})

class AutoBookInitArmTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temporary=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temporary.cleanup);p=Path(cls.temporary.name)
  cls.env=dict(os.environ);cls.env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+cls.env['PATH']
  cls.build_directory=p
 def build(self):
  self.assertTrue((ROOT/'browser_sort/init.c').exists(),'cold book init has not been implemented')
  if hasattr(type(self),'code'):return
  p=self.build_directory
  (p/'browser_playback.h').write_text('#define BOOK_NAV_INIT_ADDR 0x03093000\n')
  (p/'stubs.c').write_text('unsigned valid __attribute__((section(".sort_metadata")))=0; int browser_sort_select(void *p){(void)p;return 1;} unsigned browser_book_event(unsigned message){return message;} void browser_sort_enumerate(void){}')
  for name,source in [('header',ROOT/'browser_sort/header.S'),('init',ROOT/'browser_sort/init.c'),('bridges',ROOT/'browser_sort/bridges.S'),('stubs',p/'stubs.c')]:
   subprocess.run(['arm-none-eabi-gcc','-c','-mthumb','-mcpu=cortex-m3','-Os','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-Isrc','-I'+str(p),str(source),'-o',str(p/(name+'.o'))],cwd=ROOT,env=self.env,check=True,capture_output=True)
  subprocess.run(['arm-none-eabi-ld','--no-warn-rwx-segments','-T','browser_sort/link.ld',str(p/'header.o'),str(p/'init.o'),str(p/'bridges.o'),str(p/'stubs.o'),'-o',str(p/'init.elf')],cwd=ROOT,env=self.env,check=True)
  subprocess.run(['arm-none-eabi-objcopy','-O','binary',str(p/'init.elf'),str(p/'init.bin')],cwd=ROOT,env=self.env,check=True,capture_output=True)
  symbols=subprocess.check_output(['arm-none-eabi-nm',str(p/'init.elf')],env=self.env,text=True)
  type(self).symbols={n:int(v,16) for v,t,n in (line.split() for line in symbols.splitlines())}
  type(self).code=(p/'init.bin').read_bytes()
  subprocess.run(['tools/asm2patch.sh','playback/hooks/nav_browser_loader.S',str(p/'loader.patch'),str(p)],cwd=ROOT,env=self.env,check=True,capture_output=True)
  type(self).loader=bytes.fromhex((p/'loader.patch').read_text().splitlines()[-1].split(':')[2])
 def cpu(self):
  self.build();c=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);c.mem_map(0x03000000,0x100000);c.mem_map(0x20000000,0x10000);c.mem_write(0x0307b874,self.code);return c
 def test_fixed_init_runs_resident_init_before_replacing_event_hook(self):
  c=self.cpu();self.assertEqual(self.symbols['browser_book_init'],0x0307b884)
  calls=[]
  def hook(c,a,n,u):
   if a==0x03093000:
    calls.append(a);c.mem_write(0x0307b31a,b'OLD!!!');c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
   elif a==0x20000000:c.emu_stop()
  c.hook_add(UC_HOOK_CODE,hook);c.reg_write(UC_ARM_REG_SP,0x030fe000);c.reg_write(UC_ARM_REG_LR,0x20000001);c.emu_start(0x0307b885,0x20000000,count=1000)
  self.assertEqual(calls,[0x03093000]);self.assertEqual(bytes(c.mem_read(0x0307b31a,6)),encode_t32_branch(0x0307b31a,self.symbols['browser_book_event_bridge'],False)+b'\x00\xbf')
 def test_event_bridge_preserves_native_frames_for_all_dispatch_results(self):
  for result in (0,1,2):
   with self.subTest(result=result):
    c=self.cpu();stack=0x030fe000;message=0x40000040;registers=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12)
    for i,reg in enumerate(registers):c.reg_write(reg,0x1230+i)
    c.reg_write(UC_ARM_REG_SP,stack);c.reg_write(UC_ARM_REG_LR,0x20000001);c.mem_write(stack+32,struct.pack('<I',message));calls=[]
    def hook(c,a,n,u):
     if a==self.symbols['browser_book_event']:
      calls.append(c.reg_read(UC_ARM_REG_R0));c.reg_write(UC_ARM_REG_R0,result);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
     elif a in (0x0307b320,0x0307b758):c.emu_stop()
    c.hook_add(UC_HOOK_CODE,hook);c.emu_start(self.symbols['browser_book_event_bridge']|1,0x20000000,count=1000)
    self.assertEqual(calls,[message]);self.assertEqual(c.reg_read(UC_ARM_REG_SP),stack);self.assertEqual(c.reg_read(UC_ARM_REG_PC),0x0307b758 if result else 0x0307b320)
    for i,reg in enumerate(registers):self.assertEqual(c.reg_read(reg),message if not result and reg==UC_ARM_REG_R0 else 0x1230+i)
    if result:self.assertEqual(c.reg_read(UC_ARM_REG_R4),result-1)
    else:self.assertEqual(c.reg_read(UC_ARM_REG_R10),0x0300d164)
 def test_loader_remains_24_bytes_and_calls_fixed_cold_init(self):
  self.build();self.assertEqual(len(self.loader),24);self.assertEqual(self.loader[10:14],encode_t32_branch(0x0307afaa,0x0307b884,True))

if __name__=='__main__':unittest.main()
