# Audiobooks and meditations

This guide covers the card side of the custom firmware: how to arrange and mark
folders, how book playlists are made, which M3U files work, how to convert
audiobooks, and how to use them on the player. Install the firmware first.
Several features are not yet confirmed on hardware; the project's README lists
their status.

## Quick start

1. On the card, make an `Audiobooks` folder and a `Meditations` folder next to
   your music, and put an empty marker file in each:
   `Audiobooks/.audiobook` and `Meditations/.meditation`.
2. Copy each book into its own folder inside `Audiobooks`.
3. Prepare each book on your computer with `prepare_book.py` (see
   [Prepare books on a computer](#prepare-books-on-a-computer)). The player can
   also prepare simple book folders itself.
4. Eject the player from your computer, then run **Media Library → Media Library
   Refresh** once, so marked folders leave the Music Library and Shuffle.
5. Open **Audiobooks** in the main menu.

## Folder layout

```
Music/                         ordinary music, unchanged
Audiobooks/
├── .audiobook                 marker: adds Audiobooks to the main menu
├── The First Book/            one folder per book
│   ├── 01 Opening.mp3
│   ├── 02 Chapter One.mp3
│   ├── 10 Chapter Nine.mp3
│   ├── BOOK.M3U               created by the player or by prepare_book.py
│   ├── BOOK.RSM
│   └── BOOK.BMK
├── Some Author/               grouping folders are fine
│   └── Another Book/
│       └── ...
└── Book On Discs/             disc folders: prepare on a computer
    ├── CD1/01 Track.mp3 ...
    ├── CD2/01 Track.mp3 ...
    └── BOOK.M3U ...
Meditations/
├── .meditation                marker: adds Meditations to the main menu
└── Morning Series/
    ├── 01 Breathing.mp3
    └── 02 Body Scan.mp3
```

- **One folder per book.** The folder name becomes the book name on the player.
- **Order comes from file names, not tags.** Names sort naturally, so
  `2 Chapter` comes before `10 Chapter`. Leading track numbers are the safest
  choice. Edit the playlist if you need another order.
- **Chapter files directly inside the book folder** can be prepared by the
  player or the computer. **Disc subfolders** (`CD1`, `CD2`, …) need the
  computer.
- **Keep paths short:** at most seven folder levels below the card root, file
  names up to 127 characters, and full paths up to 255 characters.
- **Meditations** can use any folder layout. Tracks play in natural name order
  within their folder, or in playlist order when you select an M3U.

## Mark the folders

A marker is an **empty file inside the folder**, not a renamed folder. Replace
`/Volumes/NANO` with the name your card mounts as:

```sh
touch '/Volumes/NANO/Audiobooks/.audiobook'
touch '/Volumes/NANO/Meditations/.meditation'
```

On Windows, in Command Prompt (replace `E:` with your card's drive letter):

```bat
type nul > E:\Audiobooks\.audiobook
type nul > E:\Meditations\.meditation
```

Names starting with a dot are hidden by default. In macOS Finder, press
Shift-Command-Period to show them.

- Audiobooks and Meditations appear in the main menu only when their marker is
  found. Reopen the main menu after you change the card.
- You can have up to eight marked folders. With more than one Audiobooks or
  Meditations folder, the menu shows a chooser.
- The marker search covers seven folder levels and up to 2,048 folders. If the
  card exceeds that, both entries are hidden rather than showing an incomplete
  list.
- Marked folders are excluded from the Music Library and Shuffle after a Media
  Library Refresh. An empty `.nomusic` file does the same without adding a menu
  entry.

## Playlists and state files

Each prepared book has three files with the same name stem:

| File | Purpose |
|---|---|
| `BOOK.M3U` | Chapter order. A plain text playlist you may edit |
| `BOOK.RSM` | Saved chapter, time and speed (1024 bytes). Don't edit it |
| `BOOK.BMK` | Bookmarks (1024 bytes). Don't edit it |

Without `BOOK.RSM` the book cannot remember its position, speed or Continue
entry. Without `BOOK.BMK` bookmarks cannot be saved. Don't create these files by
hand: an empty or corrupt file is left alone and doesn't work.
`prepare_book.py --write` also adds an empty `.nomusic`.

### When playlists are created

**On the player.** When you open a book folder from **Audiobooks**, the player
checks whether it can prepare the folder. If the folder has 1–256 audio files
directly inside it and no playlist, the player creates the missing `BOOK.M3U`,
`BOOK.RSM` and `BOOK.BMK`, with the files in natural name order, and opens the
book menu. Existing files are never overwritten: if only some are missing, only
those are created.

The player skips automatic preparation:

- for folders with only subfolders, such as disc folders or author folders;
- for folders that already contain a differently named `.M3U`;
- for very large folders, and inside Meditations or Music;
- on card layouts it does not support, such as clusters larger than 128 KiB.

Unsupported folders open as ordinary folders, or the player shows **Prepare
failed / Use host tool**. Press Enter or Back to dismiss the message, then
prepare that book on a computer. M4B files are never converted on the player.
Automatic preparation is not yet confirmed on hardware; preparing on a computer
is the reliable route.

**On a computer.** `prepare_book.py` works for every layout above, including
disc folders and single long files. See the next section.

**Neither route regenerates an existing playlist.** If you add or rename chapter
files later, edit `BOOK.M3U`, or delete it and prepare the book again. A new
playlist can reset the saved position.

### Write your own M3U

Any `.M3U` file works as long as it follows these rules:

- Plain text in UTF-8; a byte-order mark is optional. Any line endings work.
- The file name must end in `.m3u` (any case). `.m3u8` is not recognized.
- One file per line, relative to the playlist's folder. Both `/` and `\` work,
  and `..` may go up to the card root. Absolute paths, drive letters and URLs
  are rejected.
- Lines starting with `#` are ignored, so `#EXTM3U` and `#EXTINF` are fine.
- Listed order is kept, including duplicates. Missing and non-audio entries are
  skipped.
- ASCII letters match in any case; other characters must match the file name
  exactly.
- Limits: 256 tracks, 512 non-comment lines, 1 MiB per file, 1,024 bytes per
  line and 255 characters per resolved path.

```
#EXTM3U
01 Opening.mp3
CD1/02 Chapter One.mp3
CD2/01 Chapter Two.mp3
```

What the playlist's name and location change:

- **`BOOK.M3U` in a book folder** is the standard. The book name is the folder
  name. Selecting a chapter file in that folder starts the book from that
  chapter, and automatic preparation recognizes it.
- **Any other name inside Audiobooks**, such as `Part Two.M3U`, works when you
  select the playlist itself. The book name is the file name, and the state files
  must share its stem: `Part Two.RSM` and `Part Two.BMK`. `prepare_book.py --name
  'Part Two'` creates them. Selecting a chapter file directly works only with
  `BOOK.M3U`.
- **Inside Meditations**, a playlist plays in listed order with normal track
  controls, without bookmarks or speed.

## Prepare books on a computer

`prepare_book.py` needs Python 3.10 or newer. Converting or remuxing also needs
FFmpeg with `ffprobe`. Original audio files are never changed or renamed. On
Windows, use `py -3` instead of `python3`.

Run from this repository, replacing the example paths with your own. The first
command previews what would be written as JSON; add `--write` to write it:

```sh
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/My Book'
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/My Book' --write
```

Prepare one book folder at a time. Rerunning keeps an existing playlist and
valid state files. A single long file works too, and its state files are named
after the file:

```sh
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/My Book/book.mp3' --write
```

### Which command to use

| You have | Do this |
|---|---|
| A folder of MP3 files | Prepare it as above, or let the player do it |
| MP3 files in `CD1`, `CD2`, … subfolders | Prepare the book folder; numbered disc folders sort numerically |
| An M4B, M4A or other non-MP3 book, and you want speed control | Convert to MP3: `--convert-to mp3 --split-chapters` |
| An M4B with AAC or ALAC audio, and you want to keep the original audio | Remux to M4A: `--remux-to m4a` |
| A long variable-bitrate MP3 with imprecise seeking | Convert it to constant-bitrate MP3: `--convert-to mp3` |
| A DRM-protected book | Not supported; the tool does not remove DRM |

**Convert to MP3** when you want speed control, which works only with MP3. With
`--split-chapters`, each embedded chapter becomes its own numbered MP3, listed in
`BOOK.M3U`:

```sh
python3 tools/prepare_book.py '/path/to/Book.m4b' --convert-to mp3 --split-chapters --output '/Volumes/NANO/Audiobooks/Book' --write
```

Conversion re-encodes to 128 kb/s constant-bitrate MP3, because the player seeks
using the average bitrate. Without `--split-chapters` the result is one long
file; an M3U cannot add chapter marks inside a single MP3.

**Remux to M4A** to keep the original AAC or ALAC audio without re-encoding.
The player does not list `.m4b` files, but it does list `.m4a`. The result is
one long file without the embedded chapter list, and speed control is not
available. Playback of remuxed books on the player is not yet confirmed.

```sh
python3 tools/prepare_book.py '/path/to/Book.m4b' --remux-to m4a --output '/path/to/Prepared Book' --write
```

`--output` must be a new or empty folder outside the source book. The whole
result is staged first, so a failed conversion leaves no partial book behind.
Copy the complete output folder to the card if you didn't write it there
directly.

## Use it on the player

**Main menu:** Now Playing, Audiobooks, Meditations, Music Library, Folders,
Shuffle, Playback Settings, System Settings. Now Playing returns to whatever is
playing.

**Audiobooks** opens with **Continue *book name*** for the book you last played,
then **Browse books**. Continue survives a restart once you have played the book
with this firmware.

**Book menu**, when you open a prepared book: **Continue**, **Chapters**,
**Bookmarks** and **MP3 speed**. The speed you choose here applies when you
start playback from this menu.

**While a book plays:**

- Previous and Next seek ten seconds back or forward within the chapter. Hold
  to repeat.
- Press Previous twice quickly to save a bookmark.
- Double-click the main button for the player menu. **Speed** changes the speed
  immediately (MP3 only). **Bookmarks** starts with **Add bookmark**, followed
  by your saved bookmarks; select one to jump there.
- Speeds are 1×, 1.25×, 1.5×, 1.75× and 2×. Each book remembers its own speed.
- The position is saved when you stop and about every five minutes while
  playing.

**Meditations** open like ordinary folders. Select a track to play its folder in
natural name order with normal controls. Meditations have no Continue,
bookmarks or speed.

## Limits and troubleshooting

- **Book unavailable:** the playlist is missing or malformed, the selected
  chapter file is not listed exactly once in `BOOK.M3U`, or files changed after
  preparation. Check the playlist or prepare the book again.
- **Prepare failed / Use host tool:** prepare that book on a computer.
- **No Speed in the menu:** the book is not MP3. Convert it.
- **Start a book over:** delete its `BOOK.RSM` and prepare the book again.
- **Position after a power cut:** progress is saved about every five minutes,
  so a sudden reset can return to an earlier point.
- Up to 60 bookmarks per book. Folder playback holds up to 256 audio files.
  After a restart, select a folder track again to restore natural order.

## For maintainers

Implementation details and evidence:
[automatic preparation](automatic-book-preparation.md),
[playlist parser](playlists.md), [per-book speed](per-book-speed.md),
[book screen and Continue](book-screen-and-continue.md),
[player controls](audiobook-player-controls.md) and
[content navigation](content-navigation-followup.md).

The release builder copies this guide into the patch ZIP up to this heading and
rewrites its `prepare_book.py` commands for the bundle.

Device acceptance checklist:

- [ ] Main-menu and Audiobooks scan latency with a realistically full card.
- [ ] With no markers, both optional menu entries are absent.
- [ ] Add each marker, reopen the main menu, and verify the matching entry.
- [ ] With two roots, select either, and check Back returns through real parents.
- [ ] Remove a selected root or marker and verify no stale folder opens.
- [ ] The approved icons render correctly, including the music note.
- [ ] A prepared book's M3U opens with audible playback.
- [ ] Numbered chapters play in order, even with music Shuffle enabled.
- [ ] Next/Previous and the end of the book stay within that book.
- [ ] Seek within a long file; stop, reopen and verify the approximate time.
- [ ] Book A → music → book B → book A restores A's chapter and time.
- [ ] Normal shutdown and restart, then Continue and each book, restore position.
- [ ] Refresh the library; music Shuffle excludes marked trees.
- [ ] Meditation folders stay contained; ordinary music playback still works.
