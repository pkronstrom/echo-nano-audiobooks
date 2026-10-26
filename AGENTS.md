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
not passing checks. See device-test-and-restore.md. SD inspection subsequently confirmed missing BOOK.BMK for Book A; it was
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
user. Bookmark gesture on Book B briefly blackens display; text visibility
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
User confirms Book B Speed via double-click works nicely. Book D
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
and Book B live speed works; initial startup anomaly remains unresolved.


## Small-label candidate staged — 2026-10-15

User connected Nano for20261029 update. Fresh071b:3203 USB identification
matched internal disk7(262144000B) and SD disk8 on same device. Archived custom
and recovery hashes, dates, headers and CRCs verified. No update image existed
in either root. Exclusive internal copy, flush/sync and full byte-for-byte
readback succeeded, SHA256 b5630159bccf08f26632d8000da68a130f60c65bf56e0d29bd96e4d02abb48a3.
Both volumes ejected. Evidence: builds/device-check/small-label-stage-20261015-205607/.
No SD content changes or raw/bootloader operations. Installation and boot await
user confirmation;20261027 remains last confirmed booted. Disk numbers historical.


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

## Native folder sorting candidate — 2026-10-15

Candidate20261102/recovery20261103 adds natural numeric folder ordering for
native Music/Meditations/File Browser lists: directories first, then names
(CD1 before CD2 before CD10), with raw entry identity preserved for selection,
Back and reentry. Explicit M3U order stays unchanged. Native playback Next/Prev
sequencing is still physical unless a playlist supplies order.

Browser-only helper2944B plus6560B scratch uses audited overlay memory; no
persistent playback payload growth (24112text+32176BSS,16B static headroom).
Module31 code backing relocates into verified unused refresh-buffer tail;
native data/BSS and other module records are preserved. Real native loader,
FAT/exFAT iterator, selection, stale-device/read failures and reload tests pass.
Scoped independent Codex review found no remaining concrete blocker; this is
not a new Fable/revx review or hardware acceptance. First-open large-folder
latency and hardware navigation/boot acceptance remain untested.

Includes prior full-width double-click settings menu fix. Archive:
builds/phase4f-controls-20261015/folder-sort-reviewed/manifest.json.
Custom SHA256:7a9d44f5b7e2f4d889d23c740bdc6e416963a7a3d57f73c451bdb57278d40269
Recovery SHA256:3c85e8eabad617c353ddaa75d6a512ec7f4c4c1c7c1d023f6c901841cb88948e

Verification: full suite ran430 tests in267.983s;429 passed and one release
packaging check rejected the audited relocation. Standalone release validation
was corrected with a narrowly pinned exception; all9 release tests then passed
(including the failed case and a new negative-layout regression). Final12
focused ARM sorting/selection checks passed too. Firmware unchanged after the
full run. No device transfer at this archive checkpoint.

## Folder sorting candidate staged — 2026-10-15

User authorized transfer when ready. Fresh USB071b:3203 identification linked
internal disk7(262144000B) and SD disk8 to one Nano; these IDs are historical.
No update image existed in either root. Archived candidate20261102 and stock
recovery20261103 passed hash/date/duplicate-header/CRC verification. Exclusive
internal copy, flush/sync and full byte-for-byte readback succeeded:
7a9d44f5b7e2f4d889d23c740bdc6e416963a7a3d57f73c451bdb57278d40269.
Both volumes safely ejected. Evidence:
builds/device-check/folder-sort-stage-20261015-214111/result.json.
No SD content changes, raw flash or bootloader operations. Installation, boot,
Meditation set ordering, selected-file identity and Back acceptance await user test.
No commit or push for this iteration.

## Hardware regression — folder-sort20261102

User reports Enter on Meditations / Meditation set does nothing.
Reproduced offline: native exFAT alias generation includes a clock suffix,
which the new selection guard wrongly compared as persistent identity.
Do not treat20261102 folder navigation as accepted. Narrow correction ignores
only exFAT synthetic alias bytes while checking stable metadata/full name and
all device/parent/read guards. FAT unchanged. Regression failed before fix and
passes after it; changed cluster/size/name/flags still reject. Candidate20261104
with recovery20261105 is being verified; no corrected image staged yet.
See docs/folder-sort-native-audit.md.

