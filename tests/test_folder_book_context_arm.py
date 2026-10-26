"""Direct file selection retains book identity and explicitly selects its chapter."""
import struct,unittest
import test_playback_session_arm as session
from test_music_filter import fat_entry,END
from test_media_path import lfn
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR
B=0x03005f6c;NODE=0x0300e73c
class FolderBookTests(unittest.TestCase):
 def setUp(self):
  self.s=session.SessionTests();self.s.setUp();self.f=self.s.f;self.cpu=self.s.cpu
  self.cpu.mem_write(NODE+4,struct.pack('<I',0x0300e9ac));self.cpu.mem_write(0x0300e9ac+4,struct.pack('<I',NODE))
  self.f.dirs[0][0]=fat_entry(b'BOOK    M3U',90)
  self.f.dirs[0][-1:]=[*lfn('.audiobook',b'AUDIOB~1   ',92),END]
  self.cpu.mem_write(NODE+12,struct.pack('<I',1));self.cpu.mem_write(NODE+0x4e,b'\x01')
  self.cpu.mem_write(NODE+0x70,'one.mp3\0'.encode('utf-16le'))
  self.cpu.mem_write(NODE+0x4f,fat_entry(b'ONE     MP3',100))
 def title(self):return bytes(self.cpu.mem_read(NODE+0x70,512)).decode('utf-16le').split('\0')[0]
 def open(self,result=1,root=0):self.assertEqual(self.f.call('book_menu_open_audio',root),result)
 def test_direct_audio_uses_playlist_order_and_book_context(self):
  self.open(2);self.assertEqual(self.s.window,[(3,b'\x01\0')])
  self.f.call('playback_begin',0x20001000);self.assertEqual(self.f.call('playback_prepare',3),0)
  self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
  self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,2))
  self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['playback_active'],4))[0],1)
  self.assertEqual(self.f.call('last_book_get',0x20002000),1)
  self.assertEqual(bytes(self.cpu.mem_read(0x20002000,20)).decode('utf-16le'),'/BOOK.M3U\0')
 def test_missing_playlist_refuses_ordinary_launch(self):
  self.f.dirs[0][0]=fat_entry(b'OTHER   M3U',90);self.open()
  self.assertEqual(self.title(),'Book unavailable');self.assertFalse(self.s.window)
 def test_unlisted_or_repeated_audio_refuses_ambiguous_launch(self):
  for data in (b'two.mp3\n',b'one.mp3\none.mp3\n'):
   self.setUp();self.f.files[90]=data;self.open()
   self.assertEqual(self.title(),'Book unavailable');self.assertFalse(self.s.window)
 def test_stale_selected_index_refuses(self):
  self.cpu.mem_write(NODE+12,struct.pack('<I',2));self.open()
  self.assertEqual(self.title(),'Book unavailable');self.assertFalse(self.s.window)
 def test_non_audio_is_not_intercepted(self):
  self.cpu.mem_write(NODE+0x4e,b'\x06');self.assertEqual(self.f.call('book_menu_open_audio',0),0)

 def nested(self):
  self.f.dirs={0:[fat_entry(b'BOOKS      ',10,True),END],10:[fat_entry(b'BOOK    M3U',90),fat_entry(b'DISC       ',20,True),*lfn('.audiobook',b'AUDIOB~1   ',92),END],20:[fat_entry(b'ONE     MP3',100),fat_entry(b'TWO     MP3',101),END]}
  self.f.files[90]=b'disc/two.mp3\ndisc/one.mp3\n'
  self.cpu.mem_write(B+0x1cc,struct.pack('<H',2))
  self.cpu.mem_write(B+56+20,struct.pack('<I',10));self.cpu.mem_write(B+112+20,struct.pack('<I',20))
  self.cpu.mem_write(NODE+8,struct.pack('<II',20,0))
 def test_nested_disc_resolves_parent_book_and_chapter(self):
  self.nested();self.open(2,1)
  self.f.call('playback_begin',0x20001000);self.assertEqual(self.f.call('playback_prepare',3),0)
  self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
  self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,2))
 def test_search_does_not_escape_marked_root(self):
  self.nested();self.open(1,2);self.assertEqual(self.title(),'Book unavailable');self.assertFalse(self.s.window)

 def test_same_name_same_index_replaced_file_is_rejected(self):
  self.f.dirs[0][1]=fat_entry(b'ONE     MP3',110);self.open()
  self.assertEqual(self.title(),'Book unavailable');self.assertFalse(self.s.window)

class MeditationPlaylistTests(unittest.TestCase):
 def test_marked_meditation_playlist_keeps_normal_track_context(self):
  s=session.SessionTests();s.setUp();f=s.f;cpu=s.cpu
  f.dirs[0][-1:]=[*lfn('.meditation',b'MEDITA~1   ',92),END]
  image=session.fixture.Image((session.fixture.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
  def module(index):
   m=image.modules[index]
   for kind in ('code','data'):
    off=image.l2f(m[kind+'_load']);cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
  module(21);f.call('navigation_menu_init');module(31)
  cpu.mem_write(0x0300ec1c+8,struct.pack('<H',3))
  self.assertEqual(f.call('navigation_content_kind'),0xffffffff)
  s.launch()
  self.assertEqual(struct.unpack('<I',cpu.mem_read(f.syms['playback_active'],4))[0],2)
  self.assertEqual(f.call('playback_add_bookmark'),0xffffffff)
  self.assertEqual(f.call('playback_speed_supported'),0)
  self.assertEqual(f.call('last_book_get',0x20002000),0)
  self.assertEqual(f.call('playback_advance',0x0300d85c,1),0)
  self.assertEqual(struct.unpack('<HH',cpu.mem_read(0x0300d85c,4)),(2,2))
