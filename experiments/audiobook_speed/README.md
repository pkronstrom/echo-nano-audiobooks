# Bounded audiobook speed prototype

**Experimental core, now linked by the in-progress P4e firmware adapter.** It demonstrates a
small integer pitch-period overlap-add core for approximately 1x, 1.25x, 1.5x,
1.75x and 2x speech playback. It does not establish speech quality, real-time
performance, device audio compatibility or safe installation. See
[the integration checkpoint](../../docs/speed-integration-checkpoint.md)
for the current firmware verification status.

The user prioritizes clear speech and efficient processing over exact speed
multipliers. Rational settings are inexpensive bookkeeping; they are not a
promise of mathematically exact track duration. No floating-point code, heap
allocation or global mutable state is used by the core.

## Run checks

From the repository root:

```sh
python3 experiments/audiobook_speed/run_checks.py
python3 experiments/audiobook_speed/run_checks.py --arm
```

The first command uses Clang with AddressSanitizer/UndefinedBehaviorSanitizer.
The second also uses the repository's downloaded ARM GCC 13.2 toolchain for a
standalone Cortex-M3 size artifact. It does not build or install firmware.

Checks cover eight input sample rates (including 11,999 Hz, a downsampling
boundary), both channel counts, all five settings, empty/tiny/partial/large
streams, 7-frame versus 2,048-frame chunks, one-frame output capacity, chunk
invariance, exact 1x samples, guards, silence/full-scale/noise, source accounting,
reset, rejected arguments and EOF. Two-second 125 Hz signals check approximate
pitch preservation for opposite-phase stereo and right-channel-only audio.
An additional416 cases cover65–400 Hz across8/22.05/44.1/48 kHz and all four
speedups: pure tones and three-harmonic signals with a slowly varying amplitude
envelope. The worst zero-crossing frequency error was1.03%, matching the older
search's baseline; the limit is3% (or2 Hz for low frequencies). This is a
synthetic voiced-signal regression, not an evaluation of intelligibility,
timbre, pumping or actual recorded speech. Real speech still needs listening.

TDD evidence: the initial API stub failed initialization in the matrix; the
first-channel-only pitch estimator failed the subsequently added right-only
stereo test. Choosing the stronger channel for the single shared pitch decision
fixed the latter. The performance regression initially measured62,374
comparisons/search and failed the15,000 limit. The bounded refinement below
passes the final sanitizer and comparison-bound checks.

## API and ownership

- Caller owns one `speed_state` per stream. Keep it outside a small task stack.
- `speed_init` accepts sample rates 8,000–48,000 Hz, one/two channels and a rate
  in quarters: 4/5/6/7/8. Input/output are interleaved signed 16-bit PCM.
- All lengths and `consumed`/`produced` counts are **frames**, not sample values
  or bytes. A stereo frame contains two sample values.
- `speed_process` may consume without producing during lookahead, or produce
  without consuming while draining. Advance both pointers by their respective
  counts; keep retrying unconsumed source. Buffers must not alias each other or
  the state. Use the test harness's `run` function as a complete driver example.
- `eof=1` means no frames follow the offered input. If not all input was accepted,
  retry that remainder with EOF set. Once it was all accepted, call with no new
  input until `done`. No zero-padding or upstream flush routine is used.
- Zero output capacity is permitted but can stall progress. Repeated zero-space
  calls are not a useful drain loop. Any positive capacity supports progress.
- Reset discards pending PCM and accounting, retaining format/rate. Call it on
  seek/track change. Rate changes currently require reinitialization; an audible
  transition/drain policy belongs in the future adapter. There is no click-free
  live-rate-change implementation yet.

The core is single-owner, not thread-safe or interrupt-safe. The caller must
serialize processing/reset and preserve input/output buffer lifetimes.

## Timing and accounting

The processor finds one pitch period, overlaps two periods into one, then copies
an appropriate number of frames to approach the selected rate. Stereo shares
that decision and retains both channels; it never downmixes the output. Choosing
the stronger channel for analysis avoids cancellation of opposite-phase audio
and failure on silent-left/right-only speech.