## Verified exFAT entry correction — 2026-10-15

Corrected candidate20261104/recovery20261105 passes all433 tests in272.639s
and scoped independent review. Browser helper2952B plus6560B BSS; resident
playback unchanged. This fixes clock-dependent exFAT alias validation while
retaining stale-file rejection. Hardware acceptance remains pending.
Archive:builds/phase4f-controls-20261015/folder-entry-fixed/manifest.json.
Custom SHA256:2509f5ba98b13073eecca16abd1391f4d66c719716fa2d8b611fd2aba813df4a
Recovery SHA256:ad1a9cef80335a46c9baedda7035f9dafe5449ce973367a76577dcca952507c7
User authorized replacement transfer and requested a commit; no push.

## exFAT correction staged — 2026-10-15

Fresh USB071b:3203 identification exposed only internal disk8(262144000B),
no SD volume. Archived20261104 and recovery20261105 hashes/date/CRC/header
checks passed; no leftover update was present. Exclusive internal copy and
full readback verified2509f5ba98b13073eecca16abd1391f4d66c719716fa2d8b611fd2aba813df4a.
Internal disk8 safely ejected. Evidence:
builds/device-check/folder-entry-stage-20261015-215651/result.json.
No SD writes, raw flash or bootloader operations. Installation/boot and
the meditation set folder entry await user confirmation. DiskID historical.

## Sorted folder playback candidate — 2026-10-15

User confirms natural listing order works on20261104, but selecting CD1 showed
2/N because native playback still used physical directory order. Candidate
20261106/recovery20261107 now copies sorted audio identities into the resident
queue before browser exit. Track counters, Next/Previous and automatic advance
follow visible order; directories and M3Us are excluded from folder audio counts.
Explicit M3U order remains unchanged. Book speed/bookmarks are isolated from
ordinary folder playback; native Favorites retain physical file identity.

All451 tests passed in297.724s, including actual native browser handoff and
CD1-to-CD2 automatic advancement. Scoped independent review found no remaining
concrete blocker; this is not a new Fable/revx review or hardware acceptance.
Playback24568text+31664BSS leaves72B within existing memory boundaries; browser
3336text+10408BSS stays within audited overlay space. Preview scratch sharing
recovers512B; bootloader and memory boundaries are unchanged.

Limits:256 audio entries per folder queue; raw entry indexes below65536.
Overflow refuses playback rather than silently truncating. Cold resume does not
rebuild natural order: reselect a folder track after restart. Folder→book→Music
returns Library because the book replaced the shared queue.

Archive: builds/phase4f-controls-20261015/ordered-playback-reviewed/manifest.json.
No device transfer performed; Nano storage is not mounted. Hardware check:
Meditations → Meditation set → CD1 should show1/N; Next/Previous and track completion
must follow CD2/CD3 order. Test ordinary Music and explicit M3Us too.

## Audiobook player controls candidate — 2026-10-16

Candidate20261108/recovery20261109 includes sorted folder playback plus book-only
Previous/Next seeking (ten seconds, hold repeats, bounded within chapter) and
Bookmarks in the player double-click menu. Add bookmark is first; saved
chapter/time entries jump directly, with pages above20 marks up to60. Unsupported
speed codecs still get Bookmarks. Music/folder controls retain native behavior.

All471 tests passed in348.072s. Two scoped independent reviews found and helped
correct paused-seek source-clock updates, nonempty bookmark-target validation,
and pending-seek cancellation on player exit. Actual native seek dispatcher and
speed-seek hook are exercised; committed relaunch survives uninit. Final
rereviews found no remaining concrete blocker. This is not a new Fable/revx
review and does not establish hardware boot or audio acceptance.

Memory uses25672text+30512BSS=56184B,120B below unchanged boundary. Scratch sharing,
bounded root indexes/flags and cold-helper code reuse make the combined payload
48B smaller than20261106 despite added controls. Audio DSP is unchanged.
See docs/audiobook-player-controls.md for behavior, limitations and device checks.

