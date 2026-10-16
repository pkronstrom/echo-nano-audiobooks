"""Checked, in-memory staging for Phase2 integration tests; no release CLI yet."""
import hashlib
import struct
from rknano_fw import Image
from hooks import encode_t32_branch
STOCK_SHA256='54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116'
# Sector-aligned unused portion of module40's first 64 KiB sort buffer.
# Refresh already stages its separate blob earlier in that same buffer.
FLASH_START,FLASH_END=0x36200,0x3c800
FIRMWARE_END=0xa58000
RAM_START,RAM_END=0x03092400,0x0309fff0
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
    # Refresh (module40) is the only permitted overlapping owner. Its forward
    # load replaces browser/player hooks before invalidating the payload header.
    overlaps=[]
    for module in stock.modules:
        for kind in ('code','data','bss'):
            start=module[kind+'_exec'];end=start+module[kind+'_len']
            if module[kind+'_len'] and start<RAM_END and end>RAM_START:
                overlaps.append((module['index'],kind))
    if overlaps!=[(40,'code')]:
        raise ValueError('playback RAM overlaps an unexpected module')
    refresh=stock.modules[40]
    refresh_offset=image.l2f(refresh['code_load'])+RAM_START-refresh['code_exec']
    if image.d[refresh_offset:refresh_offset+4]==struct.pack('<I',0x32504e45):
        raise ValueError('refresh does not invalidate playback header')
    if len(image.d)!=len(stock.d) or image.fw_len!=FIRMWARE_END or image.modules!=stock.modules or image.sections!=stock.sections:
        raise ValueError('firmware layout changed')
    if not image.header_copy_ok() or image.crc_stored()!=image.crc_calc():
        raise ValueError('input image integrity failed')
    if any(s['offset']<FLASH_END and s['offset']+s['length']>FLASH_START for s in stock.sections):
        raise ValueError('payload overlaps a resource')
    stage_exec=refresh['code_exec']+FLASH_START-stock.l2f(refresh['code_load'])
    if not (0x0307b674<=stage_exec and stage_exec+FLASH_END-FLASH_START<=0x0308b674):
        raise ValueError('payload staging leaves the verified refresh sort buffer')
    if any(stock.d[FLASH_START:FLASH_END]):
        raise ValueError('stock payload staging buffer is occupied')
    if any(image.d[FLASH_START:FLASH_END]):
        raise ValueError('payload padding is occupied')
    if len(payload)<16 or len(payload)>FLASH_END-FLASH_START or len(payload)%4:
        raise ValueError('payload size invalid')
    magic,entry,bss_start,bss_end=struct.unpack_from('<4I',payload)
    if magic!=0x32504e45 or not entry&1 or not RAM_START+16<=entry&~1<RAM_START+len(payload):
        raise ValueError('payload entry invalid')
    if bss_start!=RAM_START+len(payload) or not bss_start<=bss_end<=RAM_END:
        raise ValueError('payload RAM bounds invalid')
    read_length=(len(payload)+511)&~511
    if FLASH_START+read_length>FLASH_END or RAM_START+read_length>bss_end:
        raise ValueError('sector-rounded payload read exceeds padding/BSS bounds')
    if len(loader)!=len(DEBUG_TEXT) or len(loader)!=84:
        raise ValueError('loader does not fit reclaimed message')
    if struct.unpack_from('<I',loader,68)[0]!=RAM_START:
        raise ValueError('loader RAM address mismatch')
    if struct.unpack_from('<I',loader,80)[0]!=FLASH_START-512:
        raise ValueError('loader flash address mismatch')
    # The only immediate payload length and entry call must match this build.
    a,b=struct.unpack_from('<HH',loader,24)
    length=((a&15)<<12)|(((a>>10)&1)<<11)|(((b>>12)&7)<<8)|(b&255)
    if a&0xfbf0!=0xf240 or b&0x0f00!=0x0200 or length!=read_length:
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
    'startup_invalidate':(0,0x030733e0,32,None),
    'startup_invalidate_entry':(0,0x030660ca,4,None),
    'player_controls_uninit_guard':(27,0x0307a270,44,None),
    'player_controls_uninit_pointer':(27,0x0300e6d4,4,None),
    'player_controls_key':(27,0x0307bc7e,4,0x03063242),
    'player_controls_guard':(27,0x0307a3d4,36,None),
    'player_speed_menu_action_0':(32,0x0307a7f4,4,None),
    'player_speed_menu_action_guard':(32,0x0307a79c,48,None),
    'player_speed_menu_no_print_back':(32,0x0307a61a,4,None),
    'player_speed_menu_no_print_display':(32,0x03079734,4,None),
    'player_speed_menu_no_print_playlist':(32,0x0307af5e,4,None),
    'player_speed_menu_no_print_product_init':(32,0x0307ccfe,4,None),
    'player_speed_menu_no_print_product_uninit':(32,0x0307cee8,4,None),
    'player_speed_menu_no_print_screen':(32,0x03079ad8,4,None),
    'player_speed_menu_record_0':(32,0x0307955e,4,None),
    'player_speed_menu_record_1':(32,0x0307972e,4,None),
    'player_speed_menu_record_2':(32,0x0307988a,4,None),
    'player_speed_menu_record_3':(32,0x0307a010,4,None),
    'player_speed_menu_record_4':(32,0x0307a66c,4,None),
    'player_speed_menu_record_fallback':(32,0x0307cd64,24,None),
    'player_speed_menu_record_guard':(32,0x03079aac,32,None),
    'player_speed_menu_service_guard':(32,0x0307b2b4,36,None),
    'player_speed_menu_service_pointer':(32,0x0300e6c4,4,None),
    'player_speed_menu_text_0':(32,0x030797be,4,None),
    'player_speed_menu_text_1':(32,0x030797f8,4,None),
    'player_speed_menu_text_2':(32,0x030798fc,4,None),
    'player_speed_menu_text_3':(32,0x03079948,4,None),
    'player_speed_menu_text_fallback':(32,0x0307cf98,28,None),
    'player_speed_menu_text_guard':(32,0x03079ed0,32,None),
    'settings_row_icon_skip':(32,0x03079738,4,None),
    'settings_row_background':(32,0x0307973c,24,None),
    'settings_row_full':(32,0x0307975c,4,None),
    'settings_row_update_selected':(32,0x03079896,4,None),
    'settings_row_update_old':(32,0x030798a2,4,None),
    'settings_row_text_full':(32,0x03079768,2,None),
    'settings_row_text_update':(32,0x030798ac,2,None),
    'player_speed_label_width':(27,0x0307ade8,6,None),
    'player_speed_label_width_guard':(27,0x0307a39c,56,None),
    'player_speed_label_paint':(27,0x0307ae22,4,0x03052fe4),
    'player_speed_label_guard':(27,0x0307a2c8,36,None),
    'media_row_width':(23,0x0307a316,2,None),
    'media_row_text_full_left':(23,0x0307a428,2,None),
    'media_row_text_full_right':(23,0x0307a43c,2,None),
    'media_row_text_update_left':(23,0x0307a56a,4,None),
    'media_row_text_update_right':(23,0x0307a58c,2,None),
    'media_row_icon':(23,0x0307a408,4,0x030521d4),
    'media_row_full_x':(23,0x0307a424,2,None),
    'media_row_update_x':(23,0x0307a568,2,None),
    'media_row_full_old':(23,0x0307a45a,4,0x030521d4),
    'media_row_full_new':(23,0x0307a46e,4,0x030521d4),
    'media_row_update_old':(23,0x0307a5ae,4,0x030521d4),
    'media_row_update_new':(23,0x0307a5c2,4,0x030521d4),
    'media_row_glyph_full':(23,0x0307a4b6,4,0x030521d4),
    'media_row_glyph_update':(23,0x0307a60a,4,0x030521d4),
    'media_row_helpers':(23,0x03079e40,48,None),
    'library_row_text':(22,0x03079c22,8,None),
    'library_row_icon':(22,0x03079c42,4,0x030521d4),
    'library_row_full_x':(22,0x03079c80,2,None),
    'library_row_full':(22,0x03079c84,4,0x030521d4),
    'library_row_update_x':(22,0x03079d5a,4,None),
    'library_row_update':(22,0x03079d66,4,0x030521d4),
    'library_row_background':(22,0x0300e788,32,None),
    'navigation_hold':(0,0x03065ec0,4,None),
    'navigation_hold_resident':(0,0x03065918,40,None),
    'speed_status':(0,0x0306955e,4,None),
    'speed_status_guard':(0,0x030696d4,56,None),
    'speed_guard':(0,0x03072f54,64,None),
    'speed_capture':(33,0x030835c8,4,None),
    'speed_seek':(33,0x030834d8,4,None),
    'speed_time':(33,0x030834f6,4,None),
    'speed_dma_pump':(0,0x0306985e,4,0x0306c1e4),
    'speed_dma_callback':(0,0x030693fa,4,0x0306c1e4),
    'speed_dma_start':(33,0x0308168c,4,0x0306c1e4),
    'speed_dma_resume':(33,0x03081f98,4,0x0306c1e4),
    'speed_dma_restart':(33,0x03082062,4,0x0306c1e4),
    'speed_dma_reconfigure':(33,0x03083360,4,0x0306c1e4),
    'feedback_stub':(27,0x0307a014,36,None),
    'feedback_epilogue':(27,0x0307a860,8,None),
    'bookmark_poll':(33,0x03082d4c,4,0x0306b05c),
    'bookmark_gesture':(0,0x03052d68,48,None),
    'browser_row_update':(31,0x0307a4c6,4,0x030521d4),
    'browser_row_full':(31,0x0307a640,4,0x030521d4),
    'nav_menu_loader':(21,0x03079600,24,None),
    'nav_browser_loader':(31,0x0307afa0,24,None),
    'nav_menu_init':(21,0x030794ac,4,None),
    'nav_browser_init':(31,0x03079afc,4,None),
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

