"""Compile isolated speed bridges; validate guarded resident ABI and staging.

No firmware image is built. Payload functions and DMA hardware are substituted.
"""
from pathlib import Path
import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_XPSR, UC_ARM_REG_R12)
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from hooks import encode_t32_branch
from playback_layout import (HOOKS, RAM_START, STOCK_SHA256, SPEED_GUARD_ADDRESS,
                             SPEED_DONE_ADDRESS, SPEED_STUB_TEXT, read_patch,
                             speed_guard_space, speed_status_space)
REGS=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,
      UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
      UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
SYMS={'playback_header':RAM_START,'playback_speed_dma':0x03093000,
      'playback_speed_done':0x03093100,'playback_speed_capture_bridge':0x03093200,
      'playback_speed_status_bridge':0x03093500,'playback_speed_seek_bridge':0x03093300,'playback_speed_time_bridge':0x03093400}
STOP,SP=0x030ff000,0x030fe000

class SpeedHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'NANOV170.IMG').read_bytes()
        if hashlib.sha256(cls.source).hexdigest()!=STOCK_SHA256:
            raise AssertionError('speed hooks require pinned stock')
        cls.temp=tempfile.TemporaryDirectory(prefix='echo-speed-hook-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        out=Path(cls.temp.name)
        (out/'playback_syms.inc').write_text('\n'.join(
            f'.equ {name},0x{value:x}' for name,value in SYMS.items())+'\n')
        env=os.environ.copy()
        toolbin=ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin'
        env['PATH']=str(toolbin)+os.pathsep+env.get('PATH','')
        cls.patches={}
        for name in HOOKS:
            if not name.startswith('speed_'):continue
            result=subprocess.run(['bash','tools/asm2patch.sh',f'playback/hooks/{name}.S',
                                   str(out/f'{name}.patch'),str(out)],cwd=ROOT,env=env,
                                  capture_output=True,text=True)
            if result.returncode:raise AssertionError(result.stdout+result.stderr)
            cls.patches[name]=read_patch(out/f'{name}.patch')

        bridge=out/'status_bridge.S'
        bridge.write_text('@ patch 0 03093500\n#include "fw.inc"\n.equ playback_speed_owns,0x03093601\n'+
                          (ROOT/'playback/speed_status_bridge.S').read_text())
        result=subprocess.run(['bash','tools/asm2patch.sh',str(bridge),str(out/'status_bridge.patch'),str(out)],
                              cwd=ROOT,env=env,capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.status_bridge=read_patch(out/'status_bridge.patch')

    def setUp(self):
        self.image=Image(self.source)
        self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000,0x100000)
        for module in (0,33):
            m=self.image.modules[module]
            for kind in ('code','data'):
                if not m[kind+'_len']:continue
                off=self.image.l2f(m[kind+'_load'])
                self.cpu.mem_write(m[kind+'_exec'],bytes(self.image.d[off:off+m[kind+'_len']]))
        for mod,addr,data in self.patches.values():self.cpu.mem_write(addr,data)
        self.cpu.mem_write(self.status_bridge[1],self.status_bridge[2])

    def execute(self,address,target,magic,return_to=STOP):
        self.cpu.mem_write(RAM_START,magic)
        values=[0x11220000+i for i in range(len(REGS))]
        for reg,value in zip(REGS,values):self.cpu.reg_write(reg,value)
        stack=struct.pack('<4I',0x12345678,0x87654321,0xdeadbeef,0xcafebabe)
        self.cpu.mem_write(SP,stack)
        self.cpu.reg_write(UC_ARM_REG_SP,SP)
        self.cpu.reg_write(UC_ARM_REG_LR,STOP|1)
        seen=[];returned=[]
        def intercept(cpu,pc,size,user):
            if pc==target:
                self.assertEqual([cpu.reg_read(reg) for reg in REGS],values)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP),SP)
                self.assertEqual(bytes(cpu.mem_read(SP,16)),stack)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_LR),return_to|1)
                seen.append(pc)
                cpu.reg_write(UC_ARM_REG_R0,77)
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
            elif pc==return_to:
                returned.append(pc);cpu.emu_stop()
        hook=self.cpu.hook_add(UC_HOOK_CODE,intercept)
        self.cpu.emu_start(address|1,0,count=1000)
        self.cpu.hook_del(hook)
        self.assertEqual(seen,[target]);self.assertEqual(returned,[return_to])
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),SP)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0),77)

    def test_resident_guard_preserves_six_arguments_registers_stack_and_lr(self):
        for magic in (b'ENP2',b'CFW!',bytes(4)):
            for entry,custom,native in ((SPEED_GUARD_ADDRESS,SYMS['playback_speed_dma'],0x0306c1e4),
                                        (SPEED_DONE_ADDRESS,SYMS['playback_speed_done'],0x030693ca)):
                with self.subTest(magic=magic,entry=hex(entry)):
                    self.execute(entry,custom if magic==b'ENP2' else native,magic)

    def test_all_native_output_dma_calls_reach_guard_with_original_six_arguments(self):
        for address in (0x0306985e,0x030693fa,0x0308168c,0x03081f98,0x03082062,0x03083360):
            for magic in (b'ENP2',b'CFW!'):
                with self.subTest(address=hex(address),magic=magic):
                    self.execute(address,SYMS['playback_speed_dma'] if magic==b'ENP2' else 0x0306c1e4,
                                 magic,address+4)

    def test_overlay_capture_seek_and_time_entries_tailcall_payload_bridges(self):
        for name,symbol in (('speed_capture','playback_speed_capture_bridge'),
                            ('speed_seek','playback_speed_seek_bridge'),
                            ('speed_time','playback_speed_time_bridge')):
            with self.subTest(name=name):
                self.execute(HOOKS[name][1],SYMS[symbol],b'ENP2')

    def test_patch_sizes_and_branch_targets_match_audited_ranges(self):
        for name,(module,address,data) in self.patches.items():
            self.assertEqual((module,address,len(data)),HOOKS[name][:3])
        self.assertEqual(SPEED_DONE_ADDRESS,SPEED_GUARD_ADDRESS+8)
        for name in (name for name in HOOKS if name.startswith('speed_dma_')):
            _,address,data=self.patches[name]
            self.assertEqual(data,encode_t32_branch(address,SPEED_GUARD_ADDRESS,True))
            module=HOOKS[name][0]
            offset,_=self.image.region(module,address)
            self.assertEqual(bytes(self.image.d[offset:offset+4]),
                             encode_t32_branch(address,0x0306c1e4,True))

    def test_status_guard_and_helper_preserve_registers_flags_and_frame(self):
        for status in (0,4):
            for valid in (False,True):
                for owned in (False,True):
                    with self.subTest(status=status,valid=valid,owned=owned):
                        values=[0x11220000+i for i in range(len(REGS))]
                        values[0]=status;values[7]=0x0300d7e8
                        for reg,value in zip(REGS,values):self.cpu.reg_write(reg,value)
                        self.cpu.reg_write(UC_ARM_REG_R12,0xabcdef12)
                        flags=(0x60000000 if status==0 else 0x20000000)|0x08000000
                        self.cpu.reg_write(UC_ARM_REG_XPSR,flags|0x01000000)
                        self.cpu.reg_write(UC_ARM_REG_SP,SP)
                        self.cpu.reg_write(UC_ARM_REG_LR,STOP|1)
                        stack=bytes(range(64));self.cpu.mem_write(SP,stack)
                        self.cpu.mem_write(RAM_START,b'ENP2' if valid else b'CFW!')
                        self.cpu.mem_write(0x0300d7f4,struct.pack('<I',0x03094000))
                        destination=0x03069562 if status==0 else (0x030695e8 if valid and owned else 0x030697e2)
                        helpers=[];landed=[]
                        def intercept(cpu,pc,size,user):
                            if pc==0x03093600:
                                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP)%8,0)
                                self.assertEqual(cpu.reg_read(UC_ARM_REG_R0),0x03094000)
                                helpers.append(pc)
                                for reg in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12):cpu.reg_write(reg,123)
                                cpu.reg_write(UC_ARM_REG_XPSR,0x01000000)
                                cpu.reg_write(UC_ARM_REG_R0,int(owned))
                                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
                            elif pc==destination:
                                landed.append(pc);cpu.emu_stop()
                        hook=self.cpu.hook_add(UC_HOOK_CODE,intercept)
                        self.cpu.emu_start(0x0306955f,0,count=1000)
                        self.cpu.hook_del(hook)
                        self.assertEqual(landed,[destination])
                        self.assertEqual(len(helpers),int(status!=0 and valid))
                        self.assertEqual([self.cpu.reg_read(reg) for reg in REGS],values)
                        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),SP)
                        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_LR),STOP|1)
                        self.assertEqual(bytes(self.cpu.mem_read(SP,64)),stack)
                        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R12),0xabcdef12)
                        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_XPSR)&0xf8000000,flags)

    def test_status_diagnostic_reclaim_validates_original_bytes(self):
        before=bytes(self.image.d)
        speed_status_space(self.image)
        expected=Image(before)
        for address in (0x030695b6,0x030695ce):
            expected.patch(0,address,bytes.fromhex('00bf00bf'))
        self.assertEqual(self.image.d,expected.d)
        for address in (0x030696d4,0x030695b4,0x030695cc,0x0306955e,0x030695b6,0x030695ce):
            changed=Image(before);off,_=changed.region(0,address);changed.d[off]^=1
            with self.subTest(address=hex(address)),self.assertRaises(ValueError):
                speed_status_space(changed)

    def test_reclaim_disables_only_printf_and_rejects_changed_inputs(self):
        before=bytes(self.image.d)
        speed_guard_space(self.image)
        expected=Image(before)
        expected.patch(0,0x03052410,bytes.fromhex('00bf00bf'))
        self.assertEqual(self.image.d,expected.d)
        for address in (SPEED_GUARD_ADDRESS,0x03052804,0x0305240e,0x03052410):
            changed=Image(before);off,_=changed.region(0,address);changed.d[off]^=1
            with self.subTest(address=hex(address)),self.assertRaisesRegex(ValueError,'diagnostic changed'):
                speed_guard_space(changed)

    def test_diagnostic_has_only_the_audited_absolute_pointer_reference(self):
        hits=[];needle=struct.pack('<I',SPEED_GUARD_ADDRESS)
        for module in self.image.modules:
            for kind in ('code','data'):
                length=module[kind+'_len']
                if not length:continue
                off=self.image.l2f(module[kind+'_load'])
                data=bytes(self.image.d[off:off+length]);position=0
                while True:
                    position=data.find(needle,position)
                    if position<0:break
                    hits.append((module['index'],kind,module[kind+'_exec']+position))
                    position+=1
        self.assertEqual(hits,[(0,'code',0x03052804)])
        off,_=self.image.region(0,SPEED_GUARD_ADDRESS)
        self.assertEqual(bytes(self.image.d[off:off+len(SPEED_STUB_TEXT)]),SPEED_STUB_TEXT)
        self.assertGreaterEqual(len(SPEED_STUB_TEXT),64)

if __name__=='__main__':unittest.main()
