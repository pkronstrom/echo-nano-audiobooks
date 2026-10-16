"""Streaming metadata construction; output is not linked into firmware yet."""
import ctypes as C
from pathlib import Path
import struct,subprocess,tempfile,unittest,zlib
ROOT=Path(__file__).resolve().parents[1]
NAME=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint16))
WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32)
CRC=C.CFUNCTYPE(C.c_uint32,C.c_void_p,C.c_uint32)
class Source(C.Structure):_fields_=[('context',C.c_void_p),('count',C.c_uint32),('name',NAME),('prefix_units',C.c_uint32)]
class Workspace(C.Structure):_fields_=[('block',C.c_uint8*512),('name',C.c_uint16*128)]
class Plan(C.Structure):_fields_=[('bytes',C.c_uint32),('fingerprint',C.c_uint32),('count',C.c_uint32)]
class AutoBookPlaylistTests(unittest.TestCase):
 def library(self):
  path=ROOT/'experiments/auto_book_prepare/playlist.c'
  self.assertTrue(path.exists(),'streaming auto-book metadata constructor is not implemented')
  if not hasattr(type(self),'lib'):
   tmp=tempfile.TemporaryDirectory();type(self).tmp=tmp;type(self).addClassCleanup(tmp.cleanup)
   output=Path(tmp.name)/'playlist.dylib'
   subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Isrc','-Iplayback',str(path),'playback/m3u.c','-o',str(output)],cwd=ROOT,check=True)
   lib=C.CDLL(str(output));type(self).lib=lib
   lib.book_playlist_plan.argtypes=[C.POINTER(Source),C.POINTER(Workspace),C.POINTER(Plan)]
   lib.book_playlist_emit.argtypes=[C.POINTER(Source),C.POINTER(Workspace),C.POINTER(Plan),WRITE,C.c_void_p]
   lib.book_prepare_sector.argtypes=[C.c_void_p,C.c_uint32,CRC]
  return self.lib
 def source(self,names,error=None,prefix_units=1):
  @NAME
  def name(_,index,out):
   if index==error:return -1
   value=names[index]
   raw=value.encode('utf-16le',errors='surrogatepass') if isinstance(value,str) else value
   C.memset(out,0,256);C.memmove(out,raw,min(len(raw),256));return 1
  return Source(None,len(names),name,prefix_units)
 def plan(self,source):
  lib=self.library();workspace=Workspace();plan=Plan();result=lib.book_playlist_plan(C.byref(source),C.byref(workspace),C.byref(plan));return result,workspace,plan
 def emit(self,source,workspace,plan,short=False,write_result=None):
  lib=self.library();calls=[];data=bytearray()
  @WRITE
  def write(_,offset,out,length):
   calls.append((offset,length));self.assertEqual(offset,len(data));self.assertEqual(offset%512,0);self.assertLessEqual(length,512)
   raw=C.string_at(out,length);data.extend(raw)
   return write_result(length) if write_result else length-1 if short else length
  result=lib.book_playlist_emit(C.byref(source),C.byref(workspace),C.byref(plan),write,None)
  return result,bytes(data),calls
 def test_relative_utf8_preserves_naturally_ordered_upstream_names(self):
  names=['CD1-1.mp3','CD2-3.mp3','CD10-1.mp3','雪の本 😀.mp3','#Chapter.mp3']
  source=self.source(names);result,w,p=self.plan(source);self.assertEqual(result,1)
  result,data,_=self.emit(source,w,p);self.assertEqual(result,1)
  self.assertEqual(data,b'#EXTM3U\n#ECHO-BOOK-1\n'+''.join('./'+n+'\n' for n in names).encode()+b'#ECHO-END\n')
  self.assertEqual(p.bytes,len(data));self.assertEqual(p.count,5)
 def test_blocks_cross_utf8_and_filename_boundaries(self):
  source=self.source(['雪'*100+str(i)+'.mp3' for i in range(12)])
  result,w,p=self.plan(source);self.assertEqual(result,1)
  result,data,calls=self.emit(source,w,p);self.assertEqual(result,1)
  self.assertEqual(sum(n for _,n in calls),len(data));self.assertGreater(len(calls),5)
  self.assertTrue(all(n==512 for _,n in calls[:-1]));data.decode('utf-8')
 def test_one_and_256_entries_are_supported_without_truncation(self):
  for count in (1,256):
   source=self.source(['Track'+str(i)+'.mp3' for i in range(count)])
   result,w,p=self.plan(source);self.assertEqual(result,1)
   result,data,_=self.emit(source,w,p);self.assertEqual(result,1);self.assertEqual(data.count(b'./'),count)
 def test_empty_oversized_invalid_or_failed_scan_produces_no_plan(self):
  for names,error in [([],None),(['x.mp3']*257,None),(['valid.mp3','broken.mp3'],1),(['bad/name.mp3'],None),(['bad\\name.mp3'],None),(['bad\nname.mp3'],None),(['x'*128],None),(['\ud800.mp3'],None),(['\udc00.mp3'],None),(['..'],None),(['bad:track.mp3'],None)]:
   with self.subTest(names=names[:1],error=error):
    result,_,plan=self.plan(self.source(names,error));self.assertLess(result,0);self.assertEqual(plan.bytes,0)
 def test_changed_input_refuses_emission_before_writing(self):
  source=self.source(['A.mp3']);result,w,p=self.plan(source);self.assertEqual(result,1)
  changed=self.source(['B.mp3']);result,data,calls=self.emit(changed,w,p)
  self.assertLess(result,0);self.assertEqual((data,calls),(b'',[]))
 def test_short_write_is_not_success(self):
  source=self.source(['A.mp3']);result,w,p=self.plan(source);self.assertEqual(result,1)
  result,_,_=self.emit(source,w,p,short=True);self.assertLess(result,0)
 def test_false_failed_or_oversized_writer_result_is_not_success(self):
  for reply in (lambda n:0,lambda n:-1,lambda n:n+1):
   source=self.source(['A.mp3']);result,w,p=self.plan(source);self.assertEqual(result,1)
   result,_,_=self.emit(source,w,p,write_result=reply);self.assertLess(result,0)
 def test_source_change_during_emission_fails_even_with_complete_trailer(self):
  calls=0
  @NAME
  def name(_,index,out):
   nonlocal calls
   calls+=1
   # plan, emit's precheck, then its writing pass
   raw=('A.mp3' if calls<3 else 'B.mp3').encode('utf-16le')
   C.memset(out,0,256);C.memmove(out,raw,len(raw));return 1
  source=Source(None,1,name,1);result,w,p=self.plan(source);self.assertEqual(result,1)
  result,data,_=self.emit(source,w,p)
  self.assertLess(result,0);self.assertTrue(data.endswith(b'#ECHO-END\n'))
 def test_changed_folder_budget_refuses_before_writing(self):
  source=self.source(['A.mp3']);result,w,p=self.plan(source);self.assertEqual(result,1)
  source.prefix_units=2
  result,data,calls=self.emit(source,w,p)
  self.assertLess(result,0);self.assertEqual((data,calls),(b'',[]))
 def test_generated_playlist_roundtrips_through_production_parser(self):
  from test_m3u import Stats,Workspace as ParserWorkspace,wide
  read_type=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32)
  entry_type=C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(C.c_uint16),C.c_uint32)
  lib=self.library();lib.m3u_scan_with_workspace.argtypes=[C.POINTER(ParserWorkspace),read_type,entry_type,C.c_void_p,C.c_void_p,C.POINTER(Stats)]
  names=['#start.mp3','雪の本 😀.mp3','CD10-1.mp3']
  source=self.source(names,prefix_units=6);result,w,p=self.plan(source);self.assertEqual(result,1)
  result,data,_=self.emit(source,w,p);self.assertEqual(result,1)
  entries=[]
  @read_type
  def read(_,offset,out,length):
   part=data[offset:offset+min(length,1)];C.memmove(out,part,len(part));return len(part)
  @entry_type
  def entry(_,path,offset):
   n=0
   while path[n]:n+=1
   entries.append(C.string_at(path,n*2).decode('utf-16le'));return 1
  stats=Stats();workspace=ParserWorkspace()
  self.assertEqual(lib.m3u_scan_with_workspace(C.byref(workspace),read,entry,None,wide('/Book'),C.byref(stats)),0)
  self.assertEqual(entries,['/Book/'+name for name in names]);self.assertEqual(stats.accepted,len(names))
  self.assertEqual((stats.skipped,stats.invalid,stats.limited),(0,0,0))
 def test_absolute_path_budget_is_checked_before_writing(self):
  # Prefix includes the normalized absolute folder's final separator. The
  # native resolver stores at most 255 UTF-16 units, excluding the terminator.
  for prefix,filename,valid in [(131,'b'*120+'.mp3',True),
                                (132,'b'*120+'.mp3',False),
                                (247,'a.mp3',True),(248,'a.mp3',False),
                                (0,'a.mp3',False),
                                (128,'x'*123+'😀.m',True),
                                (129,'x'*123+'😀.m',False)]:
   with self.subTest(prefix=prefix,filename=filename):
    source=self.source([filename],prefix_units=prefix)
    result,w,p=self.plan(source)
    self.assertEqual(result,1 if valid else -1)
    if not valid:
     self.assertEqual(p.bytes,0)
     result,data,calls=self.emit(source,w,p)
     self.assertLess(result,0);self.assertEqual((data,calls),(b'',[]))
 def test_existing_journal_wire_format_is_unchanged(self):
  lib=self.library()
  @CRC
  def crc(data,length):return zlib.crc32(C.string_at(data,length))
  for magic in (0x31524e45,0x31424e45):
   out=(C.c_uint8*512)(*([0xa5]*512));lib.book_prepare_sector(out,magic,crc)
   expected=bytearray(512);struct.pack_into('<I',expected,0,magic);struct.pack_into('<I',expected,508,zlib.crc32(expected[:508]));self.assertEqual(bytes(out),bytes(expected))
if __name__=='__main__':unittest.main()