# Runtime branches/count/table pointers rely on this exact P1b shuffle base.
NAVIGATION_BASE={
    0x03079f5e:bytes.fromhex('052000bf'),
    0x03079f70:bytes.fromhex('0528'),
    0x0307a4d8:bytes.fromhex('04950703'),
    0x0307a24c:bytes.fromhex('d8e60003'),
    0x03079504:struct.pack('<6I',0x03072dff,0x03072daf,0x03072d5f,0x03072d87,0x03072dd7,0x0307951c),
    0x030795b4:bytes.fromhex('7fb5094c'),
    0x03079b1e:bytes.fromhex('30b5b049'),
}
NAVIGATION_BROWSER_BASE={0x0307b31a:bytes.fromhex('0898dff8eca0')}
def validate_navigation_base(image):
    for module,sites in ((21,NAVIGATION_BASE),(31,NAVIGATION_BROWSER_BASE)):
        for address,expected in sites.items():
            offset,_=image.region(module,address)
            if image.d[offset:offset+len(expected)]!=expected:
                raise ValueError(f'navigation base changed at {module}:{address:08x}')

BROWSER_GEOMETRY={
    0x0307a442:('d7f7c7fe','00bf00bf'),
    0x0307a59a:('d7f71bfe','00bf00bf'),
    0x0307a486:('4ff02d0b','4ff00d0b'),
    0x0307a616:('2c20','0c20'),
    **{a:('4ff02001','4ff00001') for a in
       (0x0307a4e6,0x0307a536,0x0307a660,0x0307a6e8)},
}
def browser_geometry(image):
    for address,(before,after) in BROWSER_GEOMETRY.items():
        offset,_=image.region(31,address)
        if image.d[offset:offset+len(bytes.fromhex(before))]!=bytes.fromhex(before):
            raise ValueError(f'browser geometry base changed at {address:08x}')
        image.patch(31,address,bytes.fromhex(after))

