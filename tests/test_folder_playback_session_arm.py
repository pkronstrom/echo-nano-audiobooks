"""Persistent folder queue handoff, using compiled playback and native readers."""
import struct
import unittest
import test_playback_session_arm as session
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
import test_book_resume_arm as resume
import test_music_resume_arm as music_resume

class FolderSessionTests(unittest.TestCase):
    setUp=session.SessionTests.setUp
    hook=session.SessionTests.hook
    launch=session.SessionTests.launch
    def staged(self):
        q=bytearray(3848)
        for i,(raw,cluster) in enumerate(((1,100),(2,101))):
            struct.pack_into('<III',q,i*12,0,0,cluster)
            struct.pack_into('<H',q,3072+i*2,raw)
        struct.pack_into('<II',q,3840,2,123)
        self.cpu.mem_write(0x20004000,bytes(q))
        return 0x20004000
    def folder(self,position=1):
        self.assertEqual(self.f.call('playback_folder_launch',self.staged(),position),1)
        self.cpu.mem_write(0x20004000,bytes(3848)) # overlay expires
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
    def test_folder_import_survives_overlay_and_has_real_order(self):
        self.folder()
        self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,1))
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x0300d85c+0x38,4))[0],2) # native Favorites raw identity
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,1),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],101)
        self.assertEqual(self.f.call('playback_add_bookmark'),0xffffffff)
        self.assertEqual(self.f.call('playback_speed_supported'),0)
    def test_rejected_folder_keeps_book(self):
        self.launch()
        self.assertEqual(self.f.call('playback_folder_launch',self.staged(),3),0)
        self.assertEqual(self.f.call('playlist_count'),2)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)
    def test_book_folder_book(self):
        self.launch();self.folder(2)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],2)
        self.window=[];self.launch()
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)
    def test_folder_to_book_music_return_falls_back_to_library(self):
        music_resume.MusicResumeTests.music_context(self)
        self.launch();self.folder()
        self.assertEqual(self.f.call('playback_music_request'),0)
        self.window=[];self.launch()
        self.assertEqual(self.f.call('playback_music_request'),2)
    def test_folder_device_change_rejects_advance(self):
        self.folder()
        self.cpu.mem_write(0x0300d173,b'\x01')
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,1),19)

    def test_missing_selection_refuses_without_stop(self):
        self.launch();q=self.staged()
        # Stale physical cluster, valid queue geometry
        self.cpu.mem_write(q+8,struct.pack('<I',999))
        self.assertEqual(self.f.call('playback_folder_launch',q,1),0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)
        self.assertEqual(self.f.call('playlist_count'),2)
    def test_bad_count_and_position_preserve_context(self):
        for count,pos in ((0,1),(257,1),(2,0),(2,3)):
            q=self.staged();self.cpu.mem_write(q+3840,struct.pack('<I',count))
            self.assertEqual(self.f.call('playback_folder_launch',q,pos),0)
        self.assertEqual(self.window,[])
    def test_reentry_manual_previous_auto_end_and_settings(self):
        self.folder(2)
        self.cpu.mem_write(0x0300d81a,struct.pack('<H',3))
        self.f.call('playback_begin',0)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d81a,2))[0],3)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
        self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,2))
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,1),19)
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,0xffffffff),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],100)
        self.cpu.mem_write(0x03023090+28,struct.pack('<3I',1,1,3))
        self.f.call('playback_force_mode')
        self.assertEqual(struct.unpack('<3I',self.cpu.mem_read(0x03023090+28,12)),(2,0,2))
        self.cpu.mem_write(0x03039708+8,struct.pack('<I',1))
        self.assertEqual(self.f.call('playback_advance',0x0300d85c,0xffffffff),0)
        self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,2))
    def test_native_automatic_advance_and_cold_resume_physical_index(self):
        self.folder()
        self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
        self.f.call(0x03081786,1)
        self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,2))
        self.f.call(0x03081786,1)
        self.assertEqual(self.stopped,1)
        image=session.fixture.Image((session.fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        m=image.modules[34]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.f.call(0x030830a4,1234567,0x0300d85c)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+2,2))[0],2)
        self.assertEqual(struct.unpack('<HI',self.cpu.mem_read(0x0300d164+0x66,6)),(17,1234567))
    def test_real_stop_saves_old_book_before_queue_import(self):
        self.writes=[];self.short_write=False
        self.cpu.hook_add(UC_HOOK_CODE,lambda *args:resume.ResumeTests.write(self,*args))
        self.f.dirs[0].insert(-1,resume.sized(b'LIST    RSM',91,1024))
        self.f.files[91]=resume.blank()
        self.launch();self.window=[]
        image=session.fixture.Image((session.fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        m=image.modules[34]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
        self.cpu.mem_write(0x03023090,struct.pack('<II',7200000,1234567))
        self.cpu.mem_write(0x0300d0cc,b'\x01')
        self.cpu.mem_write(0x0300dc1c,struct.pack('<I',0x0302315c))
        self.cpu.mem_write(0x0302315c,struct.pack('<5I',0,0,0,0,0x030833f1))
        stubs={0x0306b0a0,0x030656b8,0x03059a74,0x03056880,0x03054d1c,
               0x030838b8,0x0306b6bc,0x03083660,0x03081aa4,0x0305fbf2,
               0x030595b4,0x0305965e,0x0306a33c,0x03084ea0,0x03069876,
               0x0306af30,0x030718f6,0x030715a0}
        def hardware(cpu,address,size,user):
            if address==0x0306b26a:self.assertEqual(self.writes,[(91,512)])
            if address in stubs:
                cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,hardware);self.real_callbacks=True
        self.folder()
        self.assertEqual(struct.unpack_from('<II',self.f.files[91],524),(1,1234567))
        self.assertEqual(struct.unpack_from('<I',self.f.files[91],540)[0],101) # old book first track
        self.assertEqual(self.codec_closes,1)
        self.f.call('book_save')
        self.assertEqual(self.writes,[(91,512)])
        self.assertEqual(self.f.call('playback_music_request'),0)

if __name__=='__main__':unittest.main()
