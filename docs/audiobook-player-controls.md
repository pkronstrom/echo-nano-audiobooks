# Audiobook player controls

The 20261108 candidate combines the sorted-folder playback fix with audiobook
seeking and a Bookmarks entry in the player double-click menu. Hardware
acceptance is pending; host tests and review do not establish boot safety.

## Controls

- Audiobook Previous/Next: seek backward/forward ten seconds. Holding repeats.
  Seeking clamps within the current chapter, avoiding the native manual
  chapter restart/skip paths. Normal end-of-chapter advancement remains.
- Double-Previous: existing bookmark shortcut, unchanged.
- Double-click main: existing sound controls, Speed when supported, and
  Bookmarks for audiobook sessions even when the codec has no speed support.
- Bookmarks: Add bookmark first, followed by saved chapter/time entries. Select
  an entry to jump there. More than twenty marks use pages of twenty, up to
  the existing sixty-mark limit. Native Back returns through the menu.
- Chapters remain available through the book menu. Ordinary Music and sorted
  folder playback retain their native directional/favorite controls.

Add bookmark captures the current audible source position and queues the
existing journal writer, then returns to Now Playing for saved/failed feedback.
The prepared BMK companion is still required; this change does not create files.
A missing or unusable companion appears empty and adding reports failure.

## Implementation and review findings

Native input decoding runs before book-only interception, retaining orientation
mapping and the double-Previous route. Native forward seek also skipped chapters
at its boundary, so simply remapping short clicks to held events was insufficient.
Book seeks now pause, wait for owned DMA to drain, use native absolute seek, and
restore the original pause state. Targets use audible source time and stop at
zero or one second before duration (zero for clips no longer than one second).
Native seek rounding still applies. The displayed/session source time is updated
explicitly: the native seek dispatcher alone did not update it while paused.

Bookmark jumps reuse the pause/drain/relaunch path, preserving actual speed,
desired speed, and pause state. They revalidate playlist, bookmark snapshot and
physical chapter identity before and after draining. Queue references omit file
size; an erroneous comparison against their zero size was removed after a
nonempty-file regression reproduced refusal. The native raw-entry/cluster check
remains. No UI bookmark read uses the player-owned journal scratch.

Player uninit cancels an uncommitted operation on every window exit. Committed
relaunches survive cleanup. Timeout or cancellation after pause can leave the
book paused; no pending seek is performed later. Seek refusal is consumed so it
cannot fall through to chapter skipping. A late decoder/I/O failure cannot
resurrect a decoder already closed during a bookmark jump.

## Memory and performance

No memory boundary, bootloader, DSP buffer or clock was changed. Savings include
512B from temporary navigation path reuse, 480B from nonoverlapping preview
parser/bookmark storage, and 128B from bounded sixteen-bit root entry indexes.
The scan already has a 65,536-entry work bound; assignment also checks overflow.
Bounded UI flags were narrowed; generation and synchronization tokens were not.
Keeping two cold-path helpers out of line reduces duplicated code by176B.

Final resident code is25,672B and BSS30,512B, total56,184B:120B remain before the
existing0x0309fff0 boundary. Browser helper remains3,336B code/10,408B BSS.
Compiler experiments with LTO grew code and were rejected. Audio-speed DSP is
unchanged. Opening Bookmarks still reparses the playlist to validate the current
book; this iteration does not claim lower menu-opening latency.

## Device acceptance checklist

1. Confirm normal boot, then open an MP3 audiobook.
2. Tap Previous/Next: move about ten seconds, keeping the chapter number.
   Hold each direction and check the start/end boundaries.
3. Pause at about12s; press Next twice: approximately22s then32s. Add a bookmark
   and check its time. Repeat while playing at an accelerated rate.
4. Double-click main → Bookmarks → Add bookmark. Check visible confirmation.
   Reopen Bookmarks and select a saved chapter/time; verify the destination.
5. Test bookmarks in an M4A book, where Speed is absent, and the existing shortcut.
6. Check Back/Home/settings transitions and normal music track skipping.
7. Check the combined sorting fix: Meditation CD1 starts1/N, then CD2 follows.

Sorted folder queues remain RAM-only and limited to256 audio entries. Reselect a
folder track after restart to rebuild natural playback order. See the latest
entry in device-test-and-restore.md for archive and full-suite results.
