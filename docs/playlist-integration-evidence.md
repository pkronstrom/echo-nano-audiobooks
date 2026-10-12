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
- Current device test image is `builds/phase3a/custom/NANOV170.IMG`.
  P1b is preserved separately.

## Observed and checked

| Finding | Evidence | Limit |
| --- | --- | --- |
| Browser selection is a node, not a stored absolute path | Module 31 `0x0307ace2..0x0307acf8`; browser base `0x03005f6c`, selection at `+0x1ee`, next node at `+4` | Activation hook installed in P3a; device UI untested |
| Directory ancestry uses 56-byte rows, depth at `+0x1cc`, maximum 7 | Module 31 `0x0307ad6e..0x0307adc8`; child cluster at row `+20`/`+24` | Host fixtures reconstruct paths; no device navigation test |
| Root node parent may be zero or the filesystem root cluster | Module 31 `0x0307a084..0x0307a096` normalizes zero parent through filesystem descriptor `+13` | Fixtures exercise both representations |
| `0x0300d492` holds a localized browser title | Module 31 `0x0307b000..0x0307b006` calls string routine with ID 3 | Must not use it as a filesystem path |
| 84-byte resident debug message can hold the loader | Exact bytes at `0x03072e28`; all-module pointer scan finds one reference, module 21 `0x03079dfc` | Associated printf at `0x03079d1a` must be disabled; staging verifies its original instruction |
| Payload fits existing flash padding and unused high RAM | `tools/playback_layout.py`, linker assertions, layout tests | Integrated image checks pass; device execution untested |
| Loader retains an active queue and reloads after refresh overwrites its header | Compiled ARM tests of loader and payload initialization | Flash reads are substituted; actual flash timing/cache behavior is untested |
| Failed reads and bad magic invalidate the payload signature | Compiled ARM loader failure/retry tests | Integrity still depends on the checked firmware image and stock flash layer |

The P3a suite has 107 checks. Payload code is 6692 bytes; BSS is 7752 bytes;
4336 bytes remain in the 18780-byte shared RAM window. Module entries, resources
and firmware length remain unchanged. P3a changes the build date and CRC.

## Resolved integration questions

- Browser prefix `0x0307acb6` captures a pending path separately from the current
  queue/book. The native handoff `0x0307b0be` removes music node `0x0302315c`
  via `0x03059910`; its callback `0x030833f0` synchronously dispatches stop event
  241 through `0x03082524`. A compiled native callback test reaches full stop,
  both save hooks, and resumes the same book after reloading it.
- Initialization `0x030827ba` loads/validates the payload. Count and queue hooks
  reject empty lists before native initialization continues. Settings force
  sequential listed order, including the later order load at `0x030831ba`.
- Six advance sites use a bridge that stops on exhausted automatic progression;
  native code ignores the original callee's return, so returning an error alone
  was insufficient. Manual progression retains bounded wrap.
- `*(u32*)0x03039714` points to player info; offsets 0/4 are duration/current ms.
  Native restore `0x03080d54` consumes saved ms at `0x0300d1cc` and flag at
  `0x0300d1d0`, then calls seek `0x030834d8`, rounding forward to a second.
- The `0x030822ac` codec-close hook saves the book first. Stock save at
  `0x030825c4` rebases a persisted raw-folder ordinal; its bridge preserves the
  live playlist position so this does not corrupt chapter selection.
- Normal shutdown statically follows `0x0306a106 → 0x03069d2a → 0x03059974`
  (registered callbacks), including the music callback above, before settings
  persistence `0x030712fc` and powerdown `0x03063fe4`. Hardware poweroff itself
  is not executed by the tests. Alternate/emergency shutdown is not covered.
- Save hooks have resident signature guards: when refresh owns high RAM, they
  tail-call the original functions rather than branching into overwritten code.
- Native indexed-open accepts `RW`; FCB bit 2 enables writing. A valid existing
  1024-byte companion is updated in alternating 512-byte sectors with CRC and
  generation. Tests execute native indexed-open; sector writes are substituted.

## Remaining device questions

Boot/loading, codec timing, actual fast seeking, flash/card flush durability,
refresh/playback scheduling, and physical UI transitions require the device
checklist. A torn-write fixture demonstrates journal fallback, not atomic media
behavior. In-place audio replacement preserving entry indices and clusters can
retain stale progress. No dedicated audiobook boot reconstruction, embedded M4B
chapters or new seek button mapping is claimed.
