# Audiobook screen and durable Continue

Offline candidate 20261120, stock recovery 20261121. Not installed or hardware
accepted. Includes the prior 20261118 preparation correction.

## Screen

In normal audiobook Now Playing, the first row shows a book icon and book name
(the containing folder for BOOK.M3U, otherwise the playlist stem). The second
row uses the chapter's native title metadata, falling back to its filename.
The author glyph, favorite heart and playback-order arrow are cleared. Time,
chapter counter, play/pause, storage, actual speed and transient bookmark
feedback remain. Music, ordinary folders and other display modes retain their
native behavior. Long titles use native marquees; a persistent bounded UTF-16
buffer avoids retaining a stack pointer and avoids truncating surrogate pairs.
A single-file book without chapter metadata still has one chapter.

## Continue after restart

The newest deliberately launched book is remembered in its existing BOOK.RSM
journal. It is saved on the first valid playback-position poll, then normal
progress checkpoints continue approximately every five minutes. Speed changes,
bookmark jumps and automatic chapter transitions preserve selection ordering.
There is no extra state file. Legacy resume records remain usable; open and play
a book once with this firmware to create its durable Continue hint.

Audiobooks landing performs bounded, read-only discovery within marked audiobook
roots. It chooses each journal's newest CRC-valid sector before comparing book
selection sequences, validates the playlist's physical identity and publishes
only after a successful complete scan. Read failure does not publish a partial
winner. Device/filesystem changes invalidate cached scan state. Missing/replaced
playlists and records without the extension are skipped. Sequence ordering uses
signed serial comparison and skips zero.

RSM words 9–15 contain ELB1 tag (0x31424c45), selection sequence, playlist parent
cluster/raw index/cluster/size, and content signature. Existing sector CRC covers
the extension. Bookmark format is unchanged. The normal record remains valid
if the supplementary playlist lookup fails; a later successful save can add
the hint. A crash before a successful save can retain the earlier selection or
position. This is best-effort recovery, not a maximum-loss guarantee.

## Layout and review

Resident: 28,008 bytes text + 28,048 BSS = 56,056, leaving 248 bytes below the
unchanged 0x0309fff0 boundary. Browser: 13,956 text + 5,320 BSS. Resident flash
reservation is 28,160 bytes at 0x36200..0x3d000. Browser backing moves to
0x3d000..0x42b48 inside checked-zero refresh storage. Bootloader, resident RAM
boundary, decoder boundary and audio DSP buffers/clocks are unchanged.

Temporary path/parser buffers moved onto the stack while last-book and current
playlist paths remain distinct. Seven-level FAT host measurements from native
stack top 0x03004000: cold Continue 2,984 bytes; preview 3,592 bytes. Native indexed
open runs; raw I/O, locks and watchdog are mocked. IRQ and full driver stack use
remain unmeasured. Native marquee execution is covered with font rasterizer and
blitter mocked; this does not establish exact hardware appearance.

Scoped independent review found two scan failure bugs, both fixed with regression
coverage: partial-winner publication after lookup I/O failure, and reuse of a
previous medium's sequence after scan failure. Final scoped rereview found no
remaining concrete blocker. This is not a new cross-vendor revx panel. The
attempted external design review failed to run; no approval is attributed to it.

## Device acceptance checklist

- Observe first update boot before manual reset.
- Open Book C: book/title first row; chapter title second row; no heart or
  order arrow; verify long-title scrolling, time beyond one hour and speed.
- Play a book long enough for the first valid save, restart, then open Audiobooks:
  Continue should name and reopen it at saved progress.
- Switch books, restart and confirm the most recently opened book wins; change
  speed and jump to a bookmark without changing that ordering.
- Check ordinary Music display, bookmark feedback and audio remain usable.

No device writes or installation were performed for this checkpoint.


## Final offline checkpoint — 20261120

All 611 regression tests passed in 616.628 seconds; 16 new focused checks also
passed. Fresh resident/browser/custom/recovery rebuilds match byte for byte.
Scoped independent rereview found no remaining concrete blocker after the two
scan failure corrections. Candidate 20261120 and stock recovery 20261121 are
archived at builds/phase4l-book-screen-20261018/reviewed/manifest.json.
Resident text/BSS 28008/28048 bytes leaves 248 bytes below unchanged 0x0309fff0.
No installation, commit or push; hardware UI/boot/Continue acceptance pending.
Legacy books need one successful playback save to establish a durable hint.


## 20261122 navigation/display follow-up

See [current behavior and acceptance checks](content-navigation-followup.md). This supersedes the
20261120 display implementation and previous-music return behavior. Offline only.