Archive: builds/phase4g-player-controls-20261016/reviewed/manifest.json.
Custom SHA256:7286d161307d05072480e85a7bcd0bf241bd385c9db2febb01b0bf2ef5b6e576
Recovery SHA256:bdba2a1943c5640325d53e5094601a6b485005cb8d4942eef2e2bb0d44d5e179
CRC and duplicate-header checks passed for both. About stillP4e. No transfer,
commit or push performed. Device still needs testing of the new seek/menu
controls and the prior20261106 sorted playback queue. Do not conflate this
uninstalled candidate with user-confirmed20261104 natural folder listing.

## Player controls candidate staged — 2026-10-16

User connected Nano for update. Fresh normal071b:3203 identification matched
internal disk5(262144000B) and SD disk6 on the same device. These disk IDs are
historical. Archived candidate20261108/recovery20261109 passed hash/date/CRC/
duplicate-header checks. No leftover update existed in either root. Exclusive
internal copy, flush/sync and full byte-for-byte readback succeeded:
7286d161307d05072480e85a7bcd0bf241bd385c9db2febb01b0bf2ef5b6e576.
Both volumes safely ejected. No SD content changes, raw flash or bootloader
operations. Evidence: builds/device-check/player-controls-stage-20261016-091930/result.json.
Installation and boot await user confirmation; test book seek-only controls,
Bookmarks via double-click, and Meditation CD1 counter/order after normal boot.

## Startup cache and per-book speed candidate — 2026-10-16

User reports update-only startup looping/hanging that clears after Power/reset.
The exact latest screen behavior is unconfirmed. Reproduced retained-RAM failure:
new loader accepts an older ENP2 payload without flash reads or initialization.
Actual factory/app startup leaves that RAM intact through both vector stages.
Candidate20261110/recovery20261111 invalidates the header at pinned application
entry660ca before callbacks, forcing current-payload load and fresh BSS. The
32B resident diagnostic stub preserves entry registers/frame and reboot marker.
No bootloader or memory-boundary changes. Full update/reset/ROM retention chain
on hardware is not established; this fixes a reproduced hazard, not a confirmed
complete explanation of the observed device symptom. First-update boot test is
still required. See docs/update-startup-investigation.md.

Per-book selected speed now persists in the existing CRC-covered RSM word8.
Legacy/missing/invalid values default1x; identity mismatch resets state. Browser
preview selection is local until its book launches and is normally saved.
Normal progress saving/stop persists launched rate, including across unsupported
chapters playing native1x. No extra file; prepared RSM required. Abrupt reset
before saving can retain the older rate. Optional0.75x is deferred: the current
DSP and source-time invariants only support contraction. Audio core/buffers are
unchanged. See docs/per-book-speed.md.

All484 tests passed in375.034s. Scoped independent reviews covered startup
invalidation and initial persistence logic. Parent/worker reproduced and fixed
pending-rate leakage across ordinary/folder selections and unsupported-codec
fallback losing the book preference; final tests exercise these corrections.
An unsafe pre-decoder immediate resume save was removed. No new Fable/revx
review. Host emulation/review are not hardware boot/audio acceptance.

Resident25752text+30520BSS=56272B leaves32B below0x0309fff0. Browser3336text/
10408BSS unchanged. Reused pinned native whitelist and cold-helper code sharing;
no DSP buffer/clock or reserved-boundary increase.

Archive: builds/phase4h-startup-speed-20261016/reviewed/manifest.json.
Custom SHA256:d8e261af1f43bdb5f7e3feed9780a88d148bd3964ac8de40774da0b16d9c0e9a
Recovery SHA256:92ab37a147e549bd7fd39f352ea1509cbd4aa776136efde44ed49a9470d36318
Both pass CRC/duplicate-header checks. About stillP4e. No device transfer,
commit or push this iteration. Last staged20261108 has no explicit boot/controls
acceptance. Nano storage is not mounted. Next test must observe the first boot
after updating before manual reset, then per-book rate save/reopen/restart.

## Startup/speed candidate staged — 2026-10-16

