"""Real resident key FSM and repeat dispatcher; physical input is substituted.

No firmware image is built. Two self-contained resident hooks are assembled in
a temporary directory; stock timing is checked independently of patched timing.
"""
import hashlib
import os
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import tempfile
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from rknano_fw import Image
from playback_layout import STOCK_SHA256, navigation_hold_space, read_patch

STOP = 0x030ff000
STATE = 0x0300d03c
FLAG = 0x0300d080


class NavigationHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiled = []
        environment = os.environ.copy()
        if not shutil.which('arm-none-eabi-gcc'):
            toolchain = ROOT / 'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin'
            environment['PATH'] = str(toolchain) + os.pathsep + environment.get('PATH', '')
        with tempfile.TemporaryDirectory(prefix='nano-navigation-hold-') as directory:
            for name in ('navigation_hold', 'navigation_hold_resident'):
                destination = Path(directory) / (name + '.patch')
                subprocess.run(['tools/asm2patch.sh', 'playback/hooks/' + name + '.S', str(destination)],
                               cwd=ROOT, env=environment, check=True, capture_output=True)
                cls.compiled.append(read_patch(destination))

    def setUp(self):
        source = (ROOT / 'NANOV170.IMG').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), STOCK_SHA256)
        self.image = Image(source)
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000, 0x100000)
        for index in (0, 31):
            module = self.image.modules[index]
            for kind in ('code', 'data'):
                offset = self.image.l2f(module[kind + '_load'])
                self.cpu.mem_write(module[kind + '_exec'], bytes(self.image.d[offset:offset+module[kind + '_len']]))
        self.key = 0
        self.stop_at = None
        self.windows = []
        self.services = []
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)

    def put(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def word(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def hook(self, cpu, address, size, context):
        if address == self.stop_at:
            cpu.reg_write(UC_ARM_REG_PC, STOP)
        elif address == 0x03065d5c:
            self.put(cpu.reg_read(UC_ARM_REG_R0), self.key)
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        elif address in (0x030550b6, 0x0306b0a0, 0x0306b040):
            self.services.append((address, cpu.reg_read(UC_ARM_REG_R0)))
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        elif address == 0x0306b26a:
            self.windows.append(cpu.reg_read(UC_ARM_REG_R0))
            cpu.reg_write(UC_ARM_REG_PC, STOP)

    def call(self, address):
        self.cpu.reg_write(UC_ARM_REG_SP, 0x030fe000)
        self.cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
        self.cpu.emu_start(address | 1, STOP, count=10000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC), STOP)

    def patch(self):
        navigation_hold_space(self.image)
        for module, address, data in self.compiled:
            self.image.patch(module, address, data)
        for address, length in ((0x03004110, 4), (0x030658b8, 4),
                                (0x03065918, 40), (0x03065ec0, 4)):
            offset, _ = self.image.region(0, address)
            self.cpu.mem_write(address, bytes(self.image.d[offset:offset+length]))

    def poll(self, key):
        self.key = key
        self.put(FLAG, 0)  # native consumer acknowledges event-ready flags
        self.call(0x03065e9a)
        return self.word(STATE + 40) if self.word(FLAG) & 1 else None

    def dispatch(self, event):
        self.cpu.reg_write(UC_ARM_REG_R4, event)
        self.cpu.reg_write(UC_ARM_REG_R5, 0)
        self.stop_at = 0x03063aca
        self.call(0x03063a76)
        self.stop_at = None

    def consume_home(self):
        self.stop_at = 0x03079eea
        self.call(0x03079ed2)
        self.stop_at = None
        return bool(self.windows)

    def sequence(self, key, polls):
        return [(n, event) for n in range(1, polls+1)
                if (event := self.poll(key)) is not None]

    def test_stock_center_baseline(self):
        events = self.sequence(0x40, 76)
        self.assertEqual(events[:3], [(2, 0x10000040), (20, 0x20000040), (28, 0x30000040)])
        for n, event in events:
            self.dispatch(event)
            if n < 76:
                self.assertFalse(self.consume_home())
        self.assertTrue(self.consume_home())

    def test_center_back_15_home_55(self):
        self.patch()
        events = self.sequence(0x40, 55)
        self.assertEqual(events, [(2, 0x10000040), (15, 0x20000040)] +
                         [(n, 0x30000040) for n in (23, 31, 39, 47, 55)])
        for n, event in events:
            self.dispatch(event)
            if n < 55:
                self.assertFalse(self.consume_home())
        self.assertTrue(self.consume_home())

    def test_release_boundaries(self):
        for length in (1, 2, 14, 15, 19, 20):
            with self.subTest(length=length):
                self.setUp()
                self.patch()
                self.sequence(0x40, length)
                expected = None if length < 2 else (0x40000040 if length < 15 else 0x50000040)
                self.assertEqual(self.poll(0), expected)
                self.assertEqual(self.word(STATE + 60), 0)
                self.assertEqual(self.sequence(0x40, 2), [(2, 0x10000040)])

    def test_other_keys_unchanged(self):
        for key in (1, 2, 4, 8, 0x10, 0x20, 0x80, 0x1000):
            with self.subTest(key=key):
                expected = self.sequence(key, 80) + [(81, self.poll(0))]
                self.setUp()
                self.patch()
                actual = self.sequence(key, 80) + [(81, self.poll(0))]
                self.assertEqual(actual, expected)
                self.setUp()

    def test_two_short_clicks_keep_release_events(self):
        self.patch()
        for _ in range(2):
            self.assertEqual(self.sequence(0x40, 4), [(2, 0x10000040)])
            self.assertEqual(self.poll(0), 0x40000040)
        # The separate native click aggregation delay remains byte-identical.
        self.assertEqual(bytes(self.cpu.mem_read(0x030636fe, 2)), bytes.fromhex('2328'))

    def test_release_resets_home_repeat_count(self):
        self.patch()
        for _, event in self.sequence(0x40, 47):
            self.dispatch(event)
        self.assertEqual(self.word(0x03004108), 4)
        self.dispatch(self.poll(0))
        self.assertEqual(self.word(0x03004108), 0)
        for _, event in self.sequence(0x40, 47):
            self.dispatch(event)
        self.assertFalse(self.consume_home())
        for _, event in self.sequence(0x40, 8):
            self.dispatch(event)
        self.assertTrue(self.consume_home())

    def test_watchdog_handler_retains_fault_call(self):
        self.patch()
        self.stop_at = 0x030658c2
        self.call(0x030658b6)
        self.assertEqual(self.services, [(0x030550b6, 0)])

    def test_helper_registers_and_boundaries(self):
        self.patch()
        for key, count, expected in ((0x40, 14, 20), (0x40, 13, 14), (4, 14, 15)):
            registers = (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                         UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                         UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
                         UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12)
            values = {reg: 0x1000 + reg for reg in registers}
            values[UC_ARM_REG_R1] = key
            values[UC_ARM_REG_R5] = STATE
            for reg, value in values.items():
                self.cpu.reg_write(reg, value)
            self.cpu.reg_write(UC_ARM_REG_R0, count)
            self.stop_at = 0x03065ec4
            self.call(0x03065ec0)
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), expected)
            self.assertEqual(self.word(STATE + 48), key)
            for reg, value in values.items():
                self.assertEqual(self.cpu.reg_read(reg), value)
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP), 0x030fe000)
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_LR), STOP | 1)
        self.assertEqual([(module, address, len(data)) for module, address, data in self.compiled],
                         [(0, 0x03065ec0, 4), (0, 0x03065918, 40)])

    def test_reclaim_rejects_changed_bytes_or_interior_pointer(self):
        original = bytes(self.image.d)
        for address in (0x03065918, 0x030658b6, 0x030658b8, 0x03065ec0, 0x03004110):
            candidate = Image(original)
            candidate.patch(0, address, b'\xff')
            with self.assertRaisesRegex(ValueError, 'navigation hold base changed'):
                navigation_hold_space(candidate)
        candidate = Image(original)
        candidate.patch(0, 0x03004121, struct.pack('<I', 0x03065923))
        with self.assertRaisesRegex(ValueError, 'absolute reference'):
            navigation_hold_space(candidate)
