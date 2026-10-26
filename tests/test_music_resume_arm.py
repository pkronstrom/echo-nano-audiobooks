"""Now Playing supersedes previous-music restoration; preserve current audio."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_PC, UC_ARM_REG_LR
import test_playback_session_arm as session
import test_book_resume_arm as resume

class MusicResumeTests(unittest.TestCase):
    setUp=session.SessionTests.setUp
    def hook(self,cpu,address,size,user):
        if address==0x0305e64c and getattr(self,'observe_ordinal',False): return
        session.SessionTests.hook(self,cpu,address,size,user)
    launch=session.SessionTests.launch
    def music_context(self, mode=99):
        self.cpu.mem_write(0x0300d85c, struct.pack('<7H', 7, 4, 0, 4, 7, 3, 1))
        self.cpu.mem_write(0x0300d85c+0xf2, struct.pack('<H', mode))
        self.cpu.mem_write(0x0300d85c+0x14, session.fat_entry(b'ONE     MP3',100))
        self.cpu.mem_write(0x0300d85c+0x38, struct.pack('<I', 2))
        self.cpu.mem_write(0x0300d164+0x68, struct.pack('<I', 54321))
        self.cpu.mem_write(0x0300d164+0x6d, b'\x03')

    def test_now_playing_keeps_book_after_music(self):
        for mode in (8,9,10,99):
            with self.subTest(mode=mode):
                self.setUp();self.music_context(mode);self.launch()
                before=bytes(self.cpu.mem_read(0x0300d85c,256))
                self.f.call('playback_begin',0)
                self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)
                self.assertEqual(bytes(self.cpu.mem_read(0x0300d85c,256)),before)

    def test_deliberate_new_music_selection_exits_book(self):
        self.launch();self.f.call('playback_begin',0x20001000)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],0)

    def test_actual_main_now_playing_dispatch_opens_current_player_without_stop(self):
        self.music_context();self.launch();self.window=[]
        self.cpu.mem_map(0,4096)
        image=session.fixture.Image((session.fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        m=image.modules[21]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load']);self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.f.call('navigation_menu_init');self.cpu.mem_write(0x0300e708,b'\0\0')
        visited=[]
        def hardware(cpu,address,size,user):
            if address==0x03059910:visited.append(address)
            if address in (0x0306b0a0,0x030656b8,0x030595b4):
                cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,hardware)
        self.assertEqual(self.f.call(0x03079b1e),1)
        self.assertFalse(visited)
        self.assertEqual(self.window,[(3,b'\0\0')])
        self.assertEqual(bytes(self.cpu.mem_read(0x0300e708,2)),b'\0\0')
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)
