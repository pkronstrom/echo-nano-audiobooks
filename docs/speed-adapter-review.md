# Independent speed adapter review — 2026-10-15

Reviewed `playback/speed.c`, menu API use, DSP contract, synthetic adapter tests,
and `docs/speed-native-codec-audit.md`. This is source/native-disassembly review,
not device validation or an approval to install. Implementation is still in
progress; findings refer to this checkpoint.

## Findings requiring resolution before device testing

1. **Reset must establish DMA ownership safety.** `playback_speed_reset()` clears
   both busy slots and `playing` immediately; seek calls it before forwarding
   opcode14. There is no generation or quiescence check in this adapter. If a
   current slot or native prepared slot survives the reset, subsequent capture
   can reuse its storage while native code still owns it. An old completion
   can also be attributed to a newly populated `playing` value. Prove all reset
   callers stop/drain the native pump and DMA (including seek and startup), or
   add a quiescent reset protocol. Generation alone cannot protect memory still
   read by DMA. Test current+prepared, reset/seek, late callback, then new capture.
   Current synthetic tests complete every DMA before the next capture.

2. **Initial source timestamp is not bound to a confirmed completed packet.**
   Capture reads packet timestamp/count before native opcode10. If decode
   completes between these reads and the native call, opcode10 can return the
   newly completed buffer with old timestamp/count used as its anchor. This
   matters once at activation/seek, but can persist in every saved position.
   Require a stable completed-packet snapshot before consuming it or establish
   another coherent metadata protocol. Add an interleaving test that completes
   decoding between metadata snapshot and dispatch. Count0 is currently accepted
   as an anchor duration even when the returned frame count is nonzero.

3. **Unsupported-format UI is misleading.** The book menu shows desired speed
   for all books, while adapter eligibility only permits native codec0 MP3,
   16-bit, supported rates. Unsupported content silently remains at1x. Explain
   that this is an MP3-only preference and provide an effective-rate/fallback
   indication; do not label it as a universally applied rate.

## Checks that look coherent, with limits

- A retained native input pointer is not replaced until `remaining==0`.
- Two output slots include padding for native expansion/spectrum and are guarded
  against reuse in the ordinary no-reset path.
- Native completion is called after retiring the old slot, allowing it to submit
  the prepared slot. The completion-side PendSV wake addresses the documented
  final-DMA EOF stall.
- Ordinary EOF drains the DSP and both busy slots before returning0. The DSP
  error path returns0 immediately; either prove impossible under adapter
  invariants or apply the same drain policy for errors.
- Source position advances at DMA completion, independently of desired speed,
  and the codec time wrapper prevents stock decoded-ahead time overwriting it.
- Desired rate is latched by DSP initialization; menu changes do not mutate an
  active DSP stream. Exact native startup/seek anchoring still needs testing.

## Documentation correction

The native audit describes `0x030834d8` as opcode11. Direct stock disassembly
shows `0x030834f2: movs r0,#14`; adapter opcode14 is correct. Native time wrapper
at `0x030834f6` dispatches opcode7 as implemented.

No implementation files were changed during this review.

## Follow-up source review: deferred reset revision

The updated implementation preserves busy/current DMA ownership across reset,
assigns output slot epochs, and suppresses stale-epoch timestamp retirement.
Non-pump capture cancels the discarded prepared handoff while retaining current
DMA and restores a large native buffer before native startup can ignore a wait
result. These changes address the original unconditional slot-reuse flaw.
Direct seek may drain old prepared/current packets before new output; no memory
reuse was found in that ordinary path.

A short PRIMASK section now binds timestamp/count to the ready shadow. This
closes the identified race **provided that the ready/metadata shadow is published
only by the host IRQ**. Pin that writer evidence and verify the masked not-ready
native path cannot wait for IRQ-dependent mailbox work. A separate module42
success-path hook is unnecessary if those two conditions are proven.

At this review point the root agent is fixing raw-startup DMA serialization:
all channel5 audio submissions must preserve an existing `playing` owner, and
failed raw submissions must clear their own `playing==3` state. Keep tests for
both raw/DSP ownership directions, including delayed completion after reset.
No additional concrete fault was found in ordinary EOF draining; the exceptional
DSP error path still returns EOF before pending DMA drains and needs either a
proved invariant or an explicit safe error policy.