BOOKMARK_STUB_TEXT=b'[ERROR] MLCD_DrawPoint: x=%d, y=%d is out of range\0'
NAVIGATION_HOLD_TEXT=b' \n>>>### watch dog isr coming<<<### \n\0\0\0'
LIBRARY_GEOMETRY_BASE={
    0x03079c22:'4ff023084ff07109',0x03079c42:'d8f7c7fa',
    0x03079c80:'1f21',0x03079c84:'d8f7a6fa',
    0x03079d5a:'4ff01f01',0x03079d66:'d8f735fa',
    0x0300e788:'00'*32,
}
MEDIA_GEOMETRY_BASE={50832150: '4d20', 50832424: '2c20', 50832444: '2c30', 50832746: '4ff02c08', 50832780: '2c30', 50832392: 'd7f7e4fe', 50832420: '1f27', 50832744: '1f27', 50832474: 'd7f7bbfe', 50832494: 'd7f7b1fe', 50832814: 'd7f711fe', 50832834: 'd7f707fe', 50832566: 'd7f78dfe', 50832906: 'd7f7e3fd', 50830912: '04f10c00fff795fca08904f10c0128b332e02781b8f8000064680025401c08bfbde8f087701981b204f10c00fff781fc'}
def validate_library_geometry(image):
    for module,sites in ((22,LIBRARY_GEOMETRY_BASE),(23,MEDIA_GEOMETRY_BASE)):
        for address,expected in sites.items():
            offset,_=image.region(module,address)
            data=bytes.fromhex(expected)
            if image.d[offset:offset+len(data)]!=data:
                raise ValueError(f'list geometry base changed at {module}:{address:08x}')

