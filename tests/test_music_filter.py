"""Execute the production marker filter against raw FAT/exFAT directory fixtures."""
import ctypes as C
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
END = bytes(32)


def fat_entry(name=b"TRACK   FLA", cluster=20, directory=False):
    e = bytearray(32)
    e[:11] = name
    e[11] = 0x10 if directory else 0x20
    struct.pack_into("<H", e, 20, cluster >> 16)
    struct.pack_into("<H", e, 26, cluster & 65535)
    return bytes(e)


def fat_marker(name=".nomusic", short=b"NOMUSI~1   "):
    e = bytearray(b"\xff" * 32)
    e[0], e[11], e[12] = 0x41, 0x0f, 0
    checksum = 0
    for b in short:
        checksum = (((checksum & 1) << 7) + (checksum >> 1) + b) & 255
    e[13] = checksum
    e[26:28] = b"\0\0"
    encoded = (name + "\0").encode("utf-16le").ljust(26, b"\xff")
    e[1:11], e[14:26], e[28:32] = encoded[:10], encoded[10:22], encoded[22:26]
    return [bytes(e), fat_entry(short, cluster=0)]


def exfat_entry(name, cluster=20, directory=False, flags=3, length=4096):
    primary, stream = bytearray(32), bytearray(32)
    names = []
    encoded = name.encode("utf-16le")
    for i in range(0, len(encoded), 30):
        e = bytearray(32)
        e[0] = 0xc1
        e[2:2 + len(encoded[i:i + 30])] = encoded[i:i + 30]
        names.append(bytes(e))
    primary[0], primary[1] = 0x85, 1 + len(names)
    primary[4] = 0x10 if directory else 0x20
    stream[0], stream[1], stream[3] = 0xc0, flags, len(encoded) // 2
    struct.pack_into("<Q", stream, 8, length)
    struct.pack_into("<I", stream, 20, cluster)
    struct.pack_into("<Q", stream, 24, length)
    return [bytes(primary), bytes(stream), *names]


class MusicFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        lib = Path(cls.tmp.name) / "filter.dylib"
        subprocess.run(["cc", "-shared", "-fPIC", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "src"), str(ROOT / "src/music_filter.c"),
                        str(ROOT / "tests/music_filter_shim.c"), "-o", str(lib)], check=True)
        cls.lib = C.CDLL(str(lib))
        cls.fat_fn = C.CFUNCTYPE(C.c_int, C.POINTER(C.c_ubyte), C.c_uint, C.c_uint)
        cls.exfat_fn = C.CFUNCTYPE(C.c_int, C.POINTER(C.c_ubyte), C.c_void_p, C.c_uint)
        cls.lib.music_test_readers.argtypes = [cls.fat_fn, cls.exfat_fn]
        cls.lib.music_fat_entry.argtypes = [C.c_void_p, C.c_uint, C.c_uint]
        cls.lib.music_exfat_entry.argtypes = [C.c_void_p, C.c_void_p, C.c_uint]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.fat = {0: [END]}
        self.exfat = {2: [END]}
        self.errors = {}
        self.calls = []

        def read(out, cluster, index, fs):
            self.calls.append((fs, cluster, index))
            if (fs, cluster) in self.errors:
                return self.errors[fs, cluster]
            entries = (self.fat if fs == "fat" else self.exfat).get(cluster, [END])
            if index >= len(entries):
                return 9  # stock raw-reader end-of-cluster-chain status
            C.memmove(out, entries[index], 32)
            return 0

        self.fat_cb = self.fat_fn(lambda out, cluster, index: read(out, cluster, index, "fat"))

        def exfat_read(out, desc, index):
            raw = C.string_at(desc, 13)
            cluster, length = struct.unpack_from("<II", raw)
            if not cluster:
                C.memmove(desc, struct.pack("<I", 2), 4)
                cluster = 2
            if cluster != 2:
                self.assertEqual(length, 4096)
                self.assertIn(raw[12], (1, 3))
            return read(out, cluster, index, "exfat")

        self.exfat_cb = self.exfat_fn(exfat_read)
        self.lib.music_test_readers(self.fat_cb, self.exfat_cb)
        self.lib.music_filter_reset()

    def fat_get(self, cluster, index=0):
        out = (C.c_ubyte * 32)()
        result = self.lib.music_fat_entry(out, cluster, index)
        return result, bytes(out)

    def exfat_get(self, cluster=2, index=0):
        out = (C.c_ubyte * 32)()
        desc = C.create_string_buffer(struct.pack("<IIIB3x", cluster, 4096, 0, 3))
        result = self.lib.music_exfat_entry(out, desc, index)
        return result, bytes(out)

    def test_activity_markers_exclude_roots_and_subtrees(self):
        for name in (".audiobook", ".meditation", ".AuDiObOoK", ".Meditation"):
            with self.subTest(name=name):
                self.fat = {0: [fat_entry(b"ROOT       ", 30, True), END],
                            30: [fat_entry(), *fat_marker(name), END]}
                self.lib.music_filter_reset()
                self.assertTrue(self.fat_get(0)[1][11] & 2)
                self.assertTrue(self.fat_get(30)[1][11] & 2)
                self.exfat = {2: [*exfat_entry("Root", 30, True), END],
                              30: [*exfat_entry("track.mp3"), *exfat_entry(name, 0, length=0), END]}
                self.lib.music_filter_reset()
                self.assertTrue(self.exfat_get()[1][4] & 2)
                self.assertTrue(self.exfat_get(30)[1][4] & 2)

    def test_activity_marker_exact_names_and_regular_files_only(self):
        for name in (".audiobooks", ".meditations", ".audiobookx", "audiobook", ".meditationx"):
            self.fat = {0: [fat_entry(), *fat_marker(name), END]}
            self.exfat = {2: [*exfat_entry("track.mp3"), *exfat_entry(name, 0, length=0), END]}
            self.lib.music_filter_reset()
            self.assertFalse(self.fat_get(0)[1][11] & 2, name)
            self.assertFalse(self.exfat_get()[1][4] & 2, name)
        for name in (".audiobook", ".meditation"):
            marker = fat_marker(name)
            e = bytearray(marker[1]); e[11] = 16; marker[1] = bytes(e)
            self.fat = {0: [fat_entry(), *marker, END]}
            self.exfat = {2: [*exfat_entry("track.mp3"), *exfat_entry(name, 30, True), END], 30: [END]}
            self.lib.music_filter_reset()
            self.assertFalse(self.fat_get(0)[1][11] & 2)
            self.assertFalse(self.exfat_get()[1][4] & 2)

    def test_unmarked_fat_entries_unchanged(self):
        self.fat[0] = [fat_entry(), fat_entry(b"MUSIC      ", 30, True), END]
        for i in range(3):
            self.assertEqual(self.fat_get(0, i), (0, self.fat[0][i]))

    def test_fat_marker_after_audio_hides_parent_directory(self):
        self.fat[0] = [fat_entry(b"BOOKS      ", 30, True), END]
        self.fat[30] = [fat_entry(), *fat_marker(), END]
        before = dict(self.fat)
        status, e = self.fat_get(0)
        self.assertEqual(status, 0)
        self.assertTrue(e[11] & 2)
        self.assertEqual(self.fat, before)

    def test_fat_root_marker_hides_files_and_child_folders(self):
        self.fat[0] = [fat_entry(), fat_entry(b"BOOKS      ", 30, True), *fat_marker(), END]
        for i in (0, 1):
            self.assertTrue(self.fat_get(0, i)[1][11] & 2)

    def test_root_marker_covers_direct_record_pass(self):
        self.fat[0] = [fat_entry(b"RECORD     ", 30, True), *fat_marker(), END]
        self.fat[30] = [fat_entry(), END]
        self.assertTrue(self.fat_get(30)[1][11] & 2)
        self.exfat[2] = [*exfat_entry("RECORD", 30, True), *exfat_entry(".nomusic", 0, length=0), END]
        self.exfat[30] = [*exfat_entry("record.wav"), END]
        self.assertTrue(self.exfat_get(cluster=30)[1][4] & 2)

    def test_fat_marker_is_case_insensitive(self):
        self.fat[0] = [fat_entry(), *fat_marker(".NoMusic"), END]
        self.assertTrue(self.fat_get(0)[1][11] & 2)

    def test_fat_deleted_malformed_and_similar_names_do_not_match(self):
        for variant in ("deleted", "checksum", "directory", ".nomusicx", "nomusic"):
            with self.subTest(variant=variant):
                marker = fat_marker(variant if variant.startswith(".") or variant == "nomusic" else ".nomusic")
                if variant == "deleted":
                    e = bytearray(marker[1]); e[0] = 0xe5; marker[1] = bytes(e)
                elif variant == "checksum":
                    e = bytearray(marker[0]); e[13] ^= 1; marker[0] = bytes(e)
                elif variant == "directory":
                    e = bytearray(marker[1]); e[11] = 0x10; marker[1] = bytes(e)
                self.fat[0] = [fat_entry(), *marker, END]
                self.lib.music_filter_reset()
                self.assertFalse(self.fat_get(0)[1][11] & 2)

    def test_fat_end_of_full_directory_is_not_an_io_error(self):
        self.fat[0] = [fat_entry()]
        self.assertFalse(self.fat_get(0)[1][11] & 2)

    def test_probe_io_error_excludes_child_and_is_counted(self):
        self.fat[0] = [fat_entry(b"BOOKS      ", 30, True), END]
        self.errors["fat", 30] = 7
        self.assertTrue(self.fat_get(0)[1][11] & 2)
        self.assertEqual(C.c_uint.in_dll(self.lib, "music_filter_errors").value, 1)

    def test_original_reader_error_is_propagated(self):
        self.errors["fat", 0] = 7
        self.assertEqual(self.fat_get(0)[0], 7)

    def test_refresh_reset_picks_up_marker_removal(self):
        self.fat[0] = [fat_entry(), *fat_marker(), END]
        self.assertTrue(self.fat_get(0)[1][11] & 2)
        self.fat[0] = [fat_entry(), END]
        self.lib.music_filter_reset()
        self.assertFalse(self.fat_get(0)[1][11] & 2)

    def test_exfat_child_marker_preserves_unicode_siblings(self):
        self.exfat[2] = [*exfat_entry("Kirjat — 日本語", 30, True),
                         *exfat_entry("Musiikki äö", 40, True), END]
        self.exfat[30] = [*exfat_entry("1.flac"), *exfat_entry(".nomusic", 0, length=0), END]
        before = dict(self.exfat)
        self.assertTrue(self.exfat_get(index=0)[1][4] & 2)
        self.assertFalse(self.exfat_get(index=3)[1][4] & 2)
        self.assertEqual(self.exfat, before)

    def test_exfat_root_marker_and_fragmented_directory(self):
        self.exfat[2] = [*exfat_entry("book", 30, True, flags=1), END]
        self.exfat[30] = [*exfat_entry(".NOMUSIC", 0, length=0), END]
        self.assertTrue(self.exfat_get()[1][4] & 2)
        self.exfat[2] = [*exfat_entry("track.flac"), *exfat_entry(".nomusic", 0, length=0), END]
        self.lib.music_filter_reset()
        self.assertTrue(self.exfat_get(cluster=0)[1][4] & 2)

    def test_exfat_deleted_and_similar_names_do_not_match(self):
        for name in (".nomusicx", "nomusic", ".nomusic"):
            with self.subTest(name=name):
                marker = exfat_entry(name, 0, length=0)
                if name == ".nomusic":
                    e = bytearray(marker[0]); e[0] = 5; marker[0] = bytes(e)
                self.exfat[2] = [*exfat_entry("song.flac"), *marker, END]
                self.lib.music_filter_reset()
                self.assertFalse(self.exfat_get()[1][4] & 2)

    def test_metadata_entries_are_not_modified(self):
        self.fat[0] = [*fat_marker(), END]
        self.assertEqual(self.fat_get(0, 0)[1], self.fat[0][0])
        self.exfat[2] = [*exfat_entry(".nomusic", 0, length=0), END]
        self.assertEqual(self.exfat_get(index=1)[1], self.exfat[2][1])
        self.assertEqual(self.exfat_get(index=2)[1], self.exfat[2][2])


if __name__ == "__main__":
    unittest.main()
