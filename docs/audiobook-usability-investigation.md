# Audiobook usability investigation — 2026-10-14

## Current device evidence

The loader-corrected20261017 image reaches responsive menus and passes the
previous Shuffle→File Browser freeze sequence. User reports M3U resume works.
Readback of Book A BOOK.RSM contains valid CRC records, generations6/7,
chapter1 at171448/174760ms. Audible output has not yet been confirmed.

Original Book B MP3 and minimal-metadata MP3 each take about8s to start directly;
minimal M3U starts quickly. Earlier attribution to cover art was premature and
is withdrawn. Compare identical bytes through the two launch routes.

## Playlist visibility fix (offline)

Stock browser classification table at module31 data0x0300e6bc has category1
(audio-only) and category6 (all supported browser types). Category6 points to
our M3U-enabled resident whitelist. Returning from playback can initialize a
category1 browser and hide M3U files. Changing the shared category1 table is
unsafe: stock uses it for file classification and ordinary playback ordinals.
An initial regression exposed that interaction; that approach was discarded.

navigation_browser_init now changes only this browser instance's filter pointer
to the existing category6 record when media==3, category==1 and depth<=7. It
recounts and reenumerates the current folder, resetting pagination because the
widened list has different ordinals. Decoder whitelists and native classification
remain untouched. Tests execute native category selection and verify unrelated
views and invalid depth are unchanged. Exact selection restoration is pending.
No image from this work has been installed on hardware.

## Direct-file startup lead

Module31 native selection uses0x0307aa10 to scan entries and reconstruct an
ordinal, then0x0305e64c to count entries (e.g.0x0307af58..0x0307af76).
The M3U launch bridge skips ordinary selection's ordinal reconstruction and uses
indexed media references. This is a plausible difference to instrument, not a
measured cause. Do not change codec parameters based on the8s observation.

## Screen layout lead

Module31 draws resource146 at0x0307a442 and0x0307a59a after clearing640 bytes.
The two list render paths use text x44/45 and row icon x32, with16-pixel rows.
Examples:0x0307a486,0x0307a4ac,0x0307a616,0x0307a626. Need to decode the resource
and verify both redraw paths, clipping, selection backgrounds and scrollbar
before device acceptance. Both paths are now patched offline: remove resource146,
move row icons to x0 and text to x12/13, and tile the existing92px backgrounds at
x0 and x32 to preserve the scrollbar at x124. Geometry and ARM draw-call tests
pass; physical display verification is still pending.

## Memory gate

Before this work, code ends0x0309dfdc and BSS ends0x0309fe84; limit0x0309fff0.
Only364 bytes remain. Native browser sorting must keep display, raw-entry
identity and selection ordinals aligned. A label-only sort is invalid. Prefer
browser-overlay storage with a proven lifetime, or a bounded disk index, over
unverified expansion of shared resident RAM. The bootloader/reboot flag region
must remain protected.

## Bookmarks / book menu implementation design

Accepted UX: book names hide technical companion extensions; Continue displays
saved chapter/time; Chapters preserves explicit playlist order; Bookmarks lists
chapter/time entries. Double Previous adds a bookmark only for active audiobook
sessions; normal music retains favorites. Explicit deletion; no text entry.

Use a separate versioned preallocated companion for multiple bookmarks, keeping
existing RSM files compatible. Journal updates need CRC/generation checks and
bounded capacity. Stream records into a small display window rather than keeping
all bookmarks in RAM. Validate queue/file identity before a jump. Storage format and ARM APIs now exist; see [bookmark storage](bookmark-storage.md).
Preparation creates a separate BMK and preserves existing files. Button/menu/jump
integration remains absent, so no usable on-device bookmark feature is claimed.

## Speed feasibility

Inspected primary SDK sources from xinghuaman/RKNanoD_MP3_V1.3_20161102 at
6c9657140305a91bedc5602e3822d1904056a635: AudioControl.c/.h, Pcm.c,
audio_globals.h and audio_track_control.c. Local copies: builds/research/speed/.
They expose sample-rate/resampling paths, but the inspected controls contain no
identified pitch-preserving tempo API. These related SDK sources are clues,
not proof of installed Nano functions/addresses or absence of support.

Do not advertise1.25/1.5/1.75/2x as implemented. Trace the exact stock PCM/output
path and resource use before choosing an on-device time-stretch implementation.
Changing output sample rate alone changes pitch. Offline prepared speed variants
are possible but do not meet seamless on-device speed switching and require
position mapping; they are a fallback, not the accepted implementation.

## Offline checkpoint

All150 tests pass after the browser-view fix (49.031s). BSS now ends
0x0309ff10, leaving224 bytes; no reserved-boundary change. Candidate20261019
and stock restore20261020 are archived under builds/phase4b-browser-return.
Neither was flashed. Sorting, layout and bookmark/menu implementation remain
pending; speed feasibility remains unresolved.


## Latest offline checkpoint — bookmark foundation

169 host/ARM tests pass (59.856s). Code11616B + BSS7128B leaves only36B in the
reserved payload region and160B in flash staging. The parser/resume share a
word-aligned scratch buffer with synchronous parser-busy protection; the queue
uses aligned separate geometry/index/flag arrays, keeping256-track capacity.
The current build includes the wide browser and bookmark storage APIs but has
not been flashed. The older builds/phase4b-browser-return archive still represents
only the earlier browser-return checkpoint, not these later changes.

Remaining: bookmark event/menu/session wiring, Continue/Chapters UX, physical
natural sorting, exact Back selection, measured direct-open optimization and
speed feasibility. A proven overlay memory/code design is required before adding
those interfaces. Do not weaken linker/loader boundaries to make them fit.


## Memory gate follow-up

The36-byte limit was resolved by auditing refresh/playback ownership, not by
crossing the reboot flag or changing firmware size. New placement and regression
coverage are in docs/playback-memory-layout.md. Current payload11668B + BSS7128B
leaves37508B RAM and21100B flash staging. Journal sector/path handling is shared
between resume and bookmarks. Book launches open BMK with the queue signature;
ordinary music and failed launches clear the bookmark context. Verified current
chapter/time capture is implemented; no favorite gesture/menu/jump yet.

Now Playing is module27 (its entry contains `MusicWinInit`, and it consumes
0x03039714 playback info). The earlier suggestion of module23 was incorrect.
Module27 key handling calls resident0x03063242. That routine contains double-key
counters and favorite-query/add/remove calls around0x030638aa..0x030638ee;
interception still needs a guarded resident route and native-path regression.
Do not patch an always-resident call directly into payload code without checking
its lifetime/magic, including ordinary music and post-refresh states.

## Favorite gesture milestone

The resident guard is implemented for both native favorite-query paths; active
books queue chapter/time and the player service writes BMK at its message439
poll. Music favorites and missing-payload fallback preserve native semantics.
The guard uses48 bytes of a disabled pixel-error diagnostic, audited in
playback-memory-layout.md. New code11808B/BSS7140B leaves37356B RAM.
Full suite188 passed; focused13-test gesture suite additionally covers the native
poll call and parser-busy deferral. No installation or on-device save feedback.
The book/chapters/bookmark menus and jump controls remain to be implemented.

## Launch timing observation — 2026-10-15

User tentatively reports Book B indexed opens fastest, with minimal also fast.
No new timed comparison or exact file identity was supplied. Preserve both as
comparison cases; do not equate this with proof of metadata or codec cost.
Main-menu category latency is a separate root-discovery path.
