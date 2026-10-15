"""Preview another book without changing the decoder or its journal targets."""
import struct
import test_bookmark_session_arm as base
from test_book_resume_arm import sized

class BookPreviewTests(base.BookmarkSessionTests):
    def preview(self,name):
        self.cpu.mem_write(0x20001000,name.encode('utf-16le')+b'\0\0')
        return self.f.call('book_preview_open',0x20001000)

    def test_other_book_preview_preserves_playback_and_bookmark_target(self):
        self.f.dirs[0].insert(-1,sized(b'OTHER   M3U',95,8))
        self.f.files[95]=b'one.mp3\n'
        before=bytes(self.cpu.mem_read(0x0300d85c,256))
        signature=self.f.call('playlist_signature')
        self.assertEqual(self.preview('/OTHER.M3U'),1)
        self.assertEqual(self.f.call('book_preview_count'),1)
        self.assertEqual(self.f.call('playlist_count'),2)
        self.assertEqual(self.f.call('playlist_signature'),signature)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d85c,256)),before)
        self.assertEqual(self.add(),1)
        self.assertEqual(self.writes[-1][0],94)

    def test_preview_reads_manual_marks_without_opening_active_companion(self):
        self.assertEqual(self.add(),1)
        self.assertEqual(self.preview('/LIST.M3U'),2)
        self.assertEqual(self.f.call('book_preview_marks'),1)
        self.assertEqual(self.f.call('book_preview_mark',0,0x20002400),1)
        self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(1,1234567))
        self.assertEqual(self.f.call('book_preview_mark',1,0x20002400),0)

    def test_failed_preview_leaves_active_queue_intact(self):
        signature=self.f.call('playlist_signature')
        self.assertEqual(self.preview('/MISSING.M3U'),0xffffffff)
        self.assertEqual(self.f.call('book_preview_count'),0)
        self.assertEqual(self.f.call('playlist_signature'),signature)
        self.assertEqual(self.add(),1)

    def test_preview_delete_updates_sd_and_preserves_active_companion(self):
        self.add();self.cpu.mem_write(0x03023090+4,struct.pack('<I',9000));self.add()
        self.preview('/LIST.M3U')
        self.assertEqual(self.f.call('book_preview_delete',0),1)
        self.assertEqual(self.f.call('book_preview_marks'),1)
        self.assertEqual(self.f.call('bookmarks_get',0,0x20002400),1)
        self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(1,9000))
        self.assertEqual(self.add(),2)

    def test_stale_delete_rejects_newer_bookmark_journal(self):
        self.add();self.preview('/LIST.M3U');self.add()
        before=self.f.files[94]
        self.assertEqual(self.f.call('book_preview_delete',0),0xffffffff)
        self.assertEqual(self.f.files[94],before)

    def test_bookmark_writers_reject_overlapping_transactions(self):
        self.add();self.preview('/LIST.M3U');before=self.f.files[94]
        self.assertEqual(self.f.call('journal_try_write'),1)
        self.assertEqual(self.f.call('book_preview_delete',0),0xffffffff)
        self.assertEqual(self.add(),0xffffffff)
        self.assertEqual(self.f.files[94],before)
        self.f.call('journal_end_write')
        self.assertEqual(self.f.call('book_preview_delete',0),1)

    def test_preview_uses_private_scratch_while_player_parser_is_busy(self):
        scratch=self.f.syms['playback_scratch'];busy=self.f.syms['playback_scratch_busy']
        before=bytes(range(256))*4
        self.cpu.mem_write(scratch,before);self.cpu.mem_write(busy,struct.pack('<I',1))
        self.assertEqual(self.preview('/LIST.M3U'),2)
        self.assertEqual(bytes(self.cpu.mem_read(scratch,1024)),before)
        self.assertEqual(bytes(self.cpu.mem_read(busy,4)),struct.pack('<I',1))

    def test_preview_b_preserves_a_automatic_resume_target(self):
        from test_book_resume_arm import blank
        self.f.dirs[0].insert(-1,sized(b'LIST    RSM',96,1024));self.f.files[96]=blank()
        self.cpu.mem_write(0x20001000,'/LIST.M3U'.encode('utf-16le')+b'\0\0')
        self.f.call('book_load',0x20001000,0x20002400)
        self.f.call('book_save')
        self.f.dirs[0].insert(-1,sized(b'OTHER   M3U',95,8));self.f.files[95]=b'one.mp3\n'
        self.assertEqual(self.preview('/OTHER.M3U'),1)
        self.cpu.mem_write(0x03023090+4,struct.pack('<I',9000));self.f.call('book_save')
        self.assertEqual(self.writes[-1][0],96)
        self.assertEqual(self.preview('/LIST.M3U'),2)
        self.assertEqual(self.f.call('book_preview_resume',0x20002400),1)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x20002400,4))[0],9000)
