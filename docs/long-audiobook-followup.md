# Long audiobook follow-up — 2026-10-18

Offline RC 20261116/recovery 20261117. No device staging, installation, commit or push. The reported
ten-second seek restarting Soulcraft is **not yet reproduced or fixed**.

## Source changes

- Native Now Playing time painter retains hours instead of discarding them.
  Compact digits cover the entire unsigned millisecond range; the chapter
  counter moves from x40 to x48 to avoid overlap. This is a display correction,
  not evidence that the seek clock wrapped.
- While a valid book is playing, the player poll attempts to save Continue about
  every five minutes through the existing alternating CRC-protected RSM journal.
  Paused playback, scratch ownership and pending seek/relaunch defer the attempt.
  Failed writes back off for five minutes. Successful ordinary saves reset the
  timer. Existing valid RSM companions are required; no manual bookmarks or
  history entries are created. This does not provide undo after a bookmark jump.
- Book-menu and pending-launch paths share storage to recover 512 bytes. Browser
  paths are built separately and published only after validation; explicit menu
  launches also require matching retained paths. Failed native launch selection preserves the
  menu path. Idle menu discovery may replace it; active and returning menu
  guards prevent writes while a menu launch retains ownership. Loader boundaries and bootloader are unchanged.
- `tools/prepare_book.py --convert-to mp3 --split-chapters --output <new-folder>`
  previews one MP3 per embedded chapter plus BOOK.M3U/RSM/BMK; add `--write` to
  export. The original remains unchanged. It refuses a nonempty destination.
  Chapter starts partition the complete source from zero through its duration.
  Transcoding uses output seeking, decoding preceding audio to retain AAC
  decoder history at chapter cuts ([FFmpeg documentation](https://ffmpeg.org/ffmpeg.html#Main-options)).

The sibling BKZ Books repository has matching automatic chapter export for new
Echo Nano transfers from M4B/M4A files. Legacy receipts retain their original
single-file layout and state; they are not silently converted. Fresh exports
use numbered MP3 files and an ordered BOOK.M3U. The firmware counts M3U files;
it does not implement timestamp sections within one MP3.

## Evidence and remaining work

The mounted Bembun T5 SSD contains Soulcraft's original M4B: 51,373 seconds,
AAC 22,050 Hz stereo, 16 embedded chapters. No Soulcraft MP3 or Nano volume was
found. A local reproduction using BKZ's original one-file conversion command
has a plausible 51,373-second duration. This does not establish the exact bytes
or player behavior of the file that restarted. The listening speed is unknown.

Native time conversion retains hours; the former painter discarded them.
The inspected custom seek path uses full millisecond values, and the native MP3
offset calculation uses a wide multiplication. No one-hour seek overflow has
been established. Obtain the actual player MP3, its M3U/RSM and the listening
speed before choosing a decoder or seek fix. Also establish whether playback
was launched through the book playlist or as an ordinary standalone file.

Verification: the full firmware suite passed 593 tests in 553.952 seconds.
The first run's three old launch-fixture failures were corrected by retaining
the selected path as the real menu does. The final suite includes the new poll,
path-ownership, hours-rendering and timeout checks. BKZ passes 120 tests. After
the output-seeking adjustment, all 17 host preparation/remux checks and the full
120-test BKZ suite pass again; firmware image bytes are unchanged.

All four requested `/revx` reviewers returned: Sonnet, Codex, Grok and GLM.
Sonnet reviewed the initial snapshot; its rerun was separately rejected by
automatic approval. The other three reviewed the corrected snapshot. Codex and
Grok independently found two BKZ long-name compatibility regressions, which
were fixed while retaining historical 65-character destination/non-chapter rules.
The new long-name ready/repair test passes; Codex and Grok follow-ups approved
the compatibility correction with no remaining concrete blockers.
Codex scoped review approved the final chapter-boundary correction; final review
artifacts and dispositions are recorded with the candidate archive.

The synthetic 65,535-hour case is outside the sole native caller's u32-ms
contract (maximum 1,193 hours); the renderer's stack padding preserves alignment.
The periodic save may occur on the first playing poll after a long pause. It
uses existing validated position/journal logic; synchronous write latency and
its audio effect remain hardware checks, not claimed solved by offline tests.

The offline RC uses 26,048 bytes text + 29,928 BSS, leaving 328 bytes
below the unchanged 0x0309fff0 boundary and 64 bytes in its sector-rounded text
reservation. The exact pair is archived under
`builds/phase4k-long-books-20261018/reviewed/manifest.json`. It is uninstalled
and carries limited offline approval, not a device-safety guarantee. Hardware boot, clock
legibility, periodic persistence and long-file seek/audio acceptance are pending.
Local media and disassembly evidence stay ignored in `builds/research/long-book/`.

## Actual SD file inspected — 2026-10-18

Fresh identification: Music SD, exFAT, UUID
693B8030-CB7E-32AE-999B-5D186782949A, 255,936,692,224-byte filesystem, in the
Mac's SD reader. Historical device identifier disk4s1 must not be reused without
identification. No Nano internal volume was present. All card access was read-only.

Soulcraft's 603,055,993-byte MP3 matches its original BKZ receipt SHA256
`360b62e8659bd444411b6c5469512ef21e27bd9764cb7fc133978a6a66111d07`.
It is MPEG-2 Layer III, 22,050 Hz stereo, VBR with Xing metadata, no embedded
chapters. BOOK.M3U references this one file. Both RSM and BMK journal sectors
have valid CRCs. RSM generations 37/38 record 3,627,352/6,169,914 ms and 1x;
the latest six bookmarks extend from 3,532,168 to 6,167,668 ms. Persistence has
therefore retained positions beyond an hour. This does not establish the speed
or launch route at the moment of the reported failure.

The actual stock module-73 metadata parser, executed offline with file callbacks
against a local copy, reports audio offset 902, size 603,055,091, rate 22,050 and
average bitrate 93,909. Its seek calculation/scanner reaches valid frames around
one hour, both saved positions and 50,000 seconds, with correct sample clocks.
This diagnostic stops before DSP restart and supplies decoder header state;
it does not exercise the full player, device filesystem or live IPC sequence.

**Confirmed separate problem:** the native seek implementation uses average
bitrate rather than the VBR seek table. Counting actual MP3 frames shows the
requested 3,600-second offset lands at source 3,574.152 seconds. A request for
3,637.352 seconds lands at 3,612.839 seconds, so a forward ten-second seek from
3,627.352 can audibly move backward. At 6,179.914 seconds it lands at 6,127.569.
This explains inaccurate seeks, not a proven restart at source zero.

Future MP3 conversions in BKZ and prepare_book.py now use 128 kb/s constant
bitrate instead of VBR quality 2. Chapter export remains as above. Existing MP3
inputs/transfers are preserved; Soulcraft on the SD card has not been replaced.
Real short chapter conversions pass at 128 kb/s in both exporters. Long-book
and hardware audio acceptance remain pending.

Evidence is ignored under `builds/device-check/soulcraft-20261018/`: exact copied
audio, original metadata/journals, ffprobe metadata, native parser/seek output
and actual frame positions. The reusable diagnostic is
`builds/research/long-book/probe_native_mp3.py`. The whole-book restart remains
open, including whether native Next was reached through standalone playback.

### User clarified launch route

User explicitly confirmed Audiobooks / Continue: the display wrapped after
59:59, then pressing Next restarted the book. Standalone-file launch is no
longer a supported explanation for this report. Keep the VBR seek inaccuracy
separate from the reported complete restart.

Inspected command-251 dispatch and module-42 seek IPC retain the full 32-bit
millisecond target. Ordinary-player hot-seek resumes through 0x03081f10; prior
focused seek coverage replaces that native resume function, so it does not
establish correctness of the complete playing→pause→seek→resume sequence.

An expanded offline diagnostic (`probe_native_mp3_restart.py`) maps both code
aliases used by native indirect pointers and begins full decoder startup, but
fresh initialization reaches a hardware-dependent decode loop and exhausts its
instruction budget before returning. Subsequent seek output from that incomplete
state is invalid evidence. An earlier run that returned after reusing pre-parser
state had a doubled audio start offset and is also not a valid full-startup result.
No full decoder restart reproduction or additional firmware correction is claimed.
Next useful hardware distinction: paused Next versus Next during active playback,
using the existing bookmark around 1:00:23 on the current installed firmware.

## Review scope and accepted restrictions

New automatic BKZ chapter export requires usable chapter metadata and ffprobe.
Malformed chapter geometry produces an error before publication; it does not
silently discard the requested chapter structure. Explicit whole-file conversion
is available through `prepare_book.py --convert-to mp3` without `--split-chapters`.
Existing receipt validation retains its old filename rules and layout.

The periodic journal update is best-effort: a failed or no-op attempt waits about
five minutes before trying again. Therefore five minutes is not a guaranteed
maximum loss window after a crash. Saved positions also depend on the native
filesystem's persistence behavior, which needs device acceptance.

FFmpeg's documented default `accurate_seek` discards samples before the requested
input timestamp during transcoding, so the review's keyframe-only claim was too
broad. However, a real AAC chirp diagnostic found differing initial samples even
though sample counts and alignment matched. Chapter export therefore now uses
output seeking (`-ss` after `-i`) to preserve decoder history from the start.
This costs additional decoding time for later chapters. Both exporters exercise
the command ordering in their real chapter-export tests.
See [FFmpeg main options](https://ffmpeg.org/ffmpeg.html#Main-options).
