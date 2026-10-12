# Playlist integration evidence

This ledger follows the evidence/unknowns workflow in
[REA](https://github.com/morluto/rea), inspected at revision
`f611d8ce722cd36345e9ff83b9669ef2e7fe57a9`.
Observations below come from GNU ARM disassembly, host fixtures and Unicorn,
not from a REA analysis engine. No REA engine or global configuration was installed.

## Target identity

- Stock V1.7.0 image SHA-256:
  `54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
- Module 0 is resident; module 31 is File Browser; module 33 is the music service.
- Extracted modules/disassembly are retained under `builds/research/`.
- Current device test image remains `builds/phase1b/custom/NANOV170.IMG`.
  The new loader is compiled separately and is not included there.

## Observed and checked

| Finding | Evidence | Limit |
| --- | --- | --- |
| Browser selection is a node, not a stored absolute path | Module 31 `0x0307ace2..0x0307acf8`; browser base `0x03005f6c`, selection at `+0x1ee`, next node at `+4` | Activation hook is not installed |
| Directory ancestry uses 56-byte rows, depth at `+0x1cc`, maximum 7 | Module 31 `0x0307ad6e..0x0307adc8`; child cluster at row `+20`/`+24` | Host fixtures reconstruct paths; no device navigation test |
| Root node parent may be zero or the filesystem root cluster | Module 31 `0x0307a084..0x0307a096` normalizes zero parent through filesystem descriptor `+13` | Fixtures exercise both representations |
| `0x0300d492` holds a localized browser title | Module 31 `0x0307b000..0x0307b006` calls string routine with ID 3 | Must not use it as a filesystem path |
| 84-byte resident debug message can hold the loader | Exact bytes at `0x03072e28`; all-module pointer scan finds one reference, module 21 `0x03079dfc` | Associated printf at `0x03079d1a` must be disabled; staging verifies its original instruction |
| Payload fits existing flash padding and unused high RAM | `tools/playback_layout.py`, linker assertions, layout tests | Stage operation remains in-memory only; no flashable playlist release |
| Loader retains an active queue and reloads after refresh overwrites its header | Compiled ARM tests of loader and payload initialization | Flash reads are substituted; actual flash timing/cache behavior is untested |
| Failed reads and bad magic invalidate the payload signature | Compiled ARM loader failure/retry tests | Integrity still depends on the checked firmware image and stock flash layer |

The full suite has 75 checks. Payload code is 4660 bytes; BSS is 10756 bytes;
3364 bytes remain in the 18780-byte shared RAM window. Staging does not change
module entries, resources, firmware length or build date.

## Unresolved before enabling hooks

1. **Discovery and selection:** expose M3U only in physical File Browser, retain
   original audio-only indexing for ordinary files, copy the selected path before
   UI state is reused, and validate the complete native launch sequence.
2. **Player lifecycle:** distinguish a fresh playlist launch, returning to an
   existing queue, selecting ordinary audio, and payload replacement by refresh.
   Loader tests alone do not prove all these UI transitions.
3. **End-of-list behavior:** module 33's sequential mode checks position/count
   before calling native advance. At `0x0308182a`, its return value is immediately
   overwritten. The current core step wraps while skipping stale entries. Wiring
   it directly would restart a list when its trailing entries disappear. The
   integration needs an explicit stop path, plus manual next/previous and signed
   multi-step coverage; returning an error alone is insufficient.
4. **Initialization errors and settings:** native queue initialization also ignores
   its result. Empty/unreadable playlists must take a verified failure path;
   settings changes must preserve listed order.
5. **Resume and hardware:** RAM queues do not survive power loss. Define the
   transition into Phase 3 persistence; do not claim playlist resume, decoder,
   storage or UI behavior from host tests.

Preserve the P1b image while these questions are resolved. The checked core and
loader are implementation checkpoints, not evidence that playlists work on-device.
