"""Book session captures verified chapter/time and isolates ordinary music."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
import test_playback_session_arm as session
import test_book_resume_arm as resume
from test_prepare_book import book

class BookmarkSessionTests(unittest.TestCase):
    def setUp(self):
        self.s=session.SessionTests();self.s.setUp();self.f=self.s.f;self.cpu=self.s.cpu
        self.writes=[];self.short_write=False
        self.cpu.hook_add(UC_HOOK_CODE,lambda *args:resume.ResumeTests.write(self,*args))
        self.f.dirs[0].insert(-1,resume.sized(b'LIST    BMK',94,1024))
        self.f.files[94]=book.bookmark_bytes()
        self.s.launch()
        self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
        self.cpu.mem_write(0x03023090,struct.pack('<II',7200000,1234567))

    def add(self):
        self.assertIn('playback_add_bookmark',self.f.syms)
        return self.f.call('playback_add_bookmark')

    def test_captures_multiple_chapters_without_resume_companion(self):
        self.assertEqual(self.add(),1)
        self.f.call('playback_advance',0x0300d85c,1)
        self.cpu.mem_write(0x03023090+4,struct.pack('<I',9000))
        self.assertEqual(self.add(),2)
        self.assertEqual(self.f.call('bookmarks_get',0,0x20002400),1)
        self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(1,1234567))
        self.assertEqual(self.f.call('bookmarks_get',1,0x20002400),1)
        self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(2,9000))

    def test_music_transition_clears_bookmark_context(self):
        self.assertEqual(self.add(),1)
        self.f.call('playback_begin',0x20001000)
        before=self.f.files[94]
        self.assertEqual(self.add(),0xffffffff)
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,1,0),0xffffffff)
        self.assertEqual(self.f.files[94],before)

    def test_stale_decoder_identity_is_not_bookmarked(self):
        self.cpu.mem_write(0x0300d85c+0x14+26,struct.pack('<H',999))
        before=self.f.files[94]
        self.assertEqual(self.add(),0xffffffff)
        self.assertEqual(self.f.files[94],before)
