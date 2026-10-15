# Book usability follow-up — 15 October 2026

This checkpoint is offline. The installed, partially accepted image remains
20261019 (f6be6580…bd4c). These changes have not been copied to the Nano.

## Implemented behavior

- Prepared folders under a marked audiobook root open the book menu directly
  when they contain BOOK.M3U. Other folders retain native browsing, and arbitrary
  selected M3Us remain supported. Back restores the selected parent folder.
  Invalid books can return to their parent; replaced folders are revalidated
  before old native cursor records can be restored.
- Once a book has successfully prepared through the book menu, Audiobooks opens
  a two-row landing menu: Continue last book, then Browse books. Continue resumes
  directly; Back from playback opens the book menu, and Back again returns to
  the landing menu. Browse books opens the existing root/chooser listing.
  Changed playlist contents or missing/replaced identities fail closed.
- Double Previous queues a bookmark. The UI shows Bookmark saved only after a
  successful journal write, or Bookmark failed on a rejected position/write.
  The custom popup lasts1.5seconds and blocks ordinary keys while displayed.
  It waits behind an existing dialog and is canceled on book/session changes.
  Its timeout redraws the player without native error-recovery message227.
- Music Playback can restore a previous ordinary File Browser music context
  (native mode99), including track/time/order. It stops and saves the audiobook
  through native callbacks before starting the restored music queue.

## Material limits and unfinished work

Music resume is **partial**: native library modes8/9/10 open Music Library rather
than restoring a prior track. Those modes use different library/cache state;
the tested raw-file reconstruction is not valid for them. See
[music investigation](music-resume-investigation.md).

Both the saved Music context and Continue last book selection live in payload
RAM. Restart or library refresh clears them. Per-book BOOK.RSM and BOOK.BMK
remain durable on SD. A durable last-selected-book feature still needs a
separate, preallocated journal and preparation migration; it is not implemented.

Only Bhagavad received its missing BMK on the previous SD connection. The other
four prepared test books need the preparation tool rerun before testing saves.
No SD card was modified during this offline checkpoint.

Physical rendering, popup input behavior, boot and all new navigation need
on-device acceptance. Raw identities/content cannot distinguish replacement
media with coincidentally identical metadata. No bootloader changes or raw-flash
operations are part of these changes.

## Review and validation

Direct-folder, Music and feedback paths received independent spec/correctness
reviews. Fixed findings included invalid-book Back, stale saved browser records,
Music file metadata reuse, and the Music menu reopening UI without stopping the
book service. Last-book path and signature now come from one locked snapshot.

Tests execute native browser launch, Music queue reconstruction, actual native
stop/save callbacks, native window creation/destruction and dispatcher teardown
before overlay loading. Device I/O and text rasterization remain substituted.
Final suite: 271 passed in 87.431s. Build text18640B/BSS17676B leaves19988B
within the audited payload RAM. Both package CRCs and duplicate headers pass.
Archive: builds/phase4d-usability-20261015/review-fixed/, custom20261021/recovery20261022.
Fable returned warnings. Its JSON lacked the final closing brace; the raw
envelope/text and repaired JSON are retained. Reproduced and fixed exFAT
root detection using the traversal cursor instead of the stable cluster, and
an interrupted Music restore leaking its pending state into a new selection.
The About label now says P4d; browser category reads use the same width.
Low-priority key-code/snapshot duplication and512-byte scratch cleanup remain
deferred. Independent source re-review found no remaining must-fix issue in
those corrections. The final 271-test post-review results supersede the earlier 269-test checkpoint. No new device acceptance or installation is implied.

## Next device acceptance

1. Prepare companions for all test books while preserving existing M3U/RSM/BMK.
2. Stage only the reviewed later-dated candidate after identifying the connected
   Nano and checking the archived recovery pair. Do not reuse mutable output.
3. Check boot, menus and ordinary Music first. Select a music file deliberately,
   play to a known position, then open a prepared book folder.
4. Check direct book menu, Continue, Back and last-book landing Continue/Browse.
5. Save a bookmark and observe the confirmation; verify actual stored mark.
   Test another chapter, deletion and normal restart persistence separately.
6. Switch to Music and verify the saved track/time and preserved book progress.
   Check Library fallback separately; do not report it as library resume.
7. Check popup expiry leaves playback/view intact and ordinary navigation works.
