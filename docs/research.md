# Firmware integration findings

This records source inspection and stock-binary disassembly at the revision/hash
in [baseline.md](baseline.md). Device behavior remains unverified locally.

## Library refresh

`src/hooks.txt` redirects directory recording at module 39 `0x0307aade`, ordinary
song recording at `0x0307b086`, CUE song recording at `0x0307ae46`, tag parsing at
`0x0307af66`, and module 40 sort/comparison sites. Module 5's refresh driver
stages the C blob from module 40 into RAM, then runs `cfw_scan`.

The source explicitly limits blob hooks to refresh. `src/link.ld` allocates
`0x0309b694..0x0309fff0`; this build leaves only 816 bytes. The folder-date table
uses `0x03092400` with 3,584 entries during walking and is intentionally reused by
module 40. It cannot simply become persistent playback storage.

Stock module 39 disassembly confirms that song counters and directory-entry
tables advance immediately after `mod39_mkrec` calls. In particular CUE recording
at `0x0307ae46` is followed by increments of `sl` and `r9` at `0x0307ae4a..56`.
Consequently returning a special value from `cfw_file_record` is not a proven
way to exclude a song: the caller's bookkeeping must also be bypassed or rebuilt.
The normal and CUE paths both need inspection. Skipping only tag parsing would
still leave records and queue membership.

A plausible Phase 1 approach is intercepting the walk before record creation,
maintaining inherited folder eligibility, and leaving deliberate folder browsing
intact. This is a research direction, not an implemented or approved configuration.
Verify FAT and exFAT contexts and the distinct library/browser indexes before
selecting the hook. The card's actual organization is unknown. Marker files avoid
renaming folders, while a root-path configuration avoids placing markers in many
trees; neither convention has been selected.

## Shuffle and playback scope

The main-menu patch uses a sixth entry in module 21. Its route selects All Songs,
sets shuffle mode and posts messages `0x113`/`0x114`. The module 23 key hook chooses
the initial index using `(ticks XOR SysTick) % count`, restores the All Songs title,
and synthesizes the select key. There is an empty-library guard.

`patches/shuffle_scope.patch` changes module 33 initialization and message paths
at `0x03082968`, `0x03083026..122`, and end-of-track dispatch at `0x030817a9`.
Stock disassembly at `0x03080512..570` confirms lazy permutation behavior:
unseen suffix selection by modulo, element swap into the generated prefix,
prefix advancement, and reuse of earlier generated entries. Random uniformity,
cross-cycle repeats and restart behavior are not established by this inspection.

The patch's whole-medium scope also applies to shuffle entered from folder
navigation. Trace actual song-list construction and every continuation path before
claiming library filtering makes all automatic music playback safe. Determine how
deliberately selected excluded content gets a bounded continuation queue.

`src/fw.h` exposes 8 file handles and a `MAX_SONGS` value of 8,192 for the CFW's
compact indexing. The stock shuffle routine uses 16-bit indexes and metadata
16 KiB past its array base. Those facts do not establish a supported M3U count
limit or the available capacity of a new queue.

## M3U integration prerequisites

There is no existing M3U implementation in the inspected source. File primitives
include read/seek and create/write/close/delete; a proven long-name path open and
playback queue handoff still need to be mapped. Establish those APIs and a safe
playback-lifetime memory region before selecting a parser representation.

The first parser should stream path entries, ignore comments/EXTINF, resolve
relative to the playlist's directory, support BOM and ordinary line endings,
and bound line/path length. Those are requirements to test, not working features.
Recommended missing-entry behavior is to skip it and stop cleanly if none remain.
Whether an explicit playlist may select excluded recordings stays a product
decision; an implementation must not silently choose a policy.

## Audiobooks and meditation

[FiiO's FAQ](https://www.fiio.com/newsinfo/1132454.html) documents copy-time file
browsing order and long-press Previous/Next seeking. Its changelog documents
album sorting using CD number, track number and filename. These statements have
not been confirmed on this stock image/device. Preserve existing seek controls
for an initial increment; a new 30-second mapping requires user input.

Independent resume needs chapter identity, current position, lifecycle save hooks,
and storage that survives shutdown. The refresh blob's globals cannot provide it.
No save/load playback ABI or atomic persistence strategy is established yet.
Do not invent a fixed-size bookmark structure without mapping storage constraints.
Natural numeric ordering is a candidate for `1,2,10`, but representative real
filenames/formats and single-file versus folder book identity remain unknown.
Meditation remains a hierarchy of folders with direct file selection; no automatic
series progression or forced resume is approved.

## Icons

The added shuffle bitmap is 20×16, monochrome, page-major, with 40 bytes in
`patches/shuffle_10_mod21_cave.S`. The original icon table has five pointers; the
patch copies them and appends shuffle. The patched menu strip uses 25-pixel spacing
and draws a sixth entry separately. Larger icons therefore affect layout/code-cave
budget, not just bitmap substitution. Stock icon decoding and the display's exact
layout still need inspection before showing alternatives. No visual direction,
additional menu layout or icon replacement is approved.
