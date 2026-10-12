"""Run compiled hooks and stock folder counters on Cortex-M3 with virtual media.

Requires unicorn==2.1.4 and a built out/gen/cfw.bin. Raw directory-reader trampolines and the watchdog are substituted; filtering,
patch installation, and counters execute ARM. Stock sector I/O and cursor-cache
behavior are outside this fixture.
"""
import struct
import sys
import unittest
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from test_music_filter import fat_entry, fat_marker, exfat_entry, END

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from rknano_fw import Image

class ArmMusicTests(unittest.TestCase):
    def setUp(self):
        self.syms = {n: int(v, 16) for v, t, n in
                     (line.split() for line in (ROOT / 'out/gen/cfw.nm').read_text().splitlines())}
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000, 0x100000)
        self.cpu.mem_map(0x20000000, 0x10000)
        img = Image((ROOT / 'NANOV170.IMG').read_bytes())
        for kind in ('code', 'data'):
            m = img.modules[0]
            start, length = m[kind + '_exec'], m[kind + '_len']
            offset = img.l2f(m[kind + '_load'])
            self.cpu.mem_write(start, bytes(img.d[offset:offset + length]))
        self.cpu.mem_write(self.syms['cfw_stub'], (ROOT / 'out/gen/cfw.bin').read_bytes())
        self.fat = {0: [fat_entry(b'BOOKS      ', 30, True), fat_entry(b'MUSIC      ', 40, True), END],
                    30: [fat_entry(), *fat_marker(), END], 40: [fat_entry(), END]}
        self.exfat = {2: [*exfat_entry('Kirjat 日本語', 30, True), *exfat_entry('Musiikki äö', 40, True), END],
                      30: [*exfat_entry('.nomusic', 0, length=0), END], 40: [END]}
        self.cpu.hook_add(UC_HOOK_CODE, self.intercept)
        self.call('cfw_stub')
        self.call('music_filter_reset')
        self.call('music_hooks', 1)

    def intercept(self, cpu, address, size, user):
        if address in (self.syms['music_watchdog'], 0x03065800):
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
            return
        if address not in (self.syms['music_fat_original'], self.syms['music_exfat_original']):
            return
        out, parent, index = [cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        dirs = self.fat
        if address == self.syms['music_exfat_original']:
            dirs = self.exfat
            descriptor = parent
            parent = struct.unpack('<I', cpu.mem_read(parent, 4))[0]
            if parent == 0:
                parent = 2
                cpu.mem_write(descriptor, struct.pack('<I', parent))
        entries = dirs.get(parent, [END])
        if index < len(entries):
            cpu.mem_write(out, entries[index])
            result = 0
        else:
            result = 9
        cpu.reg_write(UC_ARM_REG_R0, result)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def call(self, function, *args):
        for r, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
            self.cpu.reg_write(r, value)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x2000f000)
        self.cpu.reg_write(UC_ARM_REG_LR, 0x20000001)
        address = self.syms[function] if isinstance(function, str) else function
        self.cpu.emu_start(address | 1, 0x20000000, count=2000000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC), 0x20000000, 'instruction limit reached')
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP), 0x2000f000)
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def test_fat_real_entry_hook(self):
        self.assertEqual(self.call(0x0305b3ea, 0x20001000, 0, 0), 0)
        self.assertTrue(self.cpu.mem_read(0x2000100b, 1)[0] & 2)
        self.assertEqual(self.call(0x0305b3ea, 0x20001000, 0, 1), 0)
        self.assertFalse(self.cpu.mem_read(0x2000100b, 1)[0] & 2)

    def test_stock_fat_counter_agrees_with_filter(self):
        self.assertEqual(self.call(0x0305c9e8, 0, 0), 1)
        self.fat[40] = [*fat_marker(), END]
        self.call('music_filter_reset')
        self.assertEqual(self.call(0x0305c9e8, 0, 0), 0)

    def test_stock_exfat_counter_agrees_with_filter(self):
        self.cpu.mem_write(0x03076b24, b'\x03')
        self.cpu.mem_write(0x20002000, struct.pack('<IIIB3x', 2, 4096, 0, 3))
        self.assertEqual(self.call(0x0305cad2, 0x20002000, 0), 1)

    def test_restores_both_original_prologues(self):
        self.call('music_hooks', 0)
        self.assertEqual(bytes(self.cpu.mem_read(0x0305b3ea, 4)), bytes.fromhex('2de9f05f'))
        self.assertEqual(bytes(self.cpu.mem_read(0x0305b2a2, 4)), bytes.fromhex('2de9f74f'))

if __name__ == '__main__':
    unittest.main()
