"""Current book menu jumps and bounded seeks share the safe DMA drain lifecycle."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
import test_live_speed_arm as live
import test_book_resume_arm as resume
from test_prepare_book import book

class PlayerBookmarkJumpTests(unittest.TestCase):
 def setUp(self):
  self.t=live.LiveSpeedTests();self.t.setUp();self.f=self.t.f;self.cpu=self.t.cpu;self.a=self.t.a
  self.writes=[];self.short_write=False;self.seeks=[];self.resumes=0
  self.cpu.hook_add(UC_HOOK_CODE,lambda *args:resume.ResumeTests.write(self,*args))
  self.cpu.hook_add(UC_HOOK_CODE,self.hook)
 def hook(self,cpu,address,size,user):
  if address==0x03082524 and not getattr(self,'native_seek',False):self.seeks.append((cpu.reg_read(UC_ARM_REG_R0),cpu.reg_read(UC_ARM_REG_R1)))
  elif address==0x03081f10:self.resumes+=1
  else:return
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 def launch(self,paused=False):
  self.t.launch(6,paused)
  self.f.dirs[0].insert(-1,resume.sized(b'LIST    BMK',94,1024));self.f.files[94]=book.bookmark_bytes()
  self.cpu.mem_write(0x20001000,'/list.m3u\0'.encode('utf-16le'))
  self.f.call('bookmarks_open',0x20001000,self.f.call('playlist_signature'))
  self.assertEqual(self.f.call('bookmarks_change',0xffffffff,2,34000),1)
 def test_folder_and_ordinary_selection_discard_pending_book_rate(self):
  for folder in (False,True):
   self.setUp();self.launch();self.f.call('playback_launch_rate',8)
   if folder:
    q=bytearray(3848)
    for i,cluster in enumerate((100,101)):
     struct.pack_into('<III',q,i*12,0,0,cluster);struct.pack_into('<H',q,3072+i*2,i+1)
    struct.pack_into('<II',q,3840,2,123);self.cpu.mem_write(0x20004000,bytes(q))
    self.assertEqual(self.f.call('playback_folder_launch',0x20004000,1),1)
    self.f.call('playback_begin',0x20001000);self.f.call('playback_prepare',3)
   else:
    self.cpu.mem_write(0x0300e73c+0x70,'one.mp3\0'.encode('utf-16le'))
    self.cpu.mem_write(0x0300e73c+0x4e,b'\x01')
    self.f.call('playback_browser_select',0x20004000)
   self.cpu.mem_write(0x0300e73c+0x70,'list.m3u\0'.encode('utf-16le'))
   self.cpu.mem_write(0x0300e73c+0x4e,b'\x06')
   self.f.call('playback_browser_select',0x20004000);self.f.call('playback_begin',0x20001000)
   self.assertEqual(self.f.call('playback_prepare',3),0)
   self.assertEqual(self.f.call('playback_speed_get'),4)
 def test_mark_jump_keeps_actual_and_desired_rates_and_pause(self):
  self.assertIn('playback_bookmark_jump',self.f.syms)
  for paused in (False,True):
   self.setUp();self.launch(paused);self.f.call('playback_speed_set',8)
   self.assertEqual(self.f.call('playback_bookmarks_open'),1)
   self.assertEqual(self.f.call('playback_bookmark_jump',0),2)
   self.f.call('playback_begin',0x20001000);self.assertEqual(self.f.call('playback_prepare',3),0)
   self.t.half(0x0300d81a,0);self.assertEqual(self.f.call('playback_queue_init',0x0300d85c,1,3,1,0),0)
   self.assertEqual(self.a.get(0x0300d1cc),34000)
   self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d85e,2))[0],2)
   self.assertEqual(self.f.call('playback_speed_actual'),6);self.assertEqual(self.f.call('playback_speed_get'),8)
   self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x0300d81a,2))[0],3 if paused else 0)
 def test_nonempty_target_chapter_can_jump(self):
  self.launch();self.f.dirs[0][2]=resume.sized(b'TWO     MP3',101,1234567)
  self.assertEqual(self.f.call('playback_bookmarks_open'),1)
  self.assertEqual(self.f.call('playback_bookmark_jump',0),2)
 def test_stale_target_and_missing_mark_refuse_before_pause(self):
  self.launch();self.assertEqual(self.f.call('playback_bookmarks_open'),1)
  self.assertEqual(self.f.call('playback_bookmark_jump',59),0xffffffff)
  self.f.dirs[0][2]=resume.sized(b'TWO     MP3',999,42)
  self.assertEqual(self.f.call('playback_bookmark_jump',0),0xffffffff)
  self.assertEqual(self.t.pauses,0);self.assertEqual(self.t.removals,0)
 def test_bookmarks_work_when_codec_has_no_speed_support(self):
  self.launch();self.a.put(0x03039e94,1)
  self.assertEqual(self.f.call('playback_speed_supported'),0)
  self.assertEqual(self.f.call('playback_bookmarks_open'),1)
  self.assertEqual(self.f.call('playback_bookmark_jump',0),2)
 def test_jump_revalidates_changed_mark_after_dma_drain(self):
  self.launch();self.assertEqual(self.f.call('playback_bookmarks_open'),1)
  self.a.dma_result=4;self.a.submit(0x03023174,128);self.a.put(0x600003a0,1<<4)
  self.assertEqual(self.f.call('playback_bookmark_jump',0),1)
  self.assertEqual(self.f.call('bookmarks_change',0,0,0),0)
  self.a.put(0x600003a0,0)
  self.assertEqual(self.f.call('playback_rate_poll'),0xffffffff)
  self.assertEqual(self.t.removals,0)
 def test_seek_clamps_and_preserves_pause_without_relaunch(self):
  self.assertIn('playback_seek_request',self.f.syms)
  for paused in (False,True):
   for time,direction,target in ((3000,-1,0),(12000,-1,2000),(98000,1,99000)):
    self.setUp();self.launch(paused);self.a.put(0x03023094,time)
    self.assertEqual(self.f.call('playback_seek_request',direction),3)
    self.assertEqual(self.seeks,[(251,target)]);self.assertEqual(self.resumes,0 if paused else 1)
    self.assertEqual(self.t.removals,0)
 def test_native_dispatcher_repeated_paused_seeks_advance_source_clock(self):
  image=live.adapter.runtime.Image((live.adapter.runtime.ROOT/'NANOV170.IMG').read_bytes());m=image.modules[33]
  for kind in ('code','data'):
   off=image.l2f(m[kind+'_load']);self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
  from playback_layout import read_patch
  _,address,data=read_patch(live.adapter.runtime.ROOT/'out/playback/speed_seek.patch');self.cpu.mem_write(address,data)
  self.a.put(0x03035178,0x20000301);self.a.put(0x03023098,48000);self.a.put(0x0302312c,16)
  self.launch(True);self.native_seek=True
  self.assertEqual(self.f.call('playback_seek_request',1),3)
  self.assertEqual(self.a.get(0x03023094),22000)
  self.assertEqual(self.f.call('playback_seek_request',1),3)
  self.assertEqual(self.a.get(0x03023094),32000)
  self.assertEqual(self.a.commands.count(14),2)
  self.assertEqual(self.f.call('playback_add_bookmark'),2)
  self.assertEqual(self.f.call('bookmarks_get',1,0x20002400),1)
  self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(1,32000))
  self.assertEqual(self.resumes,0)
 def test_seek_waits_for_dma_and_cancel_does_not_seek(self):
  self.launch();self.a.dma_result=4;self.a.submit(0x03023174,128);self.a.put(0x600003a0,1<<4)
  self.assertEqual(self.f.call('playback_seek_request',-1),1)
  self.assertEqual(self.f.call('playback_seek_request',1),0xffffffff)
  self.assertEqual(self.seeks,[]);self.f.call('playback_rate_cancel');self.a.put(0x600003a0,0)
  self.assertEqual(self.f.call('playback_rate_poll'),0xffffffff);self.assertEqual(self.seeks,[])

 def test_player_uninit_cancels_seek_but_preserves_committed_jump(self):
  self.assertIn('playback_player_uninit',self.f.syms)
  def native_uninit(cpu,address,size,user):
   if address==0x03079512:cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  self.cpu.hook_add(UC_HOOK_CODE,native_uninit)
  self.launch();self.a.dma_result=4;self.a.submit(0x03023174,128);self.a.put(0x600003a0,1<<4)
  self.assertEqual(self.f.call('playback_seek_request',1),1)
  self.f.call('playback_player_uninit');self.a.put(0x600003a0,0)
  self.assertEqual(self.f.call('playback_rate_poll'),0xffffffff);self.assertEqual(self.seeks,[])
  self.assertEqual(self.f.call('playback_bookmarks_open'),1)
  self.assertEqual(self.f.call('playback_bookmark_jump',0),2)
  self.f.call('playback_player_uninit')
  self.assertEqual(self.f.call('playback_rate_poll'),2)
