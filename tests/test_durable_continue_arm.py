"""Cold Continue selection uses CRC journals, without creating files."""
import struct
import unittest
import zlib
import test_book_resume_arm as resume
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
from test_media_path import lfn

class DurableContinueTests(unittest.TestCase):
    def setUp(self):
        self.r=resume.ResumeTests();self.r.setUp();self.f=self.r.f;self.cpu=self.r.cpu
        self.f.dirs[0][-1:-1]=lfn('.audiobook',b'AUDIOB~1   ',110)
    def launch(self,path):
        self.r.load(path)
        address=self.f.call('playback_book_path')
        self.cpu.mem_write(address,(path+'\0').encode('utf-16le'))
        self.f.call('last_book_remember',0x20001000)
        self.r.select(1)
        self.f.call('book_autosave')
    def cold(self):
        self.f.call('playback_init')
        result=self.f.call('last_book_get',0x20003000)
        path=bytes(self.cpu.mem_read(0x20003000,512)).decode('utf-16le').split('\0')[0]
        return result,path
    def newest(self,cluster):
        sectors=[self.f.files[cluster][i:i+512] for i in (0,512)]
        valid=[s for s in sectors if zlib.crc32(s[:508])==struct.unpack_from('<I',s,508)[0]]
        return max(valid,key=lambda s:struct.unpack_from('<I',s,4)[0])
    def test_first_safe_poll_persists_selection_and_cold_path(self):
        self.launch('/BOOK.M3U')
        self.assertEqual(self.r.writes,[(91,512)])
        self.assertEqual(struct.unpack_from('<II',self.newest(91),36),(0x31424c45,1))
        self.assertEqual(self.cold(),(1,'/BOOK.M3U'))
    def test_two_books_and_launch_before_navigation_seed_sequence(self):
        self.launch('/BOOK.M3U');self.launch('/OTHER.M3U')
        self.assertEqual(self.cold(),(1,'/OTHER.M3U'))
        self.f.call('playback_init')
        self.cpu.mem_write(self.f.syms['playback_active'],struct.pack('<I',1))
        self.launch('/BOOK.M3U')
        self.assertEqual(struct.unpack_from('<I',self.newest(91),40)[0],3)
        self.assertEqual(self.cold(),(1,'/BOOK.M3U'))
    def test_torn_write_preserves_previous_available_selection(self):
        self.launch('/BOOK.M3U')
        self.r.short_write=True;self.launch('/OTHER.M3U')
        self.assertEqual(self.cold(),(1,'/BOOK.M3U'))
    def test_legacy_records_offer_no_guessed_last_book(self):
        self.assertEqual(self.cold(),(0,''))
    def test_removed_or_replaced_playlist_is_not_restored(self):
        self.launch('/BOOK.M3U')
        entry=bytearray(self.f.dirs[0][0]);struct.pack_into('<H',entry,26,111);self.f.dirs[0][0]=bytes(entry)
        self.assertEqual(self.cold(),(0,''))
    def test_newest_generation_without_extension_does_not_resurrect_old_sector(self):
        self.launch('/BOOK.M3U')
        old=bytearray(self.newest(91));struct.pack_into('<I',old,4,2)
        old[36:64]=bytes(28);struct.pack_into('<I',old,508,zlib.crc32(old[:508]))
        self.f.files[91]=bytes(old)+self.f.files[91][512:]
        self.assertEqual(self.cold(),(0,''))
    def test_checkpoint_saves_preserve_selection_order(self):
        self.launch('/BOOK.M3U');seq=struct.unpack_from('<I',self.newest(91),40)[0]
        self.r.tick(30000);self.f.call('book_autosave')
        self.assertEqual(struct.unpack_from('<I',self.newest(91),40)[0],seq)
        self.assertEqual(self.cold(),(1,'/BOOK.M3U'))

    def test_lookup_io_failure_discards_partial_winner(self):
        self.launch('/BOOK.M3U');self.launch('/OTHER.M3U')
        def fault(cpu,address,size,user):
            if address!=self.f.syms['playback_lookup']:return
            p=cpu.reg_read(UC_ARM_REG_R0)
            if bytes(cpu.mem_read(p,22))!='/OTHER.M3U\0'.encode('utf-16le'):return
            cpu.reg_write(UC_ARM_REG_R0,0xfffffffe);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,fault)
        self.assertEqual(self.cold(),(0,''))
    def test_failed_scan_after_storage_change_does_not_reuse_old_sequence(self):
        self.launch('/BOOK.M3U');self.cpu.mem_write(0x0300d173,b'\x03')
        def fault(cpu,address,size,user):
            if address!=self.f.syms['content_scan']:return
            cpu.reg_write(UC_ARM_REG_R0,0xfffffffe);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        self.cpu.hook_add(UC_HOOK_CODE,fault)
        self.cpu.mem_write(0x20001000,'/OTHER.M3U\0'.encode('utf-16le'))
        self.f.call('last_book_remember',0x20001000)
        self.assertEqual(struct.unpack('<I',self.cpu.mem_read(self.f.syms['book_selection'],4))[0],0)

    def test_nested_unicode_exfat_book_restores(self):
        from test_music_filter import exfat_entry,END
        from test_content_roots import checksum
        def e(name,cluster,length=0,directory=False):
            return checksum(exfat_entry(name,cluster,directory,length=length))
        self.cpu.mem_write(0x03076b24,b'\x03')
        self.f.dirs={2:[*e('Books',20,4096,True),END],
                     20:[*e('.audiobook',110),*e('雪の本',30,4096,True),END],
                     30:[*e('BOOK.M3U',90,16),*e('BOOK.RSM',91,1024),*e('one.mp3',100),*e('two.mp3',101),END]}
        self.launch('/Books/雪の本/BOOK.M3U')
        self.assertEqual(self.cold(),(1,'/Books/雪の本/BOOK.M3U'))
