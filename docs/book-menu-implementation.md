# Audiobook menu — offline implementation, 2026-10-15

Selecting an M3U below a discovered `.audiobook` root opens a two-row book menu:
Continue (saved chapter/time), Chapters, Bookmarks. Music and meditation roots
retain ordinary selection. Chapters are currently numbered, not titled.
Bookmarks display chapter and time, then offer Play bookmark or Delete bookmark.
Deletion requires confirmation, with Cancel selected initially.

Continue re-reads automatic resume at launch rather than using potentially stale
preview progress. Explicit chapter/bookmark choices carry the preview signature;
changed playlists and invalid chapters fail before activation. Missing selected
media fails rather than silently playing the first chapter. The existing native
startup seek consumes the requested milliseconds (including its rounding).

## Ownership

Preview has its own compact256-entry queue, parser workspace, journal sector and
bookmark snapshot. It never calls `book_load` or `bookmarks_open` or replaces the
active queue. Native file reads/writes/close use short filesystem locks; preview
never masks decoder filesystem IRQs for a whole playlist scan. Bookmark append
and deletion share a nonblocking atomic transaction guard across read/modify/
write. Deletion rejects a newer journal generation instead of applying a stale
row index. Existing two-sector CRC journal remains unchanged.

UI deletion uses private scratch, unlike the player-owned bookmark API. This
supersedes the earlier plan to route every preview operation through the player
service: the browser also needs to work when no player is running. Shared player
scratch remains exclusive to existing parser/resume/bookmark calls.

## Native launch and return

Synthetic rows preserve512 bytes browser state,32 bytes control state, and two
624-byte real nodes. Launch restores those real nodes and calls the existing
native handler0x0307acb6. The override is armed before that call and consumed by
playlist selection, then applied inside playback_prepare. Do not call the
assembly launch bridge from C; it assumes the native handler's stack frame.

Back from playback reaches navigation_browser_init, which validates the book
before restoring its menu. If media is unavailable, fresh native browser state
is preserved. A fresh browser initialization clears a non-returning menu.
Synthetic rows consume native context/delete routes. Initial unavailable-book
errors visibly exit to the main menu rather than restoring stale identities.

## Review and verification

Independent implementation reviews identified concurrent bookmark writers,
asymmetric filesystem locking, stale browser restoration, and overly broad M3U
menu interception. These were addressed before the full219-test regression run
(70.089s). A subsequent real menu-to-native Chapter2 launch test passed as well.
Fable reviewed this milestone and returned **warn**, with maintainability/docs
findings rather than a new behavioral fault. Shared journal constants/validators,
physical queue signature, and selected-M3U detection were consolidated; header
ownership wording and the per-case failure assertion were corrected. Local report:
`builds/sd-audiobook-test/fable-book-menu-review.json`. The duplicated latest-slot
loops and synthetic-page geometry remain small cleanup opportunities; no clean
independent re-review is claimed. Neither review is hardware validation.

Current payload:15356 bytes code,16452 bytes BSS,24496 bytes RAM remaining inside
the audited56304-byte region; flash staging has17412 bytes free. No installation.

Remaining: actual chapter titles, save feedback, natural physical folder sorting,
pitch-preserving speed feasibility, direct-file startup profiling, and controlled
hardware acceptance. Existing prepared SD books need BMK companions added by the
preparation tool before bookmarks can be saved; missing companions fail closed.

## Final offline checkpoint

After review cleanup, all222 tests passed in68.795s. Custom and stock-recovery
image CRCs and copied headers passed. Archived pair and evidence:
`builds/phase4c-book-menu-20261015/manifest.json`.
Custom date20261019, SHA256
`f6be6580d9705a23874d7abb09abe5fdc4d70aaa74bcf0469b584039c630bd4c`.
Recovery date20261020, SHA256
`04581ba6c5375c695478418c9a0b55fa2afcee185b545a1e93e3b8232e942892`.
This archived milestone has not been installed. Preserve the previously tested
loader-fix image and recovery evidence for controlled hardware acceptance.