User connected Nano to test20261110. Fresh071b:3203 identification linked internal
disk5(262144000B) and SD disk6 to one Nano; these identifiers are historical.
Archived candidate/recovery20261111 hashes, dates, duplicate headers and CRCs
verified. No leftover update existed in either root. Exclusive internal copy,
flush/sync and complete byte-for-byte readback succeeded:
d8e261af1f43bdb5f7e3feed9780a88d148bd3964ac8de40774da0b16d9c0e9a.
Both volumes safely ejected. No SD content writes, raw flash or bootloader
operations. Evidence: builds/device-check/startup-speed-stage-20261016-095039/result.json.
Installation/first-post-update boot await user observation before any manual
reset. Also pending: per-book speed save/switch/reopen/restart acceptance.

## Offline named Continue row — 2026-10-16

Candidate20261112/recovery20261113 changes Audiobooks landing to
`Continue <book name>`; genericBOOK.M3U uses the immediate parent folder.
Unicode/case are preserved, with bounded UTF-16 truncation. Cached path formatting
adds no disk reads; current-session last-book lifetime is unchanged.

All488 tests passed in384.249s, plus34 final focused checks. Parent scoped review
checked label bounds, unchanged identity validation, and parser/snapshot lifetime.
No new independent/Fable/revx review or hardware acceptance. Preview saved journal
metadata shares the inactive parser workspace, excluding its busy word; failed
scans clear metadata before returning. Four checked last-book identity words and
shared label/cold-helper code retain the existing memory boundary.

Resident25864text+30440BSS=56304B reaches exactly0x0309fff0 (zero static margin);
reboot marker, stack placement, loader and DSP buffers are unchanged. Browser
3336text/10408BSS unchanged. Future additions must free static space first.
Archive: builds/phase4i-named-continue-20261016/reviewed/manifest.json.
Custom SHA256:1e9065a050adf21bd5c419550de1e5ee807cc9dbc39c6bfbbc8912ccd7d70720
Recovery SHA256:145613bd8c21dbe9fc1aa13f932144de35e4b1091dd686355d21ef2061fc43be
No device staging, commit or push for this change. Latest staged20261110; the user
observed the last-book landing, but first-post-update boot sequence and durable
per-book rate acceptance remain unconfirmed. See docs/named-continue-label.md.

## Post-RC automatic-preparation research — 2026-10-16

Local annotated tag `phase4i-release-candidate` points to bac9473. No push or
publication. Subsequent research is separate; see
`docs/automatic-book-preparation-investigation.md` and the reusable
`experiments/native_file_creation/probe_stock_create.py`. All 11 offline native
wrapper/duplicate probes passed. Stock file creation exists, but its exFAT path
does not propagate insertion failure and can create duplicate names. Do not
call it blindly or claim safe generic UTF-16 path creation. Directory/allocator
write/close persistence and interrupted creation still need sector-level tests.
No auto-creation is linked, no new firmware built, no device operations.
Resident zero static margin remains; cold browser helper placement is only a
candidate. Recommended next scope: missing BOOK companions first, then guarded
M3U generation; preserve all existing files and explicit playlist order.

## Post-RC automatic preparation — final offline checkpoint, 2026-10-16

Supersedes the research-only status above. The cold browser now creates missing
BOOK.RSM/BMK and naturally sorted BOOK.M3U for a simple directly contained book,
inside a live marked Audiobooks tree. Existing BOOK/custom M3Us and state are
preserved. Larger directories bypass generation and retain native entry. Music,
Meditations, collection roots and nested-disc grouping are excluded. Read
docs/automatic-book-preparation.md BEFORE changing or testing the adapter.

All578 tests passed in498.928s. Independent scoped storage/UI and fresh final
review give limited offline approval after tested fixes, including foreign dirty
cache/FCB ownership, malformed parents/bitmap geometry, stale medium/parent,
copied overlay flags, invalid bookmarks, playlist limits, multi-cluster bypass,
and native parent selection remaining valid after preparation no-ops. This is
not a new Fable/revx review or hardware acceptance. Real stock module+byte-reader
loading in both slots and byte-identical isolated payload/image rebuilds pass.

