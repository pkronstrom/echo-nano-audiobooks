# Playback speed integration — 2026-10-15

Status: offline verification complete; experimental candidate, not installed.
The corrected paired image passes333 tests. The /revx launch-rate finding is
fixed and independently re-reviewed. Hardware acceptance is pending.

User explicitly requested a pause before leaving. No device writes, firmware
installation, SD operations or commits occurred during this integration turn.
Installed hardware remains the previously confirmed 20261019 build. P4d's
review-fixed archive is unchanged.

## Current implementation

- Bounded, allocation-free pitch-preserving core linked through
  `playback/speed_core.c`; five requested presets, 1x–2x in quarter steps.
- Cheaper search: conservative 11,071 comparisons/search; 416 synthetic voiced
  cases and sanitizer/bounds/source-mapping checks pass. This is not a measured
  device CPU deadline or recorded-speech quality result.
- Book menu has `MP3 speed` presets. Selection applies on a later launch,
  is RAM-only/global, and unsupported formats retain native 1x playback.
- MP3 adapter uses two 256-frame slots, deferred reset epochs, source-time
  completion accounting, EOF draining, native-buffer restoration for non-pump
  callers, and raw-preroll tracking. Implementation is still under review.
- Six native DMA sites, capture/seek/time wrappers, guarded resident callbacks,
  and a nonzero-status pump guard are staged in source. The last guard protects
  small DSP buffers from stock re-expansion after pause/stop.
- Linker code-end alignment is now eight bytes because the DSP state contains
  64-bit counters; staging requires the BSS to immediately follow code.

## Current verification gate

After the first Fable review rejected the baseline, fixes restored unsupported
book prefetch, reclaimed discarded prepared buffers, re-owned completed slots
on resubmission, and added thread-only stopped-DMA retirement. The adapter tracks
the actual allocated DMA channel and preserves active or foreign ownership.
Tests execute the stock pending IRQ after retirement to check for stale callbacks.
The independent native-lifecycle audit found no remaining blocker in retirement.

Output slots are now256 frames, with1536-frame core input storage. This halves
output interrupt frequency while retaining the same BSS allocation and enough
input for the1476-frame maximum lookahead. Final payload build:22,384 bytes text,
31,584 bytes BSS,53,968 total;2,336 bytes remain in the reserved region.

- 36 targeted ARM tests passed after lifecycle and packet-size changes.
- Host ASan/UBSan matrix and416 synthetic pitch cases pass; maximum observed
 pitch-search count10,852, conservative bound11,071.
- Combined custom/recovery image build succeeds (20261023/20261024, About P4e).
- Full paired-image suite:332 tests passed in124.482s.
- Fable follow-up:limited offline approval; no new correctness regressions.
  Initial and follow-up reviews are archived with the candidate.

The final full-suite log and review match the archived source/image checkpoint. Offline checks do not establish hardware speed quality,
real-time load, headphone output, or on-device pause/seek/resume/EOF acceptance.
See [the device test checklist](speed-device-test.md). No device operation has
been performed during this integration.

## Quarantined image

The intermediate 20261023 image was built before later safety fixes and is NOT
installable. It has been moved out of `out/audiobook/NANOV170.IMG` into ignored
`builds/research/speed/paused-20261015/UNSAFE-INCOMPLETE-NANOV170.IMG`, with a hash
manifest. Do not restore it to the normal install path or use it for testing.
The later-dated stock recovery output is only a local artifact; it was not copied
to a device. Read AGENTS.md and the recovery lessons before future device work.

Historical pause: the integration-test agent was interrupted at the user's pause
request before its latest handoff completed. Treat additional edits to
`tests/test_speed_pump_arm.py` as unverified until rerun. Agents were stopped at that pause; subsequent work is recorded above.

## Earlier resumed adapter verification — historical baseline

The user authorized continuing offline integration, not installation. The paused
image remains unsuitable for installation; the installed device is unchanged.

Adapter ownership fixes now serialize all intercepted channel5 audio submissions
against the current owner. A rejected raw or prepared submission cannot replace
the current callback. Completion forwards the callback belonging to the accepted
submission. Failed submissions release only their own accepted token.

