# P4e accelerated-audio crackle — 15 October 2026

Hardware: corrected P4e `e40a2e82…1210be` reached the normal menu. User reports
considerable crackle at1.5x and2x, while the same book is clean at1x. Changing
speed requires relaunch, as designed. Accelerated audio has not passed acceptance.
The exact source file, sample rate and EQ mode have not yet been established.
User subsequently confirmed the crackle remains with EQ off. The effects gate
can still matter when enabled, but EQ alone does not explain this report.

## Reproduced packet fragmentation

The adapter's256-frame output capacity is a maximum, not a promise to fill it.
It submits every nonzero core result immediately. The core may exhaust the
current1152-frame input block while returning less than256 output frames.
This creates small non-EOF DMA submissions with very short playback deadlines.

A host diagnostic using the actual core and adapter demand/refill order found:

-48kHz/1.5x220Hz tone:95 of334 packets short;95 non-EOF packets not divisible64,
 with104/180-frame partials.
-48kHz/2x harmonics:95 of247 packets not divisible64, with105/210-frame partials.
-48kHz noise: minimum2 frames at1.5x and3 at2x;44.1kHz/2x minimum1 frame.

Evidence: `builds/research/speed/crackle/packet_lengths.c` and
`packet-lengths.csv`. These are synthetic diagnostic signals, not a listening
assessment or proof of the precise hardware cause.

Native ARM pump instrumentation records steady invocation instruction ranges:

| Signal/speed | Instruction range |
| --- | --- |
| Tone/1.5x |24,188–173,500|
| Tone/2x |8,959–277,655|
| Noise/1.5x |26,308–190,648|
| Noise/2x |13,741–339,724|

Native state+28 is expanded stereo-lane count, not frames; divide it by2.
Evidence: `pump_instructions.py` and `pump-instructions.json` in that directory.
Instruction counts are not CPU cycles or real-time measurements. Host Cortex-M3
clock frequency remains unestablished; the decoder-core144MHz figure is not a
valid substitute. Stock has a dynamic clock-request/reconfiguration path.

## Native effects boundary

Pump effect selector and wrapper mode are the same byte at `0x030398a4`.
Mode0 skips effects (`0x03069740..9742` and `0x030837b0..37c2`). Modes1–8 reach
`frames &63` at `0x030837c4`; only multiples of64 call processor `0x03084d32`.
Variable short output can alternate processing and bypass when effects are on.
The corresponding UI label was not independently pinned. Mode0 is the exact
technical baseline for eliminating this particular effect interaction.

Native PCM conversion itself uses actual lengths: first signed16→24-bit words
at `0x03069484`, then shift and stereo-lane count at `0x030697fc..9836`.
The fixed128-lane spectrum read fits padded slots. No256-frame packing defect
was found in this audit.

## Correction under test

Accumulate unpublished PCM until a complete256-frame packet is ready. Preserve
partial staging across decoder waits and bounded CPU-work yields; expose it to
native conversion/DMA only when full. Emit a final partial packet once at EOF.
Reset/seek discards only unpublished staging and preserves live DMA ownership.
Publish one aggregate source-time endpoint per submitted packet.

Required checks: varying PCM, no dropped/duplicated samples, all steady packets
256 frames, wait/seek during partial staging, EOF tail/drain and existing DMA
ownership regressions. Even passing these checks will not establish CPU deadline
margin or remove the need for another headphone test. Do not change clocks or
core quality parameters in the same correction.

## Packet correction verified offline — 2026-10-15

The adapter now coalesces partial output into256-frame packets, with at most
one short EOF tail. All336 tests pass (128.949s), including native-pump PCM
comparison against the independent core reference at all four speed presets,
partial decoder waits, seek discard and bounded-work yields. Scoped independent
review found no blockers. Core DSP and clock configuration are unchanged.

Audio-only checkpoint: `builds/phase4e-speed-20261015/packet-fixed/manifest.json`.
Custom date20261025, recovery20261026; text22416/BSS31592,2296 bytes headroom.
This image is uninstalled. Hardware crackle resolution is unproven; installed
20261023 remains the build with clean1x and crackly accelerated audio.

## Main-menu latency follow-up

User identifies the delay at main-menu Audiobooks entry and reports roughly
three seconds for Meditations too. Both share navigation_browser_init, which
scans roots and builds matches before either drawing the last-book landing
(which does not use those results) or calling browse_roots (which rebuilds
them). Remove that redundant scan only; retain fresh root discovery when
browsing and last-book storage/identity validation. No persistent cache.

Menu optimization implemented: removed the unused scan and match-building loop
from category browser initialization. Six FAT/exFAT regression subcases failed
before the change and pass afterward, covering Audiobooks, Meditations, saved
book identity and marker removal before Browse. Scoped spec and quality review
approved. Combined payload22360 text/31592BSS=53952 bytes,2352 bytes headroom.
Actual menu timing remains unmeasured on hardware.

Hardware follow-up: user reports “that fixed it” after testing the20261025
packet/menu candidate. This is a positive device result, but whether it refers
to accelerated-audio crackle, menu latency, or both awaits clarification. Do
not mark both acceptance items passed yet or infer every speed was tested.
