"""Run the stock byte reader, mocking only locks and its sector I/O boundary."""
from pathlib import Path
import struct
import sys
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from playback_layout import RAM_START,FLASH_START,LOADER_ADDRESS

class PayloadFlashReadTests(unittest.TestCase):
    def setup_cpu(self,data,second_slot=False,execute_init=False):
        self.image=Image(data);self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000,0x100000)
        m=self.image.modules[0]
        for kind in ('code','data'):
            off=self.image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(self.image.d[off:off+m[kind+'_len']]))
        self.cpu.mem_write(0x0300d454,struct.pack('<I',512))
        self.cpu.mem_write(0x0300e238,bytes([int(second_slot)]))
        self.cpu.mem_write(0x0300e224,struct.pack('<I',26624))
        self.flash=data+bytes(0xd00000-len(data))+data
        self.execute_init=execute_init
        self.reads=[];self.init_seen=False;self.returned=False
        self.entry=struct.unpack_from('<I',data,FLASH_START+4)[0]&~1
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
    def hook(self,cpu,addr,size,user):
        result=None
        if addr in (0x0306a40e,0x0306a466):result=0
        elif addr==0x0306b716:
            dev,lba,count,dst=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
            self.assertEqual(dev,0x30000)
            b=self.flash[lba*512:(lba+count)*512];self.assertEqual(len(b),count*512)
            cpu.mem_write(dst,b);self.reads.append((lba,count));result=0
        elif addr==self.entry:
            self.init_seen=True
            if not self.execute_init:result=0x32504e45 # inspect before BSS init
        elif addr==0x03010000:
            self.returned=True;cpu.emu_stop()
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def load(self):
        self.cpu.reg_write(UC_ARM_REG_SP,0x03003f00)
        self.cpu.reg_write(UC_ARM_REG_LR,0x03010001)
        self.cpu.emu_start(LOADER_ADDRESS|1,0,count=200000)
        self.assertTrue(self.returned);self.assertTrue(self.init_seen)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0),0)
    def test_loader_copies_entire_payload_with_real_stock_byte_reader(self):
        data=(ROOT/'out/audiobook/NANOV170.IMG').read_bytes()
        payload=(ROOT/'out/playback/playback.bin').read_bytes()
        for second in (False,True):
            with self.subTest(second_slot=second):
                self.setup_cpu(data,second);self.load()
                actual=bytes(self.cpu.mem_read(RAM_START,len(payload)))
                first=next((i for i,(a,b) in enumerate(zip(actual,payload)) if a!=b),None)
                self.assertIsNone(first, f'first corrupt byte={first}; sector requests={self.reads}')
    def test_refresh_overlay_and_stub_then_real_reader_reload(self):
        data=(ROOT/'out/audiobook/NANOV170.IMG').read_bytes()
        symbols={n:int(v,16) for v,t,n in (l.split() for l in
            (ROOT/'out/gen/cfw.nm').read_text().splitlines())}
        for second in (False,True):
            with self.subTest(second_slot=second):
                self.setup_cpu(data,second,execute_init=True);self.load()
                start,end=struct.unpack_from('<II',data,FLASH_START+8)
                self.cpu.mem_write(start,b'LIVE')
                marker=b'NanoCRebootFlag\0\0'
                self.cpu.mem_write(0x0309fff0,marker)
                module=self.image.modules[40]
                off=self.image.l2f(module['code_load'])
                self.cpu.mem_write(module['code_exec'],bytes(self.image.d[off:off+module['code_len']]))
                self.assertNotEqual(bytes(self.cpu.mem_read(RAM_START,4)),b'ENP2')
                # Execute the actual refresh-copy/clear stub, not a simulated
                # marker write. Then reload through the actual resident reader.
                self.returned=False
                self.cpu.reg_write(UC_ARM_REG_SP,0x03003f00)
                self.cpu.reg_write(UC_ARM_REG_LR,0x03010001)
                self.cpu.emu_start(symbols['cfw_stub']|1,0,count=200000)
                self.assertTrue(self.returned)
                reads=len(self.reads);self.returned=False;self.init_seen=False
                self.load()
                self.assertGreater(len(self.reads),reads)
                self.assertEqual(bytes(self.cpu.mem_read(start,end-start)),bytes(end-start))
                self.assertEqual(bytes(self.cpu.mem_read(0x0309fff0,len(marker))),marker)

    def test_real_payload_init_clears_bss_and_preserves_reboot_marker(self):
        data=(ROOT/'out/audiobook/NANOV170.IMG').read_bytes()
        for second in (False,True):
            with self.subTest(second_slot=second):
                self.setup_cpu(data,second,execute_init=True)
                start,end=struct.unpack_from('<II',data,FLASH_START+8)
                self.cpu.mem_write(start,b'\xa5'*(end-start))
                marker=b'NanoCRebootFlag\0\0'
                self.cpu.mem_write(0x0309fff0,marker)
                self.load()
                self.assertEqual(bytes(self.cpu.mem_read(start,end-start)),bytes(end-start))
                self.assertEqual(bytes(self.cpu.mem_read(0x0309fff0,len(marker))),marker)

if __name__=='__main__':unittest.main()
