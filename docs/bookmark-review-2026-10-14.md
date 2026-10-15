# Bookmark milestone review — 2026-10-14

Claude CLI Fable reviewed the offline bookmark gesture and memory relocation.
Its verdict was **warn**. The dispatcher exited65 because the JSON result
lacked its final closing brace. The original text was recovered and parsed by
adding that brace; no finding text was changed. Local report:
`builds/sd-audiobook-test/fable-bookmark-review.json` (ignored build evidence).

## Behavioral findings addressed

- Recurring player message poll entered payload without checking ENP2. It now
  enters a28-byte guard in the existing settings patch at0x03083084, preserving
  r0 and falling back to the stock query when the header is absent. Tests execute
  the actual call site with present and missing payloads.
- A UI request could publish after a session reset and target the next book.
  Snapshots now include a session generation, incremented on cancel/reset. The
  player rejects mismatches; a regression simulates publication after reset.
  Both sides have compiler barriers for the shared snapshot fields.
- Native favorite fallback changed r0. This was already corrected while Fable
  ran; the guard uses r2 and tests assert the native zero argument.
- docs/playlists.md retained old layout figures. Updated to the audited layout.

Two low-priority maintainability suggestions remain: consolidate the loader
header bias/chapter capacity constants, and move aggregate session clearing out
of resume.c. They do not establish a hardware safety defect by themselves.

This is a reviewed milestone with tested fixes, not an independent re-review
pass or hardware validation. Book menu/jump/delete UI and save feedback remain
unfinished. No firmware was installed during this milestone.
