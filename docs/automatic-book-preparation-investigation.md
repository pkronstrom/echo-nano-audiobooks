# Automatic audiobook preparation: feasibility investigation

> Historical research checkpoints below are superseded by the linked cold-browser
> implementation. See [current behavior and limits](automatic-book-preparation.md).
> Automatic creation/publication is implemented and offline verified:578 tests
> pass, with limited independent offline approval. Nothing has been installed
> on the Nano for this work.

Date: 2026-10-16. Research after the local annotated tag
`phase4i-release-candidate`, which points to
`bac947351396fa21e66eb8606f96a67da65cd872`. The tag excludes this research.
Nothing was pushed, published, built for installation, or written to a device.

## Finding

Automatic preparation is feasible in principle. The stock firmware already
contains file creation and growing writes; our refresh logger calls them.
Pre-created M3U/RSM/BMK files are a limitation of the present audiobook adapter,
not an established hardware restriction. A safe integration is still unfinished.

The intended user experience could be: copy one book folder into the marked
Audiobooks collection, open it, and have the player prepare missing metadata
once. Existing custom playlists, saved positions and bookmarks must survive.
This does not convert codecs or remove DRM.

## Evidence

The checked stock image SHA256 is
`54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
REA 6.4.0 / Ghidra 12.1.4 analyzed a non-flashable ELF containing only resident
module0, with explicit analyst-supplied Thumb function labels. Initialized
sections were verified byte-for-byte against stock. The wrapper is under
`builds/research/auto-create/`; generated binaries and evidence remain ignored.

| Observation | Evidence and limits |
| --- | --- |
| Creation already exists | `src/fw.h:fw_file_create` is0x0305fba6; `src/cfw.c:write_log` creates CFWLOG.TXT. This proves source usage, not arbitrary SD-directory validation. |
| The public create entry sets attribute0x20 and branches to0x0305f89c | Stock assembly and REA `create-function.json`, evidence `ev_762666ed9eb21fd6ae378babaad48178cfbef9f56f43d785067a36cdeccac722`. |
| The wrapper copies exactly11 filename bytes; FAT receives padded8.3, exFAT byte-widens a dotted name | Actual instructions0x0305f8ea..0x0305f906. This is not a general UTF-16 long-filename creation API. Directory resolvers0x0305ba94/0x0305b9b0 also consume byte-oriented short components. |
| FAT wrapper checks parent and insertion failure |0x0305f944..0x0305f95a. Emulated successful insertion returns handle0; insertion errors7/10 and invalid parent return-1. |
| exFAT wrapper does not propagate parent/insertion failure | Calls0x0305b9b0 and0x0305f114 are followed by handle initialization, without checking their result. Mocked failure injection still returns handle0/open flags3. This does not prove a real disk failure succeeded. |
| exFAT insertion finds inactive slots without checking the requested name | Real0x0305f114 slot scan against synthetic existing BOOK.BMK chooses index3 and reaches directory writing for a second same-name entry. REA `exfat-insert-function.json`, evidence `ev_3b9586679200c1aacaac784ddb24a867443dc96a9025cc1e05380eb8540a45aa`. |
| Exhausted handles are rejected | All eight handles marked open: wrapper returns-1 before insertion on both filesystems. |
| Allocation is deferred beyond empty-file creation | Wrapper initializes size/first cluster/current cluster to zero. Stock writer0x0305fda4 includes allocator calls0x0305e912/0x0305e9c2. REA `write-function.json`, evidence `ev_22657385bc060bade8d319cf96e66e731e443f6e687915df529a7f0b6fb38157`, corroborates those allocation branches. Actual free-space accounting, directory expansion, write/close persistence and crash recovery are not yet exercised. |

The reusable [probe](../experiments/native_file_creation/probe_stock_create.py)
passes 11 bounded ARM cases: nine wrapper scenarios and two duplicate scenarios.
It executes original stock instructions but substitutes directory resolution,
selected lookup/insertion boundaries, and disk-boundary writes. It cannot access
attached media. The duplicate exFAT case executes the native slot scanner.
Maximum observed emulated stack depth is 1448B in that case, excluding deeper
actual directory-write/allocation routines. It is not a complete stack bound.

Run from the repository root, with the existing Unicorn test environment:

```sh
builds/tools/test-env/bin/python experiments/native_file_creation/probe_stock_create.py
```

Complete local results: `builds/research/auto-create/probes.json`. These probes
are research, separate from the tagged firmware's 488-test verification.

## Approaches

| Approach | Advantages | Cost / limitation |
| --- | --- | --- |
| Create missing companions first; generate BOOK.M3U afterward | Reuses the existing validated journal/playback path; normal book folders can eventually need no PC preparation. Recommended staged route. | New allocation and interrupted-creation handling must be tested. Arbitrary existing long playlist names need an explicit companion naming solution. |
| Treat a folder as a book using an in-memory queue | Avoids writing an M3U and its partial-file problem; sorted folder queues already exist. | Current last-book identity, preview, launch, signatures and resume are tied to a real playlist file. This requires a broader source abstraction; state storage is still needed. |
| Keep host preparation, improve its packaging | Already implemented; naturally sorted playlists and valid journals are created together. | Requires an extra desktop step for users. Useful fallback for unsupported layouts/codecs. |

## Recommended scope for a first implementation

1. Start with missing state files for the existing BOOK.M3U convention. Use the
   same two 512-byte CRC journal sectors as `tools/prepare_book.py`. Keep legacy
   prepared books fully compatible. General long-basename playlist companions
   remain a separate naming/API question; do not silently share one state file
   between different playlists in a folder.
2. Resolve and revalidate the physical parent directory using the existing
   Unicode-aware reader. Use guarded native insertion by parent identity, or a
   verified adapter; do not send arbitrary UTF-16 folders through the short-name
   create wrapper. Fixed BOOK.M3U/RSM/BMK names avoid long-name creation for
   automatically prepared one-book-per-folder content.
3. Check absence under the filesystem lock immediately before creation, with
   the existing writer guard. Never delete/truncate an existing file, even an
   invalid companion. An exFAT success-looking handle is insufficient: close,
   re-resolve, reopen and verify exact length, identity, headers and CRCs before
   enabling persistence. Preserve the actual lower-level error where possible.
4. Prepare on book entry, before playback starts. Keep allocation out of audio
   callbacks and bookmark gestures. Distinguish preparation failure visibly;
   do not pretend saving worked. Limit each lock interval and measure its cost.
5. Then add M3U generation for unambiguous single-book folders, naturally sorted
   and bounded to 256 accepted audio entries. Preflight paths/count before any
   output. Preserve existing M3U ordering. Do not merge the collection root or
   guess that several nested book folders form one book. Loose-file/multidisc
   grouping requires an explicit rule before claiming general support.
6. Prevent a partially written generated playlist from becoming a valid shorter
   book. An audited publish/rename operation or a generated-file completion
   marker validated on entry is required. Neither mechanism is implemented.

Interrupted initial creation is different from updating an existing CRC journal:
FAT/exFAT directory entries, chains/bitmaps and file length also change. Existing
alternating-sector tests do not establish creation safety. Zero-length, partial,
invalid or foreign files must fail closed; automatic repair/cleanup requires
provable ownership and must never overwrite existing content.

## Remaining proof before linking into firmware

- Execute real native insert, allocator, write and close paths with only sector
  I/O mocked; inspect resulting FAT/exFAT directory/chain/bitmap/size state.
- Cover Unicode/nested parent identity, same-name files and directories,
  read-only media/files, full card/directory, exhausted handles, short/failed
  I/O, stale/unplugged storage and all interrupted-creation stages.
- Establish creation and publication semantics, cache invalidation, stack bound
  and acceptable lock duration before any hardware test.
- Find a measured memory fit. The tagged resident payload has zero static margin
  below0x0309fff0. The browser helper has 996B code margin under its current
  flash cap and additional runtime scratch space; this is a placement candidate,
  not proof the complete feature fits. Do not expand boundaries casually.
- Add integration tests preserving custom playlists, independent per-book
  bookmarks/speed/resume, natural chapter order and the existing Music behavior.

No automatic preparation code is linked, no new update image was generated,
and no hardware acceptance is claimed. Next useful work is the allocation/write
harness and a minimal BOOK companion-creation adapter, before broad M3U UX work.

## Streaming metadata prototype checkpoint — 2026-10-16

`experiments/auto_book_prepare/playlist.c` now plans and streams a relative UTF-8
playlist from an already naturally ordered source, using 768B of caller-owned
workspace and 512-byte write blocks. It emits the current ENR1/ENB1 blank-sector
formats through the existing CRC callback. It performs no filesystem operations
and is not linked into firmware.

All12 focused host tests pass. They cover Unicode, leading `#`, 1/256-entry
bounds, invalid names, failed/short/oversized writes, changed scan results and a
round trip through the production parser with one-byte reads. Independent review
identified the native resolver's absolute-path limit; a failing boundary test
preceded the correction. Planning now checks the normalized parent prefix plus
each chapter name against255 UTF-16 units, including surrogate pairs, and leaves
room for BOOK.M3U. The caller must supply the verified normalized prefix length.

