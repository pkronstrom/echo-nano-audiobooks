"""Native list removal -> music callback -> stop dispatch -> journal save.

Codec/hardware/resource operations and sector I/O remain substituted.
"""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR
import test_playback_session_arm as session
import test_book_resume_arm as resume

class LifecycleTests(unittest.TestCase):
    def test_native_browser_handoff_saves_previous_book_before_new_load(self):
        s=session.SessionTests();s.setUp();self.f=s.f;self.cpu=s.cpu
        self.writes=[];self.short_write=False
        self.cpu.hook_add(UC_HOOK_CODE,lambda *args:resume.ResumeTests.write(self,*args))
        image=session.fixture.Image((session.fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        m=image.modules[34]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.f.dirs[0].insert(-1,resume.sized(b'LIST    RSM',91,1024))
        self.f.files[91]=resume.blank()
        s.launch()
        self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
        self.cpu.mem_write(0x03023090,struct.pack('<II',7200000,1234567))
        self.cpu.mem_write(0x0300d0cc,b'\x01')
        self.cpu.mem_write(0x0300dc1c,struct.pack('<I',0x0302315c))
        self.cpu.mem_write(0x0302315c,struct.pack('<5I',0,0,0,0,0x030833f1))
        visited=[]
        stubs={0x0306b0a0,0x030656b8,0x03059a74,0x03056880,0x03054d1c,
               0x030838b8,0x0306b6bc,0x03083660,0x03081aa4,0x0305fbf2,
               0x030595b4,0x0305965e,0x0306a33c,0x03084ea0,0x03069876,
               0x0306af30,0x030718f6,0x030715a0}
        def hardware(cpu,address,size,user):
            if address in (0x03059910,0x030833f0,0x03082524,0x03082164,0x030822ac,0x030825c4):visited.append(address)
            if address in stubs:
                cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,hardware)
        s.real_callbacks=True;s.window=[]
        self.assertEqual(self.f.call(0x0307acb6),1)
        self.assertEqual(visited,[0x03059910,0x030833f0,0x03082524,0x03082164,0x030822ac,0x030825c4])
        self.assertEqual(self.writes,[(91,512)])
        self.assertEqual(s.codec_closes,1)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+2,2))[0],1)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x0300d1cc,4))[0],1234567)

if __name__=='__main__':unittest.main()
