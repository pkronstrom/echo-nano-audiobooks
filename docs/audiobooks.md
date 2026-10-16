# P4a audiobook device test

> **2026-10-14 hardware result:** P4a boot-looped. Stock recovery succeeded and
> the user confirmed the normal menu. Do not reflash or publish this candidate.
> Read [recovery lessons](recovery-lessons-2026-10-14.md) before device work.

P4a adds the approved icons and conditional marked-root shortcuts, retaining File Browser M3U playback in listed order and a separate saved chapter
and time for each prepared book. It includes P1b music exclusion and folder
containment. Host/ARM checks pass; boot, decoding and storage durability still
need device validation. Nothing has been flashed automatically.

## Images and installation

Local artifacts (excluded from Git):

- Custom: `builds/phase4a/custom/NANOV170.IMG`, About **P4a**, date **20261013**.
- Stock recovery: `builds/phase4a/recovery/NANOV170.IMG`, date **20261014**.
- Source checkpoint: `phase4a-marked-roots-test`.
- Checksums, source revision and test results: `builds/phase4a/manifest.json`.

The player selects the newest dated valid firmware. These dates must be newer
than what is installed. After using this recovery, rebuild subsequent custom
images with `AUDIOBOOK_DATE=20261015` or a suitably later date.
Copy the **custom** image to the root of the player's internal storage, eject
and restart. Check About for P4a. Keep the recovery image on the computer; to
restore stock, copy that image instead, eject and restart. See
[baseline installation and recovery](baseline.md#installation-and-recovery-pending-device-checkpoint).

## Prepare a book

The tagged RC and installed versions require host preparation for each new book.
The post-RC candidate adds guarded automatic `BOOK.M3U` / RSM / BMK creation
when entering a simple book folder through Audiobooks. It preserves existing
files and custom playlists. Hardware acceptance is pending; supported card/layout
limits and fallback are in [automatic preparation](automatic-book-preparation.md).
The host workflow below remains supported. Keep each book in its own directory.

Run from this repository, replacing the example path with your book's path:

```sh
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/ThinkAndGrowRich'
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/ThinkAndGrowRich' --write
```

The first command previews JSON. The second creates `BOOK.M3U`, a 1024-byte
`BOOK.RSM` resume companion, a 1024-byte `BOOK.BMK` bookmark companion, and `.nomusic`. Tracks sort naturally by relative
path: `00 Introduction`, `01 Chapter 1`, `02 Chapter 2`, …; numbered disc folders
also sort numerically. Metadata tags are not used for ordering. Open the M3U in
a text editor if you need a different order. Rerunning preparation preserves an
existing playlist and valid resume/bookmark files. Use one book directory at a time.

A single long file works too:

```sh
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/My Book/book.mp3' --write
```

This creates `book.M3U`, `book.RSM` and `book.BMK` beside it. Single-file preparation does
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

## Audiobooks and Meditation shortcuts

Put an empty `.audiobook` file inside your audiobook collection root, and an
empty `.meditation` file inside your meditation root. Folder names are free.
For example, after replacing the volume name with your Nano's mounted name:

```sh
touch '/Volumes/NANO/Audiobooks/.audiobook'
touch '/Volumes/NANO/Meditations/.meditation'
```

These are **files inside folders**, not renamed folders. A category appears in
the main menu only when its marker is found. One root opens directly; multiple
roots show a chooser with their paths. Back follows the real folder ancestry.
The menu rescans when opened and checks roots again before entry. Reopen the
main menu after changing media. Scan limits are eight roots total, seven folder
levels, 2,048 directories and 65,536 directory-entry reads; exceeding a work or
root limit hides both shortcuts rather than showing an incomplete collection.

Both markers recursively exclude their roots from Music and global Shuffle
following **Media Library Refresh**. Existing `.nomusic` continues to exclude
music without adding a shortcut. Book preparation still creates `.nomusic`;
add `.audiobook` once at the collection root to show the menu. The Meditation
shortcut uses ordinary contained folder playback; it adds no new timer.

## M4B: try audio-preserving M4A first

The native extension list recognizes M4A/MP4 but omits M4B. This does not prove
its decoder cannot play the audio inside. For an unprotected AAC/ALAC M4B, the
preparation tool can copy the audio into M4A without re-encoding. It requires
installed `ffmpeg` and `ffprobe`, and an empty destination outside the source
book directory:

```sh
python3 tools/prepare_book.py '/path/to/Book.m4b' --remux-to m4a --output '/path/to/Prepared Book'
python3 tools/prepare_book.py '/path/to/Book.m4b' --remux-to m4a --output '/path/to/Prepared Book' --write
```

The first command previews and checks the codec; the second writes a prepared
book. Tests verify identical AAC and ALAC audio packet hashes before/after.
**Nano decoding, long-file seeking and resume still require the device test.**
Embedded chapter tables are omitted; a long M4B remains one long audio file.
Sources stay untouched. [FFmpeg stream-copy documentation](https://ffmpeg.org/ffmpeg.html#Streamcopy)
explains the mechanism.

## Optional MP3 fallback

If the original codec is incompatible or M4A fails on the device, use explicit
MP3 conversion. This re-encodes audio, unlike the M4A option:

```sh
python3 tools/prepare_book.py '/path/to/Book.m4b' --convert-to mp3 --output '/path/to/MP3 Book' --write
```

Chapter MP3 folders and long M4B files are common distribution shapes; see
[LibriVox help](https://librivox.org/pages/help/) and
[Audiobookshelf directory conventions](https://audiobookshelf.org/docs/documentation/libraries/book-library/directory-structure/).
Existing native MP3 files need no conversion. A folder is processed one file at
a time. Copy the complete output directory to the player. Processing stages the
whole result before publishing it; an FFmpeg failure leaves no partial prepared
book in the destination. Neither path removes DRM or modifies originals.

## Device acceptance checklist

- [ ] Check main-menu/shortcut scan latency with a realistically full card.
- [ ] With no category markers, both optional menu entries are absent.
- [ ] Add each marker, reopen the main menu, and verify the corresponding shortcut.
- [ ] Try two roots, select either, and check Back returns through real parents.
- [ ] Remove a selected root/marker and verify no stale folder opens.
- [ ] The approved icons render correctly, including the music note.
- [ ] The current reviewed candidate boots and a prepared book's M3U opens with audible playback. Never install the failed P4a image.
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

Manual bookmarks use a valid `.BMK` companion. The post-RC automatic-preparation
candidate can create a missing BOOK.BMK in its supported scope; installed/tagged
versions still require host preparation. Embedded chapters and completed-book
tracking remain unsupported. Upstream experimental power patches remain disabled.

## Experimental MP3 speed control

P4e source adds an **MP3 speed** row below Continue, Chapters and Bookmarks.
Choose 1x, 1.25x, 1.5x, 1.75x or 2x, then launch Continue, a chapter or a
bookmark. The 20261110 candidate stores each book's launched speed in its existing RSM
resume companion during normal progress saving/stopping. It restores on reopening
and restart; legacy or missing values default to 1x. See [per-book speed](per-book-speed.md). Changing
it does not change a book that is already playing, including through seek,
pause/resume or automatic chapter changes. Explicitly launch Continue, a chapter
or a bookmark to apply the newly selected speed.

The speedups use approximate pitch-preserving processing for native 16-bit MP3
at 8–48 kHz. Other codecs retain their normal 1x playback. Music outside the
book queue retains native playback. Bookmarks and resume positions use source
time, rather than elapsed listening time multiplied by the selected speed.

This feature is undergoing integration verification; it is not yet confirmed on
the Nano. Read [the speed checkpoint](speed-integration-checkpoint.md) before
building or installing an image. Hardware acceptance must include headphone
listening at each preset, pause/resume and seek, the last chapter ending,
bookmark reopening, and normal music playback afterward.

## Build

```sh
make audiobook AUDIOBOOK_DATE=20261013
make test PY=path/to/python-with-unicorn
```

GNU make 4.3+ and the Arm GNU toolchain are required. The image outputs are
`out/audiobook/NANOV170.IMG` and `out/audiobook/recovery/NANOV170.IMG`.
The default `make` still produces the separate P1b image.

The Audiobooks landing row reads **Continue <book name>** for the current saved
book, followed by Browse books. A generic `BOOK.M3U` uses its parent folder's
name. This selection remains in RAM for the current firmware session; the
per-book resume position and speed use their existing SD journal files.