Resident25864text/30440BSS remains unchanged at3092400..309fff0, zero static
margin; queue ABI and bootloader unchanged. Resident flash reservation shrinks
to26112B (exact sector-rounded read),36200..3c800. Browser backing3c800..42348
uses checked-zero refresh sort-A tail plus first3KiB sort B. Browser13960text/
5320BSS ends030803c8,168B below unchanged decoder boundary03080470. Rows/launch/
preparation share scratch;64-key sort windows stream without truncation.

Storage is deliberately restricted: one FAT,512B sectors, single-cluster book
directory, first contiguous free run within one allocation sector, bounded4096
allocation-sector search. exFAT requires actual root81 bitmap ID0/cluster2,
contiguous bitmap<=4096sectors and one-cluster root; new three-entry sets must
fit one directory sector. Unsupported shapes use host preparation. Unknown,
partial or invalid companions/TMP are preserved; no automatic cleanup/retry.
Interrupted initial creation can leave owned empty files or leaked reservations.
Atomic sector/stable media/exclusive writer assumptions and full IRQ-stack
bounds remain unproved. Observed native entry stack3160B FAT/3184B exFAT is NOT
a bound. Do not describe synthetic fixtures as complete mount/card acceptance.

## Documentation checkpoint — 2026-10-17

The retained 2026-10-12..16 project session is audited in
`docs/session-learnings-2026-10-12-to-16.md`. Current summary: local
`phase4j-release-candidate` (`219d972`) is offline-only and uninstalled;
20261110 remains the latest staged image. After that update the user reported a
startup hang/loop, then manually restarted and reached the menu with the named
Continue row. Do not mark its first boot as clean or its speed persistence as
hardware-accepted. New books previously copied to SD were found still needing
preparation; their current card state is unknown. Read `MASTERPLAN.md` for
current work and the incident record before any device operation.

Archive:builds/phase4j-auto-preparation-20261016/reviewed/manifest.json.
Custom20261114 SHA2569ed49a71ffafc11615e69165729e0378303d8211243bdff85c9b3d6bd9420792.
Stock recovery20261115 SHA2565d6a3bacc87321b32087f75559d28e44a233b0bf08cf88ac636b3a6efb986039.
About remainsP4e. phase4i-release-candidate stays atbac9473. No Nano access,
update staging, hardware acceptance, push or publication for this iteration.


## Long-audiobook offline RC — 2026-10-18

Phase4k candidate20261116/recovery20261117 adds hours on Now Playing and
best-effort five-minute existing-RSM Continue saving. Shared menu/launch path
storage frees512B; guards and ownership regressions cover pending/return states.
Payload26048text+29928BSS leaves328B below unchanged0309fff0; sector-rounded
text reservation has64B spare. Browser13956text/5320BSS. Loader boundaries,
bootloader and speed DSP unchanged. Isolated payload/image rebuilds match.

593 firmware tests passed in553.952s; after host output-seeking correction,
17 preparation/remux checks and120 BKZ tests pass. All four /revx reviewers
returned; confirmed findings fixed, Codex follow-ups approved naming preservation
and final seek commands. Sonnet reviewed the initial snapshot only; its rerun
was blocked by automatic approval. See archived review reports and dispositions.
Host exports use128kb/s CBR; embedded chapters become numbered MP3+BOOK.M3U.
Legacy exports preserve65-character names and state. No SD content changed.

Archive: builds/phase4k-long-books-20261018/reviewed/manifest.json.
Custom SHA256:0902a40a9df68b8badc63273c0c6d512ab2aae374be731913e42ac502fbe2f97
Recovery SHA256:004caf0875a3c3605f9e1dbd6733608544f5818493a90402091334867e91af0e
Offline RC only; no installation, publication, commit or push. First-update boot
anomaly and user-deferred Book C full restart remain unresolved. Hardware
clock legibility, autosave durability/audio timing and long-file seek acceptance
remain pending. Read docs/long-audiobook-followup.md for evidence and limits.


## Long-audiobook RC staged — 2026-10-18

