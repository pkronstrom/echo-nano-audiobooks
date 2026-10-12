#!/usr/bin/env bash
# Experimental playback payload. Not included in delivery image until UI/queue integration.
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
