"""Small native-digit speed label, artist hooks, and framebuffer isolation."""
import os,struct,subprocess,tempfile,unittest
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *
import test_playback_runtime_arm as runtime
from playback_layout import read_patch
ROOT=runtime.ROOT;STOP=0x030ff000
class PlayerSpeedLabelTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  env=dict(os.environ);env['PATH']=str(ROOT/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin')+os.pathsep+env['PATH']
  with tempfile.TemporaryDirectory(prefix='speed-label-') as d:
   p=Path(d)
   def run(args):return subprocess.check_output(args,cwd=ROOT,env=env)
   run(['arm-none-eabi-gcc','-mthumb','-mcpu=cortex-m3','-Os','-ffreestanding','-Isrc','-Iplayback','-c','playback/player_speed_label.c','-o',str(p/'label.o')])
   defs={'playback_speed_actual':0x030ff101,'playback_active':0x030f0000,'playback_header':0x03092400}
   run(['arm-none-eabi-ld','-Ttext=0x03098000','-e','playback_speed_label',str(p/'label.o'),'-o',str(p/'label.elf')]+['--defsym='+k+'='+hex(v) for k,v in defs.items()])
   run(['arm-none-eabi-objcopy','-O','binary',str(p/'label.elf'),str(p/'label.bin')]);cls.code=(p/'label.bin').read_bytes()
   cls.symbols={line.split()[2]:int(line.split()[0],16) for line in run(['arm-none-eabi-nm',str(p/'label.elf')]).decode().splitlines() if len(line.split())==3}
   (p/'playback_syms.inc').write_text('\n'.join('.equ '+k+', '+hex(v) for k,v in cls.symbols.items()))
   cls.patches=[]
   for source in sorted((ROOT/'playback/hooks').glob('player_speed_label*.S')):
    dest=p/(source.stem+'.patch');run(['tools/asm2patch.sh',str(source),str(dest),str(p)]);cls.patches.append(read_patch(dest))
 def setUp(self):
  self.image=runtime.Image((ROOT/'NANOV170.IMG').read_bytes());self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);self.cpu.mem_map(0x03000000,0x100000)
  for index in (0,27):
   m=self.image.modules[index]
   for kind in ('code','data'):
    o=self.image.l2f(m[kind+'_load']);self.cpu.mem_write(m[kind+'_exec'],bytes(self.image.d[o:o+m[kind+'_len']]))
  _,a,data=read_patch(ROOT/'out/playback/speed_guard.patch');self.cpu.mem_write(a,data)
  for module,a,data in self.patches:self.assertEqual(module,27);self.cpu.mem_write(a,data)
  self.cpu.mem_write(0x03098000,self.code);self.cpu.mem_write(0x03092400,b'ENP2');self.word(0x030f0000,1)
  self.rate=4;self.marquees=0;self.stop=None;self.dirty=0;self.rects=[];self.cpu.hook_add(UC_HOOK_CODE,self.hook)
 def word(self,a,v):self.cpu.mem_write(a,struct.pack('<I',v))
 def hook(self,cpu,a,size,user):
  if a==self.stop:cpu.emu_stop();return
  if a==0x030ff100:cpu.reg_write(UC_ARM_REG_R0,self.rate)
  elif a==0x03052fe4:self.marquees+=1
  elif a==0x0306b05c:cpu.reg_write(UC_ARM_REG_R0,self.dirty)
  elif a in (0x03052b08,0x03052c66):self.rects.append(struct.unpack('<4H',cpu.mem_read(cpu.reg_read(UC_ARM_REG_R0),8)))
  else:return
  cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 def call(self,a):
  self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000);self.cpu.reg_write(UC_ARM_REG_LR,STOP|1)
  self.cpu.emu_start(a|1,STOP,count=10000);self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),0x030fe000)
 def bitmap(self,text):
  glyph={'.':bytes([0x40,0]),'x':bytes([0x28,0x10,0x28,0])};b=self.image.sections[-1]['offset']
  for c in '1257':
   w,h,_,_,n,o=struct.unpack_from('<4H2I',self.image.d,b+32+(33+int(c))*16)
   self.assertEqual(h,8);self.assertEqual(n,w*h*2)
   pixels=struct.unpack_from('<'+str(w*h)+'H',self.image.d,b+o)
   glyph[c]=bytes(sum((pixels[y*w+x]==0)<<y for y in range(h)) for x in range(w))
  data=b''.join(glyph[c] for c in text);return bytes(22-len(data))+data
 def test_all_rates_match_stock_small_digits_and_preserve_other_pixels(self):
  for q,text in enumerate(('1x','1.25x','1.5x','1.75x','2x'),4):
   with self.subTest(rate=q):
    self.rate=q;before=bytes([0xa5])*640;self.cpu.mem_write(0x03007d88,before)
    modes=bytes(range(40));self.cpu.mem_write(0x0300d6c0,modes)
    self.call(self.symbols['playback_speed_label'])
    expected=bytearray(before)
    for x,bits in enumerate(self.bitmap(text),86):expected[x*5+1]&=15;expected[x*5+2]=bits
    self.assertEqual(bytes(self.cpu.mem_read(0x03007d88,640)),bytes(expected))
    self.assertEqual(bytes(self.cpu.mem_read(0x0300d6c0,40)),modes)
 def test_shorter_rate_erases_old_label(self):
  self.cpu.mem_write(0x03007d88,bytes(640));self.rate=7;self.call(self.symbols['playback_speed_label'])
  self.rate=4;self.call(self.symbols['playback_speed_label'])
  self.assertEqual(bytes(self.cpu.mem_read(0x03007d88+86*5,110))[2::5],self.bitmap('1x'))
 def test_music_and_invalid_payload_do_not_draw(self):
  for header,active in ((b'ENP2',0),(b'CFW!',1)):
   self.cpu.mem_write(0x03092400,header);self.word(0x030f0000,active)
   before=bytes([0xa5])*640;self.cpu.mem_write(0x03007d88,before);self.call(0x0307a2c8)
   self.assertEqual(bytes(self.cpu.mem_read(0x03007d88,640)),before)
  self.assertEqual(self.marquees,2)
 def test_artist_width_guard_and_stock_title_bottom(self):
  for header,active,width in ((b'ENP2',1,86),(b'ENP2',0,107),(b'CFW!',1,107)):
   self.cpu.mem_write(0x03092400,header);self.word(0x030f0000,active)
   self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000);self.stop=0x0307adee
   self.cpu.emu_start(0x0307ade9,STOP,count=1000);self.stop=None
   self.assertEqual(struct.unpack('<H',self.cpu.mem_read(0x030fe03c,2))[0],width)
  self.assertEqual(bytes(self.cpu.mem_read(0x0307ad34,6)).hex(),'7f20adf80c00')
  self.assertEqual(bytes(self.cpu.mem_read(0x0307ad72,4)).hex(),'d8f737f9')
  self.assertEqual(bytes(self.cpu.mem_read(0x0307bb64,4)).hex(),'fef702ff')
 def test_artist_incremental_marquee_always_precedes_label(self):
  self.cpu.mem_write(0x03007d88,bytes(640));self.call(0x0307a2c8)
  self.assertEqual(self.marquees,1)
  self.assertEqual(bytes(self.cpu.mem_read(0x03007d88+86*5,110))[2::5],self.bitmap('1x'))
 def test_real_artist_full_and_incremental_routes(self):
  for dirty in (0,1):
   self.dirty=dirty;self.rects=[];before=self.marquees
   self.cpu.mem_write(0x03007d88,bytes(640));self.call(0x0307adc8)
   self.assertEqual(self.marquees,before+1)
   self.assertEqual(self.rects,[(12,12,86,23)] if dirty else [])
   self.assertEqual(bytes(self.cpu.mem_read(0x03007d88+86*5,110))[2::5],self.bitmap('1x'))
 def test_combined_image_hooks_and_actual_payload(self):
  f=runtime.PlaybackRuntimeTests();f.setUp();cpu=f.cpu
  image=runtime.Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
  for source in sorted((ROOT/'playback/hooks').glob('player_speed_label*.S')):
   module,address,data=read_patch(ROOT/'out/playback'/(source.stem+'.patch'))
   off,_=image.region(module,address)
   self.assertEqual(bytes(image.d[off:off+len(data)]),data,source.stem)
  for index in (0,27):
   m=image.modules[index]
   for kind in ('code','data'):
    off=image.l2f(m[kind+'_load']);cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
  cpu.mem_write(f.syms['playback_active'],struct.pack('<I',1))
  cpu.mem_write(0x03039e94,struct.pack('<I',1)) # Unsupported book must show actual1x.
  self.assertEqual(f.call('playback_speed_actual'),4)
  rects=[];marquees=[]
  def native(cpu,address,size,user):
   if address==0x0306b05c:cpu.reg_write(UC_ARM_REG_R0,1)
   elif address in (0x03052b08,0x03052c66):rects.append(struct.unpack('<4H',cpu.mem_read(cpu.reg_read(UC_ARM_REG_R0),8)))
   elif address==0x03052fe4:marquees.append(address)
   else:return
   cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  cpu.hook_add(UC_HOOK_CODE,native)
  before=bytes([0xa5])*640;cpu.mem_write(0x03007d88,before)
  f.call(0x0307adc8)
  self.assertEqual(rects,[(12,12,86,23)])
  self.assertEqual(marquees,[0x03052fe4])
  expected=bytearray(before)
  for x,bits in enumerate(self.bitmap('1x'),86):expected[x*5+1]&=15;expected[x*5+2]=bits
  self.assertEqual(bytes(cpu.mem_read(0x03007d88,640)),bytes(expected))
  self.assertEqual(bytes(cpu.mem_read(0x0307ad34,6)).hex(),'7f20adf80c00')
  self.assertEqual(bytes(cpu.mem_read(0x0307ad72,4)).hex(),'d8f737f9')
  self.assertEqual(bytes(cpu.mem_read(0x0307bb64,4)).hex(),'fef702ff')