SETTINGS_GEOMETRY_BASE={50829112: '387810b1', 50829116: '012804d008e000221146812002e0002211468220d8f740fd', 50829148: 'd8f73afd', 50829462: 'd8f79dfc', 50829474: 'd8f797fc', 50829160: '2320', 50829484: '2325'}
def validate_settings_geometry(image):
    # The logo-only block becomes a local helper after the entry skips it.
    for address,value in SETTINGS_GEOMETRY_BASE.items():
        off,_=image.region(32,address);data=bytes.fromhex(value)
        if image.d[off:off+len(data)]!=data:
            raise ValueError(f'settings geometry base changed at {address:08x}')

PLAYER_SPEED_MENU_BASE={50390724: '759a0703',
 50828638: 'eef713fa',
 50829102: 'eef72bf9',
 50829108: 'f8f778fb',
 50829246: 'eef74ff8',
 50829304: 'eef732f8',
 50829450: 'eef77df8',
 50829564: 'edf7b0ff',
 50829640: 'edf78aff',
 50829996: '3d3d3d3d3d3d4d53475f5359535f5345545f444953504c41595f414c4c0a0000',
 50830040: 'f8f7a6f9',
 50831056: '4d53475f534352454e5f5550205365744d656e75536572766963650a00000000',
 50831376: 'edf7bafc',
 50832922: 'f7f705fc',
 50833004: 'edf78cf9',
 50833308: '5265714d656e75547874496e666f537472756374466c6167203d2025642c20536574646566203d20307825780a000000',
 50833396: 'fff7e2fb',
 50835294: 'f6f763ff',
 50836148: '5365745363726f6c6c696e67506c61796c6973742c6974656d4e756d2069732025640a00',
 50842878: 'f5f793f8',
 50842980: '4669696f50726f64756374496e666f57696e496e69740a00',
 50843368: 'f4f79ebf',
 50843544: '4669696f50726f64756374496e666f57696e4465496e69740a000000'}
