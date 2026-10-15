"""Execute the native audio-selection route with sorted/physical order differing."""
import struct
import unittest
from unicorn.arm_const import *
import test_playback_runtime_arm as fixture
from test_music_filter import fat_entry, exfat_entry, END


class BrowserSortSelectionTests(unittest.TestCase):
    def check_ordinal(self, exfat=False):
        f = fixture.PlaybackRuntimeTests()
        f.setUp()
        cpu = f.cpu
        image = fixture.Image((fixture.ROOT / 'out/audiobook/NANOV170.IMG').read_bytes())
        m = image.modules[31]
        for kind in ('code', 'data'):
            off = image.l2f(m[kind + '_load'])
            cpu.mem_write(m[kind + '_exec'], bytes(image.d[off:off + m[kind + '_len']]))
        # CD1 sorts first but is the second playable file on disk. A directory
        # and unrelated text file must not contribute to the audio ordinal.
        selected = fat_entry(b'CD1     MP3', 101)
        f.dirs = {0: [fat_entry(b'SUBDIR     ', 90, True),
                      fat_entry(b'CD2     MP3', 100),
                      fat_entry(b'README  TXT', 102), selected, END]}
        node = 0x0300e73c
        cpu.mem_write(node + 8, struct.pack('<II', 0, 3))
        if exfat:
            f.dirs = {2: [*exfat_entry('subdir', 90, True),
                          *exfat_entry('CD2.mp3', 100),
                          *exfat_entry('readme.txt', 102),
                          *exfat_entry('CD1.mp3', 101), END]}
            cpu.mem_write(0x03076b24, b'\x03')
            cpu.mem_write(node + 8, struct.pack('<II', 2, 9))
            cpu.mem_write(node + 0x24, struct.pack('<I', 2))
            cpu.mem_write(node + 0x70, 'CD1.mp3'.encode('utf-16le') + b'\0\0')
        cpu.mem_write(node + 0x4e, b'\x01')
        cpu.mem_write(node + 0x4f, selected)
        cpu.mem_write(0x0300ec1c + 8, struct.pack('<H', 3 if exfat else 2))
        for reg, value in ((UC_ARM_REG_R4, node), (UC_ARM_REG_R5, 1),
                           (UC_ARM_REG_R7, 0x03005f6c),
                           (UC_ARM_REG_R10, 0x0300ec1c),
                           (UC_ARM_REG_SP, 0x2000f000)):
            cpu.reg_write(reg, value)
        cpu.emu_start(0x0307ad13, 0x0307af26, count=200000)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x0307af26)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_R0), 2)

    def test_fat_sorted_first_row_uses_second_physical_audio_ordinal(self):
        self.check_ordinal()

    def test_exfat_keeps_native_physical_audio_ordinal(self):
        self.check_ordinal(exfat=True)
