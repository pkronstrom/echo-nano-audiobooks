# Audiobook speed DSP feasibility — 2026-10-15

Status: research only. No DSP was added to the firmware, no firmware image was
built here, and no device operation occurred. The bounded prototype below is a
plausible next step, not evidence that real-time playback works on the Nano.

## Evidence and recommendation

Use a small, fixed-capacity, pitch-period overlap-add processor as the first
prototype. Keep the decoder and output sample rate unchanged; consume more
source frames per output second. Changing the DAC clock alone changes pitch.
The exact stock PCM ownership, pump/backpressure and timestamp integration must
be established independently before installing any hook.

[Sonic](https://github.com/waywardgeek/sonic) is an Apache-2.0 speech-speed library.
Its `sonic_lite` variant is specifically a static-memory, mono-only speedup
implementation. The small variant is a useful algorithm/reference, **not a safe
drop-in dependency**. Upstream source was pinned to commit
`b93885dcb70aae50c6f76b0fe4e0868f029a077e` on this investigation. Preserve its
license and attribution if adapting code.

The local SDK reference `builds/research/speed/AudioControl.c` contains sample-rate
conversion for Bluetooth output and codec/DAC setup. That is not evidence of a
stock pitch-preserving speed feature or of Nano buffer addresses. In particular,
its large static resample buffer is not memory we may assume is free.

## Concrete RAM and code constraints

P4d's measured payload is 18,640 bytes text and 17,676 bytes BSS, leaving **19,988
bytes** inside the audited `0x03092400..0x0309fff0` interval. This headroom must pay
for DSP code, state, PCM buffers and any additional integration storage. It is
not a general heap allowance. See [layout](playback-memory-layout.md) and
[P4d checkpoint](book-usability-followup.md).

Standalone object measurements use the existing GCC 13.2 ARM toolchain,
`-mthumb -mcpu=cortex-m3 -Os -ffreestanding`, with lite input bounded at 256
mono frames and minimum pitch 65 Hz:

| Sample rate | Object text | Object BSS | Approximate shared-period stereo state |
| --- | ---: | ---: | ---: |
| 44,100 Hz | 1,072 B | 6,212 B | 12,148 B |
| 48,000 Hz | 1,072 B | 6,692 B | 13,108 B |

Mono sizes are actual object measurements. Stereo is an estimate, rounded to
4-byte alignment, doubling input/output sample arrays while retaining a single
mono pitch-analysis array; no stereo implementation was compiled. Stereo must
use one timing decision for both channels, not two independently drifting mono
streams. Counts exclude adapter/output staging, stack and linked runtime helpers.

The object still references software floating-point helpers, including double
comparison/conversion, and memcpy/memmove/memset. Its text size is therefore
**not the final linked cost**. Fixed rational settings (5/4, 3/2, 7/4, 2/1) can
remove floating-point speed calculations in an adaptation; measure the actual
linked result before claiming it fits. Leave margin for bounds checks and safe
EOF handling.

For comparison, full Sonic's initial PCM buffer allocation alone is 12,882/
14,022 bytes mono and 23,052/25,092 bytes stereo at 44.1/48 kHz respectively.
Those are derived from its allocation expressions, excluding stream state,
code and later growth. Full stereo already exceeds the headroom. The generic
no-malloc mode does not solve this: its realloc replacement consumes additional
arena space. [Pinned full source](https://github.com/waywardgeek/sonic/blob/b93885dcb70aae50c6f76b0fe4e0868f029a077e/sonic.c)

## CPU evidence versus estimates

At 2x, decoding must sustain twice the source frames per wall-clock second,
in addition to stretching and the existing player/UI. For 48 kHz stereo 16-bit,
that means 384,000 decoded PCM bytes per second versus 192,000 output bytes per
second. At 44.1 kHz it is 352,800 versus 176,400. These are throughput arithmetic,
not bandwidth or CPU benchmarks of the device.

A local instrumented lite run counted inner AMDF comparisons on a 60-second,
48 kHz mono 125 Hz sine wave (amplitude 12,000), with 256-frame writes and output
drained after every write. No EOF flush was used in this counter run:

| Speed | Comparisons/source second | Comparisons/compressed second, estimated |
| --- | ---: | ---: |
| 1.25x | 977,350 | 1,221,688 |
| 1.5x | 1,628,265 | 2,442,398 |
| 1.75x | 2,093,484 | 3,663,596 |
| 2x | 2,442,723 | 4,885,447 |

These are operation counts on one synthetic signal, **not Cortex-M3 cycles,
speech benchmarks or worst-case bounds**. Each comparison includes loads,
subtraction/absolute-value and accumulation; overlap-add and other work are
additional. The instrument inserted a counter in `findPitchPeriodInRange`'s
inner loop. Actual speech, silence, music and noise need separate measurements.
No CPU-utilization or battery claim is supported yet. Do not combine the first
speed prototype with a CPU-clock reduction.

## Reproduced upstream lite safety failure

A host AddressSanitizer run of the pinned lite source, changed only to 48,000 Hz
and 256 input frames, reports global-buffer-overflow during `sonicFlushStream`.
Reproduction writes twenty zero-filled blocks at 1.25x, drains after each block,
then flushes. The failure is in `copyToOutput` via `copyInputToOutput`; ASan reports
a 720-byte write reaching beyond the 6,692-byte `sonicStream` global.

```c
#include "sonic_lite.h"
int main(void) {
    short in[256] = {0}, out[4096];
    sonicInit();
    sonicSetSpeed(1.25f);
    for (int i = 0; i < 20; i++) {
        sonicWriteShortToStream(in, 256);
        sonicReadShortFromStream(out, 4096);
    }
    sonicFlushStream();
    return 0;
}
```

Fetch pinned `sonic_lite.c`/`.h`, change header `SONIC_SAMPLE_RATE` from 8000 to
48000 and `SONIC_INPUT_SAMPLES` from 80 to 256, then:

```sh
clang -g -fsanitize=address sonic_lite.c probe.c -o probe
./probe
```

The source's flush advances the input count beyond the declared buffer capacity;
output writes also lack capacity checks. Consequently an adaptation requires
explicit consume/produce bounds and incremental EOF draining, not merely a
larger buffer or a wrapper around the unmodified flush. Pinned sources, object files, probes, the captured ASan failure and SHA manifest
are archived in ignored `builds/research/speed/sonic-feasibility/`.
[Pinned lite implementation](https://github.com/waywardgeek/sonic/blob/b93885dcb70aae50c6f76b0fe4e0868f029a077e/sonic_lite.c)

## Bounded next implementation and ship blockers

1. Build a host-only speedup core: 16-bit PCM, 1x bit-exact bypass, four rational
   speed settings, caller-provided fixed buffers, explicit consumed/produced
   frame counts and checked capacity on every path. Start mono; add stereo using
   shared pitch decisions. Keep native sample rate and channels unchanged.
2. Test every supported rate/speed/channel combination with uneven chunks,
   silence/noise/tones/speech, full-scale values, tiny outputs, EOF, reset/seek,
   and live setting changes. Use sanitizers and canaries; check duration, pitch,
   channel alignment and bounded latency. Never flush old samples into a new
   chapter after seek/reset. Listen to real speech before choosing quality.
3. Measure linked Thumb footprint and host operation counts. Then map the exact
   stock PCM callback ABI, decoder/output ownership, sample format and maximum
   frame count, DMA lifetime, pause/seek/EOF paths and timestamps. Existing book
   bookmarks must remain source-time coordinates, not shortened playback time.
4. Integrate only after those contracts are verified. Measure target deadline
   margin at 2x while navigating/saving bookmarks. Hardware audio acceptance is
   required; emulator tests do not establish real-time scheduling or fidelity.

If the checked stereo adapter cannot fit the audited region with margin, keep
stereo at 1x until there is an explicit solution. Do not silently downmix books,
reuse native decoder buffers without ownership proof, or expand into unverified
RAM. Offline conversion remains a separate user-visible fallback rather than
pretending the requested on-device speed control exists.


## Host prototype checkpoint

The first bounded core now exists under
[experiments/audiobook_speed](../experiments/audiobook_speed/README.md). It is not
firmware-integrated. The sanitizer matrix passed; the standalone Cortex-M3 link
measured 2,048 bytes text plus 11,728 bytes caller state, leaving 6,212 bytes of
P4d's headroom before integration. This supersedes the earlier stereo estimate
for the implemented prototype, not the measured upstream object sizes above.

Its stronger-channel pitch analysis shares timing across stereo, including
opposite-phase and right-only input. Integer rational bookkeeping retains
approximate requested rates; EOF can differ by one pitch period. This matches
the user's preference for clear speech/performance over exact multipliers.

The prototype's retired-source counter is not audible playback position. The
future stock adapter must carry source-time mapping through pending overlap,
audio output and DMA queues before updating resume/bookmark state. No automatic
rate menu, live rate-change policy, hardware deadline result or speech listening
acceptance is implemented by this checkpoint.