def validate_player_speed_menu(image):
    for address,value in PLAYER_SPEED_MENU_BASE.items():
        off,_=image.region(32,address);expected=bytes.fromhex(value)
        if image.d[off:off+len(expected)]!=expected:
            raise ValueError(f'player speed menu base changed at {address:08x}')

def player_speed_label_space(image):
    checks={
        0x0307a2c8:b'Error: Cannot open LRC file: %s\n\0\0\0\0',
        0x0307a39c:b'No valid LRC time found for current playback position\n\0\0',
        0x0307a0f2:bytes.fromhex('75a0f7f798fe'),
        0x0307a258:bytes.fromhex('50a0f7f7e5fd'),
        0x0307ade8:bytes.fromhex('6b20adf83c00'),
    }
    for address,data in checks.items():
        off,_=image.region(27,address)
        if image.d[off:off+len(data)]!=data:
            raise ValueError(f'player speed label base changed at {address:08x}')
    # Other overlays have their own code at these addresses; they do not use
    # module27 backing. Resident/player/decoder references are forbidden.
    for module in (0,27,33):
        m=image.modules[module]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load'])
            data=bytes(image.d[off:off+m[kind+'_len']])
            for start,size in ((0x0307a2c8,36),(0x0307a39c,56)):
                if any(struct.pack('<I',a) in data for a in range(start,start+size)):
                    raise ValueError('player speed label cave referenced')
    for address in (0x0307a0f4,0x0307a25a):
        image.patch(27,address,bytes.fromhex('00bf00bf'))

def startup_invalidation_space(image):
    """Reclaim only the pinned SafePoweroff print; preserve all startup logic."""
    start,size=0x030733e0,35
    checks=((0,start,b'---1---gSysConfig.SafePoweroff=%d\n\0'),
            (0,0x030660ca,bytes.fromhex('2de9f043')),
            (1,0x0307a23a,bytes.fromhex('8248d4f84912f7f7f2fd')),
            (1,0x0307a444,struct.pack('<I',start)))
    for module,address,expected in checks:
        off,_=image.region(module,address)
        if image.d[off:off+len(expected)]!=expected:
            raise ValueError(f'startup invalidation base changed at {address:08x}')
    # Across every overlay, the sole absolute reference must remain the pinned
    # module1 printf literal. Also reject interior/unaligned pointer references.
    for module in image.modules:
        for kind in ('code','data'):
            off=image.l2f(module[kind+'_load'])
            data=bytes(image.d[off:off+module[kind+'_len']])
            for address in range(start,start+size):
                needle=struct.pack('<I',address);found=data.find(needle)
                while found>=0:
                    if (module['index'],kind,module[kind+'_exec']+found,address)!=(1,'code',0x0307a444,start):
                        raise ValueError('startup invalidation cave referenced')
                    found=data.find(needle,found+1)
    image.patch(1,0x0307a240,bytes.fromhex('00bf00bf'))

def player_controls_space(image):
    start,size=0x0307a3d4,36
    checks={start:bytes.fromhex('3d3d3d20456e64204d757369634c7263496e6974204465627567203d3d3d0a0a00000000'),
            0x0307a25e:bytes.fromhex('5da0f7f7e2fd'),
            0x0307a270:bytes.fromhex('4c52432066696c652073697a653a20256420627974657320286275666665722073697a653a202564290a0000'),
            0x0307a0aa:bytes.fromhex('71a0f7f7bcfe'),
            0x0300e6d4:bytes.fromhex('13950703')}
    for address,data in checks.items():
        off,_=image.region(27,address)
        if image.d[off:off+len(data)]!=data:
            raise ValueError('player controls diagnostic changed')
    for module in (0,27,33):
        m=image.modules[module]
        for kind in ('code','data'):
            off=image.l2f(m[kind+'_load']);data=bytes(image.d[off:off+m[kind+'_len']])
            for start,size in ((0x0307a3d4,36),(0x0307a270,44)):
                if any(struct.pack('<I',a) in data for a in range(start,start+size)):
                    raise ValueError('player controls cave referenced')
    image.patch(27,0x0307a260,bytes.fromhex('00bf00bf'))
    image.patch(27,0x0307a0ac,bytes.fromhex('00bf00bf'))

