# P4a first device test and stock restore

Prepared 2026-10-14 for the HW1.0.0 / SW1.7.0 Nano tested in this workspace.

**Outcome: stock normal menu restored and confirmed by the user. P4a failed
hardware boot acceptance.** Read [the consolidated recovery lessons](recovery-lessons-2026-10-14.md).
The installation procedure below is a historical record, not authorization to
repeat the failed P4a test. Later incident entries supersede earlier pending status.

## Evidence and limits

Physical Previous/Up + USB recovery entry and return to the normal menu were
observed. Read-only USB access works on this Mac with 32-sector requests.
The retained 476 MiB logical image contains two stock-matching application
regions and the entire declared FAT volume. Four independent spot checks passed.
The factory loader's device-type-3 read/write mapping adds a 4 MiB prefix;
installed-loader identity and actual USB restoration remain untested.
This is not a bootloader backup or a guaranteed unbrick procedure.

## First installation

1. Leave the SD card out for the initial boot test. Exit recovery by unplugging,
   holding Power for about 10 seconds if needed, then boot normally.
2. Connect normally so internal storage mounts. Identify the Nano by USB identity,
   volume and capacity; do not assume a persistent disk number.
3. Inspect the volume root for existing update images before copying anything.
   Preserve existing files; do not overwrite an unexpected image silently.
4. Copy `builds/phase4a/custom/NANOV170.IMG` to the internal-storage root.
   Expected SHA256: `01c28d12759aea3f93125e4168c9044e8a324f3eead875bb52ae04834aa4b494`.
   Compare the destination hash, safely eject, then restart with adequate battery.
   Do not interrupt an update indication.
5. Check About for P4a, inspect icons and navigate the ordinary menus before
   adding the SD card. Continue with `builds/phase4a/DEVICE-TEST.md` for audio,
   marker menus, chapter order and resume acceptance checks.

## Stock restore when normal USB storage works

Use `builds/phase4a/recovery/NANOV170.IMG`, SHA256
`b251de1eb74e9e3eea9a206cf9a0a034a8371f57265e959c733bb8ae2e62d57d`.
It contains stock code with date 20261014, later than P4a's 20261013.
Copy it to internal-storage root as NANOV170.IMG, replacing the known P4a
update file if still present. Verify the destination hash, safely eject and
restart. Confirm the stock menu/version. This procedure is prepared but has
not been exercised on this unit. After restoring it, a later custom test needs
a suitably later build date.

## If normal boot or USB storage fails

Correction: holding Power for about 10 seconds forces a restart; it does not
guarantee power-off. Previous/Up held before USB insertion worked in an earlier
powered-off test. The precise successful gesture during the later boot loop is
not established. Verify recovery by USB enumeration, not screen appearance.
Approve the Mac accessory if prompted.
Use only read-only detection first; expected recovery USB identity is2207:262d.
The recovery diagnostic executable rejects all commands except ld/rci/rfi/rl.

Stop before any recovery write: the exact installed-loader write path and
rollback behavior have not been hardware-validated. Do not bulk-restore the
476 MiB file, erase flash, send a factory loader, or substitute a physical-zero
write for logical-zero. Recovery enumeration is established; a complete
emergency restore procedure is not yet established.

## First hardware result — 2026-10-14

P4a was copied to the identified normal USB volume, destination SHA256 verified,
and the volume safely ejected. The user observed the firmware update screen,
then recurring logo animation with approximately 30-second pauses. P4a boot
acceptance failed; the cause is not yet established. Normal USB storage still
mounted when reconnected (071b:3203). The update image was no longer present.
The verified stock recovery image was then staged and the volume safely ejected.
Stock restoration and successful normal boot still await user observation.
Do not reuse this P4a image for another device test before investigating the failure.

Recovery USB access was regained after the subsequent button/reset attempts;
the exact successful gesture is not yet confirmed. Device 2207:262d Loader,
chip and flash info unchanged. Read-only 16 KiB samples at logical LBA0 and
26624 both match P4a exactly (date bytes 26201310), not the stock restore image.
Therefore the later-dated restore is not present in either sampled header.
Evidence: builds/device-check/post-bootloop-20261014-125232/results.json.
This establishes recovery survived the P4a boot failure; no recovery writes
have yet been performed. Next step is a bounded application-only stock restore
proposal with exact bytes/addresses and readback verification, preserving the
reserved prefix and user filesystem.

## Application-only recovery write — 2026-10-14

Before writing, both full 11 MiB application extents were independently read
and preserved under `builds/device-check/restore-preflight/before-*.bin`.
Both matched P4a exactly (payload SHA256
8899c4c5d9aac0e07e978d3826c132005268b3127b651995378e8219a8ea310d).

Restored the date-adjusted stock recovery's first 11 MiB (excluding its four-byte
package CRC trailer), first at logical LBA26624, then LBA0. Each extent is22528
sectors. Each write used opcode0x15 in at-most32-sector requests and was followed
by a complete, byte-for-byte readback before advancing. Both passed. Payload SHA256:
`8e931d60a034055fd0350004edbf00eb9151689d00ca0e58e625aaac1ffff51f`.

