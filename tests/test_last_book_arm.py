"""Last-book identity is independent of preview and validates live storage."""
import struct
import unittest
import test_playback_session_arm as base

class LastBookTests(unittest.TestCase):
    def setUp(self):
        self.s=base.SessionTests();self.s.setUp();self.f=self.s.f;self.cpu=self.s.cpu
    def remember(self,path='/list.m3u'):
        self.cpu.mem_write(0x20001000,(path+'\0').encode('utf-16le'))
        self.f.call('last_book_remember',0x20001000)
    def get(self):return self.f.call('last_book_get',0x20002000)
    def test_remember_and_lookup_validates_physical_identity(self):
        self.assertEqual(self.get(),0)
        self.remember();self.assertEqual(self.get(),1)
        self.assertEqual(bytes(self.cpu.mem_read(0x20002000,20)),'/list.m3u\0'.encode('utf-16le'))
        self.f.dirs[0][0]=base.fat_entry(b'LIST    M3U',91)
        self.assertEqual(self.get(),0)
    def test_invalid_candidate_does_not_replace_last_book(self):
        self.remember();self.remember('/missing.m3u');self.assertEqual(self.get(),1)
    def test_storage_change_and_payload_reload_invalidate(self):
        self.remember();self.cpu.mem_write(0x0300d173,b'\x03');self.assertEqual(self.get(),0)
        self.cpu.mem_write(0x0300d173,b'\0');self.assertEqual(self.get(),1)
        self.f.call('playback_init');self.assertEqual(self.get(),0)

    def test_ordinary_playlist_does_not_become_last_book(self):
        self.s.launch()
        self.assertEqual(self.get(),0)
    def test_snapshot_copies_signature_with_path(self):
        self.s.launch();self.remember()
        self.assertEqual(self.f.call('last_book_snapshot',0x20002000,0x20003000),1)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x20003000,4))[0],self.f.call('playlist_signature'))

    def label(self):
        self.assertIn('last_book_label',self.f.syms)
        self.cpu.mem_write(0x20002000,b'Z'*514)
        self.f.call('last_book_label',0x20002000)
        self.assertEqual(bytes(self.cpu.mem_read(0x20002200,2)),b'ZZ')
        return bytes(self.cpu.mem_read(0x20002000,512)).decode('utf-16le').split('\0')[0]
    def test_continue_label_names_playlist_or_generic_book_folder(self):
        from test_media_path import lfn
        from test_music_filter import END
        self.remember('/list.m3u');self.assertEqual(self.label(),'Continue list')
        self.f.dirs[0].insert(-1,base.fat_entry(b'BOOKS      ',20,directory=True))
        self.f.dirs[20]=[base.fat_entry(b'BOOK    M3U',90),END]
        self.remember('/Books/BOOK.M3U');self.assertEqual(self.label(),'Continue Books')
        self.f.dirs[0].insert(-1,base.fat_entry(b'BOOK    M3U',90))
        self.remember('/BOOK.M3U');self.assertEqual(self.label(),'Continue BOOK')
    def test_continue_label_bounds_unicode_without_splitting_surrogate(self):
        from test_media_path import lfn
        from test_music_filter import END
        for name in ('雪の本', 'a'*245+'😀'):
            self.f.dirs[0]=[*lfn(name+'.m3u',b'BOOK~1  M3U',90),END]
            self.remember('/'+name+'.m3u')
            label=self.label()
            self.assertTrue(label.startswith('Continue '))
            self.assertLessEqual(len(label.encode('utf-16le'))//2,255)
            self.assertTrue(('Continue '+name).startswith(label))
