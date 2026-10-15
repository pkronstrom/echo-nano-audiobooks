# Browser-only folder-sort memory audit

Read-only audit for the user's request to finish folder sorting. No helper,
firmware build, device operation or memory-boundary expansion was performed.
The persistent playback payload has16B remaining; sorting should not be added
to it. The viable placement direction is an expanded module31 overlay with
relocated backing, plus explicitly initialized browser-only cache storage.

## Existing ownership

Pinned stock module31:

| Region | Start | Exclusive end | Size |
| --- | --- | --- | --- |
| Code execution | `03079418` | `0307b874` | 9308B |
| Code load address | `030b5648` | `030b7aa4` | 9308B |
| Initialized data execution | `0300e6bc` | `0300e73c` | 128B |
| Initialized data load | `030b7aa4` | `030b7b24` | 128B |
| BSS | `0300e73c` | `0300efa2` | 2150B |

The BSS is not spare scratch. Native initialization997a..99c0 clears1248B at
e73c and links two624B nodes at e73c/e9ac (literals9d78/9d7c). Other state starts
ec1c (literal9d98). Node name storage is live during rendering/selection. The
browser path/depth state at03005f6c is resident and also cannot be overwritten.
No safe2–4KiB contiguous diagnostic/function cave was established inside native
module31. Its current code backing is immediately followed by its live data
and module32 backing; appending in place would corrupt those sections.

## Concrete backing region

The already audited first module40 refresh sort buffer is
`0307b674..0308b674`. Existing playback staging remains exactly file
`0x36200..0x3e200` (32KiB), corresponding to refresh execution
`0308012c..0308812c`. Its untouched tail is:

- file offsets `[0x3e200,0x41748)`, **13640B**;
- load addresses `[0308e000,03091548)`;
- module40 execution addresses `[0308812c,0308b674)`.

All13640 bytes are zero in both pinned stock and the current combined image.
This interval does not touch the existing refresh blob or32KiB playback staging.
It can hold module31's9308B native code plus up to4332B helper code/initialized
metadata. A4096B helper leaves236B. Relocate the *complete already-patched*
module31 code image here, retain code_exec03079418, append helper at0307b874,
and update only module31 code_load/code_len. Keep its original data/BSS fields.
Native code's absolute execution addresses and PC-relative offsets do not move.
The normal native overlay loader then loads the helper with the browser, without
another flash reader, resident trampoline, or persistent payload code.

This requires a narrow, explicit exception to current build invariants that
all module records match stock. Preserve every other record and resource,
firmware length, both table/header representations where applicable, checksums,
playback32KiB staging, refresh contents outside the new interval, and the upper
RAM boundary. Check all destination bytes before writing; construct from the
patched browser image so existing navigation/selection hooks are retained.

## Cache and lifetime constraints

Do not extend low-RAM module31 BSS speculatively. A NOLOAD mapping/name scratch
area immediately after the appended code can use the browser overlay's unused
execution tail. Copy a small initialized metadata block with cachevalid=0 on
every overlay load. Rebuild/invalidate again on directory/device/filesystem
identity changes; never infer validity from stale bytes left in NOLOAD storage.
No resident callback or player may retain a pointer into this overlay.

The execution gap before module33 is `[0307b874,03080470)` (19452B).
Module33 MP3 code begins03080470, data03022fc8, BSS03035500. Raw absolute-word
scans of module31 and33 found no references into that execution gap. Resident
module0 has no such candidates below0307d518; higher matches include genuine
other-overlay pointers and coincidental instruction/text halfwords. This is
negative evidence, not a proof against computed pointers or asynchronous use.

A conservative sizing target below0307d500 is7308B total. Example budgets:

- helper+metadata <=2048B; aligned4KiB u16 ordinal map (2048entries) and1024B
  name scratch can end near0307d480;
- helper+metadata <=4096B; aligned1024B map (512entries) and1024B name scratch
  can end near0307d080.

Choose a checked bound and explicit overflow fallback; never partially expose
a sorted list with uninitialized identity mapping. Name scratch could instead
be bounded stack storage only after stack costs are measured, not by borrowing
the two live native nodes.

## Auxiliary-overlay lifetime follow-up

Declared alternative owners of the full gap are modules9,12,15,16,18,19,20,27,
32,40,63. The specific module9 concern is resolved for native window transitions:

- Resident literal at306b364 points to the window state/table03005b8c. Its
  module-ID table at+80 maps window9 -> module31 and window11 -> module9;
  callback-root table at+4 maps them to0300e700 and03031488 respectively.
