"""Bounded physical collection-root discovery, including corrupt/stale media."""
import ctypes as C
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from test_media_path import Dir, Ref, lfn
from test_music_filter import fat_entry, exfat_entry, END
ROOT = Path(__file__).resolve().parents[1]

class Root(C.Structure):
    _fields_ = [('index', C.c_uint * 7), ('cluster', C.c_uint * 7),
                ('depth', C.c_ubyte), ('kind', C.c_ubyte), ('pad', C.c_ushort)]

def checksum(entries):
    entries = [bytearray(e) for e in entries]
    value = 0
    for i, e in enumerate(entries):
        for j, b in enumerate(e):
            if i == 0 and j in (2, 3): continue
            value = ((value >> 1) + ((value & 1) << 15) + b) & 65535
    struct.pack_into('<H', entries[0], 2, value)
    return [bytes(e) for e in entries]

class ContentRootsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        lib = Path(cls.tmp.name) / 'roots.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Wextra',
                        '-Werror', '-Isrc', '-Iplayback', 'playback/content_roots.c',
                        '-o', str(lib)], cwd=ROOT, check=True)
        cls.lib = C.CDLL(str(lib))
        cls.read_fn = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_int, C.POINTER(Dir), C.c_uint, C.c_void_p)
        cls.lib.content_scan.argtypes = [cls.read_fn, C.c_void_p, C.c_int, C.POINTER(Root), C.c_uint]
        cls.lib.content_root_chain.argtypes = [cls.read_fn, C.c_void_p, C.c_int, C.POINTER(Root), C.POINTER(Ref)]
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self): self.dirs, self.calls = {}, 0
    def entry(self, fs, name, cluster=20, directory=False):
        return checksum(exfat_entry(name, cluster, directory)) if fs else lfn(name, b'ENTRY~1    ', cluster, directory)
    def reader(self):
        @self.read_fn
        def read(ctx, fs, desc, index, out):
            self.calls += 1
            cluster = desc.contents.cluster
            if fs and not cluster: cluster = desc.contents.cluster = 2
            entries = self.dirs.get(cluster, [END])
            if entries is None: return 7
            if index >= len(entries): return 9
            C.memmove(out, entries[index], 32)
            return 0
        return read
    def scan(self, fs, cap=8):
        roots = (Root * 8)()
        n = self.lib.content_scan(self.reader(), None, fs, roots, cap)
        return n, roots
    def test_absent_nested_multiple_and_both_markers(self):
        for fs in (0, 1):
            base = 2 if fs else 0
            self.dirs = {base: [END]}
            self.assertEqual(self.scan(fs)[0], 0)
            self.dirs = {base: [*self.entry(fs, 'Arbitrary name', 20, True), END],
                         20: [*self.entry(fs, 'Nested', 30, True), *self.entry(fs, '.AUDIOBOOK'), END],
                         30: [*self.entry(fs, '.audiobook'), *self.entry(fs, '.Meditation'), END]}
            n, roots = self.scan(fs)
            self.assertEqual(n, 2)
            self.assertEqual([(r.depth, r.kind) for r in roots[:n]], [(2, 3), (1, 1)])
            self.assertEqual(list(roots[0].cluster)[:2], [20, 30])
            out = (Ref * 7)()
            self.assertEqual(self.lib.content_root_chain(self.reader(), None, fs, C.byref(roots[0]), out), 1)
            self.dirs[20] = [END]
            self.assertEqual(self.lib.content_root_chain(self.reader(), None, fs, C.byref(roots[0]), out), 0)
    def test_card_root_and_regular_file_exact_names(self):
        for fs in (0, 1):
            base = 2 if fs else 0
            self.dirs = {base: [*self.entry(fs, '.audiobooks'), *self.entry(fs, '.meditation.old'),
                               *self.entry(fs, '.audiobook', 30, True), END]}
            self.assertEqual(self.scan(fs)[0], 0)
            self.dirs[base] = [*self.entry(fs, '.meditation'), END]
            n, roots = self.scan(fs)
            self.assertEqual((n, roots[0].depth, roots[0].kind), (1, 0, 2))
    def test_deleted_bad_checksum_and_hidden_directories(self):
        for fs in (0, 1):
            base = 2 if fs else 0
            marker = list(self.entry(fs, '.audiobook'))
            bad = bytearray(marker[0]); bad[2 if fs else 13] ^= 1; marker[0] = bytes(bad)
            self.dirs = {base: [*marker, END]}
            self.assertEqual(self.scan(fs)[0], 0)
            marker = list(self.entry(fs, '.audiobook'))
            bad = bytearray(marker[0]); bad[0] = 5 if fs else 0xe5; marker[0] = bytes(bad)
            self.dirs[base] = [*marker, END]
            self.assertEqual(self.scan(fs)[0], 0)
            folder = list(self.entry(fs, 'Hidden', 30, True))
            index = 0 if fs else -1
            bad = bytearray(folder[index]); bad[4 if fs else 11] |= 2; folder[index] = bytes(bad)
            if fs: folder = checksum(folder)
            self.dirs = {base: [*folder, END], 30: [*self.entry(fs, '.audiobook'), END]}
            self.assertEqual(self.scan(fs)[0], 0)
    def test_capacity_io_and_cycle(self):
        for fs in (0, 1):
            base = 2 if fs else 0
            self.dirs = {base: [*self.entry(fs, 'Folder', 30, True), END],
                         30: [*self.entry(fs, 'Cycle', 30, True), *self.entry(fs, '.audiobook'), END]}
            self.assertEqual(self.scan(fs)[0], 1)
            self.assertEqual(self.scan(fs, 0)[0], -1)
            self.dirs[30] = None
            self.assertEqual(self.scan(fs)[0], -2)
    def test_hidden_marker_and_malformed_exfat_stream(self):
        for fs in (0, 1):
            base = 2 if fs else 0
            marker = list(self.entry(fs, '.audiobook'))
            index = 0 if fs else -1
            changed = bytearray(marker[index]); changed[4 if fs else 11] |= 6
            marker[index] = bytes(changed)
            if fs: marker = checksum(marker)
            self.dirs = {base: [*marker, END]}
            self.assertEqual(self.scan(fs)[0], 1)
        for offset, value in ((0, 0xc1), (3, 12), (28, 1), (1, 7)):
            marker = list(self.entry(1, '.audiobook'))
            changed = bytearray(marker[1]); changed[offset] = value
            marker[1] = bytes(changed)
            self.dirs = {2: [*checksum(marker), END]}
            self.assertEqual(self.scan(1)[0], 0)
    def test_ninth_root_and_directory_work_limit_reject_partial_output(self):
        self.dirs = {0: []}
        for i in range(9):
            self.dirs[0] += self.entry(0, 'Folder', 20+i, True)
            self.dirs[20+i] = self.entry(0, '.audiobook')
        self.assertEqual(self.scan(0)[0], -1)
        self.dirs = {0: [fat_entry(b'FOLDER     ', i+20, True) for i in range(2048)]}
        self.assertEqual(self.scan(0)[0], -1)
    def test_depth_and_global_entry_budget(self):
        for fs in (0, 1):
            base = 2 if fs else 0
            self.dirs = {base: self.entry(fs, 'Folder', 20, True)}
            for i in range(20, 28): self.dirs[i] = self.entry(fs, 'Folder', i+1, True)
            self.dirs[26] += self.entry(fs, '.audiobook')
            self.dirs[27] += self.entry(fs, '.meditation')
            n, roots = self.scan(fs)
            self.assertEqual((n, roots[0].depth, roots[0].kind), (1, 7, 1))
        self.dirs = {0: [fat_entry()] * 65537}
        self.assertEqual(self.scan(0)[0], -1)

if __name__ == '__main__': unittest.main()
