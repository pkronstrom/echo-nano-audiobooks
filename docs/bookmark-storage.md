# Bookmark storage

Status: storage, favorite gesture, book/chapters/bookmark menus, jump and confirmed
deletion are implemented offline. See [current UI integration](book-menu-implementation.md).
On2026-10-15 the user confirmed bookmark saving on the installed book-menu
candidate after Bhagavad received its missing BMK companion. Other operations
remain host-tested rather than device-accepted. No public release is approved.

Bookmarks belong beside the playlist, on the same storage device:
`BOOK.M3U`, `BOOK.RSM` (automatic resume), `BOOK.BMK` (manual bookmarks).
For books on SD, both companions are on SD. Preparing a book again preserves
existing companions and custom playlist ordering; unknown/corrupt companion
formats and symlinks are rejected before creating metadata. No existing audio
is changed. Existing prepared books need preparation rerun to add BMK.

## ENB1 format

The preallocated file is exactly 1024 bytes: two alternating 512-byte sectors.
All integers are unsigned little endian. Each sector contains:

| Byte offset | Meaning |
| --- | --- |
| 0 | Magic `0x31424e45` (`ENB1`) |
| 4 | Generation, wrapping 32-bit serial comparison |
| 8 | Playlist fingerprint |
| 12 | Entry count, 0–60 |
| 16–495 | Up to 60 entries: 1-based chapter index, then milliseconds (8 bytes) |
| 496–507 | Reserved, initially zero |
| 508 | IEEE CRC-32 of bytes 0–507 |

Empty companions contain two valid empty generation-zero sectors. Every change
reads and validates both sectors, selects the newest valid generation, edits the
shared scratch buffer, and writes only the opposite sector. Failed/short writes
report failure. Emulator tests demonstrate recovery from a partial sector write;
this is not proof of the SD controller's physical power-loss behavior.

A full journal rejects additions without evicting old marks. Deletion is explicit
and compacts the remaining entries. Resume saves never modify BMK, and bookmark
changes never modify RSM. Invalid chapter indexes, invalid CRCs, changed nonempty
playlist fingerprints, missing media and parser-busy state fail closed.

## Identity and caller obligations

`playlist_signature()` fingerprints playlist bytes plus accepted line offsets,
independently of physical file clusters. Moving a whole book with unchanged
relative playlist contents preserves it; changing order or the set of resolved
tracks changes it. This is a compact accidental-change guard, not a cryptographic
identity. Changing comments also invalidates it. Replacing audio under identical
names and playlist contents is not detected. Existing RSM identity remains
physical and has not acquired relocation support from this work.

Session integration calls `bookmarks_open(path, playlist_signature())` on every
book launch and clears the context on ordinary music/failed launches.
`playback_add_bookmark()` verifies current chapter identity and clamps time to
the reported duration. Jump targets are revalidated during launch. `bookmarks_get()` returns stored chapter and
milliseconds; it does not start playback. API calls belong to the player service,
never to an interrupt or another task. The shared parser/journal scratch busy
flag protects synchronous parser reentry, not arbitrary cross-task concurrency.

## Budget and verification

The initial implementation left36 bytes. The audited relocation described in
[playback memory layout](playback-memory-layout.md) now gives playback56304 bytes
of RAM and32768 bytes of flash staging, sharing refresh-only storage. The upper
reboot boundary is unchanged. Current code11836B + BSS7148B leaves37320B RAM;
flash staging has20932B free. No relocated firmware has been flashed.

Scratch sharing recovered 508 bytes; splitting queue geometry, indexes and flags
into aligned arrays recovered 256 bytes before code overhead, preserving the
256-track capacity and avoiding unaligned packed accesses.

The initial storage milestone passed169 host/ARM tests. Current verification is recorded below. Evidence is in ignored
`builds/sd-audiobook-test/usability-tests.log` and `usability-build.log`.
Bookmark tests cover multiple chapters, restart/reopen, deletion, interrupted
write, full capacity, changed playlist, corruption, invalid operations, parser
busy state and card removal. Queue tests verify signature stability across folder
relocation and read chunk sizes, and changes on reorder/missing tracks.

The memory gate is resolved for the declared synchronous overlay lifecycle.
Book/chapters/bookmark menus, jump and confirmed deletion are implemented offline;
device acceptance remains outstanding. See the memory audit for remaining hardware and
asynchronous-lifecycle limits.

## Deferred favorite gesture

Both native favorite-query routes now enter a resident 48-byte guard. Ordinary
music and an absent payload call the stock query with its original zero argument.
An active book captures chapter/time into a single pending request; it does not
open files from the UI handler. A second press before consumption is rejected,
retaining the first snapshot. The player service checks the request at its native
message439 poll and writes BMK there. Chapter advancement retains the captured
position; new book/music transitions cancel the pending request. Parser-busy
state defers consumption. There is not yet success/failure feedback on screen.

The resident stub replaces the out-of-bounds pixel diagnostic at0x03052d68.
Its only identified caller's tail printf at0x03052c9c is replaced with return;
out-of-bounds drawing still returns without modifying the framebuffer. The
native query hooks are0x030638ac and0x030638ee; the service poll is0x03082d4c.
These are validated against stock bytes by the image builder.

Tests cover both native favorite routes, missing payload, ordinary music,
chapter advance between press and service, cancellation, duplicate pending
presses and disabled diagnostic behavior. Hardware task scheduling/interleaving
and on-screen feedback still require work; emulator coverage is synchronous.

Latest verification: full suite188 tests passed (72.146s), followed by12 gesture
tests including the additional native message-poll argument/result regression.
`git diff --check` passed. Build code11808B/BSS7140B. No device installation.

Fable review follow-up: the native player poll now passes through a module33
ENP2 guard at0x03083084, preserving the stock call when payload RAM is absent.
Queued snapshots also carry a session generation; late publication after a book
reset is discarded. Reader and writer compiler barriers order the shared fields.
The review returned warnings (its JSON lacked the closing brace, recovered in
builds/sd-audiobook-test/fable-bookmark-review.json); it was not a clean pass.
The two behavioral findings have regression tests. The stale playlist-layout
documentation and native favorite argument preservation are also corrected.
Minor constant consolidation and resume/session ownership cleanup remain.

After the review fixes, all192 host/ARM regression tests passed. No hardware validation.
