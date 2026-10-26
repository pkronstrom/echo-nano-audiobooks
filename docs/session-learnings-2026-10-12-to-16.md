# Echo Nano session learning audit — 12–16 October 2026

This audit compares the saved Echo Nano project conversation with the current
source, local tags, candidate manifest, and project documentation. It covers
the user decisions, implementation outcomes, hardware observations, and the
limits that should carry into later work. The detailed technical evidence stays
in the linked investigation and device records.

## Current source and device state

- Local `phase4i-release-candidate` points to `bac947351396fa21e66eb8606f96a67da65cd872`;
  local `phase4j-release-candidate` points to `219d972c299c5129bd19a9116ed03bfdd4f29176`.
  Both tags are preserved locally. Neither has been pushed or published.
- The phase4j manifest pairs custom date 20261114 and stock recovery date
  20261115. Custom SHA256 is
  `9ed49a71ffafc11615e69165729e0378303d8211243bdff85c9b3d6bd9420792`; recovery
  SHA256 is `5d6a3bacc87321b32087f75559d28e44a233b0bf08cf88ac636b3a6efb986039`.
  The candidate passed 578 offline tests, scoped independent reviews, and
  isolated reproducible image builds. It is **not staged, installed, or
  hardware accepted**. The manifest is
  `builds/phase4j-auto-preparation-20261016/reviewed/manifest.json`.
- The 20261110 startup/speed image was staged to internal storage and fully
  readback-verified. After the update, the user reported a startup hang/loop,
  then restarted the player and reached the menu; the named Continue row was
  visible. This records a successful post-restart menu, not a confirmed clean
  first boot. Per-book speed persistence was not accepted on hardware.
- Earlier hardware feedback confirms the P4a candidate boot-looped and the
  menu-bypass diagnostic froze after Shuffle. Stock application recovery
  returned the normal menu. Later, the 20261025 packet/menu build was reported
  booting with its speed crackle fixed, and its roughly two-second Audiobooks
  and three-second Meditations opening times were accepted as tolerable. These
  results do not validate later images.
- A later SD inspection found newly copied books still needed preparation.
  No subsequent completion was recorded. Check the actual card before assuming
  its playlists or state companions exist. The phase4j feature is not installed
  and does not convert audio.

## Decisions and where they are documented

| Session learning or decision | Current record |
| --- | --- |
| Keep Music, Audiobooks, and Meditations as parallel collections; use `.audiobook` and `.meditation` root markers to show menus and exclude category trees from Music after refresh. | [Music separation](music-separation.md), [audiobook setup](audiobooks.md) |
| Preserve explicit M3U order; sort native folder listings naturally and make folder playback follow the visible order. Folder queues are RAM-only and must be rebuilt after restart. | [Folder sorting](folder-sorting-investigation.md), [native audit](folder-sort-native-audit.md) |
| A book's resume and bookmarks belong on its SD card. Prepared RSM/BMK files have checksummed journal formats; do not make empty files by hand. The phase4j candidate can create missing companions only inside its supported scope. | [Bookmark storage](bookmark-storage.md), [automatic preparation](automatic-book-preparation.md) |
| Book navigation includes Continue, Chapters, and Bookmarks; Previous/Next seek within the current chapter; Bookmarks is available through the player menu. Meaningful chapter titles are still outstanding. | [Player controls](audiobook-player-controls.md), [book menu](book-menu-implementation.md) |
| Speed presets are approximate, performance-prioritized MP3 support. Speed is saved with normal per-book resume state; unsupported codecs remain at 1x. The optional 0.75x rate was deferred because it needs period insertion and new source-time/buffer guarantees. | [DSP investigation](stock-pcm-speed-investigation.md), [per-book speed](per-book-speed.md), [device test](speed-device-test.md) |
| The user's long first-start concern is not fully explained by the reproduced retained-RAM hazard. The 20261110 invalidation fix has not had a clean first-boot hardware acceptance. | [Startup investigation](update-startup-investigation.md), [incident record](device-test-and-restore.md) |
| Automatic book preparation must preserve existing playlists and state, validate writes by reopening and reading them, and fail safely on unsupported storage layouts. Interrupted creation may leave partial owned files or leaked clusters; it does not repair or retry them. | [Feasibility investigation](automatic-book-preparation-investigation.md), [current behavior and limits](automatic-book-preparation.md) |
| No bootloader changes are part of the current candidates. That does not guarantee recovery from an application boot failure. Re-identify USB and mounted disks each time; never treat the 476 MiB logical backup as a full-chip backup. | [Recovery lessons](recovery-lessons-2026-10-14.md), [factory loader analysis](factory-loader-analysis.md) |
| The main user-facing claims must distinguish host tests, scoped review, staged images, and observed hardware behavior. A review or emulator pass does not establish hardware safety. | [Incident record](device-test-and-restore.md), [release guidance](releases.md) |

## Implementation discoveries worth retaining

- The original P4a failure was traced to a sector-rounded loader read: the
  stock byte reader mishandled a partial tail, corrupting the loaded payload
  while reporting success. Exercise the real byte reader at non-sector-aligned
  lengths when testing injected code; mocking only the sector layer hid this
  failure. See [P4a investigation](p4a-bootloop-investigation.md).
- A later startup hazard came from accepting a retained `ENP2` header for an
  older payload. This failure was reproduced offline and addressed by clearing
  the readiness marker at a pinned application entry. The full physical
  update/reset/retained-RAM chain is still unproven; see the startup record.
- Accelerated audio crackled even with EQ disabled. Short, variable DSP packets
  were implicated, and packet coalescing fixed the reported crackle on an
  earlier candidate. Do not raise clocks or buffer sizes without a diagnosis;
  the newer speed path needs its own listening acceptance.
- Natural sorting initially broke exFAT selection because native short aliases
  include a changing clock suffix. Compare stable metadata and the full name,
  while ignoring only those synthetic alias bytes. Later, display sorting alone
  left playback in physical order; the sorted identities must reach the
  playback queue too. See [native folder audit](folder-sort-native-audit.md).
- The playback payload reached zero static margin at the established upper
  boundary. The browser helper has 168 bytes of measured static margin, and
  observed FAT/exFAT stack peaks are not a complete IRQ-stack bound. Free space
  before adding resident state; do not widen audited memory boundaries. See
  [playback memory layout](playback-memory-layout.md) and
  [automatic preparation](automatic-book-preparation.md).

## Remaining checks

1. For a future update, observe and record the first automatic boot before
   pressing Power/reset.
2. Test the phase4j candidate on hardware only after following the current
   recovery and device-identification instructions. Include supported and
   unsupported media layouts, reopen verification, and preservation of existing
   playlists/state.
3. Verify speed save/reopen/restart, audio quality, bookmarking, and seek/menu
   behavior on the installed candidate. Keep results tied to an exact image hash.
4. Recheck the newly copied books on the card and prepare unsupported formats
   or names using the documented host workflow. Do not assume automatic
   preparation from source code has already changed SD contents.
5. A hosted draft-release workflow run and public release are not recorded.

The original 12 October plan and older milestone notes remain useful as history;
use [MASTERPLAN.md](../MASTERPLAN.md) for current status. The requested session
ID supplied for this audit had no saved turns after `/clear`; the retained
Echo-Nano history used here is the project conversation from 12–16 October.
