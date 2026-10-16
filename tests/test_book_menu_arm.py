"""Synthetic book UI executes compiled ARM; native media/UI I/O is stubbed."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_PC, UC_ARM_REG_LR
import test_playback_session_arm as session
from test_music_filter import fat_entry, END
from test_media_path import lfn

B=0x03005f6c
C=0x0300ec1c
SELECT=0x40000040
NEXT=0x40000004
BACK=0x40001000

class BookMenuTests(unittest.TestCase):
    def setUp(self):
        self.s=session.SessionTests();self.s.setUp();self.f=self.s.f;self.cpu=self.f.cpu
        self.cpu.mem_write(0x0300e73c+4,struct.pack('<I',0x0300e9ac))
        self.cpu.mem_write(0x0300e9ac+4,struct.pack('<I',0x0300e73c))
        self.cpu.mem_write(B+0x1f4,struct.pack('<I',0x0300e6e4))
        self.cpu.mem_write(B+12,struct.pack('<HHH',3,0,3))
        self.saved=bytes(self.cpu.mem_read(B,512))
        self.nodes=bytes(self.cpu.mem_read(0x0300e73c,1248))
        self.fail_preview=False;self.calls=[];self.override=[];self.marks=[[1,61000],[2,125000]]
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
    def hook(self,cpu,address,size,user):
        result=None
        if address==self.f.syms.get('book_preview_open',0)&~1 and self.fail_preview:result=-1
        elif address==self.f.syms.get('book_preview_marks',0)&~1:result=len(self.marks)
        elif address==self.f.syms.get('book_preview_mark',0)&~1:
            i=cpu.reg_read(UC_ARM_REG_R0)
            result=int(i<len(self.marks))
            if result:cpu.mem_write(cpu.reg_read(UC_ARM_REG_R1),struct.pack('<II',*self.marks[i]))
        elif address==self.f.syms.get('book_preview_delete',0)&~1:
            i=cpu.reg_read(UC_ARM_REG_R0);self.calls.append(('delete',i))
            if i<len(self.marks):self.marks.pop(i);result=1
            else:result=-1
        elif address==self.f.syms.get('playback_launch_override',0)&~1:
            self.override.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)))
            result=0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result&0xffffffff);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def call(self,name,*args):return self.f.call(name,*args)
    def event(self,key):return self.call('book_menu_event',key)
    def title(self,slot=0):
        data=bytes(self.cpu.mem_read((0x0300e73c,0x0300e9ac)[slot]+0x70,512))
        return data.decode('utf-16le').split('\0',1)[0]
    def open(self):self.assertEqual(self.call('book_menu_open_selected'),1)
    def test_open_and_back_preserve_real_browser_and_active_queue(self):
        self.s.launch();before=bytes(self.cpu.mem_read(0x0300d85c,256))
        self.open()
        self.assertTrue(self.title().startswith('Continue'))
        self.assertEqual(self.title(1),'Chapters')
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d85c,256)),before)
        self.assertEqual(self.event(BACK),1)
        self.assertEqual(bytes(self.cpu.mem_read(B,512)),self.saved)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300e73c,1248)),self.nodes)
        self.assertEqual(self.event(SELECT),0)
    def test_chapters_launch_restores_real_node_and_sets_explicit_position(self):
        self.open();self.event(NEXT);self.event(SELECT)
        self.assertEqual(self.title(),'Chapter 1');self.assertEqual(self.title(1),'Chapter 2')
        self.event(NEXT);self.event(SELECT)
        self.assertEqual(self.override[-1][:2],(2,0))
        self.assertNotEqual(self.override[-1][2],0)
        self.assertEqual(self.s.window,[(3,b'\x01\x00')])
        self.assertEqual(self.call('book_menu_browser_init'),1)
        self.assertTrue(self.title().startswith('Continue'))
    def test_bookmarks_jump_and_delete_requires_confirmation(self):
        self.open();self.event(NEXT);self.event(NEXT);self.event(SELECT)
        self.assertEqual(self.title(),'Ch 1 00:01:01')
        self.event(NEXT);self.event(SELECT)
        self.assertEqual(self.title(),'Play bookmark')
        self.event(NEXT);self.event(SELECT)
        self.assertEqual(self.title(),'Delete bookmark?')
        self.assertEqual(self.calls,[])
        self.event(BACK);self.assertEqual(self.calls,[])
        self.event(NEXT);self.event(SELECT);self.event(NEXT);self.event(SELECT)
        self.assertEqual(self.calls,[('delete',1)])
        self.assertEqual(self.title(),'Ch 1 00:01:01')
    def test_synthetic_context_actions_blocked_and_service_messages_forwarded(self):
        self.open()
        for key in (0x20000080,0x40000002,0x40010000,0x50010000):self.assertEqual(self.event(key),1)
        self.assertEqual(self.event(439),0)
        self.assertEqual(self.event(333),0)
        self.assertEqual(self.s.window,[])
    def speed_menu(self):
        self.open()
        for _ in range(3):self.event(NEXT)
        self.assertEqual(self.title(1),'MP3 speed 1x')
        self.event(SELECT)

    def test_speed_presets_apply_only_on_selection_and_preserve_launch_routes(self):
        self.speed_menu()
        labels=('1x','1.25x','1.5x','1.75x','2x')
        for index,label in enumerate(labels):
            if index:
                self.event(SELECT) # reopen from selected top Speed row
                self.event(NEXT)
            self.assertEqual(self.title(index&1),label)
            self.event(SELECT)
            self.assertEqual(self.call('book_preview_rate'),index+4)
            self.assertEqual(self.call('playback_speed_get'),4)
            self.assertEqual(self.title(),'Bookmarks')
            self.assertEqual(self.title(1),'MP3 speed '+label)
            self.assertEqual(self.override,[])
            self.assertEqual(self.s.window,[])
        self.event(NEXT) # wrap to Continue
        self.assertEqual(self.event(SELECT),2)
        self.assertEqual(self.override[-1][:2],(0,0))

    def test_speed_back_does_not_change_setting_and_keeps_speed_selected(self):
        self.speed_menu()
        self.event(NEXT);self.event(NEXT)
        self.event(BACK)
        self.assertEqual(self.call('playback_speed_get'),4)
        self.assertEqual(self.title(1),'MP3 speed 1x')
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(B+0x1ee,2))[0],1)
        self.event(SELECT)
        self.assertEqual(self.title(),'1x')
        self.assertEqual(self.title(1),'1.25x')

    def folder(self,prepared=True):
        self.f.dirs[0]=[fat_entry(b'BOOK       ',20,True),END]
        self.f.dirs[20]=[fat_entry(b'BOOK    M3U',90),fat_entry(b'ONE     MP3',100),END] if prepared else [END]
        self.f.files[90]=b'one.mp3\n'
        self.cpu.mem_write(0x0300e73c+0x4e,b'\0')
        self.cpu.mem_write(0x0300e73c+0x69,struct.pack('<H',20))
        self.cpu.mem_write(0x0300e73c+0x70,'Book\0'.encode('utf-16le'))
        self.nodes=bytes(self.cpu.mem_read(0x0300e73c,1248))
    def test_prepared_folder_opens_book_menu_and_back_restores_parent(self):
        self.folder();self.open()
        self.assertTrue(self.title().startswith('Continue'))
        self.assertEqual(self.event(BACK),1)
        self.assertEqual(bytes(self.cpu.mem_read(B,512)),self.saved)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300e73c,1248)),self.nodes)
    def test_invalid_prepared_book_back_restores_parent(self):
        self.cpu.mem_map(0,4096)
        for key in (BACK,SELECT):
            self.folder();self.f.files[90]=b'';self.open()
            self.assertEqual(self.title(),'Book unavailable')
            self.assertEqual(self.event(key),1)
            self.assertEqual(bytes(self.cpu.mem_read(B,512)),self.saved)
            self.assertEqual(bytes(self.cpu.mem_read(0x0300e73c,1248)),self.nodes)
    def test_replaced_folder_return_does_not_restore_old_identities(self):
        self.folder();self.open();self.event(SELECT)
        self.f.dirs[0]=[fat_entry(b'BOOK       ',21,True),END]
        self.f.dirs[21]=self.f.dirs[20]
        fresh=bytes([0xA5])*512;self.cpu.mem_write(B,fresh)
        self.assertEqual(self.call('book_menu_browser_init'),0)
        self.assertEqual(bytes(self.cpu.mem_read(B,512)),fresh)

    def test_folder_back_revalidates_identity_while_menu_is_open(self):
        self.cpu.mem_map(0,4096)
        self.folder();self.open()
        self.f.dirs[0]=[fat_entry(b'BOOK       ',21,True),END]
        self.assertEqual(self.event(BACK),2)
        self.assertEqual(self.s.window[-1][0],0)
        self.assertNotEqual(bytes(self.cpu.mem_read(B,512)),self.saved)
    def test_folder_in_second_slot_with_reversed_list_restores_exactly(self):
        self.folder()
        self.cpu.mem_write(B,struct.pack('<I',0x0300e9ac))
        self.cpu.mem_write(B+0x1ee,struct.pack('<H',1))
        self.saved=bytes(self.cpu.mem_read(B,512))
        self.open();self.event(BACK)
        self.assertEqual(bytes(self.cpu.mem_read(B,512)),self.saved)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300e73c,1248)),self.nodes)

    def test_unprepared_folder_falls_through(self):
        self.folder(False)
        self.assertEqual(self.call('book_menu_open_selected'),0)
        self.assertEqual(bytes(self.cpu.mem_read(B,512)),self.saved)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300e73c,1248)),self.nodes)
    def test_prepared_folder_launch_uses_native_path_and_correct_queue(self):
        self.folder();self.open()
        self.assertEqual(self.event(SELECT),2)
        self.assertEqual(self.s.window,[(3,b'\x01\x00')])
        self.call('playback_begin',0x20001000)
        self.assertEqual(self.call('playback_prepare',3),0)
        self.assertEqual(self.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
        self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(1,1))
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],100)

    def test_nonplaylist_selection_not_intercepted(self):
        self.cpu.mem_write(0x0300e73c+0x70,'two.mp3\0'.encode('utf-16le'))
        self.assertEqual(self.call('book_menu_open_selected'),0)
    def test_missing_return_media_keeps_fresh_native_browser(self):
        self.open();self.event(SELECT)
        self.fail_preview=True
        fresh=bytes([0xA5])*512
        self.cpu.mem_write(B,fresh)
        self.assertEqual(self.call('book_menu_browser_init'),0)
        self.assertEqual(bytes(self.cpu.mem_read(B,512)),fresh)
        self.assertEqual(self.event(SELECT),0)
    def test_initial_preview_failure_shows_error_and_back_exits(self):
        self.cpu.mem_map(0,4096) # legacy window stub reads two bytes even for null args
        self.fail_preview=True;self.open()
        self.assertEqual(self.title(),'Book unavailable')
        self.assertEqual(self.title(1),'Back')
        self.assertEqual(self.event(SELECT),2)
        self.assertEqual(self.s.window[-1][0],0)
        self.assertEqual(self.event(SELECT),0)
    def test_fresh_native_browser_init_clears_active_menu(self):
        self.open()
        self.assertEqual(self.call('book_menu_browser_init'),0)
        self.assertEqual(self.event(SELECT),0)
    def test_continue_last_uses_stored_path_not_current_browser_node(self):
        self.s.launch()
        self.cpu.mem_write(0x20001000,'/list.m3u\0'.encode('utf-16le'))
        self.call('last_book_remember',0x20001000)
        self.cpu.mem_write(0x0300e73c+0x70,'Other folder\0'.encode('utf-16le'))
        self.assertEqual(self.call('book_menu_continue_last'),2)
        self.assertEqual(self.s.window[-1],(3,b'\x01\x00'))

    def test_last_book_signature_change_fails_without_launch(self):
        self.s.launch()
        self.cpu.mem_write(0x20001000,'/list.m3u\0'.encode('utf-16le'))
        self.call('last_book_remember',0x20001000)
        self.f.files[90]=b'one.mp3\ntwo.mp3\n'
        before=len(self.s.window)
        self.assertEqual(self.call('book_menu_continue_last'),0)
        self.assertEqual(len(self.s.window),before)

    def test_landing_continue_return_back_then_browse_owns_synthetic_rows(self):
        self.s.launch()
        self.cpu.mem_write(0x20001000,'/list.m3u\0'.encode('utf-16le'))
        self.call('last_book_remember',0x20001000)
        self.f.dirs[0][-1:]=[*lfn('.audiobook',b'AUDIOB~1   ',92),END]
        image=session.fixture.Image((session.fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        def module(index):
            m=image.modules[index]
            for kind in ('code','data'):
                off=image.l2f(m[kind+'_load'])
                self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        module(21);self.call('navigation_menu_init')
        self.cpu.mem_write(0x0300e708,struct.pack('<H',6))
        self.assertEqual(self.call('navigation_menu_dispatch'),1)
        module(31)
        self.cpu.mem_write(B+0x1f4,struct.pack('<I',0x0300e6e4))
        self.call('navigation_browser_init')
        self.assertEqual(self.title(),'Continue list')
        self.assertEqual(self.call('navigation_event',SELECT),2)
        self.call('navigation_browser_init')
        self.assertTrue(self.title().startswith('Continue '))
        self.assertEqual(self.call('navigation_event',BACK),1)
        self.assertEqual(self.title(),'Continue list')
        calls=[]
        def enumeration(cpu,address,size,user):
            if address not in (0x0307974e,0x03079592):return
            calls.append(address)
            cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,enumeration)
        self.call('navigation_event',NEXT)
        self.assertEqual(self.call('navigation_event',SELECT),1)
        self.assertIn(0x03079592,calls)

    def test_reset_prevents_stale_return(self):
        self.open();self.event(SELECT);self.call('book_menu_reset')
        self.assertEqual(self.call('book_menu_browser_init'),0)

if __name__=='__main__':unittest.main()
