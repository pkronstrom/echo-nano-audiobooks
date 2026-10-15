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
contained BOOK.M3U and BOOK.RSM but no BOOK.BMK for Bhagavad Gita. The other
four prepared test-book folders also had no BMK. The firmware requires a
preallocated companion; missing storage makes saving fail without visible feedback.
This establishes a storage prerequisite failure, not that the physical gesture works.

Preserved Bhagavad playlist/resume under ignored
builds/device-check/bookmark-investigation-20261015/. Both resume sectors have
valid CRCs. Ran the preparation tool for Bhagavad only; created 1024-byte BMK
with two valid empty ENB1 sectors, flushed and read back. M3U and RSM remained
byte-identical. No audio or firmware was changed. Other test books still need
preparation before bookmark tests. Device retest: reopen Bhagavad BOOK.M3U,
start playback, double Previous, wait briefly, Back then Bookmarks.

Lesson: installing bookmark-capable firmware does not retrofit companion files
onto previously prepared books. Verify preparation prerequisites before gesture
diagnosis; future UI should distinguish missing storage from an empty journal.


## Bookmark hardware retest passed — 2026-10-15

After adding Bhagavad's missing BOOK.BMK, the user confirmed bookmarks work.
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
bookmark gesture on Ichigo showed a black screen for about a second. Whether
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
Hemi-Sync CD2-3 appearsbeforeCD1-1. See docs/folder-sorting-investigation.md.

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
Hemi-Sync ordering, selected-file identity and Back acceptance await user test.
No commit or push for this iteration.

## Hardware regression — folder-sort20261102

User reports Enter on Meditations / The Gateway Experience does nothing.
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
The Gateway Experience folder entry await user confirmation. DiskID historical.
