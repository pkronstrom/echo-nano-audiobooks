"""Offline stock wrapper probe. Directory resolution/entry insertion mocked.
No sectors, host filesystems, attached media, or firmware are written.
"""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from rknano_fw import Image
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *
stock=(ROOT/'NANOV170.IMG').read_bytes()
assert hashlib.sha256(stock).hexdigest()=='54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116'
image=Image(stock)
def probe(fs,error=0,full=False,parent_error=False):
 cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);cpu.mem_map(0x03000000,0x100000);cpu.mem_map(0x20000000,0x10000)
 m=image.modules[0]
 for kind in ('code','data'):
  o=image.l2f(m[kind+'_load']);cpu.mem_write(m[kind+'_exec'],bytes(image.d[o:o+m[kind+'_len']]))
 cpu.mem_write(0x03076b24,bytes([fs]));cpu.mem_write(0x20001000,b'\\BOOKS      \\\0');cpu.mem_write(0x20002000,b'BOOK.BMK\0\0\0' if fs==3 else b'BOOK    BMK\0')
 if full:
  for h in range(8):cpu.mem_write(0x03077668+h*0x27e,b'\x01')
 calls=[];minimum_sp=0x030fe000
 def hook(c,a,n,u):
  nonlocal minimum_sp
  minimum_sp=min(minimum_sp,c.reg_read(UC_ARM_REG_SP))
  r0,r1,r2=[c.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if a==0x20000000:c.emu_stop();return
  if a in (0x0305ba94,0x0305b9b0):
   calls.append({'function':hex(a),'directory_bytes':bytes(c.mem_read(r0,16)).hex()})
   if a==0x0305b9b0:c.mem_write(r1,struct.pack('<III',20,4096,0)+b'\x01'+bytes(29))
   result=0x0ffffff7 if parent_error else 20
  elif a in (0x0305f064,0x0305f114):
   entry=bytes(c.mem_read(r1,96 if fs==3 else 32));calls.append({'function':hex(a),'parent':r0 if fs!=3 else struct.unpack('<I',c.mem_read(r0,4))[0],'entry':entry.hex(),'mock_result':error})
   c.mem_write(r2,struct.pack('<I',2));result=error
  else:return
  c.reg_write(UC_ARM_REG_R0,result);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 cpu.hook_add(UC_HOOK_CODE,hook);cpu.reg_write(UC_ARM_REG_SP,0x030fe000);cpu.reg_write(UC_ARM_REG_LR,0x20000001)
 cpu.reg_write(UC_ARM_REG_R0,0x20001000);cpu.reg_write(UC_ARM_REG_R1,0x20002000)
 cpu.emu_start(0x0305fba7,0x20000000,count=200000)
 assert cpu.reg_read(UC_ARM_REG_PC)==0x20000000,'probe did not return'
 result=cpu.reg_read(UC_ARM_REG_R0);result=result if result<0x80000000 else result-0x100000000
 return {'filesystem':'exFAT' if fs==3 else 'FAT','entry_error':error,'handles_full':full,'parent_error':parent_error,'returned_handle':result,'fcb_open':cpu.mem_read(0x03077668,1)[0],'maximum_stack_bytes':0x030fe000-minimum_sp,'calls':calls}

sys.path.insert(0,str(ROOT/'tests'))
from test_music_filter import exfat_entry,END

def duplicate(fs):
 cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);cpu.mem_map(0x03000000,0x100000);cpu.mem_map(0x20000000,0x10000)
 m=image.modules[0]
 for kind in ('code','data'):
  o=image.l2f(m[kind+'_load']);cpu.mem_write(m[kind+'_exec'],bytes(image.d[o:o+m[kind+'_len']]))
 cpu.mem_write(0x03076b24,bytes([fs]));cpu.mem_write(0x20001000,b'\\\0'+bytes(16));cpu.mem_write(0x20002000,b'BOOK.BMK\0\0\0' if fs==3 else b'BOOK    BMK\0')
 minimum_sp=0x030fe000
 entries=exfat_entry('BOOK.BMK',90,length=1024)+[END]*4;reads=[];writes=[]
 def hook(c,a,n,u):
  nonlocal minimum_sp
  minimum_sp=min(minimum_sp,c.reg_read(UC_ARM_REG_SP))
  r0,r1,r2=[c.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if a==0x20000000:c.emu_stop();return
  if a in (0x0305ba94,0x0305b9b0):
   if fs==3:c.mem_write(r1,struct.pack('<III',20,4096,0)+b'\x01'+bytes(29))
   result=20
  elif a==0x0305b68a:result=0 # Actual FAT insertion detects existing short name.
  elif a==0x0305b2a2:
   reads.append(r2);c.mem_write(r0,entries[r2] if r2<len(entries) else END);result=0
  elif a==0x0305ec52:
   writes.append({'index':r1,'entry':bytes(c.mem_read(r2,96)).hex()});result=0
  else:return
  c.reg_write(UC_ARM_REG_R0,result);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 cpu.hook_add(UC_HOOK_CODE,hook);cpu.reg_write(UC_ARM_REG_SP,0x030fe000);cpu.reg_write(UC_ARM_REG_LR,0x20000001);cpu.reg_write(UC_ARM_REG_R0,0x20001000);cpu.reg_write(UC_ARM_REG_R1,0x20002000)
 cpu.emu_start(0x0305fba7,0x20000000,count=200000);assert cpu.reg_read(UC_ARM_REG_PC)==0x20000000
 h=cpu.reg_read(UC_ARM_REG_R0);h=h if h<0x80000000 else h-0x100000000
 return {'filesystem':'exFAT' if fs==3 else 'FAT','returned_handle':h,'directory_reads':reads,'entry_writes':writes,'maximum_stack_bytes':0x030fe000-minimum_sp,'limitation':'Parent resolution and directory-write boundary mocked; FAT name lookup supplied existing result, exFAT directory-slot scan runs native code against synthetic existing BOOK.BMK.'}

if __name__=='__main__':
 cases=[probe(fs,error,full,parent_error) for fs,error,full,parent_error in
        [(2,0,False,False),(2,7,False,False),(2,10,False,False),
         (2,0,True,False),(2,0,False,True),(3,0,False,False),
         (3,7,False,False),(3,0,True,False),(3,0,False,True)]]
 assert cases[0]['returned_handle']==0
 assert all(cases[i]['returned_handle']==-1 for i in (1,2,3,4,7))
 assert all(cases[i]['returned_handle']==0 for i in (5,6,8))
 duplicates=[duplicate(2),duplicate(3)]
 assert duplicates[0]['returned_handle']==-1 and not duplicates[0]['entry_writes']
 assert duplicates[1]['returned_handle']==0 and duplicates[1]['entry_writes'][0]['index']==3
 print(json.dumps({'stock_sha256':hashlib.sha256(stock).hexdigest(),
       'scope':'11 offline stock-code probes. Parent resolution/insertion mocked for wrapper cases; actual exFAT slot scan uses synthetic entries in duplicate cases. No real allocation, sector writes or device access.',
       'wrapper_cases':cases,'duplicate_cases':duplicates},indent=2))
