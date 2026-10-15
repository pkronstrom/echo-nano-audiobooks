"""Natural UTF16 ordering without numeric overflow or dependence on locale."""
import ctypes as C
import functools
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def wide(s):
 b=s.encode('utf-16le')+b'\0\0'
 return (C.c_uint16*(len(b)//2)).from_buffer_copy(b)
class BrowserNaturalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
  out=Path(cls.tmp.name)/'natural.dylib'
  subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror','-Ibrowser_sort','browser_sort/natural.c','-o',str(out)],cwd=ROOT,check=True)
  cls.lib=C.CDLL(str(out));cls.lib.browser_natural_compare.argtypes=[C.POINTER(C.c_uint16)]*2;cls.lib.browser_natural_compare.restype=C.c_int
 def cmp(self,a,b):return self.lib.browser_natural_compare(wide(a),wide(b))
 def test_disc_and_track_numbers(self):
  names=['CD 2 - 3','CD 10 - 1','CD 1 - 10','CD 1 - 2','CD 1 - 1']
  self.assertEqual(sorted(names,key=functools.cmp_to_key(self.cmp)),['CD 1 - 1','CD 1 - 2','CD 1 - 10','CD 2 - 3','CD 10 - 1'])
 def test_zero_padding_and_case_are_equal_with_raw_index_tiebreak_left_to_caller(self):
  for a,b in [('Track002','track2'),('Ääni 01','ääni 1'),('Ö 000','ö 0')]:self.assertEqual(self.cmp(a,b),0)
  self.assertGreater(self.cmp('Track002b','track2a'),0)
 def test_large_numeric_runs_do_not_overflow(self):
  self.assertLess(self.cmp('9'*200,'1'+'0'*200),0)
  self.assertGreater(self.cmp('1'+'0'*199+'1','1'+'0'*200),0)
  self.assertEqual(self.cmp('0'*250+'2','2'),0)
 def test_prefix_empty_and_unicode_are_deterministic(self):
  for a,b in [('', 'a'),('a','aa'),('波1','波2'),('a2','a10'),('ä','ö')]:
   self.assertLess(self.cmp(a,b),0);self.assertGreater(self.cmp(b,a),0)
 def test_fixed_capacity_without_terminator_is_bounded(self):
  a=(C.c_uint16*256)(*([ord('0')]*256));b=wide('0')
  self.assertEqual(self.lib.browser_natural_compare(a,b),0)
