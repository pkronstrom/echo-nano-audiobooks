"""Execute native module22 draw paths with isolated module-local layout patches.

Graphics are captured at their native API boundary; this is coordinate/ABI
verification, not a device screenshot or framebuffer rendering test.
"""
from pathlib import Path
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from rknano_fw import Image
ROOT=Path(__file__).resolve().parents[1]
STATE=0x0300e8a8
EXPECTED={
    'library_row_text':(0x03079c22,'4ff023084ff07109'),
    'library_row_icon':(0x03079c42,'d8f7c7fa'),
    'library_row_full_x':(0x03079c80,'1f21'),
    'library_row_full':(0x03079c84,'d8f7a6fa'),
    'library_row_update_x':(0x03079d5a,'4ff01f01'),
    'library_row_update':(0x03079d66,'d8f735fa'),
    'library_row_background':(0x0300e788,'00'*32),
}
class LibraryLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='echo-library-layout-')
        cls.addClassCleanup(cls.temporary.cleanup)
        env=dict(os.environ)
        env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
        cls.patches={}
        for name in (*EXPECTED,'library_menu_42_mod22_restore'):
            source=ROOT/('patches' if name.startswith('library_menu') else 'playback/hooks')/(name+'.S')
            output=Path(cls.temporary.name)/(name+'.patch')
            subprocess.run([str(ROOT/'tools/asm2patch.sh'),str(source),str(output)],cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
            line=next(line for line in output.read_text().splitlines() if line and not line.startswith('#'))
            module,address,data=line.split(':')
            assert module=='22'
            cls.patches[name]=(int(address,16),bytes.fromhex(data))
    def test_combined_image_contains_all_library_hooks(self):
        image=Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        for name in EXPECTED:
            address,data=self.patches[name]
            offset,_=image.region(22,address)
            with self.subTest(hook=name):
                self.assertEqual(bytes(image.d[offset:offset+len(data)]),data)

    def setUp(self):
        self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000,0x100000)
        image=Image((ROOT/'NANOV170.IMG').read_bytes());m=image.modules[22]
        for kind in ('code','data'):
            offset=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[offset:offset+m[kind+'_len']]))
        for name,(address,original) in EXPECTED.items():
            self.assertEqual(bytes(self.cpu.mem_read(address,len(bytes.fromhex(original)))),bytes.fromhex(original))
        restore_address,restore=self.patches['library_menu_42_mod22_restore']
        self.assertLessEqual(restore_address+len(restore),0x0300e788)
        for address,data in self.patches.values():self.cpu.mem_write(address,data)
        self.assertLessEqual(self.patches['library_row_background'][0]+len(self.patches['library_row_background'][1]),STATE)
        self.draws=[];self.texts=[];self.full=False;self.update=False
        self.cpu.mem_write(STATE,bytes([10,0,1,0,2,1]))
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
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
            result=int((event==368 and self.full) or (event==369 and self.update) or event==399)
        elif address==0x03067e4e:
            resource=cpu.reg_read(UC_ARM_REG_R0);p=cpu.reg_read(UC_ARM_REG_R1)
            cpu.mem_write(p,struct.pack('<8H',96,4 if resource==9 else 32,0,0,0,0,0,0));result=0
        elif address in (0x03051540,0x03051524,0x03067904,0x030678e0,0x0306b0a0,
                         0x0306b040,0x030579a8,0x03067860,0x030599b8):result=0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def draw(self,full=False,update=False):
        self.full=full;self.update=update
        self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000)
        self.cpu.emu_start(0x03079b5b,0x03079ec6,count=10000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),0x03079ec6)
    def test_full_draw_has_no_side_icon_and_wide_text_rows(self):
        self.draw(full=True)
        self.assertEqual(self.texts,[(3,2,123,13),(3,18,123,29)])
        self.assertNotIn(126,[draw[0] for draw in self.draws])
        self.assertEqual([d for d in self.draws if d[0]==17],[(17,0,16),(17,32,16)])
        self.assertEqual([d for d in self.draws if d[0] in (8,9)],[(8,124,0),(9,124,0)])
    def test_update_redraws_old_and_new_rows_and_keeps_scrollbar(self):
        self.draw(update=True)
        self.assertEqual(self.texts,[(3,2,123,13),(3,18,123,29)])
        self.assertEqual([d for d in self.draws if d[0] in (17,127)],
                         [(127,0,0),(127,32,0),(17,0,16),(17,32,16)])
        self.assertEqual([d for d in self.draws if d[0] in (8,9)],[(8,124,0),(9,124,0)])
    def test_native_helper_preserves_stack_and_menu_state_without_payload(self):
        before=bytes(self.cpu.mem_read(STATE,6))
        self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000);self.cpu.reg_write(UC_ARM_REG_LR,0x030ff001)
        for r,v in ((UC_ARM_REG_R0,127),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,16)):
            self.cpu.reg_write(r,v)
        self.cpu.emu_start(0x0300e789,0x030ff000,count=1000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),0x030fe000)
        self.assertEqual(self.draws,[(127,0,16),(127,32,16)])
        self.assertEqual(bytes(self.cpu.mem_read(STATE,6)),before)
        # No playback overlay is loaded anywhere in this fixture.
        self.assertEqual(bytes(self.cpu.mem_read(0x03092400,4)),bytes(4))
if __name__=='__main__':unittest.main()
