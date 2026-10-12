"""Experimental payload on Cortex-M3; stock indexed file-open executes unchanged.
Raw directory readers, locks and watchdog are substituted. This does not verify
actual sectors, driver behavior or the stock shared directory cache.
"""
import struct
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from test_music_arm import ROOT, Image
from test_music_filter import fat_entry, exfat_entry, END
from test_media_path import lfn

class PlaybackRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.syms={n:int(v,16) for v,t,n in (l.split() for l in (ROOT/'out/playback/playback.nm').read_text().splitlines())}
        self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000,0x100000)
        self.cpu.mem_map(0x20000000,0x10000)
        image=Image((ROOT/'NANOV170.IMG').read_bytes())
        m=image.modules[0]
        for kind in ('code','data'):
            offset=image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[offset:offset+m[kind+'_len']]))
        self.cpu.mem_write(0x0309b694,(ROOT/'out/playback/playback.bin').read_bytes())
        self.dirs={0:[END],2:[END]}
        self.cpu.mem_write(0x03076b24,b'\x02')
        self.cpu.hook_add(UC_HOOK_CODE,self.intercept)
        self.entries=[]
        self.files={}
        self.closed=[]
        self.flash_mode=None
        self.flash_reads=0
        self.assertEqual(self.call('playback_init'),0x32504e45)

    def intercept(self,cpu,address,size,user):
        result=None
        if address in (0x03065800,0x0306a40e,0x0306a466): result=0
        elif address in (0x0305b3ea,0x0305b2a2):
            out,parent,index=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
            if address==0x0305b2a2:
                descriptor=parent
                parent=struct.unpack('<I',cpu.mem_read(parent,4))[0]
                if parent==0:
                    parent=2;cpu.mem_write(descriptor,struct.pack('<I',2))
            entries=self.dirs.get(parent,[END])
            result=9 if index>=len(entries) else 0
            if not result: cpu.mem_write(out,entries[index])
        elif address==0x0306b36c and self.flash_mode is not None:
            dev,source,length,out=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
            self.assertEqual(dev,0x30000);self.assertEqual(source,self.slot+0xa55000)
            payload=(ROOT/'out/playback/playback.bin').read_bytes()
            self.assertEqual((length,out),(len(payload),0x0309b694));self.flash_reads+=1
            if self.flash_mode=='bad-magic':payload=b'BAD!'+payload[4:]
            cpu.mem_write(out,payload)
            result=1 if self.flash_mode=='error' else 0
        elif address==0x0305c8f2 and self.files:
            offset,whence,handle=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
            self.assertEqual(whence,0)
            cpu.mem_write(0x03077668+handle*0x27e+32,struct.pack('<I',offset));result=0
        elif address==0x0305c3fa and self.files:
            out,length,handle=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
            fcb=0x03077668+handle*0x27e
            cluster=struct.unpack('<I',cpu.mem_read(fcb+20,4))[0]
            offset=struct.unpack('<I',cpu.mem_read(fcb+32,4))[0]
            part=self.files[cluster][offset:offset+min(length,7)]
            cpu.mem_write(out,part);result=len(part)
        elif address==0x0305c2e0 and self.files:
            handle=cpu.reg_read(UC_ARM_REG_R0);self.closed.append(handle)
            cpu.mem_write(0x03077668+handle*0x27e,b'\0');result=0
        elif address==0x20000100:
            offset,out,length=[cpu.reg_read(r) for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
            part=self.playlist[offset:offset+min(length,5)]
            cpu.mem_write(out,part);result=len(part)
        elif address==0x20000200:
            path=cpu.reg_read(UC_ARM_REG_R1)
            data=bytes(cpu.mem_read(path,512));end=0
            while data[end:end+2]!=b'\0\0':end+=2
            self.entries.append(data[:end].decode('utf-16le'));result=1
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0,result)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))

    def call(self,name,*args):
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):self.cpu.reg_write(register,value)
        self.cpu.reg_write(UC_ARM_REG_SP,0x2000f000)
        if len(args)>4:self.cpu.mem_write(0x2000f000,struct.pack('<I',args[4]))
        self.cpu.reg_write(UC_ARM_REG_LR,0x20000001)
        self.cpu.emu_start((self.syms[name] if isinstance(name,str) else name)|1,0x20000000,count=2000000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),0x20000000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP),0x2000f000)
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def lookup(self,path):
        self.cpu.mem_write(0x20001000,path.encode('utf-16le')+b'\0\0')
        return self.call('playback_lookup',0x20001000,0x20002000)

    def test_fat_native_indexed_open_after_unicode_lookup(self):
        entry=bytearray(fat_entry(b'CHAPTE~1FLA',100));struct.pack_into('<I',entry,28,12345)
        entries=lfn('Chapter 日本語.flac',b'CHAPTE~1FLA',100);entries[-1]=bytes(entry)
        self.dirs={0:[*entries,END]}
        self.assertEqual(self.lookup('/Chapter 日本語.flac'),1)
        self.assertEqual(self.call('playback_open',0x20002000),0)
        handle=bytes(self.cpu.mem_read(0x03077668,44))
        self.assertEqual(handle[0],1)
        self.assertEqual(struct.unpack_from('<II',handle,16),(12345,100))

    def test_exfat_native_indexed_open_after_unicode_lookup(self):
        self.cpu.mem_write(0x03076b24,b'\x03')
        self.dirs={2:[*exfat_entry('Méditation 日本語.flac',100,length=12345),END]}
        self.assertEqual(self.lookup('/Méditation 日本語.flac'),1)
        self.assertEqual(self.call('playback_open',0x20002000),0)
        handle=bytes(self.cpu.mem_read(0x03077668,44))
        self.assertEqual(handle[0],1)
        self.assertEqual(struct.unpack_from('<II',handle,16),(12345,100))

    def test_native_metadata_selection_is_exact_and_transactional(self):
        for exfat in (False, True):
            with self.subTest(exfat=exfat):
                self.cpu.mem_write(0x03076b24,bytes([3 if exfat else 2]))
                self.dirs={2: [*exfat_entry('two.flac',100,length=12345),END]} if exfat else {0:[fat_entry(b'TWO     FLA',100),END]}
                self.assertEqual(self.lookup('/two.flac' if exfat else '/TWO.FLA'),1)
                state=0x20003000
                self.cpu.mem_write(state,b'\xa5'*256)
                self.assertEqual(self.call('playback_select_ref',0x20002000,state,2,3),0)
                data=bytes(self.cpu.mem_read(state,96))
                self.assertEqual(struct.unpack_from('<HH',data),(3,2))
                self.assertEqual(struct.unpack_from('<4H',data,6),(2,3,2,0))
                self.assertEqual(struct.unpack_from('<I',data,0x38)[0],1)
                self.assertEqual((struct.unpack_from('<H',data,0x28)[0]<<16)|struct.unpack_from('<H',data,0x2e)[0],100)
                before=bytes(self.cpu.mem_read(state,256))
                self.cpu.mem_write(0x20002000+20,struct.pack('<I',101))
                self.assertNotEqual(self.call('playback_select_ref',0x20002000,state,1,3),0)
                self.assertEqual(bytes(self.cpu.mem_read(state,256)),before)

    def test_exfat_native_name_limit_and_changed_stream_are_guarded(self):
        self.cpu.mem_write(0x03076b24,b'\x03')
        for units in (127,128):
            name='日'*(units-4)+'.m3u'
            self.dirs={2:[*exfat_entry(name,90),END]}
            self.assertEqual(self.lookup('/'+name),1)
            result=self.call('playback_open',0x20002000)
            if units==127:
                self.assertEqual(result,0)
                self.cpu.mem_write(0x03077668,b'\0')
            else:self.assertEqual(result,0xffffffff)
        # Reference was originally safe: use live stream length, not cached length.
        self.dirs={2:[*exfat_entry('safe.mp3',90),END]}
        self.assertEqual(self.lookup('/safe.mp3'),1)
        self.dirs={2:[*exfat_entry('日'*124+'.mp3',90),END]}
        state=0x20003000;before=b'\xa5'*256;self.cpu.mem_write(state,before)
        self.assertEqual(self.call('playback_open',0x20002000),0xffffffff)
        self.assertEqual(self.call('playback_select_ref',0x20002000,state,1,1),0xffffffff)
        self.assertEqual(bytes(self.cpu.mem_read(state,256)),before)

    def test_playlist_load_and_native_queue_advance_across_folders(self):
        for exfat in (False,True):
            with self.subTest(exfat=exfat):
                self.call('playback_init');self.closed=[]
                self.cpu.mem_write(0x03076b24,bytes([3 if exfat else 2]))
                data=b'#EXTM3U\nBooks/two.flac\nmissing.mp3\nMusic/one.mp3\nBooks/two.flac\n'
                self.files={90:data}
                if exfat:
                    self.dirs={2:[*exfat_entry('list.m3u',90,length=len(data)),*exfat_entry('Books',20,directory=True),*exfat_entry('Music',30,directory=True),END],
                               20:[*exfat_entry('two.flac',100,length=12345),END],30:[*exfat_entry('one.mp3',101,length=12345),END]}
                else:
                    self.dirs={0:[fat_entry(b'LIST    M3U',90),fat_entry(b'BOOKS      ',20,directory=True),fat_entry(b'MUSIC      ',30,directory=True),END],
                               20:[*lfn('two.flac',b'TWO     FLA',100),END],30:[fat_entry(b'ONE     MP3',101),END]}
                self.cpu.mem_write(0x20001000,'/list.m3u'.encode('utf-16le')+b'\0\0')
                self.assertEqual(self.call('playback_load_playlist',0x20001000,0x20002000),3)
                self.assertEqual(self.closed,[0])
                self.assertEqual(struct.unpack('<4I',self.cpu.mem_read(0x20002000,16)),(3,1,0,0))
                state=0x20003000;self.cpu.mem_write(state,bytes(256))
                for direction,position,cluster in ((0,1,100),(1,2,101),(1,3,100),(1,1,100),(-1,3,100),(-1,2,101)):
                    self.assertEqual(self.call('playback_playlist_step',state,direction & 0xffffffff),0)
                    q=bytes(self.cpu.mem_read(state,96))
                    self.assertEqual(struct.unpack_from('<HH',q),(3,position))
                    self.assertEqual((struct.unpack_from('<H',q,0x28)[0]<<16)|struct.unpack_from('<H',q,0x2e)[0],cluster)
                # Replacing a listed file must not silently play the replacement.
                self.dirs[20]=[*exfat_entry('two.flac',999,length=12345),END] if exfat else [*lfn('two.flac',b'TWO     FLA',999),END]
                self.assertEqual(self.call('playback_playlist_step',state,1),0)
                self.assertEqual(struct.unpack('<H',self.cpu.mem_read(state+2,2))[0],2)
                before=bytes(self.cpu.mem_read(state,256));self.dirs[30]=[END]
                self.assertEqual(self.call('playback_playlist_step',state,1),19)
                self.assertEqual(bytes(self.cpu.mem_read(state,256)),before)

    def install_loader(self):
        line=next(l for l in (ROOT/'out/playback/loader.patch').read_text().splitlines() if not l.startswith('#'))
        mod,address,data=line.split(':');code=bytes.fromhex(data)
        self.assertEqual((mod,int(address,16),len(code)),('0',0x03072e28,84))
        self.cpu.mem_write(int(address,16),code)
        self.slot=0x10000200;self.cpu.mem_write(0x0300d454,struct.pack('<I',self.slot))
        return int(address,16)

    def test_loader_reuses_live_queue_and_reinitializes_after_refresh(self):
        loader=self.install_loader();self.flash_mode='ok'
        start,end=self.syms['__play_bss_start'],self.syms['__play_bss_end']
        self.cpu.mem_write(0x0309b694,b'CFW!');self.cpu.mem_write(start,b'\xa5'*(end-start))
        self.assertEqual(self.call(loader),0);self.assertEqual(self.flash_reads,1)
        self.assertEqual(bytes(self.cpu.mem_read(start,end-start)),bytes(end-start))
        self.cpu.mem_write(start,b'LIVE')
        self.assertEqual(self.call(loader),0);self.assertEqual(self.flash_reads,1)
        self.assertEqual(bytes(self.cpu.mem_read(start,4)),b'LIVE')
        self.cpu.mem_write(0x0309b694,b'CFW!')
        self.assertEqual(self.call(loader),0);self.assertEqual(self.flash_reads,2)
        self.assertEqual(bytes(self.cpu.mem_read(start,4)),bytes(4))

    def test_loader_failure_never_leaves_a_ready_signature(self):
        loader=self.install_loader()
        for mode in ('error','bad-magic'):
            with self.subTest(mode=mode):
                self.flash_mode=mode;self.cpu.mem_write(0x0309b694,b'CFW!')
                self.assertEqual(self.call(loader),1)
                self.assertEqual(bytes(self.cpu.mem_read(0x0309b694,4)),bytes(4))
                self.flash_mode='ok';self.assertEqual(self.call(loader),0)

    def test_compiled_parser_streams_unicode_in_order(self):
        self.playlist='\ufeff#EXTM3U\r\n../Kirjat/02 ä.flac\n../Kirjat/01 日本語.flac'.encode()
        self.cpu.mem_write(0x20001000,'/Playlists'.encode('utf-16le')+b'\0\0')
        self.assertEqual(self.call('m3u_scan',0x20000101,0x20000201,0,0x20001000,0x20002000),0)
        self.assertEqual(self.entries,['/Kirjat/02 ä.flac','/Kirjat/01 日本語.flac'])
        self.assertEqual(struct.unpack('<4I',self.cpu.mem_read(0x20002000,16)),(2,0,0,0))

if __name__=='__main__':unittest.main()
