"""Execute menu routing/chooser and native Back against compiled ARM payload.
Filesystem reads and native count/enumeration are mocked; device I/O remains
an explicit hardware check.
"""
import struct
import unittest
from unicorn.arm_const import *
import test_playback_runtime_arm as runtime
from test_music_arm import ROOT, Image
from test_music_filter import END, fat_entry, exfat_entry
from test_media_path import lfn
from test_content_roots import checksum
B=0x03005f6c
C=0x0300ec1c

class NavigationTests(unittest.TestCase):
    call=runtime.PlaybackRuntimeTests.call
    def setUp(self):
        self.events=[];self.windows=[];self.window_args=[];self.counts=[];self.enumerations=[]
        runtime.PlaybackRuntimeTests.setUp(self)
        self.image=Image((ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        self.module(21)
    def module(self,n):
        m=self.image.modules[n]
        for kind in ('code','data'):
            off=self.image.l2f(m[kind+'_load'])
            self.cpu.mem_write(m[kind+'_exec'],bytes(self.image.d[off:off+m[kind+'_len']]))
    def word(self,p):return struct.unpack('<I',self.cpu.mem_read(p,4))[0]
    def half(self,p):return struct.unpack('<H',self.cpu.mem_read(p,2))[0]
    def w(self,p,v):self.cpu.mem_write(p,struct.pack('<I',v))
    def h(self,p,v=None):
        if v is None:return self.half(p)
        self.cpu.mem_write(p,struct.pack('<H',v))
    def intercept(self,cpu,address,size,user):
        result=0
        if address==0x0306b040:self.events.append(cpu.reg_read(UC_ARM_REG_R0))
        elif address==0x0306b26a:
            p=cpu.reg_read(UC_ARM_REG_R1)
            self.window_args.append(bytes(cpu.mem_read(p,32)) if p else None)
            self.windows.append((cpu.reg_read(UC_ARM_REG_R0),bytes(cpu.mem_read(p,4)) if p else None))
        elif address==0x0307974e:
            p=cpu.reg_read(UC_ARM_REG_R1);self.counts.append(p)
            cpu.mem_write(p,struct.pack('<3H',3,1,2))
        elif address==0x03079592:self.enumerations.append(cpu.reg_read(UC_ARM_REG_R2))
        elif address==0x0306b082:pass
        else:return runtime.PlaybackRuntimeTests.intercept(self,cpu,address,size,user)
        cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def entry_set(self,fs,name,cluster,directory=False):
        return checksum(exfat_entry(name,cluster,directory)) if fs else lfn(name,b'ENTRY~1    ',cluster,directory)
    def tree(self,fs,both=False,multiple=False):
        self.cpu.mem_write(0x03076b24,bytes([3 if fs else 2]))
        root=2 if fs else 0
        e=lambda n,c,d=False:self.entry_set(fs,n,c,d)
        self.dirs={root:[*e('Parent',10,True),END],10:[*e('Before',11,True),*e('Books',20,True),END],11:[END],20:[*e('.audiobook',90),END]}
        if both or multiple:
            self.dirs[root]=[*e('Parent',10,True),*e('Other',30,True),END]
            self.dirs[30]=[*e('.audiobook' if multiple else '.meditation',91),END]
    def browser(self):
        self.module(31)
        self.cpu.mem_write(B,b'\0'*512)
        self.w(B,0x0300e73c);self.w(0x0300e73c+4,0x0300e9ac);self.w(0x0300e9ac+4,0x0300e73c)
        self.w(B+0x1f4,0x20008000);self.w(0x20008004,0x03005a5e)
        self.call('navigation_browser_init')
    def select(self,index=6):
        self.h(0x0300e708,index)
        self.assertEqual(self.call(0x03079b1e),1)
    def test_overlay_loader_failure_keeps_native_fallback(self):
        self.module(0)
        self.slot=0;self.w(0x0300d454,self.slot)
        for module,stub,hook,length in ((21,0x03079600,0x03079b1e,4),(31,0x0307afa0,0x0307b31a,6)):
            for fail in (True,False):
                self.module(module)
                original=bytes(self.cpu.mem_read(hook,length))
                self.flash_mode='error' if fail else 'ok'
                self.w(0x0309b694,0)
                self.call(stub,0x20007000)
                self.assertEqual(self.h(0x20007000+28),100)
                current=bytes(self.cpu.mem_read(hook,length))
                if fail:self.assertEqual(current,original)
                else:self.assertNotEqual(current,original)

    def test_conditional_categories_and_removed_roots(self):
        for fs in (False,True):
            self.call('playback_init');self.module(21);self.tree(fs,True)
            self.call('navigation_menu_init')
            self.assertEqual(self.word(self.syms['navigation_count']),8)
            table=self.word(0x0307a24c)
            self.assertEqual([self.h(table+8*i+6) for i in (6,7)],[0x83,0x84])
            self.assertEqual(bytes(self.cpu.mem_read(0x03079f70,1)),b'\x07')
            self.assertEqual(bytes(self.cpu.mem_read(0x03079f5e,2)),b'\x07\x20')
            self.dirs={2 if fs else 0:[END]}
            self.select();self.assertFalse(self.windows)
            self.assertEqual(self.word(self.syms['navigation_count']),6)
    def test_single_root_ancestry_and_native_back(self):
        for fs in (False,True):
            self.module(21);self.tree(fs);self.call('navigation_menu_init');self.select();self.browser()
            self.assertEqual(self.h(B+0x1cc),2)
            self.assertEqual(self.word(B+56+20),10);self.assertEqual(self.word(B+112+20),20)
            self.assertEqual(self.h(B+0x1de+2),1)
            self.assertEqual(self.h(C+12),0)
            # Native Back restores the actual parent, including the child row.
            self.call(0x03079c8e)
            self.assertEqual(self.h(B+0x1cc),1)
            self.assertEqual(self.h(B+0x1ee),1)
            self.assertEqual(self.call('navigation_event',0x40000040),0)
    def test_back_ordinal_matches_native_hidden_and_system_visibility(self):
        for fs in (False,True):
            self.module(21);self.tree(fs)
            def flagged(name,cluster,flag):
                entries=self.entry_set(fs,name,cluster,True)
                index,offset=(0,4) if fs else (-1,11)
                raw=bytearray(entries[index]);raw[offset]|=flag;entries[index]=bytes(raw)
                return checksum(entries) if fs else entries
            self.dirs[10]=[*flagged('Hidden',12,2),*flagged('System',13,4),
                           *self.entry_set(fs,'Before',11,True),*self.entry_set(fs,'Books',20,True),END]
            self.dirs[12]=self.dirs[13]=[END]
            self.call('navigation_menu_init');self.select();self.browser()
            # Stock enumeration hides bit 2 but retains system-only folders.
            self.assertEqual(self.h(B+0x1ce+2),2)
            self.assertEqual(self.h(B+0x1de+2),0)
            self.call(0x03079c8e)
            self.assertEqual(self.h(B+0x1cc),1);self.assertEqual(self.h(B+0x1ee),0)
            self.assertEqual(self.h(B+0x1ce+2),2)

    def test_multi_root_chooser_blocks_context_and_enters_selection(self):
        self.tree(False,multiple=True);self.call('navigation_menu_init');self.select();self.browser()
        self.assertEqual(self.h(B+12),2)
        name=bytes(self.cpu.mem_read(0x0300e73c+0x70,512)).decode('utf-16le').split('\0')[0]
        self.assertEqual(name,'/Parent/Books')
        self.assertEqual(self.call('navigation_event',0x20000080),1)
        self.assertEqual(self.call('navigation_event',0x40000004),1)
        self.assertEqual(self.call('navigation_event',0x40000040),1)
        self.assertEqual(self.h(B+0x1cc),1);self.assertEqual(self.word(B+56+20),30)
        self.assertEqual(self.call('navigation_event',0x40000040),0)
    def test_custom_route_initializes_native_flags_and_full_arguments(self):
        self.tree(False);self.call('navigation_menu_init')
        self.cpu.mem_write(0x030057f0,b'\xa5');self.cpu.mem_write(0x0300d695,b'\0')
        self.select()
        self.assertEqual(bytes(self.cpu.mem_read(0x030057f0,1)),b'\0')
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d695,1)),b'\x01')
        self.assertEqual(self.window_args[-1],b'\x06'+b'\0'*31)
    def test_chooser_passes_volume_services_and_blocks_all_context_routes(self):
        self.tree(False,multiple=True);self.call('navigation_menu_init');self.select();self.browser()
        for message in (0x40004000,0x40008000,0x41000000,0x42000000,0):
            self.assertEqual(self.call('navigation_event',message),0)
        for message in (0x20000080,0x40000002,0x40010000,0x50010000):
            self.assertEqual(self.call('navigation_event',message),1)

    def test_chooser_rechecks_the_selected_category(self):
        self.tree(False,multiple=True)
        self.dirs[20]=[*self.entry_set(False,'.audiobook',90),*self.entry_set(False,'.meditation',91),END]
        self.call('navigation_menu_init');self.select();self.browser()
        self.dirs[20]=[*self.entry_set(False,'.meditation',91),END]
        self.assertEqual(self.call('navigation_event',0x40000040),2)
        self.assertEqual(self.windows[-1],(0,None))

    def test_stale_chooser_and_marker_removed_before_init(self):
        self.tree(False,multiple=True);self.call('navigation_menu_init');self.select();self.browser()
        self.dirs[20]=[END]
        self.assertEqual(self.call('navigation_event',0x40000040),2)
        self.assertEqual(self.windows[-1],(0,None))
        self.module(21);self.tree(False);self.call('navigation_menu_init');self.select()
        self.dirs[20]=[END];self.browser()
        self.assertEqual(self.windows[-1][0],9)
        self.assertEqual(self.call('navigation_event',0),2)
        self.assertEqual(self.windows[-1],(0,None))

if __name__=='__main__':unittest.main()
