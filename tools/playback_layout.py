"""Checked, in-memory staging for Phase2 integration tests; no release CLI yet."""
import hashlib
import struct
from rknano_fw import Image
from hooks import encode_t32_branch
STOCK_SHA256='54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116'
FLASH_START,FLASH_END=0xa55200,0xa58000
RAM_START,RAM_END=0x0309b694,0x0309fff0
LOADER_ADDRESS=0x03072e28
DEBUG_TEXT=b'[INFO] ---------------------ffff is MSG_VIDEO_FILENOTSUPPORT--------------------- \n\0'

def stage(stock_data,input_data,payload,loader):
    """Install code only; browser/player entry hooks are a separate integration.

    Reclaim the exact 84-byte debug string and disable its one printf call.
    No module-table/resource relocation, firmware-size or date changes.
    """
    if hashlib.sha256(stock_data).hexdigest()!=STOCK_SHA256:
        raise ValueError('playback layout requires the pinned stock image')
    stock,image=Image(stock_data),Image(input_data)
    if len(image.d)!=len(stock.d) or image.fw_len!=FLASH_END or image.modules!=stock.modules or image.sections!=stock.sections:
        raise ValueError('firmware layout changed')
    if not image.header_copy_ok() or image.crc_stored()!=image.crc_calc():
        raise ValueError('input image integrity failed')
    if any(s['offset']+s['length']>FLASH_START for s in stock.sections):
        raise ValueError('payload overlaps a resource')
    if any(image.d[FLASH_START:FLASH_END]):
        raise ValueError('payload padding is occupied')
    if len(payload)<16 or len(payload)>FLASH_END-FLASH_START or len(payload)%4:
        raise ValueError('payload size invalid')
    magic,entry,bss_start,bss_end=struct.unpack_from('<4I',payload)
    if magic!=0x32504e45 or not entry&1 or not RAM_START+16<=entry&~1<RAM_START+len(payload):
        raise ValueError('payload entry invalid')
    if bss_start!=RAM_START+len(payload) or not bss_start<=bss_end<=RAM_END:
        raise ValueError('payload RAM bounds invalid')
    if len(loader)!=len(DEBUG_TEXT) or len(loader)!=84:
        raise ValueError('loader does not fit reclaimed message')
    # The only immediate payload length and entry call must match this build.
    a,b=struct.unpack_from('<HH',loader,24)
    length=((a&15)<<12)|(((a>>10)&1)<<11)|(((b>>12)&7)<<8)|(b&255)
    if a&0xfbf0!=0xf240 or b&0x0f00!=0x0200 or length!=len(payload):
        raise ValueError('loader payload length mismatch')
    if loader[52:56]!=encode_t32_branch(LOADER_ADDRESS+52,entry&~1,True):
        raise ValueError('loader entry mismatch')
    offset,_=image.region(0,LOADER_ADDRESS)
    if image.d[offset:offset+84]!=DEBUG_TEXT:
        raise ValueError('reclaimed debug message changed')
    call,_=image.region(21,0x03079d1a)
    if image.d[call:call+4]!=encode_t32_branch(0x03079d1a,0x03071e28,True):
        raise ValueError('debug call changed')
    image.patch(21,0x03079d1a,bytes.fromhex('00bf00bf'))
    image.patch(0,LOADER_ADDRESS,loader)
    image.d[FLASH_START:FLASH_START+len(payload)]=payload
    image.finalize()
    return bytes(image.d)
