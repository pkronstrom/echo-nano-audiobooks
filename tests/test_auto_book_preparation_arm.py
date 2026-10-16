"""Cold automatic preparation against stock native code and sector fixtures."""
import struct
import unittest
import zlib
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
from experiments.native_file_creation.disk_harness import NativeDisk
from test_media_path import lfn
from test_music_filter import exfat_entry
from test_content_roots import checksum
from rknano_fw import Image

ROOT=Path(__file__).resolve().parents[1]

class AutomaticBookPreparationTests(unittest.TestCase):
 def setUp(self):
  self.symbols={n:int(a,16) for a,t,n in (line.split() for line in (ROOT/'out/browser_sort/browser_sort.nm').read_text().splitlines())}
  self.assertIn('browser_prepare_book',self.symbols,'automatic preparation is not integrated')
  self.resident={n:int(a,16) for a,t,n in (line.split() for line in (ROOT/'out/playback/playback.nm').read_text().splitlines())}
 def fixture(self,fs,names=('CD2.mp3','CD1.mp3'),sectors_per_cluster=4,clusters=64):
  disk=NativeDisk(fs,sectors_per_cluster=sectors_per_cluster,clusters=clusters)
  image=Image((ROOT/'NANOV170.IMG').read_bytes());module=image.modules[31]
  for kind in ('code','data'):
   offset=image.l2f(module[kind+'_load']);disk.cpu.mem_write(module[kind+'_exec'],bytes(image.d[offset:offset+module[kind+'_len']]))
  disk.cpu.mem_write(0x03092400,(ROOT/'out/playback/playback.bin').read_bytes())
  disk.cpu.mem_write(0x0307b874,(ROOT/'out/browser_sort/browser_sort.bin').read_bytes())
  def ignore_watchdog(cpu,a,size,_):
   cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  disk.cpu.hook_add(UC_HOOK_CODE,ignore_watchdog,begin=0x03065800,end=0x03065800)
  disk.set_fat(10,0x0fffffff)
  def entries(name,cluster,directory=False):
   if fs=='exfat':
    rows=[bytearray(x) for x in exfat_entry(name,cluster,directory)]
    struct.pack_into('<Q',rows[1],8,disk.SPC*512 if directory else 128)
    struct.pack_into('<Q',rows[1],24,disk.SPC*512 if directory else 128)
    return checksum([bytes(x) for x in rows])
   rows=lfn(name,b'BOOKDIR    ' if directory else b'CHAP~1  MP3',cluster,directory)
   rows=[bytearray(x) for x in rows];struct.pack_into('<I',rows[-1],28,0 if directory else 128)
   return [bytes(x) for x in rows]
  if fs=='exfat':
   bitmap=bytearray(32);bitmap[0]=0x81
   struct.pack_into('<I',bitmap,20,2);struct.pack_into('<I',bitmap,24,(disk.CLUSTERS+7)//8)
   disk.set_entry(0,bytes(bitmap))
  for i,row in enumerate(entries('Book',10,True),1 if fs=='exfat' else 0):disk.set_entry(i,row)
  child=(disk.DATA_LBA+(10-2)*disk.SPC)*512
  rows=[]
  for i,name in enumerate(names):
   cluster=20+i;disk.set_fat(cluster,0x0fffffff);rows+=entries(name,cluster)
   if fs=='exfat':disk.sectors[disk.DATA_LBA*512+(cluster-2)//8]|=1<<((cluster-2)%8)
  disk.sectors[child:child+len(rows)*32]=b''.join(rows)
  if fs=='exfat':disk.sectors[disk.DATA_LBA*512+1]|=1 # child cluster10
  parent=struct.pack('<III',10,disk.SPC*512,0)+b'\x01\x10'+bytes(28)
  disk.cpu.mem_write(0x20008000,parent)
  disk.cpu.mem_write(0x20009000,'/Book\0'.encode('utf-16le'))
  return disk,child
 def invoke(self,disk):
  return disk.call(self.symbols['browser_prepare_book'],0x20008000,0x20009000,disk.DEV,(3 if disk.filesystem=='exfat' else 2)<<8)
 def read_file(self,disk,path):
  disk.cpu.mem_write(0x2000a000,(path+'\0').encode('utf-16le'))
  self.assertEqual(disk.call(self.resident['playback_lookup'],0x2000a000,0x2000a400),1)
  size=struct.unpack('<I',disk.cpu.mem_read(0x2000a400+24,4))[0]
  self.last_file_cluster=struct.unpack('<I',disk.cpu.mem_read(0x2000a400+20,4))[0]
  handle=disk.call(self.resident['playback_open'],0x2000a400);self.assertGreaterEqual(handle,0)
  self.assertEqual(disk.call(self.resident['playback_read'],handle,0,0x2000b000,size),size)
  data=bytes(disk.cpu.mem_read(0x2000b000,size));disk.call(self.resident['playback_close'],handle)
  return data
 def test_two_tracks_prepare_and_repeated_entry_preserves_all_bytes(self):
  for fs in ('fat','exfat'):
   with self.subTest(fs=fs):
    disk,_=self.fixture(fs);self.assertEqual(self.invoke(disk),1)
    playlist=self.read_file(disk,'/Book/BOOK.M3U')
    self.assertEqual(playlist,b'#EXTM3U\n#ECHO-BOOK-1\n./CD1.mp3\n./CD2.mp3\n#ECHO-END\n')
    for ext,magic in [('RSM',0x31524e45),('BMK',0x31424e45)]:
     data=self.read_file(disk,'/Book/BOOK.'+ext);self.assertEqual(len(data),1024)
     for slot in (data[:512],data[512:]):
      self.assertEqual(struct.unpack_from('<I',slot)[0],magic)
      self.assertEqual(struct.unpack_from('<I',slot,508)[0],zlib.crc32(slot[:508]))
    before=bytes(disk.sectors);writes=len(disk.sector_writes)
    self.assertEqual(self.invoke(disk),1)
    self.assertEqual(bytes(disk.sectors),before);self.assertEqual(len(disk.sector_writes),writes)
 def test_custom_playlist_suppresses_generation_and_all_writes(self):
  for fs in ('fat','exfat'):
   disk,_=self.fixture(fs,('Custom.m3u','One.mp3'))
   before=bytes(disk.sectors)
   self.assertEqual(self.invoke(disk),0);self.assertEqual(bytes(disk.sectors),before)
   self.assertFalse(disk.sector_writes)
 def test_no_direct_audio_causes_no_writes(self):
  for fs in ('fat','exfat'):
   disk,_=self.fixture(fs,())
   self.assertEqual(self.invoke(disk),0);self.assertFalse(disk.sector_writes)
 def test_wrong_device_lease_refuses_without_writes(self):
  for fs in ('fat','exfat'):
   disk,_=self.fixture(fs)
   self.assertLess(disk.call(self.symbols['browser_prepare_book'],0x20008000,0x20009000,disk.DEV+1,(3 if fs=='exfat' else 2)<<8),0)
   self.assertFalse(disk.sector_writes)
 def test_temporary_collision_and_long_paths_are_preserved(self):
  for fs in ('fat','exfat'):
   for names,path in [(('BOOK.TMP','One.mp3'),'/Book'),(('One.mp3',),'/'+'x'*246)]:
    with self.subTest(fs=fs,names=names,path_length=len(path)):
     disk,_=self.fixture(fs,names);disk.cpu.mem_write(0x20009000,(path+'\0').encode('utf-16le'))
     before=bytes(disk.sectors);self.assertLess(self.invoke(disk),0)
     self.assertEqual(bytes(disk.sectors),before);self.assertFalse(disk.sector_writes)
 def test_crc_valid_but_malformed_bookmarks_are_preserved_and_reported(self):
  for fs in ('fat','exfat'):
   disk,_=self.fixture(fs);self.assertEqual(self.invoke(disk),1)
   data=bytearray(self.read_file(disk,'/Book/BOOK.BMK'))
   for offset in (0,512):
    struct.pack_into('<I',data,offset+12,61)
    struct.pack_into('<I',data,offset+508,zlib.crc32(data[offset:offset+508]))
   start=(disk.DATA_LBA+(self.last_file_cluster-2)*disk.SPC)*512
   disk.sectors[start:start+1024]=data;disk.call(0x0305bddc)
   before=bytes(disk.sectors);writes=len(disk.sector_writes)
   self.assertLess(self.invoke(disk),0);self.assertEqual(bytes(disk.sectors),before)
   self.assertEqual(len(disk.sector_writes),writes)
 def test_saved_resume_speed_and_bookmarks_are_not_reinitialized(self):
  for fs in ('fat','exfat'):
   disk,_=self.fixture(fs);self.assertEqual(self.invoke(disk),1)
   for extension in ('RSM','BMK'):
    data=bytearray(self.read_file(disk,'/Book/BOOK.'+extension))
    for offset in (0,512):
     struct.pack_into('<III',data,offset+4,7,0x12345678,1)
     if extension=='RSM':struct.pack_into('<I',data,offset+32,0x53504400+6)
     else:struct.pack_into('<II',data,offset+16,1,123456)
     struct.pack_into('<I',data,offset+508,zlib.crc32(data[offset:offset+508]))
    start=(disk.DATA_LBA+(self.last_file_cluster-2)*disk.SPC)*512
    disk.sectors[start:start+1024]=data;disk.call(0x0305bddc)
   before=bytes(disk.sectors);writes=len(disk.sector_writes)
   self.assertEqual(self.invoke(disk),1);self.assertEqual(bytes(disk.sectors),before)
   self.assertEqual(len(disk.sector_writes),writes)
 def test_authoritative_and_custom_playlists_after_over_256_audio_entries(self):
  tracks=tuple(f'Track{i}.mp3' for i in range(257))
  for fs in ('fat','exfat'):
   for playlist,result in [('Custom.m3u',0),('BOOK.M3U',1)]:
    with self.subTest(fs=fs,playlist=playlist):
     disk,_=self.fixture(fs,tracks+(playlist,),sectors_per_cluster=64,clusters=512)
     self.assertEqual(self.invoke(disk),result)
     if not result:self.assertFalse(disk.sector_writes)
     else:self.assertEqual(self.read_file(disk,'/Book/BOOK.M3U'),bytes(128))
 def test_multicluster_directories_bypass_generation_and_keep_native_entry(self):
  # A playlist beyond cluster one must never be shadowed or prevented from
  # reaching the existing native/resident folder-entry path.
  for fs in ('fat','exfat'):
   for playlist in ('BOOK.M3U','Custom.m3u'):
    with self.subTest(fs=fs,playlist=playlist):
     disk,child=self.fixture(fs,('One.mp3',))
     disk.set_fat(10,11);disk.set_fat(11,0x0fffffff)
     if fs=='exfat':disk.sectors[disk.DATA_LBA*512+1]|=2
     disk.cpu.mem_write(0x20008004,struct.pack('<I',disk.SPC*1024))
     second=child+disk.SPC*512
     rows=checksum(exfat_entry(playlist,30)) if fs=='exfat' else lfn(playlist,b'BOOK    M3U',30)
     disk.sectors[second:second+len(rows)*32]=b''.join(rows)
     before=bytes(disk.sectors)
     self.assertEqual(self.invoke(disk),0)
     self.assertEqual(bytes(disk.sectors),before);self.assertFalse(disk.sector_writes)

if __name__=='__main__':unittest.main()
