"""Preparation bypasses must still permit the subsequent native folder Enter."""
import struct
import unittest

import test_auto_book_gate_arm as gate_tests
from test_content_roots import checksum
from test_media_path import lfn
from test_music_filter import exfat_entry

B, NODE0 = gate_tests.B, gate_tests.NODE0


class AutomaticBookNativeEntryTests(unittest.TestCase):
    def test_bypassed_preparation_preserves_real_parent_selection(self):
        for fs in ('fat', 'exfat'):
            for shape in ('custom_playlist', 'no_audio', 'nested', 'multicluster'):
                with self.subTest(fs=fs, shape=shape):
                    gate = gate_tests.AutomaticBookGateTests()
                    gate.setUp()
                    names = ('Custom.m3u', 'One.mp3') if shape == 'custom_playlist' else () if shape == 'no_audio' else ('One.mp3',)
                    disk, child = gate.fixture(fs, names=names, resident=True)
                    if shape == 'nested':
                        rows = checksum(exfat_entry('Disc', 20, True, length=disk.SPC * 512)) if fs == 'exfat' else lfn('Disc', b'DISC       ', 20, True)
                        disk.sectors[child:child + disk.SPC * 512] = bytes(disk.SPC * 512)
                        disk.sectors[child:child + len(rows) * 32] = b''.join(rows)
                    if shape == 'multicluster':
                        disk.set_fat(10, 11)
                        disk.set_fat(11, 0x0fffffff)
                        if fs == 'exfat':
                            disk.sectors[disk.DATA_LBA * 512 + 1] |= 2
                            rows = [bytearray(disk.entry(i)) for i in (1, 2, 3)]
                            struct.pack_into('<Q', rows[1], 8, disk.SPC * 1024)
                            struct.pack_into('<Q', rows[1], 24, disk.SPC * 1024)
                            for i, row in enumerate(checksum(rows), 1):
                                disk.set_entry(i, row)

                    # Populate the displayed parent through the real native
                    # iterator and production sort adapter, not fixture nodes.
                    self.assertEqual(disk.call(gate.symbols['browser_sort_count'], 0x03005a5e, B + 12, 3), 0)
                    disk.call(gate.symbols['browser_sort_enumerate'], 0x03005a5e, NODE0, B + 12, 0, 3)
                    self.assertEqual(disk.call(gate.symbols['browser_sort_select'], NODE0), 1)
                    before = bytes(disk.sectors)
                    self.assertEqual(gate.event(disk), 0)
                    self.assertEqual(bytes(disk.sectors), before)
                    self.assertFalse(disk.sector_writes)
                    # Return zero delegates the Enter event to native code;
                    # its mandatory selection guard must still accept Book.
                    self.assertEqual(disk.call(gate.symbols['browser_sort_select'], NODE0), 1)
                    label = bytes(disk.cpu.mem_read(NODE0 + 0x70, 512)).decode('utf-16le').split('\0')[0]
                    self.assertEqual(label, 'Book')


if __name__ == '__main__':
    unittest.main()