- Native window loader306b246..268 reads currentwindow, selects that module,
  and unconditionally calls306b6bc(module,7), loading code/data and clearing
  the declared BSS, before returning the new callback root.
- Native service teardown306b178..1aa invokes old-window cleanup, clears its
  links, then branches to306b116, which calls306b246 before new-window init
  at306b12a. Thus a normal window11 -> browser return reloads31, including
  appended code and copied-invalid metadata. Module9 is not assumed terminal
  merely because it contains the string CRebootFlag.
- No direct module9 load with constant9 was found in the available complete
  mod*.txt disassemblies; its observed owner is the window loader.

Other auxiliary groups are entered by different base windows, which already
replace stock browser code before their higher fragments load:

| Higher owner | Observed parent/load path |
| --- | --- |
| 12 | module10 at30794ac..ae loads12 with flags7; module12 itself overlaps native browser from307b1b8 |
| 15/16 | module14 at307a34a..4c loads15;3079ec2..c4 loads16; module14 occupies browser base, and15 overlaps stock browser too |
| 18 | window6 maps17; module17 at307942e..30 loads18 |
| 19/20 | module18 at307d580..598 selects and loads20 or19 |
| 63 | window7 maps29; module29 at3079624..26 loads63 |
| 27/32/40 | player/settings/refresh overlays already replace stock browser code |

The callback teardown/load ordering and these parent paths support treating the
whole gap as browser-owned until the browser window exits. This does not claim
that stale browser code remains callable during other windows. No external
callback may be registered by the new sort helper.

A concrete full-size placement is now available: helper plus copied-invalid
metadata `[0307b874,0307c874)` (4096B), alignment to0307c880, NOLOAD u32 map
`[0307c880,0307d880)` (1024entries), and two512B name buffers
`[0307d880,0307dc80)`. End0307dc80 remains10224B below decoder code03080470.
The copied native+helper image is13404B,236B below the checked flash-tail limit.
An explicit linker cap should enforce each interval. If helper code needs more
than4096B, use at most4332B including metadata and shift the NOLOAD regions with
assertions, rather than growing the playback staging or RAM boundary.

The low-RAM0300f000 alternative remains unnecessary and less well established.
Do not change module31's low-RAM BSS table to cover the high execution cache.

## Required implementation verification

1. Validate exact original module31 table, patched native code9308B, zero backing
   interval, disjoint resource/staging bounds, unchanged other module records.
2. Exercise the native module loader against relocated backing; verify full
   browser code/helper bytes, copied invalid metadata, unchanged data/BSS and
   decoder state. Validate load lengths and boundary canaries.
3. Exercise browser -> player/settings/USB/refresh -> browser transitions;
   verify no browser callback resumes with overwritten helper/cache, and every
   reload invalidates cached mappings. Retain the audited auxiliary parent-load paths in tests.
4. Verify sorted-to-physical identity on enumeration, selection, Back and device
   changes, bounded overflow fallback and all node fields. Native ordinal
   selection must use the physical entry, not the displayed sorted position.

This design avoids moving existing payload functions into an overlay, which
would create new cross-overlay calls and broader lifetime risk. It is a concrete
placement plan with4332B of checked flash room for appended code; native window lifetime is traced above, while loader/transition regression
remains a prerequisite for implementation acceptance.

## Implemented loader regression follow-up

The layout/helper build work now implements checked backing relocation. The
original native loader306b6bc/306b5b6 and its sector-copy loop306b542 are exercised
in ARM tests with only flash reads and lock calls substituted. They verify code
and independently located initialized data, native BSS clear, exact copy bounds,
and metadata reset on repeated loads. A native306b246 window11/module9 load
followed by window9/module31 reload explicitly overwrites appended helper bytes
with module9 first and verifies restoration before browser use. Shared playback
RAM and its32KiB staging allocation remain unchanged.

The first isolated linked implementation measures2820B copied code/metadata and
6560B NOLOAD state: header/code end0307c378, runtime end0307dd18. Relocated native
plus helper code totals12128B, leaving1512B in the verified flash tail and10072B
before the decoder execution boundary. The build emits hashes for the helper
and four hook files; integration parses only those already-hashed bytes and
rejects stale artifacts before changing the in-memory image. Final combined
build and device acceptance are owned by the parent task.

Final linked candidate20261102 uses2944B copied code/metadata and6560B NOLOAD
state. Code ends0307c3f4, BSS ends0307dd98, leaving1388B of verified flash-tail
capacity and9944B before decoder execution. The combined image and actual
compiled-metadata/native-window-reload regression passed. Playback's separate
24112B text+32176B BSS allocation remains unchanged.
