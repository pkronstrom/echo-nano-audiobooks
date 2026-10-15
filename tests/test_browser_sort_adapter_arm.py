"""Browser extension execution with physical FAT/exFAT entry reads."""
import struct,unittest
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *
from test_music_filter import END,exfat_entry
from test_music_arm import Image
from test_media_path import lfn
ROOT=Path(__file__).resolve().parents[1]
B=0x03005f6c; NODE=0x0300e73c; FOLDER=B+12; STOP=0x03048000
class BrowserSortAdapterTests(unittest.TestCase):
 def setUp(self):
  self.sym={}
  for line in (ROOT/'out/browser_sort/browser_sort.nm').read_text().splitlines():
   a,_,n=line.split();self.sym[n]=int(a,16)
  self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB);self.cpu.mem_map(0x03000000,0x100000)
  image=Image((ROOT/'NANOV170.IMG').read_bytes())
  for module in (0,31):
   m=image.modules[module]
   for kind in ('code','data'):
    offset=image.l2f(m[kind+'_load']);self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[offset:offset+m[kind+'_len']]))
  self.real_native=False
  self.cpu.mem_write(0x0307b874,(ROOT/'out/browser_sort/browser_sort.bin').read_bytes())
  self.cpu.mem_write(B,struct.pack('<I',NODE));self.w(NODE+4,NODE+624);self.w(NODE+624+4,NODE)
  for address in (STOP,0x03079cee,0x030798c8,0x0306a40e,0x0306a466,0x03065800,0x0305b3ea,0x0305b2a2,0x0305dcb4,0x03079484,0x0305fa94):
   self.cpu.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)
  self.reads=0;self.fail=None;self.return_to=STOP
 def w(self,p,n):self.cpu.mem_write(p,struct.pack('<I',n))
 def word(self,p):return struct.unpack('<I',self.cpu.mem_read(p,4))[0]
 def call(self,name,*args):
  sp=0x03048000-1024
  for i,v in enumerate(args):
   if i<4:self.cpu.reg_write(UC_ARM_REG_R0+i,v)
   else:self.w(sp+(i-4)*4,v)
  self.cpu.reg_write(UC_ARM_REG_SP,sp);self.cpu.reg_write(UC_ARM_REG_LR,self.return_to|1)
  self.cpu.emu_start(self.sym[name]|1,STOP,count=200000000)
  self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),self.return_to,"emulator instruction budget exhausted")
  return self.cpu.reg_read(UC_ARM_REG_R0)
 def hook(self,c,a,size,_):
  if a==self.return_to:c.emu_stop();return
  r=[c.reg_read(UC_ARM_REG_R0+i) for i in range(4)];result=0
  if a in (0x0306a40e,0x0306a466,0x03065800):pass
  elif a in (0x0305b3ea,0x0305b2a2):
   self.reads+=1;idx=r[2]
   result=8 if idx==self.fail else 0
   if not result:c.mem_write(r[0],self.entries[idx] if idx<len(self.entries) else END)
  elif a==0x0305dcb4:
   if self.real_native:return
   idx=self.word(r[1]+4)
   while idx<len(self.entries):
    entry=self.entries[idx];idx+=1
    accept=entry[0]==0x85 if self.fs else entry[0] not in (0,0xe5,46) and not(entry[11]&10)
    if accept:
     raw=bytearray(entry)
     if self.fs:
      raw=bytearray(32);raw[11]=entry[4];stream=self.entries[idx];raw[20:22]=stream[22:24];raw[26:28]=stream[20:22]
     c.mem_write(r[0],bytes(raw));self.w(r[1]+4,idx);break
   else:result=9
  elif a==0x03079484:
   if self.real_native:return
   result=0x03047000;c.mem_write(result,b'\x01')
  elif a==0x0305fa94:
   if self.real_native:return
  else:return
  c.reg_write(UC_ARM_REG_R0,result);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 def directory(self,fs):
  self.fs=fs;self.cpu.mem_write(0x03076b24,bytes([3 if fs else 2]));self.entries=[];self.keys=[]
  for i,name in enumerate(('CD2-3','CD1-1','CD10-1','CD2-1')):
   rows=exfat_entry(name,100+i,True) if fs else lfn(name,('CD%d        '%i).encode()[:11],100+i,True)
   self.keys.append(len(self.entries) if fs else len(self.entries)+len(rows)-1);self.entries+=rows
  self.entries.append(END);self.cpu.mem_write(FOLDER,struct.pack('<3H',4,0,4));self.w(FOLDER+8,2);self.w(FOLDER+12,2)
 def label(self,node):return bytes(self.cpu.mem_read(node+112,512)).decode('utf-16le').split('\0')[0]
 def test_natural_rows_preserve_raw_identity(self):
  for fs in (False,True):
   self.directory(fs);self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
   self.assertEqual([self.label(NODE),self.label(NODE+624)],['CD1-1','CD2-1'])
   self.assertEqual([self.word(NODE+12),self.word(NODE+624+12)],[self.keys[1],self.keys[3]])
 def test_read_failure_clears_both_nodes(self):
  self.directory(False);self.fail=self.keys[1]
  self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
  self.assertEqual(self.label(NODE),'');self.assertEqual(self.label(NODE+624),'')

 def test_back_restores_child_identity_for_both_filesystems(self):
  for fs in (False,True):
   self.directory(fs);self.w(B+56+20,0);self.w(B+56+24,0);self.w(B+56+(24 if fs else 20),100);self.return_to=0x03079cee
   self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
   self.assertEqual(self.label(NODE),'CD2-3')
   self.assertEqual(struct.unpack('<H',self.cpu.mem_read(B+0x1ce,2))[0],2)
 def test_reentry_maps_physical_selection_to_natural_rank(self):
  self.directory(False);self.return_to=0x030798c8
  self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
  self.assertEqual(self.label(NODE),'CD2-3')
  self.assertEqual(self.word(NODE+12),self.keys[0])
 def test_count_mismatch_invalidates_both_outputs(self):
  self.directory(False);self.cpu.mem_write(FOLDER,struct.pack('<H',5))
  self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
  self.assertEqual(self.label(NODE),'');self.assertEqual(self.label(NODE+624),'')
  self.assertEqual(self.call('browser_sort_validate',NODE),0)
 def test_stale_entry_replacement_refuses_action(self):
  self.directory(False);self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
  self.assertEqual(self.call('browser_sort_validate',NODE),1)
  key=self.keys[1];entry=bytearray(self.entries[key]);entry[26]^=1;self.entries[key]=bytes(entry)
  self.assertEqual(self.call('browser_sort_validate',NODE),0)
 def test_cached_paging_only_reads_chosen_entries(self):
  self.directory(False);self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
  initial=self.reads;self.call('browser_sort_enumerate',0,NODE,FOLDER,2,3)
  self.assertEqual([self.label(NODE),self.label(NODE+624)],['CD2-3','CD10-1'])
  self.assertLess(self.reads-initial,initial)

 def test_device_switch_refuses_displayed_identity(self):
  self.directory(False);self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
  self.cpu.mem_write(0x0300d173,b'\x01')
  self.assertEqual(self.call('browser_sort_validate',NODE),0)
 def test_filesystem_switch_refuses_displayed_identity(self):
  self.directory(False);self.call('browser_sort_enumerate',0,NODE,FOLDER,0,3)
  self.cpu.mem_write(0x03076b24,b'\x03')
  self.assertEqual(self.call('browser_sort_validate',NODE),0)

 def test_real_native_iterator_count_classifier_fat_and_exfat(self):
  self.real_native=True
  for fs in (False,True):
   self.directory(fs);self.entries=[];self.keys=[]
   for i,label in enumerate(('CD2-3.mp3','CD1-1.mp3','CD10-1.mp3','CD2-1.mp3')):
    rows=exfat_entry(label,100+i) if fs else lfn(label,('CD%d     MP3'%i).encode(),100+i)
    self.keys.append(len(self.entries) if fs else len(self.entries)+len(rows)-1);self.entries+=rows
   self.entries.append(END)
   self.call('browser_sort_count',0x03005a5e,FOLDER,3)
   self.assertEqual(struct.unpack('<3H',self.cpu.mem_read(FOLDER,6)),(4,4,0))
   self.call('browser_sort_enumerate',0x03005a5e,NODE,FOLDER,0,3)
   self.assertEqual([self.label(NODE),self.label(NODE+624)],['CD1-1.mp3','CD2-1.mp3'])
   self.assertEqual(self.word(NODE+12),self.keys[1]);self.assertEqual(self.cpu.mem_read(NODE+0x4e,1),b'\x01')

 def test_exfat_directory_selection_survives_native_alias_clock_change(self):
  self.real_native=True;self.directory(True)
  self.entries=[*exfat_entry('The Gateway Experience',100,True),END]
  self.w(0x0300d144,123)
  self.call('browser_sort_count',0x03005a5e,FOLDER,3)
  self.call('browser_sort_enumerate',0x03005a5e,NODE,FOLDER,0,3)
  self.assertEqual(self.label(NODE),'The Gateway Experience')
  self.assertEqual(self.call('browser_sort_validate',NODE),1)
  self.w(0x0300d144,456)
  self.assertEqual(self.call('browser_sort_validate',NODE),1)

 def test_exfat_stable_identity_changes_still_refuse_selection(self):
  self.real_native=True
  for field in ('cluster','size','name','flags'):
   with self.subTest(field=field):
    self.directory(True)
    self.entries=[*exfat_entry('The Gateway Experience',100,True),END]
    self.call('browser_sort_count',0x03005a5e,FOLDER,3)
    self.call('browser_sort_enumerate',0x03005a5e,NODE,FOLDER,0,3)
    self.w(0x0300d144,456)
    if field=='name':self.entries=[*exfat_entry('The Gateway Experiencf',100,True),END]
    else:
     e=bytearray(self.entries[1]);e[{'cluster':20,'size':8,'flags':1}[field]]^=1;self.entries[1]=bytes(e)
    self.assertEqual(self.call('browser_sort_validate',NODE),0)
    self.assertEqual(self.label(NODE),'')
