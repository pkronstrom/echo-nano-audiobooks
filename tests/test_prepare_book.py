import importlib.util
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import shutil
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_book',ROOT/'tools/prepare_book.py')
book=importlib.util.module_from_spec(spec);spec.loader.exec_module(book)

class PrepareBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'Book';self.root.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def audio(self,name):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'audio');return p
    def test_numbered_chapters_and_discs_use_natural_order(self):
        for p in ('Disc 10/01.mp3','Disc 2/10.mp3','Disc 2/2.mp3','Disc 1/00 Introduction.mp3','Disc 1/01 Chapter 1.mp3'):
            self.audio(p)
        result=book.prepare(self.root)
        self.assertEqual(result['tracks'],['Disc 1/00 Introduction.mp3','Disc 1/01 Chapter 1.mp3','Disc 2/2.mp3','Disc 2/10.mp3','Disc 10/01.mp3'])
        self.assertFalse((self.root/'BOOK.M3U').exists())
    def test_appledouble_sidecars_are_not_audio_tracks(self):
        self.audio('01.mp3');self.audio('Disc 2/02.mp3')
        self.audio('._01.mp3');self.audio('Disc 2/._02.mp3')
        result=book.prepare(self.root,write=True)
        self.assertEqual(result['tracks'],['01.mp3','Disc 2/02.mp3'])
        self.audio('._Unsupported.m4b')
        self.assertEqual(book.prepare(self.root)['tracks'],result['tracks'])
        with self.assertRaisesRegex(ValueError,'No supported audio'):
            book.prepare(self.root/'._01.mp3')

    def test_write_retry_preserves_progress_and_explicit_order(self):
        self.audio('2 日本語.flac');self.audio('1 ä.flac')
        book.prepare(self.root,write=True)
        self.assertTrue(book.valid_resume((self.root/'BOOK.RSM').read_bytes()))
        custom=b'#EXTM3U\n2 \xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e.flac\n1 \xc3\xa4.flac\n'
        (self.root/'BOOK.M3U').write_bytes(custom)
        before=(self.root/'BOOK.RSM').read_bytes()
        book.prepare(self.root,write=True)
        self.assertEqual((self.root/'BOOK.M3U').read_bytes(),custom)
        self.assertEqual((self.root/'BOOK.RSM').read_bytes(),before)
        self.assertTrue((self.root/'.nomusic').exists())
    def test_bookmark_companion_is_created_and_never_replaced(self):
        self.audio('01.mp3')
        result=book.prepare(self.root,write=True)
        path=self.root/'BOOK.BMK'
        self.assertTrue(path.exists())
        self.assertEqual(result['bookmarks'],str(path.resolve()))
        data=bytearray(path.read_bytes())
        self.assertEqual(len(data),1024)
        # A saved bookmark: generation 1, queue fingerprint 123, chapter 2 at 9s.
        import struct,zlib
        struct.pack_into('<6I',data,512,0x31424e45,1,123,1,2,9000)
        struct.pack_into('<I',data,1020,zlib.crc32(data[512:1020]))
        path.write_bytes(data)
        book.prepare(self.root,write=True)
        self.assertEqual(path.read_bytes(),data)
        path.write_bytes(b'unknown format')
        with self.assertRaisesRegex(ValueError,'preserved'):
            book.prepare(self.root,write=True)
        self.assertEqual(path.read_bytes(),b'unknown format')

    def test_bookmark_symlink_is_rejected_before_metadata_writes(self):
        self.audio('01.mp3')
        target=Path(self.tmp.name)/'target';target.write_bytes(b'untouched')
        (self.root/'BOOK.BMK').symlink_to(target)
        with self.assertRaisesRegex(ValueError,'symlinks'):
            book.prepare(self.root,write=True)
        self.assertFalse((self.root/'BOOK.M3U').exists())
        self.assertEqual(target.read_bytes(),b'untouched')

    def test_hash_prefixed_names_are_not_playlist_comments(self):
        self.audio('#Chapter.mp3');self.audio('#Disc/01.mp3')
        result=book.prepare(self.root,write=True)
        entries=(self.root/'BOOK.M3U').read_text().splitlines()[1:]
        self.assertEqual(entries,['./#Chapter.mp3','./#Disc/01.mp3'])
        self.assertTrue(all(not line.startswith('#') for line in entries))

    def test_single_long_file_and_invalid_input(self):
        source=self.audio('Long book.mp3')
        result=book.prepare(source,write=True)
        self.assertEqual(result['tracks'],['Long book.mp3'])
        self.assertIsNone(result['marker'])
        self.assertFalse((self.root/'.nomusic').exists())
        self.assertTrue((self.root/'Long book.M3U').exists())
        (self.root/'Long book.RSM').write_bytes(bytes(1024))
        with self.assertRaisesRegex(ValueError,'preserved'):book.prepare(source,write=True)
    def test_cli_preview_write_retry_and_error(self):
        self.audio('00 Introduction.mp3')
        command=[sys.executable,str(ROOT/'tools/prepare_book.py'),str(self.root)]
        for options in ([],['--write'],['--write']):
            self.assertEqual(subprocess.run(command+options,capture_output=True).returncode,0)
        self.assertEqual(subprocess.run(command+['--output',str(self.root)],capture_output=True).returncode,2)
    @unittest.skipUnless(shutil.which('ffmpeg'),'optional conversion needs ffmpeg')
    def test_optional_conversion_of_single_m4b_keeps_original(self):
        source=self.root/'Long.m4b'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.1','-c:a','aac',str(source)],check=True)
        original=source.read_bytes();output=Path(self.tmp.name)/'Converted'
        book.prepare(source,write=True,output=output,convert=True)
        self.assertEqual(source.read_bytes(),original)
        self.assertTrue((output/'000 Long.mp3').stat().st_size)
        self.assertTrue(book.valid_resume((output/'Long.RSM').read_bytes()))

if __name__=='__main__':unittest.main()
