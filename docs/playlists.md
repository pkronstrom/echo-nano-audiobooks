# Phase 2: playlist core checkpoint

The playlist parser and queue are implemented under `playback/`. They are **not
connected to File Browser or included in the firmware image yet**. P1b remains
the current device test build; see [its instructions](playback-containment.md).

Implemented behavior:

- UTF-8 M3U, optional BOM, comments/EXTINF, CR/LF/CRLF and relative paths.
- Slash/backslash and dot-component normalization; reject absolute paths,
  traversal above root, invalid UTF-8 and unsupported filename characters.
- Preserve listed order and duplicates. Skip missing files, directories and
  non-audio entries. Abort and discard a partial queue on storage errors.
- Physical FAT/exFAT lookup, including long Unicode names. ASCII case folds;
  non-ASCII spelling/case must match the filesystem name.
- Deliberately listed content may come from `.nomusic` trees. General music
  exclusion remains independent. This is the proposed policy pending feedback.
- At most 512 candidate entries, 1 MiB input, 1024 bytes per line and 255 UTF-16
  units per normalized path. Invalid/missing candidates count toward the limit;
  parser statistics report truncation and skipped entries.
- exFAT file basenames are limited to 127 UTF-16 units before entering stock
  indexed-open; its 256-byte name buffer overflows on longer legal exFAT names.
  The limit is rechecked against live metadata before selection/open. FAT long
  names use short aliases for native open and do not need this extra limit.
- A 512-entry queue uses 8192 bytes. Native metadata selection rechecks both raw
  entry index and file cluster before changing playback state. Missing/replaced
  entries are skipped during next/previous; an all-unavailable queue fails after
  one lap without replacing the last valid playback state.

The full suite has 75 tests. ARM tests execute the compiled parser, resolver,
queue adapter, stock indexed file-open and stock metadata enumerator. Fixtures
cover FAT and exFAT, Unicode, cross-folder listed order, duplicate entries, wrap,
and replacement/removal after loading. Raw directory reads, sector I/O, locks
and watchdog are substituted: hardware storage, audio decoding and UI behavior
are not verified by these tests.

Build/check (GNU make 4.3+, Arm GNU Toolchain and Python with Unicorn required):

```sh
make playback-core
make test PY=path/to/python-with-unicorn
```

The experimental payload currently uses 4660 bytes of code and 10756 bytes of
BSS, below the 18780-byte RAM window. The queue stores compact physical references;
parser scratch uses BSS to avoid adding approximately 3.4 KiB of nested stack
use. The parser/queue have one player-service owner and are not reentrant.
Compiler stack-usage reports are emitted under `out/playback/obj/`.

## Remaining integration

The native File Browser exposes directory identities, not a ready-to-use full
Unicode path. Its saved `LIB+0x93` / `0x0300d492` field is the title “File Browser.”
A launch hook must capture the selected node and reconstruct ancestry before UI
state is reused. The browser has up to seven directory levels, each with physical
cluster/exFAT descriptor information. See the implementation plan for sequencing.

The experimental loader now has ARM coverage for first load, cached queue
preservation, reload after refresh, and failed/invalid flash reads. Image staging
checks preserve resources, module layout, header copy and CRC; it is still a
test-only operation. Browser-path fixtures cover root/nested FAT and exFAT
selections, Unicode ancestry, stale identities and invalid names/depth.

Code loading needs an explicit lifecycle in the final hooks: playback and refresh share the
high RAM window. The proposed flash staging region is verified zero padding
`0xa55200..0xa58000`, beyond declared resources and before the header copy. The
module table must remain unchanged; bytes after its entries are occupied.

Do not enable playback hooks until their loader, browser selection, queue modes,
resume behavior and refresh transitions have compiled ARM coverage. This is an
implementation checkpoint, not a flashable playlist release.

See the [integration evidence ledger](playlist-integration-evidence.md) for
verified addresses, test limits and the remaining handoff questions.
