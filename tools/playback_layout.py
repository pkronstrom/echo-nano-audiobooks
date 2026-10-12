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

AUDIO_REFS=((0,0x03050bc8),(22,0x03079a18),(23,0x03079c88),
            (27,0x0307c3b4),(27,0x0307c7a4),(31,0x0307a2b8),
            (31,0x0300e6c0),(34,0x03084dd4))

def discovery(image):
    """Extend only the browser's fallback whitelist; audio stays audio-only."""
    audio=b'MP1MP2MP3WMAWAVAPEFLAAACM4AOGGMP43GPDFFDSF\0'
    for address in (0x03005a5e,0x03005a89,0x03005ab4):
        offset,_=image.region(0,address)
        if image.d[offset:offset+len(audio)]!=audio:
            raise ValueError('original audio whitelist changed')
    # Consolidate the second duplicate before extending the first into it.
    for module,address in AUDIO_REFS:
        offset,_=image.region(module,address)
        if image.d[offset:offset+4]!=struct.pack('<I',0x03005a89):
            raise ValueError('audio whitelist reference changed')
        image.patch(module,address,struct.pack('<I',0x03005ab4))
    image.patch(0,0x03005a5e,audio[:-1]+b'M3U\0')
    return image

HOOKS={
    'browser':(31,0x0307acb6,66,None),
    'settings':(33,0x0308301e,190,None),
    'music_enter':(33,0x030827ba,4,None),
    'prepare':(33,0x030828ec,4,0x03082732),
    'queue':(33,0x030829d6,4,0x030603d0),
    'save_close':(33,0x030822ac,4,0x03084e28),
    'stock_save':(33,0x030825c4,4,0x03085000),
    'order':(33,0x030831ba,4,None),
    **{f'advance_{a:x}':(33,a,4,0x03060c10) for a in (0x030817be,0x030817e4,0x0308182a,0x03081890,0x030819d2,0x030819e2)},
}

def read_patch(path):
    lines=[line for line in path.read_text().splitlines() if line and not line.startswith('#')]
    if len(lines)!=1:raise ValueError(f'Expected one compiled patch: {path}')
    mod,address,data=lines[0].split(':')
    return int(mod),int(address,16),bytes.fromhex(data)

def integrate(stock_data,input_data,directory,date):
    """Build the audiobook test image; reject mismatched base or hook layout."""
    from datetime import datetime
    datetime.strptime(date,'%Y%m%d')
    loader=read_patch(directory/'loader.patch')
    if loader[:2]!=(0,LOADER_ADDRESS):raise ValueError('loader location changed')
    image=Image(stage(stock_data,input_data,(directory/'playback.bin').read_bytes(),loader[2]))
    stock=Image(stock_data)
    discovery(image)
    for name,(module,address,length,callee) in HOOKS.items():
        mod,addr,data=read_patch(directory/(name+'.patch'))
        if (mod,addr,len(data))!=(module,address,length):raise ValueError(f'Unexpected hook range: {name}')
        offset,_=image.region(module,address)
        before=bytes(image.d[offset:offset+length])
        if name=='settings':
            if hashlib.sha256(before).hexdigest()!='886f050afc1d77f1697f92be367336af906a5447df813c2b7635ea01d601a2c4':
                raise ValueError('P1b settings base changed')
        elif callee:
            if before!=encode_t32_branch(address,callee,True):raise ValueError(f'Original call changed: {name}')
        else:
            original,_=stock.region(module,address)
            if before!=stock.d[original:original+length]:raise ValueError(f'Original entry changed: {name}')
        image.patch(module,address,data)
    # Existing P1b scope branches enter the helpers retained by our replacement.
    for address,target in ((0x03082962,0x03083060),(0x03081844,0x030830a0)):
        offset,_=image.region(33,address)
        if image.d[offset:offset+4]!=encode_t32_branch(address,target,False):
            raise ValueError('P1b scope branch changed')
    image.patch(32,0x0307cf14,'P3a\0'.encode('utf-16le'))
    image.set_date(date);image.finalize()
    return bytes(image.d)
