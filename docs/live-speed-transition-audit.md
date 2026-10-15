# Live speed transition audit — 2026-10-15

Initial read-only source/disassembly investigation for a player double-click speed menu.
The implementation update below supersedes the initial proposal/status statements.
No transition implementation, firmware build or device operation was performed.
The current packet-coalescing fix must remain intact. Current image/layout has
2352 bytes of RAM headroom; this is a budget constraint, not spare stack proof.

## Recommended boundary

Use a controlled same-book restart at the current chapter and audible source
position. Do not change `launched`, reset the active core, or discard live PCM
from a menu callback. The current adapter deliberately preserves DMA ownership
across generic reset/seek, and changing its rate midstream would require a new
source-mapping and pending-output contract.

The successful `pending` branch of `playback_prepare()` already validates the
playlist, applies an explicit chapter/time override, and calls
`playback_speed_launch()`. This is the existing rate-latching boundary to reuse.
`playback_position()` obtains the current physical chapter identity and replaces
native decoded-ahead time with the adapter's completed-output source clock.

The current browser launcher cannot be called blindly from the player:

- `playback_launch_path()` only arms `path_armed`; browser selection later copies
  that intent into `pending`.
- `book_menu.c:launch()` calls browser-overlay function `0x0307acb6`. Its presence
  and browser context are not established while the player owns the UI.
- `playback_music_launch()` provides a resident handoff pattern: remove the
  player service using `0x03059910(0x0300dc1c, 0x0302315c)`, post/remove native
  events396/349/395, then open window3 with argument1 through `0x0306b26a`.
  Reusing this sequence for a pending book relaunch needs a native integration
  test from the actual player-menu event context. Existing Music tests alone
  do not prove that new call site safe.

## Authoritative book identity and RAM

There is currently no `book_get()` API returning the active playlist path.
`resume.c` stores the RSM file identity, generation and signatures; `journal_open`
creates a companion pathname on its stack. The active queue stores chapter
identities and signatures, not the playlist pathname.

`last_book_snapshot()` validates a remembered explicit launch. It can describe a
different book from the current ordinary M3U launch. `pending_path` normally still
contains the active path, but a later attempted/cancelled selection can overwrite
it while the old book continues playing. Neither is an authoritative live path.

The robust option is to save `current_path[256]`, its playlist `media_ref` (32B),
and device/filesystem/valid fields at successful book preparation: approximately
548B, before alignment and other transition fields. Invalidate on leaving book
playback. This leaves roughly1800B of the current headroom for UI/state changes;
measure the final linked layout and stack paths together.

An alternative can reuse `pending_path` with a validity bit cleared before every
attempted overwrite. That avoids512B but disables live changes after a cancelled
or failed selection until another successful launch. It is safe only with that
explicit limitation and is less robust for the requested interaction.

## Preflight and commit API proposal

These names are proposed APIs, not existing functions:

1. `playback_current_book_snapshot(...)` validates active session, current
   playlist physical identity, device/filesystem, chapter identity and
   `playback_position()`. Reject missing or replaced files and unsafe scratch
   ownership without stopping playback.
2. `playback_change_speed(quarters)` validates range and current MP3 eligibility.
   Use a single pending transition token, not multiple queued restarts.
   Before teardown, validate that the on-card playlist still produces the active
   queue signature and that its selected chapter matches the active physical
   chapter. Existing private `book_preview_open()` can perform a preliminary
   validation without replacing the active queue, although it also reads
   companions; a smaller validation helper would need separate review.
3. After potentially slow validation, recheck the session token and chapter,
   then recapture audible time and play/pause state immediately before commit.
   An EOF/chapter transition during preflight must invalidate or retry the
   snapshot. Do not change desired/current rate on a failed preflight.
4. Stage an explicit pending launch with chapter>0, source milliseconds and
   expected signature. Use the resident service/window handoff, with an audited
   quiescent boundary before new audio starts. Only the successful preparation
   adopts the requested rate. Decide and test rollback behavior if an I/O error
   occurs after teardown; preflight cannot eliminate all later failures.

A same-rate selection should avoid restarting. Unsupported formats should retain
native1x and communicate that fact. All new requests must preserve the current
coalescing, epoch, bookmark writer and source-time rules.

## Native pause-state evidence

Evidence is existing stock disassembly in `builds/research/mod33.txt`:

- Native player state is the halfword at `0x0300d81a`, referenced by literals
  `0x030818f8` and `0x03082228`.
- The pause/toggle routine `0x030816ee` sees state0, sets state3 at
  `0x03081716..0x0308171a`, sets pump status4, and drains/polls channel5.
- Resume `0x03081f10` reads this state, handles state3, captures native preroll at
  `0x03081f56`, submits at `0x03081f98`, then writes state0 at `0x03081f9e` and
  pump status0 at `0x03081fa0`.
- Startup `0x03081432` checks the same halfword at `0x03081662`. Nonzero state
  skips the DMA submission and pump-enable branch. State3 also sets service+56
  to-1 before joining `0x030816b8`.

