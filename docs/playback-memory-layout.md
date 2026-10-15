# Playback overlay layout — offline expansion audit

The bookmark foundation originally left36 bytes in an18780-byte payload area.
That lower boundary came from taking the largest end address of **all** modules,
including media-library refresh. Playback and refresh already have mutually
exclusive hook/code lifetimes, so that conservative boundary was unnecessarily
restrictive for playback. The reboot flag boundary remains unchanged.

## New placement

| Region | Bounds | Purpose |
| --- | --- | --- |
| Playback RAM | `0x03092400..0x0309fff0` | Code and persistent playback state |
| Reboot flag | `0x0309fff0..0x030a0000` | Preserved, never allocated |
| Playback flash staging | file `0x36200..0x3e200` | 32 KiB, sector aligned |
| Staging when module40 is loaded | `0x0308012c..0x0308812c` | Part of first refresh sort buffer |
| Existing refresh blob | starts `0x0307b674` in module40 | Unchanged6320-byte staged copy |
| Existing refresh execution RAM | starts `0x0309b694` | Unchanged |

Every nonempty stock module code/data/BSS interval was checked. The only declared
owner overlapping the new playback RAM is module40's code/sort-buffer range
`0x030797ec..0x0309b694`. The highest other code end is module62 at
`0x03092234`, below the new playback start. `tools/playback_layout.py` enforces
this owner set against the pinned stock image on every build.

The flash interval is all zero in pinned stock, remains clear in the input base
image, and lies wholly inside module40's first64 KiB sort buffer
`0x0307b674..0x0308b674`. That buffer already stages the refresh blob; refresh
clears it before sorting. Image generation checks the interval, rejects occupied
staging, and preserves the original refresh blob/hooks. Firmware size, module
records, resources and upper RAM bound remain unchanged. There are no bootloader
changes.

## Ownership transition

Loading module40 replaces the lower-address browser/player branch sites before
its forward copy reaches the new playback header. The bytes loaded at that
header are not `ENP2`, invalidating playback. The refresh stub then copies its
own unchanged blob into its original high RAM and clears its own BSS.

On subsequent playback entry, the resident loader sees the invalid signature,
reads the relocated payload in whole sectors, verifies magic and clears the new
playback BSS. Queue/bookmark context is intentionally reset across refresh.
The resident save guards now derive their address from `playback_header`, rather
than split hardcoded MOVW/MOVT constants. A regression caught those old literals
during this relocation before hardware use.

Changing the flash constant initially made the assembler choose a wider MOV
instruction instead of a literal LDR. The existing loader-length check rejected
that build. An explicit literal label restores the84-byte loader layout; image
staging additionally rejects stale RAM and flash literals as well as stale
length/entry addresses. Keep these guards.

## Verification and limits

Tests check all module intervals, exact image changes, preserved resources and
refresh patch bytes, loader pairing, and stock-reader loading from both firmware
slots. The refresh lifecycle test loads actual module40 bytes into emulated RAM,
executes `cfw_stub`, then reloads playback through the actual resident byte reader
and initializer. It checks that BSS resets and the reboot marker survives.

These checks establish declared layout and the exercised synchronous lifecycle.
They do not prove undocumented DMA/dynamic use, every interrupt interleaving or
hardware acceptance. No relocated image has been installed on the device.
Do not reuse this layout for another stock version without repeating the audit.

## Resident gesture bridge

The favorite bridge also needs48 resident bytes when playback is absent. It uses
0x03052d68..0x03052d98 from the51-byte pixel bounds diagnostic. The sole identified
reference is the ADR at0x03052c9a; its tail printf at0x03052c9c is disabled with
`bx lr; nop`. No new RAM region is claimed. Build checks validate the complete
original diagnostic and both native favorite-query call sites before replacing
anything. A missing ENP2 header falls back to the original query without touching
payload pointers or changing the native r0 argument. Emulator tests execute the
out-of-range draw return and both favorite routes. This audit is not proof
against unobserved runtime users of those bytes.


## Current controls/live-speed candidate — 2026-10-15

The latest offline payload occupies24096B code/data plus32176B BSS at the same
playback base. It ends at0x0309ffd0, leaving32B before the preserved reboot flag.
This is static allocation headroom, not stack headroom. Known initial native
SP0x03004000 remains far below this area; complete native/IRQ stack high-water
is not established. Do not expand the upper limit to add features.

Current regression coverage still includes exact stock-byte-reader loading,
BSS initialization, reboot-marker preservation and the refresh/reload lifecycle.
Earlier statements in this document that no relocated build was installed refer
to the original audit: installed20261025 uses this placement and boots; the new
controls/live-speed20261027 candidate itself remains uninstalled.