The isolated restore executable rejects commands other than `wl`, start LBAs
other than0/26624, and input lengths other than11MiB. Its communication layer
bounds every write to the two application extents, rejects zero/over32-sector
transfers and nonzero subcodes, and treats every nonzero CSW status as failure.
The Python runner pins the payload digest, device identity, pre-write backups,
and requires verified second-region success before restoring the first.
No erase, reset, loader-download or filesystem-write command was issued.

Evidence: `restore-preflight/restore-26624.json`, `restore-0.json`, complete
write/readback logs and before/after binaries. Writer SHA256
`8ecda97d0c98f1cba87c1b57c32ce845781d4cfb3440fd11fed87798662a5f4b`.
Six invalid-command/file guard checks passed before device use. This is local
recovery tooling, not yet a portable/publicly supported restore utility.

Both application regions now match the prepared stock recovery payload; actual
normal boot is still pending user observation. No further USB operations are running.


## User-confirmed recovery outcome

After both application regions were restored and fully read back, the user
reported another firmware-update screen, followed by: "works. now back on normal
menu." Stock normal boot is therefore confirmed. The extra update likely used
the previously staged stock file; that file was not inspected afterward.
About/version and post-recovery audio playback have not yet been rechecked.
Preserve the working stock state; investigate P4a offline before further tests.


## Book-menu candidate staged — 2026-10-15

User connected the Nano for the proposed controlled test. Normal USB071b:3203
was identified at location02100000; disk5/internal262144000-byte media matched.
No NANOV170.IMG was present. Preserved CFWLOG.TXT, verified both archived package
hashes and CRC/header copies, exclusively created the custom update file, flushed
and read back SHA256 f6be6580d9705a23874d7abb09abe5fdc4d70aaa74bcf0469b584039c630bd4c.
Disk5 ejection succeeded. Custom date20261019; later stock recovery20261020 remains
on the computer. Evidence: builds/device-check/book-menu-stage-20261015-122113/.
Installation, boot and menu acceptance await user observation. No raw flash or
bootloader operation occurred. Device identifiers above are historical, not reusable.


## Book-menu hardware feedback — 2026-10-15

User confirmed normal boot of staged f6be6580…bd4c, saw Continue1 00:02:54 and
Chapters, then confirmed Continue resumed chapter2. This is partial hardware
acceptance, not complete acceptance. New defects/requests:

- Double Previous produces no visible action; bookmark saving is not confirmed.
  Double Forward activates the spectrum display. Gesture recognition exists,
  but neither callback execution nor BMK presence/validity is proven on device.
  SD is not mounted on the Mac at this observation; inspect test-book M3U/RSM/BMK
  before attributing the issue to the gesture or journal.
- Main Music Playback reopens the audiobook. The shared native player and
  playback_begin(NULL) preserve active book state. Separate music resume is
  needed; merely clearing playback_active would leave native book state and
  must not be treated as a fix.
- Audiobooks should offer Continue last book as its first item, separate from
  the per-book Continue action, and prepared book folders should open the book
  menu without locating the M3U at the bottom of the ordinary listing.
- The main-button double-click opens native sound settings. User favors an
  audiobook-only Speed item there; pitch-preserving support remains unproven.

No new firmware was staged after these reports. Preserve the installed test
build and companion evidence while diagnosing bookmarks.


## Missing bookmark companion — 2026-10-15

Connected Music SD (UUID693B8030-CB7E-32AE-999B-5D186782949A, Secure Digital)
contained BOOK.M3U and BOOK.RSM but no BOOK.BMK for Book A. The other
four prepared test-book folders also had no BMK. The firmware requires a
preallocated companion; missing storage makes saving fail without visible feedback.
This establishes a storage prerequisite failure, not that the physical gesture works.

Preserved Book A playlist/resume under ignored
builds/device-check/bookmark-investigation-20261015/. Both resume sectors have
valid CRCs. Ran the preparation tool for Book A only; created 1024-byte BMK
with two valid empty ENB1 sectors, flushed and read back. M3U and RSM remained
byte-identical. No audio or firmware was changed. Other test books still need
preparation before bookmark tests. Device retest: reopen Book A BOOK.M3U,
start playback, double Previous, wait briefly, Back then Bookmarks.

Lesson: installing bookmark-capable firmware does not retrofit companion files
onto previously prepared books. Verify preparation prerequisites before gesture
diagnosis; future UI should distinguish missing storage from an empty journal.


## Bookmark hardware retest passed — 2026-10-15

After adding Book A's missing BOOK.BMK, the user confirmed bookmarks work.
The user also confirmed there is no visible feedback when pressing the shortcut.
Bookmark creation/gesture is therefore hardware-confirmed for this test; visible
save confirmation remains a UX issue. This does not establish every bookmark
operation (deletion, cross-chapter jumps, persistence after restart) as tested.
The missing companion, rather than a proven broken button hook, blocked the
earlier test. Other previously prepared books still need BMK companions.


## Corrected P4e speed candidate staged — 2026-10-15

