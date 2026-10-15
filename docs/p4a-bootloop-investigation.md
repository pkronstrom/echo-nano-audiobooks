# P4a boot-loop investigation

2026-10-14. Stock was restored and the user confirmed the normal menu. This
investigation has sent no further USB commands or firmware writes.

## Established facts

The failed installed image was not corrupted in transit: both complete11MiB
application regions matched P4a byte for byte. Restoring stock resolved the boot
loop. This implicates the custom image, but does not identify a specific patch.

The new main-menu hook is module21 address0x030794ac. It replaces the stock
`movs r1,#100; strh r1,[r0,#28]` with a call to0x03079600. That trampoline calls
the resident payload loader and, on success, `navigation_menu_init`, which
synchronously scans the current filesystem and installs runtime menu tables and
branches. It runs before the stock menu initializer returns.

The existing navigation tests directly exercise payload routines and the loader
trampoline, but mock raw directory reads, filesystem locks, watchdog service and
payload flash reads. Their success does not verify the complete cold-start
storage/interrupt path. In particular, the device test had no SD card; this is a
condition to investigate, not proof of a missing-card bug. The FAT code supports
filesystem types0/1 as well as2; do not label type0 alone as unmounted.

No root cause has been proven. Do not claim that scanning, icons, RAM placement,
watchdog timing or the lack of SD card caused the loop without further evidence.

## Prepared single-change diagnostic

Builder: `builds/bootloop-audit/build_menu_bypass.py`.
Image: `builds/bootloop-audit/diagnostic/menu-bypass-20261015.IMG`.
SHA256: `b339324b122ef6029f0a98a2bd51397f98fe66c2853a77f1571da8c416b36c48`.

Only the four bytes at module21 address0x030794ac are restored to stock.
Build-date fields and the package CRC also change. All other bytes match the
failed P4a candidate. An exhaustive difference check, duplicate-header check and
package CRC check passed. Manifest records exact changed offsets. The About
label remains P4a intentionally; use the hash/date to distinguish this diagnostic.

Paired stock restore date20261016:
`builds/bootloop-audit/diagnostic/stock-restore-20261016.IMG`, SHA256
`4e1600df372722863d9e919ed3c151c889859456cbbfbacaa0702688a7ae54fb`.
It is verified stock with date/checksum changes. Neither file has been flashed.
The earlier guarded restore runner is pinned to the earlier recovery payload;
it must not be reused with this newer pair without updating and checking its
preconditions against the actual device state.

This disables automatic optional-category setup at the main menu. It retains
other P4a changes, including icons and browser/player hooks. It is an isolation
experiment, not a fixed or release-ready firmware.

## Next checkpoint and interpretation

A hardware boot check is needed to distinguish these paths. Before it, identify
the normal USB volume, inspect leftover update images, confirm the working stock
state and recovery artifacts, and keep the SD card absent to match the failed
test. Follow the recovery lessons; do not install the old failed image again.

If this diagnostic boots, the removed main-menu initialization path is necessary
for the observed failure under that test condition. That does not distinguish
payload loading, filesystem scanning, runtime patches or their interactions.
Further isolation should split those stages. If it still loops, investigate
other patches and startup paths; do not attribute the cause to scanning.

Keep stock recoverable and use the complete readback procedure if normal file
restoration cannot run. No automatic reflashing or additional speculative fix
has been scheduled.

## Diagnostic staged

The user connected for the proposed test. Normal USB071b:3203 and the262.1MB
internal Nano volume were identified; no NANOV170.IMG update file remained.
The menu-bypass image above was copied to the root as NANOV170.IMG, destination
SHA256 verified, and the volume safely ejected. Evidence:
`builds/bootloop-audit/diagnostic/device-stage.json`. Boot result is pending.
The diagnostic and stock-restore payloads remain unchanged from their recorded
hashes. This staging supersedes the earlier “neither file flashed” preparation
status; successful installation/boot must still be reported by the user.

## Hardware result: menu bypass boots, Shuffle freezes

The user reported reaching the main menu and successful icon rendering with the
single-hook bypass. This narrows the original boot failure to the added menu
initialization path or its interactions; it does not identify its failing stage.
The user then pressed Shuffle and reported a freeze, could not open File Browser,
and could not confirm whether audio continued. Normal USB storage mounted after
reconnection (071b:3203). No remaining update IMG was present in the volume root.

Do not treat the diagnostic as usable firmware. The freeze is a distinct observed
failure; whether it shares a cause with the boot loop is unresolved. Both paths
can reach the playback payload, but that is an investigation lead, not proof.
Stock recovery dated20261016 was staged with destination SHA256 verification;
normal boot after that restore is pending user confirmation. See
`builds/bootloop-audit/diagnostic/shuffle-freeze-restore.json`.