User authorized firmware transfer. Fresh normal USB071b:3203 identification
linked internal disk6(262144000B) and SD disk7 to the same Nano. These disk
identifiers are historical. No leftover NANOV170.IMG existed in either root.
Archived custom20261116/recovery20261117 hashes, dates, duplicate headers and
CRCs verified. Exclusive internal copy, flush/sync and full byte-for-byte
readback succeeded:
0902a40a9df68b8badc63273c0c6d512ab2aae374be731913e42ac502fbe2f97.
Both volumes safely ejected. Evidence: builds/device-check/long-books-stage-20261018-135339/result.json.
No SD content changes, raw flash or bootloader operations. Installation and
first-post-update boot await user confirmation; hardware hours/autosave acceptance
and the deferred Book C full-restart issue remain open. Archived RC manifest
is preserved as the pre-staging checkpoint. No commit, push or publication.


## Verified preparation fallback correction — 2026-10-18

User reported Prepare failed / Use host tool for all books on20261116.
All11 inspected books retain M3U and CRC-valid RSM/BMK; all33 companions unchanged.
Small-file256KiB allocation suggests512-sector exFAT clusters, but raw boot-sector
reads were blocked by macOS even with approved administrator prompt. Do not claim
physical geometry confirmed. Offline512-sector native ARM fixture reproduces
preparation-1 while existing playlist lookup succeeds, with zero writes.

Candidate20261118/recovery20261119 bypasses automatic creation for clusters above
its scan bound and continues normal native/resident book entry. Guarded creation
limits unchanged. A separate real resident-menu diagnostic reaches Continue
with unchanged sectors.595 full tests passed in568.570s;18 focused tests and
scoped independent Codex review pass. This is not a new revx panel. Resident
26048text/29928BSS and browser13956text/5320BSS sizes unchanged; isolated paired
images reproduce byte for byte. Hardware retest pending.
Archive: builds/phase4k-long-books-20261018/prepare-fallback-reviewed/manifest.json.
Custom SHA256:ddc5d4dfddaf3b3d8cb2530ce27342d02a3201efbd9c4ae8dd3c28e92b12ad94
Recovery SHA256:42f989e92b443fb77b0cacd543c21770c33e82d92f32584edc444580a94edaf4
Screen redesign is pending; no book regeneration or state reset performed.


## Preparation fallback correction staged — 2026-10-18

Corrected20261118/recovery20261119 passed595 full tests in568.570s,18 focused
checks and scoped independent review. Fresh normal071b:3203 identification
reconfirmed internal disk6(262144000B) and SD disk7 on one Nano. These IDs are
historical. No leftover update existed. Both archived dates/hashes/CRC/header
copies verified; exclusive internal update copy, flush/sync and complete
byte-for-byte readback passed:
ddc5d4dfddaf3b3d8cb2530ce27342d02a3201efbd9c4ae8dd3c28e92b12ad94.
Both volumes safely ejected. Evidence: builds/device-check/prepare-fallback-stage-20261018-141657/result.json.
All33 book companions matched initial read-only snapshots before staging.
No SD content writes, raw flash or bootloader operations. Installation/boot and
book-opening retest remain pending. Physical card cluster size remains inferred;
user-approved raw geometry read was blocked by macOS. No hardware fix claimed.


## Hardware follow-up and audiobook screen work — 2026-10-18

User confirms 20261118 opens books and reports seeking beyond one hour seemed
to work. This is positive feedback, not exhaustive seek/startup acceptance.
The still-visible music icons and author row were expected in that candidate;
its Continue cache lasted only for the running session. The new offline
20261120/20261121 work addresses both: see
[book screen and durable Continue](docs/book-screen-and-continue.md).
No device operations or new installation occurred for this work.


## Final offline checkpoint — 20261120

All 611 regression tests passed in 616.628 seconds; 16 new focused checks also
passed. Fresh resident/browser/custom/recovery rebuilds match byte for byte.
Scoped independent rereview found no remaining concrete blocker after the two
scan failure corrections. Candidate 20261120 and stock recovery 20261121 are
archived at builds/phase4l-book-screen-20261018/reviewed/manifest.json.
Resident text/BSS 28008/28048 bytes leaves 248 bytes below unchanged 0x0309fff0.
No installation, commit or push; hardware UI/boot/Continue acceptance pending.
Legacy books need one successful playback save to establish a durable hint.


