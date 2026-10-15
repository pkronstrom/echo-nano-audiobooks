"""Relocated browser overlay bounds and native noncontiguous code/data loading."""
import hashlib,json,struct,sys,tempfile,unittest
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
import playback_layout as layout
START=0x0307b874;END=0x03080470;FLASH=0x3e200
class BrowserSortLayoutTests(unittest.TestCase):
 def setUp(self):
  self.stock=Image((ROOT/'NANOV170.IMG').read_bytes());self.image=Image((ROOT/'out/NANOV170.IMG').read_bytes())
  self.payload=struct.pack('<4I',0x314f5342,START+17,START+32,START+0x1800)+b'\x70\x47'+bytes(14)
 def relocate(self,payload=None):layout.relocate_browser_sort(self.stock,self.image,self.payload if payload is None else payload)
 def test_only_browser_code_table_and_verified_tail_change(self):
  before=bytes(self.image.d);modules=[dict(m) for m in self.image.modules];m=modules[31];o=self.image.l2f(m['code_load']);code=before[o:o+m['code_len']]
  self.relocate();new=self.image.modules[31]
  self.assertEqual(new['code_exec'],m['code_exec']);self.assertEqual(new['code_len'],m['code_len']+len(self.payload))
  self.assertEqual(self.image.d[FLASH:FLASH+new['code_len']],code+self.payload)
  expected=bytearray(before);expected[FLASH:FLASH+new['code_len']]=code+self.payload
  for offset,key in ((0,'code_load'),(8,'code_len')):struct.pack_into('<I',expected,0x208+31*32+offset,new[key])
  self.assertEqual(self.image.d,expected)
  for i in range(len(modules)):
   if i!=31:self.assertEqual(self.image.modules[i],modules[i])
  for key in ('data_load','data_exec','data_len','bss_exec','bss_len'):self.assertEqual(new[key],m[key])
 def test_occupied_tail_and_changed_table_are_rejected(self):
  self.image.d[FLASH+13000]=1
  with self.assertRaisesRegex(ValueError,'occupied'):self.relocate()
  self.setUp();self.image.modules[31]['code_len']+=4
  with self.assertRaisesRegex(ValueError,'table'):self.relocate()
 def test_bad_header_and_code_runtime_overflow_are_rejected(self):
  for payload in (b'BAD!'+self.payload[4:],self.payload+bytes(4332),struct.pack('<4I',0x314f5342,START+17,START+32,END+4)+self.payload[16:]):
   with self.subTest(payload=len(payload)),self.assertRaises(ValueError):self.relocate(payload)
 def test_native_loader_copies_code_data_and_bss_independently(self):
  if getattr(self,'window_load',False) and not getattr(self,'compiled',False):
   self.payload=struct.pack('<4I',0x314f5342,START+17,START+4096,START+0x1800)+self.payload[16:]+bytes(4096-len(self.payload))
  self.relocate();m=self.image.modules[31];cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);cpu.mem_map(0x03000000,0x100000)
  native=self.stock.modules[0]
  for k in ('code','data'):
   o=self.stock.l2f(native[k+'_load']);cpu.mem_write(native[k+'_exec'],bytes(self.stock.d[o:o+native[k+'_len']]))
  cpu.mem_write(0x0300d454,struct.pack('<I',0)) # Firmware table at flash-relative0.
  for a,n in ((m['code_exec']-8,m['code_len']+16),(m['data_exec']-8,m['data_len']+16),(m['bss_exec'],m['bss_len']+8)):
   cpu.mem_write(a,b'Z'*n)
  reads=[]
  def hook(cpu,a,size,user):
   if a==0x0306b36c:
    dev,off,n,dst=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    self.assertEqual(dev,0x30000);self.assertLessEqual(off+n,len(self.image.d)-512)
    reads.append((off,n));cpu.mem_write(dst,bytes(self.image.d[off+512:off+512+n]));cpu.reg_write(UC_ARM_REG_R0,0)
   elif a in (0x0306a40e,0x0306a466):cpu.reg_write(UC_ARM_REG_R0,0)
   else:return
   cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  cpu.hook_add(UC_HOOK_CODE,hook)
  for attempt in range(2):
   cpu.mem_write(getattr(self,'metadata',START+20),b'FAIL') # copied metadata must reset each reload
   if getattr(self,'window_load',False):
    # Enter a complete different native window (11/module9), which overlaps
    # the appended helper but not the old browser entry; then return to9/31.
    if attempt:
     cpu.mem_write(0x03005b8c,b'\x0b');cpu.reg_write(UC_ARM_REG_R0,0x030f8000)
     cpu.reg_write(UC_ARM_REG_SP,0x030fe000);cpu.reg_write(UC_ARM_REG_LR,0x030ff001)
     cpu.emu_start(0x0306b247,0x030ff000,count=200000)
     self.assertNotEqual(bytes(cpu.mem_read(0x0307c154,32)),bytes(32))
    cpu.mem_write(0x03005b8c,b'\x09');cpu.reg_write(UC_ARM_REG_R0,0x030f8000);entry=0x0306b247
   else:
    cpu.reg_write(UC_ARM_REG_R0,31);cpu.reg_write(UC_ARM_REG_R1,7);entry=0x0306b6bd
   cpu.reg_write(UC_ARM_REG_SP,0x030fe000);cpu.reg_write(UC_ARM_REG_LR,0x030ff001)
   cpu.emu_start(entry,0x030ff000,count=200000)
   self.assertEqual(cpu.reg_read(UC_ARM_REG_PC),0x030ff000)
   for k in ('code','data'):
    o=self.image.l2f(m[k+'_load']);self.assertEqual(bytes(cpu.mem_read(m[k+'_exec'],m[k+'_len'])),bytes(self.image.d[o:o+m[k+'_len']]))
   self.assertEqual(bytes(cpu.mem_read(m['bss_exec'],m['bss_len'])),bytes(m['bss_len']))
  self.assertEqual(bytes(cpu.mem_read(m['code_exec']-8,8)),b'Z'*8)
  if not getattr(self,'window_load',False):self.assertEqual(bytes(cpu.mem_read(m['code_exec']+m['code_len'],8)),b'Z'*8)
  self.assertEqual(bytes(cpu.mem_read(m['data_exec']-8,8)),b'Z'*8)
  self.assertEqual(bytes(cpu.mem_read(m['bss_exec']+m['bss_len'],8)),b'Z'*8)
  self.assertTrue(any(o==FLASH-512 for o,n in reads))
  self.assertTrue(any(o<self.image.l2f(m['data_load'])-512<o+n for o,n in reads))
 def test_native_window_nine_auxiliary_is_reloaded_before_browser_resume(self):
  self.window_load=True
  self.test_native_loader_copies_code_data_and_bss_independently()
 def test_hook_manifest_and_relocation_are_one_checked_transaction(self):
  with tempfile.TemporaryDirectory(prefix='sort-layout-') as temp:
   directory=Path(temp);(directory/'browser_sort.bin').write_bytes(self.payload)
   for name,(address,expected) in layout.BROWSER_SORT_HOOKS.items():
    target=0x0307aefc if name=='browser_sort_ordinal' else START+16
    data=layout.encode_t32_branch(address,target,False)
    (directory/(name+'.patch')).write_text(f'31:{address:08x}:{data.hex()}\n')
   files=['browser_sort.bin']+[name+'.patch' for name in layout.BROWSER_SORT_HOOKS]
   manifest={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in files}
   (directory/'manifest.json').write_text(json.dumps(manifest))
   before=bytes(self.image.d)
   (directory/'browser_sort.bin').write_bytes(self.payload+b'FAIL')
   with self.assertRaisesRegex(ValueError,'artifact'):layout.apply_browser_sort(self.stock,self.image,directory)
   self.assertEqual(bytes(self.image.d),before)
   (directory/'browser_sort.bin').write_bytes(self.payload)
   layout.apply_browser_sort(self.stock,self.image,directory)
   for name,(address,expected) in layout.BROWSER_SORT_HOOKS.items():
    off,_=self.image.region(31,address);self.assertEqual(bytes(self.image.d[off:off+4]),layout.read_patch(directory/(name+'.patch'))[2])
 def test_compiled_extension_metadata_and_native_window_reload(self):
  directory=ROOT/'out/browser_sort';self.payload=(directory/'browser_sort.bin').read_bytes()
  symbols={n:int(v,16) for v,t,n in (line.split() for line in (directory/'browser_sort.nm').read_text().splitlines())}
  self.metadata=symbols['__sort_metadata_start'];end=symbols['__sort_metadata_end']
  self.assertGreaterEqual(end-self.metadata,4)
  self.assertEqual(self.payload[self.metadata-START:end-START],bytes(end-self.metadata))
  magic,entry,code_end,bss_end=struct.unpack_from('<4I',self.payload)
  self.assertEqual(entry,symbols['browser_sort_enumerate']|1)
  self.assertEqual((code_end,bss_end),(symbols['__sort_code_end'],symbols['__sort_bss_end']))
  self.window_load=True;self.compiled=True
  self.test_native_loader_copies_code_data_and_bss_independently()
