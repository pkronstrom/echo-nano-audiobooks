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

class EmbeddedChapterExportTests(unittest.TestCase):
    def test_chapter_boundaries_cover_entire_source_and_reject_bad_starts(self):
        import json
        from unittest.mock import patch
        data={'format':{'duration':'12'},'chapters':[
            {'start_time':'0.2','end_time':'5','tags':{'title':'Intro'}},
            {'start_time':'5','end_time':'11','tags':{'title':'Two'}}]}
        with patch.object(book.shutil,'which',return_value='/ffprobe'),patch.object(book.subprocess,'check_output',return_value=json.dumps(data).encode()):
            self.assertEqual(book.chapter_segments(Path('book.m4b')),[('0','5','Intro'),('5','7','Two')])
        data['chapters'][1]['start_time']='0.1'
        with patch.object(book.shutil,'which',return_value='/ffprobe'),patch.object(book.subprocess,'check_output',return_value=json.dumps(data).encode()):
            with self.assertRaises(ValueError):book.chapter_segments(Path('book.m4b'))
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'ffmpeg/ffprobe required')
    def test_real_m4b_exports_ordered_chapter_audio_and_valid_companions(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'source').mkdir();source=root/'source/original.m4b';meta=root/'chapters.txt'
            meta.write_text(';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1000\ntitle=One\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=1000\nEND=2000\ntitle=Two\n')
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=2','-i',str(meta),'-map_metadata','1','-c:a','aac',str(source)],check=True)
            original=source.read_bytes();output=root/'export'
            from unittest.mock import patch
            with patch.object(book.subprocess, 'run', wraps=book.subprocess.run) as run:
                result=book.prepare(source,write=True,output=output,convert=True,split_chapters=True)
            commands=[call.args[0] for call in run.call_args_list if '-ss' in call.args[0]]
            self.assertEqual(len(commands),2)
            for command in commands:
                self.assertGreater(command.index('-ss'), command.index('-i'))
            self.assertEqual(result['tracks'],['001 One.mp3','002 Two.mp3'])
            self.assertEqual((output/'BOOK.M3U').read_text(),'#EXTM3U\n001 One.mp3\n002 Two.mp3\n')
            self.assertTrue(book.valid_resume((output/'BOOK.RSM').read_bytes()))
            self.assertTrue(book.valid_bookmarks((output/'BOOK.BMK').read_bytes()))
            for name in result['tracks']:
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(output/name)]))
                self.assertAlmostEqual(float(probe['format']['duration']),1,delta=.15)
            self.assertEqual(source.read_bytes(),original)
            with self.assertRaisesRegex(ValueError,'empty directory'):
                book.prepare(source,write=True,output=output,convert=True,split_chapters=True)

    def test_probe_timeout_is_a_clear_preparation_error(self):
        from unittest.mock import patch
        with patch.object(book.shutil, 'which', return_value='/ffprobe'), patch.object(
                book.subprocess, 'check_output', side_effect=subprocess.TimeoutExpired('ffprobe', 30)):
            with self.assertRaisesRegex(ValueError, 'Could not inspect chapters'):
                book.chapter_segments(Path('book.m4b'))

if __name__=='__main__':unittest.main()
