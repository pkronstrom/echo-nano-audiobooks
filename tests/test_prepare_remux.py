"""Real packet-preserving remux and safe host preparation failures."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_prepare_book as base
book=base.book

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'needs ffmpeg and ffprobe')
class RemuxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'Original';self.source.mkdir();self.output=self.root/'Prepared'
    def tearDown(self):self.tmp.cleanup()
    def audio(self,name,codec):
        path=self.source/name
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.15','-c:a',codec,str(path)],check=True)
        return path
    def packets(self,path):
        value=subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_data_hash','sha256','-show_entries','packet=data_hash','-of','json',str(path)])
        return [p['data_hash'] for p in json.loads(value)['packets']]
    def test_aac_remux_preserves_packets_original_and_prepares_sidecars(self):
        source=self.audio('Book.m4b','aac');before=source.read_bytes()
        preview=book.prepare(source,output=self.output,remux=True)
        self.assertEqual(preview['remux'],'m4a');self.assertFalse(self.output.exists())
        result=book.prepare(source,write=True,output=self.output,remux=True)
        target=self.output/'000 Book.m4a'
        self.assertEqual(self.packets(source),self.packets(target))
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(result['tracks'],['000 Book.m4a'])
        self.assertTrue(book.valid_resume((self.output/'Book.RSM').read_bytes()))
        self.assertTrue((self.output/'.nomusic').exists())
    def test_alac_is_copied_without_transcoding(self):
        source=self.audio('Book.m4a','alac')
        self.output.mkdir() # Also supported on Windows, which cannot replace dirs.
        book.prepare(source,write=True,output=self.output,remux=True)
        self.assertEqual(self.packets(source),self.packets(self.output/'000 Book.m4a'))
    def test_incompatible_codec_fails_before_output(self):
        source=self.audio('Book.wav','pcm_s16le')
        with self.assertRaisesRegex(ValueError,'AAC or ALAC'):
            book.prepare(source,write=True,output=self.output,remux=True)
        self.assertFalse(self.output.exists())
    def test_failed_second_conversion_leaves_empty_destination_unchanged(self):
        self.audio('1.m4b','aac');(self.source/'2.m4b').write_bytes(b'broken')
        self.output.mkdir()
        with self.assertRaises(subprocess.CalledProcessError):
            book.prepare(self.source,write=True,output=self.output,convert=True)
        self.assertEqual(list(self.output.iterdir()),[])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),['Original','Prepared'])
    def test_transform_rejects_source_alias_and_conflicting_modes(self):
        source=self.audio('Book.m4b','aac')
        with self.assertRaises(ValueError):book.prepare(source,write=True,output=self.source,remux=True)
        with self.assertRaises(ValueError):book.prepare(source,output=self.output,convert=True,remux=True)
        command=[sys.executable,str(base.ROOT/'tools/prepare_book.py'),str(source),'--convert-to','mp3','--remux-to','m4a','--output',str(self.output)]
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,2)
        self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
