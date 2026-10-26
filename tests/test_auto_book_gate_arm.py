"""Browser event gate exercises against real resident/path/native disk code.

Only event posting and, for negative gates, the final resident dispatcher are
intercepted. Path resolution, marker reads and preparation still execute ARM.
"""
from pathlib import Path
import re
import struct
import subprocess
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_LR, UC_ARM_REG_PC
import test_auto_book_preparation_arm as preparation
from test_media_path import lfn
from test_music_filter import exfat_entry
from test_content_roots import checksum

ROOT = Path(__file__).resolve().parents[1]
B, C, NODE0, NODE1 = 0x03005f6c, 0x0300ec1c, 0x0300e73c, 0x0300e9ac
ENTER, BACK, HOME = 0x40000040, 0x20000040, 0x40001000


class AutomaticBookGateTests(unittest.TestCase):
    def setUp(self):
        self.base = preparation.AutomaticBookPreparationTests()
        self.base.setUp()
        self.symbols = self.base.symbols
        self.bound = {name: int(value, 16) for name, value in re.findall(
            r'#define (\w+) (0x[0-9a-f]+)',
            (ROOT / 'out/browser_sort/browser_playback.h').read_text())}

    def directory_index(self, entries, cluster, exfat):
        for index, entry in enumerate(entries):
            if exfat:
                if entry[0] == 0x85 and entry[4] & 16 and struct.unpack_from('<I', entries[index + 1], 20)[0] == cluster:
                    return index
            elif entry[0] not in (0, 0xe5) and entry[11] != 15 and entry[11] & 16:
                value = struct.unpack_from('<H', entry, 20)[0] << 16 | struct.unpack_from('<H', entry, 26)[0]
                if value == cluster:
                    return index
        self.fail('fixture directory not present in live sectors')

    def fixture(self, fs='fat', marker=True, cached_kind=1, resident=False,
                names=('CD2.mp3', 'CD1.mp3'), sectors_per_cluster=4):
        disk, child = self.base.fixture(fs, names, sectors_per_cluster=sectors_per_cluster)
        disk.cpu.mem_write(B, bytes(0x210))
        disk.cpu.mem_write(C, bytes(0x100))
        disk.cpu.mem_write(0x0300d173, b'\0')
        for name in ('BOOK_CHOOSER_ADDR', 'BOOK_MENU_ACTIVE_ADDR', 'BOOK_MENU_RETURNING_ADDR'):
            disk.cpu.mem_write(self.bound[name], b'\0')
        disk.cpu.mem_write(self.bound['BOOK_ROOTS_ADDR'], bytes(44 * 8))
        disk.cpu.mem_write(self.bound['BOOK_ROOT_COUNT_ADDR'], b'\x01')
        disk.cpu.mem_write(self.bound['BOOK_ROOTS_ADDR'] + 43, bytes([cached_kind]))
        disk.cpu.mem_write(C + 8, struct.pack('<H', 3))
        disk.cpu.mem_write(B, struct.pack('<I', NODE0))
        disk.cpu.mem_write(B + 12, struct.pack('<HHHHI', 1, 0, 1, 0, disk.ROOT_CLUSTER))
        disk.cpu.mem_write(B + 24, struct.pack('<III', disk.ROOT_CLUSTER, disk.SPC * 512, 0) + b'\x01' + bytes(29))
        node = bytearray(624)
        struct.pack_into('<I', node, 4, NODE1)
        selected_index = self.directory_index([disk.entry(i) for i in range(disk.SPC * 16)], 10, fs == 'exfat')
        struct.pack_into('<II', node, 8, disk.ROOT_CLUSTER, selected_index)
        node[0x5a] = 16
        node[0x5c] = 1
        struct.pack_into('<H', node, 0x69, 10)
        struct.pack_into('<I', node, 0x6b, 2048 if fs == 'exfat' else 0)
        node[0x70:0x7a] = 'Book\0'.encode('utf-16le')
        disk.cpu.mem_write(NODE0, bytes(node))
        second = bytearray(624)
        struct.pack_into('<I', second, 4, NODE0)
        second[0x4e] = 0xff
        disk.cpu.mem_write(NODE1, bytes(second))
        if marker:
            entries = checksum(exfat_entry('.audiobook', 0)) if fs == 'exfat' else lfn('.audiobook', b'AUDIOB~1   ', 0)
            first = next(index for index in range(disk.SPC * 16) if disk.entry(index)[0] == 0)
            for index, entry in enumerate(entries, first):
                disk.set_entry(index, entry)
        self.posts, self.dispatches = [], []
        def event_hook(cpu, address, size, unused):
            if address == 0x0306b040:
                self.posts.append(cpu.reg_read(UC_ARM_REG_R0))
            elif address == self.bound['BOOK_NAV_EVENT_ADDR']:
                self.dispatches.append(cpu.reg_read(UC_ARM_REG_R0))
                if resident:
                    return
            else:
                return
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        disk.cpu.hook_add(UC_HOOK_CODE, event_hook)
        return disk, child

    def event(self, disk, message=ENTER):
        return disk.call(self.symbols['browser_book_event'], message)

    def test_large_exfat_cluster_keeps_existing_book_entry_without_failure_screen(self):
        disk, _ = self.fixture('exfat', names=('BOOK.M3U', 'BOOK.RSM', 'BOOK.BMK', 'One.mp3'), sectors_per_cluster=512)
        before = bytes(disk.sectors)
        self.assertEqual(self.event(disk), 0)
        self.assertEqual(self.dispatches, [ENTER])
        self.assertFalse(self.posts)
        self.assertFalse(disk.sector_writes)
        self.assertEqual(bytes(disk.sectors), before)

    def test_negative_collection_and_ui_gates_do_not_write(self):
        for fs in ('fat', 'exfat'):
            for gate in ('missing_marker', 'music', 'meditation', 'both_markers',
                         'chooser', 'book_menu', 'returning', 'wrong_category',
                         'not_directory', 'invalid_root_count'):
                with self.subTest(fs=fs, gate=gate):
                    disk, _ = self.fixture(fs, marker=gate != 'missing_marker',
                        cached_kind={'music': 0, 'meditation': 2, 'both_markers': 3}.get(gate, 1))
                    if gate in ('chooser', 'book_menu', 'returning'):
                        address = {'chooser': 'BOOK_CHOOSER_ADDR', 'book_menu': 'BOOK_MENU_ACTIVE_ADDR', 'returning': 'BOOK_MENU_RETURNING_ADDR'}[gate]
                        disk.cpu.mem_write(self.bound[address], b'\x01')
                    elif gate == 'wrong_category':
                        disk.cpu.mem_write(C + 8, b'\x02\0')
                    elif gate == 'not_directory':
                        disk.cpu.mem_write(NODE0 + 0x4e, b'\x01')
                    elif gate == 'invalid_root_count':
                        disk.cpu.mem_write(self.bound['BOOK_ROOT_COUNT_ADDR'], b'\x09')
                    before = bytes(disk.sectors)
                    self.assertEqual(self.event(disk), 0)
                    self.assertEqual(self.dispatches, [ENTER])
                    self.assertEqual(bytes(disk.sectors), before)
                    self.assertFalse(disk.sector_writes)

    def test_marked_book_prepares_then_opens_real_resident_book_menu(self):
        for fs in ('fat', 'exfat'):
            with self.subTest(fs=fs):
                disk, _ = self.fixture(fs, resident=True)
                self.assertEqual(self.event(disk), 1)
                self.assertTrue(disk.sector_writes)
                self.assertEqual(bytes(disk.cpu.mem_read(self.bound['BOOK_MENU_ACTIVE_ADDR'], 1)), b'\x01')
                self.assertEqual(self.dispatches, [ENTER])
                text = bytes(disk.cpu.mem_read(NODE0 + 0x70, 512)).decode('utf-16le').split('\0')[0]
                self.assertTrue(text.startswith('Continue'), text)

    def test_nested_meditation_ancestor_keeps_native_route_despite_audiobook_root(self):
        for fs in ('fat', 'exfat'):
            with self.subTest(fs=fs):
                disk, _ = self.fixture(fs)
                def entries(name, cluster, directory=False):
                    if fs == 'exfat':
                        return checksum(exfat_entry(name, cluster, directory, length=2048))
                    return lfn(name, b'ENTRY~1    ', cluster, directory)
                disk.set_fat(11, 0x0fffffff)
                if fs == 'exfat':
                    disk.sectors[disk.DATA_LBA * 512 + 1] |= 2
                # Preserve the live exFAT AllocationBitmap system entry.
                root = ([disk.entry(0)] if fs == 'exfat' else []) + entries('Relax', 11, True) + entries('.audiobook', 0)
                root_offset = (disk.DATA_LBA + (disk.ROOT_CLUSTER - 2) * disk.SPC) * 512
                disk.sectors[root_offset:root_offset + disk.SPC * 512] = bytes(disk.SPC * 512)
                disk.sectors[root_offset:root_offset + len(root) * 32] = b''.join(root)
                inner = entries('Book', 10, True) + entries('.meditation', 0)
                inner_offset = (disk.DATA_LBA + (11 - 2) * disk.SPC) * 512
                disk.sectors[inner_offset:inner_offset + len(inner) * 32] = b''.join(inner)
                disk.cpu.mem_write(B + 0x1cc, b'\x01\0')
                record = bytearray(56)
                struct.pack_into('<HHHHI', record, 0, 1, 0, 1, 0, 11)
                record[12:54] = struct.pack('<III', 11, 2048, 0) + b'\x03\x10' + bytes(28)
                disk.cpu.mem_write(B + 68, bytes(record))
                selected_index = self.directory_index(inner, 10, fs == 'exfat')
                disk.cpu.mem_write(NODE0 + 8, struct.pack('<II', 11, selected_index))
                disk.cpu.mem_write(self.bound['BOOK_ROOT_COUNT_ADDR'], b'\x02')
                meditation = bytearray(44)
                struct.pack_into('<I', meditation, 0, 11)
                struct.pack_into('<H', meditation, 28, self.directory_index(root, 11, fs == 'exfat'))
                meditation[42:44] = b'\x01\x02'
                disk.cpu.mem_write(self.bound['BOOK_ROOTS_ADDR'] + 44, bytes(meditation))
                before = bytes(disk.sectors)
                self.assertEqual(self.event(disk), 0)
                self.assertEqual(self.dispatches, [ENTER])
                self.assertEqual(bytes(disk.sectors), before)
                self.assertFalse(disk.sector_writes)

    def test_medium_switch_after_marker_resolution_refuses_before_any_write(self):
        for fs in ('fat', 'exfat'):
            for field in ('native_device', 'ui_device', 'filesystem'):
                with self.subTest(fs=fs, field=field):
                    disk, _ = self.fixture(fs)
                    switched = []
                    def switch(cpu, address, size, unused):
                        if address == self.symbols['browser_prepare_book'] and not switched:
                            switched.append(True)
                            if field == 'native_device':
                                cpu.mem_write(0x03076b2c, struct.pack('<I', disk.DEV + 1))
                            elif field == 'ui_device':
                                cpu.mem_write(0x0300d173, b'\x01')
                            else:
                                cpu.mem_write(0x03076b24, b'\x02' if fs == 'exfat' else b'\x03')
                    disk.cpu.hook_add(UC_HOOK_CODE, switch)
                    before = bytes(disk.sectors)
                    self.assertEqual(self.event(disk), 1)
                    self.assertEqual(switched, [True])
                    self.assertFalse(disk.sector_writes)
                    self.assertEqual(bytes(disk.sectors), before)
                    self.assertFalse(self.dispatches)

    def test_live_directory_descriptor_replaces_stale_node_size_and_flags(self):
        disk, _ = self.fixture('exfat')
        disk.cpu.mem_write(NODE0 + 0x5c, b'\x01')
        disk.cpu.mem_write(NODE0 + 0x6b, struct.pack('<I', 0x12345678))
        captured = []
        def capture(cpu, address, size, unused):
            if address == self.symbols['browser_prepare_book']:
                captured.append(bytes(cpu.mem_read(cpu.reg_read(UC_ARM_REG_R0), 42)))
        disk.cpu.hook_add(UC_HOOK_CODE, capture)
        self.assertEqual(self.event(disk), 0)
        self.assertEqual(len(captured), 1)
        self.assertEqual(struct.unpack_from('<II', captured[0]), (10, 2048))
        self.assertEqual(captured[0][12], 3)
        self.assertTrue(disk.sector_writes)

    def test_failure_screen_consumes_context_and_delete_gestures_then_restores_nodes(self):
        for fs in ('fat', 'exfat'):
            with self.subTest(fs=fs):
                disk, _ = self.fixture(fs, names=('BOOK.TMP', 'One.mp3'))
                original = [bytes(disk.cpu.mem_read(address, 624)) for address in (NODE0, NODE1)]
                self.assertEqual(self.event(disk), 1)
                self.assertEqual(self.posts, [333, 335])
                self.assertFalse(self.dispatches)
                self.assertFalse(disk.sector_writes)
                labels = [bytes(disk.cpu.mem_read(address + 0x70, 512)).decode('utf-16le').split('\0')[0] for address in (NODE0, NODE1)]
                self.assertEqual(labels, ['Prepare failed', 'Use host tool'])
                for message in (0x20000080, 0x40000002, 0x40010000, 0x50010000, 0x40000004):
                    self.assertEqual(self.event(disk, message), 1)
                    self.assertFalse(self.dispatches)
                self.assertEqual(self.event(disk, BACK), 1)
                for address, expected in zip((NODE0, NODE1), original):
                    self.assertEqual(bytes(disk.cpu.mem_read(address, 624)), expected)
                self.assertEqual(self.posts, [333, 335, 333, 335])
                self.assertEqual(self.event(disk, 0x40000004), 0)
                self.assertEqual(self.dispatches, [0x40000004])
                self.assertFalse(disk.sector_writes)

    def test_overlay_code_reload_resets_preparation_flags_before_next_event(self):
        disk, _ = self.fixture(marker=False)
        payload = (ROOT / 'out/browser_sort/browser_sort.bin').read_bytes()
        tool = ROOT / 'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin/arm-none-eabi-nm'
        if not tool.exists():
            tool = 'arm-none-eabi-nm'
        table = subprocess.check_output([str(tool), str(ROOT / 'out/browser_sort/browser_sort.elf')], text=True)
        locals_ = {name: int(value, 16) for value, kind, name in (line.split() for line in table.splitlines())}
        for name in ('preparing', 'preparation_error'):
            address = locals_[name]
            self.assertGreaterEqual(address, 0x0307b874)
            self.assertLess(address, 0x0307b874 + len(payload), name + ' must be copied metadata, not NOLOAD')
            disk.cpu.mem_write(address, b'\xff')
        disk.cpu.mem_write(0x0307b874, payload)
        self.assertEqual(self.event(disk), 0)
        self.assertEqual(self.dispatches, [ENTER])
        self.assertFalse(disk.sector_writes)


if __name__ == '__main__':
    unittest.main()
