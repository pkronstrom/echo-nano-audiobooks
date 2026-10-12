# Tomorrow's Nano test

Start with **P3a**, stock power settings. The firmware image is unchanged from
the 107-check checkpoint; tonight's additions improve preparation, release
packaging and the icon review, without adding another untested player hook.

## 1. Firmware

Ready locally:

- Custom: `builds/phase3a/custom/NANOV170.IMG` (P3a, 20261012).
- Recovery: `builds/phase3a/recovery/NANOV170.IMG` (stock, 20261013).

The custom date must be newer than the device's installed image. Copy only the
custom image to the internal-storage root, eject and restart; check About for
P3a. Keep recovery on the computer. If recovery was already installed, use a
newer custom date when generating the next pair.

For the future GitHub distribution, `builds/release/echo-nano-p3a.zip` contains
patches and a Python applier, not complete firmware. Extract it and run:

```sh
python3 apply_release.py --input '/path/to/original/NANOV170.IMG' --output ./nano-ready
```

This creates the same custom image and a later-dated stock recovery. It never
flashes the player. See [release instructions](releases.md).

## 2. One book first

For a folder of MP3 chapters, run from this repository:

```sh
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/Your Book'
python3 tools/prepare_book.py '/Volumes/NANO/Audiobooks/Your Book' --write
```

Inspect the preview order before the second command. On the player, select
**File Browser → Your Book → BOOK.M3U**. Selecting the audio file directly uses
ordinary folder playback rather than the independent book-resume path.

For M4B containing AAC/ALAC, first try the audio-preserving option on the computer:

```sh
python3 tools/prepare_book.py '/path/to/Book.m4b' --remux-to m4a --output '/path/to/Prepared Book' --write
```

Copy the prepared directory onto the player. MP3 conversion is an explicit
fallback if needed. See [all preparation options](audiobooks.md).

## 3. Short acceptance run

1. Check sound, chapter order and next/previous within the book.
2. Seek into a chapter with the existing long-press controls.
3. Play music, then reopen the book's M3U: check chapter/time.
4. Repeat with a second book. Normal shutdown/restart, then reopen both M3Us.
5. Refresh the music library: marked books and meditation should stay out of
   library/Shuffle but remain playable in File Browser.
6. Try your FLAC meditation phase folders and direct file selection.

If something fails, record the exact action, filename/format, approximate time,
filesystem (FAT/exFAT if known) and whether rebooting changes it. Keep
`CFWLOG.TXT` and the affected M3U/RSM files; avoid overwriting the evidence with
repeated preparation. Abrupt-power-loss behavior is not yet hardware verified.

## 4. Icon review

Open [icon-review.html](icon-review.html), compare at native size, choose an
overall direction and individual approvals, add comments, then **Copy feedback**
and paste it into the chat. Download is a fallback. This is icons only; it
neither changes firmware nor approves navigation shortcuts.

Dedicated book/meditation menu shortcuts still require native folder traversal
and Back-navigation tests; see [navigation findings](navigation.md). The
[community performance review](community-patches.md) explains why power patches
remain disabled. No additional unique Nano patch was found upstream tonight.
