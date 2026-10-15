# Stock PCM boundary for audiobook speed — 15 October 2026

Status: offline investigation and native-instruction regression tests. No speed
hook, menu control, firmware build or device write. P4d remains the archived
candidate; its 271-test evidence is separate from these new research tests.

## Finding

A candidate processing boundary exists immediately after codec buffer delivery
and before stock PCM expansion/EQ/output DMA. It is not yet a safe hook contract:
the decoder wrapper requests the next decode and copies a completed block into
alternating buffers. A variable-output processor needs its own bounded pending
input/output state and must preserve the stock two-phase handoff. It cannot just
shorten the DMA length or call the existing pump twice without ownership proof.

No pitch-preserving speed API has been identified in this trace. This is not a
proof that none exists elsewhere. The lightweight host prototype is described in
[speed DSP feasibility](speed-dsp-feasibility.md).

## Exact source and method

Source: original `NANOV170.IMG`, SHA-256
`54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
Assembly from extracted modules; REA 6.4.0 / Ghidra 12.1.4 corroborates the resident
pump. Analysis wrapper includes modules 0/33 only; it is not flashable and all
initialized sections were checked byte-for-byte against stock. Module42 was
subsequently inspected separately and included in native emulation, not presumed
to be present from the incomplete Ghidra overlay map. Function names are analyst
labels; assembly and execution take precedence over inferred decompiler types.

Local ignored evidence:

- `builds/research/speed/prepare-stock.py`: analysis ELF construction.
- `builds/research/speed/stock/provenance.json`: source/section hashes.
- `builds/research/speed/stock/pcm-pump.json`: REA/Ghidra output.
- `builds/research/speed/stock/pcm-tests.log`: native emulation results.

## Mapped boundary

| Address | Evidence / current interpretation |
| --- | --- |
| module33 `0x030835c8` | Codec buffer wrapper. Two pointer arguments: destination buffer pointer and length. Dispatches opcode10 through table at `0x03035178`, indexed by `0x03039e94`. |
| module42 `0x03085130` | One codec dispatcher. Opcode10 reaches `0x0308519a`; completion/error/in-progress fields at `0x03039e20+36/+44/+40`. Other codec overlays need separate validation. |
| module42 `0x030851ce..0x0308528a` | Clears completion, marks decoding, sends next request, then DMA-copies the completed PCM into alternating buffers `0x03023174` / `0x0302c174`; waits for copy completion before returning a pointer. These buffers are not free workspace. |
| resident `0x03069542` | PCM pump. Calls buffer wrapper at `0x0306957a`; result0 takes error/EOF handling, result2 sets wait flag and returns without converting/submitting stale PCM. Other successful results continue. |
| resident `0x03069484` | Expands packed 16-bit samples into signed 32-bit lanes shifted by8. Input length is stereo frames on this tested path; length is unchanged. Also has 24/32-bit branches, not yet dynamically checked. |
| resident `0x030697e2..0x03069836` | Final shift by8 and doubles frame count to output word count. This stage changes units. |
| resident `0x0306c1e4` | DMA submission boundary: channel5, PCM pointer, destination `0x40030024`, word count, config `0x03005b2c`, callback `0x030693cb`. Hardware/DMA implementation substituted in tests. |
| resident `0x030693ca` | Completion callback participates in prepared-block handoff using state fields +16/+20. Both callback-before-pump and pump-before-callback were executed. |

Shared state base is `0x0300d7e8`: status at+8, PCM pointer at+12, handoff flags
at+16/+20, waiting flag at+24, length at+28. Length means frames before final
conversion, words afterward. Codec metadata pointer is `0x03039714`, with bit
depth at metadata+156 and sample rate at+8 on the traced startup path.

Stock spectrum analysis reads128 32-bit sample lanes unconditionally on its
active path (`0x030697a4..0x030697b4`). A short DSP output block must not expose
an undersized allocation to that path. Bypassing the spectrum or providing a
padded bounded staging buffer requires an explicit integration design; changing
the output count alone does not protect this reader.

## Executed checks

`tests/test_stock_pcm_arm.py` executes original machine code:

1. Signed/full-scale 16-bit stereo samples expand correctly, frame count intact.
2. Ready PCM reaches DMA in original order, left-aligned in 32-bit words, with
   twice as many words as stereo frames and the observed callback/config.
3. Codec wait does not modify or submit a stale PCM buffer.
4. Actual module33 wrapper plus module42 dispatcher returns2 while decode is in
   progress, leaving output parameters unchanged.
5. Pump-before-callback prepares then submits once; a subsequent callback clears
   the handoff flag without resubmitting the same block in this sequence.
6. Callback-before-pump clears the flag and the pump submits the next block.

7. Native audio initialization installs the PCM pump at exception vector14
   (PendSV), with requested priority0xe0; actual vector registration executes.

All seven pass; independent source review and test rerun found no must-fix
defect in these limited claims. Tests pin the stock SHA-256 before execution. Decoder delivery is substituted in pump tests; the wait-dispatch
check uses native wrapper/dispatcher. IRQ controls, events, output DMA and
spectrum/EQ execution are outside these checks. No real-time scheduling, audio
quality, maximum decoder block size or cross-codec ownership guarantee follows.

## Integration gates still open

- Identify the installed codec overlay selection for each supported input and
  verify completed-buffer ownership, maximum block size and next-decode timing.
  Module42 requests another decode before rereading shared source pointer/length/
  format for its copy; field immutability cannot be assumed.
- Pump registration is PendSV (vector14, priority0xe0), confirmed through native
  initialization. Trace competing interrupt priorities and measure processing
  deadlines before adding DSP to this deferred interrupt path.
- Define bounded backpressure: DSP may consume a block without producing output,
  or have output remaining while native decoding progresses. Native return2 is
  a decoder-wait state, not permission to discard an unconsumed buffer.
- Drain delayed DSP output before allowing native EOF/chapter transition. Reset
  on seek, stop and chapter change; no old samples may bleed into the next file.
- Preserve bookmarks/resume in source time. Account for decoded-but-not-audible
  input when displaying/saving position; do not multiply saved timestamps by speed.
- Prove buffer/callback lifetime across overlay changes, and measure target CPU
  margin with normal UI/bookmark operations. Keep stock clocks during this work.

The next implementation is deliberately a host-only bounded processor with
rational speeds and shared stereo pitch decisions. A device Speed menu follows
only once the processing and native adapter work; inert presets are not useful.
