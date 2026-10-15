#!/usr/bin/env bash
# Browser overlay extension only; no firmware staging or device operations.
set -euo pipefail
out=${1:-out/browser_sort}
mkdir -p "$out/obj"
flags=(-mthumb -mcpu=cortex-m3 -Os -std=gnu11 -ffreestanding -fno-common
       -fno-strict-aliasing -fstack-usage -ffunction-sections -fdata-sections
       -Wall -Wextra -Werror -Isrc -Ibrowser_sort)
objs=()
for source in browser_sort/*.c browser_sort/*.S src/libc.c; do
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
files=['browser_sort.bin']+[n+'.patch' for n in names]
manifest={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in files}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
MANIFEST