Pitch analysis uses the original coarse AMDF search, then refines within one
coarse bin on each side, comparing every second input frame. The mean is
normalized by the actual comparison count `ceil(period / 2)`, not the period
length; this matters for odd candidate periods. There is one fixed algorithm,
with no runtime quality knob.

At EOF, a short tail is copied without padding. Duration differs from the ideal
ratio by at most approximately one maximum pitch period (15.4 ms at these
settings). The minimum pitch is 65 Hz, so analysis needs about 31 ms of source
lookahead. Speech quality and artifacts outside the tested tones remain unknown.

`accepted` counts input copied/consumed; `retired` counts source frames removed
from the internal input queue. **Retired is not audible position.** Some retired
source corresponds to pending overlap output, and the stock audio queue/DMA
adds further delay. `produced` counts frames actually returned to the caller;
`dropped` accounts for removed pitch periods. At completion,
`accepted == retired == produced + dropped`.

An eventual firmware adapter must map source positions through overlap output
and downstream queues before updating resume/bookmark timestamps. Neither a
fixed multiplier of wall time nor `retired` alone is a correct audible position.
`speed_result.source_begin/source_end` now describe the returned output packet's
source-frame interval. These are relative to the most recent reset, independent
of mono/stereo sample count. Overlap output accounts for both source periods;
unchanged copy output accounts one-to-one. Consecutive packets have contiguous
endpoints, and zero-output calls retain the last emitted endpoint. Endpoints are
exact accounting positions, not a claim that a crossfade has one perceptually
exact source instant. Native queue consumption still has to be tracked.

## Measured resources and next gate

Standalone GCC 13.2 Cortex-M3 `-Os` measurement, with all five public functions
retained and libc memory helpers linked:

| Item | Size |
| --- | ---: |
| Core object text | 1,684 B |
| Linked text, including memory helpers | 2,388 B |
| Caller-owned state | 9,688 B |
| Combined code/state | 12,076 B |

There are no unresolved target symbols or software floating-point helpers.
Against P4d's 19,988-byte remaining region, this leaves **7,912 bytes** before
adapter code, position mapping, additional PCM storage or future features.
A `speed_packet` descriptor is24 bytes (two native slots need48 bytes). The
compiler reports128 bytes stack for `speed_process` plus64 for its `search`
callee, a192-byte core call chain; packet helpers each use20 bytes. These static
figures exclude the native caller, libc routines and interrupt nesting. Caller
state must not be allocated on that stack. The final firmware link/stack must
still be measured. A standalone
link is not proof that the integrated firmware fits or runs in time.

A separate instrumented one-second48 kHz mono run counted AMDF inner-loop
comparisons at2x per generated output second:

| Signal | Previous search | Current bounded refinement |
| --- | ---: | ---: |
| 125 Hz sine | 4.66 million | 0.79 million |
| Deterministic noise | 4.50 million | 0.89 million |
| Silence | 3.35 million | 1.01 million |

These exclude stereo analysis, mixing, memory copies, decoding and UI work.
They are operation counts, not target cycles. The counts reuse the one-second
input generator in ignored `builds/research/speed/core-feasibility/count.c`,
with a counter in the current core's AMDF inner loop; that directory's older
instrumented implementation/output are historical baseline evidence.

The conservative per-search bound at48 kHz is **11,071 comparisons**, down from
73,432. With `skip=sample_rate/4000`, `lo=sample_rate/400` and
`hi=sample_rate/65`, the bound is:

- Coarse: sum of every candidate period from `lo/skip` through `hi/skip`.
- Fine: at most `(2*skip+1) * ceil(hi/2)` comparisons.

The test checks this formula for every integer sample rate8,000–48,000 Hz;
11,071 is the maximum. Host-only instrumentation observed a peak of10,852 in
the complete tests (9,802 in the initial noise/chunk matrix). Instrumentation
is excluded from normal and ARM builds. This bounds AMDF comparisons per search,
not total work per process call: a256-frame output request can need more than
one search, plus downsampling/channel analysis and memory work.