def navigation_hold_space(image):
    """Center-only timing; preserve watchdog handling beyond its debug print."""
    checks=((0x03065918,NAVIGATION_HOLD_TEXT),
            (0x030658b6,bytes.fromhex('18a0')),
            (0x030658b8,bytes.fromhex('0cf0b6fa')),
            (0x03065ec0,bytes.fromhex('401c2963')),
            (0x03004104,struct.pack('<4I',0x30000040,0,0,7)))
    for address,expected in checks:
        off,_=image.region(0,address)
        if image.d[off:off+len(expected)]!=expected:
            raise ValueError(f'navigation hold base changed at {address:08x}')
    # The sole PC-relative ADR above is pinned. Reject absolute references,
    # including unaligned pointers and pointers into the middle of the string.
    pointers=[struct.pack('<I',address) for address in range(0x03065918,0x03065940)]
    for module in image.modules:
        for kind in ('code','data'):
            if not module[kind+'_len']:continue
            off=image.l2f(module[kind+'_load'])
            data=bytes(image.d[off:off+module[kind+'_len']])
            if any(pointer in data for pointer in pointers):
                raise ValueError('navigation hold cave has an absolute reference')
    image.patch(0,0x030658b8,bytes.fromhex('00bf00bf'))
    image.patch(0,0x03004110,struct.pack('<I',5))

FEEDBACK_STUB_TEXT=b'[INFO] pLongFileName = \x00[INFO]  %c \x00'
SPEED_GUARD_ADDRESS=0x03072f54
SPEED_DONE_ADDRESS=SPEED_GUARD_ADDRESS+8
SPEED_STUB_TEXT=b'=== Frame Buffer Region: Cols %d-%d, Rows %d-%d (Buf: %dx%d) ===\r\n\0'
def speed_guard_space(image):
    """Reclaim only the audited framebuffer diagnostic; native drawing remains."""
    checks=((SPEED_GUARD_ADDRESS,SPEED_STUB_TEXT),
            (0x03052804,struct.pack('<I',SPEED_GUARD_ADDRESS)),
            (0x0305240e,bytes.fromhex('fd48')),
            (0x03052410,encode_t32_branch(0x03052410,0x03071e28,True)))
    for address,expected in checks:
        off,_=image.region(0,address)
        if image.d[off:off+len(expected)]!=expected:
            raise ValueError(f'speed guard diagnostic changed at {address:08x}')
    image.patch(0,0x03052410,bytes.fromhex('00bf00bf'))

SPEED_STATUS_TEXT=b'\n------1 file error------ \x00\x00\n------2 decode end------ \x00\x00'
def speed_status_space(image):
    checks=((0x030696d4,SPEED_STATUS_TEXT),
            (0x030695b4,bytes.fromhex('47a0')),
            (0x030695cc,bytes.fromhex('48a0')),
            (0x0306955e,bytes.fromhex('40f04081')))
    for address in (0x030695b6,0x030695ce):
        checks+=((address,encode_t32_branch(address,0x03071e28,True)),)
    for address,expected in checks:
        off,_=image.region(0,address)
        if image.d[off:off+len(expected)]!=expected:
            raise ValueError(f'speed status diagnostic changed at {address:08x}')
    for address in (0x030695b6,0x030695ce):
        image.patch(0,address,bytes.fromhex('00bf00bf'))

def bookmark_feedback(image):
    off,_=image.region(27,0x0307a014)
    if image.d[off:off+36]!=FEEDBACK_STUB_TEXT:
        raise ValueError('feedback diagnostic changed')
    for address in (0x03079e50,0x03079e5e):
        off,_=image.region(27,address)
        if image.d[off:off+4]!=encode_t32_branch(address,0x03071e28,True):
            raise ValueError('feedback diagnostic caller changed')
        image.patch(27,address,bytes.fromhex('00bf00bf'))

