#!/usr/bin/env bash
# Playback payload and native hooks, included by the separate audiobook target.
set -euo pipefail
# Globs set the link order, so the image must not depend on the locale.
export LC_ALL=C
out=${1:-out/playback}
mkdir -p "$out/obj"
python3 - "$out" <<'ICONS'
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from approved_icons import icon_bytes
Path(sys.argv[1], 'navigation_icons.inc').write_text('\n'.join(
    'static const u8 navigation_%s_icon[40]={%s};' % (name, ','.join(map(str, icon_bytes(kind))))
    for name,kind in [('book','books'),('meditation','meditation')]))
ICONS
flags=(-mthumb -mcpu=cortex-m3 -Os -std=gnu11 -ffreestanding -fno-common
       -fno-strict-aliasing -fstack-usage -Wall -Wextra -Werror -Isrc -Iplayback -I"$out")
objs=()
for source in playback/*.c playback/*.S src/libc.c; do
  object="$out/obj/$(basename "${source%.*}").o"
  arm-none-eabi-gcc "${flags[@]}" -c "$source" -o "$object"
  objs+=("$object")
done
arm-none-eabi-gcc -mthumb -mcpu=cortex-m3 -nostdlib -T playback/link.ld \
  -Wl,-Map="$out/playback.map" -Wl,--no-warn-rwx-segments \
  -o "$out/playback.elf" "${objs[@]}" -lgcc
arm-none-eabi-objcopy -O binary "$out/playback.elf" "$out/playback.bin"
arm-none-eabi-nm -g "$out/playback.elf" > "$out/playback.nm"
arm-none-eabi-size "$out/playback.elf"

python3 - "$out" <<'SYMS'
from pathlib import Path
import sys
sys.path.insert(0,'tools')
from playback_layout import FLASH_START
out = Path(sys.argv[1])
lines = [f".equ PLAYBACK_BYTES, {len((out/'playback.bin').read_bytes())}",
         f".equ PLAYBACK_FLASH_OFFSET, {FLASH_START-512}"]
for line in (out/'playback.nm').read_text().splitlines():
    value, kind, name = line.split()
    if kind.upper() in ('T','B','D','R'):
        lines.append(f".equ {name}, 0x{value}")
(out/'playback_syms.inc').write_text('\n'.join(lines)+'\n')
SYMS

for source in playback/hooks/*.S; do
  name=$(basename "${source%.S}")
  tools/asm2patch.sh "$source" "$out/$name.patch" "$out" > "$out/$name.disassembly"
done
