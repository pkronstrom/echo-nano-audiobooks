"""Book overlay uses persistent text and preserves native controls/music."""
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
import test_playback_runtime_arm as runtime

class BookScreenTests(unittest.TestCase):
    def setUp(self):
        self.f=runtime.PlaybackRuntimeTests();self.f.setUp();self.cpu=self.f.cpu
        image=runtime.Image((runtime.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        for index in (0,27):
            m=image.modules[index]
            for kind in ('code','data'):
                off=image.l2f(m[kind+'_load']);self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.rows=[];self.scroll=[];self.dirty={73,482};self.real_text=False;self.native_events=False
        self.cpu.hook_add(UC_HOOK_CODE,self.hook)
        self.cpu.mem_write(self.f.syms['playback_active'],struct.pack('<I',1))
        self.cpu.mem_write(0x0300e6e3,b'\0')
        self.cpu.mem_write(self.f.call('playback_book_path'),'/Books/Soulcraft/BOOK.M3U\0'.encode('utf-16le'))
        self.cpu.mem_write(0x03039928,'The chapter title\0'.encode('utf-16le'))
        self.cpu.mem_write(0x03039a26,'Author should be hidden\0'.encode('utf-16le'))
        self.cpu.mem_write(0x03039798,'Chapter file.mp3\0'.encode('utf-16le'))
    def text(self,address):
        out=[]
        for i in range(256):
            c=struct.unpack('<H',self.cpu.mem_read(address+i*2,2))[0]
            if not c:break
            out.append(c)
        return struct.pack('<'+'H'*len(out),*out).decode('utf-16le')
    def hook(self,cpu,address,size,user):
        if address==0x0306b05c and not self.native_events:cpu.reg_write(UC_ARM_REG_R0,int(cpu.reg_read(UC_ARM_REG_R0) in self.dirty))
        elif address==0x03051574:cpu.reg_write(UC_ARM_REG_R0,1)
        elif address==0x03052b08:
            ptr=cpu.reg_read(UC_ARM_REG_R1)
            self.rows.append((struct.unpack('<4H',cpu.mem_read(cpu.reg_read(UC_ARM_REG_R0),8)),self.text(ptr),ptr))
            if self.real_text:return
        elif address==0x03052fe4:
            self.scroll.append(cpu.reg_read(UC_ARM_REG_R0))
            if self.real_text:return
        elif self.real_text and address==0x03064a90:cpu.reg_write(UC_ARM_REG_R0,len(self.text(cpu.reg_read(UC_ARM_REG_R3)))*6)
        elif self.real_text and address in (0x030527b0,0x03059090):cpu.reg_write(UC_ARM_REG_R0,0)
        else:return
        cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def test_full_rows_icons_and_bottom_controls(self):
        before=bytes([0xa5])*640;self.cpu.mem_write(0x03007d88,before)
        self.cpu.mem_write(0x0300d6e0,b'\x01\0')
        self.assertEqual(self.f.call(0x0307b1f4),1)
        self.assertEqual([(r,t) for r,t,_ in self.rows],[((12,0,127,11),'Soulcraft'),((0,12,86,23),'The chapter title')])
        self.assertEqual(self.scroll,[0x03005edc,0x03005f0c])
        self.assertEqual(self.text(self.rows[0][2]),'Soulcraft')
        self.assertEqual(bytes(self.cpu.mem_read(0x0300d6e0,2)),b'\x01\0')
        after=bytes(self.cpu.mem_read(0x03007d88,640))
        for x in range(128):
            self.assertEqual(after[x*5+4],before[x*5+4])
            self.assertEqual(after[x*5+3],0 if 87<=x<115 else before[x*5+3])
        self.assertTrue(any(after[:60:5]))
        self.assertEqual(after[2:60:5],bytes(12))
    def test_incremental_overlay_does_not_restart_marquees(self):
        self.real_text=True
        for record,buffer in ((0x03005edc,0x20004000),(0x03005f0c,0x20005000)):
            self.cpu.mem_write(record,bytes(48));self.cpu.mem_write(record+16,struct.pack('<I',buffer))
        self.f.call('playback_book_screen');self.rows=[];self.scroll=[]
        self.dirty=set();self.f.call('playback_book_screen')
        self.assertEqual(self.rows,[]);self.assertEqual(self.scroll,[])
    def test_missing_chapter_tag_uses_filename(self):
        self.cpu.mem_write(0x03039928,b'\0\0');self.f.call('playback_book_screen')
        self.assertEqual(self.rows[1][1],'Chapter file.mp3')
    def test_music_folder_invalid_payload_and_other_display_are_unchanged(self):
        for active,header,display in ((0,b'ENP2',0),(2,b'ENP2',0),(1,b'BAD!',0),(1,b'ENP2',1)):
            with self.subTest(active=active,header=header,display=display):
                self.rows=[];self.scroll=[]
                self.cpu.mem_write(self.f.syms['playback_active'],struct.pack('<I',active))
                self.cpu.mem_write(0x03092400,header);self.cpu.mem_write(0x0300e6e3,bytes([display]))
                before=bytes([0xa5])*640;self.cpu.mem_write(0x03007d88,before)
                self.f.call(0x0307b1f4)
                self.assertEqual(bytes(self.cpu.mem_read(0x03007d88,640)),before)
                self.assertEqual(self.rows,[])
    def test_title_truncation_preserves_utf16(self):
        path='/Books/'+'a'*62+'😀'+'/BOOK.M3U\0'
        self.cpu.mem_write(self.f.call('playback_book_path'),path.encode('utf-16le'))
        self.f.call('playback_book_screen');self.assertEqual(self.rows[0][1],'a'*62)

    def test_real_native_text_and_marquee_keep_book_sources_across_incremental_paint(self):
        self.real_text=True
        self.cpu.mem_write(self.f.call('playback_book_path'),('/Books/'+'Long book title '*3+'/BOOK.M3U\0').encode('utf-16le'))
        self.cpu.mem_write(0x03039928,('Long chapter title '*3+'\0').encode('utf-16le'))
        for record,buffer in ((0x03005edc,0x20004000),(0x03005f0c,0x20005000)):
            self.cpu.mem_write(record,bytes(48));self.cpu.mem_write(record+16,struct.pack('<I',buffer))
        minimum=[0x2000f000]
        def stack(cpu,address,size,user):minimum[0]=min(minimum[0],cpu.reg_read(UC_ARM_REG_SP))
        token=self.cpu.hook_add(UC_HOOK_CODE,stack)
        self.f.call('playback_book_screen')
        self.cpu.hook_del(token)
        pointers=[struct.unpack('<I',self.cpu.mem_read(r+12,4))[0] for r in (0x03005edc,0x03005f0c)]
        self.assertTrue(self.text(pointers[0]).startswith('Long book title'))
        self.assertTrue(self.text(pointers[1]).startswith('Long chapter title'))
        self.assertGreater(minimum[0],0x2000f000-4096)
        self.dirty=set();self.rows=[]
        self.cpu.mem_write(0x0300d144,struct.pack('<I',10000))
        self.f.call(0x0307ad14);self.f.call(0x0307adc8);self.f.call('playback_book_screen')
        self.assertEqual(self.rows,[])
        self.assertEqual(pointers,[struct.unpack('<I',self.cpu.mem_read(r+12,4))[0] for r in (0x03005edc,0x03005f0c)])

    def test_native_consuming_dirty_flags_do_not_leave_author_row(self):
        self.real_text=True;self.native_events=True
        for record,buffer in ((0x03005edc,0x20004000),(0x03005f0c,0x20005000)):
            self.cpu.mem_write(record,bytes(48));self.cpu.mem_write(record+16,struct.pack('<I',buffer))
        for event in (73,482):self.f.call(0x0306b040,event)
        self.f.call(0x0307ad14);self.f.call(0x0307adc8)
        self.rows=[];self.f.call('playback_book_screen')
        self.assertEqual([text for _,text,_ in self.rows],['Soulcraft','The chapter title'])
        self.assertEqual(self.rows[1][0],(0,12,86,23))

    def test_actual_native_heart_is_cleared_and_battery_preserved(self):
        image=runtime.Image((runtime.ROOT/'NANOV170.IMG').read_bytes());base=image.sections[-1]['offset']
        before=bytearray(640)
        for resource,x in ((80,87),(159,95),(122,104),(66,115)):
            w,h,_,_,n,o=struct.unpack_from('<4H2I',image.d,base+32+resource*16)
            pixels=struct.unpack_from('<'+'H'*(w*h),image.d,base+o)
            for y in range(h):
                for dx in range(w):
                    if pixels[y*w+dx]==0:before[(x+dx)*5+(y+25)//8]|=1<<((y+25)%8)
        self.cpu.mem_write(0x03007d88,bytes(before));self.f.call('playback_book_screen')
        after=bytes(self.cpu.mem_read(0x03007d88,640))
        self.assertEqual(after[87*5+3:115*5:5],bytes(28))
        self.assertEqual(after[115*5+3::5],bytes(before[115*5+3::5]))

    def test_blank_native_artist_repaint_reclaims_static_and_scrolling_chapter(self):
        for chapter in ('Short chapter','Long chapter title '*3):
            with self.subTest(chapter=chapter):
                self.setUp();self.real_text=True;self.native_events=True
                self.cpu.mem_write(0x03039928,(chapter+'\0').encode('utf-16le'))
                self.cpu.mem_write(0x03039a26,b'\0\0')
                for record,buffer in ((0x03005edc,0x20004000),(0x03005f0c,0x20005000)):
                    self.cpu.mem_write(record,bytes(48));self.cpu.mem_write(record+16,struct.pack('<I',buffer))
                self.f.call('playback_book_screen');self.rows=[]
                # Mock the blank resource raster only; native dirty reader,
                # artist branch, width guard and marquee state machine run.
                def blank(cpu,address,size,user):
                    if address==0x03052c66:cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
                token=self.cpu.hook_add(UC_HOOK_CODE,blank)
                self.f.call(0x0306b040,482);self.f.call(0x0307adc8)
                self.f.call('playback_book_screen');self.cpu.hook_del(token)
                self.assertEqual([text for _,text,_ in self.rows],[chapter])
                self.rows=[];self.f.call(0x0307adc8);self.f.call('playback_book_screen')
                self.assertEqual(self.rows,[])
