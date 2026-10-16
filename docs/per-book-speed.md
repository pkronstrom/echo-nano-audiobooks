# Per-book playback speed

The startup/speed candidate adds per-book speed persistence to the existing
BOOK.RSM companion on the SD card. No additional file is needed. A valid
prepared resume companion remains required; the firmware does not create it.

Normal progress saving or stopping a book saves its selected speed with its
chapter/time. Reopening that book, including after restart, restores that speed.
A chapter that cannot accelerate still plays at native 1x while retaining the
book's chosen rate for supported chapters. Saving uses the launched book setting,
not a pending preference for another launch.

A different book restores its own setting; legacy/missing/invalid settings
start at 1x. Abrupt reset/power loss before a normal save can retain the older
rate, just as it can retain an older listening position.

The browser book menu reads the selected book's speed independently of the
currently playing book. Changing its MP3 speed row is pending until Continue,
chapter or bookmark playback is launched and later saved. Leaving the menu
without launching does not change the playing book or write another book's
resume data. The Now Playing Speed menu continues to use controlled restart.

## Storage compatibility

RSM word 8 (byte 32) contains `0x53504400` plus the rate in quarter-speed units 4–8.
This field is covered by the existing sector CRC. Zero, unknown tags and values
outside 4–8 default to 1x without discarding an otherwise valid position.
Saved rate restores only when the playlist physical signature and saved
chapter parent/index/cluster match. Replaced content does not inherit state.
The two-sector journal/torn-write handling remains the resume save mechanism.

## Optional 0.75x assessment

Deferred. The current DSP removes periods to accelerate audio. Both its core
and packet/source-time mapping assume output is no longer than the source
(quarters 4–8, source span at least output frames). Slower playback needs period
insertion plus revised output buffering/source accounting and a new audio test
matrix. Adding a 0.75x menu label alone would violate those guarantees. The user
made 0.75x optional when the tradeoff is substantial.

## Device checks

1. Set book A to 1.5x, stop/switch normally, and open book B: it should use its own
   speed (1x for a legacy book). Return to A: 1.5x should restore.
2. Stop normally and restart; reopen A and check speed, chapter and time.
3. Change B's speed in its browser book menu while A is playing; cancel. A should
   keep its speed. Launch B with the selection, stop it and check persistence.
4. Check an older RSM and a book without a companion: safe 1x fallback, no writes
   to a different book. Hardware validation remains pending for this candidate.

Startup fix, final memory/test/archive evidence and deployment state are recorded
in update-startup-investigation.md and the latest device-test-and-restore.md entry.
