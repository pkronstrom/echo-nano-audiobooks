# P3a audiobook device test

P3a adds File Browser M3U playback in listed order and a separate saved chapter
and time for each prepared book. It includes P1b music exclusion and folder
containment. Host/ARM checks pass; boot, decoding and storage durability still
need device validation. Nothing has been flashed automatically.

## Images and installation

Local artifacts (excluded from Git):

- Custom: `builds/phase3a/custom/NANOV170.IMG`, About **P3a**, date **20261012**.
- Stock recovery: `builds/phase3a/recovery/NANOV170.IMG`, date **20261013**.
- Source checkpoint: `phase3a-audiobook-test`.
- Checksums, source revision and test results: `builds/phase3a/manifest.json`.

The player selects the newest dated valid firmware. These dates must be newer
than what is installed. After using this recovery, rebuild subsequent custom
images with `AUDIOBOOK_DATE=20261014` or a suitably later date.
Copy the **custom** image to the root of the player's internal storage, eject
and restart. Check About for P3a. Keep the recovery image on the computer; to
restore stock, copy that image instead, eject and restart. See
[baseline installation and recovery](baseline.md#installation-and-recovery-pending-device-checkpoint).

## Prepare a book

Run from this repository, replacing the example path with your book's path:

```sh
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/ThinkAndGrowRich'
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/ThinkAndGrowRich' --write
```

The first command previews JSON. The second creates `BOOK.M3U`, a 1024-byte
`BOOK.RSM` resume companion, and `.nomusic`. Tracks sort naturally by relative
path: `00 Introduction`, `01 Chapter 1`, `02 Chapter 2`, …; numbered disc folders
also sort numerically. Metadata tags are not used for ordering. Open the M3U in
a text editor if you need a different order. Rerunning preparation preserves an
existing playlist and valid resume file. Use one book directory at a time.

A single long file works too:

```sh
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/My Book/book.mp3' --write
```

This creates `book.M3U` and `book.RSM` beside it. Single-file preparation does
not exclude its entire parent from music. Put books in their own directory and
prepare that directory, or add an empty `.nomusic` to your audiobook root.

After copying/preparing books, run **Media Library Refresh** so excluded book
folders disappear from music and global Shuffle. Open **File Browser → your
book folder → BOOK.M3U** (or `book.M3U`). Selecting an audio file directly uses
ordinary folder playback; select the playlist for per-book resume.

Normal playback advances in listed order and stops at the end. Manual
next/previous wrap within the playlist. Missing entries are skipped. An M3U
without a valid RSM companion can play but has no independent saved position.
Progress is saved when the native player stops, including the usual browser
handoff and normal shutdown path. Reopen the same M3U after restarting to restore
its chapter and time; this build does not auto-reconstruct the book queue at boot.
Stock seek rounds the restored time to the next second.

Hold previous/next for stock rewind/fast-forward, as described in
[FiiO's Echo Nano controls](https://support.fiio.jp/hc/ja/articles/60876814334617-Snowsky-ECHO-NANO%E3%81%AE%E3%82%88%E3%81%8F%E3%81%82%E3%82%8B%E8%A8%AD%E5%AE%9A%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6).
There is no new ±30-second mapping in this build.

## Optional conversion to MP3

Chapter MP3 folders and long M4B files are common distribution shapes; see
[LibriVox help](https://librivox.org/pages/help/) and
[Audiobookshelf directory conventions](https://audiobookshelf.org/docs/documentation/libraries/book-library/directory-structure/).
The optional conversion path keeps format handling on the computer. It requires
an installed `ffmpeg` and an empty destination outside the source folder:

```sh
python3 tools/prepare_book.py '/path/to/Book.m4b' --convert-to mp3 --output '/path/to/Prepared Book'
python3 tools/prepare_book.py '/path/to/Book.m4b' --convert-to mp3 --output '/path/to/Prepared Book' --write
```

Copy the resulting directory to the player. A source directory converts each
recognized audio file separately; one M4B becomes one long MP3. Original files
remain untouched. Embedded M4B chapters are not extracted. Conversion cannot
remove DRM. A failed conversion can leave completed output files; use a fresh
empty destination for a retry. Existing native MP3 files need no conversion.

## Device acceptance checklist

- [ ] P3a boots and a prepared book's M3U opens with audible playback.
- [ ] Numbered chapters play in order, even with music Shuffle enabled.
- [ ] Next/previous and automatic end-of-book stay within that book.
- [ ] Seek within a long file; stop, reopen and verify the approximate time.
- [ ] Book A → music → book B → book A restores A's chapter and time.
- [ ] Normal shutdown/restart, then reopening each M3U, restores both books.
- [ ] Refresh the library, then reopen a book; music Shuffle excludes marked trees.
- [ ] Meditation folders remain contained; ordinary music playback still works.

## Current limits

256 queued tracks, 512 candidate lines, 1 MiB M3U input, 1024 bytes per line and
255 UTF-16 units per resolved path. The preparation tool limits basenames to
127 UTF-16 units for stock exFAT safety. Deep paths can exceed limits after being
copied to the player. Keep book paths short and within the browser's seven levels.

Resume uses two CRC-protected sectors in a pre-created file. Power loss during
writing can fall back to the older record in emulation; physical flash/card
behavior is unverified. Replacing audio in place while preserving filesystem
indices/clusters can retain a stale position. To deliberately reset a book,
remove its RSM companion and rerun preparation. Do not edit RSM contents.

Dedicated Audiobooks menus, new icons, playback speed, embedded chapters,
manual bookmarks and completed-book tracking are not included. Upstream
experimental power patches remain disabled.

## Build

```sh
make audiobook AUDIOBOOK_DATE=20261012
make test PY=path/to/python-with-unicorn
```

GNU make 4.3+ and the Arm GNU toolchain are required. The image outputs are
`out/audiobook/NANOV170.IMG` and `out/audiobook/recovery/NANOV170.IMG`.
The default `make` still produces the separate P1b image.
