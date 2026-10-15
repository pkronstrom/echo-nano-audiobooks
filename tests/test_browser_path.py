"""Recover browser selections from the audited native node/ancestry layout."""
import ctypes as C
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from test_media_path import Dir, lfn
from test_music_filter import fat_entry, exfat_entry, END
ROOT=Path(__file__).resolve().parents[1]

class BrowserPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();lib=Path(cls.tmp.name)/'browser.dylib'
        subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',
                        '-Wno-unused-parameter','-Isrc','-Iplayback','playback/path.c',
                        'playback/browser.c','-o',str(lib)],cwd=ROOT,check=True)
        cls.lib=C.CDLL(str(lib))
        cls.readfn=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int,C.POINTER(Dir),C.c_uint,C.c_void_p)
        cls.lib.media_browser_path.argtypes=[cls.readfn,C.c_void_p,C.c_int,C.c_void_p,C.c_void_p,C.c_uint,C.c_void_p]
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def path(self,exfat,ancestors,name,parent,index=0,depth=None,directory_cluster=None):
        browser=bytearray(512);node=bytearray(624)
        struct.pack_into('<H',browser,0x1cc,len(ancestors) if depth is None else depth)
        for i,cluster in enumerate(ancestors,1):struct.pack_into('<I',browser,i*56+(24 if exfat else 20),cluster)
        struct.pack_into('<II',node,8,parent,index)
        encoded=name.encode('utf-16le')+b'\0\0';node[0x70:0x70+len(encoded)]=encoded
        @self.readfn
        def read(ctx,fs,desc,i,out):
            cluster=desc.contents.cluster
            if fs and not cluster:cluster=desc.contents.cluster=2
            entries=self.dirs.get(cluster,[END])
            if i>=len(entries):return 9
            C.memmove(out,entries[i],32);return 0
        out=(C.c_uint16*256)()
        function=self.lib.media_browser_path
        if directory_cluster is not None:
            function=self.lib.media_browser_directory
            function.argtypes=self.lib.media_browser_path.argtypes
            struct.pack_into('<H',node,0x63,directory_cluster>>16)
            struct.pack_into('<H',node,0x69,directory_cluster&65535)
        result=function(read,None,exfat,(C.c_ubyte*len(browser)).from_buffer(browser),
                                          (C.c_ubyte*len(node)).from_buffer(node),2,out)
        n=0
        while out[n]:n+=1
        return result,C.string_at(out,n*2).decode('utf-16le')
    def test_nested_selection_and_root_on_both_filesystems(self):
        for exfat in (False,True):
            with self.subTest(exfat=exfat):
                if exfat:
                    self.dirs={2:[*exfat_entry('Kirjat 日本語',20,True),*exfat_entry('root.m3u',91),END],
                               20:[*exfat_entry('Meditaatio',30,True),END],30:[*exfat_entry('list.m3u',90),END]}
                    root_index=3
                else:
                    folder=lfn('Kirjat 日本語',b'KIRJAT~1   ',20,True)
                    self.dirs={0:[*folder,fat_entry(b'ROOT    M3U',91),END],
                               20:[*lfn('Meditaatio',b'MEDITA~1   ',30,True),END],30:[fat_entry(b'LIST    M3U',90),END]}
                    root_index=len(folder)
                self.assertEqual(self.path(exfat,[20,30],'list.m3u',30),(1,'/Kirjat 日本語/Meditaatio/list.m3u'))
                self.assertEqual(self.path(exfat,[],'root.m3u',2,root_index),(1,'/root.m3u'))
    def test_directory_path_requires_matching_type_and_cluster(self):
        for exfat in (False,True):
            self.dirs={2:[*exfat_entry('Book',20,True),END]} if exfat else {0:[fat_entry(b'BOOK       ',20,True),END]}
            self.assertEqual(self.path(exfat,[],'Book',2,directory_cluster=20),(1,'/Book'))
            self.assertEqual(self.path(exfat,[],'Book',2,directory_cluster=21),(0,''))
            self.assertEqual(self.path(exfat,[],'Book',2),(0,''))
        self.dirs={0:[fat_entry(b'LIST    M3U',90),END]}
        self.assertEqual(self.path(False,[],'list.m3u',2,directory_cluster=90),(0,''))

    def test_stale_parent_index_and_invalid_depth_are_rejected(self):
        self.dirs={0:[fat_entry(b'LIST    M3U',90),END]}
        for args in ((False,[],'list.m3u',30,0,None),(False,[],'list.m3u',2,1,None),(False,[],'list.m3u',2,0,8)):
            with self.subTest(args=args):self.assertEqual(self.path(*args),(0,''))
    def test_name_cannot_escape_ancestry(self):
        self.dirs={0:[fat_entry(b'LIST    M3U',90),END]}
        for name in ('../list.m3u','sub/list.m3u','sub\\list.m3u','..',''):
            self.assertEqual(self.path(False,[],name,2),(0,''))

if __name__=='__main__':unittest.main()
