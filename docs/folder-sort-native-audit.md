# Native File Browser natural ordering audit

2026-10-15. This audit covers physical File Browser module31, including the
Meditations/Music folder routes. It does not replace BOOK.M3U's explicit order
or change indexed Music metadata sorting. No device operation was performed.

## Existing native data flow

Browser global B is `0x03005f6c`. There are exactly two linked624-byte visible
nodes at `0x0300e73c` and `0x0300e9ac`, not an all-files linked list. Node fields:

| Offset | Meaning |
| --- | --- |
| +4 | next visible node |
| +8 | physical parent cluster |
| +12 | physical raw directory-entry index |
| +0x24 |42-byte native directory descriptor |
| +0x4e | classified native file type; zero means directory |
| +0x4f |32-byte native/FAT-compatible entry |
| +0x70 | UTF16 filename, up to256 units |

`0x03079592(filter,nodes,folder_record,visible_start,kind)` fills at most two
nodes. It enumerates directories before files, preserving physical order within
each group. It has no filename comparator. First/next calls are
`0x0305dce0` and `0x0305dcb4`, through `0x0305d668`; physical mode3 increments
the raw index at `0x0305d6b8..c0`. Mode1 instead reads indexed database records;
it is not an alphabetic-sort flag for the physical browser.

Names are loaded only after a visible ordinal is chosen. FAT uses
`0x0305e388(parent,index,kind,out)`. exFAT uses
`0x0305d520(directory_descriptor,index,kind,out)` and then
`0x0305fa94(raw_entry,name)` to produce the native compatible entry before
classification at `0x03079484`. Keep these filesystem-specific operations;
copying only the display name would break selection and directory entry.

Count function `0x0307974e(filter,folder_record,kind)` uses native FAT directory
and file counters `0x0305c9e8`/`0x0305de7e`, and exFAT
`0x0305cad2`/`0x0305e006`. The folder record holds total at+0, file count at+2,
directory count at+4, parent cluster at+8, descriptor at+12. It is the56-byte
per-depth record at B+56*depth+12. B+0x1cc is depth; B+0x1ce+2*depth is visible
page start; B+0x1de+2*depth saves selected row on descent; B+0x1ee is selected
row. These are display ordinals, not raw directory indices.

## Recommended bounded mapping

Keep native counts/filtering. Replace the common enumerator entry with a checked
browser-local helper, so existing paging callers all receive ordered nodes.
Build a map of raw32-bit directory indices, with ordering key:

1. directory before file;
2. natural UTF16 filename comparison;
3. raw directory index as a deterministic tie-break.

Natural comparison must not overflow on long numeric runs. Case/leading-zero
ties are resolved by raw index. The shared implementation is
`browser_sort/natural.c`; do not duplicate it in native assembly.

Use1024 raw indices (4096B), not an unbounded list or a u16 index that silently
truncates large raw-directory offsets. Two256-unit name buffers add1024B.
Provider callbacks expose reset/next raw key and direct name/type lookup.
Comparisons use direct keyed entry/name reads, never invoke the native visible
row enumerator repeatedly. This avoids rescanning from directory start on each
comparison. Only the final two chosen entries populate native nodes.

For more than1024 accepted entries, select a sorted window with a bounded
max-heap: scan all accepted keys after the previous window's last key, retain
the smallest1024, then heapsort ascending. Cache the current window's start
rank and final pivot. Normal forward navigation builds the next window only
when crossing its boundary. A backward/deep arbitrary request can regenerate
windows from the start; correctness is retained at higher I/O cost. There is
no silent unsorted fallback or truncation. Iterator/name-read errors invalidate
the entire pending map; never publish a partial ordered directory.

The provider owns a valid native directory descriptor and filter. Preserve
native hidden/system/.nomusic behavior through the existing filtered iterator
rather than inventing a second eligibility rule. Retain directory/file counts
and validate them against the accepted scan before publication. A changing
medium or directory must not produce a mixed snapshot.

## File selection: retain the physical playback ordinal

The FAT file-selection path at `0x0307ad1c..3a` currently derives its audio
ordinal from sorted-page-sensitive values (page+row-directory_count+1). That
calculation must not survive a display reorder.

There is an existing identity-based alternative: native
`0x0307aa10(selected_node,1)` returns the original ordinal for the selected
native file type. Its FAT implementation scans/compares the11-byte short alias;
its exFAT implementation resolves/compares the filename. It does not rely on
display position. Preserve node raw entry/name/parent exactly.