The output trailer alone is never permission to publish: a source mutation during
emission can leave a complete trailer while returning failure. Publication must
require successful emission AND closed, cold content/identity verification.
Existing files remain outside this prototype's write authority.

ARM Cortex-M3 `-Os` object measurement is924B text, zero data/BSS; this excludes
the caller's workspace, adapter, callbacks and final linked alignment. Compiler
stack reports are per-function, not a complete native/IRQ stack bound. Guarded
empty creation is a separate research prototype; safe allocation, bounded content
writes, cold verification, publication and browser integration remain unfinished.
The release-candidate tag and firmware artifacts are unchanged.

## Final linked checkpoint — 2026-10-16

The previous sections record intermediate research. The completed cold-browser
path creates missing fixed-name companions, streams and cold-verifies BOOK.TMP,
then publishes BOOK.M3U through guarded native routines. Native FAT mutation is
used only after a checked bounded free-run search, avoiding the stock allocator's
unbounded rescan; exFAT bitmap geometry is proved before its native mutator runs.
No raw device writer or new filesystem implementation was introduced.

All578 tests passed in498.928s. Independent scoped storage verification covers
40 guarded and12 raw native tests. UI tests cover collection gating, live parent
metadata, medium changes, copied overlay state, failure restoration and actual
native folder entry after preparation bypass. Review corrections also protect
foreign dirty caches/FCBs, invalid bookmarks, explicit/custom playlist limits and
prepared multi-cluster folders. Final review gives limited offline approval;
there was no new Fable/revx run or hardware acceptance.

Resident25864B text/30440B BSS and queue ABI remain unchanged. Browser13960B
text/5320B BSS ends030803c8 with168B static margin. Shared scratch and64-key
paged natural-sort windows recover space. Flash rebalancing and stock module /
byte-reader loading are verified in both slots; isolated payload/image rebuilds
are byte-identical. Observed synthetic native book-entry stack peaks3160B FAT /
3184B exFAT are measurements, not complete stack bounds.

Supported geometry, failure artifacts and host fallback are documented in the
current guide. Existing partial/foreign files are preserved; interrupted initial
creation can leave an empty owned file or leaked free-space reservation. Stable
mounted media and atomic sectors remain model assumptions. No install, device
write, push or publication occurred. Archive:
`builds/phase4j-auto-preparation-20261016/reviewed/manifest.json`.
