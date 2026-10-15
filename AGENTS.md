# Device work: read this first

Before any Nano device operation, firmware build proposed for installation, or
release, read [the recovery lessons](docs/recovery-lessons-2026-10-14.md) and
[the device incident record](docs/device-test-and-restore.md).

- P4a (`01c28d12…94b494`) boot-looped on hardware. Do not reflash or release
  that candidate. Passing host tests and review did not establish boot safety.
- The menu-hook-bypass diagnostic reached the menu but froze after Shuffle.
  It is not a validated workaround. See `docs/p4a-bootloop-investigation.md`.
- On 2026-10-14, stock application recovery through USB Loader succeeded and
  the user confirmed the normal menu returned. Preserve this working state.
- Long Power is a forced restart, not a guaranteed power-off. A black screen
  does not prove recovery; verify USB enumeration.
- Never equate the 476 MiB logical backup with a bootloader/full-chip backup.
  Never erase flash, download a loader, or bulk-restore that file as a shortcut.
- Existing release manifests are historical build evidence. Consult current
  incident status before treating any image as a device-test candidate.
- Re-identify the USB device and mounted disk on every connection. Disk numbers
  change. Preserve local recovery evidence in ignored `builds/device-check/`;
  do not commit firmware, device dumps, or private filesystem contents.

Current device follow-up: the sector-rounded loader fix (20261017, SHA0a6fffbe…)
boots, Shuffle starts playback and File Browser remains responsive. User reports
M3U resume works; audio output and broader acceptance remain incomplete. Current
usability work and constraints are in docs/audiobook-usability-investigation.md.
The 20261019 offline browser-return build is not installed or hardware-validated.
Do not confuse either with the original failed P4a or menu-bypass diagnostic.

Current offline milestone (2026-10-15): Continue/Chapters/Bookmarks menu,
chapter/bookmark jumps and confirmed deletion are implemented. Read
`docs/book-menu-implementation.md` for ownership, review findings and limitations.
The final222-test run passed. Archived candidate/recovery pair and hashes are
in builds/phase4c-book-menu-20261015/manifest.json. No new device validation or automatic installation is authorized.

Playback starts at0x03092400 and uses refresh-only staging; read
`docs/playback-memory-layout.md` before changing loader/layout. The upper reboot
boundary remains0x0309fff0. The old36-byte RAM limit and statements that the
bookmark menu is absent describe earlier milestones, not this working tree.

Both favorite routes have a guarded resident bridge. Gestures queue chapter/time
and player polling saves BMK. Preview/deletion have separate scratch and a shared
nonblocking bookmark writer guard. Music retains native favorites. Fable's first
review returned warnings with tested fixes; the current UI review also returned warnings; addressed and deferred items are
recorded in docs/book-menu-implementation.md.
Do not report emulator passing as hardware safety or a clean independent review.

Latest hardware feedback (2026-10-15): book-menu candidate f6be6580…bd4c booted;
Continue and chapter2 resume were observed. Bookmark gesture has no visible
result, and Music Playback reopens the book. These are open acceptance issues,
not passing checks. See device-test-and-restore.md. SD inspection subsequently confirmed missing BOOK.BMK for Bhagavad; it was
created and verified while preserving M3U/RSM. User subsequently confirmed
bookmark saving works on hardware, but the shortcut has no visible feedback.
See bookmark-investigation-20261015 evidence and the incident record.


Latest offline source checkpoint: see docs/book-usability-followup.md. Adds
direct BOOK.M3U folder entry, a RAM-lifetime Continue last book landing, visible
bookmark results, and partial native mode99 Music resume. Modes8/9/10 fall back
to Library; do not claim universal/durable Music resume. New candidate date
20261021/recovery20261022 is uninstalled. Installed hardware remains20261019.

Final offline P4d checkpoint: 271 tests passed in 87.431s after Fable fixes.
Use builds/phase4d-usability-20261015/review-fixed/manifest.json; the parent
archive is superseded. About says P4d. No device installation performed.

Playback-speed investigation (2026-10-15): experiments/audiobook_speed/ is a
host-only bounded PCM prototype, NOT linked into firmware. Seven stock PCM ARM
checks pass; ASan/UBSan prototype matrix passes. Standalone linked core+state
13,776B, excluding native adapter/staging/stack. See
docs/stock-pcm-speed-investigation.md and docs/speed-dsp-feasibility.md. Native
buffer ownership, EOF/source-time adapter and device CPU/audio acceptance remain
open. User accepts approximate speed presets and prioritizes performance. Do not
claim a Speed menu or on-device speed support; do not import unchecked Sonic lite
EOF logic. Existing P4d image/recovery archives are unchanged.

