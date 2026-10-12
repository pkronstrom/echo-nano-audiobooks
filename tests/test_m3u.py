"""Production streaming parser, including deliberately short read chunks."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]

def wide(text):
    data = text.encode('utf-16le') + b'\0\0'
    return (C.c_uint16 * (len(data)//2)).from_buffer_copy(data)

class Stats(C.Structure):
    _fields_ = [(name, C.c_uint) for name in ('accepted', 'skipped', 'invalid', 'limited')]

class PlaylistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        lib = Path(cls.tmp.name)/'m3u.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Isrc', '-Iplayback', 'playback/m3u.c', '-o', str(lib)],
                       cwd=ROOT, check=True)
        cls.lib = C.CDLL(str(lib))
        cls.read_fn = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_uint, C.c_void_p, C.c_uint)
        cls.entry_fn = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(C.c_uint16), C.c_uint)
        cls.lib.m3u_scan.argtypes = [cls.read_fn, cls.entry_fn, C.c_void_p, C.c_void_p, C.POINTER(Stats)]

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def scan(self, data, base='/Playlists', missing=(), chunk=7, read_error=False):
        if isinstance(data, str): data = data.encode('utf-8')
        self.entries = []
        @self.read_fn
        def read(ctx, offset, out, length):
            if read_error: return -1
            part = data[offset:offset + min(length, chunk)]
            C.memmove(out, part, len(part))
            return len(part)
        @self.entry_fn
        def entry(ctx, path, offset):
            n = 0
            while path[n]: n += 1
            text = C.string_at(path, n*2).decode('utf-16le')
            self.entries.append((text, offset))
            return int(text not in missing)
        stats = Stats()
        result = self.lib.m3u_scan(read, entry, None, wide(base), C.byref(stats))
        return result, stats

    def test_order_comments_and_missing_entries(self):
        result, stats = self.scan('#EXTM3U\n#EXTINF:3,Title\n../Music/2.flac\n../Music/missing.flac\n../Music/1.flac\n', missing={'/Music/missing.flac'})
        self.assertEqual(result, 0)
        self.assertEqual([p for p, _ in self.entries], ['/Music/2.flac', '/Music/missing.flac', '/Music/1.flac'])
        self.assertEqual((stats.accepted, stats.skipped), (2, 1))

    def test_unicode_bom_spaces_and_all_line_endings(self):
        result, stats = self.scan('\ufeff#EXTM3U\r\n../Musiikki äö/日本語.flac\r../Books/🎵 01.mp3\nlast.flac', chunk=1)
        self.assertEqual(result, 0)
        self.assertEqual(stats.accepted, 3)
        self.assertEqual([p for p, _ in self.entries], ['/Musiikki äö/日本語.flac', '/Books/🎵 01.mp3', '/Playlists/last.flac'])

    def test_path_normalization_and_relocation(self):
        _, stats = self.scan('../Music/./Album/../1.flac\n..\\Music\\2.flac', base='/Collection/Playlists')
        self.assertEqual(stats.accepted, 2)
        self.assertEqual([p for p, _ in self.entries], ['/Collection/Music/1.flac', '/Collection/Music/2.flac'])

    def test_bad_paths_and_utf8_do_not_discard_later_tracks(self):
        for bad in (b'../../escape.flac', b'/absolute.flac', b'https://example/a.flac', b'bad\0file', b'\xc0\xaf.flac', b'\xed\xa0\x80.flac', b'\xf4\x90\x80\x80.flac'):
            with self.subTest(bad=bad):
                _, stats = self.scan(bad + b'\ngood.flac\n')
                self.assertEqual([p for p, _ in self.entries], ['/Playlists/good.flac'])
                self.assertEqual(stats.invalid, 1)

    def test_overlong_line_is_skipped_as_one_line(self):
        _, stats = self.scan('a'*2000 + '\ngood.flac')
        self.assertEqual([p for p, _ in self.entries], ['/Playlists/good.flac'])
        self.assertEqual(stats.invalid, 1)

    def test_path_capacity_counts_utf16_units(self):
        _, stats = self.scan('a'*250 + '.flac\ngood.flac')
        self.assertEqual(stats.invalid, 1)
        self.assertEqual(stats.accepted, 1)

    def test_entry_limit_is_bounded_even_if_every_track_is_missing(self):
        _, stats = self.scan('missing.flac\n'*600, missing={'/Playlists/missing.flac'}, chunk=256)
        self.assertEqual(len(self.entries), 512)
        self.assertEqual(stats.skipped, 512)
        self.assertEqual(stats.limited, 1)

    def test_offsets_identify_original_lines(self):
        data = b'#x\r\none.flac\r\ntwo.flac'
        _, stats = self.scan(data)
        self.assertEqual(self.entries, [('/Playlists/one.flac', 4), ('/Playlists/two.flac', 14)])
        self.assertEqual(stats.accepted, 2)

    def test_byte_limit_never_emits_a_line_crossing_the_boundary(self):
        data = b'#' + b'a'*(1048576-6) + b'\n' + b'good.flac\n'
        _, stats = self.scan(data, chunk=200)
        self.assertEqual(self.entries, [])
        self.assertEqual(stats.limited, 1)

    def test_io_failure_propagates(self):
        result, stats = self.scan('one.flac', read_error=True)
        self.assertLess(result, 0)
        self.assertEqual(self.entries, [])

    def test_blank_and_comment_only_playlists(self):
        _, stats = self.scan('\n\r\n#EXTM3U\n#EXTINF:1,Hello')
        self.assertEqual(self.entries, [])
        self.assertEqual((stats.accepted, stats.invalid), (0, 0))

if __name__ == '__main__': unittest.main()