User connected the Nano after accepting the controlled test steps. Fresh USB
identification:071b:3203 ECHO NANO at02100000; internal disk7 (262144000 bytes),
SD disk8 on the same USB device. Internal FAT32 mounted at/Volumes/ECHO NANO;
SD UUID693B8030-CB7E-32AE-999B-5D186782949A. These identifiers are historical.
Neither root contained NANOV170.IMG; the existing internal AppleDouble sidecar
was preserved. CFWLOG.TXT and root listing were saved before staging.

Both archived corrected P4e and later stock-recovery hashes, dates, duplicate
headers and package CRCs verified. Exclusively created internal NANOV170.IMG,
flushed, synced and read back byte-for-byte:
`e40a2e82d53e959126e6d1e85658382dacc4ea38bb2b9c9aab3e5c9ef31210be`,
11534340 bytes, date20261023/About P4e. Recovery20261024 remains on the computer
(SHA2563fae8497208ca04284d2d0b02f1ce4faf65f27bb8913aced32d5a6ac2e30be30).
Both SD disk8 and internal disk7 ejected successfully. No SD file changes, raw
flash writes, loader downloads or bootloader operations were performed.

Evidence:builds/device-check/p4e-stage-20261015-184155/. Installation, normal
boot and audio/speed acceptance await user observation. Last confirmed installed
build remains20261019 until that confirmation.


## P4e hardware result: boots, accelerated audio crackles

User initially suspected a boot loop, then confirmed the normal menu appeared.
Corrected P4e e40a2e82…1210be therefore has observed boot acceptance. User
reports1.5x and2x speed processing works but has considerable crackle; explicitly
confirmed1x plays cleanly. Accelerated audio acceptance FAILED. Replaying to
apply the preferred speed is observed and matches the current launch-latched
behavior. Do not present this candidate as ready for normal audiobook use.

No recovery write was attempted. No newer firmware was staged. Investigate
actual produced packet sizes, native effects behavior and CPU/codec deadlines
before another candidate. EQ-off comparison requested, result pending.

EQ-off follow-up: user confirmed accelerated playback remains crackly with EQ
off. This strengthens the scheduling/short-packet lead; it is not proof of
actual hardware underruns or measured CPU capacity.

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

Hardware follow-up: user reports “that fixed it” after testing the20261025
packet/menu candidate. This is a positive device result, but whether it refers
to accelerated-audio crackle, menu latency, or both awaits clarification. Do
not mark both acceptance items passed yet or infer every speed was tested.

## Hardware feedback — 2026-10-15, packet/menu build

User clarified accelerated crackle was fixed; category menus still take about
2s Audiobooks/3s Meditations and user considers this tolerable. Double Previous
bookmark gesture on Book B showed a black screen for about a second. Whether
confirmation text appeared and bookmark persisted awaits clarification.

feedback.c paint clears all640 framebuffer bytes, renders a confirmation and
transfers the whole128x32 display; popup lasts150 native ticks (~1.5s). This
explains the screen replacement/timing, but does not prove why it looked black.
Existing tests substitute the native font renderer; they cannot establish
visible glyphs. Investigate native rasterization/render state before patching.

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

## Startup/speed candidate result — 2026-10-16

User reported the first startup after the 20261110 update felt like a boot loop.
After manually restarting, the Nano reached the normal menu. The user then
observed the named Continue row. The report does not establish whether the first
attempt showed repeated logo animation, a static logo, or an update screen, and
it is not a clean first-boot pass. Keep the retained-RAM fix classified as a
reproduced offline hazard with unresolved hardware causality. The durable
per-book speed behavior was not accepted in this test.

The later 20261114 / recovery20261115 phase4j pair is an offline candidate only;
it was not staged or installed during this session. See
[automatic preparation](automatic-book-preparation.md) and its exact manifest
before treating that image as a test candidate. No new device operations,
hardware acceptance, push or publication were recorded after the 20261110 stage.

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


## Hardware preparation regression — 2026-10-18

After staging20261116, user reached Audiobooks and reports all books display
Prepare failed / Use host tool. Do not treat book-opening acceptance as passed.
Fresh normal USB071b:3203 links internal disk6 and SD disk7 (historical IDs).
Read-only inspection found all11 books have M3U and1024-byte RSM/BMK with both
sector CRCs valid. No BOOK.TMP files observed. Existing Nano diagnostic log has
no preparation result codes. Update image has been consumed; exact installed
application bytes and first-update boot sequence were not independently read.

Small companion allocation is262144B each, suggesting512-sector exFAT clusters.
Raw boot-sector access remains macOS-blocked even after user-approved admin
prompt; do not claim confirmed physical geometry. Offline512-sector native ARM
fixture reproduces preparation-1 despite readable BOOK.M3U and zero writes.
Narrow source correction treats clusters outside preparation's bound as a
no-write bypass to normal book/native entry. Creation limits remain unchanged.
18 focused checks pass; full checks/review in progress. New offline pair
20261118/19 not staged. Device audio/state unchanged during investigation.
Evidence: builds/device-check/prepare-failure-20261018-140137/investigation.json.


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
[book screen and durable Continue](book-screen-and-continue.md).
No device operations or new installation occurred for this work.


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
