"""Browser-generated ordered queues use physical identities and audio-only ranks."""
import struct,unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR
import test_browser_sort_adapter_arm as fixture
from test_music_filter import fat_entry,exfat_entry,END
from test_media_path import lfn

class BrowserFolderQueueTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.BrowserSortAdapterTests();self.f.setUp();self.f.real_native=True
  symbols={n:int(v,16) for v,t,n in (l.split() for l in (fixture.ROOT/'out/playback/playback.nm').read_text().splitlines())}
  self.launch=symbols['playback_folder_launch'];self.calls=[]
  self.f.cpu.hook_add(UC_HOOK_CODE,self.capture,begin=self.launch,end=self.launch)
 def capture(self,c,a,size,_):
  ptr=c.reg_read(UC_ARM_REG_R0);pos=c.reg_read(UC_ARM_REG_R1)
  self.calls.append((bytes(c.mem_read(ptr,3848)),pos))
  c.reg_write(UC_ARM_REG_R0,1);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 def directory(self,exfat,names):
  f=self.f;f.directory(exfat);f.entries=[];self.raw={}
  for i,name in enumerate(names):
   isdir=name=='Subfolder'
   rows=exfat_entry(name,100+i,isdir) if exfat else lfn(name,(f'T{i:07d}'+('   ' if isdir else name[-3:].upper())).encode(),100+i,isdir)
   self.raw[name]=len(f.entries) if exfat else len(f.entries)+len(rows)-1
   f.entries+=rows
  f.entries.append(END)
  f.cpu.mem_write(0x0300ec1c+8,struct.pack('<H',3))
  f.call('browser_sort_count',0x03005a5e,fixture.FOLDER,3)
 def test_cd_order_and_selected_position_exclude_subfolders(self):
  for fs in (False,True):
   with self.subTest(exfat=fs):
    self.directory(fs,['CD2-3.mp3','CD1-1.mp3','Subfolder','CD10-1.mp3','CD2-1.mp3'])
    self.f.call('browser_sort_enumerate',0x03005a5e,fixture.NODE,fixture.FOLDER,0,3)
    self.assertEqual(self.f.label(fixture.NODE+624),'CD1-1.mp3')
    self.assertEqual(self.f.call('browser_sort_select',fixture.NODE+624),2)
    q,pos=self.calls[-1];count=struct.unpack_from('<I',q,3840)[0]
    self.assertEqual((pos,count),(1,4))
    self.assertEqual(list(struct.unpack_from('<4H',q,3072)),[self.raw[x] for x in ('CD1-1.mp3','CD2-1.mp3','CD2-3.mp3','CD10-1.mp3')])
    self.assertEqual([struct.unpack_from('<I',q,i*12+8)[0] for i in range(4)],[101,104,100,103])
 def test_directory_selection_keeps_native_navigation(self):
  self.directory(False,['Subfolder','CD1.mp3'])
  self.f.call('browser_sort_enumerate',0x03005a5e,fixture.NODE,fixture.FOLDER,0,3)
  self.assertEqual(self.f.call('browser_sort_select',fixture.NODE),1);self.assertFalse(self.calls)
 def test_oversized_folder_is_not_truncated(self):
  self.directory(False,[f'Track{i}.mp3' for i in range(257)])
  self.f.call('browser_sort_enumerate',0x03005a5e,fixture.NODE,fixture.FOLDER,0,3)
  self.assertEqual(self.f.call('browser_sort_select',fixture.NODE),0);self.assertFalse(self.calls)
 def test_playlist_entries_do_not_join_folder_audio_queue(self):
  self.directory(True,['CD2.mp3','BOOK.m3u','CD1.mp3'])
  self.f.cpu.mem_write(0x03047000,b'MP3M3U\0')
  self.f.call('browser_sort_count',0x03047000,fixture.FOLDER,3)
  self.f.call('browser_sort_enumerate',0x03047000,fixture.NODE,fixture.FOLDER,0,3)
  self.assertEqual(self.f.label(fixture.NODE),'BOOK.m3u')
  self.assertEqual(self.f.call('browser_sort_select',fixture.NODE),1)
  self.assertEqual(self.f.call('browser_sort_select',fixture.NODE+624),2)
  q,pos=self.calls[-1];self.assertEqual((struct.unpack_from('<I',q,3840)[0],pos),(2,1))
 def test_large_raw_index_is_rejected_without_truncation(self):
  f=self.f;f.real_native=False;f.directory(False)
  f.entries=[b'\xe5'+bytes(31)]*65536+[fat_entry(b'CD1     MP3',100),END]
  f.cpu.mem_write(fixture.FOLDER,struct.pack('<3H',1,1,0))
  f.cpu.mem_write(0x0300ec1c+8,struct.pack('<H',3))
  f.call('browser_sort_enumerate',0,fixture.NODE,fixture.FOLDER,0,3)
  self.assertEqual(f.word(fixture.NODE+12),65536)
  self.assertEqual(f.call('browser_sort_select',fixture.NODE),0);self.assertFalse(self.calls)

# Whole launch path: sorted browser row -> native callback -> resident queue.
import test_playback_session_arm as session
class BrowserFolderLaunchTests(unittest.TestCase):
 setUp=session.SessionTests.setUp
 def hook(self,c,a,size,user):
  if getattr(self,'native_window',False):
   if a==0x0306b26a:return # execute actual window request, not aggregate stub
   if a==0x0306b6bc:self.fail('window request must defer module loading')
   if a in (0x030595b4,0x0305965e,0x0306a33c,0x0306a2ec,0x03059558,0x03053a4e):
    c.reg_write(UC_ARM_REG_R0,0);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR));return
  session.SessionTests.hook(self,c,a,size,user)
 def test_first_visible_cd_is_one_and_automatic_next_is_cd_two(self):
  self.f.syms.update({n:int(v,16) for v,t,n in (l.split() for l in (fixture.ROOT/'out/browser_sort/browser_sort.nm').read_text().splitlines())})
  self.f.dirs={0:[fat_entry(b'CD2     MP3',100),fat_entry(b'CD1     MP3',101),END]}
  self.f.files={}
  self.cpu.mem_write(fixture.NODE+4,struct.pack('<I',fixture.NODE+624))
  self.cpu.mem_write(fixture.NODE+624+4,struct.pack('<I',fixture.NODE))
  self.cpu.mem_write(fixture.FOLDER,bytes(56))
  self.f.call('browser_sort_count',0x03005a5e,fixture.FOLDER,3)
  self.f.call('browser_sort_enumerate',0x03005a5e,fixture.NODE,fixture.FOLDER,0,3)
  self.assertEqual(bytes(self.cpu.mem_read(fixture.NODE+112,14)).decode('utf-16le'),'CD1.MP3')
  self.assertEqual(self.f.call(0x0307acb6),1)
  self.f.call('playback_begin',0x20001000)
  self.assertEqual(self.f.call('playback_prepare',3),0)
  self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
  self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,1))
  self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],101)
  self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
  self.f.call(0x03081786,1)
  self.assertEqual(struct.unpack('<HH',self.cpu.mem_read(0x0300d85c,4)),(2,2))
  self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85c+0x2e,2))[0],100)

 def test_native_window_request_returns_before_overlay_replacement(self):
  self.native_window=True
  before=bytes(self.cpu.mem_read(0x03079418,9308))
  self.test_first_visible_cd_is_one_and_automatic_next_is_cd_two()
  self.assertEqual(bytes(self.cpu.mem_read(0x03079418,9308)),before)
  self.assertEqual(self.cpu.mem_read(0x03005b8c,1),b'\x03')