Superseding speed checkpoint: user requested PAUSE on 2026-10-15. Read
`docs/speed-integration-checkpoint.md` before continuing. Speed core/menu/native
adapter are now in source, but integration review and full verification remain
unfinished. No speed build is device-ready. The intermediate 20261023 image was
quarantined out of the normal output path under builds/research/speed/paused-20261015/.
Do not install it. Installed Nano and archived P4d/recovery files are unchanged.

Resumed P4e checkpoint (supersedes the pause above): speed adapter/menu are linked.
The first Fable review rejected the baseline; lifecycle, unsupported-codec and
slot-reuse fixes followed. Current paired build passes332 tests plus the core
sanitizer/pitch matrix.256-frame output and1536-frame input storage use53,944B
(text22,360/BSS31,584), with2,360B remaining. Fable follow-up gives limited offline approval;
see builds/phase4e-speed-20261015/reviewed/manifest.json. Hardware acceptance
is pending, and no installation was performed. Rare active-DMA overlap on
stop/resume deliberately ends the file; read the checkpoint limitations. Read docs/speed-integration-checkpoint.md for
current review outcome before using any image. No device writes occurred.

Final P4e launch-rate correction: /revx completed3 of4 reviewers (Sonnet quota
unavailable), finding one confirmed medium preference-latching mismatch. Fixed
by capturing speed only after validated pending playlist preparation; ordinary
seek/resume/re-entry/automatic chapters preserve the launched rate.12 new
subcases failed before the fix;333 full tests now pass in119.130s. Independent
scoped review approved the correction. Use
`builds/phase4e-speed-20261015/review-fixed/manifest.json`; older `reviewed/` is
superseded. Payload22,384text+31,584BSS=53,968B;2,336B headroom. Same uninstalled
dates20261023/24. No device operations; hardware acceptance is still pending.

Device staging update: user authorized the controlled P4e test and connected
the Nano. Corrected image e40a2e82…1210be was copied to freshly identified
internal storage, byte-for-byte verified, then internal and SD volumes safely
ejected. Evidence:builds/device-check/p4e-stage-20261015-184155/. Installation
and normal boot remain unconfirmed; await user report. Read latest incident
entry before further device operations. No raw flash or bootloader operations.

Latest hardware result supersedes pending boot: user confirmed corrected P4e
reached normal menu.1x audio is clean, but1.5x/2x have considerable crackle.
Accelerated audio acceptance failed; do not release as working speed support.
Current investigation: short variable DSP packets (256 is max), possible
underrun and native EQ's multiple-of64 processing gate. EQ-off result pending.
Do not blindly increase clocks or stage another firmware without diagnosis.

EQ-off follow-up: accelerated audio still crackles with EQ off. Packet-size
coalescing fix now passes336 tests and scoped independent review. Audio-only
uninstalled checkpoint is builds/phase4e-speed-20261015/packet-fixed/manifest.json
(date20261025/recovery20261026). This is not hardware audio acceptance.
Main-menu Audiobooks/Meditations redundant scan optimization is in progress.

## Packet/menu candidate staged — 2026-10-15

Combined candidate passed338 tests in129.282s and scoped independent reviews.
Archive: builds/phase4e-speed-20261015/packet-menu-fixed/manifest.json.
Payload22360text+31592BSS=53952B,2352B headroom. Date20261025, recovery20261026.
User connected Nano for test. Fresh normal071b:3203 identification matched
internal disk7 (262144000B) and SD disk8 on the same USB device. These disk
numbers are historical, not reusable assumptions. Copied only internal update
image and verified entire readback SHA256:
e65934c49cefcef4110b50d3620e05594e727ac197b3ad70e304603db88f5add.
Both volumes ejected. No SD changes or raw/bootloader operations. Evidence:
builds/device-check/p4e-stage-20261015-191250/. Boot, accelerated audio quality
and Audiobooks/Meditations opening timing await user confirmation. Installed
20261023 remains last confirmed booted image.

Latest device feedback:20261025 packet/menu candidate boots and user reports
crackle fixed. Audiobooks entry ~2s, Meditations ~3s remain but acceptable to
user. Bookmark gesture on Ichigo briefly blackens display; text visibility
and save result need clarification (feedback painter replaces whole screen).
New requested UX work: modestly shorter Back/Home holds, remove giant side
artwork from Music Playback and Media Library for more text. Investigate exact
screen and native thresholds; no new image staged for this work.

## Offline controls checkpoint — 2026-10-15

Center-only Back threshold20→15 native polls; Home76→55 polls. Other buttons'
FSM sequences remain unchanged. Media Library and indexed music lists now
reclaim the large left panel, preserve small row glyphs where applicable, and
keep full/update selection backgrounds clear of the x124 scrollbar.

