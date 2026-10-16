"""Book switching and two-sector resume journal through compiled ARM code.
Native indexed opens execute; sector writes and codec timing are substituted.
"""
import struct
import unittest
import zlib
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR
import test_playback_runtime_arm as fixture
from test_music_filter import fat_entry,exfat_entry,END

def blank():
    b=bytearray(512);struct.pack_into('<I',b,0,0x31524e45)
    struct.pack_into('<I',b,508,zlib.crc32(b[:508]));return bytes(b)*2

def sized(name,cluster,length):
    b=bytearray(fat_entry(name,cluster));struct.pack_into('<I',b,28,length);return bytes(b)

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PlaybackRuntimeTests();self.f.setUp();self.cpu=self.f.cpu
        self.writes=[];self.short_write=False
        self.cpu.hook_add(UC_HOOK_CODE,self.write)
        self.f.files={90:b'one.mp3\ntwo.mp3\n',91:blank(),92:b'two.mp3\n',93:blank()}
        self.f.dirs={0:[sized(b'BOOK    M3U',90,16),sized(b'BOOK    RSM',91,1024),
                        sized(b'OTHER   M3U',92,8),sized(b'OTHER   RSM',93,1024),
                        fat_entry(b'ONE     MP3',100),fat_entry(b'TWO     MP3',101),END]}
        self.cpu.mem_write(0x03039714,struct.pack('<I',0x03023090))
        self.cpu.mem_write(0x03023090,struct.pack('<II',7200000,1234567))
        self.cpu.mem_write(self.f.syms['playback_active'],struct.pack('<I',1))
    def write(self,cpu,address,size,user):
        if address!=0x0305fda4:return
        data,offset,length,h=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        self.assertEqual((offset%512,length),(0,512));self.assertLess(offset,1024)
        fcb=0x03077668+h*0x27e
        self.assertTrue(cpu.mem_read(fcb,1)[0]&2,'native indexed open must enable write')
        cluster=struct.unpack('<I',cpu.mem_read(fcb+20,4))[0]
        count=128 if self.short_write else length
        b=bytearray(self.f.files[cluster]);b[offset:offset+count]=cpu.mem_read(data,count)
        self.f.files[cluster]=bytes(b);self.writes.append((cluster,offset))
        cpu.reg_write(UC_ARM_REG_R0,count);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def load(self,name):
        self.cpu.mem_write(0x20001000,name.encode('utf-16le')+b'\0\0')
        self.assertGreater(self.f.call('playback_load_playlist',0x20001000,0x20002000),0)
        pos=self.f.call('book_load',0x20001000,0x20002400)
        ms=struct.unpack('<I',self.cpu.mem_read(0x20002400,4))[0]
        return pos,ms
    def select(self,position):
        self.f.call('playback_playlist_step',0x0300d85c,0)
        for _ in range(position-1):self.f.call('playback_playlist_step',0x0300d85c,1)
    def test_book_a_music_book_b_and_restart_keep_independent_progress(self):
        self.assertEqual(self.load('/BOOK.M3U'),(0,0));self.select(2)
        self.f.call('book_save')
        self.assertEqual(self.writes,[(91,512)])
        self.f.call('book_clear');self.f.call('book_save')
        self.assertEqual(len(self.writes),1)
        self.assertEqual(self.load('/OTHER.M3U'),(0,0));self.select(1)
        self.cpu.mem_write(0x03023090+4,struct.pack('<I',765432))
        self.f.call('book_save')
        self.f.call('playback_init') # simulated restart: all payload RAM forgotten
        self.assertEqual(self.load('/BOOK.M3U'),(2,1234567))
        self.assertEqual(self.load('/OTHER.M3U'),(1,765432))
    def test_speed_is_per_book_and_survives_payload_restart(self):
        self.f.call('playback_speed_set',8)
        self.load('/BOOK.M3U');self.select(1)
        self.assertEqual(self.f.call('playback_speed_get'),4)
        self.cpu.mem_write(0x03023098,struct.pack('<I',48000))
        self.cpu.mem_write(0x0302312c,struct.pack('<I',16))
        self.f.call('playback_speed_set',6);self.f.call('playback_speed_launch')
        self.f.call('playback_speed_set',8) # Pending preference is not this book's launched setting.
        self.cpu.mem_write(0x03039e94,struct.pack('<I',1)) # Unsupported chapter plays at 1x.
        self.assertEqual(self.f.call('playback_speed_actual'),4)
        self.f.call('book_save')
        self.f.call('playback_init');self.load('/BOOK.M3U')
        self.assertEqual(self.f.call('playback_speed_get'),6)
        self.f.call('playback_launch_rate',8);self.f.call('playback_launch_cancel')
        self.cpu.mem_write(0x03039e94,struct.pack('<I',0))
        # Reopen through the real pending-path session, not just the journal API.
        self.cpu.mem_write(0x20001000,'/BOOK.M3U\0'.encode('utf-16le'))
        self.assertEqual(self.f.call('playback_launch_path',0x20001000,0,0,self.f.call('playlist_signature')),1)
        self.f.call('playback_browser_select',0x20004000)
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.f.call('playback_prepare',3),0)
        self.assertEqual(self.f.call('playback_speed_get'),6)
        self.assertEqual(self.f.call('playback_speed_actual'),6)
        self.load('/OTHER.M3U');self.assertEqual(self.f.call('playback_speed_get'),4)

    def test_missing_companion_resets_previous_books_speed(self):
        self.f.dirs[0].pop(1);self.f.call('playback_speed_set',8)
        self.assertEqual(self.load('/BOOK.M3U'),(0,0))
        self.assertEqual(self.f.call('playback_speed_get'),4)

    def test_invalid_rate_tag_keeps_resume_but_defaults_to_one(self):
        self.load('/BOOK.M3U');self.select(1);self.f.call('book_save')
        for tag in (0,0x53504403,0x53504409,0x12345678):
            data=bytearray(self.f.files[91]);struct.pack_into('<I',data,512+32,tag)
            struct.pack_into('<I',data,1020,zlib.crc32(data[512:1020]));self.f.files[91]=bytes(data)
            self.f.call('playback_speed_set',8)
            self.assertEqual(self.load('/BOOK.M3U'),(1,1234567))
            self.assertEqual(self.f.call('playback_speed_get'),4)
    def test_preview_speed_does_not_change_playing_books_rate(self):
        self.load('/BOOK.M3U');self.f.call('playback_speed_set',6)
        self.cpu.mem_write(0x20001000,'/OTHER.M3U\0'.encode('utf-16le'))
        self.assertEqual(self.f.call('book_preview_open',0x20001000),1)
        self.assertEqual(self.f.call('book_preview_rate'),4)
        self.f.call('book_preview_set_rate',8)
        self.assertEqual(self.f.call('book_preview_rate'),8)
        self.assertEqual(self.f.call('playback_speed_get'),6)

    def test_failed_preview_scan_clears_overlaid_metadata_and_can_reopen(self):
        self.cpu.mem_write(0x20001000,'/BOOK.M3U\0'.encode('utf-16le'))
        self.assertEqual(self.f.call('book_preview_open',0x20001000),2)
        self.f.call('book_preview_set_rate',8)
        self.f.files[90]=b'xxxxxxx\nxxxxxxx\n' # Neither line resolves.
        self.assertEqual(self.f.call('book_preview_open',0x20001000),0)
        self.assertEqual(self.f.call('book_preview_count'),0)
        self.assertEqual(self.f.call('book_preview_marks'),0)
        self.assertEqual(self.f.call('book_preview_rate'),4)
        self.assertEqual(self.f.call('book_preview_resume',0x20002000),0)
        self.assertEqual(bytes(self.cpu.mem_read(0x20002000,4)),bytes(4))
        self.f.files[90]=b'one.mp3\ntwo.mp3\n'
        self.assertEqual(self.f.call('book_preview_open',0x20001000),2)

    def test_resume_does_not_touch_parser_scratch_while_busy(self):
        self.load('/BOOK.M3U');self.select(1)
        scratch=self.f.syms['playback_scratch']
        before=bytes(range(256))*4
        self.cpu.mem_write(scratch,before)
        self.cpu.mem_write(self.f.syms['playback_scratch_busy'],struct.pack('<I',1))
        self.f.call('book_save')
        self.assertEqual(self.writes,[])
        self.assertEqual(bytes(self.cpu.mem_read(scratch,1024)),before)
        self.cpu.mem_write(self.f.syms['playback_scratch_busy'],bytes(4))
        self.f.call('book_save')
        self.assertEqual(self.load('/BOOK.M3U'),(1,1234567))

    def test_torn_save_uses_last_valid_sector(self):
        self.load('/BOOK.M3U');self.select(1);self.f.call('book_save')
        self.short_write=True;self.cpu.mem_write(0x03023090+4,struct.pack('<I',999999))
        self.f.call('book_save');self.f.call('playback_init')
        self.assertEqual(self.load('/BOOK.M3U'),(1,1234567))
    def test_changed_queue_and_corrupt_journal_do_not_restore_wrong_chapter(self):
        self.load('/BOOK.M3U');self.select(2);self.f.call('book_save')
        self.f.files[90]=b'two.mp3\none.mp3\n'
        self.assertEqual(self.load('/BOOK.M3U'),(0,0))
        self.f.files[91]=bytes(1024)
        self.assertEqual(self.load('/BOOK.M3U'),(0,0))
        self.f.call('book_save');self.assertEqual(len(self.writes),1)
    def test_exfat_native_update_mode_and_restore(self):
        self.cpu.mem_write(0x03076b24,b'\x03')
        self.f.dirs={2:[*exfat_entry('BOOK.M3U',90,length=16),*exfat_entry('BOOK.RSM',91,length=1024),
                        *exfat_entry('one.mp3',100),*exfat_entry('two.mp3',101),END]}
        self.assertEqual(self.load('/BOOK.M3U'),(0,0));self.select(2);self.f.call('book_save')
        self.assertEqual(self.load('/BOOK.M3U'),(2,1234567))

if __name__=='__main__':unittest.main()