## Audiobook screen/Continue candidate staged — 2026-10-18

User authorized installation and connected Nano. Fresh normal USB071b:3203
linked internal disk6 (262144000B) and SD disk7 on the same device; identifiers
are historical. Archived custom20261120/recovery20261121 hashes, dates, CRCs
and duplicate headers verified. No existing update image in either root.
Exclusive internal copy, flush/sync and full byte-for-byte readback succeeded:
6efeeb926d1b41d77b33bbe5772052a7a90d39bb170aaf76ace53457c1308616.
Both volumes safely ejected. Evidence:
builds/device-check/book-screen-stage-20261018-1719/result.json.
No SD content changes, raw flash or bootloader operations. Installation and
first boot remain unconfirmed. Check book/chapter rows, removed heart/order
glyphs, and Continue after playing once and restarting. Last confirmed working
book opening remains20261118. Archive manifest retains its offline provenance.


## 20261120 hardware UI feedback — 2026-10-18

A user photo shows Book C playing with hours displayed and the new
book glyph, but stale author text and footer symbols. User confirms Continue
Book C works from the Audiobooks menu. This confirms the candidate ran;
first-post-update boot timing and a separate restart durability check were not
reported. The screen change is not accepted. Photo remains private/outside Git.

Offline reproduction found two mistakes in the initial UI checks: native dirty
events are consumed before the overlay runs; resource IDs were misidentified
(heart158/159 atx95, mode80 atx87, battery65+ atx115). The prior clear removed
the battery region instead of the heart. New checks use consuming native flags
and actual resource bitmaps. Blank artist redraw also needs marquee retirement
before the native blank paint. Work is combined with user-approved navigation
consistency changes; see docs/plans/2026-10-18-consistent-content-navigation.md.
No new device staging occurred during this correction.
# Offline consistent content navigation — 2026-10-18

Candidate20261122/recovery20261123 fixes the photographed stale author/footer
display using native marquee ownership and actual resource positions. Chapter
text starts at x0; the book glyph is revised; heart/mode pixels clear while
battery remains. Menu order is Now Playing, Audiobooks, Meditations, Music
Library, Folders, Shuffle, Playback Settings, System Settings (marked categories
remain conditional). Now Playing opens current audio. Direct chapter selection
under marked audiobook ancestry resolves unique membership in BOOK.M3U, bounded
at the marked root; custom M3Us remain explicitly selectable. Meditation M3Us
retain ordinary track behavior and do not replace audiobook Continue.

All611 tests passed in619.562s plus72 focused checks. Scoped independent
rereview found no remaining concrete blocker after handoff-return and blank
artist lifecycle fixes. No new revx panel or hardware acceptance. Rebuilds were
byte-identical; both images pass CRC/duplicate-header checks. Resident text/BSS
27952/27952 leaves400B below the unchanged boundary; browser13960/5320 unchanged.
See docs/content-navigation-followup.md for limits and device checklist.
Archive: builds/phase4m-content-navigation-20261018/reviewed/manifest.json.
Custom SHA256:84f78dea227b030734c34f2eae8398efe354040ca36f35592e1782bd63e74b67
Recovery SHA256:650fde2891e65a11c9b5ce116a89e84fd61151cf523eb964f88d7b32a6927615
No device staging, commit or push.20261120 is the last photographed running
candidate; its Continue menu works but screen acceptance failed.

## Content navigation candidate staged — 2026-10-18

User authorized installation. Fresh normal USB071b:3203 identification linked
internal disk5(262144000B) and SD disk6 to the same Nano; IDs are historical.
Archived custom20261122/recovery20261123 passed hash/date/CRC/duplicate-header
checks. Neither root contained an existing update image. Exclusive internal
copy, flush/sync and complete byte-for-byte readback succeeded:
84f78dea227b030734c34f2eae8398efe354040ca36f35592e1782bd63e74b67.
Both volumes safely ejected. Evidence:
builds/device-check/content-navigation-stage-20261018-193547/result.json.
No SD content changes, raw flash or bootloader operations. Installation and
first boot await user observation; screen/menu/folder acceptance is pending.
20261120 remains the last photographed running candidate. No commit or push.
