# P4e MP3 speed acceptance

This is a controlled device-test checklist, not a hardware-validation result.
The installed20261027 live-speed build reached the menu after one user restart;
the initial startup anomaly remains unresolved. The user reports Book B speed
selection via the player menu works nicely. The20261029 small-label follow-up
remains offline. The earlier20261025 packet fix was reported crackle-free. Identify images
by archive and SHA256, not date alone; an earlier controls-only20261027 archive
has different contents. Consult the current archive manifest and
[recovery lessons](recovery-lessons-2026-10-14.md) before staging.

## Controls

Open Audiobooks → a prepared book → **MP3 speed** to set the next-launch
preference. During supported MP3 book playback, double-click the main button,
open **Speed**, and select1x,1.25x,1.5x,1.75x or2x. This requests a controlled
restart of the current chapter at its audible source position and preserves
whether playback was paused. A short interruption and native seek rounding are
expected; this is not seamless time stretching across the rate change.

The normal Now Playing view shows the effective rate. In the20261029 follow-up,
it uses small bottom-row digits on the artist row immediately left of SD; the
title is full width and the bottom controls retain their existing layout. The preference is shared
by books and resets to1x on reboot or payload reload. Unsupported playback
remains1x. A refused switch stays in the menu without an error message; a drain
timeout or cancellation after pausing can leave playback paused. Reopen the
book if needed. Post-handoff I/O failure cannot restore an already closed decoder.

Speed processing supports native 16-bit MP3 at 8–48 kHz. Other codecs and
ordinary music keep native 1x playback. Source-time positions remain the units
used for the player clock, resume and bookmarks. At faster speed the displayed
source time should advance faster than wall time.

## First listening pass

1. Start a short MP3 book at 1x; check sound in both channels and normal controls.
2. While playing, double-click the main button → Speed →1.25x. Repeat for
   1.5x,1.75x,2x and back to1x. Check the label, continuity of the spoken passage,
   and that speech gets faster while voice pitch stays approximately unchanged.
3. At2x, navigate menus and save a bookmark. Confirm visible feedback, then
   listen for gaps, distortion, clicks or stalls; note the file and sample rate.
4. Pause, select a different rate through the player menu, and confirm it remains
   paused. Resume and check the new speed. Repeat across chapters and after a
   seek. Selecting the current effective speed should not restart playback.
   The separate book-menu preference still applies at the next book launch.
5. Save and reopen bookmarks at different speeds. Verify they return to the
   same spoken passage. Stop/reopen the book and check Continue as well.
6. Let the final chapter finish. Check that playback terminates and navigation
   still works. Test a very short MP3 too, to cover the final partial buffer.
7. Start ordinary music, then an unsupported-format book. Both should play at
   their normal speed. Return to an MP3 book and verify the preference still works.
8. Reboot and confirm MP3 speed defaults to 1x. Check persisted book positions
   independently of this intentionally temporary preference.

The algorithm and synthetic native pipeline pass offline checks, but processor
deadline margin, actual DMA timing, real-speech quality and headphone output
still require this listening test. Stock clock/power settings remain unchanged
to avoid combining performance experiments.

If playback freezes or the device reboots, record the exact action/file/speed
and stop that test. Use the documented recovery process rather than repeatedly
installing or resetting an unknown state. Never erase flash or replace the
bootloader as part of this test.

Known degraded path: a stop/resume racing an active DMA transfer can end the
current file. If this occurs, note the exact action and selected speed; do not
treat it as a passed pause/resume check. See the integration checkpoint.