This suggests a genuine paused relaunch can initialize/seek the decoder while
preserving state3, avoiding a play-then-pause audio burst. It is not yet proven:
trace and execute all writers between player initialization, custom queue init
and `0x03081662` to identify the correct place to restore state3. Do not infer
user pause solely from pump status4, which also represents stop/error states.
Reject or defer a transition in unsupported native transient states.

## DMA and time constraints

Normal pause/stop polling is bounded and checks requested channel5; the driver
can allocate channels0–4 instead. A successful return is not proof of quiescence.
The adapter now tracks the actual accepted channel. Only its existing thread-mode
non-pump boundary can retire an idle current transfer, under PRIMASK, with no
foreign callback and the documented callback-table acknowledgment protocol.

A restart must not rush into a raw submission while the old actual channel is
still active. Existing serialization would preserve memory but terminal-fault
the stream. Prove the resident handoff drains the actual channel, or add a bounded
transition/deferred-start mechanism that waits for that condition. Do not hold
interrupts disabled while waiting or while native codec copies complete.

Bookmarks and resume saves must keep using completed source time. Capture time
before resetting the adapter; never derive it from output time times speed.
Current timing is packet-completion based, and the existing native resume path
rounds saved milliseconds to its seek granularity (the regression maps1234567ms
to1235000ms). A restart therefore must not promise sample-exact continuity.

## Current-speed label

`playback_speed_get()` returns the global desired preference, not current rate.
The UI needs a separate status API exposing the launched/effective rate and
unsupported/starting/paused state. Fast playback with an active eligible core
can report its launched rate. Unsupported native playback is1x. During a pending
transition distinguish requested from effective; do not show a requested value
as already audible. Avoid changing eligibility state merely to render a label.

## Focused implementation tests

- Actual player-menu launch path: valid current identity, explicit chapter/time,
  correct pending preparation and new rate; no browser-overlay call dependency.
- Playing1x→fast, fast→1x, fast→fast; same-rate selection does not restart.
- Paused transition: native initialization and startup branch execute with no
  audio DMA; resume starts at the selected rate and source position.
- Current+prepared DMA, unpublished partial packet, delayed completion and
  fallback DMA channel; no old storage reuse or stale timestamp publication.
- Missing/replaced playlist or chapter, changed signature/device, scratch busy,
  and session/chapter change during preflight: no service stop or preference
  mutation on refusal.
- Failed/cancelled future book selection cannot cause restart of the wrong book.
- EOF boundary and last chapter: no accidental wrap, duplicate advance or
  restart at chapter1.
- Bookmarks before/after change use source time, including native seek rounding.
- Global next-launch preference and current effective label remain distinct;
  unsupported content remains native1x.
- Re-run coalescing/sample-equivalence tests and final memory/layout checks.

This design is not a claim that paused relaunch, DMA quiescence, or the new live
menu transition has been verified. Those are explicit implementation gates.


## Implementation update — 2026-10-15

The combined offline candidate implements an authoritative current-book snapshot,
`playback_rate_request/poll/cancel`, actual-channel DMA drain, and a resident
same-book relaunch. Preflight runs before pausing and again after drain. It checks
playlist identity/signature and chapter identity; size validation reads the
physical directory record rather than the queue's deliberately zero size field.
Same-cluster, same-size content replacement is not detected by a content hash.

The native player settings menu appends Speed to its six existing entries for
eligible MP3 books. Native submenu entry, Back, ordinary sound-control dispatch,
and service cancellation have instruction-level tests. The normal player title
reserves room for an actual-rate label; ordinary music retains its title width.
The label uses the existing five strings and native text renderer.

Paused relaunch restores native state after initialization, and tests execute
the stock startup branch that skips DMA when paused. Playing transitions wait
for the actual accepted audio channel, not a hard-coded channel5. They preserve
completed source time and retain the packet coalescing fix.

Known limits: the speed preference is shared/RAM-only; changing speed briefly
restarts the decoder with native seek rounding. Refusal has no explicit UI error.
Cancellation/timeout after pausing leaves playback paused. A late I/O failure
cannot roll back an already closed decoder. Hardware timing and listening tests
remain required; emulator checks do not establish device acceptance.


### Review corrections

The final backend review found two defensive-path defects. Runtime PCM bypass
could be displayed as the latched accelerated rate. Eligibility now rejects
`bypass && launched > 4`, so the label reports1x and a same-rate1x selection
cannot silently leave an accelerated latch to reappear on seek. The user must
relaunch normally after this exceptional decoder-contract fallback.

Queue chapter references intentionally have size0, making a size comparison
between them ineffective. Preflight now resolves the selected directory entry
into a96-byte temporary native state and compares its size with the current
player record, both before pause and after drain. Regressions cover unchanged
cluster/index with changed size at both boundaries. The compiler reports a184B
preflight stack frame; this is separate from static payload headroom. Native
calls and interrupt stack high-water remain outside a complete worst-case proof.

The linked payload is24096B text plus32176B BSS, ending32B below the unchanged
0x0309fff0 limit. No RAM boundary was expanded. Further additions require
reclaiming space;32B is a static allocation margin, not a stack allowance.
