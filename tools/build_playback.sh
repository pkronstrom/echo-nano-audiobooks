#!/usr/bin/env bash
# Playback payload and native hooks, included by the separate audiobook target.
set -euo pipefail
out=${1:-out/playback}
mkdir -p "$out/obj"
flags=(-mthumb -mcpu=cortex-m3 -Os -std=gnu11 -ffreestanding -fno-common
       -fno-strict-aliasing -fstack-usage -Wall -Wextra -Werror -Isrc -Iplayback)
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
out = Path(sys.argv[1])
lines = [f".equ PLAYBACK_BYTES, {len((out/'playback.bin').read_bytes())}"]
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
