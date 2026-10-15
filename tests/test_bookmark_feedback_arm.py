"""Feedback uses native window linking/destruction; LCD hardware is substituted."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11
import test_playback_runtime_arm as runtime
from playback_layout import RAM_START
import test_bookmark_session_arm as session

class BookmarkFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.f=runtime.PlaybackRuntimeTests(); self.f.setUp(); self.cpu=self.f.cpu
        self.assertIn('feedback_poll',self.f.syms,'compiled feedback UI is missing')
        image=runtime.Image((runtime.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        for i in (0,27):
            m=image.modules[i]
            for kind in ('code','data'):
                off=image.l2f(m[kind+'_load'])
                self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.events=[];self.text=[];self.transfers=[];self.init_modes()
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
        self.cpu.mem_write(self.f.syms['playback_active'],struct.pack('<I',1))

    def hook(self,cpu,address,size,user):
        result=None
        if address==0x0306b040:self.events.append(cpu.reg_read(UC_ARM_REG_R0));result=0
        elif address==0x03052b08:
            p=cpu.reg_read(UC_ARM_REG_R1);units=[]
            for i in range(40):
                v=struct.unpack('<H',cpu.mem_read(p+i*2,2))[0]
                if not v:break
                units.append(v)
            self.text.append(''.join(map(chr,units)));result=0
            self.assertEqual(self.raw_mode(),2,'text ink must be set on the cleared framebuffer')
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R2),2)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R3),1)
            self.assertEqual(struct.unpack('<I',cpu.mem_read(cpu.reg_read(UC_ARM_REG_SP),4))[0],0)
        elif address==0x030643d8:
            self.transfers.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)));result=0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))

    def init_modes(self):
        # Use the real native setters: color accepts logical but returns raw.
        self.cpu.mem_write(0x0300d6e0,struct.pack('<H',0))
        self.cpu.mem_write(0x0300d6e4,struct.pack('<H',2))
    def raw_mode(self):return struct.unpack('<H',self.cpu.mem_read(0x0300d6e0,2))[0]
    def test_paint_restores_each_raw_mode(self):
        self.publish(1);self.f.call('feedback_poll',0)
        for raw in (0,1,2):
            with self.subTest(raw=raw):
                self.cpu.mem_write(0x0300d6e0,struct.pack('<H',raw))
                self.callback(16)
                self.assertEqual(self.raw_mode(),raw)

    def child(self):return struct.unpack('<I',self.cpu.mem_read(0x0300e6bc,4))[0]
    def callback(self,offset):return self.f.call(struct.unpack('<I',self.cpu.mem_read(self.child()+offset,4))[0])
    def publish(self,success):
        token=self.f.call('feedback_token');self.f.call('feedback_result',token,success)
    def test_saved_result_renders_and_timeout_restores_player(self):
        self.publish(1);self.f.call('feedback_poll',0);self.assertNotEqual(self.child(),0)
        self.callback(16);self.assertEqual(self.text,['Bookmark saved'])
        self.assertEqual(self.transfers,[(0,0,128,31)])
        self.assertEqual(self.raw_mode(),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d6e4,2))[0],2)
        self.cpu.mem_write(0x0300d144,struct.pack('<I',151));self.callback(8)
        self.assertEqual(self.child(),0);self.assertIn(57,self.events);self.assertNotIn(227,self.events)
    def test_failure_busy_child_and_transition(self):
        self.publish(0);self.cpu.mem_write(0x0300e6bc,struct.pack('<I',0x20003000))
        self.f.call('feedback_poll',0);self.assertEqual(self.child(),0x20003000)
        self.cpu.mem_write(0x0300e6bc,bytes(4));self.f.call('feedback_poll',1);self.assertEqual(self.child(),0)
        self.f.call('feedback_poll',0);self.callback(16);self.assertEqual(self.text,['Bookmark failed'])
    def test_cancellation_discards_late_result_and_closes_existing_popup(self):
        token=self.f.call('feedback_token');self.f.call('feedback_cancel');self.f.call('feedback_result',token,1)
        self.f.call('feedback_poll',0);self.assertEqual(self.child(),0)
        self.publish(1);self.f.call('feedback_poll',0);self.assertNotEqual(self.child(),0)
        self.f.call('feedback_cancel');self.callback(8);self.assertEqual(self.child(),0)
    def test_native_parent_destroy_unlinks_child_before_refresh(self):
        self.publish(1);self.f.call('feedback_poll',0);child=self.child()
        # Substitute only parent uninit: child uninit and native tree teardown run.
        self.cpu.mem_write(0x20004000,bytes.fromhex('7047'))
        self.cpu.mem_write(0x0300e6bc+24,struct.pack('<I',0x20004001))
        self.f.call(0x03059840,0x0300e6bc)
        self.assertEqual(self.child(),0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(child+4,4))[0],0)
        self.cpu.mem_write(RAM_START,b'CFW!')
        self.epilogue(0)
    def test_dispatcher_uninitializes_child_before_next_overlay_loader(self):
        self.publish(1);self.f.call('feedback_poll',0);child=self.child()
        self.cpu.mem_write(0x20004000,bytes.fromhex('7047'))
        self.cpu.mem_write(0x0300e6bc+24,struct.pack('<I',0x20004001))
        self.cpu.mem_write(0x20004100,struct.pack('<I',0x0300e6bc))
        seen=[]
        def stop_at_loader(cpu,address,size,user):
            if address==0x0306b6bc:
                self.assertEqual(self.child(),0)
                self.assertEqual(struct.unpack('<I',cpu.mem_read(child+4,4))[0],0)
                seen.append(address)
                # Model refresh replacing the payload only after native unlink.
                cpu.mem_write(RAM_START,b'CFW!');cpu.emu_stop()
        hook=self.cpu.hook_add(UC_HOOK_CODE,stop_at_loader)
        self.cpu.reg_write(UC_ARM_REG_SP,0x20008000)
        self.cpu.reg_write(UC_ARM_REG_R5,0x20004100)
        self.cpu.reg_write(UC_ARM_REG_R7,0)
        self.cpu.emu_start(0x0306b179,0x20000000,count=100000)
        self.cpu.hook_del(hook)
        self.assertEqual(seen,[0x0306b6bc]);self.epilogue(0)
    def epilogue(self,transition):
        regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
        saved=[0x44550000+i for i in range(8)]
        sp=0x20008000
        self.cpu.mem_write(sp,bytes(36)+struct.pack('<9I',*saved,0x20000001))
        self.cpu.reg_write(UC_ARM_REG_SP,sp);self.cpu.reg_write(UC_ARM_REG_R4,transition)
        self.cpu.emu_start(0x0307a861,0x20000000,count=100000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0),transition)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),sp+72)
        self.assertEqual([self.cpu.reg_read(r) for r in regs],saved)
    def test_guarded_epilogue_preserves_native_contract(self):
        self.epilogue(1);self.publish(1);self.epilogue(0);self.assertNotEqual(self.child(),0)

class BookmarkFeedbackSessionTests(session.BookmarkSessionTests):
    def setUp(self):
        super().setUp()
        self.ui=BookmarkFeedbackTests()
        self.ui.f=self.f;self.ui.cpu=self.cpu
        self.ui.events=[];self.ui.text=[];self.ui.transfers=[]
        self.ui.init_modes()
        self.cpu.hook_add(UC_HOOK_CODE,self.ui.hook)
        image=runtime.Image((runtime.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        m=image.modules[27]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
    def test_success_is_published_only_after_completed_write(self):
        self.assertEqual(self.f.call('playback_request_bookmark'),0)
        self.f.call('feedback_poll',0);self.assertEqual(self.ui.child(),0)
        self.f.call('playback_bookmark_poll',439)
        self.assertEqual(len(self.writes),1)
        self.f.call('feedback_poll',0);self.ui.callback(16)
        self.assertEqual(self.ui.text,['Bookmark saved'])
    def test_short_write_reports_failure(self):
        self.short_write=True
        self.f.call('playback_request_bookmark');self.f.call('playback_bookmark_poll',439)
        self.f.call('feedback_poll',0);self.ui.callback(16)
        self.assertEqual(self.ui.text,['Bookmark failed'])
    def test_invalid_decoder_request_reports_failure_without_write(self):
        self.cpu.mem_write(0x0300d85c+0x14+26,struct.pack('<H',999))
        self.assertEqual(self.f.call('playback_request_bookmark'),0xffffffff)
        self.f.call('feedback_poll',0);self.ui.callback(16)
        self.assertEqual(self.ui.text,['Bookmark failed']);self.assertEqual(self.writes,[])
    def test_session_change_discards_unshown_feedback(self):
        self.f.call('playback_request_bookmark');self.f.call('playback_bookmark_poll',439)
        self.f.call('playback_begin',0x20001000)
        self.cpu.mem_write(self.f.syms['playback_active'],struct.pack('<I',1))
        self.f.call('feedback_poll',0);self.assertEqual(self.ui.child(),0)
