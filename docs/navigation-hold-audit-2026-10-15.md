# Navigation hold timing audit — 2026-10-15

Stock-instruction analysis followed by isolated resident-hook implementation
and host ARM emulation. No combined firmware build or device operation.
Source: pinned NANOV170.IMG, SHA256
54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116.
Evidence disassemblies: builds/research/mod00.txt, mod31.txt and mod27.txt.

## Native events and thresholds

The physical-key FSM is 0x03065e9a, called by 0x03065fba.
State base is 0x0300d03c; +44 is current key, +48 retained key,
+56 event phase and +60 held-poll counter. It emits:

- Poll2: 0x10000000 | key (down/debounced).
- Poll20: 0x20000000 | key (initial hold), at 0x03065eea and
  0x03065efe..5f10.
- Poll28,36,...: 0x30000000 | key (repeat), offset20/mask7 at
  0x03065f14..5f18.
- Release before20 after at least2 polls: 0x40000000 | key.
- Release at/after20: 0x50000000 | key, compare at 0x03065f68.

Navigation consumes 0x20000040 as Back. Key0x40 is the center/select route.
The key decoder 0x03065d5c returns it through 0x03065dda; do not infer
thresholds from its ADC-level comparisons, which are voltages/counts, not time.

The longer center hold uses initialized module0 data at 0x03004104:
words {0x30000040, 0, 0, 7}. The event dispatcher at
0x03063a76..3a88 counts matching repeats, and on the seventh sets flag10
through 0x03063a8a..3a8c -> 0x03051524. Thus its nominal threshold is
held poll76 (20 + 7*8), assuming each repeat is consumed.

Flag10 is demonstrably main-menu navigation: module31 0x03079ed2..9ed8
tests/clears it via 0x03051574, then 0x03079eda..9ede calls window(0,sp)
through 0x0306b26a. Module27 0x0307a52a..a536 does the same.
The center long-release resets the repeat count at 0x03063ac0..3ac8.

Timing is pinned in key polls, not milliseconds. The callback pointer
0x03065fbb occurs at module0 data0x03005a50; nearby record0x03005a38
has value2 at +16. This suggests a two-tick registration but the scheduler
unit/callback cadence has not been proven. Do not present a millisecond value.

## Implemented isolated change

Do not patch the global20-poll comparisons: other keys use these for seeking
and power behavior. Instead, only for current key0x40, change the held-counter
transition14->15 into14->20. All remaining stock FSM code stays intact.
Persisting the adjusted count means release after the earlier hold correctly
uses the long-release class; no spurious short click is introduced.

Hook site module0 0x03065ec0, expected bytes `40 1c 29 63`:
`adds r0,r0,#1; str r1,[r5,#48]`. Replace with a non-linking branch to a
resident helper that adds6 iff r1==0x40 and r0==14, otherwise adds1;
replays `str r1,[r5,#48]`; branches back to0x03065ec4. That instruction
persists the adjusted counter. Preserve r1/r2/r4/r5/r6/LR and stack.
Subsequent stock comparison replaces flags, so incoming NZCV need not survive.

Additionally change the repeat threshold at module0 DATA address0x03004110
from `07 00 00 00` to `05 00 00 00`. This is not code address0x03054110.
Then Back starts at physical poll15 (25% shorter), repeats at23,31,39,47,55,
and main-menu flag10 occurs at55 (about28% shorter). The isolated hook and
data edit implement these values; native instruction tests verify both boundaries.

Short presses below15 polls retain stock processing. The separate35-tick
click aggregation at0x030636fe is untouched. Other-key held counters,
repeat intervals, ADC thresholds and power-special handling at0x03065f20..64
are untouched. This is not a change to forced-restart timing or hardware.

## Resident placement

Existing playback/speed/bookmark caves have explicit owners; do not append
to them or call an unguarded reloadable playback payload from this global FSM.
A small independent resident helper fits in module0 0x03065918..0x0306593f,
currently a40-byte watchdog diagnostic string:

```
200a3e3e3e23232320776174636820646f672069737220636f6d696e673c3c3c232323200a000000
```

Visible ADR user:0x030658b6 (`18 a0`); printf call0x030658b8
(`0c f0 b6 fa`, BL0x03071e28). Reclamation must disable that printf alone,
preserve watchdog fault handling from0x030658bc onward, and check exact bytes.
An unaligned four-byte pointer scan across every module code/data range found
no absolute pointer into [0x03065918,0x03065940). The mod00 disassembly has
the one ADR user above. Layout validation pins the string, ADR, printf, replaced
FSM instructions and full four-word repeat record, and rejects absolute references
to any byte in the cave. Tests verify the patched fault path still calls
0x030550b6(0) and reaches the original terminal loop. This removes only the
watchdog diagnostic printf; no claim of device boot safety follows.

## Offline regression scope

Execute the real stock key FSM with only physical GPIO/ADC substituted,
and the actual dispatcher with unrelated services stubbed:

1. Center holds/releases at1,2,14,15,19,20 polls; down remains poll2,
   hold exactly poll15, release below15 short and at/above15 long.
2. Center repeat sequence23,31,39,47,55; exactly five matching repeats
   set flag10; native browser consumes it and calls window0.
3. Center long-release clears repetition state; a new press starts fresh.
4. Every other physical key retains the stock event sequence, especially
   previous/next seeking and power-special behavior.
5. Short/double center clicks retain the separate aggregation behavior.
6. Byte-pinned helper/cave/data edits; helper preserves required registers,
   stack and LR; watchdog fault path still executes its original handling.

After offline checks, user hardware acceptance still determines feel and
interaction during playback. Host execution alone does not establish boot safety.

## Implementation and result

Owned source files are `playback/hooks/navigation_hold.S`,
`playback/hooks/navigation_hold_resident.S`, the narrow hook registrations and
`navigation_hold_space()` in `tools/playback_layout.py`, and
`tests/test_navigation_hold_arm.py`. The resident helper uses 40 existing code
bytes and no additional RAM; it never enters the reloadable playback payload.

The boundary tests were first run against stock with a no-op patch function:
three expected failures demonstrated stock hold20 and short releases at15/19.
After applying the hook, all nine focused tests passed (0.761s):

```
builds/tools/test-env/bin/python -m unittest discover -s tests -p test_navigation_hold_arm.py -v
```

The test harness assembles only the two new hook files into a temporary
directory. It runs the native key FSM, repeat dispatcher fragment, native flag
setter and browser flag consumer. It checks stock20/76 versus patched15/55,
release boundaries, repeat reset across presses, unchanged sequences for keys
1/2/4/8/0x10/0x20/0x80/0x1000 (including the power service path), preserved
registers/SP/LR, exact hook sizes, changed-byte/interior-pointer rejection, and
the watchdog fault-call continuation. Physical key acquisition and power/fault
services are substituted; no real hardware is accessed.

Two short center presses retain their native short-release events, and the
separate click aggregation code remains byte-identical. Full end-to-end click
aggregation/UI behavior is not emulated by this focused harness. Combined image
integration, independent review and hardware acceptance remain separate work.
