"""Deferred rate changes: real session/adapter code, filesystem and UI hardware mocked."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
import test_speed_adapter_arm as adapter
from test_music_filter import END, fat_entry

class LiveSpeedTests(unittest.TestCase):
    def setUp(self):
        self.a=adapter.SpeedAdapterTests();self.a.setUp();self.f=self.a.f;self.cpu=self.a.cpu
        self.pauses=0;self.removals=0;self.windows=0;self.native_pause=False
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
    def half(self,p,n):self.cpu.mem_write(p,struct.pack('<H',n))
    def hook(self,cpu,address,size,user):
        result=None
        if address==0x030816ee and not self.native_pause:
            self.pauses+=1;self.half(0x0300d81a,3);self.half(0x0300d7f0,4);result=0
        elif address==0x03059910:self.removals+=1;result=0
        elif address==0x0306b26a:self.windows+=1;result=0
        elif address in (0x0306b082,0x0306b040):result=0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def launch(self,q=4,paused=False):
        self.f.call('playback_speed_set',q);self.a.launch_book()
        self.a.put(0x03023090,100000);self.a.put(0x03023094,12000)
        self.half(0x0300d81a,3 if paused else 0);self.half(0x0300d7f0,4 if paused else 0)
        self.a.put(0x600003a0,0)
    def finish(self,paused=False):
        self.assertGreaterEqual(self.removals,1);self.assertEqual(self.windows,self.removals)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.half(0x0300d81a,0) # Native init resets pause before custom queue hook.
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
        self.assertEqual(self.f.call('playback_rate_poll'),3)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d81a,2))[0],3 if paused else 0)
        self.assertEqual(self.a.get(0x0300d1cc),12000)
    def test_presets_change_only_on_validated_relaunch_preserving_pause(self):
        for old,new in ((4,8),(8,4),(8,5),(5,6),(6,7)):
            for paused in (False,True):
                with self.subTest(old=old,new=new,paused=paused):
                    self.setUp();self.launch(old,paused)
                    self.assertEqual(self.f.call('playback_rate_request',new),2)
                    self.assertEqual(self.f.call('playback_speed_actual'),old)
                    self.assertEqual(self.f.call('playback_speed_get'),old)
                    self.assertEqual(self.pauses,int(not paused))
                    self.finish(paused)
                    self.assertEqual(self.f.call('playback_speed_actual'),new)
    def test_same_rate_selection_updates_next_launch_preference_without_restart(self):
        self.launch(4)
        self.f.call('playback_speed_set',8)
        self.assertEqual(self.f.call('playback_rate_request',4),3)
        self.assertEqual(self.f.call('playback_speed_get'),4)
        self.assertEqual(self.f.call('playback_speed_actual'),4)
        self.assertEqual((self.pauses,self.removals),(0,0))
    def test_same_rate_unsupported_and_invalid_identity_do_not_stop(self):
        self.launch(4)
        self.assertEqual(self.f.call('playback_rate_request',4),3)
        self.a.put(0x03039e94,1)
        self.assertEqual(self.f.call('playback_rate_request',8),0xffffffff)
        self.assertEqual(self.f.call('playback_speed_actual'),4)
        self.a.put(0x03039e94,0);self.f.dirs[0]=[END]
        self.assertEqual(self.f.call('playback_rate_request',8),0xffffffff)
        self.assertEqual((self.pauses,self.removals),(0,0))
        self.assertEqual(self.f.call('playback_speed_get'),4)
    def test_replaced_chapter_with_unchanged_playlist_refuses_before_pause(self):
        self.launch()
        self.f.dirs[0][1]=fat_entry(b'ONE     MP3',200)
        self.assertEqual(self.f.call('playback_rate_request',8),0xffffffff)
        self.assertEqual((self.pauses,self.removals),(0,0))
    def test_changed_chapter_during_drain_refuses_relaunch(self):
        self.launch();self.a.dma_result=4;self.a.submit(0x03023174,128)
        self.a.put(0x600003a0,1<<4)
        self.assertEqual(self.f.call('playback_rate_request',8),1)
        self.f.dirs[0][1]=fat_entry(b'ONE     MP3',200)
        self.a.put(0x600003a0,0)
        self.assertEqual(self.f.call('playback_rate_poll'),0xffffffff)
        self.assertEqual(self.removals,0)
    def test_failed_queue_restores_desired_rate(self):
        self.launch()
        self.f.call('playback_speed_set',6)
        self.assertEqual(self.f.call('playback_rate_request',8),2)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(self.f.call('playback_speed_get'),8)
        self.f.dirs[0][1]=fat_entry(b'ONE     MP3',200)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),19)
        self.assertEqual(self.f.call('playback_rate_poll'),0xffffffff)
        self.assertEqual(self.f.call('playback_speed_get'),6)
        self.assertEqual(self.f.call('playback_speed_actual'),4)
    def test_cancelled_future_selection_does_not_replace_authoritative_path(self):
        self.launch()
        self.cpu.mem_write(0x20005000,'/missing.m3u\0'.encode('utf-16le'))
        self.assertEqual(self.f.call('playback_launch_path',0x20005000,1,0,0),1)
        self.f.call('playback_launch_cancel')
        self.assertEqual(self.f.call('playback_rate_request',8),2)
        self.finish()
    def test_runtime_bypass_reports_one_and_refuses_rate_selection(self):
        self.launch(8)
        self.a.put(0x0302312c,24);self.a.capture()
        self.a.put(0x0302312c,16) # Runtime bypass remains latched until a reset.
        self.assertEqual(self.f.call('playback_speed_actual'),4)
        self.assertEqual(self.f.call('playback_speed_supported'),0)
        self.assertEqual(self.f.call('playback_rate_request',4),0xffffffff)
        self.assertEqual(self.f.call('playback_speed_get'),8)
        self.assertEqual((self.pauses,self.removals),(0,0))
    def test_changed_chapter_size_refuses_before_pause_and_after_drain(self):
        for during_drain in (False,True):
            with self.subTest(during_drain=during_drain):
                self.setUp();self.launch()
                if during_drain:
                    self.a.dma_result=4;self.a.submit(0x03023174,128)
                    self.a.put(0x600003a0,1<<4)
                    self.assertEqual(self.f.call('playback_rate_request',8),1)
                entry=bytearray(self.f.dirs[0][1]);struct.pack_into('<I',entry,28,12345)
                self.f.dirs[0][1]=bytes(entry)
                if during_drain:
                    self.a.put(0x600003a0,0)
                    result=self.f.call('playback_rate_poll')
                else:result=self.f.call('playback_rate_request',8)
                self.assertEqual(result,0xffffffff)
                self.assertEqual(self.removals,0)
                self.assertEqual(self.pauses,int(during_drain))
    def test_changed_signature_refuses_before_pause(self):
        self.launch();self.f.files[90]=b'two.mp3\none.mp3\n'
        self.assertEqual(self.f.call('playback_rate_request',8),0xffffffff)
        self.assertEqual((self.pauses,self.removals),(0,0))
    def test_raw_one_x_actual_fallback_channel_must_drain(self):
        self.launch();self.a.dma_result=4
        self.a.submit(0x03023174,128)
        self.a.put(0x600003a0,1<<4);self.a.put(0x0300bd98,0x030693cb)
        self.assertEqual(self.f.call('playback_rate_request',8),1)
        self.assertEqual(self.removals,0)
        self.assertEqual(self.f.call('playback_speed_actual'),4)
        self.a.put(0x600003a0,1<<5) # Requested channel5 still busy, actual4 idle.
        self.assertEqual(self.f.call('playback_rate_poll'),2)
        self.assertEqual(self.a.get(0x0300bd98),0)
        self.assertEqual(self.a.get(0x60000338),1<<4)
        self.a.put(0x600002e8,1<<4);self.f.call(0x0306c3c8)
        self.assertEqual(self.a.done_calls,0)
        self.finish()
    def test_foreign_callback_timeout_preserves_session_and_rate(self):
        self.launch();self.a.dma_result=4;self.a.submit(0x03023174,128)
        self.a.put(0x0300bd98,0x20000401)
        self.assertEqual(self.f.call('playback_rate_request',8),1)
        for _ in range(201):self.f.call('playback_rate_poll')
        self.assertEqual(self.f.call('playback_rate_poll'),0xffffffff)
        self.assertEqual(self.removals,0);self.assertEqual(self.a.get(0x0300bd98),0x20000401)
        self.assertEqual(self.a.get(self.f.syms['playback_active']),1)
        self.assertEqual(self.f.call('playback_speed_actual'),4)
    def test_cancel_wait_does_not_reset_dma_or_resume(self):
        self.launch();self.a.dma_result=4;self.a.submit(0x03023174,128)
        self.a.put(0x600003a0,1<<4)
        self.assertEqual(self.f.call('playback_rate_request',8),1)
        self.f.call('playback_rate_cancel')
        self.assertEqual(self.f.call('playback_rate_poll'),0xffffffff)
        self.assertEqual((self.pauses,self.removals),(1,0))
        self.assertEqual(self.a.get(0x600003a0),1<<4)
    def test_native_pause_then_restored_paused_startup_skips_dma(self):
        image=adapter.runtime.Image((adapter.runtime.ROOT/'NANOV170.IMG').read_bytes())
        m=image.modules[33]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.launch(8)
        self.a.put(0x03039714,0x03023090);self.a.put(0x03023098,48000);self.a.put(0x0302312c,16)
        self.native_pause=True
        calls=[]
        def native(cpu,address,size,user):
            if address in (0x030656b8,0x03059a74,0x03055590,0x03069c6a,0x03069876):
                calls.append(address);cpu.reg_write(UC_ARM_REG_R0,0)
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,native)
        self.assertEqual(self.f.call('playback_rate_request',5),2)
        self.assertIn(0x03059a74,calls)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d81a,2))[0],3)
        # Exercise a request originally paused, with native init clearing state.
        self.f.call('playback_begin',0x20001000);self.f.call('playback_prepare',3)
        self.half(0x0300d81a,0)
        self.f.call('playback_queue_init',0x0300d85c,1,3,1,0)
        # Above began playing, so its restoration must permit DMA.
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d81a,2))[0],0)
        self.half(0x0300d81a,3);self.half(0x0300d7f0,4)
        self.assertEqual(self.f.call('playback_rate_request',6),2)
        self.finish(True)
        self.cpu.reg_write(UC_ARM_REG_R7,0x0300d81a)
        self.cpu.reg_write(UC_ARM_REG_R6,0x03039708)
        self.cpu.emu_start(0x03081663,0x030816b8,count=100)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),0x030816b8)
        self.assertEqual(self.a.get(0x03039708+56),0xffffffff)
        self.assertEqual(self.a.dma,[])
    def test_accelerated_current_and_prepared_packets_wait_for_owned_dma(self):
        self.launch(8);self.a.blocks=[1152]*10
        _,p,n=self.a.capture();self.a.dma_result=4;self.a.submit(p,n)
        self.a.capture() # Prepared output must survive until the drain gate.
        self.a.put(0x600003a0,1<<4);self.a.put(0x0300bd98,0x03072f5d)
        self.assertEqual(self.f.call('playback_rate_request',4),1)
        self.assertEqual(self.f.call('playback_speed_actual'),8)
        self.assertEqual(self.removals,0)
        self.a.put(0x600003a0,0)
        self.assertEqual(self.f.call('playback_rate_poll'),2)
        self.assertEqual(self.a.get(0x0300bd98),0)
        self.a.put(0x600002e8,1<<4);self.f.call(0x0306c3c8)
        self.assertEqual(self.a.done_calls,0)
if __name__=='__main__':unittest.main()
