"""Patched resident PCM pump/callback integration, with synthetic codec and DMA.

Real stock pump/conversion/callback plus compiled speed overlay/resident guards
execute. Codec delivery, IRQ/event functions and DMA hardware are substituted;
this verifies scheduling/ABI/sample ownership, not real-time audio or hardware.
"""
import struct
import math
import unittest
from unicorn import UcError, UC_HOOK_MEM_INVALID
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK
import test_stock_pcm_arm as stock
from test_stock_pcm_arm import ROOT, STATE, REGS, STOP

PACKET_FRAMES = 256
PACKET_BYTES = PACKET_FRAMES * 8


class SpeedPumpTests(unittest.TestCase):
    def setUp(self):
        self.f = stock.StockPcmTests()
        self.f.hook = self.hook
        self.f.setUp()
        self.cpu = self.f.cpu
        self.cpu.mem_map(0xe000e000, 0x2000)
        self.cpu.mem_map(0x60000000,4096)
        self.cpu.mem_write(0x600003a0,struct.pack("<I",0xff))
        self.syms = {name: int(value, 16) for value, kind, name in
                     (line.split() for line in (ROOT/'out/playback/playback.nm').read_text().splitlines())}
        self.cpu.mem_write(self.syms['playback_header'], (ROOT/'out/playback/playback.bin').read_bytes())
        for name in ('speed_capture', 'speed_dma_pump', 'speed_dma_callback', 'speed_guard', 'speed_seek', 'speed_status', 'speed_status_guard'):
            path = ROOT/'out/playback'/f'{name}.patch'
            for line in path.read_text().splitlines():
                if line and not line.startswith('#'):
                    module, address, data = line.split(':')
                    self.cpu.mem_write(int(address, 16), bytes.fromhex(data))
        self.f.native_codec = True  # execute patched capture wrapper, not stock fixture shortcut
        self.codec_entry = self.f.readword(0x03035178) & ~1
        self.blocks = [1152] * 4
        self.codec_calls = 0
        self.codec_wait = False
        self.codec_value = 1000
        self.variable_pcm = False
        self.source_frames = 0
        self.source_origin = 0
        self.pending_completion = False
        self.seeks = []
        self.notifications = []
        self.bad_memory = None
        self.dsp_fault = False
        self.dma_failure = False
        self.cpu.hook_add(UC_HOOK_MEM_INVALID, self.invalid_memory)
        self.f.word(0x03039e94, 0)
        self.f.word(0x03039714, 0x03023090)
        self.f.word(0x03023098, 48000)
        self.f.word(0x0302312c, 16)
        self.f.word(0x03039e20, 24)
        self.f.word(0x03039e40, 1152)
        self.f.word(0x03039e44, 1)  # coherent completed host packet
        self.f.word(0x03039e48, 0)
        # File progress is beyond halfway, selecting native EOF notification243
        # rather than its decoder-error notification85 in the synthetic stream.
        self.f.word(0x030045ac, 0)
        self.f.word(0x03077668+16, 1000)
        self.f.word(0x03077668+32, 1000)
        self.f.word(self.syms['playback_active'], 1)
        self.call(self.syms['playback_speed_set'], 8)
        self.call(self.syms['playback_speed_launch'])

    def publish_completion(self):
        frames = self.blocks[0] if self.blocks else 0
        self.f.word(0x03039e20, self.source_origin + (self.source_frames+frames)*1000//48000)
        self.f.word(0x03039e40, frames)
        self.f.word(0x03039e4c, int(not self.blocks))
        self.f.word(0x03039e48, 0)
        self.f.word(0x03039e44, 1)
        self.pending_completion = False

    def hook(self, cpu, address, size, user):
        # Complete the next synthetic codec block at the first unmasked CPU
        # boundary, preserving the real ready/in-progress publication contract.
        if (getattr(self, 'pending_completion', False) and not self.codec_wait
                and not cpu.reg_read(UC_ARM_REG_PRIMASK)):
            self.publish_completion()
        if address == getattr(self, 'syms', {}).get('speed_process') and self.dsp_fault:
            cpu.reg_write(UC_ARM_REG_R0, 0xffffffff)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
            return
        if address == getattr(self, 'codec_entry', None):
            operation, buffer_ptr, count_ptr, fourth = (cpu.reg_read(r) for r in REGS)
            if operation == 14:
                self.seeks.append((buffer_ptr, count_ptr))
                self.source_origin = buffer_ptr
                self.source_frames = 0
                self.f.word(0x03039e44, 0)
                self.f.word(0x03039e48, 1)
                self.pending_completion = True
                cpu.reg_write(UC_ARM_REG_R0, 1)
                cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
                return
            self.assertEqual(operation, 10)
            if self.codec_wait or self.f.readword(0x03039e44) != 1:
                self.f.word(0x03039e48, 1)
                status = 2
            elif self.blocks:
                frames = self.blocks.pop(0)
                buffer = (0x03023174, 0x0302c174)[self.codec_calls % 2]
                pcm = struct.pack('<'+'hh'*frames, *([self.codec_value, -self.codec_value]*frames))
                if self.variable_pcm:
                    samples=[]
                    for frame in range(self.source_frames,self.source_frames+frames):
                        value=int(12000*math.sin(2*math.pi*220*frame/48000))
                        samples.extend((value,-value))
                    pcm=struct.pack('<'+'h'*len(samples),*samples)
                cpu.mem_write(buffer, pcm)
                self.f.word(buffer_ptr, buffer)
                self.f.word(count_ptr, frames)
                self.codec_calls += 1
                self.source_frames += frames
                self.f.word(0x03039e44, 0)
                self.f.word(0x03039e48, 1)
                self.pending_completion = True
                status = 1
            else:
                status = 0
            cpu.reg_write(UC_ARM_REG_R0, status)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
            return
        if address == 0x0306c1e4 and self.dma_failure:
            cpu.reg_write(UC_ARM_REG_R0,0xffffffff)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
            return
        if address == 0x0306b040:
            self.notifications.append(cpu.reg_read(UC_ARM_REG_R0))
        if address == 0x0305a128:
            # UART write used by stock EOF diagnostic, not audio processing.
            cpu.reg_write(UC_ARM_REG_R0, cpu.reg_read(UC_ARM_REG_R2))
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
            return
        stock.StockPcmTests.hook(self.f, cpu, address, size, user)

    def invalid_memory(self, cpu, access, address, size, value, user):
        self.bad_memory = (access, hex(address), size)
        return False

    def call(self, address, *args):
        self.f.returned = False
        for reg, value in zip(REGS, args):
            self.cpu.reg_write(reg, value)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x030fe000)
        if len(args) > 4:
            self.cpu.mem_write(0x030fe000, struct.pack('<'+'I'*(len(args)-4), *args[4:]))
        self.cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
        try:
            self.cpu.emu_start(address | 1, 0, count=2000000)
        except UcError as error:
            self.fail(f'{error}: PC={self.cpu.reg_read(UC_ARM_REG_PC):08x}, access={self.bad_memory}')
        self.assertTrue(self.f.returned, f'call did not return: {address:08x}')
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP), 0x030fe000)
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def pump(self):
        if self.codec_wait:
            self.f.word(0x03039e44, 0)
            self.f.word(0x03039e48, 1)
        self.call(0x03069542)

    def complete(self, index):
        callback = self.f.dma[index][1][1]
        self.call(callback)

    def assert_dma_samples(self, index):
        args, extra, pcm = self.f.dma[index]
        self.assertEqual(args[0], 5)
        self.assertEqual(args[2], 0x40030024)
        self.assertLessEqual(args[3], PACKET_FRAMES*2)
        samples = struct.unpack('<'+'i'*(len(pcm)//4), pcm)
        self.assertEqual(samples, (1000 << 16, -1000 << 16)*(len(samples)//2))
        self.assertEqual(extra, (0x03005b2c, 0x03072f5d))

    def test_variable_pcm_has_full_nonfinal_packets_and_one_eof_tail(self):
        for quarters in (5,6,7,8):
            with self.subTest(quarters=quarters):
                self.setUp();self.variable_pcm=True;self.blocks=[1152]*8
                self.call(self.syms['playback_speed_set'],quarters)
                self.call(self.syms['playback_speed_launch'])
                self.pump();self.pump();completed=0
                for _ in range(100):
                    if completed<len(self.f.dma):self.complete(completed);completed+=1
                    self.pump()
                    if 243 in self.notifications:break
                else:self.fail('variable PCM failed to drain')
                frames=[entry[0][3]//2 for entry in self.f.dma]
                self.assertTrue(all(n==PACKET_FRAMES for n in frames[:-1]),frames)
                self.assertLessEqual(frames[-1],PACKET_FRAMES)
                self.assertEqual(completed,len(frames))
                self.call(self.syms['playback_speed_position'],0x03045000)
                self.assertEqual(self.f.readword(0x03045000),192)
                # Compare the DMA sample stream with the same core run using
                # one source span, independently of adapter packet boundaries.
                samples=[]
                for frame in range(1152*8):
                    value=int(12000*math.sin(2*math.pi*220*frame/48000))
                    samples.extend((value,-value))
                self.cpu.mem_write(0x030b0000,struct.pack('<'+'h'*len(samples),*samples))
                self.assertEqual(self.call(self.syms['speed_init'],0x030c0000,48000,2,quarters),0)
                used=0;reference=[]
                for _ in range(100):
                    self.assertEqual(self.call(self.syms['speed_process'],0x030c0000,
                        0x030b0000+used*4,1152*8-used,1,0x030d0000,256,0x030d1000),0)
                    consumed,produced,done=struct.unpack('<III',self.cpu.mem_read(0x030d1000,12))
                    used+=consumed
                    reference.extend(struct.unpack('<'+'h'*(produced*2),self.cpu.mem_read(0x030d0000,produced*4)))
                    if done:break
                else:self.fail('reference core failed to drain')
                actual=[]
                for _,_,pcm in self.f.dma:
                    actual.extend(value>>16 for value in struct.unpack('<'+'i'*(len(pcm)//4),pcm))
                self.assertEqual(actual,reference)


    def test_two_slots_prepare_then_native_callback_hands_off_without_reuse(self):
        self.pump()
        self.assertEqual(len(self.f.dma), 1)
        self.assert_dma_samples(0)
        first = self.f.dma[0][0][1]
        first_bytes = bytes(self.cpu.mem_read(first, PACKET_BYTES))
        self.pump()
        self.assertEqual(len(self.f.dma), 1)
        second = self.f.readword(STATE+12)
        self.assertNotEqual(first, second)
        self.assertEqual(bytes(self.cpu.mem_read(first, PACKET_BYTES)), first_bytes)
        self.pump()
        self.assertEqual(len(self.f.dma), 1)
        self.assertEqual(bytes(self.cpu.mem_read(first, PACKET_BYTES)), first_bytes)
        self.complete(0)
        self.assertEqual(len(self.f.dma), 2)
        self.assertEqual(self.f.dma[1][0][1], second)
        self.assert_dma_samples(1)
        self.pump()
        self.assertEqual(self.f.readword(STATE+12), first)

    def test_eof_drains_native_slots_and_completion_wakes_final_pump(self):
        self.pump()
        self.pump()
        completed = 0
        for _ in range(100):
            if completed < len(self.f.dma):
                self.f.word(0xe000ed04, 0)
                self.complete(completed)
                completed += 1
                self.assertEqual(self.f.readword(0xe000ed04), 1 << 28)
            self.pump()
            if 243 in self.notifications:
                break
        else:
            self.fail('EOF failed to drain')
        self.assertIn(243, self.notifications)
        self.assertEqual(self.codec_calls, 4)
        self.assertEqual(completed, len(self.f.dma))
        self.assertGreater(len(self.f.dma), 2)
        for index in range(len(self.f.dma)):
            self.assert_dma_samples(index)
        frames = sum(item[0][3]//2 for item in self.f.dma)
        self.assertLessEqual(abs(frames - 4608//2), 739)
        self.assertEqual(self.call(self.syms['playback_speed_position'], 0x03045000), 1)
        self.assertEqual(self.f.readword(0x03045000), 96)

    def test_non_book_keeps_native_pcm_and_native_completion(self):
        self.f.word(self.syms['playback_active'], 0)
        self.blocks = [4]
        self.pump()
        self.assertEqual(len(self.f.dma), 1)
        args, extra, pcm = self.f.dma[0]
        self.assertEqual(args, (5, 0x03023174, 0x40030024, 8))
        self.assertEqual(extra, (0x03005b2c, 0x030693cb))
        self.assertEqual(struct.unpack('<8i', pcm), (1000 << 16, -1000 << 16)*4)
        self.assertEqual(self.call(self.syms['playback_speed_position'], 0x03045000), 0)

    def test_unsupported_book_prepares_native_block_while_dma_plays(self):
        self.f.word(0x03039e94,1)
        self.f.word(0x0303517c,self.codec_entry|1)
        self.pump()
        self.assertEqual(len(self.f.dma),1)
        self.assertEqual(self.f.dma[0][1][1],0x030693cb)
        current=self.f.dma[0][0][1]
        before=bytes(self.cpu.mem_read(current,1152*8))
        self.pump()
        self.assertEqual(self.codec_calls,2)
        self.assertEqual(len(self.f.dma),1)
        self.assertNotEqual(self.f.readword(STATE+12),current)
        self.assertEqual(bytes(self.cpu.mem_read(current,1152*8)),before)
        self.complete(0)
        self.assertEqual(len(self.f.dma),2)
        self.assertEqual(self.f.dma[1][1][1],0x030693cb)

    def test_seek_does_not_overwrite_inflight_pcm_or_use_old_completion_time(self):
        self.pump()
        self.pump()
        old_buffer = self.f.dma[0][0][1]
        before = bytes(self.cpu.mem_read(old_buffer, PACKET_BYTES))
        self.codec_value = 2000
        self.blocks = [1152] * 2
        self.f.word(0x03039e20, 10024)
        self.call(0x030834d8, 10000, 0)
        self.assertEqual(self.seeks, [(10000, 0)])
        self.pump()
        self.assertTrue(bytes(self.cpu.mem_read(old_buffer, PACKET_BYTES)) == before,
                        'seek reused PCM still owned by old output DMA')
        self.call(self.syms['playback_speed_position'], 0x03045000)
        position = self.f.readword(0x03045000)
        self.complete(0)
        self.call(self.syms['playback_speed_position'], 0x03045000)
        self.assertEqual(self.f.readword(0x03045000), position,
                         'old generation completion advanced new source time')

    def test_seek_drains_both_old_callbacks_then_new_source_to_eof(self):
        self.pump();self.pump()
        old_current=self.f.dma[0][0][1]
        old_prepared=self.f.readword(STATE+12)
        old_bytes={p:bytes(self.cpu.mem_read(p,PACKET_BYTES)) for p in (old_current,old_prepared)}
        self.blocks=[1152]*2;self.codec_value=2000
        self.call(0x030834d8,10000,0)
        self.pump()
        self.assertEqual(len(self.f.dma),1)
        self.complete(0)
        self.assertEqual(self.f.dma[1][0][1],old_prepared)
        self.pump()
        self.assertEqual(self.call(self.syms['playback_speed_position'],0x03045000),0)
        self.assertEqual(bytes(self.cpu.mem_read(old_prepared,PACKET_BYTES)),old_bytes[old_prepared])
        self.complete(1)
        self.assertEqual(self.call(self.syms['playback_speed_position'],0x03045000),0)
        self.pump()
        self.assertEqual(len(self.f.dma),3)
        self.assertEqual(self.call(self.syms['playback_speed_position'],0x03045000),1)
        self.assertEqual(self.f.readword(0x03045000),10000)
        completed=2;positions=[]
        for _ in range(100):
            if completed<len(self.f.dma):
                self.complete(completed);completed+=1
                self.call(self.syms['playback_speed_position'],0x03045000)
                positions.append(self.f.readword(0x03045000))
            self.pump()
            if 243 in self.notifications:break
        else:self.fail('seek generation failed to reach EOF')
        self.assertEqual(completed,len(self.f.dma))
        self.assertEqual(positions,sorted(positions))
        self.assertGreater(positions[0],10000)
        self.assertEqual(positions[-1],10048)
        for args,extra,pcm in self.f.dma[2:]:
            samples=struct.unpack('<'+'i'*(len(pcm)//4),pcm)
            self.assertEqual(samples,(2000<<16,-2000<<16)*(len(samples)//2))

    def test_nonpump_wait_restores_native_buffer_before_ignored_status_clear(self):
        self.pump()
        self.pump()
        current = self.f.dma[0][0][1]
        prepared = self.f.readword(STATE+12)
        snapshots = {p: bytes(self.cpu.mem_read(p, PACKET_BYTES)) for p in (current, prepared)}
        self.codec_wait = True
        self.f.word(0x03039e44, 0)
        self.f.word(0x03039e48, 1)
        self.assertEqual(self.call(0x030835c8, STATE+12, STATE+28), 2)
        native = self.f.readword(STATE+12)
        self.assertIn(native, (0x03023174, 0x0302c174))
        self.assertEqual(self.f.readword(STATE+28), 1152)
        self.assertEqual(self.f.readword(STATE+16), 1)  # prepared handoff canceled
        # Execute the native clear/conversion sequence even though capture waited.
        self.call(0x030579a8, native, 1152*4)
        self.call(0x03069484, native, STATE+28, 16)
        for pointer, before in snapshots.items():
            self.assertTrue(bytes(self.cpu.mem_read(pointer, PACKET_BYTES)) == before)
        self.complete(0)
        self.assertEqual(len(self.f.dma), 1)

    def test_nonpump_restart_releases_prepared_slot_after_native_pointer_replacement(self):
        self.pump();self.pump()
        current=self.f.dma[0][0][1]
        before=bytes(self.cpu.mem_read(current,PACKET_BYTES))
        # Native stop/resume can discard the prepared pointer and flag before
        # the wrapper sees the next non-pump capture.
        self.f.word(STATE+12,0x03023174);self.f.word(STATE+16,1)
        self.codec_wait=True;self.f.word(0x03039e44,0)
        self.assertEqual(self.call(0x030835c8,STATE+12,STATE+28),2)
        self.assertEqual(bytes(self.cpu.mem_read(current,PACKET_BYTES)),before)
        self.complete(0)
        self.codec_wait=False;self.publish_completion()
        self.pump()
        self.assertEqual(len(self.f.dma),2)

    def test_raw_preroll_guard_blocks_capture_until_native_completion(self):
        native = 0x03023174
        data = struct.pack('<8i', *([777 << 16, -777 << 16]*4))
        self.cpu.mem_write(native, data)
        self.f.word(STATE+16, 1)
        self.f.word(STATE+20, 1)
        self.call(0x03072f54, 5, native, 0x40030024, 8, 0x03005b2c, 0x030693cb)
        self.assertEqual(len(self.f.dma), 1)
        self.assertEqual(self.f.dma[0][1][1], 0x03072f5d)
        self.pump()
        self.assertEqual(self.codec_calls, 0)
        self.assertEqual(bytes(self.cpu.mem_read(native, len(data))), data)
        self.assertEqual(len(self.f.dma), 1)
        self.complete(0)
        self.pump()
        self.assertGreater(self.codec_calls, 0)
        self.assertEqual(len(self.f.dma), 2)

    def test_dma_failure_reaches_native_terminal_state_without_callback(self):
        self.dma_failure=True
        self.pump()
        self.assertEqual(self.f.dma,[])
        self.pump()
        self.assertIn(243,self.notifications)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(STATE+8,2))[0],4)
        self.assertEqual(self.f.readword(STATE+16),0)

    def test_prepared_dma_failure_after_callback_does_not_leave_busy_forever(self):
        self.pump();self.pump()
        self.dma_failure=True
        self.complete(0)
        self.pump()
        self.assertIn(243,self.notifications)
        self.assertEqual(len(self.f.dma),1)

    def test_nonzero_status_does_not_reexpand_current_or_prepared_dsp(self):
        self.pump();self.pump()
        pointers=(self.f.dma[0][0][1],self.f.readword(STATE+12))
        snapshots=[bytes(self.cpu.mem_read(p,PACKET_BYTES)) for p in pointers]
        for status in (1,2,3,4):
            self.cpu.mem_write(STATE+8,struct.pack('<H',status))
            self.pump()
            self.assertEqual(len(self.f.dma),1)
            self.assertEqual([bytes(self.cpu.mem_read(p,PACKET_BYTES)) for p in pointers],snapshots)

    def test_fault_drain_does_not_zero_current_pcm_or_post_early_eof(self):
        self.pump()
        current=self.f.dma[0][0][1]
        before=bytes(self.cpu.mem_read(current,PACKET_BYTES))
        self.dsp_fault=True
        self.pump()
        self.assertEqual(self.notifications,[])
        self.assertEqual(bytes(self.cpu.mem_read(current,PACKET_BYTES)),before)
        self.complete(0)
        self.pump()
        self.assertIn(243,self.notifications)

    def test_nonpump_capture_during_raw_dma_uses_other_native_buffer(self):
        native=0x03023174
        data=bytes([0x55])*9216
        self.cpu.mem_write(native,data)
        self.f.word(STATE+12,native);self.f.word(STATE+28,1152)
        self.f.word(STATE+16,1);self.f.word(STATE+20,1)
        self.call(0x03072f54,5,native,0x40030024,2304,0x03005b2c,0x030693cb)
        for _ in range(3):
            self.assertEqual(self.call(0x030835c8,STATE+12,STATE+28),2)
            other=self.f.readword(STATE+12)
            self.assertEqual(other,0x0302c174)
            self.call(0x030579a8,other,self.f.readword(STATE+28)*4)
            self.call(0x03069484,other,STATE+28,16)
            self.assertEqual(bytes(self.cpu.mem_read(native,len(data))),data)
        self.assertEqual(self.codec_calls,0)
        self.complete(0);self.pump()
        self.assertGreater(self.codec_calls,0)

    def test_raw_ignored_wait_submission_preserves_current_then_terminates(self):
        native=0x03023174
        data=bytes([0x55])*9216
        self.cpu.mem_write(native,data)
        self.f.word(STATE+12,native);self.f.word(STATE+28,1152)
        self.f.word(STATE+16,1);self.f.word(STATE+20,1)
        self.call(0x03072f54,5,native,0x40030024,2304,0x03005b2c,0x030693cb)
        self.assertEqual(self.call(0x030835c8,STATE+12,STATE+28),2)
        other=self.f.readword(STATE+12)
        self.call(0x030579a8,other,self.f.readword(STATE+28)*4)
        self.call(0x03069484,other,STATE+28,16)
        self.assertEqual(self.call(0x03072f54,5,other,0x40030024,
                                  self.f.readword(STATE+28)*2,0x03005b2c,0x030693cb),0xffffffff)
        self.assertEqual(len(self.f.dma),1)
        self.assertEqual(bytes(self.cpu.mem_read(native,len(data))),data)
        self.pump()
        self.assertEqual(self.notifications,[])
        self.assertEqual(self.codec_calls,0)
        self.complete(0)
        self.pump()
        self.assertEqual(len(self.f.dma),1)
        self.assertIn(243,self.notifications)
        self.assertEqual(struct.unpack('<H',self.cpu.mem_read(STATE+8,2))[0],4)

    def test_codec_wait_does_not_convert_or_submit_a_stale_slot(self):
        self.codec_wait = True
        self.pump()
        self.assertEqual(self.f.dma, [])
        self.assertEqual(self.codec_calls, 0)


if __name__ == '__main__':
    unittest.main()
