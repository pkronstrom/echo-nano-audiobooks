"""Physical UTF-16 lookup fixtures; no dependence on filtered music records."""
import ctypes as C
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from test_music_filter import fat_entry, exfat_entry, END
from test_m3u import ROOT, wide

def lfn(name, short=b'LONGNA~1FLA', cluster=20, directory=False):
    checksum = 0
    for b in short: checksum = (((checksum & 1) << 7) + (checksum >> 1) + b) & 255
    data = (name+'\0').encode('utf-16le')
    data += b'\xff' * ((-len(data)) % 26)
    entries = []
    for index in range(len(data)//26, 0, -1):
        e = bytearray(32)
        e[0] = index | (0x40 if index == len(data)//26 else 0)
        e[11], e[13] = 15, checksum
        part = data[(index-1)*26:index*26]
        e[1:11], e[14:26], e[28:32] = part[:10], part[10:22], part[22:]
        entries.append(bytes(e))
    return [*entries, fat_entry(short, cluster, directory)]

class Dir(C.Structure):
    _fields_ = [(n, C.c_uint) for n in ('cluster', 'length', 'index', 'flags')]
class Ref(C.Structure):
    _fields_ = [('parent', Dir), ('index', C.c_uint), ('cluster', C.c_uint), ('size', C.c_uint), ('flags', C.c_ubyte), ('attrs', C.c_ubyte), ('filesystem', C.c_ubyte), ('name_units', C.c_ubyte)]

class PathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        lib = Path(cls.tmp.name)/'path.dylib'
        subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',
                        '-Wno-unused-parameter','-Isrc','-Iplayback','playback/path.c','-o',str(lib)], cwd=ROOT,check=True)
        cls.lib = C.CDLL(str(lib))
        cls.read_fn = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_int, C.POINTER(Dir), C.c_uint, C.c_void_p)
        cls.lib.media_resolve.argtypes = [cls.read_fn,C.c_void_p,C.c_int,C.c_void_p,C.POINTER(Ref)]

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def setUp(self): self.dirs, self.calls, self.errors = {}, [], {}

    def reader(self):
        @self.read_fn
        def read(ctx, fs, parent, index, out):
            cluster = parent.contents.cluster
            if fs and not cluster:
                cluster = parent.contents.cluster = 2
                parent.contents.flags = 1
            self.calls.append((cluster, index))
            if cluster in self.errors: return self.errors[cluster]
            entries = self.dirs.get(cluster, [END])
            if index >= len(entries): return 9
            C.memmove(out, entries[index], 32)
            return 0
        return read

    def resolve(self, path, exfat=False):
        ref = Ref()
        result = self.lib.media_resolve(self.reader(),None,exfat,wide(path),C.byref(ref))
        return result, ref

    def directory_name(self, cluster, exfat=False, parent_cluster=0):
        self.lib.media_directory_name.argtypes=[self.read_fn,C.c_void_p,C.c_int,C.POINTER(Dir),C.c_uint,C.c_void_p,C.POINTER(Ref)]
        parent=Dir(parent_cluster,4096,0,3);name=(C.c_uint16*256)();ref=Ref()
        result=self.lib.media_directory_name(self.reader(),None,exfat,C.byref(parent),cluster,name,C.byref(ref))
        n=0
        while name[n]:n+=1
        return result,C.string_at(name,n*2).decode('utf-16le'),ref

    def test_directory_identity_recovers_unicode_name_and_geometry(self):
        for exfat in (False,True):
            with self.subTest(exfat=exfat):
                if exfat:
                    self.dirs={2:[*exfat_entry('Wrong',29,True),*exfat_entry('Kirjat 日本語',30,True),END]}
                else:self.dirs={0:[fat_entry(b'WRONG      ',29,True),*lfn('Kirjat 日本語',b'KIRJAT~1   ',30,True),END]}
                result,name,ref=self.directory_name(30,exfat)
                self.assertEqual((result,name,ref.cluster),(1,'Kirjat 日本語',30))
                self.assertEqual(ref.attrs & 16,16)
                self.assertEqual(self.directory_name(99,exfat)[0],0)

    def test_directory_identity_never_accepts_file_or_dot_entry(self):
        self.dirs={0:[fat_entry(b'NOTADIR FLA',30),fat_entry(b'..         ',30,True),END]}
        self.assertEqual(self.directory_name(30)[0],0)

    def test_directory_identity_falls_back_to_checked_short_alias(self):
        entries=lfn('Wrong long name',b'SAFE       ',30,True)
        corrupt=bytearray(entries[0]);corrupt[13]^=1;entries[0]=bytes(corrupt)
        self.dirs={0:[*entries,END]}
        self.assertEqual(self.directory_name(30)[:2],(1,'SAFE'))

    def test_nested_fat_unicode_and_long_names(self):
        self.dirs = {0:[*lfn('Kirjat 日本語', b'KIRJAT~1   ',30,True),END],
                     30:[*lfn('Chapter 10 — älä unohda.flac',cluster=100),END]}
        result, ref = self.resolve('/Kirjat 日本語/Chapter 10 — älä unohda.flac')
        self.assertEqual(result,1)
        self.assertEqual((ref.parent.cluster, ref.cluster, ref.index),(30,100,3))

    def test_fat_short_alias_and_ascii_case(self):
        self.dirs = {0:[fat_entry(b'MUSIC      ',30,True),END],30:[fat_entry(b'TRACK01 FLA',100),END]}
        result, ref = self.resolve('/music/track01.fla')
        self.assertEqual(result,1)
        self.assertEqual(ref.cluster,100)

    def test_fat_full_thirteen_character_lfn_needs_no_terminator(self):
        entries=lfn('12345678.flac')
        # FAT permits one completely full LFN entry, with no NUL code unit.
        e=bytearray(entries[-2]);e[0]=0x41
        self.dirs[0]=[bytes(e),entries[-1],END]
        self.assertEqual(self.resolve('/12345678.flac')[0],1)

    def test_broken_fat_lfn_is_not_used(self):
        entries=lfn('Long name.flac')
        e=bytearray(entries[0]);e[13]^=1;entries[0]=bytes(e)
        self.dirs[0]=[*entries,END]
        self.assertEqual(self.resolve('/Long name.flac')[0],0)
        self.assertEqual(self.resolve('/LONGNA~1.FLA')[0],1)

    def test_exfat_unicode_and_contiguous_parent(self):
        self.dirs={2:[*exfat_entry('Meditation 日本語',30,True,flags=3),END],
                   30:[*exfat_entry('Phase 01 🎵.flac',100,length=12345),END]}
        result,ref=self.resolve('/Meditation 日本語/Phase 01 🎵.flac',True)
        self.assertEqual(result,1)
        self.assertEqual((ref.parent.cluster,ref.parent.length,ref.parent.flags),(30,4096,3))
        self.assertEqual((ref.cluster,ref.size,ref.flags),(100,12345,3))

    def test_exfat_matches_every_character_and_full_length(self):
        self.dirs={2:[*exfat_entry('axb.flac',100),*exfat_entry('ayb.flac',200),END]}
        self.assertEqual(self.resolve('/ayb.flac',True)[1].cluster,200)
        self.assertEqual(self.resolve('/axb.flac.extra',True)[0],0)
        self.assertEqual(self.resolve('/azb.flac',True)[0],0)

    def test_exfat_deleted_entry_is_not_found(self):
        entries=exfat_entry('gone.flac');e=bytearray(entries[0]);e[0]=5;entries[0]=bytes(e)
        self.dirs={2:[*entries,END]}
        self.assertEqual(self.resolve('/gone.flac',True)[0],0)

    def test_missing_component_and_file_as_directory(self):
        self.dirs={0:[fat_entry(),END]}
        self.assertEqual(self.resolve('/missing/file.flac')[0],0)
        self.assertEqual(self.resolve('/track.fla/another.flac')[0],0)

    def test_hidden_content_remains_deliberately_accessible(self):
        e=bytearray(fat_entry());e[11]|=2
        self.dirs={0:[bytes(e),END]}
        self.assertEqual(self.resolve('/TRACK.FLA')[0],1)

    def test_io_error_is_distinct_from_missing(self):
        self.errors[0]=7
        self.assertLess(self.resolve('/track.fla')[0],0)

    def test_only_normalized_absolute_paths_are_accepted(self):
        for path in ('relative.flac','/../track.flac','/a/./b.flac','/'):
            with self.subTest(path=path): self.assertLess(self.resolve(path)[0],0)

if __name__=='__main__': unittest.main()
