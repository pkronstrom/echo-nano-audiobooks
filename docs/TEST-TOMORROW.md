# Next Nano test — current status, 2026-10-15

**Do not install an old P3a/P4a artifact from historical notes.** The original
P4a boot-looped; its menu-bypass diagnostic later froze. The20261017 loader-fix
image boots and received user menu/Shuffle/M3U-resume checks. The installed20261019 book-menu build f6be6580…bd4c boots; Continue and
chapter2 resume work, and Bhagavad bookmark saving works after adding BOOK.BMK.
Music still reopens the book and save feedback is absent. Follow-up changes are
offline until reviewed; do not confuse mutable build output with that candidate.
Read [recovery lessons](recovery-lessons-2026-10-14.md) and
[incident record](device-test-and-restore.md) before any device operation.

## Offline menu milestone

Implemented: wide browser, playlist visibility on Back, book Continue/Chapters/
Bookmarks menu, explicit chapter/time launch, manual bookmark gesture and
confirmed deletion. Details and verification:
[book menu implementation](book-menu-implementation.md).

Pending: broader audible playback, bookmark jump/delete/restart checks, and
acceptance of subsequent changes. Fable returned
maintainability warnings; implemented fixes and remaining cleanup are recorded
in the implementation note. The archived20261019 candidate was installed; subsequent source changes have not.
Generated files under `out/audiobook` are mutable build output, not a published
release or a previously device-accepted candidate.

## Prepare a book

Books on SD should have an M3U and separate1024-byte RSM/BMK companions beside it.
The enclosing audiobook root must have its `.audiobook` marker. Run the preparation
tool in preview mode first; `--write` preserves existing valid progress files.
Existing prepared books need rerunning to add BMK. See [audiobooks](audiobooks.md).

## Controlled acceptance after review and staging

1. Confirm exact candidate/recovery hashes and dates; identify current USB device
   and mounted storage, inspect leftover updates, and preserve recovery evidence.
2. First boot without SD. Check normal menus and Shuffle/File Browser before
   proceeding. A host test pass is not boot acceptance.
3. Insert prepared SD and open an audiobook M3U. Check Continue, numbered Chapters,
   Bookmarks, Back to the book listing and Back from playback to the book menu.
4. Select Chapter2, confirm correct audio and chapter counter. Play long enough
   to establish a nonzero time. Double Previous to add a bookmark; open the list
   and verify its chapter/time. On-screen save feedback is not implemented yet.
5. Save another mark in another chapter. Play each mark and check time rounding.
   Delete one: Cancel must be selected by default; cancelling preserves it.
   Confirm deletion, reopen and check the remaining mark.
6. Browse bookB while bookA plays; check A continues, then explicitly choose B.
   Return to A with Continue and verify independent resume. Restart normally and
   verify SD bookmark persistence.
7. Check ordinary music favorites and meditation playlists retain their behavior.
   Confirm library refresh and return to playback after the overlay reload.

Record exact actions, book/format, audio behavior, approximate time and failures.
Preserve M3U/RSM/BMK and CFWLOG.TXT evidence. Never erase flash, download a loader,
or treat the476MiB logical backup as a full-chip restoration image.

Speed presets, natural folder sorting and actual chapter-title labels are not
part of this implemented menu milestone. No GitHub release has been published.


## Subsequent offline usability checkpoint

See [follow-up behavior and test steps](book-usability-followup.md). The archived
20261021 custom/20261022 recovery pair in builds/phase4d-usability-20261015/review-fixed/
is uninstalled. 271 tests pass, with explicit partial Music and RAM-lifetime
last-book limits. Do not confuse it with the installed20261019 candidate.
