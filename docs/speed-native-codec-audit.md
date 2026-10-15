# Native MP3 speed adapter audit — 15 October 2026

Offline native-instruction evidence only. No firmware build or device operation.
Source is stock `NANOV170.IMG`, SHA256
`54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
Tests pin this hash. Addresses below are host processor addresses unless marked
module73 offsets (secondary processor code addresses, not the upload window).

## Confirmed adapter boundary

Module33 `0x030835c8` is the codec buffer wrapper. Its two arguments are pointers
to a returned PCM pointer and frame count. The resident pump calls it from
`0x0306957a`, with LR `0x0306957f`. Other callers include startup/resume at
`0x03083326`; these must retain stock behavior. Intercepting only the pump caller
avoids changing native initialization and its muted initial block.

Type at `0x03039e94` equal to zero selects table slot0 at `0x03035178`, pointing
to module42 dispatcher `0x03085131`. Native loader function `0x03080f02` selects
module42 through `0x0306b6bc(42,7)`, then secondary module73 through
`0x030714e4(73)`. A native test executes this path to the loading boundary.
Module73 contains explicit `Mp3\libMad\mp3_decinternal.c` and
`mp3_preparse.c` strings: this is the MP3 path, not an inferred file extension.
Other codec types/overlays remain outside this adapter contract.

Conservative enable guards: active audiobook session, codec type0, depth16,
sample rate8000..48000, and validated successful delivery with frame count in
1..1152 and one of the two native destination addresses. Keep all other formats
on stock playback. A malformed or changed block while DSP has pending output
needs an explicit drain/reset policy; silently discarding accepted PCM is not a
safe fallback.

## Successful native delivery and ownership

Module42 opcode10 enters `0x0308519a`, using shared packet `0x03039e20`:

| Offset | Observed meaning |
| --- | --- |
| +0 | decoded source timestamp in milliseconds (opcode7) |
| +12 | bit depth (opcode17) |
| +28 | source PCM pointer from secondary processor |
| +32 | frames in completed block |
| +36 | completed packet flag |
| +40 | decode in progress flag |
| +44 | completion error/end flag |

With completion1 and error0 it stores the output frame count, clears completion,
sets in-progress, then issues mailbox calls `0x03071a90(4,0,1)` and
`0x03071a64(0,0,1)`. **The next decode is requested before the copy.**
It then allocates a DMA channel with `0x0306c1b8`, copies from packet+28 to
alternating buffers `0x03023174` and `0x0302c174`, and polls completion through
`0x03059a04`. Native completion callback `0x03057420` writes halfword1 to
`0x030045c4`. Returned pointer is published only after that completion.
Copy DMA count is `(frames * bits) >> 4` 32-bit words: for16-bit, four bytes per
frame, consistent with interleaved stereo. These buffers have stock owners and
must not become general workspace.

Native execution of three1152-frame deliveries proves A/B/A destination reuse,
unchanged first buffer after the second delivery, and overwrite on the third.
Tests substitute mailbox hardware and DMA transport but execute the actual
copy-completion callback. They do not simulate a concurrently executing decoder.
Thus they prove wrapper ordering and bounded reuse, not arbitrary asynchronous
shared-packet immutability.

An adapter may retain one returned input buffer only while it prevents subsequent
native deliveries until that block is consumed. It must never request another
block merely to obtain more output while retaining unconsumed pointers. Output
staging must also survive the stock prepared/current DMA handoff and in-place
16-bit-to32-bit expansion. Spectrum additionally reads128 sample lanes even for
short blocks; allocate and pad appropriately.

No completion + in-progress1 returns2 without changing output arguments.
No completion + idle0 sends the next request and returns2.
Completed packet + error1 returns0 without a copy or further request.
These three paths and successful alternating delivery are exercised natively.

## MP3 channel format and block size

Secondary module73 is linked with code addresses starting at zero; the image
code execution field `0x01000000` is the upload window. Tests load its code at
zero and data at its linked `0x01020000` region, separately from host modules.
This is analysis/emulation only, not a proposed loader change.

Native output setup offset`0x3968` derives the channel mode from the decoder
object byte1. Output routine offset`0x36ea` writes signed16 interleaved stereo:
mono samples are duplicated into left/right pairs, while stereo channel0/1
fill their own alternating lanes. Native tests execute setup and rendering with
full-scale signed samples and distinct stereo content. Therefore the host speed
adapter should process two channels even for mono MP3 source files.

Module73 opcode17 returns fixed16 through offset`0x33d0`. Opcode10 at offset
`0x3290` returns buffer pointer from `0x0102221c` and frame count from
`0x010242f8`. Initialization defaults that count to1152 at offset`0x3180`;
examined parser writers use1152/576/384 (for example offsets`0x42d6`, `0x42f6`,
`0x46c6`, `0x46d6`). Native export tests cover all three. This is strong evidence
for normal MP3 blocks, not proof of a bound under corrupt state: retain the
runtime1152 cap. No whole-file decode or malformed-MP3 campaign was performed.

## Source time and EOF hazards

**Timestamp is packet+0, not packet+4.** A regression deliberately puts different
values in those fields and verifies native host opcode7 uses+0. Module73 opcode7
computes total decoded frames at `0x010429bc+60` times1000 divided by sample rate
at+40. Native test4800frames/48000Hz returns100ms. Successful decode increments
that total at offsets`0x335a..0x3360`; initialization seeds1152 frames. This is
decoded-source time, not output DMA completion time.

Host player service at `0x03082ffc` calls opcode7 wrapper `0x030834f6` with
PLAYER metadata+4 while playback status is zero, refreshing visible current time.
Consequently a corrected timestamp written only at DMA submission can later be
overwritten by stock decoded-ahead time. Override the getter or otherwise guard
that refresh while the speed adapter owns timing; preserve all stock callers
when inactive.

Capture timestamp/frame metadata **before** native buffer delivery sends the next
decode, and only bind it after successful delivery. An end-time-minus-block-time
anchor is consistent with the native decoded-frame accounting, but startup/seek
pre-roll must be integration-tested before claiming exact bookmark positions.
Requested resume time alone ignores the native startup muted block. Keep source
accounting in source frames and account separately for DSP-retired, staged,
submitted and completed output; do not save output-time multiplied by speed.

Native EOF paths zero PCM and post events85/243. An adapter must delay EOF until
its own output and native prepared/current DMA blocks are drained. **Wakeup trap:**
callback `0x030693ca`, when state+16 equals1, clears state+20 and returns at
`0x030693dc` without triggering PendSV. If adapter returns2 solely waiting for
final DMA completion, no decoder event may remain to wake it. A completion-side
adapter wakeup or another proven scheduling source is required.

Native pump is installed as PendSV vector14, priority request0xe0. The callback
and pump share state `0x0300d7e8`, including PCM pointer+12, flags+16/+20,
wait+24 and length+28. Stock status halfword+8 gates pump work. Long DSP work
must be measured against actual interrupt deadlines; host execution does not
establish schedulability.

Seek helper `0x03082132` forwards current metadata milliseconds through
`0x030834d8` (opcode14). Stop path `0x03082164` sets pump status4 and polls DMA
channel5 before teardown; shutdown helper `0x03081a8c` disables/unregisters
vector14. These are static traces, not exhaustive pause/seek interleaving tests.
Explicit generation reset is still required for seek, stop, new chapter and
format/session changes. Do not treat every pause as EOF or restart a paused DSP
stream from stale buffered PCM.

## Resident bridge cave candidate

`0x030696d4..0x0306970b` is56 bytes occupied by two diagnostic strings:
`\n------1 file error------ ` and `\n------2 decode end------ ` with padding.
Their visible ADR users are `0x030695b4` and `0x030695cc`, followed by printf
BLs at`0x030695b6`/`0x030695ce` targeting`0x03071e28`. If reclaimed, remove both
printf calls and validate exact bytes first, leaving error state, zeroing and
event posting intact. No absolute pointer reference occurs in module0 code.
A full-overlay reference scan and patched fallback execution are still required;
this paragraph is a candidate, not authorization to overwrite unchecked bytes.

## Verification

`tests/test_stock_pcm_arm.py`: **15 tests pass**, including native loader mapping,
module42 successful/error/wait paths, module73 channel packing and metadata/time
exports, resident expansion, DMA handoff and PendSV registration. Command:

```
builds/tools/test-env/bin/python -m unittest discover -s tests -p test_stock_pcm_arm.py -v
```

Last run:15 tests in0.090s, OK. Unicorn requires the approved JIT execution
permission on this host. No device writes or firmware builds were performed.

## Integration follow-up evidence

The host completion IRQ publishes the packet shadow: success at `0x03081b7a`
copies the secondary-core packet into `0x03039e20`, then `0x03081baa` stores
completed=1/decoding=0. EOF at `0x03081bc0..0x03081bc8` sets completed/error.
The secondary packet is a distinct copy source. Module73 has no direct reference
to this host shadow. Mailbox sends `0x03071a64` and `0x03071a90` are MMIO writes
followed by return, without an interrupt-dependent wait. This supports a short
PRIMASK guard around the not-ready check/request and metadata snapshot. Restore
interrupts before ready opcode10, which waits for the DMA copy callback.

Output DMA submissions also occur in module33 at `0x0308168c`, `0x03081f98`,
`0x03082062` and `0x03083360`; all four join the two resident sites in the speed
guard. Non-pump capture callers ignore wait status and can clear/convert the
output pointer immediately. The adapter must restore a large native buffer when
leaving its small DSP slots and preserve any currently playing slot.

The pump's nonzero-status branch at `0x0306955e` skips capture and reaches the
final conversion at `0x030697e2` with a previous word count. Repeating this on a
small DSP slot can write beyond it. The new guarded branch exits through the
native epilogue at `0x030695e8` for an owned DSP pointer; stock pointers and an
invalid playback header retain the native continuation. Its resident space is
the audited 56-byte diagnostic block above, with both printf calls disabled.

DMA submission itself uses stock critical nesting: `0x0306a37a` increments the
byte at `0x0300d83e`; `0x0306a360` decrements it and executes CPSIE i on zero.
An independent PRIMASK guard alone is therefore not sufficient to keep the
native call masked through its return. Preserve both the nesting contract and
the incoming mask when protecting adapter ownership around this call.

## Stop/resume audit after Fable review

Normal module33 pause (`0x03081ec8`) and stop (`0x03082164`) set status4,
poll channel5 with bounded loops, then clear native prepared/current flags.
Their return is not proof of DMA quiescence. No direct DMA-abort call was found
in either path. `0x0306c362` halts DMA and is paired with resume
`0x0306c3a0`; it is not callback cancellation. Low-level disable helpers
`0x03059c08` and `0x03059c32` can acknowledge completion without invoking or
clearing callbacks, but no direct module00/module33 callers were found.

The DMA IRQ at `0x0306c3c8` snapshots pending bits at `0x600002e8`, acknowledges
through W1C `0x60000338`, clears its callback-table entry at `0x0306c404`, then
invokes the captured callback at `0x0306c408`. Table base is `0x0300bd88`.
An idle hardware channel alone therefore does not prove callback completion.
Track the actual channel returned by DMA submission; native allocation can
fall back from requested channel5 to channels0–4.

At a non-pump startup in thread mode (IPSR0), with interrupts masked, the
adapter can cancel prepared chaining and release unsubmitted slots independently
of the native PCM pointer. It can retire current ownership only when the actual
channel is idle and its callback entry is zero or still our own callback. In
the latter case, remove our entry, acknowledge only that channel and issue DSB.
Do not call stock completion or publish an audible timestamp for retired work.
An active channel or foreign callback retains ownership. Thread-mode restriction
prevents an already-running ISR holding the old callback in a register. Seek
and generic reset must not perform this destructive retirement.

The known stock callback `0x030693ca` overwrites incoming argument registers
before use (r0 loaded at `0x030693d0`, subsequent DMA arguments initialized).
Calling this specific callback without arguments preserves its actual contract;
this is not a general guarantee for arbitrary callback functions.

Follow-up confirms a zero callback entry needs no explicit acknowledgement at
retirement: a pending IRQ sees null, and native submission acknowledges its
channel at `0x03059aa2` before registering a new callback at `0x03059ad8`.
The allocator's return at `0x0306c286` is the actual signed channel result.

### Module33 callback arguments pinned

All four module33 audio DMA sites pass the known `0x030693cb` callback as
argument6 (`[sp+4]`). The referenced literals contain halfwords `93cb 0306`:

| DMA call | Callback load | Literal | Stack setup |
| --- | --- | --- | --- |
| `0x0308168c` | `0x03081674: ldr r1` | `0x03081950` | `0x0308167c: strd r0,r1,[sp]` |
| `0x03081f98` | `0x03081f86: ldr r1` | `0x03082238` | `0x03081f8a: strd r0,r1,[sp]` |
| `0x03082062` | `0x03082052: ldr r1` | `0x03082238` | `0x03082056: strd r0,r1,[sp]` |
| `0x03083360` | `0x0308334c: ldr r1` | `0x030833dc` | `0x03083354: strd r0,r1,[sp]` |

Native DMA `0x0306c1ec` loads arguments5/6 into r6/r5 from `[sp+48]` after its
48-byte prologue. Evidence is the pinned stock disassembly in
`builds/research/mod33.txt` and `mod00.txt`. This resolves the follow-up review's
callback-evidence note for these four sites; future hooks must recheck their ABI.

## Final panel follow-up: metadata and wait-state publication

Normal startup publishes valid metadata before enabling the PCM pump:
`0x03082906` loads `0x03023090` from literal `0x03082ad4`, and `0x03082908`
stores it at player+12 (`0x03039714`). Startup calls initializer `0x03080dee`
at `0x03081524`. The initializer writes rate+8 through `0x03080e0a` →
`0x03083532` (opcode4), and depth+156 through `0x03080e22` → `0x03083604`
(opcode17), rejecting missing/nonpositive fields at `0x03080e64..e76`.
Only afterward does startup capture at `0x0308157a`, submit DMA at
`0x0308168c`, set status0 at `0x03081692`, and wake the pump at `0x030816a2`.
Thus the review's speculative early-metadata bypass is not demonstrated for
normal startup; this does not prove every corrupted/unusual state impossible.

With no completed packet, opcode10 returns2 for valid in-progress values0/1:
value1 returns at `0x030851b2..b6`; value0 requests decode at
`0x0308528c..a2` and returns2 at `0x030852a8`. Under PRIMASK, the completion
IRQ cannot publish a different shadow during this check. An invalid flag other
than0/1 can return0 via `0x030851ba` → `0x0308538e`; the wait-only contract
assumes valid native state. Treat validation of corrupted native flags as a
separate hardening task, not evidence of a normal ready-path drain failure.
