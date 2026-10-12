"""Ordered queue policy and bounded storage, using production parser and queue."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_m3u import wide, Stats
from test_media_path import Ref
ROOT = Path(__file__).resolve().parents[1]

class QueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        lib = Path(cls.tmp.name)/'queue.dylib'
        subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',
                        '-Wno-unused-parameter','-Isrc','-Iplayback','playback/m3u.c',
                        'playback/queue.c','-o',str(lib)],cwd=ROOT,check=True)
        cls.lib=C.CDLL(str(lib))
        cls.readfn=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint,C.c_void_p,C.c_uint)
        cls.lookupfn=C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(C.c_uint16),C.POINTER(Ref))
        cls.lib.playlist_build.argtypes=[cls.readfn,cls.lookupfn,C.c_void_p,C.c_void_p,C.POINTER(Stats)]
        cls.lib.playlist_ref.argtypes=[C.c_uint,C.POINTER(Ref)]
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def build(self,text,missing=(),directories=(),error=None,exfat=False):
        data=text.encode();self.lookups=[]
        @self.readfn
        def read(ctx,offset,out,length):
            part=data[offset:offset+min(length,17)];C.memmove(out,part,len(part));return len(part)
        @self.lookupfn
        def lookup(ctx,path,out):
            n=0
            while path[n]:n+=1
            name=C.string_at(path,n*2).decode('utf-16le');self.lookups.append(name)
            if name==error:return -2
            if name in missing:return 0
            ref=out.contents;ref.parent.cluster=20;ref.parent.length=4096;ref.parent.flags=3
            ref.index=len(self.lookups)*3;ref.cluster=100+len(self.lookups)
            ref.attrs=16 if name in directories else 0
            ref.filesystem=3 if exfat else 2
            ref.name_units=len(name.rsplit("/",1)[-1].encode("utf-16le"))//2
            return 1
        stats=Stats();result=self.lib.playlist_build(read,lookup,None,wide('/Lists'),C.byref(stats))
        return result,stats
    def refs(self):
        result=[]
        for i in range(self.lib.playlist_count()):
            ref=Ref();self.assertEqual(self.lib.playlist_ref(i,C.byref(ref)),1)
            result.append((ref.parent.cluster,ref.parent.length,ref.parent.flags,ref.index,ref.cluster))
        return result
    def test_order_duplicates_missing_and_non_audio(self):
        result,stats=self.build('../Books/02.FLAC\n../Books/gone.mp3\n../Books/01.mp3\n../Books/02.FLAC\ncover.jpg\nother.m3u\nfolder.flac',missing={'/Books/gone.mp3'},directories={'/Lists/folder.flac'})
        self.assertEqual(result,3);self.assertEqual(stats.accepted,3)
        self.assertEqual([r[3] for r in self.refs()],[3,9,12])
        self.assertEqual(self.refs()[0][:3],(20,4096,3))
    def test_error_discards_partial_queue(self):
        self.assertEqual(self.build('one.mp3\nbroken.mp3',error='/Lists/broken.mp3')[0],-2)
        self.assertEqual(self.lib.playlist_count(),0)
    def test_empty_replaces_previous_queue(self):
        self.assertEqual(self.build('one.mp3')[0],1)
        self.assertEqual(self.build('#empty')[0],0)
        self.assertEqual(self.lib.playlist_count(),0)
    def test_capacity_and_out_of_range(self):
        result,stats=self.build('one.mp3\n'*600)
        self.assertEqual(result,512);self.assertEqual(stats.limited,1)
        ref=Ref();self.assertEqual(self.lib.playlist_ref(512,C.byref(ref)),0)
    def test_exfat_native_open_limit_is_applied_before_queuing(self):
        text='日'*123+'.mp3\n'+'日'*124+'.mp3'
        result,stats=self.build(text,exfat=True)
        self.assertEqual((result,stats.accepted,stats.skipped),(1,1,1))
        self.assertEqual(self.build(text,exfat=False)[0],2)

    def test_standard_extensions_and_unicode(self):
        result,_=self.build('日本語.flac\nä.m4a\nx.mp3x\nx.MP3\nx.wav\nx.ogg\nx.dsf')
        self.assertEqual(result,6)

if __name__=='__main__':unittest.main()