DMA rejection/failure and DSP processing errors now enter a terminal fault:
unsubmitted prepared output is discarded, native prepared handoff is canceled,
and actual current DMA remains owned until its completion. Capture waits for
that DMA before returning EOF. This intentionally ends the stream after an error;
it does not retry or silently resume output behind native busy flags. Actual
stock pump tests verify first-submission and callback-handoff failures reach
native terminal status4/event243 without requiring a nonexistent completion.

Native DMA's internal critical exit can execute CPSIE regardless of incoming
PRIMASK. The adapter holds one additional native critical nesting level at byte
`0x0300d83e` around submission, under PRIMASK, and restores the previous depth
before restoring PRIMASK. Depth254 or255 fails closed to prevent byte overflow.
The address and byte width are pinned by stock enter/exit disassembly
(`0x0306a37a` / `0x0306a360`, literal at `0x0306a51c`). A regression executes those
actual stock enter/exit instructions and checks incoming PRIMASK1 and depth0
are preserved. No interrupt mask covers the codec's DMA-copy completion wait.

Non-pump capture during raw preroll now returns the other native A/B buffer and
waits without dispatching another decoder delivery. This preserves current raw
DMA even when startup ignores wait and clears/converts the returned pointer.
Seek adds PendSV only when an existing speed stream or owned slot requires it.
The pump fixture now applies both speed_status patches and verifies statuses1–4
do not re-expand either current or prepared DSP storage.

Targeted adapter/pump run: **29 tests passed in8.046s**, including five regressions
that failed on the pre-fix baseline, terminal DMA failures, DSP-fault draining,
actual callback preservation, native critical depth overflow, raw A/B reuse and
nonzero-status interleavings. Command:

```
builds/tools/test-env/bin/python -m unittest discover -s tests -p 'test_speed*_arm.py'
```

Last adapter payload build: text22,272B, BSS31,576B, total53,848B. Root is responsible
for subsequent combined image/full-suite verification and independent review;
these targeted results are not a claim those gates passed. Native hardware DMA,
interrupt latency, CPU deadlines, real speech quality, audio output and on-device
pause/seek/EOF acceptance remain unverified. No installation was performed.

## Remaining acceptance limits

If native pause/stop returns while the adapter's actual DMA channel is still
active, a new overlapping submission is rejected and the stream enters terminal
EOF after draining its actual owner. This can end the current file; it avoids
reusing live PCM. It can particularly matter when native channel5 allocation
falls back to0–4 because the stock stop loop polls5. This is a known degraded
path, not seamless pause/resume in every hardware timing scenario.

The tests substitute native DMA submission; stock critical enter/exit and pending
IRQ instructions execute in focused fixtures, but full hardware DMA timing and
stock pause/stop are not emulated end to end. Fable approval is limited to offline
source correctness. Use the controlled headphone checklist before broader use.

## /revx follow-up: launch-latched speed

The final panel completed Sol, Grok and GLM; Sonnet was unavailable due to account
quota. One confirmed medium finding: changing the preferred rate then seeking
or resuming re-read it before a new launch. ARM reproduction confirmed8→5
quarters without a new launch. All12 new regression subcases failed before
the correction.

`playback_speed_launch()` now captures the preference only after a pending
playlist selection validates successfully in `playback_prepare()`. Eligibility,
raw preroll ownership and DSP initialization use that captured rate. Seek,
pause/resume, Now Playing re-entry and automatic chapter changes retain it.
An explicit Continue/chapter/bookmark launch adopts the newest preference.
The preference and launched rate remain RAM-lifetime only.

37 targeted ARM tests pass, including12 combinations of4→8,8→4 and8→5 quarters
across seek/resume/re-entry/chapter changes and genuine relaunch. Independent
scoped source review approved the fix with no blockers. Full paired-image
verification:333 tests passed in119.130s. The corrected archive is
`builds/phase4e-speed-20261015/review-fixed/`; preserve the older `reviewed/`
archive as review evidence, not the preferred test candidate.