def bookmark_gesture(image):
    off,_=image.region(0,0x03052d68)
    if image.d[off:off+len(BOOKMARK_STUB_TEXT)]!=BOOKMARK_STUB_TEXT:
        raise ValueError('bookmark resident diagnostic changed')
    # Remove only the diagnostic tail-call; out-of-bounds pixels still return.
    off,_=image.region(0,0x03052c9c)
    if image.d[off:off+4]!=encode_t32_branch(0x03052c9c,0x03071e28,False):
        raise ValueError('bookmark diagnostic caller changed')
    image.patch(0,0x03052c9c,bytes.fromhex('704700bf'))
    # Both key modes share the native query/add/remove route and continuation.
    for address in (0x030638ac,0x030638ee):
        off,_=image.region(0,address)
        if image.d[off:off+4]!=encode_t32_branch(address,0x030686e0,True):
            raise ValueError('favorite gesture caller changed')
        image.patch(0,address,encode_t32_branch(address,0x03052d68,True))

# Audited zero backing: tail of refresh sort A plus first 3KiB of sort B.
# Runtime browser bound is independent and remains below the active decoder.
BROWSER_SORT_FLASH_START,BROWSER_SORT_FLASH_END=0x3c800,0x42348
BROWSER_SORT_START,BROWSER_SORT_END=0x0307b874,0x03080470

BROWSER_SORT_HOOKS={
    'browser_sort_enumerate':(0x03079592,'2de9ff4f'),
    'browser_sort_count':(0x0307974e,'70b50c46'),
    'browser_sort_select':(0x0307acf8,'94f84e50'),
    'browser_sort_ordinal':(0x0307ad18,'00f0f080'),
}

def apply_browser_sort(stock,image,directory):
    import json
    manifest=json.loads((directory/'manifest.json').read_text())
    names=['browser_sort.bin','playback.bind']+[name+'.patch' for name in BROWSER_SORT_HOOKS]
    if set(manifest)!=set(names):raise ValueError('browser sort manifest entries changed')
    artifacts={name:(directory/name).read_bytes() for name in names}
    if any(hashlib.sha256(data).hexdigest()!=manifest[name] for name,data in artifacts.items()):
        raise ValueError('browser sort artifact mismatch')
    binding=json.loads(artifacts['playback.bind'])
    length=binding['bytes']
    if not isinstance(length,int) or not 16<=length<=FLASH_END-FLASH_START or hashlib.sha256(image.d[FLASH_START:FLASH_START+length]).hexdigest()!=binding['sha256']:
        raise ValueError('browser sort playback binding mismatch')
    patches=[]
    for name,(address,expected) in BROWSER_SORT_HOOKS.items():
        lines=[line for line in artifacts[name+'.patch'].decode().splitlines() if line and not line.startswith('#')]
        if len(lines)!=1:raise ValueError('browser sort patch format changed')
        module,target,hexdata=lines[0].split(':')
        module,target,data=int(module),int(target,16),bytes.fromhex(hexdata)
        if (module,target,len(data))!=(31,address,4):raise ValueError('browser sort hook bounds changed')
        off,_=image.region(31,address)
        if bytes(image.d[off:off+4])!=bytes.fromhex(expected):raise ValueError('browser sort hook base changed')
        patches.append((address,data))
    # Validate payload, original module records and backing before any mutation.
    staged=Image(bytes(image.d))
    relocate_browser_sort(stock,staged,artifacts['browser_sort.bin'])
    for address,data in patches:staged.patch(31,address,data)
    image.d=staged.d;image.modules=staged.modules

