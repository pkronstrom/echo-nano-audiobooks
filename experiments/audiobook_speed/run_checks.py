#!/usr/bin/env python3
"""Host sanitizer checks and optional standalone Cortex-M3 size measurement."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--arm', action='store_true', help='also measure standalone Cortex-M3 code and state')
args = parser.parse_args()
here = Path(__file__).resolve().parent
root = here.parents[1]
with tempfile.TemporaryDirectory(prefix='echo-speed-') as directory:
    work = Path(directory)
    binary = work / 'test_speed'
    subprocess.run(['clang', '-O1', '-g', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fno-omit-frame-pointer', '-fsanitize=address,undefined', '-DSPEED_TEST_METRICS',
                    str(here / 'speed.c'), str(here / 'test_speed.c'),
                    '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    if args.arm:
        toolchain = root / 'builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin'
        gcc = str(toolchain / 'arm-none-eabi-gcc')
        flags = ['-mthumb', '-mcpu=cortex-m3', '-Os', '-std=c11', '-ffreestanding',
                 '-ffunction-sections', '-fdata-sections', '-fstack-usage', '-Wall', '-Wextra', '-Werror']
        obj = work / 'speed.o'
        subprocess.run([gcc, *flags, '-c', str(here / 'speed.c'), '-o', str(obj)], check=True)
        # A dummy global represents caller-owned state in this standalone size
        # artifact. No such global is present in the actual reusable core.
        census = work / 'census.c'
        census.write_text('#include "speed.h"\nchar state_size[sizeof(speed_state)];\n')
        census_obj = work / 'census.o'
        subprocess.run([gcc, *flags, '-I', str(here), '-c', str(census), '-o', str(census_obj)], check=True)
        elf = work / 'speed.elf'
        subprocess.run([gcc, '-mthumb', '-mcpu=cortex-m3', '-nostdlib',
                        '-Wl,--gc-sections,-e,speed_process,-u,speed_init,-u,speed_reset,-u,speed_packet_init,-u,speed_packet_position,-u,state_size',
                        str(obj), str(census_obj), '-lc', '-lgcc', '-o', str(elf)], check=True)
        subprocess.run([str(toolchain / 'arm-none-eabi-size'), str(obj), str(elf)], check=True)
        print('Compiler stack estimates (individual functions; not interrupt nesting):', flush=True)
        print((work / 'speed.su').read_text(), end='', flush=True)
        unresolved = subprocess.check_output([str(toolchain / 'arm-none-eabi-nm'), '-u', str(elf)], text=True)
        if unresolved.strip():
            raise SystemExit('Unresolved target symbols:\n' + unresolved)
