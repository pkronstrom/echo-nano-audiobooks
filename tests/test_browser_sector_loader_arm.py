"""Browser relocation through actual stock module AND byte readers.

Only sector I/O and IRQ locks are mocked. No firmware image is written.
"""
import unittest
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR
import test_payload_flash_read_arm as fixture
ROOT=fixture.ROOT
from rknano_fw import Image
import playback_layout as layout

class BrowserSectorLoaderTests(unittest.TestCase):
 setup_cpu=fixture.PayloadFlashReadTests.setup_cpu
 hook=fixture.PayloadFlashReadTests.hook
 def test_browser_native_module_loader_preserves_every_code_byte(self):
  stock=(ROOT/'NANOV170.IMG').read_bytes()
  base=(ROOT/'out/NANOV170.IMG').read_bytes()
  resident=(ROOT/'out/playback/playback.bin').read_bytes()
  loader=layout.read_patch(ROOT/'out/playback/loader.patch')[2]
  image=Image(layout.stage(stock,base,resident,loader))
  payload=(ROOT/'out/browser_sort/browser_sort.bin').read_bytes()
  layout.relocate_browser_sort(Image(stock),image,payload)
  module=image.modules[31];code=bytes(image.d[layout.BROWSER_SORT_FLASH_START:layout.BROWSER_SORT_FLASH_START+module['code_len']])
  for second in (False,True):
   with self.subTest(second_slot=second):
    self.setup_cpu(bytes(image.d),second)
    self.cpu.mem_write(module['code_exec'],b'Z'*module['code_len'])
    self.cpu.reg_write(UC_ARM_REG_R0,31);self.cpu.reg_write(UC_ARM_REG_R1,7)
    self.cpu.reg_write(UC_ARM_REG_SP,0x03003f00);self.cpu.reg_write(UC_ARM_REG_LR,0x03010001)
    self.cpu.emu_start(0x0306b6bd,0,count=2000000)
    self.assertTrue(self.returned)
    actual=bytes(self.cpu.mem_read(module['code_exec'],module['code_len']))
    first=next((i for i,(a,b) in enumerate(zip(actual,code)) if a!=b),None)
    self.assertIsNone(first,f'first corrupt byte={first}; sector requests={self.reads}')