The integrated adapter uses256-frame output packets (5.33 ms at48 kHz),
with1536 input frames instead of2048 to keep total adapter BSS unchanged.
1536 exceeds the1476-frame maximum two-period lookahead.
Small output packets alone do not prove a5.33 ms deadline at48 kHz. Native
prefill, interrupt interference and actual clock/memory behavior still need
measurement. No deadline-safe integration is established by these host checks.

The next integration gate is verified stock PCM ownership/backpressure and
native consumption tracking, followed by real speech listening and target deadline
measurements. Any further CPU tradeoff must be judged against speech quality
rather than chasing exact multipliers. Do not simultaneously
reduce CPU clocks or silently downmix stereo.

## Attribution

Algorithm and reference: [Sonic](https://github.com/waywardgeek/sonic), Copyright
2010 Bill Cox, Apache-2.0; examined commit
`b93885dcb70aae50c6f76b0fe4e0868f029a077e`. See LICENSE. This adaptation replaces
stream buffering, EOF handling and floating-point speed math, adds explicit
consume/produce counts and bounds, and shares stereo timing decisions. It does
not call or copy upstream's unsafe lite flush behavior.

The pinned upstream source, failing ASan repro and hashes are preserved in
ignored `builds/research/speed/sonic-feasibility/`. Background findings:
[feasibility investigation](../../docs/speed-dsp-feasibility.md).


## Native packet mapping API

```c
speed_result result;
speed_packet slot;
/* After speed_process succeeds and returns output: */
if (speed_packet_init(&slot, &result) != 0) {
    /* Reject oversized/invalid packet; do not submit it. */
}
/* Later, from verified native consumption of this slot: */
uint64_t relative_source_frame;
if (speed_packet_position(&slot, frames_consumed_within_slot,
                          &relative_source_frame) == 0) {
    /* Add the seek/chapter source origin, convert by original sample rate.
     * Do not multiply book time by the selected speed. */
}
```

The descriptor does not own a queue or track clocks. Root's native adapter owns
the pending/playing slots and their lifetimes. `frames_consumed_within_slot` is
an absolute frame count within that packet, not an increment. The helper is
pure: repeated reads are stable and a caller can request a smaller count; the
native adapter must supply monotonic actual consumption. Submission alone must
not advance audible time. Failed submissions retain their PCM and descriptor.
Pause/frozen consumption leaves source time unchanged. Core EOF is not audible
completion while native packets remain queued.

A packet can combine overlap and copy regions. Its endpoints are exact, but
`speed_packet_position` linearly interpolates the interior. Error against the
piecewise frame mapping is conservatively bounded by one output packet in
source frames (256 frames is5.33 ms at48 kHz). This is acceptable for the user's
approximate timestamps; the buffering/notification delay still must be accounted
for separately. Keep packets small for tighter mapping. The helper accepts up
to65,535 frames and validates a source span between1x and2x their count; this
keeps the interpolation product32-bit with no64-bit division helper. Empty
packets map only offset0 to their identical endpoint and should not be queued.

On seek/track/rate reset, stop or flush old native slots before resetting the
core and clearing descriptors. Anchor the new relative frame0 to the new source
position; do not let a stale old-slot completion overwrite the new timestamp.
The API intentionally has no generic FIFO, clock extrapolation or guessed DMA
ownership. Tests cover partial drains, monotonic/contiguous mappings, bypass,
zero-output calls, removed-frame accounting, EOF/reset, invalid descriptors,
maximal packet counts and source positions near UINT64_MAX.

## Integrated P4e resource checkpoint

After lifecycle review fixes, the complete payload is22,384 bytes text and
31,584 bytes BSS, totaling53,968 bytes with2,336 bytes below its reserved upper
boundary. This is allocation headroom, not measured stack or real-time margin.
Full firmware verification and review status are tracked in the integration
checkpoint; the standalone figures above do not replace those gates.
