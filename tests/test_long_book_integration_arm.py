"""Long-book autosave eligibility and shared menu/launch path ownership."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR
import test_live_speed_arm as live
import test_playback_session_arm as session


class LongBookIntegrationTests(unittest.TestCase):
    def test_autosave_poll_only_enters_writer_for_ready_playing_book(self):
        for condition in ('playing', 'paused', 'music', 'folder', 'scratch', 'seeking', 'relaunch', 'invalid'):
            with self.subTest(condition=condition):
                t = live.LiveSpeedTests(); t.setUp(); t.launch()
                f, cpu = t.f, t.cpu
                calls = []
                def hook(c, address, size, user):
                    if address == f.syms['book_autosave']:
                        calls.append('save')
                    elif address == 0x0306b05c:
                        c.reg_write(UC_ARM_REG_R0, 123)
                    else:
                        return
                    c.reg_write(UC_ARM_REG_PC, c.reg_read(UC_ARM_REG_LR))
                cpu.hook_add(UC_HOOK_CODE, hook)
                if condition == 'paused': t.half(0x0300d81a, 3)
                elif condition in ('music', 'folder'):
                    t.a.put(f.syms['playback_active'], 0 if condition == 'music' else 2)
                elif condition == 'scratch': t.a.put(f.syms['playback_scratch_busy'], 1)
                elif condition == 'seeking':
                    t.a.dma_result = 4; t.a.submit(0x03023174, 128); t.a.put(0x600003a0, 1 << 4)
                    self.assertEqual(f.call('playback_seek_request', 1), 1)
                    t.half(0x0300d81a, 0)  # Isolate transition guard from pause guard.
                elif condition == 'relaunch':
                    self.assertEqual(f.call('playback_rate_request', 8), 2)
                    t.half(0x0300d81a, 0)
                elif condition == 'invalid':
                    f.call('playback_init')
                    t.a.put(f.syms['playback_active'], 1)
                self.assertEqual(f.call('playback_bookmark_poll', 57), 123)
                self.assertEqual(calls, ['save'] if condition == 'playing' else [])

    def test_browser_rejection_preserves_shared_menu_path(self):
        for condition in ('scratch', 'failed_path', 'different_path', 'matching_path'):
            with self.subTest(condition=condition):
                t = session.SessionTests(); t.setUp(); f, cpu = t.f, t.cpu
                path = '/list.m3u' if condition == 'matching_path' else '/other.m3u'
                before = (path + '\0').encode('utf-16le') + bytes(512 - (len(path) + 1) * 2)
                pointer = f.syms['playback_launch_buffer']; cpu.mem_write(pointer, before)
                f.call('playback_launch_override', 1, 3600000, 123)
                if condition == 'scratch':
                    cpu.mem_write(f.syms['playback_scratch_busy'], struct.pack('<I', 1))
                elif condition == 'failed_path':
                    from unicorn.arm_const import UC_ARM_REG_R1
                    def fail(c, address, size, user):
                        if address == f.syms['playback_browser_path']:
                            c.mem_write(c.reg_read(UC_ARM_REG_R1), b'\0\0')
                            c.reg_write(UC_ARM_REG_R0, 0)
                            c.reg_write(UC_ARM_REG_PC, c.reg_read(UC_ARM_REG_LR))
                    cpu.hook_add(UC_HOOK_CODE, fail)
                result = f.call('playback_browser_select', 0x20003000)
                self.assertEqual(bool(result), condition == 'matching_path')
                self.assertEqual(bytes(cpu.mem_read(pointer, len(before))), before)
                if condition != 'scratch':
                    self.assertEqual(bytes(cpu.mem_read(f.syms['playback_scratch_busy'], 4)), bytes(4))

    def test_shared_path_can_launch_itself(self):
        t = session.SessionTests(); t.setUp(); f, cpu = t.f, t.cpu
        pointer = f.syms['playback_launch_buffer']; data = '/list.m3u\0'.encode('utf-16le')
        cpu.mem_write(pointer, data)
        self.assertEqual(f.call('playback_launch_path', pointer, 1, 3600000, 123), 1)
        self.assertEqual(bytes(cpu.mem_read(pointer, len(data))), data)

    def test_ordinary_selection_publishes_new_path(self):
        t = session.SessionTests(); t.setUp(); f, cpu = t.f, t.cpu
        pointer = f.syms['playback_launch_buffer']
        cpu.mem_write(pointer, '/previous.m3u\0'.encode('utf-16le'))
        self.assertTrue(f.call('playback_browser_select', 0x20003000))
        self.assertEqual(bytes(cpu.mem_read(pointer, 20)), '/list.m3u\0'.encode('utf-16le'))

    def test_menu_open_guards_preserve_active_and_returning_path(self):
        import test_book_menu_arm as menu
        for returning in (False, True):
            with self.subTest(returning=returning):
                t = menu.BookMenuTests(); t.setUp(); t.open()
                if returning:
                    self.assertEqual(t.event(menu.SELECT), 2)
                pointer = t.f.syms['playback_launch_buffer']
                before = bytes(t.cpu.mem_read(pointer, 512))
                self.assertEqual(t.call('book_menu_open_selected'), 0)
                self.assertEqual(t.call('book_menu_continue_last'), 0)
                self.assertEqual(bytes(t.cpu.mem_read(pointer, 512)), before)