A minimal candidate hook is changing the FS==3 branch at `0x0307ad18` to route
all actual file selections through existing `0x0307aefc`. That path already
calls `aa10(node,1)` at `0x0307af1e..22`, and preserves extra native ordinal
conversion for other file types at `0x0307af04..1c`. This must be exercised for
FAT/exFAT audio and nonaudio types, plus existing custom M3U launch hooks,
before accepting it. `0x0305e64c` remains the native folder/global ordinal
conversion; it is not a sorting function.

This preserves the file the user selected. Native Next/Previous during playback
continues its existing physical sequence; natural playback sequencing is a
separate resident-player change, while BOOK.M3U order remains authoritative.

## Back and ancestry

Normal descent in `0x0307acb6` saves selected row at `0x0307ad74`, increments
depth, and copies the selected node's physical cluster into the child ancestry
record. Sorted page positions therefore work during an unchanged browser
session, provided raw node identity remains intact.

Back function `0x03079c8e` decrements depth at `0x03079c9e`, restores a saved
row, recounts at `0x03079cc2`, and enumerates the parent at `0x03079cea`.
Wrap that last call: recover the child cluster from the next-depth record
(B+56*(new_depth+1)+20), find the child's raw directory entry, and compute its
natural rank in the parent. Set parent page=rank&~1 and row=rank&1, then call
the ordered enumerator. This also corrects ancestry synthesized by
`navigation.c:install_root()`, whose saved ordinals currently count raw entries.
Do not require a growing per-depth mapping cache. If the child disappeared,
clamp to a valid parent selection and do not substitute a different raw child.

Returning from playback can likewise start with native physical ordinals.
Browser reentry must restore by physical selected identity (native decoder
record/raw index), not reinterpret those ordinals as sorted positions. Initial
module31 restore/count/enumerate sequence is `0x03079794`, calls at
`0x0307985c` and `0x030798c4`; it needs an identity-to-rank wrapper analogous to
Back. This is an implementation test gate, not yet a proven hook.

## Cache invalidation and ownership

Only one current-directory window is cached. Key it by device, filesystem,
parent cluster, exFAT descriptor identity/flags, filter and native kind. Clear
valid before any rebuild and set it only after a complete successful scan/sort.
Invalidate on overlay reload, directory change, directory recount/refresh,
media/device change, native mutation/delete paths, and any read/identity error.
The count-function wrapper provides a common recount invalidation boundary;
ordinary paging can reuse the map. Before selection, reread and validate the
chosen raw entry against the displayed node to reject stale media changes.

The16B remaining playback RAM must not be expanded. Module31 native code is
9308B at execution`0x03079418..0x0307b874`; its existing BSS
`0x0300e73c..0x0300efa2` is occupied and is not scratch.

The memory audit proposes relocating module31's *flash backing* to verified
zero refresh-buffer tail`[0x3e200,0x41748)` (13640B): native9308B plus at most
4332B helper/initialized metadata, keeping the same execution base. The stock
module loader then loads the appended helper; no second loader is required.
NOLOAD map/name scratch follows the appended code and stays below decoder33's
`0x03080470` start. An initialized valid=0 word in the loaded helper invalidates
the scratch on every overlay reload. Exact backing end/alignment is owned by
the memory/layout audit and must be pinned before implementation.

Declared overlaps with the broader execution gap`0x0307b874..0x03080470` are
modules9/12/15/16/18/19/20/27/32/40/63. They must be shown mutually exclusive
with active browser helper execution; absence of absolute pointers alone is
not proof. Prefer the smallest verified interval. The helper/map must never
execute after another overlay takes ownership. Existing layout validation
currently requires unchanged module records, so allow only the exact audited
module31 backing/length change, not a blanket relaxation.

## Required execution tests

- Physical order CD2-3, CD1-1, CD10-1, CD2-1 produces natural visible order;
  include case/leading-zero ties, non-ASCII names and long digit runs.
- FAT and exFAT, directories before files, native filters and hidden entries.
- Empty/one/two items;1024/1025 and multiple-window boundaries; reverse/wrap
  navigation and arbitrary requested page; raw indices above65535.
- Full node identities match each rendered name. Native selection reaches the
  intended file, with original playback ordinal, including M3U interception.
- Enter child then Back; marked-root direct entry then Back; playback return;
  parent changes while browsing; removed selected child and media replacement.
- Incomplete reads/name failures never publish partial maps or stale nodes.
- Actual overlay load invalidates cache; other UI overlays then browser reload;
  refresh and decoder coexistence; unchanged reboot/persistent payload bounds.
- Measure callback/read counts for representative100/1000/large folders. Host
  instruction or I/O counts are not hardware latency or safety evidence.

## Implemented overlay extension and verification

