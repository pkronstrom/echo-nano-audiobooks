"""Persistent multi-book bookmarks, executed as ARM against simulated media."""
import struct
import test_book_resume_arm as resume
from test_book_resume_arm import sized
from test_music_filter import fat_entry, END
from test_prepare_book import book

class BookmarkTests(resume.ResumeTests):
    def setUp(self):
        super().setUp()
        self.f.files[94]=book.bookmark_bytes()
        self.f.dirs[0].insert(-1,sized(b'BOOK    BMK',94,1024))

    def open_bookmarks(self,signature=123):
        self.assertIn('bookmarks_open',self.f.syms)
        self.cpu.mem_write(0x20001000,'/BOOK.M3U'.encode('utf-16le')+b'\0\0')
        return self.f.call('bookmarks_open',0x20001000,signature)

    def get(self,index):
        result=self.f.call('bookmarks_get',index,0x20002400)
        return result,struct.unpack('<II',self.cpu.mem_read(0x20002400,8))

    def test_multiple_chapters_reopen_delete_and_independent_resume(self):
        resume=self.f.files[91]
        self.assertEqual(self.open_bookmarks(),0)
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,1,9000),1)
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,7,42000),2)
        self.f.call('playback_init')
        self.assertEqual(self.open_bookmarks(),2)
        self.assertEqual(self.get(0),(1,(1,9000)))
        self.assertEqual(self.get(1),(1,(7,42000)))
        self.assertEqual(self.f.call('bookmarks_change',0,0,0),1)
        self.assertEqual(self.get(0),(1,(7,42000)))
        self.assertEqual(self.f.files[91],resume)

    def test_torn_write_retains_previous_bookmarks(self):
        self.open_bookmarks()
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,1,1000),1)
        self.short_write=True
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,2,2000),0xffffffff)
        self.f.call('playback_init')
        self.assertEqual(self.open_bookmarks(),1)
        self.assertEqual(self.get(0),(1,(1,1000)))

    def test_changed_playlist_and_corruption_preserve_file(self):
        self.open_bookmarks();self.f.call('bookmarks_change',0xffffffff,2,2000)
        before=self.f.files[94]
        self.assertEqual(self.open_bookmarks(456),0xffffffff)
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,1,0),0xffffffff)
        self.assertEqual(self.f.files[94],before)
        self.f.files[94]=bytes(1024)
        self.assertEqual(self.open_bookmarks(),0xffffffff)
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,1,0),0xffffffff)
        self.assertEqual(self.f.files[94],bytes(1024))

    def test_full_journal_rejects_add_without_eviction(self):
        self.open_bookmarks()
        for i in range(60):
            self.assertEqual(self.f.call('bookmarks_change',0xffffffff,i+1,i*1000),i+1)
        before=self.f.files[94]
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,61,61000),0xffffffff)
        self.assertEqual(self.f.files[94],before)
        self.assertEqual(self.get(0),(1,(1,0)))

    def test_invalid_operations_and_busy_parser_never_write(self):
        self.open_bookmarks();before=self.f.files[94]
        for args in ((0xffffffff,257,0),(0,0,0),(0,1,0)):
            self.assertEqual(self.f.call('bookmarks_change',*args),0xffffffff)
        self.cpu.mem_write(self.f.syms['playback_scratch_busy'],struct.pack('<I',1))
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,1,0),0xffffffff)
        self.assertEqual(self.f.files[94],before)

    def test_card_removal_does_not_write_another_file(self):
        self.open_bookmarks();before=self.f.files[94]
        self.f.dirs[0]=[END]
        self.assertEqual(self.f.call('bookmarks_change',0xffffffff,1,0),0xffffffff)
        self.assertEqual(self.f.files[94],before)
        self.assertEqual(self.writes,[])
