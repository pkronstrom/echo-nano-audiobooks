# Music separation: P1b test build

P1b combines recursive `.nomusic` library exclusion with **File Browser folder
containment**. This is the current custom feature build.

Put an empty `.nomusic` file in each audiobook/meditation root and refresh the
media library. Main-menu Shuffle and library views omit each marked tree.
Deliberate File Browser playback remains available. File Browser next/previous,
shuffle and automatic continuation stay inside the selected folder, even when
Folder Jumping Song is enabled in preferences. Library playback retains its
upstream cross-folder behavior over the filtered library. Preferences are not
rewritten: containment applies to the active File Browser playback context.

This means playing one meditation phase folder will not automatically advance
to a sibling phase folder. Choose another folder deliberately. M3U playback and
independent per-book resume are still pending.

## Ready-to-test artifacts

- Custom: `builds/phase1b/custom/NANOV170.IMG`, About **P1b**, date `20260829`.
- Recovery: `builds/phase1b/recovery/NANOV170.IMG`, stock code, date `20260830`.
- Source tag: `phase1b-playback-containment`.
- SHA-256 hashes/source revision: `builds/phase1b/manifest.json`.

These are local, ignored build artifacts. Both earlier checkpoints are preserved.
See [manual installation and recovery](baseline.md#installation-and-recovery-pending-device-checkpoint).
The dates assume no newer image has already been installed; rebuild with suitable
successive dates if necessary. No player has been flashed or device-tested here.

## Evidence and remaining limits

30 tests pass: marker parsing/filtering, compiled ARM hooks, stock folder counters,
playback mode matrices, stock queue initialization and folder wrap, and binary
identity/CRC/recovery checks. Clean rebuilding gives the identical image.

ARM scope checks cover modes 0–9, both next/previous directions, library versus
File Browser contexts, settings position/order preservation and saved-index
rebasing from whole-storage count 100 to folder count 12. Queue tests substitute
filesystem helper results; they do not emulate actual audio decoding, storage
hardware or boot/resume timing. Hardware validation remains pending.

The playback code replaces only a dedicated File Browser settings branch and
uses space recovered from that branch for helpers. It does not put persistent
code into an unverified zero-filled buffer. Assembly builds reject a patch whose
start address shifts because of alignment. Default stock power settings remain.

## First device check

1. Confirm About says P1b. Add music plus marked book and meditation trees; refresh.
2. Confirm main-menu Shuffle and library lists contain only music.
3. Deliberately play from a marked folder. Test next/previous, the last track,
   shuffle, and changes to Folder Jumping Song while playing. Playback must stay
   within that folder. Test at least two sibling meditation phase folders.
4. Restart with File Browser playback as the last context and repeat boundary checks.
5. Return to main-menu Shuffle; music should still cross music folders.
6. Remove a marker and refresh; tracks should return. Capture `CFWLOG.TXT`.

For local builds, the restored toolchain is in ignored `builds/tools/`:

```sh
export PATH="$PWD/builds/tools/arm-gnu-toolchain-13.2.Rel1-darwin-arm64-arm-none-eabi/bin:$PATH"
builds/tools/local/bin/make
builds/tools/local/bin/make recovery
builds/tools/local/bin/make playback-core
builds/tools/test-env/bin/python -m unittest discover -s tests -v
```

The Python test environment uses `unicorn==2.1.4`. On this Mac its initialization
requires execution outside the Codex sandbox.
