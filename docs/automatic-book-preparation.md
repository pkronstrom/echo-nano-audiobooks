# Automatic book preparation

Local `phase4j-release-candidate` at `219d972` (candidate date20261114, stock
recovery date20261115). All578 tests passed in498.928s; scoped and final
independent reviews gave limited offline approval. Reproducible paired images
are archived in `builds/phase4j-auto-preparation-20261016/reviewed/manifest.json`.
This candidate is not staged, installed or hardware-accepted. The earlier local
`phase4i-release-candidate` at `bac9473` remains preserved. Neither tag is
pushed or published. The hardware-installed/staged image and its startup
observations are tracked separately in [the incident record](device-test-and-restore.md).

## Using it

Keep Music, Audiobooks and Meditations as parallel folders. Put `.audiobook` in
the Audiobooks collection root and `.meditation` in the Meditations root. These
are empty marker files; they also exclude their trees from Music after refresh.

Put each book in its own subfolder. When you enter that folder through Audiobooks,
the new candidate can create:

- `BOOK.M3U`, listing directly contained supported audio files in natural order;
- `BOOK.RSM`, the existing 1024-byte resume/speed journal;
- `BOOK.BMK`, the existing 1024-byte bookmark journal.

A single long MP3 works the same way. Preparation opens the existing Continue /
Chapters / Bookmarks menu. Later entries preserve the playlist and saved state.
Adding chapters does not regenerate an existing playlist.

Existing `BOOK.M3U` keeps its exact order; only missing fixed-name companions are
created. A differently named M3U suppresses automatic generation. Music and
Meditations keep ordinary folder navigation. Collection roots and folders with
nested disc/book directories are not merged automatically.

## Supported scope and fallback

Generation supports 1–256 direct audio files, names up to127 UTF-16 units, and
complete absolute chapter paths up to255 units. No conversion is performed; M4B
still needs the existing explicit host remux/conversion workflow.

The conservative storage adapter requires 512-byte sectors, at most256 sectors
per cluster, a one-cluster book directory, one FAT copy, and a first contiguous
free run contained within one allocation sector. exFAT additionally requires the
verified bitmap layout used by its native writer: bitmap ID0 at cluster2 with
a contiguous FAT chain, at most4096 bitmap sectors, and a one-cluster root.
Each new exFAT three-entry set must fit one directory sector. These restrictions
can refuse otherwise valid cards/folders; use host preparation in that case.
Larger book directories bypass preparation and retain native browsing and
existing playlist entry, including playlists stored beyond the first cluster.

`Prepare failed` / `Use host tool` preserves existing files. Press Enter or Back
to dismiss it. Run `python3 tools/prepare_book.py '/path/to/Book'` to inspect the
folder, then add `--write` for supported host preparation. In a patch bundle use
`python3 prepare_book.py` instead. Unknown/corrupt companions and existing
`BOOK.TMP` are preserved for manual inspection; do not create empty state files.

Creation is separate from normal alternating-sector progress saving. Interrupted
initial preparation can leave an empty/partial new companion or `BOOK.TMP`, and
unreferenced newly reserved clusters. The firmware does not delete, repair or
retry those files automatically. Existing metadata/content is preserved in the
tested sector-failure model; torn card sectors, removal/replacement with an
indistinguishable mount, physical durability and hardware timing remain untested.

## Implementation and verification

The cold browser helper uses the native FAT/exFAT insertion, mutation, file and
entry-writing routines. It checks cache ownership, names, device/geometry and
free extents; preallocates a bounded run; streams aligned packets; closes and
reopens through the native reader; then publishes a verified `BOOK.TMP` by
same-length rename. Native write success alone is never accepted as persistence.
Existing journal formats and resident playback allocations are unchanged.

Browser row rendering, folder launch and preparation share scratch only across
disjoint lifetimes. The resident payload remains25864B text plus30440B BSS,
ending at `0x0309fff0`. Resident flash reservation shrinks to26112B, exactly its
sector-rounded read length. Browser backing is `0x3c800..0x42348`, verified empty
in stock, covering the refresh sort-A tail and first3KiB of sort B. Browser
execution still ends below `0x03080470`; the bootloader is untouched.
The linked helper is13960B text plus5320B BSS, leaving168B after alignment.

The browser keeps64 natural-sort keys per window and streams further windows
without truncation; the playback queue still supports256 audio entries. Larger
folder pages may need another scan. New flags live in copied reset metadata,
so another overlay cannot leave stale preparation/error state on return.

Focused tests execute the real native filesystem with only sector I/O, IRQ locks
and watchdog hardware substituted. Separate regressions load every browser byte
through both the stock module loader and byte reader, in both firmware slots.
See the investigation and final archive manifest for exact review/test results;
host tests do not establish device acceptance.

Paired candidate20261114 / stock recovery20261115 and exact hashes are archived
locally in `builds/phase4j-auto-preparation-20261016/reviewed/manifest.json`.
Isolated payload rebuilds reproduce both complete images byte-for-byte. The
source remains on `feature/automatic-book-preparation`; no push or staging.


## Large-cluster fallback correction — 2026-10-18

Hardware feedback for20261116 reported Prepare failed for every prepared book.
All11 inspected book folders had playlists and CRC-valid resume/bookmark files.
A512-sector exFAT fixture reproduced the refusal before checking existing files;
resident playlist lookup still succeeded. Source correction bypasses automatic
preparation when cluster geometry exceeds its4096-entry scan bound, allowing
the existing native/resident book-entry route. This matches the existing behavior
for multi-cluster directories. It does not enable file creation on that geometry.

The real card's256KiB allocations suggest this geometry, but direct boot-sector
reads were OS-blocked even after administrator authorization. Keep that device
attribution provisional until hardware retest. The corrected ARM path reaches
Continue without any sector writes. Device contents were not regenerated.
Candidate20261118/recovery20261119 passes595 full checks in568.570s,18 focused
checks and scoped independent review. Isolated images reproduce byte for byte.
Archive: `builds/phase4k-long-books-20261018/prepare-fallback-reviewed/manifest.json`.
Hardware retest remains pending; see the incident log.
