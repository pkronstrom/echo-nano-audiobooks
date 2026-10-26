# Content navigation and display follow-up

Candidate 20261122 / stock recovery 20261123. Offline only; not installed.
Supersedes the incomplete 20261120 audiobook screen. The user confirmed its
Continue Book C menu entry works, but reported stale author/footer symbols
and an unclear book glyph. First-boot and separate restart durability acceptance
were not explicitly reported.

## Behavior

Main menu order: Now Playing, Audiobooks, Meditations, Music Library, Folders,
Shuffle, Playback Settings, System Settings. Category entries remain conditional
on their markers. English labels are renamed; other existing translations retain
their native wording. Categories use the existing English category labels.
Native action IDs are translated independently of the visible position; the
visible cursor is restored after the native window request is queued.

Now Playing returns to the current book/folder audio. Ordinary native music uses
its existing current-player route. The previous attempt to restore an earlier
music session after entering a book has been removed. With no current audio,
the native route can open the library.

Folders respects marked ancestry. Under an audiobook root, prepared book folders
and playlists retain the existing book menu. Selecting an audio file searches
for BOOK.M3U in its folder and ancestors, stopping at the marked root. A unique
physical match selects that chapter from its beginning, with the book queue,
bookmarks, resume file, saved rate and Continue selection retained. It does not
resume the old chapter time when explicitly selecting a different chapter.
Missing/malformed playlists, unlisted or repeated physical files and stale
selected file identities refuse launch with Book unavailable. Custom-named
playlists remain accessible by selecting the M3U itself; automatic direct-audio
association currently uses the standard BOOK.M3U convention. No genre guessing.
Existing bounded automatic preparation gates are unchanged.

Marked meditation trees keep normal track controls, including when selecting an
M3U. Explicit playlist order is preserved; plain folder audio uses natural order.
Meditations do not acquire audiobook bookmarks/speed or replace Continue book.
A marked meditation ancestor takes precedence over audiobook eligibility.
Music Library and global Shuffle still exclude marked trees after library refresh.

## Display correction

Native dirty-event reads consume their bits. The original overlay checked them
after native painters, so it missed text reconfiguration. The corrected overlay
recognizes native marquee ownership changes instead. A blank artist branch can
clear the row without replacing that pointer; the existing guarded width hook
now retires its marquee state/source on that full redraw before the blank paint.
Incremental updates retain scrolling. The chapter row starts at x0, with no empty
icon slot; the top row uses a revised open-book glyph.

Actual native resources establish the footer positions: mode80 atx87, heart158/159
atx95, additional mode122+ atx104, battery65+ atx115. Book mode clears x87..114 and
preserves battery115..127, time, count and play/pause. The earlier source/comment
and tests misidentified these resources and cleared the wrong region. New tests
use actual resource pixels and consuming native redraw functions.

## Review and limits

Scoped independent review identified and corrected the successful direct-launch
return code (2, matching existing chapter menu) and blank-artist redraw lifecycle.
Native dispatch tests execute both original and mapped actions, comparing defined
arguments, window requests and events. Uninitialized copied native argument tails
are not an action contract. Tests substitute physical device drivers/font raster;
this does not establish hardware appearance, boot safety or driver stack use.

Resident text/BSS is 27,952/27,952 bytes, leaving 400 bytes below the unchanged
0x0309fff0 boundary. Browser text/BSS is 13,960/5,320 bytes. A seven-level FAT
direct-chapter selection measured 3,680 bytes of stack from native top0x03004000;
full caller/IRQ stack and hardware driver use remain unmeasured.

The existing resident RAM/flash and browser runtime boundaries remain unchanged.
Audio DSP algorithm, buffers and clocks are unchanged. No new device operations.

## Offline verification — 2026-10-18

All 611 tests passed in 619.562s, with 72 focused checks passing separately.
An isolated rebuild produced byte-identical resident/browser payloads and both
images. Candidate 20261122 and recovery 20261123 passed CRC and duplicate-header
checks. Scoped independent rereview found no remaining concrete blocker; this
was not a new revx panel and does not establish hardware acceptance.

Archive: `builds/phase4m-content-navigation-20261018/reviewed/manifest.json`.
No device staging, commit or push was performed for this iteration.

## Device acceptance checklist

- Observe first boot, then open Book C: clear book glyph, left-aligned chapter
  row, no heart/mode symbols, visible battery and correct hours/speed/count.
- Open Now Playing from a book, a meditation and music; current audio remains.
- Check every reordered icon opens its matching screen and the highlight returns.
- Folders → marked book → chapter file retains book controls and correct chapter.
- Meditation folder/M3U retains track Next/Previous and stays out of music Shuffle.
- Restart after a book save and check Continue still names/resumes that book.
