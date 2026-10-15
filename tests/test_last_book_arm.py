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
