"""Guarded adapter + actual stock filesystem, only sector I/O/IRQ substituted."""
from pathlib import Path
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.native_file_creation.disk_harness import NativeDisk


class GuardedCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = dict(os.environ)
        env['PATH'] = str(ROOT / 'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin') + os.pathsep + env['PATH']
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            def run(args):
                return subprocess.check_output(args, cwd=ROOT, env=env, stderr=subprocess.STDOUT)
            run(['arm-none-eabi-gcc', '-mthumb', '-mcpu=cortex-m3', '-Os', '-ffreestanding', '-fno-builtin', '-Wall', '-Wextra', '-Werror', '-c', 'experiments/native_file_creation/guarded_create.c', '-o', str(p/'guard.o')])
            run(['arm-none-eabi-ld', '-Ttext=0x030a0000', '-e', 'guarded_create_empty', str(p/'guard.o'), '-o', str(p/'guard.elf')])
            run(['arm-none-eabi-objcopy', '-O', 'binary', str(p/'guard.elf'), str(p/'guard.bin')])
            cls.code = (p/'guard.bin').read_bytes()
            cls.symbols = {line.split()[2]:int(line.split()[0], 16) for line in run(['arm-none-eabi-nm', str(p/'guard.elf')]).decode().splitlines() if len(line.split()) == 3}

    def prepare(self, filesystem,sectors_per_cluster=1,clusters=64):
        disk = NativeDisk(filesystem,sectors_per_cluster,clusters)
        if filesystem=='exfat':
            bitmap=bytearray(32);bitmap[0]=0x81
            struct.pack_into('<I',bitmap,20,2);struct.pack_into('<I',bitmap,24,(clusters+7)//8)
            disk.set_entry(0,bitmap)
            # Test book parent is separate from the genuine mounted root.
            disk.ROOT_CLUSTER=max(10,disk.ROOT_CLUSTER+1)
            disk.set_fat(disk.ROOT_CLUSTER,0x0fffffff)
            bit=disk.ROOT_CLUSTER-2
            disk.sectors[disk.DATA_LBA*512+bit//8] |= 1<<(bit%8)
        disk.cpu.mem_write(0x030a0000, self.code)
        self.parent = struct.pack('<III', disk.ROOT_CLUSTER, disk.SPC*512, 0) + b'\x01' + bytes(29)
        disk.cpu.mem_write(0x20008000, self.parent)
        disk.cpu.mem_write(0x20009000, b'BOOK.BMK\0')
        disk.cpu.mem_write(0x03077664, b'KEEP')
        disk.cpu.mem_write(0x03078a5c, bytes(range(42)))
        return disk

    def invoke(self, disk, device=None, fs=None, event_bytes=1024):
        return disk.call(self.symbols['guarded_create_empty'], 0x20008000, 0x20009000,
                         disk.DEV if device is None else device,
                         (3 if disk.filesystem == 'exfat' else 2) if fs is None else fs, event_bytes)

    def reserve(self,disk,length=1024):
        disk.cpu.mem_write(0x20007000,bytes(8))
        result=disk.call(self.symbols['guarded_reserve_native'],disk.DEV,
                        3 if disk.filesystem=='exfat' else 2,length,0x20007000)
        return result,struct.unpack('<II',disk.cpu.mem_read(0x20007000,8))

    def begin(self,disk,total):
        disk.cpu.mem_write(0x2000a000,bytes(128))
        return disk.call(self.symbols['guarded_writer_begin'],0x2000a000,0x20008000,
                         0x20009000,disk.DEV,3 if disk.filesystem=='exfat' else 2,total)

    def packet(self,disk,data):
        disk.cpu.mem_write(0x2000b000,data)
        return disk.call(self.symbols['guarded_writer_packet'],0x2000a000,0x2000b000,len(data))

    def finish(self,disk):
        return disk.call(self.symbols['guarded_writer_finish'],0x2000a000)

    def completed_tmp(self,filesystem):
        disk=self.prepare(filesystem);disk.cpu.mem_write(0x20009000,b'BOOK.TMP\0')
        self.assertEqual(self.begin(disk,513),0)
        self.assertEqual(self.packet(disk,b'X'*512),512)
        self.assertEqual(self.packet(disk,b'Z'),1)
        self.assertEqual(self.finish(disk),0)
        return disk

    def publish(self,disk):
        return disk.call(self.symbols['guarded_writer_publish'],0x2000a000)

    def test_closed_tmp_publication_uses_native_same_length_entry_writer(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.completed_tmp(filesystem);before=bytes(disk.sectors)
                calls=len(disk.native_calls);writes=len(disk.sector_writes)
                self.assertEqual(self.publish(disk),0)
                newcalls=disk.native_calls[calls:]
                self.assertIn(0x0305eba0 if filesystem=='fat' else 0x0305ec52,newcalls)
                self.assertEqual(len(disk.sector_writes)-writes,1)
                root=(disk.DATA_LBA+disk.ROOT_CLUSTER-2)*512
                self.assertEqual(disk.sectors[:root],before[:root])
                self.assertEqual(disk.sectors[root+512:],before[root+512:])
                if filesystem=='fat':self.assertEqual(disk.entry()[:11],b'BOOK    M3U')
                else:self.assertEqual(disk.entry(2)[2:18],b'BOOK.M3U'.decode().encode('utf-16le'))
                writes=len(disk.sector_writes)
                self.assertLess(self.publish(disk),0)
                self.assertEqual(len(disk.sector_writes),writes)

    def all_content(self,disk):
        if self.begin(disk,513):return -1
        if self.packet(disk,b'X'*512)!=512:return -1
        if self.packet(disk,b'Z')!=1:return -1
        return self.finish(disk)

    def test_every_stream_read_and_write_failure_preserves_neighbor_entry(self):
        for filesystem in ('fat','exfat'):
            good=self.prepare(filesystem);self.assertEqual(self.all_content(good),0)
            for kind,count in (('read',len(good.sector_reads)),('write',len(good.sector_writes))):
                for fault in range(1,count+1):
                    with self.subTest(filesystem=filesystem,kind=kind,fault=fault):
                        disk=self.prepare(filesystem)
                        sentinel=b'\x83'+bytes(range(31)) if filesystem=='exfat' else b'PRESERVETXT\x20'+bytes(20)
                        disk.set_entry(8,sentinel)
                        setattr(disk,'fail_'+kind+'_number',fault)
                        self.assertLess(self.all_content(disk),0)
                        self.assertEqual(disk.entry(8),sentinel)
                        self.assertEqual(disk.cpu.mem_read(0x03077668,1),b'\0')
                        self.assertEqual(disk.cpu.mem_read(0x03076914,1),b'\0')

    def test_publication_rejects_collision_changed_content_and_unfinished_source(self):
        for filesystem in ('fat','exfat'):
            for failure in ('collision','content','unfinished'):
                with self.subTest(filesystem=filesystem,failure=failure):
                    disk=self.completed_tmp(filesystem)
                    if failure=='collision':
                        if filesystem=='fat':disk.set_entry(8,b'BOOK    M3U\x10'+bytes(20))
                        else:
                            disk.set_entry(8,b'\x85\x02\0\0\x10'+bytes(27))
                            disk.set_entry(9,b'\xc0\x01\0\x08'+bytes(28))
                            disk.set_entry(10,b'\xc1\0'+b'BOOK.M3U'.decode().encode('utf-16le')+bytes(14))
                    elif failure=='content':
                        first=int.from_bytes(disk.cpu.mem_read(0x2000a000+8,4),'little')
                        disk.sectors[(disk.DATA_LBA+first-2)*512]^=1
                    else:disk.cpu.mem_write(0x2000a000+52,bytes(4)) # verified
                    before=bytes(disk.sectors);writes=len(disk.sector_writes)
                    self.assertLess(self.publish(disk),0)
                    self.assertEqual(len(disk.sector_writes),writes)
                    self.assertEqual(bytes(disk.sectors),before)

    def test_every_publication_io_failure_preserves_other_sectors(self):
        for filesystem in ('fat','exfat'):
            good=self.completed_tmp(filesystem);reads=len(good.sector_reads);writes=len(good.sector_writes)
            self.assertEqual(self.publish(good),0)
            added_reads=len(good.sector_reads)-reads
            for kind,count in (('read',added_reads),('write',1)):
                for fault in range(1,count+1):
                    with self.subTest(filesystem=filesystem,kind=kind,fault=fault):
                        disk=self.completed_tmp(filesystem);before=bytes(disk.sectors)
                        setattr(disk,'fail_'+kind+'_number',len(disk.sector_reads if kind=='read' else disk.sector_writes)+fault)
                        self.assertLess(self.publish(disk),0)
                        root=(disk.DATA_LBA+disk.ROOT_CLUSTER-2)*512
                        self.assertEqual(disk.sectors[:root],before[:root])
                        self.assertEqual(disk.sectors[root+512:],before[root+512:])

    def test_packets_never_call_native_growth_allocators(self):
        for filesystem in ('fat','exfat'):
            disk=self.prepare(filesystem);self.assertEqual(self.begin(disk,1024),0)
            calls=len(disk.native_calls)
            self.assertEqual(self.packet(disk,b'X'*512),512)
            self.assertEqual(self.packet(disk,b'Z'*512),512)
            self.assertEqual(self.finish(disk),0)
            self.assertNotIn(0x0305e912,disk.native_calls[calls:])
            self.assertNotIn(0x0305e9c2,disk.native_calls[calls:])

    def test_98k_stream_and_publication_on_128k_exfat_cluster(self):
        disk=self.prepare('exfat',256);disk.cpu.mem_write(0x20009000,b'BOOK.TMP\0')
        length=98305
        self.assertEqual(self.begin(disk,length),0)
        for offset in range(0,length,512):
            chunk=bytes([(offset//512)%251])*min(512,length-offset)
            self.assertEqual(self.packet(disk,chunk),len(chunk))
        self.assertEqual(self.finish(disk),0)
        self.assertEqual(self.publish(disk),0)
        self.assertEqual(int.from_bytes(disk.entry(1)[24:28],'little'),length)

    def test_packet_bounds_and_changed_fcb_refuse_before_data_writes(self):
        for filesystem in ('fat','exfat'):
            for failure in ('short','oversize','fcb','device'):
                with self.subTest(filesystem=filesystem,failure=failure):
                    disk=self.prepare(filesystem);self.assertEqual(self.begin(disk,1024),0)
                    data=b'X'*512
                    if failure=='short':data=b'X'
                    elif failure=='oversize':data=b'X'*513
                    elif failure=='fcb':disk._word(0x03077668+20,50)
                    else:disk._word(0x03076b2c,disk.DEV+1)
                    writes=len(disk.sector_writes);before=bytes(disk.sectors)
                    self.assertLess(self.packet(disk,data),0)
                    self.assertEqual(len(disk.sector_writes),writes)
                    self.assertEqual(bytes(disk.sectors),before)

    def test_abort_preserves_foreign_fcb_after_device_or_filesystem_change(self):
        for filesystem in ('fat','exfat'):
            for changed in ('device','filesystem'):
                for route in ('direct','packet'):
                    with self.subTest(filesystem=filesystem,changed=changed,route=route):
                        disk=self.prepare(filesystem);self.assertEqual(self.begin(disk,512),0)
                        foreign=bytes(disk.cpu.mem_read(0x03077668,0x27e))
                        if changed=='device':disk._word(0x03076b2c,disk.DEV+1)
                        else:disk.cpu.mem_write(0x03076b24,bytes([2 if filesystem=='exfat' else 3]))
                        writes=len(disk.sector_writes)
                        if route=='direct':disk.call(self.symbols['guarded_writer_abort'],0x2000a000)
                        else:self.assertLess(self.packet(disk,b'X'*512),0)
                        self.assertEqual(bytes(disk.cpu.mem_read(0x03077668,0x27e)),foreign)
                        self.assertEqual(len(disk.sector_writes),writes)
                        self.assertEqual(disk.cpu.mem_read(0x2000a000+36,4),b'\xff'*4)

    def test_abort_takes_own_nestable_filesystem_lock(self):
        for route in ('direct','packet'):
            with self.subTest(route=route):
                disk=self.prepare('fat');self.assertEqual(self.begin(disk,512),0)
                events=[]
                disk.cpu.hook_add(UC_HOOK_CODE,lambda c,a,n,u:events.append(a) if a in (0x0306a40e,0x0306a466) else None)
                if route=='direct':
                    disk.call(self.symbols['guarded_writer_abort'],0x2000a000)
                    self.assertEqual(events,[0x0306a40e,0x0306a466])
                    self.assertEqual(disk.cpu.mem_read(0x03077668,1),b'\0')
                else:
                    disk._word(0x03076b2c,disk.DEV+1)
                    self.assertLess(self.packet(disk,b'X'*512),0)
                    self.assertEqual(events,[0x0306a40e,0x0306a40e,0x0306a466,0x0306a466])

    def test_streaming_preallocated_native_overwrite_closes_and_cold_verifies(self):
        for filesystem in ('fat','exfat'):
            for length in (31,512,1024,1025):
                with self.subTest(filesystem=filesystem,length=length):
                    disk=self.prepare(filesystem)
                    self.assertEqual(self.begin(disk,length),0)
                    payload=(bytes(range(256))*5)[:length]
                    for offset in range(0,length,512):
                        chunk=payload[offset:offset+512]
                        self.assertEqual(self.packet(disk,chunk),len(chunk))
                    self.assertEqual(self.finish(disk),0)
                    entry=disk.entry(1 if filesystem=='exfat' else 0)
                    self.assertEqual(int.from_bytes(entry[24:28] if filesystem=='exfat' else entry[28:32],'little'),length)

    def test_foreign_same_name_inserted_before_owned_fat_entry_prevents_close(self):
        disk=self.prepare('fat');disk.set_entry(0,b'OTHER   TXT\x20'+bytes(20))
        self.assertEqual(self.begin(disk,512),0)
        self.assertEqual(self.packet(disk,b'X'*512),512)
        foreign=bytearray(b'BOOK    BMK\x20'+bytes(20));struct.pack_into('<H',foreign,26,50);struct.pack_into('<I',foreign,28,13)
        disk.set_entry(0,foreign);before=bytes(disk.sectors);writes=len(disk.sector_writes)
        self.assertLess(self.finish(disk),0)
        self.assertEqual(len(disk.sector_writes),writes)
        self.assertEqual(bytes(disk.sectors),before)

    def test_changed_fcb_after_last_packet_cannot_publish_foreign_cluster(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem);self.assertEqual(self.begin(disk,512),0)
                self.assertEqual(self.packet(disk,b'X'*512),512)
                disk._word(0x03077668+20,50)
                before=bytes(disk.sectors);writes=len(disk.sector_writes)
                self.assertLess(self.finish(disk),0)
                self.assertEqual(len(disk.sector_writes),writes)
                self.assertEqual(bytes(disk.sectors),before)

    def test_dirty_foreign_fat_cache_is_preserved_on_finish_and_publish_refusal(self):
        for filesystem in ('fat','exfat'):
            for phase in ('finish','publish'):
                with self.subTest(filesystem=filesystem,phase=phase):
                    if phase=='publish':disk=self.completed_tmp(filesystem)
                    else:
                        disk=self.prepare(filesystem);self.assertEqual(self.begin(disk,512),0)
                        self.assertEqual(self.packet(disk,b'X'*512),512)
                    disk.cpu.mem_write(0x03076714,b'Q'*512)
                    disk.cpu.mem_write(0x03076914,b'\x01')
                    disk._word(0x03076918,17)
                    cache=bytes(disk.cpu.mem_read(0x03076714,520));writes=len(disk.sector_writes)
                    self.assertLess((self.publish if phase=='publish' else self.finish)(disk),0)
                    self.assertEqual(bytes(disk.cpu.mem_read(0x03076714,520)),cache)
                    self.assertEqual(len(disk.sector_writes),writes)

    def test_wrapping_cluster_heap_extent_refuses_before_reservation_mutation(self):
        disk=self.prepare('fat');disk._word(0x03076b4f,0xffffff00)
        disk._word(0x03076b34,128);disk.cpu.mem_write(0x03076b26,b'\x07\0')
        before=bytes(disk.sectors)
        self.assertLess(self.reserve(disk,131072)[0],0)
        self.assertEqual(disk.sector_writes,[]);self.assertEqual(bytes(disk.sectors),before)

    def test_exfat_allocation_geometry_is_proved_before_creation(self):
        for failure in ('missing','cluster','flags','length','fat_count','self_bit','root_bit','parent_bit'):
            with self.subTest(failure=failure):
                disk=self.prepare('exfat')
                native_root=int.from_bytes(disk.cpu.mem_read(0x03076b3d,4),'little')
                offset=(disk.DATA_LBA+(native_root-2)*disk.SPC)*512
                if failure=='missing':disk.sectors[offset]=0
                elif failure=='cluster':struct.pack_into('<I',disk.sectors,offset+20,4)
                elif failure=='flags':disk.sectors[offset+1]=1
                elif failure=='length':struct.pack_into('<I',disk.sectors,offset+24,7)
                elif failure=='fat_count':disk.cpu.mem_write(0x03076b3a,b'\x02')
                else:
                    cluster=2 if failure=='self_bit' else native_root if failure=='root_bit' else disk.ROOT_CLUSTER
                    bit=cluster-2;disk.sectors[disk.DATA_LBA*512+bit//8] &= ~(1<<(bit%8))
                self.refuse_unchanged(disk)

    def test_multiple_fat_copies_refuse_without_unverified_mirror_writes(self):
        disk=self.prepare('fat');disk.cpu.mem_write(0x03076b3a,b'\x02')
        self.refuse_unchanged(disk)
        self.assertLess(self.reserve(disk)[0],0)
        self.assertEqual(disk.sector_writes,[])

    def test_first_free_run_beyond_4096_clusters_is_found_with_sector_bound(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem,clusters=8192)
                if filesystem=='fat':
                    for cluster in range(3,5002):disk.set_fat(cluster,0x0fffffff)
                else:disk.sectors[disk.DATA_LBA*512:disk.DATA_LBA*512+625]=b'\xff'*625
                self.assertEqual(self.reserve(disk),(0,(5002,2)))
                self.assertGreater(disk.watchdog_kicks,0)

    def test_fragmented_bitmap_chain_refuses_before_allocation(self):
        disk=self.prepare('exfat',clusters=8192);disk.set_fat(2,0x0fffffff)
        before=bytes(disk.sectors)
        self.assertLess(self.reserve(disk)[0],0)
        self.assertEqual(disk.sector_writes,[]);self.assertEqual(bytes(disk.sectors),before)

    def test_native_reservation_preserves_neighbors_and_persists_allocation(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem)
                before=bytes(disk.sectors)
                result,(first,count)=self.reserve(disk)
                self.assertEqual(result,0)
                self.assertEqual(count,2)
                if filesystem=='fat':
                    self.assertEqual(first,3);self.assertEqual(disk.chain(first),[3,4])
                    self.assertEqual(disk.sectors[512:524],before[512:524])
                    self.assertEqual(disk.sectors[532:],before[532:])
                else:
                    self.assertEqual(first,4);self.assertEqual(disk.sectors[4*512],15)
                    self.assertEqual(disk.sectors[:4*512],before[:4*512])
                    self.assertEqual(disk.sectors[4*512+1:],before[4*512+1:])
                self.assertEqual(disk.entry(),bytes(32))
                self.assertEqual(disk.cpu.mem_read(0x03076914,1),b'\0')

    def test_128k_cluster_and_98k_playlist_preflight_are_supported(self):
        disk=self.prepare('exfat',256)
        self.assertEqual(self.invoke(disk,event_bytes=98304),0)
        result,(first,count)=self.reserve(disk,98304)
        self.assertEqual(result,0);self.assertEqual((first,count),(4,1))

    def test_reservation_read_failure_matrix_never_changes_other_sectors(self):
        for filesystem in ('fat','exfat'):
            good=self.prepare(filesystem);self.assertEqual(self.reserve(good)[0],0)
            for fault in range(1,len(good.sector_reads)+1):
                with self.subTest(filesystem=filesystem,read=fault):
                    disk=self.prepare(filesystem)
                    before=bytes(disk.sectors);disk.fail_read_number=fault
                    result,output=self.reserve(disk)
                    self.assertLess(result,0);self.assertEqual(output,(0,0))
                    allocation_lba=1 if filesystem=='fat' else 4
                    self.assertEqual(disk.sectors[:allocation_lba*512],before[:allocation_lba*512])
                    self.assertEqual(disk.sectors[(allocation_lba+1)*512:],before[(allocation_lba+1)*512:])
                    self.assertEqual(disk.cpu.mem_read(0x03076914,1),b'\0')
                    self.assertEqual(disk.cpu.mem_read(0x03076918,4),bytes(4))

    def test_reservation_failed_allocation_write_is_not_success(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem);before=bytes(disk.sectors)
                disk.failed_write_lbas.add(1 if filesystem=='fat' else 4)
                result,output=self.reserve(disk)
                self.assertLess(result,0);self.assertEqual(output,(0,0))
                self.assertEqual(bytes(disk.sectors),before)
                self.assertEqual(disk.cpu.mem_read(0x03076914,1),b'\0')

    def test_reservation_refuses_fragmented_first_run_and_full_cards_without_writes(self):
        for filesystem in ('fat','exfat'):
            for full in (False,True):
                with self.subTest(filesystem=filesystem,full=full):
                    disk=self.prepare(filesystem)
                    if filesystem=='fat':
                        for cluster in (range(3,disk.CLUSTERS+2) if full else [4]):disk.set_fat(cluster,0x0fffffff)
                    else:
                        disk.sectors[4*512:4*512+8]=b'\xff'*8 if full else b'\x0b'+bytes(7)
                    before=bytes(disk.sectors)
                    self.assertLess(self.reserve(disk)[0],0)
                    self.assertEqual(disk.sector_writes,[]);self.assertEqual(bytes(disk.sectors),before)

    def later_fat_run(self):
        disk=self.prepare('fat');disk._word(0x03076b4b,256)
        for cluster in range(3,128):disk.set_fat(cluster,0x0fffffff)
        return disk

    def test_fat_native_scan_failure_before_pinned_run_cannot_flush_stale_cache(self):
        good=self.later_fat_run()
        result,output=self.reserve(good)
        self.assertEqual((result,output),(0,(128,2)))
        for fault in range(1,len(good.sector_reads)+1):
            with self.subTest(read=fault):
                disk=self.later_fat_run();before=bytes(disk.sectors)
                disk.fail_read_number=fault
                self.assertLess(self.reserve(disk)[0],0)
                self.assertEqual(disk.sectors[:2*512],before[:2*512])
                self.assertEqual(disk.sectors[3*512:],before[3*512:])
                self.assertEqual(disk.cpu.mem_read(0x03076914,1),b'\0')

    def test_fat_run_crossing_cache_sector_is_refused_before_mutation(self):
        disk=self.prepare('fat');disk._word(0x03076b4b,256)
        for cluster in range(3,127):disk.set_fat(cluster,0x0fffffff)
        before=bytes(disk.sectors)
        self.assertLess(self.reserve(disk)[0],0)
        self.assertEqual(disk.sector_writes,[]);self.assertEqual(bytes(disk.sectors),before)

    def test_empty_creation_restores_native_current_directory(self):
        for filesystem in ('fat', 'exfat'):
            with self.subTest(filesystem=filesystem):
                disk = self.prepare(filesystem)
                self.assertEqual(self.invoke(disk), 0)
                self.assertTrue(disk.sector_writes)
                self.assertEqual(bytes(disk.cpu.mem_read(0x03077664, 4)), b'KEEP')
                self.assertEqual(bytes(disk.cpu.mem_read(0x03078a5c, 42)), bytes(range(42)))
                self.assertEqual(disk.cpu.mem_read(0x03077668, 1), b'\0')
                self.assertEqual(disk.entry()[0], 0x85 if filesystem == 'exfat' else ord('B'))

    def refuse_unchanged(self, disk, **kwargs):
        before = bytes(disk.sectors)
        self.assertLess(self.invoke(disk, **kwargs), 0)
        self.assertEqual(disk.sector_writes, [])
        self.assertEqual(bytes(disk.sectors), before)
        self.assertEqual(bytes(disk.cpu.mem_read(0x03077664, 4)), b'KEEP')
        self.assertEqual(bytes(disk.cpu.mem_read(0x03078a5c, 42)), bytes(range(42)))

    def test_full_cards_refuse_before_native_allocation_or_writes(self):
        for filesystem in ('fat', 'exfat'):
            with self.subTest(filesystem=filesystem):
                disk = self.prepare(filesystem)
                if filesystem == 'exfat':
                    disk.sectors[disk.DATA_LBA*512:disk.DATA_LBA*512+8] = b'\xff'*8
                else:
                    for cluster in range(3, disk.CLUSTERS+2):
                        disk.set_fat(cluster, 0x0fffffff)
                self.refuse_unchanged(disk)

    def test_exfat_first_pair_with_active_third_refuses_even_if_later_space(self):
        disk = self.prepare('exfat')
        disk.set_entry(0, b'\x05' + bytes(31))
        disk.set_entry(1, b'\x40' + bytes(31))
        disk.set_entry(2, b'\x83' + b'PRESERVE'.ljust(31,b'!'))
        self.refuse_unchanged(disk)

    def test_directory_growth_and_exfat_cross_sector_set_refuse(self):
        for filesystem in ('fat', 'exfat'):
            with self.subTest(filesystem=filesystem):
                disk = self.prepare(filesystem);disk.fill_root()
                self.refuse_unchanged(disk)
        disk = self.prepare('exfat');disk.fill_root()
        disk.set_entry(14,bytes(32));disk.set_entry(15,bytes(32))
        self.refuse_unchanged(disk)

    def test_directory_read_failure_and_stale_cache_refuse_without_corruption(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem)
                disk.failed_read_lbas.add(disk.DATA_LBA+disk.ROOT_CLUSTER-2)
                disk.cpu.mem_write(0x03076b68,b'Z'*512)
                disk._word(0x03076b64,123)
                self.refuse_unchanged(disk)

    def test_every_precreate_read_failure_refuses_without_native_create(self):
        for filesystem in ('fat','exfat'):
            for read_number in range(1,5):
                with self.subTest(filesystem=filesystem,read_number=read_number):
                    disk=self.prepare(filesystem)
                    disk.fail_read_number=read_number
                    self.refuse_unchanged(disk)
                    self.assertNotIn(0x0305fba6,disk.native_calls)

    def test_failed_initial_entry_write_never_calls_native_close(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem)
                root=disk.DATA_LBA+disk.ROOT_CLUSTER-2
                disk.failed_write_lbas.add(root)
                self.assertLess(self.invoke(disk),0)
                self.assertNotIn(0x0305c2e0,disk.native_calls)
                self.assertEqual(disk.entry(),bytes(32))

    def test_read_failure_after_create_abandons_only_empty_handle(self):
        for filesystem in ('fat','exfat'):
            for read_number in (5,6):
                with self.subTest(filesystem=filesystem,read_number=read_number):
                    disk=self.prepare(filesystem)
                    sentinel=b'\x83'+bytes(range(31)) if filesystem=='exfat' else b'PRESERVETXT\x20'+bytes(20)
                    disk.set_entry(8,sentinel)
                    disk.fail_read_number=read_number
                    self.assertLess(self.invoke(disk),0)
                    self.assertEqual(disk.entry(8),sentinel)
                    self.assertEqual(disk.cpu.mem_read(0x03077668,1),b'\0')
                    self.assertEqual(bytes(disk.cpu.mem_read(0x03077664,4)),b'KEEP')
                    self.assertEqual(bytes(disk.cpu.mem_read(0x03078a5c,42)),bytes(range(42)))

    def test_two_sector_cluster_native_rescan_uses_checked_directory_cache(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem)
                disk.fill_root()
                disk._word(0x03076b34,2)
                disk.cpu.mem_write(0x03076b26,b'\x01\0')
                disk.cpu.mem_write(0x20008000,struct.pack('<III',disk.ROOT_CLUSTER,1024,0)+b'\x01'+bytes(29))
                # Cluster3 root moves to LBA6 with two sectors per cluster.
                if filesystem=='exfat':
                    disk.sectors[6*512:7*512]=disk.sectors[5*512:6*512]
                    old=disk.DATA_LBA+disk.ROOT_CLUSTER-2
                    new=disk.DATA_LBA+(disk.ROOT_CLUSTER-2)*2
                    disk.sectors[new*512:(new+1)*512]=disk.sectors[old*512:(old+1)*512]
                    disk.sectors[(new+1)*512:(new+2)*512]=bytes(512)
                self.assertEqual(self.invoke(disk),0)
                root_lba=disk.DATA_LBA+(disk.ROOT_CLUSTER-2)*2
                self.assertEqual(disk.sectors[(root_lba+1)*512],0x85 if filesystem=='exfat' else ord('B'))

    def test_fixed_names_and_eventual_size_are_bounded(self):
        for name in (b'BOOK.M3U\0',b'OTHER.BMK\0',b'BOOK.BMKX\0',b'book.bmk\0'):
            disk=self.prepare('fat');disk.cpu.mem_write(0x20009000,name)
            self.refuse_unchanged(disk)
        for size in (0,513,65537):
            disk=self.prepare('fat');self.refuse_unchanged(disk,event_bytes=size)

    def test_readonly_parent_and_multicluster_parent_refuse(self):
        for filesystem in ('fat','exfat'):
            for failure in ('readonly','chain'):
                with self.subTest(filesystem=filesystem,failure=failure):
                    disk=self.prepare(filesystem)
                    if failure=='readonly':disk.cpu.mem_write(0x20008000+13,b'\x11')
                    else:disk.set_fat(disk.ROOT_CLUSTER,disk.ROOT_CLUSTER+1)
                    self.refuse_unchanged(disk)

    def test_malformed_exfat_parent_flags_and_lengths_refuse_before_writes(self):
        for flags,length in ((0,512),(4,512),(128,512),(3,1),(3,511),(1,4096),(3,0)):
            with self.subTest(flags=flags,length=length):
                disk=self.prepare('exfat')
                disk.cpu.mem_write(0x20008000,struct.pack('<III',disk.ROOT_CLUSTER,length,0)+bytes([flags])+bytes(29))
                self.refuse_unchanged(disk)

    def test_existing_same_name_file_and_directory_refuse(self):
        for filesystem in ('fat','exfat'):
            for attrs in (0x20,0x10):
                with self.subTest(filesystem=filesystem,attrs=attrs):
                    disk=self.prepare(filesystem)
                    if filesystem=='fat':
                        disk.set_entry(0,b'BOOK    BMK'+bytes([attrs])+bytes(20))
                    else:
                        disk.set_entry(0,b'\x85\x02\0\0'+bytes([attrs])+bytes(27))
                        disk.set_entry(1,b'\xc0\x01\0\x08'+bytes(28))
                        disk.set_entry(2,b'\xc1\0'+b'book.bmk'.decode().encode('utf-16le')+bytes(14))
                    self.refuse_unchanged(disk)

    def test_device_filesystem_handle_exhaustion_and_dirty_fat_refuse(self):
        for filesystem in ('fat','exfat'):
            for failure in ('device','filesystem','handles','dirty'):
                with self.subTest(filesystem=filesystem,failure=failure):
                    disk=self.prepare(filesystem)
                    kwargs={}
                    if failure=='device':kwargs['device']=disk.DEV+1
                    elif failure=='filesystem':kwargs['fs']=9
                    elif failure=='dirty':disk.cpu.mem_write(0x03076914,b'\x01')
                    else:
                        for h in range(8):disk.cpu.mem_write(0x03077668+h*0x27e,b'\x01')
                    self.refuse_unchanged(disk,**kwargs)

    def test_physical_parent_does_not_resolve_unicode_names_through_short_api(self):
        for filesystem in ('fat','exfat'):
            with self.subTest(filesystem=filesystem):
                disk=self.prepare(filesystem)
                # Move the physical parent to cluster10. Its Unicode spelling
                # is deliberately not supplied to the short-name create API.
                disk.set_fat(10,0x0fffffff)
                if filesystem=='exfat':disk.sectors[disk.DATA_LBA*512+2] |= 1<<2
                target=20
                disk.set_fat(target,0x0fffffff)
                disk.cpu.mem_write(0x20008000,struct.pack('<III',target,512,0)+b'\x01'+bytes(29))
                self.assertEqual(self.invoke(disk),0)
                start=(disk.DATA_LBA+target-2)*512
                self.assertEqual(disk.sectors[start],0x85 if filesystem=='exfat' else ord('B'))
                self.assertEqual(disk.entry(),bytes(32))


if __name__ == '__main__':
    unittest.main()
