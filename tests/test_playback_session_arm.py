"""Compiled browser/player bridges; UI event delivery and codec close are stubbed."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP,UC_ARM_REG_R7,UC_ARM_REG_R10
import test_playback_runtime_arm as fixture
from test_music_filter import fat_entry,END

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PlaybackRuntimeTests();self.f.setUp();self.cpu=self.f.cpu
        self.events=[];self.window=[];self.stopped=0;self.opened=0;self.init_slice=False;self.seeks=[];self.codec_closes=0
        image=fixture.Image((fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        for index in (0,31,33):
            m=image.modules[index]
            for kind in ('code','data'):
                off=image.l2f(m[kind+'_load'])
                self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
        self.f.dirs={0:[fat_entry(b'LIST    M3U',90),fat_entry(b'ONE     MP3',100),fat_entry(b'TWO     MP3',101),END]}
        self.f.files={90:b'two.mp3\none.mp3\n'}
        self.cpu.mem_write(0x03005f6c,struct.pack('<I',0x0300e73c))
        self.cpu.mem_write(0x0300e73c+8,struct.pack('<II',0,0))
        self.cpu.mem_write(0x0300e73c+0x4e,b'\x06')
        self.cpu.mem_write(0x0300e73c+0x70,'list.m3u'.encode('utf-16le')+b'\0\0')
        self.cpu.mem_write(0x0300ec1c+8,struct.pack('<H',3))
        self.cpu.mem_write(0x03076b30+13,struct.pack('<I',2))
    def hook(self,cpu,address,size,user):
        result=None
        if self.init_slice and address==0x03082a06:
            sp=cpu.reg_read(UC_ARM_REG_SP)
            lr=struct.unpack('<I',cpu.mem_read(sp+44,4))[0]
            cpu.reg_write(UC_ARM_REG_SP,sp+48);cpu.reg_write(UC_ARM_REG_PC,lr);return
        if self.init_slice and address in (0x030595b4,0x0305965e,0x0306a33c,0x0306aee4,0x03071e28,0x0306b0a0,0x0306af30):result=0
        elif address==0x030834d8:
            self.seeks.append((cpu.reg_read(UC_ARM_REG_R0),cpu.reg_read(UC_ARM_REG_R1)));result=0
        elif address==0x03084e28:self.codec_closes+=1;result=0
        elif address==0x03071e28:result=0
        elif address==0x0305e64c:result=17
        elif address==0x03081432:self.opened+=1;result=0
        elif address==0x03059910 and not getattr(self,'real_callbacks',False):result=0
        elif address in (0x03067860,0x0306b082):result=0
        elif address==0x0306b040:self.events.append(cpu.reg_read(UC_ARM_REG_R0));result=0
        elif address==0x0306b26a:
            arg=cpu.reg_read(UC_ARM_REG_R1)
            self.window.append((cpu.reg_read(UC_ARM_REG_R0),bytes(cpu.mem_read(arg,2))));result=0
        elif address==0x030816ee:self.stopped+=1;result=0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def launch(self):
        self.assertEqual(self.f.call(0x0307acb6),1)
        self.assertEqual(self.window,[(3,b'\x01\x00')])
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0xf2,2))[0],99)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
    def test_launch_uses_selected_playlist_and_forces_order(self):
        self.launch()
        self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,1))
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],101)
        self.assertEqual(struct.unpack('<3I',self.cpu.mem_read(0x03023090+28,12)),(2,0,2))
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,1),0)
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,1),19)
        self.cpu.mem_write(0x03039708+8,struct.pack('<I',1))
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,1),0)
    def test_native_music_initialization_reaches_custom_queue(self):
        self.assertEqual(self.f.call(0x0307acb6),1)
        self.cpu.mem_write(0x0300d0cc,b'\x01') # audio hardware already initialized
        self.cpu.mem_write(0x20001000,b'\x01\x00')
        self.init_slice=True
        self.f.call(0x030827ba,0x20001000)
        self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,1))
        self.assertEqual(struct.unpack('<3I',self.cpu.mem_read(0x03023090+28,12)),(2,0,2))
    def test_native_advance_stops_at_end_and_manual_next_wraps(self):
        self.launch()
        self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
        self.f.call(0x03081786,1)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+2,2))[0],2)
        self.assertEqual(self.opened,1)
        self.f.call(0x03081786,1)
        self.assertEqual(self.stopped,1)
        self.assertEqual(self.opened,1)
        self.cpu.mem_write(0x03039708+8,struct.pack('<I',1))
        self.f.call(0x03081786,1)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+2,2))[0],1)
        self.assertEqual(self.opened,2)

    def test_browser_discovers_m3u_without_changing_audio_indices(self):
        for alias,kind in ((b'LIST    M3U',6),(b'ONE     MP3',1)):
            self.cpu.mem_write(0x20001000,fat_entry(alias,90))
            pointer=self.f.call(0x03079484,0x20001000)
            self.assertEqual(self.cpu.mem_read(pointer,1)[0],kind)
        self.cpu.mem_write(0x20001000,b'M3U\0')
        self.assertEqual(self.f.call(0x0305d4d8,0x20001000,0x03005a5e,32),1)
        self.assertEqual(self.f.call(0x0305d4d8,0x20001000,0x03005ab4,32),0)

    def test_shuffle_setting_cannot_reorder_active_playlist(self):
        self.launch()
        self.cpu.mem_write(0x0300d164+0x6f,b'\x01')
        self.cpu.reg_write(UC_ARM_REG_R7,0x0300d164)
        self.cpu.reg_write(UC_ARM_REG_R10,0x0300d85c)
        self.cpu.reg_write(UC_ARM_REG_R1,0x03023090)
        self.cpu.emu_start(0x030831bb,0x03083242,count=1000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),0x03083242)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x03023090+32,4))[0],0)
        self.assertEqual(self.cpu.mem_read(0x0300d164+0x6f,1)[0],1)

    def test_stock_resume_uses_saved_milliseconds_and_existing_seek(self):
        self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
        self.cpu.mem_write(0x03023090,struct.pack('<II',7200000,0))
        self.cpu.mem_write(0x0300d1cc,struct.pack('<I',1234567)+b'\x01')
        self.f.call(0x03080d54)
        self.assertEqual(self.seeks,[(1235000,0)])
        self.assertEqual(self.cpu.mem_read(0x0300d1d0,1)[0],0)
        self.f.call(0x0308237a,9000000)
        self.assertEqual(self.seeks[-1],(7200000,0))
    def test_save_guard_falls_back_when_refresh_owns_ram(self):
        self.cpu.mem_write(0x0309b694,b'CFW!')
        self.f.call(0x03083064)
        self.assertEqual(self.codec_closes,1)
    def test_stock_save_rebases_persisted_folder_index_without_corrupting_live_playlist(self):
        image=fixture.Image((fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        m=image.modules[34]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.launch()
        self.f.call(0x030830a4,1234567,0x0300d85c)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+2,2))[0],1)
        self.assertEqual(struct.unpack('<HI',self.cpu.mem_read(0x0300d164+0x66,6)),(17,1234567))

    def test_invalid_selection_does_not_launch_or_replace_queue(self):
        self.cpu.mem_write(0x0300e73c+12,struct.pack('<I',99))
        self.assertEqual(self.f.call(0x0307acb6),0)
        self.assertEqual(self.window,[])
    def test_reopening_keeps_queue_but_new_audio_clears_context(self):
        self.launch()
        self.f.call('playback_begin',0)
        active=self.f.syms['playback_active']
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(active,4))[0],1)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(active,4))[0],0)
    def test_empty_playlist_fails_before_native_queue_init(self):
        self.f.files={90:b'missing.mp3\n'}
        self.assertEqual(self.f.call(0x0307acb6),1)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),1)
        self.assertIn(245,self.events)

if __name__=='__main__':unittest.main()
