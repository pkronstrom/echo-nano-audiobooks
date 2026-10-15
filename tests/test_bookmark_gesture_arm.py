"""Guard the resident favorite route across books, music and refresh."""
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
import test_bookmark_session_arm as base
from playback_layout import RAM_START

class BookmarkGestureTests(base.BookmarkSessionTests):
    def setUp(self):
        super().setUp();self.favorite_queries=0;self.consumed=False
        self.message_result=0;self.message_arguments=[]
        self.cpu.hook_add(UC_HOOK_CODE,self.gesture_hook)

    def gesture_hook(self,cpu,address,size,user):
        if address==0x0306b05c:
            self.message_arguments.append(cpu.reg_read(UC_ARM_REG_R0))
            cpu.reg_write(UC_ARM_REG_R0,self.message_result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        elif address==0x030686e0:
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R0),0,"stock favorite query mode must be preserved")
            self.favorite_queries+=1
            cpu.reg_write(UC_ARM_REG_R0,1)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        elif address in (0x030638b0,0x030638f2):
            cpu.reg_write(UC_ARM_REG_PC,0x20000000)
        elif address==0x030638ea:
            self.consumed=True;cpu.reg_write(UC_ARM_REG_PC,0x20000000)

    def invoke(self):
        # Fixed resident stub is installed by image integration, not loaded from
        # a potentially absent player overlay.
        self.assertEqual(bytes(self.cpu.mem_read(0x03052d68,2)),b'\x10\xb5')
        return self.f.call(0x030638aa)

    def test_bookmark_gesture_consumes_favorite_route_and_saves_position(self):
        self.invoke()
        self.assertTrue(self.consumed);self.assertEqual(self.favorite_queries,0)
        self.assertEqual(self.writes,[],"UI must only queue the snapshot")
        self.assertEqual(self.f.call('playback_bookmark_poll',439),0)
        self.assertEqual(self.f.call('bookmarks_get',0,0x20002400),1)
        self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(1,1234567))

    def test_music_gesture_retains_stock_favorite_query(self):
        self.f.call('playback_begin',0x20001000)
        self.assertEqual(self.invoke(),1)
        self.assertFalse(self.consumed);self.assertEqual(self.favorite_queries,1)
        self.assertEqual(self.writes,[])

    def test_missing_payload_does_not_branch_into_overwritten_code(self):
        self.cpu.mem_write(RAM_START,b'CFW!')
        self.assertEqual(self.invoke(),1)
        self.assertFalse(self.consumed);self.assertEqual(self.favorite_queries,1)
        self.assertEqual(self.writes,[])

    def test_alternate_native_key_mode_also_saves_bookmark(self):
        self.f.call(0x030638ec)
        self.assertTrue(self.consumed);self.assertEqual(self.favorite_queries,0)
        self.assertEqual(self.writes,[])
        self.f.call('playback_bookmark_poll',439)
        self.assertEqual(len(self.writes),1)

    def test_disabled_draw_diagnostic_still_returns_without_drawing(self):
        before=bytes(self.cpu.mem_read(0x03007d88,640))
        self.f.call(0x03052c8a,128,32,1)
        self.assertEqual(bytes(self.cpu.mem_read(0x03007d88,640)),before)
        self.assertEqual(self.writes,[])

    def test_queued_mark_keeps_pressed_position_after_chapter_advance(self):
        self.invoke()
        self.assertEqual(self.writes,[])
        self.f.call('playback_advance',0x0300d85c,1)
        self.cpu.mem_write(0x03023090+4,struct.pack('<I',9000))
        self.f.call('playback_bookmark_poll',439)
        self.f.call('bookmarks_get',0,0x20002400)
        self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(1,1234567))

    def test_music_transition_cancels_queued_bookmark(self):
        self.invoke();self.assertEqual(self.writes,[])
        self.f.call('playback_begin',0x20001000)
        self.f.call('playback_bookmark_poll',439)
        self.assertEqual(self.writes,[])

    def test_second_press_preserves_first_pending_snapshot(self):
        self.assertEqual(self.f.call('playback_request_bookmark'),0)
        self.cpu.mem_write(0x03023090+4,struct.pack('<I',9000))
        self.assertEqual(self.f.call('playback_request_bookmark'),0xffffffff)
        self.f.call('playback_bookmark_poll',439)
        self.f.call('bookmarks_get',0,0x20002400)
        self.assertEqual(struct.unpack('<II',self.cpu.mem_read(0x20002400,8)),(1,1234567))
        self.f.call('playback_bookmark_poll',439)
        self.assertEqual(len(self.writes),1)

    def test_patched_service_call_preserves_message_argument_and_result(self):
        self.message_result=1
        def stop(cpu,address,size,user):
            if address==0x03082d50:cpu.reg_write(UC_ARM_REG_PC,0x20000000)
        self.cpu.hook_add(UC_HOOK_CODE,stop)
        self.assertEqual(self.f.call(0x03082d48),1)
        self.assertEqual(self.message_arguments,[439])

    def test_parser_busy_defers_pending_write_without_losing_snapshot(self):
        self.invoke()
        busy=self.f.syms['playback_scratch_busy']
        self.cpu.mem_write(busy,struct.pack('<I',1))
        self.f.call('playback_bookmark_poll',439)
        self.assertEqual(self.writes,[])
        self.cpu.mem_write(busy,struct.pack('<I',0))
        self.f.call('playback_bookmark_poll',439)
        self.assertEqual(len(self.writes),1)

    def test_missing_payload_service_poll_uses_native_fallback(self):
        self.cpu.mem_write(RAM_START,b'CFW!')
        self.test_patched_service_call_preserves_message_argument_and_result()
        self.assertEqual(self.writes,[])

    def test_late_publication_from_old_session_is_discarded(self):
        self.invoke()
        self.f.call('playback_cancel_bookmark')
        # Model the interrupted UI publishing its old snapshot after reset.
        import subprocess
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        nm=root/'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin/arm-none-eabi-nm'
        symbols=subprocess.check_output([str(nm),str(root/'out/playback/playback.elf')],text=True)
        address=next(int(line.split()[0],16) for line in symbols.splitlines() if line.endswith(' bookmark_pending'))
        self.cpu.mem_write(address,struct.pack('<I',1))
        self.f.call('playback_bookmark_poll',439)
        self.assertEqual(self.writes,[])