## Stock restored again; shared loader defect reproduced and corrected

The user confirmed the 20261016 stock update reached the normal menu. Subsequent
work was offline. The next candidate has not been flashed.

The resident loader requested10568 bytes from stock `fw_read` at0x0306b36c.
The aligned bulk path reads20 sectors, advances the destination by10240 bytes,
and leaves328 bytes. But the common continuation at0x0306b4e2 increments the
source sector by only1 rather than20. The partial-tail read therefore comes
from the second sector, not the twenty-first. Status still reports success,
and the intact header passes the loader's magic check.

New `tests/test_payload_flash_read_arm.py` executes the actual resident loader
and stock byte-reader instructions, intercepting only locks and sector I/O.
Against the exact failed P4a image it failed at byte10240, recording requests
`[(21161,20),(21162,1)]`. The expected tail sector was21181. Log:
`builds/bootloop-audit/real-reader-red.log`.

The corrupted RAM range starts0x0309de94 and extends to0x0309dfdc. The linker map
places bridge literals, memcpy (0x0309dea8), memset (0x0309debe), strcmp and
payload constants in that range. This is a concrete defect in the shared load
path and a strong explanation for both symptoms. Hardware confirmation is still
required; do not equate a reproduced defect with completed device acceptance.

Correction: request10752 bytes (21 whole sectors). The184 extra bytes occupy
verified unused firmware padding and the beginning of payload BSS, cleared by
real playback_init. The image builder now rejects a rounded read exceeding
flash padding or BSS bounds. Payload code/state size and RAM allocation do not
increase. The original main-menu initialization hook is restored in this image;
it is not the earlier bypass diagnostic.

The new regression verifies all payload bytes for either firmware-region mapping
and executes real payload initialization, checking zeroed BSS and preservation
of NanoCRebootFlag. Both tests pass. The complete suite passes147 tests;
`builds/bootloop-audit/fix-full-tests.log`. The old high-level flash-read mock was
updated to model the rounded request, but is no longer the only loader coverage.

Candidate: `builds/phase4a-loader-fix/custom/NANOV170.IMG`, date20261017,
SHA256 `0a6fffbeafb67adb5216a575e1e5ca5de861853b4e3b25b8a8237b92335fdb75`.
Paired stock restore: `builds/phase4a-loader-fix/recovery/NANOV170.IMG`, date20261018,
SHA256 `ebbe0c996db9984c61d308c84d9e7ce76a435953204a6004dc11fb0ddd7e3423`.
About still says P4a; distinguish artifacts by hash/date. Exhaustive comparison
with failed P4a finds only two changed code bytes in the loader's read-length
MOVW instruction, plus date fields and package CRC. Both header copies/CRCs
validate. The manifest records uncommitted source changes honestly.

Next hardware checkpoint: boot without SD, ordinary menu navigation, then the
Shuffle route that froze. Stop on any failure and use the newer stock recovery.
Do not publish until actual audiobook/marker/resume acceptance also passes.

## Corrected loader candidate staged for hardware test

The user connected for testing. Normal USB071b:3203 at02100000 and
the262111232-byte internal disk4s1 volume were freshly verified. No update
IMG remained. Candidate20261017 was copied as NANOV170.IMG, its full
SHA256 matched0a6fffbeafb67adb5216a575e1e5ca5de861853b4e3b25b8a8237b92335fdb75,
and disk4 was successfully ejected. Existing CFWLOG.TXT was preserved locally.
Evidence: builds/phase4a-loader-fix/device-stage.json. Installation, boot and
Shuffle results await user observation; staging does not establish acceptance.

## Corrected candidate: working menus reported

After staging candidate20261017, the user reported: "menus seem to work now".
This confirms reaching responsive menus on hardware with the original menu hook
enabled and the sector-rounded loader correction. Shuffle, audio playback,
audiobook markers and resume have not yet been separately confirmed. This is
initial boot/menu acceptance, not full feature or release acceptance.

The user additionally confirmed Shuffle starts playing the single song on
internal storage. Headphones were unavailable, so audible output remains
unverified. Returning to File Browser after Shuffle and multi-track shuffle
behavior are not yet confirmed.

The user confirmed returning to File Browser after Shuffle shows Internal.
The previously failing sequence now passes its initial hardware check: boot,
menu navigation, Shuffle starting the single internal track, and responsive
browser navigation afterward. Audible output and audiobook acceptance remain
unverified.
