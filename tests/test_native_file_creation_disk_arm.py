"""Native allocation and persistence with synthetic sectors, not host FS mocks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.native_file_creation.disk_harness import NativeDisk, PowerCut


class NativeCreationDiskTests(unittest.TestCase):
    def test_exfat_full_directory_growth_reaches_invalid_sector(self):
        disk = NativeDisk('exfat')
        disk.fill_root()
        # Characterizes a stock hazard in this bounded mounted-root fixture.
        # It is not evidence that exFAT directory expansion is safe.
        with self.assertRaisesRegex(AssertionError, 'invalid sector request'):
            disk.create('BOOK.BMK')

    def test_full_exfat_card_allocator_reaches_invalid_bitmap_sector(self):
        disk = NativeDisk('exfat')
        disk.sectors[disk.DATA_LBA * 512:disk.DATA_LBA * 512 + 8] = b'\xff' * 8
        handle = disk.create('BOOK.BMK')
        self.assertGreaterEqual(handle, 0)
        with self.assertRaisesRegex(AssertionError, 'invalid sector request'):
            disk.write(handle, b'X' * 1024)

    def test_power_cut_before_each_native_write_does_not_publish_complete_file(self):
        payload = b'X' * 1024
        for filesystem in ('fat', 'exfat'):
            complete = NativeDisk(filesystem)
            complete.create_roundtrip('BOOK.BMK', payload)
            for cutoff in range(1, len(complete.sector_writes) + 1):
                with self.subTest(filesystem=filesystem, cutoff=cutoff):
                    disk = NativeDisk(filesystem)
                    disk.cut_before_write = cutoff
                    with self.assertRaises(PowerCut):
                        disk.create_roundtrip('BOOK.BMK', payload)
                    entry = disk.entry(1 if filesystem == 'exfat' else 0)
                    length = int.from_bytes(entry[24:28] if filesystem == 'exfat' else entry[28:32], 'little')
                    self.assertNotEqual(length, 1024)

    def test_failed_directory_cache_read_can_corrupt_neighbors_on_native_write(self):
        for filesystem in ('fat', 'exfat'):
            with self.subTest(filesystem=filesystem):
                disk = NativeDisk(filesystem)
                root_lba = disk.DATA_LBA + disk.ROOT_CLUSTER - 2
                sentinel = b'\x83' + b'PRESERVE'.ljust(31, b'!') if filesystem == 'exfat' else b'PRESERVETXT' + b'\x20' + bytes(20)
                disk.set_entry(8, sentinel)
                disk.failed_read_lbas.add(root_lba)
                disk.cpu.mem_write(0x03076b68, b'Z' * 512)
                disk._word(0x03076b64, root_lba + 1)
                disk.cpu.mem_write(0x20005000, disk.entry(0) + disk.entry(1) + disk.entry(2))
                if filesystem == 'exfat':
                    disk.cpu.mem_write(0x20005000, b'\x85\x02' + bytes(94))
                    disk.cpu.mem_write(0x20006000, disk.ROOT_CLUSTER.to_bytes(4, 'little') + bytes(8) + b'\x01' + bytes(29))
                    result = disk.call(0x0305ec52, 0x20006000, 0, 0x20005000)
                else:
                    disk.cpu.mem_write(0x20005000, b'BOOK    BMK\x20' + bytes(20))
                    result = disk.call(0x0305eba0, disk.ROOT_CLUSTER, 0, 0x20005000)
                self.assertEqual(result, 0)
                self.assertNotEqual(disk.entry(8), sentinel)

    def test_exhausted_native_handles_preserve_all_sectors(self):
        for filesystem in ('fat', 'exfat'):
            with self.subTest(filesystem=filesystem):
                disk = NativeDisk(filesystem)
                before = bytes(disk.sectors)
                for handle in range(8):
                    disk.cpu.mem_write(0x03077668 + handle * 0x27e, b'\x01')
                self.assertEqual(disk.create('BOOK.BMK'), -1)
                self.assertEqual(bytes(disk.sectors), before)

    def test_fat_duplicate_refuses_without_sector_changes(self):
        disk = NativeDisk()
        disk.create_roundtrip('BOOK.BMK', b'X' * 1024)
        before = bytes(disk.sectors)
        self.assertEqual(disk.create('BOOK.BMK'), -1)
        self.assertEqual(bytes(disk.sectors), before)

    def test_full_fat_card_cannot_write_data(self):
        disk = NativeDisk()
        for cluster in range(3, disk.CLUSTERS + 2):
            disk.set_fat(cluster, 0x0fffffff)
        handle = disk.create('BOOK.BMK')
        self.assertGreaterEqual(handle, 0)
        self.assertEqual(disk.write(handle, b'X' * 1024), 0)
        disk.close(handle)
        self.assertEqual(disk.entry()[28:32], bytes(4))

    def test_fat_directory_grows_through_real_allocator(self):
        disk = NativeDisk()
        disk.fill_root()
        result = disk.create_roundtrip('BOOK.BMK', b'X' * 1024)
        self.assertEqual(result['readback'], b'X' * 1024)
        self.assertEqual(len(disk.chain(disk.ROOT_CLUSTER)), 2)

    def test_exfat_two_free_slots_overwrite_active_third_slot(self):
        disk = NativeDisk('exfat')
        disk.set_entry(0, b'\x05' + bytes(31))
        disk.set_entry(1, b'\x40' + bytes(31))
        sentinel = b'\x83' + b'PRESERVE'.ljust(31, b'!')
        disk.set_entry(2, sentinel)
        self.assertEqual(disk.create('BOOK.BMK'), 0)
        # Characterization of unsafe stock behavior, not an accepted adapter.
        self.assertNotEqual(disk.entry(2), sentinel)
        self.assertEqual(disk.entry(2)[0], 0xc1)

    def test_failed_data_write_can_report_success_but_cold_readback_detects_it(self):
        disk = NativeDisk()
        disk.failed_write_lbas.add(disk.DATA_LBA + 1)
        with self.assertRaisesRegex(AssertionError, 'readback'):
            disk.create_roundtrip('BOOK.BMK', b'X' * 1024)

    def test_exfat_create_allocate_close_and_cold_reopen(self):
        disk = NativeDisk('exfat')
        payload = bytes(range(256)) * 4
        result = disk.create_roundtrip('BOOK.BMK', payload)
        self.assertEqual(result['readback'], payload)
        self.assertEqual(result['size'], 1024)
        self.assertEqual(len(result['chain']), 2)
        self.assertTrue(result['sector_writes'])
        for cluster in result['chain']:
            byte = disk.sectors[disk.DATA_LBA * 512 + (cluster - 2) // 8]
            self.assertTrue(byte & (1 << ((cluster - 2) % 8)))

    def test_fat_create_allocate_close_and_cold_reopen(self):
        disk = NativeDisk()
        payload = bytes(range(256)) * 4
        result = disk.create_roundtrip('BOOK.BMK', payload)
        self.assertEqual(result['readback'], payload)
        self.assertEqual(result['size'], 1024)
        self.assertEqual(len(result['chain']), 2)
        self.assertTrue(result['sector_writes'])


if __name__ == '__main__':
    unittest.main()
