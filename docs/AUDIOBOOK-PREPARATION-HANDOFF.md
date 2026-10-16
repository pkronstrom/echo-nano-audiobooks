# Prepare audiobooks for Echo Nano

Run commands from the repository root.

The installed firmware and tagged RC update existing state files; prepare new
books on the computer for those versions. The post-RC candidate adds guarded
automatic preparation for simple book folders, but is not yet hardware tested.
See [automatic preparation](automatic-book-preparation.md) for its limits and
fallback. The following host workflow remains supported for all versions.

## SD layout

```text
Music SD/
  Music/
  Audiobooks/
    .audiobook
    Book Name/
      01 Chapter.mp3
      02 Chapter.mp3
      BOOK.M3U
      BOOK.RSM
      BOOK.BMK
  Meditations/
    .meditation
```

The markers are empty files inside the collection roots. `.audiobook` and
`.meditation` enable their menu entries and recursively exclude those folders
from music/global Shuffle. A root `.nomusic` also excludes recursively, but is
redundant when the category marker exists. Per-book `.nomusic` files created by
the preparation tool are harmless and useful if a book is moved elsewhere.

## Preparation

Confirm the actual mounted SD path; do not assume the example volume name.
Copy each book into its own folder, then run from the repository:

```sh
python3 tools/prepare_book.py '/Volumes/Music SD/Audiobooks/Book Name'
python3 tools/prepare_book.py '/Volumes/Music SD/Audiobooks/Book Name' --write
```

The first command previews; the second creates missing companions:

- `BOOK.M3U`: chapter playlist, naturally sorted by relative filename/disc folder.
- `BOOK.RSM`: 1024-byte resume journal for chapter and position.
- `BOOK.BMK`: 1024-byte bookmark journal.
- `.nomusic`: recursive music exclusion for this book folder.

Do not create empty RSM/BMK files manually: they require valid headers and CRCs.
Rerunning preserves existing playlists and valid state files; corrupt/unknown
state files cause an error and are preserved. Existing playlists are **not**
regenerated when tracks are added. Check chapter ordering explicitly; tags do
not determine order. Run once per book, not on the entire audiobook collection.

Prefer folder preparation even for one long file, so the book gets `BOOK.M3U`
and opens consistently through the Audiobooks menu. Direct single-file input is
also supported but names companions after that file instead of `BOOK`.

For M4B or other unsupported inputs, inspect `--help` for explicit MP3 conversion
or M4A remux options. Do not just rename the extension. MP3 is the currently tested
format for adjustable playback speed; preserve originals when converting.

## Finish and check

Safely eject the card. On the Nano, run **Media Library Refresh** to update music
exclusions. Open the prepared book through **Audiobooks**, using its playlist/book
menu rather than selecting an MP3 directly. Verify Continue resumes and a saved
bookmark appears. Preserve M3U/RSM/BMK when moving or backing up a book; changing
playlist order or file identity can invalidate saved positions.

This task concerns SD content only: no firmware update or device formatting.
