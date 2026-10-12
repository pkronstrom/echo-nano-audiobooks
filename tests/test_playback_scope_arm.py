"""Execute playback scope decisions from the built image on ARM, modes 0..9."""
import struct
import unittest
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R10, UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR
from test_music_arm import ROOT, Image
import test_music_arm as arm_fixture

class PlaybackScopeTests(unittest.TestCase):
    def intercept(self, cpu, address, size, user):
        if getattr(self, 'queue_fixture', False):
            self.queue_calls.append(address) if address in (0x0305d0dc, 0x0305d130, 0x0305ddb8, 0x0305dd8c, 0x0305de7e, 0x0305e006) else None
            result = None
            if address == 0x0305d0dc:
                result = 100  # whole storage count
            elif address == 0x0305d130:
                parent = cpu.reg_read(UC_ARM_REG_R1)
                cpu.mem_write(parent, struct.pack('<I', 30))
                cpu.mem_write(parent + 28, struct.pack('<IIIB3x', 30, 4096, 0, 3))
                result = 3  # saved global track47 is local track3
            elif address in (0x0305ddb8, 0x0305dd8c):
                self.assertEqual(self.word(cpu.reg_read(UC_ARM_REG_R1)), 30)
                result = 0
            elif address in (0x0305de7e, 0x0305e006):
                parent = cpu.reg_read(UC_ARM_REG_R0)
                self.assertEqual(self.word(parent) if address == 0x0305e006 else parent, 30)
                result = 12  # files in selected folder
            if result is not None:
                cpu.reg_write(UC_ARM_REG_R0, result)
                cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
                return
        arm_fixture.ArmMusicTests.intercept(self, cpu, address, size, user)
    call = arm_fixture.ArmMusicTests.call
    state = 0x0300d85c
    active = 0x20004000
    prefs = 0x20005000
    player = 0x20006000

    def setUp(self):
        arm_fixture.ArmMusicTests.setUp(self)
        img = Image((ROOT / 'out/NANOV170.IMG').read_bytes())
        m = img.modules[33]
        offset = img.l2f(m['code_load'])
        self.cpu.mem_write(m['code_exec'], bytes(img.d[offset:offset + m['code_len']]))

    def word(self, address, value=None):
        if value is not None:
            self.cpu.mem_write(address, struct.pack('<I', value))
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def half(self, address, value=None):
        if value is not None:
            self.cpu.mem_write(address, struct.pack('<H', value))
        return struct.unpack('<H', self.cpu.mem_read(address, 2))[0]

    def run_slice(self, start, end):
        self.cpu.reg_write(UC_ARM_REG_SP, 0x2000f000)
        self.cpu.emu_start(start | 1, end, count=10000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC), end)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP), 0x2000f000)

    def test_initialization_and_resume_scope_matrix(self):
        for kind in (1, 10, 99):
            for mode in range(10):
                with self.subTest(kind=kind, mode=mode):
                    self.half(self.state + 0xf2, kind)
                    self.word(self.active + 28, mode)
                    self.word(self.active + 36, 3)
                    self.cpu.reg_write(UC_ARM_REG_R4, self.active)
                    self.cpu.reg_write(UC_ARM_REG_R8, self.state)
                    self.run_slice(0x03082962, 0x0308298e)
                    self.assertEqual(self.word(self.active + 28), mode & ~4 if kind == 99 else mode)
                    expected = 2 if kind == 99 or mode in (0, 1, 2) else 3
                    self.assertEqual(self.word(self.active + 36), expected)

    def test_raw_settings_changes_preserve_position_and_order(self):
        for mode in range(10):
            with self.subTest(mode=mode):
                self.cpu.mem_write(self.prefs + 0x6d, bytes([mode]))
                self.word(self.player + 12, self.active)
                self.word(self.active + 32, 1)
                self.half(self.state + 2, 7)
                self.half(self.state, 12)
                self.cpu.reg_write(UC_ARM_REG_R5, self.player)
                self.cpu.reg_write(UC_ARM_REG_R7, self.prefs)
                self.cpu.reg_write(UC_ARM_REG_R10, self.state)
                self.run_slice(0x0308301e, 0x0308319c)
                self.assertEqual(self.word(self.active + 28), mode & ~4)
                self.assertEqual(self.word(self.active + 32), 1)
                self.assertEqual(self.word(self.active + 36), 2)
                self.assertEqual(self.half(self.state + 10), 2)
                self.assertEqual(self.half(self.state + 2), 7)
                self.assertEqual(self.half(self.state + 6), 7)
                self.assertEqual(self.half(self.state), 12)
                self.assertEqual(self.cpu.mem_read(self.prefs + 0x6d, 1)[0], mode)

    def test_stock_queue_rebases_saved_index_and_count(self):
        # Execute stock queue initialization, substituting filesystem helper
        # results so global/local positions and counts deliberately differ.
        for filesystem in (2, 3):
            for scope in (2, 3):
                with self.subTest(filesystem=filesystem, scope=scope):
                    self.queue_fixture, self.queue_calls = True, []
                    self.cpu.mem_write(0x03076b24, bytes([filesystem]))
                    self.half(self.state + 0xf2, 99)
                    self.word(0x2000f000, 0x03005ab4)  # fifth argument: extensions
                    self.assertEqual(self.call(0x030603d0, self.state, 47, scope, 0), 0)
                    self.assertEqual(self.half(self.state), 12 if scope == 2 else 100)
                    self.assertEqual(self.half(self.state + 2), 3 if scope == 2 else 47)
                    self.assertEqual(self.half(self.state + 10), scope)

    def test_stock_folder_wrap_never_resolves_another_folder(self):
        self.queue_fixture, self.queue_calls = True, []
        self.half(self.state + 0xf2, 99)
        self.half(self.state, 12)
        self.half(self.state + 2, 12)
        self.half(self.state + 10, 2)
        self.half(self.state + 12, 0)
        self.word(self.state + 0x34, 30)
        self.cpu.reg_write(UC_ARM_REG_R0, self.state)
        self.cpu.reg_write(UC_ARM_REG_R1, 1)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x2000f000)
        self.cpu.emu_start(0x030604ad, 0x03060840, count=10000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC), 0x03060840)
        self.assertEqual(self.half(self.state + 2), 1)
        self.assertIn(0x0305ddb8, self.queue_calls)
        self.assertNotIn(0x0305d130, self.queue_calls)
        self.assertEqual(self.word(self.state + 0x34), 30)

    def test_continuation_scope_preserves_direction(self):
        for kind in (1, 10, 99):
            for direction in (1, 0xffffffff):
                with self.subTest(kind=kind, direction=direction):
                    self.half(self.state + 0xf2, kind)
                    self.cpu.reg_write(UC_ARM_REG_R0, direction)
                    self.run_slice(0x03081844, 0x030817ba)
                    self.assertEqual(self.half(self.state + 10), 2 if kind == 99 else 3)
                    self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), direction)

if __name__ == '__main__':
    unittest.main()