The implementation now lives in `browser_sort/order.c`, `adapter.c` and four
local hooks. It uses the1024-key bounded max-heap window described above. The
native common enumeration entry9592 branches to the helper. The count entry974e
invalidates cache and replays its native prologue; the selected-node siteacf8
validates physical identity before continuing; ad18 routes file selection
through the native identity-derived ordinal path. Existing resident M3U
interception precedesacf8 and remains independent of this overlay.

The adapter recognizes the original enumeration return addresses98c8 and9cee
for playback reentry and Back. Reentry's native79794 routine always reconstructs
the current physical ordinal from305d130 plus the directory count; the helper
translates it to a sorted rank. Back resolves the child cluster from the next
depth record, using+24 for exFAT and+20 for FAT. Native descent writes both,
but using the filesystem-specific field also handles restored ancestry.

Both chosen rows are built in unpublished scratch before either native node is
updated. Any iterator/count/name error empties both visible rows and current
counts. Stale selection or a device/filesystem change refuses the action and
clears both rows. The cache key includes device byte0300d173, filesystem, native
filter/kind and the54 meaningful folder-record bytes; recount and overlay reload
invalidate it. The copied `.sort_metadata` word resets validity on every load.
The filesystem lock covers a synchronous sort/publish transaction and the
provider feeds the native watchdog during iteration and keyed reads.

Native name helpers ignore underlying read errors, and FAT may write260 UTF16
units. The adapter therefore decodes FAT long/short names and exFAT name entries
with checked raw reads into bounded256-unit names. Valid exFAT entries retain
the native compatible short alias, attributes, flags, cluster and valid size.
Native filtering/counters/iteration/classification still run, and the selected
raw index remains unchanged. Malformed or incomplete names fail closed.

The isolated extension builds to2944 copied bytes plus6560 NOLOAD bytes,
9504 bytes total. Copied-code headroom is1388 bytes under the4332-byte bound.
This does not grow the resident playback payload or relax the decoder/reboot
boundaries. The build/layout owner validates relocated backing and module load.

Verification performed: five host window tests (including2305 entries across
three windows, raw keys above65535, numeric/case ties and callback failures),
and ten ARM adapter tests. ARM cases cover FAT/exFAT natural row identities,
Back, physical-ordinal reentry, stale selection, device/filesystem replacement,
count/read failures and cached paging. One case executes the actual native
iterator305dcb4/305d668, counters, names used by that iterator and classifier,
with only raw I/O, lock and watchdog substituted. Separate parent-owned native
selection tests verify FAT/exFAT original audio ordinals. These are host checks,
not hardware latency, audio acceptance or installation-safety evidence.

Measured raw-directory reads for reverse-ordered FAT TrackN.mp3 fixtures:

| Accepted entries | First sorted page | Next cached page | Page1024 rebuild |
| ---: | ---: | ---: | ---: |
|100|3981|4|not applicable|
|1000|65865|4|not applicable|
|2305|206646|4|147146|

These execute the native iterator and checked adapter under Unicorn. Counts
include repeated name reads for heap comparisons, not device sectors (native
sector caching may coalesce many). The2305-entry run verified Track0, Track2
and Track1024 labels through the same adapter. Its initial200-million-instruction harness ceiling was exhausted
inside memset; resuming with a larger allowance completed correctly. This is a
harness limit, not a returned firmware failure. The ARM fixture now asserts
arrival at its expected return address so truncation cannot silently pass.
Large-directory initial sorting has substantial I/O and CPU cost; hardware
latency remains unmeasured. Cached two-row scrolling is much cheaper. Potential
future optimization is avoiding full name-buffer clearing on each comparison,
with explicit termination/identity tests before changing that behavior.

Measurement log: `builds/research/browser-sort/read-counts.txt`. Final focused
ARM log: `builds/research/browser-sort/arm-verification.log` (12 tests, including
the parent-owned selection cases). Host window log:
`builds/research/browser-sort/order-verification.log` (5 tests). Independent
scoped reviewer reported no remaining concrete correctness/memory blocker;
broader mixed-content filters and physical-device acceptance remain limits.

## Hardware follow-up: exFAT selection refusal

User reported20261102 reaches Meditations but Enter on The Gateway Experience
has no effect. Reproduced in native ARM execution:305fa94 synthesizes the11-byte
short alias using0300d144 clock modulo1000. Comparing all32 converted entry bytes
therefore falsely treated an unchanged entry as replaced between rendering and
selection. Earlier tests kept the clock fixed and missed this boundary.

Correction compares bytes11..31 and the full UTF16 name for exFAT, retaining
parent/raw-index/device/filesystem guards and checked physical reread. FAT still
compares all32 on-disk bytes. New real-native regression passes after clock
advances123→456; changed cluster, length, name and flags still reject and clear
the displayed nodes. Scoped independent review found no blocker. Hardware
confirmation of the correction remains pending.
