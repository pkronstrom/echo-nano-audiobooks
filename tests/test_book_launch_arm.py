"""Explicit chapter/bookmark launch reuses the native playlist start path."""
import struct
import unittest
import test_playback_session_arm as base

class BookLaunchTests(unittest.TestCase):
    def setUp(self):
        self.s=base.SessionTests();self.s.setUp();self.f=self.s.f;self.cpu=self.s.cpu
        self.cpu.mem_write(0x20001000,'/LIST.M3U'.encode('utf-16le')+b'\0\0')
        self.f.call('book_preview_open',0x20001000)
        self.signature=self.f.call('book_preview_signature')
        # The real menu captures the selected browser path before arming an
        # override. It now shares that retained path with pending launch state.
        self.cpu.mem_write(self.f.syms['playback_launch_buffer'],'/list.m3u\0'.encode('utf-16le'))
    def launch(self,chapter,ms,signature=None):
        self.f.call('playback_launch_override',chapter,ms,self.signature if signature is None else signature)
        self.assertEqual(self.f.call(0x0307acb6),1)
        self.f.call('playback_begin',0x20001000)
        return self.f.call('playback_prepare',3)
    def test_explicit_chapter_and_time_reach_native_start_seek(self):
        self.assertEqual(self.launch(2,1234567),0)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+2,2))[0],2)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(0x0300d1cc,4))[0],1234567)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d1d0,1)),b'\x01')
    def test_changed_playlist_or_invalid_chapter_fails_before_activation(self):
        for chapter,signature in ((3,self.signature),(1,self.signature^1)):
            self.s.events.clear()
            self.assertEqual(self.launch(chapter,0,signature),1)
            self.assertIn(245,self.s.events)
            self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],0)
    def test_missing_explicit_target_does_not_fall_back_to_first_chapter(self):
        self.assertEqual(self.launch(2,9000),0)
        # List entry2 is ONE.MP3, raw directory entry1.
        self.f.dirs[0][1]=bytes([0xe5])+self.f.dirs[0][1][1:]
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),19)
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d1d0,1)),b'\0')
    def test_real_menu_chapter_selection_reaches_explicit_native_queue(self):
        self.cpu.mem_write(0x0300e73c+4,struct.pack('<I',0x0300e9ac))
        self.cpu.mem_write(0x0300e9ac+4,struct.pack('<I',0x0300e73c))
        self.assertEqual(self.f.call('book_menu_open_selected'),1)
        for event in (0x40000004,0x40000040,0x40000004):
            self.assertEqual(self.f.call('book_menu_event',event),1)
        self.assertEqual(self.f.call('book_menu_event',0x40000040),2)
        self.assertEqual(self.s.window,[(3,b'\x01\x00')])
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+2,2))[0],2)
