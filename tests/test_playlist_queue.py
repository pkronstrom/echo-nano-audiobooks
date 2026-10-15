"""Ordered queue policy and bounded storage, using production parser and queue."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_m3u import wide, Stats
from test_media_path import Ref
ROOT = Path(__file__).resolve().parents[1]

class QueuedFile(C.Structure):
    _fields_=[('parent',C.c_uint32),('length',C.c_uint32),('cluster',C.c_uint32)]
class Queue(C.Structure):
    _fields_=[('tracks',QueuedFile*256),('indices',C.c_uint16*256),
              ('flags',C.c_uint8*256),('count',C.c_uint32),('signature',C.c_uint32)]

class Workspace(C.Structure):
    _fields_=[('line',C.c_uint32*256),('path',C.c_uint16*256),('busy',C.c_uint32)]

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
    def build(self,text,missing=(),directories=(),error=None,exfat=False,base='/Lists',chunk=17,queue=None,workspace=None,on_read=None):
        data=text.encode();lookups=[];self.lookups=lookups
        @self.readfn
        def read(ctx,offset,out,length):
            if on_read is not None:on_read(offset)
            part=data[offset:offset+min(length,chunk)];C.memmove(out,part,len(part));return len(part)
        @self.lookupfn
        def lookup(ctx,path,out):
            n=0
            while path[n]:n+=1
            name=C.string_at(path,n*2).decode('utf-16le');lookups.append(name)
            if name==error:return -2
            if name in missing:return 0
            ref=out.contents;ref.parent.cluster=20;ref.parent.length=4096;ref.parent.flags=3
            ref.index=len(lookups)*3;ref.cluster=100+len(lookups)
            ref.attrs=16 if name in directories else 0
            ref.filesystem=3 if exfat else 2
            ref.name_units=len(name.rsplit("/",1)[-1].encode("utf-16le"))//2
            return 1
        stats=Stats()
        if queue is None:
            result=self.lib.playlist_build(read,lookup,None,wide(base),C.byref(stats))
        elif workspace is not None:
            result=self.lib.playlist_queue_build_with_workspace(C.byref(queue),C.byref(workspace),read,lookup,None,wide(base),C.byref(stats))
        else:
            result=self.lib.playlist_queue_build(C.byref(queue),read,lookup,None,wide(base),C.byref(stats))
        return result,stats
    def context_api(self):
        self.assertTrue(hasattr(self.lib,'playlist_queue_build'), 'independent queue API missing')
        self.lib.playlist_queue_build.argtypes=[C.POINTER(Queue),self.readfn,self.lookupfn,C.c_void_p,C.c_void_p,C.POINTER(Stats)]
        self.lib.playlist_queue_ref.argtypes=[C.POINTER(Queue),C.c_uint,C.POINTER(Ref)]
        self.lib.playlist_queue_signature.restype=C.c_uint32

    def test_preview_private_workspace_nests_inside_active_scan(self):
        self.context_api()
        self.assertTrue(hasattr(self.lib,'playlist_queue_build_with_workspace'), 'workspace queue API missing')
        self.lib.playlist_queue_build_with_workspace.argtypes=[C.POINTER(Queue),C.POINTER(Workspace),self.readfn,self.lookupfn,C.c_void_p,C.c_void_p,C.POINTER(Stats)]
        text='one.mp3\ntwo.mp3\nthree.mp3'
        self.build(text);expected=self.refs();signature=self.lib.playlist_signature()
        preview=Queue();workspace=Workspace();results=[]
        def preview_scan(offset):
            if offset==0:
                results.append(self.build('other.mp3\nsecond.mp3',queue=preview,workspace=workspace)[0])
        self.assertEqual(self.build(text,on_read=preview_scan)[0],3)
        self.assertEqual(results,[2])
        self.assertEqual(self.refs(),expected)
        self.assertEqual(self.lib.playlist_signature(),signature)
        self.assertEqual(self.lib.playlist_queue_count(C.byref(preview)),2)
        ref=Ref();self.assertEqual(self.lib.playlist_queue_ref(C.byref(preview),1,C.byref(ref)),1)
        self.assertEqual(ref.index,6)
        self.assertEqual(workspace.busy,0)

    def test_independent_preview_preserves_active_queue(self):
        self.context_api()
        self.build('one.mp3\ntwo.mp3')
        active=self.refs();signature=self.lib.playlist_signature()
        preview=Queue();other=Queue()
        self.assertEqual(self.build('first.mp3\nsecond.mp3\nthird.mp3',queue=preview)[0],3)
        preview_signature=self.lib.playlist_queue_signature(C.byref(preview))
        self.assertEqual(self.build('only.mp3',queue=other)[0],1)
        self.assertEqual(self.lib.playlist_queue_count(C.byref(preview)),3)
        ref=Ref();self.assertEqual(self.lib.playlist_queue_ref(C.byref(preview),2,C.byref(ref)),1)
        self.assertEqual(ref.index,9)
        self.assertEqual(self.lib.playlist_queue_ref(C.byref(other),1,C.byref(ref)),0)
        self.assertNotEqual(self.lib.playlist_queue_signature(C.byref(other)),preview_signature)
        self.assertEqual(self.build('ok.mp3\nbad.mp3',error='/Lists/bad.mp3',queue=other)[0],-2)
        self.assertEqual(self.lib.playlist_queue_count(C.byref(other)),0)
        self.assertEqual(self.lib.playlist_queue_signature(C.byref(other)),0)
        self.assertEqual(self.lib.playlist_queue_signature(C.byref(preview)),preview_signature)
        self.lib.playlist_queue_clear(C.byref(preview))
        self.assertEqual(self.lib.playlist_queue_count(C.byref(preview)),0)
        self.assertEqual(self.refs(),active)
        self.assertEqual(self.lib.playlist_signature(),signature)

    def test_preview_capacity_and_skip_policy(self):
        self.context_api();preview=Queue()
        result,stats=self.build('bad.jpg\none.mp3\n'*300,queue=preview)
        self.assertEqual(result,256);self.assertEqual(stats.limited,1)
        self.assertEqual(self.lib.playlist_queue_count(C.byref(preview)),256)
        self.assertEqual(C.sizeof(Queue),3848)

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
        self.assertEqual(result,256);self.assertEqual(stats.limited,1)
        ref=Ref();self.assertEqual(self.lib.playlist_ref(256,C.byref(ref)),0)
    def test_exfat_native_open_limit_is_applied_before_queuing(self):
        text='日'*123+'.mp3\n'+'日'*124+'.mp3'
        result,stats=self.build(text,exfat=True)
        self.assertEqual((result,stats.accepted,stats.skipped),(1,1,1))
        self.assertEqual(self.build(text,exfat=False)[0],2)

    def test_bookmark_signature_changes_with_order_or_missing_tracks(self):
        self.assertTrue(hasattr(self.lib,'playlist_signature'))
        self.lib.playlist_signature.restype=C.c_uint
        self.build('one.mp3\ntwo.mp3\n')
        signature=self.lib.playlist_signature()
        self.build('one.mp3\ntwo.mp3\n',base='/Moved/Book',chunk=3)
        self.assertEqual(self.lib.playlist_signature(),signature)
        self.build('two.mp3\none.mp3\n')
        self.assertNotEqual(self.lib.playlist_signature(),signature)
        self.build('one.mp3\ntwo.mp3\n',missing={'/Lists/one.mp3'})
        missing_first=self.lib.playlist_signature()
        self.build('one.mp3\ntwo.mp3\n',missing={'/Lists/two.mp3'})
        self.assertNotEqual(self.lib.playlist_signature(),missing_first)

    def test_standard_extensions_and_unicode(self):
        result,_=self.build('日本語.flac\nä.m4a\nx.mp3x\nx.MP3\nx.wav\nx.ogg\nx.dsf')
        self.assertEqual(result,6)

if __name__=='__main__':unittest.main()
