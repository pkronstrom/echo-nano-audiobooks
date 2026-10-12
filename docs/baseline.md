# Phase 0 baseline: host evidence and recovery

## Provenance

Upstream: [NaniteCFW](https://github.com/maaraneasi/nanitecfw), pinned revision
`ea4e6dc2cb386483093c7b045b6e85f26939ce2e` (12 October 2026).
The Git history is imported locally, with an `upstream` remote; no commits or
remote writes were made for this project work.

Stock image downloaded from the v1.7.0 link on
[FiiO's official firmware page](https://forum.fiio.com/note/showNoteContent.do?id=202605161533005115232):
`https://fiio-firmware.fiio.net/ECHO%20NANO/ECHO%20NANO%20V1.7.0.zip`.
The extracted `NANOV170.IMG` is 11,534,340 bytes, dated 20260824, SHA-256
`54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
Stock CRC is `0xec510f0a`; its duplicated header matches.

The exact hash gate remains enabled. Do not use `--any-input` to adapt an image
from another firmware version or from an Echo Mini.

## Build profile

The only firmware build-policy change is that `POWER_SAVE=0` excludes
`patches/power_idle.patch` and `patches/power_clocks.patch` by default.
This retains stock CPU clock requests, sleep gating and scroll-wheel polling at
every site listed in those patches. `POWER_SAVE=1` opts into the upstream patches;
that option has not been device-tested or built for delivery here. Other values
are rejected. Other upstream patches, including artist/recent-album views and
unsupported-track skipping, are retained as the community baseline.

About still uses upstream's `6.0.5` string. It does not identify this local profile;
use the artifact manifest and image hash to identify the baseline. The refresh
log says `6.0.4` in upstream source; this discrepancy was left unchanged.

Build toolchain used: GNU make 4.4.1 and Arm GNU Toolchain 13.2.rel1,
`arm-none-eabi-gcc` 13.2.1. Tools were downloaded/compiled in `/private/tmp`, without
installing Homebrew packages or modifying global configuration. These temporary
tools can disappear; normal durable setup is the upstream documented Homebrew
installation (`make`, Python, `gcc-arm-embedded`).

To reproduce with that standard setup:

```sh
gmake check
gmake POWER_SAVE=0 DATE=20260825
gmake recovery DATE=20260826
python3 -m unittest discover -s tests -v
```

For the tools used in this session:

```sh
export PATH=/private/tmp/echo-nano-tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin:$PATH
/private/tmp/echo-nano-tools/local/bin/make POWER_SAVE=0 DATE=20260825
/private/tmp/echo-nano-tools/local/bin/make recovery DATE=20260826
python3 -m unittest discover -s tests -v
```

Keep the pristine stock file at the repository root; it is ignored by Git.
The above dates reproduce the artifacts, and are not a recommendation for flashing
over an unknown installed custom firmware. The tests expect the default
conservative profile and a recovery date greater than the custom date.

## Validation record

On 12 October 2026:

- Stock exact-hash check, CRC and header copy: passed.
- C compilation with upstream `-Wall -Wextra -Werror`, linking and Thumb-2 patch
  assembly: passed.
- Custom CRC `0x6dc00973` and duplicated header: passed.
- Same-date second build: byte-identical to the first build.
- Six binary integration checks: passed. They verify stock identity, all three
  image CRCs/headers, every power-patch region staying stock, shuffle-scope bytes,
  date-only recovery equivalence and rejection of modified stock input.
- Invalid `POWER_SAVE` value: rejected by make before building.
- No device flash, playback, restart or library refresh was performed.

The linker reports 5,164 staged bytes and refresh RAM ending at `0x0309fcc0`,
leaving **816 bytes** below `0x0309fff0`. This is compiler/profile-specific and
does not include a proof of runtime stack safety or memory ownership during playback.

Preserved artifacts: `builds/phase0/custom/NANOV170.IMG`,
`builds/phase0/recovery/NANOV170.IMG`, build and test logs, source snapshot and
`builds/phase0/manifest.json`. Preserve that directory before `make clean` or
later experimentation. Firmware binaries are never committed.

## Installation and recovery: pending device checkpoint

First record the device's About version and any previously flashed image date.
The bootloader date rule is documented upstream; the installed date cannot be
inferred from a version label alone. Choose a custom date newer than what was
installed, then prepare and verify a recovery image with a still-newer date.
Avoid distant future dates that could prevent a later official update from booting.

FiiO directs removing the microSD card before updating. Copy the selected image
to the root of internal storage, safely eject, and restart. This is a manual step
after the installed-version checkpoint. Check About and refresh the media library
with the test card afterward. For recovery, use the date-adjusted stock image
built with `gmake recovery DATE=<newer-date>`, not the original older stock image.
Upstream's recovery experience is not a guarantee; no local recovery flash was tested.

If the device freezes, the
[official FAQ](https://www.fiio.com/newsinfo/1132454.html) describes holding power
for ten seconds to force a reboot. That does not establish recovery from every
firmware failure.

## Short device checklist

Use a small expendable test collection and preserve the real card unchanged.

1. Confirm ordinary music and FLAC meditation playback, volume, wheel, next/previous,
   long-press seeking, folder selection and shutdown/restart.
2. Refresh the library; capture `CFWLOG.TXT`, especially write errors, counters and timings.
3. Start the main-menu Shuffle item. Check movement across artists/albums/folders,
   end-of-track continuation and an empty-card case. At this baseline books and
   meditations are still in the pool; music separation is not implemented.
4. Exercise folder navigation with shuffle enabled and check how its scope changes.
5. Reboot and check startup/resume. Upstream does not preserve shuffle order.
6. Note unsupported-file freezes, artist-list selection collisions, and back-navigation
   quirks reported upstream. Do not deliberately include suspected freezing files
   in the first baseline check.
