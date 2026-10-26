# Full-width native settings lists

The user requested removing the square logo in the double-click player settings
menu and reclaiming its text space. This change covers the shared module32 list
renderer, including Music Settings, Speed and ordinary native submenus. It does
not change slider/value-screen rendering or menu actions.

## Native geometry and local ownership

Full list paint `0x030795ce` clears the framebuffer, then its logo-only block
`0x03079738..0x03079754` chooses image129 or130 (both30x32), drawn by the call
at9750. It does not use resource126. A checked branch at9738 skips that entire
block. The now-unreachable24 bytes at973c..9754 hold the new background helper.
The old conditional branches into9742/974a were internal to this removed block;
there is no remaining fallthrough into the helper.

The helper sets x=0, calls native image draw `0x030521d4`, restores image/y/r3,
then tail-calls the same draw at x32. Its16-byte save frame preserves8-byte
alignment and does not depend on the playback payload or its magic/header.
The full selected-row call975c and incremental selected/old calls9896/98a2 use
this helper. Resources17/127 are92x16, so the two draws cover columns0..123
without crossing the scrollbar at124.

Text left changes35->3 at9768 (full) and98ac (incremental). Native right123 and
special right110 for value-bearing rows remain untouched. The native full
renderer can use110 for both visible rows, whereas incremental repaint uses123
for the previous row; this existing behavior is explicitly retained.

All seven new patches live in9738..98ae. Native action handlers, sliders,
value screens and the existing guarded Speed record/text/action hooks remain
unchanged. Payload code and BSS do not grow. The layout validator pins exact
stock bytes for every new patch, in addition to the existing stock hash and
per-hook validation. No global image resource is modified.

## Verification

The new test first failed against native geometry (logo129 present, backgrounds
at31, text at35). Six isolated ARM tests then passed: both logo variants removed;
full/incremental Music Settings with absent payload retains six native controls;
Speed submenu and seventh root entry survive; right-edge/value spacing and
scrollbar remain native; helper tolerates draw-call argument clobbers; unrelated
slider/value instruction ranges remain byte-identical to the Speed baseline.
A seventh test compares all compiled layout hooks against the combined image
and must pass after the parent's coordinated rebuild. Graphics are captured at
the native drawing API boundary, not a hardware screenshot.

No firmware/device staging, device operations or commit was performed by this
implementation task. Parent owns combined build, broader review and archive.


## Offline full-width settings candidate — 2026-10-15

20261031 removes both squarelogo variants from module32 settings lists, including
the player double-click menu and Speed. Text startsx3; selection backgrounds
cover0..123; scrollbar124 and value/slider screens stay intact. Local24B helper
reuses the bypassed logo block; playback payload unchanged24112text/32176BSS.
401 tests passed in263.866s. Scoped independent review found no blockers.
Archive: builds/phase4f-controls-20261015/settings-wide-reviewed/manifest.json.
Custom SHA256: c612cb6fe3d7e33d2b87e7f56bb39baa8b7ff067cd1f1158272bdcc5f27c364d
Recovery20261101 SHA256: bca80f077121d66ca106f459a458076fbf8582f6ee52af18ea6220a907aa2c4e
No device staging performed for this candidate.20261029 was staged previously;
its boot acceptance has not been explicitly confirmed. Initial20261027 startup
anomaly remains unresolved, though userrestart reachedmenu andliveSpeed worked.

Folder sorting is NOT implemented: the native browser still follows physical
directory order. Only generatedM3U playlists use natural sorting. User confirms
Meditation set CD2-3 appearsbeforeCD1-1. See docs/folder-sorting-investigation.md.