def relocate_browser_sort(stock,image,payload):
    """Move already-patched module31 code into checked refresh-buffer backing."""
    if hashlib.sha256(stock.d).hexdigest()!=STOCK_SHA256:
        raise ValueError('browser sort requires pinned stock')
    if image.modules!=stock.modules:
        raise ValueError('browser sort module table changed')
    m=image.modules[31];original=stock.modules[31]
    if (m['code_exec'],m['code_len'],m['data_exec'],m['data_len'],m['bss_exec'],m['bss_len'])!=(0x03079418,9308,0x0300e6bc,128,0x0300e73c,2150):
        raise ValueError('browser sort native table changed')
    start,end=BROWSER_SORT_FLASH_START,BROWSER_SORT_FLASH_END
    if any(stock.d[start:end]) or any(image.d[start:end]):
        raise ValueError('browser sort backing occupied')
    if len(image.d)!=len(stock.d) or image.sections!=stock.sections or image.fw_len!=stock.fw_len:
        raise ValueError('browser sort firmware layout changed')
    refresh=stock.modules[40]
    execution=refresh['code_exec']+start-stock.l2f(refresh['code_load'])
    if start<FLASH_END or execution!=0x0308672c or execution+end-start!=0x0308c274:
        raise ValueError('browser sort leaves verified refresh buffer')
    if any(x['offset']<end and x['offset']+x['length']>start for x in stock.sections):
        raise ValueError('browser sort overlaps resource')
    if len(payload)<16 or len(payload)%4 or len(payload)>end-start-m['code_len']:
        raise ValueError('browser sort payload length invalid')
    magic,entry,code_end,bss_end=struct.unpack_from('<4I',payload)
    if magic!=0x314f5342 or not entry&1 or not BROWSER_SORT_START+16<=entry&~1<code_end:
        raise ValueError('browser sort header invalid')
    if code_end!=BROWSER_SORT_START+len(payload) or not code_end<=bss_end<=BROWSER_SORT_END:
        raise ValueError('browser sort runtime bounds invalid')
    old=image.l2f(original['code_load']);native=bytes(image.d[old:old+m['code_len']])
    merged=native+payload
    image.d[start:start+len(merged)]=merged
    # The native loader reads code_load and data_load independently. Keep data
    # and low-RAM BSS untouched; copied metadata invalidates high NOLOAD state.
    m['code_load']=image.load_base+start-0x200;m['code_len']=len(merged)
    table=0x208+31*32
    struct.pack_into('<I',image.d,table,m['code_load'])
    struct.pack_into('<I',image.d,table+8,m['code_len'])

def integrate(stock_data,input_data,directory,date,sort_directory=None):
    """Build the audiobook test image; reject mismatched base or hook layout."""
    from datetime import datetime
    datetime.strptime(date,'%Y%m%d')
    loader=read_patch(directory/'loader.patch')
    if loader[:2]!=(0,LOADER_ADDRESS):raise ValueError('loader location changed')
    image=Image(stage(stock_data,input_data,(directory/'playback.bin').read_bytes(),loader[2]))
    bookmark_gesture(image)
    bookmark_feedback(image)
    speed_guard_space(image)
    speed_status_space(image)
    validate_settings_geometry(image)
    validate_player_speed_menu(image)
    player_speed_label_space(image)
    player_controls_space(image)
    startup_invalidation_space(image)
    validate_library_geometry(image)
    navigation_hold_space(image)
    stock=Image(stock_data)
    validate_navigation_base(image)
    discovery(image)
    browser_geometry(image)
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
    from approved_icons import apply_icons
    from rknano_fw import LANGS
    apply_icons(image,stock)
    for language in range(len(LANGS)):
        image.patch_lang(language,0x83,'Audiobooks\0'.encode('utf-16le'))
        image.patch_lang(language,0x84,'Meditation\0'.encode('utf-16le'))
    image.patch(32,0x0307cf14,'P4e\0'.encode('utf-16le'))
    apply_browser_sort(stock,image,sort_directory if sort_directory is not None else directory.parent/'browser_sort')
    image.set_date(date);image.finalize()
    return bytes(image.d)
