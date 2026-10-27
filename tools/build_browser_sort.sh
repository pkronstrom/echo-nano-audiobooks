#!/usr/bin/env bash
# Browser overlay extension only; no firmware staging or device operations.
set -euo pipefail
# Globs set the link order, so the image must not depend on the locale.
export LC_ALL=C
out=${1:-out/browser_sort}
mkdir -p "$out/obj"
python3 - "$out" <<'BIND'
from pathlib import Path
import hashlib,json,struct,subprocess,sys,tempfile

# Read local symbols too: the menu's byte-sized `active` is distinct from the
# unrelated four-byte local of the same name. Refuse missing/ambiguous matches.
def resident_bindings(symbol_table,payload):
    start,end=0x03092400,0x0309fff0
    if len(payload)<16:
        raise ValueError('resident binding payload is truncated')
    magic,entry,bss_start,bss_end=struct.unpack_from('<4I',payload)
    if (magic!=0x32504e45 or not entry&1 or
            not start+16<=entry&~1<bss_start or
            bss_start!=start+len(payload) or not bss_start<=bss_end<=end):
        raise ValueError('resident binding payload bounds changed')
    rows=[]
    for line in symbol_table.splitlines():
        fields=line.split()
        if len(fields)==4:
            value,size,kind,name=fields
            rows.append((name,kind,int(size,16),int(value,16)))
    requests=(
        ('FOLDER_LAUNCH_ADDR','playback_folder_launch','T',None),
        ('BOOK_NAV_INIT_ADDR','navigation_browser_init','T',None),
        ('BOOK_NAV_EVENT_ADDR','navigation_event','T',None),
        ('BOOK_DIRECTORY_ADDR','playback_browser_directory','T',None),
        ('BOOK_LOOKUP_ADDR','playback_lookup','T',None),
        ('BOOK_WRITE_TRY_ADDR','journal_try_write','T',None),
        ('BOOK_WRITE_END_ADDR','journal_end_write','T',None),
        ('BOOK_CRC_ADDR','book_crc','T',None),
        ('BOOK_OPEN_ADDR','playback_open','T',None),
        ('BOOK_READ_ADDR','playback_read','T',None),
        ('BOOK_CLOSE_ADDR','playback_close','T',None),
        ('BOOK_ROOTS_ADDR','roots','b',0x160),
        ('BOOK_ROOT_COUNT_ADDR','root_count','b',1),
        ('BOOK_CHOOSER_ADDR','chooser','b',1),
        ('BOOK_MENU_ACTIVE_ADDR','active','b',1),
        ('BOOK_MENU_RETURNING_ADDR','returning','b',1),
    )
    bound={}
    for macro,name,kind,size in requests:
        matches=[(length,value) for n,t,length,value in rows
                 if n==name and t==kind and (size is None or size==length)]
        if len(matches)!=1:
            raise ValueError('resident binding missing or ambiguous: '+name)
        length,value=matches[0]
        low,high=(start+16,bss_start) if kind=='T' else (bss_start,bss_end)
        if not length or value<low or value+length>high or (kind=='T' and value&1):
            raise ValueError('resident binding outside payload: '+name)
        bound[macro]=value
    return bound

if __name__=='__main__':
    out=Path(sys.argv[1]);play=out.parent/'playback'
    payload=(play/'playback.bin').read_bytes()
    # A stale ELF must never supply addresses for a different resident binary.
    with tempfile.TemporaryDirectory(prefix='browser-resident-bind-') as temporary:
        extracted=Path(temporary)/'resident.bin'
        subprocess.run(['arm-none-eabi-objcopy','-O','binary',str(play/'playback.elf'),str(extracted)],check=True)
        if extracted.read_bytes()!=payload:
            raise ValueError('resident binding ELF and payload disagree')
    symbols=subprocess.check_output(['arm-none-eabi-nm','-S','--defined-only',str(play/'playback.elf')],text=True)
    bound=resident_bindings(symbols,payload)
    digest=hashlib.sha256(payload).hexdigest()
    header='/* Resident ELF bindings; payload SHA256 '+digest+' */\n'
    header+=''.join('#define %s 0x%x\n' % item for item in bound.items())
    (out/'browser_playback.h').write_text(header)
    (out/'playback.bind').write_text(json.dumps({'bytes':len(payload),'sha256':digest}))

BIND
flags=(-mthumb -mcpu=cortex-m3 -Os -std=gnu11 -ffreestanding -fno-common
       -fno-strict-aliasing -fstack-usage -ffunction-sections -fdata-sections
       -Wall -Wextra -Werror -DBROWSER_ORDER_CAPACITY=64 -Isrc -Ibrowser_sort -Iplayback -I"$out")
objs=()
for source in browser_sort/*.c browser_sort/*.S src/libc.c experiments/auto_book_prepare/playlist.c experiments/native_file_creation/guarded_create.c; do
    object="$out/obj/$(basename "${source%.*}").o"
    arm-none-eabi-gcc "${flags[@]}" -c "$source" -o "$object"
    objs+=("$object")
done
arm-none-eabi-gcc -mthumb -mcpu=cortex-m3 -nostdlib -T browser_sort/link.ld \
    -Wl,-Map="$out/browser_sort.map" -Wl,--no-warn-rwx-segments \
    -o "$out/browser_sort.elf" "${objs[@]}" -lgcc
arm-none-eabi-objcopy -O binary "$out/browser_sort.elf" "$out/browser_sort.bin"
arm-none-eabi-nm -g "$out/browser_sort.elf" > "$out/browser_sort.nm"
arm-none-eabi-size "$out/browser_sort.elf"
python3 - "$out" <<'SYMS'
from pathlib import Path
import sys
out=Path(sys.argv[1]);lines=[]
for line in (out/'browser_sort.nm').read_text().splitlines():
    value,kind,name=line.split()
    if kind.upper() in ('T','B','D','R','A'):
        lines.append(f'.equ {name}, 0x{value}')
(out/'browser_sort_syms.inc').write_text('\n'.join(lines)+'\n')
SYMS
for source in browser_sort/hooks/*.S; do
    name=$(basename "${source%.S}")
    tools/asm2patch.sh "$source" "$out/$name.patch" "$out" > "$out/$name.disassembly"
done
python3 - "$out" <<'MANIFEST'
from pathlib import Path
import hashlib,json,sys
out=Path(sys.argv[1])
names=['browser_sort_enumerate','browser_sort_count','browser_sort_select','browser_sort_ordinal']
files=['browser_sort.bin','playback.bind']+[n+'.patch' for n in names]
manifest={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in files}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
MANIFEST
