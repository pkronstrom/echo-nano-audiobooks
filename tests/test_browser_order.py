"""Bounded natural-order windows retain raw identity across arbitrary physical order."""
import ctypes as C
import random
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
RESET=C.CFUNCTYPE(C.c_int,C.c_void_p)
NEXT=C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(C.c_uint32))
NAME=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint16),C.POINTER(C.c_uint))
class Provider(C.Structure):_fields_=[('context',C.c_void_p),('reset',RESET),('next',NEXT),('name',NAME)]
class Workspace(C.Structure):_fields_=[('keys',C.c_uint32*1024),('names',(C.c_uint16*256)*2),('count',C.c_uint)]
class BrowserOrderTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);out=Path(cls.tmp.name)/'order.dylib'
  subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror','-Ibrowser_sort','browser_sort/natural.c','browser_sort/order.c','-o',str(out)],cwd=ROOT,check=True)
  cls.lib=C.CDLL(str(out));cls.lib.browser_order_window.argtypes=[C.POINTER(Workspace),C.POINTER(Provider),C.c_int,C.c_uint32];cls.lib.browser_order_window.restype=C.c_int
 def provider(self,rows,failure=None):
  lookup={key:(name,directory) for key,name,directory in rows};index=0
  @RESET
  def reset(_):
   nonlocal index;index=0
   return -7 if failure=='reset' else 0
  @NEXT
  def next_(_,out):
   nonlocal index
   if failure=='next' and index==3:return -8
   if index==len(rows):return 0
   out[0]=rows[index][0];index+=1;return 1
  @NAME
  def name(_,key,out,directory):
   if failure=='name' and key==3:return -9
   text,isdir=lookup[key];raw=text.encode('utf-16le')+b'\0\0'
   if len(raw)>512:raise AssertionError('fixture name too long')
   C.memset(out,0,512);C.memmove(out,raw,len(raw));directory[0]=isdir;return 0
  return Provider(None,reset,next_,name)
 def window(self,w,p,pivot=None):
  result=self.lib.browser_order_window(C.byref(w),C.byref(p),pivot is not None,pivot or 0)
  return result,list(w.keys[:w.count])
 def test_natural_directory_first_and_raw_ties(self):
  rows=[(99,'CD2-3',0),(70000,'CD1-1',0),(4,'CD01-01',0),(10,'CD10-1',0),(8,'Z folder',1),(0,'CD2-1',0)]
  self.assertEqual(self.window(Workspace(),self.provider(rows)),(6,[8,4,70000,0,99,10]))
 def test_multiple_windows_and_repeatable_random_access(self):
  rows=[(i+70000,'Track'+str(i),0) for i in range(2305)];random.Random(72).shuffle(rows)
  p=self.provider(rows);w=Workspace();allkeys=[];pivot=None
  while True:
   n,keys=self.window(w,p,pivot);allkeys+=keys
   if n<1024:break
   pivot=keys[-1]
  self.assertEqual(allkeys,list(range(70000,72305)))
  self.assertEqual(self.window(w,p,71023),(1024,list(range(71024,72048))))
  self.assertEqual(self.window(w,p,None),(1024,list(range(70000,71024))))
 def test_empty_and_exact_window_boundary(self):
  self.assertEqual(self.window(Workspace(),self.provider([])),(0,[]))
  rows=[(i,str(i),0) for i in range(1024)];w=Workspace();p=self.provider(rows)
  self.assertEqual(self.window(w,p),(1024,list(range(1024))))
  self.assertEqual(self.window(w,p,1023),(0,[]))
 def test_errors_invalidate_entire_result(self):
  rows=[(i,str(i),0) for i in range(12)]
  for failure,error in [('reset',-7),('next',-8),('name',-9)]:
   with self.subTest(failure=failure):
    w=Workspace();w.count=12
    self.assertEqual(self.window(w,self.provider(rows,failure)),(error,[]))
 def test_pivot_ties_and_long_numeric_runs(self):
  rows=[(3,'a'+'9'*200,0),(2,'a1'+'0'*200,0),(9,'CD002',0),(5,'cd2',0)]
  p=self.provider(rows)
  self.assertEqual(self.window(Workspace(),p,5),(1,[9])) # a* keys precede cd*.
if __name__=='__main__':unittest.main()
