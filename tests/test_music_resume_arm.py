"""Indexed Music resume capture, with native queue reconstruction boundaries."""
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

    def test_capture_precedes_browser_resume_clear(self):
        self.music_context()
        self.launch()
        self.assertEqual(self.f.call('playback_music_request'), 1)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x0300d164+0x68,4))[0], 0)
        self.f.call('playback_begin', 0)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        rebuilt=[]
        def queue(cpu,address,size,user):
            if address != 0x030603d0: return
            rebuilt.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
            cpu.mem_write(0x0300d85c+0x14,session.fat_entry(b'ONE     MP3',100))
            cpu.mem_write(0x0300d85c+0x38,struct.pack('<I',2))
            cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,queue)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,2,0,0x03005ab4),0)
        self.assertEqual(rebuilt,[(4,3,1)])
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d1cc,5)),struct.pack('<I',54321)+b'\x01')
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],0)

    def test_fresh_entry_cancels_interrupted_restore(self):
        self.music_context();self.launch()
        self.assertEqual(self.f.call('playback_music_request'),1)
        self.f.call('playback_begin',0)
        # Previous player entry stopped before reaching its queue hook.
        self.f.call('playback_begin',0x20001000)
        calls=[]
        def prepare(cpu,address,size,user):
            if address!=0x03082732:return
            calls.append(cpu.reg_read(UC_ARM_REG_R0))
            cpu.reg_write(UC_ARM_REG_R0,42);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,prepare)
        self.assertEqual(self.f.call('playback_prepare',3),42)
        self.assertEqual(calls,[3])

    def test_unsupported_library_context_declines_resume(self):
        self.music_context(8)
        self.launch()
        self.assertEqual(self.f.call('playback_music_request'),2)

    def test_no_music_context_declines_resume(self):
        self.launch()
        self.assertEqual(self.f.call('playback_music_request'),2)

    def test_reused_cluster_with_changed_file_record_declines_resume(self):
        for offset,value in ((0,ord('X')),(11,0x21),(18,1),(28,10)):
            with self.subTest(offset=offset):
                self.setUp();self.music_context();self.launch()
                changed=bytearray(self.f.dirs[0][1]);changed[offset]=value
                self.f.dirs[0][1]=bytes(changed)
                self.assertEqual(self.f.call('playback_music_request'),2)
                self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)

    def test_reconstruction_changed_size_aborts_without_seek(self):
        self.music_context();self.launch()
        self.assertEqual(self.f.call('playback_music_request'),1)
        self.f.call('playback_begin',0)
        def replacement(cpu,address,size,user):
            if address!=0x030603d0:return
            raw=bytearray(session.fat_entry(b'ONE     MP3',100));struct.pack_into('<I',raw,28,123)
            cpu.mem_write(0x0300d85c+0x14,bytes(raw))
            cpu.mem_write(0x0300d85c+0x38,struct.pack('<I',2))
            cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,replacement)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,2,0,0x03005ab4),19)
        self.assertEqual(self.cpu.mem_read(0x0300d1d0,1)[0],0)

    def test_device_or_filesystem_change_declines_without_clearing_book(self):
        for address,value in ((0x0300d173,4),(0x03076b24,3)):
            with self.subTest(address=address):
                self.setUp();self.music_context();self.launch()
                self.cpu.mem_write(address,bytes([value]))
                self.assertEqual(self.f.call('playback_music_request'),2)
                self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)

    def test_second_book_launch_keeps_original_music(self):
        self.music_context();self.launch()
        self.cpu.mem_write(0x0300d1cc,struct.pack('<I',777))
        self.window=[];self.launch()
        self.assertEqual(self.f.call('playback_music_request'),1)
        self.f.call('playback_begin',0)
        def rebuilt(cpu,address,size,user):
            if address!=0x030603d0:return
            cpu.mem_write(0x0300d85c+0x14,session.fat_entry(b'ONE     MP3',100))
            cpu.mem_write(0x0300d85c+0x38,struct.pack('<I',2))
            cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,rebuilt)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,2,0,0x03005ab4),0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x0300d1cc,4))[0],54321)

    def test_deliberate_music_selection_replaces_earlier_capture(self):
        self.music_context();self.launch()
        self.f.call('playback_begin',0x20001000)
        self.music_context()
        self.cpu.mem_write(0x0300d85c+0x14,session.fat_entry(b'TWO     MP3',101))
        self.cpu.mem_write(0x0300d85c+0x38,struct.pack('<I',3))
        self.cpu.mem_write(0x0300d1cc,struct.pack('<I',87654))
        self.window=[];self.launch()
        self.assertEqual(self.f.call('playback_music_request'),1)
        self.f.call('playback_begin',0)
        def rebuilt(cpu,address,size,user):
            if address!=0x030603d0:return
            cpu.mem_write(0x0300d85c+0x14,session.fat_entry(b'TWO     MP3',101))
            cpu.mem_write(0x0300d85c+0x38,struct.pack('<I',3))
            cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,rebuilt)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,2,0,0x03005ab4),0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x0300d1cc,4))[0],87654)

    def test_missing_music_file_keeps_book_context(self):
        self.music_context();self.launch()
        self.f.dirs[0][1]=session.fat_entry(b'ONE     MP3',999)
        self.assertEqual(self.f.call('playback_music_request'),2)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)

    def test_changed_queue_identity_aborts_without_seeking(self):
        self.music_context();self.launch()
        self.assertEqual(self.f.call('playback_music_request'),1)
        self.f.call('playback_begin',0)
        def wrong_queue(cpu,address,size,user):
            if address!=0x030603d0:return
            cpu.mem_write(0x0300d85c+0x2e,struct.pack('<H',999))
            cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,wrong_queue)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,2,0,0x03005ab4),19)
        self.assertEqual(self.cpu.mem_read(0x0300d1d0,1)[0],0)
        self.assertEqual(self.f.call('playback_music_request'),2)

    def test_real_native_queue_reconstructs_saved_music(self):
        self.music_context();self.launch()
        self.assertEqual(self.f.call('playback_music_request'),1)
        self.f.call('playback_begin',0)
        # Native global-count and ordinal mapping use separate media caches.
        # Intercept those boundaries, execute native queue construction and
        # the raw directory enumerators (filesystem reader is fixture-backed).
        def cache(cpu,address,size,user):
            result=None
            if address==0x0305d0dc:result=7
            elif address==0x0305d130:
                descriptor=cpu.reg_read(UC_ARM_REG_R1)
                cpu.mem_write(descriptor,bytes(44));result=1
            if result is not None:
                cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,cache)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,2,0,0x03005ab4),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],100)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d1cc,5)),struct.pack('<I',54321)+b'\x01')

    def test_native_player_entry_uses_saved_index_despite_null_argument(self):
        self.native_player_restore(99)

    def test_mode10_database_context_declines_raw_reference_restore(self):
        self.music_context(10);self.launch()
        self.assertEqual(self.f.call('playback_music_request'),2)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)

    def native_player_restore(self,mode):
        self.music_context(mode);self.launch()
        self.assertEqual(self.f.call('playback_music_request'),1)
        observed=[]
        def cache(cpu,address,size,user):
            result=None
            if address==0x0305d0dc:result=7
            elif address==0x0305d130:
                observed.append(cpu.reg_read(UC_ARM_REG_R0))
                cpu.mem_write(cpu.reg_read(UC_ARM_REG_R1),bytes(44));result=1
            if result is not None:
                cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,cache)
        self.cpu.mem_write(0x0300d0cc,b'\x01');self.init_slice=True
        self.f.call(0x030827ba,0)
        self.assertEqual(observed,[4])
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0xf2,2))[0],mode)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],100)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d1cc,5)),struct.pack('<I',54321)+b'\x01')
        self.assertEqual(struct.unpack('<3I',self.cpu.mem_read(0x03023090+28,12)),(3,1,3))

    def test_folder_scope_captures_global_ordinal_before_switch(self):
        self.observe_ordinal=True
        self.music_context()
        self.cpu.mem_write(0x0300d85c+10,struct.pack('<H',2))
        calls=[]
        def ordinal(cpu,address,size,user):
            if address!=0x0305e64c:return
            calls.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
            cpu.reg_write(UC_ARM_REG_R0,17);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,ordinal)
        self.launch()
        self.assertEqual(calls,[(4,0,0x03005ab4,3)])
        self.assertEqual(self.f.call('playback_music_request'),1)
        self.f.call('playback_begin',0)
        def rebuild(cpu,address,size,user):
            if address!=0x030603d0:return
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R1),17)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R2),2)
            cpu.mem_write(0x0300d85c+0x14,session.fat_entry(b'ONE     MP3',100))
            cpu.mem_write(0x0300d85c+0x38,struct.pack('<I',2))
            cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,rebuild)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,2,0,0x03005ab4),0)

    def test_actual_main_music_dispatch_saves_book_and_restarts_player(self):
        self.music_context()
        self.writes=[];self.short_write=False
        self.cpu.hook_add(UC_HOOK_CODE,lambda *args:resume.ResumeTests.write(self,*args))
        self.f.dirs[0].insert(-1,resume.sized(b'LIST    RSM',91,1024))
        self.f.files[91]=resume.blank()
        self.launch();self.window=[]
        image=session.fixture.Image((session.fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        for index in (21,34):
            m=image.modules[index]
            for kind in ('code','data'):
                off=image.l2f(m[kind+'_load'])
                self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
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
            if address==0x0306b26a:
                self.assertEqual(self.writes,[(91,512)])
            if address in stubs:
                cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,hardware);self.real_callbacks=True
        self.f.call('navigation_menu_init')
        self.cpu.mem_write(0x0300e708,struct.pack('<H',2))
        self.assertEqual(self.f.call(0x03079b1e),1)
        self.assertEqual(visited,[0x03059910,0x030833f0,0x03082524,0x03082164,0x030822ac,0x030825c4])
        self.assertEqual(self.window,[(3,b'\x01\x00')])
        self.assertEqual(struct.unpack_from('<II',self.f.files[91],512+12),(1,1234567))
        self.assertEqual(self.codec_closes,1)
        self.f.call('playback_begin',0)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],0)

    def test_menu_no_music_chooses_native_library_without_clearing_book(self):
        self.launch()
        self.cpu.mem_write(0x0300e708,struct.pack('<H',2))
        self.assertEqual(self.f.call('navigation_menu_dispatch'),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300e708,2))[0],1)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)

    def test_ordinary_music_menu_retains_native_route(self):
        self.music_context()
        self.cpu.mem_write(0x0300e708,struct.pack('<H',2))
        self.assertEqual(self.f.call('navigation_menu_dispatch'),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300e708,2))[0],2)

if __name__=='__main__': unittest.main()
