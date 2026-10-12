# Relative playlists in P3a

The parser, native File Browser launch and ordered queue are integrated into the
[P3a audiobook test image](audiobooks.md). The default P1b image stays separate.

- UTF-8 M3U, optional BOM, comments/EXTINF, CR/LF/CRLF and relative paths.
- Slash/backslash and dot-component normalization; reject absolute paths,
  traversal above root, invalid UTF-8 and unsupported filename characters.
- Preserve listed order and duplicates. Skip missing files, directories and
  non-audio entries. Discard a partial queue on storage errors.
- Physical FAT/exFAT lookup with Unicode names. ASCII case folds; non-ASCII
  spelling/case must match the filesystem name.
- Deliberately listed files may come from `.nomusic` trees. General music
  exclusion remains independent.
- 256 queued entries (4096 bytes), 512 candidates, 1 MiB input, 1024 bytes per
  line, 255 UTF-16 units per normalized path. Invalid/missing candidates count
  toward limits; parser statistics record truncation and skipped entries.
- Stock exFAT indexed-open has a 256-byte name buffer. Basenames longer than
  127 UTF-16 units are rejected before native open/selection. FAT uses short
  aliases for native open.
- Live raw entry index and file cluster are rechecked. Missing/replaced entries
  are skipped. Automatic advancement does not wrap; manual next/previous wraps.
  Exhaustion takes the native stop path, even when trailing entries disappear.
- Native settings preserve listed order while a playlist is active, without
  rewriting the user's ordinary music preferences.

Code uses 6692 bytes and BSS 7752 bytes, leaving 4336 bytes in the 18780-byte
shared RAM window. Parser scratch is in BSS; stack reports are in
`out/playback/obj/`. There is one player-service owner; the parser is not reentrant.
The loader reloads after library refresh replaces the shared RAM signature.

The native browser has seven ancestry levels. The launch hook reconstructs the
selected path before UI state is reused. M3U is added to the generic File Browser
filter; all eight references to the displaced audio whitelist are redirected to
an unchanged duplicate. Native audio indexing remains audio-only.

Flash payload staging uses checked zero padding `0xa55200..0xa58000`, beyond
resources and before the copied header. Module entries and resources remain
unchanged. Every hook checks the expected native instruction or reclaimed
region before image output; the complete image CRC is recomputed.

107 host/ARM/binary checks cover parser/resolver, indexed open, discovery,
launch/initialization, settings, advancement, scope, loader/refresh, resume,
native callback dispatch and preparation/conversion. Raw sectors, codec and
hardware/resource operations are substituted; these checks cannot establish
boot, audible playback or hardware durability.

```sh
make audiobook
make test PY=path/to/python-with-unicorn
```

See the [integration evidence ledger](playlist-integration-evidence.md) and
[device test instructions](audiobooks.md).
