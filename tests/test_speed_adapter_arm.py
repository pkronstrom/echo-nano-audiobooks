"""Execute speed adapter ARM with a bounded synthetic native MP3 source/DMA."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_PRIMASK, UC_ARM_REG_IPSR, UC_ARM_REG_SP
import test_playback_runtime_arm as runtime
from test_music_filter import fat_entry, END

PACKET_FRAMES = 256
PACKET_BYTES = PACKET_FRAMES * 8

class SpeedAdapterTests(unittest.TestCase):
    def setUp(self):
        self.f=runtime.PlaybackRuntimeTests();self.f.setUp();self.cpu=self.f.cpu
        self.cpu.mem_map(0xe000e000,4096)
        self.cpu.mem_map(0x60000000,4096)
        self.cpu.mem_write(0x600003a0,struct.pack("<I",0xff))
        self.scripted=[];self.core_rates=[];self.done_calls=0;self.custom_completions=0;self.native_critical=False;self.critical_depths=[];self.dma_result=5;self.dsp_fault=False;self.blocks=[1152,1152,576];self.delivered=0;self.dma=[];self.commands=[]
        self.put(0x03035178,0x20000301)
        self.put(0x03039e94,0)
        self.put(0x03039e44,1)
        self.put(0x03039714,0x03023090)
        self.put(0x03023098,48000);self.put(0x0302312c,16)
        self.put(self.f.syms['playback_active'],1)
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
        self.f.call('playback_speed_set',8)
        self.f.call('playback_speed_launch')
    def put(self,p,n):self.cpu.mem_write(p,struct.pack('<I',n))
    def get(self,p):return struct.unpack('<I',self.cpu.mem_read(p,4))[0]
    def hook(self,cpu,address,size,user):
        result=None
        if address==self.f.syms['speed_init']:
            from unicorn.arm_const import UC_ARM_REG_R3
            self.core_rates.append(cpu.reg_read(UC_ARM_REG_R3))
        if address==self.f.syms['playback_speed_done']:self.done_calls+=1
        if address==0x0306c3e2:self.put(0x600002e8,0) # MMIO acknowledgment clears pending bits.
        if address==0x20000300:
            command=cpu.reg_read(UC_ARM_REG_R0)
            self.commands.append(command)
            if command in (7,14):
                if command==7:self.put(cpu.reg_read(UC_ARM_REG_R1),999999)
                cpu.reg_write(UC_ARM_REG_R0,1);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
            self.assertEqual(command,10)
            if not self.blocks:result=0
            else:
                n=self.blocks.pop(0)
                if n==0:result=2
                else:
                    p=(0x03023174,0x0302c174)[self.delivered%2]
                    self.cpu.mem_write(p,struct.pack('<hh',1234,-1234)*n)
                    self.put(cpu.reg_read(UC_ARM_REG_R1),p)
                    self.put(cpu.reg_read(UC_ARM_REG_R2),n)
                    self.delivered+=1;result=1
        elif address==self.f.syms['speed_process'] and self.scripted:
            consumed,produced,end,done,value=self.scripted.pop(0)
            sp=cpu.reg_read(UC_ARM_REG_SP)
            output,capacity,result_ptr=struct.unpack('<III',cpu.mem_read(sp,12))
            self.assertLessEqual(produced,capacity)
            self.assertLessEqual(consumed,cpu.reg_read(UC_ARM_REG_R2))
            cpu.mem_write(output,struct.pack('<hh',value,-value)*produced)
            cpu.mem_write(result_ptr,struct.pack('<III4xQQ',consumed,produced,done,0,end))
            result=0
        elif address==self.f.syms['speed_process'] and self.dsp_fault:result=-1
        elif address==0x0306c1e4:
            self.dma.append(cpu.reg_read(UC_ARM_REG_R1));result=self.dma_result
            if self.native_critical:
                # Execute the actual stock critical enter/exit instructions.
                self.critical_depths.append(self.cpu.mem_read(0x0300d83e,1)[0])
                thunk=struct.pack('<8H2I',0xb510,0x4b03,0x4798,0x4b03,
                                  0x4798,0x2005,0xbd10,0xbf00,0x0306a37b,0x0306a361)
                self.cpu.mem_write(0x20000500,thunk)
                cpu.reg_write(UC_ARM_REG_PC,0x20000501)
                return
        elif address==0x20000400:self.custom_completions+=1;result=0
        elif address==0x030693ca:result=0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def capture(self,caller=0x0306957f):
        self.put(0x03039e20,1000+self.delivered*24)
        self.put(0x03039e40,self.blocks[0] if self.blocks else 0)
        result=self.f.call('playback_speed_capture',0x20003000,0x20003004,caller)
        return result,self.get(0x20003000),self.get(0x20003004)
    def submit(self,p,n,callback=0x030693cb):
        self.put(0x2000f004,callback)
        return self.f.call('playback_speed_dma',5,p,0x40030024,n*2,0x03005b2c)
    def launch_book(self):
        self.f.dirs={0:[fat_entry(b'LIST    M3U',90),fat_entry(b'ONE     MP3',100),
                       fat_entry(b'TWO     MP3',101),END]}
        self.f.files={90:b'one.mp3\ntwo.mp3\n'}
        self.put(0x03005f6c,0x0300e73c)
        self.cpu.mem_write(0x0300e73c+8,struct.pack('<II',0,0))
        self.cpu.mem_write(0x0300e73c+0x4e,b'\x06')
        self.cpu.mem_write(0x0300e73c+0x70,'list.m3u'.encode('utf-16le')+b'\0\0')
        self.cpu.mem_write(0x0300ec1c+8,struct.pack('<H',3))
        self.cpu.mem_write(0x0300d85c+0xf2,struct.pack('<H',99))
        self.assertEqual(self.f.call('playback_browser_select',0x20004000),0x0300e73d)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)

    def test_launch_rate_survives_seek_resume_reentry_and_chapter_advance(self):
        for launched,desired in ((4,8),(8,4),(8,5)):
            for action in ('seek','resume','reentry','chapter'):
                with self.subTest(launched=launched,desired=desired,action=action):
                    self.setUp();self.blocks=[1152]*20
                    self.f.call('playback_speed_set',launched);self.launch_book()
                    status,p,n=self.capture();self.assertEqual(status,1)
                    if p not in (0x03023174,0x0302c174):
                        self.submit(p,n);self.f.call('playback_speed_done')
                    self.f.call('playback_speed_set',desired)
                    if action=='seek':self.f.call('playback_speed_seek',12000,0)
                    elif action=='resume':self.capture(0x0308332b)
                    elif action=='reentry':
                        self.f.call('playback_begin',0)
                        self.assertEqual(self.f.call('playback_prepare',3),0)
                        self.capture(0x0308332b)
                    else:
                        self.assertEqual(self.f.call('playback_advance',0x0300d85c,1),0)
                        self.capture(0x0308332b)
                    status,p,n=self.capture();self.assertEqual(status,1)
                    self.assertEqual(p in (0x03023174,0x0302c174),launched==4)
                    if launched!=4:self.assertEqual(self.core_rates[-1],launched)
                    self.assertEqual(self.f.call('playback_speed_get'),desired)
                    # A genuinely selected book adopts the new preference.
                    self.launch_book()
                    status,p,n=self.capture();self.assertEqual(status,1)
                    self.assertEqual(p in (0x03023174,0x0302c174),desired==4)
                    if desired!=4:self.assertEqual(self.core_rates[-1],desired)

    def test_native_dma_critical_exit_preserves_irq_lock_and_existing_depth(self):
        self.native_critical=True
        for nesting in (0,3):
            for mask in (0,1):
                with self.subTest(nesting=nesting,primask=mask):
                    _,a,na=self.capture()
                    self.cpu.mem_write(0x0300d83e,bytes([nesting]))
                    self.cpu.reg_write(UC_ARM_REG_PRIMASK,mask)
                    self.assertEqual(self.submit(a,na),5)
                    self.assertEqual(self.critical_depths[-1],nesting+1)
                    self.assertEqual(self.cpu.mem_read(0x0300d83e,1),bytes([nesting]))
                    self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK),mask)
                    self.cpu.reg_write(UC_ARM_REG_PRIMASK,0)
                    self.f.call('playback_speed_done')
                    self.cpu.mem_write(0x0300d83e,b'\x00')

    def test_rejected_raw_preserves_actual_current_callback(self):
        _,a,na=self.capture();self.submit(a,na,0x20000401)
        self.assertEqual(self.submit(0x03023174,128),0xffffffff)
        self.f.call('playback_speed_done')
        self.assertEqual(self.custom_completions,1)
        self.assertEqual(self.capture()[0],0)

    def test_native_depth_overflow_fails_without_submission_or_busy_owner(self):
        _,a,na=self.capture()
        self.cpu.mem_write(0x0300d83e,b'\xfe')
        self.assertEqual(self.submit(a,na),0xffffffff)
        self.assertEqual(self.dma,[])
        self.assertEqual(self.cpu.mem_read(0x0300d83e,1),b'\xfe')
        self.assertEqual(self.capture()[0],0)

    def test_completed_slot_resubmission_retains_storage_and_clock(self):
        _,a,na=self.capture();self.submit(a,na);self.f.call('playback_speed_done')
        self.f.call('playback_speed_position',0x20003008);position=self.get(0x20003008)
        self.assertEqual(self.submit(a,na),5)
        _,b,nb=self.capture();self.assertNotEqual(a,b)
        before=bytes(self.cpu.mem_read(a,PACKET_BYTES))
        self.assertEqual(self.capture()[0],2)
        self.assertEqual(bytes(self.cpu.mem_read(a,PACKET_BYTES)),before)
        self.f.call('playback_speed_done')
        self.f.call('playback_speed_position',0x20003008)
        self.assertEqual(self.get(0x20003008),position)

    def test_zero_completed_count_anchors_using_delivered_frames(self):
        self.put(0x03039e20,1000);self.put(0x03039e40,0)
        self.assertEqual(self.f.call('playback_speed_capture',0x20003000,0x20003004,0x0306957f),1)
        self.f.call('playback_speed_position',0x20003008)
        self.assertEqual(self.get(0x20003008),976)

    def test_startup_retires_only_idle_owned_or_empty_callback_channel(self):
        for channel,callback,active,ipsr,retired in ((5,0x03072f5d,False,0,True),
                (4,0x03072f5d,False,0,True),(5,0,False,0,True),
                (5,0x20000401,False,0,False),(5,0x03072f5d,True,0,False),
                (5,0x03072f5d,False,7,False)):
            with self.subTest(channel=channel,callback=callback,active=active):
                self.setUp()
                _,a,na=self.capture();self.dma_result=channel;self.submit(a,na)
                self.put(0x0300bd88+channel*4,callback)
                # Leave channel5 active when fallback channel4 is idle.
                self.put(0x600003a0,(1<<channel) if active else (0x20 if channel==4 else 0))
                self.put(0x0300d7f8,0)
                self.cpu.reg_write(UC_ARM_REG_IPSR,ipsr)
                self.blocks=[0,1152]
                self.assertEqual(self.capture(0x0308332b)[0],2)
                self.assertEqual(self.get(0x0300d7f8),1)
                self.cpu.reg_write(UC_ARM_REG_IPSR,0)
                self.assertEqual(self.get(0x0300bd88+channel*4),0 if retired else callback)
                self.assertEqual(self.get(0x60000338),(1<<channel) if retired and callback else 0)
                # A retired transfer must not keep this slot unavailable.
                _,b,nb=self.capture()
                if retired:
                    self.put(0x600002e8,1<<channel)
                    self.f.call(0x0306c3c8) # Pending IRQ sees cleared callback table.
                    self.assertEqual(self.done_calls,0)
                    self.assertEqual(b,a)
                else:
                    self.assertNotEqual(b,a)

    def test_raw_rejection_preserves_current_dsp_owner(self):
        _,a,na=self.capture();self.submit(a,na)
        self.assertEqual(self.submit(0x03023174,128),0xffffffff)
        self.assertEqual(self.dma,[a])
        self.f.call('playback_speed_done')
        self.assertEqual(self.f.call('playback_speed_position',0x20003008),1)
        self.assertGreater(self.get(0x20003008),976)

    def test_failed_raw_submit_releases_capture(self):
        self.dma_result=-1
        self.assertEqual(self.submit(0x03023174,128),0xffffffff)
        self.assertEqual(self.capture()[0],0)

    def test_rejected_prepared_slot_does_not_stay_busy(self):
        _,a,na=self.capture();self.submit(a,na)
        _,b,nb=self.capture()
        self.assertEqual(self.submit(b,nb),0xffffffff)
        self.f.call('playback_speed_done')
        self.assertEqual(self.capture()[0],0)

    def test_fault_waits_for_current_dma_before_eof(self):
        _,a,na=self.capture();self.submit(a,na)
        self.dsp_fault=True
        before=bytes(self.cpu.mem_read(a,PACKET_BYTES))
        self.assertEqual(self.capture()[0],2)
        self.assertEqual(bytes(self.cpu.mem_read(a,PACKET_BYTES)),before)
        self.f.call('playback_speed_done')
        self.assertEqual(self.capture()[0],0)

    def test_music_seek_does_not_add_pendsv(self):
        self.put(self.f.syms['playback_active'],0)
        self.put(0xe000ed04,0)
        self.f.call('playback_speed_seek',23456,1)
        self.assertEqual(self.get(0xe000ed04),0)

    def test_bounded_output_and_delayed_eof(self):
        total=0;packets=0
        for _ in range(100):
            status,p,n=self.capture()
            if status==0:break
            if status==2:continue
            self.assertLessEqual(n,PACKET_FRAMES);self.assertGreater(n,0)
            self.assertNotIn(p,(0x03023174,0x0302c174))
            self.assertEqual(bytes(self.cpu.mem_read(p+n*4,PACKET_BYTES-n*4)),bytes(PACKET_BYTES-n*4))
            total+=n;packets+=1
            self.assertEqual(self.submit(p,n),5)
            self.f.call('playback_speed_done')
        else:self.fail('EOF did not drain')
        self.assertGreater(packets,3);self.assertLess(total,2880);self.assertGreater(total,1200)
    def test_one_times_and_music_are_native(self):
        for music in (False,True):
            self.f.call('playback_speed_reset');self.f.call('playback_speed_set',8 if music else 4);self.f.call('playback_speed_launch')
            self.put(self.f.syms['playback_active'],0 if music else 1)
            status,p,n=self.capture()
            self.assertEqual(status,1);self.assertIn(p,(0x03023174,0x0302c174));self.assertEqual(n,1152)
    def test_source_clock_advances_only_at_dma_completion(self):
        status,p,n=self.capture();self.assertEqual(status,1)
        self.assertEqual(self.f.call('playback_speed_position',0x20003008),1)
        start=self.get(0x20003008)
        self.submit(p,n)
        self.f.call('playback_speed_position',0x20003008);self.assertEqual(self.get(0x20003008),start)
        self.f.call('playback_speed_done')
        self.f.call('playback_speed_position',0x20003008);self.assertGreater(self.get(0x20003008),start)
    def test_startup_capture_resets_and_preserves_native_contract(self):
        self.capture()
        expected=self.blocks[0]
        status,p,n=self.capture(0x0308332b)
        self.assertEqual(status,1);self.assertIn(p,(0x03023174,0x0302c174));self.assertEqual(n,expected)
        self.assertEqual(self.f.call('playback_speed_position',0x20003008),0)

    def test_pending_two_slots_are_not_overwritten(self):
        _,a,na=self.capture();self.submit(a,na)
        _,b,nb=self.capture();self.assertNotEqual(a,b)
        before=bytes(self.cpu.mem_read(a,PACKET_BYTES))+bytes(self.cpu.mem_read(b,PACKET_BYTES))
        delivered=self.delivered
        self.assertEqual(self.capture()[0],2)
        self.assertEqual(self.delivered,delivered)
        self.assertEqual(bytes(self.cpu.mem_read(a,PACKET_BYTES))+bytes(self.cpu.mem_read(b,PACKET_BYTES)),before)
        self.f.call('playback_speed_done');self.submit(b,nb)
        self.assertEqual(self.capture()[0],1)

    def stage_partial_then_wait(self):
        self.blocks=[1152,0,1152]
        self.scripted=[(1152,100,200,0,1111)]
        self.put(0x20003000,0x03023174);self.put(0x20003004,1152)
        self.assertEqual(self.capture(),(2,0x03023174,1152))
        self.assertEqual(self.dma,[])

    def test_partial_output_survives_decoder_wait_without_publication(self):
        self.stage_partial_then_wait()
        self.scripted=[(0,0,200,0,0),(1152,156,512,0,2222)]
        status,p,n=self.capture();self.assertEqual((status,n),(1,256))
        expected=struct.pack('<hh',1111,-1111)*100+struct.pack('<hh',2222,-2222)*156
        self.assertEqual(bytes(self.cpu.mem_read(p,1024)),expected)
        self.assertEqual(bytes(self.cpu.mem_read(p+1024,1024)),bytes(1024))
        self.f.call('playback_speed_position',0x20003008);self.assertEqual(self.get(0x20003008),976)
        self.submit(p,n);self.f.call('playback_speed_done')
        self.f.call('playback_speed_position',0x20003008);self.assertEqual(self.get(0x20003008),986)

    def test_seek_discards_unpublished_partial_output(self):
        self.stage_partial_then_wait()
        self.f.call('playback_speed_seek',12000,0)
        self.scripted=[(1152,256,512,0,2222)]
        status,p,n=self.capture();self.assertEqual((status,n),(1,256))
        self.assertEqual(bytes(self.cpu.mem_read(p,1024)),struct.pack('<hh',2222,-2222)*256)

    def test_partial_output_survives_work_budget_yield(self):
        self.scripted=[(0,16,(i+1)*32,0,1000+i) for i in range(16)]
        self.put(0x20003000,0x03023174);self.put(0x20003004,1152)
        self.assertEqual(self.capture(),(2,0x03023174,1152))
        self.assertEqual(self.get(0xe000ed04),1<<28)
        status,p,n=self.capture();self.assertEqual((status,n),(1,256))
        expected=b''.join(struct.pack('<hh',1000+i,-1000-i)*16 for i in range(16))
        self.assertEqual(bytes(self.cpu.mem_read(p,1024)),expected)
        self.assertEqual(self.delivered,1)

    def test_seek_drops_old_audio_clock_and_forwards_native_opcode(self):
        _,p,n=self.capture();self.submit(p,n)
        self.assertEqual(self.f.call('playback_speed_seek',23456,1),1)
        self.assertEqual(self.commands[-1],14)
        self.f.call('playback_speed_done')
        self.assertEqual(self.f.call('playback_speed_position',0x20003008),0)

    def test_time_getter_preserves_native_return_but_uses_audible_time(self):
        self.assertEqual(self.f.call('playback_speed_time',0x20003008),1)
        self.assertEqual(self.get(0x20003008),999999)
        self.capture()
        self.assertEqual(self.f.call('playback_speed_time',0x20003008),1)
        self.assertLess(self.get(0x20003008),1100)

    def test_unsupported_codec_and_depth_keep_native_path(self):
        for address,value in ((0x03039e94,1),(0x0302312c,24)):
            self.f.call('playback_speed_reset');self.put(0x0303517c,0x20000301)
            self.put(address,value)
            status,p,n=self.capture()
            self.assertEqual(status,1);self.assertIn(p,(0x03023174,0x0302c174))
            self.put(address,0 if address==0x03039e94 else 16)

if __name__=='__main__':unittest.main()
