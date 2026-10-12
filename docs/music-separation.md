# Music separation: P1a

Historical checkpoint. [P1b](playback-containment.md) adds File Browser containment.

P1a adds recursive `.nomusic` exclusion to media-library refresh. Place an empty
file named `.nomusic` inside each audiobook or meditation root, then run **Media
Library → Media Library Refresh**. The whole subtree is omitted from library
views and the main-menu Shuffle pool. Remove the marker and refresh to include
it again. Names are case-insensitive; no folder renaming is required.

Files and on-card attributes are never changed by the filter. Deliberate access
through File Browser remains available. A marker at the storage root excludes
all library content, including the separate RECORD pass.

**P1a limitation:** physical File Browser playback still has upstream whole-card
shuffle/folder-jump behavior and can enter excluded folders. Use the main-menu
Shuffle or filtered library for music separation in this increment. Playback
scope protection is the next increment. M3U playback and per-book resume remain
unimplemented. This is a host-verified experimental image; no device test or
flash has been performed.

## Artifacts and identity

- Custom: `builds/phase1a/custom/NANOV170.IMG`, About `P1a`, date `20260827`.
- Stock-code recovery: `builds/phase1a/recovery/NANOV170.IMG`, date `20260828`.
- Hashes and source commit: `builds/phase1a/manifest.json`.
- Source checkpoint: `phase1a-library-exclusion`.

See [baseline recovery instructions](baseline.md) for the installed-date check,
manual update procedure and recovery. These dates build on the preserved Phase 0
images; a device already running a newer-dated image needs appropriately rebuilt
custom and recovery images. No image is copied to a player automatically.

## Verification

24 checks pass: 14 C filter fixtures, four ARM-emulated integration checks and
six binary image checks. The ARM tests execute compiled hooks and original stock
folder counters, substituting the raw directory-reader trampoline entry points
and watchdog. Actual stock sector I/O, cursor-cache behavior, complete refresh,
playback and device recovery have not been executed by these tests.

Clean rebuilding produces byte-identical custom firmware. Stock hash validation,
CRC/header checks and the default stock-power profile remain enforced. Reader
prologues are checked at build time before using displaced-instruction trampolines.

The refresh blob occupies 6,212 staged bytes and ends at RAM `0x0309fbc0`, leaving
1,072 bytes below the reserved reboot flag. The sort key cache is reduced from
two windows to one to make room; this can increase sort reads. Measure refresh
performance on the device. `CFWLOG.TXT` reports `nomusic probe errors`; failed or
bounded-out marker probes omit the affected tree rather than admitting it.

## Device checks for this increment

Use a small collection containing music, a marked audiobook with nested chapter
folders, and marked meditation folders. Refresh and confirm library counts,
artists/albums and main-menu Shuffle contain only music. Explicitly browse and
play a chapter and a meditation track. Remove a marker, refresh, and check the
tracks return. Test a root marker, an empty library, FAT and exFAT where available,
and capture `CFWLOG.TXT`. Physical File Browser continuation is still the stated
P1a limitation.

To repeat host checks, build custom and recovery images, install
`unicorn==2.1.4` into an isolated Python environment, and run:

```sh
python -m unittest discover -s tests -v
```

On this Mac, Unicorn requires execution outside the Codex sandbox to initialize
its host CPU cache; the sandboxed process crashes before firmware execution.
