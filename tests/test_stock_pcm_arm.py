"""Stock 1.7.0 PCM boundary evidence; no speed patch is installed by these tests.

Execute conversion/pump instructions. Substitute codec delivery, event service,
IRQ controls and DMA hardware, so these are ABI checks, not real-time evidence.
"""
from pathlib import Path
import struct
import hashlib
import sys
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rknano_fw import Image
ROOT = Path(__file__).resolve().parents[1]
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
STATE, BUFFER, INFO, STOP = 0x0300d7e8, 0x03040000, 0x03041000, 0x030ff000

class StockPcmTests(unittest.TestCase):
    def setUp(self):
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000, 0x100000)
        source = (ROOT / 'NANOV170.IMG').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         '54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116')
        image = Image(source)
        self.image = image
        for idx in (0, 33, 42):
            m = image.modules[idx]
            for kind in ('code', 'data'):
                if m[kind + '_len']:
                    off = image.l2f(m[kind + '_load'])
                    self.cpu.mem_write(m[kind + '_exec'], bytes(image.d[off:off+m[kind+'_len']]))
        self.cpu.mem_write(STATE, bytes(40))
        self.word(0x03039714, INFO)
        self.word(INFO + 156, 16)
        self.word(STATE + 12, BUFFER)
        self.word(0x03039724, 10)  # skip startup mute counter
        self.cpu.mem_write(0x03039898 + 12, b'\0')  # EQ disabled
        self.samples = [-32768, 32767, -123, 456, 0, 1, -1, 12]
        self.codec_status = 1
        self.native_codec = False
        self.dma = []
        self.irq_calls = []
        self.mailbox = []
        self.copy_dma = []
        self.trace = []
        self.returned = False
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)

    def word(self, addr, value):
        self.cpu.mem_write(addr, struct.pack('<I', value))

    def readword(self, addr):
        return struct.unpack('<I', self.cpu.mem_read(addr, 4))[0]

    def hook(self, cpu, addr, size, user):
        result = None
        if addr == STOP:
            self.returned = True
            cpu.emu_stop()
        elif addr == 0x030835c8 and not self.native_codec:
            # Native wrapper expects pointers to buffer pointer and stereo-frame count.
            r0, r1 = (cpu.reg_read(r) for r in REGS[:2])
            self.assertEqual((r0, r1), (STATE+12, STATE+28))
            if self.codec_status == 1:
                self.word(r0, BUFFER)
                self.word(r1, len(self.samples)//2)
                cpu.mem_write(BUFFER, struct.pack('<8h', *self.samples))
            result = self.codec_status
        elif addr == 0x0306b0a0:
            result = int(cpu.reg_read(UC_ARM_REG_R0) == 301)
        elif addr == 0x03081a26:
            result = 0  # omit spectrum analysis
        elif addr in (0x03071a90, 0x03071a64):
            args = tuple(cpu.reg_read(r) for r in REGS[:3])
            self.mailbox.append((addr, args))
            self.trace.append(('mailbox', addr))
            result = 0  # decoder mailbox hardware; no simulated next decode
        elif addr == 0x0306c1b8:
            result = 2  # allocate a non-output DMA channel
        elif addr == 0x03059a04:
            result = 0  # yield while polling completed copy
        elif addr in (0x0305965e, 0x03059514, 0x030595b4, 0x03059558, 0x0306a4be):
            self.irq_calls.append((addr, cpu.reg_read(UC_ARM_REG_R0), cpu.reg_read(UC_ARM_REG_R1)))
            result = 0  # IRQ gating / request next processing pass
        elif addr == 0x0306c1e4:
            args = tuple(cpu.reg_read(r) for r in REGS)
            sp = cpu.reg_read(UC_ARM_REG_SP)
            extra = struct.unpack('<2I', cpu.mem_read(sp, 8))
            pcm = bytes(cpu.mem_read(args[1], args[3]*4))
            if args[0] == 2:
                self.copy_dma.append((args, extra, pcm))
                self.trace.append(('copy', args[2]))
                cpu.mem_write(args[2], pcm)
                self.assertEqual(extra[1], 0x03057421)
                # Simulate completion IRQ by executing the actual native callback;
                # LR is still the DMA caller's return address.
                cpu.reg_write(UC_ARM_REG_PC, extra[1])
                return
            self.dma.append((args, extra, pcm))
            result = 0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0, result)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def call(self, addr, *args):
        self.returned = False
        for r, value in zip(REGS, args): self.cpu.reg_write(r, value)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x030fe000)
        self.cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
        self.cpu.emu_start(addr | 1, 0, count=20000)
        self.assertTrue(self.returned)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP), 0x030fe000)

    def test_16bit_conversion_expands_signed_stereo_samples_without_changing_frame_count(self):
        self.cpu.mem_write(BUFFER, struct.pack('<8h', *self.samples))
        self.word(STATE+28, 4)
        self.call(0x03069484, BUFFER, STATE+28, 16)
        self.assertEqual(struct.unpack('<8i', self.cpu.mem_read(BUFFER,32)), tuple(x << 8 for x in self.samples))
        self.assertEqual(self.readword(STATE+28), 4)

    def test_ready_buffer_reaches_dma_as_words_with_original_sample_order(self):
        self.call(0x03069542)
        self.assertEqual(len(self.dma), 1)
        args, extra, pcm = self.dma[0]
        self.assertEqual(args, (5, BUFFER, 0x40030024, 8))
        self.assertEqual(extra, (0x03005b2c, 0x030693cb))
        self.assertEqual(struct.unpack('<8i', pcm), tuple(x << 16 for x in self.samples))
        self.assertEqual(self.readword(STATE+16), 1)

    def test_codec_wait_does_not_submit_or_convert_stale_buffer(self):
        self.codec_status = 2
        self.cpu.mem_write(BUFFER, b'unchanged buffer')
        self.call(0x03069542)
        self.assertEqual(self.dma, [])
        self.assertEqual(bytes(self.cpu.mem_read(BUFFER, 16)), b'unchanged buffer')
        self.assertEqual(self.readword(STATE+24), 1)

    def test_native_codec_wrapper_returns_wait_while_decode_in_progress(self):
        self.native_codec = True
        self.word(0x03039e94, 0)  # table slot 0 -> module42 dispatcher
        self.word(0x03039e20+36, 0)  # no completed block
        self.word(0x03039e20+40, 1)  # decode in progress
        self.word(STATE+12, BUFFER)
        self.word(STATE+28, 123)
        self.call(0x030835c8, STATE+12, STATE+28)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 2)
        self.assertEqual(self.readword(STATE+12), BUFFER)
        self.assertEqual(self.readword(STATE+28), 123)

    def test_pump_then_dma_callback_submits_prepared_block_only_once(self):
        self.word(STATE+20, 1)
        self.call(0x03069542)
        self.assertEqual(self.dma, [])
        self.assertEqual(self.readword(STATE+16), 0)
        self.call(0x030693ca)
        self.assertEqual(len(self.dma), 1)
        self.assertEqual(self.dma[0][0], (5, BUFFER, 0x40030024, 8))
        self.call(0x030693ca)
        self.assertEqual(len(self.dma), 1)
        self.assertEqual(self.readword(STATE+20), 0)

    def test_dma_callback_then_pump_hands_off_immediately(self):
        self.word(STATE+16, 1)
        self.word(STATE+20, 1)
        self.call(0x030693ca)
        self.assertEqual(self.dma, [])
        self.assertEqual(self.readword(STATE+20), 0)
        self.call(0x03069542)
        self.assertEqual(len(self.dma), 1)

    def test_native_init_registers_pcm_pump_as_low_priority_pendsv(self):
        self.cpu.mem_map(0xe000e000, 0x2000)
        self.word(0xe000ed08, 0x03004000)  # current vector table
        self.call(0x03081410)
        self.assertEqual(self.readword(0x03004000+14*4), 0x03069543)
        self.assertIn((0x03059514, 14, 0xe0), self.irq_calls)
        self.assertEqual(self.irq_calls[0][0:2], (0x0305965e, 14))
        self.assertEqual(self.irq_calls[-1][0:2], (0x03059558, 14))

    def prepare_native_completed_block(self, pcm, frames, bits=16):
        self.native_codec = True
        self.word(0x03039e94, 0)
        self.word(0x03039e20+12, bits)
        self.word(0x03039e20+28, 0x03044000)
        self.word(0x03039e20+32, frames)
        self.word(0x03039e20+36, 1)
        self.word(0x03039e20+40, 0)
        self.word(0x03039e20+44, 0)
        self.cpu.mem_write(0x03044000, pcm)

    def test_native_completed_blocks_copy_then_alternate_and_reuse_first_buffer(self):
        self.cpu.mem_write(0x03035174, b'\0')
        frames = 1152  # fixture size, not a proved maximum decoder block
        payloads = [struct.pack('<2304h', *([value, -value]*frames))
                    for value in (123, 456, 789)]
        destinations = (0x03023174, 0x0302c174, 0x03023174)
        for index, (pcm, dest) in enumerate(zip(payloads, destinations)):
            self.prepare_native_completed_block(pcm, frames)
            self.call(0x030835c8, STATE+12, STATE+28)
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 1)
            self.assertEqual(self.readword(STATE+12), dest)
            self.assertEqual(self.readword(STATE+28), frames)
            self.assertEqual(bytes(self.cpu.mem_read(dest, len(pcm))), pcm)
            self.assertEqual(self.copy_dma[-1][0], (2, 0x03044000, dest, frames))
            self.assertEqual(self.readword(0x03039e20+36), 0)
            self.assertEqual(self.readword(0x03039e20+40), 1)
            self.assertEqual(self.mailbox[-2:], [(0x03071a90, (4,0,1)),
                                                (0x03071a64, (0,0,1))])
            self.assertEqual(self.trace[-3:], [('mailbox',0x03071a90),
                                              ('mailbox',0x03071a64), ('copy',dest)])
            if index == 1:
                self.assertEqual(bytes(self.cpu.mem_read(destinations[0], len(pcm))), payloads[0])
        self.assertEqual(self.dma, [])  # codec copy is separate from output DMA

    def test_native_completed_error_returns_zero_without_copy_or_next_request(self):
        self.prepare_native_completed_block(bytes(16), 4)
        self.word(0x03039e20+44, 1)
        self.word(STATE+28, 99)
        self.call(0x030835c8, STATE+12, STATE+28)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 0)
        self.assertEqual(self.readword(STATE+28), 99)
        self.assertEqual(self.mailbox, [])
        self.assertEqual(self.copy_dma, [])

    def test_native_idle_decoder_starts_request_and_returns_wait(self):
        self.native_codec = True
        self.word(0x03039e94, 0)
        self.word(0x03039e20+36, 0)
        self.word(0x03039e20+40, 0)
        self.word(STATE+28, 99)
        self.call(0x030835c8, STATE+12, STATE+28)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 2)
        self.assertEqual(self.readword(STATE+28), 99)
        self.assertEqual(self.readword(0x03039e20+40), 1)
        self.assertEqual(self.mailbox, [(0x03071a90, (4,0,1)),
                                        (0x03071a64, (0,0,1))])
        self.assertEqual(self.copy_dma, [])

    def load_mp3_coprocessor(self):
        # Module73 is linked at code address zero on the secondary processor;
        # the image's 0x01000000 code_exec is its upload window, not its PC base.
        self.cpu.mem_map(0, 0x10000)
        self.cpu.mem_map(0x01000000, 0x100000)
        module = self.image.modules[73]
        offset = self.image.l2f(module['code_load'])
        code = bytes(self.image.d[offset:offset+module['code_len']])
        self.assertIn(b'Mp3\\libMad\\mp3_decinternal.c', code)
        self.cpu.mem_write(0, code)
        offset = self.image.l2f(module['data_load'])
        self.cpu.mem_write(module['data_exec'], bytes(self.image.d[offset:offset+module['data_len']]))

    def test_native_mp3_output_duplicates_mono_into_stereo_16bit_pairs(self):
        self.load_mp3_coprocessor()
        obj, dest = 0x01048000, 0x01049000
        self.cpu.mem_write(obj+1, b'\0')  # mono flag; actual setup derives mode
        self.word(obj+44, dest)
        self.word(0x010242f8, 1152)  # native block target; render only 32 frames
        self.call(0x3968, obj, 0, 0, 0)
        self.assertEqual(self.readword(0x01043b0c+28), 0)
        samples = [-32768,32767,-123,456]*8
        self.cpu.mem_write(0x01043b30, struct.pack('<32i', *samples))
        self.call(0x36ea)
        self.assertEqual(struct.unpack('<64h', self.cpu.mem_read(dest,128)),
                         tuple(v for sample in samples for v in (sample,sample)))
        self.assertEqual(self.readword(obj+52), 32)

    def test_native_mp3_output_interleaves_distinct_stereo_channels(self):
        self.load_mp3_coprocessor()
        obj, dest = 0x01048000, 0x01049000
        self.cpu.mem_write(obj+1, b'\1')
        self.word(obj+44, dest)
        self.word(obj+48, dest)
        self.word(0x010242f8, 1152)
        samples = ([-32768,32767,-123,456]*8, [12,-21,34,-43]*8)
        for channel in (0,1):
            self.call(0x3968, obj, 0, channel, 0)
            self.assertEqual(self.readword(0x01043b0c+28), 1)
            self.cpu.mem_write(0x01043b30, struct.pack('<32i', *samples[channel]))
            self.call(0x36ea)
        self.assertEqual(struct.unpack('<64h', self.cpu.mem_read(dest,128)),
                         tuple(v for pair in zip(*samples) for v in pair))
        self.assertEqual((self.readword(obj+52), self.readword(obj+56)), (32,32))

    def test_native_mp3_exports_16bit_depth_and_stereo_frame_count(self):
        self.load_mp3_coprocessor()
        self.call(0x2c18, 17, STATE+28, 0, 0)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 1)
        self.assertEqual(self.readword(STATE+28), 16)
        for frames in (384,576,1152):
            self.word(0x010242f8, frames)
            self.word(0x0102221c, 0x01049000)
            self.call(0x2c18, 10, STATE+12, STATE+28, 0)
            self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 1)
            self.assertEqual(self.readword(STATE+12), 0x01049000)
            self.assertEqual(self.readword(STATE+28), frames)

    def test_native_mp3_time_is_decoded_frame_time_and_host_getter_copies_packet_time(self):
        self.load_mp3_coprocessor()
        self.word(0x010429bc+40, 48000)
        self.word(0x010429bc+60, 4800)
        self.call(0x2c18, 7, STATE+28, 0, 0)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 1)
        self.assertEqual(self.readword(STATE+28), 100)
        self.word(0x03039e94, 0)
        self.word(0x03039e20, 123456)
        self.word(0x03039e20+4, 999999)  # deliberately distinct: not timestamp
        self.call(0x030834f6, STATE+28)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0), 1)
        self.assertEqual(self.readword(STATE+28), 123456)

    def test_native_type_zero_loader_selects_module42_and_mp3_module73(self):
        self.word(0x03039e94, 0)
        loads = []
        def loader_probe(cpu, addr, size, user):
            if addr in (0x0306b6bc,0x030714e4):
                loads.append((addr,cpu.reg_read(UC_ARM_REG_R0)))
                if addr == 0x030714e4:
                    cpu.emu_stop()
                    return
            elif addr not in (0x03054cac,0x03054d1c):
                return
            cpu.reg_write(UC_ARM_REG_R0,0)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        hook = self.cpu.hook_add(UC_HOOK_CODE,loader_probe)
        self.cpu.reg_write(UC_ARM_REG_SP,0x030fe000)
        self.cpu.reg_write(UC_ARM_REG_LR,STOP|1)
        self.cpu.emu_start(0x03080f03,0,count=1000)
        self.cpu.hook_del(hook)
        self.assertEqual(loads,[(0x0306b6bc,42),(0x030714e4,73)])

if __name__ == '__main__': unittest.main()