357 tests passed in148.977s; scoped independent reviews found no blockers.
Archive builds/phase4f-controls-20261015/reviewed/manifest.json, date20261027,
recovery20261028, About stillP4e. Custom SHA256:
05103a28bc48fdc132a9ad6f508867f8a0be34f4073a1c0e26db491be2142dba.
Payload unchanged22360text/31592BSS; changes reside in audited native overlay
caves/resident diagnostic space. This candidate is uninstalled. Live-speed
UI/backend and bookmark raster fix are subsequent work, not included.


## Offline live-speed candidate — 2026-10-15

Combined20261027 candidate adds Speed to the native player double-click menu,
restarts the same MP3 book at audible source position while preserving pause
state, and displays actual rate on normal Now Playing. Includes shorter
Back/Home holds, full-width library/indexed lists and the native raster-mode
fix for invisible bookmark confirmation.

391 tests passed in198.668s. Scoped independent re-review found no remaining
concrete blocker after runtime-bypass and physical chapter-size fixes. This is
not a new Fable/revx review or hardware acceptance. Payload24096text+32176BSS
leaves32B static headroom; memory boundaries unchanged.

Archive: builds/phase4f-controls-20261015/live-reviewed/manifest.json.
Custom SHA256: 8afede206bd54dd02642cf1ca7510039b587d40ee3ec58fc3794dc7f9a6b716b
Recovery20261028 SHA256: 681581cf55ed693583e27da6481dda78b0044710d73564dc32ae444ee4f2e722
About remainsP4e. Earlier controls-only20261027 archive is a different build.

No device writes performed. Installed20261025 remains the confirmed booting,
crackle-fixed baseline. Next test: MP3 book → double-click main → Speed; verify
rate label, position, pause preservation, audio and bookmark feedback. Refusal
has no error message; timeout/cancel after pause may leave playback paused.
Late I/O failure cannot restore a closed decoder. Native seek rounding applies.
See docs/speed-device-test.md for the checklist.


## Live-speed candidate staged — 2026-10-15

User connected USB to stage the reviewed20261027 live-speed build. Fresh USB
071b:3203 identification linked internal disk7 (262144000B) and SD disk8 to
one Nano. No existing update image was present in either root. Archived custom
and recovery dates, hashes, duplicate headers and CRCs verified. Copied only
internal NANOV170.IMG with exclusive creation, flushed/synced and compared the
complete readback byte-for-byte. SHA256:
8afede206bd54dd02642cf1ca7510039b587d40ee3ec58fc3794dc7f9a6b716b.
Both volumes safely ejected. No SD content changes or raw/bootloader operations.
Evidence: builds/device-check/live-stage-20261015-201944/result.json.
Installation, boot and live-speed acceptance await user confirmation; installed
20261025 remains the last confirmed booted version. Disk numbers are historical.


## Hardware follow-up — live-speed20261027

User initially suspected boot loop, then restarted once and reached the menu.
Startup anomaly remains unresolved; do not call repeated cold boot validated.
User confirms Ichigo Speed via double-click works nicely. The Way to Wealth
lacks Speed as expected: preparation manifest records M4B remuxed to M4A, not
MP3. No conversion performed in this follow-up.
User requested speed label on middle row immediately left of SD, using small
bottom-row digits, preserving title and bottom controls. Offline change underway.


## Offline small speed label — 2026-10-15

20261029 moves actual speed beside SD on the artist row, using native bottom-row
8px digit shapes. Full title width and all bottom controls are preserved. Artist
exclusive rightedge86 meets labelclear86..107 without stale boundary pixels.
394 tests passed in228.285s; scoped independent re-review approved. Payload
24112text+32176BSS leaves16B static margin; boundaries unchanged.
Archive: builds/phase4f-controls-20261015/small-label-reviewed/manifest.json.
Custom SHA256: b5630159bccf08f26632d8000da68a130f60c65bf56e0d29bd96e4d02abb48a3
Recovery20261030 SHA256: 21d22f3b7b7e54920826c487c51f5d6e37ab2cc4c298cf256dd426e9a2d21e32
No device staging performed. Installed20261027 reached menu after userrestart
and Ichigo live speed works; initial startup anomaly remains unresolved.


## Small-label candidate staged — 2026-10-15

User connected Nano for20261029 update. Fresh071b:3203 USB identification
matched internal disk7(262144000B) and SD disk8 on same device. Archived custom
and recovery hashes, dates, headers and CRCs verified. No update image existed
in either root. Exclusive internal copy, flush/sync and full byte-for-byte
readback succeeded, SHA256 b5630159bccf08f26632d8000da68a130f60c65bf56e0d29bd96e4d02abb48a3.
Both volumes ejected. Evidence: builds/device-check/small-label-stage-20261015-205607/.
No SD content changes or raw/bootloader operations. Installation and boot await
user confirmation;20261027 remains last confirmed booted. Disk numbers historical.
