"""Sector-backed stock ARM filesystem research; never accesses real media.

Only sector read/write, IRQ lock/unlock and watchdog hardware are substituted. All parent lookup,
directory insertion, allocation, cache flush, open and file reads execute stock.
The small fixture seeds already-mounted native geometry, not a mount parser.
"""
from pathlib import Path
import hashlib
import struct
import sys

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR,
                               UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from rknano_fw import Image

STOCK_SHA256 = '54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116'
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
RETURN = 0x20000000
STACK = 0x030fe000
FCB = 0x03077668


class PowerCut(RuntimeError):
    """An injected loss of execution before an actual sector write."""


class NativeDisk:
    FAT_LBA = 1
    DATA_LBA = 4
    ROOT_CLUSTER = 2
    CLUSTERS = 64
    DEV = 0x30002

    def __init__(self, filesystem='fat', sectors_per_cluster=1, clusters=64):
        if filesystem not in ('fat', 'exfat'):
            raise ValueError('fixture supports FAT32 and exFAT')
        self.filesystem = filesystem
        if sectors_per_cluster not in (1,2,4,8,16,32,64,128,256):
            raise ValueError('fixture cluster size must be a power of two up to 256 sectors')
        self.SPC = sectors_per_cluster
        self.CLUSTERS = clusters
        self.DATA_LBA = max(4, 2 + (clusters + 129)//128)
        bitmap_clusters = ((clusters+7)//8 + self.SPC*512-1)//(self.SPC*512)
        self.ROOT_CLUSTER = 2+bitmap_clusters if filesystem == 'exfat' else 2
        self.sectors = bytearray(max(128,self.DATA_LBA+self.CLUSTERS*self.SPC) * 512)
        struct.pack_into('<III', self.sectors, 512, 0x0ffffff8, 0x0fffffff, 0x0fffffff)
        if filesystem == 'exfat':
            for cluster in range(2,self.ROOT_CLUSTER):
                struct.pack_into('<I',self.sectors,512+cluster*4,cluster+1 if cluster+1<self.ROOT_CLUSTER else 0x0fffffff)
            struct.pack_into('<I', self.sectors, 512 + self.ROOT_CLUSTER * 4, 0x0fffffff)
            for cluster in range(2,self.ROOT_CLUSTER+1):
                self.sectors[self.DATA_LBA*512+(cluster-2)//8] |= 1<<((cluster-2)%8)
        self.sector_reads = []
        self.sector_writes = []
        self.failed_write_lbas = set()
        self.failed_read_lbas = set()
        self.fail_read_number = None
        self.native_calls = []
        self.watchdog_kicks = 0
        self.cut_before_write = None
        self.fail_write_number = None
        self.minimum_sp = STACK
        self._boot_cpu()

    def _word(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def _boot_cpu(self):
        stock = (ROOT / 'NANOV170.IMG').read_bytes()
        if hashlib.sha256(stock).hexdigest() != STOCK_SHA256:
            raise ValueError('stock image hash mismatch')
        image = Image(stock)
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.cpu.mem_map(0x03000000, 0x100000)
        self.cpu.mem_map(0x20000000, 0x10000)
        module = image.modules[0]
        for kind in ('code', 'data'):
            offset = image.l2f(module[kind + '_load'])
            self.cpu.mem_write(module[kind + '_exec'], bytes(image.d[offset:offset + module[kind + '_len']]))
        # Native packed mount geometry: FS type, device kind, cluster/sector
        # shifts, device ID, bytes/sector, sectors/cluster, root, cluster count,
        # data LBA, reserved sector count, partition LBA.
        self.cpu.mem_write(0x03076b24, bytes([3 if self.filesystem == 'exfat' else 2, 3, self.SPC.bit_length()-1, 0, 9, 0]))
        for address, value in ((0x03076b2c, self.DEV), (0x03076b30, 512),
                               (0x03076b34, self.SPC), (0x03076b3d, self.ROOT_CLUSTER),
                               (0x03076b4b, self.CLUSTERS), (0x03076b4f, self.DATA_LBA),
                               (0x03076b53, 0), (0x03076b5b, self.FAT_LBA)):
            self._word(address, value)
        self.cpu.mem_write(0x03076b38, struct.pack('<H', self.FAT_LBA))
        self.cpu.mem_write(0x03076b3a,b'\x01')  # mounted FAT count
        self.cpu.hook_add(UC_HOOK_CODE, self._hook)
        self.call(0x0305bddc)  # Native file/cache initialization.

    def _hook(self, cpu, address, size, user):
        self.minimum_sp = min(self.minimum_sp, cpu.reg_read(UC_ARM_REG_SP))
        result = None
        if address in (0x0305fba6, 0x0305e912, 0x0305e9c2, 0x0305c2e0, 0x0305eba0, 0x0305ec52):
            self.native_calls.append(address)
        if address == RETURN:
            cpu.emu_stop()
            return
        if address == 0x03065800:
            self.watchdog_kicks += 1
            result = 0
        elif address in (0x0306a40e, 0x0306a466):
            result = 0
        elif address in (0x0306b716, 0x0306b75e):
            dev, lba, count, buffer = [cpu.reg_read(reg) for reg in REGS]
            if dev != self.DEV or not count or lba + count > len(self.sectors) // 512:
                raise AssertionError(f'invalid sector request {dev:x}, {lba}, {count}')
            start, end = lba * 512, (lba + count) * 512
            if address == 0x0306b716:
                self.sector_reads.append((lba, count))
                if len(self.sector_reads) == self.fail_read_number or any(sector in self.failed_read_lbas for sector in range(lba, lba + count)):
                    result = 1
                else:
                    cpu.mem_write(buffer, bytes(self.sectors[start:end]))
            else:
                self.sector_writes.append((lba, count))
                if len(self.sector_writes) == self.cut_before_write:
                    raise PowerCut(f'before sector write {self.cut_before_write}')
                if len(self.sector_writes) == self.fail_write_number or any(sector in self.failed_write_lbas for sector in range(lba, lba + count)):
                    result = 1
                else:
                    self.sectors[start:end] = cpu.mem_read(buffer, end - start)
            if result is None:
                result = 0
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0, result)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def call(self, address, *args):
        for reg, value in zip(REGS, args):
            self.cpu.reg_write(reg, value)
        self.cpu.reg_write(UC_ARM_REG_SP, STACK)
        for index, value in enumerate(args[4:]):
            self._word(STACK + index * 4, value)
        self.cpu.reg_write(UC_ARM_REG_LR, RETURN | 1)
        self.cpu.emu_start(address | 1, RETURN, count=20000000)
        pc = self.cpu.reg_read(UC_ARM_REG_PC)
        if pc != RETURN:
            raise AssertionError(f'native call {address:x} exceeded instruction bound at {pc:x}')
        result = self.cpu.reg_read(UC_ARM_REG_R0)
        return result if result < 0x80000000 else result - 0x100000000

    def create(self, name):
        base, extension = name.split('.')
        short = (base.ljust(8) + extension.ljust(3)).encode('ascii')
        if len(short) != 11:
            raise ValueError('fixture requires an 8.3 filename')
        if self.filesystem == 'exfat':
            short = name.encode('ascii').ljust(11, b'\0')
        self._word(0x03077664, self.ROOT_CLUSTER)
        descriptor = struct.pack('<III', self.ROOT_CLUSTER, len(self.chain(self.ROOT_CLUSTER)) * self.SPC * 512, 0) + b'\x01' + bytes(29)
        self.cpu.mem_write(0x03078a5c, descriptor)
        self.cpu.mem_write(0x20001000, b'.\0')
        self.cpu.mem_write(0x20002000, short + b'\0')
        return self.call(0x0305fba6, 0x20001000, 0x20002000)

    def write(self, handle, payload, offset=0):
        self.cpu.mem_write(0x20003000, payload + bytes((-len(payload)) % 512))
        return self.call(0x0305fda4, 0x20003000, offset, len(payload), handle)

    def close(self, handle):
        return self.call(0x0305c2e0, handle)

    def entry(self, index=0):
        chain = self.chain(self.ROOT_CLUSTER)
        cluster = chain[index // (16*self.SPC)]
        start = (self.DATA_LBA + (cluster - 2)*self.SPC) * 512 + (index % (16*self.SPC)) * 32
        return bytes(self.sectors[start:start + 32])

    def set_entry(self, index, entry):
        if len(entry) != 32 or not 0 <= index < 16*self.SPC:
            raise ValueError('fixture seed entry must fit initial root sector')
        start = (self.DATA_LBA + (self.ROOT_CLUSTER - 2)*self.SPC) * 512 + index * 32
        self.sectors[start:start + 32] = entry

    def set_fat(self, cluster, value):
        struct.pack_into('<I', self.sectors, self.FAT_LBA * 512 + cluster * 4, value)

    def fill_root(self):
        for index in range(16):
            entry = bytearray(32)
            if self.filesystem == 'exfat':
                entry[0] = 0x83
            else:
                entry[:11] = f'F{index:07d}TXT'.encode('ascii')
                entry[11] = 0x20
            self.set_entry(index, entry)

    def chain(self, cluster):
        result = []
        while 2 <= cluster < 0x0ffffff8:
            if cluster in result or cluster >= self.CLUSTERS + 2:
                raise AssertionError('invalid persisted FAT chain')
            result.append(cluster)
            cluster = struct.unpack_from('<I', self.sectors, self.FAT_LBA * 512 + cluster * 4)[0] & 0x0fffffff
        return result

    def create_roundtrip(self, name, payload):
        handle = self.create(name)
        if handle < 0:
            raise AssertionError(f'native create failed: {handle}')
        if self.write(handle, payload) != len(payload):
            raise AssertionError('native growing write was short')
        if self.close(handle):
            raise AssertionError('native close failed')
        # Do not trust create's returned directory index: FAT directory growth
        # returns one past the actual newly inserted entry. Re-resolve cold.
        self._boot_cpu()
        descriptor = struct.pack('<III', self.ROOT_CLUSTER, len(self.chain(self.ROOT_CLUSTER)) * 512, 0) + b'\x01' + bytes(29)
        self.cpu.mem_write(0x20005000, descriptor)
        index = None
        base, extension = name.split('.')
        short = (base.ljust(8) + extension.ljust(3)).encode('ascii')
        for candidate in range(len(self.chain(self.ROOT_CLUSTER)) * 16):
            status = self.call(0x0305b2a2 if self.filesystem == 'exfat' else 0x0305b3ea,
                               0x20006000, 0x20005000 if self.filesystem == 'exfat' else self.ROOT_CLUSTER,
                               candidate)
            raw = bytes(self.cpu.mem_read(0x20006000, 32))
            if status:
                raise AssertionError('cold directory reread failed')
            if self.filesystem == 'exfat':
                match = raw[0] == 0xc1 and raw[2:2 + len(name) * 2] == name.encode('utf-16le')
                if match:
                    index = candidate - 2
                    break
            elif raw[:11] == short:
                index = candidate
                break
        if index is None:
            raise AssertionError('cold name re-resolution failed')
        entry = self.entry(index)
        if self.filesystem == 'exfat':
            stream = self.entry(index + 1)
            size = struct.unpack_from('<I', stream, 24)[0]
            cluster = struct.unpack_from('<I', stream, 20)[0]
            chain = list(range(cluster, cluster + (size + 511) // 512)) if stream[1] & 2 else self.chain(cluster)
        else:
            size = struct.unpack_from('<I', entry, 28)[0]
            cluster = struct.unpack_from('<H', entry, 26)[0] | struct.unpack_from('<H', entry, 20)[0] << 16
            chain = self.chain(cluster)
        # Recreate the entire emulator, retaining only persisted sector bytes.
        self._boot_cpu()
        self.cpu.mem_write(0x20002000, b'R\0')
        if self.filesystem == 'exfat':
            self.cpu.mem_write(0x20005000, struct.pack('<III', self.ROOT_CLUSTER, 512, 0) + b'\x01' + bytes(29))
            handle = self.call(0x0305c102, 0x20001000, 0x20005000, index, 3, 0x20002000)
        else:
            handle = self.call(0x0305be12, 0x20001000, self.ROOT_CLUSTER, index, 3, 0x20002000)
        if handle < 0:
            raise AssertionError('cold indexed open failed')
        got = self.call(0x0305c3fa, 0x20004000, len(payload), handle)
        readback = bytes(self.cpu.mem_read(0x20004000, got))
        self.close(handle)
        if readback != payload:
            raise AssertionError('cold native readback does not match payload')
        return dict(readback=readback, size=size,
                    chain=chain, sector_writes=list(self.sector_writes),
                    maximum_stack_bytes=STACK - self.minimum_sp)
